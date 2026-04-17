"""
Conestoga Playblast Tool - Extra Utilities
This module provides additional utilities and integrations for the playblast tool.
"""

import os
import sys
import json
import subprocess
import datetime
import platform
import tempfile
import shutil
import re
import getpass

import maya.cmds as cmds
import maya.mel as mel

import conestoga_playblast_presets as presets

# --------------------------------------------
# Utility Functions
# --------------------------------------------

def get_frame_rate():
    """Get the current frame rate in Maya."""
    rate_str = cmds.currentUnit(q=True, time=True)
    if rate_str == "game":
        return 15.0
    elif rate_str == "film":
        return 24.0
    elif rate_str == "pal":
        return 25.0
    elif rate_str == "ntsc":
        return 30.0
    elif rate_str == "show":
        return 48.0
    elif rate_str == "palf":
        return 50.0
    elif rate_str == "ntscf":
        return 60.0
    elif rate_str.endswith("fps"):
        return float(rate_str[:-3])
    else:
        raise RuntimeError("Unsupported frame rate: " + rate_str)

def get_valid_model_panel():
    """Return a valid model panel (the first found)."""
    panels = cmds.getPanel(type="modelPanel")
    if panels:
        return panels[0]
    return None

# --------------------------------------------
# Playblast Helper Functions
# --------------------------------------------

def render_and_playblast(camera, output_dir=None, render_settings=None, playblast_settings=None):
    """
    Render a frame and create a playblast with the render as background.
    
    (Dummy implementation; adapt as needed.)
    """
    if render_settings is None:
        render_settings = {}
    if playblast_settings is None:
        playblast_settings = {}

    if not output_dir:
        output_dir = os.path.join(cmds.workspace(q=True, rootDirectory=True), "images", "playblast_compare")
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

    orig_renderer = cmds.getAttr("defaultRenderGlobals.currentRenderer")
    orig_camera = cmds.getAttr("defaultRenderGlobals.cameraName")
    
    renderer = render_settings.get("renderer", "mayaHardware2")
    cmds.setAttr("defaultRenderGlobals.currentRenderer", renderer, type="string")
    cmds.setAttr("defaultRenderGlobals.cameraName", camera, type="string")
    
    if "width" in render_settings and "height" in render_settings:
        cmds.setAttr("defaultResolution.width", render_settings["width"])
        cmds.setAttr("defaultResolution.height", render_settings["height"])
    
    try:
        current_frame = cmds.currentTime(q=True)
        render_path = cmds.render(camera, x=render_settings.get("width", 1920), y=render_settings.get("height", 1080))
        
        import conestoga_playblast
        playblast_settings["camera"] = camera
        playblast_settings["output_dir"] = output_dir
        playblast_settings["show_in_viewer"] = True
        
        playblast_path = conestoga_playblast.create_playblast(**playblast_settings)
        return playblast_path
    finally:
        cmds.setAttr("defaultRenderGlobals.currentRenderer", orig_renderer, type="string")
        cmds.setAttr("defaultRenderGlobals.cameraName", orig_camera, type="string")

def create_gif_from_playblast(playblast_path, output_dir=None, width=None, fps=15):
    """
    Convert a playblast video to an animated GIF.
    """
    if not os.path.exists(playblast_path):
        cmds.warning("Playblast file does not exist: " + playblast_path)
        return None
    ffmpeg_path = get_ffmpeg_path()
    if not ffmpeg_path:
        cmds.warning("ffmpeg not available. Cannot create GIF.")
        return None
    if output_dir is None:
        output_dir = os.path.dirname(playblast_path)
    base_name = os.path.splitext(os.path.basename(playblast_path))[0]
    gif_path = os.path.join(output_dir, base_name + ".gif")
    temp_dir = tempfile.mkdtemp()
    try:
        frames_pattern = os.path.join(temp_dir, "frame%04d.png")
        scale_opt = []
        if width:
            scale_opt = ["-vf", "scale={0}:-1".format(width)]
        subprocess.run([ffmpeg_path, "-i", playblast_path, "-r", str(fps)] + scale_opt + [frames_pattern], check=True)
        subprocess.run([ffmpeg_path, "-r", str(fps), "-i", frames_pattern, "-f", "gif",
                        "-filter_complex", "[0:v] fps={0},split [a][b];[a] palettegen [p];[b][p] paletteuse".format(fps),
                        gif_path], check=True)
        return gif_path
    except subprocess.CalledProcessError as e:
        cmds.warning("Error creating GIF: " + str(e))
        return None
    finally:
        shutil.rmtree(temp_dir)

def get_ffmpeg_path():
    """Return the FFmpeg executable path from environment or optionVar."""
    ffmpeg_env = os.environ.get("FFMPEG_PATH", "")
    if ffmpeg_env and os.path.exists(ffmpeg_env):
        return ffmpeg_env
    if cmds.optionVar(exists="conestogaFFmpegPath"):
        ffmpeg_path = cmds.optionVar(q="conestogaFFmpegPath")
        if os.path.exists(ffmpeg_path):
            return ffmpeg_path
    return ""

def is_ffmpeg_available():
    """Check if FFmpeg is available."""
    return bool(get_ffmpeg_path())

# --------------------------------------------
# Viewport Management Functions
# --------------------------------------------

def get_viewport_defaults(model_panel, camera):
    """Get default viewport settings for restoration later."""
    if not model_panel or not cmds.modelPanel(model_panel, exists=True):
        return None
    defaults = {}
    defaults["camera"] = cmds.modelPanel(model_panel, query=True, camera=True)
    for item_name, command_flag in presets.VIEWPORT_VISIBILITY_LOOKUP:
        try:
            defaults[command_flag] = cmds.modelEditor(model_panel, query=True, **{command_flag: True})
        except Exception:
            defaults[command_flag] = False
    return defaults

def set_final_viewport(model_panel, camera, viewport_preset="Standard"):
    """Configure the viewport for playblast based on a preset."""
    if not model_panel or not cmds.modelPanel(model_panel, exists=True):
        return False
    cmds.lookThru(camera)
    visibility_flags = {}
    if viewport_preset in presets.VIEWPORT_VISIBILITY_PRESETS:
        preset_items = presets.VIEWPORT_VISIBILITY_PRESETS[viewport_preset]
        for item_name, command_flag in presets.VIEWPORT_VISIBILITY_LOOKUP:
            visibility_flags[command_flag] = item_name in preset_items
    for flag, value in visibility_flags.items():
        try:
            cmds.modelEditor(model_panel, edit=True, **{flag: value})
        except Exception:
            pass
    return True

def restore_viewport(model_panel, camera, viewport_defaults):
    """Restore the viewport to its original settings."""
    if not model_panel or not viewport_defaults:
        return False
    if "camera" in viewport_defaults and viewport_defaults["camera"]:
        try:
            cmds.lookThru(viewport_defaults["camera"])
        except Exception:
            pass
    for command_flag, value in viewport_defaults.items():
        if command_flag == "camera":
            continue
        try:
            cmds.modelEditor(model_panel, edit=True, **{command_flag: value})
        except Exception:
            pass
    return True

def disable_image_planes(camera):
    """Disable image planes for the specified camera and store their original states."""
    if not camera or not cmds.objExists(camera):
        return None
    camera_shape = get_camera_shape(camera)
    if not camera_shape:
        return None
    image_planes = cmds.listConnections(camera_shape, type="imagePlane") or []
    image_plane_states = {}
    for image_plane in image_planes:
        display_attr = image_plane + ".displayMode"
        if cmds.objExists(display_attr):
            image_plane_states[image_plane] = cmds.getAttr(display_attr)
            cmds.setAttr(display_attr, 0)
    return image_plane_states

def restore_image_planes(image_plane_states):
    """Restore image planes to their previous display states."""
    if not image_plane_states:
        return False
    for image_plane, display_mode in image_plane_states.items():
        display_attr = image_plane + ".displayMode"
        if cmds.objExists(display_attr):
            cmds.setAttr(display_attr, display_mode)
    return True

def get_camera_shape(camera):
    """Return the shape node for a given camera."""
    shapes = cmds.listRelatives(camera, shapes=True)
    if shapes:
        return shapes[0]
    return None

# --------------------------------------------
# Shot Mask Functions (Zurbrigg-style)
# --------------------------------------------

def create_shot_mask(camera, user_name):
    """
    Create a shot mask overlay for the specified camera using a process similar to Zurbrigg's.
    
    This method creates border planes and text labels. Instead of leaving text as curves (which
    causes membership restrictions when assigning shaders), it converts the text curves to polygons.
    
    Returns the name of the mask transform.
    """
    # Use MASK_PREFIX from presets (default if not defined)
    mask_prefix = presets.MASK_PREFIX if hasattr(presets, "MASK_PREFIX") else "cone_shotmask_"
    
    # Remove any existing shot mask.
    remove_shot_mask()
    
    # Create a main transform for the mask.
    mask_transform = cmds.createNode("transform", name=f"{mask_prefix}transform")
    
    # Create border material.
    mask_material = cmds.shadingNode("lambert", asShader=True, name=f"{mask_prefix}Material")
    cmds.setAttr(f"{mask_material}.color", 0.15, 0.15, 0.15, type="double3")
    
    # Create text material.
    text_material = cmds.shadingNode("lambert", asShader=True, name=f"{mask_prefix}TextMaterial")
    cmds.setAttr(f"{text_material}.color", 1.0, 1.0, 1.0, type="double3")
    
    # Create shading groups.
    mask_sg = cmds.sets(renderable=True, noSurfaceShader=True, empty=True, name=f"{mask_material}SG")
    text_sg = cmds.sets(renderable=True, noSurfaceShader=True, empty=True, name=f"{text_material}SG")
    cmds.connectAttr(f"{mask_material}.outColor", f"{mask_sg}.surfaceShader", force=True)
    cmds.connectAttr(f"{text_material}.outColor", f"{text_sg}.surfaceShader", force=True)
    
    # Create border planes.
    top_bar = cmds.polyPlane(name=f"{mask_prefix}TopBar", width=1, height=0.1, subdivisionsX=1, subdivisionsY=1)[0]
    bottom_bar = cmds.polyPlane(name=f"{mask_prefix}BottomBar", width=1, height=0.1, subdivisionsX=1, subdivisionsY=1)[0]
    cmds.setAttr(f"{top_bar}.translateY", 0.5)
    cmds.setAttr(f"{bottom_bar}.translateY", -0.5)
    cmds.parent([top_bar, bottom_bar], mask_transform)
    cmds.sets(top_bar, edit=True, forceElement=mask_sg)
    cmds.sets(bottom_bar, edit=True, forceElement=mask_sg)
    
    # Create text for the shot mask.
    create_shot_mask_text(mask_transform, user_name, text_sg)
    
    # Constrain mask transform to the camera.
    if cmds.objExists(camera):
        cmds.parentConstraint(camera, mask_transform, maintainOffset=False)
        cmds.setAttr(f"{mask_transform}.translateZ", -1.0)
        mask_scale = 0.25
        cmds.setAttr(f"{mask_transform}.scale", mask_scale, mask_scale, mask_scale, type="double3")
    
    # Add custom attributes.
    cmds.addAttr(mask_transform, longName="maskScale", attributeType="float", defaultValue=mask_scale)
    cmds.setAttr(f"{mask_transform}.maskScale", edit=True, keyable=True)
    cmds.addAttr(mask_transform, longName="opacity", attributeType="float", defaultValue=1.0)
    cmds.setAttr(f"{mask_transform}.opacity", edit=True, keyable=True)
    
    return mask_transform

def create_shot_mask_text(mask_transform, user_name, text_sg):
    """
    Create text elements for the shot mask. This version creates text curves,
    converts them to polygons (to avoid shader assignment restrictions), and assigns them
    to the given shading group.
    """
    # Determine dynamic values.
    scene_path = cmds.file(q=True, sn=True) or "untitled"
    scene_name = os.path.basename(scene_path).split('.')[0]
    fps = get_frame_rate()
    today = datetime.date.today().strftime("%Y-%m-%d")
    text_scale = 0.04  # Adjust as needed.
    
    # Define the labels and positions.
    text_items = {
        "Scene": {"text": f"Scene: {scene_name}", "pos": (-0.45, 0.45, 0)},
        "FPS": {"text": f"FPS: {fps}", "pos": (0.45, 0.45, 0)},
        "Artist": {"text": f"Artist: {user_name}", "pos": (-0.45, -0.45, 0)},
        "Date": {"text": f"Date: {today}", "pos": (0.0, -0.45, 0)},
        "Frame": {"text": "Frame: {counter}", "pos": (0.45, -0.45, 0)}
    }
    
    for key, item in text_items.items():
        # Create text curves with Arial.
        text_curve = cmds.textCurves(ch=0, f="Arial", t=item["text"])[0]
        # Convert curves to polygons.
        poly_obj = cmds.nurbsToPoly(text_curve, mnd=1, ch=0)[0]
        cmds.delete(text_curve)
        # Parent the polygon under the mask transform.
        cmds.parent(poly_obj, mask_transform, relative=True)
        cmds.setAttr(f"{poly_obj}.translate", item["pos"][0], item["pos"][1], item["pos"][2], type="double3")
        cmds.setAttr(f"{poly_obj}.scale", text_scale, text_scale, text_scale, type="double3")
        # Assign the resulting polygon to the text shading group.
        cmds.sets(poly_obj, edit=True, forceElement=text_sg)

def remove_shot_mask():
    """
    Remove any existing shot mask from the scene.
    """
    mask_prefix = presets.MASK_PREFIX if hasattr(presets, "MASK_PREFIX") else "cone_shotmask_"
    existing = cmds.ls(f"{mask_prefix}*", type="transform")
    if existing:
        cmds.delete(existing)

def toggle_shot_mask():
    """
    Toggle the shot mask on or off.
    
    If a shot mask exists (identified by the MASK_PREFIX), remove it.
    Otherwise, create a new shot mask using the active camera.
    """
    mask_prefix = presets.MASK_PREFIX if hasattr(presets, "MASK_PREFIX") else "cone_shotmask_"
    existing = cmds.ls(f"{mask_prefix}*", type="transform")
    if existing:
        remove_shot_mask()
        cmds.inViewMessage(amg="Shot mask removed.", pos='midCenter', fade=True)
    else:
        panel = get_valid_model_panel()
        camera = cmds.modelPanel(panel, query=True, camera=True) if panel else None
        if not camera:
            cmds.warning("No valid camera found to attach the shot mask.")
            return
        user_name = getpass.getuser()
        mask = create_shot_mask(camera, user_name)
        if mask:
            cmds.inViewMessage(amg="Shot mask created.", pos='midCenter', fade=True)

# --------------------------------------------
# Additional Utility Functions
# --------------------------------------------

def export_playblast_frames(playblast_path, output_dir=None, format="png"):
    """
    Extract individual frames from a playblast video.
    """
    if not os.path.exists(playblast_path):
        cmds.warning("Playblast file does not exist: " + playblast_path)
        return None
    ffmpeg_path = get_ffmpeg_path()
    if not ffmpeg_path:
        cmds.warning("ffmpeg not available. Cannot extract frames.")
        return None
    if output_dir is None:
        base_name = os.path.splitext(os.path.basename(playblast_path))[0]
        output_dir = os.path.join(os.path.dirname(playblast_path), base_name + "_frames")
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    output_pattern = os.path.join(output_dir, "frame_%04d." + format)
    try:
        subprocess.run([ffmpeg_path, "-i", playblast_path, "-q:v", "1", output_pattern], check=True)
        print("Frames extracted to " + output_dir)
        return output_dir
    except subprocess.CalledProcessError as e:
        cmds.warning("Error extracting frames: " + str(e))
        return None

def compare_playblasts(playblast_a, playblast_b, output_dir=None):
    """
    Create a side-by-side comparison video of two playblasts.
    """
    if not os.path.exists(playblast_a) or not os.path.exists(playblast_b):
        cmds.warning("Both playblast files must exist")
        return None
    ffmpeg_path = get_ffmpeg_path()
    if not ffmpeg_path:
        cmds.warning("ffmpeg not available. Cannot create comparison.")
        return None
    if output_dir is None:
        output_dir = os.path.dirname(playblast_a)
    base_a = os.path.splitext(os.path.basename(playblast_a))[0]
    base_b = os.path.splitext(os.path.basename(playblast_b))[0]
    output_name = f"{base_a}_vs_{base_b}.mp4"
    output_path = os.path.join(output_dir, output_name)
    try:
        subprocess.run([ffmpeg_path, "-i", playblast_a, "-i", playblast_b,
                        "-filter_complex", "[0:v]setpts=PTS-STARTPTS, pad=iw*2:ih[bg]; [1:v]setpts=PTS-STARTPTS[right]; [bg][right]overlay=w",
                        "-c:v", "libx264", "-crf", "18", output_path], check=True)
        return output_path
    except subprocess.CalledProcessError as e:
        cmds.warning("Error creating comparison: " + str(e))
        return None
