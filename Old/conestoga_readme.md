# Conestoga Playblast Tool

A modular playblast tool for Maya that provides enhanced playblast capabilities with customizable shot masks and ffmpeg integration.

## Features

- Advanced playblast creation with customizable settings
- High-quality shot masks with dynamic text tags
- FFmpeg integration for superior video quality
- Batch processing for multiple cameras and scenes
- Professional UI with settings persistence
- Simple installation and Maya integration

## Installation

### Automatic Installation

1. Download the tool files
2. Run `install.py` with Python
3. Follow the prompts to complete installation

### Manual Installation

1. Copy all Python files to your Maya scripts directory
2. Copy the `conestoga-playblast-plugin.py` file to your Maya plugins directory
3. Add the following to your `userSetup.py`:

```python
# Conestoga Playblast Tool - Auto-load
import sys
import os

# Add conestoga_playblast to Python path
script_dir = os.path.dirname(os.path.abspath(__file__))
conestoga_dir = os.path.join(script_dir, "conestoga_playblast")
if conestoga_dir not in sys.path:
    sys.path.append(conestoga_dir)

# Load plugin and initialize menu
import maya.utils
maya.utils.executeDeferred("import conestoga_playblast_menu; conestoga_playblast_menu.initialize()")
```

## Usage

### From the Maya UI

1. Start Maya
2. Select "Conestoga GameDev > Playblast Tools > Conestoga Playblast Tool" from the menu
3. Configure your playblast settings
4. Click "Create Playblast"

### From Python Scripts

```python
import conestoga_playblast

# Show the UI
conestoga_playblast.show_ui()

# Create a playblast with custom settings
conestoga_playblast.create_playblast(
    camera="persp",
    output_dir="/path/to/output",
    filename="my_playblast",
    width=1920,
    height=1080,
    start_frame=1,
    end_frame=100,
    format_type="mp4",
    encoder="h264",
    quality="High",
    viewport_preset="Standard",
    shot_mask=True,
    show_in_viewer=True
)

# Batch playblast multiple cameras
from conestoga_batch_playblast import batch_playblast_cameras
batch_playblast_cameras(
    cameras=["persp", "side", "front"],
    settings={
        "output_dir": "/path/to/output",
        "filename": "batch_test",
        "format_type": "mp4"
    }
)
```

## Shot Mask Tags

The shot mask supports the following dynamic tags:

- `{scene}` - Current scene name
- `{camera}` - Current camera name
- `{focal_length}` - Camera focal length
- `{date}` - Current date
- `{time}` - Current time
- `{username}` - Current user name
- `{counter}` - Current frame number
- `{fps}` - Current frame rate

## Customization

### Adding Custom Presets

You can add your own presets by modifying the `conestoga_playblast_presets.py` file:

```python
# Add your custom resolution presets here
CUSTOM_RESOLUTION_PRESETS = {
    "Cinema 2K": (2048, 858),
    "Square 1K": (1024, 1024),
}

# Add your custom viewport visibility presets here
CUSTOM_VIEWPORT_PRESETS = {
    "Animation": ["NURBS Curves", "Polymeshes", "Joints", "IK Handles"],
    "FX": ["Polymeshes", "nParticles", "Fluids", "Dynamics"],
}

# Add your custom shot mask templates here
CUSTOM_MASK_TEMPLATES = {
    "MyTemplate": {
        "topLeft": "Scene: {scene}",
        "topCenter": "Camera: {camera}",
        "topRight": "Focal: {focal_length}",
        "bottomLeft": "Artist: {username}",
        "bottomCenter": "Date: {date}",
        "bottomRight": "Frame: {counter}",
        "textColor": (1.0, 1.0, 1.0),
        "scale": 0.25,
        "opacity": 1.0
    },
}
```

## Requirements

- Maya 2020 or later
- FFmpeg (optional, but recommended for high-quality video output)

## Configuration

The tool stores its configuration in Maya's option variables with the prefix `conePlayblast_`. These can be managed through the UI or directly via Maya's `optionVar` commands.

## License

Copyright © 2025 Conestoga College. All rights reserved.

## Acknowledgements

This tool was inspired by Chris Zurbrigg's Advanced Playblast tool, with significant modifications and enhancements.
