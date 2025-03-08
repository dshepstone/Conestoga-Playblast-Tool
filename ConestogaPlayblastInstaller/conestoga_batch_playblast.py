"""
Conestoga Playblast Tool - Batch Playblast Utility
This module provides functions for batch playblasting from multiple cameras
or multiple scenes.
"""

import os
import sys
import time
import json
import sys
import glob
import traceback

import maya.cmds as cmds

# Add script directory to path if needed
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.append(script_dir)

import conestoga_playblast
import conestoga_playblast_utils as utils

def batch_playblast_cameras(cameras=None, settings=None):
    """
    Create playblasts for multiple cameras.
    
    Args:
        cameras (list): List of camera names (None = use all cameras)
        settings (dict): Playblast settings
        
    Returns:
        list: Paths to created playblasts
    """
    # Get all cameras if none specified
    if cameras is None:
        cameras = cmds.listCameras()
        # Filter out default cameras if needed
        default_cameras = ["persp", "top", "front", "side"]
        # Ask user if they want to include default cameras
        result = cmds.confirmDialog(
            title="Include Default Cameras",
            message="Do you want to include default cameras in the batch?",
            button=["Yes", "No"],
            defaultButton="No",
            cancelButton="No",
            dismissString="No"
        )
        
        if result == "No":
            cameras = [cam for cam in cameras if cam not in default_cameras]
    
    # Default settings
    if settings is None:
        settings = {}
    
    # Configure output filename to include camera
    filename = settings.get('filename', None)
    if filename and "{camera}" not in filename:
        settings['filename'] = f"{filename}_{{camera}}"
    
    # Batch process cameras
    return conestoga_playblast.batch_playblast(cameras, settings=settings)

def batch_playblast_scenes(scene_files, settings=None, camera=None):
    """
    Open and playblast multiple Maya scene files.
    
    Args:
        scene_files (list): List of Maya scene file paths
        settings (dict): Playblast settings
        camera (str): Camera to use (None = use active camera)
        
    Returns:
        list: Paths to created playblasts
    """
    if not scene_files:
        cmds.warning("No scene files specified for batch playblast")
        return []
    
    # Default settings
    if settings is None:
        settings = {}
    
    # Save current scene
    current_scene = cmds.file(query=True, sceneName=True)
    current_modified = cmds.file(query=True, modified=True)
    
    # Create progress window
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
            # Update progress
            if cmds.progressWindow(query=True, isCancelled=True):
                break
            
            progress = int((i / total_scenes) * 100)
            scene_name = os.path.basename(scene_file)
            cmds.progressWindow(
                edit=True,
                progress=progress,
                status=f"Processing scene: {scene_name}"
            )
            
            try:
                # Open scene
                cmds.file(scene_file, open=True, force=True)
                
                # Wait for scene to load
                cmds.refresh()
                
                # Get scene-based filename
                scene_base = os.path.splitext(os.path.basename(scene_file))[0]
                
                # Update settings for this scene
                scene_settings = settings.copy()
                scene_settings['filename'] = scene_settings.get('filename', scene_base)
                if camera:
                    scene_settings['camera'] = camera
                
                # Create playblast
                result = conestoga_playblast.create_playblast(**scene_settings)
                if result:
                    results.append(result)
                
            except Exception as e:
                cmds.warning(f"Failed to playblast scene {scene_file}: {str(e)}")
                traceback.print_exc()
    
    finally:
        # Close progress window
        cmds.progressWindow(endProgress=1)
        
        # Restore original scene
        if current_scene:
            cmds.file(current_scene, open=True, force=True)
            if not current_modified:
                cmds.file(save=True)
    
    return results

def batch_playblast_from_directory(directory, pattern="*.ma", recursive=False, settings=None, camera=None):
    """
    Batch playblast all Maya scenes in a directory.
    
    Args:
        directory (str): Directory containing Maya scene files
        pattern (str): File pattern to match (e.g., "*.ma", "*.mb")
        recursive (bool): Search subdirectories recursively
        settings (dict): Playblast settings
        camera (str): Camera to use for all scenes
        
    Returns:
        list: Paths to created playblasts
    """
    if not os.path.isdir(directory):
        cmds.warning(f"Directory does not exist: {directory}")
        return []
    
    # Find all matching scene files
    if recursive:
        search_pattern = os.path.join(directory, "**", pattern)
        scene_files = glob.glob(search_pattern, recursive=True)
    else:
        search_pattern = os.path.join(directory, pattern)
        scene_files = glob.glob(search_pattern)
    
    if not scene_files:
        cmds.warning(f"No {pattern} files found in {directory}")
        return []
    
    # Sort files by name
    scene_files.sort()
    
    # Ask for confirmation
    result = cmds.confirmDialog(
        title="Batch Playblast Scenes",
        message=f"Playblast {len(scene_files)} scenes from {directory}?",
        button=["Yes", "No"],
        defaultButton="Yes",
        cancelButton="No",
        dismissString="No"
    )
    
    if result != "Yes":
        return []
    
    # Process the scenes
    return batch_playblast_scenes(scene_files, settings, camera)