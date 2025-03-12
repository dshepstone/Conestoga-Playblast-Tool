###############################################################################
# Name:
#   cp_playblast_ui.py
#
# Usage:
#   Launch the CP Playblast UI
#
# Copyright (C) 2025 All rights reserved.
###############################################################################

import copy
import os
import sys
import time
import traceback

from functools import partial

try:
    from PySide6 import QtCore
    from PySide6 import QtGui
    from PySide6 import QtWidgets
    from shiboken6 import getCppPointer
    from shiboken6 import wrapInstance
except:
    from PySide2 import QtCore
    from PySide2 import QtGui
    from PySide2 import QtWidgets
    from shiboken2 import getCppPointer
    from shiboken2 import wrapInstance

import maya.cmds as cmds
import maya.mel as mel
import maya.api.OpenMaya as om
import maya.OpenMayaUI as omui

# Note: We still use the original preset module
from conestoga_playblast_presets import ConestogaPlayblastCustomPresets, ConestogaShotMaskCustomPresets


class CPPlayblastUtils(object):

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
                om.MGlobal.displayError("Failed to load CP Playblast plug-in: {0}".format(cls.PLUG_IN_NAME))
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

    @classmethod
    def dpi_real_scale_value(cls):
        scale_value = 1.0
        try:
            # This command does not exist on macOS
            scale_value = cmds.mayaDpiSetting(query=True, rsv=True)
        except:
            pass

        return scale_value


class CPCollapsibleGrpHeader(QtWidgets.QWidget):

    clicked = QtCore.Signal()

    def __init__(self, text, parent=None):
        super(CPCollapsibleGrpHeader, self).__init__(parent)

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

        self.main_layout = QtWidgets.QHBoxLayout(self)
        self.main_layout.setContentsMargins(4, 4, 4, 4)
        self.main_layout.addWidget(self.icon_label)
        self.main_layout.addWidget(self.text_label)

        self.set_text(text)
        self.set_expanded(False)

    def set_text(self, text):
        self.text_label.setText("<b>{0}</b>".format(text))

    def set_background_color(self, color):
        if not color:
            color = QtWidgets.QPushButton().palette().color(QtGui.QPalette.Button)

        palette = self.palette()
        palette.setColor(QtGui.QPalette.Window, color)
        self.setPalette(palette)

    def is_expanded(self):
        return self._expanded

    def set_expanded(self, expanded):
        self._expanded = expanded

        if(self._expanded):
            self.icon_label.setPixmap(self.expanded_pixmap)
        else:
            self.icon_label.setPixmap(self.collapsed_pixmap)

    def mouseReleaseEvent(self, event):
        self.clicked.emit()  # pylint: disable=E1101


class CPCollapsibleGrpWidget(QtWidgets.QWidget):

    collapsed_state_changed = QtCore.Signal()

    def __init__(self, text, parent=None):
        super(CPCollapsibleGrpWidget, self).__init__(parent)

        self.append_stretch_on_collapse = False
        self.stretch_appended = False

        self.header_wdg = CPCollapsibleGrpHeader(text)
        self.header_wdg.clicked.connect(self.on_header_clicked)  # pylint: disable=E1101

        self.body_wdg = QtWidgets.QWidget()
        self.body_wdg.setAutoFillBackground(True)

        palette = self.body_wdg.palette()
        palette.setColor(QtGui.QPalette.Window, palette.color(QtGui.QPalette.Window).lighter(110))
        self.body_wdg.setPalette(palette)

        self.body_layout = QtWidgets.QVBoxLayout(self.body_wdg)
        self.body_layout.setContentsMargins(4, 2, 4, 2)
        self.body_layout.setSpacing(3)
        self.body_layout.setAlignment(QtCore.Qt.AlignTop)

        self.main_layout = QtWidgets.QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
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

        self.collapsed_state_changed.emit()  # pylint: disable=E1101


class CPColorButton(QtWidgets.QWidget):

    color_changed = QtCore.Signal()

    def __init__(self, color=(1.0, 1.0, 1.0), parent=None):
        super(CPColorButton, self).__init__(parent)

        self.setObjectName("CPColorButton")

        self.create_control()

        self.set_size(50, 16)
        self.set_color(color)

    def create_control(self):
        window = cmds.window()
        color_slider_name = cmds.colorSliderGrp()

        self._color_slider_obj = omui.MQtUtil.findControl(color_slider_name)
        if self._color_slider_obj:
            if sys.version_info.major >= 3:
                self._color_slider_widget = wrapInstance(int(self._color_slider_obj), QtWidgets.QWidget)  # pylint: disable=E0602
            else:
                self._color_slider_widget = wrapInstance(long(self._color_slider_obj), QtWidgets.QWidget)  # pylint: disable=E0602

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
            return omui.MQtUtil.fullName(int(self._color_slider_obj))  # pylint: disable=E0602
        else:
            return omui.MQtUtil.fullName(long(self._color_slider_obj))  # pylint: disable=E0602

    def set_size(self, width, height):
        scale_value = CPPlayblastUtils.dpi_real_scale_value()

        self._color_slider_widget.setFixedWidth(int(width * scale_value))
        self._color_widget.setFixedHeight(int(height * scale_value))

    def set_color(self, color):
        cmds.colorSliderGrp(self.get_full_name(), e=True, rgbValue=(color[0], color[1], color[2]))
        self.on_color_changed()

    def get_color(self):
        return cmds.colorSliderGrp(self.get_full_name(), q=True, rgbValue=True)

    def on_color_changed(self, *args):
        self.color_changed.emit()  # pylint: disable=E1101


class CPLineEdit(QtWidgets.QLineEdit):

    TYPE_PLAYBLAST_OUTPUT_PATH = 0
    TYPE_PLAYBLAST_OUTPUT_FILENAME = 1
    TYPE_SHOT_MASK_LABEL = 2

    PLAYBLAST_OUTPUT_PATH_LOOKUP = [
        ("Project", "{project}"),
        ("Temp", "{temp}"),
    ]

    PLAYBLAST_OUTPUT_FILENAME_LOOKUP = [
        ("Scene Name", "{scene}"),
        ("Camera Name", "{camera}"),
        ("Timestamp", "{timestamp}"),
    ]

    SHOT_MASK_LABEL_LOOKUP = [
        ("Scene Name", "{scene}"),
        ("Frame Counter", "{counter}"),
        ("Camera Name", "{camera}"),
        ("Focal Length", "{focal_length}"),
        ("Logo", "{logo}"),
        ("Image", "{image=<image_path>}"),
        ("User Name", "{username}"),
        ("Date", "{date}"),
    ]

    def __init__(self, le_type, parent=None):
        super(CPLineEdit, self).__init__(parent)

        self.le_type = le_type

        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)

        self.customContextMenuRequested.connect(self.show_context_menu)

    def show_context_menu(self, pos):
        context_menu = QtWidgets.QMenu(self)

        action = context_menu.addAction("Insert {tag}")
        action.setEnabled(False)

        context_menu.addSeparator()

        lookup = []
        if self.le_type == CPLineEdit.TYPE_PLAYBLAST_OUTPUT_PATH:
            lookup.extend(CPLineEdit.PLAYBLAST_OUTPUT_PATH_LOOKUP)
            lookup.extend(ConestogaPlayblastCustomPresets.PLAYBLAST_OUTPUT_PATH_LOOKUP)
        elif self.le_type == CPLineEdit.TYPE_PLAYBLAST_OUTPUT_FILENAME:
            lookup.extend(CPLineEdit.PLAYBLAST_OUTPUT_FILENAME_LOOKUP)
            lookup.extend(ConestogaPlayblastCustomPresets.PLAYBLAST_OUTPUT_FILENAME_LOOKUP)
        elif self.le_type == CPLineEdit.TYPE_SHOT_MASK_LABEL:
            lookup.extend(CPLineEdit.SHOT_MASK_LABEL_LOOKUP)
            lookup.extend(ConestogaShotMaskCustomPresets.SHOT_MASK_LABEL_LOOKUP)

        for item in lookup:
            action = context_menu.addAction(item[0])
            action.setData(item[1])
            action.triggered.connect(self.on_context_menu_item_selected)

        context_menu.exec_(self.mapToGlobal(pos))

    def on_context_menu_item_selected(self):
        self.insert(self.sender().data())


class CPFormLayout(QtWidgets.QGridLayout):

    def __init__(self, parent=None):
        super(CPFormLayout, self).__init__(parent)

        self.setContentsMargins(0, 0, 0, 8)
        self.setColumnMinimumWidth(0, 80)
        self.setHorizontalSpacing(6)

    def addWidgetRow(self, row, label, widget):
        self.addWidget(QtWidgets.QLabel(label), row, 0, QtCore.Qt.AlignRight)
        self.addWidget(widget, row, 1)

    def addLayoutRow(self, row, label, layout):
        self.addWidget(QtWidgets.QLabel(label), row, 0, QtCore.Qt.AlignRight)
        self.addLayout(layout, row, 1)


class CPCameraSelectDialog(QtWidgets.QDialog):

    def __init__(self, parent):
        super(CPCameraSelectDialog, self).__init__(parent)

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

        # Apply modern styling
        self.setStyleSheet("""
            QDialog {
                background-color: #2D2D30;
                color: #E6E6E6;
            }
            QListWidget {
                background-color: #383838;
                border: 1px solid #555555;
                border-radius: 3px;
                padding: 2px;
                color: #E6E6E6;
            }
            QListWidget::item:selected {
                background-color: #3D7AAB;
            }
            QPushButton {
                background-color: #3D7AAB;
                border: none;
                border-radius: 3px;
                padding: 4px 8px;
                color: white;
            }
            QPushButton:hover {
                background-color: #4B94CF;
            }
            QPushButton:pressed {
                background-color: #2C5A8A;
            }
        """)

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

        self.camera_list_wdg.addItems(CPPlayblastUtils.cameras_in_scene(include_defaults, user_created_first))

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


class CPWorkspaceControl(object):

    def __init__(self, name):
        self.name = name
        self.widget = None

    def create(self, label, widget, ui_script=None):

        cmds.workspaceControl(self.name, label=label)

        if ui_script:
            cmds.workspaceControl(self.name, e=True, uiScript=ui_script)

        self.add_widget_to_layout(widget)
        self.set_visible(True)

    def restore(self, widget):
        self.add_widget_to_layout(widget)

    def add_widget_to_layout(self, widget):
        if widget:
            self.widget = widget
            self.widget.setAttribute(QtCore.Qt.WA_DontCreateNativeAncestors)

            if sys.version_info.major >= 3:
                workspace_control_ptr = int(omui.MQtUtil.findControl(self.name))
                widget_ptr = int(getCppPointer(self.widget)[0])
            else:
                workspace_control_ptr = long(omui.MQtUtil.findControl(self.name))  # pylint: disable=E0602
                widget_ptr = long(getCppPointer(self.widget)[0])  # pylint: disable=E0602

            omui.MQtUtil.addWidgetToMayaLayout(widget_ptr, workspace_control_ptr)

    def exists(self):
        return cmds.workspaceControl(self.name, q=True, exists=True)

    def is_visible(self):
        return cmds.workspaceControl(self.name, q=True, visible=True)

    def set_visible(self, visible):
        if visible:
            cmds.workspaceControl(self.name, e=True, restore=True)
        else:
            cmds.workspaceControl(self.name, e=True, visible=False)

    def set_label(self, label):
        cmds.workspaceControl(self.name, e=True, label=label)

    def is_floating(self):
        return cmds.workspaceControl(self.name, q=True, floating=True)

    def is_collapsed(self):
        return cmds.workspaceControl(self.name, q=True, collapse=True)


class CPPlayblast(QtCore.QObject):

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
        super(CPPlayblast, self).__init__()

        self.set_maya_logging_enabled(CPPlayblast.DEFAULT_MAYA_LOGGING_ENABLED)

        self.build_presets()

        self.set_camera(CPPlayblast.DEFAULT_CAMERA)
        self.set_resolution(CPPlayblast.DEFAULT_RESOLUTION)
        self.set_frame_range(CPPlayblast.DEFAULT_FRAME_RANGE)

        self.set_encoding(CPPlayblast.DEFAULT_CONTAINER, CPPlayblast.DEFAULT_ENCODER)
        self.set_h264_settings(CPPlayblast.DEFAULT_H264_QUALITY, CPPlayblast.DEFAULT_H264_PRESET)
        self.set_image_settings(CPPlayblast.DEFAULT_IMAGE_QUALITY)

        self.set_visibility(CPPlayblast.DEFAULT_VISIBILITY)

        self.initialize_ffmpeg_process()

    def build_presets(self):
        self.resolution_preset_names = []
        self.resolution_presets = {}

        for preset in CPPlayblast.RESOLUTION_PRESETS:
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

        for preset in CPPlayblast.VIEWPORT_VISIBILITY_PRESETS:
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
        if frame_range in CPPlayblast.FRAME_RANGE_PRESETS:
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
            for preset in CPPlayblast.FRAME_RANGE_PRESETS:
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
            self.log_error("Invaild visibility preset: {0}".format(visibility_preset_name))
            return None

        visibility_data = []

        preset_names = self.viewport_visibility_presets[visibility_preset_name]
        if preset_names:
            for lookup_item in CPPlayblast.VIEWPORT_VISIBILITY_LOOKUP:
                visibility_data.append(lookup_item[0] in preset_names)

        return visibility_data

    def get_viewport_visibility(self):
        model_panel = self.get_viewport_panel()
        if not model_panel:
            return None

        viewport_visibility = []
        try:
            for item in CPPlayblast.VIEWPORT_VISIBILITY_LOOKUP:
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
        for item in CPPlayblast.VIEWPORT_VISIBILITY_LOOKUP:
            visibility_flags[item[1]] = visibility_data[data_index]
            data_index += 1

        return visibility_flags

    def set_encoding(self, container_format, encoder):
        if container_format not in CPPlayblast.VIDEO_ENCODER_LOOKUP.keys():
            self.log_error("Invalid container: {0}. Expected one of {1}".format(container_format, CPPlayblast.VIDEO_ENCODER_LOOKUP.keys()))
            return

        if encoder not in CPPlayblast.VIDEO_ENCODER_LOOKUP[container_format]:
            self.log_error("Invalid encoder: {0}. Expected one of {1}".format(encoder, CPPlayblast.VIDEO_ENCODER_LOOKUP[container_format]))
            return

        self._container_format = container_format
        self._encoder = encoder

    def set_h264_settings(self, quality, preset):
        if not quality in CPPlayblast.H264_QUALITIES.keys():
            self.log_error("Invalid h264 quality: {0}. Expected one of {1}".format(quality, CPPlayblast.H264_QUALITIES.keys()))
            return

        if not preset in CPPlayblast.H264_PRESETS:
            self.log_error("Invalid h264 preset: {0}. Expected one of {1}".format(preset, CPPlayblast.H264_PRESETS))
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

        ffmpeg_path = CPPlayblastUtils.get_ffmpeg_path()
        if self.requires_ffmpeg() and not self.validate_ffmpeg(ffmpeg_path):
            self.log_error("ffmpeg executable is not configured. See script editor for details.")
            return

        temp_file_format = CPPlayblastUtils.get_temp_file_format()
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
            padding = CPPlayblast.DEFAULT_PADDING

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
            if cmds.attributeQuery(CPPlayblast.CAMERA_PLAYBLAST_START_ATTR, node=camera, exists=True) and cmds.attributeQuery(CPPlayblast.CAMERA_PLAYBLAST_END_ATTR, node=camera, exists=True):
                try:
                    start_frame = int(cmds.getAttr("{0}.{1}".format(camera, CPPlayblast.CAMERA_PLAYBLAST_START_ATTR)))
                    end_frame = int(cmds.getAttr("{0}.{1}".format(camera, CPPlayblast.CAMERA_PLAYBLAST_END_ATTR)))

                    self.log_output("Camera frame range enabled for '{0}' camera: ({1}, {2})\n".format(camera, start_frame, end_frame))
                except:
                    self.log_warning("Camera frame range disabled. Invalid attribute type(s) on '{0}' camera (expected integer or float). Defaulting to Playback range.\n".format(camera))

            else:
                self.log_warning("Camera frame range disabled. Attributes '{0}' and '{1}' do not exist on '{2}' camera. Defaulting to Playback range.\n".format(CPPlayblast.CAMERA_PLAYBLAST_START_ATTR, CPPlayblast.CAMERA_PLAYBLAST_END_ATTR, camera))

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

        crf = CPPlayblast.H264_QUALITIES[self._h264_quality]
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

        crf = CPPlayblast.H264_QUALITIES[self._h264_quality]
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
            temp_dir_path = CPPlayblastUtils.get_temp_output_dir_path()

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
            om.MGlobal.displayError("[CP Playblast] {0}".format(text))

        self.output_logged.emit("[ERROR] {0}".format(text))  # pylint: disable=E1101

    def log_warning(self, text):
        if self._log_to_maya:
            om.MGlobal.displayWarning("[CP Playblast] {0}".format(text))

        self.output_logged.emit("[WARNING] {0}".format(text))  # pylint: disable=E1101

    def log_output(self, text):
        if self._log_to_maya:
            om.MGlobal.displayInfo(text)

        self.output_logged.emit(text)  # pylint: disable=E1101


class CPPlayblastEncoderSettingsDialog(QtWidgets.QDialog):

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
        super(CPPlayblastEncoderSettingsDialog, self).__init__(parent)

        self.setWindowTitle("Encoder Settings")
        self.setWindowFlags(self.windowFlags() ^ QtCore.Qt.WindowContextHelpButtonHint)
        self.setModal(True)
        self.setMinimumWidth(220)

        self.create_widgets()
        self.create_layouts()
        self.create_connections()

        # Apply modern styling
        self.setStyleSheet("""
            QDialog {
                background-color: #2D2D30;
                color: #E6E6E6;
            }
            QGroupBox {
                background-color: #2A2A2A;
                border: 1px solid #3D3D3D;
                border-radius: 4px;
                margin-top: 1ex;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top center;
                padding: 0 5px;
                color: #4B94CF;
            }
            QComboBox, QSpinBox {
                background-color: #383838;
                border: 1px solid #555555;
                border-radius: 3px;
                padding: 3px;
                color: #E6E6E6;
            }
            QPushButton {
                background-color: #3D7AAB;
                border: none;
                border-radius: 3px;
                padding: 4px 8px;
                color: white;
            }
            QPushButton:hover {
                background-color: #4B94CF;
            }
            QPushButton:pressed {
                background-color: #2C5A8A;
            }
        """)

    def create_widgets(self):
        # h264
        self.h264_quality_combo = QtWidgets.QComboBox()
        self.h264_quality_combo.addItems(CPPlayblastEncoderSettingsDialog.H264_QUALITIES)

        self.h264_preset_combo = QtWidgets.QComboBox()
        self.h264_preset_combo.addItems(CPPlayblast.H264_PRESETS)

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
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        main_layout.addWidget(self.settings_stacked_wdg)
        main_layout.addLayout(button_layout)

    def create_connections(self):
        self.accept_btn.clicked.connect(self.accept)
        self.cancel_btn.clicked.connect(self.close)

    def set_page(self, page):
        if not page in CPPlayblastEncoderSettingsDialog.ENCODER_PAGES:
            return False

        self.settings_stacked_wdg.setCurrentIndex(CPPlayblastEncoderSettingsDialog.ENCODER_PAGES[page])
        return True

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


class CPPlayblastVisibilityDialog(QtWidgets.QDialog):

    def __init__(self, parent):
        super(CPPlayblastVisibilityDialog, self).__init__(parent)

        self.setWindowTitle("Customize Visibility")
        self.setWindowFlags(self.windowFlags() ^ QtCore.Qt.WindowContextHelpButtonHint)
        self.setModal(True)

        visibility_layout = QtWidgets.QGridLayout()

        index = 0
        self.visibility_checkboxes = []

        for i in range(len(CPPlayblast.VIEWPORT_VISIBILITY_LOOKUP)):
            checkbox = QtWidgets.QCheckBox(CPPlayblast.VIEWPORT_VISIBILITY_LOOKUP[i][0])

            visibility_layout.addWidget(checkbox, index / 3, index % 3)
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
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        main_layout.addWidget(visibility_grp)
        main_layout.addStretch()
        main_layout.addLayout(button_layout)

        # Apply modern styling
        self.setStyleSheet("""
            QDialog {
                background-color: #2D2D30;
                color: #E6E6E6;
            }
            QGroupBox {
                background-color: #2A2A2A;
                border: 1px solid #3D3D3D;
                border-radius: 4px;
            }
            QCheckBox {
                color: #E6E6E6;
            }
            QCheckBox::indicator {
                width: 14px;
                height: 14px;
            }
            QPushButton {
                background-color: #3D7AAB;
                border: none;
                border-radius: 3px;
                padding: 4px 8px;
                color: white;
            }
            QPushButton:hover {
                background-color: #4B94CF;
            }
            QPushButton:pressed {
                background-color: #2C5A8A;
            }
        """)

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


class CPPlayblastWidget(QtWidgets.QWidget):

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

    CONTAINER_PRESETS = [
        "mov",
        "mp4",
        "Image",
    ]

    collapsed_state_changed = QtCore.Signal()


    def __init__(self, parent=None):
        super(CPPlayblastWidget, self).__init__(parent)

        self._playblast = CPPlayblast()

        self._settings_dialog = None
        self._encoder_settings_dialog = None
        self._visibility_dialog = None

        self.create_widgets()
        self.create_layouts()
        self.create_connections()

        self.load_settings()

    def create_widgets(self):
        scale_value = CPPlayblastUtils.dpi_real_scale_value()

        button_height = int(19 * scale_value)
        icon_button_width = int(24 * scale_value)
        icon_button_height = int(18 * scale_value)
        combo_box_min_width = int(100 * scale_value)
        spin_box_min_width = int(40 * scale_value)

        # Create a more modern look with custom styling
        self.setStyleSheet("""
            QWidget {
                background-color: #2D2D30;
                color: #E6E6E6;
            }
            QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
                background-color: #383838;
                border: 1px solid #555555;
                border-radius: 3px;
                padding: 2px;
                selection-background-color: #3D7AAB;
            }
            QPushButton {
                background-color: #3D7AAB;
                border: none;
                border-radius: 3px;
                padding: 4px 8px;
                color: white;
            }
            QPushButton:hover {
                background-color: #4B94CF;
            }
            QPushButton:pressed {
                background-color: #2C5A8A;
            }
            QCheckBox {
                spacing: 5px;
            }
            QCheckBox::indicator {
                width: 14px;
                height: 14px;
            }
            CPCollapsibleGrpWidget {
                border: 1px solid #555555;
                border-radius: 3px;
                margin-top: 2px;
            }
            QLabel {
                color: #E6E6E6;
            }
        """)

        self.output_dir_path_le = CPLineEdit(CPLineEdit.TYPE_PLAYBLAST_OUTPUT_PATH)
        self.output_dir_path_le.setPlaceholderText("{project}/movies")

        self.output_dir_path_select_btn = QtWidgets.QPushButton("...")
        self.output_dir_path_select_btn.setFixedSize(icon_button_width, icon_button_height)
        self.output_dir_path_select_btn.setToolTip("Select Output Directory")

        self.output_dir_path_show_folder_btn = QtWidgets.QPushButton(QtGui.QIcon(":fileOpen.png"), "")
        self.output_dir_path_show_folder_btn.setFixedSize(icon_button_width, icon_button_height)
        self.output_dir_path_show_folder_btn.setToolTip("Show in Folder")

        self.output_filename_le = CPLineEdit(CPLineEdit.TYPE_PLAYBLAST_OUTPUT_FILENAME)
        self.output_filename_le.setPlaceholderText("{scene}_{timestamp}")
        self.output_filename_le.setMaximumWidth(int(200 * scale_value))
        self.force_overwrite_cb = QtWidgets.QCheckBox("Force overwrite")

        # Name Generator widgets
        self.assignmentSpinBox = QtWidgets.QSpinBox()
        self.assignmentSpinBox.setRange(1, 99)
        self.assignmentSpinBox.setValue(1)
        self.assignmentSpinBox.setFixedWidth(50)

        self.lastnameLineEdit = QtWidgets.QLineEdit()
        self.lastnameLineEdit.setPlaceholderText("Last Name")

        self.firstnameLineEdit = QtWidgets.QLineEdit()
        self.firstnameLineEdit.setPlaceholderText("First Name")

        self.versionTypeCombo = QtWidgets.QComboBox()
        self.versionTypeCombo.addItems(["wip", "final"])

        self.versionNumberSpinBox = QtWidgets.QSpinBox()
        self.versionNumberSpinBox.setRange(1, 99)
        self.versionNumberSpinBox.setValue(1)
        self.versionNumberSpinBox.setFixedWidth(50)

        self.filenamePreviewLabel = QtWidgets.QLabel("A1_LastName_FirstName_wip_01.mov")
        self.filenamePreviewLabel.setStyleSheet("color: #FFC107; font-weight: bold;")

        self.generateFilenameButton = QtWidgets.QPushButton("Generate Filename")
        self.resetNameGeneratorButton = QtWidgets.QPushButton("Reset")

        # End of Name Generator widgets

        self.resolution_select_cmb = QtWidgets.QComboBox()
        self.resolution_select_cmb.setMinimumWidth(combo_box_min_width)
        self.resolution_select_cmb.addItems(self._playblast.resolution_preset_names)
        self.resolution_select_cmb.addItem("Custom")
        self.resolution_select_cmb.setCurrentText(CPPlayblast.DEFAULT_RESOLUTION)

        self.resolution_width_sb = QtWidgets.QSpinBox()
        self.resolution_width_sb.setButtonSymbols(QtWidgets.QSpinBox.NoButtons)
        self.resolution_width_sb.setRange(1, 9999)
        self.resolution_width_sb.setMinimumWidth(spin_box_min_width)
        self.resolution_width_sb.setAlignment(QtCore.Qt.AlignRight)
        self.resolution_height_sb = QtWidgets.QSpinBox()
        self.resolution_height_sb.setButtonSymbols(QtWidgets.QSpinBox.NoButtons)
        self.resolution_height_sb.setRange(1, 9999)
        self.resolution_height_sb.setMinimumWidth(spin_box_min_width)
        self.resolution_height_sb.setAlignment(QtCore.Qt.AlignRight)

        self.camera_select_cmb = QtWidgets.QComboBox()
        self.camera_select_cmb.setMinimumWidth(combo_box_min_width)
        self.camera_select_hide_defaults_cb = QtWidgets.QCheckBox("Hide defaults")
        self.refresh_cameras()

        self.frame_range_cmb = QtWidgets.QComboBox()
        self.frame_range_cmb.setMinimumWidth(combo_box_min_width)
        self.frame_range_cmb.addItems(CPPlayblast.FRAME_RANGE_PRESETS)
        self.frame_range_cmb.addItem("Custom")
        self.frame_range_cmb.setCurrentText(CPPlayblast.DEFAULT_FRAME_RANGE)

        self.frame_range_start_sb = QtWidgets.QSpinBox()
        self.frame_range_start_sb.setButtonSymbols(QtWidgets.QSpinBox.NoButtons)
        self.frame_range_start_sb.setRange(-9999, 9999)
        self.frame_range_start_sb.setMinimumWidth(spin_box_min_width)
        self.frame_range_start_sb.setAlignment(QtCore.Qt.AlignRight)

        self.frame_range_end_sb = QtWidgets.QSpinBox()
        self.frame_range_end_sb.setButtonSymbols(QtWidgets.QSpinBox.NoButtons)
        self.frame_range_end_sb.setRange(-9999, 9999)
        self.frame_range_end_sb.setMinimumWidth(spin_box_min_width)
        self.frame_range_end_sb.setAlignment(QtCore.Qt.AlignRight)

        self.encoding_container_cmb = QtWidgets.QComboBox()
        self.encoding_container_cmb.setMinimumWidth(combo_box_min_width)
        self.encoding_container_cmb.addItems(CPPlayblastWidget.CONTAINER_PRESETS)
        self.encoding_container_cmb.setCurrentText(CPPlayblast.DEFAULT_CONTAINER)

        self.encoding_video_codec_cmb = QtWidgets.QComboBox()
        self.encoding_video_codec_cmb.setMinimumWidth(combo_box_min_width)
        self.encoding_video_codec_settings_btn = QtWidgets.QPushButton("Settings...")
        self.encoding_video_codec_settings_btn.setFixedHeight(button_height)

        self.visibility_cmb = QtWidgets.QComboBox()
        self.visibility_cmb.setMinimumWidth(combo_box_min_width)
        self.visibility_cmb.addItems(self._playblast.viewport_visibility_preset_names)
        self.visibility_cmb.addItem("Custom")
        self.visibility_cmb.setCurrentText(CPPlayblast.DEFAULT_VISIBILITY)

        self.visibility_customize_btn = QtWidgets.QPushButton("Customize...")
        self.visibility_customize_btn.setFixedHeight(button_height)

        self.overscan_cb = QtWidgets.QCheckBox("Overscan")
        self.overscan_cb.setChecked(False)

        self.ornaments_cb = QtWidgets.QCheckBox("Ornaments")
        self.ornaments_cb.setChecked(False)

        self.offscreen_cb = QtWidgets.QCheckBox("Offscreen")
        self.offscreen_cb.setChecked(False)

        self.viewer_cb = QtWidgets.QCheckBox("Show in Viewer")
        self.viewer_cb.setChecked(True)

        self.shot_mask_cb = QtWidgets.QCheckBox("Shot Mask")
        self.shot_mask_cb.setChecked(True)

        self.fit_shot_mask_cb = QtWidgets.QCheckBox("Fit Shot Mask")
        self.fit_shot_mask_cb.setChecked(False)

        self.output_edit = QtWidgets.QPlainTextEdit()
        self.output_edit.setFocusPolicy(QtCore.Qt.NoFocus)
        self.output_edit.setReadOnly(True)
        self.output_edit.setWordWrapMode(QtGui.QTextOption.NoWrap)
        self.output_edit.setStyleSheet("background-color: #1E1E1E; color: #CCCCCC; border: 1px solid #3D3D3D;")

        self.log_to_script_editor_cb = QtWidgets.QCheckBox("Log to Script Editor")
        self.log_to_script_editor_cb.setChecked(self._playblast.is_maya_logging_enabled())

        self.clear_btn = QtWidgets.QPushButton("Clear")
        self.clear_btn.setMinimumWidth(int(70 * scale_value))
        self.clear_btn.setFixedHeight(button_height)

        # Create execute button (was missing)
        self.execute_btn = QtWidgets.QPushButton("Create Playblast")
        self.execute_btn.setMinimumHeight(int(30 * scale_value))
        self.execute_btn.setStyleSheet("""
            background-color: #22883E;
            font-weight: bold;
            font-size: 14px;
        """)

    def create_layouts(self):
        # Create output path layout with enhanced styling
        output_path_layout = QtWidgets.QHBoxLayout()
        output_path_layout.setSpacing(2)
        output_path_layout.addWidget(self.output_dir_path_le)
        output_path_layout.addWidget(self.output_dir_path_select_btn)
        output_path_layout.addWidget(self.output_dir_path_show_folder_btn)

        # Create output file layout
        output_file_layout = QtWidgets.QHBoxLayout()
        output_file_layout.setSpacing(4)
        output_file_layout.addWidget(self.output_filename_le)
        output_file_layout.addWidget(self.force_overwrite_cb)

        # Main output section with a cleaner, modern header
        output_header = QtWidgets.QLabel("OUTPUT SETTINGS")
        output_header.setStyleSheet("font-weight: bold; color: #4B94CF; font-size: 13px; padding: 5px;")
        
        # Create form layout for output fields with modern spacing
        output_form = CPFormLayout()
        output_form.setContentsMargins(8, 8, 8, 12)
        output_form.setVerticalSpacing(10)
        output_form.addLayoutRow(0, "Output Dir:", output_path_layout)
        output_form.addLayoutRow(1, "Filename:", output_file_layout)
        
        output_layout = QtWidgets.QVBoxLayout()
        output_layout.addWidget(output_header)
        output_layout.addLayout(output_form)
        
        # Frame the output section
        output_frame = QtWidgets.QFrame()
        output_frame.setLayout(output_layout)
        output_frame.setStyleSheet("QFrame { background-color: #2A2A2A; border-radius: 5px; }")

        # Create Name Generator section with the same styling approach
        name_gen_header = QtWidgets.QLabel("NAME GENERATOR")
        name_gen_header.setStyleSheet("font-weight: bold; color: #4B94CF; font-size: 13px; padding: 5px;")
        
        # Create grid layout for name generator fields
        name_gen_grid = QtWidgets.QGridLayout()
        name_gen_grid.setColumnStretch(2, 1)  # Make the third column stretch
        name_gen_grid.setVerticalSpacing(8)
        name_gen_grid.setContentsMargins(8, 8, 8, 8)
        
        # Assignment field
        name_gen_grid.addWidget(QtWidgets.QLabel("Assignment:"), 0, 0)
        name_gen_grid.addWidget(self.assignmentSpinBox, 0, 1)
        
        # Last Name field
        name_gen_grid.addWidget(QtWidgets.QLabel("Last Name:"), 1, 0)
        name_gen_grid.addWidget(self.lastnameLineEdit, 1, 1, 1, 2)
        
        # First Name field
        name_gen_grid.addWidget(QtWidgets.QLabel("First Name:"), 2, 0)
        name_gen_grid.addWidget(self.firstnameLineEdit, 2, 1, 1, 2)
        
        # Version type dropdown
        name_gen_grid.addWidget(QtWidgets.QLabel("Type:"), 3, 0)
        name_gen_grid.addWidget(self.versionTypeCombo, 3, 1)
        
        # Version number
        name_gen_grid.addWidget(QtWidgets.QLabel("Version:"), 4, 0)
        name_gen_grid.addWidget(self.versionNumberSpinBox, 4, 1)
        
        # Preview field
        name_gen_grid.addWidget(QtWidgets.QLabel("Preview:"), 5, 0)
        name_gen_grid.addWidget(self.filenamePreviewLabel, 5, 1, 1, 2)
        
        # Generate and Reset buttons side by side with a modern layout
        generate_btn_layout = QtWidgets.QHBoxLayout()
        generate_btn_layout.setContentsMargins(0, 10, 0, 0)
        generate_btn_layout.addStretch()
        generate_btn_layout.addWidget(self.generateFilenameButton)
        generate_btn_layout.addSpacing(8)
        generate_btn_layout.addWidget(self.resetNameGeneratorButton)
        generate_btn_layout.addStretch()
        
        name_gen_layout = QtWidgets.QVBoxLayout()
        name_gen_layout.addWidget(name_gen_header)
        name_gen_layout.addLayout(name_gen_grid)
        name_gen_layout.addLayout(generate_btn_layout)
        
        # Frame the name generator section
        name_gen_frame = QtWidgets.QFrame()
        name_gen_frame.setLayout(name_gen_layout)
        name_gen_frame.setStyleSheet("QFrame { background-color: #2A2A2A; border-radius: 5px; }")

        # Options Section - Redesigned with card-based layout
        options_header = QtWidgets.QLabel("PLAYBLAST OPTIONS")
        options_header.setStyleSheet("font-weight: bold; color: #4B94CF; font-size: 13px; padding: 5px;")
        
        # Camera card 
        camera_card = QtWidgets.QFrame()
        camera_card.setStyleSheet("QFrame { background-color: #323232; border-radius: 4px; margin: 2px; }")
        
        camera_title = QtWidgets.QLabel("Camera")
        camera_title.setStyleSheet("font-weight: bold; color: #CCCCCC; padding-left: 5px;")
        
        camera_options_layout = QtWidgets.QHBoxLayout()
        camera_options_layout.setSpacing(6)
        camera_options_layout.addWidget(self.camera_select_cmb)
        camera_options_layout.addWidget(self.camera_select_hide_defaults_cb)
        camera_options_layout.addStretch()
        
        camera_layout = QtWidgets.QVBoxLayout(camera_card)
        camera_layout.setContentsMargins(10, 8, 10, 8)
        camera_layout.addWidget(camera_title)
        camera_layout.addLayout(camera_options_layout)

        # Resolution card
        resolution_card = QtWidgets.QFrame()
        resolution_card.setStyleSheet("QFrame { background-color: #323232; border-radius: 4px; margin: 2px; }")
        
        resolution_title = QtWidgets.QLabel("Resolution")
        resolution_title.setStyleSheet("font-weight: bold; color: #CCCCCC; padding-left: 5px;")
        
        resolution_layout = QtWidgets.QHBoxLayout()
        resolution_layout.setSpacing(4)
        resolution_layout.addWidget(self.resolution_select_cmb)
        resolution_layout.addSpacing(2)
        resolution_layout.addWidget(self.resolution_width_sb)
        resolution_layout.addWidget(QtWidgets.QLabel("x"))
        resolution_layout.addWidget(self.resolution_height_sb)
        resolution_layout.addStretch()
        
        resolution_card_layout = QtWidgets.QVBoxLayout(resolution_card)
        resolution_card_layout.setContentsMargins(10, 8, 10, 8)
        resolution_card_layout.addWidget(resolution_title)
        resolution_card_layout.addLayout(resolution_layout)

        # Frame Range card
        frame_range_card = QtWidgets.QFrame()
        frame_range_card.setStyleSheet("QFrame { background-color: #323232; border-radius: 4px; margin: 2px; }")
        
        frame_range_title = QtWidgets.QLabel("Frame Range")
        frame_range_title.setStyleSheet("font-weight: bold; color: #CCCCCC; padding-left: 5px;")
        
        frame_range_layout = QtWidgets.QHBoxLayout()
        frame_range_layout.setSpacing(4)
        frame_range_layout.addWidget(self.frame_range_cmb)
        frame_range_layout.addSpacing(2)
        frame_range_layout.addWidget(self.frame_range_start_sb)
        frame_range_layout.addWidget(self.frame_range_end_sb)
        frame_range_layout.addStretch()
        
        frame_range_card_layout = QtWidgets.QVBoxLayout(frame_range_card)
        frame_range_card_layout.setContentsMargins(10, 8, 10, 8)
        frame_range_card_layout.addWidget(frame_range_title)
        frame_range_card_layout.addLayout(frame_range_layout)

        # Encoding card
        encoding_card = QtWidgets.QFrame()
        encoding_card.setStyleSheet("QFrame { background-color: #323232; border-radius: 4px; margin: 2px; }")
        
        encoding_title = QtWidgets.QLabel("Encoding")
        encoding_title.setStyleSheet("font-weight: bold; color: #CCCCCC; padding-left: 5px;")
        
        encoding_layout = QtWidgets.QHBoxLayout()
        encoding_layout.setSpacing(2)
        encoding_layout.addWidget(self.encoding_container_cmb)
        encoding_layout.addWidget(self.encoding_video_codec_cmb)
        encoding_layout.addWidget(self.encoding_video_codec_settings_btn)
        encoding_layout.addStretch()
        
        encoding_card_layout = QtWidgets.QVBoxLayout(encoding_card)
        encoding_card_layout.setContentsMargins(10, 8, 10, 8)
        encoding_card_layout.addWidget(encoding_title)
        encoding_card_layout.addLayout(encoding_layout)

        # Visibility card
        visibility_card = QtWidgets.QFrame()
        visibility_card.setStyleSheet("QFrame { background-color: #323232; border-radius: 4px; margin: 2px; }")
        
        visibility_title = QtWidgets.QLabel("Visibility")
        visibility_title.setStyleSheet("font-weight: bold; color: #CCCCCC; padding-left: 5px;")
        
        visibility_layout = QtWidgets.QHBoxLayout()
        visibility_layout.setSpacing(4)
        visibility_layout.addWidget(self.visibility_cmb)
        visibility_layout.addWidget(self.visibility_customize_btn)
        visibility_layout.addStretch()
        
        visibility_card_layout = QtWidgets.QVBoxLayout(visibility_card)
        visibility_card_layout.setContentsMargins(10, 8, 10, 8)
        visibility_card_layout.addWidget(visibility_title)
        visibility_card_layout.addLayout(visibility_layout)

        # Checkbox options with a modern grid approach
        options_checkboxes_card = QtWidgets.QFrame()
        options_checkboxes_card.setStyleSheet("QFrame { background-color: #323232; border-radius: 4px; margin: 2px; }")
        
        checkboxes_title = QtWidgets.QLabel("Additional Options")
        checkboxes_title.setStyleSheet("font-weight: bold; color: #CCCCCC; padding-left: 5px;")
        
        checkbox_grid = QtWidgets.QGridLayout()
        checkbox_grid.addWidget(self.ornaments_cb, 0, 0)
        checkbox_grid.addWidget(self.overscan_cb, 0, 1)
        checkbox_grid.addWidget(self.offscreen_cb, 0, 2)
        checkbox_grid.addWidget(self.shot_mask_cb, 1, 0)
        checkbox_grid.addWidget(self.fit_shot_mask_cb, 1, 1)
        checkbox_grid.addWidget(self.viewer_cb, 1, 2)
        
        options_checkboxes_layout = QtWidgets.QVBoxLayout(options_checkboxes_card)
        options_checkboxes_layout.setContentsMargins(10, 8, 10, 8)
        options_checkboxes_layout.addWidget(checkboxes_title)
        options_checkboxes_layout.addLayout(checkbox_grid)

        # Layout all option cards in a vertical flow
        options_cards_layout = QtWidgets.QVBoxLayout()
        options_cards_layout.setSpacing(8)
        options_cards_layout.addWidget(camera_card)
        options_cards_layout.addWidget(resolution_card)
        options_cards_layout.addWidget(frame_range_card)
        options_cards_layout.addWidget(encoding_card)
        options_cards_layout.addWidget(visibility_card)
        options_cards_layout.addWidget(options_checkboxes_card)
        
        options_layout = QtWidgets.QVBoxLayout()
        options_layout.addWidget(options_header)
        options_layout.addLayout(options_cards_layout)
        
        options_frame = QtWidgets.QFrame()
        options_frame.setLayout(options_layout)
        options_frame.setStyleSheet("QFrame { background-color: #2A2A2A; border-radius: 5px; }")

        # Logging section
        logging_header = QtWidgets.QLabel("LOGGING")
        logging_header.setStyleSheet("font-weight: bold; color: #4B94CF; font-size: 13px; padding: 5px;")
        
        logging_button_layout = QtWidgets.QHBoxLayout()
        logging_button_layout.setContentsMargins(8, 4, 8, 10)
        logging_button_layout.addWidget(self.log_to_script_editor_cb)
        logging_button_layout.addStretch()
        logging_button_layout.addWidget(self.clear_btn)
        
        logging_layout = QtWidgets.QVBoxLayout()
        logging_layout.addWidget(logging_header)
        logging_layout.addWidget(self.output_edit)
        logging_layout.addLayout(logging_button_layout)
        
        logging_frame = QtWidgets.QFrame()
        logging_frame.setLayout(logging_layout)
        logging_frame.setStyleSheet("QFrame { background-color: #2A2A2A; border-radius: 5px; }")

        # Create Playblast Button
        execute_layout = QtWidgets.QHBoxLayout()
        execute_layout.setContentsMargins(0, 10, 0, 10)
        execute_layout.addStretch()
        execute_layout.addWidget(self.execute_btn)
        execute_layout.addStretch()

        # Main layout with all sections in a vertical flow
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        main_layout.addWidget(output_frame)
        main_layout.addWidget(name_gen_frame)
        main_layout.addWidget(options_frame)
        main_layout.addLayout(execute_layout)
        main_layout.addWidget(logging_frame)