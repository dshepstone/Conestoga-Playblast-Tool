"""
Conestoga Playblast Tool - UI Module
This module provides the user interface for the Conestoga Playblast Tool.
"""

import os
import sys
import maya.cmds as cmds

# Add script directory to path if needed
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.append(script_dir)

import conestoga_playblast_presets as presets
import conestoga_playblast_utils as utils

def show_playblast_dialog():
    """
    Show the main playblast dialog.
    
    Returns:
        str: Window name of the created dialog
    """
    # Create the UI window
    window_name = "ConestoPlayblastDialog"
    
    # Delete window if it already exists
    if cmds.window(window_name, exists=True):
        cmds.deleteUI(window_name)
    
    # Create the window
    cmds.window(window_name, title=f"{presets.TOOL_NAME} v{presets.VERSION}", width=500, height=650)
    
    # Main layout
    cmds.columnLayout(adjustableColumn=True, columnAttach=("both", 5), rowSpacing=5)
    
    # Title
    cmds.text(label=f"{presets.TOOL_NAME}", height=30, font="boldLabelFont")
    cmds.separator(height=10, style="in")
    
    # Output section
    cmds.frameLayout(label="Output Settings", collapsable=True, collapse=False)
    cmds.columnLayout(adjustableColumn=True, columnAttach=("both", 5))
    
    # Output directory
    output_dir = os.path.join(cmds.workspace(query=True, rootDirectory=True), "movies")
    output_dir_field = cmds.textFieldButtonGrp(
        label="Output Directory:", 
        text=output_dir,
        buttonLabel="Browse...",
        buttonCommand=lambda: browse_directory(output_dir_field)
    )
    
    # Filename field
    filename_field = cmds.textFieldGrp(
        label="Filename:", 
        text="{scene}_{camera}"
    )
    
    cmds.setParent("..")
    cmds.setParent("..")
    
    # Camera section
    cmds.frameLayout(label="Camera", collapsable=True, collapse=False)
    cmds.columnLayout(adjustableColumn=True, columnAttach=("both", 5))
    
    # Camera selection
    camera_menu = cmds.optionMenu(label="Camera:")
    cmds.menuItem(label="<Active Camera>")
    for cam in cmds.listCameras():
        cmds.menuItem(label=cam)
    
    cmds.setParent("..")
    cmds.setParent("..")
    
    # Resolution section
    cmds.frameLayout(label="Resolution", collapsable=True, collapse=False)
    cmds.columnLayout(adjustableColumn=True, columnAttach=("both", 5))
    
    # Resolution preset
    resolution_menu = cmds.optionMenu(
        label="Preset:",
        changeCommand=lambda val: update_resolution(val, width_field, height_field)
    )
    
    for preset in presets.RESOLUTION_PRESETS:
        cmds.menuItem(label=preset)
    
    # Width and height fields
    cmds.rowLayout(numberOfColumns=4, columnWidth4=(60, 80, 60, 80), adjustableColumn=4)
    cmds.text(label="Width:")
    width_field = cmds.intField(value=1920, minValue=1, maxValue=9999)
    cmds.text(label="Height:")
    height_field = cmds.intField(value=1080, minValue=1, maxValue=9999)
    cmds.setParent("..")
    
    cmds.setParent("..")
    cmds.setParent("..")
    
    # Frame range section
    cmds.frameLayout(label="Frame Range", collapsable=True, collapse=False)
    cmds.columnLayout(adjustableColumn=True, columnAttach=("both", 5))
    
    # Frame range preset
    frame_range_menu = cmds.optionMenu(
        label="Preset:", 
        changeCommand=lambda val: update_frame_range(val, start_field, end_field)
    )
    
    for preset in ["Playback", "Animation", "Render", "Camera", "Custom"]:
        cmds.menuItem(label=preset)
    
    # Start and end fields
    cmds.rowLayout(numberOfColumns=4, columnWidth4=(60, 80, 60, 80), adjustableColumn=4)
    cmds.text(label="Start:")
    start_field = cmds.intField(value=int(cmds.playbackOptions(q=True, minTime=True)))
    cmds.text(label="End:")
    end_field = cmds.intField(value=int(cmds.playbackOptions(q=True, maxTime=True)))
    cmds.setParent("..")
    
    cmds.setParent("..")
    cmds.setParent("..")
    
    # Format section
    cmds.frameLayout(label="Format", collapsable=True, collapse=False)
    cmds.columnLayout(adjustableColumn=True, columnAttach=("both", 5))
    
    # Format selection
    format_menu = cmds.optionMenu(
        label="Format:", 
        changeCommand=lambda val: update_encoders(val, encoder_menu)
    )
    
    for fmt in presets.OUTPUT_FORMATS:
        cmds.menuItem(label=fmt)
    
    # Encoder selection
    encoder_menu = cmds.optionMenu(label="Encoder:")
    for encoder in presets.VIDEO_ENCODERS["mp4"]:
        cmds.menuItem(label=encoder)
    
    # Quality selection
    quality_menu = cmds.optionMenu(label="Quality:")
    for quality in presets.H264_QUALITIES.keys():
        cmds.menuItem(label=quality)
    cmds.optionMenu(quality_menu, edit=True, value="High")
    
    cmds.setParent("..")
    cmds.setParent("..")
    
    # Shot mask section
    cmds.frameLayout(label="Shot Mask", collapsable=True, collapse=False)
    cmds.columnLayout(adjustableColumn=True, columnAttach=("both", 5))
    
    shot_mask_check = cmds.checkBox(label="Enable Shot Mask", value=True)
    
    cmds.setParent("..")
    cmds.setParent("..")
    
    # Options section
    cmds.frameLayout(label="Options", collapsable=True, collapse=False)
    cmds.columnLayout(adjustableColumn=True, columnAttach=("both", 5))
    
    viewer_check = cmds.checkBox(label="Show in Viewer", value=True)
    overwrite_check = cmds.checkBox(label="Force Overwrite", value=False)
    
    cmds.setParent("..")
    cmds.setParent("..")
    
    # Buttons
    cmds.separator(height=10, style="in")
    cmds.rowLayout(numberOfColumns=3, columnWidth3=(100, 200, 100), adjustableColumn=2, columnAlign=(1, "center"))
    
    # Create buttons
    cmds.button(
        label="Reset", 
        command=lambda x: reset_ui_values(
            output_dir_field, filename_field, camera_menu, resolution_menu,
            width_field, height_field, frame_range_menu, start_field, end_field,
            format_menu, encoder_menu, quality_menu, shot_mask_check, 
            viewer_check, overwrite_check
        )
    )
    
    cmds.button(
        label="Create Playblast", 
        command=lambda x: create_playblast_from_ui(
            output_dir_field, filename_field, camera_menu, 
            width_field, height_field, start_field, end_field,
            format_menu, encoder_menu, quality_menu, shot_mask_check,
            viewer_check, overwrite_check
        )
    )
    
    cmds.button(label="Close", command=f"cmds.deleteUI('{window_name}')")
    cmds.setParent("..")
    
    # Initialize UI states
    update_resolution(cmds.optionMenu(resolution_menu, q=True, value=True), width_field, height_field)
    update_frame_range(cmds.optionMenu(frame_range_menu, q=True, value=True), start_field, end_field)
    update_encoders(cmds.optionMenu(format_menu, q=True, value=True), encoder_menu)
    
    # Show the window
    cmds.showWindow(window_name)
    return window_name

# Helper UI functions
def browse_directory(field_name):
    """Browse for an output directory."""
    current_dir = cmds.textFieldButtonGrp(field_name, q=True, text=True)
    new_dir = cmds.fileDialog2(
        fileMode=3,  # Directory selection mode
        dialogStyle=2,  # Maya style dialog
        startingDirectory=current_dir
    )
    
    if new_dir:
        cmds.textFieldButtonGrp(field_name, e=True, text=new_dir[0])

def update_resolution(preset, width_field, height_field):
    """Update resolution fields based on selected preset."""
    if preset == "Render":
        width = cmds.getAttr("defaultResolution.width")
        height = cmds.getAttr("defaultResolution.height")
        cmds.intField(width_field, e=True, value=width)
        cmds.intField(height_field, e=True, value=height)
    elif preset in presets.RESOLUTION_PRESETS:
        dimensions = presets.RESOLUTION_PRESETS.get(preset)
        if dimensions:  # Some presets might be None to use render resolution
            cmds.intField(width_field, e=True, value=dimensions[0])
            cmds.intField(height_field, e=True, value=dimensions[1])

def update_frame_range(preset, start_field, end_field):
    """Update frame range fields based on selected preset."""
    if preset == "Playback":
        start = cmds.playbackOptions(q=True, minTime=True)
        end = cmds.playbackOptions(q=True, maxTime=True)
    elif preset == "Animation":
        start = cmds.playbackOptions(q=True, animationStartTime=True)
        end = cmds.playbackOptions(q=True, animationEndTime=True)
    elif preset == "Render":
        start = cmds.getAttr("defaultRenderGlobals.startFrame")
        end = cmds.getAttr("defaultRenderGlobals.endFrame")
    else:  # Camera or Custom
        return  # Keep current values
    
    cmds.intField(start_field, e=True, value=int(start))
    cmds.intField(end_field, e=True, value=int(end))

def update_encoders(format_type, encoder_menu):
    """Update encoder options based on selected format."""
    cmds.optionMenu(encoder_menu, e=True, deleteAllItems=True)
    
    if format_type in presets.VIDEO_ENCODERS:
        for encoder in presets.VIDEO_ENCODERS[format_type]:
            cmds.menuItem(parent=encoder_menu, label=encoder)

def reset_ui_values(output_dir_field, filename_field, camera_menu, resolution_menu,
                   width_field, height_field, frame_range_menu, start_field, end_field,
                   format_menu, encoder_menu, quality_menu, shot_mask_check, 
                   viewer_check, overwrite_check):
    """Reset all UI fields to default values."""
    # Reset output fields
    cmds.textFieldButtonGrp(output_dir_field, e=True, 
                            text=os.path.join(cmds.workspace(q=True, rootDirectory=True), "movies"))
    cmds.textFieldGrp(filename_field, e=True, text="{scene}_{camera}")
    
    # Reset camera
    cmds.optionMenu(camera_menu, e=True, value="<Active Camera>")
    
    # Reset resolution
    cmds.optionMenu(resolution_menu, e=True, value=presets.DEFAULT_RESOLUTION)
    update_resolution(presets.DEFAULT_RESOLUTION, width_field, height_field)
    
    # Reset frame range
    cmds.optionMenu(frame_range_menu, e=True, value=presets.DEFAULT_FRAME_RANGE)
    update_frame_range(presets.DEFAULT_FRAME_RANGE, start_field, end_field)
    
    # Reset format
    cmds.optionMenu(format_menu, e=True, value=presets.DEFAULT_OUTPUT_FORMAT)
    update_encoders(presets.DEFAULT_OUTPUT_FORMAT, encoder_menu)
    
    # Reset encoder
    cmds.optionMenu(encoder_menu, e=True, value=presets.DEFAULT_ENCODER)
    
    # Reset quality
    cmds.optionMenu(quality_menu, e=True, value=presets.DEFAULT_H264_QUALITY)
    
    # Reset checkboxes
    cmds.checkBox(shot_mask_check, e=True, value=True)
    cmds.checkBox(viewer_check, e=True, value=True)
    cmds.checkBox(overwrite_check, e=True, value=False)

def create_playblast_from_ui(output_dir_field, filename_field, camera_menu, 
                            width_field, height_field, start_field, end_field,
                            format_menu, encoder_menu, quality_menu, shot_mask_check,
                            viewer_check, overwrite_check):
    """Gather values from UI and create the playblast."""
    import conestoga_playblast
    
    # Get values from UI
    output_dir = cmds.textFieldButtonGrp(output_dir_field, q=True, text=True)
    filename = cmds.textFieldGrp(filename_field, q=True, text=True)
    
    camera = cmds.optionMenu(camera_menu, q=True, value=True)
    if camera == "<Active Camera>":
        camera = None
    
    width = cmds.intField(width_field, q=True, value=True)
    height = cmds.intField(height_field, q=True, value=True)
    
    start_frame = cmds.intField(start_field, q=True, value=True)
    end_frame = cmds.intField(end_field, q=True, value=True)
    
    format_type = cmds.optionMenu(format_menu, q=True, value=True)
    encoder = cmds.optionMenu(encoder_menu, q=True, value=True)
    quality = cmds.optionMenu(quality_menu, q=True, value=True)
    
    shot_mask = cmds.checkBox(shot_mask_check, q=True, value=True)
    show_in_viewer = cmds.checkBox(viewer_check, q=True, value=True)
    force_overwrite = cmds.checkBox(overwrite_check, q=True, value=True)
    
    # Call the playblast function
    try:
        result = conestoga_playblast.create_playblast(
            camera=camera,
            output_dir=output_dir,
            filename=filename,
            width=width,
            height=height,
            start_frame=start_frame,
            end_frame=end_frame,
            format_type=format_type,
            encoder=encoder,
            quality=quality,
            shot_mask=shot_mask,
            show_in_viewer=show_in_viewer,
            force_overwrite=force_overwrite
        )
        
        if result:
            cmds.confirmDialog(
                title="Playblast Complete",
                message=f"Playblast created successfully:\n{result}",
                button=["OK"]
            )
        else:
            cmds.confirmDialog(
                title="Playblast Failed",
                message="Failed to create playblast. See script editor for details.",
                button=["OK"]
            )
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        cmds.confirmDialog(
            title="Error",
            message=f"An error occurred:\n{str(e)}",
            button=["OK"]
        )