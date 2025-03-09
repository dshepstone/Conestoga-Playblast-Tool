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
import maya.cmds as cmds

# Add script directory to path if needed
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.append(script_dir)

import conestoga_playblast_presets as presets
# Removed circular self-import:
# import conestoga_playblast_utils as utils

# ===========================================================================
# INTEGRATION UTILITIES
# ===========================================================================

def render_and_playblast(camera, output_dir=None, render_settings=None, playblast_settings=None):
    """
    Render a frame and create a playblast with the render as background.
    
    Args:
        camera (str): Camera to use
        output_dir (str): Output directory
        render_settings (dict): Render settings
        playblast_settings (dict): Playblast settings
        
    Returns:
        str: Path to playblast file
    """
    # Default settings
    if render_settings is None:
        render_settings = {}
    if playblast_settings is None:
        playblast_settings = {}
    
    # Default output directory
    if not output_dir:
        output_dir = os.path.join(cmds.workspace(query=True, rootDirectory=True), "images", "playblast_compare")
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
    
    # Store original render settings
    orig_renderer = cmds.getAttr("defaultRenderGlobals.currentRenderer")
    orig_camera = cmds.getAttr("defaultRenderGlobals.cameraName")
    
    # Configure render settings
    renderer = render_settings.get("renderer", "mayaHardware2")
    cmds.setAttr("defaultRenderGlobals.currentRenderer", renderer, type="string")
    cmds.setAttr("defaultRenderGlobals.cameraName", camera, type="string")
    
    # Set resolution if specified
    if "width" in render_settings and "height" in render_settings:
        cmds.setAttr("defaultResolution.width", render_settings["width"])
        cmds.setAttr("defaultResolution.height", render_settings["height"])
    
    try:
        # Render frame
        current_frame = cmds.currentTime(query=True)
        render_path = cmds.render(camera, x=render_settings.get("width", 1920), y=render_settings.get("height", 1080))
        
        # Create playblast with current settings
        import conestoga_playblast
        playblast_settings["camera"] = camera
        playblast_settings["output_dir"] = output_dir
        playblast_settings["show_in_viewer"] = True
        
        playblast_path = conestoga_playblast.create_playblast(**playblast_settings)
        
        return playblast_path
    
    finally:
        # Restore original render settings
        cmds.setAttr("defaultRenderGlobals.currentRenderer", orig_renderer, type="string")
        cmds.setAttr("defaultRenderGlobals.cameraName", orig_camera, type="string")


def create_gif_from_playblast(playblast_path, output_dir=None, width=None, fps=15):
    """
    Convert a playblast video to an animated GIF.
    
    Args:
        playblast_path (str): Path to playblast video
        output_dir (str): Output directory (default: same as input)
        width (int): Output width (default: half of original)
        fps (int): Frames per second for GIF
        
    Returns:
        str: Path to GIF file
    """
    if not os.path.exists(playblast_path):
        cmds.warning(f"Playblast file does not exist: {playblast_path}")
        return None
    
    ffmpeg_path = get_ffmpeg_path()
    if not ffmpeg_path:
        cmds.warning("ffmpeg not available. Cannot create GIF.")
        return None
    
    if output_dir is None:
        output_dir = os.path.dirname(playblast_path)
    
    base_name = os.path.splitext(os.path.basename(playblast_path))[0]
    gif_path = os.path.join(output_dir, f"{base_name}.gif")
    
    temp_dir = tempfile.mkdtemp()
    try:
        frames_pattern = os.path.join(temp_dir, "frame%04d.png")
        scale_opt = []
        if width:
            scale_opt = ["-vf", f"scale={width}:-1"]
        
        subprocess.run([
            ffmpeg_path,
            "-i", playblast_path,
            "-r", str(fps),
            *scale_opt,
            frames_pattern
        ], check=True)
        
        subprocess.run([
            ffmpeg_path,
            "-r", str(fps),
            "-i", frames_pattern,
            "-f", "gif",
            "-filter_complex", f"[0:v] fps={fps},split [a][b];[a] palettegen [p];[b][p] paletteuse",
            gif_path
        ], check=True)
        
        return gif_path
    
    except subprocess.CalledProcessError as e:
        cmds.warning(f"Error creating GIF: {e}")
        return None
    finally:
        shutil.rmtree(temp_dir)


def export_playblast_frames(playblast_path, output_dir=None, format="png"):
    """
    Extract individual frames from a playblast video.
    
    Args:
        playblast_path (str): Path to playblast video
        output_dir (str): Output directory (default: same as input)
        format (str): Output format (jpg, png, tif)
        
    Returns:
        str: Path to output directory
    """
    if not os.path.exists(playblast_path):
        cmds.warning(f"Playblast file does not exist: {playblast_path}")
        return None
    
    ffmpeg_path = get_ffmpeg_path()
    if not ffmpeg_path:
        cmds.warning("ffmpeg not available. Cannot extract frames.")
        return None
    
    if output_dir is None:
        base_name = os.path.splitext(os.path.basename(playblast_path))[0]
        output_dir = os.path.join(os.path.dirname(playblast_path), f"{base_name}_frames")
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    output_pattern = os.path.join(output_dir, f"frame_%04d.{format}")
    try:
        subprocess.run([
            ffmpeg_path,
            "-i", playblast_path,
            "-q:v", "1",
            output_pattern
        ], check=True)
        
        print(f"Frames extracted to {output_dir}")
        return output_dir
    except subprocess.CalledProcessError as e:
        cmds.warning(f"Error extracting frames: {e}")
        return None


def compare_playblasts(playblast_a, playblast_b, output_dir=None):
    """
    Create a side-by-side comparison video of two playblasts.
    
    Args:
        playblast_a (str): Path to first playblast
        playblast_b (str): Path to second playblast
        output_dir (str): Output directory
        
    Returns:
        str: Path to comparison video
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
        subprocess.run([
            ffmpeg_path,
            "-i", playblast_a,
            "-i", playblast_b,
            "-filter_complex", "[0:v]setpts=PTS-STARTPTS, pad=iw*2:ih[bg]; [1:v]setpts=PTS-STARTPTS[right]; [bg][right]overlay=w",
            "-c:v", "libx264",
            "-crf", "18",
            output_path
        ], check=True)
        return output_path
    except subprocess.CalledProcessError as e:
        cmds.warning(f"Error creating comparison: {e}")
        return None


# ===========================================================================
# VIEWPORT MANAGEMENT FUNCTIONS (from working_utils_v01.py)
# ===========================================================================

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
    """Configure viewport for playblast."""
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
    """Restore viewport to original settings."""
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
    """Disable image planes for playblast and track their original states."""
    if not camera or not cmds.objExists(camera):
        return None
    camera_shape = get_camera_shape(camera)
    if not camera_shape:
        return None
    image_planes = cmds.listConnections(camera_shape, type="imagePlane") or []
    image_plane_states = {}
    for image_plane in image_planes:
        display_attr = f"{image_plane}.displayMode"
        if cmds.objExists(display_attr):
            image_plane_states[image_plane] = cmds.getAttr(display_attr)
            cmds.setAttr(display_attr, 0)
    return image_plane_states

def restore_image_planes(image_plane_states):
    """Restore image planes to their original states."""
    if not image_plane_states:
        return False
    for image_plane, display_mode in image_plane_states.items():
        display_attr = f"{image_plane}.displayMode"
        if cmds.objExists(display_attr):
            cmds.setAttr(display_attr, display_mode)
    return True

def get_camera_shape(camera):
    """Return the shape node of the given camera."""
    shapes = cmds.listRelatives(camera, shapes=True)
    if shapes:
        return shapes[0]
    return None


# ===========================================================================
# SHOT MASK FUNCTIONS (from working_utils_v01.py)
# ===========================================================================

def create_shot_mask(camera, user_name, scene_name=None, text_color=None):
    """Create a shot mask for the given camera."""
    from conestoga_playblast_presets import MASK_PREFIX
    if text_color is None:
        text_color = (1.0, 1.0, 1.0)
    if scene_name is None:
        scene_path = cmds.file(query=True, sceneName=True) or "untitled"
        scene_name = os.path.basename(scene_path).split('.')[0]
    # First remove any existing shot mask
    remove_shot_mask()
    # Create main group
    mask_transform = cmds.createNode("transform", name=f"{MASK_PREFIX}transform")
    # Create materials
    mask_material = cmds.shadingNode("lambert", name=f"{MASK_PREFIX}Material", asShader=True)
    cmds.setAttr(f"{mask_material}.color", 0.15, 0.15, 0.15, type="double3")
    text_material = cmds.shadingNode("lambert", name=f"{MASK_PREFIX}TextMaterial", asShader=True)
    cmds.setAttr(f"{text_material}.color", text_color[0], text_color[1], text_color[2], type="double3")
    # Create shading groups
    mask_sg = cmds.sets(name=f"{mask_material}SG", renderable=True, noSurfaceShader=True, empty=True)
    text_sg = cmds.sets(name=f"{text_material}SG", renderable=True, noSurfaceShader=True, empty=True)
    cmds.connectAttr(f"{mask_material}.outColor", f"{mask_sg}.surfaceShader", force=True)
    cmds.connectAttr(f"{text_material}.outColor", f"{text_sg}.surfaceShader", force=True)
    # Create border planes
    top_bar = cmds.polyPlane(name=f"{MASK_PREFIX}TopBar", width=1, height=0.1, subdivisionsX=1, subdivisionsY=1)[0]
    bottom_bar = cmds.polyPlane(name=f"{MASK_PREFIX}BottomBar", width=1, height=0.1, subdivisionsX=1, subdivisionsY=1)[0]
    cmds.setAttr(f"{top_bar}.translateY", 0.5)
    cmds.setAttr(f"{bottom_bar}.translateY", -0.5)
    cmds.parent(top_bar, mask_transform)
    cmds.parent(bottom_bar, mask_transform)
    # Assign materials to planes
    cmds.sets(top_bar, edit=True, forceElement=mask_sg)
    cmds.sets(bottom_bar, edit=True, forceElement=mask_sg)
    # Create text for the shot mask
    create_shot_mask_text(mask_transform, scene_name, user_name, text_sg)
    # Position and scale the mask
    camera_shape = get_camera_shape(camera)
    if camera_shape:
        cmds.parentConstraint(camera, mask_transform, maintainOffset=False)
        cmds.setAttr(f"{mask_transform}.translateZ", -1.0)
        mask_scale = 0.25
        cmds.setAttr(f"{mask_transform}.scale", mask_scale, mask_scale, mask_scale, type="double3")
    # Add attributes for customization
    cmds.addAttr(mask_transform, longName="maskScale", attributeType="float", defaultValue=0.25)
    cmds.setAttr(f"{mask_transform}.maskScale", edit=True, keyable=True)
    cmds.addAttr(mask_transform, longName="opacity", attributeType="float", defaultValue=1.0)
    cmds.setAttr(f"{mask_transform}.opacity", edit=True, keyable=True)
    mask_data = {
        "transform": mask_transform,
        "material": mask_material,
        "text_material": text_material,
        "top_bar": top_bar,
        "bottom_bar": bottom_bar,
        "camera": camera
    }
    return mask_data

def create_shot_mask_text(mask_transform, scene_name, user_name, text_sg):
    """Create text elements for the shot mask."""
    import datetime
    current_time = int(cmds.currentTime(query=True))
    time_unit = cmds.currentUnit(query=True, time=True)
    fps = 24
    if time_unit == "film":
        fps = 24
    elif time_unit == "pal":
        fps = 25
    elif time_unit == "ntsc":
        fps = 30
    elif time_unit.endswith("fps"):
        fps = float(time_unit[:-3])
    today = datetime.datetime.today()
    date_str = today.strftime("%Y-%m-%d")
    text_scale = 0.04
    text_positions = {
        "Scene": {"text": f"Scene: {scene_name}", "pos": (-0.45, 0.45)},
        "FPS": {"text": f"FPS: {fps}", "pos": (0.45, 0.45)},
        "Artist": {"text": f"Artist: {user_name}", "pos": (-0.45, -0.45)},
    }
    for key, value in text_positions.items():
        text_obj = cmds.textCurves(ch=0, f="Arial", t=value["text"])[0]
        cmds.parent(text_obj, mask_transform)
        cmds.setAttr(f"{text_obj}.translate", value["pos"][0], value["pos"][1], 0, type="double3")
        cmds.setAttr(f"{text_obj}.scale", text_scale, text_scale, text_scale, type="double3")
        cmds.sets(text_obj, edit=True, forceElement=text_sg)

def remove_shot_mask():
    """Remove any existing shot mask from the scene."""
    from conestoga_playblast_presets import MASK_PREFIX
    existing = cmds.ls(f"{MASK_PREFIX}*", type="transform")
    if existing:
        cmds.delete(existing)

def toggle_shot_mask(camera=None, user_name=None):
    """
    Toggle the shot mask on or off.
    
    If a shot mask exists (identified by a common prefix), remove it.
    Otherwise, create a new shot mask using the active camera.
    """
    # Use the prefix defined in presets
    from conestoga_playblast_presets import MASK_PREFIX
    # Look for existing shot mask nodes
    existing_masks = cmds.ls(f"{MASK_PREFIX}*")
    if existing_masks:
        for node in existing_masks:
            cmds.delete(node)
        cmds.inViewMessage(amg="Shot mask removed.", pos='midCenter', fade=True)
    else:
        # If no camera provided, try to get the active camera
        if camera is None:
            panel = get_valid_model_panel()  # Make sure this function exists
            if panel:
                camera = cmds.modelPanel(panel, query=True, camera=True)
        # Use current user name if not provided
        if user_name is None:
            import getpass
            user_name = getpass.getuser()
        # Create a new shot mask
        mask = create_shot_mask(camera, user_name)
        if mask:
            cmds.inViewMessage(amg="Shot mask created.", pos='midCenter', fade=True)

# ===========================================================================
# PLAYBLAST REPORTING
# ===========================================================================

def generate_playblast_report(playblast_path, report_dir=None, include_screenshot=True):
    """
    Generate a report with details about a playblast.
    
    Args:
        playblast_path (str): Path to playblast file
        report_dir (str): Output directory for report
        include_screenshot (bool): Include a screenshot in the report
        
    Returns:
        str: Path to report file
    """
    if not os.path.exists(playblast_path):
        cmds.warning(f"Playblast file does not exist: {playblast_path}")
        return None
    
    if report_dir is None:
        report_dir = os.path.dirname(playblast_path)
    
    if not os.path.exists(report_dir):
        os.makedirs(report_dir)
    
    base_name = os.path.splitext(os.path.basename(playblast_path))[0]
    file_ext = os.path.splitext(playblast_path)[1]
    file_size = os.path.getsize(playblast_path) / (1024 * 1024)
    
    scene_path = cmds.file(query=True, sceneName=True)
    scene_name = os.path.basename(scene_path) if scene_path else "untitled"
    
    creation_time = datetime.datetime.fromtimestamp(os.path.getctime(playblast_path))
    creation_date = creation_time.strftime("%Y-%m-%d %H:%M:%S")
    
    user = os.getenv("USER") or os.getenv("USERNAME") or "unknown"
    
    screenshot_path = None
    if include_screenshot and is_ffmpeg_available():
        ffmpeg_path = get_ffmpeg_path()
        screenshot_path = os.path.join(report_dir, f"{base_name}_screenshot.jpg")
        try:
            subprocess.run([
                ffmpeg_path,
                "-i", playblast_path,
                "-ss", "00:00:00",
                "-vframes", "1",
                "-q:v", "1",
                screenshot_path
            ], check=True)
        except:
            screenshot_path = None
    
    report_path = os.path.join(report_dir, f"{base_name}_report.html")
    
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Playblast Report - {base_name}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .header {{ background-color: #333; color: white; padding: 10px; }}
        .content {{ padding: 15px; }}
        .info-table {{ border-collapse: collapse; width: 100%; }}
        .info-table td, .info-table th {{ border: 1px solid #ddd; padding: 8px; }}
        .info-table tr:nth-child(even) {{ background-color: #f2f2f2; }}
        .screenshot {{ max-width: 100%; height: auto; margin-top: 20px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Playblast Report</h1>
    </div>
    <div class="content">
        <h2>{base_name}</h2>
        
        <h3>File Information</h3>
        <table class="info-table">
            <tr><td>Filename</td><td>{os.path.basename(playblast_path)}</td></tr>
            <tr><td>Format</td><td>{file_ext[1:].upper()}</td></tr>
            <tr><td>Size</td><td>{file_size:.2f} MB</td></tr>
            <tr><td>Creation Date</td><td>{creation_date}</td></tr>
            <tr><td>Path</td><td>{playblast_path}</td></tr>
        </table>
        
        <h3>Scene Information</h3>
        <table class="info-table">
            <tr><td>Scene Name</td><td>{scene_name}</td></tr>
            <tr><td>Scene Path</td><td>{scene_path}</td></tr>
            <tr><td>User</td><td>{user}</td></tr>
        </table>
        
        <h3>Maya Information</h3>
        <table class="info-table">
            <tr><td>Maya Version</td><td>{cmds.about(version=True)}</td></tr>
            <tr><td>OS</td><td>{platform.system()} {platform.release()}</td></tr>
        </table>
"""
    if screenshot_path and os.path.exists(screenshot_path):
        rel_path = os.path.relpath(screenshot_path, report_dir)
        html_content += f"""
        <h3>Screenshot</h3>
        <img class="screenshot" src="{rel_path}" alt="Playblast Screenshot">
"""
    html_content += """
    </div>
</body>
</html>
"""
    with open(report_path, 'w') as f:
        f.write(html_content)
    
    return report_path


def create_playblast_thumbnail(playblast_path, output_dir=None, width=320):
    """
    Create a thumbnail image from a playblast.
    
    Args:
        playblast_path (str): Path to playblast file
        output_dir (str): Output directory
        width (int): Thumbnail width
        
    Returns:
        str: Path to thumbnail image
    """
    if not os.path.exists(playblast_path):
        cmds.warning(f"Playblast file does not exist: {playblast_path}")
        return None
    
    ffmpeg_path = get_ffmpeg_path()
    if not ffmpeg_path:
        cmds.warning("ffmpeg not available. Cannot create thumbnail.")
        return None
    
    if output_dir is None:
        output_dir = os.path.dirname(playblast_path)
    
    base_name = os.path.splitext(os.path.basename(playblast_path))[0]
    thumb_path = os.path.join(output_dir, f"{base_name}_thumb.jpg")
    
    try:
        subprocess.run([
            ffmpeg_path,
            "-i", playblast_path,
            "-ss", "00:00:00",
            "-vframes", "1",
            "-vf", f"scale={width}:-1",
            "-q:v", "1",
            thumb_path
        ], check=True)
        return thumb_path
    except subprocess.CalledProcessError as e:
        cmds.warning(f"Error creating thumbnail: {e}")
        return None


# ===========================================================================
# SOCIAL MEDIA UTILITIES
# ===========================================================================

def prepare_for_social_media(playblast_path, platform="all", output_dir=None):
    """
    Prepare playblast for sharing on social media platforms.
    
    Args:
        playblast_path (str): Path to playblast file
        platform (str): Target platform (instagram, twitter, tiktok, youtube, all)
        output_dir (str): Output directory
        
    Returns:
        dict: Paths to created files for each platform
    """
    if not os.path.exists(playblast_path):
        cmds.warning(f"Playblast file does not exist: {playblast_path}")
        return None
    
    ffmpeg_path = get_ffmpeg_path()
    if not ffmpeg_path:
        cmds.warning("ffmpeg not available. Cannot prepare for social media.")
        return None
    
    if output_dir is None:
        base_name = os.path.splitext(os.path.basename(playblast_path))[0]
        output_dir = os.path.join(os.path.dirname(playblast_path), f"{base_name}_social")
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    results = {}
    base_name = os.path.splitext(os.path.basename(playblast_path))[0]
    
    platform_settings = {
        "instagram": {
            "max_width": 1080,
            "max_height": 1350,
            "aspect_ratio": "1:1",
            "alt_ratio": "4:5",
            "audio_bitrate": "128k",
        },
        "twitter": {
            "max_width": 1280,
            "max_height": 720,
            "aspect_ratio": "16:9",
            "audio_bitrate": "128k",
        },
        "tiktok": {
            "max_width": 1080,
            "max_height": 1920,
            "aspect_ratio": "9:16",
            "audio_bitrate": "128k",
        },
        "youtube": {
            "max_width": 1920,
            "max_height": 1080,
            "aspect_ratio": "16:9",
            "audio_bitrate": "192k",
        },
    }
    
    if platform.lower() == "all":
        platforms_to_process = platform_settings.keys()
    else:
        platforms_to_process = [platform.lower()]
    
    for platform_name in platforms_to_process:
        if platform_name not in platform_settings:
            cmds.warning(f"Unknown platform: {platform_name}")
            continue
        settings = platform_settings[platform_name]
        output_path = os.path.join(output_dir, f"{base_name}_{platform_name}.mp4")
        filter_complex = f"[0:v]scale={settings['max_width']}:{settings['max_height']}:force_original_aspect_ratio=decrease,pad={settings['max_width']}:{settings['max_height']}:(ow-iw)/2:(oh-ih)/2"
        try:
            subprocess.run([
                ffmpeg_path,
                "-i", playblast_path,
                "-vf", filter_complex,
                "-c:v", "libx264",
                "-crf", "18",
                "-c:a", "aac",
                "-b:a", settings["audio_bitrate"],
                "-movflags", "+faststart",
                output_path
            ], check=True)
            results[platform_name] = output_path
        except subprocess.CalledProcessError as e:
            cmds.warning(f"Error processing for {platform_name}: {e}")
    
    return results


def export_camera_path_for_overlay(camera, start_frame, end_frame, output_dir=None):
    """
    Export camera movement data for overlay visualization.
    
    Args:
        camera (str): Camera name
        start_frame (int): Start frame
        end_frame (int): End frame
        output_dir (str): Output directory
        
    Returns:
        str: Path to exported data file
    """
    if not cmds.objExists(camera):
        cmds.warning(f"Camera does not exist: {camera}")
        return None
    
    camera_shape = get_camera_shape(camera)
    if not camera_shape:
        return None
    
    if output_dir is None:
        output_dir = cmds.workspace(query=True, rootDirectory=True)
    
    output_path = os.path.join(output_dir, f"{camera}_path.json")
    camera_data = []
    
    for frame in range(int(start_frame), int(end_frame) + 1):
        cmds.currentTime(frame, edit=True)
        pos = cmds.xform(camera, query=True, translation=True, worldSpace=True)
        rot = cmds.xform(camera, query=True, rotation=True, worldSpace=True)
        camera_data.append({"frame": frame, "position": pos, "rotation": rot})
    
    with open(output_path, 'w') as f:
        json.dump(camera_data, f, indent=4)
    
    return output_path


# ===========================================================================
# FFmpeg UTILITY FUNCTIONS
# ===========================================================================

def get_ffmpeg_path():
    """
    Retrieve the FFmpeg executable path from presets or environment.
    
    Returns:
        str: Path to FFmpeg executable or None if not found.
    """
    ffmpeg_path = presets.CUSTOM_LOCATIONS.get("ffmpeg_path", "")
    if ffmpeg_path and os.path.exists(ffmpeg_path):
        return ffmpeg_path
    return None

def is_ffmpeg_available():
    """
    Check if FFmpeg is available.
    
    Returns:
        bool: True if FFmpeg is available, False otherwise.
    """
    return get_ffmpeg_path() is not None
