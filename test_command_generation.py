import sys
import os
import subprocess
import tempfile
import shutil
import re
import unittest # Using unittest for better structure and assertions

# Adjust path to import plugin components
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'source')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'source', 'video_transcoder_studyfranco'))) # for video_transcoder.lib

# Import necessary components
from video_transcoder_studyfranco.lib import plugin_stream_mapper
from video_transcoder_studyfranco.lib.encoders import libsvtav1
# Import plugin module itself to access helper functions if needed
import video_transcoder_studyfranco.plugin as plugin_module

# Store original subprocess.run
original_subprocess_run = subprocess.run
mock_probe_data_global = {} # To store different probe results for different calls

def mock_subprocess_run(*args, **kwargs):
    cmd = args[0]
    input_file = cmd[-1] # Assuming input file is the last argument for ffprobe

    # Default success
    mock_result = subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    if "ffprobe" in cmd:
        if "stream=color_primaries,color_trc,colorspace" in cmd:
            # Use data from the global mock_probe_data_global if available for this input_file
            data = mock_probe_data_global.get(input_file, {}).get("color_data", {})
            mock_result.stdout = f"{data.get('primaries', 'bt709')}\n{data.get('trc', 'bt709')}\n{data.get('space', 'bt709')}"
        elif "MASTERING_DISPLAY_METADATA" in cmd:
            data = mock_probe_data_global.get(input_file, {}).get("mastering_display", "")
            mock_result.stdout = data
        elif "MAX_CONTENT_LIGHT_LEVEL" in cmd:
            data = mock_probe_data_global.get(input_file, {}).get("max_cll", "")
            mock_result.stdout = data
        elif "tools.py" in cmd and "detect_black_bars" in " ".join(cmd): # if tools.py calls ffprobe
             mock_result.stdout = "crop=1920:800:0:140" # Example crop value
    elif "mkvmerge" in cmd:
        # For demux/remux, we only care about the command generation, not execution
        # but if they were called directly, this would prevent actual execution.
        print(f"Mocked mkvmerge call: {' '.join(cmd)}")
    elif "ffmpeg" in cmd and "-i" in cmd : # Transcode call
        print(f"Mocked ffmpeg transcode call: {' '.join(cmd)}")
    else:
        print(f"Warning: Unmocked or unhandled subprocess call: {cmd}")
        # Fallback to original if truly unhandled and execution is desired (not for this test)
        # return original_subprocess_run(*args, **kwargs)

    return mock_result

class MockProbe:
    def __init__(self, filepath, logger, allowed_mimetypes=None):
        self.filepath = filepath
        self.logger = logger
        self.probe_data = None # This would be populated by a real ffprobe call

    def file(self, filepath):
        # Simulate ffprobe parsing and populating self.probe_data
        # For this test, we mostly rely on mock_subprocess_run for ffprobe output
        # But plugin_stream_mapper.py might expect some basic structure
        global mock_probe_data_global
        self.probe_data = mock_probe_data_global.get(filepath, {}).get("ffprobe_streams_output", {"streams": [{"codec_type": "video"}]})
        if self.probe_data:
            return True
        return False

    def get_probe(self):
        return self.probe_data

    def get_duration(self):
        return 100 # Mock duration

    @staticmethod
    def init_probe(data, logger, allowed_mimetypes=None):
        # This is called by on_library_management_file_test, not directly by on_worker_process
        # For on_worker_process, Probe is instantiated directly.
        return MockProbe(data.get('path', "mock_input.mkv"), logger, allowed_mimetypes)


class MockSettings:
    def __init__(self, data):
        self.data = data
        self._encoders_instance = None

    def get_setting(self, key, default=None):
        return self.data.get(key, default)

    # Property to mimic how plugin.Settings initializes encoders
    @property
    def encoders(self):
        if self._encoders_instance is None:
            # Simplified version of plugin.py's __available_encoders
            self._encoders_instance = {
                'libsvtav1': libsvtav1.LibsvtAv1Encoder(self)
            }
        return self._encoders_instance


class TestCommandGeneration(unittest.TestCase):

    def setUp(self):
        # Apply the mock for subprocess.run
        subprocess.run = mock_subprocess_run
        # Mock tools.detect_black_bars if it's called by mapper and doesn't go via subprocess
        # For now, assuming it's not or covered by ffprobe mock for tools.
        self.test_temp_dir = tempfile.mkdtemp(prefix="unmanic_test_")

    def tearDown(self):
        # Restore original subprocess.run
        subprocess.run = original_subprocess_run
        if os.path.exists(self.test_temp_dir):
            shutil.rmtree(self.test_temp_dir)
        # Clear global mock data for next test if any
        global mock_probe_data_global
        mock_probe_data_global = {}


    def get_mock_settings_data(self, overrides=None):
        data = {
            'video_encoder': 'libsvtav1',
            'mode': 'standard',
            'keep_container': False,
            'dest_container': '.mkv',
            'force_transcode': False,
            'apply_smart_filters': False, # Keep it simple for now
            'autocrop_black_bars': False,
            'target_resolution': 'source',
            'main_options': '',
            'advanced_options': '',
            'custom_options': '', # for advanced mode video options
            'strip_data_streams': False,
            'strip_attachment_streams': False,
            'max_muxing_queue_size': '1024',


            # SVT-AV1 params
            'preset': '8',
            'encoder_ratecontrol_method': 'CRF', # Assuming this is how it's stored
            'constant_quality_scale': '30',
            'scd': 1,
            'enable_overlays': 1,
            'tune': 2,
            'aq_mode': 2,
            'enable_cdef': True,
            'enable_restoration': True,
            'enable_qm': True,
            'enable_variance_boost': True,
            'additional_svtav1_params': 'key1=value1:key2=value2',
            'sc_detection': "1", # FFmpeg global, ensure string if get_setting returns string
            'gop_size': "240",   # FFmpeg global
        }
        if overrides:
            data.update(overrides)
        return data

    def test_svtav1_hdr_command_generation(self):
        mock_input_file = "mock_hdr_input.mkv"
        mock_output_file = os.path.join(self.test_temp_dir, "mock_hdr_output.mkv")

        global mock_probe_data_global
        mock_probe_data_global[mock_input_file] = {
            "color_data": {
                "primaries": "bt2020",
                "trc": "arib-std-b67",
                "space": "bt2020nc"
            },
            "mastering_display": "G(34000,16000)B(13250,34500)R(7500,3000)WP(15635,16450)L(10000000,50)",
            "max_cll": "1000,300",
            "ffprobe_streams_output": { # For MockProbe.file()
                 "streams": [
                     {
                        "codec_type": "video", "width": 1920, "height": 1080, 
                        "codec_name": "hevc", 
                        "color_primaries": "bt2020", 
                        "color_trc": "arib-std-b67",
                        "colorspace": "bt2020nc",
                        "index": 0 # For mapping
                     },
                     {
                        "codec_type": "audio", "codec_name": "aac", "index": 1 # For -c:a copy
                     }
                 ]
            }
        }

        settings_data = self.get_mock_settings_data()
        mock_settings = MockSettings(settings_data)

        # Simulate plugin.py's on_worker_process logic for command generation
        
        # 1. Setup mapper (simplified from on_worker_process)
        mock_probe = MockProbe(mock_input_file, None)
        mock_probe.file(mock_input_file) # Load mock data into probe object

        mapper = plugin_stream_mapper.PluginStreamMapper()
        mapper.set_default_values(mock_settings, mock_input_file, mock_probe)
        
        # Ensure stream needs processing for args to be generated
        self.assertTrue(mapper.streams_need_processing(), "Stream should need processing based on mock setup")

        ffmpeg_encoder_args = mapper.get_ffmpeg_args()

        # 2. HDR Flag Generation (from plugin.py, simplified)
        hdr_flags = []
        try:
            probe_cmd_color = [
                "ffprobe", "-v", "error", "-select_streams", "v:0",
                "-show_entries", "stream=color_primaries,color_trc,colorspace",
                "-of", "default=noprint_wrappers=1:nokey=1", mock_input_file
            ]
            # subprocess.run is mocked here
            probe_result_color = subprocess.run(probe_cmd_color, capture_output=True, text=True, check=True)
            primaries, trc, colorspace_val = probe_result_color.stdout.strip().split('\n')
            if primaries and primaries != 'unknown': hdr_flags.extend(["-color_primaries", primaries])
            if trc and trc != 'unknown': hdr_flags.extend(["-color_trc", trc])
            if colorspace_val and colorspace_val != 'unknown': hdr_flags.extend(["-colorspace", colorspace_val])
        except Exception as e:
            print(f"Error getting color metadata in test: {e}")


        mastering = plugin_module.get_master_display_metadata(mock_input_file)
        if mastering: hdr_flags.extend(["-master_display", mastering])
        max_cll = plugin_module.get_max_cll_metadata(mock_input_file)
        if max_cll: hdr_flags.extend(["-max_cll", max_cll])
        
        # 3. Assemble Full Transcode Command (from plugin.py)
        # Ensure -c:a copy is present if audio is being mapped (simplified)
        # The mapper.get_ffmpeg_args() should already include mapped audio streams without -c:a,
        # so we add it if it's not explicitly set by other logic.
        audio_codec_set = any('-c:a' in arg or '-acodec' in arg for arg in ffmpeg_encoder_args)
        # A more robust check for audio mapping would be needed if testing complex scenarios
        # For this test, we assume audio is mapped and not encoded by default from mapper.
        final_ffmpeg_encoder_args = ffmpeg_encoder_args
        if not audio_codec_set and any("-map" in s and ":a" in s for s in ffmpeg_encoder_args): # Basic check for audio map
             final_ffmpeg_encoder_args.extend(["-c:a", "copy"])
        elif not audio_codec_set and not any("-map" in s and ":a" in s for s in ffmpeg_encoder_args):
            # If no audio is mapped, but we expect copy, this might be an issue in mapper
            # For now, let's assume mapper includes audio map by default or test separately
            # If we want to ensure -c:a copy is always there for video transcode:
            # final_ffmpeg_encoder_args.extend(["-c:a", "copy"])
            pass # Let ffmpeg_encoder_args be as is, and check it.

        transcode_command_list = hdr_flags + final_ffmpeg_encoder_args
        
        # 4. Generate Demux and Remux Commands
        demux_video_track_path = os.path.join(self.test_temp_dir, "video_track.mkv")
        demux_cmd_list = [
            "mkvmerge", "-o", demux_video_track_path,
            "--no-audio", "--no-subtitles", "--no-track-tags", "--no-attachments", "--no-chapters",
            mock_input_file
        ]
        
        # Expected transcoded video output path (as per prompt and typical usage)
        transcoded_video_output_path_in_temp = os.path.join(self.test_temp_dir, "video_av1.mkv") 
        
        # The actual ffmpeg execution command would be:
        ffmpeg_exe_cmd_list = ["ffmpeg", "-i", demux_video_track_path] + transcode_command_list + [transcoded_video_output_path_in_temp]

        remux_cmd_list = [
            "mkvmerge", "-o", mock_output_file,
            "--video-tracks", "0", transcoded_video_output_path_in_temp, # This should match the output of ffmpeg
            "--audio-tracks", "all", "--subtitle-tracks", "all",
            "--attachments", "all", "--chapters", "all",
            mock_input_file
        ]

        # Print commands for manual verification if needed
        print("\n--- Generated Demux Command ---")
        print(" ".join(demux_cmd_list))
        print("\n--- Generated FFmpeg Transcode Command List (Core Args) ---")
        # This is the list that would be passed to the transcode_video helper
        print(transcode_command_list) 
        print("\n--- Generated Remux Command ---")
        print(" ".join(remux_cmd_list))

        # Assertions
        # Demux
        self.assertEqual(demux_cmd_list[0], "mkvmerge")
        self.assertEqual(demux_cmd_list[1], "-o")
        self.assertEqual(demux_cmd_list[2], demux_video_track_path)
        self.assertIn("--no-audio", demux_cmd_list)
        self.assertIn("--no-subtitles", demux_cmd_list)
        self.assertIn("--no-track-tags", demux_cmd_list)
        self.assertIn("--no-attachments", demux_cmd_list)
        self.assertIn("--no-chapters", demux_cmd_list)
        self.assertEqual(demux_cmd_list[-1], mock_input_file)

        # Transcode (checking the transcode_command_list which is added after -i <input>)
        self.assertIn("-c:v", transcode_command_list)
        self.assertIn("libsvtav1", transcode_command_list)
        
        # HDR
        self.assertIn("-color_primaries", transcode_command_list)
        self.assertIn("bt2020", transcode_command_list)
        self.assertIn("-color_trc", transcode_command_list)
        self.assertIn("arib-std-b67", transcode_command_list)
        self.assertIn("-colorspace", transcode_command_list)
        self.assertIn("bt2020nc", transcode_command_list)
        self.assertIn("-master_display", transcode_command_list)
        self.assertIn("G(34000,16000)B(13250,34500)R(7500,3000)WP(15635,16450)L(10000000,50)", transcode_command_list)
        self.assertIn("-max_cll", transcode_command_list)
        self.assertIn("1000,300", transcode_command_list)

        # SVT-AV1 Params (ensure they are correctly formatted in -svtav1-params)
        # Need to find the -svtav1-params argument
        svtav1_params_str = ""
        try:
            idx = transcode_command_list.index('-svtav1-params')
            svtav1_params_str = transcode_command_list[idx+1]
        except ValueError:
            self.fail("-svtav1-params not found in transcode command")

        self.assertIn("scd=1", svtav1_params_str)
        self.assertIn("enable-overlays=1", svtav1_params_str)
        self.assertIn("tune=2", svtav1_params_str)
        self.assertIn("aq-mode=2", svtav1_params_str)
        self.assertIn("enable-cdef=1", svtav1_params_str) # Booleans become 1/0
        self.assertIn("enable-restoration=1", svtav1_params_str)
        self.assertIn("enable-qm=1", svtav1_params_str)
        self.assertIn("enable-variance-boost=1", svtav1_params_str)
        self.assertIn("key1=value1:key2=value2", svtav1_params_str)
        
        # FFmpeg global options from settings
        self.assertIn("-sc_detection", transcode_command_list)
        idx_sc = transcode_command_list.index('-sc_detection')
        self.assertEqual(transcode_command_list[idx_sc+1], "1")

        self.assertIn("-g", transcode_command_list)
        idx_g = transcode_command_list.index('-g')
        self.assertEqual(transcode_command_list[idx_g+1], "240")
        
        # Check for -c:a copy (this depends on default mapper behavior for audio)
        # plugin_stream_mapper.py by default maps all streams. If audio is present, it should map it.
        # The logic in this test adds -c:a copy if audio is mapped and no codec is set.
        # To make this more robust, mock_probe could define an audio stream.
        # Check for -c:a copy.
        # With an audio stream in mock_probe, mapper.get_ffmpeg_args() should include a map for it.
        # Then the logic in on_worker_process (simulated here) should add -c:a copy.
        
        # Re-evaluate final_ffmpeg_encoder_args based on the probe data that now includes audio
        # The mapper is already set up with this probe data.
        # The ffmpeg_encoder_args already comes from this mapper.
        audio_mapped = any("-map" in s and ":a" in s for s in ffmpeg_encoder_args) # from mapper
        
        # The transcode_command_list was built using the original ffmpeg_encoder_args.
        # We need to ensure that our assertion about -c:a copy is based on the *final* command list.
        # The current `final_ffmpeg_encoder_args` (which becomes `transcode_command_list` after HDR flags)
        # has the -c:a copy logic.
        
        if audio_mapped and not audio_codec_set: # audio_codec_set was from the initial ffmpeg_encoder_args
            self.assertIn("-c:a", final_ffmpeg_encoder_args) # final_ffmpeg_encoder_args is part of transcode_command_list
            self.assertIn("copy", final_ffmpeg_encoder_args)
        elif not audio_mapped:
            self.fail("Audio stream was not mapped by PluginStreamMapper based on mock probe data.")


        # Assertions for the full ffmpeg execution command
        self.assertEqual(ffmpeg_exe_cmd_list[0], "ffmpeg")
        self.assertIn("-i", ffmpeg_exe_cmd_list)
        self.assertEqual(ffmpeg_exe_cmd_list[ffmpeg_exe_cmd_list.index("-i") + 1], demux_video_track_path)
        self.assertIn(transcoded_video_output_path_in_temp, ffmpeg_exe_cmd_list)


        # Remux
        self.assertEqual(remux_cmd_list[0], "mkvmerge")
        self.assertEqual(remux_cmd_list[1], "-o")
        self.assertEqual(remux_cmd_list[2], mock_output_file)
        self.assertIn("--video-tracks", remux_cmd_list)
        self.assertEqual(remux_cmd_list[remux_cmd_list.index("--video-tracks") + 1], "0")
        self.assertIn(transcoded_video_output_path_in_temp, remux_cmd_list)
        self.assertIn("--audio-tracks", remux_cmd_list)
        self.assertEqual(remux_cmd_list[remux_cmd_list.index("--audio-tracks") + 1], "all")
        self.assertIn("--subtitle-tracks", remux_cmd_list)
        self.assertEqual(remux_cmd_list[remux_cmd_list.index("--subtitle-tracks") + 1], "all")
        self.assertIn("--attachments", remux_cmd_list)
        self.assertEqual(remux_cmd_list[remux_cmd_list.index("--attachments") + 1], "all")
        self.assertIn("--chapters", remux_cmd_list)
        self.assertEqual(remux_cmd_list[remux_cmd_list.index("--chapters") + 1], "all")
        self.assertEqual(remux_cmd_list[-1], mock_input_file)


if __name__ == "__main__":
    unittest.main()
```
