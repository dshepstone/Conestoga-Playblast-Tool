"""
Conestoga Playblast Tool - Menu Integration
This module handles the integration of the Conestoga Playblast Tool with Maya's UI.

It adds menu items to Maya's main menu and can be run automatically at Maya startup.
"""

import sys
import os

import maya.cmds as cmds
import maya.mel as mel
import maya.utils as utils

# Add script directory to path if needed
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.append(script_dir)

import conestoga_playblast_presets as presets

MENU_NAME = "ConestoGameDev"
MENU_LABEL = "Conestoga GameDev"
MENU_PARENT = "MayaWindow"

def find_icon(icon_name):
    """
    Dynamically locate an icon file in various possible locations.
    
    Args:
        icon_name (str): Base name of the icon (e.g., 'playblast.png')
        
    Returns:
        str: Full path to the icon if found, or the base name if not found
    """
    # Look in the tool's directory first
    tool_icon_path = os.path.join(script_dir, icon_name)
    if os.path.exists(tool_icon_path):
        return tool_icon_path
        
    # Look for icons with the tool name prefix
    tool_specific_icon = os.path.join(script_dir, f"conestoga_{icon_name}")
    if os.path.exists(tool_specific_icon):
        return tool_specific_icon
    
    # Try looking in standard Maya icon paths
    maya_icon_paths = []
    
    # Add MAYA_ICON_PATH if it exists
    if 'MAYA_ICON_PATH' in os.environ:
        maya_icon_paths.extend(os.environ['MAYA_ICON_PATH'].split(os.pathsep))
    
    # Add standard Maya icon locations
    maya_location = os.environ.get('MAYA_LOCATION', '')
    if maya_location:
        maya_icon_paths.append(os.path.join(maya_location, 'icons'))
    
    # Check each path for the icon
    for path in maya_icon_paths:
        full_path = os.path.join(path, icon_name)
        if os.path.exists(full_path):
            return full_path
    
    # If not found, just return the icon name for Maya to use its default search
    return icon_name

def create_menus():
    """Create the Conestoga GameDev menu in Maya."""
    # Remove existing menu if it exists
    if cmds.menu(MENU_NAME, exists=True):
        cmds.deleteUI(MENU_NAME)
    
    # Create main menu
    main_menu = cmds.menu(
        MENU_NAME,
        label=MENU_LABEL,
        parent=MENU_PARENT,
        tearOff=True
    )
    
    # Create playblast submenu
    playblast_submenu = cmds.menuItem(
        label="Playblast Tools",
        subMenu=True,
        parent=main_menu,
        tearOff=True
    )
    
    # Add playblast tool items
    cmds.menuItem(
        label=f"{presets.TOOL_NAME} v{presets.VERSION}",
        command="import conestoga_playblast; conestoga_playblast.show_ui()",
        parent=playblast_submenu
    )
    
    cmds.menuItem(
        divider=True,
        parent=playblast_submenu
    )
    
    cmds.menuItem(
        label="Quick Playblast (Default Settings)",
        command="import conestoga_playblast; conestoga_playblast.create_playblast()",
        parent=playblast_submenu
    )
    
    cmds.menuItem(
        label="Toggle Shot Mask",
        command="import conestoga_playblast_utils as utils; utils.toggle_shot_mask()",
        parent=playblast_submenu
    )
    
    # Add an About menuItem
    cmds.menuItem(
        divider=True,
        parent=playblast_submenu
    )
    
    cmds.menuItem(
        label="About Playblast Tool",
        command="import conestoga_playblast_utils as utils; utils.show_about_dialog()",
        parent=playblast_submenu
    )
    
    # Return the main menu
    return main_menu

def create_shelf_buttons():
    """Create shelf buttons for the playblast tool."""
    try:
        # Get the gShelfTopLevel global variable
        gShelfTopLevel = mel.eval('$temp=$gShelfTopLevel')
        
        # Check if GameDev shelf exists, create if needed
        shelf_exists = mel.eval('shelfLayout -exists "GameDev";')
        if not shelf_exists:
            mel.eval('addNewShelfTab "GameDev";')
        
        # Find icons - look for custom icons first, then fallback to standard ones
        # Main UI button icon
        main_icon = find_icon("conestoga_playblast_icon.png")
        if main_icon == "conestoga_playblast_icon.png" and not os.path.exists(main_icon):
            # Try alternative names
            for alt_name in ["conestoga_icon.png", "playblast_tool.png"]:
                alt_icon = find_icon(alt_name)
                if alt_icon != alt_name or os.path.exists(alt_icon):
                    main_icon = alt_icon
                    break
            # Final fallback to Maya's playblast icon
            if main_icon == "conestoga_playblast_icon.png" and not os.path.exists(main_icon):
                main_icon = "playblast.png"
        
        # Quick playblast button icon
        quick_icon = find_icon("conestoga_quick_playblast_icon.png")
        if quick_icon == "conestoga_quick_playblast_icon.png" and not os.path.exists(quick_icon):
            # Fallback to Maya's playblastOptions icon
            quick_icon = "playblastOptions.png"
        
        # Print icon paths for debugging
        print(f"Using main UI icon: {main_icon}")
        print(f"Using quick playblast icon: {quick_icon}")
        
        # Create shelf button for main UI
        button_name = "ConestoPlayblastButton"
        if cmds.shelfButton(button_name, exists=True):
            cmds.deleteUI(button_name)
        
        cmds.shelfButton(
            button_name,
            parent="GameDev",
            label="Playblast",
            image=main_icon,
            command="import conestoga_playblast; conestoga_playblast.show_ui()",
            annotation=f"{presets.TOOL_NAME} v{presets.VERSION}"
        )
        
        # Create quick playblast button
        quick_button_name = "ConestoQuickPlayblastButton"
        if cmds.shelfButton(quick_button_name, exists=True):
            cmds.deleteUI(quick_button_name)
        
        cmds.shelfButton(
            quick_button_name,
            parent="GameDev",
            label="Quick Playblast",
            image=quick_icon,
            command="import conestoga_playblast; conestoga_playblast.create_playblast()",
            annotation="Create a playblast with default settings"
        )
        
        return True
    
    except Exception as e:
        print(f"Error creating shelf buttons: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def initialize():
    """Initialize the menu integration."""
    # Create menus
    create_menus()
    
    # Create shelf buttons
    try:
        create_shelf_buttons()
    except Exception as e:
        print(f"Warning: Failed to create shelf buttons: {e}")
    
    print(f"Initialized {presets.TOOL_NAME} v{presets.VERSION}")

# Run this at Maya startup - add to userSetup.py:
# import conestoga_playblast_menu
# import maya.utils
# maya.utils.executeDeferred(conestoga_playblast_menu.initialize)

if __name__ == "__main__":
    # Run directly from script editor
    initialize()