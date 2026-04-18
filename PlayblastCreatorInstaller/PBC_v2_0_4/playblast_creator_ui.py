###############################################################################
# Name:
#   playblast_creator_ui.py
#
# Usage:
#   Launch the CP Playblast UI
#
# Copyright (C) 2025 All rights reserved.
###############################################################################

import copy
import os
import subprocess
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
from playblast_creator_presets import PlayblastCreatorCustomPresets, PlayblastCreatorShotMaskCustomPresets


class PBCPlayblastUtils(object):

    PLUG_IN_NAME = "playblast_creator.py"

    @classmethod
    def _plugin_search_paths(cls):
        paths = []

        # Same folder as this UI script (installed PBC_v2_0_4 folder).
        paths.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), cls.PLUG_IN_NAME))

        # Maya user scripts install root fallback.
        scripts_root = os.path.join(cmds.internalVar(userAppDir=True), "scripts")
        paths.append(os.path.join(scripts_root, "playblast_creator", "PBC_v2_0_4", cls.PLUG_IN_NAME))

        # De-duplicate while preserving order.
        deduped = []
        for path in paths:
            normed = os.path.normpath(path)
            if normed not in deduped:
                deduped.append(normed)

        return deduped

    @classmethod
    def is_plugin_loaded(cls):
        loaded_plugins = cmds.pluginInfo(q=True, listPlugins=True) or []

        for plugin in loaded_plugins:
            plugin_name = os.path.basename(plugin)
            if plugin == cls.PLUG_IN_NAME or plugin_name == cls.PLUG_IN_NAME:
                return True

        return False

    @classmethod
    def _set_plugin_autoload(cls):
        """Mark the plugin for auto-load so scenes that reference the
        PlayblastCreatorShotMask node type open cleanly next session.

        Without this, Maya reports 'Unrecognized node type
        PlayblastCreatorShotMask; preserving node information during this
        session' whenever a saved scene is reopened before the UI is
        launched.
        """
        try:
            cmds.pluginInfo(cls.PLUG_IN_NAME, edit=True, autoload=True)
        except Exception:
            pass

    @classmethod
    def load_plugin(cls):
        if cls.is_plugin_loaded():
            cls._set_plugin_autoload()
            return True

        # Try the short name first (relies on MAYA_PLUG_IN_PATH), then
        # fall back to any absolute paths we know about.
        load_targets = [cls.PLUG_IN_NAME]
        load_targets.extend(cls._plugin_search_paths())

        for target in load_targets:
            try:
                cmds.loadPlugin(target)
                cls._set_plugin_autoload()
                return True
            except Exception:
                continue

        om.MGlobal.displayError(
            "Failed to load Playblast Creator plug-in: {0}. Tried: {1}".format(
                cls.PLUG_IN_NAME, ", ".join(load_targets)
            )
        )
        return False

    @classmethod
    def get_version(cls):
        return cmds.PlayblastCreator(v=True)[0]  # pylint: disable=E1101

    @classmethod
    def get_ffmpeg_path(cls):
        return cmds.PlayblastCreator(q=True, fp=True)[0]  # pylint: disable=E1101

    @classmethod
    def set_ffmpeg_path(cls, path):
        cmds.PlayblastCreator(e=True, fp=path)  # pylint: disable=E1101

    @classmethod
    def is_ffmpeg_env_var_set(cls):
        return cmds.PlayblastCreator(fev=True)[0]  # pylint: disable=E1101

    @classmethod
    def get_temp_output_dir_path(cls):
        return cmds.PlayblastCreator(q=True, tp=True)[0]  # pylint: disable=E1101

    @classmethod
    def set_temp_output_dir_path(cls, path):
        cmds.PlayblastCreator(e=True, tp=path)  # pylint: disable=E1101

    @classmethod
    def is_temp_output_env_var_set(cls):
        return cmds.PlayblastCreator(tev=True)[0]  # pylint: disable=E1101

    @classmethod
    def get_temp_file_format(cls):
        return cmds.PlayblastCreator(q=True, tf=True)[0]  # pylint: disable=E1101

    @classmethod
    def set_temp_file_format(cls, file_format):
        cmds.PlayblastCreator(e=True, tf=file_format)  # pylint: disable=E1101

    @classmethod
    def is_temp_format_env_set(cls):
        return cmds.PlayblastCreator(tfe=True)[0]  # pylint: disable=E1101

    @classmethod
    def get_logo_path(cls):
        return cmds.PlayblastCreator(q=True, lp=True)[0]  # pylint: disable=E1101

    @classmethod
    def set_logo_path(cls, path):
        cmds.PlayblastCreator(e=True, lp=path)  # pylint: disable=E1101

    @classmethod
    def is_logo_env_var_set(cls):
        return cmds.PlayblastCreator(lev=True)[0]  # pylint: disable=E1101

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

    # ------------------------------------------------------------------
    # Encoder / codec availability
    # ------------------------------------------------------------------
    _available_video_encoders_cache = None

    # ffmpeg encoder ids the tool knows how to drive.
    FFMPEG_TARGET_ENCODERS = (
        "libx264",
        "h264_nvenc",
        "h264_videotoolbox",
        "mpeg4",
        "prores",
        "prores_ks",
    )

    @classmethod
    def detect_available_video_encoders(cls, ffmpeg_path=None, use_cache=True):
        """Return a set of ffmpeg encoder ids that are present in the binary.

        Runs `ffmpeg -hide_banner -encoders` and parses the output. On
        failure (no binary, timeout, permission error) returns an empty
        set so the caller can fall back to Maya-native image sequences.
        """
        if use_cache and cls._available_video_encoders_cache is not None:
            return cls._available_video_encoders_cache

        if ffmpeg_path is None:
            try:
                ffmpeg_path = cls.get_ffmpeg_path()
            except Exception:
                ffmpeg_path = ""

        found = set()
        if ffmpeg_path and os.path.isfile(ffmpeg_path):
            try:
                popen_kwargs = {
                    "stdout": subprocess.PIPE,
                    "stderr": subprocess.STDOUT,
                }
                # Prevent a console flash on Windows.
                if sys.platform == "win32":
                    popen_kwargs["creationflags"] = 0x08000000  # CREATE_NO_WINDOW
                proc = subprocess.Popen(
                    [ffmpeg_path, "-hide_banner", "-encoders"],
                    **popen_kwargs
                )
                try:
                    out, _ = proc.communicate(timeout=5)
                except Exception:
                    proc.kill()
                    out = b""
                text = (out or b"").decode("utf-8", errors="ignore").lower()
                for name in cls.FFMPEG_TARGET_ENCODERS:
                    # ffmpeg lists each encoder on its own line; look for
                    # the whitespace-delimited token.
                    if " {0} ".format(name) in " " + text + " ":
                        found.add(name)
            except Exception:
                found = set()

        cls._available_video_encoders_cache = found
        return found

    @classmethod
    def invalidate_encoder_cache(cls):
        cls._available_video_encoders_cache = None

    @classmethod
    def detect_available_image_compressions(cls):
        """Return Maya's native image-sequence compressions that are present.

        Queries `cmds.playblast(query=True, format=True)` and then, if
        the 'image' format is available, returns the intersection of
        the encoders the tool exposes (png / jpg / tif) and what Maya
        reports. Falls back to the full set if Maya can't be queried.
        """
        wanted = ("png", "jpg", "tif")
        try:
            formats = cmds.playblast(query=True, format=True) or []
        except Exception:
            return list(wanted)

        if "image" not in [f.lower() for f in formats]:
            # Extremely unusual, but be safe.
            return list(wanted)

        try:
            compressions = cmds.playblast(query=True, compression=True) or []
            compressions_lower = {c.lower() for c in compressions}
            filtered = [c for c in wanted if c in compressions_lower]
            if filtered:
                return filtered
        except Exception:
            pass

        return list(wanted)


class PBCCollapsibleGrpHeader(QtWidgets.QWidget):

    clicked = QtCore.Signal()

    def __init__(self, text, parent=None):
        super(PBCCollapsibleGrpHeader, self).__init__(parent)

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


class PBCCollapsibleGrpWidget(QtWidgets.QWidget):

    collapsed_state_changed = QtCore.Signal()

    def __init__(self, text, parent=None):
        super(PBCCollapsibleGrpWidget, self).__init__(parent)

        self.append_stretch_on_collapse = False
        self.stretch_appended = False

        self.header_wdg = PBCCollapsibleGrpHeader(text)
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


class PBCColorButton(QtWidgets.QWidget):

    color_changed = QtCore.Signal()

    def __init__(self, color=(1.0, 1.0, 1.0), parent=None):
        super(PBCColorButton, self).__init__(parent)

        self.setObjectName("PBCColorButton")

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
        scale_value = PBCPlayblastUtils.dpi_real_scale_value()

        self._color_slider_widget.setFixedWidth(int(width * scale_value))
        self._color_widget.setFixedHeight(int(height * scale_value))

    def set_color(self, color):
        cmds.colorSliderGrp(self.get_full_name(), e=True, rgbValue=(color[0], color[1], color[2]))
        self.on_color_changed()

    def get_color(self):
        return cmds.colorSliderGrp(self.get_full_name(), q=True, rgbValue=True)

    def on_color_changed(self, *args):
        self.color_changed.emit()  # pylint: disable=E1101


class PBCLineEdit(QtWidgets.QLineEdit):

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
        super(PBCLineEdit, self).__init__(parent)

        self.le_type = le_type

        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)

        self.customContextMenuRequested.connect(self.show_context_menu)

    def show_context_menu(self, pos):
        context_menu = QtWidgets.QMenu(self)

        action = context_menu.addAction("Insert {tag}")
        action.setEnabled(False)

        context_menu.addSeparator()

        lookup = []
        if self.le_type == PBCLineEdit.TYPE_PLAYBLAST_OUTPUT_PATH:
            lookup.extend(PBCLineEdit.PLAYBLAST_OUTPUT_PATH_LOOKUP)
            lookup.extend(PlayblastCreatorCustomPresets.PLAYBLAST_OUTPUT_PATH_LOOKUP)
        elif self.le_type == PBCLineEdit.TYPE_PLAYBLAST_OUTPUT_FILENAME:
            lookup.extend(PBCLineEdit.PLAYBLAST_OUTPUT_FILENAME_LOOKUP)
            lookup.extend(PlayblastCreatorCustomPresets.PLAYBLAST_OUTPUT_FILENAME_LOOKUP)
        elif self.le_type == PBCLineEdit.TYPE_SHOT_MASK_LABEL:
            lookup.extend(PBCLineEdit.SHOT_MASK_LABEL_LOOKUP)
            lookup.extend(PlayblastCreatorShotMaskCustomPresets.SHOT_MASK_LABEL_LOOKUP)

        for item in lookup:
            action = context_menu.addAction(item[0])
            action.setData(item[1])
            action.triggered.connect(self.on_context_menu_item_selected)

        context_menu.exec_(self.mapToGlobal(pos))

    def on_context_menu_item_selected(self):
        self.insert(self.sender().data())


class PBCFormLayout(QtWidgets.QGridLayout):

    def __init__(self, parent=None):
        super(PBCFormLayout, self).__init__(parent)

        self.setContentsMargins(0, 0, 0, 8)
        self.setColumnMinimumWidth(0, 80)
        self.setHorizontalSpacing(6)

    def addWidgetRow(self, row, label, widget):
        self.addWidget(QtWidgets.QLabel(label), row, 0, QtCore.Qt.AlignRight)
        self.addWidget(widget, row, 1)

    def addLayoutRow(self, row, label, layout):
        self.addWidget(QtWidgets.QLabel(label), row, 0, QtCore.Qt.AlignRight)
        self.addLayout(layout, row, 1)


class PBCCameraSelectDialog(QtWidgets.QDialog):

    def __init__(self, parent):
        super(PBCCameraSelectDialog, self).__init__(parent)

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

        self.camera_list_wdg.addItems(PBCPlayblastUtils.cameras_in_scene(include_defaults, user_created_first))

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


class PBCWorkspaceControl(object):

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


class PBCPlayblast(QtCore.QObject):

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

    # Internal encoder ids the tool knows how to drive, per container.
    # Friendly labels shown in the UI come from ENCODER_DISPLAY_LABEL.
    VIDEO_ENCODER_LOOKUP = {
        "mov": ["h264", "mpeg4", "prores"],
        "mp4": ["h264", "mpeg4"],
        "Image": ["png", "jpg", "tif"],
    }

    # Display labels for the encoder combo box. Keeps internal ids
    # ("h264", "mpeg4", ...) stable while showing something clearer.
    ENCODER_DISPLAY_LABEL = {
        "h264": "H.264 (libx264)",
        "mpeg4": "MPEG-4",
        "prores": "Apple ProRes",
        "png": "PNG (sequence)",
        "jpg": "JPEG (sequence)",
        "tif": "TIFF (sequence)",
    }

    # Map our internal encoder id to the ffmpeg encoder names that can
    # satisfy it. Order matters: first match wins.
    ENCODER_TO_FFMPEG = {
        "h264": ("h264_nvenc", "h264_videotoolbox", "libx264"),
        "mpeg4": ("mpeg4",),
        "prores": ("prores_ks", "prores"),
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

    PLATFORM_H264_CODEC_LOOKUP = {
        "win32": "h264_nvenc",
        "darwin": "h264_videotoolbox",
    }

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
        super(PBCPlayblast, self).__init__()

        self.set_maya_logging_enabled(PBCPlayblast.DEFAULT_MAYA_LOGGING_ENABLED)

        self.build_presets()

        self.set_camera(PBCPlayblast.DEFAULT_CAMERA)
        self.set_resolution(PBCPlayblast.DEFAULT_RESOLUTION)
        self.set_frame_range(PBCPlayblast.DEFAULT_FRAME_RANGE)

        self.set_encoding(PBCPlayblast.DEFAULT_CONTAINER, PBCPlayblast.DEFAULT_ENCODER)
        self.set_h264_settings(PBCPlayblast.DEFAULT_H264_QUALITY, PBCPlayblast.DEFAULT_H264_PRESET)
        self.set_image_settings(PBCPlayblast.DEFAULT_IMAGE_QUALITY)

        self.set_visibility(PBCPlayblast.DEFAULT_VISIBILITY)

        self.initialize_ffmpeg_process()

    def build_presets(self):
        self.resolution_preset_names = []
        self.resolution_presets = {}

        for preset in PBCPlayblast.RESOLUTION_PRESETS:
            self.resolution_preset_names.append(preset[0])
            self.resolution_presets[preset[0]] = preset[1]

        try:
            for preset in PlayblastCreatorCustomPresets.RESOLUTION_PRESETS:
                self.resolution_preset_names.append(preset[0])
                self.resolution_presets[preset[0]] = preset[1]
        except:
            traceback.print_exc()
            self.log_error("Failed to add custom resolution presets. See script editor for details.")

        self.viewport_visibility_preset_names = []
        self.viewport_visibility_presets = {}

        for preset in PBCPlayblast.VIEWPORT_VISIBILITY_PRESETS:
            self.viewport_visibility_preset_names.append(preset[0])
            self.viewport_visibility_presets[preset[0]] = preset[1]

        try:
            for preset in PlayblastCreatorCustomPresets.VIEWPORT_VISIBILITY_PRESETS:
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
        if frame_range in PBCPlayblast.FRAME_RANGE_PRESETS:
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
            for preset in PBCPlayblast.FRAME_RANGE_PRESETS:
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
            for lookup_item in PBCPlayblast.VIEWPORT_VISIBILITY_LOOKUP:
                visibility_data.append(lookup_item[0] in preset_names)

        return visibility_data

    def get_viewport_visibility(self):
        model_panel = self.get_viewport_panel()
        if not model_panel:
            return None

        viewport_visibility = []
        try:
            for item in PBCPlayblast.VIEWPORT_VISIBILITY_LOOKUP:
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
        for item in PBCPlayblast.VIEWPORT_VISIBILITY_LOOKUP:
            visibility_flags[item[1]] = visibility_data[data_index]
            data_index += 1

        return visibility_flags

    def set_encoding(self, container_format, encoder):
        if container_format not in PBCPlayblast.VIDEO_ENCODER_LOOKUP.keys():
            self.log_error("Invalid container: {0}. Expected one of {1}".format(container_format, PBCPlayblast.VIDEO_ENCODER_LOOKUP.keys()))
            return

        if encoder not in PBCPlayblast.VIDEO_ENCODER_LOOKUP[container_format]:
            self.log_error("Invalid encoder: {0}. Expected one of {1}".format(encoder, PBCPlayblast.VIDEO_ENCODER_LOOKUP[container_format]))
            return

        self._container_format = container_format
        self._encoder = encoder

    def set_h264_settings(self, quality, preset):
        if not quality in PBCPlayblast.H264_QUALITIES.keys():
            self.log_error("Invalid h264 quality: {0}. Expected one of {1}".format(quality, PBCPlayblast.H264_QUALITIES.keys()))
            return

        if not preset in PBCPlayblast.H264_PRESETS:
            self.log_error("Invalid h264 preset: {0}. Expected one of {1}".format(preset, PBCPlayblast.H264_PRESETS))
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

    def execute(self, output_dir, filename, padding=4, overscan=False, show_ornaments=True, show_in_viewer=True, offscreen=False, overwrite=False, camera_override="", enable_camera_frame_range=False, include_sound=True, scale_percent=100, image_quality_override=None):

        ffmpeg_path = PBCPlayblastUtils.get_ffmpeg_path()
        if self.requires_ffmpeg() and not self.validate_ffmpeg(ffmpeg_path):
            self.log_error("ffmpeg executable is not configured. See script editor for details.")
            return

        temp_file_format = PBCPlayblastUtils.get_temp_file_format()
        temp_file_is_movie = temp_file_format == "movie"

        if temp_file_is_movie:
            if sys.platform == "win32":
                temp_file_extension = "avi"
            else:
                temp_file_extension = "mov"
        else:
            temp_file_extension = temp_file_format

        if not output_dir:
            self.log_error("Output directory path not set")
            return
        if not filename:
            self.log_error("Output file name not set")
            return

        if camera_override:
            camera = camera_override
        else:
            camera = self._camera

        viewport_model_panel = self.get_viewport_panel(preferred_camera=camera)
        if not viewport_model_panel:
            self.log_error("No model viewport panel is available. Open a viewport and retry.")
            return

        # Store original camera from the resolved viewport
        orig_camera = self.get_active_camera(viewport_model_panel)

        if not camera:
            camera = orig_camera

        if not camera in cmds.listCameras():
            self.log_error("Camera does not exist: {0}".format(camera))
            return

        output_dir = self.resolve_output_directory_path(output_dir)
        filename = self.resolve_output_filename(filename, camera)

        if padding <= 0:
            padding = PBCPlayblast.DEFAULT_PADDING

        if self.requires_ffmpeg():
            output_path = os.path.normpath(os.path.join(output_dir, "{0}.{1}".format(filename, self._container_format)))
            if not overwrite and os.path.exists(output_path):
                self.log_error("Output file already exists. Enable overwrite to ignore.")
                return

            playblast_output_dir = "{0}/playblast_temp".format(output_dir)
            playblast_output = os.path.normpath(os.path.join(playblast_output_dir, filename))
            force_overwrite = True
            viewer = False
            # Maya's 'quality' flag in the temp pass only affects the
            # intermediate; ffmpeg re-encodes with its own CRF/quality.
            quality = 100 if image_quality_override is None else int(image_quality_override)

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
            # User-supplied override wins; fall back to stored encoder setting.
            quality = int(image_quality_override) if image_quality_override is not None else self._image_quality
            index_from_zero = False
            viewer = show_in_viewer

        widthHeight = self.get_resolution_width_height()
        start_frame, end_frame = self.get_start_end_frame()

        if enable_camera_frame_range:
            if cmds.attributeQuery(PBCPlayblast.CAMERA_PLAYBLAST_START_ATTR, node=camera, exists=True) and cmds.attributeQuery(PBCPlayblast.CAMERA_PLAYBLAST_END_ATTR, node=camera, exists=True):
                try:
                    start_frame = int(cmds.getAttr("{0}.{1}".format(camera, PBCPlayblast.CAMERA_PLAYBLAST_START_ATTR)))
                    end_frame = int(cmds.getAttr("{0}.{1}".format(camera, PBCPlayblast.CAMERA_PLAYBLAST_END_ATTR)))

                    self.log_output("Camera frame range enabled for '{0}' camera: ({1}, {2})\n".format(camera, start_frame, end_frame))
                except:
                    self.log_warning("Camera frame range disabled. Invalid attribute type(s) on '{0}' camera (expected integer or float). Defaulting to Playback range.\n".format(camera))

            else:
                self.log_warning("Camera frame range disabled. Attributes '{0}' and '{1}' do not exist on '{2}' camera. Defaulting to Playback range.\n".format(PBCPlayblast.CAMERA_PLAYBLAST_START_ATTR, PBCPlayblast.CAMERA_PLAYBLAST_END_ATTR, camera))

        if start_frame > end_frame:
            self.log_error("Invalid frame range. The start frame ({0}) is greater than the end frame ({1}).".format(start_frame, end_frame))
            return


        # Clamp scale to Maya's allowed range; anything outside 10-100 is
        # likely a user mistake from a custom settings file.
        try:
            scale_percent_int = int(scale_percent)
        except (TypeError, ValueError):
            scale_percent_int = 100
        if scale_percent_int < 1:
            scale_percent_int = 1
        elif scale_percent_int > 100:
            scale_percent_int = 100

        options = {
            "filename": playblast_output,
            "widthHeight": widthHeight,
            "percent": scale_percent_int,
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

        # Only forward sound to Maya when the user opted in AND the
        # temp format can actually carry audio (i.e. movie, not an
        # image sequence).
        if temp_file_is_movie and include_sound:
            if self.use_trax_sounds():
                options["useTraxSounds"] = True
            else:
                sound_node = self.get_sound_node()
                if sound_node:
                    options["sound"] = sound_node

        self.log_output("Starting '{0}' playblast...".format(camera))
        self.log_output("Playblast options: {0}\n".format(options))
        QtCore.QCoreApplication.processEvents()

        self.set_active_camera(camera, viewport_model_panel)

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
            self.set_active_camera(orig_camera, viewport_model_panel)
            self.set_viewport_visibility(model_editor, orig_visibility_flags)

        if playblast_failed:
            return

        if self.requires_ffmpeg():
            if temp_file_is_movie:
                source_path = "{0}/{1}.{2}".format(playblast_output_dir, filename, temp_file_extension)
            else:
                source_path = "{0}/{1}.%0{2}d.{3}".format(playblast_output_dir, filename, padding, temp_file_extension)

            if self._encoder in ("h264", "mpeg4", "prores"):
                if temp_file_is_movie:
                    self.transcode_video(self._encoder, ffmpeg_path, source_path, output_path, include_audio=include_sound)
                else:
                    self.encode_video(self._encoder, ffmpeg_path, source_path, output_path, start_frame, include_audio=include_sound)
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

    def get_platform_h264_video_codec(self):
        """Pick the best available H.264 ffmpeg encoder for this platform.

        Prefers the hardware accelerator if it was detected, otherwise
        falls back to libx264 (software).
        """
        available = PBCPlayblastUtils.detect_available_video_encoders()
        preferred = PBCPlayblast.PLATFORM_H264_CODEC_LOOKUP.get(sys.platform, "libx264")
        if preferred in available:
            codec = preferred
        elif "libx264" in available:
            codec = "libx264"
        else:
            codec = preferred
        self.log_output("Selected H.264 codec for platform '{0}': {1}".format(sys.platform, codec))
        return codec

    def get_h264_video_codec_arguments(self, crf, preset):
        video_codec = self.get_platform_h264_video_codec()

        if video_codec == "h264_nvenc":
            return ["-c:v", video_codec, "-cq:v", "{0}".format(crf), "-preset:v", "p4", "-pix_fmt", "yuv420p"]

        if video_codec == "h264_videotoolbox":
            quality = max(1, 31 - int(round(crf)))
            return ["-c:v", video_codec, "-q:v", "{0}".format(quality), "-pix_fmt", "yuv420p"]

        return ["-c:v", "libx264", "-crf:v", "{0}".format(crf), "-preset:v", preset, "-profile:v", "high", "-pix_fmt", "yuv420p"]

    def get_mpeg4_video_codec_arguments(self, crf):
        """MPEG-4 Part 2 (legacy but still very common in education).

        ffmpeg's mpeg4 encoder uses -qscale:v 1..31 (lower = better),
        so map our CRF range 18..26 onto roughly 2..7 which produces
        a usable quality envelope.
        """
        qscale = max(1, min(8, int(round((crf - 15) / 2))))
        return ["-c:v", "mpeg4", "-qscale:v", "{0}".format(qscale), "-pix_fmt", "yuv420p"]

    def get_prores_video_codec_arguments(self):
        """Apple ProRes 422 HQ - editorial-friendly, large files."""
        available = PBCPlayblastUtils.detect_available_video_encoders()
        codec = "prores_ks" if "prores_ks" in available else "prores"
        return ["-c:v", codec, "-profile:v", "3", "-pix_fmt", "yuv422p10le"]

    def get_video_codec_arguments(self, encoder, crf, preset):
        """Dispatch ffmpeg codec arguments for a given internal encoder id."""
        if encoder == "h264":
            return self.get_h264_video_codec_arguments(crf, preset)
        if encoder == "mpeg4":
            return self.get_mpeg4_video_codec_arguments(crf)
        if encoder == "prores":
            return self.get_prores_video_codec_arguments()
        # Unknown encoder - fall back to a lossless copy to avoid silent
        # data loss. The caller will still have logged the mismatch.
        self.log_warning("Unknown encoder '{0}', falling back to copy.".format(encoder))
        return ["-c:v", "copy"]

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


    def encode_video(self, encoder, ffmpeg_path, source_path, output_path, start_frame, include_audio=True):
        """Encode an image sequence into a video using the given encoder.

        When include_audio is False the timeline sound node is ignored
        and the resulting file is silent.
        """
        self.log_output("Starting {0} encoding...".format(encoder))
        self.log_output("ffmpeg path: {0}".format(ffmpeg_path))

        framerate = self.get_frame_rate()

        audio_file_path = None
        audio_offset = 0.0
        if include_audio:
            audio_file_path, audio_frame_offset = self.get_audio_attributes()
            if audio_file_path:
                audio_offset = self.get_audio_offset_in_sec(start_frame, audio_frame_offset, framerate)
                self.log_output("Including timeline audio: {0}".format(audio_file_path))
        else:
            self.log_output("Audio disabled by user - output will be silent.")

        crf = PBCPlayblast.H264_QUALITIES[self._h264_quality]
        preset = self._h264_preset
        video_codec_args = self.get_video_codec_arguments(encoder, crf, preset)

        arguments = []
        arguments.append("-y")
        arguments.extend(["-framerate", "{0}".format(framerate), "-i", source_path])

        if audio_file_path:
            arguments.extend(["-ss", "{0}".format(audio_offset), "-i", audio_file_path])

        arguments.extend(video_codec_args)

        if audio_file_path:
            arguments.extend(["-filter_complex", "[1:0] apad", "-shortest"])
        elif not include_audio:
            arguments.append("-an")

        arguments.append(output_path)

        self.log_output("ffmpeg arguments: {0}\n".format(arguments))

        self.execute_ffmpeg_command(ffmpeg_path, arguments)

    def transcode_video(self, encoder, ffmpeg_path, source_path, output_path, include_audio=True):
        """Transcode a video temp file into the final container/codec.

        When include_audio is True the audio stream from the input file
        (if any) is re-encoded to AAC so it carries through to the
        final mp4/mov. `-map 0:a?` makes the audio stream optional, so
        the command still succeeds if the temp file has no audio.
        """
        self.log_output("Starting {0} transcoding...".format(encoder))
        self.log_output("ffmpeg path: {0}".format(ffmpeg_path))

        crf = PBCPlayblast.H264_QUALITIES[self._h264_quality]
        preset = self._h264_preset
        video_codec_args = self.get_video_codec_arguments(encoder, crf, preset)

        arguments = []
        arguments.append("-y")
        arguments.extend(["-i", source_path])
        arguments.extend(video_codec_args)

        if include_audio:
            arguments.extend([
                "-map", "0:v",
                "-map", "0:a?",
                "-c:a", "aac",
                "-b:a", "192k",
            ])
        else:
            arguments.append("-an")

        arguments.append(output_path)

        self.log_output("ffmpeg arguments: {0}\n".format(arguments))

        self.execute_ffmpeg_command(ffmpeg_path, arguments)

    # Backwards-compatible wrappers so any external script referencing
    # the older names keeps working.
    def encode_h264(self, ffmpeg_path, source_path, output_path, start_frame, include_audio=True):
        return self.encode_video("h264", ffmpeg_path, source_path, output_path, start_frame, include_audio=include_audio)

    def transcode_h264(self, ffmpeg_path, source_path, output_path, include_audio=True):
        return self.transcode_video("h264", ffmpeg_path, source_path, output_path, include_audio=include_audio)


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
        dir_path = PlayblastCreatorCustomPresets.parse_playblast_output_dir_path(dir_path)

        if "{project}" in dir_path:
            dir_path = dir_path.replace("{project}", self.get_project_dir_path())
        if "{temp}" in dir_path:
            temp_dir_path = PBCPlayblastUtils.get_temp_output_dir_path()

            if not temp_dir_path:
                self.log_warning("The {temp} directory path is not set")

            dir_path = dir_path.replace("{temp}", temp_dir_path)

        return dir_path

    def resolve_output_filename(self, filename, camera):
        filename = PlayblastCreatorCustomPresets.parse_playblast_output_filename(filename)

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

    def get_viewport_panel(self, preferred_camera=None):
        panels = []

        focused_panel = cmds.getPanel(withFocus=True)
        if focused_panel:
            panels.append(focused_panel)

        visible_panels = cmds.getPanel(vis=True) or []
        panels.extend(visible_panels)

        model_panels = cmds.getPanel(type="modelPanel") or []
        panels.extend(model_panels)

        # de-duplicate while preserving order
        unique_panels = []
        for panel in panels:
            if panel not in unique_panels:
                unique_panels.append(panel)

        valid_model_panels = []
        for panel in unique_panels:
            try:
                cmds.modelPanel(panel, q=True, modelEditor=True)
                valid_model_panels.append(panel)
            except Exception:
                continue

        if not valid_model_panels:
            return None

        if preferred_camera:
            for panel in valid_model_panels:
                try:
                    if cmds.modelPanel(panel, q=True, camera=True) == preferred_camera:
                        return panel
                except Exception:
                    continue

        return valid_model_panels[0]

    def get_active_camera(self, model_panel=None):
        model_panel = model_panel or self.get_viewport_panel()
        if not model_panel:
            self.log_error("Failed to get active camera. A viewport is not active.")
            return None

        return cmds.modelPanel(model_panel, q=True, camera=True)

    def set_active_camera(self, camera, model_panel=None):
        model_panel = model_panel or self.get_viewport_panel(camera)
        if model_panel:
            mel.eval("lookThroughModelPanel {0} {1}".format(camera, model_panel))
        else:
            self.log_error("Failed to set active camera. A viewport is not active.")


    def log_error(self, text):
        if self._log_to_maya:
            om.MGlobal.displayError("[Playblast Creator] {0}".format(text))

        self.output_logged.emit("[ERROR] {0}".format(text))  # pylint: disable=E1101

    def log_warning(self, text):
        if self._log_to_maya:
            om.MGlobal.displayWarning("[Playblast Creator] {0}".format(text))

        self.output_logged.emit("[WARNING] {0}".format(text))  # pylint: disable=E1101

    def log_output(self, text):
        if self._log_to_maya:
            om.MGlobal.displayInfo(text)

        self.output_logged.emit(text)  # pylint: disable=E1101


class PBCEncoderSettingsDialog(QtWidgets.QDialog):

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
        super(PBCEncoderSettingsDialog, self).__init__(parent)

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
        self.h264_quality_combo.addItems(PBCEncoderSettingsDialog.H264_QUALITIES)

        self.h264_preset_combo = QtWidgets.QComboBox()
        self.h264_preset_combo.addItems(PBCPlayblast.H264_PRESETS)

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
        if not page in PBCEncoderSettingsDialog.ENCODER_PAGES:
            return False

        self.settings_stacked_wdg.setCurrentIndex(PBCEncoderSettingsDialog.ENCODER_PAGES[page])
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


class PBCVisibilityDialog(QtWidgets.QDialog):

    def __init__(self, parent):
        super(PBCVisibilityDialog, self).__init__(parent)

        self.setWindowTitle("Customize Visibility")
        self.setWindowFlags(self.windowFlags() ^ QtCore.Qt.WindowContextHelpButtonHint)
        self.setModal(True)

        visibility_layout = QtWidgets.QGridLayout()

        index = 0
        self.visibility_checkboxes = []

        for i in range(len(PBCPlayblast.VIEWPORT_VISIBILITY_LOOKUP)):
            checkbox = QtWidgets.QCheckBox(PBCPlayblast.VIEWPORT_VISIBILITY_LOOKUP[i][0])

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


class PBCShotMask(object):
    """Helper around the PlayblastCreatorShotMask locator.

    Mirrors the ZurbriggShotMask pattern from v1.4.2: the plugin is
    loaded on demand, and the mask is created as a transform + locator
    shape pair so there is exactly one persistent mask in the scene.
    """

    NODE_NAME = "PlayblastCreatorShotMask"
    TRANSFORM_NODE_NAME = "pbcShotMask"
    SHAPE_NODE_NAME = "pbcShotMaskShape"

    @classmethod
    def ensure_plugin(cls):
        return PBCPlayblastUtils.load_plugin()

    @classmethod
    def get_mask(cls):
        if not PBCPlayblastUtils.is_plugin_loaded():
            return None
        try:
            nodes = cmds.ls(type=cls.NODE_NAME) or []
        except Exception:
            return None
        return nodes[0] if nodes else None

    @classmethod
    def create_mask(cls):
        """Make sure a shot-mask node exists in the scene and return it.

        The plug-in must be loaded first; otherwise createNode fails with
        "Unknown object type: PlayblastCreatorShotMask".
        """
        if not cls.ensure_plugin():
            return None
        mask = cls.get_mask()
        if mask:
            return mask
        selection = cmds.ls(sl=True) or []
        try:
            transform = cmds.createNode(
                "transform", name=cls.TRANSFORM_NODE_NAME, skipSelect=True
            )
            mask = cmds.createNode(
                cls.NODE_NAME,
                name=cls.SHAPE_NODE_NAME,
                parent=transform,
                skipSelect=True,
            )
        finally:
            if selection:
                try:
                    cmds.select(selection, r=True)
                except Exception:
                    pass
        return mask

    @classmethod
    def delete_mask(cls):
        mask = cls.get_mask()
        if not mask:
            return
        transform = cmds.listRelatives(mask, fullPath=True, parent=True) or []
        try:
            if transform:
                cmds.delete(transform[0])
            else:
                cmds.delete(mask)
        except Exception:
            pass

    @classmethod
    def set_camera(cls, camera_name):
        """Bind an existing mask to a camera.

        An empty string means the mask draws on all cameras (matches the
        v1.4.2 behaviour when no specific camera is chosen).
        """
        mask = cls.get_mask()
        if not mask:
            return
        if not cmds.attributeQuery("camera", node=mask, exists=True):
            return
        try:
            cmds.setAttr(
                "{0}.camera".format(mask),
                camera_name or "",
                type="string",
            )
        except RuntimeError:
            pass

    @classmethod
    def set_visible(cls, visible):
        """Toggle the mask locator's transform visibility."""
        mask = cls.get_mask()
        if not mask:
            return
        parents = cmds.listRelatives(mask, parent=True, fullPath=True) or [mask]
        for parent in parents:
            if cmds.attributeQuery("visibility", node=parent, exists=True):
                try:
                    cmds.setAttr("{0}.visibility".format(parent), bool(visible))
                except RuntimeError:
                    pass


class PBCPlayblastWidget(QtWidgets.QWidget):

    OPT_VAR_OUTPUT_DIR = "pbcrPlayblastOutputDir"
    OPT_VAR_OUTPUT_FILENAME = "pbcrPlayblastOutputFilename"
    OPT_VAR_FORCE_OVERWRITE = "pbcrPlayblastForceOverwrite"

    OPT_VAR_CAMERA = "pbcrPlayblastCamera"
    OPT_VAR_HIDE_DEFAULT_CAMERAS = "pbcrPlayblastHideDefaultCameras"

    OPT_VAR_RESOLUTION_PRESET = "pbcrPlayblastResolutionPreset"
    OPT_VAR_RESOLUTION_WIDTH = "pbcrPlayblastResolutionWidth"
    OPT_VAR_RESOLUTION_HEIGHT = "pbcrPlayblastResolutionHeight"

    OPT_VAR_FRAME_RANGE_PRESET = "pbcrPlayblastFrameRangePreset"
    OPT_VAR_FRAME_RANGE_START = "pbcrPlayblastFrameRangeStart"
    OPT_VAR_FRAME_RANGE_END = "pbcrPlayblastFrameRangeEnd"

    OPT_VAR_ENCODING_CONTAINER = "pbcrPlayblastEncodingContainer"
    OPT_VAR_ENCODING_VIDEO_CODEC = "pbcrPlayblastEncodingVideoCodec"

    OPT_VAR_H264_QUALITY = "pbcrPlayblastH264Quality"
    OPT_VAR_H264_PRESET = "pbcrPlayblastH264Preset"

    OPT_VAR_IMAGE_QUALITY = "pbcrPlayblastImageQuality"

    OPT_VAR_VISIBILITY_PRESET = "pbcrPlayblastVisibilityPreset"
    OPT_VAR_VISIBILITY_DATA = "pbcrPlayblastVisibilityData"

    OPT_VAR_OVERSCAN = "pbcrPlayblastOverscan"
    OPT_VAR_ORNAMENTS = "pbcrPlayblastOrnaments"
    OPT_VAR_OFFSCREEN = "pbcrPlayblastOffscreen"
    OPT_VAR_SHOT_MASK = "pbcrPlayblastShotMask"
    OPT_VAR_FIT_SHOT_MASK = "pbcrPlayblastFitShotMask"
    OPT_VAR_VIEWER = "pbcrPlayblastViewer"

    OPT_VAR_LOG_TO_SCRIPT_EDITOR = "pbcrPlayblastLogToSE"

    # Name generator option vars
    OPT_VAR_ASSIGNMENT_NUMBER = "pbcrPlayblastAssignmentNumber"
    OPT_VAR_LAST_NAME = "pbcrPlayblastLastName"
    OPT_VAR_FIRST_NAME = "pbcrPlayblastFirstName"
    OPT_VAR_VERSION_TYPE = "pbcrPlayblastVersionType"
    OPT_VAR_VERSION_NUMBER = "pbcrPlayblastVersionNumber"

    CONTAINER_PRESETS = [
        "mov",
        "mp4",
        "Image",
    ]

    collapsed_state_changed = QtCore.Signal()


    def __init__(self, parent=None):
        super(PBCPlayblastWidget, self).__init__(parent)

        # Load the Playblast Creator plug-in so the shot-mask node type
        # is registered before any create_mask / ls(type=...) calls.
        PBCPlayblastUtils.load_plugin()

        self._playblast = PBCPlayblast()

        self._settings_dialog = None
        self._encoder_settings_dialog = None
        self._visibility_dialog = None

        # Last shot-mask line edit the user focused - used so the Tokens
        # "Insert Item" button knows which of the six fields to insert into.
        self._last_focused_sm_le = None

        self.create_widgets()
        self.create_layouts()
        self.create_connections()

        self.load_settings()

    def create_widgets(self):
        scale_value = PBCPlayblastUtils.dpi_real_scale_value()

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
            PBCCollapsibleGrpWidget {
                border: 1px solid #555555;
                border-radius: 3px;
                margin-top: 2px;
            }
            QLabel {
                color: #E6E6E6;
            }
        """)

        self.output_dir_path_le = PBCLineEdit(PBCLineEdit.TYPE_PLAYBLAST_OUTPUT_PATH)
        self.output_dir_path_le.setPlaceholderText("{project}/movies")

        self.output_dir_path_select_btn = QtWidgets.QPushButton("...")
        self.output_dir_path_select_btn.setFixedSize(icon_button_width, icon_button_height)
        self.output_dir_path_select_btn.setToolTip("Select Output Directory")

        self.output_dir_path_show_folder_btn = QtWidgets.QPushButton(QtGui.QIcon(":fileOpen.png"), "")
        self.output_dir_path_show_folder_btn.setFixedSize(icon_button_width, icon_button_height)
        self.output_dir_path_show_folder_btn.setToolTip("Show in Folder")

        self.output_filename_le = PBCLineEdit(PBCLineEdit.TYPE_PLAYBLAST_OUTPUT_FILENAME)
        self.output_filename_le.setPlaceholderText("{scene}_{timestamp}")
        self.output_filename_le.setMaximumWidth(int(200 * scale_value))
        self.force_overwrite_cb = QtWidgets.QCheckBox("Force overwrite")

        # Name Generator widgets
        self.namegen_assignment_cb = QtWidgets.QCheckBox()
        self.namegen_assignment_cb.setChecked(True)
        self.assignmentSpinBox = QtWidgets.QSpinBox()
        self.assignmentSpinBox.setRange(1, 99)
        self.assignmentSpinBox.setValue(1)
        self.assignmentSpinBox.setFixedWidth(50)

        self.namegen_lastname_cb = QtWidgets.QCheckBox()
        self.namegen_lastname_cb.setChecked(True)
        self.lastnameLineEdit = QtWidgets.QLineEdit()
        self.lastnameLineEdit.setPlaceholderText("Last Name")

        self.namegen_firstname_cb = QtWidgets.QCheckBox()
        self.namegen_firstname_cb.setChecked(True)
        self.firstnameLineEdit = QtWidgets.QLineEdit()
        self.firstnameLineEdit.setPlaceholderText("First Name")

        self.namegen_versiontype_cb = QtWidgets.QCheckBox()
        self.namegen_versiontype_cb.setChecked(True)
        self.versionTypeCombo = QtWidgets.QComboBox()
        self.versionTypeCombo.addItems(["wip", "final"])

        self.namegen_versionnumber_cb = QtWidgets.QCheckBox()
        self.namegen_versionnumber_cb.setChecked(True)
        self.versionNumberSpinBox = QtWidgets.QSpinBox()
        self.versionNumberSpinBox.setRange(1, 99)
        self.versionNumberSpinBox.setValue(1)
        self.versionNumberSpinBox.setFixedWidth(50)

        self.filenamePreviewLabel = QtWidgets.QLabel("A1_LastName_FirstName_wip_01.mov")
        self.filenamePreviewLabel.setStyleSheet("color: #FFC107; font-weight: bold;")

        self.generateFilenameButton = QtWidgets.QPushButton("Generate Filename")
        self.resetNameGeneratorButton = QtWidgets.QPushButton("Reset")

        # End of Name Generator widgets

        # --- Playblast quality (Maya-style) ---------------------------
        # Scale (percent of render size): 10..100, default 100
        self.scale_percent_sb = QtWidgets.QSpinBox()
        self.scale_percent_sb.setRange(10, 100)
        self.scale_percent_sb.setValue(100)
        self.scale_percent_sb.setSuffix(" %")
        self.scale_percent_sb.setMinimumWidth(spin_box_min_width)

        # Image quality slider + mirrored spinbox (Maya's "Quality")
        self.image_quality_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.image_quality_slider.setRange(0, 100)
        self.image_quality_slider.setValue(100)
        self.image_quality_slider.setTickPosition(QtWidgets.QSlider.TicksBelow)
        self.image_quality_slider.setTickInterval(25)

        self.image_quality_sb = QtWidgets.QSpinBox()
        self.image_quality_sb.setRange(0, 100)
        self.image_quality_sb.setValue(100)
        self.image_quality_sb.setMinimumWidth(spin_box_min_width)

        # Frame padding (digits used in sequence file numbers)
        self.frame_padding_sb = QtWidgets.QSpinBox()
        self.frame_padding_sb.setRange(1, 8)
        self.frame_padding_sb.setValue(PBCPlayblast.DEFAULT_PADDING)
        self.frame_padding_sb.setMinimumWidth(spin_box_min_width)

        # Display size mode - mirrors Maya's "Display Size" popup
        self.display_size_cmb = QtWidgets.QComboBox()
        self.display_size_cmb.setMinimumWidth(combo_box_min_width)
        self.display_size_cmb.addItems([
            "From Window",
            "From Render Settings",
            "Custom",
        ])
        self.display_size_cmb.setCurrentText("Custom")

        self.resolution_select_cmb = QtWidgets.QComboBox()
        self.resolution_select_cmb.setMinimumWidth(combo_box_min_width)
        self.resolution_select_cmb.addItems(self._playblast.resolution_preset_names)
        self.resolution_select_cmb.addItem("Custom")
        self.resolution_select_cmb.setCurrentText(PBCPlayblast.DEFAULT_RESOLUTION)

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
        self.frame_range_cmb.addItems(PBCPlayblast.FRAME_RANGE_PRESETS)
        self.frame_range_cmb.addItem("Custom")
        self.frame_range_cmb.setCurrentText(PBCPlayblast.DEFAULT_FRAME_RANGE)

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
        self.encoding_container_cmb.addItems(PBCPlayblastWidget.CONTAINER_PRESETS)
        self.encoding_container_cmb.setCurrentText(PBCPlayblast.DEFAULT_CONTAINER)

        self.encoding_video_codec_cmb = QtWidgets.QComboBox()
        self.encoding_video_codec_cmb.setMinimumWidth(combo_box_min_width)
        self.encoding_video_codec_settings_btn = QtWidgets.QPushButton("Settings...")
        self.encoding_video_codec_settings_btn.setFixedHeight(button_height)

        self.visibility_cmb = QtWidgets.QComboBox()
        self.visibility_cmb.setMinimumWidth(combo_box_min_width)
        self.visibility_cmb.addItems(self._playblast.viewport_visibility_preset_names)
        self.visibility_cmb.addItem("Custom")
        self.visibility_cmb.setCurrentText(PBCPlayblast.DEFAULT_VISIBILITY)

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

        self.nurbs_curves_cb = QtWidgets.QCheckBox("NURBS Curves")
        self.nurbs_curves_cb.setChecked(True)

        self.nurbs_surfaces_cb = QtWidgets.QCheckBox("NURBS Surfaces")
        self.nurbs_surfaces_cb.setChecked(True)

        # --- Audio -----------------------------------------------------
        self.sound_enable_cb = QtWidgets.QCheckBox("Include Sound")
        self.sound_enable_cb.setChecked(True)

        self.sound_refresh_btn = QtWidgets.QPushButton("Refresh")
        self.sound_refresh_btn.setMaximumWidth(int(80 * scale_value))
        self.sound_refresh_btn.setFixedHeight(button_height)

        self.sound_status_label = QtWidgets.QLabel("")
        self.sound_status_label.setWordWrap(True)
        self.sound_status_label.setStyleSheet(
            "color: #9A9A9A; font-size: 11px; padding: 2px 2px;"
        )

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

        self.preview_btn = QtWidgets.QPushButton("Preview")
        self.preview_btn.setMinimumHeight(int(30 * scale_value))
        self.preview_btn.setStyleSheet("""
            background-color: #3D7AAB;
            font-weight: bold;
        """)


    def refresh_cameras(self):
        current = self.camera_select_cmb.currentText() if self.camera_select_cmb.count() else ""

        self.camera_select_cmb.blockSignals(True)
        self.camera_select_cmb.clear()
        self.camera_select_cmb.addItem("Active")

        include_defaults = not self.camera_select_hide_defaults_cb.isChecked()
        cameras = PBCPlayblastUtils.cameras_in_scene(include_defaults=include_defaults)
        self.camera_select_cmb.addItems(cameras)

        if current and self.camera_select_cmb.findText(current) >= 0:
            self.camera_select_cmb.setCurrentText(current)
        else:
            self.camera_select_cmb.setCurrentIndex(0)

        self.camera_select_cmb.blockSignals(False)

    def refresh_encoding_codecs(self):
        """Populate the codec combo with friendly labels + internal ids.

        Each combo item stores its internal encoder id ("h264", "mpeg4",
        "png", etc.) as userData so on_execute/on_preview can look it up
        via currentData(). Unavailable ffmpeg encoders are shown but
        disabled so students can see what would be possible once ffmpeg
        is configured.
        """
        container = self.encoding_container_cmb.currentText()
        current_codec = (
            self.encoding_video_codec_cmb.currentData()
            if self.encoding_video_codec_cmb.count() else ""
        )

        self.encoding_video_codec_cmb.blockSignals(True)
        self.encoding_video_codec_cmb.clear()

        codecs = PBCPlayblast.VIDEO_ENCODER_LOOKUP.get(container, [])
        ffmpeg_encoders = PBCPlayblastUtils.detect_available_video_encoders()
        image_compressions = PBCPlayblastUtils.detect_available_image_compressions()

        first_enabled_index = -1
        for codec_id in codecs:
            label = PBCPlayblast.ENCODER_DISPLAY_LABEL.get(codec_id, codec_id)
            available = True
            reason = ""

            if container in ("mov", "mp4"):
                # Needs ffmpeg.
                needed = PBCPlayblast.ENCODER_TO_FFMPEG.get(codec_id, ())
                if not ffmpeg_encoders:
                    available = False
                    reason = "ffmpeg not configured (Settings tab)"
                elif not any(name in ffmpeg_encoders for name in needed):
                    available = False
                    reason = "ffmpeg build does not ship this encoder"
            elif container == "Image":
                if codec_id not in image_compressions:
                    available = False
                    reason = "Maya cannot write this image format"

            display = label if available else "{0} - unavailable".format(label)
            self.encoding_video_codec_cmb.addItem(display, codec_id)
            idx = self.encoding_video_codec_cmb.count() - 1

            if not available:
                model = self.encoding_video_codec_cmb.model()
                item = model.item(idx) if hasattr(model, "item") else None
                if item is not None:
                    item.setFlags(item.flags() & ~QtCore.Qt.ItemIsEnabled)
                self.encoding_video_codec_cmb.setItemData(
                    idx, reason, QtCore.Qt.ToolTipRole
                )
            elif first_enabled_index == -1:
                first_enabled_index = idx

        # Restore previous selection if still available; otherwise pick
        # the first enabled item so the user doesn't start with a
        # disabled codec.
        if current_codec:
            match = self.encoding_video_codec_cmb.findData(current_codec)
            if match >= 0:
                self.encoding_video_codec_cmb.setCurrentIndex(match)
            elif first_enabled_index >= 0:
                self.encoding_video_codec_cmb.setCurrentIndex(first_enabled_index)
        elif first_enabled_index >= 0:
            self.encoding_video_codec_cmb.setCurrentIndex(first_enabled_index)

        self.encoding_video_codec_cmb.blockSignals(False)

        # Drive the companion status label on the Encoding tab.
        self._update_encoding_status_label(ffmpeg_encoders)

    def _update_encoding_status_label(self, ffmpeg_encoders=None):
        """Show a short summary of detected encoders on the Encoding tab."""
        if not hasattr(self, "encoding_status_label"):
            return

        if ffmpeg_encoders is None:
            ffmpeg_encoders = PBCPlayblastUtils.detect_available_video_encoders()

        pretty_map = {
            "libx264": "H.264 (libx264)",
            "h264_nvenc": "H.264 (NVENC)",
            "h264_videotoolbox": "H.264 (VideoToolbox)",
            "mpeg4": "MPEG-4",
            "prores": "ProRes",
            "prores_ks": "ProRes",
        }
        names = []
        seen = set()
        for enc in PBCPlayblastUtils.FFMPEG_TARGET_ENCODERS:
            if enc in ffmpeg_encoders:
                label = pretty_map.get(enc, enc)
                if label not in seen:
                    names.append(label)
                    seen.add(label)

        # Maya-native image sequences are always available.
        image_names = [
            PBCPlayblast.ENCODER_DISPLAY_LABEL[c]
            for c in PBCPlayblastUtils.detect_available_image_compressions()
        ]

        if ffmpeg_encoders:
            text = (
                "Detected video encoders: {0}.  Image sequences: {1}."
            ).format(
                ", ".join(names) if names else "none",
                ", ".join(image_names) if image_names else "none",
            )
            self.encoding_status_label.setStyleSheet(
                "color: #7FC97F; font-size: 11px; padding: 4px 2px;"
            )
        else:
            text = (
                "FFmpeg not configured - only image sequences ({0}) are "
                "available. Set the FFmpeg path on the Settings tab to "
                "unlock H.264 and MPEG-4 export."
            ).format(", ".join(image_names) if image_names else "png/jpg/tif")
            self.encoding_status_label.setStyleSheet(
                "color: #E6A23C; font-size: 11px; padding: 4px 2px;"
            )

        self.encoding_status_label.setText(text)
        self.encoding_status_label.setWordWrap(True)

    def refresh_sound_status(self):
        """Preview what audio (if any) will end up in the final playblast.

        Reads Maya's timeline control for the current sound node + Trax
        state, then sets a coloured status line beneath the Include
        Sound checkbox so students know ahead of time whether their
        export will be silent.
        """
        if not hasattr(self, "sound_status_label"):
            return

        sound_node = None
        use_trax = False
        try:
            sound_node = self._playblast.get_sound_node()
            use_trax = self._playblast.display_sound() and not sound_node
        except Exception:
            pass

        container = self.encoding_container_cmb.currentText()
        image_container = (container == "Image")

        if image_container:
            text = "Image sequences cannot carry audio - sound will be skipped."
            color = "#E6A23C"
        elif not self.sound_enable_cb.isChecked():
            text = "Sound is disabled - playblast will have no audio."
            color = "#9A9A9A"
        elif sound_node:
            file_name = ""
            try:
                file_path = cmds.getAttr("{0}.filename".format(sound_node)) or ""
                file_name = os.path.basename(file_path)
            except Exception:
                pass
            if file_name:
                text = "Will embed timeline sound: '{0}' ({1}).".format(sound_node, file_name)
            else:
                text = "Will embed timeline sound: '{0}'.".format(sound_node)
            color = "#7FC97F"
        elif use_trax:
            text = "No sound node on the timeline - Trax sounds will be used."
            color = "#7FC97F"
        else:
            text = (
                "No sound node on the timeline. Drag an audio file onto "
                "the timeline (right-click -> Audio) to add one."
            )
            color = "#9A9A9A"

        self.sound_status_label.setText(text)
        self.sound_status_label.setStyleSheet(
            "color: {0}; font-size: 11px; padding: 2px 2px;".format(color)
        )

    def _active_camera_override(self):
        camera = self.camera_select_cmb.currentText()
        if not camera or camera == "Active":
            return ""
        return camera

    def _selected_resolution(self):
        mode = self.display_size_cmb.currentText() if hasattr(self, "display_size_cmb") else "Custom"

        if mode == "From Window":
            # Use the active viewport panel's pixel size.
            try:
                panel = cmds.getPanel(withFocus=True) or ""
                if panel and cmds.getPanel(typeOf=panel) == "modelPanel":
                    w = cmds.control(panel, q=True, width=True)
                    h = cmds.control(panel, q=True, height=True)
                    if w and h:
                        return int(w), int(h)
            except Exception:
                pass

        if mode == "From Render Settings":
            try:
                w = int(cmds.getAttr("defaultResolution.width"))
                h = int(cmds.getAttr("defaultResolution.height"))
                if w and h:
                    return w, h
            except Exception:
                pass

        if self.resolution_select_cmb.currentText() == "Custom":
            return self.resolution_width_sb.value(), self.resolution_height_sb.value()

        try:
            width, height = self._playblast.preset_to_resolution(self.resolution_select_cmb.currentText())
            return int(width), int(height)
        except Exception:
            return self.resolution_width_sb.value(), self.resolution_height_sb.value()

    def _on_display_size_changed(self):
        """Enable/disable manual resolution inputs based on display-size mode."""
        mode = self.display_size_cmb.currentText()
        is_custom = (mode == "Custom")
        # Only custom mode allows hand-edited width/height and preset combo.
        self.resolution_select_cmb.setEnabled(is_custom)
        self.resolution_width_sb.setEnabled(is_custom)
        self.resolution_height_sb.setEnabled(is_custom)
        # Reflect the new resolved size in the width/height boxes for visibility.
        try:
            w, h = self._selected_resolution()
            if not is_custom:
                self.resolution_width_sb.setValue(int(w))
                self.resolution_height_sb.setValue(int(h))
        except Exception:
            pass

    def _selected_frame_range(self):
        preset = self.frame_range_cmb.currentText()

        if preset == "Custom":
            return self.frame_range_start_sb.value(), self.frame_range_end_sb.value()

        if preset == "Animation":
            return int(cmds.playbackOptions(q=True, animationStartTime=True)), int(cmds.playbackOptions(q=True, animationEndTime=True))

        if preset == "Playback":
            return int(cmds.playbackOptions(q=True, minTime=True)), int(cmds.playbackOptions(q=True, maxTime=True))

        if preset == "Render":
            return int(cmds.getAttr("defaultRenderGlobals.startFrame")), int(cmds.getAttr("defaultRenderGlobals.endFrame"))

        if preset == "Camera":
            return int(cmds.playbackOptions(q=True, minTime=True)), int(cmds.playbackOptions(q=True, maxTime=True))

        return self.frame_range_start_sb.value(), self.frame_range_end_sb.value()

    def update_filename_preview(self):
        parts = []
        if self.namegen_assignment_cb.isChecked():
            parts.append("A{0}".format(self.assignmentSpinBox.value()))
        if self.namegen_lastname_cb.isChecked():
            parts.append((self.lastnameLineEdit.text() or "LastName").strip())
        if self.namegen_firstname_cb.isChecked():
            parts.append((self.firstnameLineEdit.text() or "FirstName").strip())
        if self.namegen_versiontype_cb.isChecked():
            parts.append(self.versionTypeCombo.currentText())
        if self.namegen_versionnumber_cb.isChecked():
            parts.append("{0:02d}".format(self.versionNumberSpinBox.value()))

        filename = "_".join(p for p in parts if p) or "playblast"

        container = self.encoding_container_cmb.currentText()
        if container == "Image":
            # For image sequences the extension is the codec, not the container.
            extension = (self.encoding_video_codec_cmb.currentData() or "png").lower()
        else:
            extension = container.lower()
        self.filenamePreviewLabel.setText(filename + "." + extension)

    def apply_generated_filename(self):
        self.update_filename_preview()
        self.output_filename_le.setText(self.filenamePreviewLabel.text())

    def reset_name_generator(self):
        self.assignmentSpinBox.setValue(1)
        self.lastnameLineEdit.clear()
        self.firstnameLineEdit.clear()
        self.versionTypeCombo.setCurrentIndex(0)
        self.versionNumberSpinBox.setValue(1)
        for cb in (
            self.namegen_assignment_cb,
            self.namegen_lastname_cb,
            self.namegen_firstname_cb,
            self.namegen_versiontype_cb,
            self.namegen_versionnumber_cb,
        ):
            cb.setChecked(True)
        self.update_filename_preview()

    def select_output_dir(self):
        start_dir = self.output_dir_path_le.text() or cmds.workspace(q=True, rootDirectory=True)
        path = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Output Directory", start_dir)
        if path:
            self.output_dir_path_le.setText(path)

    def open_output_dir(self):
        output_dir = self.output_dir_path_le.text()
        if output_dir and os.path.isdir(output_dir):
            QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(output_dir))

    def clear_output_log(self):
        self.output_edit.clear()

    def on_log_output(self, message):
        self.output_edit.appendPlainText(message)

    def default_temp_output_dir(self):
        root = cmds.workspace(q=True, rootDirectory=True)
        if not root:
            root = cmds.internalVar(userWorkspaceDir=True)
        return os.path.normpath(os.path.join(root, "movies"))

    def browse_ffmpeg_path(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select ffmpeg executable")
        if path:
            self.tool_ffmpeg_path_le.setText(path)

    def browse_temp_output_dir(self):
        start_dir = self.tool_temp_dir_le.text().strip() or self.default_temp_output_dir()
        directory = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Temp Output Directory", start_dir)
        if directory:
            self.tool_temp_dir_le.setText(directory)

    def use_namegen_for_shotmask(self):
        generated = self.filenamePreviewLabel.text().strip()
        if generated:
            self.sm_top_center_le.setText(generated)

    def _populate_shot_mask_tokens(self, combo):
        """Fill the shot-mask Tokens combo with two grouped sections:
        general tokens (resolved by the mask node) and Animation Pass
        labels (inserted as plain text).
        """
        # QtGui is imported at the top for whichever Qt binding is in use.
        model = QtGui.QStandardItemModel(combo)

        def _header(title):
            item = QtGui.QStandardItem("\u2500\u2500 {0} \u2500\u2500".format(title))
            item.setFlags(QtCore.Qt.NoItemFlags)  # non-selectable separator
            font = item.font()
            font.setBold(True)
            item.setFont(font)
            item.setData(None, QtCore.Qt.UserRole)
            model.appendRow(item)

        def _entry(label, token):
            item = QtGui.QStandardItem(label)
            item.setData(token, QtCore.Qt.UserRole)
            model.appendRow(item)

        _header("General")
        for label, token in (
            ("Frame Counter", "{counter}"),
            ("FPS", "{fps}"),
            ("Camera", "{camera}"),
            ("Shot #", "{shot}"),
            ("Scene", "{scene}"),
            ("Date", "{date}"),
            ("Username", "{username}"),
        ):
            _entry(label, token)

        _header("Animation Pass")
        for label in (
            "Planning",
            "Blocking",
            "Blocking Plus",
            "Spline Pass",
            "Facial/Lip-Sync",
            "Polish",
        ):
            # Animation passes are literal text labels, not templates.
            _entry(label, label)

        combo.setModel(model)

        # Select the first real token (skip the leading header row).
        for row in range(model.rowCount()):
            if model.item(row).flags() & QtCore.Qt.ItemIsSelectable:
                combo.setCurrentIndex(row)
                break

    def _selected_token(self):
        """Return the token string for the currently-selected combo row,
        regardless of whether the row is a header (no UserRole data).
        """
        idx = self.sm_common_items_cmb.currentIndex()
        model = self.sm_common_items_cmb.model()
        if idx < 0 or not model:
            return ""
        item = model.item(idx) if hasattr(model, "item") else None
        if item is None:
            # Fallback for plain QComboBox models.
            return self.sm_common_items_cmb.currentData() or ""
        return item.data(QtCore.Qt.UserRole) or ""

    def insert_shotmask_token(self):
        token = self._selected_token()
        if not token:
            return
        target = self._last_focused_sm_le
        # Fallback to the currently-focused widget if the user happens to
        # be typing in a shot-mask field when they click Insert Item.
        focus = QtWidgets.QApplication.focusWidget()
        if isinstance(focus, QtWidgets.QLineEdit) and focus in self._shot_mask_line_edits():
            target = focus
        if target is None:
            target = self.sm_top_center_le
        target.insert(token)
        target.setFocus(QtCore.Qt.OtherFocusReason)

    def _shot_mask_line_edits(self):
        return (
            self.sm_top_left_le,
            self.sm_top_center_le,
            self.sm_top_right_le,
            self.sm_bottom_left_le,
            self.sm_bottom_center_le,
            self.sm_bottom_right_le,
        )

    def _on_shot_mask_field_focused(self, line_edit):
        self._last_focused_sm_le = line_edit

    def eventFilter(self, obj, event):
        # Remember which shot-mask field is currently focused so that
        # Tokens -> Insert Item always has a sensible target, even after
        # focus shifts to the combo or the Insert button.
        if event.type() == QtCore.QEvent.FocusIn:
            try:
                if obj in self._shot_mask_line_edits():
                    self._last_focused_sm_le = obj
            except Exception:
                pass
        return super(PBCPlayblastWidget, self).eventFilter(obj, event)

    def apply_quick_viewport_toggles(self):
        visibility_data = list(self._playblast.get_visibility())
        name_to_index = {
            item[0]: i
            for i, item in enumerate(PBCPlayblast.VIEWPORT_VISIBILITY_LOOKUP)
        }

        if "NURBS Curves" in name_to_index:
            visibility_data[name_to_index["NURBS Curves"]] = self.nurbs_curves_cb.isChecked()
        if "NURBS Surfaces" in name_to_index:
            visibility_data[name_to_index["NURBS Surfaces"]] = self.nurbs_surfaces_cb.isChecked()

        self._playblast.set_visibility(visibility_data)

    def on_execute(self):
        try:
            output_dir = self.output_dir_path_le.text().strip()
            if not output_dir:
                output_dir = cmds.workspace(q=True, rootDirectory=True)
            os.makedirs(output_dir, exist_ok=True)

            filename = self.output_filename_le.text().strip()
            if not filename:
                filename = self.filenamePreviewLabel.text().strip()

            width, height = self._selected_resolution()
            self._playblast.set_resolution((width, height))

            start_frame, end_frame = self._selected_frame_range()
            self._playblast.set_frame_range((start_frame, end_frame))

            container = self.encoding_container_cmb.currentText()
            codec = self.encoding_video_codec_cmb.currentData() or self.encoding_video_codec_cmb.currentText()
            self._playblast.set_encoding(container, codec)

            self._playblast.set_camera(self._active_camera_override() or None)
            self.apply_quick_viewport_toggles()

            # Pin the shot mask to the camera we're about to blast.
            self._sync_shot_mask_to_camera(self._resolve_playblast_camera())

            self._playblast.execute(
                output_dir=output_dir,
                filename=filename,
                padding=self.frame_padding_sb.value(),
                overscan=self.overscan_cb.isChecked(),
                show_ornaments=self.ornaments_cb.isChecked(),
                show_in_viewer=self.viewer_cb.isChecked(),
                offscreen=self.offscreen_cb.isChecked(),
                overwrite=self.force_overwrite_cb.isChecked(),
                camera_override=self._active_camera_override(),
                enable_camera_frame_range=(self.frame_range_cmb.currentText() == "Camera"),
                include_sound=self.sound_enable_cb.isChecked(),
                scale_percent=self.scale_percent_sb.value(),
                image_quality_override=self.image_quality_sb.value(),
            )
        except Exception:
            traceback.print_exc()
            self.on_log_output("[Error] Playblast failed. See Script Editor for details.")

    def on_preview(self):
        try:
            preview_dir = PBCPlayblastUtils.get_temp_output_dir_path() or self.default_temp_output_dir()
            os.makedirs(preview_dir, exist_ok=True)

            preview_name = "preview_{0}".format(int(time.time()))
            width, height = self._selected_resolution()
            self._playblast.set_resolution((width, height))

            start_frame, end_frame = self._selected_frame_range()
            self._playblast.set_frame_range((start_frame, end_frame))

            self._playblast.set_camera(self._active_camera_override() or None)
            self.apply_quick_viewport_toggles()
            container = self.encoding_container_cmb.currentText()
            codec = self.encoding_video_codec_cmb.currentData() or self.encoding_video_codec_cmb.currentText()
            self._playblast.set_encoding(container, codec)

            # Pin the shot mask to the camera we're about to blast.
            self._sync_shot_mask_to_camera(self._resolve_playblast_camera())

            self._playblast.execute(
                output_dir=preview_dir,
                filename=preview_name,
                padding=self.frame_padding_sb.value(),
                overscan=self.overscan_cb.isChecked(),
                show_ornaments=self.ornaments_cb.isChecked(),
                show_in_viewer=True,
                offscreen=self.offscreen_cb.isChecked(),
                overwrite=True,
                camera_override=self._active_camera_override(),
                enable_camera_frame_range=(self.frame_range_cmb.currentText() == "Camera"),
                include_sound=self.sound_enable_cb.isChecked(),
                scale_percent=self.scale_percent_sb.value(),
                image_quality_override=self.image_quality_sb.value(),
            )
            self.on_log_output("Preview playblast created in temp folder: {0}".format(preview_dir))
        except Exception:
            traceback.print_exc()
            self.on_log_output("[Error] Preview playblast failed. See Script Editor for details.")

    def _resolve_playblast_camera(self):
        """Return the camera transform name the playblast will use.

        Matches the resolution that PBCPlayblast.execute performs: the
        UI override wins, otherwise whatever camera is active in the
        focused viewport.
        """
        override = self._active_camera_override()
        if override:
            return override
        try:
            panel = cmds.getPanel(withFocus=True) or ""
            if panel and cmds.getPanel(typeOf=panel) == "modelPanel":
                cam = cmds.modelPanel(panel, q=True, camera=True)
                if cam:
                    return cam
        except Exception:
            pass
        return ""

    def _sync_shot_mask_to_camera(self, camera_name):
        """Bind the shot mask to the supplied camera and toggle its
        visibility to match the Render tab's Shot Mask checkbox.

        If the mask doesn't exist yet but the user has enabled Shot Mask,
        create it on the fly so the overlay reliably shows up in the
        selected camera's viewport and in the playblast.
        """
        try:
            if not PBCPlayblastUtils.load_plugin():
                # Plugin can't be loaded - nothing meaningful to do.
                return

            enabled = self.shot_mask_cb.isChecked()
            mask = PBCShotMask.get_mask()
            if enabled and not mask:
                mask = PBCShotMask.create_mask()
                if not mask:
                    return

            if not mask:
                # Nothing to update and user has disabled the mask.
                return

            PBCShotMask.set_camera(camera_name or "")
            PBCShotMask.set_visible(enabled)
        except Exception:
            traceback.print_exc()

    def apply_shot_mask_tab_settings(self):
        try:
            if not PBCPlayblastUtils.load_plugin():
                self.on_log_output(
                    "[Error] Shot mask plug-in could not be loaded. "
                    "Verify playblast_creator.py is on MAYA_PLUG_IN_PATH."
                )
                return

            mask = PBCShotMask.create_mask()
            if not mask:
                self.on_log_output(
                    "[Error] Unable to create PlayblastCreatorShotMask node."
                )
                return
            attrs = [
                ("topLeftText", self.sm_top_left_le.text() if self.sm_top_left_cb.isChecked() else ""),
                ("topCenterText", self.sm_top_center_le.text() if self.sm_top_center_cb.isChecked() else ""),
                ("topRightText", self.sm_top_right_le.text() if self.sm_top_right_cb.isChecked() else ""),
                ("bottomLeftText", self.sm_bottom_left_le.text() if self.sm_bottom_left_cb.isChecked() else ""),
                ("bottomCenterText", self.sm_bottom_center_le.text() if self.sm_bottom_center_cb.isChecked() else ""),
                ("bottomRightText", self.sm_bottom_right_le.text() if self.sm_bottom_right_cb.isChecked() else ""),
            ]
            for attr, value in attrs:
                cmds.setAttr("{0}.{1}".format(mask, attr), value, type="string")

            cmds.setAttr("{0}.topBorder".format(mask), self.sm_top_border_cb.isChecked())
            cmds.setAttr("{0}.bottomBorder".format(mask), self.sm_bottom_border_cb.isChecked())
            cmds.setAttr("{0}.counterPadding".format(mask), self.sm_counter_padding_sb.value())

            self.shot_mask_cb.setChecked(self.sm_enable_mask_cb.isChecked())

            # Bind the mask to whatever camera the user has selected on
            # the Render tab so the overlay actually appears on that view.
            self._sync_shot_mask_to_camera(self._resolve_playblast_camera())

            self.on_log_output("Shot mask settings applied to: {0}".format(mask))
        except Exception:
            traceback.print_exc()
            self.on_log_output("[Error] Failed to apply shot mask settings.")

    def apply_tool_tab_settings(self):
        try:
            PBCPlayblastUtils.set_ffmpeg_path(self.tool_ffmpeg_path_le.text().strip())
            temp_dir = self.tool_temp_dir_le.text().strip() or self.default_temp_output_dir()
            self.tool_temp_dir_le.setText(temp_dir)
            os.makedirs(temp_dir, exist_ok=True)
            PBCPlayblastUtils.set_temp_output_dir_path(temp_dir)
            PBCPlayblastUtils.set_temp_file_format(self.tool_temp_format_cmb.currentText())
            # Re-probe ffmpeg so the codec list reflects the new binary.
            PBCPlayblastUtils.invalidate_encoder_cache()
            self.refresh_encoding_codecs()
            self.on_log_output("Tool settings applied.")
        except Exception:
            traceback.print_exc()
            self.on_log_output("[Error] Failed to apply tool settings.")

    def create_connections(self):
        self.output_dir_path_select_btn.clicked.connect(self.select_output_dir)
        self.output_dir_path_show_folder_btn.clicked.connect(self.open_output_dir)
        self.clear_btn.clicked.connect(self.clear_output_log)

        self.camera_select_hide_defaults_cb.toggled.connect(self.refresh_cameras)
        self.encoding_container_cmb.currentIndexChanged.connect(self.refresh_encoding_codecs)
        self.encoding_container_cmb.currentIndexChanged.connect(self.update_filename_preview)
        self.encoding_container_cmb.currentIndexChanged.connect(self.refresh_sound_status)
        self.encoding_video_codec_cmb.currentIndexChanged.connect(self.update_filename_preview)

        self.sound_enable_cb.toggled.connect(self.refresh_sound_status)
        self.sound_refresh_btn.clicked.connect(self.refresh_sound_status)

        self.generateFilenameButton.clicked.connect(self.apply_generated_filename)
        self.resetNameGeneratorButton.clicked.connect(self.reset_name_generator)

        self.assignmentSpinBox.valueChanged.connect(self.update_filename_preview)
        self.lastnameLineEdit.textChanged.connect(self.update_filename_preview)
        self.firstnameLineEdit.textChanged.connect(self.update_filename_preview)
        self.versionTypeCombo.currentIndexChanged.connect(self.update_filename_preview)
        self.versionNumberSpinBox.valueChanged.connect(self.update_filename_preview)

        # Name-generator include/exclude checkboxes
        self.namegen_assignment_cb.toggled.connect(self.update_filename_preview)
        self.namegen_lastname_cb.toggled.connect(self.update_filename_preview)
        self.namegen_firstname_cb.toggled.connect(self.update_filename_preview)
        self.namegen_versiontype_cb.toggled.connect(self.update_filename_preview)
        self.namegen_versionnumber_cb.toggled.connect(self.update_filename_preview)

        # Quality widgets: keep slider and spinbox in sync, and react to
        # display-size-mode changes.
        self.image_quality_slider.valueChanged.connect(self.image_quality_sb.setValue)
        self.image_quality_sb.valueChanged.connect(self.image_quality_slider.setValue)
        self.display_size_cmb.currentIndexChanged.connect(self._on_display_size_changed)

        self.preview_btn.clicked.connect(self.on_preview)
        self.execute_btn.clicked.connect(self.on_execute)
        self.sm_apply_btn.clicked.connect(self.apply_shot_mask_tab_settings)
        self.sm_use_namegen_btn.clicked.connect(self.use_namegen_for_shotmask)
        self.sm_insert_item_btn.clicked.connect(self.insert_shotmask_token)

        # Track which shot-mask field the user focused most recently so
        # "Insert Item" targets the correct one even after the combo or
        # button steals focus.
        for le in self._shot_mask_line_edits():
            le.installEventFilter(self)

        # Show / hide the mask in the viewport the moment the user toggles
        # the checkbox, without waiting for the next playblast.
        self.shot_mask_cb.toggled.connect(
            lambda _checked: self._sync_shot_mask_to_camera(
                self._resolve_playblast_camera()
            )
        )
        # Re-bind to the new camera immediately when the user changes it.
        self.camera_select_cmb.currentIndexChanged.connect(
            lambda _idx: self._sync_shot_mask_to_camera(
                self._resolve_playblast_camera()
            )
        )
        self.tool_ffmpeg_browse_btn.clicked.connect(self.browse_ffmpeg_path)
        self.tool_temp_dir_browse_btn.clicked.connect(self.browse_temp_output_dir)
        self.tool_apply_btn.clicked.connect(self.apply_tool_tab_settings)
        self._playblast.output_logged.connect(self.on_log_output)

    def load_settings(self):
        self.refresh_cameras()
        self.refresh_encoding_codecs()
        self.update_filename_preview()
        self.refresh_sound_status()

        start_frame, end_frame = self._selected_frame_range()
        self.frame_range_start_sb.setValue(start_frame)
        self.frame_range_end_sb.setValue(end_frame)

        width, height = self._playblast.preset_to_resolution(self.resolution_select_cmb.currentText())
        self.resolution_width_sb.setValue(width)
        self.resolution_height_sb.setValue(height)

        # Sync enable-state of resolution inputs with the display-size mode.
        self._on_display_size_changed()

        self.tool_ffmpeg_path_le.setText(PBCPlayblastUtils.get_ffmpeg_path())
        temp_dir = PBCPlayblastUtils.get_temp_output_dir_path() or self.default_temp_output_dir()
        self.tool_temp_dir_le.setText(temp_dir)
        self.tool_temp_format_cmb.setCurrentText(PBCPlayblastUtils.get_temp_file_format())

    def create_layouts(self):
        """Redesigned layout.

        Structure:
            Title bar
            Tabs:  Output | Render | Encoding | Shot Mask | Settings
            Footer (always visible):
                collapsible log panel
                action bar:  [Preview]  [Create Playblast]
        """
        # Shot-mask widgets are referenced by create_connections(), so they
        # must be instantiated before the tab builders run regardless of
        # which tab they land in.
        self._build_shot_mask_widgets()
        self._build_settings_widgets()

        # --- Build each tab ------------------------------------------------
        output_tab = self._build_output_tab()
        render_tab = self._build_render_tab()
        encoding_tab = self._build_encoding_tab()
        shot_mask_tab = self._build_shot_mask_tab()
        settings_tab = self._build_settings_tab()

        # --- Tab container -------------------------------------------------
        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setTabPosition(QtWidgets.QTabWidget.North)
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #3D3D3D;
                border-radius: 4px;
                background-color: #2A2A2A;
                top: -1px;
            }
            QTabBar::tab {
                background: #2D2D30;
                color: #CCCCCC;
                padding: 7px 16px;
                border: 1px solid #3D3D3D;
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                margin-right: 2px;
                min-width: 80px;
            }
            QTabBar::tab:selected {
                background: #3D7AAB;
                color: white;
                font-weight: bold;
            }
            QTabBar::tab:hover:!selected {
                background: #3A3A3E;
            }
        """)
        self.tabs.addTab(output_tab, "Output")
        self.tabs.addTab(render_tab, "Render")
        self.tabs.addTab(encoding_tab, "Encoding")
        self.tabs.addTab(shot_mask_tab, "Shot Mask")
        self.tabs.addTab(settings_tab, "Settings")

        # --- Footer: log + action bar (always visible) ---------------------
        footer_frame = self._build_footer()

        # --- Title bar -----------------------------------------------------
        title_label = QtWidgets.QLabel("Playblast Creator")
        title_label.setStyleSheet(
            "font-size: 15px; font-weight: bold; color: #4B94CF; padding: 4px 2px;"
        )

        self.setMinimumWidth(760)

        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(10, 8, 10, 10)
        main_layout.setSpacing(6)
        main_layout.addWidget(title_label)
        main_layout.addWidget(self.tabs, stretch=1)
        main_layout.addWidget(footer_frame)

        # All widgets exist by this point — install tooltips.
        self._apply_tooltips()

    # ------------------------------------------------------------------
    # Helpers used by create_layouts()
    # ------------------------------------------------------------------
    @staticmethod
    def _section_header(text):
        label = QtWidgets.QLabel(text)
        label.setStyleSheet(
            "font-weight: bold; color: #4B94CF; font-size: 12px; padding: 4px 2px;"
        )
        return label

    @staticmethod
    def _help_caption(text):
        """Grey, wrapping help-text label displayed at the top of each tab."""
        label = QtWidgets.QLabel(text)
        label.setWordWrap(True)
        label.setStyleSheet(
            "color: #9A9A9A; font-size: 11px; padding: 2px 2px 6px 2px;"
        )
        return label

    @staticmethod
    def _card(title_text):
        """Returns (frame, body_layout) so callers can stack fields inside."""
        frame = QtWidgets.QFrame()
        frame.setStyleSheet(
            "QFrame { background-color: #323232; border-radius: 4px; }"
        )
        outer = QtWidgets.QVBoxLayout(frame)
        outer.setContentsMargins(10, 8, 10, 10)
        outer.setSpacing(6)

        if title_text:
            title = QtWidgets.QLabel(title_text)
            title.setStyleSheet(
                "font-weight: bold; color: #DDDDDD; padding-left: 1px;"
            )
            outer.addWidget(title)

        body_host = QtWidgets.QWidget()
        body_layout = QtWidgets.QVBoxLayout(body_host)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(6)
        outer.addWidget(body_host)

        return frame, body_layout

    def _wrap_in_scroll(self, inner_widget):
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        scroll.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        scroll.setWidget(inner_widget)
        return scroll

    # ------- Output tab ------------------------------------------------
    def _build_output_tab(self):
        # Output dir row
        output_path_row = QtWidgets.QHBoxLayout()
        output_path_row.setSpacing(2)
        output_path_row.addWidget(self.output_dir_path_le)
        output_path_row.addWidget(self.output_dir_path_select_btn)
        output_path_row.addWidget(self.output_dir_path_show_folder_btn)

        # Filename row
        output_file_row = QtWidgets.QHBoxLayout()
        output_file_row.setSpacing(4)
        output_file_row.addWidget(self.output_filename_le)
        output_file_row.addWidget(self.force_overwrite_cb)

        destination_card, destination_body = self._card("Destination")
        destination_form = PBCFormLayout()
        destination_form.setVerticalSpacing(8)
        destination_form.addLayoutRow(0, "Output Dir:", output_path_row)
        destination_form.addLayoutRow(1, "Filename:", output_file_row)
        destination_body.addLayout(destination_form)

        # Name generator
        name_gen_card, name_gen_body = self._card("Name Generator")
        name_gen_grid = QtWidgets.QGridLayout()
        name_gen_grid.setColumnStretch(3, 1)
        name_gen_grid.setVerticalSpacing(6)
        name_gen_grid.setHorizontalSpacing(8)
        # Column layout: [include?] [label:] [value] [value-wide]
        name_gen_grid.addWidget(self.namegen_assignment_cb, 0, 0)
        name_gen_grid.addWidget(QtWidgets.QLabel("Assignment:"), 0, 1)
        name_gen_grid.addWidget(self.assignmentSpinBox, 0, 2)
        name_gen_grid.addWidget(self.namegen_lastname_cb, 1, 0)
        name_gen_grid.addWidget(QtWidgets.QLabel("Last Name:"), 1, 1)
        name_gen_grid.addWidget(self.lastnameLineEdit, 1, 2, 1, 2)
        name_gen_grid.addWidget(self.namegen_firstname_cb, 2, 0)
        name_gen_grid.addWidget(QtWidgets.QLabel("First Name:"), 2, 1)
        name_gen_grid.addWidget(self.firstnameLineEdit, 2, 2, 1, 2)
        name_gen_grid.addWidget(self.namegen_versiontype_cb, 3, 0)
        name_gen_grid.addWidget(QtWidgets.QLabel("Type:"), 3, 1)
        name_gen_grid.addWidget(self.versionTypeCombo, 3, 2)
        name_gen_grid.addWidget(self.namegen_versionnumber_cb, 4, 0)
        name_gen_grid.addWidget(QtWidgets.QLabel("Version:"), 4, 1)
        name_gen_grid.addWidget(self.versionNumberSpinBox, 4, 2)
        name_gen_grid.addWidget(QtWidgets.QLabel("Preview:"), 5, 1)
        name_gen_grid.addWidget(self.filenamePreviewLabel, 5, 2, 1, 2)

        name_gen_btns = QtWidgets.QHBoxLayout()
        name_gen_btns.addStretch()
        name_gen_btns.addWidget(self.generateFilenameButton)
        name_gen_btns.addSpacing(6)
        name_gen_btns.addWidget(self.resetNameGeneratorButton)
        name_gen_btns.addStretch()

        name_gen_body.addLayout(name_gen_grid)
        name_gen_body.addLayout(name_gen_btns)

        # Compose tab
        tab_inner = QtWidgets.QWidget()
        tab_layout = QtWidgets.QVBoxLayout(tab_inner)
        tab_layout.setContentsMargins(10, 10, 10, 10)
        tab_layout.setSpacing(10)
        tab_layout.addWidget(self._help_caption(
            "Choose where the playblast is saved and what it is called. "
            "Tokens like {project}, {scene}, {timestamp} are expanded when "
            "the playblast is created. Use the Name Generator to build a "
            "class-style filename automatically."
        ))
        tab_layout.addWidget(destination_card)
        tab_layout.addWidget(name_gen_card)
        tab_layout.addStretch()

        return self._wrap_in_scroll(tab_inner)

    # ------- Render tab ------------------------------------------------
    def _build_render_tab(self):
        # Camera card
        camera_card, camera_body = self._card("Camera")
        camera_row = QtWidgets.QHBoxLayout()
        camera_row.setSpacing(6)
        camera_row.addWidget(self.camera_select_cmb)
        camera_row.addWidget(self.camera_select_hide_defaults_cb)
        camera_row.addStretch()
        camera_body.addLayout(camera_row)

        # Resolution card
        resolution_card, resolution_body = self._card("Resolution")
        resolution_row = QtWidgets.QHBoxLayout()
        resolution_row.setSpacing(4)
        resolution_row.addWidget(self.resolution_select_cmb)
        resolution_row.addSpacing(4)
        resolution_row.addWidget(self.resolution_width_sb)
        resolution_row.addWidget(QtWidgets.QLabel("x"))
        resolution_row.addWidget(self.resolution_height_sb)
        resolution_row.addStretch()
        resolution_body.addLayout(resolution_row)

        # Quality card - mirrors Maya's Playblast Options quality block.
        quality_card, quality_body = self._card("Quality")
        quality_form = PBCFormLayout()
        quality_form.setVerticalSpacing(8)

        display_size_row = QtWidgets.QHBoxLayout()
        display_size_row.setSpacing(4)
        display_size_row.addWidget(self.display_size_cmb)
        display_size_row.addStretch()
        quality_form.addLayoutRow(0, "Display Size:", display_size_row)

        scale_row = QtWidgets.QHBoxLayout()
        scale_row.setSpacing(4)
        scale_row.addWidget(self.scale_percent_sb)
        scale_row.addStretch()
        quality_form.addLayoutRow(1, "Scale:", scale_row)

        image_quality_row = QtWidgets.QHBoxLayout()
        image_quality_row.setSpacing(6)
        image_quality_row.addWidget(self.image_quality_slider, 1)
        image_quality_row.addWidget(self.image_quality_sb)
        quality_form.addLayoutRow(2, "Quality:", image_quality_row)

        padding_row = QtWidgets.QHBoxLayout()
        padding_row.setSpacing(4)
        padding_row.addWidget(self.frame_padding_sb)
        padding_row.addStretch()
        quality_form.addLayoutRow(3, "Frame Padding:", padding_row)

        quality_body.addLayout(quality_form)

        # Frame range card
        frame_range_card, frame_range_body = self._card("Frame Range")
        frame_range_row = QtWidgets.QHBoxLayout()
        frame_range_row.setSpacing(4)
        frame_range_row.addWidget(self.frame_range_cmb)
        frame_range_row.addSpacing(4)
        frame_range_row.addWidget(self.frame_range_start_sb)
        frame_range_row.addWidget(self.frame_range_end_sb)
        frame_range_row.addStretch()
        frame_range_body.addLayout(frame_range_row)

        # Visibility card
        visibility_card, visibility_body = self._card("Visibility")
        visibility_row = QtWidgets.QHBoxLayout()
        visibility_row.setSpacing(4)
        visibility_row.addWidget(self.visibility_cmb)
        visibility_row.addWidget(self.visibility_customize_btn)
        visibility_row.addStretch()
        visibility_body.addLayout(visibility_row)

        # Audio card
        audio_card, audio_body = self._card("Audio")
        audio_row = QtWidgets.QHBoxLayout()
        audio_row.addWidget(self.sound_enable_cb)
        audio_row.addStretch()
        audio_row.addWidget(self.sound_refresh_btn)
        audio_body.addLayout(audio_row)
        audio_body.addWidget(self.sound_status_label)

        # Flags card
        flags_card, flags_body = self._card("Options")
        flags_grid = QtWidgets.QGridLayout()
        flags_grid.setHorizontalSpacing(16)
        flags_grid.setVerticalSpacing(4)
        flags_grid.addWidget(self.ornaments_cb, 0, 0)
        flags_grid.addWidget(self.overscan_cb, 0, 1)
        flags_grid.addWidget(self.offscreen_cb, 0, 2)
        flags_grid.addWidget(self.viewer_cb, 1, 0)
        flags_grid.addWidget(self.shot_mask_cb, 1, 1)
        flags_grid.addWidget(self.fit_shot_mask_cb, 1, 2)
        flags_grid.addWidget(self.nurbs_curves_cb, 2, 0)
        flags_grid.addWidget(self.nurbs_surfaces_cb, 2, 1)
        flags_body.addLayout(flags_grid)

        tab_inner = QtWidgets.QWidget()
        tab_layout = QtWidgets.QVBoxLayout(tab_inner)
        tab_layout.setContentsMargins(10, 10, 10, 10)
        tab_layout.setSpacing(10)
        tab_layout.addWidget(self._help_caption(
            "Controls what Maya renders into the playblast: which camera, "
            "image size, frame range, which scene elements are visible, "
            "and whether timeline audio is included. These settings match "
            "Maya's standard playblast options."
        ))
        tab_layout.addWidget(camera_card)
        tab_layout.addWidget(resolution_card)
        tab_layout.addWidget(quality_card)
        tab_layout.addWidget(frame_range_card)
        tab_layout.addWidget(visibility_card)
        tab_layout.addWidget(audio_card)
        tab_layout.addWidget(flags_card)
        tab_layout.addStretch()

        return self._wrap_in_scroll(tab_inner)

    # ------- Encoding tab ----------------------------------------------
    def _build_encoding_tab(self):
        encoding_card, encoding_body = self._card("Format & Codec")
        encoding_form = PBCFormLayout()
        encoding_form.setVerticalSpacing(8)
        encoding_form.addWidgetRow(0, "Container:", self.encoding_container_cmb)
        encoding_form.addWidgetRow(1, "Codec:", self.encoding_video_codec_cmb)

        settings_row = QtWidgets.QHBoxLayout()
        settings_row.addStretch()
        settings_row.addWidget(self.encoding_video_codec_settings_btn)
        encoding_body.addLayout(encoding_form)
        encoding_body.addLayout(settings_row)

        # Live status describing what the tool detected on this machine.
        self.encoding_status_label = QtWidgets.QLabel("Detecting encoders...")
        self.encoding_status_label.setWordWrap(True)
        self.encoding_status_label.setStyleSheet(
            "color: #9A9A9A; font-size: 11px; padding: 4px 2px;"
        )
        encoding_body.addWidget(self.encoding_status_label)

        tab_inner = QtWidgets.QWidget()
        tab_layout = QtWidgets.QVBoxLayout(tab_inner)
        tab_layout.setContentsMargins(10, 10, 10, 10)
        tab_layout.setSpacing(10)
        tab_layout.addWidget(self._help_caption(
            "Pick a container format (the output file type) and the codec "
            "used inside it. Common choices: mp4 + H.264 for submissions, "
            "mov + ProRes for editorial, Image for a PNG/JPG sequence. "
            "Use Settings... to tune quality and preset. H.264, MPEG-4, "
            "and PNG sequences are always offered; MPEG-4 and ProRes are "
            "enabled automatically when your FFmpeg build supports them."
        ))
        tab_layout.addWidget(encoding_card)
        tab_layout.addStretch()

        return self._wrap_in_scroll(tab_inner)

    # ------- Shot Mask tab --------------------------------------------
    def _build_shot_mask_widgets(self):
        self.sm_enable_mask_cb = QtWidgets.QCheckBox("Enable Shot Mask")
        self.sm_enable_mask_cb.setChecked(self.shot_mask_cb.isChecked())
        self.sm_top_border_cb = QtWidgets.QCheckBox("Top Border")
        self.sm_top_border_cb.setChecked(True)
        self.sm_bottom_border_cb = QtWidgets.QCheckBox("Bottom Border")
        self.sm_bottom_border_cb.setChecked(True)

        self.sm_top_left_cb = QtWidgets.QCheckBox("Show")
        self.sm_top_center_cb = QtWidgets.QCheckBox("Show")
        self.sm_top_right_cb = QtWidgets.QCheckBox("Show")
        self.sm_bottom_left_cb = QtWidgets.QCheckBox("Show")
        self.sm_bottom_center_cb = QtWidgets.QCheckBox("Show")
        self.sm_bottom_right_cb = QtWidgets.QCheckBox("Show")
        for cb in (
            self.sm_top_left_cb,
            self.sm_top_center_cb,
            self.sm_top_right_cb,
            self.sm_bottom_left_cb,
            self.sm_bottom_center_cb,
            self.sm_bottom_right_cb,
        ):
            cb.setChecked(True)

        self.sm_top_left_le = QtWidgets.QLineEdit()
        self.sm_top_center_le = QtWidgets.QLineEdit()
        self.sm_top_right_le = QtWidgets.QLineEdit()
        self.sm_bottom_left_le = QtWidgets.QLineEdit()
        self.sm_bottom_center_le = QtWidgets.QLineEdit()
        self.sm_bottom_right_le = QtWidgets.QLineEdit()

        # Default target for Token inserts until the user clicks into a
        # specific slot; Top Center matches Maya's default mask layout.
        self._last_focused_sm_le = self.sm_top_center_le

        self.sm_common_items_cmb = QtWidgets.QComboBox()
        # Build a grouped token model so Animation Pass sits visually under
        # its own header, and the "General" section keeps the existing items.
        self._populate_shot_mask_tokens(self.sm_common_items_cmb)
        self.sm_insert_item_btn = QtWidgets.QPushButton("Insert Item")

        self.sm_counter_padding_sb = QtWidgets.QSpinBox()
        self.sm_counter_padding_sb.setRange(1, 8)
        self.sm_counter_padding_sb.setValue(4)

        self.sm_use_namegen_btn = QtWidgets.QPushButton("Use Name Generator Preview")
        self.sm_apply_btn = QtWidgets.QPushButton("Apply Shot Mask Settings")

    def _build_shot_mask_tab(self):
        enable_card, enable_body = self._card("Mask")
        flag_row = QtWidgets.QHBoxLayout()
        flag_row.addWidget(self.sm_enable_mask_cb)
        flag_row.addSpacing(16)
        flag_row.addWidget(self.sm_top_border_cb)
        flag_row.addWidget(self.sm_bottom_border_cb)
        flag_row.addStretch()
        enable_body.addLayout(flag_row)

        labels_card, labels_body = self._card("Labels")
        labels_grid = QtWidgets.QGridLayout()
        labels_grid.setHorizontalSpacing(8)
        labels_grid.setVerticalSpacing(6)

        row = 0
        for name, line_edit, check_box in (
            ("Top Left", self.sm_top_left_le, self.sm_top_left_cb),
            ("Top Center", self.sm_top_center_le, self.sm_top_center_cb),
            ("Top Right", self.sm_top_right_le, self.sm_top_right_cb),
            ("Bottom Left", self.sm_bottom_left_le, self.sm_bottom_left_cb),
            ("Bottom Center", self.sm_bottom_center_le, self.sm_bottom_center_cb),
            ("Bottom Right", self.sm_bottom_right_le, self.sm_bottom_right_cb),
        ):
            labels_grid.addWidget(QtWidgets.QLabel(name + ":"), row, 0, QtCore.Qt.AlignRight)
            labels_grid.addWidget(line_edit, row, 1)
            labels_grid.addWidget(check_box, row, 2)
            row += 1
        labels_grid.setColumnStretch(1, 1)
        labels_body.addLayout(labels_grid)

        tokens_card, tokens_body = self._card("Tokens")
        token_row = QtWidgets.QHBoxLayout()
        token_row.addWidget(self.sm_common_items_cmb, stretch=1)
        token_row.addWidget(self.sm_insert_item_btn)
        tokens_body.addLayout(token_row)

        counter_row = QtWidgets.QHBoxLayout()
        counter_row.addWidget(QtWidgets.QLabel("Frame Counter Padding:"))
        counter_row.addWidget(self.sm_counter_padding_sb)
        counter_row.addStretch()
        tokens_body.addLayout(counter_row)

        apply_row = QtWidgets.QHBoxLayout()
        apply_row.addStretch()
        apply_row.addWidget(self.sm_use_namegen_btn)
        apply_row.addSpacing(6)
        apply_row.addWidget(self.sm_apply_btn)

        tab_inner = QtWidgets.QWidget()
        tab_layout = QtWidgets.QVBoxLayout(tab_inner)
        tab_layout.setContentsMargins(10, 10, 10, 10)
        tab_layout.setSpacing(10)
        tab_layout.addWidget(self._help_caption(
            "Overlay text and letterbox bars burned into the playblast. "
            "Each slot accepts plain text or tokens (e.g. {scene}, "
            "{camera}, {counter}). Tick Show to display a slot; clear it "
            "to hide. Click Apply Shot Mask Settings to push changes to "
            "the scene's mask node."
        ))
        tab_layout.addWidget(enable_card)
        tab_layout.addWidget(labels_card)
        tab_layout.addWidget(tokens_card)
        tab_layout.addLayout(apply_row)
        tab_layout.addStretch()

        return self._wrap_in_scroll(tab_inner)

    # ------- Settings tab ---------------------------------------------
    def _build_settings_widgets(self):
        self.tool_ffmpeg_path_le = QtWidgets.QLineEdit()
        self.tool_ffmpeg_browse_btn = QtWidgets.QPushButton("...")
        self.tool_ffmpeg_browse_btn.setMaximumWidth(30)

        self.tool_temp_dir_le = QtWidgets.QLineEdit()
        self.tool_temp_dir_browse_btn = QtWidgets.QPushButton("...")
        self.tool_temp_dir_browse_btn.setMaximumWidth(30)

        self.tool_temp_format_cmb = QtWidgets.QComboBox()
        self.tool_temp_format_cmb.addItems(["png", "jpg", "tif"])

        self.tool_apply_btn = QtWidgets.QPushButton("Apply Tool Settings")

    def _build_settings_tab(self):
        ffmpeg_row = QtWidgets.QHBoxLayout()
        ffmpeg_row.addWidget(self.tool_ffmpeg_path_le)
        ffmpeg_row.addWidget(self.tool_ffmpeg_browse_btn)

        temp_row = QtWidgets.QHBoxLayout()
        temp_row.addWidget(self.tool_temp_dir_le)
        temp_row.addWidget(self.tool_temp_dir_browse_btn)

        paths_card, paths_body = self._card("Paths")
        paths_form = PBCFormLayout()
        paths_form.setVerticalSpacing(8)
        paths_form.addLayoutRow(0, "FFmpeg:", ffmpeg_row)
        paths_form.addLayoutRow(1, "Temp Output Dir:", temp_row)
        paths_form.addWidgetRow(2, "Temp Format:", self.tool_temp_format_cmb)
        paths_body.addLayout(paths_form)

        apply_row = QtWidgets.QHBoxLayout()
        apply_row.addStretch()
        apply_row.addWidget(self.tool_apply_btn)

        tab_inner = QtWidgets.QWidget()
        tab_layout = QtWidgets.QVBoxLayout(tab_inner)
        tab_layout.setContentsMargins(10, 10, 10, 10)
        tab_layout.setSpacing(10)
        tab_layout.addWidget(self._help_caption(
            "One-time tool setup. Point FFmpeg at your ffmpeg.exe so the "
            "tool can transcode to H.264/ProRes. The temp folder is used "
            "for the Preview button and for image sequences before "
            "encoding. Click Apply Tool Settings to save."
        ))
        tab_layout.addWidget(paths_card)
        tab_layout.addLayout(apply_row)
        tab_layout.addStretch()

        return self._wrap_in_scroll(tab_inner)

    # ------- Footer: log + action bar ---------------------------------
    def _build_footer(self):
        # Log area wrapped in a collapsible group
        log_group = PBCCollapsibleGrpWidget("Output Log")
        log_group.set_expanded(False)

        log_controls = QtWidgets.QHBoxLayout()
        log_controls.setContentsMargins(0, 0, 0, 0)
        log_controls.addWidget(self.log_to_script_editor_cb)
        log_controls.addStretch()
        log_controls.addWidget(self.clear_btn)

        self.output_edit.setMinimumHeight(80)
        self.output_edit.setMaximumHeight(160)

        log_group.add_widget(self.output_edit)
        log_group.add_layout(log_controls)

        # Action bar
        action_row = QtWidgets.QHBoxLayout()
        action_row.setContentsMargins(0, 6, 0, 0)
        action_row.addStretch()
        action_row.addWidget(self.preview_btn)
        action_row.addSpacing(8)
        action_row.addWidget(self.execute_btn)

        footer_frame = QtWidgets.QFrame()
        footer_frame.setStyleSheet(
            "QFrame { background-color: #2A2A2A; border-radius: 5px; }"
        )
        footer_layout = QtWidgets.QVBoxLayout(footer_frame)
        footer_layout.setContentsMargins(8, 6, 8, 8)
        footer_layout.setSpacing(4)
        footer_layout.addWidget(log_group)
        footer_layout.addLayout(action_row)

        return footer_frame

    # ------------------------------------------------------------------
    # Tooltips
    # ------------------------------------------------------------------
    def _apply_tooltips(self):
        """Install concise hover tooltips on every user-facing control.

        Called at the end of create_layouts(), once every widget exists.
        Keep tooltip text short, plain-language, and example-driven so
        students can learn the tool without reading docs.
        """

        # --- Output tab -----------------------------------------------
        self.output_dir_path_le.setToolTip(
            "Folder where the playblast file will be saved.\n"
            "Supports tokens: {project}, {scene}, {timestamp}.\n"
            "Example: {project}/movies"
        )
        self.output_dir_path_select_btn.setToolTip("Browse for an output folder.")
        self.output_dir_path_show_folder_btn.setToolTip(
            "Open the current output folder in your file browser."
        )
        self.output_filename_le.setToolTip(
            "Output filename without extension.\n"
            "Supports tokens: {scene}, {timestamp}, {camera}.\n"
            "Example: {scene}_{timestamp}"
        )
        self.force_overwrite_cb.setToolTip(
            "If checked, overwrite an existing file with the same name.\n"
            "If unchecked, the playblast aborts when the file exists."
        )

        self.assignmentSpinBox.setToolTip("Assignment number (the 'A1' prefix).")
        self.lastnameLineEdit.setToolTip("Your last name for the filename.")
        self.firstnameLineEdit.setToolTip("Your first name for the filename.")
        self.versionTypeCombo.setToolTip(
            "wip  = work in progress\n"
            "final = final submission version"
        )
        self.versionNumberSpinBox.setToolTip(
            "Version number, zero-padded to two digits (e.g. 01, 02)."
        )
        self.namegen_assignment_cb.setToolTip(
            "Include the assignment prefix (e.g. A1) in the generated filename."
        )
        self.namegen_lastname_cb.setToolTip(
            "Include your last name in the generated filename."
        )
        self.namegen_firstname_cb.setToolTip(
            "Include your first name in the generated filename."
        )
        self.namegen_versiontype_cb.setToolTip(
            "Include the version type (wip / final) in the generated filename."
        )
        self.namegen_versionnumber_cb.setToolTip(
            "Include the version number (01, 02, ...) in the generated filename."
        )
        self.filenamePreviewLabel.setToolTip(
            "Live preview of the generated filename."
        )
        self.generateFilenameButton.setToolTip(
            "Copy the generated name into the Filename field above."
        )
        self.resetNameGeneratorButton.setToolTip(
            "Clear the Name Generator fields back to defaults."
        )

        # --- Render tab -----------------------------------------------
        self.camera_select_cmb.setToolTip(
            "Camera to render from. 'Active' uses whichever viewport "
            "camera is currently focused when the playblast runs."
        )
        self.camera_select_hide_defaults_cb.setToolTip(
            "Hide Maya's built-in cameras (persp, top, front, side) "
            "from this list."
        )
        self.resolution_select_cmb.setToolTip(
            "Output image size. Choose a preset or 'Custom' to enter "
            "your own width and height."
        )
        self.resolution_width_sb.setToolTip("Output image width in pixels.")
        self.resolution_height_sb.setToolTip("Output image height in pixels.")

        self.display_size_cmb.setToolTip(
            "How the output size is determined (matches Maya's Playblast\n"
            "Options 'Display Size' popup):\n"
            "  From Window          - match the focused viewport's size\n"
            "  From Render Settings - match defaultResolution width/height\n"
            "  Custom               - use the Resolution controls above"
        )
        self.scale_percent_sb.setToolTip(
            "Render size as a percentage of the resolution above. 100 % is\n"
            "full size; lower values downscale for faster previews."
        )
        self.image_quality_slider.setToolTip(
            "Compression quality for the playblast frames (0-100).\n"
            "100 = maximum quality / largest file; lower values compress more."
        )
        self.image_quality_sb.setToolTip(self.image_quality_slider.toolTip())
        self.frame_padding_sb.setToolTip(
            "Number of digits used to number image-sequence frames\n"
            "(e.g. 4 -> 0001, 0002, ...). Maya default is 4."
        )
        self.frame_range_cmb.setToolTip(
            "Frames to render:\n"
            "  Animation  - scene's animation start/end\n"
            "  Playback   - timeline start/end\n"
            "  Render     - Render Globals start/end\n"
            "  Camera     - use the camera's own frame range\n"
            "  Custom     - type start/end yourself"
        )
        self.frame_range_start_sb.setToolTip("First frame to render.")
        self.frame_range_end_sb.setToolTip("Last frame to render.")

        self.visibility_cmb.setToolTip(
            "Viewport visibility preset - controls which object types "
            "(geometry, cameras, lights, NURBS, etc.) are drawn."
        )
        self.visibility_customize_btn.setToolTip(
            "Open the Visibility dialog to toggle individual object types."
        )

        self.overscan_cb.setToolTip(
            "Render the camera's overscan area (extra pixels outside the "
            "film gate). Usually OFF for submissions."
        )
        self.ornaments_cb.setToolTip(
            "Include Maya's viewport ornaments (HUDs, axis, resolution "
            "gate labels). Usually OFF for a clean playblast."
        )
        self.offscreen_cb.setToolTip(
            "Render in an offscreen buffer so other windows can't "
            "corrupt the frames. Safer, slightly slower."
        )
        self.viewer_cb.setToolTip(
            "Automatically open the finished playblast in your default "
            "movie player."
        )
        self.shot_mask_cb.setToolTip(
            "Show the Shot Mask overlay (text + letterbox) during the "
            "playblast. Configure it on the Shot Mask tab."
        )
        self.fit_shot_mask_cb.setToolTip(
            "Shrink the render inside the shot-mask borders instead of "
            "drawing the mask on top of the image."
        )
        self.nurbs_curves_cb.setToolTip(
            "Show NURBS curves (controls, motion paths) in the playblast."
        )
        self.nurbs_surfaces_cb.setToolTip(
            "Show NURBS surfaces in the playblast."
        )

        self.sound_enable_cb.setToolTip(
            "Include the timeline's sound node in the final playblast.\n"
            "Only applies to movie containers (mp4, mov) - image "
            "sequences cannot carry audio."
        )
        self.sound_refresh_btn.setToolTip(
            "Re-check Maya's timeline for a sound node and update the "
            "status line below."
        )

        # --- Encoding tab ---------------------------------------------
        self.encoding_container_cmb.setToolTip(
            "Output file format:\n"
            "  mp4   - most compatible, best for submissions\n"
            "  mov   - QuickTime, good for editorial\n"
            "  Image - a numbered sequence of stills"
        )
        self.encoding_video_codec_cmb.setToolTip(
            "Codec used inside the chosen container.\n"
            "  H.264   - small, universal; best for class submissions\n"
            "  MPEG-4  - legacy, widely playable\n"
            "  ProRes  - editorial, large files, mov only\n"
            "  PNG / JPEG / TIFF - image sequence, no ffmpeg needed\n"
            "Entries marked 'unavailable' are not present in your\n"
            "current ffmpeg build; hover them for details."
        )
        self.encoding_video_codec_settings_btn.setToolTip(
            "Open encoder settings (quality, preset, bitrate)."
        )

        # --- Shot Mask tab --------------------------------------------
        self.sm_enable_mask_cb.setToolTip(
            "Enable the shot-mask overlay on the playblast."
        )
        self.sm_top_border_cb.setToolTip(
            "Draw a solid black bar across the top of the frame."
        )
        self.sm_bottom_border_cb.setToolTip(
            "Draw a solid black bar across the bottom of the frame."
        )

        label_slot_tip = (
            "Text shown in this mask slot.\n"
            "Tokens are expanded at playblast time: {scene}, {camera}, "
            "{counter}, {fps}, {date}, {username}, {shot}."
        )
        for line_edit in (
            self.sm_top_left_le,
            self.sm_top_center_le,
            self.sm_top_right_le,
            self.sm_bottom_left_le,
            self.sm_bottom_center_le,
            self.sm_bottom_right_le,
        ):
            line_edit.setToolTip(label_slot_tip)

        show_tip = "Show this label slot in the mask. Uncheck to hide it."
        for check_box in (
            self.sm_top_left_cb,
            self.sm_top_center_cb,
            self.sm_top_right_cb,
            self.sm_bottom_left_cb,
            self.sm_bottom_center_cb,
            self.sm_bottom_right_cb,
        ):
            check_box.setToolTip(show_tip)

        self.sm_common_items_cmb.setToolTip(
            "Pre-built values you can insert into any label slot.\n"
            "  General tokens (e.g. {scene}, {camera}) are resolved live\n"
            "  by the shot mask at render time.\n"
            "  Animation Pass entries (Blocking, Polish, ...) are inserted\n"
            "  as plain text for quick submission labelling."
        )
        self.sm_insert_item_btn.setToolTip(
            "Insert the selected token into whichever label field you "
            "clicked most recently."
        )
        self.sm_counter_padding_sb.setToolTip(
            "Number of digits used for the {counter} token\n"
            "(e.g. 4 prints frame 7 as 0007)."
        )
        self.sm_use_namegen_btn.setToolTip(
            "Copy the Name Generator preview into the Top Center slot."
        )
        self.sm_apply_btn.setToolTip(
            "Push these settings onto the scene's shot-mask node."
        )

        # --- Settings tab ---------------------------------------------
        self.tool_ffmpeg_path_le.setToolTip(
            "Full path to ffmpeg (ffmpeg.exe on Windows). Required for "
            "encoding to H.264/ProRes. Download from ffmpeg.org if you "
            "don't have it."
        )
        self.tool_ffmpeg_browse_btn.setToolTip("Browse for the ffmpeg executable.")
        self.tool_temp_dir_le.setToolTip(
            "Folder used for intermediate image sequences and for the "
            "Preview button's throwaway output."
        )
        self.tool_temp_dir_browse_btn.setToolTip("Browse for the temp folder.")
        self.tool_temp_format_cmb.setToolTip(
            "Image format used for intermediate frames before ffmpeg "
            "encodes them into the final video."
        )
        self.tool_apply_btn.setToolTip(
            "Save the paths above so the tool remembers them next time."
        )

        # --- Footer ---------------------------------------------------
        self.log_to_script_editor_cb.setToolTip(
            "Also print tool messages into Maya's Script Editor."
        )
        self.clear_btn.setToolTip("Clear the log panel above.")
        self.preview_btn.setToolTip(
            "Quick low-effort playblast written to the Temp folder, "
            "handy for previewing settings without committing to a final "
            "file."
        )
        self.execute_btn.setToolTip(
            "Create the full playblast using the options on every tab."
        )


_pbc_playblast_workspace_control = None
_pbc_playblast_widget = None


def show_ui():
    """Show the Playblast Creator UI in a Maya workspace control."""
    global _pbc_playblast_workspace_control
    global _pbc_playblast_widget

    if not PBCPlayblastUtils.load_plugin():
        return None

    if _pbc_playblast_workspace_control is None:
        _pbc_playblast_workspace_control = PBCWorkspaceControl("PBCWorkspaceControl")

    if _pbc_playblast_widget is None:
        _pbc_playblast_widget = PBCPlayblastWidget()

    if _pbc_playblast_workspace_control.exists():
        _pbc_playblast_workspace_control.restore(_pbc_playblast_widget)
        _pbc_playblast_workspace_control.set_visible(True)
    else:
        _pbc_playblast_workspace_control.create("Playblast Creator", _pbc_playblast_widget)

    return _pbc_playblast_widget


def close_ui():
    """Close the Playblast Creator UI workspace control if it exists."""
    global _pbc_playblast_workspace_control
    global _pbc_playblast_widget

    if _pbc_playblast_workspace_control and _pbc_playblast_workspace_control.exists():
        cmds.deleteUI(_pbc_playblast_workspace_control.name)

    _pbc_playblast_workspace_control = None
    _pbc_playblast_widget = None


if __name__ == "__main__":
    show_ui()
