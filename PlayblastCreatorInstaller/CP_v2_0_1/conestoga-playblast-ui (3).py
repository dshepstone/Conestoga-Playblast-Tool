#!/usr/bin/env python
"""
Conestoga Playblast Tool UI
This file is part of a three‐file project:
  1. conestoga_playblast_ui.py – the user interface
  2. conestoga_presets.py – custom presets
  3. conestoga_playblast.py – the playblast plug‐in

The UI is built using a tab layout with three tabs:
  • Playblast – contains all output settings, name generator, camera/resolution/frame‐range,
    encoding and visibility controls.
  • Shot Mask – contains shot mask enable/fit controls.
  • Settings – contains logging options.

To launch the UI inside Maya, load this script and then call show_ui().
"""

import os
import sys
import time
import traceback
import getpass
import copy
from functools import partial

try:
    from PySide6 import QtCore, QtGui, QtWidgets
    from shiboken6 import getCppPointer, wrapInstance
except ImportError:
    from PySide2 import QtCore, QtGui, QtWidgets
    from shiboken2 import getCppPointer, wrapInstance

import maya.cmds as cmds
import maya.mel as mel
import maya.api.OpenMaya as om
import maya.OpenMayaUI as omui

# Import the presets and core playblast functionality from the project files.
from conestoga_presets import ConestogaPlayblastCustomPresets, ConestogaShotMaskCustomPresets

#-------------------------------------------------------------------------
# Utility Classes and Functions
#-------------------------------------------------------------------------
class ConestogaPlayblastUtils(object):
    PLUG_IN_NAME = "conestoga_playblast.py"

    @classmethod
    def is_plugin_loaded(cls):
        return cmds.pluginInfo(cls.PLUG_IN_NAME, q=True, loaded=True)

    @classmethod
    def load_plugin(cls):
        if not cls.is_plugin_loaded():
            try:
                cmds.loadPlugin(cls.PLUG_IN_NAME)
            except:
                om.MGlobal.displayError(f"Failed to load Conestoga Playblast plug-in: {cls.PLUG_IN_NAME}")
                return
        return True

    @classmethod
    def get_version(cls):
        return cmds.ConestogaPlayblast(v=True)[0]  # pylint: disable=E1101

    @classmethod
    def get_ffmpeg_path(cls):
        return cmds.ConestogaPlayblast(q=True, fp=True)[0]  # pylint: disable=E1101

    @classmethod
    def set_ffmpeg_path(cls, path):
        cmds.ConestogaPlayblast(e=True, fp=path)  # pylint: disable=E1101

    @classmethod
    def is_ffmpeg_env_var_set(cls):
        return cmds.ConestogaPlayblast(fev=True)[0]  # pylint: disable=E1101

    @classmethod
    def get_temp_output_dir_path(cls):
        return cmds.ConestogaPlayblast(q=True, tp=True)[0]  # pylint: disable=E1101

    @classmethod
    def set_temp_output_dir_path(cls, path):
        cmds.ConestogaPlayblast(e=True, tp=path)  # pylint: disable=E1101

    @classmethod
    def is_temp_output_env_var_set(cls):
        return cmds.ConestogaPlayblast(tev=True)[0]  # pylint: disable=E1101

    @classmethod
    def get_temp_file_format(cls):
        return cmds.ConestogaPlayblast(q=True, tf=True)[0]  # pylint: disable=E1101

    @classmethod
    def set_temp_file_format(cls, file_format):
        cmds.ConestogaPlayblast(e=True, tf=file_format)  # pylint: disable=E1101

    @classmethod
    def is_temp_format_env_set(cls):
        return cmds.ConestogaPlayblast(tfe=True)[0]  # pylint: disable=E1101

    @classmethod
    def get_logo_path(cls):
        return cmds.ConestogaPlayblast(q=True, lp=True)[0]  # pylint: disable=E1101

    @classmethod
    def set_logo_path(cls, path):
        cmds.ConestogaPlayblast(e=True, lp=path)  # pylint: disable=E1101

    @classmethod
    def is_logo_env_var_set(cls):
        return cmds.ConestogaPlayblast(lev=True)[0]  # pylint: disable=E1101

    @classmethod
    def dpi_real_scale_value(cls):
        scale = 1.0
        try:
            scale = cmds.mayaDpiSetting(query=True, rsv=True)
        except:
            pass
        return scale

    @classmethod
    def cameras_in_scene(cls, include_defaults=True, user_created_first=True):
        default_cameras = ["front", "persp", "side", "top"]
        found_default_cameras = []
        
        cameras = cmds.listCameras()

        if include_defaults and user_created_first or not include_defaults:
            for name in default_cameras:
                if name in cameras:
                    found_default_cameras.append(name)
                    cameras.remove(name)

            if include_defaults and user_created_first:
                for name in found_default_cameras:
                    cameras.append(name)

        return cameras

    @classmethod
    def get_opt_var_str(cls, name):
        if cmds.optionVar(exists=name):
            return cmds.optionVar(q=name)
        return ""

# A custom QLineEdit that provides a context menu for inserting tag tokens.
class ConestogaLineEdit(QtWidgets.QLineEdit):
    TYPE_PLAYBLAST_OUTPUT_PATH = 0
    TYPE_PLAYBLAST_OUTPUT_FILENAME = 1
    TYPE_SHOT_MASK_LABEL = 2

    PLAYBLAST_OUTPUT_PATH_LOOKUP = [("Project", "{project}"), ("Temp", "{temp}")]
    PLAYBLAST_OUTPUT_FILENAME_LOOKUP = [("Scene Name", "{scene}"), ("Camera Name", "{camera}"), ("Timestamp", "{timestamp}")]
    SHOT_MASK_LABEL_LOOKUP = [
        ("Scene Name", "{scene}"),
        ("Frame Counter", "{counter}"),
        ("Camera Name", "{camera}"), 
        ("Focal Length", "{focal_length}"),
        ("Logo", "{logo}"), 
        ("Image", "{image=<image_path>}"),
        ("User Name", "{username}"), 
        ("Date", "{date}")
    ]

    def __init__(self, le_type, parent=None):
        super(ConestogaLineEdit, self).__init__(parent)
        self.le_type = le_type
        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

    def show_context_menu(self, pos):
        context_menu = QtWidgets.QMenu(self)
        action = context_menu.addAction("Insert {tag}")
        action.setEnabled(False)
        context_menu.addSeparator()

        lookup = []
        if self.le_type == ConestogaLineEdit.TYPE_PLAYBLAST_OUTPUT_PATH:
            lookup.extend(self.PLAYBLAST_OUTPUT_PATH_LOOKUP)
            lookup.extend(ConestogaPlayblastCustomPresets.PLAYBLAST_OUTPUT_PATH_LOOKUP)
        elif self.le_type == ConestogaLineEdit.TYPE_PLAYBLAST_OUTPUT_FILENAME:
            lookup.extend(self.PLAYBLAST_OUTPUT_FILENAME_LOOKUP)
            lookup.extend(ConestogaPlayblastCustomPresets.PLAYBLAST_OUTPUT_FILENAME_LOOKUP)
        elif self.le_type == ConestogaLineEdit.TYPE_SHOT_MASK_LABEL:
            lookup.extend(self.SHOT_MASK_LABEL_LOOKUP)
            lookup.extend(ConestogaShotMaskCustomPresets.SHOT_MASK_LABEL_LOOKUP)

        for item in lookup:
            action = context_menu.addAction(item[0])
            action.setData(item[1])
            action.triggered.connect(self.on_context_menu_item_selected)

        context_menu.exec_(self.mapToGlobal(pos))

    def on_context_menu_item_selected(self):
        self.insert(self.sender().data())

class ConestogaFormLayout(QtWidgets.QGridLayout):
    def __init__(self, parent=None):
        super(ConestogaFormLayout, self).__init__(parent)
        self.setContentsMargins(0, 0, 0, 8)
        self.setColumnMinimumWidth(0, 80)
        self.setHorizontalSpacing(6)

    def addWidgetRow(self, row, label, widget):
        self.addWidget(QtWidgets.QLabel(label), row, 0, QtCore.Qt.AlignRight)
        self.addWidget(widget, row, 1)

    def addLayoutRow(self, row, label, layout):
        self.addWidget(QtWidgets.QLabel(label), row, 0, QtCore.Qt.AlignRight)
        self.addLayout(layout, row, 1)

#-------------------------------------------------------------------------
# Collapsible Group Widgets (for organizing UI sections)
#-------------------------------------------------------------------------
class ConestogaCollapsibleGrpHeader(QtWidgets.QWidget):
    clicked = QtCore.Signal()
    def __init__(self, text, parent=None):
        super(ConestogaCollapsibleGrpHeader, self).__init__(parent)
        self.setAutoFillBackground(True)
        self.set_background_color(None)
        self.collapsed_pixmap = QtGui.QPixmap(":teRightArrow.png")
        self.expanded_pixmap = QtGui.QPixmap(":teDownArrow.png")
        self.icon_label = QtWidgets.QLabel()
        self.icon_label.setFixedWidth(self.collapsed_pixmap.width())
        self.icon_label.setPixmap(self.collapsed_pixmap)
        self.icon_label.setAlignment(QtCore.Qt.AlignTop)
        self.text_label = QtWidgets.QLabel()
        self.text_label.setTextFormat(QtCore.Qt.RichText)
        self.text_label.setAlignment(QtCore.Qt.AlignLeft)
        self.text_label.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(4,4,4,4)
        layout.addWidget(self.icon_label)
        layout.addWidget(self.text_label)
        self.set_text(text)
        self.set_expanded(False)
        
    def set_text(self, text):
        self.text_label.setText("<b>{0}</b>".format(text))
        
    def set_background_color(self, color):
        if not color:
            color = QtWidgets.QPushButton().palette().color(QtGui.QPalette.Button)
        pal = self.palette()
        pal.setColor(QtGui.QPalette.Window, color)
        self.setPalette(pal)
        
    def is_expanded(self):
        return getattr(self, "_expanded", False)
        
    def set_expanded(self, expanded):
        self._expanded = expanded
        self.icon_label.setPixmap(self.expanded_pixmap if expanded else self.collapsed_pixmap)
        
    def mouseReleaseEvent(self, event):
        self.clicked.emit()

class ConestogaCollapsibleGrpWidget(QtWidgets.QWidget):
    collapsed_state_changed = QtCore.Signal()
    
    def __init__(self, text, parent=None):
        super(ConestogaCollapsibleGrpWidget, self).__init__(parent)
        self.append_stretch_on_collapse = False
        self.stretch_appended = False
        
        self.header_wdg = ConestogaCollapsibleGrpHeader(text)
        self.header_wdg.clicked.connect(self.on_header_clicked)
        
        self.body_wdg = QtWidgets.QWidget()
        self.body_wdg.setAutoFillBackground(True)
        
        palette = self.body_wdg.palette()
        palette.setColor(QtGui.QPalette.Window, palette.color(QtGui.QPalette.Window).lighter(110))
        self.body_wdg.setPalette(palette)
        
        self.body_layout = QtWidgets.QVBoxLayout(self.body_wdg)
        self.body_layout.setContentsMargins(4,2,4,2)
        self.body_layout.setSpacing(3)
        self.body_layout.setAlignment(QtCore.Qt.AlignTop)
        
        self.main_layout = QtWidgets.QVBoxLayout(self)
        self.main_layout.setContentsMargins(0,0,0,0)
        self.main_layout.addWidget(self.header_wdg)
        self.main_layout.addWidget(self.body_wdg)
        
        self.set_expanded(True)
        
    def add_widget(self, widget):
        self.body_layout.addWidget(widget)
        
    def add_layout(self, layout):
        self.body_layout.addLayout(layout)
        
    def set_expanded(self, expanded):
        self.header_wdg.set_expanded(expanded)
        self.body_wdg.setVisible(expanded)
        
        if self.append_stretch_on_collapse:
            if expanded:
                if self.stretch_appended:
                    self.main_layout.takeAt(self.main_layout.count() - 1)
                    self.stretch_appended = False
            elif not self.stretch_appended:
                self.main_layout.addStretch()
                self.stretch_appended = True
                
    def is_expanded(self):
        return self.header_wdg.is_expanded()
        
    def set_collapsed(self, collapsed):
        self.set_expanded(not collapsed)
        
    def is_collapsed(self):
        return not self.header_wdg.is_expanded()
        
    def set_header_background_color(self, color):
        self.header_wdg.set_background_color(color)
        
    def on_header_clicked(self):
        self.set_expanded(not self.header_wdg.is_expanded())
        self.collapsed_state_changed.emit()

class ConestogaColorButton(QtWidgets.QWidget):
    color_changed = QtCore.Signal()

    def __init__(self, color=(1.0, 1.0, 1.0), parent=None):
        super(ConestogaColorButton, self).__init__(parent)
        self.setObjectName("ConestogaColorButton")
        self.create_control()
        self.set_size(50, 16)
        self.set_color(color)

    def create_control(self):
        window = cmds.window()
        color_slider_name = cmds.colorSliderGrp()

        self._color_slider_obj = omui.MQtUtil.findControl(color_slider_name)
        if self._color_slider_obj:
            if sys.version_info.major >= 3:
                self._color_slider_widget = wrapInstance(int(self._color_slider_obj), QtWidgets.QWidget)
            else:
                self._color_slider_widget = wrapInstance(long(self._color_slider_obj), QtWidgets.QWidget)

            main_layout = QtWidgets.QVBoxLayout(self)
            main_layout.setObjectName("main_layout")
            main_layout.setContentsMargins(0, 0, 0, 0)
            main_layout.addWidget(self._color_slider_widget)

            self._slider_widget = self._color_slider_widget.findChild(QtWidgets.QWidget, "slider")
            if self._slider_widget:
                self._slider_widget.hide()

            self._color_widget = self._color_slider_widget.findChild(QtWidgets.QWidget, "port")

            cmds.colorSliderGrp(self.get_full_name(), e=True, changeCommand=partial(self.on_color_changed))

        cmds.deleteUI(window, window=True)

    def get_full_name(self):
        if sys.version_info.major >= 3:
            return omui.MQtUtil.fullName(int(self._color_slider_obj))
        else:
            return omui.MQtUtil.fullName(long(self._color_slider_obj))

    def set_size(self, width, height):
        scale_value = ConestogaPlayblastUtils.dpi_real_scale_value()
        self._color_slider_widget.setFixedWidth(int(width * scale_value))
        self._color_widget.setFixedHeight(int(height * scale_value))

    def set_color(self, color):
        cmds.colorSliderGrp(self.get_full_name(), e=True, rgbValue=(color[0], color[1], color[2]))
        self.on_color_changed()

    def get_color(self):
        return cmds.colorSliderGrp(self.get_full_name(), q=True, rgbValue=True)

    def on_color_changed(self, *args):
        self.color_changed.emit()

class ConestogaCameraSelectDialog(QtWidgets.QDialog):
    def __init__(self, parent):
        super(ConestogaCameraSelectDialog, self).__init__(parent)
        self.setWindowTitle("Camera Select")
        self.setModal(True)

        self.camera_list_label = QtWidgets.QLabel()
        self.camera_list_label.setVisible(False)

        self.camera_list_wdg = QtWidgets.QListWidget()
        self.camera_list_wdg.doubleClicked.connect(self.accept)

        self.select_btn = QtWidgets.QPushButton("Select")
        self.select_btn.clicked.connect(self.accept)

        self.cancel_btn = QtWidgets.QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.close)

        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(self.select_btn)
        button_layout.addWidget(self.cancel_btn)

        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(2, 4, 2, 2)
        main_layout.setSpacing(4)
        main_layout.addWidget(self.camera_list_label)
        main_layout.addWidget(self.camera_list_wdg)
        main_layout.addLayout(button_layout)

    def set_multi_select_enabled(self, enabled):
        if enabled:
            self.camera_list_wdg.setSelectionMode(QtWidgets.QListWidget.ExtendedSelection)
        else:
            self.camera_list_wdg.setSelectionMode(QtWidgets.QListWidget.SingleSelection)

    def set_camera_list_text(self, text):
        self.camera_list_label.setText(text)
        self.camera_list_label.setVisible(True)

    def set_select_btn_text(self, text):
        self.select_btn.setText(text)

    def refresh_list(self, selected=[], include_defaults=True, user_created_first=True, prepend=[], append=[]):
        self.camera_list_wdg.clear()

        if prepend:
            self.camera_list_wdg.addItems(prepend)

        self.camera_list_wdg.addItems(ConestogaPlayblastUtils.cameras_in_scene(include_defaults, user_created_first))

        if append:
            self.camera_list_wdg.addItems(append)

        if selected:
            for text in selected:
                items = self.camera_list_wdg.findItems(text, QtCore.Qt.MatchCaseSensitive)
                if len(items) > 0:
                    self.camera_list_wdg.setCurrentItem(items[0], QtCore.QItemSelectionModel.Select)

    def get_selected(self):
        selected = []
        items = self.camera_list_wdg.selectedItems()
        for item in items:
            selected.append(item.text())
        return selected

#-------------------------------------------------------------------------
# Encoder and Visibility Dialog Classes
#-------------------------------------------------------------------------
class ConestogaPlayblastEncoderSettingsDialog(QtWidgets.QDialog):
    ENCODER_PAGES = {
        "h264": 0,
        "Image": 1,
    }

    H264_QUALITIES = [
        "Very High",
        "High",
        "Medium",
        "Low",
    ]

    def __init__(self, parent):
        super(ConestogaPlayblastEncoderSettingsDialog, self).__init__(parent)
        self.setWindowTitle("Encoder Settings")
        self.setWindowFlags(self.windowFlags() ^ QtCore.Qt.WindowContextHelpButtonHint)
        self.setModal(True)
        self.setMinimumWidth(220)
        self.create_widgets()
        self.create_layouts()
        self.create_connections()

    def create_widgets(self):
        # h264
        self.h264_quality_combo = QtWidgets.QComboBox()
        self.h264_quality_combo.addItems(self.H264_QUALITIES)

        self.h264_preset_combo = QtWidgets.QComboBox()
        self.h264_preset_combo.addItems([
            "veryslow", "slow", "medium", "fast", "faster", "ultrafast"
        ])

        h264_layout = QtWidgets.QFormLayout()
        h264_layout.addRow("Quality:", self.h264_quality_combo)
        h264_layout.addRow("Preset:", self.h264_preset_combo)

        h264_settings_wdg = QtWidgets.QGroupBox("h264 Options")
        h264_settings_wdg.setLayout(h264_layout)

        # image
        self.image_quality_sb = QtWidgets.QSpinBox()
        self.image_quality_sb.setMinimumWidth(40)
        self.image_quality_sb.setButtonSymbols(QtWidgets.QSpinBox.NoButtons)
        self.image_quality_sb.setMinimum(1)
        self.image_quality_sb.setMaximum(100)

        image_layout = QtWidgets.QFormLayout()
        image_layout.addRow("Quality:", self.image_quality_sb)

        image_settings_wdg = QtWidgets.QGroupBox("Image Options")
        image_settings_wdg.setLayout(image_layout)

        self.settings_stacked_wdg = QtWidgets.QStackedWidget()
        self.settings_stacked_wdg.addWidget(h264_settings_wdg)
        self.settings_stacked_wdg.addWidget(image_settings_wdg)

        self.accept_btn = QtWidgets.QPushButton("Accept")
        self.cancel_btn = QtWidgets.QPushButton("Cancel")

    def create_layouts(self):
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(self.accept_btn)
        button_layout.addWidget(self.cancel_btn)

        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(2, 2, 2, 2)
        main_layout.setSpacing(4)
        main_layout.addWidget(self.settings_stacked_wdg)
        main_layout.addLayout(button_layout)

    def create_connections(self):
        self.accept_btn.clicked.connect(self.accept)
        self.cancel_btn.clicked.connect(self.close)

    def set_page(self, page):
        if page in self.ENCODER_PAGES:
            self.settings_stacked_wdg.setCurrentIndex(self.ENCODER_PAGES[page])
            return True
        return False

    def set_h264_settings(self, quality, preset):
        self.h264_quality_combo.setCurrentText(quality)
        self.h264_preset_combo.setCurrentText(preset)

    def get_h264_settings(self):
        return {
            "quality": self.h264_quality_combo.currentText(),
            "preset": self.h264_preset_combo.currentText(),
        }

    def set_image_settings(self, quality):
        self.image_quality_sb.setValue(quality)

    def get_image_settings(self):
        return {
            "quality": self.image_quality_sb.value(),
        }
        
class ConestogaPlayblastVisibilityDialog(QtWidgets.QDialog):
    VIEWPORT_VISIBILITY_LOOKUP = [
        ["Controllers", "controllers"],
        ["NURBS Curves", "nurbsCurves"],
        ["NURBS Surfaces", "nurbsSurfaces"],
        ["NURBS CVs", "cv"],
        ["NURBS Hulls", "hulls"],
        ["Polygons", "polymeshes"],
        ["Subdiv Surfaces", "subdivSurfaces"],
        ["Planes", "planes"],
        ["Lights", "lights"],
        ["Cameras", "cameras"],
        ["Image Planes", "imagePlane"],
        ["Joints", "joints"],
        ["IK Handles", "ikHandles"],
        ["Deformers", "deformers"],
        ["Dynamics", "dynamics"],
        ["Particle Instancers", "particleInstancers"],
        ["Fluids", "fluids"],
        ["Hair Systems", "hairSystems"],
        ["Follicles", "follicles"],
        ["nCloths", "nCloths"],
        ["nParticles", "nParticles"],
        ["nRigids", "nRigids"],
        ["Dynamic Constraints", "dynamicConstraints"],
        ["Locators", "locators"],
        ["Dimensions", "dimensions"],
        ["Pivots", "pivots"],
        ["Handles", "handles"],
        ["Texture Placements", "textures"],
        ["Strokes", "strokes"],
        ["Motion Trails", "motionTrails"],
        ["Plugin Shapes", "pluginShapes"],
        ["Clip Ghosts", "clipGhosts"],
        ["Grease Pencil", "greasePencils"],
        ["Grid", "grid"],
        ["HUD", "hud"],
        ["Hold-Outs", "hos"],
        ["Selection Highlighting", "sel"],
    ]

    def __init__(self, parent):
        super(ConestogaPlayblastVisibilityDialog, self).__init__(parent)
        self.setWindowTitle("Customize Visibility")
        self.setWindowFlags(self.windowFlags() ^ QtCore.Qt.WindowContextHelpButtonHint)
        self.setModal(True)

        visibility_layout = QtWidgets.QGridLayout()
        index = 0
        self.visibility_checkboxes = []

        for i in range(len(self.VIEWPORT_VISIBILITY_LOOKUP)):
            checkbox = QtWidgets.QCheckBox(self.VIEWPORT_VISIBILITY_LOOKUP[i][0])
            visibility_layout.addWidget(checkbox, index // 3, index % 3)
            self.visibility_checkboxes.append(checkbox)
            index += 1

        visibility_grp = QtWidgets.QGroupBox("")
        visibility_grp.setLayout(visibility_layout)

        apply_btn = QtWidgets.QPushButton("Apply")
        apply_btn.clicked.connect(self.accept)

        cancel_btn = QtWidgets.QPushButton("Cancel")
        cancel_btn.clicked.connect(self.close)

        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(apply_btn)
        button_layout.addWidget(cancel_btn)

        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(4)
        main_layout.addWidget(visibility_grp)
        main_layout.addStretch()
        main_layout.addLayout(button_layout)

    def get_visibility_data(self):
        data = []
        for checkbox in self.visibility_checkboxes:
            data.append(checkbox.isChecked())
        return data

    def set_visibility_data(self, data):
        if len(self.visibility_checkboxes) != len(data):
            raise RuntimeError("Visibility property/data mismatch")
        for i in range(len(data)):
            self.visibility_checkboxes[i].setChecked(data[i])

#-------------------------------------------------------------------------
# Conestoga Playblast Class (core functionality)
#-------------------------------------------------------------------------
class ConestogaPlayblast(QtCore.QObject):
    DEFAULT_FFMPEG_PATH = ""

    RESOLUTION_PRESETS = [
        ["Render", ()],
    ]

    FRAME_RANGE_PRESETS = [
        "Animation",
        "Playback",
        "Render",
        "Camera",
    ]

    VIDEO_ENCODER_LOOKUP = {
        "mov": ["h264"],
        "mp4": ["h264"],
        "Image": ["jpg", "png", "tif"],
    }

    H264_QUALITIES = {
        "Very High": 18,
        "High": 20,
        "Medium": 23,
        "Low": 26,
    }

    H264_PRESETS = [
        "veryslow",
        "slow",
        "medium",
        "fast",
        "faster",
        "ultrafast",
    ]

    VIEWPORT_VISIBILITY_LOOKUP = [
        ["Controllers", "controllers"],
        ["NURBS Curves", "nurbsCurves"],
        ["NURBS Surfaces", "nurbsSurfaces"],
        ["NURBS CVs", "cv"],
        ["NURBS Hulls", "hulls"],
        ["Polygons", "polymeshes"],
        ["Subdiv Surfaces", "subdivSurfaces"],
        ["Planes", "planes"],
        ["Lights", "lights"],
        ["Cameras", "cameras"],
        ["Image Planes", "imagePlane"],
        ["Joints", "joints"],
        ["IK Handles", "ikHandles"],
        ["Deformers", "deformers"],
        ["Dynamics", "dynamics"],
        ["Particle Instancers", "particleInstancers"],
        ["Fluids", "fluids"],
        ["Hair Systems", "hairSystems"],
        ["Follicles", "follicles"],
        ["nCloths", "nCloths"],
        ["nParticles", "nParticles"],
        ["nRigids", "nRigids"],
        ["Dynamic Constraints", "dynamicConstraints"],
        ["Locators", "locators"],
        ["Dimensions", "dimensions"],
        ["Pivots", "pivots"],
        ["Handles", "handles"],
        ["Texture Placements", "textures"],
        ["Strokes", "strokes"],
        ["Motion Trails", "motionTrails"],
        ["Plugin Shapes", "pluginShapes"],
        ["Clip Ghosts", "clipGhosts"],
        ["Grease Pencil", "greasePencils"],
        ["Grid", "grid"],
        ["HUD", "hud"],
        ["Hold-Outs", "hos"],
        ["Selection Highlighting", "sel"],
    ]

    VIEWPORT_VISIBILITY_PRESETS = [
        ["Viewport", []],
    ]

    DEFAULT_CAMERA = None
    DEFAULT_RESOLUTION = "Render"
    DEFAULT_FRAME_RANGE = "Playback"

    DEFAULT_CONTAINER = "mp4"
    DEFAULT_ENCODER = "h264"
    DEFAULT_H264_QUALITY = "High"
    DEFAULT_H264_PRESET = "fast"
    DEFAULT_IMAGE_QUALITY = 100

    DEFAULT_VISIBILITY = "Viewport"

    DEFAULT_PADDING = 4

    DEFAULT_MAYA_LOGGING_ENABLED = False

    CAMERA_PLAYBLAST_START_ATTR = "playblastStart"
    CAMERA_PLAYBLAST_END_ATTR = "playblastEnd"

    output_logged = QtCore.Signal(str)

    def __init__(self):
        super(ConestogaPlayblast, self).__init__()

        self.set_maya_logging_enabled(ConestogaPlayblast.DEFAULT_MAYA_LOGGING_ENABLED)

        self.build_presets()

        self.set_camera(ConestogaPlayblast.DEFAULT_CAMERA)
        self.set_resolution(ConestogaPlayblast.DEFAULT_RESOLUTION)
        self.set_frame_range(ConestogaPlayblast.DEFAULT_FRAME_RANGE)

        self.set_encoding(ConestogaPlayblast.DEFAULT_CONTAINER, ConestogaPlayblast.DEFAULT_ENCODER)
        self.set_h264_settings(ConestogaPlayblast.DEFAULT_H264_QUALITY, ConestogaPlayblast.DEFAULT_H264_PRESET)
        self.set_image_settings(ConestogaPlayblast.DEFAULT_IMAGE_QUALITY)

        self.set_visibility(ConestogaPlayblast.DEFAULT_VISIBILITY)

        self.initialize_ffmpeg_process()

    def build_presets(self):
        self.resolution_preset_names = []
        self.resolution_presets = {}

        for preset in ConestogaPlayblast.RESOLUTION_PRESETS:
            self.resolution_preset_names.append(preset[0])
            self.resolution_presets[preset[0]] = preset[1]

        try:
            for preset in ConestogaPlayblastCustomPresets.RESOLUTION_PRESETS:
                self.resolution_preset_names.append(preset[0])
                self.resolution_presets[preset[0]] = preset[1]
        except:
            traceback.print_exc()
            self.log_error("Failed to add custom resolution presets. See script editor for details.")

        self.viewport_visibility_preset_names = []
        self.viewport_visibility_presets = {}

        for preset in ConestogaPlayblast.VIEWPORT_VISIBILITY_PRESETS:
            self.viewport_visibility_preset_names.append(preset[0])
            self.viewport_visibility_presets[preset[0]] = preset[1]

        try:
            for preset in ConestogaPlayblastCustomPresets.VIEWPORT_VISIBILITY_PRESETS:
                self.viewport_visibility_preset_names.append(preset[0])
                self.viewport_visibility_presets[preset[0]] = preset[1]
        except:
            traceback.print_exc()
            self.log_error("Failed to add custom viewport visibility presets. See script editor for details.")

    def set_maya_logging_enabled(self, enabled):
        self._log_to_maya = enabled

    def is_maya_logging_enabled(self):
        return self._log_to_maya

    def set_camera(self, camera):
        if camera and camera not in cmds.listCameras():
            self.log_error("Camera does not exist: {0}".format(camera))
            camera = None

        self._camera = camera

    def set_resolution(self, resolution):
        self._resolution_preset = None

        try:
            widthHeight = self.preset_to_resolution(resolution)
            self._resolution_preset = resolution
        except:
            widthHeight = resolution

        valid_resolution = True
        try:
            if not (isinstance(widthHeight[0], int) and isinstance(widthHeight[1], int)):
                valid_resolution = False
        except:
            valid_resolution = False

        if valid_resolution:
            if widthHeight[0] <=0 or widthHeight[1] <= 0:
                self.log_error("Invalid resolution: {0}. Values must be greater than zero.".format(widthHeight))
                return
        else:
            self.log_error("Invalid resoluton: {0}. Expected one of [int, int], {1}".format(widthHeight, ", ".join(self.resolution_preset_names)))
            return

        self._widthHeight = (widthHeight[0], widthHeight[1])

    def get_resolution_width_height(self):
        if self._resolution_preset:
            return self.preset_to_resolution(self._resolution_preset)

        return self._widthHeight

    def preset_to_resolution(self, resolution_preset_name):
        if resolution_preset_name == "Render":
            width = cmds.getAttr("defaultResolution.width")
            height = cmds.getAttr("defaultResolution.height")
            return (width, height)
        elif resolution_preset_name in self.resolution_preset_names:
            return self.resolution_presets[resolution_preset_name]
        else:
            raise RuntimeError("Invalid resolution preset: {0}".format(resolution_preset_name))

    def set_frame_range(self, frame_range):
        resolved_frame_range = self.resolve_frame_range(frame_range)
        if not resolved_frame_range:
            return

        self._frame_range_preset = None
        if frame_range in ConestogaPlayblast.FRAME_RANGE_PRESETS:
            self._frame_range_preset = frame_range

        self._start_frame = resolved_frame_range[0]
        self._end_frame = resolved_frame_range[1]

    def get_start_end_frame(self):
        if self._frame_range_preset:
            return self.preset_to_frame_range(self._frame_range_preset)

        return (self._start_frame, self._end_frame)

    def resolve_frame_range(self, frame_range):
        try:
            if type(frame_range) in [list, tuple]:
                start_frame = frame_range[0]
                end_frame = frame_range[1]
            else:
                start_frame, end_frame = self.preset_to_frame_range(frame_range)

            return (start_frame, end_frame)

        except:
            presets = []
            for preset in ConestogaPlayblast.FRAME_RANGE_PRESETS:
                presets.append("'{0}'".format(preset))
            self.log_error('Invalid frame range. Expected one of (start_frame, end_frame), {0}'.format(", ".join(presets)))

        return None

    def preset_to_frame_range(self, frame_range_preset):
        if frame_range_preset == "Render":
            start_frame = int(cmds.getAttr("defaultRenderGlobals.startFrame"))
            end_frame = int(cmds.getAttr("defaultRenderGlobals.endFrame"))
        elif frame_range_preset == "Playback":
            if mel.eval("timeControl -q -rangeVisible $gPlayBackSlider"):
                start_frame, end_frame = mel.eval("timeControl -q -rangeArray $gPlayBackSlider")
                end_frame = end_frame - 1
            else:
                start_frame = int(cmds.playbackOptions(q=True, minTime=True))
                end_frame = int(cmds.playbackOptions(q=True, maxTime=True))
        elif frame_range_preset == "Animation":
            start_frame = int(cmds.playbackOptions(q=True, animationStartTime=True))
            end_frame = int(cmds.playbackOptions(q=True, animationEndTime=True))
        elif frame_range_preset == "Camera":
            return self.preset_to_frame_range("Playback")
        else:
            raise RuntimeError("Invalid frame range preset: {0}".format(frame_range_preset))

        return (start_frame, end_frame)

    def set_visibility(self, visibility_data):
        if not visibility_data:
            visibility_data = []

        if not type(visibility_data) in [list, tuple]:
            visibility_data = self.preset_to_visibility(visibility_data)

            if visibility_data is None:
                return

        self._visibility = copy.copy(visibility_data)

    def get_visibility(self):
        if not self._visibility:
            return self.get_viewport_visibility()

        return self._visibility

    def preset_to_visibility(self, visibility_preset_name):
        if not visibility_preset_name in self.viewport_visibility_preset_names:
            self.log_error("Invalid visibility preset: {0}".format(visibility_preset_name))
            return None

        visibility_data = []

        preset_names = self.viewport_visibility_presets[visibility_preset_name]
        if preset_names:
            for lookup_item in ConestogaPlayblast.VIEWPORT_VISIBILITY_LOOKUP:
                visibility_data.append(lookup_item[0] in preset_names)

        return visibility_data

    def get_viewport_visibility(self):
        model_panel = self.get_viewport_panel()
        if not model_panel:
            return None

        viewport_visibility = []
        try:
            for item in ConestogaPlayblast.VIEWPORT_VISIBILITY_LOOKUP:
                kwargs = {item[1]: True}
                viewport_visibility.append(cmds.modelEditor(model_panel, q=True, **kwargs))
        except:
            traceback.print_exc()
            self.log_error("Failed to get active viewport visibility. See script editor for details.")
            return None

        return viewport_visibility

    def set_viewport_visibility(self, model_editor, visibility_flags):
        cmds.modelEditor(model_editor, e=True, **visibility_flags)

    def create_viewport_visibility_flags(self, visibility_data):
        visibility_flags = {}

        data_index = 0
        for item in ConestogaPlayblast.VIEWPORT_VISIBILITY_LOOKUP:
            visibility_flags[item[1]] = visibility_data[data_index]
            data_index += 1

        return visibility_flags

    def set_encoding(self, container_format, encoder):
        if container_format not in ConestogaPlayblast.VIDEO_ENCODER_LOOKUP.keys():
            self.log_error("Invalid container: {0}. Expected one of {1}".format(container_format, ConestogaPlayblast.VIDEO_ENCODER_LOOKUP.keys()))
            return

        if encoder not in ConestogaPlayblast.VIDEO_ENCODER_LOOKUP[container_format]:
            self.log_error("Invalid encoder: {0}. Expected one of {1}".format(encoder, ConestogaPlayblast.VIDEO_ENCODER_LOOKUP[container_format]))
            return

        self._container_format = container_format
        self._encoder = encoder

    def set_h264_settings(self, quality, preset):
        if not quality in ConestogaPlayblast.H264_QUALITIES.keys():
            self.log_error("Invalid h264 quality: {0}. Expected one of {1}".format(quality, ConestogaPlayblast.H264_QUALITIES.keys()))
            return

        if not preset in ConestogaPlayblast.H264_PRESETS:
            self.log_error("Invalid h264 preset: {0}. Expected one of {1}".format(preset, ConestogaPlayblast.H264_PRESETS))
            return

        self._h264_quality = quality
        self._h264_preset = preset

    def get_h264_settings(self):
        return {
            "quality": self._h264_quality,
            "preset": self._h264_preset,
        }

    def set_image_settings(self, quality):
        if quality > 0 and quality <= 100:
            self._image_quality = quality
        else:
            self.log_error("Invalid image quality: {0}. Expected value between 1-100")

    def get_image_settings(self):
        return {
            "quality": self._image_quality,
        }

    def execute(self, output_dir, filename, padding=4, overscan=False, show_ornaments=True, show_in_viewer=True, offscreen=False, overwrite=False, camera_override="", enable_camera_frame_range=False):
        ffmpeg_path = ConestogaPlayblastUtils.get_ffmpeg_path()
        if self.requires_ffmpeg() and not self.validate_ffmpeg(ffmpeg_path):
            self.log_error("ffmpeg executable is not configured. See script editor for details.")
            return

        temp_file_format = ConestogaPlayblastUtils.get_temp_file_format()
        temp_file_is_movie = temp_file_format == "movie"

        if temp_file_is_movie:
            if sys.platform == "win32":
                temp_file_extension = "avi"
            else:
                temp_file_extension = "mov"
        else:
            temp_file_extension = temp_file_format

        viewport_model_panel = self.get_viewport_panel()
        if not viewport_model_panel:
            self.log_error("An active viewport is not selected. Select a viewport and retry.")
            return

        if not output_dir:
            self.log_error("Output directory path not set")
            return
        if not filename:
            self.log_error("Output file name not set")
            return

        # Store original camera
        orig_camera = self.get_active_camera()

        if camera_override:
            camera = camera_override
        else:
            camera = self._camera

        if not camera:
            camera = orig_camera

        if not camera in cmds.listCameras():
            self.log_error("Camera does not exist: {0}".format(camera))
            return

        output_dir = self.resolve_output_directory_path(output_dir)
        filename = self.resolve_output_filename(filename, camera)

        if padding <= 0:
            padding = ConestogaPlayblast.DEFAULT_PADDING

        if self.requires_ffmpeg():
            output_path = os.path.normpath(os.path.join(output_dir, "{0}.{1}".format(filename, self._container_format)))
            if not overwrite and os.path.exists(output_path):
                self.log_error("Output file already exists. Enable overwrite to ignore.")
                return

            playblast_output_dir = "{0}/playblast_temp".format(output_dir)
            playblast_output = os.path.normpath(os.path.join(playblast_output_dir, filename))
            force_overwrite = True
            viewer = False
            quality = 100

            if temp_file_is_movie:
                format_ = "movie"
                compression = None
                index_from_zero = False
            else:
                format_ = "image"
                compression = temp_file_format
                index_from_zero = True
        else:
            playblast_output = os.path.normpath(os.path.join(output_dir, filename))
            force_overwrite = overwrite
            format_ = "image"
            compression = self._encoder
            quality = self._image_quality
            index_from_zero = False
            viewer = show_in_viewer

        widthHeight = self.get_resolution_width_height()
        start_frame, end_frame = self.get_start_end_frame()

        if enable_camera_frame_range:
            if cmds.attributeQuery(ConestogaPlayblast.CAMERA_PLAYBLAST_START_ATTR, node=camera, exists=True) and cmds.attributeQuery(ConestogaPlayblast.CAMERA_PLAYBLAST_END_ATTR, node=camera, exists=True):
                try:
                    start_frame = int(cmds.getAttr("{0}.{1}".format(camera, ConestogaPlayblast.CAMERA_PLAYBLAST_START_ATTR)))
                    end_frame = int(cmds.getAttr("{0}.{1}".format(camera, ConestogaPlayblast.CAMERA_PLAYBLAST_END_ATTR)))

                    self.log_output("Camera frame range enabled for '{0}' camera: ({1}, {2})\n".format(camera, start_frame, end_frame))
                except:
                    self.log_warning("Camera frame range disabled. Invalid attribute type(s) on '{0}' camera (expected integer or float). Defaulting to Playback range.\n".format(camera))
            else:
                self.log_warning("Camera frame range disabled. Attributes '{0}' and '{1}' do not exist on '{2}' camera. Defaulting to Playback range.\n".format(ConestogaPlayblast.CAMERA_PLAYBLAST_START_ATTR, ConestogaPlayblast.CAMERA_PLAYBLAST_END_ATTR, camera))

        if start_frame > end_frame:
            self.log_error("Invalid frame range. The start frame ({0}) is greater than the end frame ({1}).".format(start_frame, end_frame))
            return

        options = {
            "filename": playblast_output,
            "widthHeight": widthHeight,
            "percent": 100,
            "startTime": start_frame,
            "endTime": end_frame,
            "clearCache": True,
            "forceOverwrite": force_overwrite,
            "format": format_,
            "compression": compression,
            "quality": quality,
            "indexFromZero": index_from_zero,
            "framePadding": padding,
            "showOrnaments": show_ornaments,
            "viewer": viewer,
            "offScreen": offscreen
        }

        if temp_file_is_movie:
            if self.use_trax_sounds():
                options["useTraxSounds"] = True
            else:
                sound_node = self.get_sound_node()
                if sound_node:
                    options["sound"] = sound_node

        self.log_output("Starting '{0}' playblast...".format(camera))
        self.log_output("Playblast options: {0}\n".format(options))
        QtCore.QCoreApplication.processEvents()

        self.set_active_camera(camera)

        orig_visibility_flags = self.create_viewport_visibility_flags(self.get_viewport_visibility())
        playblast_visibility_flags = self.create_viewport_visibility_flags(self.get_visibility())

        model_editor = cmds.modelPanel(viewport_model_panel, q=True, modelEditor=True)
        self.set_viewport_visibility(model_editor, playblast_visibility_flags)

        # Store original camera settings
        if not overscan:
            overscan_attr = "{0}.overscan".format(camera)
            orig_overscan = cmds.getAttr(overscan_attr)
            cmds.setAttr(overscan_attr, 1.0)

        playblast_failed = False
        try:
            cmds.playblast(**options)
        except:
            traceback.print_exc()
            self.log_error("Failed to create playblast. See script editor for details.")
            playblast_failed = True
        finally:
            # Restore original camera settings
            if not overscan:
                cmds.setAttr(overscan_attr, orig_overscan)

            # Restore original viewport settings
            self.set_active_camera(orig_camera)
            self.set_viewport_visibility(model_editor, orig_visibility_flags)

        if playblast_failed:
            return

        if self.requires_ffmpeg():
            if temp_file_is_movie:
                source_path = "{0}/{1}.{2}".format(playblast_output_dir, filename, temp_file_extension)
            else:
                source_path = "{0}/{1}.%0{2}d.{3}".format(playblast_output_dir, filename, padding, temp_file_extension)

            if self._encoder == "h264":
                if temp_file_is_movie:
                    self.transcode_h264(ffmpeg_path, source_path, output_path)
                else:
                    self.encode_h264(ffmpeg_path, source_path, output_path, start_frame)
            else:
                self.log_error("Encoding failed. Unsupported encoder ({0}) for container ({1}).".format(self._encoder, self._container_format))
                self.remove_temp_dir(playblast_output_dir, temp_file_extension)
                return

            self.remove_temp_dir(playblast_output_dir, temp_file_extension)

            if show_in_viewer:
                self.open_in_viewer(output_path)

        self.log_output("Playblast complete\n")


    def remove_temp_dir(self, temp_dir_path, temp_file_extension):
        playblast_dir = QtCore.QDir(temp_dir_path)
        playblast_dir.setNameFilters(["*.{0}".format(temp_file_extension)])
        playblast_dir.setFilter(QtCore.QDir.Files)
        for f in playblast_dir.entryList():
            playblast_dir.remove(f)

        if not playblast_dir.rmdir(temp_dir_path):
            self.log_warning("Failed to remove temporary directory: {0}".format(temp_dir_path))

    def open_in_viewer(self, path):
        if not os.path.exists(path):
            self.log_error("Failed to open in viewer. File does not exists: {0}".format(path))
            return

        if self._container_format in ("mov", "mp4") and cmds.optionVar(exists="PlayblastCmdQuicktime"):
            executable_path = cmds.optionVar(q="PlayblastCmdQuicktime")
            if executable_path:
                QtCore.QProcess.startDetached(executable_path, [path])
                return

        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(path))

    def requires_ffmpeg(self):
        return self._container_format != "Image"

    def validate_ffmpeg(self, ffmpeg_path):
        if not ffmpeg_path:
            self.log_error("ffmpeg executable path not set")
            return False
        elif not os.path.exists(ffmpeg_path):
            self.log_error("ffmpeg executable path does not exist: {0}".format(ffmpeg_path))
            return False
        elif os.path.isdir(ffmpeg_path):
            self.log_error("Invalid ffmpeg path: {0}".format(ffmpeg_path))
            return False

        return True

    def initialize_ffmpeg_process(self):
        self._ffmpeg_process = QtCore.QProcess()
        self._ffmpeg_process.readyReadStandardError.connect(self.process_ffmpeg_output)

    def execute_ffmpeg_command(self, program, arguments):
        self._ffmpeg_process.start(program, arguments)
        if self._ffmpeg_process.waitForStarted():
            while self._ffmpeg_process.state() != QtCore.QProcess.NotRunning:
                QtCore.QCoreApplication.processEvents()
                QtCore.QThread.usleep(10)

    def process_ffmpeg_output(self):
        byte_array_output = self._ffmpeg_process.readAllStandardError()

        if sys.version_info.major < 3:
            output = str(byte_array_output)
        else:
            output = str(byte_array_output, "utf-8")

        self.log_output(output)


    def encode_h264(self, ffmpeg_path, source_path, output_path, start_frame):
        self.log_output("Starting h264 encoding...")
        self.log_output("ffmpeg path: {0}".format(ffmpeg_path))

        framerate = self.get_frame_rate()

        audio_file_path, audio_frame_offset = self.get_audio_attributes()
        if audio_file_path:
            audio_offset = self.get_audio_offset_in_sec(start_frame, audio_frame_offset, framerate)

        crf = ConestogaPlayblast.H264_QUALITIES[self._h264_quality]
        preset = self._h264_preset

        arguments = []
        arguments.append("-y")
        arguments.extend(["-framerate", "{0}".format(framerate), "-i", source_path])

        if audio_file_path:
            arguments.extend(["-ss", "{0}".format(audio_offset), "-i", audio_file_path])

        arguments.extend(["-c:v", "libx264", "-crf:v", "{0}".format(crf), "-preset:v", preset, "-profile:v", "high", "-pix_fmt", "yuv420p"])

        if audio_file_path:
            arguments.extend(["-filter_complex", "[1:0] apad", "-shortest"])

        arguments.append(output_path)

        self.log_output("ffmpeg arguments: {0}\n".format(arguments))

        self.execute_ffmpeg_command(ffmpeg_path, arguments)

    def transcode_h264(self, ffmpeg_path, source_path, output_path):
        self.log_output("Starting h264 transcoding...")
        self.log_output("ffmpeg path: {0}".format(ffmpeg_path))

        crf = ConestogaPlayblast.H264_QUALITIES[self._h264_quality]
        preset = self._h264_preset

        arguments = []
        arguments.append("-y")
        arguments.extend(["-i", source_path])
        arguments.extend(["-c:v", "libx264", "-crf:v", "{0}".format(crf), "-preset:v", preset, "-profile:v", "high", "-pix_fmt", "yuv420p"])
        arguments.append(output_path)

        self.log_output("ffmpeg arguments: {0}\n".format(arguments))

        self.execute_ffmpeg_command(ffmpeg_path, arguments)


    def get_frame_rate(self):
        rate_str = cmds.currentUnit(q=True, time=True)

        if rate_str == "game":
            frame_rate = 15.0
        elif rate_str == "film":
            frame_rate = 24.0
        elif rate_str == "pal":
            frame_rate = 25.0
        elif rate_str == "ntsc":
            frame_rate = 30.0
        elif rate_str == "show":
            frame_rate = 48.0
        elif rate_str == "palf":
            frame_rate = 50.0
        elif rate_str == "ntscf":
            frame_rate = 60.0
        elif rate_str.endswith("fps"):
            frame_rate = float(rate_str[0:-3])
        else:
            raise RuntimeError("Unsupported frame rate: {0}".format(rate_str))

        return frame_rate

    def get_sound_node(self):
        return mel.eval("timeControl -q -sound $gPlayBackSlider;")

    def display_sound(self):
        return mel.eval("timeControl -q -displaySound $gPlayBackSlider;")

    def use_trax_sounds(self):
        return self.display_sound() and not self.get_sound_node()

    def get_audio_attributes(self):
        sound_node = self.get_sound_node()
        if sound_node:
            file_path = cmds.getAttr("{0}.filename".format(sound_node))
            file_info = QtCore.QFileInfo(file_path)
            if file_info.exists():
                offset = cmds.getAttr("{0}.offset".format(sound_node))

                return (file_path, offset)

        return (None, None)

    def get_audio_offset_in_sec(self, start_frame, audio_frame_offset, frame_rate):
        return (start_frame - audio_frame_offset) / frame_rate

    def resolve_output_directory_path(self, dir_path):
        dir_path = ConestogaPlayblastCustomPresets.parse_playblast_output_dir_path(dir_path)

        if "{project}" in dir_path:
            dir_path = dir_path.replace("{project}", self.get_project_dir_path())
        if "{temp}" in dir_path:
            temp_dir_path = ConestogaPlayblastUtils.get_temp_output_dir_path()

            if not temp_dir_path:
                self.log_warning("The {temp} directory path is not set")

            dir_path = dir_path.replace("{temp}", temp_dir_path)

        return dir_path

    def resolve_output_filename(self, filename, camera):
        filename = ConestogaPlayblastCustomPresets.parse_playblast_output_filename(filename)

        if "{scene}" in filename:
            filename = filename.replace("{scene}", self.get_scene_name())
        if "{timestamp}" in filename:
            filename = filename.replace("{timestamp}", self.get_timestamp())

        if "{camera}" in filename:
            new_camera_name = camera

            new_camera_name = new_camera_name.split(':')[-1]
            new_camera_name = new_camera_name.split('|')[-1]

            filename = filename.replace("{camera}", new_camera_name)

        return filename

    def get_project_dir_path(self):
        return cmds.workspace(q=True, rootDirectory=True)

    def get_scene_name(self):
        scene_name = cmds.file(q=True, sceneName=True, shortName=True)
        if scene_name:
            scene_name = os.path.splitext(scene_name)[0]
        else:
            scene_name = "untitled"

        return scene_name

    def get_timestamp(self):
        return "{0}".format(int(time.time()))

    def get_viewport_panel(self):
        model_panel = cmds.getPanel(withFocus=True)
        try:
            cmds.modelPanel(model_panel, q=True, modelEditor=True)
        except:
            return None

        return model_panel

    def get_active_camera(self):
        model_panel = self.get_viewport_panel()
        if not model_panel:
            self.log_error("Failed to get active camera. A viewport is not active.")
            return None

        return cmds.modelPanel(model_panel, q=True, camera=True)

    def set_active_camera(self, camera):
        model_panel = self.get_viewport_panel()
        if model_panel:
            mel.eval("lookThroughModelPanel {0} {1}".format(camera, model_panel))
        else:
            self.log_error("Failed to set active camera. A viewport is not active.")


    def log_error(self, text):
        if self._log_to_maya:
            om.MGlobal.displayError("[ConestogaPlayblast] {0}".format(text))

        self.output_logged.emit("[ERROR] {0}".format(text))  # pylint: disable=E1101

    def log_warning(self, text):
        if self._log_to_maya:
            om.MGlobal.displayWarning("[ConestogaPlayblast] {0}".format(text))

        self.output_logged.emit("[WARNING] {0}".format(text))  # pylint: disable=E1101

    def log_output(self, text):
        if self._log_to_maya:
            om.MGlobal.displayInfo(text)

        self.output_logged.emit(text)  # pylint: disable=E1101

#-------------------------------------------------------------------------
# Conestoga Shot Mask Class
#-------------------------------------------------------------------------
class ConestogaShotMask(object):

    NODE_NAME = "ConestogaShotMask"

    TRANSFORM_NODE_NAME = "cshotmask"
    SHAPE_NODE_NAME = "cshotmaskShape"

    DEFAULT_BORDER_COLOR = [0.0, 0.0, 0.0, 1.0]
    DEFAULT_LABEL_COLOR = [1.0, 1.0, 1.0, 1.0]

    LABEL_COUNT = 6
    MIN_COUNTER_PADDING = 1
    MAX_COUNTER_PADDING = 6
    DEFAULT_COUNTER_PADDING = 4

    OPT_VAR_CAMERA_NAME = "cstgShotMaskCameraName"
    OPT_VAR_LABEL_TEXT = "cstgShotMaskLabelText"
    OPT_VAR_LABEL_FONT = "cstgShotMaskLabelFont"
    OPT_VAR_LABEL_COLOR = "cstgShotMaskLabelColor"
    OPT_VAR_LABEL_SCALE = "cstgShotMaskLabelScale"
    OPT_VAR_BORDER_VISIBLE = "cstgShotMaskBorderVisible"
    OPT_VAR_BORDER_COLOR = "cstgShotMaskBorderColor"
    OPT_VAR_BORDER_SCALE = "cstgShotMaskBorderScale"
    OPT_VAR_BORDER_AR_ENABLED = "cstgShotMaskBorderAREnabled"
    OPT_VAR_BORDER_AR = "cstgShotMaskBorderAR"
    OPT_VAR_COUNTER_PADDING = "cstgShotMaskCounterPadding"


    @classmethod
    def create_mask(cls):
        if not ConestogaPlayblastUtils.load_plugin():
            return

        if not cls.get_mask():
            selection = cmds.ls(sl=True)

            transform_node = cmds.createNode("transform", name=cls.TRANSFORM_NODE_NAME)
            cmds.createNode(cls.NODE_NAME, name=cls.SHAPE_NODE_NAME, parent=transform_node)

            cmds.select(selection, r=True)

        cls.refresh_mask()

    @classmethod
    def delete_mask(cls):
        mask = cls.get_mask()
        if mask:
            transform = cmds.listRelatives(mask, fullPath=True, parent=True)
            if transform:
                cmds.delete(transform)
            else:
                cmds.delete(mask)

    @classmethod
    def get_mask(cls):
        if ConestogaPlayblastUtils.is_plugin_loaded():
            nodes = cmds.ls(type=cls.NODE_NAME)
            if len(nodes) > 0:
                return nodes[0]

        return None

    @classmethod
    def refresh_mask(cls):
        mask = cls.get_mask()
        if not mask:
            return

        cmds.setAttr("{0}.camera".format(mask), cls.get_camera_name(), type="string")

        try:
            label_text = cls.get_label_text()
            cmds.setAttr("{0}.topLeftText".format(mask), label_text[0], type="string")
            cmds.setAttr("{0}.topCenterText".format(mask), label_text[1], type="string")
            cmds.setAttr("{0}.topRightText".format(mask), label_text[2], type="string")
            cmds.setAttr("{0}.bottomLeftText".format(mask), label_text[3], type="string")
            cmds.setAttr("{0}.bottomCenterText".format(mask), label_text[4], type="string")
            cmds.setAttr("{0}.bottomRightText".format(mask), label_text[5], type="string")
        except:
            pass

        label_color = cls.get_label_color()
        cmds.setAttr("{0}.fontName".format(mask), cls.get_label_font(), type="string")
        cmds.setAttr("{0}.fontColor".format(mask), label_color[0], label_color[1], label_color[2], type="double3")
        cmds.setAttr("{0}.fontAlpha".format(mask), label_color[3])
        cmds.setAttr("{0}.fontScale".format(mask), cls.get_label_scale())

        border_visibility = cls.get_border_visible()
        border_color = cls.get_border_color()
        cmds.setAttr("{0}.topBorder".format(mask), border_visibility[0])
        cmds.setAttr("{0}.bottomBorder".format(mask), border_visibility[1])
        cmds.setAttr("{0}.borderColor".format(mask), border_color[0], border_color[1], border_color[2], type="double3")
        cmds.setAttr("{0}.borderAlpha".format(mask), border_color[3])
        cmds.setAttr("{0}.borderScale".format(mask), cls.get_border_scale())
        cmds.setAttr("{0}.aspectRatioBorders".format(mask), cls.is_border_aspect_ratio_enabled())
        cmds.setAttr("{0}.borderAspectRatio".format(mask), cls.get_border_aspect_ratio())

        cmds.setAttr("{0}.counterPadding".format(mask), cls.get_counter_padding())

    @classmethod
    def set_camera_name(cls, name):
        cmds.optionVar(sv=[cls.OPT_VAR_CAMERA_NAME, name])

    @classmethod
    def get_camera_name(cls):
        if cmds.optionVar(exists=cls.OPT_VAR_CAMERA_NAME):
            return cmds.optionVar(q=cls.OPT_VAR_CAMERA_NAME)
        else:
            return ""

    @classmethod
    def set_label_text(cls, text_array):
        array_len = len(text_array)
        if array_len != cls.LABEL_COUNT:
            om.MGlobal.displayError("Failed to set label text. Invalid number of text values in array: {0} (expected 6)".format(array_len))
            return

        cmds.optionVar(sv=[cls.OPT_VAR_LABEL_TEXT, text_array[0]])
        for i in range(1, array_len):
            cmds.optionVar(sva=[cls.OPT_VAR_LABEL_TEXT, text_array[i]])

    @classmethod
    def get_label_text(cls):
        if cmds.optionVar(exists=cls.OPT_VAR_LABEL_TEXT):
            return cmds.optionVar(q=cls.OPT_VAR_LABEL_TEXT)

        return ["", "{scene}", "", "{username}", "", "{counter}"]

    @classmethod
    def set_label_font(cls, font):
        cmds.optionVar(sv=[cls.OPT_VAR_LABEL_FONT, font])

    @classmethod
    def get_label_font(cls):
        if cmds.optionVar(exists=cls.OPT_VAR_LABEL_FONT):
            label_font = cmds.optionVar(q=cls.OPT_VAR_LABEL_FONT)
            if label_font:
                return label_font

        if cmds.about(win=True):
            return "Times New Roman"
        elif cmds.about(mac=True):
            return "Times New Roman-Regular"
        elif cmds.about(linux=True):
            return "Courier"
        else:
            return "Times-Roman"

    @classmethod
    def set_label_color(cls, red, green, blue, alpha):
        cmds.optionVar(fv=[cls.OPT_VAR_LABEL_COLOR, red])
        cmds.optionVar(fva=[cls.OPT_VAR_LABEL_COLOR, green])
        cmds.optionVar(fva=[cls.OPT_VAR_LABEL_COLOR, blue])
        cmds.optionVar(fva=[cls.OPT_VAR_LABEL_COLOR, alpha])

    @classmethod
    def get_label_color(cls):
        if cmds.optionVar(exists=cls.OPT_VAR_LABEL_COLOR):
            return cmds.optionVar(q=cls.OPT_VAR_LABEL_COLOR)
        else:
            return cls.DEFAULT_LABEL_COLOR

    @classmethod
    def set_label_scale(cls, scale):
        cmds.optionVar(fv=[cls.OPT_VAR_LABEL_SCALE, scale])

    @classmethod
    def get_label_scale(cls):
        if cmds.optionVar(exists=cls.OPT_VAR_LABEL_SCALE):
            return cmds.optionVar(q=cls.OPT_VAR_LABEL_SCALE)
        else:
            return 1.0

    @classmethod
    def set_border_visible(cls, top, bottom):
        cmds.optionVar(iv=[cls.OPT_VAR_BORDER_VISIBLE, top])
        cmds.optionVar(iva=[cls.OPT_VAR_BORDER_VISIBLE, bottom])

    @classmethod
    def get_border_visible(cls):
        if cmds.optionVar(exists=cls.OPT_VAR_BORDER_VISIBLE):
            border_visibility = cmds.optionVar(q=cls.OPT_VAR_BORDER_VISIBLE)
            try:
                if len(border_visibility) == 2:
                    return border_visibility
            except:
                pass

        return [1, 1]

    @classmethod
    def set_border_color(cls, red, green, blue, alpha):
        cmds.optionVar(fv=[cls.OPT_VAR_BORDER_COLOR, red])
        cmds.optionVar(fva=[cls.OPT_VAR_BORDER_COLOR, green])
        cmds.optionVar(fva=[cls.OPT_VAR_BORDER_COLOR, blue])
        cmds.optionVar(fva=[cls.OPT_VAR_BORDER_COLOR, alpha])

    @classmethod
    def get_border_color(cls):
        if cmds.optionVar(exists=cls.OPT_VAR_BORDER_COLOR):
            return cmds.optionVar(q=cls.OPT_VAR_BORDER_COLOR)
        else:
            return cls.DEFAULT_BORDER_COLOR

    @classmethod
    def set_border_scale(cls, scale):
        cmds.optionVar(fv=[cls.OPT_VAR_BORDER_SCALE, scale])

    @classmethod
    def get_border_scale(cls):
        if cmds.optionVar(exists=cls.OPT_VAR_BORDER_SCALE):
            return cmds.optionVar(q=cls.OPT_VAR_BORDER_SCALE)
        else:
            return 1.0

    @classmethod
    def set_border_aspect_ratio_enabled(cls, enabled):
        cmds.optionVar(iv=[cls.OPT_VAR_BORDER_AR_ENABLED, enabled])

    @classmethod
    def is_border_aspect_ratio_enabled(cls):
        if cmds.optionVar(exists=cls.OPT_VAR_BORDER_AR_ENABLED):
            return cmds.optionVar(q=cls.OPT_VAR_BORDER_AR_ENABLED)
        else:
            return 0

    @classmethod
    def set_border_aspect_ratio(cls, aspect_ratio):
        cmds.optionVar(fv=[cls.OPT_VAR_BORDER_AR, aspect_ratio])

    @classmethod
    def get_border_aspect_ratio(cls):
        if cmds.optionVar(exists=cls.OPT_VAR_BORDER_AR):
            return cmds.optionVar(q=cls.OPT_VAR_BORDER_AR)
        else:
            return 2.35

    @classmethod
    def set_counter_padding(cls, padding):
        cmds.optionVar(iv=[cls.OPT_VAR_COUNTER_PADDING, padding])

    @classmethod
    def get_counter_padding(cls):
        if cmds.optionVar(exists=cls.OPT_VAR_COUNTER_PADDING):
            pos = cmds.optionVar(q=cls.OPT_VAR_COUNTER_PADDING)
            if pos >= cls.MIN_COUNTER_PADDING and pos <= cls.MAX_COUNTER_PADDING:
                return pos

        return cls.DEFAULT_COUNTER_PADDING

    @classmethod
    def reset_settings(cls):
        cmds.optionVar(remove=cls.OPT_VAR_BORDER_COLOR)
        cmds.optionVar(remove=cls.OPT_VAR_BORDER_SCALE)
        cmds.optionVar(remove=cls.OPT_VAR_BORDER_VISIBLE)
        cmds.optionVar(remove=cls.OPT_VAR_BORDER_AR_ENABLED)
        cmds.optionVar(remove=cls.OPT_VAR_BORDER_AR)
        cmds.optionVar(remove=cls.OPT_VAR_CAMERA_NAME)
        cmds.optionVar(remove=cls.OPT_VAR_COUNTER_PADDING)
        cmds.optionVar(remove=cls.OPT_VAR_LABEL_COLOR)
        cmds.optionVar(remove=cls.OPT_VAR_LABEL_FONT)
        cmds.optionVar(remove=cls.OPT_VAR_LABEL_SCALE)
        cmds.optionVar(remove=cls.OPT_VAR_LABEL_TEXT)

#-------------------------------------------------------------------------
# Tab 1: Playblast Options
#-------------------------------------------------------------------------
class PlayblastTabWidget(QtWidgets.QWidget):
    artist_name_changed = QtCore.Signal(str)
    
    OPT_VAR_OUTPUT_DIR = "cstgPlayblastOutputDir"
    OPT_VAR_OUTPUT_FILENAME = "cstgPlayblastOutputFilename"
    OPT_VAR_FORCE_OVERWRITE = "cstgPlayblastForceOverwrite"

    OPT_VAR_CAMERA = "cstgPlayblastCamera"
    OPT_VAR_HIDE_DEFAULT_CAMERAS = "cstgPlayblastHideDefaultCameras"

    OPT_VAR_RESOLUTION_PRESET = "cstgPlayblastResolutionPreset"
    OPT_VAR_RESOLUTION_WIDTH = "cstgPlayblastResolutionWidth"
    OPT_VAR_RESOLUTION_HEIGHT = "cstgPlayblastResolutionHeight"

    OPT_VAR_FRAME_RANGE_PRESET = "cstgPlayblastFrameRangePreset"
    OPT_VAR_FRAME_RANGE_START = "cstgPlayblastFrameRangeStart"
    OPT_VAR_FRAME_RANGE_END = "cstgPlayblastFrameRangeEnd"

    OPT_VAR_ENCODING_CONTAINER = "cstgPlayblastEncodingContainer"
    OPT_VAR_ENCODING_VIDEO_CODEC = "cstgPlayblastEncodingVideoCodec"

    OPT_VAR_H264_QUALITY = "cstgPlayblastH264Quality"
    OPT_VAR_H264_PRESET = "cstgPlayblastH264Preset"

    OPT_VAR_IMAGE_QUALITY = "cstgPlayblastImageQuality"

    OPT_VAR_VISIBILITY_PRESET = "cstgPlayblastVisibilityPreset"
    OPT_VAR_VISIBILITY_DATA = "cstgPlayblastVisibilityData"

    OPT_VAR_OVERSCAN = "cstgPlayblastOverscan"
    OPT_VAR_ORNAMENTS = "cstgPlayblastOrnaments"
    OPT_VAR_OFFSCREEN = "cstgPlayblastOffscreen"
    OPT_VAR_SHOT_MASK = "cstgPlayblastShotMask"
    OPT_VAR_FIT_SHOT_MASK = "cstgPlayblastFitShotMask"
    OPT_VAR_VIEWER = "cstgPlayblastViewer"

    OPT_VAR_LOG_TO_SCRIPT_EDITOR = "cstgPlayblastLogToSE"

    # Name generator option vars
    OPT_VAR_ASSIGNMENT_NUMBER = "cstgPlayblastAssignmentNumber"
    OPT_VAR_LAST_NAME = "cstgPlayblastLastName"
    OPT_VAR_FIRST_NAME = "cstgPlayblastFirstName"
    OPT_VAR_VERSION_TYPE = "cstgPlayblastVersionType"
    OPT_VAR_VERSION_NUMBER = "cstgPlayblastVersionNumber"
    
    def __init__(self, parent=None):
        super(PlayblastTabWidget, self).__init__(parent)
        self.utils = ConestogaPlayblastUtils()
        self.scale = self.utils.dpi_real_scale_value()
        # Instantiate the core playblast functionality
        self._playblast = ConestogaPlayblast()
        self._encoder_settings_dialog = None
        self._visibility_dialog = None
        self.collapsed_state_changed = QtCore.Signal()
        self.init_ui()
        self.load_settings()

    def init_ui(self):
        # Output settings
        self.outputDirLE = ConestogaLineEdit(ConestogaLineEdit.TYPE_PLAYBLAST_OUTPUT_PATH)
        self.outputDirLE.setPlaceholderText("{project}/movies")
        self.selectOutputDirBtn = QtWidgets.QPushButton("...")
        self.selectOutputDirBtn.setToolTip("Select Output Directory")
        self.selectOutputDirBtn.setFixedWidth(int(24 * self.scale))
        self.selectOutputDirBtn.setFixedHeight(int(18 * self.scale))
        
        self.showFolderBtn = QtWidgets.QPushButton(QtGui.QIcon(":fileOpen.png"), "")
        self.showFolderBtn.setToolTip("Show in Folder")
        self.showFolderBtn.setFixedWidth(int(24 * self.scale))
        self.showFolderBtn.setFixedHeight(int(18 * self.scale))
        
        self.outputFilenameLE = ConestogaLineEdit(ConestogaLineEdit.TYPE_PLAYBLAST_OUTPUT_FILENAME)
        self.outputFilenameLE.setPlaceholderText("{scene}_{timestamp}")
        self.outputFilenameLE.setMaximumWidth(int(200 * self.scale))
        
        self.forceOverwriteCB = QtWidgets.QCheckBox("Force overwrite")
        
        # Name Generator
        self.assignmentSpin = QtWidgets.QSpinBox()
        self.assignmentSpin.setRange(1,99)
        self.assignmentSpin.setFixedWidth(int(50 * self.scale))
        
        self.lastNameLE = QtWidgets.QLineEdit()
        self.lastNameLE.setPlaceholderText("Last Name")
        
        self.firstNameLE = QtWidgets.QLineEdit()
        self.firstNameLE.setPlaceholderText("First Name")
        
        self.versionTypeCombo = QtWidgets.QComboBox()
        self.versionTypeCombo.addItems(["wip", "final"])
        
        self.versionNumberSpin = QtWidgets.QSpinBox()
        self.versionNumberSpin.setRange(1,99)
        self.versionNumberSpin.setFixedWidth(int(50 * self.scale))
        
        self.filenamePreviewLabel = QtWidgets.QLabel("A1_LastName_FirstName_wip_01.mov")
        self.filenamePreviewLabel.setStyleSheet("color: yellow; font-weight: bold;")
        
        self.generateFilenameBtn = QtWidgets.QPushButton("Generate Filename")
        self.resetNameGenBtn = QtWidgets.QPushButton("Reset")
        
        # Camera Selection
        self.cameraSelectCombo = QtWidgets.QComboBox()
        self.cameraSelectCombo.setMinimumWidth(int(100 * self.scale))
        
        self.hideDefaultCamsCB = QtWidgets.QCheckBox("Hide defaults")
        
        # Resolution Options
        self.resolutionPresetCombo = QtWidgets.QComboBox()
        self.resolutionPresetCombo.setMinimumWidth(int(100 * self.scale))
        self.resolutionPresetCombo.addItems(self._playblast.resolution_preset_names)
        self.resolutionPresetCombo.addItem("Custom")
        
        self.resolutionWidthSB = QtWidgets.QSpinBox()
        self.resolutionWidthSB.setButtonSymbols(QtWidgets.QSpinBox.NoButtons)
        self.resolutionWidthSB.setRange(1, 9999)
        self.resolutionWidthSB.setMinimumWidth(int(40 * self.scale))
        self.resolutionWidthSB.setAlignment(QtCore.Qt.AlignRight)
        
        self.resolutionHeightSB = QtWidgets.QSpinBox()
        self.resolutionHeightSB.setButtonSymbols(QtWidgets.QSpinBox.NoButtons)
        self.resolutionHeightSB.setRange(1, 9999)
        self.resolutionHeightSB.setMinimumWidth(int(40 * self.scale))
        self.resolutionHeightSB.setAlignment(QtCore.Qt.AlignRight)
        
        # Frame Range Options
        self.frameRangePresetCombo = QtWidgets.QComboBox()
        self.frameRangePresetCombo.setMinimumWidth(int(100 * self.scale))
        self.frameRangePresetCombo.addItems(ConestogaPlayblast.FRAME_RANGE_PRESETS)
        self.frameRangePresetCombo.addItem("Custom")
        
        self.frameRangeStartSB = QtWidgets.QSpinBox()
        self.frameRangeStartSB.setButtonSymbols(QtWidgets.QSpinBox.NoButtons)
        self.frameRangeStartSB.setRange(-9999, 9999)
        self.frameRangeStartSB.setMinimumWidth(int(40 * self.scale))
        self.frameRangeStartSB.setAlignment(QtCore.Qt.AlignRight)
        
        self.frameRangeEndSB = QtWidgets.QSpinBox()
        self.frameRangeEndSB.setButtonSymbols(QtWidgets.QSpinBox.NoButtons)
        self.frameRangeEndSB.setRange(-9999, 9999)
        self.frameRangeEndSB.setMinimumWidth(int(40 * self.scale))
        self.frameRangeEndSB.setAlignment(QtCore.Qt.AlignRight)
        
        # Encoding Options
        self.encodingContainerCombo = QtWidgets.QComboBox()
        self.encodingContainerCombo.setMinimumWidth(int(100 * self.scale))
        self.encodingContainerCombo.addItems(["mov", "mp4", "Image"])
        
        self.encodingVideoCodecCombo = QtWidgets.QComboBox()
        self.encodingVideoCodecCombo.setMinimumWidth(int(100 * self.scale))
        
        self.encoderSettingsBtn = QtWidgets.QPushButton("Settings...")
        self.encoderSettingsBtn.setFixedHeight(int(19 * self.scale))
        
        # Visibility Options
        self.visibilityCombo = QtWidgets.QComboBox()
        self.visibilityCombo.setMinimumWidth(int(100 * self.scale))
        self.visibilityCombo.addItems(self._playblast.viewport_visibility_preset_names)
        self.visibilityCombo.addItem("Custom")
        
        self.visibilityCustomizeBtn = QtWidgets.QPushButton("Customize...")
        self.visibilityCustomizeBtn.setFixedHeight(int(19 * self.scale))
        
        # Other Options
        self.overscanCB = QtWidgets.QCheckBox("Overscan")
        self.ornamentsCB = QtWidgets.QCheckBox("Ornaments")
        self.offscreenCB = QtWidgets.QCheckBox("Offscreen")
        self.shotMaskCB = QtWidgets.QCheckBox("Shot Mask")
        self.fitShotMaskCB = QtWidgets.QCheckBox("Fit Shot Mask")
        self.viewerCB = QtWidgets.QCheckBox("Show in Viewer")
        self.viewerCB.setChecked(True)
        self.shotMaskCB.setChecked(True)
        
        # Logging
        self.logToScriptEditorCB = QtWidgets.QCheckBox("Log to Script Editor")
        self.logOutputTE = QtWidgets.QPlainTextEdit()
        self.logOutputTE.setFocusPolicy(QtCore.Qt.NoFocus)
        self.logOutputTE.setReadOnly(True)
        self.logOutputTE.setWordWrapMode(QtGui.QTextOption.NoWrap)
        
        self.clearLogBtn = QtWidgets.QPushButton("Clear")
        self.clearLogBtn.setMinimumWidth(int(70 * self.scale))
        self.clearLogBtn.setFixedHeight(int(19 * self.scale))
        
        # Playblast Button
        self.playblastBtn = QtWidgets.QPushButton("Playblast")
        self.playblastBtn.setMinimumHeight(int(40 * self.scale))
        font = self.playblastBtn.font()
        font.setPointSize(10)
        font.setBold(True)
        self.playblastBtn.setFont(font)
        pal = self.playblastBtn.palette()
        pal.setColor(QtGui.QPalette.Button, QtGui.QColor(QtCore.Qt.darkGreen).darker())
        self.playblastBtn.setPalette(pal)
        
        # Create layouts
        mainLayout = QtWidgets.QVBoxLayout(self)
        
        # Output layout
        outLayout = QtWidgets.QFormLayout()
        outLayout.setContentsMargins(4, 14, 4, 14)
        
        hDirLayout = QtWidgets.QHBoxLayout()
        hDirLayout.setSpacing(2)
        hDirLayout.addWidget(self.outputDirLE)
        hDirLayout.addWidget(self.selectOutputDirBtn)
        hDirLayout.addWidget(self.showFolderBtn)
        outLayout.addRow("Output Dir:", hDirLayout)
        
        hFileLayout = QtWidgets.QHBoxLayout()
        hFileLayout.setSpacing(4)
        hFileLayout.addWidget(self.outputFilenameLE)
        hFileLayout.addWidget(self.forceOverwriteCB)
        outLayout.addRow("Filename:", hFileLayout)
        
        mainLayout.addLayout(outLayout)
        
        # Name Generator group
        self.nameGenGrp = ConestogaCollapsibleGrpWidget("Name Generator")
        nameGenLayout = QtWidgets.QVBoxLayout()
        nameGenLayout.setContentsMargins(4, 0, 4, 14)
        
        nameGenGrid = QtWidgets.QGridLayout()
        nameGenGrid.setColumnStretch(2, 1)
        
        nameGenGrid.addWidget(QtWidgets.QLabel("Assignment:"), 0, 0)
        nameGenGrid.addWidget(self.assignmentSpin, 0, 1)
        
        nameGenGrid.addWidget(QtWidgets.QLabel("Last Name:"), 1, 0)
        nameGenGrid.addWidget(self.lastNameLE, 1, 