"""
Conestoga Playblast Tool - UI Module
Implements the user interface for the playblast tool.
"""

import os
import re
import time
import json
import tempfile
import getpass
import platform
import subprocess
import traceback
from functools import partial

import maya.cmds as cmds
import maya.mel as mel
import maya.OpenMayaUI as omui

from PySide6 import QtWidgets, QtCore, QtGui
from shiboken6 import wrapInstance

# Import our modules
from conestoga_playblast_presets import (
    TOOL_NAME, VERSION, MASK_PREFIX, DEFAULT_CAMERA, DEFAULT_RESOLUTION,
    DEFAULT_FRAME_RANGE, DEFAULT_OUTPUT_FORMAT, DEFAULT_ENCODER,
    DEFAULT_H264_QUALITY, DEFAULT_H264_PRESET, DEFAULT_VIEW_PRESET,
    DEFAULT_MASK_SCALE, DEFAULT_COUNTER_PADDING, FRAME_FORMATS,
    MOVIE_FORMATS, OUTPUT_FORMATS, VIDEO_ENCODERS, H264_QUALITIES,
    H264_PRESETS, PRORES_PROFILES, VIEWPORT_VISIBILITY_LOOKUP,
    VIEWPORT_VISIBILITY_PRESETS, RESOLUTION_PRESETS, TAG_PATTERNS
)

from conestoga_playblast_utils import (
    get_maya_main_window, get_ffmpeg_path, is_ffmpeg_available,
    get_frame_rate, save_option_var, load_option_var, get_camera_shape,
    get_valid_model_panel, clean_camera_view, get_viewport_defaults,
    set_viewport_visibility, set_final_viewport, restore_viewport,
    disable_image_planes, restore_image_planes, create_shot_mask,
    parse_shot_mask_text, align_mask_to_camera, update_shot_mask_scale,
    update_shot_mask_position, update_shot_mask_text_color,
    update_shot_mask_opacity, remove_shot_mask, encode_with_ffmpeg
)

# ===========================================================================
# UI CLASSES
# ===========================================================================

class PlayblastDialog(QtWidgets.QDialog):
    """Main dialog for the Conestoga Playblast Tool"""
    
    def __init__(self, parent=get_maya_main_window()):
        super(PlayblastDialog, self).__init__(parent)
        
        self.setWindowTitle(f"{TOOL_NAME} v{VERSION}")
        self.setMinimumWidth(550)
        self.setMinimumHeight(600)
        self.setWindowFlags(QtCore.Qt.Window)
        
        self.shot_mask_data = None
        self.ffmpeg_path = get_ffmpeg_path()
        
        self.setup_ui()
        self.create_connections()
        
        # Initialize UI state
        self.initialize_ui()
        self.load_settings()
        
    def setup_ui(self):
        # Create main layout with tabs
        self.main_layout = QtWidgets.QVBoxLayout(self)
        self.tab_widget = QtWidgets.QTabWidget()
        
        # Create tabs
        self.playblast_tab = QtWidgets.QWidget()
        self.shot_mask_tab = QtWidgets.QWidget()
        self.settings_tab = QtWidgets.QWidget()
        
        # Set up tab layouts
        self.setup_playblast_tab()
        self.setup_shot_mask_tab()
        self.setup_settings_tab()
        
        # Add tabs to tab widget
        self.tab_widget.addTab(self.playblast_tab, "Playblast")
        self.tab_widget.addTab(self.shot_mask_tab, "Shot Mask")
        self.tab_widget.addTab(self.settings_tab, "Settings")
        
        # Add tab widget to main layout
        self.main_layout.addWidget(self.tab_widget)
        
        # Add action buttons at the bottom (visible across all tabs)
        self.setup_action_buttons()
        
    def setup_playblast_tab(self):
        layout = QtWidgets.QVBoxLayout(self.playblast_tab)
        
        # Camera & Audio Group
        cam_audio_group = QtWidgets.QGroupBox("Camera & Audio")
        cam_audio_layout = QtWidgets.QVBoxLayout(cam_audio_group)
        
        # Camera Selection
        camera_layout = QtWidgets.QHBoxLayout()
        camera_label = QtWidgets.QLabel("Camera:")
        self.cameraComboBox = QtWidgets.QComboBox()
        camera_refresh_btn = QtWidgets.QPushButton("↻")
        camera_refresh_btn.setToolTip("Refresh camera list")
        camera_refresh_btn.setMaximumWidth(30)
        camera_layout.addWidget(camera_label)
        camera_layout.addWidget(self.cameraComboBox)
        camera_layout.addWidget(camera_refresh_btn)
        cam_audio_layout.addLayout(camera_layout)
        
        # Audio Selection
        audio_layout = QtWidgets.QHBoxLayout()
        audio_label = QtWidgets.QLabel("Audio:")
        self.audioComboBox = QtWidgets.QComboBox()
        audio_refresh_btn = QtWidgets.QPushButton("↻")
        audio_refresh_btn.setToolTip("Refresh audio list")
        audio_refresh_btn.setMaximumWidth(30)
        audio_layout.addWidget(audio_label)
        audio_layout.addWidget(self.audioComboBox)
        audio_layout.addWidget(audio_refresh_btn)
        cam_audio_layout.addLayout(audio_layout)
        
        layout.addWidget(cam_audio_group)
        
        # Playblast Settings Group
        playblast_settings_group = QtWidgets.QGroupBox("Playblast Settings")
        playblast_settings_layout = QtWidgets.QVBoxLayout(playblast_settings_group)
        
        # Resolution Settings
        res_layout = QtWidgets.QHBoxLayout()
        res_label = QtWidgets.QLabel("Resolution:")
        self.resolutionComboBox = QtWidgets.QComboBox()
        for preset in RESOLUTION_PRESETS:
            self.resolutionComboBox.addItem(preset)
        self.resolutionComboBox.addItem("Custom")
        
        self.widthSpinBox = QtWidgets.QSpinBox()
        self.widthSpinBox.setRange(1, 9999)
        self.widthSpinBox.setValue(1920)
        self.widthSpinBox.setSuffix(" px")
        
        self.heightSpinBox = QtWidgets.QSpinBox()
        self.heightSpinBox.setRange(1, 9999)
        self.heightSpinBox.setValue(1080)
        self.heightSpinBox.setSuffix(" px")
        
        res_layout.addWidget(res_label)
        res_layout.addWidget(self.resolutionComboBox)
        res_layout.addWidget(QtWidgets.QLabel("Width:"))
        res_layout.addWidget(self.widthSpinBox)
        res_layout.addWidget(QtWidgets.QLabel("Height:"))
        res_layout.addWidget(self.heightSpinBox)
        playblast_settings_layout.addLayout(res_layout)
        
        # Frame Range Settings
        frame_layout = QtWidgets.QHBoxLayout()
        frame_label = QtWidgets.QLabel("Frame Range:")
        
        self.frameRangeComboBox = QtWidgets.QComboBox()
        self.frameRangeComboBox.addItems(["Playback", "Animation", "Render", "Camera", "Custom"])
        
        self.startFrameSpinBox = QtWidgets.QSpinBox()
        self.startFrameSpinBox.setRange(-9999, 9999)
        self.startFrameSpinBox.setValue(int(cmds.playbackOptions(query=True, min=True)))
        
        self.endFrameSpinBox = QtWidgets.QSpinBox()
        self.endFrameSpinBox.setRange(-9999, 9999)
        self.endFrameSpinBox.setValue(int(cmds.playbackOptions(query=True, max=True)))
        
        frame_layout.addWidget(frame_label)
        frame_layout.addWidget(self.frameRangeComboBox)
        frame_layout.addWidget(QtWidgets.QLabel("Start:"))
        frame_layout.addWidget(self.startFrameSpinBox)
        frame_layout.addWidget(QtWidgets.QLabel("End:"))
        frame_layout.addWidget(self.endFrameSpinBox)
        playblast_settings_layout.addLayout(frame_layout)
        
        # Encoding Settings
        encoding_layout = QtWidgets.QHBoxLayout()
        encoding_label = QtWidgets.QLabel("Format:")
        
        self.formatComboBox = QtWidgets.QComboBox()
        self.formatComboBox.addItems(OUTPUT_FORMATS)
        
        self.encoderComboBox = QtWidgets.QComboBox()
        
        self.qualityComboBox = QtWidgets.QComboBox()
        self.qualityComboBox.addItems(["Very High", "High", "Medium", "Low"])
        
        encoding_settings_btn = QtWidgets.QPushButton("Settings...")
        encoding_settings_btn.clicked.connect(self.show_encoding_settings)
        
        encoding_layout.addWidget(encoding_label)
        encoding_layout.addWidget(self.formatComboBox)
        encoding_layout.addWidget(QtWidgets.QLabel("Encoder:"))
        encoding_layout.addWidget(self.encoderComboBox)
        encoding_layout.addWidget(QtWidgets.QLabel("Quality:"))
        encoding_layout.addWidget(self.qualityComboBox)
        encoding_layout.addWidget(encoding_settings_btn)
        playblast_settings_layout.addLayout(encoding_layout)
        
        # Viewport Settings
        viewport_layout = QtWidgets.QHBoxLayout()
        viewport_label = QtWidgets.QLabel("Viewport:")
        
        self.viewportComboBox = QtWidgets.QComboBox()
        self.viewportComboBox.addItems(VIEWPORT_VISIBILITY_PRESETS.keys())
        
        viewport_customize_btn = QtWidgets.QPushButton("Customize...")
        viewport_customize_btn.clicked.connect(self.show_viewport_settings)
        
        viewport_layout.addWidget(viewport_label)
        viewport_layout.addWidget(self.viewportComboBox)
        viewport_layout.addWidget(viewport_customize_btn)
        playblast_settings_layout.addLayout(viewport_layout)
        
        # Checkboxes for options
        option_layout = QtWidgets.QGridLayout()
        
        self.saveFileCheckbox = QtWidgets.QCheckBox("Save to Movies Folder")
        self.saveFileCheckbox.setChecked(True)
        
        self.overscanCheckbox = QtWidgets.QCheckBox("Overscan")
        self.ornamentCheckbox = QtWidgets.QCheckBox("Show UI Elements")
        self.imagePlanesCheckbox = QtWidgets.QCheckBox("Include Image Planes")
        self.viewerCheckbox = QtWidgets.QCheckBox("Open in Viewer")
        self.viewerCheckbox.setChecked(True)
        
        self.forceOverwriteCheckbox = QtWidgets.QCheckBox("Force Overwrite")
        
        option_layout.addWidget(self.saveFileCheckbox, 0, 0)
        option_layout.addWidget(self.overscanCheckbox, 0, 1)
        option_layout.addWidget(self.ornamentCheckbox, 0, 2)
        option_layout.addWidget(self.imagePlanesCheckbox, 1, 0)
        option_layout.addWidget(self.viewerCheckbox, 1, 1)
        option_layout.addWidget(self.forceOverwriteCheckbox, 1, 2)
        
        playblast_settings_layout.addLayout(option_layout)
        
        layout.addWidget(playblast_settings_group)
        
        # Output File Group
        file_group = QtWidgets.QGroupBox("Output File")
        file_layout = QtWidgets.QVBoxLayout(file_group)
        
        # Output Directory
        dir_layout = QtWidgets.QHBoxLayout()
        dir_label = QtWidgets.QLabel("Directory:")
        self.outputDirLineEdit = QtWidgets.QLineEdit()
        self.outputDirLineEdit.setPlaceholderText("{project}/movies")
        
        browse_dir_btn = QtWidgets.QPushButton("...")
        browse_dir_btn.setMaximumWidth(30)
        browse_dir_btn.clicked.connect(self.browse_output_directory)
        
        dir_layout.addWidget(dir_label)
        dir_layout.addWidget(self.outputDirLineEdit)
        dir_layout.addWidget(browse_dir_btn)
        file_layout.addLayout(dir_layout)
        
        # Output Filename
        file_name_layout = QtWidgets.QHBoxLayout()
        file_label = QtWidgets.QLabel("Filename:")
        self.filenameLineEdit = QtWidgets.QLineEdit()
        self.filenameLineEdit.setPlaceholderText("{scene}_{camera}")
        
        file_name_layout.addWidget(file_label)
        file_name_layout.addWidget(self.filenameLineEdit)
        file_layout.addLayout(file_name_layout)
        
        # Filename helper tags
        tag_layout = QtWidgets.QHBoxLayout()
        tag_label = QtWidgets.QLabel("Insert Tag:")
        
        self.tagButtonScene = QtWidgets.QPushButton("{scene}")
        self.tagButtonScene.setMaximumWidth(70)
        self.tagButtonScene.clicked.connect(lambda: self.insert_filename_tag("{scene}"))
        
        self.tagButtonCamera = QtWidgets.QPushButton("{camera}")
        self.tagButtonCamera.setMaximumWidth(70)
        self.tagButtonCamera.clicked.connect(lambda: self.insert_filename_tag("{camera}"))
        
        self.tagButtonDate = QtWidgets.QPushButton("{date}")
        self.tagButtonDate.setMaximumWidth(70)
        self.tagButtonDate.clicked.connect(lambda: self.insert_filename_tag("{date}"))
        
        self.tagButtonTime = QtWidgets.QPushButton("{time}")
        self.tagButtonTime.setMaximumWidth(70)
        self.tagButtonTime.clicked.connect(lambda: self.insert_filename_tag("{time}"))
        
        tag_layout.addWidget(tag_label)
        tag_layout.addWidget(self.tagButtonScene)
        tag_layout.addWidget(self.tagButtonCamera)
        tag_layout.addWidget(self.tagButtonDate)
        tag_layout.addWidget(self.tagButtonTime)
        file_layout.addLayout(tag_layout)
        
        layout.addWidget(file_group)
        
        # Add some stretch to push everything up
        layout.addStretch()
    
    def setup_shot_mask_tab(self):
        layout = QtWidgets.QVBoxLayout(self.shot_mask_tab)
        
        # Enable Shot Mask group
        enable_group = QtWidgets.QGroupBox("Shot Mask")
        enable_layout = QtWidgets.QHBoxLayout(enable_group)
        
        self.shotMaskCheckbox = QtWidgets.QCheckBox("Enable Shot Mask")
        self.shotMaskCheckbox.setChecked(True)
        
        artist_label = QtWidgets.QLabel("Artist Name:")
        self.userNameLineEdit = QtWidgets.QLineEdit()
        self.userNameLineEdit.setPlaceholderText("Enter your name")
        
        self.createShotMaskButton = QtWidgets.QPushButton("Create Shot Mask")
        self.createShotMaskButton.setToolTip("Create the shot mask so you can adjust it before playblast")
        
        enable_layout.addWidget(self.shotMaskCheckbox)
        enable_layout.addWidget(artist_label)
        enable_layout.addWidget(self.userNameLineEdit)
        enable_layout.addWidget(self.createShotMaskButton)
        
        layout.addWidget(enable_group)
        
        # Text Content Group
        text_group = QtWidgets.QGroupBox("Text Content")
        text_layout = QtWidgets.QGridLayout(text_group)
        
        # Top Bar Text
        top_left_label = QtWidgets.QLabel("Top Left:")
        self.topLeftLineEdit = QtWidgets.QLineEdit()
        self.topLeftLineEdit.setText("Scene: {scene}")
        
        top_center_label = QtWidgets.QLabel("Top Center:")
        self.topCenterLineEdit = QtWidgets.QLineEdit()
        
        top_right_label = QtWidgets.QLabel("Top Right:")
        self.topRightLineEdit = QtWidgets.QLineEdit()
        self.topRightLineEdit.setText("FPS: {fps}")
        
        # Bottom Bar Text
        bottom_left_label = QtWidgets.QLabel("Bottom Left:")
        self.bottomLeftLineEdit = QtWidgets.QLineEdit()
        self.bottomLeftLineEdit.setText("Artist: {username}")
        
        bottom_center_label = QtWidgets.QLabel("Bottom Center:")
        self.bottomCenterLineEdit = QtWidgets.QLineEdit()
        self.bottomCenterLineEdit.setText("Date: {date}")
        
        bottom_right_label = QtWidgets.QLabel("Bottom Right:")
        self.bottomRightLineEdit = QtWidgets.QLineEdit()
        self.bottomRightLineEdit.setText("Frame: {counter}")
        
        # Add text fields to layout
        text_layout.addWidget(top_left_label, 0, 0)
        text_layout.addWidget(self.topLeftLineEdit, 0, 1, 1, 3)
        text_layout.addWidget(top_center_label, 1, 0)
        text_layout.addWidget(self.topCenterLineEdit, 1, 1, 1, 3)
        text_layout.addWidget(top_right_label, 2, 0)
        text_layout.addWidget(self.topRightLineEdit, 2, 1, 1, 3)
        
        text_layout.addWidget(bottom_left_label, 3, 0)
        text_layout.addWidget(self.bottomLeftLineEdit, 3, 1, 1, 3)
        text_layout.addWidget(bottom_center_label, 4, 0)
        text_layout.addWidget(self.bottomCenterLineEdit, 4, 1, 1, 3)
        text_layout.addWidget(bottom_right_label, 5, 0)
        text_layout.addWidget(self.bottomRightLineEdit, 5, 1, 1, 3)
        
        # Add available tags
        tags_label = QtWidgets.QLabel("Available Tags:")
        text_layout.addWidget(tags_label, 6, 0)
        
        tag_buttons_layout = QtWidgets.QHBoxLayout()
        
        tag_scene_btn = QtWidgets.QPushButton("{scene}")
        tag_scene_btn.setMaximumWidth(70)
        tag_scene_btn.clicked.connect(lambda: self.insert_mask_tag("{scene}"))
        
        tag_camera_btn = QtWidgets.QPushButton("{camera}")
        tag_camera_btn.setMaximumWidth(70)
        tag_camera_btn.clicked.connect(lambda: self.insert_mask_tag("{camera}"))
        
        tag_counter_btn = QtWidgets.QPushButton("{counter}")
        tag_counter_btn.setMaximumWidth(70)
        tag_counter_btn.clicked.connect(lambda: self.insert_mask_tag("{counter}"))
        
        tag_username_btn = QtWidgets.QPushButton("{username}")
        tag_username_btn.setMaximumWidth(80)
        tag_username_btn.clicked.connect(lambda: self.insert_mask_tag("{username}"))
        
        tag_buttons_layout.addWidget(tag_scene_btn)
        tag_buttons_layout.addWidget(tag_camera_btn)
        tag_buttons_layout.addWidget(tag_counter_btn)
        tag_buttons_layout.addWidget(tag_username_btn)
        text_layout.addLayout(tag_buttons_layout, 6, 1, 1, 3)
        
        more_tag_buttons_layout = QtWidgets.QHBoxLayout()
        
        tag_date_btn = QtWidgets.QPushButton("{date}")
        tag_date_btn.setMaximumWidth(70)
        tag_date_btn.clicked.connect(lambda: self.insert_mask_tag("{date}"))
        
        tag_time_btn = QtWidgets.QPushButton("{time}")
        tag_time_btn.setMaximumWidth(70)
        tag_time_btn.clicked.connect(lambda: self.insert_mask_tag("{time}"))
        
        tag_focal_btn = QtWidgets.QPushButton("{focal_length}")
        tag_focal_btn.setMaximumWidth(90)
        tag_focal_btn.clicked.connect(lambda: self.insert_mask_tag("{focal_length}"))
        
        more_tag_buttons_layout.addWidget(tag_date_btn)
        more_tag_buttons_layout.addWidget(tag_time_btn)
        more_tag_buttons_layout.addWidget(tag_focal_btn)
        more_tag_buttons_layout.addStretch()
        text_layout.addLayout(more_tag_buttons_layout, 7, 1, 1, 3)
        
        layout.addWidget(text_group)
        
        # Appearance Group
        appearance_group = QtWidgets.QGroupBox("Appearance")
        appearance_layout = QtWidgets.QVBoxLayout(appearance_group)
        
        # Text Color
        text_color_layout = QtWidgets.QHBoxLayout()
        text_color_label = QtWidgets.QLabel("Text Color:")
        self.textColorButton = QtWidgets.QPushButton()
        self.textColorButton.setFixedWidth(50)
        self.textColorButton.setStyleSheet("background-color: rgb(255, 255, 255);")
        self.textColorButton.clicked.connect(self.select_text_color)
        
        text_color_layout.addWidget(text_color_label)
        text_color_layout.addWidget(self.textColorButton)
        text_color_layout.addStretch()
        appearance_layout.addLayout(text_color_layout)
        
        # Bar Color
        bar_color_layout = QtWidgets.QHBoxLayout()
        bar_color_label = QtWidgets.QLabel("Bar Color:")
        self.barColorButton = QtWidgets.QPushButton()
        self.barColorButton.setFixedWidth(50)
        self.barColorButton.setStyleSheet("background-color: rgb(38, 38, 38);")
        self.barColorButton.clicked.connect(self.select_bar_color)
        
        bar_color_layout.addWidget(bar_color_label)
        bar_color_layout.addWidget(self.barColorButton)
        bar_color_layout.addStretch()
        appearance_layout.addLayout(bar_color_layout)
        
        # Scale slider
        scale_layout = QtWidgets.QHBoxLayout()
        scale_label = QtWidgets.QLabel("Scale:")
        self.maskScaleSlider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.maskScaleSlider.setRange(10, 100)  # Range from 0.1 to 1.0
        self.maskScaleSlider.setValue(25)  # Default to 0.25
        
        self.maskScaleSpinBox = QtWidgets.QDoubleSpinBox()
        self.maskScaleSpinBox.setRange(0.1, 1.0)
        self.maskScaleSpinBox.setSingleStep(0.05)
        self.maskScaleSpinBox.setValue(0.25)
        self.maskScaleSpinBox.setFixedWidth(70)
        
        self.maskScaleSlider.valueChanged.connect(lambda v: self.maskScaleSpinBox.setValue(v / 100.0))
        self.maskScaleSpinBox.valueChanged.connect(lambda v: self.maskScaleSlider.setValue(int(v * 100)))
        
        scale_layout.addWidget(scale_label)
        scale_layout.addWidget(self.maskScaleSlider)
        scale_layout.addWidget(self.maskScaleSpinBox)
        appearance_layout.addLayout(scale_layout)
        
        # Opacity slider
        opacity_layout = QtWidgets.QHBoxLayout()
        opacity_label = QtWidgets.QLabel("Opacity:")
        self.opacitySlider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.opacitySlider.setRange(0, 100)
        self.opacitySlider.setValue(100)
        
        self.opacitySpinBox = QtWidgets.QDoubleSpinBox()
        self.opacitySpinBox.setRange(0.0, 1.0)
        self.opacitySpinBox.setSingleStep(0.1)
        self.opacitySpinBox.setValue(1.0)
        self.opacitySpinBox.setFixedWidth(70)
        
        self.opacitySlider.valueChanged.connect(lambda v: self.opacitySpinBox.setValue(v / 100.0))
        self.opacitySpinBox.valueChanged.connect(lambda v: self.opacitySlider.setValue(int(v * 100)))
        
        opacity_layout.addWidget(opacity_label)
        opacity_layout.addWidget(self.opacitySlider)
        opacity_layout.addWidget(self.opacitySpinBox)
        appearance_layout.addLayout(opacity_layout)
        
        # Border visibility
        border_layout = QtWidgets.QHBoxLayout()
        border_label = QtWidgets.QLabel("Borders:")
        self.topBorderCheckbox = QtWidgets.QCheckBox("Top")
        self.topBorderCheckbox.setChecked(True)
        self.bottomBorderCheckbox = QtWidgets.QCheckBox("Bottom")
        self.bottomBorderCheckbox.setChecked(True)
        
        border_layout.addWidget(border_label)
        border_layout.addWidget(self.topBorderCheckbox)
        border_layout.addWidget(self.bottomBorderCheckbox)
        border_layout.addStretch()
        appearance_layout.addLayout(border_layout)
        
        # Counter padding
        counter_layout = QtWidgets.QHBoxLayout()
        counter_label = QtWidgets.QLabel("Frame Counter Padding:")
        self.counterPaddingSpinBox = QtWidgets.QSpinBox()
        self.counterPaddingSpinBox.setRange(1, 6)
        self.counterPaddingSpinBox.setValue(4)
        
        counter_layout.addWidget(counter_label)
        counter_layout.addWidget(self.counterPaddingSpinBox)
        counter_layout.addStretch()
        appearance_layout.addLayout(counter_layout)
        
        layout.addWidget(appearance_group)
        
        # Position Group
        position_group = QtWidgets.QGroupBox("Position")
        position_layout = QtWidgets.QVBoxLayout(position_group)
        
        # Y Position (Vertical)
        vert_pos_layout = QtWidgets.QHBoxLayout()
        vert_pos_label = QtWidgets.QLabel("Vertical Position:")
        self.vertPosSlider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.vertPosSlider.setRange(-100, 100)
        self.vertPosSlider.setValue(0)
        
        self.vertPosSpinBox = QtWidgets.QDoubleSpinBox()
        self.vertPosSpinBox.setRange(-0.1, 0.1)
        self.vertPosSpinBox.setSingleStep(0.01)
        self.vertPosSpinBox.setValue(0.0)
        self.vertPosSpinBox.setFixedWidth(70)
        
        self.vertPosSlider.valueChanged.connect(lambda v: self.vertPosSpinBox.setValue(v / 1000.0))
        self.vertPosSpinBox.valueChanged.connect(lambda v: self.vertPosSlider.setValue(int(v * 1000)))
        
        vert_pos_layout.addWidget(vert_pos_label)
        vert_pos_layout.addWidget(self.vertPosSlider)
        vert_pos_layout.addWidget(self.vertPosSpinBox)
        position_layout.addLayout(vert_pos_layout)
        
        # Z Distance
        z_dist_layout = QtWidgets.QHBoxLayout()
        z_dist_label = QtWidgets.QLabel("Z Distance:")
        self.zDistSlider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.zDistSlider.setRange(-1000, -100)
        self.zDistSlider.setValue(-1000)  # Default to -1.0
        
        self.zDistSpinBox = QtWidgets.QDoubleSpinBox()
        self.zDistSpinBox.setRange(-1.0, -0.1)
        self.zDistSpinBox.setSingleStep(0.05)
        self.zDistSpinBox.setValue(-1.0)  # Default to -1.0
        self.zDistSpinBox.setFixedWidth(70)
        
        self.zDistSlider.valueChanged.connect(lambda v: self.zDistSpinBox.setValue(v / 1000.0))
        self.zDistSpinBox.valueChanged.connect(lambda v: self.zDistSlider.setValue(int(v * 1000)))
        
        z_dist_layout.addWidget(z_dist_label)
        z_dist_layout.addWidget(self.zDistSlider)
        z_dist_layout.addWidget(self.zDistSpinBox)
        position_layout.addLayout(z_dist_layout)
        
        layout.addWidget(position_group)
        
        # Add some stretch to push everything up
        layout.addStretch()
    
    def setup_settings_tab(self):
        layout = QtWidgets.QVBoxLayout(self.settings_tab)
        
        # FFmpeg Group
        ffmpeg_group = QtWidgets.QGroupBox("FFmpeg Settings")
        ffmpeg_layout = QtWidgets.QVBoxLayout(ffmpeg_group)
        
        # FFmpeg path
        ffmpeg_path_layout = QtWidgets.QHBoxLayout()
        ffmpeg_path_label = QtWidgets.QLabel("FFmpeg Path:")
        self.ffmpegPathLineEdit = QtWidgets.QLineEdit()
        self.ffmpegPathLineEdit.setText(self.ffmpeg_path)
        
        ffmpeg_browse_btn = QtWidgets.QPushButton("...")
        ffmpeg_browse_btn.setMaximumWidth(30)
        ffmpeg_browse_btn.clicked.connect(self.browse_ffmpeg_path)
        
        ffmpeg_check_btn = QtWidgets.QPushButton("Check")
        ffmpeg_check_btn.setMaximumWidth(60)
        ffmpeg_check_btn.clicked.connect(self.check_ffmpeg)
        
        ffmpeg_path_layout.addWidget(ffmpeg_path_label)
        ffmpeg_path_layout.addWidget(self.ffmpegPathLineEdit)
        ffmpeg_path_layout.addWidget(ffmpeg_browse_btn)
        ffmpeg_path_layout.addWidget(ffmpeg_check_btn)
        ffmpeg_layout.addLayout(ffmpeg_path_layout)
        
        # Temp directory
        temp_dir_layout = QtWidgets.QHBoxLayout()
        temp_dir_label = QtWidgets.QLabel("Temp Directory:")
        self.tempDirLineEdit = QtWidgets.QLineEdit()
        
        temp_browse_btn = QtWidgets.QPushButton("...")
        temp_browse_btn.setMaximumWidth(30)
        temp_browse_btn.clicked.connect(self.browse_temp_directory)
        
        temp_dir_layout.addWidget(temp_dir_label)
        temp_dir_layout.addWidget(self.tempDirLineEdit)
        temp_dir_layout.addWidget(temp_browse_btn)
        ffmpeg_layout.addLayout(temp_dir_layout)
        
        # Encoding Presets
        encoding_presets_layout = QtWidgets.QHBoxLayout()
        
        h264_label = QtWidgets.QLabel("H.264 Preset:")
        self.h264PresetComboBox = QtWidgets.QComboBox()
        self.h264PresetComboBox.addItems(H264_PRESETS)
        self.h264PresetComboBox.setCurrentText("fast")
        
        encoding_presets_layout.addWidget(h264_label)
        encoding_presets_layout.addWidget(self.h264PresetComboBox)
        encoding_presets_layout.addStretch()
        ffmpeg_layout.addLayout(encoding_presets_layout)
        
        layout.addWidget(ffmpeg_group)
        
        # Presets Group
        presets_group = QtWidgets.QGroupBox("Playblast Presets")
        presets_layout = QtWidgets.QVBoxLayout(presets_group)
        
        # Resolution preset buttons
        res_buttons_layout = QtWidgets.QHBoxLayout()
        res_label = QtWidgets.QLabel("Resolution:")
        
        hd_preset_btn = QtWidgets.QPushButton("HD 720")
        hd_preset_btn.clicked.connect(lambda: self.apply_resolution_preset("HD 720"))
        
        full_hd_preset_btn = QtWidgets.QPushButton("HD 1080")
        full_hd_preset_btn.clicked.connect(lambda: self.apply_resolution_preset("HD 1080"))
        
        uhd_preset_btn = QtWidgets.QPushButton("UHD 4K")
        uhd_preset_btn.clicked.connect(lambda: self.apply_resolution_preset("UHD 4K"))
        
        res_buttons_layout.addWidget(res_label)
        res_buttons_layout.addWidget(hd_preset_btn)
        res_buttons_layout.addWidget(full_hd_preset_btn)
        res_buttons_layout.addWidget(uhd_preset_btn)
        presets_layout.addLayout(res_buttons_layout)
        
        # Shot Mask Presets
        mask_preset_layout = QtWidgets.QHBoxLayout()
        mask_label = QtWidgets.QLabel("Shot Mask:")
        
        minimal_preset_btn = QtWidgets.QPushButton("Minimal")
        minimal_preset_btn.clicked.connect(lambda: self.apply_shot_mask_preset("minimal"))
        
        standard_preset_btn = QtWidgets.QPushButton("Standard")
        standard_preset_btn.clicked.connect(lambda: self.apply_shot_mask_preset("standard"))
        
        detailed_preset_btn = QtWidgets.QPushButton("Detailed")
        detailed_preset_btn.clicked.connect(lambda: self.apply_shot_mask_preset("detailed"))
        
        mask_preset_layout.addWidget(mask_label)
        mask_preset_layout.addWidget(minimal_preset_btn)
        mask_preset_layout.addWidget(standard_preset_btn)
        mask_preset_layout.addWidget(detailed_preset_btn)
        presets_layout.addLayout(mask_preset_layout)
        
        # Viewport Presets
        viewport_preset_layout = QtWidgets.QHBoxLayout()
        viewport_label = QtWidgets.QLabel("Viewport:")
        
        geo_preset_btn = QtWidgets.QPushButton("Geo")
        geo_preset_btn.clicked.connect(lambda: self.apply_viewport_preset("Geo"))
        
        standard_vp_preset_btn = QtWidgets.QPushButton("Standard")
        standard_vp_preset_btn.clicked.connect(lambda: self.apply_viewport_preset("Standard"))
        
        full_preset_btn = QtWidgets.QPushButton("Full")
        full_preset_btn.clicked.connect(lambda: self.apply_viewport_preset("Full"))
        
        viewport_preset_layout.addWidget(viewport_label)
        viewport_preset_layout.addWidget(geo_preset_btn)
        viewport_preset_layout.addWidget(standard_vp_preset_btn)
        viewport_preset_layout.addWidget(full_preset_btn)
        presets_layout.addLayout(viewport_preset_layout)
        
        layout.addWidget(presets_group)
        
        # About section
        about_group = QtWidgets.QGroupBox("About")
        about_layout = QtWidgets.QVBoxLayout(about_group)
        
        about_label = QtWidgets.QLabel(
            f"<h3>{TOOL_NAME} v{VERSION}</h3>"
            "<p>This tool provides enhanced playblast capabilities with customizable shot masks and ffmpeg integration.</p>"
            "<p>Key features:</p>"
            "<ul>"
            "<li>High-quality playblasts with optimized viewport settings</li>"
            "<li>Customizable shot masks with dynamic text tags</li>"
            "<li>FFmpeg integration for superior encoding quality</li>"
            "<li>Batch processing for multiple cameras</li>"
            "<li>Comprehensive UI with settings persistence</li>"
            "</ul>"
        )
        about_label.setTextFormat(QtCore.Qt.RichText)
        about_label.setWordWrap(True)
        about_layout.addWidget(about_label)
        
        layout.addWidget(about_group)
        
        # Reset buttons
        reset_layout = QtWidgets.QHBoxLayout()
        
        self.resetPlayblastButton = QtWidgets.QPushButton("Reset Playblast Settings")
        self.resetPlayblastButton.clicked.connect(self.reset_playblast_settings)
        
        self.resetShotMaskButton = QtWidgets.QPushButton("Reset Shot Mask Settings")
        self.resetShotMaskButton.clicked.connect(self.reset_shot_mask_settings)
        
        reset_layout.addStretch()
        reset_layout.addWidget(self.resetPlayblastButton)
        reset_layout.addWidget(self.resetShotMaskButton)
        layout.addLayout(reset_layout)
        
        # Add some stretch to push everything up
        layout.addStretch()
    
    def setup_action_buttons(self):
        """Set up the action buttons at the bottom of the dialog."""
        btn_layout = QtWidgets.QHBoxLayout()
        
        # Shot Mask Toggle button
        self.toggleMaskButton = QtWidgets.QPushButton("Toggle Mask")
        self.toggleMaskButton.setMinimumHeight(30)
        self.toggleMaskButton.clicked.connect(self.toggle_shot_mask)
        
        # Batch Playblast button
        self.batchPlayblastButton = QtWidgets.QPushButton("Batch Playblast")
        self.batchPlayblastButton.setMinimumHeight(30)
        self.batchPlayblastButton.clicked.connect(self.show_batch_playblast_dialog)
        
        # Create Playblast button
        self.playblastButton = QtWidgets.QPushButton("Create Playblast")
        self.playblastButton.setMinimumHeight(40)
        self.playblastButton.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        self.playblastButton.clicked.connect(self.do_playblast)
        
        # Close button
        self.cancelButton = QtWidgets.QPushButton("Close")
        self.cancelButton.clicked.connect(self.close)
        
        btn_layout.addWidget(self.toggleMaskButton)
        btn_layout.addWidget(self.batchPlayblastButton)
        btn_layout.addStretch()
        btn_layout.addWidget(self.playblastButton)
        btn_layout.addWidget(self.cancelButton)
        
        self.main_layout.addLayout(btn_layout)
    
    def create_connections(self):
        """Connect UI signals to slots."""
        # Camera & Audio
        self.cameraComboBox.currentTextChanged.connect(self.on_camera_changed)
        
        # Resolution
        self.resolutionComboBox.currentTextChanged.connect(self.on_resolution_preset_changed)
        self.widthSpinBox.valueChanged.connect(self.on_resolution_changed)
        self.heightSpinBox.valueChanged.connect(self.on_resolution_changed)
        
        # Frame Range
        self.frameRangeComboBox.currentTextChanged.connect(self.on_frame_range_preset_changed)
        self.startFrameSpinBox.valueChanged.connect(self.on_frame_range_changed)
        self.endFrameSpinBox.valueChanged.connect(self.on_frame_range_changed)
        
        # Format & Encoding
        self.formatComboBox.currentTextChanged.connect(self.on_format_changed)
        
        # Shot Mask
        self.createShotMaskButton.clicked.connect(self.create_shot_mask_button_callback)
        self.shotMaskCheckbox.toggled.connect(self.on_shot_mask_toggled)
        
        # Shot Mask Appearance
        self.maskScaleSpinBox.valueChanged.connect(self.update_shot_mask)
        self.opacitySpinBox.valueChanged.connect(self.update_shot_mask)
        self.vertPosSpinBox.valueChanged.connect(self.update_shot_mask)
        self.zDistSpinBox.valueChanged.connect(self.update_shot_mask)
        self.topBorderCheckbox.toggled.connect(self.update_shot_mask)
        self.bottomBorderCheckbox.toggled.connect(self.update_shot_mask)
        self.counterPaddingSpinBox.valueChanged.connect(self.update_shot_mask)
        
        # Settings
        self.ffmpegPathLineEdit.editingFinished.connect(self.save_ffmpeg_path)
        self.tempDirLineEdit.editingFinished.connect(self.save_temp_directory)
    
    def initialize_ui(self):
        """Initialize UI state."""
        # Populate camera list
        self.populate_camera_list()
        
        # Populate audio list
        self.populate_audio_list()
        
        # Set artist name
        self.userNameLineEdit.setText(getpass.getuser())
        
        # Setup dependent UI elements
        self.on_format_changed()
        
        # Check ffmpeg availability
        if not is_ffmpeg_available():
            cmds.warning("FFmpeg not found. Some features will be limited.")
            if not self.ffmpeg_path:
                self.ffmpegPathLineEdit.setPlaceholderText("FFmpeg not found. Click '...' to locate")
        
        # Set default output directory
        workspace_dir = cmds.workspace(query=True, rd=True)
        movies_dir = os.path.normpath(os.path.join(workspace_dir, "movies"))
        self.outputDirLineEdit.setText(movies_dir)
        
        # Set default filename
        scene_path = cmds.file(query=True, sceneName=True) or "untitled"
        scene_name = os.path.basename(scene_path).split('.')[0]
        self.filenameLineEdit.setText(f"{scene_name}_{{camera}}")
    
    def load_settings(self):
        """Load saved settings from option variables."""
        # Playblast Settings
        self.cameraComboBox.setCurrentText(load_option_var("camera", "<Active>"))
        self.resolutionComboBox.setCurrentText(load_option_var("resolution", DEFAULT_RESOLUTION))
        self.widthSpinBox.setValue(load_option_var("width", 1920))
        self.heightSpinBox.setValue(load_option_var("height", 1080))
        self.frameRangeComboBox.setCurrentText(load_option_var("frameRange", DEFAULT_FRAME_RANGE))
        self.startFrameSpinBox.setValue(load_option_var("startFrame", int(cmds.playbackOptions(q=True, min=True))))
        self.endFrameSpinBox.setValue(load_option_var("endFrame", int(cmds.playbackOptions(q=True, max=True))))
        self.formatComboBox.setCurrentText(load_option_var("format", DEFAULT_OUTPUT_FORMAT))
        self.on_format_changed()  # Update encoder combo box
        encoder = load_option_var("encoder", DEFAULT_ENCODER)
        if encoder in [self.encoderComboBox.itemText(i) for i in range(self.encoderComboBox.count())]:
            self.encoderComboBox.setCurrentText(encoder)
        self.qualityComboBox.setCurrentText(load_option_var("quality", DEFAULT_H264_QUALITY))
        self.viewportComboBox.setCurrentText(load_option_var("viewport", DEFAULT_VIEW_PRESET))
        self.saveFileCheckbox.setChecked(load_option_var("saveFile", True))
        self.overscanCheckbox.setChecked(load_option_var("overscan", False))
        self.ornamentCheckbox.setChecked(load_option_var("ornaments", False))
        self.imagePlanesCheckbox.setChecked(load_option_var("imagePlanes", True))
        self.viewerCheckbox.setChecked(load_option_var("viewer", True))
        self.forceOverwriteCheckbox.setChecked(load_option_var("forceOverwrite", False))
        self.outputDirLineEdit.setText(load_option_var("outputDir", self.outputDirLineEdit.text()))
        self.filenameLineEdit.setText(load_option_var("filename", self.filenameLineEdit.text()))
        
        # Shot Mask Settings
        self.shotMaskCheckbox.setChecked(load_option_var("enableMask", True))
        self.userNameLineEdit.setText(load_option_var("userName", self.userNameLineEdit.text()))
        self.topLeftLineEdit.setText(load_option_var("topLeftText", "Scene: {scene}"))
        self.topCenterLineEdit.setText(load_option_var("topCenterText", ""))
        self.topRightLineEdit.setText(load_option_var("topRightText", "FPS: {fps}"))
        self.bottomLeftLineEdit.setText(load_option_var("bottomLeftText", "Artist: {username}"))
        self.bottomCenterLineEdit.setText(load_option_var("bottomCenterText", "Date: {date}"))
        self.bottomRightLineEdit.setText(load_option_var("bottomRightText", "Frame: {counter}"))
        self.maskScaleSpinBox.setValue(load_option_var("maskScale", DEFAULT_MASK_SCALE))
        self.opacitySpinBox.setValue(load_option_var("maskOpacity", 1.0))
        self.vertPosSpinBox.setValue(load_option_var("maskVertPos", 0.0))
        self.zDistSpinBox.setValue(load_option_var("maskZDist", -1.0))
        self.topBorderCheckbox.setChecked(load_option_var("topBorder", True))
        self.bottomBorderCheckbox.setChecked(load_option_var("bottomBorder", True))
        self.counterPaddingSpinBox.setValue(load_option_var("counterPadding", DEFAULT_COUNTER_PADDING))
        
        # Colors need to be handled specially
        text_color = load_option_var("textColor", [1.0, 1.0, 1.0])
        if isinstance(text_color, list) and len(text_color) >= 3:
            r, g, b = text_color[0:3]
            self.textColorButton.setStyleSheet(f"background-color: rgb({int(r*255)}, {int(g*255)}, {int(b*255)});")
        
        bar_color = load_option_var("barColor", [0.15, 0.15, 0.15])
        if isinstance(bar_color, list) and len(bar_color) >= 3:
            r, g, b = bar_color[0:3]
            self.barColorButton.setStyleSheet(f"background-color: rgb({int(r*255)}, {int(g*255)}, {int(b*255)});")
        
        # Settings Tab
        self.ffmpegPathLineEdit.setText(load_option_var("ffmpegPath", self.ffmpeg_path))
        self.tempDirLineEdit.setText(load_option_var("tempDir", tempfile.gettempdir()))
        self.h264PresetComboBox.setCurrentText(load_option_var("h264Preset", "fast"))
    
    def save_settings(self):
        """Save settings to option variables."""
        # Playblast Settings
        save_option_var("camera", self.cameraComboBox.currentText())
        save_option_var("resolution", self.resolutionComboBox.currentText())
        save_option_var("width", self.widthSpinBox.value())
        save_option_var("height", self.heightSpinBox.value())
        save_option_var("frameRange", self.frameRangeComboBox.currentText())
        save_option_var("startFrame", self.startFrameSpinBox.value())
        save_option_var("endFrame", self.endFrameSpinBox.value())
        save_option_var("format", self.formatComboBox.currentText())
        save_option_var("encoder", self.encoderComboBox.currentText())
        save_option_var("quality", self.qualityComboBox.currentText())
        save_option_var("viewport", self.viewportComboBox.currentText())
        save_option_var("saveFile", self.saveFileCheckbox.isChecked())
        save_option_var("overscan", self.overscanCheckbox.isChecked())
        save_option_var("ornaments", self.ornamentCheckbox.isChecked())
        save_option_var("imagePlanes", self.imagePlanesCheckbox.isChecked())
        save_option_var("viewer", self.viewerCheckbox.isChecked())
        save_option_var("forceOverwrite", self.forceOverwriteCheckbox.isChecked())
        save_option_var("outputDir", self.outputDirLineEdit.text())
        save_option_var("filename", self.filenameLineEdit.text())
        
        # Shot Mask Settings
        save_option_var("enableMask", self.shotMaskCheckbox.isChecked())
        save_option_var("userName", self.userNameLineEdit.text())
        save_option_var("topLeftText", self.topLeftLineEdit.text())
        save_option_var("topCenterText", self.topCenterLineEdit.text())
        save_option_var("topRightText", self.topRightLineEdit.text())
        save_option_var("bottomLeftText", self.bottomLeftLineEdit.text())
        save_option_var("bottomCenterText", self.bottomCenterLineEdit.text())
        save_option_var("bottomRightText", self.bottomRightLineEdit.text())
        save_option_var("maskScale", self.maskScaleSpinBox.value())
        save_option_var("maskOpacity", self.opacitySpinBox.value())
        save_option_var("maskVertPos", self.vertPosSpinBox.value())
        save_option_var("maskZDist", self.zDistSpinBox.value())
        save_option_var("topBorder", self.topBorderCheckbox.isChecked())
        save_option_var("bottomBorder", self.bottomBorderCheckbox.isChecked())
        save_option_var("counterPadding", self.counterPaddingSpinBox.value())
        
        # Colors - extract from stylesheet
        text_color_style = self.textColorButton.styleSheet()
        text_color = [1.0, 1.0, 1.0]  # Default white
        match = re.search(r'rgb\((\d+),\s*(\d+),\s*(\d+)\)', text_color_style)
        if match:
            r = int(match.group(1)) / 255.0
            g = int(match.group(2)) / 255.0
            b = int(match.group(3)) / 255.0
            text_color = [r, g, b]
        save_option_var("textColor", text_color)
        
        bar_color_style = self.barColorButton.styleSheet()
        bar_color = [0.15, 0.15, 0.15]  # Default dark gray
        match = re.search(r'rgb\((\d+),\s*(\d+),\s*(\d+)\)', bar_color_style)
        if match:
            r = int(match.group(1)) / 255.0
            g = int(match.group(2)) / 255.0
            b = int(match.group(3)) / 255.0
            bar_color = [r, g, b]
        save_option_var("barColor", bar_color)
        
        # Settings Tab
        save_option_var("ffmpegPath", self.ffmpegPathLineEdit.text())
        save_option_var("tempDir", self.tempDirLineEdit.text())
        save_option_var("h264Preset", self.h264PresetComboBox.currentText())
    
    def populate_camera_list(self):
        """Populate the camera dropdown list."""
        current_camera = self.cameraComboBox.currentText()
        self.cameraComboBox.clear()
        
        # Add special options
        self.cameraComboBox.addItem("<Active>")
        
        # Add all cameras
        cameras = cmds.listCameras()
        for cam in cameras:
            self.cameraComboBox.addItem(cam)
        
        # Restore selection if possible
        if current_camera and self.cameraComboBox.findText(current_camera) >= 0:
            self.cameraComboBox.setCurrentText(current_camera)
    
    def populate_audio_list(self):
        """Populate the audio dropdown list."""
        current_audio = self.audioComboBox.currentText()
        self.audioComboBox.clear()
        
        # Add None option
        self.audioComboBox.addItem("None")
        
        # Add audio nodes
        for audio in cmds.ls(type="audio"):
            try:
                audio_path = cmds.getAttr(f"{audio}.filename")
                display_name = f"{audio} ({os.path.basename(audio_path)})"
                self.audioComboBox.addItem(display_name, audio)
            except Exception as e:
                print(f"Error adding audio node {audio}: {str(e)}")
        
        # Restore selection if possible
        if current_audio and self.audioComboBox.findText(current_audio) >= 0:
            self.audioComboBox.setCurrentText(current_audio)
    
    def on_camera_changed(self):
        """Handle camera selection change."""
        # Update any UI elements that depend on camera
        pass
    
    def on_resolution_preset_changed(self):
        """Handle resolution preset selection change."""
        preset = self.resolutionComboBox.currentText()
        
        if preset != "Custom" and preset in RESOLUTION_PRESETS:
            if preset == "Render":
                width = cmds.getAttr("defaultResolution.width")
                height = cmds.getAttr("defaultResolution.height")
            else:
                width, height = RESOLUTION_PRESETS[preset]
            
            self.widthSpinBox.setValue(width)
            self.heightSpinBox.setValue(height)
            
            # Disable spinboxes for presets
            self.widthSpinBox.setEnabled(False)
            self.heightSpinBox.setEnabled(False)
        else:
            # Enable spinboxes for custom resolution
            self.widthSpinBox.setEnabled(True)
            self.heightSpinBox.setEnabled(True)
    
    def on_resolution_changed(self):
        """Handle manual resolution changes."""
        # If user changes resolution manually, switch to Custom preset
        if self.resolutionComboBox.currentText() != "Custom":
            self.resolutionComboBox.setCurrentText("Custom")
    
    def on_frame_range_preset_changed(self):
        """Handle frame range preset selection change."""
        preset = self.frameRangeComboBox.currentText()
        
        if preset != "Custom":
            if preset == "Playback":
                start_frame = int(cmds.playbackOptions(query=True, minTime=True))
                end_frame = int(cmds.playbackOptions(query=True, maxTime=True))
            elif preset == "Animation":
                start_frame = int(cmds.playbackOptions(query=True, animationStartTime=True))
                end_frame = int(cmds.playbackOptions(query=True, animationEndTime=True))
            elif preset == "Render":
                start_frame = int(cmds.getAttr("defaultRenderGlobals.startFrame"))
                end_frame = int(cmds.getAttr("defaultRenderGlobals.endFrame"))
            elif preset == "Camera":
                # Use playback range as default for Camera frame range
                start_frame = int(cmds.playbackOptions(query=True, minTime=True))
                end_frame = int(cmds.playbackOptions(query=True, maxTime=True))
                
                # Disable spinboxes for Camera frame range
                self.startFrameSpinBox.setEnabled(False)
                self.endFrameSpinBox.setEnabled(False)
                
                self.startFrameSpinBox.setValue(start_frame)
                self.endFrameSpinBox.setValue(end_frame)
                return
            
            self.startFrameSpinBox.setValue(start_frame)
            self.endFrameSpinBox.setValue(end_frame)
            
            # Enable spinboxes for all presets except Camera
            self.startFrameSpinBox.setEnabled(True)
            self.endFrameSpinBox.setEnabled(True)
        else:
            # Enable spinboxes for custom frame range
            self.startFrameSpinBox.setEnabled(True)
            self.endFrameSpinBox.setEnabled(True)
    
    def on_frame_range_changed(self):
        """Handle manual frame range changes."""
        # If user changes frame range manually, switch to Custom preset
        if self.frameRangeComboBox.currentText() != "Custom":
            self.frameRangeComboBox.setCurrentText("Custom")
    
    def on_format_changed(self):
        """Handle output format change."""
        format_type = self.formatComboBox.currentText()
        
        # Update encoder dropdown based on format
        self.encoderComboBox.clear()
        if format_type in VIDEO_ENCODERS:
            self.encoderComboBox.addItems(VIDEO_ENCODERS[format_type])
            
            # Enable or disable quality dropdown based on encoder options
            self.encoderComboBox.setEnabled(True)
            self.qualityComboBox.setEnabled(True)
        else:
            self.encoderComboBox.setEnabled(False)
            self.qualityComboBox.setEnabled(False)
    
    def on_shot_mask_toggled(self, enabled):
        """Handle shot mask checkbox toggle."""
        if enabled:
            # If mask is enabled but not created, create it
            if self.shotMaskCheckbox.isChecked() and not self.shot_mask_data:
                self.create_shot_mask_button_callback()
        else:
            # If mask is disabled but exists, remove it
            if self.shot_mask_data:
                remove_shot_mask()
                self.shot_mask_data = None
    
    def update_shot_mask(self):
        """Update shot mask with current settings."""
        if self.shot_mask_data:
            # Update scale
            update_shot_mask_scale(self.maskScaleSpinBox.value())
            
            # Update position
            update_shot_mask_position(
                y_offset=self.vertPosSpinBox.value(),
                z_distance=self.zDistSpinBox.value()
            )
            
            # Update opacity
            update_shot_mask_opacity(self.opacitySpinBox.value())
            
            # Update text color
            text_color_style = self.textColorButton.styleSheet()
            match = re.search(r'rgb\((\d+),\s*(\d+),\s*(\d+)\)', text_color_style)
            if match:
                r = int(match.group(1)) / 255.0
                g = int(match.group(2)) / 255.0
                b = int(match.group(3)) / 255.0
                update_shot_mask_text_color((r, g, b))
    
    def toggle_shot_mask(self):
        """Toggle shot mask on/off."""
        if self.shot_mask_data:
            remove_shot_mask()
            self.shot_mask_data = None
            self.shotMaskCheckbox.setChecked(False)
        else:
            self.create_shot_mask_button_callback()
            self.shotMaskCheckbox.setChecked(True)
    
    def create_shot_mask_button_callback(self):
        """Create the shot mask using current UI settings."""
        selected_camera = self.cameraComboBox.currentText()
        if selected_camera == "<Active>":
            # Get the current viewport camera
            panel = get_valid_model_panel()
            if panel:
                selected_camera = cmds.modelPanel(panel, query=True, camera=True)
            
            if not selected_camera:
                cmds.confirmDialog(title="Error", message="No active camera found. Please select a camera.", button=["OK"])
                return
        
        if not cmds.objExists(selected_camera):
            cmds.confirmDialog(title="Error", message=f"Camera '{selected_camera}' does not exist.", button=["OK"])
            return
        
        camera_shape = get_camera_shape(selected_camera)
        if not camera_shape:
            cmds.confirmDialog(title="Error", message=f"Failed to get camera shape for '{selected_camera}'.", button=["OK"])
            return
        
        if cmds.nodeType(camera_shape) == "camera":
            transforms = cmds.listRelatives(camera_shape, parent=True, fullPath=True)
            if transforms:
                camera_transform = transforms[0]
            else:
                cmds.confirmDialog(title="Error", message=f"Failed to get transform for camera '{camera_shape}'.", button=["OK"])
                return
        else:
            camera_transform = selected_camera
        
        user_name = self.userNameLineEdit.text().strip()
        if not user_name:
            user_name = getpass.getuser()
            self.userNameLineEdit.setText(user_name)
        
        # Remove existing shot mask
        if self.shot_mask_data:
            remove_shot_mask()
            self.shot_mask_data = None
        
        # Get current settings
        scene_path = cmds.file(query=True, sceneName=True) or "Untitled Scene"
        scene_name = os.path.basename(scene_path).split('.')[0]
        
        # Get text color from button
        text_color_style = self.textColorButton.styleSheet()
        text_color = (1.0, 1.0, 1.0)  # Default white
        match = re.search(r'rgb\((\d+),\s*(\d+),\s*(\d+)\)', text_color_style)
        if match:
            r = int(match.group(1)) / 255.0
            g = int(match.group(2)) / 255.0
            b = int(match.group(3)) / 255.0
            text_color = (r, g, b)
        
        # Create shot mask with custom text fields
        self.shot_mask_data = create_shot_mask(
            camera_transform,
            user_name,
            scene_name=scene_name,
            text_color=text_color
        )
        
        if self.shot_mask_data:
            # Update mask settings
            update_shot_mask_scale(self.maskScaleSpinBox.value())
            update_shot_mask_position(
                y_offset=self.vertPosSpinBox.value(),
                z_distance=self.zDistSpinBox.value()
            )
            update_shot_mask_opacity(self.opacitySpinBox.value())
            
            # Enable mask checkbox
            self.shotMaskCheckbox.setChecked(True)
            
            cmds.inViewMessage(amg="Shot Mask Created. Adjust using the controls in the Shot Mask tab.", pos='midCenter', fade=True)
        else:
            cmds.warning("Failed to create shot mask.")
    
    def select_text_color(self):
        """Open a color picker dialog for the text color."""
        current_color_style = self.textColorButton.styleSheet()
        current_color = QtGui.QColor(255, 255, 255)  # Default white
        
        match = re.search(r'rgb\((\d+),\s*(\d+),\s*(\d+)\)', current_color_style)
        if match:
            r = int(match.group(1))
            g = int(match.group(2))
            b = int(match.group(3))
            current_color = QtGui.QColor(r, g, b)
        
        color = QtWidgets.QColorDialog.getColor(current_color, self, "Select Text Color")
        
        if color.isValid():
            self.textColorButton.setStyleSheet(f"background-color: rgb({color.red()}, {color.green()}, {color.blue()});")
            
            # Update mask if it exists
            if self.shot_mask_data:
                update_shot_mask_text_color((color.red()/255.0, color.green()/255.0, color.blue()/255.0))
    
    def select_bar_color(self):
        """Open a color picker dialog for the bar color."""
        current_color_style = self.barColorButton.styleSheet()
        current_color = QtGui.QColor(38, 38, 38)  # Default dark gray
        
        match = re.search(r'rgb\((\d+),\s*(\d+),\s*(\d+)\)', current_color_style)
        if match:
            r = int(match.group(1))
            g = int(match.group(2))
            b = int(match.group(3))
            current_color = QtGui.QColor(r, g, b)
        
        color = QtWidgets.QColorDialog.getColor(current_color, self, "Select Bar Color")
        
        if color.isValid():
            self.barColorButton.setStyleSheet(f"background-color: rgb({color.red()}, {color.green()}, {color.blue()});")
            
            # Update mask if it exists (we'd need to add a bar color update function)
            if self.shot_mask_data and cmds.objExists(f"{MASK_PREFIX}BarMaterial"):
                cmds.setAttr(f"{MASK_PREFIX}BarMaterial.color", 
                            color.red()/255.0, 
                            color.green()/255.0, 
                            color.blue()/255.0, 
                            type="double3")
    
    def insert_filename_tag(self, tag):
        """Insert a tag into the filename field at cursor position."""
        cursor_pos = self.filenameLineEdit.cursorPosition()
        current_text = self.filenameLineEdit.text()
        new_text = current_text[:cursor_pos] + tag + current_text[cursor_pos:]
        self.filenameLineEdit.setText(new_text)
        self.filenameLineEdit.setCursorPosition(cursor_pos + len(tag))
    
    def insert_mask_tag(self, tag):
        """Insert a tag into the currently focused text field."""
        focused_widget = QtWidgets.QApplication.focusWidget()
        if isinstance(focused_widget, QtWidgets.QLineEdit):
            cursor_pos = focused_widget.cursorPosition()
            current_text = focused_widget.text()
            new_text = current_text[:cursor_pos] + tag + current_text[cursor_pos:]
            focused_widget.setText(new_text)
            focused_widget.setCursorPosition(cursor_pos + len(tag))
    
    def browse_output_directory(self):
        """Browse for output directory."""
        current_dir = self.outputDirLineEdit.text()
        if not os.path.isdir(current_dir):
            current_dir = cmds.workspace(query=True, rd=True)
        
        new_dir = QtWidgets.QFileDialog.getExistingDirectory(
            self, 
            "Select Output Directory", 
            current_dir
        )
        
        if new_dir:
            self.outputDirLineEdit.setText(new_dir)
    
    def browse_temp_directory(self):
        """Browse for temp directory."""
        current_dir = self.tempDirLineEdit.text()
        if not os.path.isdir(current_dir):
            current_dir = tempfile.gettempdir()
        
        new_dir = QtWidgets.QFileDialog.getExistingDirectory(
            self, 
            "Select Temporary Directory", 
            current_dir
        )
        
        if new_dir:
            self.tempDirLineEdit.setText(new_dir)
    
    def browse_ffmpeg_path(self):
        """Browse for ffmpeg executable."""
        current_path = self.ffmpegPathLineEdit.text()
        
        if platform.system() == "Windows":
            file_filter = "Executable Files (*.exe);;All Files (*.*)"
        else:
            file_filter = "All Files (*.*)"
        
        new_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, 
            "Select FFmpeg Executable", 
            os.path.dirname(current_path) if current_path else os.path.expanduser("~"),
            file_filter
        )
        
        if new_path:
            self.ffmpegPathLineEdit.setText(new_path)
            self.save_ffmpeg_path()
    
    def save_ffmpeg_path(self):
        """Save the ffmpeg path."""
        self.ffmpeg_path = self.ffmpegPathLineEdit.text()
        save_option_var("ffmpegPath", self.ffmpeg_path)
    
    def save_temp_directory(self):
        """Save the temp directory path."""
        save_option_var("tempDir", self.tempDirLineEdit.text())
    
    def check_ffmpeg(self):
        """Check if ffmpeg is available and working."""
        ffmpeg_path = self.ffmpegPathLineEdit.text()
        
        if not ffmpeg_path:
            QtWidgets.QMessageBox.warning(self, "FFmpeg Check", "FFmpeg path is not set.")
            return
        
        if not os.path.exists(ffmpeg_path):
            QtWidgets.QMessageBox.warning(self, "FFmpeg Check", f"FFmpeg executable not found at: {ffmpeg_path}")
            return
        
        try:
            result = subprocess.run(
                [ffmpeg_path, "-version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True
            )
            
            version_info = result.stdout.split('\n')[0]
            QtWidgets.QMessageBox.information(self, "FFmpeg Check", f"FFmpeg is working correctly.\n\n{version_info}")
            
        except subprocess.CalledProcessError as e:
            QtWidgets.QMessageBox.critical(self, "FFmpeg Check", f"Error running FFmpeg: {e.stderr}")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "FFmpeg Check", f"Error checking FFmpeg: {str(e)}")
    
    def show_encoding_settings(self):
        """Show dialog for advanced encoding settings."""
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Encoding Settings")
        dialog.setMinimumWidth(400)
        
        layout = QtWidgets.QVBoxLayout(dialog)
        
        # Container format
        format_layout = QtWidgets.QHBoxLayout()
        format_label = QtWidgets.QLabel("Container:")
        format_combo = QtWidgets.QComboBox()
        format_combo.addItems(OUTPUT_FORMATS)
        format_combo.setCurrentText(self.formatComboBox.currentText())
        
        format_layout.addWidget(format_label)
        format_layout.addWidget(format_combo)
        layout.addLayout(format_layout)
        
        # H.264 Settings Group
        h264_group = QtWidgets.QGroupBox("H.264 Settings")
        h264_layout = QtWidgets.QVBoxLayout(h264_group)
        
        # Quality
        quality_layout = QtWidgets.QHBoxLayout()
        quality_label = QtWidgets.QLabel("Quality:")
        quality_combo = QtWidgets.QComboBox()
        quality_combo.addItems(["Very High", "High", "Medium", "Low"])
        quality_combo.setCurrentText(self.qualityComboBox.currentText())
        
        crf_label = QtWidgets.QLabel("CRF Value:")
        crf_spinbox = QtWidgets.QSpinBox()
        crf_spinbox.setRange(0, 51)
        crf_spinbox.setValue(H264_QUALITIES.get(quality_combo.currentText(), 23))
        crf_spinbox.setToolTip("Lower values = better quality (18-28 recommended)")
        
        quality_layout.addWidget(quality_label)
        quality_layout.addWidget(quality_combo)
        quality_layout.addWidget(crf_label)
        quality_layout.addWidget(crf_spinbox)
        h264_layout.addLayout(quality_layout)
        
        # Connect quality combo to update CRF value
        quality_combo.currentTextChanged.connect(
            lambda text: crf_spinbox.setValue(H264_QUALITIES.get(text, 23))
        )
        
        # Preset
        preset_layout = QtWidgets.QHBoxLayout()
        preset_label = QtWidgets.QLabel("Preset:")
        preset_combo = QtWidgets.QComboBox()
        preset_combo.addItems(H264_PRESETS)
        preset_combo.setCurrentText(self.h264PresetComboBox.currentText())
        preset_combo.setToolTip("Encoding speed vs compression efficiency")
        
        preset_layout.addWidget(preset_label)
        preset_layout.addWidget(preset_combo)
        h264_layout.addLayout(preset_layout)
        
        layout.addWidget(h264_group)
        
        # ProRes Settings Group
        prores_group = QtWidgets.QGroupBox("ProRes Settings")
        prores_layout = QtWidgets.QVBoxLayout(prores_group)
        
        # Profile
        profile_layout = QtWidgets.QHBoxLayout()
        profile_label = QtWidgets.QLabel("Profile:")
        profile_combo = QtWidgets.QComboBox()
        profile_combo.addItems(PRORES_PROFILES.keys())
        profile_combo.setCurrentText("ProRes 422 HQ")
        
        profile_layout.addWidget(profile_label)
        profile_layout.addWidget(profile_combo)
        prores_layout.addLayout(profile_layout)
        
        layout.addWidget(prores_group)
        
        # Image Sequence Settings Group
        image_group = QtWidgets.QGroupBox("Image Sequence Settings")
        image_layout = QtWidgets.QVBoxLayout(image_group)
        
        # Format
        image_format_layout = QtWidgets.QHBoxLayout()
        image_format_label = QtWidgets.QLabel("Format:")
        image_format_combo = QtWidgets.QComboBox()
        image_format_combo.addItems(FRAME_FORMATS)
        image_format_combo.setCurrentText("png")
        
        image_format_layout.addWidget(image_format_label)
        image_format_layout.addWidget(image_format_combo)
        image_layout.addLayout(image_format_layout)
        
        # Quality for JPEG
        image_quality_layout = QtWidgets.QHBoxLayout()
        image_quality_label = QtWidgets.QLabel("JPEG Quality:")
        image_quality_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        image_quality_slider.setRange(1, 100)
        image_quality_slider.setValue(95)
        
        image_quality_spinbox = QtWidgets.QSpinBox()
        image_quality_spinbox.setRange(1, 100)
        image_quality_spinbox.setValue(95)
        
        image_quality_slider.valueChanged.connect(image_quality_spinbox.setValue)
        image_quality_spinbox.valueChanged.connect(image_quality_slider.setValue)
        
        image_quality_layout.addWidget(image_quality_label)
        image_quality_layout.addWidget(image_quality_slider)
        image_quality_layout.addWidget(image_quality_spinbox)
        image_layout.addLayout(image_quality_layout)
        
        layout.addWidget(image_group)
        
        # Show/hide appropriate sections based on format
        def update_settings_visibility():
            format_type = format_combo.currentText()
            h264_group.setVisible(format_type in ["mp4", "mov"])
            prores_group.setVisible(format_type == "mov")
            image_group.setVisible(format_type == "Image")
        
        format_combo.currentTextChanged.connect(update_settings_visibility)
        update_settings_visibility()
        
        # Buttons
        button_layout = QtWidgets.QHBoxLayout()
        ok_button = QtWidgets.QPushButton("OK")
        cancel_button = QtWidgets.QPushButton("Cancel")
        
        ok_button.clicked.connect(dialog.accept)
        cancel_button.clicked.connect(dialog.reject)
        
        button_layout.addStretch()
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)
        
        # Execute the dialog
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            # Update main UI based on dialog settings
            self.formatComboBox.setCurrentText(format_combo.currentText())
            self.on_format_changed()  # Update encoder combobox
            
            # Set encoder based on format
            format_type = format_combo.currentText()
            if format_type in ["mp4", "mov"]:
                # For video formats, determine which encoder to use
                if format_type == "mp4" or (format_type == "mov" and h264_group.isVisible()):
                    self.encoderComboBox.setCurrentText("h264")
                    self.qualityComboBox.setCurrentText(quality_combo.currentText())
                    self.h264PresetComboBox.setCurrentText(preset_combo.currentText())
                elif format_type == "mov" and prores_group.isVisible():
                    self.encoderComboBox.setCurrentText("prores")
                    # Save ProRes profile as quality
                    self.qualityComboBox.setCurrentText(profile_combo.currentText())
            elif format_type == "Image":
                # For image sequences, set the format
                self.encoderComboBox.setCurrentText(image_format_combo.currentText())
                
                # Save quality setting if jpg
                if image_format_combo.currentText() == "jpg":
                    save_option_var("jpegQuality", image_quality_spinbox.value())
    
    def show_viewport_settings(self):
        """Show dialog for customizing viewport visibility."""
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Viewport Visibility Settings")
        dialog.setMinimumWidth(450)
        
        layout = QtWidgets.QVBoxLayout(dialog)
        
        # Instructions
        instructions = QtWidgets.QLabel("Select which elements to show in the playblast viewport:")
        layout.addWidget(instructions)
        
        # Checkboxes in a grid
        form_layout = QtWidgets.QGridLayout()
        
        # Create a checkbox for each visibility item
        checkboxes = []
        row, col = 0, 0
        max_cols = 3
        
        # Create the checkboxes
        for item in VIEWPORT_VISIBILITY_LOOKUP:
            display_name = item[0]
            checkbox = QtWidgets.QCheckBox(display_name)
            
            # Check it if it's part of the current preset
            current_preset = self.viewportComboBox.currentText()
            if current_preset in VIEWPORT_VISIBILITY_PRESETS:
                checkbox.setChecked(display_name in VIEWPORT_VISIBILITY_PRESETS[current_preset])
            
            checkboxes.append(checkbox)
            form_layout.addWidget(checkbox, row, col)
            
            # Move to next column or row
            col += 1
            if col >= max_cols:
                col = 0
                row += 1
        
        # Add the grid to the layout
        layout.addLayout(form_layout)
        
        # Preset buttons
        preset_layout = QtWidgets.QHBoxLayout()
        preset_label = QtWidgets.QLabel("Presets:")
        
        viewport_btn = QtWidgets.QPushButton("Viewport")
        viewport_btn.clicked.connect(lambda: self.apply_visibility_preset_to_dialog(checkboxes, "Viewport"))
        
        geo_btn = QtWidgets.QPushButton("Geo")
        geo_btn.clicked.connect(lambda: self.apply_visibility_preset_to_dialog(checkboxes, "Geo"))
        
        standard_btn = QtWidgets.QPushButton("Standard")
        standard_btn.clicked.connect(lambda: self.apply_visibility_preset_to_dialog(checkboxes, "Standard"))
        
        full_btn = QtWidgets.QPushButton("Full")
        full_btn.clicked.connect(lambda: self.apply_visibility_preset_to_dialog(checkboxes, "Full"))
        
        preset_layout.addWidget(preset_label)
        preset_layout.addWidget(viewport_btn)
        preset_layout.addWidget(geo_btn)
        preset_layout.addWidget(standard_btn)
        preset_layout.addWidget(full_btn)
        preset_layout.addStretch()
        
        layout.addLayout(preset_layout)
        
        # Save as new preset
        save_preset_layout = QtWidgets.QHBoxLayout()
        save_preset_label = QtWidgets.QLabel("Save as new preset:")
        save_preset_name = QtWidgets.QLineEdit()
        save_preset_btn = QtWidgets.QPushButton("Save")
        
        save_preset_layout.addWidget(save_preset_label)
        save_preset_layout.addWidget(save_preset_name)
        save_preset_layout.addWidget(save_preset_btn)
        
        layout.addLayout(save_preset_layout)
        
        # Buttons
        button_layout = QtWidgets.QHBoxLayout()
        ok_button = QtWidgets.QPushButton("Apply")
        cancel_button = QtWidgets.QPushButton("Cancel")
        
        ok_button.clicked.connect(dialog.accept)
        cancel_button.clicked.connect(dialog.reject)
        
        button_layout.addStretch()
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)
        
        # Connect save preset button
        save_preset_btn.clicked.connect(lambda: self.save_visibility_preset(checkboxes, save_preset_name.text()))
        
        # Execute the dialog
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            # Create a custom visibility preset from the checkboxes
            visible_items = []
            for i, checkbox in enumerate(checkboxes):
                if checkbox.isChecked():
                    visible_items.append(VIEWPORT_VISIBILITY_LOOKUP[i][0])
            
            # Save the custom preset
            VIEWPORT_VISIBILITY_PRESETS["Custom"] = visible_items
            
            # Update the combobox
            if "Custom" not in [self.viewportComboBox.itemText(i) for i in range(self.viewportComboBox.count())]:
                self.viewportComboBox.addItem("Custom")
            
            self.viewportComboBox.setCurrentText("Custom")
    
    def apply_visibility_preset_to_dialog(self, checkboxes, preset_name):
        """Apply a visibility preset to the dialog checkboxes."""
        if preset_name not in VIEWPORT_VISIBILITY_PRESETS:
            return
        
        preset_items = VIEWPORT_VISIBILITY_PRESETS[preset_name]
        
        # Check or uncheck each box based on the preset
        for i, checkbox in enumerate(checkboxes):
            display_name = VIEWPORT_VISIBILITY_LOOKUP[i][0]
            checkbox.setChecked(display_name in preset_items)
    
    def save_visibility_preset(self, checkboxes, preset_name):
        """Save the current visibility settings as a new preset."""
        if not preset_name:
            QtWidgets.QMessageBox.warning(self, "Save Preset", "Please enter a preset name.")
            return
        
        # Create a list of visible items
        visible_items = []
        for i, checkbox in enumerate(checkboxes):
            if checkbox.isChecked():
                visible_items.append(VIEWPORT_VISIBILITY_LOOKUP[i][0])
        
        # Save to the presets dictionary
        VIEWPORT_VISIBILITY_PRESETS[preset_name] = visible_items
        
        # Save presets to option var for persistence
        preset_dict = {preset: VIEWPORT_VISIBILITY_PRESETS[preset] for preset in VIEWPORT_VISIBILITY_PRESETS if preset != "Viewport"}
        save_option_var("viewportPresets", preset_dict)
        
        # Update the combobox in main UI
        if preset_name not in [self.viewportComboBox.itemText(i) for i in range(self.viewportComboBox.count())]:
            self.viewportComboBox.addItem(preset_name)
        
        QtWidgets.QMessageBox.information(self, "Save Preset", f"Saved preset: {preset_name}")
    
    def apply_resolution_preset(self, preset_name):
        """Apply a resolution preset."""
        if preset_name in RESOLUTION_PRESETS:
            self.resolutionComboBox.setCurrentText(preset_name)
            QtWidgets.QMessageBox.information(self, "Resolution Preset", 
                                            f"Resolution set to {preset_name}")
    
    def apply_shot_mask_preset(self, preset_type):
        """Apply a predefined shot mask preset."""
        if preset_type == "minimal":
            # Minimal preset - just scene, frame counter
            self.topLeftLineEdit.setText("Scene: {scene}")
            self.topCenterLineEdit.setText("")
            self.topRightLineEdit.setText("")
            self.bottomLeftLineEdit.setText("")
            self.bottomCenterLineEdit.setText("")
            self.bottomRightLineEdit.setText("Frame: {counter}")
            self.maskScaleSpinBox.setValue(0.2)
            self.opacitySpinBox.setValue(0.8)
            
            # Light gray text
            color = QtGui.QColor(200, 200, 200)
            self.textColorButton.setStyleSheet(f"background-color: rgb({color.red()}, {color.green()}, {color.blue()});")
            
            # Update mask if it exists
            if self.shot_mask_data:
                update_shot_mask_scale(0.2)
                update_shot_mask_opacity(0.8)
                update_shot_mask_text_color((color.red()/255.0, color.green()/255.0, color.blue()/255.0))
        
        elif preset_type == "standard":
            # Standard preset - more comprehensive information
            self.topLeftLineEdit.setText("Scene: {scene}")
            self.topCenterLineEdit.setText("")
            self.topRightLineEdit.setText("FPS: {fps}")
            self.bottomLeftLineEdit.setText("Artist: {username}")
            self.bottomCenterLineEdit.setText("Date: {date}")
            self.bottomRightLineEdit.setText("Frame: {counter}")
            self.maskScaleSpinBox.setValue(0.25)
            self.opacitySpinBox.setValue(1.0)
            
            # White text
            color = QtGui.QColor(255, 255, 255)
            self.textColorButton.setStyleSheet(f"background-color: rgb({color.red()}, {color.green()}, {color.blue()});")
            
            # Update mask if it exists
            if self.shot_mask_data:
                update_shot_mask_scale(0.25)
                update_shot_mask_opacity(1.0)
                update_shot_mask_text_color((color.red()/255.0, color.green()/255.0, color.blue()/255.0))
        
        elif preset_type == "detailed":
            # Detailed preset - all information plus camera
            self.topLeftLineEdit.setText("Scene: {scene}")
            self.topCenterLineEdit.setText("Camera: {camera}")
            self.topRightLineEdit.setText("Focal: {focal_length}")
            self.bottomLeftLineEdit.setText("Artist: {username}")
            self.bottomCenterLineEdit.setText("Date: {date} {time}")
            self.bottomRightLineEdit.setText("Frame: {counter}")
            self.maskScaleSpinBox.setValue(0.3)
            self.opacitySpinBox.setValue(0.9)
            
            # Light blue text
            color = QtGui.QColor(100, 200, 255)
            self.textColorButton.setStyleSheet(f"background-color: rgb({color.red()}, {color.green()}, {color.blue()});")
            
            # Update mask if it exists
            if self.shot_mask_data:
                update_shot_mask_scale(0.3)
                update_shot_mask_opacity(0.9)
                update_shot_mask_text_color((color.red()/255.0, color.green()/255.0, color.blue()/255.0))
        
        # Update the active mask if it exists
        if self.shot_mask_data:
            # We need to update the text on the mask
            # This would require recreating the mask
            self.create_shot_mask_button_callback()
        
        QtWidgets.QMessageBox.information(self, "Shot Mask Preset", 
                                        f"Applied {preset_type} shot mask preset")
    
    def apply_viewport_preset(self, preset_name):
        """Apply a viewport visibility preset."""
        if preset_name in VIEWPORT_VISIBILITY_PRESETS:
            self.viewportComboBox.setCurrentText(preset_name)
            QtWidgets.QMessageBox.information(self, "Viewport Preset", 
                                            f"Viewport set to {preset_name}")
    
    def reset_playblast_settings(self):
        """Reset playblast settings to defaults."""
        result = QtWidgets.QMessageBox.question(
            self, 
            "Reset Playblast Settings", 
            "Are you sure you want to reset all playblast settings to defaults?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No
        )
        
        if result == QtWidgets.QMessageBox.Yes:
            # Reset to defaults
            self.shotMaskCheckbox.setChecked(True)
            self.topLeftLineEdit.setText("Scene: {scene}")
            self.topCenterLineEdit.setText("")
            self.topRightLineEdit.setText("FPS: {fps}")
            self.bottomLeftLineEdit.setText("Artist: {username}")
            self.bottomCenterLineEdit.setText("Date: {date}")
            self.bottomRightLineEdit.setText("Frame: {counter}")
            
            # Reset appearance
            self.textColorButton.setStyleSheet("background-color: rgb(255, 255, 255);")
            self.barColorButton.setStyleSheet("background-color: rgb(38, 38, 38);")
            self.maskScaleSpinBox.setValue(DEFAULT_MASK_SCALE)
            self.opacitySpinBox.setValue(1.0)
            self.topBorderCheckbox.setChecked(True)
            self.bottomBorderCheckbox.setChecked(True)
            self.counterPaddingSpinBox.setValue(DEFAULT_COUNTER_PADDING)
            
            # Reset position
            self.vertPosSpinBox.setValue(0.0)
            self.zDistSpinBox.setValue(-1.0)
            
            # Save and update
            self.save_settings()
            
            # Update mask if it exists
            if self.shot_mask_data:
                self.create_shot_mask_button_callback()
    
    def show_batch_playblast_dialog(self):
        """Show dialog for batch playblasting multiple cameras."""
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Batch Playblast")
        dialog.setMinimumWidth(350)
        
        layout = QtWidgets.QVBoxLayout(dialog)
        
        # Instructions
        instructions = QtWidgets.QLabel("Select cameras to batch playblast:")
        layout.addWidget(instructions)
        
        # Camera list
        camera_list = QtWidgets.QListWidget()
        camera_list.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        
        # Add cameras to list
        cameras = cmds.listCameras()
        default_cameras = ["persp", "top", "front", "side"]
        
        # Add user cameras first
        for cam in cameras:
            if cam not in default_cameras:
                camera_list.addItem(cam)
        
        # Add separator
        separator_item = QtWidgets.QListWidgetItem("--- Default Cameras ---")
        separator_item.setFlags(separator_item.flags() & ~QtCore.Qt.ItemIsSelectable)
        camera_list.addItem(separator_item)
        
        # Add default cameras
        for cam in default_cameras:
            if cam in cameras:
                camera_list.addItem(cam)
        
        layout.addWidget(camera_list)
        
        # Output options
        options_group = QtWidgets.QGroupBox("Output Options")
        options_layout = QtWidgets.QVBoxLayout(options_group)
        
        same_settings_checkbox = QtWidgets.QCheckBox("Use current playblast settings")
        same_settings_checkbox.setChecked(True)
        options_layout.addWidget(same_settings_checkbox)
        
        output_layout = QtWidgets.QHBoxLayout()
        output_label = QtWidgets.QLabel("Add to filename:")
        output_suffix = QtWidgets.QLineEdit("_batch")
        output_layout.addWidget(output_label)
        output_layout.addWidget(output_suffix)
        options_layout.addLayout(output_layout)
        
        layout.addWidget(options_group)
        
        # Buttons
        button_layout = QtWidgets.QHBoxLayout()
        playblast_button = QtWidgets.QPushButton("Batch Playblast")
        cancel_button = QtWidgets.QPushButton("Cancel")
        
        playblast_button.clicked.connect(dialog.accept)
        cancel_button.clicked.connect(dialog.reject)
        
        button_layout.addStretch()
        button_layout.addWidget(playblast_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)
        
        # Execute dialog
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            selected_cameras = [item.text() for item in camera_list.selectedItems()]
            
            if not selected_cameras:
                QtWidgets.QMessageBox.warning(self, "Batch Playblast", "No cameras selected.")
                return
            
            # Get current settings
            settings = self.get_current_settings()
            
            # Add suffix to filename
            if output_suffix.text():
                filename = settings.get("filename", "")
                if filename:
                    settings["filename"] = f"{filename}{output_suffix.text()}"
            
            # Call batch playblast function
            import conestoga_playblast
            progress_dialog = QtWidgets.QProgressDialog("Creating batch playblasts...", "Cancel", 0, len(selected_cameras), self)
            progress_dialog.setWindowModality(QtCore.Qt.WindowModal)
            progress_dialog.setMinimumDuration(0)
            progress_dialog.show()
            
            results = []
            for i, camera in enumerate(selected_cameras):
                progress_dialog.setValue(i)
                progress_dialog.setLabelText(f"Playblasting camera: {camera}")
                
                if progress_dialog.wasCanceled():
                    break
                
                # Update camera in settings
                camera_settings = settings.copy()
                camera_settings["camera"] = camera
                
                # Create playblast
                QtWidgets.QApplication.processEvents()
                try:
                    result = conestoga_playblast.create_playblast(**camera_settings)
                    if result:
                        results.append(result)
                except Exception as e:
                    print(f"Error playblasting camera {camera}: {str(e)}")
                    traceback.print_exc()
            
            progress_dialog.setValue(len(selected_cameras))
            
            # Show results
            if results:
                QtWidgets.QMessageBox.information(
                    self, 
                    "Batch Playblast Complete", 
                    f"Successfully created {len(results)} playblasts."
                )
    
    def get_current_settings(self):
        """Get current settings from UI as a dictionary."""
        settings = {}
        
        # Camera settings
        camera = self.cameraComboBox.currentText()
        if camera != "<Active>":
            settings["camera"] = camera
        
        # Resolution settings
        if self.resolutionComboBox.currentText() == "Custom":
            settings["width"] = self.widthSpinBox.value()
            settings["height"] = self.heightSpinBox.value()
        else:
            settings["resolution"] = self.resolutionComboBox.currentText()
        
        # Frame range settings
        if self.frameRangeComboBox.currentText() != "Camera":
            settings["start_frame"] = self.startFrameSpinBox.value()
            settings["end_frame"] = self.endFrameSpinBox.value()
        
        # Format settings
        settings["format_type"] = self.formatComboBox.currentText()
        settings["encoder"] = self.encoderComboBox.currentText()
        settings["quality"] = self.qualityComboBox.currentText()
        
        # Viewport settings
        settings["viewport_preset"] = self.viewportComboBox.currentText()
        
        # Option checkboxes
        settings["overscan"] = self.overscanCheckbox.isChecked()
        settings["ornaments"] = self.ornamentCheckbox.isChecked()
        settings["shot_mask"] = self.shotMaskCheckbox.isChecked()
        settings["show_in_viewer"] = self.viewerCheckbox.isChecked()
        settings["force_overwrite"] = self.forceOverwriteCheckbox.isChecked()
        
        # Output settings
        settings["output_dir"] = self.outputDirLineEdit.text()
        settings["filename"] = self.filenameLineEdit.text()
        
        return settings
    
    def do_playblast(self):
        """Create playblast with current settings."""
        # Get settings from UI
        settings = self.get_current_settings()
        
        # Add shot mask settings if enabled
        if settings.get("shot_mask", False):
            shot_mask_settings = {
                "topLeftText": self.topLeftLineEdit.text(),
                "topCenterText": self.topCenterLineEdit.text(),
                "topRightText": self.topRightLineEdit.text(),
                "bottomLeftText": self.bottomLeftLineEdit.text(),
                "bottomCenterText": self.bottomCenterLineEdit.text(),
                "bottomRightText": self.bottomRightLineEdit.text(),
                "userName": self.userNameLineEdit.text(),
                "scale": self.maskScaleSpinBox.value(),
                "opacity": self.opacitySpinBox.value(),
                "vertPos": self.vertPosSpinBox.value(),
                "zDist": self.zDistSpinBox.value(),
                "topBorder": self.topBorderCheckbox.isChecked(),
                "bottomBorder": self.bottomBorderCheckbox.isChecked(),
                "counterPadding": self.counterPaddingSpinBox.value()
            }
            
            # Extract text color from button
            text_color_style = self.textColorButton.styleSheet()
            match = re.search(r'rgb\((\d+),\s*(\d+),\s*(\d+)\)', text_color_style)
            if match:
                r = int(match.group(1)) / 255.0
                g = int(match.group(2)) / 255.0
                b = int(match.group(3)) / 255.0
                shot_mask_settings["textColor"] = [r, g, b]
            
            # Extract bar color from button
            bar_color_style = self.barColorButton.styleSheet()
            match = re.search(r'rgb\((\d+),\s*(\d+),\s*(\d+)\)', bar_color_style)
            if match:
                r = int(match.group(1)) / 255.0
                g = int(match.group(2)) / 255.0
                b = int(match.group(3)) / 255.0
                shot_mask_settings["barColor"] = [r, g, b]
            
            settings["shot_mask_settings"] = shot_mask_settings
        
        # Save settings
        self.save_settings()
        
        # Create playblast
        import conestoga_playblast
        
        try:
            result = conestoga_playblast.create_playblast(**settings)
            if result:
                QtWidgets.QMessageBox.information(
                    self, 
                    "Playblast Complete", 
                    f"Playblast created successfully at:\n{result}"
                )
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "Playblast Error",
                f"Error creating playblast: {str(e)}"
            )
            traceback.print_exc()

# ===========================================================================
# UI FUNCTIONS
# ===========================================================================

def show_playblast_dialog():
    """Show the main playblast dialog."""
    dialog = PlayblastDialog()
    dialog.show()
    return dialog

def show_about_dialog():
    """Show the about dialog."""
    about_text = f"""
    <h1>{TOOL_NAME}</h1>
    <h3>Version {VERSION}</h3>
    
    <p>A modular playblast tool for Maya that provides enhanced playblast capabilities 
    with customizable shot masks and ffmpeg integration.</p>
    
    <h4>Features:</h4>
    <ul>
    <li>Advanced playblast creation with customizable settings</li>
    <li>High-quality shot masks with dynamic text tags</li>
    <li>FFmpeg integration for superior video quality</li>
    <li>Batch processing for multiple cameras and scenes</li>
    <li>Professional UI with settings persistence</li>
    </ul>
    
    <p>&copy; 2025 Conestoga College. All rights reserved.</p>
    """
    
    dialog = QtWidgets.QDialog(get_maya_main_window())
    dialog.setWindowTitle(f"About {TOOL_NAME}")
    dialog.setMinimumWidth(400)
    dialog.setMinimumHeight(300)
    
    layout = QtWidgets.QVBoxLayout(dialog)
    
    about_label = QtWidgets.QLabel(about_text)
    about_label.setTextFormat(QtCore.Qt.RichText)
    about_label.setWordWrap(True)
    about_label.setAlignment(QtCore.Qt.AlignCenter)
    
    layout.addWidget(about_label)
    
    button_layout = QtWidgets.QHBoxLayout()
    ok_button = QtWidgets.QPushButton("OK")
    ok_button.clicked.connect(dialog.accept)
    
    button_layout.addStretch()
    button_layout.addWidget(ok_button)
    button_layout.addStretch()
    
    layout.addLayout(button_layout)
    
    dialog.exec_()


# If run directly, show the dialog
if __name__ == "__main__":
    show_playblast_dialog()

    self.resolutionComboBox.setCurrentText(DEFAULT_RESOLUTION)
    self.frameRangeComboBox.setCurrentText(DEFAULT_FRAME_RANGE)
    self.formatComboBox.setCurrentText(DEFAULT_OUTPUT_FORMAT)
    self.on_format_changed()
    self.encoderComboBox.setCurrentText(DEFAULT_ENCODER)
    self.qualityComboBox.setCurrentText(DEFAULT_H264_QUALITY)
    self.viewportComboBox.setCurrentText(DEFAULT_VIEW_PRESET)
    self.saveFileCheckbox.setChecked(True)
    self.overscanCheckbox.setChecked(False)
    self.ornamentCheckbox.setChecked(False)
    self.imagePlanesCheckbox.setChecked(True)
    self.viewerCheckbox.setChecked(True)
    self.forceOverwriteCheckbox.setChecked(False)
    
    # Reset ffmpeg settings
    self.h264PresetComboBox.setCurrentText("fast")
    
    # Save the reset settings
    self.save_settings()
    
    from PySide6 import QtWidgets
from conestoga_playblast_presets import DEFAULT_MASK_SCALE, DEFAULT_COUNTER_PADDING

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