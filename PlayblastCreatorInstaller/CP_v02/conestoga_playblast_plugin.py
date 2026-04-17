"""
Conestoga Playblast Tool - Maya Plugin
Implements core plugin functionality and commands for the playblast tool.

This file should be placed in your Maya plug-ins directory.
"""

import os
import sys
import json
import maya.api.OpenMaya as om
import maya.cmds as cmds

# Add plugin directory to path for imports
plugin_dir = os.path.dirname(os.path.realpath(__file__))
plugin_parent_dir = os.path.dirname(plugin_dir)
scripts_dir = os.path.join(plugin_parent_dir, "scripts")

if scripts_dir not in sys.path:
    sys.path.append(scripts_dir)

# Import tool modules
try:
    import conestoga_playblast_presets as presets
    import conestoga_playblast_utils as utils
except ImportError:
    om.MGlobal.displayError("Failed to import Conestoga Playblast modules.")
    raise

def maya_useNewAPI():
    """Tell Maya this plugin uses the newer Python API 2.0"""
    pass

# ===========================================================================
# PLUGIN COMMAND
# ===========================================================================

class ConestogsPlayblastCommand(om.MPxCommand):
    """Main command for the Conestoga Playblast Tool"""
    
    COMMAND_NAME = "conePlayblast"
    
    # Command flags
    VERSION_FLAG = ["-v", "-version", om.MSyntax.kBoolean]
    
    FFMPEG_PATH_FLAG = ["-fp", "-ffmpegPath", om.MSyntax.kString]
    FFMPEG_CHECK_FLAG = ["-fc", "-ffmpegCheck", om.MSyntax.kBoolean]
    
    TEMP_DIR_FLAG = ["-td", "-tempDir", om.MSyntax.kString]
    
    SHOW_UI_FLAG = ["-ui", "-showUI", om.MSyntax.kBoolean]
    
    def __init__(self):
        super(ConestogsPlayblastCommand, self).__init__()
        self.undoable = False

    def doIt(self, arg_list):
        """Execute the command"""
        try:
            syntax = self.syntax()
            arg_db = om.MArgDatabase(syntax, arg_list)
        except:
            self.displayError("Error parsing arguments")
            return
        
        # Process flag options
        if arg_db.isFlagSet(self.VERSION_FLAG[0]):
            # Return version information
            self.setResult(presets.VERSION)
            return
            
        if arg_db.isFlagSet(self.FFMPEG_PATH_FLAG[0]):
            # Set or get ffmpeg path
            if arg_db.isEdit():
                path = arg_db.flagArgumentString(self.FFMPEG_PATH_FLAG[0], 0)
                utils.save_option_var("ffmpegPath", path)
                self.setResult(f"FFmpeg path set to: {path}")
            elif arg_db.isQuery():
                path = utils.load_option_var("ffmpegPath", "")
                self.setResult(path)
            return
            
        if arg_db.isFlagSet(self.FFMPEG_CHECK_FLAG[0]):
            # Check ffmpeg availability
            available = utils.is_ffmpeg_available()
            self.setResult(available)
            return
            
        if arg_db.isFlagSet(self.TEMP_DIR_FLAG[0]):
            # Set or get temp directory
            if arg_db.isEdit():
                path = arg_db.flagArgumentString(self.TEMP_DIR_FLAG[0], 0)
                utils.save_option_var("tempDir", path)
                self.setResult(f"Temp directory set to: {path}")
            elif arg_db.isQuery():
                path = utils.load_option_var("tempDir", "")
                self.setResult(path)
            return
            
        if arg_db.isFlagSet(self.SHOW_UI_FLAG[0]):
            # Show UI
            self.showUI()
            return
            
        # If no flags, show UI by default
        self.showUI()

    def showUI(self):
        """Show the playblast UI"""
        # Import here to avoid circular imports
        import conestoga_playblast_ui
        conestoga_playblast_ui.show_playblast_dialog()
        self.setResult("UI displayed")

    def displayError(self, message):
        """Display an error message"""
        om.MGlobal.displayError(f"[{self.COMMAND_NAME}] {message}")

    @staticmethod
    def creator():
        """Create an instance of the command"""
        return ConestogsPlayblastCommand()

    @staticmethod
    def createSyntax():
        """Create command syntax"""
        syntax = om.MSyntax()
        
        # Add flags with types
        syntax.addFlag(*ConestogsPlayblastCommand.VERSION_FLAG)
        syntax.addFlag(*ConestogsPlayblastCommand.FFMPEG_PATH_FLAG)
        syntax.addFlag(*ConestogsPlayblastCommand.FFMPEG_CHECK_FLAG)
        syntax.addFlag(*ConestogsPlayblastCommand.TEMP_DIR_FLAG)
        syntax.addFlag(*ConestogsPlayblastCommand.SHOW_UI_FLAG)
        
        # Enable edit/query for relevant flags
        syntax.enableEdit = True
        syntax.enableQuery = True
        
        return syntax

# ===========================================================================
# INITIALIZATION
# ===========================================================================

def initializePlugin(plugin):
    """Initialize the plugin"""
    vendor = "Conestoga College"
    plugin_fn = om.MFnPlugin(plugin, vendor, presets.VERSION, "Any")
    
    try:
        plugin_fn.registerCommand(
            ConestogsPlayblastCommand.COMMAND_NAME,
            ConestogsPlayblastCommand.creator,
            ConestogsPlayblastCommand.createSyntax
        )
    except:
        om.MGlobal.displayError(f"Failed to register command: {ConestogsPlayblastCommand.COMMAND_NAME}")
        raise

    # Display plugin loaded message
    om.MGlobal.displayInfo(f"Successfully loaded {presets.TOOL_NAME} v{presets.VERSION}")

def uninitializePlugin(plugin):
    """Uninitialize the plugin"""
    plugin_fn = om.MFnPlugin(plugin)
    
    try:
        plugin_fn.deregisterCommand(ConestogsPlayblastCommand.COMMAND_NAME)
    except:
        om.MGlobal.displayError(f"Failed to deregister command: {ConestogsPlayblastCommand.COMMAND_NAME}")
        raise