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
        shot_mask=True,
        show_in_viewer=True
    )
"""

################################################################################
# IMPORTS
################################################################################
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
import getpass

import maya.cmds as cmds
import maya.mel as mel

# Set up Qt imports with proper fallbacks
QtGui = None
QtCore = None
for module_name in ("PySide6", "PySide2"):
    try:
        module = __import__(module_name, fromlist=["QtGui", "QtCore"])
        QtGui = module.QtGui
        QtCore = module.QtCore
        break
    except ImportError:
        continue

################################################################################
# UTILITY FUNCTIONS (LEGACY & HELPER FUNCTIONS)
################################################################################

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

def parse_filename_tags(filename, camera):
    """
    Replace known tags in the filename with dynamic values.
    For example, {scene} is replaced with the current scene name and {camera}
    with the camera’s short name.
    """
    scene = os.path.splitext(os.path.basename(cmds.file(q=True, sceneName=True) or "untitled"))[0]
    camera_name = camera.split('|')[-1].split(':')[-1] if camera else "cam"
    filename = filename.replace("{scene}", scene).replace("{camera}", camera_name)
    return filename

def configure_output_path(output_dir, filename, format_type, encoder):
    """
    Construct the full output path using the output directory, filename,
    and file extension determined from format_type and encoder.
    """
    ext = format_type if format_type != "Image" else encoder
    return os.path.join(output_dir, f"{filename}.{ext}")

def create_temp_directory():
    """Create a temporary directory for intermediate files."""
    temp_dir = tempfile.mkdtemp(prefix="playblast_")
    return temp_dir

def clean_temp_directories():
    """Clean up all temporary directories created during playblast generation."""
    global _temp_dirs
    for d in _temp_dirs:
        if os.path.exists(d):
            shutil.rmtree(d)
    _temp_dirs = []

def get_active_sound_node():
    """
    Dummy implementation to get the active sound node.
    Replace this with your actual logic if sound is to be included.
    """
    return None

def show_ui():
    """Show the Playblast UI."""
    try:
        import conestoga_playblast_ui
        conestoga_playblast_ui.show_playblast_dialog()
    except Exception as e:
        cmds.warning(f"Failed to display UI: {str(e)}")

################################################################################
# IMPORT PRESETS & UTILS (from external modules)
################################################################################
try:
    import conestoga_playblast_presets as presets
    import conestoga_playblast_utils as utils
except ImportError:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if script_dir not in sys.path:
        sys.path.append(script_dir)
    try:
        import conestoga_playblast_presets as presets
        import conestoga_playblast_utils as utils
    except ImportError:
        raise ImportError("Could not import required modules. Ensure conestoga_playblast_presets.py and conestoga_playblast_utils.py are in the same directory.")

################################################################################
# GLOBAL VARIABLES
################################################################################
_playblast_in_progress = False
_temp_dirs = []

################################################################################
# MAIN PLAYBLAST FUNCTIONS
################################################################################

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
    show_in_viewer=True,  # Updated parameter from working_playblast_v01.py
    force_overwrite=False,
    custom_viewport_settings=None,
    shot_mask_settings=None
):
    """
    Create a playblast with the specified settings.
    
    Args:
        camera (str): Camera to use for the playblast (None = active viewport camera)
        output_dir (str): Output directory path.
        filename (str): Output filename (without extension).
        width (int): Width in pixels (None = use render settings).
        height (int): Height in pixels (None = use render settings).
        start_frame (int): Start frame (None = use playback range).
        end_frame (int): End frame (None = use playback range).
        format_type (str): Output format ("mp4", "mov", or "Image").
        encoder (str): Video encoder (e.g., "h264", "prores") or image format (e.g., "jpg", "png", "tif").
        quality (str): Quality preset ("Very High", "High", "Medium", "Low").
        viewport_preset (str): Viewport visibility preset.
        shot_mask (bool): Whether to include a shot mask overlay.
        overscan (bool): Enable camera overscan.
        ornaments (bool): Show UI ornaments.
        show_in_viewer (bool): Open the result in a viewer when done.
        force_overwrite (bool): Overwrite existing files if they exist.
        custom_viewport_settings (list): Custom viewport settings (if provided).
        shot_mask_settings (dict): Custom shot mask settings (if provided).
        
    Returns:
        str: Path to the created playblast file, or None if failed.
    """
    global _playblast_in_progress, _temp_dirs

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

    _playblast_in_progress = True
    temp_dir = None
    original_camera = None
    viewport_defaults = None
    image_plane_states = None
    shot_mask_created = False
    output_path = None

    try:
        # Determine camera selection.
        if camera is None:
            panel = utils.get_valid_model_panel()
            if panel:
                camera = cmds.modelPanel(panel, query=True, camera=True)
        if not camera or not cmds.objExists(camera):
            cmds.warning(f"Invalid camera: {camera}")
            return None

        # Setup output directory and filename.
        if not output_dir:
            output_dir = os.path.join(cmds.workspace(query=True, rootDirectory=True), "movies")
        if not filename:
            scene_name = cmds.file(query=True, sceneName=True, shortName=True).split('.')[0] or "untitled"
            camera_name = camera.split('|')[-1].split(':')[-1]
            filename = f"{scene_name}_{camera_name}"
        filename = parse_filename_tags(filename, camera)

        # Determine frame range.
        if start_frame is None:
            start_frame = int(cmds.playbackOptions(query=True, minTime=True))
        if end_frame is None:
            end_frame = int(cmds.playbackOptions(query=True, maxTime=True))

        # Determine resolution settings.
        if width is None or height is None:
            width = cmds.getAttr("defaultResolution.width")
            height = cmds.getAttr("defaultResolution.height")

        output_path = configure_output_path(output_dir, filename, format_type, encoder)
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

        temp_dir = create_temp_directory()
        _temp_dirs.append(temp_dir)

        # Determine playblast parameters based on FFmpeg encoding.
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

        # Get the active model panel and store viewport settings.
        model_panel = utils.get_valid_model_panel()
        if not model_panel:
            cmds.warning("No valid model panel found")
            return None

        original_camera = cmds.modelPanel(model_panel, query=True, camera=True)
        viewport_defaults = utils.get_viewport_defaults(model_panel, camera)
        image_plane_states = utils.disable_image_planes(camera)

        # Setup shot mask if enabled.
        if shot_mask:
            settings = presets.CUSTOM_MASK_TEMPLATES.get("Standard", {})
            if shot_mask_settings:
                settings.update(shot_mask_settings)
            user_name = settings.get("userName", os.getenv("USER") or getpass.getuser())
            mask_data = utils.create_shot_mask(camera, user_name)
            shot_mask_created = bool(mask_data)

        try:
            # Look through the target camera and configure the viewport.
            cmds.lookThru(camera)
            utils.set_final_viewport(model_panel, camera, viewport_preset)
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
            # If using FFmpeg, perform encoding.
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
            # Updated call: use show_in_viewer (from working_playblast_v01.py) to open the result.
            if show_in_viewer and os.path.exists(output_path):
                utils.show_in_viewer(output_path)
            print(f"Playblast completed: {output_path}")
            cmds.headsUpMessage(f"Playblast saved to: {output_path}", time=3.0)
            return output_path
        finally:
            # Restore original camera and viewport settings.
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
        cameras (list): List of camera names to playblast.
        output_dir (str): Output directory path.
        filename (str): Output filename template.
        settings (dict): Additional playblast settings.
        
    Returns:
        list: Paths to the created playblast files.
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
        for i, cam in enumerate(cameras):
            if cmds.progressWindow(query=True, isCancelled=True):
                break
            progress = int((i / total_cameras) * 100)
            cmds.progressWindow(edit=True, progress=progress, status=f"Processing camera: {cam}")
            try:
                cam_settings = settings.copy()
                cam_settings['camera'] = cam
                if filename and "{camera}" not in filename:
                    cam_settings['filename'] = f"{filename}_{cam}"
                else:
                    cam_settings['filename'] = filename
                result = create_playblast(output_dir=output_dir, **cam_settings)
                if result:
                    results.append(result)
            except Exception as e:
                cmds.warning(f"Failed to create playblast for camera {cam}: {str(e)}")
    finally:
        cmds.progressWindow(endProgress=1)
    return results

def show_ui():
    """
    Display the main user interface for the Conestoga Playblast Tool.
    """
    try:
        import conestoga_playblast_ui
        conestoga_playblast_ui.show_playblast_dialog()
    except Exception as e:
        cmds.warning(f"Failed to show UI: {str(e)}")

################################################################################
# ADDITIONAL LEGACY FUNCTIONS AND INTEGRATION STUBS
# (For example, functions to initialize the tool at startup, support for batch
# processing of scenes, plugin command definitions, etc.)
################################################################################

def batch_playblast_scenes(scene_files, settings=None, camera=None):
    """
    Open and playblast multiple Maya scene files.
    
    Args:
        scene_files (list): List of Maya scene file paths.
        settings (dict): Playblast settings.
        camera (str): Camera to use (None = use active camera).
        
    Returns:
        list: Paths to created playblast files.
    """
    if not scene_files:
        cmds.warning("No scene files specified for batch playblast")
        return []
    if settings is None:
        settings = {}
    current_scene = cmds.file(query=True, sceneName=True)
    current_modified = cmds.file(query=True, modified=True)
    progress_window = cmds.progressWindow(
        title="Batch Scene Playblast",
        progress=0,
        status="Starting batch scene playblast...",
        isInterruptable=True
    )
    results = []
    total_scenes = len(scene_files)
    try:
        for i, scene_file in enumerate(scene_files):
            if cmds.progressWindow(query=True, isCancelled=True):
                break
            progress = int((i / total_scenes) * 100)
            scene_name = os.path.basename(scene_file)
            cmds.progressWindow(edit=True, progress=progress, status=f"Processing scene: {scene_name}")
            try:
                cmds.file(scene_file, open=True, force=True)
                cmds.refresh()
                scene_settings = settings.copy()
                scene_settings['filename'] = os.path.splitext(os.path.basename(scene_file))[0]
                if camera:
                    scene_settings['camera'] = camera
                result = create_playblast(**scene_settings)
                if result:
                    results.append(result)
            except Exception as e:
                cmds.warning(f"Failed to playblast scene {scene_file}: {str(e)}")
    finally:
        cmds.progressWindow(endProgress=1)
        if current_scene:
            cmds.file(current_scene, open=True, force=True)
            if not current_modified:
                cmds.file(save=True)
    return results

# Legacy integration: Plugin command definition stubs.
def initializePlugin(plugin):
    """
    Initialize the Conestoga Playblast Tool plugin.
    This function registers the tool's plugin command with Maya.
    """
    from maya.api.OpenMaya import MFnPlugin
    vendor = "Conestoga College"
    try:
        plugin_fn = MFnPlugin(plugin, vendor, presets.VERSION, "Any")
        from conestoga_playblast_plugin import ConestogsPlayblastCommand
        plugin_fn.registerCommand(ConestogsPlayblastCommand.COMMAND_NAME,
                                    ConestogsPlayblastCommand.creator,
                                    ConestogsPlayblastCommand.createSyntax)
    except Exception as e:
        cmds.warning(f"Failed to register playblast command: {str(e)}")
        raise

def uninitializePlugin(plugin):
    """
    Uninitialize the Conestoga Playblast Tool plugin.
    This function deregisters the tool's plugin command from Maya.
    """
    from maya.api.OpenMaya import MFnPlugin
    try:
        plugin_fn = MFnPlugin(plugin)
        from conestoga_playblast_plugin import ConestogsPlayblastCommand
        plugin_fn.deregisterCommand(ConestogsPlayblastCommand.COMMAND_NAME)
    except Exception as e:
        cmds.warning(f"Failed to deregister playblast command: {str(e)}")
        raise

# Legacy integration: Startup initialization stub.
def initialize_playblast_tool_at_startup():
    """
    Legacy function to initialize the playblast tool when Maya starts up.
    This function could be called from a userSetup.py script.
    """
    try:
        add_to_maya_menu()
        show_ui()
        cmds.headsUpMessage("Conestoga Playblast Tool initialized at startup", time=3.0)
    except Exception as e:
        cmds.warning(f"Failed to initialize playblast tool at startup: {str(e)}")

################################################################################
# MAIN EXECUTION (if run as a standalone script)
################################################################################
if __name__ == "__main__":
    show_ui()

################################################################################
# END OF FILE: conestoga_playblast.py
################################################################################
