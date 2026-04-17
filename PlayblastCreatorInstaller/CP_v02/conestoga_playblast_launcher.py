# conestoga_playblast_launcher.py
def launch_conestoga_playblast():
    """Launch the Conestoga Playblast tool."""
    import sys
    import os
    import maya.cmds as cmds
    
    # Add the tool directory to the Python path
    tool_dir = os.path.dirname(os.path.abspath(__file__))
    if tool_dir not in sys.path:
        sys.path.append(tool_dir)
    
    # Make sure the tool directory includes all the necessary modules
    print(f"Loading Conestoga Playblast Tool from: {tool_dir}")
    
    try:
        # Remove any existing instances of the UI
        if cmds.window("ConestoPlayblastDialog", exists=True):
            cmds.deleteUI("ConestoPlayblastDialog")
        
        # Import the UI module
        import conestoga_playblast_ui
        
        # Show the UI
        conestoga_playblast_ui.show_playblast_dialog()
        
        print("Conestoga Playblast Tool launched successfully")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Error launching Conestoga Playblast Tool: {str(e)}")