#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
    plugins.libx.py

    Written by:               Josh.5 <jsunnex@gmail.com>
    Date:                     12 Jun 2022, (9:48 AM)

    Copyright:
        Copyright (C) 2021 Josh Sunnex

        This program is free software: you can redistribute it and/or modify it under the terms of the GNU General
        Public License as published by the Free Software Foundation, version 3.

        This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the
        implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License
        for more details.

        You should have received a copy of the GNU General Public License along with this program.
        If not, see <https://www.gnu.org/licenses/>.

"""


class LibsvtAv1Encoder:

    def __init__(self, settings):
        self.settings = settings

    def provides(self):
        return {
            "libsvtav1": {
                "codec": "av1",
                "label": "CPU - libsvtav1",
            }
        }

    def options(self):
        return {
            "preset":                     "4",
            "encoder_ratecontrol_method": "CRF",
            "constant_quality_scale":     "23",
            "encoder_additional_params":  "no_additional_params",
        }

    def generate_default_args(self):
        """
        Generate a list of args for using a libx decoder

        :return:
        """
        # No default args required
        generic_kwargs = {}
        advanced_kwargs = {}
        return generic_kwargs, advanced_kwargs

    def generate_filtergraphs(self):
        """
        Generate the required filter for this encoder
        No filters are required for libx encoders

        :return:
        """
        return []

    def encoder_details(self, encoder):
        provides = self.provides()
        return provides.get(encoder, {})

    def args(self, stream_id):
        stream_encoding = []

        # Use defaults for basic mode
        if self.settings.get_setting('mode') in ['basic']:
            defaults = self.options()
            stream_encoding += [
                '-preset', str(defaults.get('preset')),
            ]
            # TODO: Calculate best crf based on source bitrate
            default_crf = defaults.get('constant_quality_scale')
            if self.settings.get_setting('video_encoder') in ['libsvtav1']:
                default_crf = 23
            stream_encoding += ['-crf', str(default_crf)]
            return stream_encoding

        if self.settings.get_setting('encoder_additional_params') in ['additional_params'] and self.settings.get_setting('encoder_svtav1_additional_params'):
            # Add additional parameters for SVT-AV1
            stream_encoding += ['-svtav1-params', self.settings.get_setting('encoder_svtav1_additional_params')]
            
        # Add the preset and tune
        if self.settings.get_setting('preset'):
            stream_encoding += ['-preset', str(self.settings.get_setting('preset'))]

        if self.settings.get_setting('encoder_ratecontrol_method') in ['CRF']:
            # Set values for constant quantizer scale
            stream_encoding += [
                '-crf', str(self.settings.get_setting('constant_quality_scale')),
            ]

        return stream_encoding

    def __set_default_option(self, select_options, key, default_option=None):
        """
        Sets the default option if the currently set option is not available

        :param select_options:
        :param key:
        :return:
        """
        available_options = []
        for option in select_options:
            available_options.append(option.get('value'))
            if not default_option:
                default_option = option.get('value')
        if self.settings.get_setting(key) not in available_options:
            self.settings.set_setting(key, default_option)

    def get_preset_form_settings(self):
        values = {
            "label":          "Encoder quality preset",
            "sub_setting":    True,
            "input_type":     "select",
            "select_options": [
                {
                    "value": "12",
                    "label": "Very fast (12) - Fastest setting, biggest quality drop",
                },
                {
                    "value": "10",
                    "label": "Faster (10) - Close to medium/fast quality, faster performance",
                },
                {
                    "value": "8",
                    "label": "Fast (8)",
                },
                {
                    "value": "6",
                    "label": "Medium (6)",
                },
                {
                    "value": "4",
                    "label": "Slow (4) - Balanced performance and quality",
                },
                {
                    "value": "2",
                    "label": "Slower (2) - Close to 'very slow' quality, faster performance",
                },
                {
                    "value": "1",
                    "label": "Very Slow (1) - Best quality",
                },
            ],
        }
        if self.settings.get_setting('mode') not in ['standard']:
            values["display"] = "hidden"
        return values

    def get_encoder_ratecontrol_method_form_settings(self):
        values = {
            "label":          "Encoder ratecontrol method",
            "sub_setting":    True,
            "input_type":     "select",
            "select_options": [
                {
                    "value": "CRF",
                    "label": "CRF - Constant Rate Factor",
                },
            ]
        }
        self.__set_default_option(values['select_options'], 'encoder_ratecontrol_method', default_option='CRF')
        if self.settings.get_setting('mode') not in ['standard']:
            values["display"] = "hidden"
        return values

    def get_constant_quality_scale_form_settings(self):
        # Lower is better
        values = {
            "label":          "Constant rate factor",
            "description":    "",
            "sub_setting":    True,
            "input_type":     "slider",
            "slider_options": {
                "min": 1,
                "max": 51,
            },
        }
        if self.settings.get_setting('mode') not in ['standard']:
            values["display"] = "hidden"
        if self.settings.get_setting('encoder_ratecontrol_method') not in ['CRF']:
            values["display"] = "hidden"
        if self.settings.get_setting('video_encoder') in ['libsvtav1']:
            values["description"] = "Default value for libsvtav1 = 23"
        return values
    
    def get_encoder_svtav1_additional_params_form_settings(self):
        values = {
            "label":          "SVT-AV1: Additional Parameters",
            "sub_setting":    True,
            "input_type":     "select",
            "select_options": [
                {
                    "value": "additional_params",
                    "label": "SVT-AV1: Additional Parameters",
                },
                {
                    "value": "no_additional_params",
                    "label": "No Additional Parameters",
                },
            ]
        }
        self.__set_default_option(values['select_options'], 'encoder_additional_params', default_option='additional_params')
        if self.settings.get_setting('mode') not in ['standard']:
            values["display"] = "hidden"
        return values
    
    def get_svtav1_additional_params_form_settings(self):
        values = {
            "label": "SVT-AV1: Additional Parameters field",
            "description": "Additional SVT-AV1 parameters as a colon-separated string (e.g., enable-cdef=1:enable-restoration=1).",
            "sub_setting": True,
            "input_type": "textarea",
        }
        if self.settings.get_setting('mode') not in ['standard']:
            values["display"] = "hidden"
        if self.settings.get_setting('encoder_additional_params') not in ['additional_params']:
            values["display"] = "hidden"
        
        return values