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
import subprocess
import tempfile
import shutil
import re

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


def get_master_display_metadata(input_file):
    """Helper function to get mastering display metadata."""
    try:
        probe_cmd = [
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream_tags=MASTERING_DISPLAY_METADATA",
            "-of", "default=noprint_wrappers=1:nokey=1", input_file
        ]
        result = subprocess.run(probe_cmd, capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        logger.error(f"Error getting mastering display metadata for {input_file}: {e}")
        return None
    except FileNotFoundError:
        logger.error(f"ffprobe not found. Please ensure it's in your PATH.")
        return None


def get_max_cll_metadata(input_file):
    """Helper function to get max content light level metadata."""
    try:
        probe_cmd = [
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream_tags=MAX_CONTENT_LIGHT_LEVEL",
            "-of", "default=noprint_wrappers=1:nokey=1", input_file
        ]
        result = subprocess.run(probe_cmd, capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        logger.error(f"Error getting max CLL metadata for {input_file}: {e}")
        return None
    except FileNotFoundError:
        logger.error(f"ffprobe not found. Please ensure it's in your PATH.")
        return None


def demux(input_path, temp_dir):
    """Demuxes the video track using mkvmerge."""
    video_track_path = os.path.join(temp_dir, "video_track.mkv")
    cmd = [
        "mkvmerge", "-o", video_track_path,
        "--no-audio", "--no-subtitles", "--no-track-tags", "--no-attachments", "--no-chapters",
        input_path
    ]
    try:
        logger.info(f"Executing demux command: {' '.join(cmd)}")
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        logger.info(f"Demux successful: {video_track_path}")
        return video_track_path
    except subprocess.CalledProcessError as e:
        logger.error(f"Demux failed for {input_path}: {e.stderr}")
        raise
    except FileNotFoundError:
        logger.error(f"mkvmerge not found. Please ensure it's in your PATH.")
        raise


def transcode_video(video_input_path, temp_dir, ffmpeg_cmd_list, output_video_filename):
    """Transcodes the video track using ffmpeg."""
    output_path = os.path.join(temp_dir, output_video_filename)
    cmd = ["ffmpeg", "-i", video_input_path] + ffmpeg_cmd_list + [output_path]
    try:
        logger.info(f"Executing transcode command: {' '.join(cmd)}")
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        logger.info(f"Transcode successful: {output_path}")
        return output_path
    except subprocess.CalledProcessError as e:
        logger.error(f"Transcode failed for {video_input_path}: {e.stderr}")
        # Log stdout as well for more info from ffmpeg
        logger.error(f"FFmpeg stdout: {e.stdout}")
        raise
    except FileNotFoundError:
        logger.error(f"ffmpeg not found. Please ensure it's in your PATH.")
        raise


def remux(original_input, transcoded_video_path, output_path):
    """Remuxes the transcoded video with other tracks from the original input."""
    cmd = [
        "mkvmerge", "-o", output_path,
        "--video-tracks", "0", transcoded_video_path,
        "--audio-tracks", "all", "--subtitle-tracks", "all",
        "--attachments", "all", "--chapters", "all",
        original_input
    ]
    try:
        logger.info(f"Executing remux command: {' '.join(cmd)}")
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        logger.info(f"Remux successful: {output_path}")
    except subprocess.CalledProcessError as e:
        logger.error(f"Remux failed for {original_input} and {transcoded_video_path}: {e.stderr}")
        raise
    except FileNotFoundError:
        logger.error(f"mkvmerge not found. Please ensure it's in your PATH.")
        raise


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

    # Get settings
    settings = Settings(library_id=data.get('library_id'))

    # Get the path to the file
    abspath = data.get('file_in')

    # Get file probe
    probe_obj = Probe(logger, allowed_mimetypes=['video']) # Renamed to avoid conflict
    if not probe_obj.file(abspath):
        # File probe failed, skip the rest of this test
        return

    # Get stream mapper
    mapper = plugin_stream_mapper.PluginStreamMapper()
    mapper.set_default_values(settings, abspath, probe_obj)

    # Check if this file needs to be processed
    if mapper.streams_need_processing():
        if file_marked_as_force_transcoded(abspath) and mapper.forced_encode:
            # Do not process this file, it has been force transcoded once before
            return

        # Runtime Assertions for SVT-AV1 parameters
        if settings.get_setting('video_encoder') == 'libsvtav1':
            scd = settings.get_setting('scd')
            assert scd in (0, 1), f"scd must be 0 or 1, got {scd}"
            sc_detection = settings.get_setting('sc_detection')
            assert sc_detection in (0, 1), f"sc_detection must be 0 or 1, got {sc_detection}"
            gop_size = settings.get_setting('gop_size')
            assert gop_size >= 1, f"gop_size must be >= 1, got {gop_size}"
            tune = settings.get_setting('tune')
            assert tune >= 0, f"tune must be >= 0, got {tune}"
            aq_mode = settings.get_setting('aq_mode')
            assert aq_mode >= 0, f"aq_mode must be >= 0, got {aq_mode}"
            additional_params = settings.get_setting('additional_svtav1_params', '').strip()
            if additional_params:
                # Regex to match "key=value" or "key=value:key2=value2"
                # Allows for alphanumeric keys, hyphens, and underscores. Values can be almost anything.
                param_pattern = re.compile(r"^([A-Za-z0-9_-]+=.+)(:([A-Za-z0-9_-]+=.+))*$")
                if not param_pattern.match(additional_params):
                    raise ValueError(
                        f"Invalid additional_svtav1_params format: '{additional_params}'. "
                        "Expected format is 'key=value' or 'key1=value1:key2=value2'."
                    )

        # HDR Metadata Preservation
        hdr_flags = []
        try:
            probe_cmd_color = [
                "ffprobe", "-v", "error", "-select_streams", "v:0",
                "-show_entries", "stream=color_primaries,color_trc,colorspace",
                "-of", "default=noprint_wrappers=1:nokey=1", abspath
            ]
            probe_result_color = subprocess.run(probe_cmd_color, capture_output=True, text=True, check=True)
            primaries, trc, colorspace_val = probe_result_color.stdout.strip().split('\n')
            if primaries and primaries != 'unknown':
                hdr_flags.extend(["-color_primaries", primaries])
            if trc and trc != 'unknown':
                hdr_flags.extend(["-color_trc", trc])
            if colorspace_val and colorspace_val != 'unknown':
                hdr_flags.extend(["-colorspace", colorspace_val])
        except subprocess.CalledProcessError as e:
            logger.warning(f"Could not retrieve color metadata for {abspath}: {e.stderr}")
        except ValueError as e:
            logger.warning(f"Error parsing color metadata for {abspath}: {e}")
        except FileNotFoundError:
            logger.error(f"ffprobe not found. Please ensure it's in your PATH.")
            # Depending on policy, you might want to raise an error or just proceed without HDR data

        mastering = get_master_display_metadata(abspath)
        if mastering:
            hdr_flags.extend(["-master_display", mastering])

        max_cll = get_max_cll_metadata(abspath)
        if max_cll:
            hdr_flags.extend(["-max_cll", max_cll])

        # Set the output file path (respecting keep_container)
        final_output_path = data.get('file_out')
        if not settings.get_setting('keep_container'):
            container_extension = settings.get_setting('dest_container')
            split_file_out = os.path.splitext(data.get('file_out'))
            final_output_path = "{}.{}".format(split_file_out[0], container_extension.lstrip('.'))
            data['file_out'] = final_output_path # Update data for Unmanic

        # Get base ffmpeg args from mapper
        ffmpeg_args = mapper.get_ffmpeg_args()

        # Ensure -c:a copy is present if audio is being mapped
        # Check if any audio stream is mapped and not explicitly encoded
        audio_mapped = any(arg == '-map' and 'a:0' in ffmpeg_args[i+1] for i, arg in enumerate(ffmpeg_args)) # basic check
        audio_codec_set = any('-c:a' in arg or '-acodec' in arg for arg in ffmpeg_args)

        if audio_mapped and not audio_codec_set:
            logger.info("Adding '-c:a copy' for audio stream.")
            ffmpeg_args.extend(["-c:a", "copy"])
        
        # Full command for transcoding, including HDR flags
        transcode_command_list = hdr_flags + ffmpeg_args

        temp_dir = None
        try:
            temp_dir = tempfile.mkdtemp(prefix="unmanic_transcode_")
            logger.info(f"Created temporary directory: {temp_dir}")

            # 1. Demux video
            demuxed_video_path = demux(abspath, temp_dir)

            # 2. Transcode video
            # The output filename for the transcoded video can be fixed for simplicity
            transcoded_video_filename = "video_transcoded.mkv" 
            transcoded_video_output_path = transcode_video(demuxed_video_path, temp_dir, transcode_command_list, transcoded_video_filename)

            # 3. Remux with original audio/subs/attachments/chapters
            remux(abspath, transcoded_video_output_path, final_output_path)
            
            logger.info(f"Successfully processed {abspath} to {final_output_path}")

        except subprocess.CalledProcessError as e:
            logger.error(f"A subprocess command failed during processing of {abspath}: {e}")
            logger.error(f"Command: {' '.join(e.cmd)}")
            logger.error(f"Stderr: {e.stderr}")
            logger.error(f"Stdout: {e.stdout}") # Log stdout for more details, especially from ffmpeg
            # To ensure Unmanic marks as failed, we might need to re-raise or handle error state
            # For now, logging and returning will prevent further processing of this item.
            return # Stop processing this file
        except Exception as e:
            logger.error(f"An unexpected error occurred during processing of {abspath}: {e}")
            # Similar to CalledProcessError, ensure this stops processing for the file.
            return # Stop processing this file
        finally:
            if temp_dir and os.path.exists(temp_dir):
                try:
                    shutil.rmtree(temp_dir)
                    logger.info(f"Cleaned up temporary directory: {temp_dir}")
                except Exception as e:
                    logger.error(f"Failed to cleanup temporary directory {temp_dir}: {e}")
        
        # Since commands are run directly, clear exec_command and parser
        data['exec_command'] = []
        data['command_progress_parser'] = None # Progress parsing would need custom implementation

        if settings.get_setting('force_transcode'):
            cache_directory = os.path.dirname(data.get('file_out')) # Use the final output path
            if not os.path.exists(cache_directory):
                os.makedirs(cache_directory)
            # Ensure .force_transcode is placed in the *cache* directory, not the final output's dir
            # Unmanic's cache directory is where data['file_out'] initially points for the worker.
            # The actual final destination is handled by post-processing.
            # The logic here assumes data['file_out'] for .force_transcode marker is correct
            # based on original plugin structure.
            # If final_output_path is different from data['file_out'] (e.g. due to container change)
            # ensure the marker is in the correct cache location that Unmanic uses.
            # For now, using data.get('file_out') as it was in original.
            force_transcode_marker_dir = os.path.dirname(data.get('file_out'))
            if not os.path.exists(force_transcode_marker_dir):
                 os.makedirs(force_transcode_marker_dir)
            with open(os.path.join(force_transcode_marker_dir, '.force_transcode'), 'w') as f:
                f.write('')
                logger.info(f"Force transcode marker written in {force_transcode_marker_dir}")

    return


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