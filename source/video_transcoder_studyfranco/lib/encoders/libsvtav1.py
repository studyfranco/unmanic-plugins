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
            "scd":                        1,
            "enable_overlays":            1,
            "tune":                       2,
            "aq_mode":                    2,
            "enable_cdef":                True,
            "enable_restoration":         True,
            "enable_qm":                  True,
            "enable_variance_boost":      True,
            "additional_svtav1_params":   "",
            "sc_detection":               1,
            "gop_size":                   240,
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

        # Add the preset and tune
        if self.settings.get_setting('preset'):
            stream_encoding += ['-preset', str(self.settings.get_setting('preset'))]

        if self.settings.get_setting('encoder_ratecontrol_method') in ['CRF']:
            # Set values for constant quantizer scale
            stream_encoding += [
                '-crf', str(self.settings.get_setting('constant_quality_scale')),
            ]

        # Add new SVT-AV1 parameters
        params = []
        scd = self.settings.get_setting('scd')
        if scd is not None:
            params.append(f"scd={scd}")

        enable_overlays = self.settings.get_setting('enable_overlays')
        if enable_overlays is not None:
            params.append(f"enable-overlays={enable_overlays}")

        tune = self.settings.get_setting('tune')
        if tune is not None:
            params.append(f"tune={tune}")

        aq_mode = self.settings.get_setting('aq_mode')
        if aq_mode is not None:
            params.append(f"aq-mode={aq_mode}")

        enable_cdef = self.settings.get_setting('enable_cdef')
        if enable_cdef is not None:
            params.append(f"enable-cdef={int(enable_cdef)}")

        enable_restoration = self.settings.get_setting('enable_restoration')
        if enable_restoration is not None:
            params.append(f"enable-restoration={int(enable_restoration)}")

        enable_qm = self.settings.get_setting('enable_qm')
        if enable_qm is not None:
            params.append(f"enable-qm={int(enable_qm)}")

        enable_variance_boost = self.settings.get_setting('enable_variance_boost')
        if enable_variance_boost is not None:
            params.append(f"enable-variance-boost={int(enable_variance_boost)}")
        
        additional_svtav1_params = self.settings.get_setting('additional_svtav1_params')
        if additional_svtav1_params:
            params.append(additional_svtav1_params)

        if params:
            param_string = ":".join(params)
            stream_encoding += ['-svtav1-params', param_string]
        
        sc_detection = self.settings.get_setting('sc_detection')
        if sc_detection is not None:
            stream_encoding += ['-sc_detection', str(sc_detection)]
        
        gop_size = self.settings.get_setting('gop_size')
        if gop_size is not None:
            stream_encoding += ['-g', str(gop_size)]

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
                    "label": "Very fast - Fastest setting, biggest quality drop",
                },
                {
                    "value": "10",
                    "label": "Faster - Close to medium/fast quality, faster performance",
                },
                {
                    "value": "8",
                    "label": "Fast",
                },
                {
                    "value": "6",
                    "label": "Medium - Balanced performance and quality",
                },
                {
                    "value": "4",
                    "label": "Slow",
                },
                {
                    "value": "2",
                    "label": "Slower - Close to 'very slow' quality, faster performance",
                },
                {
                    "value": "1",
                    "label": "Very Slow - Best quality",
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

    def get_scd_form_settings(self):
        values = {
            "label": "Scene Change Detection (scd)",
            "sub_setting": True,
            "input_type": "number",
            "number_options": {
                "min": 0,
                "max": 1,
            },
        }
        if self.settings.get_setting('mode') in ['basic']:
            values["display"] = "hidden"
        return values

    def get_enable_overlays_form_settings(self):
        values = {
            "label": "Enable Overlays",
            "sub_setting": True,
            "input_type": "number",
            "number_options": {
                "min": 0,
                "max": 1,
            },
        }
        if self.settings.get_setting('mode') in ['basic']:
            values["display"] = "hidden"
        return values

    def get_tune_form_settings(self):
        values = {
            "label": "Tune",
            "sub_setting": True,
            "input_type": "number",
            "number_options": {
                "min": 0,
            },
        }
        if self.settings.get_setting('mode') in ['basic']:
            values["display"] = "hidden"
        return values

    def get_aq_mode_form_settings(self):
        values = {
            "label": "AQ Mode",
            "sub_setting": True,
            "input_type": "number",
            "number_options": {
                "min": 0,
            },
        }
        if self.settings.get_setting('mode') in ['basic']:
            values["display"] = "hidden"
        return values

    def get_enable_cdef_form_settings(self):
        values = {
            "label": "Enable CDEF",
            "sub_setting": True,
            "input_type": "checkbox",
        }
        if self.settings.get_setting('mode') in ['basic']:
            values["display"] = "hidden"
        return values

    def get_enable_restoration_form_settings(self):
        values = {
            "label": "Enable Restoration",
            "sub_setting": True,
            "input_type": "checkbox",
        }
        if self.settings.get_setting('mode') in ['basic']:
            values["display"] = "hidden"
        return values

    def get_enable_qm_form_settings(self):
        values = {
            "label": "Enable QM",
            "sub_setting": True,
            "input_type": "checkbox",
        }
        if self.settings.get_setting('mode') in ['basic']:
            values["display"] = "hidden"
        return values

    def get_enable_variance_boost_form_settings(self):
        values = {
            "label": "Enable Variance Boost",
            "sub_setting": True,
            "input_type": "checkbox",
        }
        if self.settings.get_setting('mode') in ['basic']:
            values["display"] = "hidden"
        return values

    def get_additional_svtav1_params_form_settings(self):
        values = {
            "label": "Additional SVT-AV1 Params",
            "sub_setting": True,
            "input_type": "text",
            "text_options": {
                "pattern": "^([A-Za-z0-9_-]+=.+)(:([A-Za-z0-9_-]+=.+))*$",
            }
        }
        if self.settings.get_setting('mode') in ['basic']:
            values["display"] = "hidden"
        return values

    def get_sc_detection_form_settings(self):
        values = {
            "label": "Scene Detection (-sc_detection for FFmpeg)",
            "sub_setting": True,
            "input_type": "number",
            "number_options": {
                "min": 0,
                "max": 1,
            },
        }
        if self.settings.get_setting('mode') in ['basic']:
            values["display"] = "hidden"
        return values

    def get_gop_size_form_settings(self):
        values = {
            "label": "GOP Size (-g for FFmpeg)",
            "sub_setting": True,
            "input_type": "number",
            "number_options": {
                "min": 1,
            },
        }
        if self.settings.get_setting('mode') in ['basic']:
            values["display"] = "hidden"
        return values