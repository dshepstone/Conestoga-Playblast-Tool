"""Conestoga Playblast v2.0.4 installer.

This script is invoked by `install_conestoga_playblast_v2_0_4.mel`.
"""

import os
import shutil

import maya.cmds as cmds


VERSION_FOLDER = "CP_v2_0_4"
REQUIRED_FILES = [
    "conestoga_playblast.py",
    "conestoga_playblast_ui.py",
    "conestoga_playblast_presets.py",
]


def _write_launcher(launcher_path):
    launcher_source = (
        "import os\n"
        "import sys\n\n"
        "root = os.path.dirname(os.path.abspath(__file__))\n"
        "version_dir = os.path.join(root, 'CP_v2_0_4')\n"
        "if version_dir not in sys.path:\n"
        "    sys.path.insert(0, version_dir)\n\n"
        "from conestoga_playblast_ui import show_ui\n\n"
        "def launch():\n"
        "    show_ui()\n"
    )

    with open(launcher_path, "w") as launcher_file:
        launcher_file.write(launcher_source)


def install(source_dir=None):
    if not source_dir:
        source_dir = os.path.dirname(os.path.abspath(__file__))

    missing = [
        filename for filename in REQUIRED_FILES
        if not os.path.exists(os.path.join(source_dir, filename))
    ]
    if missing:
        raise RuntimeError(
            "[Conestoga Playblast] Missing required files: {0}".format(", ".join(missing))
        )

    maya_app_dir = os.path.normpath(cmds.internalVar(userAppDir=True))
    scripts_dir = os.path.join(maya_app_dir, "scripts")
    install_root = os.path.join(scripts_dir, "conestoga_playblast", VERSION_FOLDER)
    os.makedirs(install_root, exist_ok=True)

    for filename in REQUIRED_FILES:
        shutil.copy2(os.path.join(source_dir, filename), os.path.join(install_root, filename))

    launcher_path = os.path.join(scripts_dir, "conestoga_playblast", "conestoga_playblast_latest.py")
    _write_launcher(launcher_path)

    cmds.confirmDialog(
        title="Conestoga Playblast",
        message="Installation complete.\nFiles installed to: {0}".format(install_root),
        button=["OK"],
    )

    print("[Conestoga Playblast] Installed v2.0.4 to: {0}".format(install_root))


if __name__ == "__main__":
    install()
