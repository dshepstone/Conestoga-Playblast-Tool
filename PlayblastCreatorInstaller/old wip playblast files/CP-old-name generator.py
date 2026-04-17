import os
import time
import shutil
import types  # Needed for the UI integration
import math
import subprocess
import maya.cmds as cmds
import maya.mel as mel
import maya.OpenMayaUI as omui
from shiboken6 import wrapInstance
from PySide6 import QtWidgets, QtCore, QtGui

def get_camera_shape(camera):
    """
    Get the camera shape node from either a transform or shape node.
    Returns None if not a valid camera.
    """
    if not cmds.objExists(camera):
        cmds.warning(f"Camera does not exist: {camera}")
        return None
    print(f"Checking camera: {camera}, type: {cmds.nodeType(camera)}")
    if cmds.nodeType(camera) == "transform":
        shapes = cmds.listRelatives(camera, shapes=True, noIntermediate=True) or []
        for shape in shapes:
            print(f"  Found shape: {shape}, type: {cmds.nodeType(shape)}")
        camera_shapes = [s for s in shapes if cmds.nodeType(s) == "camera"]
        if camera_shapes:
            return camera_shapes[0]
        else:
            cmds.warning(f"No camera shape found under transform: {camera}")
    elif cmds.nodeType(camera) == "camera":
        return camera
    else:
        cmds.warning(f"Node is not a camera or camera transform: {camera}")
    return None

def remove_user_text(nodes):
    """
    Remove the 3D text and all related nodes.
    """
    try:
        if not nodes:
            return
        text_group, pos_cam, white_shader, bg_shader = nodes
        if cmds.objExists(text_group):
            cmds.delete(text_group)
        if cmds.objExists(pos_cam):
            cmds.delete(pos_cam)
        if cmds.objExists(white_shader):
            cmds.delete(white_shader)
        if cmds.objExists(bg_shader):
            cmds.delete(bg_shader)
    except Exception as e:
        cmds.warning(f"Failed to clean up artist text: {str(e)}")

def adjust_shot_mask_visibility():
    """
    Helper function to adjust shot mask visibility and properties.
    Use this to troubleshoot if the mask is not visible.
    """
    try:
        if cmds.objExists("shotMask_BgMaterial"):
            cmds.setAttr("shotMask_BgMaterial.transparency", 0, 0, 0, type="double3")
        for text in ["shotMask_SceneText", "shotMask_ArtistText", "shotMask_DateText", "shotMask_FPSText", "shotMask_FrameText"]:
            if cmds.objExists(text):
                cmds.setAttr(f"{text}.scaleX", 0.02)
                cmds.setAttr(f"{text}.scaleY", 0.02)
                cmds.setAttr(f"{text}.scaleZ", 0.02)
        if cmds.objExists("shotMask_MainGroup"):
            cmds.setAttr("shotMask_MainGroup.translateZ", -0.5)
        if cmds.objExists("shotMaskLayer"):
            cmds.setAttr("shotMaskLayer.visibility", 1)
            cmds.setAttr("shotMaskLayer.displayType", 0)
        print("Shot mask adjusted for better visibility")
        return True
    except Exception as e:
        print(f"Error adjusting shot mask: {str(e)}")
        return False

def parent_annotation(ann, plane, text_size=2.0):
    """
    Properly parent an annotation to a plane and set its scale.
    """
    # Determine the annotation transform and shape
    ann_shape = None
    if cmds.objectType(ann) == "annotationShape":
        ann_shape = ann
        ann_tr = cmds.listRelatives(ann_shape, parent=True)[0]
    else:
        ann_tr = ann
        shapes = cmds.listRelatives(ann_tr, shapes=True, type="annotationShape")
        if shapes:
            ann_shape = shapes[0]
        else:
            cmds.warning(f"No annotation shape found for {ann}")
            return None

    # IMPORTANT: Directly set the fontSize attribute if possible
    if ann_shape:
        # Try all possible attribute combinations until one works
        if cmds.attributeQuery("fontSize", node=ann_shape, exists=True):
            cmds.setAttr(f"{ann_shape}.fontSize", text_size)
            print(f"Set fontSize to {text_size} on {ann_shape}")
        elif cmds.attributeQuery("textScale", node=ann_shape, exists=True):
            cmds.setAttr(f"{ann_shape}.textScale", text_size)
            print(f"Set textScale to {text_size} on {ann_shape}")
        elif cmds.attributeQuery("fontScale", node=ann_shape, exists=True):
            cmds.setAttr(f"{ann_shape}.fontScale", text_size)
            print(f"Set fontScale to {text_size} on {ann_shape}")
        
        # Also try to override the display scale of the annotation
        try:
            # Force font size with MEL command (works in some Maya versions)
            mel.eval(f'setAttr "{ann_shape}.displayTextSize" {text_size};')
        except:
            pass
            
    # Position at plane
    plane_pos = cmds.xform(plane, query=True, worldSpace=True, translation=True)
    cmds.xform(ann_tr, worldSpace=True, translation=[plane_pos[0], plane_pos[1], plane_pos[2] + 0.01])
    
    # IMPORTANT: Also scale the annotation transform directly
    # This can help overcome font size limitations
    scale_factor = text_size / 2.0  # Adjust this ratio as needed
    cmds.setAttr(f"{ann_tr}.scaleX", scale_factor)
    cmds.setAttr(f"{ann_tr}.scaleY", scale_factor)
    cmds.setAttr(f"{ann_tr}.scaleZ", scale_factor)
    
    # Disable unwanted visual elements
    if ann_shape:
        if cmds.attributeQuery("displayArrow", node=ann_shape, exists=True):
            cmds.setAttr(f"{ann_shape}.displayArrow", 0)
        if cmds.attributeQuery("worldSpace", node=ann_shape, exists=True):
            cmds.setAttr(f"{ann_shape}.worldSpace", 0)
    
    # Return the transform for group parenting
    return ann_tr

def create_shot_mask(camera, user_name, scene_name=None, frame_rate=None, text_scale=0.02, annotation_size=2.0):
    """
    Create a professional-looking shot mask with project info.
    Uses polygon planes with shader overrides for performance.
    
    Args:
        camera: Camera to attach the mask to.
        user_name: Artist name to display.
        scene_name: Optional scene name (defaults to current file).
        frame_rate: Optional frame rate (defaults to current fps).
        text_scale: Scale factor for the text group (defaults to 0.02).
        annotation_size: Size of the annotation text (defaults to 2.0).
        
    Returns:
        List of created nodes for cleanup.
    """
    try:
        # Clear any existing shot mask.
        existing_groups = cmds.ls("shotMask_*")
        for group in existing_groups:
            if cmds.objExists(group):
                cmds.delete(group)
                
        if not scene_name:
            scene_path = cmds.file(query=True, sceneName=True) or "Untitled Scene"
            scene_name = os.path.basename(scene_path).split('.')[0]
        if not frame_rate:
            fps = cmds.playbackOptions(query=True, fps=True)
            frame_rate = f"{int(fps)} fps"
        
        import datetime
        current_date = datetime.datetime.now().strftime("%Y-%m-%d")
        currentFrameValue = int(cmds.currentTime(query=True))
        
        camera_shape = get_camera_shape(camera)
        if not camera_shape:
            cmds.warning(f"Invalid camera for shot mask: {camera}")
            return []
        if cmds.nodeType(camera_shape) == "camera":
            transforms = cmds.listRelatives(camera_shape, parent=True, fullPath=True)
            if transforms:
                camera_transform = transforms[0]
            else:
                cmds.warning(f"Failed to get transform for camera: {camera_shape}")
                return []
        else:
            camera_transform = camera
            
        print(f"Setting up shot mask for camera: {camera_transform}")
        
        if not cmds.objExists("shotMaskLayer"):
            cmds.createDisplayLayer(name="shotMaskLayer", empty=True)
            cmds.setAttr("shotMaskLayer.visibility", 1)
            cmds.setAttr("shotMaskLayer.displayType", 0)
        
        main_group = cmds.group(empty=True, name="shotMask_MainGroup")
        
        bg_plane = cmds.polyPlane(name="shotMask_Plane", width=1.8, height=0.2, subdivisionsX=1, subdivisionsY=1)[0]
        cmds.setAttr(f"{bg_plane}.rotateX", 90)
        
        scene_plane = cmds.polyPlane(name="shotMask_SceneTextPlane", width=0.3, height=0.04, subdivisionsX=1, subdivisionsY=1)[0]
        cmds.setAttr(f"{scene_plane}.translateX", 0.6)
        cmds.setAttr(f"{scene_plane}.translateY", -0.05)
        cmds.setAttr(f"{scene_plane}.translateZ", 0.01)
        
        user_plane = cmds.polyPlane(name="shotMask_ArtistTextPlane", width=0.3, height=0.04, subdivisionsX=1, subdivisionsY=1)[0]
        cmds.setAttr(f"{user_plane}.translateX", -0.6)
        cmds.setAttr(f"{user_plane}.translateY", -0.05)
        cmds.setAttr(f"{user_plane}.translateZ", 0.01)
        
        date_plane = cmds.polyPlane(name="shotMask_DateTextPlane", width=0.3, height=0.04, subdivisionsX=1, subdivisionsY=1)[0]
        cmds.setAttr(f"{date_plane}.translateX", -0.6)
        cmds.setAttr(f"{date_plane}.translateY", 0.05)
        cmds.setAttr(f"{date_plane}.translateZ", 0.01)
        
        fps_plane = cmds.polyPlane(name="shotMask_FPSTextPlane", width=0.3, height=0.04, subdivisionsX=1, subdivisionsY=1)[0]
        cmds.setAttr(f"{fps_plane}.translateX", 0.6)
        cmds.setAttr(f"{fps_plane}.translateY", 0.05)
        cmds.setAttr(f"{fps_plane}.translateZ", 0.01)
        
        frame_plane = cmds.polyPlane(name="shotMask_FrameTextPlane", width=0.3, height=0.04, subdivisionsX=1, subdivisionsY=1)[0]
        cmds.setAttr(f"{frame_plane}.translateX", 0)
        cmds.setAttr(f"{frame_plane}.translateY", 0)
        cmds.setAttr(f"{frame_plane}.translateZ", 0.01)
        
        # Group text planes into a text group
        text_group = cmds.group([scene_plane, user_plane, date_plane, fps_plane, frame_plane], name="shotMask_TextGroup")
        
        # Make planes transparent
        for plane in [scene_plane, user_plane, date_plane, fps_plane, frame_plane]:
            # Set visibility to 0 but ensure annotations stay visible
            shapes = cmds.listRelatives(plane, shapes=True, noIntermediate=True) or []
            
            for shape in shapes:
                try:
                    if cmds.attributeQuery("visibility", node=shape, exists=True):
                        cmds.setAttr(f"{shape}.visibility", 0)
                except:
                    pass
            
            # Use a transparent material
            mat_name = f"{plane}_invisMat"
            invis_material = cmds.shadingNode("lambert", asShader=True, name=mat_name)
            cmds.setAttr(f"{invis_material}.color", 0, 0, 0, type="double3")
            cmds.setAttr(f"{invis_material}.transparency", 1, 1, 1, type="double3")
            
            # Create shading group
            sg_name = f"{mat_name}SG"
            sg = cmds.sets(name=sg_name, renderable=True, noSurfaceShader=True, empty=True)
            cmds.connectAttr(f"{invis_material}.outColor", f"{sg}.surfaceShader", force=True)
            
            # Assign material
            cmds.sets(plane, edit=True, forceElement=sg)
        
        # Set up background material
        bg_material = cmds.shadingNode("lambert", asShader=True, name="shotMask_BgMaterial")
        cmds.setAttr(f"{bg_material}.color", 0.1, 0.1, 0.1, type="double3")
        cmds.setAttr(f"{bg_material}.transparency", 0.25, 0.25, 0.25, type="double3")
        
        # Set up text materials (these won't be visible but we'll keep them for consistency)
        scene_text_mat = cmds.shadingNode("lambert", asShader=True, name="shotMask_SceneTextMaterial")
        user_text_mat = cmds.shadingNode("lambert", asShader=True, name="shotMask_ArtistTextMaterial")
        date_text_mat = cmds.shadingNode("lambert", asShader=True, name="shotMask_DateTextMaterial")
        fps_text_mat = cmds.shadingNode("lambert", asShader=True, name="shotMask_FPSTextMaterial")
        frame_text_mat = cmds.shadingNode("lambert", asShader=True, name="shotMask_FrameTextMaterial")
        for mat in [scene_text_mat, user_text_mat, date_text_mat, fps_text_mat, frame_text_mat]:
            cmds.setAttr(f"{mat}.color", 0.0, 1.0, 0.0, type="double3")
        
        bg_sg = cmds.sets(name="shotMask_BgSG", renderable=True, noSurfaceShader=True, empty=True)
        scene_sg = cmds.sets(name="shotMask_SceneSG", renderable=True, noSurfaceShader=True, empty=True)
        user_sg = cmds.sets(name="shotMask_ArtistSG", renderable=True, noSurfaceShader=True, empty=True)
        date_sg = cmds.sets(name="shotMask_DateSG", renderable=True, noSurfaceShader=True, empty=True)
        fps_sg = cmds.sets(name="shotMask_FPSSG", renderable=True, noSurfaceShader=True, empty=True)
        frame_sg = cmds.sets(name="shotMask_FrameSG", renderable=True, noSurfaceShader=True, empty=True)
        
        cmds.connectAttr(f"{bg_material}.outColor", f"{bg_sg}.surfaceShader", force=True)
        cmds.connectAttr(f"{scene_text_mat}.outColor", f"{scene_sg}.surfaceShader", force=True)
        cmds.connectAttr(f"{user_text_mat}.outColor", f"{user_sg}.surfaceShader", force=True)
        cmds.connectAttr(f"{date_text_mat}.outColor", f"{date_sg}.surfaceShader", force=True)
        cmds.connectAttr(f"{fps_text_mat}.outColor", f"{fps_sg}.surfaceShader", force=True)
        cmds.connectAttr(f"{frame_text_mat}.outColor", f"{frame_sg}.surfaceShader", force=True)
        
        cmds.sets(bg_plane, edit=True, forceElement=bg_sg)
        
        # Create annotations
        scene_ann = cmds.annotate(scene_plane, text="Scene: " + scene_name)
        user_ann = cmds.annotate(user_plane, text="Artist: " + user_name)
        date_ann = cmds.annotate(date_plane, text="Date: " + current_date)
        fps_ann = cmds.annotate(fps_plane, text="FPS: " + frame_rate)
        frame_ann = cmds.annotate(frame_plane, text="Frame: " + str(currentFrameValue))
        
        # Collect transforms for group parenting
        ann_transforms = []
        for ann, plane in [(scene_ann, scene_plane), 
                        (user_ann, user_plane),
                        (date_ann, date_plane), 
                        (fps_ann, fps_plane), 
                        (frame_ann, frame_plane)]:
            transform = parent_annotation(ann, plane, text_size=annotation_size)
            if transform:
                ann_transforms.append(transform)
        
        # Reparent annotations under the text group so they scale together
        cmds.parent(ann_transforms, text_group, relative=True)
        
        cmds.parent(bg_plane, main_group)
        cmds.parent(text_group, main_group)
        
        cmds.setAttr(f"{text_group}.scaleX", text_scale)
        cmds.setAttr(f"{text_group}.scaleY", text_scale)
        cmds.setAttr(f"{text_group}.scaleZ", text_scale)
        
        cmds.editDisplayLayerMembers("shotMaskLayer", main_group)
        
        cmds.parent(main_group, camera_transform)
        cmds.setAttr(f"{main_group}.translateX", 0)
        cmds.setAttr(f"{main_group}.translateY", -0.061)
        cmds.setAttr(f"{main_group}.translateZ", -0.578)
        cmds.setAttr(f"{main_group}.scaleX", 0.452)
        cmds.setAttr(f"{main_group}.scaleY", 0.452)
        cmds.setAttr(f"{main_group}.scaleZ", 0.452)
        cmds.setAttr("shotMask_MainGroup.rotateZ", 0)
        cmds.setAttr("shotMask_MainGroup.rotateX", 0)
        cmds.setAttr("shotMask_MainGroup.rotateY", 0)
        
        frame_script = cmds.scriptNode(
            scriptType=7,
            beforeScript="",
            sourceType="python",
            name="shotMask_FrameScript"
        )
        update_code = '''# Update frame number
import maya.cmds as cmds
if cmds.objExists("shotMask_FrameTextPlane"):
    current_frame = int(cmds.currentTime(query=True))
    annotation_shapes = cmds.listRelatives("shotMask_FrameTextPlane", allDescendents=True, type="annotationShape") or []
    for shape in annotation_shapes:
        if cmds.objectType(shape) == "annotationShape":
            cmds.setAttr(shape + ".text", "Frame: " + str(current_frame), type="string")
            break
'''
        cmds.scriptNode(frame_script, edit=True, beforeScript=update_code)
        
        panel = get_valid_model_panel()
        if panel:
            cmds.refresh(force=True)
            
        print("Shot mask created successfully with optimized geometry")
        return [main_group, text_group, bg_material,
                [scene_text_mat, user_text_mat, date_text_mat, fps_text_mat, frame_text_mat],
                frame_script, [bg_sg, scene_sg, user_sg, date_sg, fps_sg, frame_sg]]
    except Exception as e:
        cmds.warning(f"Failed to create shot mask: {str(e)}")
        import traceback
        traceback.print_exc()
        return []

def update_shot_mask_text_scale(scale=0.02):
    """
    Update the scale of the text in the shot mask text group.
    """
    if cmds.objExists("shotMask_TextGroup"):
        cmds.setAttr("shotMask_TextGroup.scaleX", scale)
        cmds.setAttr("shotMask_TextGroup.scaleY", scale)
        cmds.setAttr("shotMask_TextGroup.scaleZ", scale)
        print(f"Shot mask text scale updated to {scale}")
        return True
    else:
        cmds.warning("Shot mask text group not found")
        return False

def update_shot_mask_position(y_offset=None, z_distance=None):
    """
    Update the position of the shot mask relative to the camera.
    """
    if cmds.objExists("shotMask_MainGroup"):
        if y_offset is not None:
            cmds.setAttr("shotMask_MainGroup.translateY", y_offset)
        if z_distance is not None:
            cmds.setAttr("shotMask_MainGroup.translateZ", z_distance)
        print("Shot mask position updated")
        return True
    else:
        cmds.warning("Shot mask main group not found")
        return False

def debug_keep_shot_mask(keep=True):
    """
    Set whether to keep the shot mask after playblast for debugging.
    """
    cmds.optionVar(intValue=["keepShotMask", 1 if keep else 0])
    if keep:
        print("Shot mask will be kept after playblast for debugging")
    else:
        print("Shot mask will be removed after playblast")
    return True

def disable_image_planes(camera):
    """
    Disable image planes for a camera.
    """
    state = {}
    try:
        print(f"Disabling image planes for camera: {camera}")
        camera_shape = get_camera_shape(camera)
        if not camera_shape:
            print(f"No valid camera shape found for: {camera}")
            return state
        print(f"Using camera shape: {camera_shape}")
        image_planes = cmds.listConnections(camera_shape, type="imagePlane") or []
        if not image_planes:
            all_planes = cmds.ls(type="imagePlane") or []
            for plane in all_planes:
                try:
                    connected_cam = cmds.listConnections(plane + ".imageCenterX", destination=False, source=True)
                    if connected_cam and camera_shape in connected_cam:
                        image_planes.append(plane)
                except:
                    pass
        print(f"Found image planes: {image_planes}")
        for plane in image_planes:
            try:
                state[plane] = cmds.getAttr(plane + ".display")
                cmds.setAttr(plane + ".display", 0)
                print(f"Disabled image plane: {plane}")
            except Exception as e:
                print(f"Error disabling image plane {plane}: {str(e)}")
    except Exception as e:
        print(f"Error in disable_image_planes: {str(e)}")
    return state

def restore_image_planes(state):
    for s, val in state.items():
        if cmds.objExists(s):
            cmds.setAttr(s + ".display", val)

def get_maya_main_window():
    ptr = omui.MQtUtil.mainWindow()
    return wrapInstance(int(ptr), QtWidgets.QWidget) if ptr else None

def confirm_overwrite(full_file_path):
    filename = os.path.basename(full_file_path)
    result = QtWidgets.QMessageBox.question(
        get_maya_main_window(),
        "Confirm Overwrite",
        f'File "{filename}" already exists.\nDo you want to overwrite it?',
        QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
        QtWidgets.QMessageBox.No
    )
    return result == QtWidgets.QMessageBox.Yes

def clean_camera_view(camera_name):
    shapes = cmds.listRelatives(camera_name, shapes=True, type="camera")
    camera_shape = shapes[0] if shapes else camera_name
    cmds.camera(camera_shape, edit=True,
                displayFilmGate=False,
                displayResolution=False,
                displaySafeAction=False,
                displaySafeTitle=False,
                displayFieldChart=False,
                displayGateMask=False,
                overscan=1.0)

def get_viewport_defaults(panel, camera):
    if cmds.nodeType(camera) == "transform":
        shapes = cmds.listRelatives(camera, shapes=True, noIntermediate=True, type="camera")
        cameraShape = shapes[0] if shapes else camera
    else:
        cameraShape = camera
    defaults = {}
    try:
        defaults['displayFilmGate'] = cmds.getAttr(cameraShape + ".displayFilmGate")
    except:
        defaults['displayFilmGate'] = 1
    try:
        defaults['displayResolution'] = cmds.getAttr(cameraShape + ".displayResolution")
    except:
        defaults['displayResolution'] = 1
    try:
        defaults['displaySafeAction'] = cmds.getAttr(cameraShape + ".displaySafeAction")
    except:
        defaults['displaySafeAction'] = 1
    try:
        defaults['displayGateMask'] = cmds.getAttr(cameraShape + ".displayGateMask")
    except:
        defaults['displayGateMask'] = 1
    try:
        defaults['nurbsCurves'] = cmds.modelEditor(panel, q=True, nurbsCurves=True)
    except:
        defaults['nurbsCurves'] = True
    try:
        defaults['grid'] = cmds.modelEditor(panel, q=True, grid=True)
    except:
        defaults['grid'] = True
    try:
        defaults['textures'] = cmds.modelEditor(panel, q=True, textures=True)
    except:
        defaults['textures'] = True
    try:
        defaults['shadows'] = cmds.modelEditor(panel, q=True, shadows=True)
    except:
        defaults['shadows'] = True
    try:
        defaults['occlusionCulling'] = cmds.modelEditor(panel, q=True, occlusionCulling=True)
    except:
        defaults['occlusionCulling'] = False
    return defaults

def set_final_viewport(panel, camera_transform):
    """
    Force the viewport to hide NURBS curves and other unwanted items.
    """
    clean_camera_view(camera_transform)
    cmds.lookThru(camera_transform)
    cmds.modelEditor(panel, edit=True, allObjects=False)
    cmds.modelEditor(
        panel,
        edit=True,
        grid=False,
        displayAppearance='smoothShaded',
        polymeshes=True,
        nurbsSurfaces=True,
        subdivSurfaces=True,
        displayLights='default',
        textures=True,
        shadows=True,
        displayTextures=True,
        nurbsCurves=False,
        cv=False,
        hulls=False,
        planes=False,
        lights=False,
        cameras=False,
        joints=False,
        ikHandles=False,
        deformers=False,
        dynamics=False,
        fluids=False,
        hairSystems=False,
        follicles=False,
        nCloths=False,
        nParticles=False,
        nRigids=False,
        dynamicConstraints=False,
        locators=False,
        dimensions=False,
        pivots=False,
        handles=False,
        controlVertices=False,
        manipulators=False,
        clipGhosts=False,
        wireframeOnShaded=False,
        strokes=False,
        motionTrails=False,
        pluginShapes=False,
        fogEnd=False,
        useDefaultMaterial=False,
        selectionHiliteDisplay=False
    )
    cmds.refresh(force=True)
    cmds.select(clear=True)
    mel.eval(f'modelEditor -e -allObjects 0 {panel}')
    mel.eval(f'modelEditor -e -polymeshes 1 {panel}')
    mel.eval(f'modelEditor -e -nurbsSurfaces 1 {panel}')
    mel.eval(f'modelEditor -e -nurbsCurves 0 {panel}')
    curves_state = cmds.modelEditor(panel, query=True, nurbsCurves=True)
    if curves_state:
        cmds.warning("NURBS curves still visible after all attempts to hide them")
    else:
        print("Successfully turned off NURBS curves")

def restore_viewport(panel, camera, defaults):
    if cmds.nodeType(camera) == "transform":
        shapes = cmds.listRelatives(camera, shapes=True, noIntermediate=True, type="camera")
        cameraShape = shapes[0] if shapes else camera
    else:
        cameraShape = camera
    try:
        cmds.setAttr(cameraShape + ".displayFilmGate", defaults.get('displayFilmGate', 1))
    except Exception as e:
        print("Error restoring film gate: " + str(e))
    try:
        cmds.setAttr(cameraShape + ".displayResolution", defaults.get('displayResolution', 1))
    except Exception as e:
        print("Error restoring resolution gate: " + str(e))
    try:
        cmds.setAttr(cameraShape + ".displaySafeAction", defaults.get('displaySafeAction', 1))
    except Exception as e:
        print("Error restoring safe action: " + str(e))
    try:
        cmds.setAttr(cameraShape + ".displayGateMask", defaults.get('displayGateMask', 1))
    except Exception as e:
        print("Error restoring gate mask: " + str(e))
    cmds.modelEditor(panel, edit=True,
                     nurbsCurves=defaults.get('nurbsCurves', True),
                     grid=defaults.get('grid', True),
                     shadows=defaults.get('shadows', True),
                     occlusionCulling=defaults.get('occlusionCulling', False),
                     displayTextures=defaults.get('textures', True))
    cmds.refresh(force=True)

def get_valid_model_panel():
    panel = cmds.getPanel(withFocus=True)
    if cmds.getPanel(type=panel) != "modelPanel":
        panels = cmds.getPanel(type="modelPanel")
        panel = panels[0] if panels else None
    return panel

def update_shot_mask_annotation_size(size=2.0):
    """
    Update the size of annotation text in the shot mask.
    """
    if not cmds.objExists("shotMask_TextGroup"):
        cmds.warning("Shot mask text group not found")
        return False
        
    try:
        # Get all annotation shapes and transforms
        ann_shapes = cmds.listRelatives("shotMask_TextGroup", allDescendents=True, type="annotationShape") or []
        
        # First try setting the font size attribute on each shape
        for shape in ann_shapes:
            # Try all possible attributes for text scaling
            for attr in ["fontSize", "textScale", "fontScale"]:
                if cmds.attributeQuery(attr, node=shape, exists=True):
                    cmds.setAttr(f"{shape}.{attr}", size)
                    break
        
        # Then also scale the transform nodes of each annotation
        for shape in ann_shapes:
            parent = cmds.listRelatives(shape, parent=True)
            if parent:
                scale_factor = size / 2.0  # Adjust this ratio as needed
                cmds.setAttr(f"{parent[0]}.scaleX", scale_factor)
                cmds.setAttr(f"{parent[0]}.scaleY", scale_factor)
                cmds.setAttr(f"{parent[0]}.scaleZ", scale_factor)
        
        # Temporarily set the Maya UI font size preference (optional)
        ui_size = int(max(8, min(18, size * 4)))  # Map to reasonable UI font size
        cmds.optionVar(intValue=["UIFontSize", ui_size])
        
        # Refresh the viewport
        cmds.refresh(force=True)
        
        print(f"Updated {len(ann_shapes)} annotations to size {size}")
        return True
    except Exception as e:
        cmds.warning(f"Failed to update annotation size: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def remove_shot_mask(nodes):
    """
    Remove the shot mask and all related nodes.
    """
    try:
        if not nodes:
            return
        
        main_group = nodes[0] if isinstance(nodes, list) and len(nodes) > 0 else None
        
        if main_group and cmds.objExists(main_group):
            cmds.delete(main_group)
            print(f"Shot mask {main_group} removed")
        else:
            print("Main shot mask group not found in nodes")
            
        # Clean up any other remaining nodes
        for node in nodes:
            if isinstance(node, list):
                for sub_node in node:
                    if cmds.objExists(sub_node):
                        cmds.delete(sub_node)
            elif cmds.objExists(node):
                cmds.delete(node)
                
    except Exception as e:
        cmds.warning(f"Failed to remove shot mask: {str(e)}")
        import traceback
        traceback.print_exc()

def update_maya_font_size(size):
    """
    Updates Maya's UI font size preference (alternate method)
    """
    try:
        # Convert annotation scale to UI font size
        ui_font_size = int(max(8, min(18, size * 5)))
        
        # Set the UI Font Size option
        cmds.optionVar(intValue=["UIFontSize", ui_font_size])
        
        # Inform the user changes will apply after restart
        message = f"Font size preference updated to {ui_font_size}.\nNote: Some UI elements may not update until they are reopened."
        cmds.confirmDialog(title="Font Size Updated", message=message, button=["OK"])
        
        # For annotations specifically, we can still try to force an update
        if cmds.objExists("shotMask_TextGroup"):
            # Try to directly modify annotation text display properties
            ann_shapes = cmds.listRelatives("shotMask_TextGroup", allDescendents=True, type="annotationShape") or []
            for shape in ann_shapes:
                # Try different attributes based on Maya version
                for attr in ["fontSize", "textScale", "fontScale"]:
                    if cmds.attributeQuery(attr, node=shape, exists=True):
                        cmds.setAttr(f"{shape}.{attr}", ui_font_size / 4.0)  # Adjusted scale for annotations
                        
        # Refresh the view
        cmds.refresh(force=True)
        
        return True
    except Exception as e:
        cmds.warning(f"Failed to update font size: {str(e)}")
        return False


        full_name = f"{firstname} {lastname}".strip()
        self.userNameLineEdit.setText(full_name)

# Global variable to hold the dialog instance
playblast_dialog = None

class ConestogaPlayblastDialog(QtWidgets.QDialog):

    def __init__(self, parent=get_maya_main_window()):
        super().__init__(parent)
        self.setWindowTitle("Conestoga Playblast Tool")
        self.setMinimumWidth(500)
        self.setWindowFlags(QtCore.Qt.Window)
        self.shot_mask_data = None  # Hold shot mask nodes if pre-created
        
        # Create main layout
        main_layout = QtWidgets.QVBoxLayout(self)
        self.settings_layout = QtWidgets.QVBoxLayout()
        main_layout.addLayout(self.settings_layout)
        
        # Add camera and audio selection
        camera_layout = QtWidgets.QHBoxLayout()
        camera_label = QtWidgets.QLabel("Camera:")
        camera_label.setStyleSheet("color: white;")
        self.cameraComboBox = QtWidgets.QComboBox()
        self.populate_camera_list()
        camera_layout.addWidget(camera_label)
        camera_layout.addWidget(self.cameraComboBox)
        self.settings_layout.addLayout(camera_layout)

        # Audio selection
        audio_layout = QtWidgets.QHBoxLayout()
        audio_label = QtWidgets.QLabel("Audio:")
        audio_label.setStyleSheet("color: white;")
        self.audioComboBox = QtWidgets.QComboBox()
        self.populate_audio_list()
        audio_layout.addWidget(audio_label)
        audio_layout.addWidget(self.audioComboBox)
        self.settings_layout.addLayout(audio_layout)
        
        # Final Playblast and Save As checkboxes
        checkbox_layout = QtWidgets.QHBoxLayout()
        self.finalPlayblastCheckbox = QtWidgets.QCheckBox("Final Quality Playblast")
        self.finalPlayblastCheckbox.setStyleSheet("color: white;")
        self.finalPlayblastCheckbox.setChecked(True)
        self.saveAsCheckbox = QtWidgets.QCheckBox("Save to Movies Folder")
        self.saveAsCheckbox.setStyleSheet("color: white;")
        self.saveAsCheckbox.setChecked(True)
        checkbox_layout.addWidget(self.finalPlayblastCheckbox)
        checkbox_layout.addWidget(self.saveAsCheckbox)
        self.settings_layout.addLayout(checkbox_layout)
        
        # Now set up the output name generator
        self.setup_output_name_generator()

        # Additional Options: Image Planes and HUD (Artist Text)
        extra_options_layout = QtWidgets.QHBoxLayout()
        self.imagePlanesCheckbox = QtWidgets.QCheckBox("Include Image Planes")
        self.imagePlanesCheckbox.setStyleSheet("color: white;")
        self.imagePlanesCheckbox.setChecked(True)
        self.hudCheckbox = QtWidgets.QCheckBox("Artist Display Name")
        self.hudCheckbox.setStyleSheet("color: white;")
        self.hudCheckbox.setChecked(False)
        self.userNameLineEdit = QtWidgets.QLineEdit()
        self.userNameLineEdit.setPlaceholderText("Enter your name")
        extra_options_layout.addWidget(self.imagePlanesCheckbox)
        extra_options_layout.addWidget(self.hudCheckbox)
        extra_options_layout.addWidget(self.userNameLineEdit)
        self.settings_layout.addLayout(extra_options_layout)

        # Resolution Settings
        res_layout = QtWidgets.QHBoxLayout()
        res_label = QtWidgets.QLabel("Resolution:")
        res_label.setStyleSheet("color: white;")
        self.widthSpinBox = QtWidgets.QSpinBox()
        self.widthSpinBox.setRange(100, 10000)
        self.widthSpinBox.setValue(1920)
        self.widthSpinBox.setSuffix(" px")
        self.heightSpinBox = QtWidgets.QSpinBox()
        self.heightSpinBox.setRange(100, 10000)
        self.heightSpinBox.setValue(1080)
        self.heightSpinBox.setSuffix(" px")
        res_layout.addWidget(res_label)
        res_layout.addWidget(QtWidgets.QLabel("Width:"))
        res_layout.addWidget(self.widthSpinBox)
        res_layout.addWidget(QtWidgets.QLabel("Height:"))
        res_layout.addWidget(self.heightSpinBox)
        self.settings_layout.addLayout(res_layout)

        # Frame Range Settings
        frame_layout = QtWidgets.QHBoxLayout()
        frame_label = QtWidgets.QLabel("Frame Range:")
        frame_label.setStyleSheet("color: white;")
        self.startFrameSpinBox = QtWidgets.QSpinBox()
        self.startFrameSpinBox.setRange(1, 100000)
        self.startFrameSpinBox.setValue(int(cmds.playbackOptions(query=True, min=True)))
        self.endFrameSpinBox = QtWidgets.QSpinBox()
        self.endFrameSpinBox.setRange(1, 100000)
        self.endFrameSpinBox.setValue(int(cmds.playbackOptions(query=True, max=True)))
        frame_layout.addWidget(frame_label)
        frame_layout.addWidget(QtWidgets.QLabel("Start:"))
        frame_layout.addWidget(self.startFrameSpinBox)
        frame_layout.addWidget(QtWidgets.QLabel("End:"))
        frame_layout.addWidget(self.endFrameSpinBox)
        self.settings_layout.addLayout(frame_layout)

        # Quality Settings
        quality_layout = QtWidgets.QHBoxLayout()
        quality_label = QtWidgets.QLabel("Quality:")
        quality_label.setStyleSheet("color: white;")
        self.qualitySlider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.qualitySlider.setRange(0, 100)
        self.qualitySlider.setValue(100)
        self.qualitySlider.setStyleSheet(
            "QSlider::groove:horizontal { height: 8px; background: #999; }" +
            "QSlider::handle:horizontal { background: #ccc; border: 1px solid #555; width: 14px; margin: -4px 0; border-radius: 4px; }"
        )
        self.qualitySpinBox = QtWidgets.QSpinBox()
        self.qualitySpinBox.setRange(0, 100)
        self.qualitySpinBox.setValue(100)
        self.qualitySpinBox.setFixedWidth(60)
        self.qualitySpinBox.setSuffix("%")
        self.qualitySlider.valueChanged.connect(self.qualitySpinBox.setValue)
        self.qualitySpinBox.valueChanged.connect(self.qualitySlider.setValue)
        quality_layout.addWidget(quality_label)
        quality_layout.addWidget(self.qualitySlider)
        quality_layout.addWidget(self.qualitySpinBox)
        self.settings_layout.addLayout(quality_layout)

        # Scale Settings
        scale_layout = QtWidgets.QHBoxLayout()
        scale_label = QtWidgets.QLabel("Scale:")
        scale_label.setStyleSheet("color: white;")
        self.scaleSlider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.scaleSlider.setRange(1, 100)
        self.scaleSlider.setValue(100)
        self.scaleSlider.setStyleSheet(
            "QSlider::groove:horizontal { height: 8px; background: #999; }" +
            "QSlider::handle:horizontal { background: #ccc; border: 1px solid #555; width: 14px; margin: -4px 0; border-radius: 4px; }"
        )
        self.scaleSpinBox = QtWidgets.QSpinBox()
        self.scaleSpinBox.setRange(1, 100)
        self.scaleSpinBox.setValue(100)
        self.scaleSpinBox.setFixedWidth(60)
        self.scaleSlider.valueChanged.connect(self.scaleSpinBox.setValue)
        self.scaleSpinBox.valueChanged.connect(self.scaleSlider.setValue)
        scale_layout.addWidget(scale_label)
        scale_layout.addWidget(self.scaleSlider)
        scale_layout.addWidget(self.scaleSpinBox)
        self.settings_layout.addLayout(scale_layout)

        # Output Filename
        file_layout = QtWidgets.QHBoxLayout()
        file_label = QtWidgets.QLabel("Output Name:")
        file_label.setStyleSheet("color: white;")
        self.filenameLineEdit = QtWidgets.QLineEdit()
        self.filenameLineEdit.setPlaceholderText("e.g. A1_LastName_FirstName_week1_wip.mov")
        file_layout.addWidget(file_label)
        file_layout.addWidget(self.filenameLineEdit)
        self.settings_layout.addLayout(file_layout)

        # Action Buttons
        btn_layout = QtWidgets.QHBoxLayout()
        self.playblastButton = QtWidgets.QPushButton("Playblast")
        self.cancelButton = QtWidgets.QPushButton("Close")
        self.playblastButton.clicked.connect(self.do_playblast)
        self.cancelButton.clicked.connect(self.close)
        btn_layout.addWidget(self.playblastButton)
        btn_layout.addWidget(self.cancelButton)
        self.settings_layout.addLayout(btn_layout)

        # Create Shot Mask button
        self.createShotMaskButton = QtWidgets.QPushButton("Create Shot Mask")
        self.createShotMaskButton.setToolTip("Create the shot mask so you can adjust it before playblast")
        self.createShotMaskButton.clicked.connect(self.create_shot_mask_button_callback)
        self.settings_layout.addWidget(self.createShotMaskButton)
        
        # Set up shot mask controls after main UI
        self.setup_shot_mask_controls()

    def setup_shot_mask_controls(self):
        try:
            mask_frame = QtWidgets.QGroupBox("Shot Mask Controls")
            mask_layout = QtWidgets.QVBoxLayout(mask_frame)
            
            # Group Scale slider (affects overall text group size)
            text_scale_layout = QtWidgets.QHBoxLayout()
            text_scale_label = QtWidgets.QLabel("Group Scale:")
            text_scale_label.setStyleSheet("color: white;")
            self.textScaleSlider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
            self.textScaleSlider.setRange(1, 5000)
            self.textScaleSlider.setValue(820)
            self.textScaleSlider.setStyleSheet(
                "QSlider::groove:horizontal { height: 8px; background: #999; }" +
                "QSlider::handle:horizontal { background: #ccc; border: 1px solid #555; width: 14px; margin: -4px 0; border-radius: 4px; }"
            )
            self.textScaleSpinBox = QtWidgets.QDoubleSpinBox()
            self.textScaleSpinBox.setRange(0.01, 1)
            self.textScaleSpinBox.setSingleStep(0.005)
            self.textScaleSpinBox.setValue(0.82)
            self.textScaleSpinBox.setFixedWidth(70)
            self.textScaleSlider.valueChanged.connect(lambda v: self.textScaleSpinBox.setValue(v / 1000.0))
            self.textScaleSpinBox.valueChanged.connect(lambda v: self.textScaleSlider.setValue(int(v * 1000)))
            self.textScaleSpinBox.valueChanged.connect(lambda v: update_shot_mask_text_scale(v) if cmds.objExists("shotMask_TextGroup") else None)
            text_scale_layout.addWidget(text_scale_label)
            text_scale_layout.addWidget(self.textScaleSlider)
            text_scale_layout.addWidget(self.textScaleSpinBox)
            mask_layout.addLayout(text_scale_layout)
            
            # Annotation Text Size slider
            ann_size_layout = QtWidgets.QHBoxLayout()
            ann_size_label = QtWidgets.QLabel("Annotation Size:")
            ann_size_label.setStyleSheet("color: white;")
            self.annSizeSlider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
            self.annSizeSlider.setRange(1, 100)
            self.annSizeSlider.setValue(20)  # Default value 2.0 when divided by 10
            self.annSizeSlider.setStyleSheet(
                "QSlider::groove:horizontal { height: 8px; background: #999; }" +
                "QSlider::handle:horizontal { background: #ccc; border: 1px solid #555; width: 14px; margin: -4px 0; border-radius: 4px; }"
            )
            self.annSizeSpinBox = QtWidgets.QDoubleSpinBox()
            self.annSizeSpinBox.setRange(0.1, 10.0)
            self.annSizeSpinBox.setSingleStep(0.1)
            self.annSizeSpinBox.setValue(2.0)
            self.annSizeSpinBox.setFixedWidth(70)
            self.annSizeSlider.valueChanged.connect(lambda v: self.annSizeSpinBox.setValue(v / 10.0))
            self.annSizeSpinBox.valueChanged.connect(lambda v: self.annSizeSlider.setValue(int(v * 10)))
            self.annSizeSpinBox.valueChanged.connect(lambda v: self.update_annotation_font_size(v))
            ann_size_layout.addWidget(ann_size_label)
            ann_size_layout.addWidget(self.annSizeSlider)
            ann_size_layout.addWidget(self.annSizeSpinBox)
            mask_layout.addLayout(ann_size_layout)
            
            # Vertical Position slider
            vert_pos_layout = QtWidgets.QHBoxLayout()
            vert_pos_label = QtWidgets.QLabel("Vertical Position:")
            vert_pos_label.setStyleSheet("color: white;")
            self.vertPosSlider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
            self.vertPosSlider.setRange(-200, 200)
            self.vertPosSlider.setValue(-190)
            self.vertPosSlider.setStyleSheet(
                "QSlider::groove:horizontal { height: 8px; background: #999; }" +
                "QSlider::handle:horizontal { background: #ccc; border: 1px solid #555; width: 14px; margin: -4px 0; border-radius: 4px; }"
            )
            self.vertPosSpinBox = QtWidgets.QDoubleSpinBox()
            self.vertPosSpinBox.setRange(-0.2, 0.2)
            self.vertPosSpinBox.setSingleStep(0.01)
            self.vertPosSpinBox.setValue(-0.19)
            self.vertPosSpinBox.setFixedWidth(70)
            self.vertPosSlider.valueChanged.connect(lambda v: self.vertPosSpinBox.setValue(v / 1000.0))
            self.vertPosSpinBox.valueChanged.connect(lambda v: self.vertPosSlider.setValue(int(v * 1000)))
            self.vertPosSpinBox.valueChanged.connect(lambda v: update_shot_mask_position(y_offset=v) if cmds.objExists("shotMask_MainGroup") else None)
            vert_pos_layout.addWidget(vert_pos_label)
            vert_pos_layout.addWidget(self.vertPosSlider)
            vert_pos_layout.addWidget(self.vertPosSpinBox)
            mask_layout.addLayout(vert_pos_layout)
            
            # Z Distance slider
            z_dist_layout = QtWidgets.QHBoxLayout()
            z_dist_label = QtWidgets.QLabel("Z Distance:")
            z_dist_label.setStyleSheet("color: white;")
            self.zDistSlider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
            self.zDistSlider.setRange(-1000, -100)
            self.zDistSlider.setValue(-790)
            self.zDistSlider.setStyleSheet(
                "QSlider::groove:horizontal { height: 8px; background: #999; }" +
                "QSlider::handle:horizontal { background: #ccc; border: 1px solid #555; width: 14px; margin: -4px 0; border-radius: 4px; }"
            )
            self.zDistSpinBox = QtWidgets.QDoubleSpinBox()
            self.zDistSpinBox.setRange(-1.0, -0.1)
            self.zDistSpinBox.setSingleStep(0.05)
            self.zDistSpinBox.setValue(-0.79)
            self.zDistSpinBox.setFixedWidth(70)
            self.zDistSlider.valueChanged.connect(lambda v: self.zDistSpinBox.setValue(v / 1000.0))
            self.zDistSpinBox.valueChanged.connect(lambda v: self.zDistSlider.setValue(int(v * 1000)))
            self.zDistSpinBox.valueChanged.connect(lambda v: update_shot_mask_position(z_distance=v) if cmds.objExists("shotMask_MainGroup") else None)
            z_dist_layout.addWidget(z_dist_label)
            z_dist_layout.addWidget(self.zDistSlider)
            z_dist_layout.addWidget(self.zDistSpinBox)
            mask_layout.addLayout(z_dist_layout)
            
            self.settings_layout.addWidget(mask_frame)
            return True
        except Exception as e:
            cmds.warning(f"Failed to add shot mask controls: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

    def setup_output_name_generator(self):
        """
        Add a filename generator section to the UI.
        """
        # Create a frame for the output name generator
        filename_frame = QtWidgets.QGroupBox("Output Name Generator")
        filename_frame.setStyleSheet("color: white;")
        filename_layout = QtWidgets.QVBoxLayout(filename_frame)
        
        # Create input controls layout
        input_layout = QtWidgets.QHBoxLayout()
        
        # Assignment field
        assignment_layout = QtWidgets.QHBoxLayout()
        assignment_label = QtWidgets.QLabel("A")
        assignment_label.setStyleSheet("color: white;")
        self.assignmentSpinBox = QtWidgets.QSpinBox()
        self.assignmentSpinBox.setRange(1, 99)
        self.assignmentSpinBox.setValue(1)
        self.assignmentSpinBox.setFixedWidth(50)
        assignment_layout.addWidget(assignment_label)
        assignment_layout.addWidget(self.assignmentSpinBox)
        
        # Last Name field
        lastname_layout = QtWidgets.QHBoxLayout()
        lastname_label = QtWidgets.QLabel("Last Name:")
        lastname_label.setStyleSheet("color: white;")
        self.lastnameLineEdit = QtWidgets.QLineEdit()
        self.lastnameLineEdit.setPlaceholderText("Last Name")
        lastname_layout.addWidget(lastname_label)
        lastname_layout.addWidget(self.lastnameLineEdit)
        
        # First Name field
        firstname_layout = QtWidgets.QHBoxLayout()
        firstname_label = QtWidgets.QLabel("First Name:")
        firstname_label.setStyleSheet("color: white;")
        self.firstnameLineEdit = QtWidgets.QLineEdit()
        self.firstnameLineEdit.setPlaceholderText("First Name")
        firstname_layout.addWidget(firstname_label)
        firstname_layout.addWidget(self.firstnameLineEdit)
        
        # Version type dropdown
        version_type_layout = QtWidgets.QHBoxLayout()
        version_type_label = QtWidgets.QLabel("Type:")
        version_type_label.setStyleSheet("color: white;")
        self.versionTypeCombo = QtWidgets.QComboBox()
        self.versionTypeCombo.addItems(["wip", "final"])
        version_type_layout.addWidget(version_type_label)
        version_type_layout.addWidget(self.versionTypeCombo)
        
        # Version number
        version_number_layout = QtWidgets.QHBoxLayout()
        version_number_label = QtWidgets.QLabel("Version:")
        version_number_label.setStyleSheet("color: white;")
        self.versionNumberSpinBox = QtWidgets.QSpinBox()
        self.versionNumberSpinBox.setRange(1, 99)
        self.versionNumberSpinBox.setValue(1)
        self.versionNumberSpinBox.setFixedWidth(50)
        version_number_layout.addWidget(version_number_label)
        version_number_layout.addWidget(self.versionNumberSpinBox)
        
        # Add all controls to the input layout
        input_layout.addLayout(assignment_layout)
        input_layout.addLayout(lastname_layout)
        input_layout.addLayout(firstname_layout)
        input_layout.addLayout(version_type_layout)
        input_layout.addLayout(version_number_layout)
        
        # Preview field
        preview_layout = QtWidgets.QHBoxLayout()
        preview_label = QtWidgets.QLabel("Preview:")
        preview_label.setStyleSheet("color: white;")
        self.filenamePreviewLabel = QtWidgets.QLabel("A1*LastName*FirstName*wip*01.mov")
        self.filenamePreviewLabel.setStyleSheet("color: yellow; font-weight: bold;")
        preview_layout.addWidget(preview_label)
        preview_layout.addWidget(self.filenamePreviewLabel)
        
        # Generate button
        generate_layout = QtWidgets.QHBoxLayout()
        self.generateFilenameButton = QtWidgets.QPushButton("Generate Filename")
        self.generateFilenameButton.clicked.connect(self.generate_filename)
        generate_layout.addWidget(self.generateFilenameButton)
        
        # Add layouts to the main layout
        filename_layout.addLayout(input_layout)
        filename_layout.addLayout(preview_layout)
        filename_layout.addLayout(generate_layout)
        
        # Add the frame to the main UI
        self.settings_layout.addWidget(filename_frame)
        
        # Connect all input fields to update the preview
        self.assignmentSpinBox.valueChanged.connect(self.update_filename_preview)
        self.lastnameLineEdit.textChanged.connect(self.update_filename_preview)
        self.firstnameLineEdit.textChanged.connect(self.update_filename_preview)
        self.versionTypeCombo.currentTextChanged.connect(self.update_filename_preview)
        self.versionNumberSpinBox.valueChanged.connect(self.update_filename_preview)
        
        # Auto-update the artist name field when first/last name changes
        self.lastnameLineEdit.textChanged.connect(self.update_artist_name)
        self.firstnameLineEdit.textChanged.connect(self.update_artist_name)
        
        # Initial preview update
        self.update_filename_preview()

    def _populate_camera_list(self):
        self.cameraComboBox.clear()
        cams = cmds.ls(type="camera")
        cam_transforms = set()
        for cam in cams:
            par = cmds.listRelatives(cam, parent=True, fullPath=True)
            if par:
                cam_transforms.add(par[0])
            else:
                cam_transforms.add(cam)
        for cam in sorted(cam_transforms):
            self.cameraComboBox.addItem(cam)

    def _populate_audio_list(self):
        self.audioComboBox.clear()
        self.audioComboBox.addItem("None")
        for audio in cmds.ls(type="audio"):
            try:
                audio_path = cmds.getAttr(audio + ".filename")
                display_name = f"{audio} ({os.path.basename(audio_path)})"
                self.audioComboBox.addItem(display_name, audio)
            except Exception as e:
                print(f"Error adding audio node {audio}: {str(e)}")
                continue

    def setup_ui(self):
        """
        Setup the UI elements (note: most UI is already initialized in __init__)
        This method is kept for compatibility but should not be called directly.
        """
        try:
            # Create Shot Mask button
            self.createShotMaskButton = QtWidgets.QPushButton("Create Shot Mask")
            self.createShotMaskButton.setToolTip("Create the shot mask so you can adjust it before playblast")
            self.createShotMaskButton.clicked.connect(self.create_shot_mask_button_callback)
            self.settings_layout.addWidget(self.createShotMaskButton)
            return True
        except Exception as e:
            cmds.warning(f"Failed to setup UI: {str(e)}")
            import traceback
            traceback.print_exc()
            return False                                 

    def create_shot_mask_button_callback(self):
        """
        Create the shot mask using current UI settings so that the user can adjust it before playblast.
        """
        selected_camera = self.cameraComboBox.currentText()
        if not cmds.objExists(selected_camera):
            cmds.confirmDialog(title="Error", message=f"Camera '{selected_camera}' does not exist.", button=["OK"])
            return
        camera_shape = get_camera_shape(selected_camera)
        if not camera_shape:
            cmds.confirmDialog(title="Error", message=f"Failed to get camera shape for '{selected_camera}'.", button=["OK"])
            return
        if cmds.nodeType(camera_shape) == "camera":
            transforms = cmds.listRelatives(camera_shape, parent=True, fullPath=True)
            if transforms:
                camera_transform = transforms[0]
            else:
                cmds.confirmDialog(title="Error", message=f"Failed to get transform for camera '{camera_shape}'.", button=["OK"])
                return
        else:
            camera_transform = selected_camera
        if self.hudCheckbox.isChecked() and self.userNameLineEdit.text().strip():
            if self.shot_mask_data:
                remove_shot_mask(self.shot_mask_data)
                self.shot_mask_data = None
            scene_path = cmds.file(query=True, sceneName=True) or "Untitled Scene"
            scene_name = os.path.basename(scene_path).split('.')[0]
            text_scale = self.textScaleSpinBox.value()
            vert_pos = self.vertPosSpinBox.value()
            z_dist = self.zDistSpinBox.value()
            annotation_size = self.annSizeSpinBox.value()
            self.shot_mask_data = create_shot_mask(camera_transform, self.userNameLineEdit.text().strip(),
                                                  scene_name=scene_name, text_scale=text_scale,
                                                  annotation_size=annotation_size)
            if self.shot_mask_data:
                update_shot_mask_position(y_offset=vert_pos, z_distance=z_dist)
                cmds.inViewMessage(amg="Shot Mask Created. Adjust using the controls below.", pos='midCenter', fade=True)
            else:
                cmds.warning("Failed to create shot mask.")
        else:
            cmds.confirmDialog(title="Error", message="Please check the HUD option and enter your name.", button=["OK"])

    def populate_camera_list(self):
        self.cameraComboBox.clear()
        cams = cmds.ls(type="camera")
        cam_transforms = set()
        for cam in cams:
            par = cmds.listRelatives(cam, parent=True, fullPath=True)
            if par:
                cam_transforms.add(par[0])
            else:
                cam_transforms.add(cam)
        for cam in sorted(cam_transforms):
            self.cameraComboBox.addItem(cam)

    def populate_audio_list(self):
        self.audioComboBox.clear()
        self.audioComboBox.addItem("None")
        for audio in cmds.ls(type="audio"):
            try:
                audio_path = cmds.getAttr(audio + ".filename")
                display_name = f"{audio} ({os.path.basename(audio_path)})"
                self.audioComboBox.addItem(display_name, audio)
            except Exception as e:
                print(f"Error adding audio node {audio}: {str(e)}")
                continue

    def do_playblast(self):
        try:
            width = self.widthSpinBox.value()
            height = self.heightSpinBox.value()
            start_frame = self.startFrameSpinBox.value()
            end_frame = self.endFrameSpinBox.value()
            quality = self.qualitySpinBox.value()
            scale_value = self.scaleSpinBox.value()
            filename = self.filenameLineEdit.text().strip()
            if not filename:
                cmds.confirmDialog(title="Error", message="Please enter an output file name.", button=["OK"])
                return
            if not filename.lower().endswith(".mov"):
                filename += ".mov"
            workspace_dir = cmds.workspace(query=True, rd=True)
            movies_dir = os.path.normpath(os.path.join(workspace_dir, "movies"))
            if not os.path.exists(movies_dir):
                os.makedirs(movies_dir)
            temp_dir = os.path.join(movies_dir, "temp")
            if not os.path.exists(temp_dir):
                os.makedirs(temp_dir)
            base_name = os.path.splitext(filename)[0]
            temp_path = os.path.join(temp_dir, base_name + ".mov")
            if self.saveAsCheckbox.isChecked():
                final_output_path = os.path.join(movies_dir, filename)
                if os.path.exists(final_output_path):
                    if not confirm_overwrite(final_output_path):
                        return
                    try:
                        os.remove(final_output_path)
                    except Exception as e:
                        cmds.warning("Could not remove existing file: " + str(e))
                        return
                else:
                    final_output_path = temp_path
            selected_camera = self.cameraComboBox.currentText()
            print(f"Selected camera: {selected_camera}")
            if not cmds.objExists(selected_camera):
                cmds.confirmDialog(title="Error", message=f"Camera '{selected_camera}' does not exist.", button=["OK"])
                return
            camera_shape = get_camera_shape(selected_camera)
            if not camera_shape:
                cmds.confirmDialog(title="Error", message=f"Failed to get camera shape for '{selected_camera}'.", button=["OK"])
                return
            if cmds.nodeType(camera_shape) == "camera":
                transforms = cmds.listRelatives(camera_shape, parent=True, fullPath=True)
                if transforms:
                    camera_transform = transforms[0]
                else:
                    cmds.confirmDialog(title="Error", message=f"Failed to get transform for camera '{camera_shape}'.", button=["OK"])
                    return
            else:
                camera_transform = selected_camera
            print(f"Using camera: {camera_transform} (shape: {camera_shape})")
            audio_index = self.audioComboBox.currentIndex()
            audio_node = None
            if audio_index > 0:
                audio_node = self.audioComboBox.itemData(audio_index)
                if audio_node and cmds.objExists(audio_node):
                    print(f"Using audio node: {audio_node}")
                else:
                    print("Audio node not found or invalid")
                    audio_node = None
            ip_state = {}
            mask_data = None
            try:
                if not self.imagePlanesCheckbox.isChecked():
                    ip_state = disable_image_planes(camera_transform)
                if self.hudCheckbox.isChecked() and self.userNameLineEdit.text().strip():
                    if self.shot_mask_data:
                        mask_data = self.shot_mask_data
                        update_shot_mask_position(y_offset=self.vertPosSpinBox.value(), z_distance=self.zDistSpinBox.value())
                        print(f"Using pre-created shot mask: {mask_data}")
                    else:
                        scene_path = cmds.file(query=True, sceneName=True) or "Untitled Scene"
                        scene_name = os.path.basename(scene_path).split('.')[0]
                        text_scale = self.textScaleSpinBox.value()
                        annotation_size = self.annSizeSpinBox.value()
                        mask_data = create_shot_mask(camera_transform, self.userNameLineEdit.text().strip(),
                                                     scene_name=scene_name, text_scale=text_scale,
                                                     annotation_size=annotation_size)
                        if mask_data:
                            update_shot_mask_position(y_offset=self.vertPosSpinBox.value(), z_distance=self.zDistSpinBox.value())
                            print(f"Automatically created shot mask: {mask_data}")
            except Exception as e:
                cmds.warning(f"Failed to setup image planes or shot mask: {str(e)}")
                import traceback
                traceback.print_exc()
            old_time_unit = cmds.currentUnit(query=True, time=True)
            cmds.currentUnit(time="film")
            panel = get_valid_model_panel()
            if not panel:
                cmds.confirmDialog(title="Error", message="No valid model panel found.", button=["OK"])
                return
            old_camera = cmds.modelEditor(panel, query=True, camera=True)
            print(f"Setting panel {panel} to use camera {camera_transform}")
            cmds.modelEditor(panel, edit=True, camera=camera_transform)
            cmds.lookThru(camera_transform)
            cmds.setFocus(panel)
            cmds.refresh(force=True)
            QtWidgets.QApplication.processEvents()
            viewport_defaults = {}
            if self.finalPlayblastCheckbox.isChecked():
                viewport_defaults = get_viewport_defaults(panel, camera_transform)
                set_final_viewport(panel, camera_transform)
                cmds.refresh(force=True)
                QtWidgets.QApplication.processEvents()
                cmds.setFocus(panel)
                time.sleep(1.0)
            cmds.select(clear=True)
            cmds.currentTime(start_frame)
            time.sleep(0.2)
            self.playblastButton.setText("Processing...")
            self.playblastButton.setEnabled(False)
            QtWidgets.QApplication.processEvents()
            try:
                print(f"Starting playblast with camera: {camera_transform}")
                result = cmds.playblast(
                    filename=temp_path,
                    format="qt",
                    forceOverwrite=True,
                    startTime=start_frame,
                    endTime=end_frame,
                    width=width,
                    height=height,
                    quality=quality,
                    viewer=False,
                    showOrnaments=True,
                    percent=scale_value,
                    compression="H.264",
                    offScreen=False,
                    clearCache=True,
                    sound=audio_node
                )
                if not result:
                    raise Exception("Playblast command returned no output path")
                actual_output = result if result.endswith(".mov") else result + ".mov"
                prog = QtWidgets.QProgressDialog("Creating playblast...", None, 0, 100, self)
                prog.setWindowModality(QtCore.Qt.WindowModal)
                prog.setAutoClose(True)
                prog.setCancelButton(None)
                prog.show()
                start_wait = time.time()
                while not os.path.exists(actual_output) and (time.time() - start_wait < 60):
                    prog.setValue(int((time.time() - start_wait) * 2))
                    QtWidgets.QApplication.processEvents()
                    time.sleep(0.1)
                prog.close()
                if not os.path.exists(actual_output):
                    raise Exception("Playblast file was not created within 60 seconds")
                if self.saveAsCheckbox.isChecked():
                    try:
                        if os.path.exists(final_output_path):
                            os.remove(final_output_path)
                        os.rename(actual_output, final_output_path)
                    except Exception as e:
                        raise Exception(f"Failed to move playblast file to final location: {str(e)}")
                    final_path = final_output_path
                else:
                    final_path = actual_output
                if self.finalPlayblastCheckbox.isChecked():
                    restore_viewport(panel, camera_transform, viewport_defaults)
                try:
                    if os.name == "nt":
                        os.startfile(final_path)
                    else:
                        subprocess.call(["open", final_path])
                except Exception as e:
                    cmds.warning("Failed to open video: " + str(e))
                if self.saveAsCheckbox.isChecked():
                    QtWidgets.QMessageBox.information(self, "Playblast",
                                                      "Playblast completed successfully and saved as:\n" + final_path)
                else:
                    QtWidgets.QMessageBox.information(self, "Playblast",
                                                      "Temporary playblast completed successfully (file not saved permanently):\n" + final_path)
                try:
                    if os.path.exists(temp_dir):
                        for f in os.listdir(temp_dir):
                            try:
                                os.remove(os.path.join(temp_dir, f))
                            except:
                                pass
                        os.rmdir(temp_dir)
                except:
                    pass
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Error", "Playblast failed:\n" + str(e))
                import traceback
                traceback.print_exc()
            finally:
                if self.finalPlayblastCheckbox.isChecked():
                    restore_viewport(panel, camera_transform, viewport_defaults)
                if old_camera:
                    cmds.modelEditor(panel, edit=True, camera=old_camera)
                if ip_state:
                    restore_image_planes(ip_state)
                if mask_data:
                    remove_shot_mask(mask_data)
                    self.shot_mask_data = None
                cmds.currentUnit(time=old_time_unit)
                self.playblastButton.setText("Playblast")
                self.playblastButton.setEnabled(True)
        except Exception as e:
            cmds.warning(f"Error during playblast: {str(e)}")
            import traceback
            traceback.print_exc()

    def update_filename_preview(self):
            """
            Update the filename preview label based on current inputs.
            """
            assignment = self.assignmentSpinBox.value()
            lastname = self.lastnameLineEdit.text() or "LastName"
            firstname = self.firstnameLineEdit.text() or "FirstName"
            version_type = self.versionTypeCombo.currentText()
            version_number = str(self.versionNumberSpinBox.value()).zfill(2)
            
            # Use * for preview but _ for actual filename
            filename = f"A{assignment}*{lastname}*{firstname}*{version_type}*{version_number}.mov"
            self.filenamePreviewLabel.setText(filename)

    def generate_filename(self):
        """
        Generate a filename from the inputs and place it in the output field.
        """
        assignment = self.assignmentSpinBox.value()
        lastname = self.lastnameLineEdit.text()
        firstname = self.firstnameLineEdit.text()
        version_type = self.versionTypeCombo.currentText()
        version_number = str(self.versionNumberSpinBox.value()).zfill(2)
        
        if not lastname or not firstname:
            QtWidgets.QMessageBox.warning(self, "Missing Information", 
                                        "Please enter both last name and first name.")
            return
        
        # Use underscores for the actual file
        filename = f"A{assignment}_{lastname}_{firstname}_{version_type}_{version_number}.mov"
        self.filenameLineEdit.setText(filename)
        
        # Update the artist display name field
        self.userNameLineEdit.setText(f"{firstname} {lastname}")

    def update_annotation_font_size(self, size):
        """
        Updates both the annotations in the shot mask and Maya's font preference
        """
        # First update our specific annotations if they exist
        if cmds.objExists("shotMask_TextGroup"):
            update_shot_mask_annotation_size(size)
        
        # Then update Maya's global UI font size
        update_maya_font_size(size)
        
        # Refresh the viewport to see changes
        cmds.refresh(force=True)

    def update_artist_name(self):
        """
        Update the artist name field based on first and last name
        """
        firstname = self.firstnameLineEdit.text()
        lastname = self.lastnameLineEdit.text()
        
        if firstname or lastname:
            full_name = f"{firstname} {lastname}".strip()
            self.userNameLineEdit.setText(full_name)

def show_conestoga_playblast_dialog():
    global playblast_dialog
    try:
        if playblast_dialog:
            playblast_dialog.close()
            playblast_dialog.deleteLater()
    except Exception:
        pass
    playblast_dialog = ConestogaPlayblastDialog()
    playblast_dialog.show()

if __name__ == "__main__":
    show_conestoga_playblast_dialog()


