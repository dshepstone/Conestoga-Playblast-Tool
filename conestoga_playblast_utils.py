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
import maya.mel as mel

# Add script directory to path if needed
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.append(script_dir)

import conestoga_playblast_presets as presets
import conestoga_playblast_utils as utils

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
    ffmpeg_path = utils.get_ffmpeg_path()
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
    ffmpeg_path = utils.get_ffmpeg_path()
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
    ffmpeg_path = utils.get_ffmpeg_path()
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
    if include_screenshot and utils.is_ffmpeg_available():
        ffmpeg_path = utils.get_ffmpeg_path()
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
    ffmpeg_path = utils.get_ffmpeg_path()
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
    ffmpeg_path = utils.get_ffmpeg_path()
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
        
        # Get aspect ratio values
        aspect_ratio = settings["aspect_ratio"]
        ar_parts = aspect_ratio.split(":")
        ar_width = int(ar_parts[0])
        ar_height = int(ar_parts[1])
        
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
                "-movflags", "+faststart",  # Optimized for streaming
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
    camera_shape = utils.get_camera_shape(camera)
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