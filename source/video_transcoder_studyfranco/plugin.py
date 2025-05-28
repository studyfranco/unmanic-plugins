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

# --- Helper Functions for Demux-Transcode-Remux Workflow ---

# Helper function to extract video track using mkvmerge
def _demux(original_input_file, temp_dir, logger_instance):
    """Helper function to demux the video track."""
    logger_instance.info("Starting demux for %s", original_input_file)
    output_video_track = os.path.join(temp_dir, "video_track.mkv")
    cmd = ['mkvmerge', '-o', output_video_track, '--no-audio', '--no-subtitles', 
           '--no-chapters', '--no-attachments', '--no-track-tags', 
           '--video-tracks', '0', original_input_file]
    logger_instance.info("Executing demux command: %s", " ".join(cmd))
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False, encoding='utf-8', errors='replace')
        if result.returncode != 0:
            logger_instance.error("Demuxing failed for %s. Return code: %s", original_input_file, result.returncode)
            logger_instance.error("mkvmerge stderr: %s", result.stderr)
            logger_instance.error("mkvmerge stdout: %s", result.stdout)
            return None
        logger_instance.info("Demuxing successful, mkvmerge stdout: %s", result.stdout)
        if result.stderr: # mkvmerge often outputs warnings/info to stderr
            logger_instance.info("mkvmerge stderr (demux): %s", result.stderr)
        return output_video_track
    except Exception as e:
        logger_instance.error("Exception during demuxing: %s", str(e), exc_info=True)
        return None

# Helper function to transcode the demuxed video track using ffmpeg
def _transcode(input_file_to_transcode, temp_dir, settings_obj, original_probe_obj, 
               hdr_metadata_dict, ffmpeg_parser_obj, logger_instance, worker_log_list):
    """Helper function to transcode the video track."""
    logger_instance.info("Starting transcode for %s", input_file_to_transcode)
    output_av1_track = os.path.join(temp_dir, "video_av1.mkv")

    mapper = plugin_stream_mapper.PluginStreamMapper(hdr_metadata=hdr_metadata_dict)
    
    # Use original file's path and probe for set_default_values for decisions based on original file context
    original_file_path = original_probe_obj.get_probe().get('format', {}).get('filename', input_file_to_transcode)
    mapper.set_default_values(settings_obj, original_file_path, original_probe_obj)
    
    # Set the actual input and output for the ffmpeg command
    mapper.set_input_file(input_file_to_transcode)
    mapper.set_output_file(output_av1_track)
    
    ffmpeg_args = mapper.get_ffmpeg_args()
    ffmpeg_cmd = ['ffmpeg'] + ffmpeg_args
    
    # Log the full FFmpeg command for debugging and verification
    logger_instance.info("Full FFmpeg command for transcoding: %s", " ".join(ffmpeg_cmd))
    logger_instance.debug("FFmpeg command list for transcoding: %s", ffmpeg_cmd)
    # Note: The line below was in the original plan, but logger_instance.info is already used above.
    # logger_instance.info("Executing transcode command: %s", " ".join(ffmpeg_cmd)) 

    # Probe the actual input to ffmpeg (demuxed track) for accurate progress parsing
    transcode_input_probe = Probe(logger_instance, allowed_mimetypes=['video'])
    if not transcode_input_probe.file(input_file_to_transcode):
        logger_instance.error("Failed to probe input for transcoding: %s", input_file_to_transcode)
        return None
    ffmpeg_parser_obj.set_probe(transcode_input_probe)

    try:
        process = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, 
                                   universal_newlines=True, encoding='utf-8', errors='replace', bufsize=1)
        for line in iter(process.stdout.readline, ''):
            line_strip = line.strip()
            if line_strip: # Avoid logging empty lines
                logger_instance.debug("FFMPEG: %s", line_strip)
                if worker_log_list is not None:
                    worker_log_list.append(line_strip)
                progress = ffmpeg_parser_obj.parse_progress(line_strip)
                if progress and 'percent' in progress:
                    try:
                        percent_val = float(progress['percent'])
                        logger_instance.info("FFMPEG progress: {:.2f}%".format(percent_val))
                    except ValueError:
                        logger_instance.info("FFMPEG progress: {}".format(progress['percent']))
        process.stdout.close()
        process.wait()
        if process.returncode != 0:
            logger_instance.error("Transcoding failed for %s. Return code: %s", input_file_to_transcode, process.returncode)
            # worker_log_list already contains ffmpeg output
            return None
        logger_instance.info("Transcoding successful: %s", output_av1_track)
        return output_av1_track
    except Exception as e:
        logger_instance.error("Exception during transcoding: %s", str(e), exc_info=True)
        return None

# Helper function to remux the transcoded video with other tracks using mkvmerge
def _remux(transcoded_av1_file, original_input_file, final_output_file, logger_instance):
    """Helper function to remux the transcoded video with other tracks from the original file."""
    logger_instance.info("Starting remux: video from %s, other tracks from %s, output to %s", 
                       transcoded_av1_file, original_input_file, final_output_file)
    cmd = ['mkvmerge', '-o', final_output_file, 
           '--video-tracks', '0', transcoded_av1_file, 
           '--audio-tracks', 'all', 
           '--subtitle-tracks', 'all', 
           '--attachments', 'all', 
           '--chapters', 
           original_input_file]
    logger_instance.info("Executing remux command: %s", " ".join(cmd))

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False, encoding='utf-8', errors='replace')
        if result.returncode != 0:
            logger_instance.error("Remuxing failed. Return code: %s", result.returncode)
            logger_instance.error("mkvmerge stderr: %s", result.stderr)
            logger_instance.error("mkvmerge stdout: %s", result.stdout)
            return False
        logger_instance.info("Remuxing successful, mkvmerge stdout: %s", result.stdout)
        if result.stderr: # mkvmerge often outputs warnings/info to stderr
            logger_instance.info("mkvmerge stderr (remux): %s", result.stderr)
        return True
    except Exception as e:
        logger_instance.error("Exception during remuxing: %s", str(e), exc_info=True)
        return False


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
    Runner function - implements a demux-transcode-remux workflow using helper functions.
    """
    # Initialization
    logger.info("Starting demux-transcode-remux process for file: %s", data.get('file_in'))
    data['exec_command'] = []
    data['command_progress_parser'] = None 
    data['repeat'] = False

    settings = Settings(library_id=data.get('library_id'))
    abspath = data.get('file_in') # This is the original_input_file

    original_probe = Probe(logger, allowed_mimetypes=['video'])
    if not original_probe.file(abspath):
        logger.error("Failed to probe original file: %s", abspath)
        if 'worker_log' in data: data['worker_log'].append("Error: Failed to probe original file.")
        return 

    ffmpeg_parser = Parser(logger)

    # Nested helper function for HDR metadata parsing (remains here as it's used before helpers)
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
                return metadata_str
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
    video_streams = [s for s in original_probe.get('streams', []) if s.get('codec_type') == 'video']
    if video_streams:
        main_video_stream = video_streams[0]

        # Extract basic color metadata from main video stream
        # These will be used if not overridden by more specific side data (though we simplify this for now)
        if main_video_stream.get('color_space'):
            hdr_metadata['colorspace'] = main_video_stream.get('color_space')
        if main_video_stream.get('color_primaries'):
            hdr_metadata['color_primaries'] = main_video_stream.get('color_primaries')
        # FFmpeg uses 'color_trc' for transfer characteristics
        if main_video_stream.get('color_transfer'):
            hdr_metadata['color_trc'] = main_video_stream.get('color_transfer')

        side_data_list = main_video_stream.get('side_data_list', [])
        for side_data in side_data_list:
            side_data_type = side_data.get('side_data_type')
            if side_data_type == 'Mastering display metadata':
                raw_master_display_str = side_data.get('value') # Use 'value' for mastering display string
                if raw_master_display_str:
                    hdr_metadata['master_display_data_string'] = parse_mastering_display_metadata(raw_master_display_str)
                # According to the simplified plan, we are not re-extracting color space/primaries/transfer from here
                # as the main stream info is generally sufficient and structure of these within side_data can vary.
            elif side_data_type == 'Content light level metadata':
                # Use specified keys: max_content_light_level, max_picture_average_light_level
                # Fallback to common ffprobe keys if specific ones are not found.
                max_content = side_data.get('max_content_light_level', side_data.get('max_content'))
                max_average = side_data.get('max_picture_average_light_level', side_data.get('max_frame_average_light_level'))
                if max_content is not None and max_average is not None:
                    hdr_metadata['max_cll_data_string'] = f"{max_content},{max_average}"
        
        if hdr_metadata:
            logger.info("Detected HDR metadata: %s", hdr_metadata)
    else:
        logger.info("No video streams found in the original probe data.")
    
    final_mkv_out = os.path.splitext(data.get('file_out'))[0] + ".mkv"
                    # The following lines for updating color_primaries, color_transfer, color_space
                    # from mastering display side_data were part of the original code.
                    # These specific sub-keys ('primaries', 'transfer_characteristics', 'matrix_coefficients')
                    # might not always be present directly under 'Mastering display metadata' side data in ffprobe.
                    # It's safer to rely on the top-level stream info for these unless ffprobe structure guarantees them here.
                    # For now, retaining the logic as it was, but noting this as a potential point of review based on actual ffprobe outputs.
                    if side_data.get('color_primaries'): color_primaries = side_data.get('color_primaries')[0] # This was in original, but 'primaries' might be the key
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