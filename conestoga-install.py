"""
Conestoga Playblast Tool - Installation Script

This script installs the Conestoga Playblast Tool into the user's Maya scripts directory
and optionally sets up the userSetup.py to load the tool on Maya startup.

Usage:
    1. Run this script in a Python environment with os and shutil modules available
    2. Follow the prompts to complete installation
"""

import os
import sys
import shutil
import platform
import glob
from textwrap import dedent

def get_maya_scripts_dir():
    """Get the user's Maya scripts directory based on OS."""
    maya_dir = None
    
    if platform.system() == "Windows":
        documents = os.path.join(os.path.expanduser("~"), "Documents")
        maya_dir = os.path.join(documents, "maya")
    elif platform.system() == "Darwin":  # macOS
        maya_dir = os.path.join(os.path.expanduser("~"), "Library", "Preferences", "Autodesk", "maya")
    elif platform.system() == "Linux":
        maya_dir = os.path.join(os.path.expanduser("~"), "maya")
    
    if not maya_dir or not os.path.exists(maya_dir):
        print("Could not locate Maya directory. Please enter your Maya scripts directory manually.")
        return None
    
    # Find all version directories
    version_dirs = [d for d in os.listdir(maya_dir) if os.path.isdir(os.path.join(maya_dir, d))]
    version_dirs = [d for d in version_dirs if d.isdigit()]
    
    if not version_dirs:
        print("No Maya version directories found. Please enter your Maya scripts directory manually.")
        return None
    
    # Sort by newest version
    version_dirs.sort(reverse=True)
    
    # Let user choose version
    print("Found Maya versions:")
    for i, version in enumerate(version_dirs):
        print(f"{i+1}. Maya {version}")
    
    choice = input("Which version to install for? (Enter number, or 'a' for all, or 'm' for manual): ")
    
    if choice.lower() == 'm':
        return None
    elif choice.lower() == 'a':
        # Return the parent directory for manual copying later
        return maya_dir
    else:
        try:
            index = int(choice) - 1
            version = version_dirs[index]
            scripts_dir = os.path.join(maya_dir, version, "scripts")
            if not os.path.exists(scripts_dir):
                os.makedirs(scripts_dir)
            return scripts_dir
        except (ValueError, IndexError):
            print("Invalid choice. Please enter your Maya scripts directory manually.")
            return None

def install_to_directory(source_dir, target_dir):
    """Install the playblast tool to the specified directory."""
    # Create target directory if it doesn't exist
    if not os.path.exists(target_dir):
        os.makedirs(target_dir)
    
    # Create conestoga_playblast directory in target
    conestoga_dir = os.path.join(target_dir, "conestoga_playblast")
    if not os.path.exists(conestoga_dir):
        os.makedirs(conestoga_dir)
    
    # Copy all Python files
    py_files = glob.glob(os.path.join(source_dir, "*.py"))
    for py_file in py_files:
        shutil.copy2(py_file, conestoga_dir)
    
    # Copy any additional directories
    for item in os.listdir(source_dir):
        item_path = os.path.join(source_dir, item)
        if os.path.isdir(item_path) and item != "__pycache__":
            target_subdir = os.path.join(conestoga_dir, item)
            shutil.copytree(item_path, target_subdir, dirs_exist_ok=True)
    
    print(f"Files copied to {conestoga_dir}")
    
    # Create the plugin directory
    plugins_dir = os.path.join(os.path.dirname(target_dir), "plug-ins")
    if not os.path.exists(plugins_dir):
        os.makedirs(plugins_dir)
    
    # Copy plugin file to plugins directory
    plugin_file = os.path.join(source_dir, "conestoga-playblast-plugin.py")
    if os.path.exists(plugin_file):
        shutil.copy2(plugin_file, plugins_dir)
        print(f"Plugin copied to {plugins_dir}")
    
    # Setup userSetup.py for automatic loading
    setup_usersetup(target_dir)
    
    return conestoga_dir

def setup_usersetup(target_dir):
    """Set up userSetup.py to load the tool at Maya startup."""
    usersetup_path = os.path.join(target_dir, "userSetup.py")
    
    # Code to add to userSetup.py
    code_to_add = """
# Conestoga Playblast Tool - Auto-load
import sys
import os

# Add conestoga_playblast to Python path
script_dir = os.path.dirname(os.path.abspath(__file__))
conestoga_dir = os.path.join(script_dir, "conestoga_playblast")
if conestoga_dir not in sys.path:
    sys.path.append(conestoga_dir)

# Load plugin and initialize menu
import maya.utils
maya.utils.executeDeferred("import conestoga_playblast_menu; conestoga_playblast_menu.initialize()")
"""
    
    # Check if userSetup.py exists
    if os.path.exists(usersetup_path):
        # Read existing content
        with open(usersetup_path, 'r') as f:
            content = f.read()
        
        # Check if our code is already in userSetup.py
        if "conestoga_playblast" in content:
            print("Tool already set up in userSetup.py")
            return
        
        # Ask user if they want to modify userSetup.py
        choice = input("Existing userSetup.py found. Modify it to auto-load the tool? (y/n): ")
        if choice.lower() != 'y':
            print("Skipping userSetup.py modification")
            return
        
        # Append our code
        with open(usersetup_path, 'a') as f:
            f.write("\n" + code_to_add)
    else:
        # Create new userSetup.py
        choice = input("Create userSetup.py to auto-load the tool at Maya startup? (y/n): ")
        if choice.lower() != 'y':
            print("Skipping userSetup.py creation")
            return
        
        with open(usersetup_path, 'w') as f:
            f.write(code_to_add)
    
    print(f"userSetup.py updated at {usersetup_path}")

def main():
    """Main installation function."""
    print("=== Conestoga Playblast Tool Installer ===")
    
    # Get current directory (where this script is located)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Check if required files exist
    required_files = [
        "conestoga_playblast.py",
        "conestoga_playblast_utils.py",
        "conestoga_playblast_presets.py",
        "conestoga_playblast_ui.py",
        "conestoga_playblast_menu.py",
        "conestoga-playblast-plugin.py"
    ]
    
    missing_files = [f for f in required_files if not os.path.exists(os.path.join(current_dir, f))]
    if missing_files:
        print("Error: The following required files are missing:")
        for f in missing_files:
            print(f"  - {f}")
        print("Please make sure all files are in the same directory as this installer.")
        return
    
    # Get Maya scripts directory
    scripts_dir = get_maya_scripts_dir()
    
    # If user wants to install to all versions or scripts_dir is the Maya directory
    if scripts_dir and not os.path.basename(scripts_dir) == "scripts":
        maya_dir = scripts_dir
        for version_dir in os.listdir(maya_dir):
            version_scripts_dir = os.path.join(maya_dir, version_dir, "scripts")
            if os.path.isdir(os.path.join(maya_dir, version_dir)) and version_dir.isdigit():
                if not os.path.exists(version_scripts_dir):
                    os.makedirs(version_scripts_dir)
                print(f"\nInstalling for Maya {version_dir}...")
                install_to_directory(current_dir, version_scripts_dir)
    else:
        # Ask for manual entry if automatic detection failed
        if not scripts_dir:
            scripts_dir = input("Enter your Maya scripts directory: ")
            if not os.path.exists(scripts_dir):
                create_dir = input(f"Directory {scripts_dir} doesn't exist. Create it? (y/n): ")
                if create_dir.lower() == 'y':
                    os.makedirs(scripts_dir)
                else:
                    print("Installation cancelled.")
                    return
        
        # Install to the specified directory
        install_to_directory(current_dir, scripts_dir)
    
    print("\nInstallation complete!")
    print("\nTo use the tool in Maya:")
    print("1. Start Maya")
    print("2. The 'Conestoga GameDev' menu should appear in the menu bar")
    print("3. Select 'Conestoga GameDev > Playblast Tools > Conestoga Playblast Tool'")
    print("\nIf the menu doesn't appear automatically, run this code in the script editor:")
    print("import sys; sys.path.append(r'" + os.path.join(scripts_dir, "conestoga_playblast") + "')")
    print("import conestoga_playblast_menu; conestoga_playblast_menu.initialize()")

if __name__ == "__main__":
    main()
    input("\nPress Enter to exit...")
