"""
Conestoga Playblast Tool - Maya Startup Script

This script is executed when Maya starts up. It adds the Conestoga Playblast
Tool to Maya's UI and loads the necessary Python modules.

To activate, copy this file to your Maya scripts directory.
"""

import sys
import os
import maya.cmds as cmds
import maya.utils

# Add the conestoga_playblast directory to Python path
script_dir = os.path.dirname(os.path.abspath(__file__))
conestoga_dir = os.path.join(script_dir, "conestoga_playblast")
if conestoga_dir not in sys.path:
    sys.path.append(conestoga_dir)

def initialize_conestoga_playblast():
    """Initialize the Conestoga Playblast Tool."""
    # Import the menu module and initialize
    try:
        import conestoga_playblast_menu
        conestoga_playblast_menu.initialize()
        print("Conestoga Playblast Tool initialized")
    except Exception as e:
        print(f"Error initializing Conestoga Playblast Tool: {e}")

# Schedule the initialization to run after Maya is fully loaded
maya.utils.executeDeferred(initialize_conestoga_playblast)
