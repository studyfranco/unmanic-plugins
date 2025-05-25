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

from . import base_encoder


class LibsvtAv1Encoder(base_encoder.BaseEncoder):

    def __init__(self, settings=None):
        super().__init__(settings)
        self.encoder_codec = "av1"
        self.encoder_name = "libsvt-av1"

    def provides(self):
        return {
            self.encoder_name: { # Should resolve to "libsvt-av1"
                "codec": self.encoder_codec, # Should resolve to "av1"
                "label": "CPU - libsvt-av1 (AV1)",
            }
        }

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
                    {"name": "4", "value": "4"},
                    {"name": "3", "value": "3"},
                    {"name": "2", "value": "2"},
                    {"name": "1", "value": "1"},
                    {"name": "0 - Slowest/Best Quality", "value": "0"}
                ],
                "default": "8", 
                "order": 180,
            },
            "video_encoder_libsvt_av1_crf": {
                "label": "AV1 CRF (libsvt-av1)",
                "type": "slider", # Changed to slider
                "slider_options": {"min": 0, "max": 63, "step": 1},
                "default": "30",
                "tooltip": "Constant Rate Factor (0-63). Lower values mean better quality. Recommended: 25-35 for 1080p.",
                "order": 181,
            },
            "video_encoder_libsvt_av1_pix_fmt": {
                "label": "AV1 Pixel Format (libsvt-av1)",
                "type": "text",
                "default": "yuv420p10le",
                "tooltip": "Specify the pixel format (e.g., yuv420p, yuv420p10le). Leave empty to use source.",
                "order": 182,
            },
            "video_encoder_libsvt_av1_gop_size": {
                "label":   "AV1 GOP Size (libsvt-av1)",
                "type":    "text",
                "default": "", 
                "tooltip": "Keyframe interval (GOP size). Empty for auto/default. E.g., 240 for 10-second interval at 24fps.",
                "order":   185,
            },
            "video_encoder_libsvt_av1_force_key_frames": {
                "label":   "AV1 Force Keyframes (libsvt-av1)",
                "type":    "text",
                "default": "",
                "tooltip": "Force keyframes using an expression. Example: expr:gte(t,n_forced*240)",
                "order":   186,
            },
            "video_encoder_libsvt_av1_params_string": { # Renamed from video_encoder_libsvt_av1_custom_params
                "label": "AV1 Specific Parameters (libsvt-av1)",
                "type": "text",
                "default": "",
                "tooltip": "Directly pass parameters to libsvt-av1 using the -svtav1-params flag. Example: scd=1:tune=0:enable-overlays=1",
                "order": 187, 
            },
        }

    def build_video_encoding_parameters(self, outmaps, settings_dict=None):
        params = super().build_video_encoding_parameters(outmaps, settings_dict)
        
        preset = self.get_setting("video_encoder_libsvt_av1_preset", settings_dict)
        if preset:
            params.extend(["-preset", str(preset)])

        crf = self.get_setting("video_encoder_libsvt_av1_crf", settings_dict)
        if crf:
            params.extend(["-crf", str(crf)])

        pix_fmt = self.get_setting("video_encoder_libsvt_av1_pix_fmt", settings_dict)
        if pix_fmt:
            params.extend(["-pix_fmt", str(pix_fmt)])

        gop_size = self.get_setting("video_encoder_libsvt_av1_gop_size", settings_dict)
        if gop_size:
            params.extend(["-g", str(gop_size)])

        force_key_frames = self.get_setting("video_encoder_libsvt_av1_force_key_frames", settings_dict)
        if force_key_frames:
            params.extend(["-force_key_frames", str(force_key_frames)])
            
        params_string = self.get_setting("video_encoder_libsvt_av1_params_string", settings_dict)
        if params_string:
            # Pass the value as a single string, not split
            params.extend(["-svtav1-params", str(params_string)]) 
            
        return params

    # The __getattr__ in BaseEncoder should handle the form settings methods automatically
    # for options defined in get_encoder_options_model.
    # If specific form settings are needed for video_encoder_libsvt_av1_crf (slider),
    # and BaseEncoder doesn't handle it correctly, this method can be uncommented and customized:
    # def get_video_encoder_libsvt_av1_crf_form_settings(self, settings_dict=None):
    #     form_settings = super().get_video_encoder_libsvt_av1_crf_form_settings(settings_dict)
    #     # Ensure slider specific settings are correctly passed if BaseEncoder doesn't do it.
    #     # form_settings["input_type"] = "slider" # Should be picked from model type
    #     # form_settings["slider_options"] = self.get_encoder_options_model()["video_encoder_libsvt_av1_crf"]["slider_options"]
    #     return form_settings
