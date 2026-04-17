###############################################################################
# Name:
#   zurbrigg_advanced_playblast_presets.py
#
# Author:
#   Chris Zurbrigg (http://zurbrigg.com)
#
# Usage:
#   Visit http://zurbrigg.com for details
#
# Copyright (C) 2024 Chris Zurbrigg. All rights reserved.
###############################################################################

class ZurbriggPlayblastCustomPresets(object):


    RESOLUTION_PRESETS = [
        #
        # Format:  ["preset_name", (width, height)],
        #

        ["HD 1080", (1920, 1080)],
        ["HD 720", (1280, 720)],
        ["HD 540", (960, 540)],
    ]


    VIEWPORT_VISIBILITY_PRESETS = [
        #
        # Format: ["preset_name", ["type_name_1", "type_name_2", ...]],
        #
        # Viewport visibility types:
        #
        #    Controllers            NURBS Curves      NURBS Surfaces          NURBS CVs
        #    NURBS Hulls            Polygons          Subdiv Surfaces         Planes
        #    Lights                 Cameras           Image Planes            Joints
        #    IK Handles             Deformers         Dynamics                Particle Instancers
        #    Fluids                 Hair Systems      Follicles               nCloths
        #    nParticles             nRigids           Dynamic Constraints     Locators
        #    Dimensions             Pivots            Handles                 Texture Placements
        #    Strokes                Motion Trails     Plugin Shapes           Clip Ghosts
        #    Grease Pencil          Grid              HUD                     Hold-Outs
        #    Selection Highlighting
        #

        ["Geo", ["NURBS Surfaces", "Polygons"]],
        ["Dynamics", ["NURBS Surfaces", "Polygons", "Dynamics", "Fluids", "nParticles"]],
    ]

    PLAYBLAST_OUTPUT_PATH_LOOKUP = [
        #
        # Format:  ("display_name", "{tag_name}"),
        #
    ]

    PLAYBLAST_OUTPUT_FILENAME_LOOKUP = [
        #
        # Format:  ("display_name", "{tag_name}"),
        #
    ]


    @classmethod
    def parse_playblast_output_dir_path(cls, dir_path):
        """
        User defined output directory {tags}. Logic should replace tag with a string.

        PLAYBLAST_OUTPUT_PATH_LOOKUP can be used to add {tag} to context menu.
        """
        # if "{my_tag}" in dir_path:
        #     dir_path = dir_path.replace("{my_tag}", "My Custom Value")

        return dir_path

    @classmethod
    def parse_playblast_output_filename(cls, filename):
        """
        User defined output filenname {tags}. Logic should replace tag with a string.

        PLAYBLAST_OUTPUT_FILENAME_LOOKUP can be used to add {tag} to context menu.
        """
        # if "{my_tag}" in filename:
        #     filename = filename.replace("{my_tag}", "My Custom Value")

        return filename


class ZurbriggShotMaskCustomPresets(object):


    SHOT_MASK_LABEL_LOOKUP = [
        #
        # Format:  ("display_name", "{tag_name}"),
        #
    ]

    @classmethod
    def parse_shot_mask_text(cls, text):
        """
        User defined shot mask label {tags}. Logic should replace tag with a string.

        SHOT_MASK_LABEL_LOOKUP can be used to add {tag} to context menu.
        """
        # if "{my_tag}" in text:
        #     text = text.replace("{my_tag}", "My Custom Value")

        return text

