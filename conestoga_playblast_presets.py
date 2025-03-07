"""
Conestoga Playblast Tool - Presets Module
This module contains constants, default settings, and presets for the playblast tool.
"""

import os
import maya.cmds as cmds

# Tool Information
TOOL_NAME = "Conestoga Playblast Tool"
VERSION = "2.0.0"

# Shot Mask Constants
MASK_PREFIX = "cone_shotmask_"

# Default Settings
DEFAULT_CAMERA = "<Active>"
DEFAULT_RESOLUTION = "HD 1080"
DEFAULT_FRAME_RANGE = "Playback"
DEFAULT_OUTPUT_FORMAT = "mp4"
DEFAULT_ENCODER = "h264"
DEFAULT_H264_QUALITY = "High"
DEFAULT_H264_PRESET = "fast"
DEFAULT_VIEW_PRESET = "Standard"
DEFAULT_MASK_SCALE = 0.25
DEFAULT_COUNTER_PADDING = 4

# Format and Encoder Settings
FRAME_FORMATS = ["jpg", "png", "tif"]
MOVIE_FORMATS = ["mp4", "mov"]
OUTPUT_FORMATS = ["mp4", "mov", "Image"]

VIDEO_ENCODERS = {
    "mp4": ["h264"],
    "mov": ["h264", "prores"],
    "Image": FRAME_FORMATS
}

H264_QUALITIES = {
    "Very High": 18,
    "High": 20,
    "Medium": 23,
    "Low": 26
}

H264_PRESETS = [
    "veryslow",
    "slow",
    "medium",
    "fast",
    "faster",
    "ultrafast"
]

PRORES_PROFILES = {
    "ProRes 422 Proxy": 0,
    "ProRes 422 LT": 1,
    "ProRes 422": 2,
    "ProRes 422 HQ": 3,
    "ProRes 4444": 4,
    "ProRes 4444 XQ": 5
}

# Resolution Presets
RESOLUTION_PRESETS = {
    "HD 720": (1280, 720),
    "HD 1080": (1920, 1080),
    "UHD 4K": (3840, 2160),
    "Cinematic 2K": (2048, 1080),
    "Cinematic 4K": (4096, 2160),
    "Square 1080": (1080, 1080),
    "Vertical HD": (720, 1280),
    "Render": None  # This will use Maya's render settings
}

# Viewport Visibility Settings
VIEWPORT_VISIBILITY_LOOKUP = [
    ["NURBS Curves", "nurbsCurves"],
    ["NURBS Surfaces", "nurbsSurfaces"],
    ["Polygons", "polymeshes"],
    ["Subdivs", "subdivSurfaces"],
    ["Planes", "planes"],
    ["Lights", "lights"],
    ["Cameras", "cameras"],
    ["Image Planes", "imagePlane"],
    ["Joints", "joints"],
    ["IK Handles", "ikHandles"],
    ["Deformers", "deformers"],
    ["Dynamics", "dynamics"],
    ["Particle Instances", "particleInstancers"],
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
    ["Textures", "textures"],
    ["Strokes", "strokes"],
    ["Motion Trails", "motionTrails"],
    ["Plugin Shapes", "pluginShapes"],
    ["Clip Ghosts", "clipGhosts"],
    ["Controllers", "controllers"],
    ["Manipulators", "manipulators"],
    ["Grid", "grid"],
    ["HUD", "hud"],
    ["Selection Highlighting", "sel"]
]

# Viewport Visibility Presets
VIEWPORT_VISIBILITY_PRESETS = {
    "Viewport": [],  # Current viewport settings
    "Geo": ["NURBS Surfaces", "Polygons", "Subdivs"],
    "Standard": ["NURBS Curves", "NURBS Surfaces", "Polygons", "Subdivs", "Planes", 
                "Lights", "Cameras", "Joints", "IK Handles", "Locators"],
    "Full": ["NURBS Curves", "NURBS Surfaces", "Polygons", "Subdivs", "Planes", 
            "Lights", "Cameras", "Image Planes", "Joints", "IK Handles", 
            "Deformers", "Dynamics", "Locators", "Dimensions", "Pivots", 
            "Handles", "Textures", "Controllers", "Grid"]
}

# Shot Mask Templates
CUSTOM_MASK_TEMPLATES = {
    "Standard": {
        "topLeftText": "Scene: {scene}",
        "topCenterText": "",
        "topRightText": "FPS: {fps}",
        "bottomLeftText": "Artist: {username}",
        "bottomCenterText": "Date: {date}",
        "bottomRightText": "Frame: {counter}",
        "textColor": (1.0, 1.0, 1.0),
        "scale": 0.25,
        "opacity": 1.0
    },
    "Minimal": {
        "topLeftText": "{scene}",
        "topCenterText": "",
        "topRightText": "",
        "bottomLeftText": "",
        "bottomCenterText": "",
        "bottomRightText": "{counter}",
        "textColor": (1.0, 1.0, 1.0),
        "scale": 0.2,
        "opacity": 0.8
    },
    "Detailed": {
        "topLeftText": "Scene: {scene}",
        "topCenterText": "Camera: {camera}",
        "topRightText": "Focal: {focal_length}mm",
        "bottomLeftText": "Artist: {username}",
        "bottomCenterText": "Date: {date} {time}",
        "bottomRightText": "Frame: {counter}",
        "textColor": (0.4, 0.8, 1.0),
        "scale": 0.3,
        "opacity": 0.9
    }
}

# Filename Tag Patterns
TAG_PATTERNS = {
    "scene": lambda: os.path.splitext(os.path.basename(cmds.file(q=True, sn=True) or "untitled"))[0],
    "camera": lambda cam: cam.split("|")[-1].split(":")[-1] if cam else "cam",
    "date": lambda: cmds.about(cd=True).split()[0],
    "time": lambda: cmds.about(ct=True),
    "fps": lambda: int(round(mel.eval("currentTimeUnitToFPS"))),
    "username": lambda: os.environ.get("USER", os.environ.get("USERNAME", "user"))
}

# Custom locations for integrations
CUSTOM_LOCATIONS = {
    "ffmpeg_path": "",
    "temp_directory": "",
    "plugins_directory": ""
}

# Allow for custom presets via import
try:
    from conestoga_custom_presets import *
except ImportError:
    pass