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
from conestoga_playblast_presets import ConestogaPlayblastCustomPresets, ConestogaShotMaskCustomPresets
from conestoga_playblast import ConestogaPlayblast

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
    
    def __init__(self, parent=None):
        super(PlayblastTabWidget, self).__init__(parent)
        self.utils = ConestogaPlayblastUtils()
        self.scale = self.utils.dpi_real_scale_value()
        # Instantiate the core playblast functionality from the plug‐in file.
        self._playblast = ConestogaPlayblast()
        self._encoder_settings_dialog = None
        self._visibility_dialog = None
        self.init_ui()

    def init_ui(self):
        # Output settings
        self.outputDirLE = ConestogaLineEdit(ConestogaLineEdit.TYPE_PLAYBLAST_OUTPUT_PATH)
        self.outputDirLE.setPlaceholderText("{project}/movies")
        self.selectOutputDirBtn = QtWidgets.QPushButton("...")
        self.selectOutputDirBtn.setToolTip("Select Output Directory")
        self.showFolderBtn = QtWidgets.QPushButton(QtGui.QIcon(":fileOpen.png"), "")
        self.showFolderBtn.setToolTip("Show in Folder")
        self.outputFilenameLE = ConestogaLineEdit(ConestogaLineEdit.TYPE_PLAYBLAST_OUTPUT_FILENAME)
        self.outputFilenameLE.setPlaceholderText("{scene}_{timestamp}")
        self.forceOverwriteCB = QtWidgets.QCheckBox("Force overwrite")
        
        # Name Generator
        self.assignmentSpin = QtWidgets.QSpinBox()
        self.assignmentSpin.setRange(1,99)
        self.assignmentSpin.setFixedWidth(50)
        self.lastNameLE = QtWidgets.QLineEdit()
        self.lastNameLE.setPlaceholderText("Last Name")
        self.firstNameLE = QtWidgets.QLineEdit()
        self.firstNameLE.setPlaceholderText("First Name")
        self.versionTypeCombo = QtWidgets.QComboBox()
        self.versionTypeCombo.addItems(["wip", "final"])
        self.versionNumberSpin = QtWidgets.QSpinBox()
        self.versionNumberSpin.setRange(1,99)
        self.versionNumberSpin.setFixedWidth(50)
        self.filenamePreviewLabel = QtWidgets.QLabel("A1_LastName_FirstName_wip_01.mov")
        self.filenamePreviewLabel.setStyleSheet("color: yellow; font-weight: bold;")
        self.generateFilenameBtn = QtWidgets.QPushButton("Generate Filename")
        self.resetNameGenBtn = QtWidgets.QPushButton("Reset")
        
        # Camera Selection
        self.cameraSelectCombo = QtWidgets.QComboBox()
        self.hideDefaultCamsCB = QtWidgets.QCheckBox("Hide defaults")
        self.refresh_camera_combo()
        
        # Resolution Options
        self.resolutionPresetCombo = QtWidgets.QComboBox()
        self.resolutionPresetCombo.addItems(["Render", "HD 1080", "HD 720", "Custom"])
        self.resolutionWidthSB = QtWidgets.QSpinBox()
        self.resolutionWidthSB.setRange(1,9999)
        self.resolutionHeightSB = QtWidgets.QSpinBox()
        self.resolutionHeightSB.setRange(1,9999)
        self.resolutionWidthSB.setValue(1920)
        self.resolutionHeightSB.setValue(1080)
        
        # Frame Range Options
        self.frameRangePresetCombo = QtWidgets.QComboBox()
        self.frameRangePresetCombo.addItems(["Animation", "Playback", "Render", "Camera", "Custom"])
        self.frameRangeStartSB = QtWidgets.QSpinBox()
        self.frameRangeEndSB = QtWidgets.QSpinBox()
        self.frameRangeStartSB.setRange(-9999,9999)
        self.frameRangeEndSB.setRange(-9999,9999)
        self.frameRangeStartSB.setValue(1)
        self.frameRangeEndSB.setValue(100)
        
        # Encoding Options
        self.encodingContainerCombo = QtWidgets.QComboBox()
        self.encodingContainerCombo.addItems(["mov", "mp4", "Image"])
        self.encodingVideoCodecCombo = QtWidgets.QComboBox()
        self.encodingVideoCodecCombo.addItems(["h264"])
        self.encoderSettingsBtn = QtWidgets.QPushButton("Settings...")
        
        # Visibility Options
        self.visibilityCombo = QtWidgets.QComboBox()
        self.visibilityCombo.addItems(["Viewport", "Custom"])
        self.visibilityCustomizeBtn = QtWidgets.QPushButton("Customize...")
        
        # Other Options
        self.overscanCB = QtWidgets.QCheckBox("Overscan")
        self.ornamentsCB = QtWidgets.QCheckBox("Ornaments")
        self.offscreenCB = QtWidgets.QCheckBox("Offscreen")
        self.viewerCB = QtWidgets.QCheckBox("Show in Viewer")
        self.shotMaskCB = QtWidgets.QCheckBox("Shot Mask")
        self.fitShotMaskCB = QtWidgets.QCheckBox("Fit Shot Mask")
        self.viewerCB.setChecked(True)
        self.shotMaskCB.setChecked(True)
        
        # Playblast Button
        self.playblastBtn = QtWidgets.QPushButton("Playblast")
        button_size = int(40 * self.scale)
        self.playblastBtn.setMinimumHeight(button_size)
        font = self.playblastBtn.font()
        font.setPointSize(10)
        font.setBold(True)
        self.playblastBtn.setFont(font)
        
        # Logging 
        self.logToScriptEditorCB = QtWidgets.QCheckBox("Log to Script Editor")
        self.logOutputTE = QtWidgets.QPlainTextEdit()
        self.logOutputTE.setReadOnly(True)
        self.clearLogBtn = QtWidgets.QPushButton("Clear Log")
        
        # Layouts
        mainLayout = QtWidgets.QVBoxLayout(self)
        
        # Output layout
        outLayout = QtWidgets.QFormLayout()
        hDirLayout = QtWidgets.QHBoxLayout()
        hDirLayout.addWidget(self.outputDirLE)
        hDirLayout.addWidget(self.selectOutputDirBtn)
        hDirLayout.addWidget(self.showFolderBtn)
        outLayout.addRow("Output Dir:", hDirLayout)
        
        hFileLayout = QtWidgets.QHBoxLayout()
        hFileLayout.addWidget(self.outputFilenameLE)
        hFileLayout.addWidget(self.forceOverwriteCB)
        outLayout.addRow("Filename:", hFileLayout)
        mainLayout.addLayout(outLayout)
        
        # Name Generator group
        nameGenGrp = ConestogaCollapsibleGrpWidget("Name Generator")
        nameGenLayout = QtWidgets.QGridLayout()
        nameGenLayout.addWidget(QtWidgets.QLabel("Assignment:"), 0, 0)
        nameGenLayout.addWidget(self.assignmentSpin, 0, 1)
        nameGenLayout.addWidget(QtWidgets.QLabel("Last Name:"), 1, 0)
        nameGenLayout.addWidget(self.lastNameLE, 1, 1, 1, 2)
        nameGenLayout.addWidget(QtWidgets.QLabel("First Name:"), 2, 0)
        nameGenLayout.addWidget(self.firstNameLE, 2, 1, 1, 2)
        nameGenLayout.addWidget(QtWidgets.QLabel("Type:"), 3, 0)
        nameGenLayout.addWidget(self.versionTypeCombo, 3, 1)
        nameGenLayout.addWidget(QtWidgets.QLabel("Version:"), 4, 0)
        nameGenLayout.addWidget(self.versionNumberSpin, 4, 1)
        nameGenLayout.addWidget(QtWidgets.QLabel("Preview:"), 5, 0)
        nameGenLayout.addWidget(self.filenamePreviewLabel, 5, 1, 1, 2)
        btnRow = QtWidgets.QHBoxLayout()
        btnRow.addWidget(self.generateFilenameBtn)
        btnRow.addWidget(self.resetNameGenBtn)
        nameGenLayout.addLayout(btnRow, 6, 0, 1, 3)
        nameGenGrp.add_layout(nameGenLayout)
        mainLayout.addWidget(nameGenGrp)
        
        # Options group
        optionsGrp = ConestogaCollapsibleGrpWidget("Options")
        optionsLayout = QtWidgets.QVBoxLayout()
        
        # Two-column layout for options
        optionsColumns = QtWidgets.QHBoxLayout()
        
        # Left Column (Camera, Resolution, Frame Range)
        leftCol = QtWidgets.QVBoxLayout()
        
        # Camera Selection
        camLayout = QtWidgets.QHBoxLayout()
        camLayout.addWidget(QtWidgets.QLabel("Camera:"))
        camLayout.addWidget(self.cameraSelectCombo)
        camLayout.addWidget(self.hideDefaultCamsCB)
        camLayout.addStretch()
        leftCol.addLayout(camLayout)
        
        # Resolution
        resLayout = QtWidgets.QHBoxLayout()
        resLayout.addWidget(QtWidgets.QLabel("Resolution:"))
        resLayout.addWidget(self.resolutionPresetCombo)
        resLayout.addWidget(self.resolutionWidthSB)
        resLayout.addWidget(QtWidgets.QLabel("x"))
        resLayout.addWidget(self.resolutionHeightSB)
        resLayout.addStretch()
        leftCol.addLayout(resLayout)
        
        # Frame Range
        frLayout = QtWidgets.QHBoxLayout()
        frLayout.addWidget(QtWidgets.QLabel("Frame Range:"))
        frLayout.addWidget(self.frameRangePresetCombo)
        frLayout.addWidget(self.frameRangeStartSB)
        frLayout.addWidget(self.frameRangeEndSB)
        frLayout.addStretch()
        leftCol.addLayout(frLayout)
        
        # Right Column (Encoding, Visibility)
        rightCol = QtWidgets.QVBoxLayout()
        
        # Encoding
        encLayout = QtWidgets.QHBoxLayout()
        encLayout.addWidget(QtWidgets.QLabel("Encoding:"))
        encLayout.addWidget(self.encodingContainerCombo)
        encLayout.addWidget(self.encodingVideoCodecCombo)
        encLayout.addWidget(self.encoderSettingsBtn)
        encLayout.addStretch()
        rightCol.addLayout(encLayout)
        
        # Visibility
        visLayout = QtWidgets.QHBoxLayout()
        visLayout.addWidget(QtWidgets.QLabel("Visibility:"))
        visLayout.addWidget(self.visibilityCombo)
        visLayout.addWidget(self.visibilityCustomizeBtn)
        visLayout.addStretch()
        rightCol.addLayout(visLayout)
        
        # Add columns to layout
        optionsColumns.addLayout(leftCol)
        optionsColumns.addLayout(rightCol)
        optionsLayout.addLayout(optionsColumns)
        
        # Add separator
        separator = QtWidgets.QFrame()
        separator.setFrameShape(QtWidgets.QFrame.HLine)
        separator.setFrameShadow(QtWidgets.QFrame.Sunken)
        optionsLayout.addWidget(separator)
        
        # Checkboxes in rows at the bottom
        checkboxLayout = QtWidgets.QVBoxLayout()
        
        # First row of checkboxes
        cb1Layout = QtWidgets.QHBoxLayout()
        cb1Layout.addStretch()
        cb1Layout.addWidget(self.ornamentsCB)
        cb1Layout.addSpacing(15)
        cb1Layout.addWidget(self.overscanCB)
        cb1Layout.addSpacing(15)
        cb1Layout.addWidget(self.offscreenCB)
        cb1Layout.addStretch()
        checkboxLayout.addLayout(cb1Layout)
        
        # Second row of checkboxes
        cb2Layout = QtWidgets.QHBoxLayout()
        cb2Layout.addStretch()
        cb2Layout.addWidget(self.shotMaskCB)
        cb2Layout.addSpacing(15)
        cb2Layout.addWidget(self.fitShotMaskCB)
        cb2Layout.addSpacing(15)
        cb2Layout.addWidget(self.viewerCB)
        cb2Layout.addStretch()
        checkboxLayout.addLayout(cb2Layout)
        
        optionsLayout.addLayout(checkboxLayout)
        optionsGrp.add_layout(optionsLayout)
        mainLayout.addWidget(optionsGrp)
        
        # Add the playblast button
        mainLayout.addWidget(self.playblastBtn, alignment=QtCore.Qt.AlignCenter)
        
        # Logging section
        loggingGrp = ConestogaCollapsibleGrpWidget("Logging")
        loggingLayout = QtWidgets.QVBoxLayout()
        
        loggingLayout.addWidget(self.logOutputTE)
        
        logOptionsLayout = QtWidgets.QHBoxLayout()
        logOptionsLayout.addWidget(self.logToScriptEditorCB)
        logOptionsLayout.addStretch()
        logOptionsLayout.addWidget(self.clearLogBtn)
        loggingLayout.addLayout(logOptionsLayout)
        
        loggingGrp.add_layout(loggingLayout)
        mainLayout.addWidget(loggingGrp)

        # Connect signals for dynamic updates
        self.selectOutputDirBtn.clicked.connect(self.select_output_directory)
        self.showFolderBtn.clicked.connect(self.open_output_directory)
        
        self.generateFilenameBtn.clicked.connect(self.generate_filename)
        self.resetNameGenBtn.clicked.connect(self.reset_name_generator)
        self.assignmentSpin.valueChanged.connect(self.update_filename_preview)
        self.lastNameLE.textChanged.connect(self.update_filename_preview)
        self.firstNameLE.textChanged.connect(self.update_filename_preview)
        self.versionTypeCombo.currentTextChanged.connect(self.update_filename_preview)
        self.versionNumberSpin.valueChanged.connect(self.update_filename_preview)
        
        self.cameraSelectCombo.currentTextChanged.connect(self.on_camera_changed)
        self.hideDefaultCamsCB.toggled.connect(self.refresh_camera_combo)
        
        self.frameRangePresetCombo.currentTextChanged.connect(self.refresh_frame_range)
        self.frameRangeStartSB.editingFinished.connect(self.on_frame_range_changed)
        self.frameRangeEndSB.editingFinished.connect(self.on_frame_range_changed)
        
        self.resolutionPresetCombo.currentTextChanged.connect(self.refresh_resolution)
        self.resolutionWidthSB.editingFinished.connect(self.on_resolution_changed)
        self.resolutionHeightSB.editingFinished.connect(self.on_resolution_changed)
        
        self.encodingContainerCombo.currentTextChanged.connect(self.refresh_video_encoders)
        self.encodingVideoCodecCombo.currentTextChanged.connect(self.on_video_encoder_changed)
        self.encoderSettingsBtn.clicked.connect(self.show_encoder_settings_dialog)
        
        self.visibilityCombo.currentTextChanged.connect(self.on_visibility_preset_changed)
        self.visibilityCustomizeBtn.clicked.connect(self.show_visibility_dialog)
        
        self.playblastBtn.clicked.connect(self.do_playblast)
        
        self.logToScriptEditorCB.toggled.connect(self.on_log_to_script_editor_changed)
        self.clearLogBtn.clicked.connect(lambda: self.logOutputTE.clear())
        
        self.lastNameLE.textChanged.connect(self.update_artist_name)
        self.firstNameLE.textChanged.connect(self.update_artist_name)
        
        self._playblast.output_logged.connect(self.append_output)

    def select_output_directory(self):
        current_dir_path = self.outputDirLE.text()
        if not current_dir_path:
            current_dir_path = self.outputDirLE.placeholderText()

        dir_path = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Select Output Directory", current_dir_path)
        
        if dir_path:
            self.outputDirLE.setText(dir_path)

    def open_output_directory(self):
        output_dir_path = self.outputDirLE.text()
        if not output_dir_path:
            output_dir_path = self.outputDirLE.placeholderText()

        if os.path.isdir(output_dir_path):
            if sys.platform == "win32":
                file_prefix = "file:///"
            else:
                file_prefix = "file://"
            QtGui.QDesktopServices.openUrl(QtCore.QUrl(f"{file_prefix}{output_dir_path}"))
        else:
            self.append_output(f"[ERROR] Invalid directory path: {output_dir_path}")

    def refresh_camera_combo(self):
        current_camera = self.cameraSelectCombo.currentText()
        self.cameraSelectCombo.clear()
        self.cameraSelectCombo.addItem("<Active>")
        cams = ConestogaPlayblastUtils.cameras_in_scene(
            not self.hideDefaultCamsCB.isChecked(), True)
        self.cameraSelectCombo.addItems(cams)
        
        if current_camera and self.cameraSelectCombo.findText(current_camera) >= 0:
            self.cameraSelectCombo.setCurrentText(current_camera)

    def refresh_resolution(self):
        preset = self.resolutionPresetCombo.currentText()
        if preset != "Custom":
            if preset == "Render":
                w = cmds.getAttr("defaultResolution.width")
                h = cmds.getAttr("defaultResolution.height")
            elif preset == "HD 1080":
                w, h = 1920, 1080
            elif preset == "HD 720":
                w, h = 1280, 720
            else:
                return
                
            self.resolutionWidthSB.setValue(w)
            self.resolutionHeightSB.setValue(h)

    def refresh_frame_range(self):
        preset = self.frameRangePresetCombo.currentText()
        if preset != "Custom":
            if preset == "Playback":
                start = int(cmds.playbackOptions(q=True, minTime=True))
                end = int(cmds.playbackOptions(q=True, maxTime=True))
            elif preset == "Animation":
                start = int(cmds.playbackOptions(q=True, animationStartTime=True))
                end = int(cmds.playbackOptions(q=True, animationEndTime=True))
            elif preset == "Render":
                start = int(cmds.getAttr("defaultRenderGlobals.startFrame"))
                end = int(cmds.getAttr("defaultRenderGlobals.endFrame"))
            else:
                return
                
            self.frameRangeStartSB.setValue(start)
            self.frameRangeEndSB.setValue(end)
            
        # Enable/disable spinboxes based on selected preset
        use_camera_range = preset == "Camera"
        self.frameRangeStartSB.setEnabled(not use_camera_range)
        self.frameRangeEndSB.setEnabled(not use_camera_range)

    def refresh_video_encoders(self):
        container = self.encodingContainerCombo.currentText()
        self.encodingVideoCodecCombo.clear()
        
        if container == "mov" or container == "mp4":
            self.encodingVideoCodecCombo.addItem("h264")
        elif container == "Image":
            self.encodingVideoCodecCombo.addItems(["jpg", "png", "tif"])

    def on_video_encoder_changed(self):
        container = self.encodingContainerCombo.currentText()
        encoder = self.encodingVideoCodecCombo.currentText()
        
        # Additional logic here if needed

    def on_resolution_changed(self):
        w = self.resolutionWidthSB.value()
        h = self.resolutionHeightSB.value()
        
        # Check if it matches any preset
        if (w == 1920 and h == 1080):
            self.resolutionPresetCombo.setCurrentText("HD 1080")
        elif (w == 1280 and h == 720):
            self.resolutionPresetCombo.setCurrentText("HD 720")
        else:
            self.resolutionPresetCombo.setCurrentText("Custom")

    def on_frame_range_changed(self):
        self.frameRangePresetCombo.setCurrentText("Custom")

    def show_encoder_settings_dialog(self):
        if not self._encoder_settings_dialog:
            self._encoder_settings_dialog = ConestogaPlayblastEncoderSettingsDialog(self)
        
        container = self.encodingContainerCombo.currentText()
        if container == "Image":
            self._encoder_settings_dialog.set_page("Image")
            self._encoder_settings_dialog.set_image_settings(100)  # Default value
        else:
            self._encoder_settings_dialog.set_page("h264")
            self._encoder_settings_dialog.set_h264_settings("High", "fast")  # Default values
        
        self._encoder_settings_dialog.exec_()

    def on_visibility_preset_changed(self):
        # Logic for handling visibility preset changes
        pass

    def show_visibility_dialog(self):
        if not self._visibility_dialog:
            self._visibility_dialog = ConestogaPlayblastVisibilityDialog(self)
        
        # Here you would set the initial visibility data
        # self._visibility_dialog.set_visibility_data(data)
        
        self._visibility_dialog.exec_()

    def update_filename_preview(self):
        assign = self.assignmentSpin.value()
        lname = self.lastNameLE.text() or "LastName"
        fname = self.firstNameLE.text() or "FirstName"
        vtype = self.versionTypeCombo.currentText()
        vnum = str(self.versionNumberSpin.value()).zfill(2)
        
        # Use * for preview but _ for actual filename
        filename = f"A{assign}_*{lname}*_{fname}*_{vtype}*_{vnum}.mov"
        self.filenamePreviewLabel.setText(filename)

    def reset_name_generator(self):
        """Reset all fields in the name generator to default values."""
        self.assignmentSpin.setValue(1)
        self.lastNameLE.clear()
        self.firstNameLE.clear()
        self.versionTypeCombo.setCurrentIndex(0)  # "wip"
        self.versionNumberSpin.setValue(1)
        self.update_filename_preview()

    def generate_filename(self):
        """Generate a filename from the inputs and place it in the output field."""
        assign = self.assignmentSpin.value()
        lname = self.lastNameLE.text()
        fname = self.firstNameLE.text()
        
        if not lname or not fname:
            QtWidgets.QMessageBox.warning(self, "Missing Information", 
                                         "Please enter both last name and first name.")
            return
        
        vtype = self.versionTypeCombo.currentText()
        vnum = str(self.versionNumberSpin.value()).zfill(2)
        
        # Use underscores for the actual file
        filename = f"A{assign}_{lname}_{fname}_{vtype}_{vnum}"
        
        # Add extension based on the selected container format
        container = self.encodingContainerCombo.currentText()
        if container == "Image":
            codec = self.encodingVideoCodecCombo.currentText()
            filename += f".{codec}"
        else:
            filename += f".{container}"
            
        self.outputFilenameLE.setText(filename)

    def update_artist_name(self):
        lname = self.lastNameLE.text()
        fname = self.firstNameLE.text()
        artist = f"{fname} {lname}".strip() if (lname or fname) else ""
        self.artist_name_changed.emit(artist)

    def on_camera_changed(self, text):
        # Additional logic (if needed) when the camera selection changes
        pass

    def on_log_to_script_editor_changed(self, state):
        if hasattr(self._playblast, 'set_maya_logging_enabled'):
            self._playblast.set_maya_logging_enabled(state)

    def append_output(self, text):
        self.logOutputTE.appendPlainText(text)
        cursor = self.logOutputTE.textCursor()
        cursor.movePosition(QtGui.QTextCursor.End)
        self.logOutputTE.setTextCursor(cursor)

    def do_playblast(self):
        outDir = self.outputDirLE.text() or self.outputDirLE.placeholderText()
        fname = self.outputFilenameLE.text() or self.outputFilenameLE.placeholderText()
        pad = 4  # Default padding
        overscan = self.overscanCB.isChecked()
        ornaments = self.ornamentsCB.isChecked()
        viewer = self.viewerCB.isChecked()
        offscreen = self.offscreenCB.isChecked()
        overwrite = self.forceOverwriteCB.isChecked()
        cam_range = (self.frameRangePresetCombo.currentText() == "Camera")
        
        # Handle shot mask settings
        shot_mask = self.shotMaskCB.isChecked()
        fit_shot_mask = self.fitShotMaskCB.isChecked()
        
        # Camera selection
        camera = ""
        if self.cameraSelectCombo.currentText() != "<Active>":
            camera = self.cameraSelectCombo.currentText()
        
        # Call the core playblast execution from the plug‐in
        if hasattr(self._playblast, 'execute'):
            self._playblast.execute(
                outDir, fname, pad, overscan, ornaments, viewer, 
                offscreen, overwrite, camera, cam_range
            )

#-------------------------------------------------------------------------
# Tab 2: Shot Mask Options
#-------------------------------------------------------------------------
class ShotMaskTabWidget(QtWidgets.QWidget):
    collapsed_state_changed = QtCore.Signal()
    ALL_CAMERAS = "<All Cameras>"
    LABELS = ["Top-Left", "Top-Center", "Top-Right", "Bottom-Left", "Bottom-Center", "Bottom-Right"]
    
    def __init__(self, parent=None):
        super(ShotMaskTabWidget, self).__init__(parent)
        self._camera_select_dialog = None
        self._update_mask_enabled = True
        self.create_widgets()
        self.create_layouts()
        self.create_connections()
        self.update_ui_elements()
        
    def create_widgets(self):
        scale_value = ConestogaPlayblastUtils.dpi_real_scale_value()

        button_width = int(60 * scale_value)
        button_height = int(18 * scale_value)
        spin_box_width = int(50 * scale_value)

        self.camera_le = QtWidgets.QLineEdit()
        self.camera_select_btn = QtWidgets.QPushButton("Select...")
        self.camera_select_btn.setFixedSize(button_width, button_height)

        self.label_line_edits = []
        for i in range(len(self.LABELS)):
            line_edit = ConestogaLineEdit(ConestogaLineEdit.TYPE_SHOT_MASK_LABEL)
            self.label_line_edits.append(line_edit)

        self.font_le = QtWidgets.QLineEdit()
        self.font_le.setEnabled(False)

        self.font_select_btn = QtWidgets.QPushButton("Select...")
        self.font_select_btn.setFixedSize(button_width, button_height)

        self.label_color_btn = ConestogaColorButton()

        self.label_transparency_dsb = QtWidgets.QDoubleSpinBox()
        self.label_transparency_dsb.setMinimumWidth(spin_box_width)
        self.label_transparency_dsb.setSingleStep(0.05)
        self.label_transparency_dsb.setMinimum(0.0)
        self.label_transparency_dsb.setMaximum(1.0)
        self.label_transparency_dsb.setValue(1.0)
        self.label_transparency_dsb.setDecimals(3)
        self.label_transparency_dsb.setButtonSymbols(QtWidgets.QSpinBox.NoButtons)

        self.label_scale_dsb = QtWidgets.QDoubleSpinBox()
        self.label_scale_dsb.setMinimumWidth(spin_box_width)
        self.label_scale_dsb.setSingleStep(0.05)
        self.label_scale_dsb.setMinimum(0.1)
        self.label_scale_dsb.setMaximum(2.0)
        self.label_scale_dsb.setValue(1.0)
        self.label_scale_dsb.setDecimals(3)
        self.label_scale_dsb.setButtonSymbols(QtWidgets.QSpinBox.NoButtons)

        self.top_border_cb = QtWidgets.QCheckBox("Top")
        self.top_border_cb.setChecked(True)
        self.bottom_border_cb = QtWidgets.QCheckBox("Bottom")
        self.bottom_border_cb.setChecked(True)

        self.border_color_btn = ConestogaColorButton()

        self.border_transparency_dsb = QtWidgets.QDoubleSpinBox()
        self.border_transparency_dsb.setMinimumWidth(spin_box_width)
        self.border_transparency_dsb.setSingleStep(0.05)
        self.border_transparency_dsb.setMinimum(0.0)
        self.border_transparency_dsb.setMaximum(1.0)
        self.border_transparency_dsb.setValue(1.0)
        self.border_transparency_dsb.setDecimals(3)
        self.border_transparency_dsb.setButtonSymbols(QtWidgets.QSpinBox.NoButtons)

        self.border_scale_dsb = QtWidgets.QDoubleSpinBox()
        self.border_scale_dsb.setMinimumWidth(spin_box_width)
        self.border_scale_dsb.setSingleStep(0.05)
        self.border_scale_dsb.setMinimum(0.1)
        self.border_scale_dsb.setMaximum(5.0)
        self.border_scale_dsb.setValue(1.0)
        self.border_scale_dsb.setDecimals(3)
        self.border_scale_dsb.setButtonSymbols(QtWidgets.QSpinBox.NoButtons)

        self.border_aspect_ratio_dsb = QtWidgets.QDoubleSpinBox()
        self.border_aspect_ratio_dsb.setMinimumWidth(spin_box_width)
        self.border_aspect_ratio_dsb.setSingleStep(0.05)
        self.border_aspect_ratio_dsb.setMinimum(0.1)
        self.border_aspect_ratio_dsb.setMaximum(10.0)
        self.border_aspect_ratio_dsb.setValue(2.35)
        self.border_aspect_ratio_dsb.setDecimals(3)
        self.border_aspect_ratio_dsb.setButtonSymbols(QtWidgets.QSpinBox.NoButtons)

        self.frame_border_to_aspect_ratio_cb = QtWidgets.QCheckBox("Frame border to aspect ratio")
        self.border_size_type_text = QtWidgets.QLabel("Scale")

        self.counter_padding_sb = QtWidgets.QSpinBox()
        self.counter_padding_sb.setMinimumWidth(spin_box_width)
        self.counter_padding_sb.setSingleStep(1)
        self.counter_padding_sb.setMinimum(1)
        self.counter_padding_sb.setMaximum(6)
        self.counter_padding_sb.setButtonSymbols(QtWidgets.QSpinBox.NoButtons)
        
    def create_layouts(self):
        camera_layout = QtWidgets.QHBoxLayout()
        camera_layout.setContentsMargins(4, 14, 4, 14)
        camera_layout.setSpacing(2)
        camera_layout.addWidget(self.camera_le)
        camera_layout.addWidget(self.camera_select_btn)

        camera_grp_layout = ConestogaFormLayout()
        camera_grp_layout.addLayoutRow(0, "Camera", camera_layout)

        labels_layout = ConestogaFormLayout()
        for i in range(len(ShotMaskTabWidget.LABELS)):
            labels_layout.addWidgetRow(i, ShotMaskTabWidget.LABELS[i], self.label_line_edits[i])

        self.labels_grp = ConestogaCollapsibleGrpWidget("Labels")
        self.labels_grp.add_layout(labels_layout)

        font_layout = QtWidgets.QHBoxLayout()
        font_layout.setSpacing(2)
        font_layout.addWidget(self.font_le)
        font_layout.addWidget(self.font_select_btn)

        text_color_layout = QtWidgets.QHBoxLayout()
        text_color_layout.addWidget(self.label_color_btn)
        text_color_layout.addSpacing(4)
        text_color_layout.addWidget(QtWidgets.QLabel("Alpha"))
        text_color_layout.addWidget(self.label_transparency_dsb)
        text_color_layout.addSpacing(4)
        text_color_layout.addWidget(QtWidgets.QLabel("Scale"))
        text_color_layout.addWidget(self.label_scale_dsb)
        text_color_layout.addStretch()

        text_layout = ConestogaFormLayout()
        text_layout.addLayoutRow(0, "Font", font_layout)
        text_layout.addLayoutRow(1, "Color", text_color_layout)

        self.text_grp = ConestogaCollapsibleGrpWidget("Text")
        self.text_grp.add_layout(text_layout)

        border_visibility_layout = QtWidgets.QHBoxLayout()
        border_visibility_layout.addWidget(self.top_border_cb)
        border_visibility_layout.addWidget(self.bottom_border_cb)
        border_visibility_layout.addWidget(self.frame_border_to_aspect_ratio_cb)
        border_visibility_layout.addStretch()

        border_color_layout = QtWidgets.QHBoxLayout()
        border_color_layout.addWidget(self.border_color_btn)
        border_color_layout.addSpacing(4)
        border_color_layout.addWidget(QtWidgets.QLabel("Alpha"))
        border_color_layout.addWidget(self.border_transparency_dsb)
        border_color_layout.addSpacing(4)
        border_color_layout.addWidget(self.border_size_type_text)
        border_color_layout.addWidget(self.border_scale_dsb)
        border_color_layout.addWidget(self.border_aspect_ratio_dsb)
        border_color_layout.addStretch()

        borders_layout = ConestogaFormLayout()
        borders_layout.addLayoutRow(0, "", border_visibility_layout)
        borders_layout.addLayoutRow(1, "Color", border_color_layout)

        self.borders_grp = ConestogaCollapsibleGrpWidget("Borders")
        self.borders_grp.add_layout(borders_layout)

        counter_padding_layout = QtWidgets.QHBoxLayout()
        counter_padding_layout.addWidget(self.counter_padding_sb)
        counter_padding_layout.addStretch()

        counter_layout = ConestogaFormLayout()
        counter_layout.addLayoutRow(0, "Padding", counter_padding_layout)

        self.counter_grp = ConestogaCollapsibleGrpWidget("Counter")
        self.counter_grp.add_layout(counter_layout)

        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(2)
        main_layout.addLayout(camera_grp_layout)
        main_layout.addWidget(self.labels_grp)
        main_layout.addWidget(self.text_grp)
        main_layout.addWidget(self.borders_grp)
        main_layout.addWidget(self.counter_grp)
        main_layout.addStretch()
        
    def create_connections(self):
        self.camera_le.editingFinished.connect(self.update_mask)
        self.camera_select_btn.clicked.connect(self.show_camera_select_dialog)

        for label_le in self.label_line_edits:
            label_le.editingFinished.connect(self.update_mask)

        self.font_select_btn.clicked.connect(self.show_font_select_dialog)
        self.label_color_btn.color_changed.connect(self.update_mask)
        self.label_transparency_dsb.valueChanged.connect(self.update_mask)
        self.label_scale_dsb.valueChanged.connect(self.update_mask)

        self.top_border_cb.toggled.connect(self.update_mask)
        self.bottom_border_cb.toggled.connect(self.update_mask)
        self.frame_border_to_aspect_ratio_cb.toggled.connect(self.on_border_aspect_ratio_enabled_changed)
        self.border_color_btn.color_changed.connect(self.update_mask)
        self.border_transparency_dsb.valueChanged.connect(self.update_mask)
        self.border_scale_dsb.valueChanged.connect(self.update_mask)
        self.border_aspect_ratio_dsb.editingFinished.connect(self.update_mask)

        self.counter_padding_sb.valueChanged.connect(self.update_mask)

        self.labels_grp.collapsed_state_changed.connect(self.on_collapsed_state_changed)
        self.text_grp.collapsed_state_changed.connect(self.on_collapsed_state_changed)
        self.borders_grp.collapsed_state_changed.connect(self.on_collapsed_state_changed)
        self.counter_grp.collapsed_state_changed.connect(self.on_collapsed_state_changed)
        
    def refresh_cameras(self):
        cameras = cmds.listCameras()
        cameras.insert(0, ShotMaskTabWidget.ALL_CAMERAS)
        
    def create_mask(self):
        ConestogaShotMask.create_mask()

    def delete_mask(self):
        ConestogaShotMask.delete_mask()

    def toggle_mask(self):
        if ConestogaShotMask.get_mask():
            self.delete_mask()
        else:
            self.create_mask()

    def update_mask(self):
        if not self._update_mask_enabled:
            return

        ConestogaShotMask.set_camera_name(self.camera_le.text())

        label_text = []
        for line_edit in self.label_line_edits:
            label_text.append(line_edit.text())
        ConestogaShotMask.set_label_text(label_text)

        ConestogaShotMask.set_label_font(self.font_le.text())
        ConestogaShotMask.set_label_scale(self.label_scale_dsb.value())

        label_color = self.label_color_btn.get_color()
        label_alpha = self.label_transparency_dsb.value()
        ConestogaShotMask.set_label_color(label_color[0], label_color[1], label_color[2], label_alpha)

        ConestogaShotMask.set_border_visible(self.top_border_cb.isChecked(), self.bottom_border_cb.isChecked())
        ConestogaShotMask.set_border_scale(self.border_scale_dsb.value())
        ConestogaShotMask.set_border_aspect_ratio_enabled(self.frame_border_to_aspect_ratio_cb.isChecked())
        ConestogaShotMask.set_border_aspect_ratio(self.border_aspect_ratio_dsb.value())

        border_color = self.border_color_btn.get_color()
        border_alpha = self.border_transparency_dsb.value()
        ConestogaShotMask.set_border_color(border_color[0], border_color[1], border_color[2], border_alpha)

        ConestogaShotMask.set_counter_padding(self.counter_padding_sb.value())

        ConestogaShotMask.refresh_mask()

    def update_ui_elements(self):
        self._update_mask_enabled = False

        camera_name = ConestogaShotMask.get_camera_name()
        if not camera_name:
            camera_name = ShotMaskTabWidget.ALL_CAMERAS
        self.camera_le.setText(camera_name)

        try:
            label_text = ConestogaShotMask.get_label_text()
            for i in range(len(label_text)):
                self.label_line_edits[i].setText(label_text[i])
        except:
            pass

        label_font = ConestogaShotMask.get_label_font()
        self.font_le.setText(label_font)

        label_color = ConestogaShotMask.get_label_color()
        self.label_color_btn.set_color(label_color)
        self.label_transparency_dsb.setValue(label_color[3])
        self.label_scale_dsb.setValue(ConestogaShotMask.get_label_scale())

        border_visible = ConestogaShotMask.get_border_visible()
        self.top_border_cb.setChecked(border_visible[0])
        self.bottom_border_cb.setChecked(border_visible[1])

        border_color = ConestogaShotMask.get_border_color()
        self.border_color_btn.set_color(border_color)
        self.border_transparency_dsb.setValue(border_color[3])
        
        border_ar_enabled = ConestogaShotMask.is_border_aspect_ratio_enabled()
        self.frame_border_to_aspect_ratio_cb.setChecked(border_ar_enabled)
        
        self.border_aspect_ratio_dsb.setVisible(border_ar_enabled)
        self.border_scale_dsb.setVisible(not border_ar_enabled)
        self.border_size_type_text.setText("Aspect Ratio:" if border_ar_enabled else "Scale:")
        
        self.border_aspect_ratio_dsb.setValue(ConestogaShotMask.get_border_aspect_ratio())
        self.border_scale_dsb.setValue(ConestogaShotMask.get_border_scale())

        self.counter_padding_sb.setValue(ConestogaShotMask.get_counter_padding())

        self._update_mask_enabled = True

    def on_collapsed_state_changed(self):
        self.collapsed_state_changed.emit()

    def on_border_aspect_ratio_enabled_changed(self, enabled):
        self.border_aspect_ratio_dsb.setVisible(enabled)
        self.border_scale_dsb.setVisible(not enabled)
        self.border_size_type_text.setText("Aspect Ratio:" if enabled else "Scale:")
        self.update_mask()

    def show_camera_select_dialog(self):
        if not self._camera_select_dialog:
            self._camera_select_dialog = ConestogaCameraSelectDialog(self)
            
        self._camera_select_dialog.set_multi_select_enabled(False)
        self._camera_select_dialog.set_camera_list_text("Select a camera to restrict the shot mask, or select <All Cameras> to show on all cameras")
        self._camera_select_dialog.set_select_btn_text("Select")
        
        cameras = [ShotMaskTabWidget.ALL_CAMERAS]
        selected = []
        
        camera_name = self.camera_le.text()
        if camera_name and camera_name != ShotMaskTabWidget.ALL_CAMERAS:
            selected.append(camera_name)
        elif camera_name == ShotMaskTabWidget.ALL_CAMERAS:
            selected.append(ShotMaskTabWidget.ALL_CAMERAS)
            
        self._camera_select_dialog.refresh_list(selected, True, True, cameras)
        
        if self._camera_select_dialog.exec_() == QtWidgets.QDialog.Accepted:
            selected = self._camera_select_dialog.get_selected()
            if len(selected) > 0:
                self.camera_le.setText(selected[0])
                self.update_mask()

    def show_font_select_dialog(self):
        current_font = QtGui.QFont(self.font_le.text())
        font, ok = QtWidgets.QFontDialog.getFont(current_font, self)
        if ok:
            self.font_le.setText(font.family())
            self.update_mask()

#-------------------------------------------------------------------------
# Tab 3: Settings / Logging
#-------------------------------------------------------------------------
class SettingsTabWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(SettingsTabWidget, self).__init__(parent)
        self.init_ui()

    def init_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        
        # About section with version info
        aboutText = (
            '<h3>Conestoga Playblast Tool</h3>'
            '<h3>v1.0.0</h3>'
            '<p>Conestoga College<br>'
            '<a style="color:white;text-decoration:none;" href="http://conestogac.on.ca">conestogac.on.ca</a></p>'
        )
        
        aboutLabel = QtWidgets.QLabel(aboutText)
        aboutLabel.setOpenExternalLinks(True)
        aboutLabel.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(aboutLabel)
        
        # Playblast settings
        playblastGroup = ConestogaCollapsibleGrpWidget("Playblast")
        playblastLayout = QtWidgets.QFormLayout()
        
        # FFmpeg path
        ffmpegLayout = QtWidgets.QHBoxLayout()
        self.ffmpegPathLE = QtWidgets.QLineEdit()
        self.ffmpegPathLE.setPlaceholderText("<path to ffmpeg executable>")
        self.ffmpegSelectBtn = QtWidgets.QPushButton("...")
        ffmpegLayout.addWidget(self.ffmpegPathLE)
        ffmpegLayout.addWidget(self.ffmpegSelectBtn)
        playblastLayout.addRow("FFmpeg Path:", ffmpegLayout)
        
        # Temp directory
        tempDirLayout = QtWidgets.QHBoxLayout()
        self.tempDirLE = QtWidgets.QLineEdit()
        self.tempDirLE.setPlaceholderText("<temp directory path>")
        self.tempDirSelectBtn = QtWidgets.QPushButton("...")
        tempDirLayout.addWidget(self.tempDirLE)
        tempDirLayout.addWidget(self.tempDirSelectBtn)
        playblastLayout.addRow("Temp Directory:", tempDirLayout)
        
        # Temp file format
        self.tempFormatCombo = QtWidgets.QComboBox()
        self.tempFormatCombo.addItems(["movie", "png", "tga", "tif"])
        formatLayout = QtWidgets.QHBoxLayout()
        formatLayout.addWidget(self.tempFormatCombo)
        formatLayout.addStretch()
        playblastLayout.addRow("Temp Format:", formatLayout)
        
        # Reset button
        resetLayout = QtWidgets.QHBoxLayout()
        resetLayout.addStretch()
        self.resetPlayblastBtn = QtWidgets.QPushButton("Reset Playblast Settings")
        resetLayout.addWidget(self.resetPlayblastBtn)
        resetLayout.addStretch()
        
        playblastGroup.add_layout(playblastLayout)
        playblastGroup.add_layout(resetLayout)
        layout.addWidget(playblastGroup)
        
        # Shot mask settings
        shotMaskGroup = ConestogaCollapsibleGrpWidget("Shot Mask")
        shotMaskLayout = QtWidgets.QFormLayout()
        
        # Logo path
        logoLayout = QtWidgets.QHBoxLayout()
        self.logoPathLE = QtWidgets.QLineEdit()
        self.logoPathLE.setPlaceholderText("<path to logo image>")
        self.logoSelectBtn = QtWidgets.QPushButton("...")
        logoLayout.addWidget(self.logoPathLE)
        logoLayout.addWidget(self.logoSelectBtn)
        shotMaskLayout.addRow("Logo Path:", logoLayout)
        
        # Reset button
        resetSMLayout = QtWidgets.QHBoxLayout()
        resetSMLayout.addStretch()
        self.resetShotMaskBtn = QtWidgets.QPushButton("Reset Shot Mask Settings")
        resetSMLayout.addWidget(self.resetShotMaskBtn)
        resetSMLayout.addStretch()
        
        shotMaskGroup.add_layout(shotMaskLayout)
        shotMaskGroup.add_layout(resetSMLayout)
        layout.addWidget(shotMaskGroup)
        
        # Add logging if needed
        loggingGroup = ConestogaCollapsibleGrpWidget("Logging")
        loggingLayout = QtWidgets.QVBoxLayout()
        
        self.loggingTextEdit = QtWidgets.QPlainTextEdit()
        self.loggingTextEdit.setReadOnly(True)
        
        logControlsLayout = QtWidgets.QHBoxLayout()
        self.logToScriptEditorCB = QtWidgets.QCheckBox("Log to Script Editor")
        self.clearLogBtn = QtWidgets.QPushButton("Clear Log")
        logControlsLayout.addWidget(self.logToScriptEditorCB)
        logControlsLayout.addStretch()
        logControlsLayout.addWidget(self.clearLogBtn)
        
        loggingLayout.addWidget(self.loggingTextEdit)
        loggingLayout.addLayout(logControlsLayout)
        
        loggingGroup.add_layout(loggingLayout)
        layout.addWidget(loggingGroup)
        
        layout.addStretch()
        
        # Connect signals
        self.ffmpegSelectBtn.clicked.connect(self.select_ffmpeg)
        self.tempDirSelectBtn.clicked.connect(self.select_temp_dir)
        self.logoSelectBtn.clicked.connect(self.select_logo)
        self.resetPlayblastBtn.clicked.connect(self.reset_playblast_settings)
        self.resetShotMaskBtn.clicked.connect(self.reset_shot_mask_settings)
        self.clearLogBtn.clicked.connect(self.loggingTextEdit.clear)
        
    def select_ffmpeg(self):
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Select FFmpeg Executable", 
            self.ffmpegPathLE.text(), 
            "Executable Files (*.exe);;All Files (*)")
        if file_path:
            self.ffmpegPathLE.setText(file_path)
            # Update FFmpeg path in settings
            ConestogaPlayblastUtils.set_ffmpeg_path(file_path)
            
    def select_temp_dir(self):
        dir_path = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Select Temporary Directory", 
            self.tempDirLE.text())
        if dir_path:
            self.tempDirLE.setText(dir_path)
            # Update temp directory in settings
            ConestogaPlayblastUtils.set_temp_output_dir_path(dir_path)
            
    def select_logo(self):
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Select Logo Image", 
            self.logoPathLE.text(), 
            "Image Files (*.png *.jpg *.jpeg *.tif *.tiff);;All Files (*)")
        if file_path:
            self.logoPathLE.setText(file_path)
            # Update logo path in settings
            if hasattr(ConestogaPlayblastUtils, 'set_logo_path'):
                ConestogaPlayblastUtils.set_logo_path(file_path)
            
    def reset_playblast_settings(self):
        result = QtWidgets.QMessageBox.question(
            self, "Confirm Reset", 
            "Are you sure you want to reset playblast settings to defaults?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        if result == QtWidgets.QMessageBox.Yes:
            # Reset playblast settings
            self.ffmpegPathLE.clear()
            self.tempDirLE.clear()
            self.tempFormatCombo.setCurrentIndex(0)
            
    def reset_shot_mask_settings(self):
        result = QtWidgets.QMessageBox.question(
            self, "Confirm Reset", 
            "Are you sure you want to reset shot mask settings to defaults?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        if result == QtWidgets.QMessageBox.Yes:
            # Reset shot mask settings
            self.logoPathLE.clear()
            ConestogaShotMask.reset_settings()
            
#-------------------------------------------------------------------------
# Main UI Window
#-------------------------------------------------------------------------
class ConestogaPlayblastWindow(QtWidgets.QMainWindow):
    def __init__(self, parent=None):
        super(ConestogaPlayblastWindow, self).__init__(parent)
        self.setWindowTitle("Conestoga Playblast Tool")
        self.setWindowFlags(self.windowFlags() ^ QtCore.Qt.WindowContextHelpButtonHint)
        
        # Create central widget and main layout
        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QtWidgets.QVBoxLayout(central_widget)
        main_layout.setContentsMargins(2, 2, 2, 2)
        main_layout.setSpacing(0)
        
        # Create tab widget and tabs
        self.tab_widget = QtWidgets.QTabWidget()
        
        # Create and add the tab widgets
        self.playblast_tab = PlayblastTabWidget()
        self.shot_mask_tab = ShotMaskTabWidget()
        self.settings_tab = SettingsTabWidget()
        
        self.tab_widget.addTab(self.playblast_tab, "Playblast")
        self.tab_widget.addTab(self.shot_mask_tab, "Shot Mask")
        self.tab_widget.addTab(self.settings_tab, "Settings")
        
        main_layout.addWidget(self.tab_widget)
        
        # Add status bar with buttons
        status_layout = QtWidgets.QHBoxLayout()
        status_layout.setContentsMargins(4, 4, 4, 4)
        
        self.logo_label = QtWidgets.QLabel("Conestoga College")
        
        self.create_mask_btn = QtWidgets.QPushButton("Create Shot Mask")
        self.create_mask_btn.setToolTip("Create a new shot mask node")
        
        self.delete_mask_btn = QtWidgets.QPushButton("Delete Shot Mask")
        self.delete_mask_btn.setToolTip("Delete the shot mask node")
        
        status_layout.addWidget(self.logo_label)
        status_layout.addStretch()
        status_layout.addWidget(self.create_mask_btn)
        status_layout.addWidget(self.delete_mask_btn)
        
        main_layout.addLayout(status_layout)
        
        # Connect signals
        self.create_mask_btn.clicked.connect(self.shot_mask_tab.create_mask)
        self.delete_mask_btn.clicked.connect(self.shot_mask_tab.delete_mask)
        self.playblast_tab.artist_name_changed.connect(self.update_artist_name)
        self.shot_mask_tab.collapsed_state_changed.connect(self.adjust_size)
        
        # Initial update
        self.update_mask_button_states()
        
    def update_artist_name(self, name):
        if name:
            self.logo_label.setText("Conestoga College - {0}".format(name))
        else:
            self.logo_label.setText("Conestoga College")
            
    def update_mask_button_states(self):
        has_mask = ConestogaShotMask.get_mask() is not None
        self.create_mask_btn.setEnabled(not has_mask)
        self.delete_mask_btn.setEnabled(has_mask)
        
    def showEvent(self, event):
        super(ConestogaPlayblastWindow, self).showEvent(event)
        self.update_mask_button_states()
        
    def adjust_size(self):
        self.adjustSize()
        
#-------------------------------------------------------------------------
# Global Variable and UI Display Functions
#-------------------------------------------------------------------------
_conestoga_playblast_window = None

def show_ui():
    """Show the Conestoga Playblast Tool UI"""
    global _conestoga_playblast_window
    
    if _conestoga_playblast_window is None:
        # Load the plugin
        ConestogaPlayblastUtils.load_plugin()
        
        # Get Maya main window as parent
        maya_main_window = None
        for obj in QtWidgets.QApplication.topLevelWidgets():
            if obj.objectName() == "MayaWindow":
                maya_main_window = obj
                break
        
        # Create the window
        _conestoga_playblast_window = ConestogaPlayblastWindow(maya_main_window)
        
    # Show the window
    _conestoga_playblast_window.show()
    _conestoga_playblast_window.raise_()
    _conestoga_playblast_window.activateWindow()
    
    return _conestoga_playblast_window

def close_ui():
    """Close the Conestoga Playblast Tool UI"""
    global _conestoga_playblast_window
    
    if _conestoga_playblast_window is not None:
        _conestoga_playblast_window.close()
        _conestoga_playblast_window = None
        
# Auto-run when executed directly
if __name__ == "__main__":
    show_ui()