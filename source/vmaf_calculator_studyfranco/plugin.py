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
import multiprocessing
from os import path
import shutil
import json

from unmanic.libs.directoryinfo import UnmanicDirectoryInfo
from unmanic.libs.unplugins.settings import PluginSettings

# Configure plugin logger
logger = logging.getLogger("Unmanic.Plugin.vmaf_calculator_studyfranco")


class Settings(PluginSettings):
    settings = {}

def launch_cmdExt_no_test(cmd):
    from subprocess import Popen, PIPE
    cmdDownload = Popen(cmd, stdout=PIPE, stderr=PIPE)
    stdout, stderror = cmdDownload.communicate()
    exitCode = cmdDownload.returncode
    return stdout, stderror, exitCode

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
    data['file_out'] = data.get('file_in')
    
    stdout, stderror, exitCode = launch_cmdExt_no_test(['mkvmerge', "-o", path.join(path.dirname(data.get('file_out')),'source.mkv'), "-A", "-S", "-M", "-B", "--no-chapters", "--no-attachments", "--no-global-tags", data.get('original_file_path')])
    
    stdout, stderror, exitCode = launch_cmdExt_no_test(['mkvmerge', "-o", path.join(path.dirname(data.get('file_out')),'converted.mkv'), "-A", "-S", "-M", "-B", "--no-chapters", "--no-attachments", "--no-global-tags", data.get('file_in')])
    
    # Apply ffmpeg args to command
    data['exec_command'] = ['ffmpeg', '-i', path.join(path.dirname(data.get('file_out')),'converted.mkv'), '-i', path.join(path.dirname(data.get('file_out')),'source.mkv'), '-lavfi', f"libvmaf=log_path='{path.join(path.dirname(data.get('file_in')),path.basename(data.get('original_file_path')))}_vmaf.log':log_fmt=json:n_threads={multiprocessing.cpu_count()}", '-f', 'null', '-an', '-sn', '-']

    return data

def on_postprocessor_task_results(data):
    """
    Runner function - provides a means for additional postprocessor functions based on the task success.

    The 'data' object argument includes:
        final_cache_path                - The path to the final cache file that was then used as the source for all destination files.
        library_id                      - The library that the current task is associated with.
        task_processing_success         - Boolean, did all task processes complete successfully.
        file_move_processes_success     - Boolean, did all postprocessor movement tasks complete successfully.
        destination_files               - List containing all file paths created by postprocessor file movements.
        source_data                     - Dictionary containing data pertaining to the original source file.

    :param data:
    :return:

    """
    try:
        with open(path.join(path.dirname(data.get('final_cache_path')),path.basename(data.get('source_data', {}).get('abspath')))+"_vmaf.log") as f:
            vmaf = json.load(f)
        
        shutil.move(path.join(path.dirname(data.get('final_cache_path')),path.basename(data.get('source_data', {}).get('abspath')))+"_vmaf.log", path.join(path.dirname(data.get('destination_files')[0]), path.basename(data.get('source_data', {}).get('abspath'))+f"_vmaf__{vmaf['pooled_metrics']['vmaf']['mean']}__.log"))
    except Exception as e:
        logger.error("Failed to move VMAF log file: {}".format(e))