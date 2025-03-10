###############################################################################
# Name:
#   conestoga_playblast_ui.py
#
# Author:
#   Conestoga College
#
# Usage:
#   Launch the Conestoga Playblast UI
#
# Copyright (C) 2025 Conestoga College. All rights reserved.
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

from conestoga_playblast_presets import ConestogaPlayblastCustomPresets, ConestogaShotMaskCustomPresets


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
                om.MGlobal.displayError("Failed to load Conestoga Playblast plug-in: {0}".format(cls.PLUG_IN_NAME))
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
    def get_temp_output_dir_path(self):
        return cmds.ConestogaPlayblast(q=True, tp=True)[0]  # pylint: disable=E1101

    @classmethod
    def set_temp_output_dir_path(self, path):
        cmds.ConestogaPlayblast(e=True, tp=path)  # pylint: disable=E1101

    @classmethod
    def is_temp_output_env_var_set(cls):
        return cmds.ConestogaPlayblast(tev=True)[0]  # pylint: disable=E1101

    @classmethod
    def get_temp_file_format(self):
        return cmds.ConestogaPlayblast(q=True, tf=True)[0]  # pylint: disable=E1101

    @classmethod
    def set_temp_file_format(self, file_format):
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


class ConestogaCollapsibleGrpWidget(QtWidgets.QWidget):

    collapsed_state_changed = QtCore.Signal()

    def __init__(self, text, parent=None):
        super(ConestogaCollapsibleGrpWidget, self).__init__(parent)

        self.append_stretch_on_collapse = False
        self.stretch_appended = False

        self.header_wdg = ConestogaCollapsibleGrpHeader(text)
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
        scale_value = ConestogaPlayblastUtils.dpi_real_scale_value()

        self._color_slider_widget.setFixedWidth(int(width * scale_value))
        self._color_widget.setFixedHeight(int(height * scale_value))

    def set_color(self, color):
        cmds.colorSliderGrp(self.get_full_name(), e=True, rgbValue=(color[0], color[1], color[2]))
        self.on_color_changed()

    def get_color(self):
        return cmds.colorSliderGrp(self.get_full_name(), q=True, rgbValue=True)

    def on_color_changed(self, *args):
        self.color_changed.emit()  # pylint: disable=E1101


class ConestogaLineEdit(QtWidgets.QLineEdit):

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
            lookup.extend(ConestogaLineEdit.PLAYBLAST_OUTPUT_PATH_LOOKUP)
            lookup.extend(ConestogaPlayblastCustomPresets.PLAYBLAST_OUTPUT_PATH_LOOKUP)
        elif self.le_type == ConestogaLineEdit.TYPE_PLAYBLAST_OUTPUT_FILENAME:
            lookup.extend(ConestogaLineEdit.PLAYBLAST_OUTPUT_FILENAME_LOOKUP)
            lookup.extend(ConestogaPlayblastCustomPresets.PLAYBLAST_OUTPUT_FILENAME_LOOKUP)
        elif self.le_type == ConestogaLineEdit.TYPE_SHOT_MASK_LABEL:
            lookup.extend(ConestogaLineEdit.SHOT_MASK_LABEL_LOOKUP)
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


class ConestogaCameraSelectDialog(QtWidgets.QDialog):

    def __init__(self, parent):
        super(ConestogaCameraSelectDialog, self).__init__(parent)

        self.setWindowTitle("Camera Select")
        # self.setWindowFlags(self.windowFlags() ^ QtCore.Qt.WindowContextHelpButtonHint)
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


class ConestogaWorkspaceControl(object):

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
            self.log_error("Invaild visibility preset: {0}".format(visibility_preset_name))
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
                self.log_error("Output file already exists. Eanble overwrite to ignore.")
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
        self.h264_quality_combo.addItems(ConestogaPlayblastEncoderSettingsDialog.H264_QUALITIES)

        self.h264_preset_combo = QtWidgets.QComboBox()
        self.h264_preset_combo.addItems(ConestogaPlayblast.H264_PRESETS)

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
        if not page in ConestogaPlayblastEncoderSettingsDialog.ENCODER_PAGES:
            return False

        self.settings_stacked_wdg.setCurrentIndex(ConestogaPlayblastEncoderSettingsDialog.ENCODER_PAGES[page])
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


class ConestogaPlayblastVisibilityDialog(QtWidgets.QDialog):

    def __init__(self, parent):
        super(ConestogaPlayblastVisibilityDialog, self).__init__(parent)

        self.setWindowTitle("Customize Visibility")
        self.setWindowFlags(self.windowFlags() ^ QtCore.Qt.WindowContextHelpButtonHint)
        self.setModal(True)

        visibility_layout = QtWidgets.QGridLayout()

        index = 0
        self.visibility_checkboxes = []

        for i in range(len(ConestogaPlayblast.VIEWPORT_VISIBILITY_LOOKUP)):
            checkbox = QtWidgets.QCheckBox(ConestogaPlayblast.VIEWPORT_VISIBILITY_LOOKUP[i][0])

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


class ConestogaPlayblastWidget(QtWidgets.QWidget):

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

    # New option vars for name generator
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
        super(ConestogaPlayblastWidget, self).__init__(parent)

        self._playblast = ConestogaPlayblast()

        self._settings_dialog = None
        self._encoder_settings_dialog = None
        self._visibility_dialog = None

        self.create_widgets()
        self.create_layouts()
        self.create_connections()

        self.load_settings()

    def create_widgets(self):
        scale_value = ConestogaPlayblastUtils.dpi_real_scale_value()

        button_height = int(19 * scale_value)
        icon_button_width = int(24 * scale_value)
        icon_button_height = int(18 * scale_value)
        combo_box_min_width = int(100 * scale_value)
        spin_box_min_width = int(40 * scale_value)

        self.output_dir_path_le = ConestogaLineEdit(ConestogaLineEdit.TYPE_PLAYBLAST_OUTPUT_PATH)
        self.output_dir_path_le.setPlaceholderText("{project}/movies")

        self.output_dir_path_select_btn = QtWidgets.QPushButton("...")
        self.output_dir_path_select_btn.setFixedSize(icon_button_width, icon_button_height)
        self.output_dir_path_select_btn.setToolTip("Select Output Directory")

        self.output_dir_path_show_folder_btn = QtWidgets.QPushButton(QtGui.QIcon(":fileOpen.png"), "")
        self.output_dir_path_show_folder_btn.setFixedSize(icon_button_width, icon_button_height)
        self.output_dir_path_show_folder_btn.setToolTip("Show in Folder")

        self.output_filename_le = ConestogaLineEdit(ConestogaLineEdit.TYPE_PLAYBLAST_OUTPUT_FILENAME)
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
        self.filenamePreviewLabel.setStyleSheet("color: yellow; font-weight: bold;")

        self.generateFilenameButton = QtWidgets.QPushButton("Generate Filename")

        # End of Name Generator widgets

        self.resolution_select_cmb = QtWidgets.QComboBox()
        self.resolution_select_cmb.setMinimumWidth(combo_box_min_width)
        self.resolution_select_cmb.addItems(self._playblast.resolution_preset_names)
        self.resolution_select_cmb.addItem("Custom")
        self.resolution_select_cmb.setCurrentText(ConestogaPlayblast.DEFAULT_RESOLUTION)

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
        self.frame_range_cmb.addItems(ConestogaPlayblast.FRAME_RANGE_PRESETS)
        self.frame_range_cmb.addItem("Custom")
        self.frame_range_cmb.setCurrentText(ConestogaPlayblast.DEFAULT_FRAME_RANGE)

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
        self.encoding_container_cmb.addItems(ConestogaPlayblastWidget.CONTAINER_PRESETS)
        self.encoding_container_cmb.setCurrentText(ConestogaPlayblast.DEFAULT_CONTAINER)

        self.encoding_video_codec_cmb = QtWidgets.QComboBox()
        self.encoding_video_codec_cmb.setMinimumWidth(combo_box_min_width)
        self.encoding_video_codec_settings_btn = QtWidgets.QPushButton("Settings...")
        self.encoding_video_codec_settings_btn.setFixedHeight(button_height)

        self.visibility_cmb = QtWidgets.QComboBox()
        self.visibility_cmb.setMinimumWidth(combo_box_min_width)
        self.visibility_cmb.addItems(self._playblast.viewport_visibility_preset_names)
        self.visibility_cmb.addItem("Custom")
        self.visibility_cmb.setCurrentText(ConestogaPlayblast.DEFAULT_VISIBILITY)

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

        self.log_to_script_editor_cb = QtWidgets.QCheckBox("Log to Script Editor")
        self.log_to_script_editor_cb.setChecked(self._playblast.is_maya_logging_enabled())

        self.clear_btn = QtWidgets.QPushButton("Clear")
        self.clear_btn.setMinimumWidth(int(70 * scale_value))
        self.clear_btn.setFixedHeight(button_height)

    def create_layouts(self):
        # Create output path layout (spanning full width)
        output_path_layout = QtWidgets.QHBoxLayout()
        output_path_layout.setSpacing(2)
        output_path_layout.addWidget(self.output_dir_path_le)
        output_path_layout.addWidget(self.output_dir_path_select_btn)
        output_path_layout.addWidget(self.output_dir_path_show_folder_btn)

        # Create output file layout (spanning full width)
        output_file_layout = QtWidgets.QHBoxLayout()
        output_file_layout.setSpacing(4)
        output_file_layout.addWidget(self.output_filename_le)
        output_file_layout.addWidget(self.force_overwrite_cb)

        # Create form layout for output fields (spanning full width)
        output_layout = ConestogaFormLayout()
        output_layout.setContentsMargins(4, 14, 4, 14)
        output_layout.addLayoutRow(0, "Output Dir:", output_path_layout)
        output_layout.addLayoutRow(1, "Filename:", output_file_layout)

        # Create Name Generator section (spanning full width)
        name_gen_layout = QtWidgets.QVBoxLayout()
        name_gen_layout.setContentsMargins(4, 0, 4, 14)
        
        # Add title for name generator
        name_gen_title = QtWidgets.QLabel("Output Name Generator")
        name_gen_title.setStyleSheet("font-weight: bold;")
        name_gen_layout.addWidget(name_gen_title)
        
        # Create grid layout for name generator fields
        name_gen_grid = QtWidgets.QGridLayout()
        name_gen_grid.setColumnStretch(2, 1)  # Make the third column stretch
        
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
        
        # Add grid to layout
        name_gen_layout.addLayout(name_gen_grid)
        
        # Generate button
        generate_btn_layout = QtWidgets.QHBoxLayout()
        generate_btn_layout.addStretch()
        generate_btn_layout.addWidget(self.generateFilenameButton)
        generate_btn_layout.addStretch()
        name_gen_layout.addLayout(generate_btn_layout)
        
        # Create a collapsible widget for the name generator
        self.name_gen_grp = ConestogaCollapsibleGrpWidget("Name Generator")
        self.name_gen_grp.add_layout(name_gen_layout)

        # Continue with the rest of the layouts as before
        camera_options_layout = QtWidgets.QHBoxLayout()
        camera_options_layout.setSpacing(6)
        camera_options_layout.addWidget(self.camera_select_cmb)
        camera_options_layout.addWidget(self.camera_select_hide_defaults_cb)
        camera_options_layout.addStretch()

        resolution_layout = QtWidgets.QHBoxLayout()
        resolution_layout.setSpacing(4)
        resolution_layout.addWidget(self.resolution_select_cmb)
        resolution_layout.addSpacing(2)
        resolution_layout.addWidget(self.resolution_width_sb)
        resolution_layout.addWidget(QtWidgets.QLabel("x"))
        resolution_layout.addWidget(self.resolution_height_sb)
        resolution_layout.addStretch()

        frame_range_layout = QtWidgets.QHBoxLayout()
        frame_range_layout.setSpacing(4)
        frame_range_layout.addWidget(self.frame_range_cmb)
        frame_range_layout.addSpacing(2)
        frame_range_layout.addWidget(self.frame_range_start_sb)
        frame_range_layout.addWidget(self.frame_range_end_sb)
        frame_range_layout.addStretch()

        encoding_layout = QtWidgets.QHBoxLayout()
        encoding_layout.setSpacing(2)
        encoding_layout.addWidget(self.encoding_container_cmb)
        encoding_layout.addWidget(self.encoding_video_codec_cmb)
        encoding_layout.addWidget(self.encoding_video_codec_settings_btn)
        encoding_layout.addStretch()

        visibility_layout = QtWidgets.QHBoxLayout()
        visibility_layout.setSpacing(4)
        visibility_layout.addWidget(self.visibility_cmb)
        visibility_layout.addWidget(self.visibility_customize_btn)
        visibility_layout.addStretch()

        cb_options_layout_a = QtWidgets.QGridLayout()
        cb_options_layout_a.setColumnMinimumWidth(0, 100)
        cb_options_layout_a.addWidget(self.ornaments_cb, 0, 0)
        cb_options_layout_a.addWidget(self.overscan_cb, 0, 1)
        cb_options_layout_a.addWidget(self.offscreen_cb, 0, 2)
        cb_options_layout_a.setColumnStretch(2, 1)

        cb_options_layout_b = QtWidgets.QGridLayout()
        cb_options_layout_b.setColumnMinimumWidth(0, 100)
        cb_options_layout_b.addWidget(self.shot_mask_cb, 0, 0)
        cb_options_layout_b.addWidget(self.fit_shot_mask_cb, 0, 1)
        cb_options_layout_b.addWidget(self.viewer_cb, 0, 2)
        cb_options_layout_b.setColumnStretch(2, 1)

        options_layout = ConestogaFormLayout()
        options_layout.setVerticalSpacing(5)
        options_layout.addLayoutRow(0, "Camera:", camera_options_layout)
        options_layout.addLayoutRow(1, "Resolution:", resolution_layout)
        options_layout.addLayoutRow(2, "Frame Range:", frame_range_layout)
        options_layout.addLayoutRow(3, "Encoding:", encoding_layout)
        options_layout.addLayoutRow(4, "Visiblity:", visibility_layout)
        options_layout.addLayoutRow(5, "", cb_options_layout_a)
        options_layout.addLayoutRow(6, "", cb_options_layout_b)

        self.options_grp = ConestogaCollapsibleGrpWidget("Options")
        self.options_grp.add_layout(options_layout)

        logging_button_layout = QtWidgets.QHBoxLayout()
        logging_button_layout.setContentsMargins(4, 0, 4, 10)
        logging_button_layout.addWidget(self.log_to_script_editor_cb)
        logging_button_layout.addStretch()
        logging_button_layout.addWidget(self.clear_btn)

        self.logging_grp = ConestogaCollapsibleGrpWidget("Logging")
        self.logging_grp.body_layout.setContentsMargins(0, 0, 0, 0)
        self.logging_grp.append_stretch_on_collapse = True
        self.logging_grp.setContentsMargins(0, 0, 0, 0)
        self.logging_grp.add_widget(self.output_edit)
        self.logging_grp.add_layout(logging_button_layout)

        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(4)
        main_layout.addLayout(output_layout)
        main_layout.addWidget(self.name_gen_grp)  # Add name generator below output fields
        main_layout.addWidget(self.options_grp)
        main_layout.addWidget(self.logging_grp)

    def create_connections(self):
        self.output_dir_path_select_btn.clicked.connect(self.select_output_directory)
        self.output_dir_path_show_folder_btn.clicked.connect(self.open_output_directory)

        # Name Generator connections
        self.assignmentSpinBox.valueChanged.connect(self.update_filename_preview)
        self.lastnameLineEdit.textChanged.connect(self.update_filename_preview)
        self.firstnameLineEdit.textChanged.connect(self.update_filename_preview)
        self.versionTypeCombo.currentTextChanged.connect(self.update_filename_preview)
        self.versionNumberSpinBox.valueChanged.connect(self.update_filename_preview)
        self.generateFilenameButton.clicked.connect(self.generate_filename)
        
        # Artist name update from first/last name
        self.lastnameLineEdit.textChanged.connect(self.update_artist_name)
        self.firstnameLineEdit.textChanged.connect(self.update_artist_name)

        self.camera_select_cmb.currentTextChanged.connect(self.on_camera_changed)
        self.camera_select_hide_defaults_cb.toggled.connect(self.refresh_cameras)

        self.frame_range_cmb.currentTextChanged.connect(self.refresh_frame_range)
        self.frame_range_start_sb.editingFinished.connect(self.on_frame_range_changed)
        self.frame_range_end_sb.editingFinished.connect(self.on_frame_range_changed)

        self.encoding_container_cmb.currentTextChanged.connect(self.refresh_video_encoders)
        self.encoding_video_codec_cmb.currentTextChanged.connect(self.on_video_encoder_changed)
        self.encoding_video_codec_settings_btn.clicked.connect(self.show_encoder_settings_dialog)

        self.resolution_select_cmb.currentTextChanged.connect(self.refresh_resolution)
        self.resolution_width_sb.editingFinished.connect(self.on_resolution_changed)
        self.resolution_height_sb.editingFinished.connect(self.on_resolution_changed)

        self.visibility_cmb.currentTextChanged.connect(self.on_visibility_preset_changed)
        self.visibility_customize_btn.clicked.connect(self.show_visibility_dialog)

        self._playblast.output_logged.connect(self.append_output)  # pylint: disable=E1101

        self.log_to_script_editor_cb.toggled.connect(self.on_log_to_script_editor_changed)
        self.clear_btn.clicked.connect(self.output_edit.clear)

        self.options_grp.collapsed_state_changed.connect(self.on_collapsed_state_changed)  # pylint: disable=E1101
        self.logging_grp.collapsed_state_changed.connect(self.on_collapsed_state_changed)  # pylint: disable=E1101
    
    # Name Generator Methods
    def update_filename_preview(self):
        """
        Update the filename preview label based on current inputs.
        """
        assignment = self.assignmentSpinBox.value()
        lastname = self.lastnameLineEdit.text() or "LastName" 
        firstname = self.firstnameLineEdit.text() or "FirstName"
        version_type = self.versionTypeCombo.currentText()
        version_number = str(self.versionNumberSpinBox.value()).zfill(2)
        
        # Use * for preview but _ for actual filename
        filename = f"A{assignment}*{lastname}*{firstname}*{version_type}*{version_number}.mov"
        self.filenamePreviewLabel.setText(filename)

    def generate_filename(self):
        """
        Generate a filename from the inputs and place it in the output field.
        """
        assignment = self.assignmentSpinBox.value()
        lastname = self.lastnameLineEdit.text()
        firstname = self.firstnameLineEdit.text()
        version_type = self.versionTypeCombo.currentText()
        version_number = str(self.versionNumberSpinBox.value()).zfill(2)
        
        if not lastname or not firstname:
            QtWidgets.QMessageBox.warning(self, "Missing Information", 
                                        "Please enter both last name and first name.")
            return
        
        # Use underscores for the actual file
        filename = f"A{assignment}_{lastname}_{firstname}_{version_type}_{version_number}.mov"
        self.output_filename_le.setText(filename)

    def update_artist_name(self):
        """
        This function would update an artist name field if available in the UI.
        For this integration, we'll check if there is a HUD checkbox or user name field.
        """
        # This function would be useful if the UI has a field for artist name display
        # Since the original Conestoga Playblast UI doesn't have this field,
        # this is a placeholder for possible future integration
        pass

    def do_playblast(self, batch_cameras=[]):
        output_dir_path = self.output_dir_path_le.text()
        if not output_dir_path:
            output_dir_path = self.output_dir_path_le.placeholderText()

        filename = self.output_filename_le.text()
        if not filename:
            filename = self.output_filename_le.placeholderText()

        padding = ConestogaPlayblast.DEFAULT_PADDING

        overscan = self.overscan_cb.isChecked()
        show_ornaments = self.ornaments_cb.isChecked()
        show_in_viewer = self.viewer_cb.isChecked()
        overwrite = self.force_overwrite_cb.isChecked()
        use_camera_frame_range = self.frame_range_cmb.currentText() == "Camera"
        offscreen = self.offscreen_cb.isChecked()

        display_shot_mask = self.shot_mask_cb.isChecked()
        shot_mask_visible = ConestogaShotMask.get_mask()
        fit_shot_mask = self.fit_shot_mask_cb.isChecked()

        orig_camera = ConestogaShotMask.get_camera_name()

        cmds.evalDeferred(partial(self.pre_playblast, display_shot_mask, shot_mask_visible, fit_shot_mask))

        if batch_cameras:
            for batch_camera in batch_cameras:
                batch_camera_filename = filename
                if "{camera}" not in batch_camera_filename:
                    batch_camera_filename = "{0}_{{camera}}".format(filename)

                cmds.evalDeferred(partial(self._playblast.execute, output_dir_path, batch_camera_filename, padding, overscan, show_ornaments, show_in_viewer, offscreen, overwrite, batch_camera, use_camera_frame_range))
        else:
            cmds.evalDeferred(partial(self._playblast.execute, output_dir_path, filename, padding, overscan, show_ornaments, show_in_viewer, offscreen, overwrite, "", use_camera_frame_range))

        cmds.evalDeferred(partial(self.post_playblast, display_shot_mask, shot_mask_visible, fit_shot_mask, orig_camera))

    def pre_playblast(self, display_shot_mask, shot_mask_visible, fit_shot_mask):
        if display_shot_mask:
            if fit_shot_mask:
                # Fit shot mask to playbast width/height
                self.orig_render_width = cmds.getAttr("defaultResolution.width")
                self.orig_render_device_aspect_ratio = cmds.getAttr("defaultResolution.deviceAspectRatio")

                playblast_width, playblast_height = self._playblast.get_resolution_width_height()
                cmds.setAttr("defaultResolution.width", playblast_width)
                cmds.setAttr("defaultResolution.deviceAspectRatio", playblast_width / float(playblast_height))

            ConestogaShotMask.set_camera_name("")
            if shot_mask_visible:
                ConestogaShotMask.refresh_mask()
            else:
                ConestogaShotMask.create_mask()
        else:
            ConestogaShotMask.delete_mask()

    def post_playblast(self, display_shot_mask, shot_mask_visible, fit_shot_mask, orig_camera):
        if display_shot_mask:
            if fit_shot_mask:
                cmds.setAttr("defaultResolution.width", self.orig_render_width)
                cmds.setAttr("defaultResolution.deviceAspectRatio", self.orig_render_device_aspect_ratio)

            ConestogaShotMask.set_camera_name(orig_camera)
            if shot_mask_visible:
                ConestogaShotMask.refresh_mask()
            else:
                ConestogaShotMask.delete_mask()
        elif shot_mask_visible:
            ConestogaShotMask.create_mask()

    def select_output_directory(self):
        current_dir_path = self.output_dir_path_le.text()
        if not current_dir_path:
            current_dir_path = self.output_dir_path_le.placeholderText()

        current_dir_path = self._playblast.resolve_output_directory_path(current_dir_path)

        file_info = QtCore.QFileInfo(current_dir_path)
        if not file_info.exists():
            current_dir_path = self._playblast.get_project_dir_path()

        new_dir_path = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Directory", current_dir_path)
        if new_dir_path:
            self.output_dir_path_le.setText(new_dir_path)

    def open_output_directory(self):
        output_dir_path = self.output_dir_path_le.text()
        if not output_dir_path:
            output_dir_path = self.output_dir_path_le.placeholderText()

        output_dir_path = self._playblast.resolve_output_directory_path(output_dir_path)

        file_info = QtCore.QFileInfo(output_dir_path)
        if file_info.isDir():
            if cmds.about(win=True):
                file_prefix = "file:///"
            else:
                file_prefix = "file://"

            QtGui.QDesktopServices.openUrl(QtCore.QUrl("{0}{1}".format(file_prefix, file_info.absoluteFilePath()), QtCore.QUrl.TolerantMode))
        else:
            self.append_output("[ERROR] Invalid directory path: {0}".format(output_dir_path))

    def refresh_all(self):
        self.refresh_cameras()
        self.refresh_resolution()
        self.refresh_frame_range()
        self.refresh_video_encoders()

    def refresh_cameras(self):
        current_camera = self.camera_select_cmb.currentText()
        self.camera_select_cmb.clear()

        self.camera_select_cmb.addItem("<Active>")
        self.camera_select_cmb.addItems(ConestogaPlayblastUtils.cameras_in_scene(not self.camera_select_hide_defaults_cb.isChecked(), True))

        self.camera_select_cmb.setCurrentText(current_camera)

    def on_camera_changed(self):
        camera = self.camera_select_cmb.currentText()

        if camera == "<Active>":
            camera = None

        self._playblast.set_camera(camera)

    def refresh_resolution(self):
        resolution_preset = self.resolution_select_cmb.currentText()
        if resolution_preset != "Custom":
            self._playblast.set_resolution(resolution_preset)

            resolution = self._playblast.get_resolution_width_height()
            self.resolution_width_sb.setValue(resolution[0])
            self.resolution_height_sb.setValue(resolution[1])

    def on_resolution_changed(self):
        resolution = (self.resolution_width_sb.value(), self.resolution_height_sb.value())

        for key in self._playblast.resolution_presets.keys():
            if self._playblast.resolution_presets[key] == resolution:
                self.resolution_select_cmb.setCurrentText(key)
                return

        self.resolution_select_cmb.setCurrentText("Custom")

        self._playblast.set_resolution(resolution)

    def refresh_frame_range(self):
        frame_range_preset = self.frame_range_cmb.currentText()
        if frame_range_preset != "Custom":
            frame_range = self._playblast.preset_to_frame_range(frame_range_preset)

            self.frame_range_start_sb.setValue(frame_range[0])
            self.frame_range_end_sb.setValue(frame_range[1])

            self._playblast.set_frame_range(frame_range_preset)

        enable_frame_range_spinboxes = frame_range_preset != "Camera"
        self.frame_range_start_sb.setEnabled(enable_frame_range_spinboxes)
        self.frame_range_end_sb.setEnabled(enable_frame_range_spinboxes)


    def on_frame_range_changed(self):
        self.frame_range_cmb.setCurrentText("Custom")

        frame_range = (self.frame_range_start_sb.value(), self.frame_range_end_sb.value())
        self._playblast.set_frame_range(frame_range)

    def refresh_video_encoders(self):
        encoder = self.encoding_video_codec_cmb.currentText()
        self.encoding_video_codec_cmb.clear()

        container = self.encoding_container_cmb.currentText()
        self.encoding_video_codec_cmb.addItems(ConestogaPlayblast.VIDEO_ENCODER_LOOKUP[container])
        self.encoding_video_codec_cmb.setCurrentText(encoder)

    def on_video_encoder_changed(self):
        container = self.encoding_container_cmb.currentText()
        encoder = self.encoding_video_codec_cmb.currentText()

        if container and encoder:
            self._playblast.set_encoding(container, encoder)

    def show_encoder_settings_dialog(self):
        if not self._encoder_settings_dialog:
            self._encoder_settings_dialog = ConestogaPlayblastEncoderSettingsDialog(self)
            self._encoder_settings_dialog.accepted.connect(self.on_encoder_settings_dialog_modified)

        if self.encoding_container_cmb.currentText() == "Image":
            self._encoder_settings_dialog.set_page("Image")

            image_settings = self._playblast.get_image_settings()
            self._encoder_settings_dialog.set_image_settings(image_settings["quality"])

        else:
            encoder = self.encoding_video_codec_cmb.currentText()
            if encoder == "h264":
                self._encoder_settings_dialog.set_page("h264")

                h264_settings = self._playblast.get_h264_settings()
                self._encoder_settings_dialog.set_h264_settings(h264_settings["quality"], h264_settings["preset"])
            else:
                self.append_output("[ERROR] Settings page not found for encoder: {0}".format(encoder))

        self._encoder_settings_dialog.show()

    def on_encoder_settings_dialog_modified(self):
        if self.encoding_container_cmb.currentText() == "Image":
            image_settings = self._encoder_settings_dialog.get_image_settings()
            self._playblast.set_image_settings(image_settings["quality"])
        else:
            encoder = self.encoding_video_codec_cmb.currentText()
            if encoder == "h264":
                h264_settings = self._encoder_settings_dialog.get_h264_settings()
                self._playblast.set_h264_settings(h264_settings["quality"], h264_settings["preset"])
            else:
                self.append_output("[ERROR] Failed to set encoder settings. Unknown encoder: {0}".format(encoder))

    def on_visibility_preset_changed(self):
        visibility_preset = self.visibility_cmb.currentText()
        if visibility_preset != "Custom":
            self._playblast.set_visibility(visibility_preset)

    def show_visibility_dialog(self):
        if not self._visibility_dialog:
            self._visibility_dialog = ConestogaPlayblastVisibilityDialog(self)
            self._visibility_dialog.accepted.connect(self.on_visibility_dialog_modified)

        self._visibility_dialog.set_visibility_data(self._playblast.get_visibility())

        self._visibility_dialog.show()

    def on_visibility_dialog_modified(self):
        self.visibility_cmb.setCurrentText("Custom")
        self._playblast.set_visibility(self._visibility_dialog.get_visibility_data())

    def on_log_to_script_editor_changed(self):
        self._playblast.set_maya_logging_enabled(self.log_to_script_editor_cb.isChecked())

    def on_collapsed_state_changed(self):
        self.collapsed_state_changed.emit()  # pylint: disable=E1101

    def get_collapsed_states(self):
        collapsed = 0
        collapsed += int(self.name_gen_grp.is_collapsed())
        collapsed += int(self.options_grp.is_collapsed()) << 1
        collapsed += int(self.logging_grp.is_collapsed()) << 2

        return collapsed

    def set_collapsed_states(self, collapsed):
        self.name_gen_grp.set_collapsed(collapsed & 1)
        self.options_grp.set_collapsed(collapsed & 2)
        self.logging_grp.set_collapsed(collapsed & 4)

    def save_settings(self):
        cmds.optionVar(sv=(ConestogaPlayblastWidget.OPT_VAR_OUTPUT_DIR, self.output_dir_path_le.text()))
        cmds.optionVar(sv=(ConestogaPlayblastWidget.OPT_VAR_OUTPUT_FILENAME, self.output_filename_le.text()))
        cmds.optionVar(iv=(ConestogaPlayblastWidget.OPT_VAR_FORCE_OVERWRITE, self.force_overwrite_cb.isChecked()))

        # Save name generator settings
        cmds.optionVar(iv=(ConestogaPlayblastWidget.OPT_VAR_ASSIGNMENT_NUMBER, self.assignmentSpinBox.value()))
        cmds.optionVar(sv=(ConestogaPlayblastWidget.OPT_VAR_LAST_NAME, self.lastnameLineEdit.text()))
        cmds.optionVar(sv=(ConestogaPlayblastWidget.OPT_VAR_FIRST_NAME, self.firstnameLineEdit.text()))
        cmds.optionVar(sv=(ConestogaPlayblastWidget.OPT_VAR_VERSION_TYPE, self.versionTypeCombo.currentText()))
        cmds.optionVar(iv=(ConestogaPlayblastWidget.OPT_VAR_VERSION_NUMBER, self.versionNumberSpinBox.value()))

        cmds.optionVar(sv=(ConestogaPlayblastWidget.OPT_VAR_CAMERA, self.camera_select_cmb.currentText()))
        cmds.optionVar(iv=(ConestogaPlayblastWidget.OPT_VAR_HIDE_DEFAULT_CAMERAS, self.camera_select_hide_defaults_cb.isChecked()))

        cmds.optionVar(sv=(ConestogaPlayblastWidget.OPT_VAR_RESOLUTION_PRESET, self.resolution_select_cmb.currentText()))
        cmds.optionVar(iv=(ConestogaPlayblastWidget.OPT_VAR_RESOLUTION_WIDTH, self.resolution_width_sb.value()))
        cmds.optionVar(iv=(ConestogaPlayblastWidget.OPT_VAR_RESOLUTION_HEIGHT, self.resolution_height_sb.value()))

        cmds.optionVar(sv=(ConestogaPlayblastWidget.OPT_VAR_FRAME_RANGE_PRESET, self.frame_range_cmb.currentText()))
        cmds.optionVar(iv=(ConestogaPlayblastWidget.OPT_VAR_FRAME_RANGE_START, self.frame_range_start_sb.value()))
        cmds.optionVar(iv=(ConestogaPlayblastWidget.OPT_VAR_FRAME_RANGE_END, self.frame_range_end_sb.value()))

        cmds.optionVar(sv=(ConestogaPlayblastWidget.OPT_VAR_ENCODING_CONTAINER, self.encoding_container_cmb.currentText()))
        cmds.optionVar(sv=(ConestogaPlayblastWidget.OPT_VAR_ENCODING_VIDEO_CODEC, self.encoding_video_codec_cmb.currentText()))

        h264_settings = self._playblast.get_h264_settings()
        cmds.optionVar(sv=(ConestogaPlayblastWidget.OPT_VAR_H264_QUALITY, h264_settings["quality"]))
        cmds.optionVar(sv=(ConestogaPlayblastWidget.OPT_VAR_H264_PRESET, h264_settings["preset"]))

        image_settings = self._playblast.get_image_settings()
        cmds.optionVar(iv=(ConestogaPlayblastWidget.OPT_VAR_IMAGE_QUALITY, image_settings["quality"]))

        cmds.optionVar(sv=(ConestogaPlayblastWidget.OPT_VAR_VISIBILITY_PRESET, self.visibility_cmb.currentText()))

        visibility_data = self._playblast.get_visibility()
        if visibility_data:
            visibility_str = ""
            for item in visibility_data:
                visibility_str = "{0} {1}".format(visibility_str, int(item))
            cmds.optionVar(sv=(ConestogaPlayblastWidget.OPT_VAR_VISIBILITY_DATA, visibility_str))

        cmds.optionVar(iv=(ConestogaPlayblastWidget.OPT_VAR_OVERSCAN, self.overscan_cb.isChecked()))
        cmds.optionVar(iv=(ConestogaPlayblastWidget.OPT_VAR_ORNAMENTS, self.ornaments_cb.isChecked()))
        cmds.optionVar(iv=(ConestogaPlayblastWidget.OPT_VAR_OFFSCREEN, self.offscreen_cb.isChecked()))
        cmds.optionVar(iv=(ConestogaPlayblastWidget.OPT_VAR_SHOT_MASK, self.shot_mask_cb.isChecked()))
        cmds.optionVar(iv=(ConestogaPlayblastWidget.OPT_VAR_FIT_SHOT_MASK, self.fit_shot_mask_cb.isChecked()))
        cmds.optionVar(iv=(ConestogaPlayblastWidget.OPT_VAR_VIEWER, self.viewer_cb.isChecked()))

        cmds.optionVar(iv=(ConestogaPlayblastWidget.OPT_VAR_LOG_TO_SCRIPT_EDITOR, self.log_to_script_editor_cb.isChecked()))

    def load_settings(self):
        if cmds.optionVar(exists=ConestogaPlayblastWidget.OPT_VAR_OUTPUT_DIR):
            self.output_dir_path_le.setText(cmds.optionVar(q=ConestogaPlayblastWidget.OPT_VAR_OUTPUT_DIR))
        if cmds.optionVar(exists=ConestogaPlayblastWidget.OPT_VAR_OUTPUT_FILENAME):
            self.output_filename_le.setText(cmds.optionVar(q=ConestogaPlayblastWidget.OPT_VAR_OUTPUT_FILENAME))
        if cmds.optionVar(exists=ConestogaPlayblastWidget.OPT_VAR_FORCE_OVERWRITE):
            self.force_overwrite_cb.setChecked(cmds.optionVar(q=ConestogaPlayblastWidget.OPT_VAR_FORCE_OVERWRITE))

        # Load name generator settings
        if cmds.optionVar(exists=ConestogaPlayblastWidget.OPT_VAR_ASSIGNMENT_NUMBER):
            self.assignmentSpinBox.setValue(cmds.optionVar(q=ConestogaPlayblastWidget.OPT_VAR_ASSIGNMENT_NUMBER))
        if cmds.optionVar(exists=ConestogaPlayblastWidget.OPT_VAR_LAST_NAME):
            self.lastnameLineEdit.setText(cmds.optionVar(q=ConestogaPlayblastWidget.OPT_VAR_LAST_NAME))
        if cmds.optionVar(exists=ConestogaPlayblastWidget.OPT_VAR_FIRST_NAME):
            self.firstnameLineEdit.setText(cmds.optionVar(q=ConestogaPlayblastWidget.OPT_VAR_FIRST_NAME))
        if cmds.optionVar(exists=ConestogaPlayblastWidget.OPT_VAR_VERSION_TYPE):
            self.versionTypeCombo.setCurrentText(cmds.optionVar(q=ConestogaPlayblastWidget.OPT_VAR_VERSION_TYPE))
        if cmds.optionVar(exists=ConestogaPlayblastWidget.OPT_VAR_VERSION_NUMBER):
            self.versionNumberSpinBox.setValue(cmds.optionVar(q=ConestogaPlayblastWidget.OPT_VAR_VERSION_NUMBER))

        if cmds.optionVar(exists=ConestogaPlayblastWidget.OPT_VAR_CAMERA):
            self.camera_select_cmb.setCurrentText(cmds.optionVar(q=ConestogaPlayblastWidget.OPT_VAR_CAMERA))
        if cmds.optionVar(exists=ConestogaPlayblastWidget.OPT_VAR_HIDE_DEFAULT_CAMERAS):
            self.camera_select_hide_defaults_cb.setChecked(cmds.optionVar(q=ConestogaPlayblastWidget.OPT_VAR_HIDE_DEFAULT_CAMERAS))

        if cmds.optionVar(exists=ConestogaPlayblastWidget.OPT_VAR_RESOLUTION_PRESET):
            self.resolution_select_cmb.setCurrentText(cmds.optionVar(q=ConestogaPlayblastWidget.OPT_VAR_RESOLUTION_PRESET))
        if self.resolution_select_cmb.currentText() == "Custom":
            if cmds.optionVar(exists=ConestogaPlayblastWidget.OPT_VAR_RESOLUTION_WIDTH):
                self.resolution_width_sb.setValue(cmds.optionVar(q=ConestogaPlayblastWidget.OPT_VAR_RESOLUTION_WIDTH))
            if cmds.optionVar(exists=ConestogaPlayblastWidget.OPT_VAR_RESOLUTION_HEIGHT):
                self.resolution_height_sb.setValue(cmds.optionVar(q=ConestogaPlayblastWidget.OPT_VAR_RESOLUTION_HEIGHT))
            self.on_resolution_changed()

        if cmds.optionVar(exists=ConestogaPlayblastWidget.OPT_VAR_FRAME_RANGE_PRESET):
            self.frame_range_cmb.setCurrentText(cmds.optionVar(q=ConestogaPlayblastWidget.OPT_VAR_FRAME_RANGE_PRESET))
        if self.frame_range_cmb.currentText() == "Custom":
            if cmds.optionVar(exists=ConestogaPlayblastWidget.OPT_VAR_FRAME_RANGE_START):
                self.frame_range_start_sb.setValue(cmds.optionVar(q=ConestogaPlayblastWidget.OPT_VAR_FRAME_RANGE_START))
            if cmds.optionVar(exists=ConestogaPlayblastWidget.OPT_VAR_FRAME_RANGE_END):
                self.frame_range_end_sb.setValue(cmds.optionVar(q=ConestogaPlayblastWidget.OPT_VAR_FRAME_RANGE_END))
            self.on_frame_range_changed()

        if cmds.optionVar(exists=ConestogaPlayblastWidget.OPT_VAR_ENCODING_CONTAINER):
            self.encoding_container_cmb.setCurrentText(cmds.optionVar(q=ConestogaPlayblastWidget.OPT_VAR_ENCODING_CONTAINER))
        if cmds.optionVar(exists=ConestogaPlayblastWidget.OPT_VAR_ENCODING_VIDEO_CODEC):
            self.encoding_video_codec_cmb.setCurrentText(cmds.optionVar(q=ConestogaPlayblastWidget.OPT_VAR_ENCODING_VIDEO_CODEC))

        if cmds.optionVar(exists=ConestogaPlayblastWidget.OPT_VAR_H264_QUALITY) and cmds.optionVar(exists=ConestogaPlayblastWidget.OPT_VAR_H264_PRESET):
            self._playblast.set_h264_settings(cmds.optionVar(q=ConestogaPlayblastWidget.OPT_VAR_H264_QUALITY), cmds.optionVar(q=ConestogaPlayblastWidget.OPT_VAR_H264_PRESET))

        if cmds.optionVar(exists=ConestogaPlayblastWidget.OPT_VAR_IMAGE_QUALITY):
            self._playblast.set_image_settings(cmds.optionVar(q=ConestogaPlayblastWidget.OPT_VAR_IMAGE_QUALITY))

        if cmds.optionVar(exists=ConestogaPlayblastWidget.OPT_VAR_VISIBILITY_PRESET):
            self.visibility_cmb.setCurrentText(cmds.optionVar(q=ConestogaPlayblastWidget.OPT_VAR_VISIBILITY_PRESET))
        if self.visibility_cmb.currentText() == "Custom":
            if cmds.optionVar(exists=ConestogaPlayblastWidget.OPT_VAR_VISIBILITY_DATA):
                visibility_str_list = cmds.optionVar(q=ConestogaPlayblastWidget.OPT_VAR_VISIBILITY_DATA).split()
                visibility_data = []
                for item in visibility_str_list:
                    if item:
                        visibility_data.append(bool(int(item)))

                self._playblast.set_visibility(visibility_data)

        if cmds.optionVar(exists=ConestogaPlayblastWidget.OPT_VAR_OVERSCAN):
            self.overscan_cb.setChecked(cmds.optionVar(q=ConestogaPlayblastWidget.OPT_VAR_OVERSCAN))
        if cmds.optionVar(exists=ConestogaPlayblastWidget.OPT_VAR_ORNAMENTS):
            self.ornaments_cb.setChecked(cmds.optionVar(q=ConestogaPlayblastWidget.OPT_VAR_ORNAMENTS))
        if cmds.optionVar(exists=ConestogaPlayblastWidget.OPT_VAR_OFFSCREEN):
            self.offscreen_cb.setChecked(cmds.optionVar(q=ConestogaPlayblastWidget.OPT_VAR_OFFSCREEN))
        if cmds.optionVar(exists=ConestogaPlayblastWidget.OPT_VAR_SHOT_MASK):
            self.shot_mask_cb.setChecked(cmds.optionVar(q=ConestogaPlayblastWidget.OPT_VAR_SHOT_MASK))
        if cmds.optionVar(exists=ConestogaPlayblastWidget.OPT_VAR_FIT_SHOT_MASK):
            self.fit_shot_mask_cb.setChecked(cmds.optionVar(q=ConestogaPlayblastWidget.OPT_VAR_FIT_SHOT_MASK))
        if cmds.optionVar(exists=ConestogaPlayblastWidget.OPT_VAR_VIEWER):
            self.viewer_cb.setChecked(cmds.optionVar(q=ConestogaPlayblastWidget.OPT_VAR_VIEWER))

        if cmds.optionVar(exists=ConestogaPlayblastWidget.OPT_VAR_LOG_TO_SCRIPT_EDITOR):
            self.log_to_script_editor_cb.setChecked(cmds.optionVar(q=ConestogaPlayblastWidget.OPT_VAR_LOG_TO_SCRIPT_EDITOR))

        # Update filename preview after loading
        self.update_filename_preview()

    def append_output(self, text):
        self.output_edit.appendPlainText(text)

        cursor = self.output_edit.textCursor()
        cursor.movePosition(QtGui.QTextCursor.End)
        self.output_edit.setTextCursor(cursor)

    def reset_settings(self):
        self.output_dir_path_le.setText("")
        self.output_filename_le.setText("")
        self.force_overwrite_cb.setChecked(False)

        # Reset name generator settings
        self.assignmentSpinBox.setValue(1)
        self.lastnameLineEdit.setText("")
        self.firstnameLineEdit.setText("")
        self.versionTypeCombo.setCurrentText("wip")
        self.versionNumberSpinBox.setValue(1)

        self.camera_select_cmb.setCurrentIndex(0)
        self.camera_select_hide_defaults_cb.setChecked(False)

        self.resolution_select_cmb.setCurrentText(ConestogaPlayblast.DEFAULT_RESOLUTION)

        self.frame_range_cmb.setCurrentText(ConestogaPlayblast.DEFAULT_FRAME_RANGE)

        self.encoding_container_cmb.setCurrentText(ConestogaPlayblast.DEFAULT_CONTAINER)
        self.encoding_video_codec_cmb.setCurrentText(ConestogaPlayblast.DEFAULT_ENCODER)

        self._playblast.set_h264_settings(ConestogaPlayblast.DEFAULT_H264_QUALITY, ConestogaPlayblast.DEFAULT_H264_PRESET)
        self._playblast.set_image_settings(ConestogaPlayblast.DEFAULT_IMAGE_QUALITY)

        self.visibility_cmb.setCurrentText(ConestogaPlayblast.DEFAULT_VISIBILITY)
        self._playblast.set_viewport_visibility

        self.ornaments_cb.setChecked(False)
        self.overscan_cb.setChecked(False)
        self.shot_mask_cb.setChecked(True)
        self.fit_shot_mask_cb.setChecked(False)
        self.viewer_cb.setChecked(True)

        self.log_to_script_editor_cb.setChecked(ConestogaPlayblast.DEFAULT_MAYA_LOGGING_ENABLED)

        self.save_settings()

    def log_warning(self, msg):
        self._playblast.log_warning(msg)

    def showEvent(self, e):
        self.refresh_all()

    def hideEvent(self, e):
        self.save_settings()


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


class ConestogaShotMaskWidget(QtWidgets.QWidget):

    LABELS = ["Top-Left", "Top-Center", "Top-Right", "Bottom-Left", "Bottom-Center", "Bottom-Right"]

    ALL_CAMERAS = "<All Cameras>"

    collapsed_state_changed = QtCore.Signal()


    def __init__(self, parent=None):
        super(ConestogaShotMaskWidget, self).__init__(parent)

        self._camera_select_dialog = None
        self._update_mask_enabled = True

        self.create_widgets()
        self.create_layouts()
        self.create_connections()

    def create_widgets(self):
        scale_value = ConestogaPlayblastUtils.dpi_real_scale_value()

        button_width = int(60 * scale_value)
        button_height = int(18 * scale_value)
        spin_box_width = int(50 * scale_value)

        self.camera_le = QtWidgets.QLineEdit()
        self.camera_select_btn = QtWidgets.QPushButton("Select...")
        self.camera_select_btn.setFixedSize(button_width, button_height)

        self.label_line_edits = []
        for i in range(len(ConestogaShotMaskWidget.LABELS)):  # pylint: disable=W0612
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

        self.update_ui_elements()

    def create_layouts(self):
        camera_layout = QtWidgets.QHBoxLayout()
        camera_layout.setContentsMargins(4, 14, 4, 14)
        camera_layout.setSpacing(2)
        camera_layout.addWidget(self.camera_le)
        camera_layout.addWidget(self.camera_select_btn)

        camera_grp_layout = ConestogaFormLayout()
        camera_grp_layout.addLayoutRow(0, "Camera", camera_layout)

        labels_layout = ConestogaFormLayout()
        for i in range(len(ConestogaShotMaskWidget.LABELS)):
            labels_layout.addWidgetRow(i,ConestogaShotMaskWidget.LABELS[i], self.label_line_edits[i])

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
        # borders_layout.setSpacing(4)
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
        cameras.insert(0, ConestogaShotMaskWidget.ALL_CAMERAS)

    def on_border_aspect_ratio_enabled_changed(self):
        enabled = self.frame_border_to_aspect_ratio_cb.isChecked()
        if enabled:
            self.border_size_type_text.setText("Aspect Ratio")
        else:
            self.border_size_type_text.setText("Scale")

        self.border_aspect_ratio_dsb.setVisible(enabled)
        self.border_scale_dsb.setHidden(enabled)

        self.update_mask()

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
            camera_name = ConestogaShotMaskWidget.ALL_CAMERAS
        self.camera_le.setText(camera_name)

        label_text = ConestogaShotMask.get_label_text()
        for i in range(len(label_text)):
            self.label_line_edits[i].setText(label_text[i])

        self.font_le.setText(ConestogaShotMask.get_label_font())
        self.label_scale_dsb.setValue(ConestogaShotMask.get_label_scale())

        label_color = ConestogaShotMask.get_label_color()
        self.label_color_btn.set_color(label_color)
        self.label_transparency_dsb.setValue(label_color[3])

        border_visible = ConestogaShotMask.get_border_visible()
        self.top_border_cb.setChecked(border_visible[0])
        self.bottom_border_cb.setChecked(border_visible[1])
        self.border_scale_dsb.setValue(ConestogaShotMask.get_border_scale())

        border_color = ConestogaShotMask.get_border_color()
        self.border_color_btn.set_color(border_color)
        self.border_transparency_dsb.setValue(border_color[3])

        self.frame_border_to_aspect_ratio_cb.setChecked(ConestogaShotMask.is_border_aspect_ratio_enabled())
        self.border_aspect_ratio_dsb.setValue(ConestogaShotMask.get_border_aspect_ratio())
        self.on_border_aspect_ratio_enabled_changed()

        self.counter_padding_sb.setValue(ConestogaShotMask.get_counter_padding())

        self._update_mask_enabled = True

    def reset_settings(self):
        ConestogaShotMask.reset_settings()

        self.update_ui_elements()
        self.update_mask()

    def show_camera_select_dialog(self):
        if not self._camera_select_dialog:
            self._camera_select_dialog = ConestogaCameraSelectDialog(self)
            self._camera_select_dialog.setWindowTitle("Shot Mask Camera")
            self._camera_select_dialog.set_camera_list_text("Select shot mask camera:")
            self._camera_select_dialog.accepted.connect(self.on_camera_select_accepted)

        self._camera_select_dialog.refresh_list(selected=[self.camera_le.text()], prepend=[ConestogaShotMaskWidget.ALL_CAMERAS])

        self._camera_select_dialog.show()

    def on_camera_select_accepted(self):
        selected = self._camera_select_dialog.get_selected()
        if selected:
            self.camera_le.setText(selected[0])
            self.update_mask()

    def on_collapsed_state_changed(self):
        self.collapsed_state_changed.emit()

    def get_collapsed_states(self):
        collapsed = 0
        collapsed += int(self.labels_grp.is_collapsed())
        collapsed += int(self.text_grp.is_collapsed()) << 1
        collapsed += int(self.borders_grp.is_collapsed()) << 2
        collapsed += int(self.counter_grp.is_collapsed()) << 3

        return collapsed

    def set_collapsed_states(self, collapsed):
        self.labels_grp.set_collapsed(collapsed & 1)
        self.text_grp.set_collapsed(collapsed & 2)
        self.borders_grp.set_collapsed(collapsed & 4)
        self.counter_grp.set_collapsed(collapsed & 8)

    def show_font_select_dialog(self):
        current_font = QtGui.QFont(self.font_le.text())

        font = QtWidgets.QFontDialog.getFont(current_font, self)

        # Order of the tuple returned by getFont changed in newer versions of Qt
        if type(font[0]) == bool:
            ok = font[0]
            family = font[1].family()
        else:
            family = font[0].family()
            ok = font[1]

        if(ok):
            self.font_le.setText(family)
            self.update_mask()

class ConestogaPlayblastSettingsWidget(QtWidgets.QWidget):

    TEMP_FILE_FORMATS = [
        "movie",
        "png",
        "tga",
        "tif"
    ]

    shot_mask_reset = QtCore.Signal()
    playblast_reset = QtCore.Signal()

    logo_path_updated = QtCore.Signal()

    collapsed_state_changed = QtCore.Signal()


    def __init__(self, parent=None):
        super(ConestogaPlayblastSettingsWidget, self).__init__(parent)

        self.create_widgets()
        self.create_layouts()
        self.create_connections()

    def create_widgets(self):
        scale_value = ConestogaPlayblastUtils.dpi_real_scale_value()
        button_width = int(24 * scale_value)
        button_height = int(19 * scale_value)
        reset_button_min_width = int(200 * scale_value)

        text = '<h3>{0}</h3>'.format(ConestogaPlayblastUi.WINDOW_TITLE)
        text += '<h3>v{0}</h3>'.format(ConestogaPlayblastUtils.get_version())
        text += '<p>Conestoga College<br><a style="color:white;text-decoration:none;" href="http://conestogac.on.ca">conestogac.on.ca</a></p>'

        self.about_label = QtWidgets.QLabel(text)
        self.about_label.setOpenExternalLinks(True)
        self.about_label.setAlignment(QtCore.Qt.AlignCenter)

        self.ffmpeg_path_le = QtWidgets.QLineEdit()
        self.ffmpeg_path_le.setPlaceholderText("<path to {0}>".format(self.get_ffmpeg_executable_text()))
        self.ffmpeg_path_select_btn = QtWidgets.QPushButton("...")
        self.ffmpeg_path_select_btn.setFixedSize(button_width, button_height)

        self.temp_dir_le = QtWidgets.QLineEdit()
        self.temp_dir_le.setPlaceholderText("<path to {temp} output directory>")
        self.temp_dir_select_btn = QtWidgets.QPushButton("...")
        self.temp_dir_select_btn.setFixedSize(button_width, button_height)

        self.temp_file_format_cmb = QtWidgets.QComboBox()
        self.temp_file_format_cmb.addItems(self.TEMP_FILE_FORMATS)

        self.playblast_reset_btn = QtWidgets.QPushButton("Reset Playblast")
        self.playblast_reset_btn.setMinimumWidth(reset_button_min_width)

        self.logo_path_le = QtWidgets.QLineEdit()
        self.logo_path_le.setPlaceholderText("<path to {logo} image>")
        self.logo_path_select_btn = QtWidgets.QPushButton("...")
        self.logo_path_select_btn.setFixedSize(button_width, button_height)

        self.shot_mask_reset_btn = QtWidgets.QPushButton("Reset Shot Mask")
        self.shot_mask_reset_btn.setMinimumWidth(reset_button_min_width)

    def create_layouts(self):
        about_layout = QtWidgets.QVBoxLayout()
        about_layout.setContentsMargins(0, 14, 0, 14)
        about_layout.addWidget(self.about_label)

        ffmpeg_path_layout = QtWidgets.QHBoxLayout()
        ffmpeg_path_layout.setSpacing(2)
        ffmpeg_path_layout.addWidget(self.ffmpeg_path_le)
        ffmpeg_path_layout.addWidget(self.ffmpeg_path_select_btn)

        temp_dir_layout = QtWidgets.QHBoxLayout()
        temp_dir_layout.setSpacing(2)
        temp_dir_layout.addWidget(self.temp_dir_le)
        temp_dir_layout.addWidget(self.temp_dir_select_btn)

        temp_format_layout =  QtWidgets.QHBoxLayout()
        temp_format_layout.addWidget(self.temp_file_format_cmb)
        temp_format_layout.addStretch()

        playblast_layout = ConestogaFormLayout()
        playblast_layout.addLayoutRow(0, "ffmpeg Path", ffmpeg_path_layout)
        playblast_layout.addLayoutRow(1, "Temp Dir", temp_dir_layout)
        playblast_layout.addLayoutRow(2, "Temp Format", temp_format_layout)

        playblast_reset_layout = QtWidgets.QHBoxLayout()
        playblast_reset_layout.setContentsMargins(0, 0, 0, 10)
        playblast_reset_layout.addStretch()
        playblast_reset_layout.addWidget(self.playblast_reset_btn)
        playblast_reset_layout.addStretch()

        self.playblast_grp = ConestogaCollapsibleGrpWidget("Playblast")
        self.playblast_grp.add_layout(playblast_layout)
        self.playblast_grp.add_layout(playblast_reset_layout)

        logo_path_layout = QtWidgets.QHBoxLayout()
        logo_path_layout.setSpacing(2)
        logo_path_layout.addWidget(self.logo_path_le)
        logo_path_layout.addWidget(self.logo_path_select_btn)

        shot_mask_tags_layout = ConestogaFormLayout()
        shot_mask_tags_layout.addLayoutRow(0, "Logo Path", logo_path_layout)

        shot_mask_reset_layout = QtWidgets.QHBoxLayout()
        shot_mask_reset_layout.setContentsMargins(0, 0, 0, 10)
        shot_mask_reset_layout.addStretch()
        shot_mask_reset_layout.addWidget(self.shot_mask_reset_btn)
        shot_mask_reset_layout.addStretch()

        self.shot_mask_grp = ConestogaCollapsibleGrpWidget("Shot Mask")
        self.shot_mask_grp.add_layout(shot_mask_tags_layout)
        self.shot_mask_grp.add_layout(shot_mask_reset_layout)

        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addLayout(about_layout)
        main_layout.addWidget(self.playblast_grp)
        main_layout.addWidget(self.shot_mask_grp)
        main_layout.addStretch()

    def create_connections(self):
        self.ffmpeg_path_le.editingFinished.connect(self.update_ffmpeg_path)
        self.ffmpeg_path_select_btn.clicked.connect(self.open_ffmpeg_select_dialog)

        self.temp_dir_le.editingFinished.connect(self.update_temp_dir_path)
        self.temp_dir_select_btn.clicked.connect(self.open_temp_dir_select_dialog)

        self.temp_file_format_cmb.currentTextChanged.connect(self.update_temp_file_format)

        self.playblast_reset_btn.clicked.connect(self.on_reset_playblast)

        self.logo_path_le.editingFinished.connect(self.update_logo_path)
        self.logo_path_select_btn.clicked.connect(self.open_logo_select_dialog)

        self.shot_mask_reset_btn.clicked.connect(self.on_reset_shot_mask)

        self.playblast_grp.collapsed_state_changed.connect(self.on_collapsed_state_changed)  # pylint: disable=E1101
        self.shot_mask_grp.collapsed_state_changed.connect(self.on_collapsed_state_changed)  # pylint: disable=E1101

    def get_ffmpeg_executable_text(self):
        if cmds.about(win=True):
            return "ffmpeg.exe"

        return "ffmpeg executable"

    def open_ffmpeg_select_dialog(self):

        if ConestogaPlayblastUtils.is_ffmpeg_env_var_set():
            QtWidgets.QMessageBox.information(self, "Select ffmpeg Executable", "The ffmpeg path is currently set using the CONESTOGA_PLAYBLAST_FFMPEG environment variable.")
            return

        current_path = self.ffmpeg_path_le.text()

        new_path = QtWidgets.QFileDialog.getOpenFileName(self, "Select ffmpeg Executable", current_path)[0]
        if new_path and new_path != self.ffmpeg_path_le.text():
            self.ffmpeg_path_le.setText(new_path)
            self.update_ffmpeg_path()

    def update_ffmpeg_path(self):
        ConestogaPlayblastUtils.set_ffmpeg_path(self.ffmpeg_path_le.text())

    def open_temp_dir_select_dialog(self):
        if ConestogaPlayblastUtils.is_temp_output_env_var_set():
            QtWidgets.QMessageBox.information(self, "Select Temp Output Directory", "The temp output directory is currently set using the CONESTOGA_PLAYBLAST_TEMP_OUTPUT_DIR environment variable.")
            return

        current_path = self.temp_dir_le.text()

        new_path = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Temp Directory", current_path)
        if new_path and new_path != self.temp_dir_le.text():
            self.temp_dir_le.setText(new_path)
            self.update_temp_dir_path()

    def update_temp_dir_path(self):
        ConestogaPlayblastUtils.set_temp_output_dir_path(self.temp_dir_le.text())

    def update_temp_file_format(self, text):
        ConestogaPlayblastUtils.set_temp_file_format(text)

    def open_logo_select_dialog(self):

        if ConestogaPlayblastUtils.is_logo_env_var_set():
            QtWidgets.QMessageBox.information(self, "Select Logo", "The logo path is currently set using the CONESTOGA_PLAYBLAST_LOGO environment variable.")
            return

        current_path = self.logo_path_le.text()

        new_path = QtWidgets.QFileDialog.getOpenFileName(self, "Select Logo", current_path)[0]
        if new_path and new_path != self.logo_path_le.text():
            self.logo_path_le.setText(new_path)
            self.update_logo_path()

    def update_logo_path(self):
        ConestogaPlayblastUtils.set_logo_path(self.logo_path_le.text())

        self.logo_path_updated.emit()  # pylint: disable=E1101

    def on_reset_playblast(self):
        result = QtWidgets.QMessageBox.question(self, "Confirm Reset", "Restore playblast defaults?")
        if result != QtWidgets.QMessageBox.Yes:
            return

        self.playblast_reset.emit()  # pylint: disable=E1101

    def on_reset_shot_mask(self):
        result = QtWidgets.QMessageBox.question(self, "Confirm Reset", "Restore shot mask defaults?")
        if result != QtWidgets.QMessageBox.Yes:
            return

        self.shot_mask_reset.emit()  # pylint: disable=E1101

    def on_collapsed_state_changed(self):
        self.collapsed_state_changed.emit()  # pylint: disable=E1101

    def refresh_settings(self):
        self.ffmpeg_path_le.setText(ConestogaPlayblastUtils.get_ffmpeg_path())
        self.ffmpeg_path_le.setDisabled(ConestogaPlayblastUtils.is_ffmpeg_env_var_set())

        self.temp_dir_le.setText(ConestogaPlayblastUtils.get_temp_output_dir_path())
        self.temp_dir_le.setDisabled(ConestogaPlayblastUtils.is_temp_output_env_var_set())

        self.temp_file_format_cmb.setCurrentText(ConestogaPlayblastUtils.get_temp_file_format())
        self.temp_file_format_cmb.setDisabled(ConestogaPlayblastUtils.is_temp_format_env_set())

        self.logo_path_le.setText(ConestogaPlayblastUtils.get_logo_path())
        self.logo_path_le.setDisabled(ConestogaPlayblastUtils.is_logo_env_var_set())

    def get_collapsed_states(self):
        collapsed = 0
        collapsed += int(self.playblast_grp.is_collapsed())
        collapsed += int(self.shot_mask_grp.is_collapsed()) << 1

        return collapsed

    def set_collapsed_states(self, collapsed):
        self.playblast_grp.set_collapsed(collapsed & 1)
        self.shot_mask_grp.set_collapsed(collapsed & 2)

    def showEvent(self, e):
        self.refresh_settings()


class ConestogaPlayblastUi(QtWidgets.QWidget):

    WINDOW_TITLE = "Conestoga Playblast"
    UI_NAME = "ConestogaPlayblast"

    OPT_VAR_GROUP_STATE = "cstgAPGroupState"

    ui_instance = None


    @classmethod
    def display(cls):
        if cls.ui_instance:
            cls.ui_instance.show_workspace_control()
        else:
            if ConestogaPlayblastUtils.load_plugin():
                cls.ui_instance = ConestogaPlayblastUi()

    @classmethod
    def get_workspace_control_name(cls):
        return "{0}WorkspaceControl".format(cls.UI_NAME)

    def __init__(self):
        super(ConestogaPlayblastUi, self).__init__()

        self.setObjectName(ConestogaPlayblastUi.UI_NAME)

        self.setMinimumWidth(int(400 * ConestogaPlayblastUtils.dpi_real_scale_value()))

        self._batch_playblast_dialog = None

        self.create_widgets()
        self.create_layouts()
        self.create_connections()
        self.create_workspace_control()

        self.restore_collaspsed_states()

        self.main_tab_wdg.setCurrentIndex(0)

    def create_widgets(self):
        scale_value = ConestogaPlayblastUtils.dpi_real_scale_value()
        button_width = int(120 * scale_value)
        button_height = int(40 * scale_value)
        batch_button_width = int(40 * scale_value)

        self.playblast_wdg = ConestogaPlayblastWidget()
        self.playblast_wdg.setAutoFillBackground(True)

        playblast_scroll_area = QtWidgets.QScrollArea()
        playblast_scroll_area.setFrameShape(QtWidgets.QFrame.NoFrame)
        playblast_scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        playblast_scroll_area.setWidgetResizable(True)
        playblast_scroll_area.setWidget(self.playblast_wdg)

        self.shot_mask_wdg = ConestogaShotMaskWidget()
        self.shot_mask_wdg.setAutoFillBackground(True)

        shot_mask_scroll_area = QtWidgets.QScrollArea()
        shot_mask_scroll_area.setFrameShape(QtWidgets.QFrame.NoFrame)
        shot_mask_scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        shot_mask_scroll_area.setWidgetResizable(True)
        shot_mask_scroll_area.setWidget(self.shot_mask_wdg)

        self.settings_wdg = ConestogaPlayblastSettingsWidget()
        self.settings_wdg.setAutoFillBackground(True)

        settings_scroll_area = QtWidgets.QScrollArea()
        settings_scroll_area.setFrameShape(QtWidgets.QFrame.NoFrame)
        settings_scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        settings_scroll_area.setWidgetResizable(True)
        settings_scroll_area.setWidget(self.settings_wdg)

        self.main_tab_wdg = QtWidgets.QTabWidget()
        self.main_tab_wdg.setAutoFillBackground(True)
        self.main_tab_wdg.setStyleSheet("QTabWidget::pane { border: 0; }")
        self.main_tab_wdg.setMinimumHeight(int(200 * scale_value))
        self.main_tab_wdg.addTab(playblast_scroll_area, "Playblast")
        self.main_tab_wdg.addTab(shot_mask_scroll_area, "Shot Mask")
        self.main_tab_wdg.addTab(settings_scroll_area, "Settings")

        palette = self.main_tab_wdg.palette()
        palette.setColor(QtGui.QPalette.Window, QtWidgets.QWidget().palette().color(QtGui.QPalette.Midlight))
        self.main_tab_wdg.setPalette(palette)


        self.toggle_mask_btn = QtWidgets.QPushButton("Shot Mask")
        self.toggle_mask_btn.setFixedSize(button_width, button_height)

        self.playblast_btn = QtWidgets.QPushButton("Playblast")
        self.playblast_btn.setMinimumSize(button_width, button_height)

        self.batch_playblast_btn = QtWidgets.QPushButton("...")
        self.batch_playblast_btn.setFixedSize(batch_button_width, button_height)

        font = self.toggle_mask_btn.font()
        font.setPointSize(10)
        font.setBold(True)
        self.toggle_mask_btn.setFont(font)
        self.playblast_btn.setFont(font)

        pal = self.toggle_mask_btn.palette()
        pal.setColor(QtGui.QPalette.Button, QtGui.QColor(QtCore.Qt.darkCyan).darker())
        self.toggle_mask_btn.setPalette(pal)

        pal.setColor(QtGui.QPalette.Button, QtGui.QColor(QtCore.Qt.darkGreen).darker())
        self.playblast_btn.setPalette(pal)
        self.batch_playblast_btn.setPalette(pal)

    def create_layouts(self):

        button_layout = QtWidgets.QHBoxLayout()
        button_layout.setContentsMargins(0, 10, 0, 0)
        button_layout.addWidget(self.toggle_mask_btn)
        button_layout.addWidget(self.playblast_btn)
        button_layout.addWidget(self.batch_playblast_btn)

        status_bar_layout = QtWidgets.QHBoxLayout()
        status_bar_layout.setContentsMargins(4, 6, 4, 0)
        status_bar_layout.addStretch()
        status_bar_layout.addWidget(QtWidgets.QLabel("v{0}".format(ConestogaPlayblastUtils.get_version())))

        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(6, 6, 6, 0)
        main_layout.setSpacing(2)
        main_layout.addWidget(self.main_tab_wdg)
        main_layout.addLayout(button_layout)
        main_layout.addLayout(status_bar_layout)

    def create_connections(self):
        self.settings_wdg.playblast_reset.connect(self.playblast_wdg.reset_settings)
        self.settings_wdg.logo_path_updated.connect(self.shot_mask_wdg.update_mask)
        self.settings_wdg.shot_mask_reset.connect(self.shot_mask_wdg.reset_settings)

        self.playblast_wdg.collapsed_state_changed.connect(self.on_collapsed_state_changed)
        self.shot_mask_wdg.collapsed_state_changed.connect(self.on_collapsed_state_changed)
        self.settings_wdg.collapsed_state_changed.connect(self.on_collapsed_state_changed)

        self.toggle_mask_btn.clicked.connect(self.shot_mask_wdg.toggle_mask)
        self.playblast_btn.clicked.connect(self.playblast_wdg.do_playblast)
        self.batch_playblast_btn.clicked.connect(self.show_batch_playblast_dialog)

    def create_workspace_control(self):
        self.workspace_control_instance = ConestogaWorkspaceControl(self.get_workspace_control_name())
        if self.workspace_control_instance.exists():
            self.workspace_control_instance.restore(self)
        else:
            self.workspace_control_instance.create(self.WINDOW_TITLE, self, ui_script="from conestoga_playblast_ui import ConestogaPlayblastUi\nConestogaPlayblastUi.display()")

    def show_batch_playblast_dialog(self):
        if not self._batch_playblast_dialog:
            self._batch_playblast_dialog = ConestogaCameraSelectDialog(self)
            self._batch_playblast_dialog.setWindowTitle("Batch Playblast")
            self._batch_playblast_dialog.set_multi_select_enabled(True)
            self._batch_playblast_dialog.set_camera_list_text("Select one or more cameras:")
            self._batch_playblast_dialog.set_select_btn_text("Playblast")
            self._batch_playblast_dialog.accepted.connect(self.on_batch_playblast_accepted)

            selected = []
        else:
            selected = self._batch_playblast_dialog.get_selected()

        self._batch_playblast_dialog.refresh_list(selected=selected)

        self._batch_playblast_dialog.show()

    def on_batch_playblast_accepted(self):
        batch_cameras = self._batch_playblast_dialog.get_selected()

        if batch_cameras:
            self.playblast_wdg.do_playblast(batch_cameras)
        else:
            self.playblast_wdg.log_warning("No cameras selected for batch playblast.")

    def on_collapsed_state_changed(self):
        cmds.optionVar(iv=[ConestogaPlayblastUi.OPT_VAR_GROUP_STATE, self.playblast_wdg.get_collapsed_states()])
        cmds.optionVar(iva=[ConestogaPlayblastUi.OPT_VAR_GROUP_STATE, self.shot_mask_wdg.get_collapsed_states()])
        cmds.optionVar(iva=[ConestogaPlayblastUi.OPT_VAR_GROUP_STATE, self.settings_wdg.get_collapsed_states()])

    def restore_collaspsed_states(self):
        if cmds.optionVar(exists=ConestogaPlayblastUi.OPT_VAR_GROUP_STATE):
            collasped_states = cmds.optionVar(q=ConestogaPlayblastUi.OPT_VAR_GROUP_STATE)

            self.playblast_wdg.set_collapsed_states(collasped_states[0])
            self.shot_mask_wdg.set_collapsed_states(collasped_states[1])
            self.settings_wdg.set_collapsed_states(collasped_states[2])

    def show_workspace_control(self):
        self.workspace_control_instance.set_visible(True)

    def keyPressEvent(self, e):
        pass

    def event(self, e):
        if e.type() == QtCore.QEvent.WindowActivate:
            if self.playblast_wdg.isVisible():
                self.playblast_wdg.refresh_all()

        elif e.type() == QtCore.QEvent.WindowDeactivate:
            if self.playblast_wdg.isVisible():
                self.playblast_wdg.save_settings()

        return super(ConestogaPlayblastUi, self).event(e)


if __name__ == "__main__":

    if ConestogaPlayblastUtils.load_plugin():
        workspace_control_name = ConestogaPlayblastUi.get_workspace_control_name()
        if cmds.window(workspace_control_name, exists=True):
            cmds.deleteUI(workspace_control_name)

        cstg_test_ui = ConestogaPlayblastUi()

    def get_collapsed_states(self):
        collapsed = 0
        collapsed += int(self.labels_grp.is_collapsed())
        collapsed += int(self.text_grp.is_collapsed()) << 1
        collapsed += int(self.borders_grp.is_collapsed()) << 2
        collapsed += int(self.counter_grp.is_collapsed()) << 3

        return collapsed

    def set_collapsed_states(self, collapsed):
        self.labels_grp.set_collapsed(collapsed & 1)
        self.text_grp.set_collapsed(collapsed & 2)
        self.borders_grp.set_collapsed(collapsed & 4)
        self.counter_grp.set_collapsed(collapsed & 8)

    def show_font_select_dialog(self):
        current_font = QtGui.QFont(self.font_le.text())

        font = QtWidgets.QFontDialog.getFont(current_font, self)

        # Order of the tuple returned by getFont changed in newer versions of Qt
        if type(font[0]) == bool:
            ok = font[0]
            family = font[1].family()
        else:
            family = font[0].family()
            ok = font[1]

        if(ok):
            self.font_le.setText(family)

            self.update_mask()