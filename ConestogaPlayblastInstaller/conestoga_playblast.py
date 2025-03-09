"""
Conestoga Playblast Tool - Main Module
This is the main entry point for the Conestoga Playblast Tool.

This module provides functions to create playblasts with customizable settings,
shot masks, and ffmpeg integration.

Usage:
    import conestoga_playblast
    conestoga_playblast.show_ui()  # Show the UI
    
    # Or create a playblast directly
    conestoga_playblast.create_playblast(
        camera="persp",
        output_dir="/path/to/output",
        filename="my_playblast",
        width=1920,
        height=1080,
        start_frame=1,
        end_frame=100,
        shot_mask=True
    )
"""

import os
import re
import sys
import json
import time
import glob
import shutil
import tempfile
import datetime
import subprocess
import traceback
from functools import partial

import maya.cmds as cmds
import maya.mel as mel
import getpass

# Set up Qt imports with proper fallbacks
QtGui = None
QtCore = None

# Attempt to import QtGui and QtCore from PySide6 or PySide2
QtGui, QtCore = None, None
for module_name in ("PySide6", "PySide2"):
    try:
        module = __import__(module_name, fromlist=["QtGui", "QtCore"])
        QtGui = module.QtGui
        QtCore = module.QtCore
        break
    except ImportError:
        continue

# Define utility functions used across the module before imports that might use them
def get_frame_rate():
    """Get the current frame rate in Maya."""
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
        raise RuntimeError(f"Unsupported frame rate: {rate_str}")

    return frame_rate


# Import the utilities and presets
try:
    import conestoga_playblast_presets as presets
    import conestoga_playblast_utils as utils
except ImportError:
    # Add the tool directory to the Python path
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if script_dir not in sys.path:
        sys.path.append(script_dir)
    try:
        import conestoga_playblast_presets as presets
        import conestoga_playblast_utils as utils
    except ImportError:
        raise ImportError("Could not import required modules. Make sure conestoga_playblast_presets.py and conestoga_playblast_utils.py are in the same directory.")

# Global variables
_playblast_in_progress = False
_temp_dirs = []


# ===========================================================================
# MAIN PLAYBLAST FUNCTIONS
# ===========================================================================

def create_playblast(
    camera=None,
    output_dir=None,
    filename=None,
    width=None,
    height=None,
    start_frame=None,
    end_frame=None,
    format_type="mp4",
    encoder="h264",
    quality="High",
    viewport_preset="Standard",
    shot_mask=True,
    overscan=False,
    ornaments=False,
    open_viewer=True,  # Renamed to avoid conflict with the helper function
    force_overwrite=False,
    custom_viewport_settings=None,
    shot_mask_settings=None
):
    """
    Create a playblast with the specified settings.
    
    Args:
        camera (str): Camera to use for the playblast (None = active viewport camera)
        output_dir (str): Output directory path
        filename (str): Output filename (without extension)
        width (int): Width in pixels (None = use render settings)
        height (int): Height in pixels (None = use render settings)
        start_frame (int): Start frame (None = use playback range)
        end_frame (int): End frame (None = use playback range)
        format_type (str): Output format (mp4, mov, or Image)
        encoder (str): Video encoder (h264, prores) or image format (jpg, png, tif)
        quality (str): Quality preset (Very High, High, Medium, Low)
        viewport_preset (str): Viewport visibility preset
        shot_mask (bool): Whether to include a shot mask
        overscan (bool): Enable camera overscan
        ornaments (bool): Show UI ornaments
        open_viewer (bool): Open the result in a viewer when done
        force_overwrite (bool): Overwrite existing files
        custom_viewport_settings (list): Custom viewport settings (None = use preset)
        shot_mask_settings (dict): Custom shot mask settings
        
    Returns:
        str: Path to the created playblast file or None if failed
    """
    global _playblast_in_progress, _temp_dirs
    
    # Initial checks
    if _playblast_in_progress:
        cmds.warning("A playblast is already in progress")
        return None
    
    if format_type in presets.MOVIE_FORMATS and not utils.is_ffmpeg_available():
        cmds.warning("FFmpeg is required but not available. Please install FFmpeg or choose Image format.")
        ffmpeg_path = utils.get_ffmpeg_path()
        if not ffmpeg_path:
            cmds.confirmDialog(
                title="FFmpeg Not Found",
                message="FFmpeg executable not found. Video encoding features will be limited.\n\nPlease configure FFmpeg in the Settings tab.",
                button=["OK"],
                defaultButton="OK"
            )
        else:
            cmds.confirmDialog(
                title="FFmpeg Test Failed",
                message=f"FFmpeg executable found at:\n{ffmpeg_path}\n\nBut it could not be executed successfully. Please check the path and permissions.",
                button=["OK"],
                defaultButton="OK"
            )
        return None
    
    # Marking that we're starting a playblast
    _playblast_in_progress = True
    
    # Variables that need to be tracked for cleanup
    temp_dir = None
    original_camera = None
    viewport_defaults = None
    image_plane_states = None
    shot_mask_created = False
    output_path = None
    
    try:
        # Validate camera
        if camera is None:
            panel = utils.get_valid_model_panel()
            if panel:
                camera = cmds.modelPanel(panel, query=True, camera=True)
        
        if not camera or not cmds.objExists(camera):
            cmds.warning(f"Invalid camera: {camera}")
            return None
        
        # Setup output paths
        if not output_dir:
            output_dir = os.path.join(cmds.workspace(query=True, rootDirectory=True), "movies")
        
        if not filename:
            scene_name = cmds.file(query=True, sceneName=True, shortName=True).split('.')[0] or "untitled"
            camera_name = camera.split('|')[-1].split(':')[-1]
            filename = f"{scene_name}_{camera_name}"
        
        filename = parse_filename_tags(filename, camera)
        
        # Setup frame range
        if start_frame is None:
            start_frame = int(cmds.playbackOptions(query=True, minTime=True))
        if end_frame is None:
            end_frame = int(cmds.playbackOptions(query=True, maxTime=True))
        
        # Setup resolution
        if width is None or height is None:
            width = cmds.getAttr("defaultResolution.width")
            height = cmds.getAttr("defaultResolution.height")
        
        output_path = configure_output_path(output_dir, filename, format_type, encoder)
        
        # Check for existing file
        if os.path.exists(output_path) and not force_overwrite:
            result = cmds.confirmDialog(
                title="File Exists",
                message=f"The file already exists:\n{output_path}\n\nDo you want to overwrite it?",
                button=["Yes", "No"],
                defaultButton="No",
                cancelButton="No",
                dismissString="No"
            )
            
            if result != "Yes":
                cmds.warning("Playblast cancelled - file exists")
                return None
        
        # Setup temp directory
        temp_dir = create_temp_directory()
        _temp_dirs.append(temp_dir)
        
        # Setup playblast parameters
        use_ffmpeg = format_type in presets.MOVIE_FORMATS and utils.is_ffmpeg_available()
        
        if use_ffmpeg:
            temp_format = "png"
            playblast_format = "image"
            compression = temp_format
            playblast_filename = os.path.join(temp_dir, filename)
        else:
            if format_type == "Image":
                playblast_format = "image"
                compression = encoder
            else:
                playblast_format = "movie"
                compression = None
            
            playblast_filename = os.path.normpath(output_path)
        
        # Setup viewport
        model_panel = utils.get_valid_model_panel()
        if not model_panel:
            cmds.warning("No valid model panel found")
            return None
        
        original_camera = cmds.modelPanel(model_panel, query=True, camera=True)
        viewport_defaults = utils.get_viewport_defaults(model_panel, camera)
        image_plane_states = utils.disable_image_planes(camera)
        
        # Setup shot mask
        if shot_mask:
            settings = presets.CUSTOM_MASK_TEMPLATES.get("Standard", {})
            if shot_mask_settings:
                settings.update(shot_mask_settings)
            
            user_name = settings.get("userName", os.getenv("USER") or getpass.getuser())
            mask_data = utils.create_shot_mask(camera, user_name)
            shot_mask_created = bool(mask_data)
        
        try:
            # Look through the camera
            cmds.lookThru(camera)
            
            # Configure viewport
            utils.set_final_viewport(model_panel, camera, viewport_preset)
            
            # Create the playblast
            print(f"Creating playblast: {playblast_filename}")
            cmds.playblast(
                filename=playblast_filename,
                forceOverwrite=True,
                format=playblast_format,
                compression=compression,
                quality=100,
                width=width,
                height=height,
                startTime=start_frame,
                endTime=end_frame,
                viewer=False,
                showOrnaments=ornaments,
                offScreen=not ornaments,
                percent=100,
                clearCache=True
            )
            
            # Encode with ffmpeg if needed
            if use_ffmpeg:
                input_pattern = os.path.join(temp_dir, f"{filename}.%04d.{temp_format}")
                print(f"Encoding with ffmpeg: {input_pattern} -> {output_path}")
                
                ffmpeg_settings = {
                    "encoder": encoder,
                    "quality": quality,
                    "preset": utils.load_option_var("h264Preset", presets.DEFAULT_H264_PRESET),
                    "framerate": get_frame_rate()
                }
                
                sound_node = get_active_sound_node()
                if sound_node:
                    audio_path = cmds.getAttr(f"{sound_node}.filename")
                    audio_offset = cmds.getAttr(f"{sound_node}.offset")
                    if os.path.exists(audio_path):
                        ffmpeg_settings["audio_path"] = audio_path
                        ffmpeg_settings["audio_offset"] = audio_offset / get_frame_rate()
                
                if not utils.encode_with_ffmpeg(input_pattern, output_path, ffmpeg_settings):
                    cmds.warning("ffmpeg encoding failed")
            
            # Show the result in the viewer using the helper function
            if open_viewer and os.path.exists(output_path):
                show_in_viewer(output_path)
            
            print(f"Playblast completed: {output_path}")
            cmds.headsUpMessage(f"Playblast saved to: {output_path}", time=3.0)
            
            return output_path
            
        finally:
            # Restore original viewport and camera settings
            if original_camera:
                try:
                    cmds.lookThru(original_camera)
                except Exception:
                    pass
                    
            if model_panel and viewport_defaults:
                try:
                    utils.restore_viewport(model_panel, camera, viewport_defaults)
                except Exception:
                    pass
                    
            if image_plane_states:
                try:
                    utils.restore_image_planes(image_plane_states)
                except Exception:
                    pass
                    
            if shot_mask_created:
                try:
                    utils.remove_shot_mask()
                except Exception:
                    pass
    
    except Exception as e:
        cmds.warning(f"Playblast failed: {str(e)}")
        traceback.print_exc()
        return None
        
    finally:
        # Always clean up temp directories and reset progress flag
        try:
            clean_temp_directories()
        except Exception:
            pass
            
        _playblast_in_progress = False


def batch_playblast(
    cameras,
    output_dir=None,
    filename=None,
    settings=None
):
    """
    Create playblasts for multiple cameras.
    
    Args:
        cameras (list): List of camera names to playblast
        output_dir (str): Output directory path
        filename (str): Output filename template
        settings (dict): Playblast settings
        
    Returns:
        list: Paths to created playblasts
    """
    if not cameras:
        cmds.warning("No cameras specified for batch playblast")
        return []
    
    if settings is None:
        settings = {}
    
    progress_window = cmds.progressWindow(
        title="Batch Playblast",
        progress=0,
        status="Starting batch playblast...",
        isInterruptable=True
    )
    
    results = []
    total_cameras = len(cameras)
    
    try:
        for i, camera in enumerate(cameras):
            if cmds.progressWindow(query=True, isCancelled=True):
                break
            
            progress = int((i / total_cameras) * 100)
            cmds.progressWindow(
                edit=True,
                progress=progress,
                status=f"Creating playblast for camera: {camera}"
            )
            
            camera_filename = filename
            if filename and "{camera}" not in filename:
                camera_name = camera.split('|')[-1].split(':')[-1]
                camera_filename = f"{filename}_{camera_name}"
            
            camera_settings = settings.copy()
            camera_settings["camera"] = camera
            camera_settings["output_dir"] = output_dir
            camera_settings["filename"] = camera_filename
            
            result = create_playblast(**camera_settings)
            if result:
                results.append(result)
    
    finally:
        cmds.progressWindow(endProgress=1)
    
    return results


# ===========================================================================
# HELPER FUNCTIONS
# ===========================================================================

def parse_filename_tags(filename, camera):
    """
    Replace tags in filename with actual values.
    
    Args:
        filename (str): Filename with {tags}
        camera (str): Camera name
        
    Returns:
        str: Parsed filename
    """
    if not filename:
        return filename
    
    if "{scene}" in filename:
        scene_path = cmds.file(query=True, sceneName=True, shortName=True)
        scene_name = os.path.splitext(scene_path)[0] if scene_path else "untitled"
        filename = filename.replace("{scene}", scene_name)
    
    if "{camera}" in filename:
        camera_name = camera.split('|')[-1].split(':')[-1]
        filename = filename.replace("{camera}", camera_name)
    
    if "{date}" in filename:
        date_str = datetime.datetime.now().strftime("%Y%m%d")
        filename = filename.replace("{date}", date_str)
    
    if "{time}" in filename:
        time_str = datetime.datetime.now().strftime("%H%M%S")
        filename = filename.replace("{time}", time_str)
    
    if "{timestamp}" in filename:
        timestamp = int(time.time())
        filename = filename.replace("{timestamp}", str(timestamp))
    
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    
    return filename


def configure_output_path(output_dir, filename, format_type, encoder):
    """
    Configure the output path based on format and encoder.
    
    Args:
        output_dir (str): Output directory
        filename (str): Base filename
        format_type (str): Output format type
        encoder (str): Encoder or image format
        
    Returns:
        str: Full output path
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    if format_type == "Image":
        extension = encoder.lower()
    else:
        extension = format_type.lower()
    
    output_path = os.path.normpath(os.path.join(output_dir, f"{filename}.{extension}"))
    
    return output_path


def create_temp_directory():
    """Create a temporary directory for playblast files."""
    temp_base = utils.load_option_var("tempDir", tempfile.gettempdir())
    timestamp = int(time.time())
    temp_dir = os.path.join(temp_base, f"conestoga_playblast_{timestamp}")
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)
    return temp_dir


def clean_temp_directories():
    """Clean up temporary directories after playblast."""
    global _temp_dirs
    for temp_dir in _temp_dirs:
        try:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
        except Exception as e:
            print(f"Warning: Failed to remove temp directory {temp_dir}: {e}")
    _temp_dirs = []


def get_active_sound_node():
    """Get the active sound node in the timeline."""
    timeline_sound = mel.eval("timeControl -q -sound $gPlayBackSlider;")
    if timeline_sound and cmds.objExists(timeline_sound):
        return timeline_sound
    audio_nodes = cmds.ls(type="audio")
    if audio_nodes:
        return audio_nodes[0]
    return None


def show_in_viewer(file_path):
    """
    Open the playblast in an external viewer.
    
    Args:
        file_path (str): Path to the file to open
    """
    if not os.path.exists(file_path):
        cmds.warning(f"File does not exist: {file_path}")
        return
    
    # First try using Qt if available
    if QtGui is not None and QtCore is not None:
        try:
            QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(file_path))
            return
        except Exception as e:
            cmds.warning(f"Qt viewer failed: {str(e)}")
    
    # Fallback method using OS commands
    try:
        if sys.platform == "win32":
            os.system(f'start "" "{file_path}"')
        elif sys.platform == "darwin":
            os.system(f'open "{file_path}"')
        else:  # Linux
            os.system(f'xdg-open "{file_path}"')
    except Exception as e:
        cmds.warning(f"Failed to open file: {str(e)}")


# ===========================================================================
# PLUGIN MANAGEMENT
# ===========================================================================

def load_plugin():
    """
    Load the Conestoga Playblast plugin if not already loaded.
    
    Returns:
        bool: True if plugin is loaded, False otherwise
    """
    plugin_name = "conestoga-playblast-plugin.py"
    if cmds.pluginInfo(plugin_name, query=True, loaded=True):
        return True
    try:
        cmds.loadPlugin(plugin_name)
        print(f"Loaded plugin: {plugin_name}")
        return True
    except Exception as e:
        cmds.warning(f"Failed to load plugin {plugin_name}: {str(e)}")
        return False


def show_ui():
    """
    Show the Conestoga Playblast UI.
    
    This function imports the GUI module (conestoga_playblast_ui.py) and calls its
    function to display the playblast dialog.
    """
    try:
        import conestoga_playblast_ui
        return conestoga_playblast_ui.show_playblast_dialog()
    except ImportError as e:
        cmds.warning(f"Failed to import UI module: {str(e)}")
        cmds.confirmDialog(
            title="UI Module Missing",
            message="Could not load the Conestoga Playblast UI module.\nMake sure conestoga_playblast_ui.py is installed correctly.",
            button=["OK"],
            defaultButton="OK"
        )
        return None


# For backwards compatibility, alias show_ui as show_playblast
show_playblast = show_ui


# ===========================================================================
# ENTRY POINT
# ===========================================================================

def main():
    """Main function when run as a script."""
    show_ui()


if __name__ == "__main__":
    main()