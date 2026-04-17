class CPPlayblastUi(QtWidgets.QWidget):

    WINDOW_TITLE = "CP Playblast"
    UI_NAME = "CPPlayblast"

    OPT_VAR_GROUP_STATE = "cpPlayblastGroupState"

    ui_instance = None


    @classmethod
    def display(cls):
        if cls.ui_instance:
            cls.ui_instance.show_workspace_control()
        else:
            if CPPlayblastUtils.load_plugin():
                cls.ui_instance = CPPlayblastUi()

    @classmethod
    def get_workspace_control_name(cls):
        return "{0}WorkspaceControl".format(cls.UI_NAME)

    def __init__(self):
        super(CPPlayblastUi, self).__init__()

        self.setObjectName(CPPlayblastUi.UI_NAME)

        self.setMinimumWidth(int(400 * CPPlayblastUtils.dpi_real_scale_value()))

        self._batch_playblast_dialog = None

        self.create_widgets()
        self.create_layouts()
        self.create_connections()
        self.create_workspace_control()

        self.main_tab_wdg.setCurrentIndex(0)
        
        # Apply modern styling
        self.setStyleSheet("""
            QTabWidget::pane {
                border: none;
                background-color: #2D2D30;
            }
            QTabBar::tab {
                background-color: #252526;
                color: #CCCCCC;
                padding: 8px 16px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background-color: #3D7AAB;
                color: white;
            }
            QTabBar::tab:hover:!selected {
                background-color: #333333;
            }
            QPushButton {
                background-color: #3D7AAB;
                color: white;
                border: none;
                border-radius: 3px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #4B94CF;
            }
            QPushButton:pressed {
                background-color: #2C5A8A;
            }
        """)

    def create_widgets(self):
        scale_value = CPPlayblastUtils.dpi_real_scale_value()
        button_width = int(120 * scale_value)
        button_height = int(40 * scale_value)
        batch_button_width = int(40 * scale_value)

        self.playblast_wdg = CPPlayblastWidget()
        self.playblast_wdg.setAutoFillBackground(True)

        playblast_scroll_area = QtWidgets.QScrollArea()
        playblast_scroll_area.setFrameShape(QtWidgets.QFrame.NoFrame)
        playblast_scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        playblast_scroll_area.setWidgetResizable(True)
        playblast_scroll_area.setWidget(self.playblast_wdg)

        self.shot_mask_wdg = CPShotMaskWidget()
        self.shot_mask_wdg.setAutoFillBackground(True)

        shot_mask_scroll_area = QtWidgets.QScrollArea()
        shot_mask_scroll_area.setFrameShape(QtWidgets.QFrame.NoFrame)
        shot_mask_scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        shot_mask_scroll_area.setWidgetResizable(True)
        shot_mask_scroll_area.setWidget(self.shot_mask_wdg)

        self.settings_wdg = CPPlayblastSettingsWidget()
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

        # Create action buttons with modern styling
        self.toggle_mask_btn = QtWidgets.QPushButton("Shot Mask")
        self.toggle_mask_btn.setFixedSize(button_width, button_height)
        self.toggle_mask_btn.setStyleSheet("background-color: #2980B9;")

        self.playblast_btn = QtWidgets.QPushButton("Playblast")
        self.playblast_btn.setMinimumSize(button_width, button_height)
        self.playblast_btn.setStyleSheet("background-color: #27AE60;")

        self.batch_playblast_btn = QtWidgets.QPushButton("...")
        self.batch_playblast_btn.setFixedSize(batch_button_width, button_height)
        self.batch_playblast_btn.setStyleSheet("background-color: #27AE60;")

        font = self.toggle_mask_btn.font()
        font.setPointSize(10)
        font.setBold(True)
        self.toggle_mask_btn.setFont(font)
        self.playblast_btn.setFont(font)

    def create_layouts(self):
        # Create modern button layout with shadows and spacing
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.setContentsMargins(0, 10, 0, 0)
        button_layout.addWidget(self.toggle_mask_btn)
        button_layout.addWidget(self.playblast_btn)
        button_layout.addWidget(self.batch_playblast_btn)

        # Status bar with version info
        status_bar_layout = QtWidgets.QHBoxLayout()
        status_bar_layout.setContentsMargins(4, 6, 4, 0)
        status_bar_layout.addStretch()
        
        version_label = QtWidgets.QLabel("v{0}".format(CPPlayblastUtils.get_version()))
        version_label.setStyleSheet("color: #777777; font-size: 10px;")
        status_bar_layout.addWidget(version_label)

        # Create a container frame for tabs
        tab_container = QtWidgets.QFrame()
        tab_container.setObjectName("tabContainer")
        tab_container.setStyleSheet("#tabContainer { border: 1px solid #333333; border-radius: 5px; }")
        
        tab_layout = QtWidgets.QVBoxLayout(tab_container)
        tab_layout.setContentsMargins(1, 1, 1, 1)
        tab_layout.setSpacing(0)
        tab_layout.addWidget(self.main_tab_wdg)

        # Main layout with modern spacing
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 6)
        main_layout.setSpacing(6)
        main_layout.addWidget(tab_container)
        main_layout.addLayout(button_layout)
        main_layout.addLayout(status_bar_layout)

    def create_connections(self):
        self.settings_wdg.playblast_reset.connect(self.playblast_wdg.reset_settings)
        self.settings_wdg.logo_path_updated.connect(self.shot_mask_wdg.update_mask)
        self.settings_wdg.shot_mask_reset.connect(self.shot_mask_wdg.reset_settings)

        self.toggle_mask_btn.clicked.connect(self.shot_mask_wdg.toggle_mask)
        self.playblast_btn.clicked.connect(self.playblast_wdg.do_playblast)
        self.batch_playblast_btn.clicked.connect(self.show_batch_playblast_dialog)

    def create_workspace_control(self):
        self.workspace_control_instance = CPWorkspaceControl(self.get_workspace_control_name())
        if self.workspace_control_instance.exists():
            self.workspace_control_instance.restore(self)
        else:
            self.workspace_control_instance.create(self.WINDOW_TITLE, self, ui_script="from cp_playblast_ui import CPPlayblastUi\nCPPlayblastUi.display()")

    def show_batch_playblast_dialog(self):
        if not self._batch_playblast_dialog:
            self._batch_playblast_dialog = CPCameraSelectDialog(self)
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

        return super(CPPlayblastUi, self).event(e)


if __name__ == "__main__":

    if CPPlayblastUtils.load_plugin():
        workspace_control_name = CPPlayblastUi.get_workspace_control_name()
        if cmds.window(workspace_control_name, exists=True):
            cmds.deleteUI(workspace_control_name)

        cp_test_ui = CPPlayblastUi()
