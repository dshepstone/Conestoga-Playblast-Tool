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

# Try to import Qt frameworks based on Maya version
try:
    from PySide6 import QtWidgets, QtCore, QtGui
except ImportError:
    try:
        from PySide2 import QtWidgets, QtCore, QtGui
    except ImportError:
        from PySide import QtWidgets, QtCore, QtGui

class PlayblastDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(PlayblastDialog, self).__init__(parent)
        
        self.setWindowTitle(f"{presets.TOOL_NAME} v{presets.VERSION}")
        self.setMinimumWidth(500)
        self.setMinimumHeight(600)
        self.setObjectName("ConestoPlayblastDialog")
        
        self.create_widgets()
        self.create_layouts()
        self.create_connections()
        self.update_ui()
        
    def create_widgets(self):
        # Output settings
        self.output_group = QtWidgets.QGroupBox("Output Settings")
        self.output_dir_label = QtWidgets.QLabel("Output Directory:")
        self.output_dir_field = QtWidgets.QLineEdit()
        self.output_dir_browse = QtWidgets.QPushButton("Browse...")
        
        self.filename_label = QtWidgets.QLabel("Filename:")
        self.filename_field = QtWidgets.QLineEdit("{scene}_{camera}")
        
        # Camera settings
        self.camera_group = QtWidgets.QGroupBox("Camera")
        self.camera_label = QtWidgets.QLabel("Camera:")
        self.camera_combo = QtWidgets.QComboBox()
        self.camera_combo.addItem(presets.DEFAULT_CAMERA)
        
        # Resolution settings
        self.resolution_group = QtWidgets.QGroupBox("Resolution")
        self.resolution_label = QtWidgets.QLabel("Preset:")
        self.resolution_combo = QtWidgets.QComboBox()
        for preset in presets.RESOLUTION_PRESETS:
            self.resolution_combo.addItem(preset)
        
        self.width_label = QtWidgets.QLabel("Width:")
        self.width_field = QtWidgets.QSpinBox()
        self.width_field.setRange(1, 9999)
        self.width_field.setValue(1920)
        
        self.height_label = QtWidgets.QLabel("Height:")
        self.height_field = QtWidgets.QSpinBox()
        self.height_field.setRange(1, 9999)
        self.height_field.setValue(1080)
        
        # Frame range settings
        self.frame_range_group = QtWidgets.QGroupBox("Frame Range")
        self.frame_range_label = QtWidgets.QLabel("Preset:")
        self.frame_range_combo = QtWidgets.QComboBox()
        self.frame_range_combo.addItems(["Playback", "Animation", "Render", "Camera", "Custom"])
        
        self.start_frame_label = QtWidgets.QLabel("Start:")
        self.start_frame_field = QtWidgets.QSpinBox()
        self.start_frame_field.setRange(-9999, 9999)
        
        self.end_frame_label = QtWidgets.QLabel("End:")
        self.end_frame_field = QtWidgets.QSpinBox()
        self.end_frame_field.setRange(-9999, 9999)
        
        # Format settings
        self.format_group = QtWidgets.QGroupBox("Format")
        self.format_label = QtWidgets.QLabel("Format:")
        self.format_combo = QtWidgets.QComboBox()
        self.format_combo.addItems(presets.OUTPUT_FORMATS)
        
        self.encoder_label = QtWidgets.QLabel("Encoder:")
        self.encoder_combo = QtWidgets.QComboBox()
        
        self.quality_label = QtWidgets.QLabel("Quality:")
        self.quality_combo = QtWidgets.QComboBox()
        self.quality_combo.addItems(list(presets.H264_QUALITIES.keys()))
        
        # Shot mask settings
        self.shot_mask_group = QtWidgets.QGroupBox("Shot Mask")
        self.shot_mask_checkbox = QtWidgets.QCheckBox("Enable Shot Mask")
        self.shot_mask_checkbox.setChecked(True)
        
        # Create shot mask text input fields
        self.topLeftLabel = QtWidgets.QLabel("Top Left:")
        self.topLeftLineEdit = QtWidgets.QLineEdit("Scene: {scene}")
        
        self.topCenterLabel = QtWidgets.QLabel("Top Center:")
        self.topCenterLineEdit = QtWidgets.QLineEdit("")
        
        self.topRightLabel = QtWidgets.QLabel("Top Right:")
        self.topRightLineEdit = QtWidgets.QLineEdit("FPS: {fps}")
        
        self.bottomLeftLabel = QtWidgets.QLabel("Bottom Left:")
        self.bottomLeftLineEdit = QtWidgets.QLineEdit("Artist: {username}")
        
        self.bottomCenterLabel = QtWidgets.QLabel("Bottom Center:")
        self.bottomCenterLineEdit = QtWidgets.QLineEdit("Date: {date}")
        
        self.bottomRightLabel = QtWidgets.QLabel("Bottom Right:")
        self.bottomRightLineEdit = QtWidgets.QLineEdit("Frame: {counter}")
        
        # Additional options
        self.options_group = QtWidgets.QGroupBox("Options")
        self.show_in_viewer_checkbox = QtWidgets.QCheckBox("Show in Viewer")
        self.show_in_viewer_checkbox.setChecked(True)
        
        self.overwrite_checkbox = QtWidgets.QCheckBox("Force Overwrite")
        self.overwrite_checkbox.setChecked(False)
        
        # Buttons
        self.reset_button = QtWidgets.QPushButton("Reset")
        self.playblast_button = QtWidgets.QPushButton("Create Playblast")
        self.cancel_button = QtWidgets.QPushButton("Cancel")
        
    def create_layouts(self):
        # Output group layout
        output_layout = QtWidgets.QGridLayout()
        output_layout.addWidget(self.output_dir_label, 0, 0)
        output_layout.addWidget(self.output_dir_field, 0, 1)
        output_layout.addWidget(self.output_dir_browse, 0, 2)
        output_layout.addWidget(self.filename_label, 1, 0)
        output_layout.addWidget(self.filename_field, 1, 1, 1, 2)
        self.output_group.setLayout(output_layout)
        
        # Camera group layout
        camera_layout = QtWidgets.QHBoxLayout()
        camera_layout.addWidget(self.camera_label)
        camera_layout.addWidget(self.camera_combo)
        self.camera_group.setLayout(camera_layout)
        
        # Resolution group layout
        resolution_layout = QtWidgets.QGridLayout()
        resolution_layout.addWidget(self.resolution_label, 0, 0)
        resolution_layout.addWidget(self.resolution_combo, 0, 1)
        resolution_layout.addWidget(self.width_label, 1, 0)
        resolution_layout.addWidget(self.width_field, 1, 1)
        resolution_layout.addWidget(self.height_label, 2, 0)
        resolution_layout.addWidget(self.height_field, 2, 1)
        self.resolution_group.setLayout(resolution_layout)
        
        # Frame range group layout
        frame_range_layout = QtWidgets.QGridLayout()
        frame_range_layout.addWidget(self.frame_range_label, 0, 0)
        frame_range_layout.addWidget(self.frame_range_combo, 0, 1)
        frame_range_layout.addWidget(self.start_frame_label, 1, 0)
        frame_range_layout.addWidget(self.start_frame_field, 1, 1)
        frame_range_layout.addWidget(self.end_frame_label, 2, 0)
        frame_range_layout.addWidget(self.end_frame_field, 2, 1)
        self.frame_range_group.setLayout(frame_range_layout)
        
        # Format group layout
        format_layout = QtWidgets.QGridLayout()
        format_layout.addWidget(self.format_label, 0, 0)
        format_layout.addWidget(self.format_combo, 0, 1)
        format_layout.addWidget(self.encoder_label, 1, 0)
        format_layout.addWidget(self.encoder_combo, 1, 1)
        format_layout.addWidget(self.quality_label, 2, 0)
        format_layout.addWidget(self.quality_combo, 2, 1)
        self.format_group.setLayout(format_layout)
        
        # Shot mask group layout
        shot_mask_layout = QtWidgets.QGridLayout()
        shot_mask_layout.addWidget(self.shot_mask_checkbox, 0, 0, 1, 2)
        shot_mask_layout.addWidget(self.topLeftLabel, 1, 0)
        shot_mask_layout.addWidget(self.topLeftLineEdit, 1, 1)
        shot_mask_layout.addWidget(self.topCenterLabel, 2, 0)
        shot_mask_layout.addWidget(self.topCenterLineEdit, 2, 1)
        shot_mask_layout.addWidget(self.topRightLabel, 3, 0)
        shot_mask_layout.addWidget(self.topRightLineEdit, 3, 1)
        shot_mask_layout.addWidget(self.bottomLeftLabel, 4, 0)
        shot_mask_layout.addWidget(self.bottomLeftLineEdit, 4, 1)
        shot_mask_layout.addWidget(self.bottomCenterLabel, 5, 0)
        shot_mask_layout.addWidget(self.bottomCenterLineEdit, 5, 1)
        shot_mask_layout.addWidget(self.bottomRightLabel, 6, 0)
        shot_mask_layout.addWidget(self.bottomRightLineEdit, 6, 1)
        self.shot_mask_group.setLayout(shot_mask_layout)
        
        # Options group layout
        options_layout = QtWidgets.QVBoxLayout()
        options_layout.addWidget(self.show_in_viewer_checkbox)
        options_layout.addWidget(self.overwrite_checkbox)
        self.options_group.setLayout(options_layout)
        
        # Button layout
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addWidget(self.reset_button)
        button_layout.addStretch()
        button_layout.addWidget(self.playblast_button)
        button_layout.addWidget(self.cancel_button)
        
        # Add everything to main layout
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.addWidget(self.output_group)
        main_layout.addWidget(self.camera_group)
        main_layout.addWidget(self.resolution_group)
        main_layout.addWidget(self.frame_range_group)
        main_layout.addWidget(self.format_group)
        main_layout.addWidget(self.shot_mask_group)
        main_layout.addWidget(self.options_group)
        main_layout.addLayout(button_layout)
    
    def create_connections(self):
        # Connect signals and slots
        self.output_dir_browse.clicked.connect(self.browse_output_dir)
        self.camera_combo.currentTextChanged.connect(self.on_camera_changed)
        self.resolution_combo.currentTextChanged.connect(self.on_resolution_changed)
        self.frame_range_combo.currentTextChanged.connect(self.on_frame_range_changed)
        self.format_combo.currentTextChanged.connect(self.on_format_changed)
        self.encoder_combo.currentTextChanged.connect(self.on_encoder_changed)
        
        self.shot_mask_checkbox.toggled.connect(self.on_shot_mask_toggled)
        
        self.reset_button.clicked.connect(self.reset_settings)
        self.playblast_button.clicked.connect(self.create_playblast)
        self.cancel_button.clicked.connect(self.close)
    
    def update_ui(self):
        # Populate camera combobox
        self.camera_combo.clear()
        self.camera_combo.addItem(presets.DEFAULT_CAMERA)
        for camera in cmds.listCameras():
            self.camera_combo.addItem(camera)
        
        # Set initial frame range
        self.on_frame_range_changed(self.frame_range_combo.currentText())
        
        # Set initial resolution
        self.on_resolution_changed(self.resolution_combo.currentText())
        
        # Set initial format and encoder options
        self.on_format_changed(self.format_combo.currentText())
    
    def browse_output_dir(self):
        directory = QtWidgets.QFileDialog.getExistingDirectory(
            self, 
            "Select Output Directory",
            self.output_dir_field.text() or cmds.workspace(q=True, rootDirectory=True)
        )
        if directory:
            self.output_dir_field.setText(directory)
    
    def on_camera_changed(self, camera_name):
        # Handle camera change
        pass
    
    def on_resolution_changed(self, preset_name):
        # Update resolution fields based on preset
        if preset_name == "Render":
            self.width_field.setValue(cmds.getAttr("defaultResolution.width"))
            self.height_field.setValue(cmds.getAttr("defaultResolution.height"))
        elif preset_name in presets.RESOLUTION_PRESETS:
            dimensions = presets.RESOLUTION_PRESETS.get(preset_name)
            if dimensions:  # Check if not None
                self.width_field.setValue(dimensions[0])
                self.height_field.setValue(dimensions[1])
    
    def on_frame_range_changed(self, preset_name):
        # Update frame range fields based on preset
        if preset_name == "Playback":
            start = cmds.playbackOptions(q=True, minTime=True)
            end = cmds.playbackOptions(q=True, maxTime=True)
        elif preset_name == "Animation":
            start = cmds.playbackOptions(q=True, animationStartTime=True)
            end = cmds.playbackOptions(q=True, animationEndTime=True)
        elif preset_name == "Render":
            start = cmds.getAttr("defaultRenderGlobals.startFrame")
            end = cmds.getAttr("defaultRenderGlobals.endFrame")
        else:  # Camera or Custom
            # Just keep current values
            return
        
        self.start_frame_field.setValue(start)
        self.end_frame_field.setValue(end)
    
    def on_format_changed(self, format_name):
        # Update encoder options based on format
        self.encoder_combo.clear()
        if format_name in presets.VIDEO_ENCODERS:
            self.encoder_combo.addItems(presets.VIDEO_ENCODERS[format_name])
            if presets.VIDEO_ENCODERS[format_name]:
                self.encoder_combo.setCurrentText(presets.VIDEO_ENCODERS[format_name][0])
        
        self.on_encoder_changed(self.encoder_combo.currentText())
    
    def on_encoder_changed(self, encoder_name):
        # Update quality options based on encoder
        self.quality_combo.clear()
        if encoder_name == "h264":
            self.quality_combo.addItems(list(presets.H264_QUALITIES.keys()))
            self.quality_combo.setCurrentText(presets.DEFAULT_H264_QUALITY)
        elif encoder_name == "prores" and hasattr(presets, "PRORES_PROFILES"):
            self.quality_combo.addItems(list(presets.PRORES_PROFILES.keys()))
            self.quality_combo.setCurrentText("ProRes 422 HQ")
        else:  # Image formats
            self.quality_combo.addItem("100")
    
    def on_shot_mask_toggled(self, enabled):
        # Enable/disable shot mask settings
        for widget in [
            self.topLeftLabel, self.topLeftLineEdit,
            self.topCenterLabel, self.topCenterLineEdit,
            self.topRightLabel, self.topRightLineEdit,
            self.bottomLeftLabel, self.bottomLeftLineEdit,
            self.bottomCenterLabel, self.bottomCenterLineEdit,
            self.bottomRightLabel, self.bottomRightLineEdit
        ]:
            widget.setEnabled(enabled)
    
    def reset_settings(self):
        # Reset all settings to defaults
        result = QtWidgets.QMessageBox.question(
            self, 
            "Reset Settings", 
            "Are you sure you want to reset all settings to defaults?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No
        )
        
        if result == QtWidgets.QMessageBox.Yes:
            self.filename_field.setText("{scene}_{camera}")
            self.camera_combo.setCurrentText(presets.DEFAULT_CAMERA)
            self.resolution_combo.setCurrentText(presets.DEFAULT_RESOLUTION)
            self.frame_range_combo.setCurrentText(presets.DEFAULT_FRAME_RANGE)
            self.format_combo.setCurrentText(presets.DEFAULT_OUTPUT_FORMAT)
            
            self.shot_mask_checkbox.setChecked(True)
            self.reset_shot_mask_settings()
            
            self.show_in_viewer_checkbox.setChecked(True)
            self.overwrite_checkbox.setChecked(False)
            
            self.update_ui()
    
    def reset_shot_mask_settings(self):
        """Reset shot mask settings to defaults."""
        # Reset text fields to default values
        self.topLeftLineEdit.setText("Scene: {scene}")
        self.topCenterLineEdit.setText("")
        self.topRightLineEdit.setText("FPS: {fps}")
        self.bottomLeftLineEdit.setText("Artist: {username}")
        self.bottomCenterLineEdit.setText("Date: {date}")
        self.bottomRightLineEdit.setText("Frame: {counter}")
        
        # Update the live shot mask (if one exists)
        self.update_shot_mask()
    
    def update_shot_mask(self):
        """Update the live shot mask if it exists."""
        if not hasattr(utils, "remove_shot_mask"):
            return
            
        if utils.remove_shot_mask():
            # Recreate with new settings if shot mask is enabled
            if self.shot_mask_checkbox.isChecked():
                settings = {
                    "topLeftText": self.topLeftLineEdit.text(),
                    "topCenterText": self.topCenterLineEdit.text(),
                    "topRightText": self.topRightLineEdit.text(),
                    "bottomLeftText": self.bottomLeftLineEdit.text(),
                    "bottomCenterText": self.bottomCenterLineEdit.text(),
                    "bottomRightText": self.bottomRightLineEdit.text()
                }
                
                import conestoga_playblast
                camera = self.camera_combo.currentText()
                if camera == presets.DEFAULT_CAMERA:
                    camera = None  # Use active viewport camera
                
                utils.create_shot_mask(
                    camera=camera,
                    user_name=os.getenv("USER") or os.getenv("USERNAME") or "user"
                )
    
    def create_playblast(self):
        # Get all the configuration options from UI
        import conestoga_playblast
        
        output_dir = self.output_dir_field.text() or os.path.join(cmds.workspace(q=True, rootDirectory=True), "movies")
        filename = self.filename_field.text() or "{scene}_{camera}"
        
        camera = self.camera_combo.currentText()
        if camera == presets.DEFAULT_CAMERA:
            camera = None  # Use active viewport camera
        
        width = self.width_field.value()
        height = self.height_field.value()
        
        start_frame = self.start_frame_field.value()
        end_frame = self.end_frame_field.value()
        
        format_type = self.format_combo.currentText()
        encoder = self.encoder_combo.currentText()
        quality = self.quality_combo.currentText()
        
        shot_mask = self.shot_mask_checkbox.isChecked()
        
        show_in_viewer = self.show_in_viewer_checkbox.isChecked()
        force_overwrite = self.overwrite_checkbox.isChecked()
        
        # Shot mask settings if enabled
        shot_mask_settings = None
        if shot_mask:
            shot_mask_settings = {
                "topLeftText": self.topLeftLineEdit.text(),
                "topCenterText": self.topCenterLineEdit.text(),
                "topRightText": self.topRightLineEdit.text(),
                "bottomLeftText": self.bottomLeftLineEdit.text(), 
                "bottomCenterText": self.bottomCenterLineEdit.text(),
                "bottomRightText": self.bottomRightLineEdit.text()
            }
        
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
                shot_mask_settings=shot_mask_settings,
                show_in_viewer=show_in_viewer,
                force_overwrite=force_overwrite
            )
            
            if result:
                QtWidgets.QMessageBox.information(
                    self,
                    "Playblast Complete",
                    f"Playblast created successfully:\n{result}"
                )
                self.close()
            else:
                QtWidgets.QMessageBox.warning(
                    self,
                    "Playblast Failed",
                    "Failed to create playblast. See script editor for details."
                )
        except Exception as e:
            import traceback
            traceback.print_exc()
            QtWidgets.QMessageBox.critical(
                self,
                "Error",
                f"An error occurred:\n{str(e)}"
            )

# Function to show the playblast dialog
def show_playblast_dialog():
    """
    Show the main playblast dialog.
    
    Returns:
        PlayblastDialog: Instance of the dialog
    """
    # Get Maya main window as parent
    try:
        parent = utils.get_maya_main_window()
    except:
        parent = None
    
    # Create and show dialog
    dialog = PlayblastDialog(parent)
    dialog.show()
    
    # Return dialog instance
    return dialog