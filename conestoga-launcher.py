"""
Conestoga Playblast Tool - Quick Launch Script

This script provides simple functions to launch the playblast tool and create
playblasts with default settings.

Copy this script to your scripts directory and run it in Maya's script editor:
import playblast_launcher
playblast_launcher.launch_ui()

Or create a shelf button with this command:
import playblast_launcher; playblast_launcher.quick_playblast()
"""

import os
import sys
import maya.cmds as cmds

def setup_paths():
    """Set up Python paths to find the playblast modules."""
    # Try to find the conestoga_playblast directory
    maya_script_path = os.environ.get('MAYA_SCRIPT_PATH', '')
    paths = maya_script_path.split(os.pathsep)
    
    # Add current directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    paths.insert(0, script_dir)
    
    for path in paths:
        conestoga_dir = os.path.join(path, "conestoga_playblast")
        if os.path.exists(conestoga_dir) and conestoga_dir not in sys.path:
            sys.path.append(conestoga_dir)
            return True
    
    # If we couldn't find it in the standard locations, look in the parent directory
    parent_dir = os.path.dirname(script_dir)
    conestoga_dir = os.path.join(parent_dir, "conestoga_playblast")
    if os.path.exists(conestoga_dir) and conestoga_dir not in sys.path:
        sys.path.append(conestoga_dir)
        return True
    
    # If still not found, try common install locations
    common_locations = [
        os.path.join(os.path.expanduser("~"), "maya", "scripts", "conestoga_playblast"),
        "C:/Program Files/Autodesk/Maya2023/scripts/conestoga_playblast",
        "C:/Program Files/Autodesk/Maya2022/scripts/conestoga_playblast",
        "/Applications/Autodesk/maya2023/scripts/conestoga_playblast",
        "/usr/autodesk/maya2023/scripts/conestoga_playblast"
    ]
    
    for location in common_locations:
        if os.path.exists(location) and location not in sys.path:
            sys.path.append(location)
            return True
    
    return False

def launch_ui():
    """Launch the Conestoga Playblast UI."""
    if not setup_paths():
        cmds.error("Could not find the Conestoga Playblast Tool. Please make sure it is installed correctly.")
        return
    
    try:
        import conestoga_playblast
        ui = conestoga_playblast.show_ui()
        return ui
    except ImportError as e:
        cmds.error(f"Error importing Conestoga Playblast Tool: {e}")
        return None

def quick_playblast(camera=None, output_dir=None, filename=None):
    """Create a playblast with default settings."""
    if not setup_paths():
        cmds.error("Could not find the Conestoga Playblast Tool. Please make sure it is installed correctly.")
        return
    
    try:
        import conestoga_playblast
        
        # Set default values
        if not camera:
            panel = cmds.getPanel(withFocus=True)
            if cmds.getPanel(typeOf=panel) == "modelPanel":
                camera = cmds.modelPanel(panel, query=True, camera=True)
        
        if not output_dir:
            output_dir = os.path.join(cmds.workspace(query=True, rootDirectory=True), "movies")
        
        if not filename:
            scene_name = cmds.file(query=True, sceneName=True, shortName=True).split('.')[0] or "untitled"
            camera_name = camera.split('|')[-1].split(':')[-1] if camera else "cam"
            filename = f"{scene_name}_{camera_name}"
        
        # Create the playblast
        path = conestoga_playblast.create_playblast(
            camera=camera,
            output_dir=output_dir,
            filename=filename,
            format_type="mp4",
            encoder="h264",
            quality="High",
            viewport_preset="Standard",
            shot_mask=True,
            show_in_viewer=True
        )
        
        return path
    
    except ImportError as e:
        cmds.error(f"Error importing Conestoga Playblast Tool: {e}")
        return None

def batch_playblast_selected_cameras():
    """Create playblasts for all selected cameras."""
    if not setup_paths():
        cmds.error("Could not find the Conestoga Playblast Tool. Please make sure it is installed correctly.")
        return
    
    try:
        import conestoga_playblast
        import conestoga_batch_playblast
        
        # Get selected cameras
        selection = cmds.ls(selection=True)
        cameras = []
        
        for obj in selection:
            shapes = cmds.listRelatives(obj, shapes=True, type="camera")
            if shapes:
                cameras.append(obj)
        
        if not cameras:
            cmds.warning("No cameras selected. Please select one or more cameras.")
            return
        
        # Configure output
        output_dir = os.path.join(cmds.workspace(query=True, rootDirectory=True), "movies")
        scene_name = cmds.file(query=True, sceneName=True, shortName=True).split('.')[0] or "untitled"
        
        # Create the playblasts
        paths = conestoga_batch_playblast.batch_playblast_cameras(
            cameras=cameras,
            settings={
                "output_dir": output_dir,
                "filename": f"{scene_name}_{{camera}}",
                "format_type": "mp4",
                "encoder": "h264",
                "quality": "High",
                "viewport_preset": "Standard",
                "shot_mask": True,
                "show_in_viewer": False
            }
        )
        
        # Show results
        if paths:
            cmds.confirmDialog(
                title="Batch Playblast Complete",
                message=f"Created {len(paths)} playblasts in {output_dir}",
                button=["OK"]
            )
        
        return paths
    
    except ImportError as e:
        cmds.error(f"Error importing Conestoga Playblast Tool: {e}")
        return None

def show_menu():
    """Create a simple menu for the Conestoga Playblast Tool."""
    if not setup_paths():
        cmds.error("Could not find the Conestoga Playblast Tool. Please make sure it is installed correctly.")
        return
    
    try:
        import conestoga_playblast_menu
        menu = conestoga_playblast_menu.create_menus()
        return menu
    
    except ImportError as e:
        cmds.error(f"Error importing Conestoga Playblast Menu: {e}")
        return None

if __name__ == "__main__":
    # When run directly from script editor
    launch_ui()
