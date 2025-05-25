#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright:
#   Copyright (C) 2021 Josh Sunnex <josh@sunnex.com.au>
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

class BaseEncoder(object):
    """
    BaseEncoder

    Handles all interactions with the FFMPEG.
    Ensures that all commands are built in the correct ways
    """

    def __init__(self, settings=None):
        self.settings = settings
        self.encoder_codec = None  # E.g. h264, h265
        self.encoder_name = None  # E.g. libx264, libx265

    def get_setting(self, setting_key, settings_dict=None):
        """
        Fetches a single setting value by its key.
        Uses self.settings by default, but can also use a provided settings_dict.
        """
        # First try to get from passed settings_dict (e.g. from webhook)
        if settings_dict and setting_key in settings_dict:
            # Assuming settings_dict[setting_key] is the model for that setting
            # and contains a 'value' field. Adjust if structure is different.
            option_model = settings_dict[setting_key]
            if isinstance(option_model, dict) and 'value' in option_model:
                return option_model['value']
            # If it's directly the value (older format or simpler webhook)
            return option_model
        # Fallback to plugin settings if available
        if self.settings and hasattr(self.settings, 'get_setting'):
            return self.settings.get_setting(setting_key)
        return None

    def provides(self):
        """
        Returns a list of encoders that this class provides.
        This should be overridden by child classes.
        :return:
        """
        return []

    def options(self):
        """
        Return all options available for this encoder
        :return:
        """
        options = {}
        # Add model options from get_encoder_options_model
        model_options = self.get_encoder_options_model()
        for key, value in model_options.items():
            options[key] = value
        return options

    def get_encoder_options_model(self):
        """
        Return a model of the encoder options
        This should be overridden by child classes.
        :return:
        """
        return {}

    def build_video_encoding_parameters(self, outmaps, settings_dict=None):
        """
        Builds the video encoding parameters for FFMPEG.
        This can be extended by child classes for specific encoder parameters.
        :param outmaps:
        :param settings_dict:
        :return:
        """
        # Ensure outmaps is a dictionary, even if None is passed
        current_outmaps = outmaps if outmaps is not None else {}
        params = ['-c:v:{}'.format(current_outmaps.get('video_stream_index', 0)), self.encoder_name]
        return params

    # Generic form settings methods for options defined in get_encoder_options_model
    # These ensure that options are only shown when the respective encoder is selected.
    # Child classes can override these if more specific visibility logic is needed.
    def __getattr__(self, name):
        if name.startswith('get_') and name.endswith('_form_settings'):
            option_name = name[4:-15] # e.g. video_encoder_libx_crf from get_video_encoder_libx_crf_form_settings
            # Check if this option is part of this encoder's model
            if option_name in self.get_encoder_options_model():
                def form_settings_method(settings_dict=None):
                    return {
                        "visibility_conditions": [
                            {
                                "key":   "video_encoder",
                                "value": self.encoder_name
                            }
                        ]
                    }
                return form_settings_method
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")
