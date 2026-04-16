"""Conestoga Playblast v2.0.4 installer.

Executed by install_conestoga_playblast_v2_0_4.mel when dragged into Maya.
"""

import os
import shutil
import sys

import maya.cmds as cmds
import maya.mel as mel


VERSION_FOLDER = "CP_v2_0_4"
TOOL_FOLDER = "conestoga_playblast"
ICON_NAME = "conestoga_playblast_icon.png"

REQUIRED_FILES = [
    "conestoga_playblast.py",
    "conestoga_playblast_ui.py",
    "conestoga_playblast_presets.py",
]


def _resolve_source_dir(source_dir):
    if source_dir:
        return os.path.normpath(source_dir)
    return os.path.dirname(os.path.abspath(__file__))


def _copy_required_files(source_dir, install_root):
    missing = [
        filename for filename in REQUIRED_FILES
        if not os.path.exists(os.path.join(source_dir, filename))
    ]
    if missing:
        raise RuntimeError(
            "[Conestoga Playblast] Missing required files: {0}".format(", ".join(missing))
        )

    os.makedirs(install_root, exist_ok=True)

    for filename in REQUIRED_FILES:
        shutil.copy2(os.path.join(source_dir, filename), os.path.join(install_root, filename))


def _install_icon(source_dir, icons_dir):
    package_root = os.path.dirname(source_dir)
    source_icon = os.path.join(package_root, ICON_NAME)
    if not os.path.exists(source_icon):
        print("[Conestoga Playblast] Icon not found: {0}".format(source_icon))
        return ""

    os.makedirs(icons_dir, exist_ok=True)
    target_icon = os.path.join(icons_dir, ICON_NAME)
    shutil.copy2(source_icon, target_icon)
    return target_icon


def _write_launcher(scripts_dir):
    launcher_root = os.path.join(scripts_dir, TOOL_FOLDER)
    os.makedirs(launcher_root, exist_ok=True)
    launcher_path = os.path.join(launcher_root, "conestoga_playblast_latest.py")

    launcher_source = (
        "import os\n"
        "import sys\n"
        "import maya.cmds as cmds\n\n"
        "root = os.path.join(cmds.internalVar(userAppDir=True), 'scripts', 'conestoga_playblast', 'CP_v2_0_4')\n"
        "if root not in sys.path:\n"
        "    sys.path.insert(0, root)\n\n"
        "from conestoga_playblast_ui import show_ui\n\n"
        "def launch():\n"
        "    show_ui()\n"
    )

    with open(launcher_path, "w") as launcher_file:
        launcher_file.write(launcher_source)


def _add_shelf_button(icon_path):
    try:
        shelf_top_level = mel.eval('$tmp = $gShelfTopLevel')
        if not shelf_top_level:
            print("[Conestoga Playblast] Shelf layout not available. Skipping shelf button creation.")
            return

        current_shelf = cmds.tabLayout(shelf_top_level, q=True, selectTab=True)
        if not current_shelf:
            print("[Conestoga Playblast] No active shelf tab. Skipping shelf button creation.")
            return

        existing_buttons = cmds.shelfLayout(current_shelf, q=True, childArray=True) or []
        for button in existing_buttons:
            if cmds.objectTypeUI(button) == "shelfButton":
                cmd = cmds.shelfButton(button, q=True, command=True) or ""
                if "conestoga_playblast_latest" in cmd:
                    cmds.deleteUI(button)

        shelf_command = (
            "import os, sys, maya.cmds as cmds\n"
            "root = os.path.join(cmds.internalVar(userAppDir=True), 'scripts', 'conestoga_playblast')\n"
            "if root not in sys.path:\n"
            "    sys.path.insert(0, root)\n"
            "import conestoga_playblast_latest\n"
            "conestoga_playblast_latest.launch()"
        )

        image_name = os.path.basename(icon_path) if icon_path else "commandButton.png"

        cmds.shelfButton(
            parent=current_shelf,
            label="Playblast",
            annotation="Launch Conestoga Playblast",
            image1=image_name,
            imageOverlayLabel="CP",
            command=shelf_command,
            sourceType="python",
        )

    except Exception as exc:
        print("[Conestoga Playblast] Failed to create shelf button: {0}".format(exc))


def install(source_dir=None):
    source_dir = _resolve_source_dir(source_dir)

    maya_app_dir = os.path.normpath(cmds.internalVar(userAppDir=True))
    scripts_dir = os.path.join(maya_app_dir, "scripts")
    icons_dir = os.path.join(maya_app_dir, "prefs", "icons")
    install_root = os.path.join(scripts_dir, TOOL_FOLDER, VERSION_FOLDER)

    _copy_required_files(source_dir, install_root)
    icon_path = _install_icon(source_dir, icons_dir)
    _write_launcher(scripts_dir)
    _add_shelf_button(icon_path)

    message = "Installation complete.\nInstalled to:\n{0}".format(install_root)
    cmds.confirmDialog(title="Conestoga Playblast", message=message, button=["OK"])
    print("[Conestoga Playblast] Installed v2.0.4 to: {0}".format(install_root))


if __name__ == "__main__":
    passed_source_dir = None
    if len(sys.argv) > 1:
        passed_source_dir = sys.argv[1]
    install(source_dir=passed_source_dir)
