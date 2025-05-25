#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright:
#   Copyright (C) 2023 studyfranco <user@example.com> 
#   (Replace studyfranco <user@example.com> with the actual author if known, otherwise this is a placeholder)
#
#   This program is free software: you can redistribute it and/or modify it under the terms of the GNU General
#   Public License as published by the Free Software Foundation, version 3.
#
#   This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the
#   implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License
#   for more details.
#
#   You should have received a copy of the GNU General Public License along with this program.
#   If not, see <https://www.gnu.org/licenses/>.

from video_transcoder_studyfranco.lib.encoders import base_encoder


class LibsvtAv1Encoder(base_encoder.BaseEncoder):

    def __init__(self, settings=None):
        super().__init__(settings)
        self.encoder_codec = "av1"
        self.encoder_name = "libsvt-av1"

    def provides(self):
        return [self.encoder_name]

    def get_encoder_options_model(self):
        return {
            "video_encoder_libsvt_av1_preset": {
                "label": "AV1 Preset (libsvt-av1)",
                "type": "select",
                "options": [
                    {"name": "12 - Fastest", "value": "12"},
                    {"name": "11", "value": "11"},
                    {"name": "10", "value": "10"},
                    {"name": "9", "value": "9"},
                    {"name": "8 - Default", "value": "8"},
                    {"name": "7", "value": "7"},
                    {"name": "6", "value": "6"},
                    {"name": "5", "value": "5"},
                    {"name": "4 - Slowest", "value": "4"},
                ],
                "default": "8",
                "order": 180,
            },
            "video_encoder_libsvt_av1_crf": {
                "label": "AV1 CRF (libsvt-av1)",
                "type": "text",
                "default": "30",
                "order": 181,
            },
            "video_encoder_libsvt_av1_pix_fmt": {
                "label": "AV1 Pixel Format (libsvt-av1)",
                "type": "text",
                "default": "yuv420p10le",
                "tooltip": "Specify the pixel format (e.g., yuv420p, yuv420p10le). Leave empty to use source.",
                "order": 182,
            },
            "video_encoder_libsvt_av1_scd": {
                "label": "AV1 Scene Change Detection (libsvt-av1)",
                "type": "select",
                "options": [
                    {"name": "Enable", "value": "1"},
                    {"name": "Disable", "value": "0"}
                ],
                "default": "1",
                "tooltip": "Enable or disable scene change detection.",
                "order": 183,
            },
            "video_encoder_libsvt_av1_custom_params": {
                "label": "AV1 Custom Parameters (libsvt-av1)",
                "type": "text",
                "default": "",
                "tooltip": "Specify any additional custom parameters for libsvt-av1, e.g., '-svtav1-params tune=0'.",
                "order": 184,
            },
        }

    def build_video_encoding_parameters(self, outmaps, settings_dict=None):
        params = super().build_video_encoding_parameters(outmaps, settings_dict)
        
        # Correct way to access settings, using the get_setting method from BaseEncoder
        preset = self.get_setting("video_encoder_libsvt_av1_preset", settings_dict)
        if preset:
            params.extend(["-preset", str(preset)])

        crf = self.get_setting("video_encoder_libsvt_av1_crf", settings_dict)
        if crf:
            params.extend(["-crf", str(crf)])

        pix_fmt = self.get_setting("video_encoder_libsvt_av1_pix_fmt", settings_dict)
        if pix_fmt:
            params.extend(["-pix_fmt", str(pix_fmt)])

        scd = self.get_setting("video_encoder_libsvt_av1_scd", settings_dict)
        if scd == "0": # Note: settings often come as strings
            params.extend(["-scd", "0"])

        custom_params = self.get_setting("video_encoder_libsvt_av1_custom_params", settings_dict)
        if custom_params:
            params.extend(custom_params.split())
            
        return params

    # The __getattr__ in BaseEncoder should handle the form settings methods automatically.
    # If specific logic is needed for any of these, they can be explicitly defined.
    # For example:
    # def get_video_encoder_libsvt_av1_preset_form_settings(self, settings_dict=None):
    #     # Custom logic here if needed, otherwise BaseEncoder handles it
    #     return super().get_video_encoder_libsvt_av1_preset_form_settings(settings_dict)
    #
    # No need to redefine these if the BaseEncoder.__getattr__ handles them:
    # def get_video_encoder_libsvt_av1_crf_form_settings(self, settings_dict=None):
    # def get_video_encoder_libsvt_av1_pix_fmt_form_settings(self, settings_dict=None):
    # def get_video_encoder_libsvt_av1_scd_form_settings(self, settings_dict=None):
    # def get_video_encoder_libsvt_av1_custom_params_form_settings(self, settings_dict=None):
