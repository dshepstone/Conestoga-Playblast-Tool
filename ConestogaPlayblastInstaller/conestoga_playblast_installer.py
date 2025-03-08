"""
Conestoga Playblast Tool - Installer
This script installs the Conestoga Playblast Tool into Maya.
Compatible with Python 3.
"""

import os
import sys
import shutil
import maya.cmds as cmds
import maya.mel as mel
import re
import traceback

def get_maya_directories():
    """Get the Maya user directories for scripts, plugins, and icons."""
    maya_app_dir = cmds.internalVar(userAppDir=True)
    scripts_dir = os.path.join(maya_app_dir, "scripts")
    plugins_dir = os.path.join(maya_app_dir, "plug-ins")
    icons_dir = os.path.join(maya_app_dir, "prefs", "icons")
    
    # Create directories if they don't exist
    for directory in [scripts_dir, plugins_dir, icons_dir]:
        if not os.path.exists(directory):
            os.makedirs(directory)
            
    return scripts_dir, plugins_dir, icons_dir

def get_available_shelves():
    """Get a list of available shelves in Maya."""
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
    return ["Custom", "Animation", "Polygons", "Surfaces", "Dynamics", "Rendering"]

def show_installation_dialog():
    """Show a dialog for selecting installation options."""
    if cmds.window("conestoPlayblastInstaller", exists=True):
        cmds.deleteUI("conestoPlayblastInstaller")
        
    window = cmds.window("conestoPlayblastInstaller", title="Conestoga Playblast Tool Installer", widthHeight=(400, 240))
    main_layout = cmds.columnLayout(adjustableColumn=True, columnAttach=('both', 10), rowSpacing=10, columnWidth=380)
    
    # Header
    cmds.text(label="<h1>Conestoga Playblast Tool</h1>", height=40)
    cmds.separator()
    
    # Installation location info
    cmds.text(label="This will install the Conestoga Playblast Tool to your Maya scripts directory.", align="left")
    cmds.text(label="Select which shelf to add the tool buttons:", align="left")
    
    # Shelf selection dropdown
    shelves = get_available_shelves()
    shelf_optmenu = cmds.optionMenu(label="Target Shelf: ", width=200)
    for shelf in shelves:
        cmds.menuItem(label=shelf)
        
    # Set a default shelf if exists
    default_shelf = "Animation"
    if default_shelf in shelves:
        cmds.optionMenu(shelf_optmenu, edit=True, value=default_shelf)
        
    cmds.separator()
    
    # Auto-load option
    auto_load_checkbox = cmds.checkBox(label="Load tool automatically when Maya starts", value=True)
    
    cmds.separator()
    
    # Buttons
    button_layout = cmds.rowLayout(numberOfColumns=2, columnWidth2=(190, 190), 
                                  columnAlign2=("center", "center"), 
                                  columnAttach=[(1, "both", 0), (2, "both", 0)])
    
    cmds.button(label="Install", width=180, height=30, 
                command=lambda x: perform_installation(
                    cmds.optionMenu(shelf_optmenu, query=True, value=True),
                    cmds.checkBox(auto_load_checkbox, query=True, value=True)
                ))
    cmds.button(label="Cancel", width=180, height=30, 
                command=lambda x: cmds.deleteUI("conestoPlayblastInstaller"))
                
    cmds.setParent(main_layout)
    
    cmds.showWindow(window)

def fix_python3_compatibility(file_path):
    """Fix Python 2 code to be Python 3 compatible."""
    if not os.path.exists(file_path):
        return False
        
    try:
        # Read the file content
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Fix print statements without parentheses
        # Match print statements that don't have parentheses
        content = re.sub(r'(?<!\w)print\s+"([^"]*)"', r'print("\1")', content)
        content = re.sub(r'(?<!\w)print\s+\'([^\']*)\'', r'print("\1")', content)
        
        # Fix any exception handling syntax that uses 'except Exception, e:'
        content = re.sub(r'except\s+([a-zA-Z0-9_]+),\s+([a-zA-Z0-9_]+):', r'except \1 as \2:', content)
        
        # Fix unicode/str handling for Python 3
        content = content.replace('unicode(', 'str(')
        
        # Fix syntax for raising exceptions
        content = re.sub(r'raise\s+([a-zA-Z0-9_]+),\s+"([^"]*)"', r'raise \1("\2")', content)
        
        # Remove any __future__ imports that aren't needed in Python 3
        content = re.sub(r'from\s+__future__\s+import\s+print_function\s*\n', '', content)
        
        # Replace iteritems() with items() for dictionaries
        content = re.sub(r'\.iteritems\(\)', '.items()', content)
        
        # Replace xrange() with range()
        content = re.sub(r'(?<!\w)xrange\(', 'range(', content)
        
        # Write the updated content back to the file
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
            
        return True
    except Exception as e:
        print(f"Error fixing Python 3 compatibility in {file_path}: {str(e)}")
        return False

def perform_installation(target_shelf, auto_load):
    """Perform the actual installation."""
    # Close the dialog
    if cmds.window("conestoPlayblastInstaller", exists=True):
        cmds.deleteUI("conestoPlayblastInstaller")
        
    # Show progress window
    cmds.progressWindow(
        title="Installing Conestoga Playblast Tool",
        progress=0,
        status="Starting installation...",
        isInterruptable=False
    )
    
    try:
        # Get Maya directories
        cmds.progressWindow(edit=True, progress=10, status="Finding Maya directories...")
        scripts_dir, plugins_dir, icons_dir = get_maya_directories()
        
        # Source directory (where this script is)
        source_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Create target directory
        cmds.progressWindow(edit=True, progress=20, status="Creating directories...")
        target_dir = os.path.join(scripts_dir, "conestoga_playblast")
        if not os.path.exists(target_dir):
            os.makedirs(target_dir)
            
        # Copy Python files
        cmds.progressWindow(edit=True, progress=30, status="Copying Python files...")
        python_files = [
            "conestoga_playblast.py",
            "conestoga_playblast_ui.py",
            "conestoga_playblast_utils.py",
            "conestoga_playblast_presets.py",
            "conestoga_playblast_menu.py",
            "conestoga_batch_playblast.py"
        ]
        
        for file_name in python_files:
            src_path = os.path.join(source_dir, file_name)
            # Check for both naming conventions
            if not os.path.exists(src_path):
                alt_name = file_name.replace("_", "-")
                alt_path = os.path.join(source_dir, alt_name)
                if os.path.exists(alt_path):
                    src_path = alt_path
                    
            if os.path.exists(src_path):
                dst_path = os.path.join(target_dir, file_name)
                shutil.copy2(src_path, dst_path)
                print(f"Copied {file_name} to {target_dir}")
                
                # Fix Python 3 compatibility issues
                fix_python3_compatibility(dst_path)
                
        # Copy plugin file
        cmds.progressWindow(edit=True, progress=50, status="Copying plugin files...")
        plugin_files = ["conestoga_playblast_plugin.py"]
        
        for file_name in plugin_files:
            src_path = os.path.join(source_dir, file_name)
            # Check for both naming conventions
            if not os.path.exists(src_path):
                alt_name = file_name.replace("_", "-")
                alt_path = os.path.join(source_dir, alt_name)
                if os.path.exists(alt_path):
                    src_path = alt_path
                    
            if os.path.exists(src_path):
                dst_path = os.path.join(plugins_dir, file_name)
                shutil.copy2(src_path, dst_path)
                print(f"Copied {file_name} to {plugins_dir}")
                
                # Fix Python 3 compatibility issues
                fix_python3_compatibility(dst_path)
                
        # Copy icon files
        cmds.progressWindow(edit=True, progress=60, status="Copying icon files...")
        for file_name in os.listdir(source_dir):
            if file_name.endswith(('.png', '.xpm', '.svg')) and "playblast" in file_name.lower():
                src_path = os.path.join(source_dir, file_name)
                dst_path = os.path.join(icons_dir, file_name)
                shutil.copy2(src_path, dst_path)
                print(f"Copied icon {file_name} to {icons_dir}")
                
        # Fix orphaned function in UI module
        cmds.progressWindow(edit=True, progress=70, status="Fixing UI module...")
        ui_file = os.path.join(target_dir, "conestoga_playblast_ui.py")
        if os.path.exists(ui_file):
            # Read the file content
            with open(ui_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check if the orphaned function exists
            if "def reset_shot_mask_settings(self):" in content and "class PlayblastDialog" in content:
                # Fix by moving the function into the class
                
                # Remove standalone function
                content = re.sub(r'from PySide6 import QtWidgets[\s\S]*?def reset_shot_mask_settings\(self\):[\s\S]*?self\.update_shot_mask\(\)', '', content)
                
                # Add function to class
                reset_function = '''
    def reset_shot_mask_settings(self):
        """Reset shot mask settings to defaults."""
        result = QtWidgets.QMessageBox.question(
            self, 
            "Reset Shot Mask Settings", 
            "Are you sure you want to reset all shot mask settings to defaults?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No
        )
        
        if result == QtWidgets.QMessageBox.Yes:
            # Reset text fields to default values
            self.topLeftLineEdit.setText("Scene: {scene}")
            self.topCenterLineEdit.setText("")
            self.topRightLineEdit.setText("FPS: {fps}")
            self.bottomLeftLineEdit.setText("Artist: {username}")
            self.bottomCenterLineEdit.setText("Date: {date}")
            self.bottomRightLineEdit.setText("Frame: {counter}")
            
            # Reset numerical settings
            self.maskScaleSpinBox.setValue(DEFAULT_MASK_SCALE)
            self.opacitySpinBox.setValue(1.0)
            self.vertPosSpinBox.setValue(0.0)
            self.zDistSpinBox.setValue(-1.0)
            self.counterPaddingSpinBox.setValue(DEFAULT_COUNTER_PADDING)
            
            # Reset border visibility
            self.topBorderCheckbox.setChecked(True)
            self.bottomBorderCheckbox.setChecked(True)
            
            # Update the live shot mask (if one exists)
            self.update_shot_mask()
'''
                # Find the class definition and add the function after it
                class_match = re.search(r'class PlayblastDialog\(QtWidgets\.QDialog\):', content)
                if class_match:
                    insert_pos = class_match.end()
                    content = content[:insert_pos] + reset_function + content[insert_pos:]
                
                # Write fixed content back
                with open(ui_file, 'w', encoding='utf-8') as f:
                    f.write(content)
                print("Fixed orphaned function in UI module")
                
        # Setup userSetup.py
        cmds.progressWindow(edit=True, progress=80, status="Setting up auto-loading...")
        if auto_load:
            setup_code = f'''
# Conestoga Playblast Tool - Auto-load
import sys
import os
import maya.utils

# Add conestoga_playblast to Python path
script_dir = os.path.dirname(os.path.abspath(__file__))
conestoga_dir = os.path.join(script_dir, "conestoga_playblast")
if conestoga_dir not in sys.path:
    sys.path.append(conestoga_dir)

# Initialize menu and shelf
def initialize_conestoga_playblast():
    try:
        import conestoga_playblast_menu
        conestoga_playblast_menu.initialize()
        print("Conestoga Playblast Tool initialized")
    except Exception as e:
        print(f"Error initializing Conestoga Playblast Tool: {{e}}")

maya.utils.executeDeferred(initialize_conestoga_playblast)
'''
            usersetup_file = os.path.join(scripts_dir, "userSetup.py")
            
            if os.path.exists(usersetup_file):
                # Check if our code is already in userSetup.py
                with open(usersetup_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                if "conestoga_playblast" not in content:
                    # Append our code
                    with open(usersetup_file, 'a', encoding='utf-8') as f:
                        f.write(setup_code)
            else:
                # Create new userSetup.py
                with open(usersetup_file, 'w', encoding='utf-8') as f:
                    f.write(setup_code)
                
        # Update menu module with target shelf
        cmds.progressWindow(edit=True, progress=90, status="Configuring menu...")
        menu_file = os.path.join(target_dir, "conestoga_playblast_menu.py")
        if os.path.exists(menu_file):
            # Read the file
            with open(menu_file, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Add or update TARGET_SHELF variable
            if "TARGET_SHELF" in content:
                content = re.sub(r'TARGET_SHELF\s*=\s*"[^"]*"', f'TARGET_SHELF = "{target_shelf}"', content)
            else:
                # Insert after VERSION if it exists
                if "VERSION" in content:
                    content = content.replace('VERSION =', f'VERSION =\n\n# Target shelf for buttons\nTARGET_SHELF = "{target_shelf}"\n')
            
            # Write back to file
            with open(menu_file, 'w', encoding='utf-8') as f:
                f.write(content)
                
        # Complete installation
        cmds.progressWindow(endProgress=True)
        
        # Show success message
        cmds.confirmDialog(
            title="Installation Complete",
            message=f'''Conestoga Playblast Tool has been successfully installed!

Buttons will be added to the "{target_shelf}" shelf.
{"The tool will automatically load when you start Maya." if auto_load else ""}

To use the tool, you can:
- Restart Maya (recommended)
- Run this Python code in the script editor:
  import conestoga_playblast
  conestoga_playblast.show_ui()''',
            button=["OK"]
        )
        
    except Exception as e:
        cmds.progressWindow(endProgress=True)
        cmds.confirmDialog(
            title="Installation Error", 
            message=f"An error occurred during installation:\n\n{str(e)}\n\nSee script editor for details.", 
            button=["OK"]
        )
        traceback.print_exc()

def install():
    """Main installer function."""
    show_installation_dialog()

if __name__ == "__main__":
    install()