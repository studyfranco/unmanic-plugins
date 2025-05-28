#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright:
#   Copyright (C) 2021 Josh Sunnex <josh@sunnex.com.au>
#   Copyright (C) 2023 studyfranco <studyfranco@gmail.com> 
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

import logging
import os
import re
import subprocess
import shutil
import tempfile
import uuid # For unique task ID if not provided

from video_transcoder.lib import plugin_stream_mapper
from video_transcoder.lib.ffmpeg import Parser, Probe
from video_transcoder.lib.global_settings import GlobalSettings
from video_transcoder.lib.encoders.libx import LibxEncoder
from video_transcoder.lib.encoders.qsv import QsvEncoder
from video_transcoder.lib.encoders.vaapi import VaapiEncoder
from video_transcoder.lib.encoders.nvenc import NvencEncoder
from video_transcoder.lib.encoders.libsvtav1 import LibsvtAv1Encoder

from unmanic.libs.unplugins.settings import PluginSettings
from unmanic.libs.directoryinfo import UnmanicDirectoryInfo

# Configure plugin logger
logger = logging.getLogger("Unmanic.Plugin.video_transcoder")


class Settings(PluginSettings):

    def __init__(self, *args, **kwargs):
        super(Settings, self).__init__(*args, **kwargs)
        self.settings = self.__build_settings_object()
        self.encoders = self.__available_encoders()
        self.global_settings = GlobalSettings(self)
        self.form_settings = self.__build_form_settings_object()

    def __build_form_settings_object(self):
        """
        Build a form input config for all the plugin settings
        This input changes dynamically based on the encoder selected

        :return:
        """
        return_values = {}
        for setting in self.settings:
            # Fetch currently configured encoder
            # This should be done every loop as some settings my change this value
            selected_encoder = self.encoders.get(self.get_setting('video_encoder'))
            # Disable form by default
            setting_form_settings = {
                "display": "hidden"
            }
            # First check if selected_encoder object has form settings method
            if hasattr(selected_encoder, 'get_{}_form_settings'.format(setting)):
                getter = getattr(selected_encoder, 'get_{}_form_settings'.format(setting))
                if callable(getter):
                    setting_form_settings = getter()
            # Next check if global_settings object has form settings method
            elif hasattr(self.global_settings, 'get_{}_form_settings'.format(setting)):
                getter = getattr(self.global_settings, 'get_{}_form_settings'.format(setting))
                if callable(getter):
                    setting_form_settings = getter()
            # Apply form settings
            return_values[setting] = setting_form_settings
        return return_values

    def __available_encoders(self):
        return_encoders = {}
        encoder_libs = [
            LibxEncoder,
            QsvEncoder,
            VaapiEncoder,
            NvencEncoder,
            LibsvtAv1Encoder,
        ]
        for encoder_class in encoder_libs:
            encoder_lib = encoder_class(self)
            for encoder in encoder_lib.provides():
                return_encoders[encoder] = encoder_lib
        return return_encoders

    def __encoder_settings_object(self):
        """
        Returns a list of encoder settings for FFmpeg

        :return:
        """
        # Initial options forces the order they appear in the settings list
        # We need this because some encoders have settings that
        # Fetch all encoder settings from encoder libs
        libx_options = LibxEncoder(self.settings).options()
        qsv_options = QsvEncoder(self.settings).options()
        vaapi_options = VaapiEncoder(self.settings).options()
        nvenc_options = NvencEncoder(self.settings).options()
        libsvtav1_options = LibsvtAv1Encoder(self.settings).options()
        return {
            **libx_options,
            **qsv_options,
            **vaapi_options,
            **nvenc_options,
            **libsvtav1_options, # Ensure this is correctly indented
        }

    def __build_settings_object(self):
        # Global and main config options
        global_settings = GlobalSettings.options()
        main_options = global_settings.get('main_options')
        encoder_selection = global_settings.get('encoder_selection')
        encoder_settings = self.__encoder_settings_object()
        advanced_input_options = global_settings.get('advanced_input_options')
        output_settings = global_settings.get('output_settings')
        filter_settings = global_settings.get('filter_settings')
        return {
            **main_options,
            **encoder_selection,
            **encoder_settings,
            **advanced_input_options,
            **output_settings,
            **filter_settings,
        }


def file_marked_as_force_transcoded(path):
    directory_info = UnmanicDirectoryInfo(os.path.dirname(path))
    try:
        has_been_force_transcoded = directory_info.get('video_transcoder', os.path.basename(path))
    except NoSectionError as e:
        has_been_force_transcoded = ''
    except NoOptionError as e:
        has_been_force_transcoded = ''
    except Exception as e:
        logger.debug("Unknown exception %s.", e)
        has_been_force_transcoded = ''

    if has_been_force_transcoded == 'force_transcoded':
        # This file has already been force transcoded
        return True

    # Default to...
    return False


def on_library_management_file_test(data):
    """
    Runner function - enables additional actions during the library management file tests.

    The 'data' object argument includes:
        library_id                      - The library that the current task is associated with
        path                            - String containing the full path to the file being tested.
        issues                          - List of currently found issues for not processing the file.
        add_file_to_pending_tasks       - Boolean, is the file currently marked to be added to the queue for processing.
        priority_score                  - Integer, an additional score that can be added to set the position of the new task in the task queue.
        shared_info                     - Dictionary, information provided by previous plugin runners. This can be appended to for subsequent runners.

    :param data:
    :return:

    """

    # Get settings
    settings = Settings(library_id=data.get('library_id'))

    # Get the path to the file
    abspath = data.get('path')

    # Get file probe
    probe = Probe.init_probe(data, logger, allowed_mimetypes=['video'])
    if not probe:
        # File not able to be probed by ffprobe
        return

    # Get stream mapper
    mapper = plugin_stream_mapper.PluginStreamMapper()
    mapper.set_default_values(settings, abspath, probe)

    # Check if this file needs to be processed
    if mapper.streams_need_processing():
        if file_marked_as_force_transcoded(abspath) and mapper.forced_encode:
            logger.debug(
                "File '%s' has been previously marked as forced transcoded. Plugin found streams require processing, but will ignore this file.",
                abspath)
            return
        # Mark this file to be added to the pending tasks
        data['add_file_to_pending_tasks'] = True
        logger.debug("File '%s' should be added to task list. Plugin found streams require processing.", abspath)
    else:
        logger.debug("File '%s' does not contain streams require processing.", abspath)


def on_worker_process(data):
    """
    Runner function - implements a demux-transcode-remux workflow.
    """
    # Initialization
    logger.info("Starting demux-transcode-remux process for file: %s", data.get('file_in'))
    data['exec_command'] = []
    data['command_progress_parser'] = None 
    data['repeat'] = False

    settings = Settings(library_id=data.get('library_id'))
    abspath = data.get('file_in')

    original_probe = Probe(logger, allowed_mimetypes=['video'])
    if not original_probe.file(abspath):
        logger.error("Failed to probe original file: %s", abspath)
        data['worker_log'].append("Error: Failed to probe original file.")
        return # Stop processing if initial probe fails

    ffmpeg_parser = Parser(logger)

    # Nested helper function for HDR metadata parsing
    def parse_mastering_display_metadata(metadata_str):
        patterns = {
            'R_x': r"R\(x=([0-9\.]+)", 'R_y': r"R\(x=[0-9\.]+,y=([0-9\.]+)\)",
            'G_x': r"G\(x=([0-9\.]+)", 'G_y': r"G\(x=[0-9\.]+,y=([0-9\.]+)\)",
            'B_x': r"B\(x=([0-9\.]+)", 'B_y': r"B\(x=[0-9\.]+,y=([0-9\.]+)\)",
            'WP_x': r"WP\(x=([0-9\.]+)", 'WP_y': r"WP\(x=[0-9\.]+,y=([0-9\.]+)\)",
            'min_L': r"L\(min=([0-9\.]+)", 'max_L': r"L\(min=[0-9\.]+,max=([0-9\.]+)\)",
        }
        values = {}
        for key, pattern in patterns.items():
            match = re.search(pattern, metadata_str)
            if match: values[key] = match.group(1)
            else:
                logger.warning(f"Could not parse {key} from mastering display metadata: {metadata_str}")
                return metadata_str # Return original on partial failure, to allow potential direct passthrough
        
        try:
            g_x_scaled = int(float(values.get('G_x', '0')) * 50000)
            g_y_scaled = int(float(values.get('G_y', '0')) * 50000)
            b_x_scaled = int(float(values.get('B_x', '0')) * 50000)
            b_y_scaled = int(float(values.get('B_y', '0')) * 50000)
            r_x_scaled = int(float(values.get('R_x', '0')) * 50000)
            r_y_scaled = int(float(values.get('R_y', '0')) * 50000)
            wp_x_scaled = int(float(values.get('WP_x', '0')) * 50000)
            wp_y_scaled = int(float(values.get('WP_y', '0')) * 50000)
            max_l_scaled = int(float(values.get('max_L', '0')) * 10000)
            min_l_scaled = int(float(values.get('min_L', '0')) * 10000)
            
            return f"G({g_x_scaled},{g_y_scaled})B({b_x_scaled},{b_y_scaled})R({r_x_scaled},{r_y_scaled})WP({wp_x_scaled},{wp_y_scaled})L({max_l_scaled},{min_l_scaled})"
        except ValueError as e:
            logger.error(f"ValueError during scaling of mastering display metadata: {e}. Original string: {metadata_str}")
            return metadata_str # Fallback to original string if scaling fails

    # HDR Metadata Detection
    hdr_metadata = {}
    probe_streams = original_probe.get('streams', [])
    for stream in probe_streams:
        if stream.get('codec_type') == 'video':
            color_space = stream.get('color_space')
            color_primaries = stream.get('color_primaries')
            color_transfer = stream.get('color_transfer')
            side_data_list = stream.get('side_data_list', [])
            for side_data in side_data_list:
                if side_data.get('side_data_type') == 'Mastering display metadata':
                    raw_master_display_str = side_data.get('mastering_display_metadata')
                    if raw_master_display_str:
                        hdr_metadata['master_display_data_string'] = parse_mastering_display_metadata(raw_master_display_str)
                    if side_data.get('color_primaries'): color_primaries = side_data.get('color_primaries')[0]
                    if side_data.get('color_transfer'): color_transfer = side_data.get('color_transfer')[0]
                    if side_data.get('color_space'): color_space = side_data.get('color_space')[0]
                elif side_data.get('side_data_type') == 'Content light level metadata':
                    hdr_metadata['max_cll_data_string'] = f"{side_data.get('max_content', 0)},{side_data.get('max_frame_average_light_level', 0)}"
            if color_space: hdr_metadata['colorspace'] = color_space
            if color_primaries: hdr_metadata['color_primaries'] = color_primaries
            if color_transfer: hdr_metadata['color_trc'] = color_transfer
            if hdr_metadata:
                logger.info("Detected HDR metadata: %s", hdr_metadata)
                break
    
    final_mkv_out = os.path.splitext(data.get('file_out'))[0] + ".mkv"
    data['file_out'] = final_mkv_out
    logger.info("Final output file will be: %s", final_mkv_out)

    task_id = data.get('task_id', str(uuid.uuid4()))
    temp_dir_path = os.path.join(tempfile.gettempdir(), f"unmanic_vt_{task_id}")
    
    try:
        os.makedirs(temp_dir_path, exist_ok=True)
        logger.info("Created temporary directory: %s", temp_dir_path)

        # --- Demux Video (mkvmerge) ---
        logger.info("Starting video demuxing with mkvmerge.")
        temp_video_track = os.path.join(temp_dir_path, "video_track.mkv")
        mkvmerge_demux_cmd = ['mkvmerge', '-o', temp_video_track, '--no-audio', '--no-subtitles', 
                              '--no-chapters', '--no-attachments', '--no-track-tags', 
                              '--video-tracks', '0', abspath]
        logger.info("Executing mkvmerge demux command: %s", " ".join(mkvmerge_demux_cmd))
        try:
            demux_result = subprocess.run(mkvmerge_demux_cmd, capture_output=True, text=True, check=True, encoding='utf-8')
            logger.info("mkvmerge demux stdout: %s", demux_result.stdout)
            data['worker_log'].append("mkvmerge demux stdout: " + demux_result.stdout)
            if demux_result.stderr:
                logger.info("mkvmerge demux stderr (warnings/info): %s", demux_result.stderr)
                data['worker_log'].append("mkvmerge demux stderr: " + demux_result.stderr)
        except subprocess.CalledProcessError as e:
            logger.error(f"mkvmerge demux failed. Return code: {e.returncode}\nstdout: {e.stdout}\nstderr: {e.stderr}")
            data['worker_log'].append(f"Error: mkvmerge demux failed. stderr: {e.stderr} stdout: {e.stdout}")
            raise

        # --- Transcode Video (ffmpeg) ---
        logger.info("Starting video transcoding with ffmpeg.")
        temp_av1_track = os.path.join(temp_dir_path, "video_av1.mkv")

        mapper = plugin_stream_mapper.PluginStreamMapper(hdr_metadata=hdr_metadata)
        
        transcode_input_probe = Probe(logger, allowed_mimetypes=['video'])
        if not transcode_input_probe.file(temp_video_track):
            logger.error("Failed to probe temporary video track for transcoding: %s", temp_video_track)
            data['worker_log'].append("Error: Failed to probe temp video track for transcoding.")
            raise Exception("Probe failed for temp video track")
        
        # Settings for mapper: 'abspath' is the current input (temp_video_track), 'probe' is for this input.
        mapper.set_default_values(settings, temp_video_track, transcode_input_probe)
        mapper.set_input_file(temp_video_track) 
        mapper.set_output_file(temp_av1_track) 
        
        ffmpeg_args = mapper.get_ffmpeg_args()
        ffmpeg_cmd = ['ffmpeg'] + ffmpeg_args
        logger.info("Executing ffmpeg transcode command: %s", " ".join(ffmpeg_cmd))
        
        ffmpeg_parser.set_probe(transcode_input_probe)

        try:
            process = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True, encoding='utf-8', bufsize=1)
            for line in iter(process.stdout.readline, ''):
                line = line.strip()
                if line:
                    logger.debug("FFMPEG: %s", line)
                    data['worker_log'].append(line)
                    progress = ffmpeg_parser.parse_progress(line)
                    if progress and 'percent' in progress:
                        try:
                            percent_val = float(progress['percent'])
                            logger.info("FFMPEG progress: {:.2f}%".format(percent_val))
                        except ValueError:
                            logger.info("FFMPEG progress: {}".format(progress['percent']))
            process.stdout.close()
            process.wait()
            if process.returncode != 0:
                logger.error(f"FFmpeg transcoding failed with return code: {process.returncode}. Check worker log for details.")
                raise subprocess.CalledProcessError(process.returncode, ffmpeg_cmd, output=None, stderr="FFmpeg failed. Check logs in worker_log.")
        except Exception as e: 
            logger.error(f"Exception during ffmpeg transcoding: {str(e)}", exc_info=True)
            if isinstance(e, subprocess.CalledProcessError) and hasattr(e, 'output') and e.output:
                 data['worker_log'].append("FFMPEG Error Output (from exception): " + str(e.output))
            raise 

        # --- Remux Final MKV (mkvmerge) ---
        logger.info("Starting final remuxing with mkvmerge.")
        mkvmerge_remux_cmd = ['mkvmerge', '-o', final_mkv_out,
                              '--video-tracks', '0', temp_av1_track, 
                              '--audio-tracks', 'all', 
                              '--subtitle-tracks', 'all', 
                              '--attachments', 'all', 
                              '--chapters', 
                              abspath]
        logger.info("Executing mkvmerge remux command: %s", " ".join(mkvmerge_remux_cmd))
        try:
            remux_result = subprocess.run(mkvmerge_remux_cmd, capture_output=True, text=True, check=True, encoding='utf-8')
            logger.info("mkvmerge remux stdout: %s", remux_result.stdout)
            data['worker_log'].append("mkvmerge remux stdout: " + remux_result.stdout)
            if remux_result.stderr:
                logger.info("mkvmerge remux stderr (warnings/info): %s", remux_result.stderr)
                data['worker_log'].append("mkvmerge remux stderr: " + remux_result.stderr)
        except subprocess.CalledProcessError as e:
            logger.error(f"mkvmerge remux failed. Return code: {e.returncode}\nstdout: {e.stdout}\nstderr: {e.stderr}")
            data['worker_log'].append(f"Error: mkvmerge remux failed. stderr: {e.stderr} stdout: {e.stdout}")
            raise

        logger.info("Demux-transcode-remux process completed successfully for: %s", final_mkv_out)

    except Exception as e:
        logger.error(f"An error occurred during the demux-transcode-remux process: {str(e)}", exc_info=True)
        data['worker_log'].append("Fatal error in processing: " + str(e))
        # Re-raising the exception ensures Unmanic handles it as a task failure.
        # The 'finally' block will execute for cleanup.
        raise 
    finally:
        # Ensure temp_dir_path is defined even if an early error occurred before its assignment
        if 'temp_dir_path' in locals() and os.path.exists(temp_dir_path):
            logger.info("Cleaning up temporary directory: %s", temp_dir_path)
            shutil.rmtree(temp_dir_path, ignore_errors=True)
            logger.info("Temporary directory cleanup finished.")
        else:
            logger.info("Temporary directory was not created or already cleaned up.")
            
    return # End of on_worker_process

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
    # Get settings
    settings = Settings(library_id=data.get('library_id'))

    # Get the original file's absolute path
    original_source_path = data.get('source_data', {}).get('abspath')
    if not original_source_path:
        logger.error("Provided 'source_data' is missing the source file abspath data.")
        return

    # Mark the source file to be ignored on subsequent scans if 'force_transcode' was enabled
    if settings.get_setting('force_transcode'):
        cache_directory = os.path.dirname(data.get('final_cache_path'))
        if os.path.exists(os.path.join(cache_directory, '.force_transcode')):
            directory_info = UnmanicDirectoryInfo(os.path.dirname(original_source_path))
            directory_info.set('video_transcoder', os.path.basename(original_source_path), 'force_transcoded')
            directory_info.save()
            logger.debug("Ignore on next scan written for '%s'.", original_source_path)