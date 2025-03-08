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
    
    # Get ffmpeg path
    ffmpeg_path = get_ffmpeg_path()
    if not ffmpeg_path:
        cmds.warning("ffmpeg not available. Cannot create GIF.")
        return None
    
    # Configure output path
    if output_dir is None:
        output_dir = os.path.dirname(playblast_path)
    
    base_name = os.path.splitext(os.path.basename(playblast_path))[0]
    gif_path = os.path.join(output_dir, f"{base_name}.gif")
    
    # Create temp directory for frames
    temp_dir = tempfile.mkdtemp()
    try:
        # Extract frames with ffmpeg
        frames_pattern = os.path.join(temp_dir, "frame%04d.png")
        
        # Scale option
        scale_opt = []
        if width:
            scale_opt = ["-vf", f"scale={width}:-1"]
        
        # Extract frames
        subprocess.run([
            ffmpeg_path,
            "-i", playblast_path,
            "-r", str(fps),
            *scale_opt,
            frames_pattern
        ], check=True)
        
        # Convert frames to GIF with ffmpeg
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
        # Clean up temp directory
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
    
    # Get ffmpeg path
    ffmpeg_path = get_ffmpeg_path()
    if not ffmpeg_path:
        cmds.warning("ffmpeg not available. Cannot extract frames.")
        return None
    
    # Configure output path
    if output_dir is None:
        base_name = os.path.splitext(os.path.basename(playblast_path))[0]
        output_dir = os.path.join(os.path.dirname(playblast_path), f"{base_name}_frames")
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Configure output pattern
    output_pattern = os.path.join(output_dir, f"frame_%04d.{format}")
    
    try:
        # Extract frames with ffmpeg
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
    
    # Get ffmpeg path
    ffmpeg_path = get_ffmpeg_path()
    if not ffmpeg_path:
        cmds.warning("ffmpeg not available. Cannot create comparison.")
        return None
    
    # Configure output path
    if output_dir is None:
        output_dir = os.path.dirname(playblast_a)
    
    # Create output filename
    base_a = os.path.splitext(os.path.basename(playblast_a))[0]
    base_b = os.path.splitext(os.path.basename(playblast_b))[0]
    output_name = f"{base_a}_vs_{base_b}.mp4"
    output_path = os.path.join(output_dir, output_name)
    
    try:
        # Create side-by-side comparison with ffmpeg
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
    
    # Configure output path
    if report_dir is None:
        report_dir = os.path.dirname(playblast_path)
    
    if not os.path.exists(report_dir):
        os.makedirs(report_dir)
    
    # Get file details
    base_name = os.path.splitext(os.path.basename(playblast_path))[0]
    file_ext = os.path.splitext(playblast_path)[1]
    file_size = os.path.getsize(playblast_path) / (1024 * 1024)  # Size in MB
    
    # Get scene details
    scene_path = cmds.file(query=True, sceneName=True)
    scene_name = os.path.basename(scene_path) if scene_path else "untitled"
    
    # Get creation date
    creation_time = datetime.datetime.fromtimestamp(os.path.getctime(playblast_path))
    creation_date = creation_time.strftime("%Y-%m-%d %H:%M:%S")
    
    # Get current user
    user = os.getenv("USER") or os.getenv("USERNAME") or "unknown"
    
    # Generate screenshot if required
    screenshot_path = None
    if include_screenshot and is_ffmpeg_available():
        ffmpeg_path = get_ffmpeg_path()
        screenshot_path = os.path.join(report_dir, f"{base_name}_screenshot.jpg")
        try:
            subprocess.run([
                ffmpeg_path,
                "-i", playblast_path,
                "-ss", "00:00:00",  # Take screenshot from beginning
                "-vframes", "1",
                "-q:v", "1",
                screenshot_path
            ], check=True)
        except:
            screenshot_path = None
    
    # Create HTML report
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
    
    # Add screenshot if available
    if screenshot_path and os.path.exists(screenshot_path):
        rel_path = os.path.relpath(screenshot_path, report_dir)
        html_content += f"""
        <h3>Screenshot</h3>
        <img class="screenshot" src="{rel_path}" alt="Playblast Screenshot">
"""
    
    # Close HTML
    html_content += """
    </div>
</body>
</html>
"""
    
    # Write HTML to file
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
    
    # Get ffmpeg path
    ffmpeg_path = get_ffmpeg_path()
    if not ffmpeg_path:
        cmds.warning("ffmpeg not available. Cannot create thumbnail.")
        return None
    
    # Configure output path
    if output_dir is None:
        output_dir = os.path.dirname(playblast_path)
    
    base_name = os.path.splitext(os.path.basename(playblast_path))[0]
    thumb_path = os.path.join(output_dir, f"{base_name}_thumb.jpg")
    
    try:
        # Create thumbnail with ffmpeg
        subprocess.run([
            ffmpeg_path,
            "-i", playblast_path,
            "-ss", "00:00:00",  # Take screenshot from beginning
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
    
    # Get ffmpeg path
    ffmpeg_path = get_ffmpeg_path()
    if not ffmpeg_path:
        cmds.warning("ffmpeg not available. Cannot prepare for social media.")
        return None
    
    # Configure output path
    if output_dir is None:
        base_name = os.path.splitext(os.path.basename(playblast_path))[0]
        output_dir = os.path.join(os.path.dirname(playblast_path), f"{base_name}_social")
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    results = {}
    base_name = os.path.splitext(os.path.basename(playblast_path))[0]
    
    # Define platform-specific settings
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
    
    # Process for requested platforms
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
        
        # Build ffmpeg filter for this platform
        filter_complex = f"[0:v]scale={settings['max_width']}:{settings['max_height']}:force_original_aspect_ratio=decrease,pad={settings['max_width']}:{settings['max_height']}:(ow-iw)/2:(oh-ih)/2"
        
        try:
            # Process with ffmpeg
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
    
    # Get camera shape node
    camera_shape = get_camera_shape(camera)
    if not camera_shape:
        return None
    
    # Configure output path
    if output_dir is None:
        output_dir = cmds.workspace(query=True, rootDirectory=True)
    
    output_path = os.path.join(output_dir, f"{camera}_path.json")
    
    # Collect camera data at each frame
    camera_data = []
    
    current_frame = cmds.currentTime(query=True)
    try:
        for frame in range(start_frame, end_frame + 1):
            cmds.currentTime(frame)
            
            # Get camera position and rotation
            position = cmds.xform(camera, query=True, worldSpace=True, translation=True)
            rotation = cmds.xform(camera, query=True, worldSpace=True, rotation=True)
            focal_length = cmds.getAttr(f"{camera_shape}.focalLength")
            
            # Save frame data
            camera_data.append({
                "frame": frame,
                "position": position,
                "rotation": rotation,
                "focal_length": focal_length
            })
    
    finally:
        # Restore original frame
        cmds.currentTime(current_frame)
    
    # Write data to file
    with open(output_path, 'w') as f:
        json.dump(camera_data, f, indent=2)
    
    return output_path

def remove_shot_mask():
    """Remove the shot mask if it exists."""
    import maya.cmds as cmds
    from conestoga_playblast_presets import MASK_PREFIX
    
    # Find all shot mask nodes
    mask_nodes = []
    
    # Try to find transform nodes
    transforms = cmds.ls(MASK_PREFIX + "*", type="transform")
    if transforms:
        mask_nodes.extend(transforms)
    
    # Try to find materials
    materials = cmds.ls(MASK_PREFIX + "*Material", type="lambert")
    if materials:
        mask_nodes.extend(materials)
    
    # Try to find textures
    textures = cmds.ls(MASK_PREFIX + "*Text", type="mesh")
    if textures:
        mask_nodes.extend(textures)
    
    # Delete all found nodes
    if mask_nodes:
        try:
            cmds.delete(mask_nodes)
            print(f"Shot mask removed: {len(mask_nodes)} nodes deleted")
            return True
        except Exception as e:
            print(f"Error removing shot mask: {str(e)}")
    
    return False

def get_maya_main_window():
    """Get Maya's main window as a Qt widget."""
    import maya.OpenMayaUI as omui
    
    # Add these Qt imports inside the function
    try:
        from PySide6 import QtWidgets
    except ImportError:
        try:
            from PySide2 import QtWidgets
        except ImportError:
            from PySide import QtWidgets
    
    try:
        from shiboken2 import wrapInstance
    except ImportError:
        from shiboken6 import wrapInstance
    
    ptr = omui.MQtUtil.mainWindow()
    if ptr is not None:
        return wrapInstance(int(ptr), QtWidgets.QWidget)
    return None

def get_ffmpeg_path():
    """Get the configured FFmpeg path."""
    # Try to get from option var first
    path = cmds.optionVar(q="ffmpegPath") if cmds.optionVar(exists="ffmpegPath") else ""
    
    # If not set, try some common locations
    if not path or not os.path.exists(path):
        if platform.system() == "Windows":
            common_paths = [
                os.path.join(os.environ.get("ProgramFiles", "C:\\Program Files"), "ffmpeg", "bin", "ffmpeg.exe"),
                os.path.join(os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)"), "ffmpeg", "bin", "ffmpeg.exe")
            ]
        elif platform.system() == "Darwin":
            common_paths = [
                "/usr/local/bin/ffmpeg",
                "/opt/homebrew/bin/ffmpeg"
            ]
        else:  # Linux
            common_paths = [
                "/usr/bin/ffmpeg",
                "/usr/local/bin/ffmpeg"
            ]
            
        for common_path in common_paths:
            if os.path.exists(common_path):
                path = common_path
                break
    
    return path

def is_ffmpeg_available():
    """Check if FFmpeg is available."""
    ffmpeg_path = get_ffmpeg_path()
    if not ffmpeg_path or not os.path.exists(ffmpeg_path):
        return False
        
    try:
        subprocess.run([ffmpeg_path, "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return True
    except (subprocess.SubprocessError, OSError):
        return False

def get_camera_shape(camera):
    """Get the shape node of a camera."""
    if not cmds.objExists(camera):
        return None
        
    # Check if it's already a shape node
    if cmds.nodeType(camera) == "camera":
        return camera
        
    # Get shape node from transform
    shapes = cmds.listRelatives(camera, shapes=True, type="camera")
    if shapes:
        return shapes[0]
        
    return None

def get_valid_model_panel():
    """Get a valid model panel that is visible."""
    panel = cmds.getPanel(withFocus=True)
    if cmds.getPanel(typeOf=panel) == "modelPanel":
        return panel
    model_panels = cmds.getPanel(type="modelPanel")
    for panel in model_panels:
        if cmds.modelPanel(panel, query=True, visible=True):
            return panel
    return None

def toggle_shot_mask():
    """Toggle the shot mask on/off."""
    from conestoga_playblast_presets import MASK_PREFIX
    mask_nodes = cmds.ls(MASK_PREFIX + "*", type="transform")
    
    if mask_nodes:
        remove_shot_mask()
        return False
    else:
        import conestoga_playblast
        conestoga_playblast.show_ui()
        return True

def create_shot_mask(camera, user_name, scene_name=None, text_color=None):
    """Create a shot mask for the given camera."""
    import maya.cmds as cmds
    from conestoga_playblast_presets import MASK_PREFIX
    
    if text_color is None:
        text_color = (1.0, 1.0, 1.0)
    
    if scene_name is None:
        scene_path = cmds.file(query=True, sceneName=True) or "untitled"
        scene_name = os.path.basename(scene_path).split('.')[0]
    
    mask_transform = cmds.createNode("transform", name=f"{MASK_PREFIX}transform")
    
    mask_material = cmds.createNode("lambert", name=f"{MASK_PREFIX}Material")
    cmds.setAttr(f"{mask_material}.color", 0.15, 0.15, 0.15, type="double3")
    cmds.setAttr(f"{mask_material}.transparency", 0, 0, 0, type="double3")
    
    text_material = cmds.createNode("lambert", name=f"{MASK_PREFIX}TextMaterial")
    cmds.setAttr(f"{text_material}.color", text_color[0], text_color[1], text_color[2], type="double3")
    cmds.setAttr(f"{text_material}.transparency", 0, 0, 0, type="double3")
    
    top_bar = cmds.polyPlane(name=f"{MASK_PREFIX}TopBar", width=1, height=0.1, subdivisionsX=1, subdivisionsY=1)[0]
    bottom_bar = cmds.polyPlane(name=f"{MASK_PREFIX}BottomBar", width=1, height=0.1, subdivisionsX=1, subdivisionsY=1)[0]
    
    cmds.setAttr(f"{top_bar}.translateY", 0.5)
    cmds.setAttr(f"{bottom_bar}.translateY", -0.5)
    
    cmds.parent(top_bar, mask_transform)
    cmds.parent(bottom_bar, mask_transform)
    
    cmds.select(top_bar, bottom_bar)
    cmds.hyperShade(assign=mask_material)
    
    camera_shape = get_camera_shape(camera)
    if camera_shape:
        cmds.parentConstraint(camera, mask_transform, maintainOffset=False)
        cmds.setAttr(f"{mask_transform}.translateZ", -1.0)
        mask_scale = 0.25
        cmds.setAttr(f"{mask_transform}.scale", mask_scale, mask_scale, mask_scale, type="double3")
    
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

def update_shot_mask_scale(scale):
    """Update the scale of the shot mask."""
    import maya.cmds as cmds
    from conestoga_playblast_presets import MASK_PREFIX
    mask_transform = cmds.ls(f"{MASK_PREFIX}transform", type="transform")
    if mask_transform:
        cmds.setAttr(f"{mask_transform[0]}.scale", scale, scale, scale, type="double3")
        cmds.setAttr(f"{mask_transform[0]}.maskScale", scale)
        return True
    return False

def update_shot_mask_position(y_offset=0.0, z_distance=-1.0):
    """Update the position of the shot mask."""
    import maya.cmds as cmds
    from conestoga_playblast_presets import MASK_PREFIX
    mask_transform = cmds.ls(f"{MASK_PREFIX}transform", type="transform")
    if mask_transform:
        cmds.setAttr(f"{mask_transform[0]}.translateY", y_offset)
        cmds.setAttr(f"{mask_transform[0]}.translateZ", z_distance)
        return True
    return False

def update_shot_mask_text_color(color):
    """Update the text color of the shot mask."""
    import maya.cmds as cmds
    from conestoga_playblast_presets import MASK_PREFIX
    text_material = cmds.ls(f"{MASK_PREFIX}TextMaterial", type="lambert")
    if text_material:
        cmds.setAttr(f"{text_material[0]}.color", color[0], color[1], color[2], type="double3")
        return True
    return False

def update_shot_mask_opacity(opacity):
    """Update the opacity of the shot mask."""
    import maya.cmds as cmds
    from conestoga_playblast_presets import MASK_PREFIX
    mask_transform = cmds.ls(f"{MASK_PREFIX}transform", type="transform")
    mask_material = cmds.ls(f"{MASK_PREFIX}Material", type="lambert")
    text_material = cmds.ls(f"{MASK_PREFIX}TextMaterial", type="lambert")
    
    if mask_transform:
        cmds.setAttr(f"{mask_transform[0]}.opacity", opacity)
    
    if mask_material:
        transparency = 1.0 - opacity
        cmds.setAttr(f"{mask_material[0]}.transparency", transparency, transparency, transparency, type="double3")
    
    if text_material:
        transparency = 1.0 - opacity
        cmds.setAttr(f"{text_material[0]}.transparency", transparency, transparency, transparency, type="double3")
    
    return mask_material or text_material

def safe_execute(func):
    """Decorator for safely executing functions with error handling."""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            cmds.warning(f"Error in {func.__name__}: {str(e)}")
            import traceback
            traceback.print_exc()
            return None
    return wrapper

def encode_with_ffmpeg(input_path, output_path, settings=None):
    """
    Encode video using FFmpeg with specified settings.
    
    Args:
        input_path (str): Input file or pattern (e.g., '%04d.png')
        output_path (str): Output file path
        settings (dict): Encoding settings
        
    Returns:
        bool: True if successful, False otherwise
    """
    if settings is None:
        settings = {}
        
    ffmpeg_path = get_ffmpeg_path()
    if not ffmpeg_path:
        cmds.warning("FFmpeg not available. Cannot encode video.")
        return False
        
    encoder = settings.get("encoder", "h264")
    quality = settings.get("quality", "High")
    preset = settings.get("preset", "fast")
    framerate = settings.get("framerate", 24)
    
    args = [ffmpeg_path, "-y"]
    
    if input_path.endswith(".%04d.png") or input_path.endswith(".%04d.jpg") or input_path.endswith(".%04d.tif"):
        args.extend(["-framerate", str(framerate), "-i", input_path])
    else:
        args.extend(["-i", input_path])
    
    audio_path = settings.get("audio_path", None)
    audio_offset = settings.get("audio_offset", 0)
    if audio_path and os.path.exists(audio_path):
        args.extend(["-ss", str(audio_offset), "-i", audio_path])
    
    if encoder == "h264":
        h264_qualities = {
            "Very High": 18,
            "High": 20,
            "Medium": 23,
            "Low": 26
        }
        crf = h264_qualities.get(quality, 23)
        args.extend([
            "-c:v", "libx264",
            "-crf", str(crf),
            "-preset", preset,
            "-pix_fmt", "yuv420p"
        ])
    elif encoder == "prores":
        prores_profiles = {
            "ProRes 422 Proxy": 0,
            "ProRes 422 LT": 1,
            "ProRes 422": 2,
            "ProRes 422 HQ": 3,
            "ProRes 4444": 4,
            "ProRes 4444 XQ": 5
        }
        profile = prores_profiles.get(quality, 3)
        args.extend([
            "-c:v", "prores_ks",
            "-profile:v", str(profile),
            "-vendor", "apl0",
            "-pix_fmt", "yuv422p10le"
        ])
        
    if audio_path and os.path.exists(audio_path):
        args.extend(["-c:a", "aac", "-b:a", "192k", "-shortest"])
    
    args.append(output_path)
    
    try:
        print(f"Running FFmpeg command: {' '.join(args)}")
        process = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        stdout, stderr = process.communicate()
        
        if process.returncode != 0:
            cmds.warning(f"FFmpeg encoding failed: {stderr}")
            return False
            
        return True
        
    except Exception as e:
        cmds.warning(f"Error running FFmpeg: {str(e)}")
        return False

def get_frame_rate():
    """Get the current frame rate in Maya."""
    import maya.cmds as cmds
    import maya.mel as mel
    
    rate_str = cmds.currentUnit(q=True, time=True)
    
    if rate_str == "game":
        frame_rate = 15.0
    elif rate_str == "film":
        frame_rate = 24.0
    elif rate_str == "pal":
        frame_rate = 25.0
    elif rate_str == "ntsc":
        frame_rate = 30.0
    elif rate_str == "show":
        frame_rate = 48.0
    elif rate_str == "palf":
        frame_rate = 50.0
    elif rate_str == "ntscf":
        frame_rate = 60.0
    elif rate_str.endswith("fps"):
        frame_rate = float(rate_str[:-3])
    else:
        try:
            frame_rate = float(mel.eval("currentTimeUnitToFPS"))
        except:
            frame_rate = 24.0
            cmds.warning(f"Unsupported frame rate: {rate_str}, defaulting to 24 fps")
    
    return frame_rate
