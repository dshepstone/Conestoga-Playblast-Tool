"""
Conestoga Playblast Tool - Enhanced Drag & Drop Installer
Drag this file into Maya viewport to install the tool and automatically load it

Key Improvements:
- Allows reinstallation of the tool when already installed
- Respects user's shelf selection for button placement
- Fixes indentation issues in Python modules
- Improved error handling and user feedback
"""

def onMayaDroppedPythonFile(dropped_file):
    import maya.cmds as cmds
    import maya.mel as mel
    import os
    import sys
    import shutil
    import importlib
    import traceback
    import re

    # Get all available shelves for dropdown menu
    def get_available_shelves():
        shelves = []
        try:
            # Get the shelf layout from the global variable
            gShelfTopLevel = mel.eval('$temp=$gShelfTopLevel')
            # Get all child layouts (shelves)
            if gShelfTopLevel:
                shelf_layouts = cmds.shelfTabLayout(gShelfTopLevel, query=True, childArray=True)
                if shelf_layouts:
                    return list(shelf_layouts)
        except Exception as e:
            print(f"Error getting shelves: {str(e)}")
        # Return default list if we couldn't get actual shelves
        return ["Shelf1", "Custom", "Animation", "Polygons", "Surfaces", "Dynamics", "Rendering", "nDynamics"]

    # Check if tool is already installed
    def is_tool_installed():
        # Check for the main module directory
        maya_dir = os.path.normpath(os.path.expanduser(cmds.internalVar(userAppDir=True)))
        scripts_dir = os.path.join(maya_dir, "scripts")
        target_dir = os.path.join(scripts_dir, "conestoga_playblast")
        
        return os.path.exists(target_dir)

    # Function to fix Python indentation issues in a file
    def fix_indentation_issues(file_path):
        if not os.path.exists(file_path):
            return False

        try:
            # Read the file
            with open(file_path, 'r') as f:
                content = f.read()

            # Check for mixed tab and space indentation
            has_tabs = '\t' in content
            has_spaces = re.search(r'^\s+ ', content, re.MULTILINE) is not None

            if has_tabs and has_spaces:
                # Convert tabs to spaces throughout the file
                content = content.replace('\t', '    ')

            # Fix specific functions that have indentation issues
            key_functions = ['show_ui', 'create_playblast', 'reset_playblast_settings']
            
            for func_name in key_functions:
                # Try to find the function in the content
                func_pattern = r'(def\s+' + func_name + r'\s*\([^)]*\).*?)(?=\ndef|\Z)'
                func_match = re.search(func_pattern, content, re.DOTALL)
                
                if func_match:
                    func_text = func_match.group(1)
                    # Get the function definition line
                    lines = func_text.split('\n')
                    if len(lines) <= 1:
                        continue  # Skip if there's only one line or empty function
                    
                    # Get the expected indentation from the first non-empty line after def
                    base_indent = None
                    for i in range(1, len(lines)):
                        if lines[i].strip():
                            indent_match = re.match(r'^(\s+)', lines[i])
                            if indent_match:
                                base_indent = indent_match.group(1)
                                break
                    
                    if base_indent:
                        # Fix indentation for all lines in the function
                        fixed_lines = [lines[0]]  # Keep function definition
                        for i in range(1, len(lines)):
                            line = lines[i]
                            if not line.strip():
                                fixed_lines.append(line)  # Keep empty lines
                                continue
                            
                            # If line has indentation but it's not the base indentation,
                            # fix it to use base_indent + proper nested indentation
                            if line.strip() and not line.startswith(base_indent):
                                # Strip all leading whitespace
                                stripped = line.lstrip()
                                # Apply the base indentation
                                fixed_lines.append(base_indent + stripped)
                            else:
                                fixed_lines.append(line)
                        
                        # Replace the function in the content
                        fixed_func = '\n'.join(fixed_lines)
                        content = content.replace(func_match.group(1), fixed_func)

            # Fix any trailing whitespace and ensure consistent newlines
            content = '\n'.join(line.rstrip() for line in content.splitlines())
            content += '\n'  # Ensure the file ends with a newline

            # Write the fixed content back
            with open(file_path, 'w') as f:
                f.write(content)

            return True
        except Exception as e:
            print(f"Error fixing indentation in {file_path}: {str(e)}")
            traceback.print_exc()
            return False

    # Create installation dialog with shelf selection
    def show_installation_dialog():
        shelves = get_available_shelves()
        
        # Check if already installed
        already_installed = is_tool_installed()
        
        # Create dialog
        dialog_name = "conestoPlayblastInstaller"
        if cmds.window(dialog_name, exists=True):
            cmds.deleteUI(dialog_name)
            
        dialog = cmds.window(dialog_name, title="Conestoga Playblast Tool Installer", 
                             widthHeight=(400, 240), minimizeButton=False, maximizeButton=False)
        main_layout = cmds.columnLayout(adjustableColumn=True, columnAttach=('both', 10), 
                                        rowSpacing=10, columnWidth=380)
        # Logo/header
        cmds.text(label="<h1>Conestoga Playblast Tool</h1>", height=40)
        cmds.separator()
        
        # Installation status
        if already_installed:
            cmds.text(label="<b>Tool is already installed.</b> Would you like to reinstall it?", align="left")
        else:
            cmds.text(label="This will install the Conestoga Playblast Tool to your Maya scripts directory.", align="left")
            
        # Installation location info
        cmds.text(label="Select which shelf to add the tool buttons:", align="left")
        
        # Shelf selection dropdown
        shelf_optmenu = cmds.optionMenu(label="Target Shelf: ", width=200)
        for shelf in shelves:
            cmds.menuItem(label=shelf)
            
        # Set a default shelf if exists
        default_shelf = "Animation"
        if default_shelf in shelves:
            cmds.optionMenu(shelf_optmenu, edit=True, value=default_shelf)
            
        cmds.separator()
        
        # Buttons
        button_layout = cmds.rowLayout(numberOfColumns=2, columnWidth2=(190, 190), 
                                       columnAlign2=("center", "center"), columnAttach=[(1, "both", 0), (2, "both", 0)])
        
        button_label = "Reinstall" if already_installed else "Install"
        cmds.button(label=button_label, width=180, height=30, 
                    command=lambda x: install_tool(cmds.optionMenu(shelf_optmenu, query=True, value=True)))
        cmds.button(label="Cancel", width=180, height=30, 
                    command=lambda x: cmds.deleteUI(dialog_name))
                    
        cmds.setParent(main_layout)
        
        # Show dialog
        cmds.showWindow(dialog)
        return dialog

    # Main installation function
    def install_tool(target_shelf):
        # Close the dialog
        if cmds.window("conestoPlayblastInstaller", exists=True):
            cmds.deleteUI("conestoPlayblastInstaller")
            
        # Simple progress window
        cmds.progressWindow(
            title="Installing Conestoga Playblast Tool",
            progress=0,
            status="Starting installation...",
            isInterruptable=False
        )
        
        try:
            # Get Maya directories
            cmds.progressWindow(edit=True, progress=10, status="Finding Maya directories...")
            maya_dir = os.path.normpath(os.path.expanduser(cmds.internalVar(userAppDir=True)))
            scripts_dir = os.path.join(maya_dir, "scripts")
            plugins_dir = os.path.join(maya_dir, "plug-ins")
            icons_dir = os.path.join(maya_dir, "prefs/icons")
            
            print(f"Maya scripts directory: {scripts_dir}")
            print(f"Maya plugins directory: {plugins_dir}")
            
            # Create directories if needed
            for directory in [scripts_dir, plugins_dir, icons_dir]:
                if not os.path.exists(directory):
                    os.makedirs(directory)
                    
            # Create target directory (or clean it if reinstalling)
            target_dir = os.path.join(scripts_dir, "conestoga_playblast")
            if os.path.exists(target_dir):
                # Reinstallation - remove existing files
                cmds.progressWindow(edit=True, progress=15, status="Cleaning existing installation...")
                try:
                    # Don't delete the directory itself as user might have custom files
                    for item in os.listdir(target_dir):
                        item_path = os.path.join(target_dir, item)
                        if os.path.isfile(item_path):
                            os.remove(item_path)
                        elif os.path.isdir(item_path):
                            shutil.rmtree(item_path)
                except Exception as e:
                    print(f"Warning: Could not clean all existing files: {str(e)}")
            else:
                os.makedirs(target_dir)
                
            # Source directory (where this script is)
            source_dir = os.path.dirname(os.path.abspath(dropped_file))
            print(f"Source directory: {source_dir}")
            
            # Find icon files in the source directory
            icons_found = False
            icon_files = {}
            
            # Look for icon files in source directory and its subdirectories
            for root, dirs, files in os.walk(source_dir):
                for file in files:
                    if file.endswith(('.png', '.xpm', '.svg')):
                        file_path = os.path.join(root, file)
                        # Save the path with a simple name as key
                        if "playblast" in file.lower():
                            icon_files["playblast_icon"] = file_path
                            icons_found = True
                        elif "mask" in file.lower():
                            icon_files["mask_icon"] = file_path
                            icons_found = True
                        elif "icon" in file.lower():
                            if "main" in file.lower():
                                icon_files["main_icon"] = file_path
                            else:
                                icon_files["alt_icon"] = file_path
                            icons_found = True
                                
            # If we found any icons, copy them to the icons directory
            if icons_found:
                cmds.progressWindow(edit=True, progress=15, status="Copying icons...")
                for icon_name, icon_path in icon_files.items():
                    if os.path.exists(icon_path):
                        target_icon_path = os.path.join(icons_dir, os.path.basename(icon_path))
                        shutil.copy2(icon_path, target_icon_path)
                        # Update path to use the copied version
                        icon_files[icon_name] = target_icon_path
                        print(f"Copied icon: {icon_path} to {target_icon_path}")
                        
            # Set default icons if none found
            if "playblast_icon" not in icon_files:
                icon_files["playblast_icon"] = "playblast.png"
            if "mask_icon" not in icon_files:
                icon_files["mask_icon"] = "playblastOptions.png"
                
            # Files to copy with name corrections (source_name -> destination_name)
            files_map = {
                # Module files -> scripts/conestoga_playblast
                "conestoga_batch_playblast.py": "conestoga_batch_playblast.py",
                "conestoga-batch-playblast.py": "conestoga_batch_playblast.py",
                "conestoga_playblast_menu.py": "conestoga_playblast_menu.py",
                "conestoga-playblast-menu.py": "conestoga_playblast_menu.py",
                "conestoga_playblast_ui.py": "conestoga_playblast_ui.py",
                "conestoga-playblast-ui.py": "conestoga_playblast_ui.py",
                "conestoga_playblast_utils.py": "conestoga_playblast_utils.py",
                "conestoga-playblast-utils.py": "conestoga_playblast_utils.py",
                "conestoga-playblast.py": "conestoga_playblast.py",
                "conestoga_playblast.py": "conestoga_playblast.py",
                "conestoga_playblast_presets.py": "conestoga_playblast_presets.py",
                "conestoga-playblast-presets.py": "conestoga_playblast_presets.py",
                # Plugin file -> plug-ins directory
                "conestoga-playblast-plugin.py": "conestoga_playblast_plugin.py",
                "conestoga_playblast_plugin.py": "conestoga_playblast_plugin.py"
            }
            
            # Copy files
            cmds.progressWindow(edit=True, progress=20, status="Copying files...")
            copied_files = []
            
            for source_name, dest_name in files_map.items():
                source_file = os.path.join(source_dir, source_name)
                if os.path.exists(source_file) and os.path.isfile(source_file):
                    print(f"Found file: {source_name}")
                    # Determine destination
                    if dest_name.endswith("plugin.py"):
                        dest_path = plugins_dir
                    else:
                        dest_path = target_dir
                        
                    dest_file = os.path.join(dest_path, dest_name)
                    print(f"Copying {source_file} to {dest_file}")
                    
                    try:
                        shutil.copy2(source_file, dest_file)
                        copied_files.append(dest_name)
                        print(f"Successfully copied {source_name} to {dest_name}")
                        
                        # Fix indentation issues in the copied file
                        if dest_name in ["conestoga_playblast_ui.py", "conestoga_playblast.py"]:
                            cmds.progressWindow(edit=True, progress=30, status=f"Fixing indentation in {dest_name}...")
                            if fix_indentation_issues(dest_file):
                                print(f"Fixed indentation issues in {dest_name}")
                            else:
                                print(f"No indentation issues to fix in {dest_name}")
                                
                        cmds.progressWindow(edit=True, progress=30 + len(copied_files)*2, status=f"Copied: {dest_name}")
                    except Exception as e:
                        print(f"Error copying {source_name}: {str(e)}")
                        traceback.print_exc()
                        
            # Fix the conestoga_playblast.py file specifically to ensure it has the required functions
            conestoga_playblast_py = os.path.join(target_dir, "conestoga_playblast.py")
            
            if not os.path.exists(conestoga_playblast_py) or "conestoga_playblast.py" not in copied_files:
                # Create minimal file if it doesn't exist
                cmds.progressWindow(edit=True, progress=50, status="Creating main module...")
                minimal_content = '''"""
Conestoga Playblast Tool - Main Module
This is the main entry point for the Conestoga Playblast Tool.
"""

import os
import sys
import maya.cmds as cmds

def show_ui():
    """Show the main playblast UI."""
    try:
        import conestoga_playblast_ui
        return conestoga_playblast_ui.show_playblast_dialog()
    except ImportError as e:
        cmds.warning(f"Error loading UI: {str(e)}")
        return None

def create_playblast(camera=None, output_dir=None, filename=None, **kwargs):
    """Create a playblast with the specified settings."""
    try:
        # Call UI module's playblast method
        import conestoga_playblast_ui
        
        # Get active camera if none specified
        if not camera:
            panel = cmds.getPanel(withFocus=True)
            if cmds.getPanel(typeOf=panel) == "modelPanel":
                camera = cmds.modelPanel(panel, query=True, camera=True)
        
        # Call the actual implementation
        from conestoga_playblast_ui import PlayblastDialog
        dialog = PlayblastDialog()
        
        # Set values from arguments
        if camera:
            dialog.cameraComboBox.setCurrentText(camera)
        if output_dir:
            dialog.outputDirLineEdit.setText(output_dir)
        if filename:
            dialog.filenameLineEdit.setText(filename)
            
        # Do the playblast
        dialog.do_playblast()
        
        return "Playblast complete"
    except Exception as e:
        cmds.warning(f"Error creating playblast: {str(e)}")
        return None

def main():
    """Main function when run as a script."""
    return show_ui()

if __name__ == "__main__":
    main()
'''
                with open(conestoga_playblast_py, 'w') as f:
                    f.write(minimal_content)
                print(f"Created main module at {conestoga_playblast_py}")
                copied_files.append("conestoga_playblast.py")
            else:
                # Fix the existing file
                print("Fixing conestoga_playblast.py file")
                fix_indentation_issues(conestoga_playblast_py)
                
                # Verify the file has necessary functions
                with open(conestoga_playblast_py, 'r') as f:
                    content = f.read()
                    
                has_show_ui = 'def show_ui(' in content
                has_create_playblast = 'def create_playblast(' in content
                
                if not has_show_ui or not has_create_playblast:
                    # Functions are missing, add them
                    with open(conestoga_playblast_py, 'a') as f:
                        if not has_show_ui:
                            f.write('''
def show_ui():
    """Show the main playblast UI."""
    try:
        import conestoga_playblast_ui
        return conestoga_playblast_ui.show_playblast_dialog()
    except ImportError as e:
        cmds.warning(f"Error loading UI: {str(e)}")
        return None
''')
                        if not has_create_playblast:
                            f.write('''
def create_playblast(camera=None, output_dir=None, filename=None, **kwargs):
    """Create a playblast with the specified settings."""
    try:
        # Call UI module's playblast method
        import conestoga_playblast_ui
        
        # Get active camera if none specified
        if not camera:
            panel = cmds.getPanel(withFocus=True)
            if cmds.getPanel(typeOf=panel) == "modelPanel":
                camera = cmds.modelPanel(panel, query=True, camera=True)
        
        # Call the actual implementation
        from conestoga_playblast_ui import PlayblastDialog
        dialog = PlayblastDialog()
        
        # Set values from arguments
        if camera:
            dialog.cameraComboBox.setCurrentText(camera)
        if output_dir:
            dialog.outputDirLineEdit.setText(output_dir)
        if filename:
            dialog.filenameLineEdit.setText(filename)
            
        # Do the playblast
        dialog.do_playblast()
        
        return "Playblast complete"
    except Exception as e:
        cmds.warning(f"Error creating playblast: {str(e)}")
        return None
''')
            
            # Create the presets file if it doesn't exist
            presets_file = os.path.join(target_dir, "conestoga_playblast_presets.py")
            if not os.path.exists(presets_file) or "conestoga_playblast_presets.py" not in copied_files:
                cmds.progressWindow(edit=True, progress=50, status="Creating presets module...")
                # Content for the presets file with the target shelf
                presets_content = '''"""
Conestoga Playblast Tool - Presets Module
This module contains constants, default settings, and presets for the playblast tool.
"""

import os
import maya.cmds as cmds

# Tool Information
TOOL_NAME = "Conestoga Playblast Tool"
VERSION = "2.0.0"

# Shot Mask Constants
MASK_PREFIX = "cone_shotmask_"

# Target shelf for the tools (populated by installer)
TARGET_SHELF = "{0}"

# Default Settings
DEFAULT_CAMERA = "<Active>"
DEFAULT_RESOLUTION = "HD 1080"
DEFAULT_FRAME_RANGE = "Playback"
DEFAULT_OUTPUT_FORMAT = "mp4"
DEFAULT_ENCODER = "h264"
DEFAULT_H264_QUALITY = "High"
DEFAULT_H264_PRESET = "fast"
DEFAULT_VIEW_PRESET = "Standard"
DEFAULT_MASK_SCALE = 0.25
DEFAULT_COUNTER_PADDING = 4

# Format and Encoder Settings
FRAME_FORMATS = ["jpg", "png", "tif"]
MOVIE_FORMATS = ["mp4", "mov"]
OUTPUT_FORMATS = ["mp4", "mov", "Image"]

VIDEO_ENCODERS = {{
    "mp4": ["h264"],
    "mov": ["h264", "prores"],
    "Image": FRAME_FORMATS
}}

H264_QUALITIES = {{
    "Very High": 18,
    "High": 20,
    "Medium": 23,
    "Low": 26
}}

H264_PRESETS = [
    "veryslow",
    "slow",
    "medium",
    "fast",
    "faster",
    "ultrafast"
]

PRORES_PROFILES = {{
    "ProRes 422 Proxy": 0,
    "ProRes 422 LT": 1,
    "ProRes 422": 2,
    "ProRes 422 HQ": 3,
    "ProRes 4444": 4,
    "ProRes 4444 XQ": 5
}}

# Resolution Presets
RESOLUTION_PRESETS = {{
    "HD 720": (1280, 720),
    "HD 1080": (1920, 1080),
    "UHD 4K": (3840, 2160),
    "Cinematic 2K": (2048, 1080),
    "Cinematic 4K": (4096, 2160),
    "Square 1080": (1080, 1080),
    "Vertical HD": (720, 1280),
    "Render": None  # This will use Maya's render settings
}}

# Viewport Visibility Settings
VIEWPORT_VISIBILITY_LOOKUP = [
    ["NURBS Curves", "nurbsCurves"],
    ["NURBS Surfaces", "nurbsSurfaces"],
    ["Polygons", "polymeshes"],
    ["Subdivs", "subdivSurfaces"],
    ["Planes", "planes"],
    ["Lights", "lights"],
    ["Cameras", "cameras"],
    ["Image Planes", "imagePlane"],
    ["Joints", "joints"],
    ["IK Handles", "ikHandles"],
    ["Deformers", "deformers"],
    ["Dynamics", "dynamics"],
    ["Particle Instances", "particleInstancers"],
    ["Fluids", "fluids"],
    ["Hair Systems", "hairSystems"],
    ["Follicles", "follicles"],
    ["nCloths", "nCloths"]
]

# Viewport Visibility Presets
VIEWPORT_VISIBILITY_PRESETS = {{
    "Viewport": [],
    "Geo": ["NURBS Surfaces", "Polygons", "Subdivs"],
    "Standard": ["NURBS Curves", "NURBS Surfaces", "Polygons", "Subdivs", "Planes", 
                "Lights", "Cameras", "Joints", "IK Handles", "Locators"],
    "Full": ["NURBS Curves", "NURBS Surfaces", "Polygons", "Subdivs", "Planes", 
            "Lights", "Cameras", "Image Planes", "Joints", "IK Handles", 
            "Deformers", "Dynamics", "Locators", "Dimensions", "Pivots", 
            "Handles", "Textures", "Controllers", "Grid"]
}}

# Shot Mask Templates
CUSTOM_MASK_TEMPLATES = {{
    "Standard": {{
        "topLeftText": "Scene: {{scene}}",
        "topCenterText": "",
        "topRightText": "FPS: {{fps}}",
        "bottomLeftText": "Artist: {{username}}",
        "bottomCenterText": "Date: {{date}}",
        "bottomRightText": "Frame: {{counter}}",
        "textColor": (1.0, 1.0, 1.0),
        "scale": 0.25,
        "opacity": 1.0
    }},
    "Minimal": {{
        "topLeftText": "{{scene}}",
        "topCenterText": "",
        "topRightText": "",
        "bottomLeftText": "",
        "bottomCenterText": "",
        "bottomRightText": "{{counter}}",
        "textColor": (1.0, 1.0, 1.0),
        "scale": 0.2,
        "opacity": 0.8
    }},
    "Detailed": {{
        "topLeftText": "Scene: {{scene}}",
        "topCenterText": "Camera: {{camera}}",
        "topRightText": "Focal: {{focal_length}}mm",
        "bottomLeftText": "Artist: {{username}}",
        "bottomCenterText": "Date: {{date}} {{time}}",
        "bottomRightText": "Frame: {{counter}}",
        "textColor": (0.4, 0.8, 1.0),
        "scale": 0.3,
        "opacity": 0.9
    }}
}}

# Filename Tag Patterns
TAG_PATTERNS = {{
    "scene": lambda: os.path.splitext(os.path.basename(cmds.file(q=True, sn=True) or "untitled"))[0],
    "camera": lambda cam: cam.split("|")[-1].split(":")[-1] if cam else "cam",
    "date": lambda: cmds.about(cd=True).split()[0],
    "time": lambda: cmds.about(ct=True)
}}

# Allow for custom presets via import
try:
    from conestoga_custom_presets import *
except ImportError:
    pass
'''.format(target_shelf)
                with open(presets_file, 'w') as f:
                    f.write(presets_content)
                print(f"Created presets module at {presets_file}")
                copied_files.append("conestoga_playblast_presets.py")
            else:
                # Update the target shelf in the existing presets file
                with open(presets_file, 'r') as f:
                    content = f.read()
                
                # Update or add the TARGET_SHELF variable
                if 'TARGET_SHELF' in content:
                    content = re.sub(r'TARGET_SHELF\s*=\s*"[^"]*"', f'TARGET_SHELF = "{target_shelf}"', content)
                else:
                    # Add after VERSION if it exists
                    if 'VERSION' in content:
                        content = content.replace('VERSION = ', f'VERSION = \n\n# Target shelf for the tools (populated by installer)\nTARGET_SHELF = "{target_shelf}"\n\n')
                    else:
                        # Add at the top of the file after the docstring
                        docstring_end = content.find('"""', content.find('"""') + 3) + 3
                        content = content[:docstring_end] + f'\n\n# Target shelf for the tools (populated by installer)\nTARGET_SHELF = "{target_shelf}"\n\n' + content[docstring_end:]
                
                with open(presets_file, 'w') as f:
                    f.write(content)
            
            # Create or update the menu module
            menu_file = os.path.join(target_dir, "conestoga_playblast_menu.py")
            cmds.progressWindow(edit=True, progress=70, status="Creating menu module...")
            
            menu_content = '''"""
Conestoga Playblast Tool - Menu Integration
This module handles the integration of the Conestoga Playblast Tool with Maya's UI.
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

try:
    import conestoga_playblast_presets as presets
except ImportError:
    # Default values if presets module not found
    class presets:
        TOOL_NAME = "Conestoga Playblast Tool"
        VERSION = "2.0.0"
        TARGET_SHELF = "{0}"  # This will be replaced with the user-selected shelf

MENU_NAME = "ConestoPlayblast"
MENU_LABEL = "Conestoga Playblast"
MENU_PARENT = "MayaWindow"

def find_icon(icon_name):
    """
    Dynamically locate an icon file in various possible locations.
    """
    # Look in the tool's directory first
    tool_icon_path = os.path.join(script_dir, icon_name)
    if os.path.exists(tool_icon_path):
        return tool_icon_path
        
    # Look for icons with the tool name prefix
    tool_specific_icon = os.path.join(script_dir, f"conestoga_{{icon_name}}")
    if os.path.exists(tool_specific_icon):
        return tool_specific_icon
    
    # Try looking in Maya's prefs/icons directory
    maya_app_dir = cmds.internalVar(userAppDir=True)
    icons_dir = os.path.join(maya_app_dir, "prefs/icons")
    
    # Check for icon in icons directory
    icon_path = os.path.join(icons_dir, icon_name)
    if os.path.exists(icon_path):
        return icon_path
        
    # Check for any icon matching pattern
    if os.path.exists(icons_dir):
        for file in os.listdir(icons_dir):
            if icon_name.split('.')[0].lower() in file.lower():
                return os.path.join(icons_dir, file)
    
    # If not found, just return the icon name for Maya to use its default search
    return icon_name

def create_menus():
    """Create the Conestoga Playblast menu in Maya."""
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
    
    # Add playblast tool items
    cmds.menuItem(
        label=f"{{presets.TOOL_NAME}} v{{presets.VERSION}}",
        command="import conestoga_playblast; conestoga_playblast.show_ui()",
        parent=main_menu
    )
    
    cmds.menuItem(
        divider=True,
        parent=main_menu
    )
    
    cmds.menuItem(
        label="Quick Playblast (Default Settings)",
        command="import conestoga_playblast; conestoga_playblast.create_playblast()",
        parent=main_menu
    )
    
    cmds.menuItem(
        label="Toggle Shot Mask",
        command="import conestoga_playblast_utils as utils; utils.toggle_shot_mask()",
        parent=main_menu
    )
    
    # Add an About menuItem
    cmds.menuItem(
        divider=True,
        parent=main_menu
    )
    
    cmds.menuItem(
        label="About Playblast Tool",
        command="import conestoga_playblast_ui; conestoga_playblast_ui.show_about_dialog()",
        parent=main_menu
    )
    
    # Return the main menu
    return main_menu

def create_shelf_buttons():
    """Create shelf buttons for the playblast tool."""
    try:
        # Get the gShelfTopLevel global variable
        gShelfTopLevel = mel.eval('$temp=$gShelfTopLevel')
        
        # Get target shelf - This is the key fix!
        # Use the TARGET_SHELF from presets module
        target_shelf = getattr(presets, 'TARGET_SHELF', "{0}")
        
        # Check if the target shelf exists
        if not target_shelf or not cmds.shelfLayout(target_shelf, exists=True):
            # Find an available shelf if the target doesn't exist
            shelves = cmds.shelfTabLayout(gShelfTopLevel, query=True, childArray=True) or []
            if shelves:
                target_shelf = shelves[0]  # Use the first available shelf
                print(f"Target shelf '{target_shelf}' not found. Using '{shelves[0]}' instead.")
            else:
                # Create a new shelf if none exist
                target_shelf = "Custom"
                print(f"No shelves found. Creating a new '{target_shelf}' shelf.")
                mel.eval('addNewShelfTab "{{}}";'.format(target_shelf))
        
        # Find icons - look for custom icons first, then fallback to standard ones
        # Main UI button icon
        main_icon = find_icon("conestoga_playblast_icon.png")
        if main_icon == "conestoga_playblast_icon.png" and not os.path.exists(main_icon):
            # Try alternative names
            for alt_name in ["conestoga_icon.png", "playblast_tool.png", "playblast.png"]:
                alt_icon = find_icon(alt_name)
                if alt_icon != alt_name or os.path.exists(alt_icon):
                    main_icon = alt_icon
                    break
                    
        # Quick playblast button icon
        quick_icon = find_icon("conestoga_quick_playblast_icon.png")
        if quick_icon == "conestoga_quick_playblast_icon.png" and not os.path.exists(quick_icon):
            # Fallback to Maya's playblastOptions icon
            quick_icon = "playblastOptions.png"
        
        # Print icon paths for debugging
        print(f"Using main UI icon: {{main_icon}}")
        print(f"Using quick playblast icon: {{quick_icon}}")
        print(f"Using target shelf: {{target_shelf}}")
        
        # Create shelf button for main UI
        button_name = "ConestoPlayblastButton"
        if cmds.shelfButton(button_name, exists=True):
            cmds.deleteUI(button_name)
        
        cmds.shelfButton(
            button_name,
            parent=target_shelf,
            label="Playblast",
            image=main_icon,
            command="import conestoga_playblast; conestoga_playblast.show_ui()",
            annotation=f"{{presets.TOOL_NAME}} v{{presets.VERSION}}"
        )
        
        # Create quick playblast button
        quick_button_name = "ConestoQuickPlayblastButton"
        if cmds.shelfButton(quick_button_name, exists=True):
            cmds.deleteUI(quick_button_name)
        
        cmds.shelfButton(
            quick_button_name,
            parent=target_shelf,
            label="Quick Playblast",
            image=quick_icon,
            command="import conestoga_playblast; conestoga_playblast.create_playblast()",
            annotation="Create a playblast with default settings"
        )
        
        print(f"Successfully added buttons to shelf: {{target_shelf}}")
        return True
    
    except Exception as e:
        print(f"Error creating shelf buttons: {{str(e)}}")
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
        print(f"Warning: Failed to create shelf buttons: {{e}}")
    
    print(f"Initialized {{presets.TOOL_NAME}} v{{presets.VERSION}}")

# Run this at Maya startup - add to userSetup.py:
# import conestoga_playblast_menu
# import maya.utils
# maya.utils.executeDeferred(conestoga_playblast_menu.initialize)

if __name__ == "__main__":
    # Run directly from script editor
    initialize()
'''.format(target_shelf)
            with open(menu_file, 'w') as f:
                f.write(menu_content)
                
            # Setup userSetup.py to auto-load the tool
            usersetup_file = os.path.join(scripts_dir, "userSetup.py")
            setup_code = '''
# Conestoga Playblast Tool - Auto-load
import sys
import os
import maya.utils

# Add conestoga_playblast to Python path
script_dir = os.path.dirname(os.path.abspath(__file__))
conestoga_dir = os.path.join(script_dir, "conestoga_playblast")
if conestoga_dir not in sys.path:
    sys.path.append(conestoga_dir)

# Load plugin and initialize menu
def initialize_conestoga_playblast():
    try:
        import conestoga_playblast_menu
        conestoga_playblast_menu.initialize()
        print("Conestoga Playblast Tool initialized")
    except Exception as e:
        print(f"Error initializing Conestoga Playblast Tool: {e}")

maya.utils.executeDeferred(initialize_conestoga_playblast)
'''
            cmds.progressWindow(edit=True, progress=80, status="Setting up auto-loading...")
            
            if os.path.exists(usersetup_file):
                # Check if our code is already in userSetup.py
                with open(usersetup_file, 'r') as f:
                    content = f.read()
                    
                if "conestoga_playblast" in content:
                    print("userSetup.py already has Conestoga Playblast setup")
                else:
                    # Append our code
                    with open(usersetup_file, 'a') as f:
                        f.write(setup_code)
                    print("Updated userSetup.py to auto-load the tool")
            else:
                # Create new userSetup.py
                with open(usersetup_file, 'w') as f:
                    f.write(setup_code)
                print("Created userSetup.py to auto-load the tool")
                
            # Final steps - initialize the tool and add to Python path
            cmds.progressWindow(edit=True, progress=90, status="Initializing tool...")
            
            # Add to Python path for immediate use
            if target_dir not in sys.path:
                sys.path.append(target_dir)
                print(f"Added {target_dir} to sys.path")
                
            # Try to load modules
            try:
                # Force reload any existing modules
                if 'conestoga_playblast_presets' in sys.modules:
                    del sys.modules['conestoga_playblast_presets']
                if 'conestoga_playblast_utils' in sys.modules:
                    del sys.modules['conestoga_playblast_utils']
                if 'conestoga_playblast_menu' in sys.modules:
                    del sys.modules['conestoga_playblast_menu']
                if 'conestoga_playblast' in sys.modules:
                    del sys.modules['conestoga_playblast']
                
                # Import modules
                import conestoga_playblast_presets
                print("Imported presets module")
                
                import conestoga_playblast_utils
                print("Imported utils module")
                
                import conestoga_playblast_menu
                print("Imported menu module")
                
                # Initialize menu
                conestoga_playblast_menu.initialize()
                print("Successfully initialized menu")
                
            except Exception as e:
                print(f"Warning: Could not immediately initialize tool: {str(e)}")
                traceback.print_exc()
                
            cmds.progressWindow(endProgress=True)
            
            # Show success message with proper formatting
            cmds.confirmDialog(
                title="Installation Complete",
                message=f'''Conestoga Playblast Tool has been successfully installed!

Buttons have been added to the "{target_shelf}" shelf.
The tool will automatically load when you start Maya.

To use the tool, click the "Playblast" button on the shelf,
or use the Conestoga Playblast menu in the main menu bar.''',
                button=["OK"]
            )
            
        except Exception as e:
            cmds.progressWindow(endProgress=True)
            print("Installation error: " + str(e))
            traceback.print_exc()
            cmds.confirmDialog(
                title="Installation Error", 
                message=f"An error occurred during installation:\n\n{str(e)}\n\nSee script editor for details.", 
                button=["OK"]
            )

    # Start the installation dialog
    show_installation_dialog()

# End of onMayaDroppedPythonFile function