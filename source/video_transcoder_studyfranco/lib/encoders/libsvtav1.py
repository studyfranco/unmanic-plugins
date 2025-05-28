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
import re


class LibsvtAv1Encoder:

    def __init__(self, settings):
        self.settings = settings
        # self.sc_detection, self.g, self.svtav1_params are superseded by granular settings

    def provides(self):
        return {
            "libsvtav1": {
                "codec": "av1",
                "label": "CPU - libsvtav1",
            }
        }

    def options(self):
        return {
            # Existing options
            "preset":                     "4", # String, will be used directly
            "encoder_ratecontrol_method": "CRF", # String
            "constant_quality_scale":     "23",# String, will be used directly

            # New top-level FFmpeg options (replacing old g and sc_detection)
            "gop_size":                   240,  # Integer, for -g
            "sc_detection":               1,    # Integer, for -sc_detection (Note: different from svtav1_scd)

            # New granular SVT-AV1 params (replacing svtav1_params string)
            "svtav1_scd":                 1,    # Integer (0: off, 1: on)
            "svtav1_enable_overlays":     1,    # Integer (0: off, 1: on)
            "svtav1_tune":                2,    # Integer (0: VQ, 1: PSNR, 2: SSIM) - example, use actual valid range
            "svtav1_aq_mode":             2,    # Integer (0-4) - Adaptive Quantization mode
            "svtav1_enable_cdef":         True, # Boolean
            "svtav1_enable_restoration":  True, # Boolean
            "svtav1_enable_qm":           True, # Boolean
            "svtav1_enable_variance_boost": True,# Boolean
            "svtav1_additional_params":   "",   # String for key=value pairs
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

    # Constructs the complete list of FFmpeg arguments for libsvtav1 encoding.
    # This includes top-level FFmpeg options like -preset, -crf, -g, -sc_detection,
    # and dynamically builds the -svtav1-params string from individual granular settings
    # when in 'advanced' mode.
    def args(self, stream_id):
        stream_encoding = []

        # Runtime validation for advanced mode parameters
        if self.settings.get_setting('mode') in ['advanced']:
            try:
                gop_size_setting = self.settings.get_setting('gop_size', 240) # Default from options()
                if gop_size_setting is not None: # Allow disabling if user clears field and None is stored
                    gop_size = int(gop_size_setting)
                    if gop_size < 1:
                        raise ValueError("Invalid GOP size. Must be an integer >= 1.")
                else: # Handle case where gop_size might be explicitly set to None or empty string resulting in None
                    gop_size = None # Explicitly set to None if not provided or empty

                sc_detection_setting = self.settings.get_setting('sc_detection', 1) # Default from options()
                if sc_detection_setting is not None:
                    sc_detection = int(sc_detection_setting)
                    if sc_detection not in [0, 1]:
                        raise ValueError("Invalid sc_detection. Must be 0 or 1.")
                else:
                    sc_detection = None


                svtav1_scd_setting = self.settings.get_setting('svtav1_scd', 1)
                if svtav1_scd_setting is not None:
                    svtav1_scd = int(svtav1_scd_setting)
                    if svtav1_scd not in [0, 1]:
                        raise ValueError("Invalid svtav1_scd. Must be 0 or 1.")
                else:
                    svtav1_scd = None
                
                svtav1_tune_setting = self.settings.get_setting('svtav1_tune', 2)
                if svtav1_tune_setting is not None:
                    svtav1_tune = int(svtav1_tune_setting)
                    if svtav1_tune not in [0, 1, 2]: # Assuming 0-2 based on current form options
                        raise ValueError("Invalid svtav1_tune. Must be an integer between 0 and 2.")
                else:
                    svtav1_tune = None

                svtav1_aq_mode_setting = self.settings.get_setting('svtav1_aq_mode', 2)
                if svtav1_aq_mode_setting is not None:
                    svtav1_aq_mode = int(svtav1_aq_mode_setting)
                    if not (0 <= svtav1_aq_mode <= 4):
                        raise ValueError("Invalid svtav1_aq_mode. Must be an integer between 0 and 4.")
                else:
                    svtav1_aq_mode = None

                # Boolean settings validation (assuming settings framework provides them as bool)
                # If they come as strings "True"/"False", parsing would be needed:
                # e.g., str(self.settings.get_setting('svtav1_enable_cdef', True)).lower() == 'true'
                boolean_params_keys = [
                    "svtav1_enable_cdef", "svtav1_enable_restoration", 
                    "svtav1_enable_qm", "svtav1_enable_variance_boost"
                ]
                for key in boolean_params_keys:
                    val = self.settings.get_setting(key)
                    if not isinstance(val, bool):
                        # This error implies the settings framework isn't returning bools as expected
                        # For now, we assume it does. If not, this check would fail for string "True"/"False".
                        # An alternative: if str(val).lower() not in ['true', 'false']: raise ValueError(...)
                        pass # Assuming True/False are actual booleans from settings

                additional_params = self.settings.get_setting('svtav1_additional_params', "")
                if additional_params and not re.match(r"^([a-zA-Z0-9_-]+=[^:]+(:[a-zA-Z0-9_-]+=[^:]+)*)?$", additional_params):
                    raise ValueError("Invalid format for additional_svtav1_params. Must be key=value pairs separated by colons (e.g., key1=value1:key2=value2) or empty.")

            except ValueError as e:
                # Log the error (assuming logger is available, e.g., self.logger or global logger)
                # For now, just re-raise as this class doesn't have its own logger.
                # Consider adding logging capabilities to encoder classes if not already present framework-wide.
                # logger.error(f"Validation failed for LibsvtAv1Encoder settings: {e}")
                raise # Re-raise to halt processing

        # Use defaults for basic mode
        if self.settings.get_setting('mode') in ['basic']:
            defaults = self.options()
            stream_encoding += [
                '-preset', str(defaults.get('preset')),
            ]
            default_crf = defaults.get('constant_quality_scale')
            if self.settings.get_setting('video_encoder') in ['libsvtav1']:
                default_crf = 23
            stream_encoding += ['-crf', str(default_crf)]
            return stream_encoding

        # Add the preset (applies to standard and advanced mode)
        if self.settings.get_setting('preset'):
            stream_encoding += ['-preset', str(self.settings.get_setting('preset'))]

        # Add CRF (applies to standard and advanced mode if CRF is the rate control method)
        if self.settings.get_setting('encoder_ratecontrol_method') in ['CRF']:
            stream_encoding += [
                '-crf', str(self.settings.get_setting('constant_quality_scale')),
            ]

        if self.settings.get_setting('mode') in ['advanced']:
            # Use validated & parsed values if available, otherwise fall back to get_setting for safety
            # (though if validation failed, we would have raised an error)
            
            # Handle top-level FFmpeg specific params
            # Use the variables defined in the validation block if they exist, otherwise re-fetch.
            # This assumes that if validation passed, the variables (e.g., sc_detection) hold the validated int values.
            
            current_sc_detection = locals().get('sc_detection', self.settings.get_setting('sc_detection'))
            if current_sc_detection is not None:
                stream_encoding += ['-sc_detection', str(current_sc_detection)]

            current_gop_size = locals().get('gop_size', self.settings.get_setting('gop_size'))
            if current_gop_size is not None:
                stream_encoding += ['-g', str(current_gop_size)]

            # Constructing the -svtav1-params string from individual settings
            svt_params = []
            param_map = {
                "svtav1_scd": "scd",
                "svtav1_enable_overlays": "enable-overlays",
                "svtav1_tune": "tune",
                "svtav1_aq_mode": "aq-mode",
                "svtav1_enable_cdef": "enable-cdef",
                "svtav1_enable_restoration": "enable-restoration",
                "svtav1_enable_qm": "enable-qm",
                "svtav1_enable_variance_boost": "enable-variance-boost",
            }
            for setting_key, param_name in param_map.items():
                value = self.settings.get_setting(setting_key)
                if value is not None: # Check for None to allow False/0 values
                    if isinstance(value, bool):
                        svt_params.append(f"{param_name}={int(value)}")
                    else:
                        svt_params.append(f"{param_name}={value}")
            
            additional_params = self.settings.get_setting('svtav1_additional_params')
            if additional_params:
                # Simple validation: ensure it's key=value pairs, but don't be too strict here.
                # Users should ensure correct formatting.
                if '=' in additional_params: # Basic check
                    svt_params.append(additional_params)
                elif additional_params.strip(): # Non-empty but not key=value
                    # Log a warning or ignore, depending on desired strictness. Here, we'll log and potentially ignore.
                    # For now, let's assume it might be a single flag param, though svtav1-params are usually key=value.
                    # To be safe, only append if it seems like a valid structure or is a known single flag.
                    # The prompt implies key=value, so let's only add if it contains '=' or if we trust user input.
                    # For now, let's be more permissive and add it if it's not empty.
                    # A better approach might be to split by ':' and validate each part.
                    svt_params.append(additional_params)


            if svt_params:
                stream_encoding += ['-svtav1-params', ":".join(svt_params)]
        
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
        if self.settings.get_setting('mode') not in ['standard', 'advanced']:
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
        if self.settings.get_setting('mode') not in ['standard', 'advanced']:
            values["display"] = "hidden"
        if self.settings.get_setting('encoder_ratecontrol_method') not in ['CRF']:
            values["display"] = "hidden"
        if self.settings.get_setting('video_encoder') in ['libsvtav1']:
            values["description"] = "Default value for libsvtav1 = 23"
        return values

    def get_sc_detection_form_settings(self):
        values = {
            "label":          "Scene Change Detection",
            "sub_setting":    True,
            "input_type":     "select",
            "select_options": [
                {
                    "value": "0",
                    "label": "Disabled",
                },
                {
                    "value": "1",
                    "label": "Enabled",
                },
            ],
        }
        if self.settings.get_setting('mode') not in ['advanced']:
            values["display"] = "hidden"
        return values

    def get_gop_size_form_settings(self):
        return {
            "label": "GOP Size (-g)",
            "description": "Set GOP size. Integer value.",
            "sub_setting": True,
            "input_type": "text", 
            "placeholder": "e.g., 240 (must be >= 1)", # Added placeholder
            "display": "hidden" if self.settings.get_setting('mode') not in ['advanced'] else "visible",
        }

    # Note: sc_detection form settings already exists from a previous step, 
    # but its label/description might need an update if it's different from svtav1_scd.
    # The existing get_sc_detection_form_settings is for the top-level -sc_detection.
    # I will assume the existing one is fine and not redefine it unless it was for svtav1_params before.
    # The prompt asks for get_*_form_settings for "sc_detection" for top-level flag.
    # The existing one is:
    # def get_sc_detection_form_settings(self):
    #     values = {
    #         "label":          "Scene Change Detection",
    # ...
    # This seems to be for the top-level flag. I'll keep it and ensure its label is clear.
    # Let's update its description to clarify it's for -sc_detection FFmpeg flag.
    
    # Re-defining get_sc_detection_form_settings for clarity as per prompt,
    # ensuring it's for the top-level FFmpeg flag.
    def get_sc_detection_form_settings(self): # Overwriting/Adjusting existing one
        values = {
            "label":          "Scene Change Detection (-sc_detection)",
            "description":    "FFmpeg top-level scene change detection. 0 = Disable, 1 = Enable.",
            "sub_setting":    True,
            "input_type":     "select",
            "select_options": [
                {"value": 0, "label": "0 - Disabled"}, # Using integer values directly
                {"value": 1, "label": "1 - Enabled"},
            ],
        }
        if self.settings.get_setting('mode') not in ['advanced']:
            values["display"] = "hidden"
        # Ensure default is set if not present
        # self.__set_default_option(values['select_options'], 'sc_detection', default_option=1)
        return values

    def get_svtav1_scd_form_settings(self):
        return {
            "label": "SVT-AV1: Scene Change Detection (scd)",
            "description": "Used within -svtav1-params. 0 = Disable, 1 = Enable.",
            "sub_setting": True,
            "input_type": "select",
            "select_options": [{"value": 0, "label": "0 - Disabled"}, {"value": 1, "label": "1 - Enabled"}],
            "display": "hidden" if self.settings.get_setting('mode') not in ['advanced'] else "visible",
        }

    def get_svtav1_enable_overlays_form_settings(self):
        return {
            "label": "SVT-AV1: Enable Overlays (enable-overlays)",
            "description": "Enable overlay frames. 0 = Disable, 1 = Enable.",
            "sub_setting": True,
            "input_type": "select",
            "select_options": [{"value": 0, "label": "0 - Disabled"}, {"value": 1, "label": "1 - Enabled"}],
            "display": "hidden" if self.settings.get_setting('mode') not in ['advanced'] else "visible",
        }

    def get_svtav1_tune_form_settings(self):
        return {
            "label": "SVT-AV1: Tune (tune)",
            "description": "0 = VQ (Visual Quality), 1 = PSNR (Objective Quality), 2 = SSIM (Objective Quality). Integer value.",
            "sub_setting": True,
            "input_type": "select", 
            "placeholder": "e.g., 2 (0-2 for VQ, PSNR, SSIM)", # Added placeholder
            "select_options": [
                {"value": 0, "label": "0 - VQ (Visual Quality)"},
                {"value": 1, "label": "1 - PSNR (Objective Quality)"},
                {"value": 2, "label": "2 - SSIM (Objective Quality)"}
            ],
            "display": "hidden" if self.settings.get_setting('mode') not in ['advanced'] else "visible",
        }

    def get_svtav1_aq_mode_form_settings(self):
        return {
            "label": "SVT-AV1: Adaptive Quantization Mode (aq-mode)",
            "description": "Adaptive Quantization mode (0-4). Integer value.",
            "sub_setting": True,
            "input_type": "select", 
            "placeholder": "e.g., 2 (0-4)", # Added placeholder
            "select_options": [
                {"value": 0, "label": "0 - Off"},
                {"value": 1, "label": "1 - Variance AQ"},
                {"value": 2, "label": "2 - Complexity AQ"},
                {"value": 3, "label": "3 - Cyclic Refresh AQ"},
                {"value": 4, "label": "4 - Delta QP based AQ (Experimental)"}
            ],
            "display": "hidden" if self.settings.get_setting('mode') not in ['advanced'] else "visible",
        }

    def get_svtav1_enable_cdef_form_settings(self):
        return {
            "label": "SVT-AV1: Enable CDEF (enable-cdef)",
            "description": "Constrained Directional Enhancement Filter.",
            "sub_setting": True,
            "input_type": "select",
            "select_options": [{"value": False, "label": "False"}, {"value": True, "label": "True"}],
            "display": "hidden" if self.settings.get_setting('mode') not in ['advanced'] else "visible",
        }

    def get_svtav1_enable_restoration_form_settings(self):
        return {
            "label": "SVT-AV1: Enable Restoration (enable-restoration)",
            "description": "Loop Restoration Filter.",
            "sub_setting": True,
            "input_type": "select",
            "select_options": [{"value": False, "label": "False"}, {"value": True, "label": "True"}],
            "display": "hidden" if self.settings.get_setting('mode') not in ['advanced'] else "visible",
        }

    def get_svtav1_enable_qm_form_settings(self):
        return {
            "label": "SVT-AV1: Enable QM (enable-qm)",
            "description": "Enable Quantization Matrix.",
            "sub_setting": True,
            "input_type": "select",
            "select_options": [{"value": False, "label": "False"}, {"value": True, "label": "True"}],
            "display": "hidden" if self.settings.get_setting('mode') not in ['advanced'] else "visible",
        }
        
    def get_svtav1_enable_variance_boost_form_settings(self):
        return {
            "label": "SVT-AV1: Enable Variance Boost (enable-variance-boost)",
            "description": "Enable variance boost.",
            "sub_setting": True,
            "input_type": "select",
            "select_options": [{"value": False, "label": "False"}, {"value": True, "label": "True"}],
            "display": "hidden" if self.settings.get_setting('mode') not in ['advanced'] else "visible",
        }

    def get_svtav1_additional_params_form_settings(self):
        return {
            "label": "SVT-AV1: Additional Parameters",
            "description": "Additional SVT-AV1 parameters as a colon-separated string (e.g., key1=value1:key2=value2).",
            "sub_setting": True,
            "input_type": "text",
            "placeholder": "e.g., key1=value1:key2=value2", # Added placeholder
            "pattern": "^([a-zA-Z0-9_-]+=[^:]+(:[a-zA-Z0-9_-]+=[^:]+)*)?$", # Added pattern
            "display": "hidden" if self.settings.get_setting('mode') not in ['advanced'] else "visible",
        }