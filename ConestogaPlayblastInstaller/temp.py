import os
import sys
import time
import maya.cmds as cmds
import maya.mel as mel
import maya.OpenMayaUI as omui
from PySide6 import QtWidgets, QtCore, QtGui
from shiboken6 import wrapInstance
import traceback

# Import required Zurbrigg modules (from your existing implementation)
from zurbrigg_advanced_playblast_ui import ZurbriggLineEdit, ZurbriggColorButton, ZurbriggFormLayout

class ConestoggZurbriggPlayblastDialog(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(ConestoggZurbriggPlayblastDialog, self).__init__(parent)
        self.setWindowTitle("Conestoga Playblast Tool v2.0")
        self.setMinimumWidth(600)
        self.setWindowFlags(QtCore.Qt.Window)
        
        # Store state
        self.shot_mask_data = None  # Store shot mask nodes if created
        
        # Create main layout and tabs
        self.main_layout = QtWidgets.QVBoxLayout(self)
        
        # Create tabs
        self.main_tab_wdg = QtWidgets.QTabWidget()
        self.playblast_tab = QtWidgets.QWidget()
        self.shot_mask_tab = QtWidgets.QWidget()
        self.settings_tab = QtWidgets.QWidget()
        
        # Add tabs to tab widget
        self.main_tab_wdg.addTab(self.playblast_tab, "Playblast")
        self.main_tab_wdg.addTab(self.shot_mask_tab, "Shot Mask")
        self.main_tab_wdg.addTab(self.settings_tab, "Settings")
        
        # Add tab widget to main layout
        self.main_layout.addWidget(self.main_tab_wdg)
        
        # Setup each tab's content
        self.setup_playblast_tab()
        self.setup_shot_mask_tab()
        self.setup_settings_tab()
        
        # Setup connections
        self.create_connections()
        
        # Initialize UI with default values
        self.refresh_cameras()
        self.refresh_resolution()
        self.refresh_frame_range()
        self.refresh_encoders()
        self.update_filename_preview()

    def setup_playblast_tab(self):
        # Create layout for the tab
        playblast_layout = QtWidgets.QVBoxLayout(self.playblast_tab)
        
        # Output settings group
        output_group = QtWidgets.QGroupBox("Output Settings")
        output_layout = QtWidgets.QGridLayout(output_group)
        
        # Output directory
        self.output_dir_label = QtWidgets.QLabel("Output Directory:")
        self.output_dir_le = ZurbriggLineEdit(ZurbriggLineEdit.TYPE_PLAYBLAST_OUTPUT_PATH)
        self.output_dir_le.setPlaceholderText("{project}/movies")
        self.output_dir_select_btn = QtWidgets.QPushButton("...")
        self.output_dir_show_folder_btn = QtWidgets.QPushButton("Open")
        
        # Output filename
        self.output_filename_label = QtWidgets.QLabel("Filename:")
        self.output_filename_le = ZurbriggLineEdit(ZurbriggLineEdit.TYPE_PLAYBLAST_OUTPUT_FILENAME)
        self.output_filename_le.setPlaceholderText("{scene}_{timestamp}")
        self.force_overwrite_cb = QtWidgets.QCheckBox("Force overwrite")
        
        # Add to layout
        output_layout.addWidget(self.output_dir_label, 0, 0)
        output_layout.addWidget(self.output_dir_le, 0, 1)
        output_layout.addWidget(self.output_dir_select_btn, 0, 2)
        output_layout.addWidget(self.output_dir_show_folder_btn, 0, 3)
        output_layout.addWidget(self.output_filename_label, 1, 0)
        output_layout.addWidget(self.output_filename_le, 1, 1, 1, 2)
        output_layout.addWidget(self.force_overwrite_cb, 1, 3)
        
        # Add output group to main layout
        playblast_layout.addWidget(output_group)
        
        # Add the output name generator (Conestoga feature)
        self.setup_output_name_generator()
        playblast_layout.addWidget(self.output_name_generator_group)
        
        # Camera settings
        camera_group = QtWidgets.QGroupBox("Camera")
        camera_layout = QtWidgets.QHBoxLayout(camera_group)
        
        self.camera_label = QtWidgets.QLabel("Camera:")
        self.camera_combo = QtWidgets.QComboBox()
        self.camera_hide_defaults_cb = QtWidgets.QCheckBox("Hide defaults")
        
        camera_layout.addWidget(self.camera_label)
        camera_layout.addWidget(self.camera_combo)
        camera_layout.addWidget(self.camera_hide_defaults_cb)
        camera_layout.addStretch()
        
        playblast_layout.addWidget(camera_group)
        
        # Resolution settings
        resolution_group = QtWidgets.QGroupBox("Resolution")
        resolution_layout = QtWidgets.QGridLayout(resolution_group)
        
        self.resolution_label = QtWidgets.QLabel("Preset:")
        self.resolution_combo = QtWidgets.QComboBox()
        self.resolution_combo.addItems(["Render", "HD 720", "HD 1080", "UHD 4K", "Cinematic 2K", "Custom"])
        self.width_label = QtWidgets.QLabel("Width:")
        self.width_spinbox = QtWidgets.QSpinBox()
        self.height_label = QtWidgets.QLabel("Height:")
        self.height_spinbox = QtWidgets.QSpinBox()
        
        # Configure spinboxes
        self.width_spinbox.setRange(1, 9999)
        self.width_spinbox.setValue(1920)
        self.height_spinbox.setRange(1, 9999)
        self.height_spinbox.setValue(1080)
        
        resolution_layout.addWidget(self.resolution_label, 0, 0)
        resolution_layout.addWidget(self.resolution_combo, 0, 1)
        resolution_layout.addWidget(self.width_label, 1, 0)
        resolution_layout.addWidget(self.width_spinbox, 1, 1)
        resolution_layout.addWidget(self.height_label, 2, 0)
        resolution_layout.addWidget(self.height_spinbox, 2, 1)
        
        playblast_layout.addWidget(resolution_group)
        
        # Frame range settings
        frame_range_group = QtWidgets.QGroupBox("Frame Range")
        frame_range_layout = QtWidgets.QGridLayout(frame_range_group)
        
        self.frame_range_label = QtWidgets.QLabel("Preset:")
        self.frame_range_combo = QtWidgets.QComboBox()
        self.frame_range_combo.addItems(["Playback", "Animation", "Render", "Camera", "Custom"])
        self.start_frame_label = QtWidgets.QLabel("Start:")
        self.start_frame_spinbox = QtWidgets.QSpinBox()
        self.end_frame_label = QtWidgets.QLabel("End:")
        self.end_frame_spinbox = QtWidgets.QSpinBox()
        
        # Configure spinboxes
        self.start_frame_spinbox.setRange(-9999, 9999)
        self.end_frame_spinbox.setRange(-9999, 9999)
        
        frame_range_layout.addWidget(self.frame_range_label, 0, 0)
        frame_range_layout.addWidget(self.frame_range_combo, 0, 1)
        frame_range_layout.addWidget(self.start_frame_label, 1, 0)
        frame_range_layout.addWidget(self.start_frame_spinbox, 1, 1)
        frame_range_layout.addWidget(self.end_frame_label, 2, 0)
        frame_range_layout.addWidget(self.end_frame_spinbox, 2, 1)
        
        playblast_layout.addWidget(frame_range_group)
        
        # Format settings
        format_group = QtWidgets.QGroupBox("Format")
        format_layout = QtWidgets.QGridLayout(format_group)
        
        self.format_label = QtWidgets.QLabel("Format:")
        self.format_combo = QtWidgets.QComboBox()
        self.format_combo.addItems(["mp4", "mov", "Image"])
        self.encoder_label = QtWidgets.QLabel("Encoder:")
        self.encoder_combo = QtWidgets.QComboBox()
        self.quality_label = QtWidgets.QLabel("Quality:")
        self.quality_combo = QtWidgets.QComboBox()
        self.quality_combo.addItems(["Very High", "High", "Medium", "Low"])
        self.encoder_settings_btn = QtWidgets.QPushButton("Settings...")
        
        format_layout.addWidget(self.format_label, 0, 0)
        format_layout.addWidget(self.format_combo, 0, 1)
        format_layout.addWidget(self.encoder_label, 1, 0)
        format_layout.addWidget(self.encoder_combo, 1, 1)
        format_layout.addWidget(self.quality_label, 2, 0)
        format_layout.addWidget(self.quality_combo, 2, 1)
        format_layout.addWidget(self.encoder_settings_btn, 2, 2)
        
        playblast_layout.addWidget(format_group)
        
        # Options
        options_group = QtWidgets.QGroupBox("Options")
        options_layout = QtWidgets.QVBoxLayout(options_group)
        
        self.show_in_viewer_cb = QtWidgets.QCheckBox("Show in Viewer")
        self.show_in_viewer_cb.setChecked(True)
        
        self.shot_mask_enable_cb = QtWidgets.QCheckBox("Enable Shot Mask")
        self.shot_mask_enable_cb.setChecked(True)
        
        self.image_planes_cb = QtWidgets.QCheckBox("Include Image Planes")
        self.image_planes_cb.setChecked(True)
        
        options_layout.addWidget(self.show_in_viewer_cb)
        options_layout.addWidget(self.shot_mask_enable_cb)
        options_layout.addWidget(self.image_planes_cb)
        
        playblast_layout.addWidget(options_group)
        
        # Action buttons
        action_layout = QtWidgets.QHBoxLayout()
        self.reset_btn = QtWidgets.QPushButton("Reset")
        self.playblast_btn = QtWidgets.QPushButton("Create Playblast")
        self.cancel_btn = QtWidgets.QPushButton("Cancel")
        
        action_layout.addWidget(self.reset_btn)
        action_layout.addStretch()
        action_layout.addWidget(self.playblast_btn)
        action_layout.addWidget(self.cancel_btn)
        
        playblast_layout.addLayout(action_layout)

    def setup_output_name_generator(self):
        # Create a frame for the output name generator
        self.output_name_generator_group = QtWidgets.QGroupBox("Output Name Generator")
        filename_layout = QtWidgets.QVBoxLayout(self.output_name_generator_group)
        
        # Create input controls layout
        input_layout = QtWidgets.QHBoxLayout()
        
        # Assignment field
        assignment_layout = QtWidgets.QHBoxLayout()
        assignment_label = QtWidgets.QLabel("A")
        self.assignment_spinbox = QtWidgets.QSpinBox()
        self.assignment_spinbox.setRange(1, 99)
        self.assignment_spinbox.setValue(1)
        self.assignment_spinbox.setFixedWidth(50)
        assignment_layout.addWidget(assignment_label)
        assignment_layout.addWidget(self.assignment_spinbox)
        
        # Last Name field
        lastname_layout = QtWidgets.QHBoxLayout()
        lastname_label = QtWidgets.QLabel("Last Name:")
        self.lastname_le = QtWidgets.QLineEdit()
        self.lastname_le.setPlaceholderText("Last Name")
        lastname_layout.addWidget(lastname_label)
        lastname_layout.addWidget(self.lastname_le)
        
        # First Name field
        firstname_layout = QtWidgets.QHBoxLayout()
        firstname_label = QtWidgets.QLabel("First Name:")
        self.firstname_le = QtWidgets.QLineEdit()
        self.firstname_le.setPlaceholderText("First Name")
        firstname_layout.addWidget(firstname_label)
        firstname_layout.addWidget(self.firstname_le)
        
        # Version type dropdown
        version_type_layout = QtWidgets.QHBoxLayout()
        version_type_label = QtWidgets.QLabel("Type:")
        self.version_type_combo = QtWidgets.QComboBox()
        self.version_type_combo.addItems(["wip", "final"])
        version_type_layout.addWidget(version_type_label)
        version_type_layout.addWidget(self.version_type_combo)
        
        # Version number
        version_number_layout = QtWidgets.QHBoxLayout()
        version_number_label = QtWidgets.QLabel("Version:")
        self.version_number_spinbox = QtWidgets.QSpinBox()
        self.version_number_spinbox.setRange(1, 99)
        self.version_number_spinbox.setValue(1)
        self.version_number_spinbox.setFixedWidth(50)
        version_number_layout.addWidget(version_number_label)
        version_number_layout.addWidget(self.version_number_spinbox)
        
        # Add all controls to the input layout
        input_layout.addLayout(assignment_layout)
        input_layout.addLayout(lastname_layout)
        input_layout.addLayout(firstname_layout)
        input_layout.addLayout(version_type_layout)
        input_layout.addLayout(version_number_layout)
        
        # Preview field
        preview_layout = QtWidgets.QHBoxLayout()
        preview_label = QtWidgets.QLabel("Preview:")
        self.filename_preview_label = QtWidgets.QLabel("A1_LastName_FirstName_wip_01.mov")
        self.filename_preview_label.setStyleSheet("color: yellow; font-weight: bold;")
        preview_layout.addWidget(preview_label)
        preview_layout.addWidget(self.filename_preview_label)
        
        # Generate button
        generate_layout = QtWidgets.QHBoxLayout()
        self.generate_filename_btn = QtWidgets.QPushButton("Generate Filename")
        generate_layout.addWidget(self.generate_filename_btn)
        
        # Add layouts to the main layout
        filename_layout.addLayout(input_layout)
        filename_layout.addLayout(preview_layout)
        filename_layout.addLayout(generate_layout)

    def setup_shot_mask_tab(self):
        # Create layout for the tab
        shot_mask_layout = QtWidgets.QVBoxLayout(self.shot_mask_tab)
        
        # Shot Mask Text Fields
        shot_mask_text_group = QtWidgets.QGroupBox("Shot Mask Text")
        shot_mask_text_layout = QtWidgets.QGridLayout(shot_mask_text_group)
        
        # Top Labels
        self.top_left_label = QtWidgets.QLabel("Top Left:")
        self.top_left_le = ZurbriggLineEdit(ZurbriggLineEdit.TYPE_SHOT_MASK_LABEL)
        self.top_left_le.setText("Scene: {scene}")
        
        self.top_center_label = QtWidgets.QLabel("Top Center:")
        self.top_center_le = ZurbriggLineEdit(ZurbriggLineEdit.TYPE_SHOT_MASK_LABEL)
        self.top_center_le.setText("")
        
        self.top_right_label = QtWidgets.QLabel("Top Right:")
        self.top_right_le = ZurbriggLineEdit(ZurbriggLineEdit.TYPE_SHOT_MASK_LABEL)
        self.top_right_le.setText("FPS: {fps}")
        
        # Bottom Labels
        self.bottom_left_label = QtWidgets.QLabel("Bottom Left:")
        self.bottom_left_le = ZurbriggLineEdit(ZurbriggLineEdit.TYPE_SHOT_MASK_LABEL)
        self.bottom_left_le.setText("Artist: {username}")
        
        self.bottom_center_label = QtWidgets.QLabel("Bottom Center:")
        self.bottom_center_le = ZurbriggLineEdit(ZurbriggLineEdit.TYPE_SHOT_MASK_LABEL)
        self.bottom_center_le.setText("Date: {date}")
        
        self.bottom_right_label = QtWidgets.QLabel("Bottom Right:")
        self.bottom_right_le = ZurbriggLineEdit(ZurbriggLineEdit.TYPE_SHOT_MASK_LABEL)
        self.bottom_right_le.setText("Frame: {counter}")
        
        # Add to layout
        shot_mask_text_layout.addWidget(self.top_left_label, 0, 0)
        shot_mask_text_layout.addWidget(self.top_left_le, 0, 1)
        shot_mask_text_layout.addWidget(self.top_center_label, 1, 0)
        shot_mask_text_layout.addWidget(self.top_center_le, 1, 1)
        shot_mask_text_layout.addWidget(self.top_right_label, 2, 0)
        shot_mask_text_layout.addWidget(self.top_right_le, 2, 1)
        shot_mask_text_layout.addWidget(self.bottom_left_label, 3, 0)
        shot_mask_text_layout.addWidget(self.bottom_left_le, 3, 1)
        shot_mask_text_layout.addWidget(self.bottom_center_label, 4, 0)
        shot_mask_text_layout.addWidget(self.bottom_center_le, 4, 1)
        shot_mask_text_layout.addWidget(self.bottom_right_label, 5, 0)
        shot_mask_text_layout.addWidget(self.bottom_right_le, 5, 1)
        
        shot_mask_layout.addWidget(shot_mask_text_group)
        
        # Border options
        border_options_group = QtWidgets.QGroupBox("Border Options")
        border_options_layout = QtWidgets.QGridLayout(border_options_group)
        
        self.top_border_cb = QtWidgets.QCheckBox("Top Border")
        self.top_border_cb.setChecked(True)
        self.bottom_border_cb = QtWidgets.QCheckBox("Bottom Border")
        self.bottom_border_cb.setChecked(True)
        
        self.border_color_label = QtWidgets.QLabel("Border Color:")
        self.border_color_btn = ZurbriggColorButton((0.0, 0.0, 0.0))
        
        self.border_scale_label = QtWidgets.QLabel("Border Scale:")
        self.border_scale_spinbox = QtWidgets.QDoubleSpinBox()
        self.border_scale_spinbox.setRange(0.5, 5.0)
        self.border_scale_spinbox.setSingleStep(0.1)
        self.border_scale_spinbox.setValue(1.0)
        
        self.aspect_ratio_borders_cb = QtWidgets.QCheckBox("Aspect Ratio Borders")
        self.aspect_ratio_spinbox = QtWidgets.QDoubleSpinBox()
        self.aspect_ratio_spinbox.setRange(0.1, 10.0)
        self.aspect_ratio_spinbox.setSingleStep(0.05)
        self.aspect_ratio_spinbox.setValue(2.35)
        
        border_options_layout.addWidget(self.top_border_cb, 0, 0)
        border_options_layout.addWidget(self.bottom_border_cb, 0, 1)
        border_options_layout.addWidget(self.border_color_label, 1, 0)
        border_options_layout.addWidget(self.border_color_btn, 1, 1)
        border_options_layout.addWidget(self.border_scale_label, 2, 0)
        border_options_layout.addWidget(self.border_scale_spinbox, 2, 1)
        border_options_layout.addWidget(self.aspect_ratio_borders_cb, 3, 0)
        border_options_layout.addWidget(self.aspect_ratio_spinbox, 3, 1)
        
        shot_mask_layout.addWidget(border_options_group)
        
        # Position controls (from Conestoga UI)
        position_group = QtWidgets.QGroupBox("Position Controls")
        position_layout = QtWidgets.QGridLayout(position_group)
        
        self.vert_pos_label = QtWidgets.QLabel("Vertical Position:")
        self.vert_pos_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.vert_pos_slider.setRange(-200, 200)
        self.vert_pos_slider.setValue(-190)
        self.vert_pos_spinbox = QtWidgets.QDoubleSpinBox()
        self.vert_pos_spinbox.setRange(-0.2, 0.2)
        self.vert_pos_spinbox.setSingleStep(0.01)
        self.vert_pos_spinbox.setValue(-0.19)
        
        self.z_dist_label = QtWidgets.QLabel("Z Distance:")
        self.z_dist_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.z_dist_slider.setRange(-1000, -100)
        self.z_dist_slider.setValue(-790)
        self.z_dist_spinbox = QtWidgets.QDoubleSpinBox()
        self.z_dist_spinbox.setRange(-1.0, -0.1)
        self.z_dist_spinbox.setSingleStep(0.05)
        self.z_dist_spinbox.setValue(-0.79)
        
        # Add annotation size controls
        self.ann_size_label = QtWidgets.QLabel("Annotation Size:")
        self.ann_size_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.ann_size_slider.setRange(10, 100)
        self.ann_size_slider.setValue(20)
        self.ann_size_spinbox = QtWidgets.QDoubleSpinBox()
        self.ann_size_spinbox.setRange(1.0, 10.0)
        self.ann_size_spinbox.setSingleStep(0.1)
        self.ann_size_spinbox.setValue(2.0)
        
        position_layout.addWidget(self.vert_pos_label, 0, 0)
        position_layout.addWidget(self.vert_pos_slider, 0, 1)
        position_layout.addWidget(self.vert_pos_spinbox, 0, 2)
        position_layout.addWidget(self.z_dist_label, 1, 0)
        position_layout.addWidget(self.z_dist_slider, 1, 1)
        position_layout.addWidget(self.z_dist_spinbox, 1, 2)
        position_layout.addWidget(self.ann_size_label, 2, 0)
        position_layout.addWidget(self.ann_size_slider, 2, 1)
        position_layout.addWidget(self.ann_size_spinbox, 2, 2)
        
        shot_mask_layout.addWidget(position_group)
        
        # Create and test shot mask buttons
        mask_buttons_layout = QtWidgets.QHBoxLayout()
        self.create_mask_btn = QtWidgets.QPushButton("Create Shot Mask")
        self.remove_mask_btn = QtWidgets.QPushButton("Remove Shot Mask")
        
        mask_buttons_layout.addWidget(self.create_mask_btn)
        mask_buttons_layout.addWidget(self.remove_mask_btn)
        
        shot_mask_layout.addLayout(mask_buttons_layout)

    def setup_settings_tab(self):
        # Create layout for the tab
        settings_layout = QtWidgets.QVBoxLayout(self.settings_tab)
        
        # FFmpeg Settings
        ffmpeg_group = QtWidgets.QGroupBox("FFmpeg Settings")
        ffmpeg_layout = QtWidgets.QGridLayout(ffmpeg_group)
        
        self.ffmpeg_path_label = QtWidgets.QLabel("FFmpeg Path:")
        self.ffmpeg_path_le = QtWidgets.QLineEdit()
        self.ffmpeg_path_select_btn = QtWidgets.QPushButton("...")
        
        ffmpeg_layout.addWidget(self.ffmpeg_path_label, 0, 0)
        ffmpeg_layout.addWidget(self.ffmpeg_path_le, 0, 1)
        ffmpeg_layout.addWidget(self.ffmpeg_path_select_btn, 0, 2)
        
        settings_layout.addWidget(ffmpeg_group)
        
        # Temp Directory Settings
        temp_dir_group = QtWidgets.QGroupBox("Temporary Directory")
        temp_dir_layout = QtWidgets.QGridLayout(temp_dir_group)
        
        self.temp_dir_label = QtWidgets.QLabel("Temp Directory:")
        self.temp_dir_le = QtWidgets.QLineEdit()
        self.temp_dir_select_btn = QtWidgets.QPushButton("...")
        
        self.temp_file_format_label = QtWidgets.QLabel("Temp File Format:")
        self.temp_file_format_combo = QtWidgets.QComboBox()
        self.temp_file_format_combo.addItems(["movie", "png", "tga", "tif"])
        
        temp_dir_layout.addWidget(self.temp_dir_label, 0, 0)
        temp_dir_layout.addWidget(self.temp_dir_le, 0, 1)
        temp_dir_layout.addWidget(self.temp_dir_select_btn, 0, 2)
        temp_dir_layout.addWidget(self.temp_file_format_label, 1, 0)
        temp_dir_layout.addWidget(self.temp_file_format_combo, 1, 1)
        
        settings_layout.addWidget(temp_dir_group)
        
        # Logo Settings
        logo_group = QtWidgets.QGroupBox("Logo Settings")
        logo_layout = QtWidgets.QGridLayout(logo_group)
        
        self.logo_path_label = QtWidgets.QLabel("Logo Path:")
        self.logo_path_le = QtWidgets.QLineEdit()
        self.logo_path_select_btn = QtWidgets.QPushButton("...")
        
        logo_layout.addWidget(self.logo_path_label, 0, 0)
        logo_layout.addWidget(self.logo_path_le, 0, 1)
        logo_layout.addWidget(self.logo_path_select_btn, 0, 2)
        
        settings_layout.addWidget(logo_group)
        
        # Reset buttons
        reset_layout = QtWidgets.QHBoxLayout()
        self.reset_playblast_btn = QtWidgets.QPushButton("Reset Playblast Settings")
        self.reset_shot_mask_btn = QtWidgets.QPushButton("Reset Shot Mask Settings")
        
        reset_layout.addWidget(self.reset_playblast_btn)
        reset_layout.addWidget(self.reset_shot_mask_btn)
        
        settings_layout.addLayout(reset_layout)
        settings_layout.addStretch()
        
        # About info
        about_group = QtWidgets.QGroupBox("About")
        about_layout = QtWidgets.QVBoxLayout(about_group)
        
        about_text = QtWidgets.QLabel(
            "<h3>Conestoga Playblast Tool v2.0</h3>"
            "<p>Based on Zurbrigg Advanced Playblast</p>"
            "<p>Enhanced for Conestoga College</p>"
        )
        about_text.setOpenExternalLinks(True)
        about_text.setAlignment(QtCore.Qt.AlignCenter)
        
        about_layout.addWidget(about_text)
        settings_layout.addWidget(about_group)

    def create_connections(self):
        # Playblast tab connections
        self.output_dir_select_btn.clicked.connect(self.browse_output_dir)
        self.output_dir_show_folder_btn.clicked.connect(self.open_output_dir)
        
        self.camera_hide_defaults_cb.toggled.connect(self.refresh_cameras)
        
        self.resolution_combo.currentTextChanged.connect(self.on_resolution_changed)
        self.width_spinbox.valueChanged.connect(lambda: self.resolution_combo.setCurrentText("Custom"))
        self.height_spinbox.valueChanged.connect(lambda: self.resolution_combo.setCurrentText("Custom"))
        
        self.frame_range_combo.currentTextChanged.connect(self.on_frame_range_changed)
        self.start_frame_spinbox.valueChanged.connect(lambda: self.frame_range_combo.setCurrentText("Custom"))
        self.end_frame_spinbox.valueChanged.connect(lambda: self.frame_range_combo.setCurrentText("Custom"))
        
        self.format_combo.currentTextChanged.connect(self.on_format_changed)
        self.encoder_settings_btn.clicked.connect(self.show_encoder_settings)
        
        self.reset_btn.clicked.connect(self.reset_playblast_settings)
        self.playblast_btn.clicked.connect(self.do_playblast)
        self.cancel_btn.clicked.connect(self.close)
        
        # Output name generator connections
        self.assignment_spinbox.valueChanged.connect(self.update_filename_preview)
        self.lastname_le.textChanged.connect(self.update_filename_preview)
        self.firstname_le.textChanged.connect(self.update_filename_preview)
        self.version_type_combo.currentTextChanged.connect(self.update_filename_preview)
        self.version_number_spinbox.valueChanged.connect(self.update_filename_preview)
        self.generate_filename_btn.clicked.connect(self.generate_filename)
        
        # Shot mask tab connections
        self.vert_pos_slider.valueChanged.connect(lambda v: self.vert_pos_spinbox.setValue(v / 1000.0))
        self.vert_pos_spinbox.valueChanged.connect(lambda v: self.vert_pos_slider.setValue(int(v * 1000)))
        
        self.z_dist_slider.valueChanged.connect(lambda v: self.z_dist_spinbox.setValue(v / 1000.0))
        self.z_dist_spinbox.valueChanged.connect(lambda v: self.z_dist_slider.setValue(int(v * 1000)))
        
        self.ann_size_slider.valueChanged.connect(lambda v: self.ann_size_spinbox.setValue(v / 10.0))
        self.ann_size_spinbox.valueChanged.connect(lambda v: self.ann_size_slider.setValue(int(v * 10)))
        
        self.aspect_ratio_borders_cb.toggled.connect(self.on_aspect_ratio_borders_toggled)
        
        self.create_mask_btn.clicked.connect(self.create_shot_mask)
        self.remove_mask_btn.clicked.connect(self.remove_shot_mask)
        
        # Settings tab connections
        self.ffmpeg_path_select_btn.clicked.connect(self.browse_ffmpeg_path)
        self.temp_dir_select_btn.clicked.connect(self.browse_temp_dir)
        self.logo_path_select_btn.clicked.connect(self.browse_logo_path)
        
        self.reset_playblast_btn.clicked.connect(self.reset_playblast_settings)
        self.reset_shot_mask_btn.clicked.connect(self.reset_shot_mask_settings)
        
        # Auto-update the user field when first/last name is entered
        self.lastname_le.textChanged.connect(self.update_user_field)
        self.firstname_le.textChanged.connect(self.update_user_field)

    # Utility methods
    def get_maya_main_window():
        """Get Maya's main window as a Qt widget."""
        ptr = omui.MQtUtil.mainWindow()
        return wrapInstance(int(ptr), QtWidgets.QWidget) if ptr else None

    # Implementation methods
    def browse_output_dir(self):
        current_dir = self.output_dir_le.text()
        if not current_dir:
            current_dir = cmds.workspace(query=True, rootDirectory=True)
        
        new_dir = cmds.fileDialog2(fileMode=3, dialogStyle=2, startingDirectory=current_dir)
        if new_dir:
            self.output_dir_le.setText(new_dir[0])

    def open_output_dir(self):
        dir_path = self.output_dir_le.text()
        if not dir_path:
            dir_path = cmds.workspace(query=True, rootDirectory=True) + "/movies"
        
        if os.path.exists(dir_path):
            import webbrowser
            webbrowser.open(os.path.normpath(dir_path))
        else:
            cmds.warning(f"Directory does not exist: {dir_path}")

    def refresh_cameras(self):
        self.camera_combo.clear()
        
        cameras = cmds.listCameras()
        
        if not self.camera_hide_defaults_cb.isChecked():
            self.camera_combo.addItems(cameras)
        else:
            # Filter out default cameras
            default_cameras = ["front", "persp", "side", "top"]
            filtered_cameras = [cam for cam in cameras if cam not in default_cameras]
            self.camera_combo.addItems(filtered_cameras)

    def refresh_resolution(self):
        preset = self.resolution_combo.currentText()
        if preset == "Custom":
            return
        
        try:
            if preset == "Render":
                width = cmds.getAttr("defaultResolution.width")
                height = cmds.getAttr("defaultResolution.height")
            else:
                # Common resolutions
                resolutions = {
                    "HD 720": (1280, 720),
                    "HD 1080": (1920, 1080),
                    "UHD 4K": (3840, 2160),
                    "Cinematic 2K": (2048, 1080)
                }
                width, height = resolutions.get(preset, (1920, 1080))
            
            self.width_spinbox.setValue(width)
            self.height_spinbox.setValue(height)
        except Exception as e:
            cmds.warning(f"Error setting resolution: {str(e)}")

    def refresh_frame_range(self):
        preset = self.frame_range_combo.currentText()
        if preset == "Custom":
            return
        
        try:
            if preset == "Playback":
                start = cmds.playbackOptions(query=True, minTime=True)
                end = cmds.playbackOptions(query=True, maxTime=True)
            elif preset == "Animation":
                start = cmds.playbackOptions(query=True, animationStartTime=True)
                end = cmds.playbackOptions(query=True, animationEndTime=True)
            elif preset == "Render":
                start = cmds.getAttr("defaultRenderGlobals.startFrame")
                end = cmds.getAttr("defaultRenderGlobals.endFrame")
            else:  # Camera or Custom
                return
            
            self.start_frame_spinbox.setValue(int(start))
            self.end_frame_spinbox.setValue(int(end))
        except Exception as e:
            cmds.warning(f"Error setting frame range: {str(e)}")

    def refresh_encoders(self):
        format_name = self.format_combo.currentText()
        self.encoder_combo.clear()
        
        # Video encoder lookup
        video_encoder_lookup = {
            "mov": ["h264"],
            "mp4": ["h264"],
            "Image": ["jpg", "png", "tif"]
        }
        
        if format_name in video_encoder_lookup:
            self.encoder_combo.addItems(video_encoder_lookup[format_name])

    def on_resolution_changed(self, preset):
        self.refresh_resolution()

    def on_frame_range_changed(self, preset):
        self.refresh_frame_range()

    def on_format_changed(self, format_name):
        self.refresh_encoders()

    def update_filename_preview(self):
        assignment = self.assignment_spinbox.value()
        lastname = self.lastname_le.text() or "LastName"
        firstname = self.firstname_le.text() or "FirstName"
        version_type = self.version_type_combo.currentText()
        version_number = str(self.version_number_spinbox.value()).zfill(2)
        
        # Use * for preview but _ for actual filename
        filename = f"A{assignment}*{lastname}*{firstname}*{version_type}*{version_number}.mov"
        self.filename_preview_label.setText(filename)

    def generate_filename(self):
        assignment = self.assignment_spinbox.value()
        lastname = self.lastname_le.text()
        firstname = self.firstname_le.text()
        version_type = self.version_type_combo.currentText()
        version_number = str(self.version_number_spinbox.value()).zfill(2)
        
        if not lastname or not firstname:
            cmds.warning("Please enter both last name and first name.")
            return
        
        # Use underscores for the actual file
        filename = f"A{assignment}_{lastname}_{firstname}_{version_type}_{version_number}.mov"
        self.output_filename_le.setText(filename)
        
        # Also update username in shot mask bottom left if default format is used
        if self.bottom_left_le.text() == "Artist: {username}":
            self.bottom_left_le.setText(f"Artist: {firstname} {lastname}")

    def update_user_field(self):
        """Update the username field in the shot mask tab based on the firstname and lastname fields"""
        firstname = self.firstname_le.text()
        lastname = self.lastname_le.text()
        
        if firstname or lastname:
            full_name = f"{firstname} {lastname}".strip()
            # Update the shot mask text if it uses the default pattern
            if self.bottom_left_le.text().startswith("Artist:"):
                self.bottom_left_le.setText(f"Artist: {full_name}")

    def on_aspect_ratio_borders_toggled(self, enabled):
        # Show/hide the appropriate controls based on aspect ratio borders setting
        self.border_scale_spinbox.setVisible(not enabled)
        self.aspect_ratio_spinbox.setVisible(enabled)

    def show_encoder_settings(self):
        # This would create and show Zurbrigg's encoder settings dialog
        pass

    def create_shot_mask(self):
        """Create or update shot mask with current settings"""
        # This implementation would call the Zurbrigg shot mask creation function
        # But augmented with the additional Conestoga positioning controls
        try:
            # Import from Zurbrigg module or use functions from wip_playblast_script
            from wip_playblast_script_v08 import create_shot_mask, update_shot_mask_position
            
            camera = self.camera_combo.currentText()
            if not camera:
                cmds.warning("Please select a camera")
                return
            
            # Get user name from first/last name fields
            user_name = ""
            if self.lastname_le.text() and self.firstname_le.text():
                user_name = f"{self.firstname_le.text()} {self.lastname_le.text()}"
            else:
                user_name = os.environ.get("USER", "Artist")
            
            # Create the shot mask
            self.shot_mask_data = create_shot_mask(
                camera, 
                user_name,
                annotation_size=self.ann_size_spinbox.value()
            )
            
            # Update position using Conestoga controls
    def update_shot_mask_position(self, y_offset=None, z_distance=None):
        """Update the position of the shot mask using the current control values"""
        if not cmds.objExists("shotMask_MainGroup"):
            return False
        
        if y_offset is not None:
            cmds.setAttr("shotMask_MainGroup.translateY", y_offset)
        
        if z_distance is not None:
            cmds.setAttr("shotMask_MainGroup.translateZ", z_distance)
        
        return True

    def remove_shot_mask(self):
        """Remove the shot mask and clean up nodes"""
        try:
            # Import from Zurbrigg module or use functions from wip_playblast_script
            from wip_playblast_script_v08 import remove_shot_mask
            
            if self.shot_mask_data:
                remove_shot_mask(self.shot_mask_data)
                self.shot_mask_data = None
                cmds.refresh(force=True)
                return True
            
            # If no stored data, try to find and remove by name
            if cmds.objExists("shotMask_MainGroup"):
                cmds.delete("shotMask_MainGroup")
                cmds.refresh(force=True)
                return True
                
            return False
        except Exception as e:
            cmds.warning(f"Error removing shot mask: {str(e)}")
            traceback.print_exc()
            return False

    def do_playblast(self):
        """Create playblast with current settings"""
        try:
            # Get all settings from UI
            output_dir = self.output_dir_le.text()
            if not output_dir:
                output_dir = cmds.workspace(query=True, rootDirectory=True) + "/movies"
                
            filename = self.output_filename_le.text()
            if not filename:
                filename = "{scene}_{camera}"
                
            camera = self.camera_combo.currentText()
            width = self.width_spinbox.value()
            height = self.height_spinbox.value()
            start_frame = self.start_frame_spinbox.value()
            end_frame = self.end_frame_spinbox.value()
            
            format_type = self.format_combo.currentText()
            encoder = self.encoder_combo.currentText()
            quality = self.quality_combo.currentText()
            
            shot_mask = self.shot_mask_enable_cb.isChecked()
            show_in_viewer = self.show_in_viewer_cb.isChecked()
            force_overwrite = self.force_overwrite_cb.isChecked()
            include_image_planes = self.image_planes_cb.isChecked()
            
            # Custom shot mask settings
            shot_mask_settings = None
            if shot_mask:
                shot_mask_settings = {
                    "topLeftText": self.top_left_le.text(),
                    "topCenterText": self.top_center_le.text(),
                    "topRightText": self.top_right_le.text(),
                    "bottomLeftText": self.bottom_left_le.text(),
                    "bottomCenterText": self.bottom_center_le.text(),
                    "bottomRightText": self.bottom_right_le.text()
                }
            
            # Create progress dialog
            progress = QtWidgets.QProgressDialog("Creating playblast...", "Cancel", 0, 100, self)
            progress.setWindowTitle("Playblast Progress")
            progress.setWindowModality(QtCore.Qt.WindowModal)
            progress.setValue(10)
            QtWidgets.QApplication.processEvents()
            
            # Import from main module
            import conestoga_playblast
            
            # Create playblast
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
            
            progress.setValue(100)
            
            if result:
                QtWidgets.QMessageBox.information(self, "Playblast Complete", 
                                             f"Playblast completed successfully!\n\nSaved to:\n{result}")
            else:
                QtWidgets.QMessageBox.warning(self, "Playblast Failed", 
                                         "Failed to create playblast. Check the script editor for details.")
                
            return result
            
        except Exception as e:
            cmds.warning(f"Error creating playblast: {str(e)}")
            traceback.print_exc()
            QtWidgets.QMessageBox.critical(self, "Error", f"An error occurred during playblast:\n{str(e)}")
            return None

    def reset_playblast_settings(self):
        """Reset all playblast settings to defaults"""
        confirmation = QtWidgets.QMessageBox.question(
            self, "Reset Settings", 
            "Are you sure you want to reset all playblast settings to defaults?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No
        )
        
        if confirmation == QtWidgets.QMessageBox.Yes:
            # Reset output path
            self.output_dir_le.setText("")
            self.output_filename_le.setText("")
            self.force_overwrite_cb.setChecked(False)
            
            # Reset camera
            self.camera_hide_defaults_cb.setChecked(False)
            self.refresh_cameras()
            
            # Reset resolution
            self.resolution_combo.setCurrentText("HD 1080")
            
            # Reset frame range
            self.frame_range_combo.setCurrentText("Playback")
            
            # Reset format
            self.format_combo.setCurrentText("mp4")
            self.on_format_changed("mp4")
            self.quality_combo.setCurrentText("High")
            
            # Reset options
            self.show_in_viewer_cb.setChecked(True)
            self.shot_mask_enable_cb.setChecked(True)
            self.image_planes_cb.setChecked(True)
            
            # Reset output name generator
            self.assignment_spinbox.setValue(1)
            self.lastname_le.setText("")
            self.firstname_le.setText("")
            self.version_type_combo.setCurrentText("wip")
            self.version_number_spinbox.setValue(1)
            
            # Refresh UI
            self.update_filename_preview()

    def reset_shot_mask_settings(self):
        """Reset shot mask settings to defaults"""
        confirmation = QtWidgets.QMessageBox.question(
            self, "Reset Shot Mask", 
            "Are you sure you want to reset all shot mask settings to defaults?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No
        )
        
        if confirmation == QtWidgets.QMessageBox.Yes:
            # Reset text fields
            self.top_left_le.setText("Scene: {scene}")
            self.top_center_le.setText("")
            self.top_right_le.setText("FPS: {fps}")
            self.bottom_left_le.setText("Artist: {username}")
            self.bottom_center_le.setText("Date: {date}")
            self.bottom_right_le.setText("Frame: {counter}")
            
            # Reset border options
            self.top_border_cb.setChecked(True)
            self.bottom_border_cb.setChecked(True)
            self.border_color_btn.set_color((0.0, 0.0, 0.0))
            self.border_scale_spinbox.setValue(1.0)
            self.aspect_ratio_borders_cb.setChecked(False)
            self.aspect_ratio_spinbox.setValue(2.35)
            
            # Reset position controls
            self.vert_pos_slider.setValue(-190)
            self.vert_pos_spinbox.setValue(-0.19)
            self.z_dist_slider.setValue(-790)
            self.z_dist_spinbox.setValue(-0.79)
            self.ann_size_slider.setValue(20)
            self.ann_size_spinbox.setValue(2.0)
            
            # Update shot mask if it exists
            if self.shot_mask_data:
                # Recreate with new settings
                self.remove_shot_mask()
                self.create_shot_mask()

    def browse_ffmpeg_path(self):
        """Browse for ffmpeg executable"""
        current_path = self.ffmpeg_path_le.text()
        
        # Default start directory
        if not current_path:
            if os.name == 'nt':  # Windows
                start_dir = "C:/Program Files"
            else:  # macOS, Linux
                start_dir = "/usr/local/bin"
        else:
            start_dir = os.path.dirname(current_path)
        
        file_filter = "All Files (*.*)" if os.name == 'nt' else "All Files (*)"
        new_path = QtWidgets.QFileDialog.getOpenFileName(
            self, "Select FFmpeg Executable", start_dir, file_filter
        )[0]
        
        if new_path:
            self.ffmpeg_path_le.setText(new_path)
            # Also update the ffmpeg path in the plugin
            import conestoga_playblast
            if hasattr(conestoga_playblast, "set_ffmpeg_path"):
                conestoga_playblast.set_ffmpeg_path(new_path)
            else:
                cmds.warning("Could not update ffmpeg path in plugin.")

    def browse_temp_dir(self):
        """Browse for temporary directory"""
        current_dir = self.temp_dir_le.text()
        if not current_dir:
            current_dir = tempfile.gettempdir()
        
        new_dir = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Select Temporary Directory", current_dir
        )
        
        if new_dir:
            self.temp_dir_le.setText(new_dir)
            # Update temp directory in plugin
            import conestoga_playblast
            if hasattr(conestoga_playblast, "set_temp_dir"):
                conestoga_playblast.set_temp_dir(new_dir)
            else:
                cmds.warning("Could not update temp directory in plugin.")

    def browse_logo_path(self):
        """Browse for logo image file"""
        current_path = self.logo_path_le.text()
        if not current_path:
            current_path = cmds.workspace(query=True, rootDirectory=True)
        
        file_filter = "Image Files (*.png *.jpg *.jpeg *.tif *.tiff);;All Files (*.*)"
        new_path = QtWidgets.QFileDialog.getOpenFileName(
            self, "Select Logo Image", current_path, file_filter
        )[0]
        
        if new_path:
            self.logo_path_le.setText(new_path)
            # Update logo path in plugin
            import conestoga_playblast
            if hasattr(conestoga_playblast, "set_logo_path"):
                conestoga_playblast.set_logo_path(new_path)
            else:
                cmds.warning("Could not update logo path in plugin.")


# Show UI function
def show_playblast_dialog():
    """Show the Conestoga-Zurbrigg Playblast Dialog"""
    global playblast_dialog
    
    try:
        # Clean up existing dialog if it exists
        if playblast_dialog:
            playblast_dialog.close()
            playblast_dialog.deleteLater()
    except:
        pass
    
    # Get Maya's main window as parent
    parent = None
    try:
        parent = get_maya_main_window()
    except:
        pass
    
    # Create and show the dialog
    playblast_dialog = ConestoggZurbriggPlayblastDialog(parent)
    playblast_dialog.show()
    
    return playblast_dialog


# Helper function to get Maya's main window
def get_maya_main_window():
    """Get Maya's main window as a Qt widget."""
    ptr = omui.MQtUtil.mainWindow()
    return wrapInstance(int(ptr), QtWidgets.QWidget) if ptr else None


# Global variable to hold the dialog instance
playblast_dialog = None