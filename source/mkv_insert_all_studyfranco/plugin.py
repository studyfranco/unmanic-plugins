#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
    Written by:               Josh.5 <jsunnex@gmail.com>
    Date:                     22 Aug 2021, (9:55 PM)

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
import logging
import os

from unmanic.libs.directoryinfo import UnmanicDirectoryInfo
from unmanic.libs.unplugins.settings import PluginSettings

# Configure plugin logger
logger = logging.getLogger("Unmanic.Plugin.mkv_insert_all_studyfranco")


class Settings(PluginSettings):
    settings = {
        "louis" : False,
        "keep_only_language": False,
        "keep_only_language_values": "",
        "remove_sub_language_not_keep": False,
    }
    
    def __init__(self, *args, **kwargs):
        super(Settings, self).__init__(*args, **kwargs)
        self.form_settings = {
            "louis":           {
                "label": "Louis parametres",
            },
            "keep_only_language":  {
                "label": "Keep only this languages",
            },
            "keep_only_language_values": self.__set_language_to_keep(),
            "remove_sub_language_not_keep": self.__set_remove_sub_language_not_keep(),
        }

    def __set_language_to_keep(self):
        values = {
            "label":      "List languages to keep",
            "description": "List the languages to keep in the format iso 2 letter: fr,en,de,... (comma separated).",
            "sub_setting": True,
            "input_type":  "textarea",
        }
        if not self.get_setting('keep_only_language'):
            values["display"] = 'hidden'
        return values

    def __set_remove_sub_language_not_keep(self):
        values = {
            "label": "Remove subtitles not in the language to keep",
            "description": "Remove the subtitles not in the language to keep. If you don't use this option, the subtitles not in the language to keep will be kept with the original language.",
            "sub_setting": True,
        }
        if not self.get_setting('keep_only_language'):
            values["display"] = 'hidden'
        return values

def on_worker_process(data):
    """
    Runner function - enables additional configured processing jobs during the worker stages of a task.

    The 'data' object argument includes:
        worker_log              - Array, the log lines that are being tailed by the frontend. Can be left empty.
        library_id              - Number, the library that the current task is associated with.
        exec_command            - Array, a subprocess command that Unmanic should execute. Can be empty.
        command_progress_parser - Function, a function that Unmanic can use to parse the STDOUT of the command to collect progress stats. Can be empty.
        file_in                 - String, the source file to be processed by the command.
        file_out                - String, the destination that the command should output (may be the same as the file_in if necessary).
        original_file_path      - String, the absolute path to the original file.
        repeat                  - Boolean, should this runner be executed again once completed with the same variables.

    :param data:
    :return:

    """
    
    # Default to no FFMPEG command required. This prevents the FFMPEG command from running if it is not required
    data['exec_command'] = []
    data['repeat'] = False
    
    settings = Settings(library_id=data.get('library_id'))
    # Apply ffmpeg args to command
    if settings.get_setting('louis'):
        activate_louis = "True"
    else:
        activate_louis = "False"
        
    if settings.get_setting('remove_sub_language_not_keep'):
        remove_sub_language_not_keep = "True"
    else:
        remove_sub_language_not_keep = "False"
        
    data['exec_command'] = ['python3', "/config/.unmanic/plugins/mkv_insert_studyfranco/lib/main.py", "-o", data.get('file_out'), "-s", data.get('original_file_path'), "-f", data.get('file_in'), "-l", activate_louis, "--pwd", "/config/.unmanic/plugins/mkv_insert_studyfranco", "--tmp", os.path.dirname(data.get('file_out')), "--language_keep", settings.get_setting('keep_only_language_values'), "--remove_sub_language_not_keep", remove_sub_language_not_keep]

    return data
