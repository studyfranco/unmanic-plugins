#!/usr/bin/env python3
# -*- coding:utf-8 -*-

"""
    plugins.global_settings.py

    Written by:               Josh.5 <jsunnex@gmail.com>
    Date:                     10 Jun 2022, (6:52 PM)

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
import sys
import traceback
from os import path
from random import shuffle
from statistics import variance,mean
from time import strftime,gmtime
from threading import Thread
import tools
import video
from decimal import *

def not_keep_ass_converted_in_srt(file_path,keep_sub_ass,keep_sub_srt):
    set_md5_ass = set()
    for sub in keep_sub_ass:
        stream_ID,md5 = video.subtitle_text_srt_md5(file_path,sub["StreamOrder"])
        set_md5_ass.add(md5)
    for sub in keep_sub_srt:
        stream_ID,md5 = video.subtitle_text_srt_md5(file_path,sub["StreamOrder"])
        if md5 in set_md5_ass:
            sub['keep'] = False

def generate_merge_command_insert_ID_sub_track_set_not_default(merge_cmd,video_sub_track_list,md5_sub_already_added,list_track_order=[]):
    track_to_remove = set()
    number_track_sub = 0
    dic_language_list_track_ID = {}
    for language,subs in video_sub_track_list.items():
        for sub in subs:
            if (sub['keep'] and sub['MD5'] not in md5_sub_already_added):
                number_track_sub += 1
                if sub['MD5'] != '':
                    md5_sub_already_added.add(sub['MD5'])
                
                codec = sub['ffprobe']["codec_name"].lower()
                if codec in tools.sub_type_not_encodable:
                    language_and_type = language+'uncodable'
                elif codec in tools.sub_type_near_srt:
                    language_and_type = language+'srt'
                else:
                    language_and_type = language+'all'
                merge_cmd.extend(["--default-track-flag", sub["StreamOrder"]+":0"])
                if "Title" in sub:
                    if re.match(r".* *\[{0,1}forced\]{0,1} *.*", sub["Title"].lower()):
                        merge_cmd.extend(["--forced-display-flag", sub["StreamOrder"]+":1"])
                        if language_and_type+'_forced' not in dic_language_list_track_ID:
                            dic_language_list_track_ID[language_and_type+'_forced'] = [sub["StreamOrder"]]
                        else:
                            dic_language_list_track_ID[language_and_type+'_forced'].append(sub["StreamOrder"])
                    elif re.match(r".* *\[{0,1}sdh\]{0,1} *.*", sub["Title"].lower()):
                        merge_cmd.extend(["--hearing-impaired-flag", sub["StreamOrder"]+":1"])
                        if language_and_type+'_hearing' not in dic_language_list_track_ID:
                            dic_language_list_track_ID[language_and_type+'_hearing'] = [sub["StreamOrder"]]
                        else:
                            dic_language_list_track_ID[language_and_type+'_hearing'].append(sub["StreamOrder"])
                    else:
                        if language_and_type not in dic_language_list_track_ID:
                            dic_language_list_track_ID[language_and_type] = [sub["StreamOrder"]]
                        else:
                            dic_language_list_track_ID[language_and_type].append(sub["StreamOrder"])
                else:
                    if language_and_type not in dic_language_list_track_ID:
                        dic_language_list_track_ID[language_and_type] = [sub["StreamOrder"]]
                    else:
                        dic_language_list_track_ID[language_and_type].append(sub["StreamOrder"])
            else:
                track_to_remove.add(sub["StreamOrder"])
    if len(track_to_remove):
        merge_cmd.extend(["-s","!"+",".join(track_to_remove)])
    
    for language in sorted(dic_language_list_track_ID.keys()):
        list_track_order.extend(dic_language_list_track_ID[language])
    
    return number_track_sub

def generate_merge_command_insert_ID_audio_track_to_remove_and_new_und_language_set_not_default_not_forced(merge_cmd,audio):
    merge_cmd.extend(["--forced-display-flag", audio["StreamOrder"]+":0", "--default-track-flag", audio["StreamOrder"]+":0"])

default_audio = True
def generate_merge_command_insert_ID_audio_track_to_remove_and_new_und_language(merge_cmd,video_audio_track_list,video_commentary_track_list,video_audio_desc_track_list,md5_audio_already_added,list_track_order=[]):
    global default_audio
    number_track_audio = 0
    dic_language_list_track_ID = {}
    if len(video_audio_track_list) == 2 and "und" in video_audio_track_list and tools.default_language_for_undetermine != "und":
        # This step is linked by the fact if you have und audio they are orginialy convert in another language
        # This was convert in a language, but the object is the same and can be compared
        if video_audio_track_list[tools.default_language_for_undetermine] == video_audio_track_list['und']:
            del video_audio_track_list[tools.default_language_for_undetermine]
        
    track_to_remove = set()
    for language,audios in video_audio_track_list.items():
        for audio in audios:
            if ((not audio["keep"]) or (audio["MD5"] != '' and audio["MD5"] in md5_audio_already_added)):
                track_to_remove.add(audio["StreamOrder"])
            else:
                number_track_audio += 1
                if language not in dic_language_list_track_ID:
                    dic_language_list_track_ID[language] = [audio["StreamOrder"]]
                else:
                    dic_language_list_track_ID[language].append(audio["StreamOrder"])
                md5_audio_already_added.add(audio["MD5"])
                original_audio = False
                if language == "und" and tools.special_params["change_all_und"]:
                    merge_cmd.extend(["--language", audio["StreamOrder"]+":"+tools.default_language_for_undetermine])
                    if tools.default_language_for_undetermine == tools.special_params["original_language"]:
                        merge_cmd.extend(["--original-flag", audio["StreamOrder"]])
                        original_audio = True
                elif language == tools.special_params["original_language"]:
                    merge_cmd.extend(["--original-flag", audio["StreamOrder"]])
                    original_audio = True
                if default_audio and original_audio:
                    merge_cmd.extend(["--forced-display-flag", audio["StreamOrder"]+":0", "--default-track-flag", audio["StreamOrder"]+":1"])
                    default_audio = False
                else:
                    generate_merge_command_insert_ID_audio_track_to_remove_and_new_und_language_set_not_default_not_forced(merge_cmd,audio)
    for language,audios in video_commentary_track_list.items():
        for audio in audios:
            if ((not audio["keep"]) or (audio["MD5"] != '' and audio["MD5"] in md5_audio_already_added)):
                track_to_remove.add(audio["StreamOrder"])
            else:
                number_track_audio += 1
                if language+'_com' not in dic_language_list_track_ID:
                    dic_language_list_track_ID[language+'_com'] = [audio["StreamOrder"]]
                else:
                    dic_language_list_track_ID[language+'_com'].append(audio["StreamOrder"])
                md5_audio_already_added.add(audio["MD5"])
                if language == "und" and tools.special_params["change_all_und"]:
                    merge_cmd.extend(["--language", audio["StreamOrder"]+":"+tools.default_language_for_undetermine])
                generate_merge_command_insert_ID_audio_track_to_remove_and_new_und_language_set_not_default_not_forced(merge_cmd,audio)
                merge_cmd.extend(["--commentary-flag", audio["StreamOrder"]])
    for language,audios in video_audio_desc_track_list.items():
        for audio in audios:
            if (audio["MD5"] in md5_audio_already_added):
                track_to_remove.add(audio["StreamOrder"])
            else:
                number_track_audio += 1
                if language+'_visuali' not in dic_language_list_track_ID:
                    dic_language_list_track_ID[language+'_visuali'] = [audio["StreamOrder"]]
                else:
                    dic_language_list_track_ID[language+'_visuali'].append(audio["StreamOrder"])
                md5_audio_already_added.add(audio["MD5"])
                if language == "und" and tools.special_params["change_all_und"]:
                    merge_cmd.extend(["--language", audio["StreamOrder"]+":"+tools.default_language_for_undetermine])
                generate_merge_command_insert_ID_audio_track_to_remove_and_new_und_language_set_not_default_not_forced(merge_cmd,audio)
                merge_cmd.extend(["--visual-impaired-flag", audio["StreamOrder"]])

    if len(track_to_remove):
        merge_cmd.extend(["-a","!"+",".join(track_to_remove)])
        
    for language in sorted(dic_language_list_track_ID.keys()):
        list_track_order.extend(dic_language_list_track_ID[language])
    
    return number_track_audio

def extract_stream(video_obj, type_stream, id_stream, out_file):
    cmd_extract = [tools.software["mkvmerge"], "-o", out_file]
    if type_stream == "audio":
        cmd_extract.extend(["-D","-S","--no-global-tags", "-M", "-B", "--no-chapters",
                            "--audio-tracks", f"{id_stream}"])
    elif type_stream == "subtitle":
        cmd_extract.extend(["-D","-A","--no-global-tags", "-M", "-B", "--no-chapters",
                            "--subtitle-tracks", f"{id_stream}"])
    elif type_stream == "video":
        cmd_extract.extend(["-S","-A","--no-global-tags", "-M", "-B", "--no-chapters",
                            "--video-tracks", f"{id_stream}"])
    cmd_extract.extend([video_obj.filePath])
    tools.launch_cmdExt(cmd_extract)

def generate_new_file_audio_config(video_obj,base_cmd,audio,md5_audio_already_added,ffmpeg_cmd_dict,duration_best_video):
    if ((not audio["keep"]) or (audio["MD5"] != '' and audio["MD5"] in md5_audio_already_added)):
        return 0
    else:
        tmp_file_extract = path.join(tools.tmpFolder,f"{video_obj.fileBaseName}_{audio['StreamOrder']}_tmp_extr.mkv")
        extract_stream(video_obj, "audio", audio['StreamOrder'], tmp_file_extract)
        cmd_convert = base_cmd.copy()
        cmd_convert.extend(["-i", tmp_file_extract,
                "-map", "0:a?", "-map", "0:s?", "-map_metadata", "0", "-copy_unknown",
                "-movflags", "use_metadata_tags", "-c", "copy"])
        
        md5_audio_already_added.add(audio["MD5"])
        if tools.louis:
            if audio["Format"].lower() not in {"aac", "ac3", "eac3", "mp3", "opus", "he-aac", "he-aacv2"}:
                cmd_convert.extend(["-c:a", "libfdk_aac"])
                try:
                    if float(video.get_bitrate(audio))/float(audio['Channels']) < 128000:
                        cmd_convert.extend(["-b:a", video.get_bitrate(audio)])
                    elif float(audio['Channels']) > 2:
                        cmd_convert.extend(["-b:a", "640k"])
                    else:
                        cmd_convert.extend(["-b:a", "256k"])
                except:
                    pass
                cmd_convert.extend(["-ac", str(audio['Channels'])])
        else:
            if "Compression_Mode" in audio and audio["Compression_Mode"] == "Lossless":
                cmd_convert.extend([f"-c:a", "flac", "-compression_level", "12"])
                if "BitDepth" in audio:
                    if audio["BitDepth"] == "16":
                        cmd_convert.extend(["-sample_fmt", "s16"])
                    else:
                        cmd_convert.extend(["-sample_fmt", "s32"])
                else:
                    cmd_convert.extend(["-sample_fmt", "s32"])
                cmd_convert.extend(["-exact_rice_parameters", "1", "-multi_dim_quant", "1"])
        tmp_file_convert = path.join(tools.tmpFolder,f"{video_obj.fileBaseName}_{audio['StreamOrder']}_tmp.mkv")
        cmd_convert.extend(["-t", duration_best_video, tmp_file_convert])
        ffmpeg_cmd_dict['convert_process'].append(video.ffmpeg_pool_audio_convert.apply_async(tools.launch_cmdExt, (cmd_convert,)))
        sys.stderr.write(str(cmd_convert)+"\n")
        ffmpeg_cmd_dict['merge_cmd'].extend(["--no-global-tags", "-M", "-B", tmp_file_convert])
        return 1

def generate_new_file(video_obj,ffmpeg_cmd_dict,md5_audio_already_added,md5_sub_already_added,duration_best_video):
    base_cmd = [tools.software["ffmpeg"], "-err_detect", "crccheck", "-err_detect", "bitstream",
                    "-err_detect", "buffer", "-err_detect", "explode", "-fflags", "+genpts+igndts",
                    "-threads", str(tools.core_to_use), "-vn"]
    
    number_track = 0
    for language,subs in video_obj.subtitles.items():
        for sub in subs:
            if (sub['keep'] and sub['MD5'] not in md5_sub_already_added):
                number_track += 1
                tmp_file_extract = path.join(tools.tmpFolder,f"{video_obj.fileBaseName}_{sub['StreamOrder']}_tmp_extr.mkv")
                extract_stream(video_obj, "subtitle", sub['StreamOrder'], tmp_file_extract)
                cmd_convert = base_cmd.copy()
                cmd_convert.extend(["-i", tmp_file_extract,
                     "-map", "0:a?", "-map", "0:s?", "-map_metadata", "0", "-copy_unknown",
                     "-movflags", "use_metadata_tags", "-c", "copy"])
                
                if sub['MD5'] != '':
                    md5_sub_already_added.add(sub['MD5'])
                codec = sub["Format"].lower()
                if codec in tools.sub_type_not_encodable:
                    pass
                elif codec in tools.sub_type_near_srt:
                    cmd_convert.extend(["-c:s", "srt"])
                else:
                    cmd_convert.extend(["-c:s", "ass"])
                tmp_file_convert = path.join(tools.tmpFolder,f"{video_obj.fileBaseName}_{sub['StreamOrder']}_tmp.mkv")
                cmd_convert.extend(["-t", duration_best_video, tmp_file_convert])
                ffmpeg_cmd_dict['convert_process'].append(video.ffmpeg_pool_audio_convert.apply_async(tools.launch_cmdExt, (cmd_convert,)))
                sys.stderr.write(str(cmd_convert)+"\n")
                ffmpeg_cmd_dict['merge_cmd'].extend(["--no-global-tags", "-M", "-B", tmp_file_convert])
    
    for language,audios in video_obj.audios.items():
        for audio in audios:
            number_track += generate_new_file_audio_config(video_obj,base_cmd,audio,md5_audio_already_added,ffmpeg_cmd_dict,duration_best_video)
    for language,audios in video_obj.commentary.items():
        for audio in audios:
            number_track += generate_new_file_audio_config(video_obj,base_cmd,audio,md5_audio_already_added,ffmpeg_cmd_dict,duration_best_video)
    for language,audios in video_obj.audiodesc.items():
        for audio in audios:
            number_track += generate_new_file_audio_config(video_obj,base_cmd,audio,md5_audio_already_added,ffmpeg_cmd_dict,duration_best_video)
    
    if number_track:
        ffmpeg_cmd_dict['metadata_cmd'].extend(["-A", "-S", "-D", video_obj.filePath])
    return number_track

def merge_videos(file, source, out):
    md5_audio_already_added = set()
    md5_sub_already_added = set()
    
    ffmpeg_cmd_dict = {'files_with_offset' : [],
                       'number_files_add' : 0,
                       'convert_process' : [],
                       'merge_cmd' : [],
                       'metadata_cmd' : []}
    
    source_video_metadata = video.video(path.dirname(source),path.basename(source))
    source_video_metadata.get_mediadata()
    source_video_metadata.video = source_video_metadata.video
    source_video_metadata.calculate_md5_streams()
    
    if 'Language' in source_video_metadata.video and source_video_metadata.video['Language'] != "und":
        language = source_video_metadata.video['Language'].split("-")[0]
        tools.special_params["original_language"] = language
        
    
    generate_new_file(source_video_metadata,ffmpeg_cmd_dict,md5_audio_already_added,md5_sub_already_added,source_video_metadata.video['Duration'])
    
    out_path_tmp_file_name_split = path.join(tools.tmpFolder,f"{source_video_metadata.fileBaseName}_merged_split.mkv")
    merge_cmd = [tools.software["mkvmerge"], "-o", out_path_tmp_file_name_split]
    merge_cmd.extend(ffmpeg_cmd_dict['merge_cmd'])
    for convert_process in ffmpeg_cmd_dict['convert_process']:
        convert_process.get()
    try:
        tools.launch_cmdExt(merge_cmd)
    except Exception as e:
        import re
        lined_error = str(e).splitlines()
        if re.match('Return code: 1', lined_error[-1]) != None:
            only_UID_warning = True
            i = 0
            while only_UID_warning and i < len(lined_error):
                if re.match('^Warning:.*', lined_error[i]) != None:
                    if re.match(r"^Warning:.+Could not keep a track's UID \d+ because it is already allocated for another track. A new random UID will be allocated automatically.", lined_error[i]) == None:
                        only_UID_warning = False
                i += 1
            if (not only_UID_warning):
                raise e
            else:
                sys.stderr.write(str(e)+"\n")
        else:
            raise e

    tools.launch_cmdExt([tools.software["ffmpeg"], "-err_detect", "crccheck", "-err_detect", "bitstream",
                         "-err_detect", "buffer", "-err_detect", "explode", "-threads", str(tools.core_to_use),
                         "-i", out_path_tmp_file_name_split, "-map", "0", "-f", "null", "-c", "copy", "-"])
    
    out_video_metadata = video.video(tools.tmpFolder,path.basename(out_path_tmp_file_name_split))
    out_video_metadata.get_mediadata()
    out_video_metadata.video = source_video_metadata.video
    out_video_metadata.calculate_md5_streams_split()
    
    final_insert = [tools.software["mkvmerge"], "-o", out]
    final_insert.extend(["-A", "-S", "--no-chapters", "-M", "-B", "--no-global-tags", file])
    
    list_track_order=[]
    global default_audio
    default_audio = True
    generate_merge_command_insert_ID_audio_track_to_remove_and_new_und_language(final_insert,out_video_metadata.audios,out_video_metadata.commentary,out_video_metadata.audiodesc,set(),list_track_order)
    
    sub_same_md5 = {}
    keep_sub = {'ass':[],'srt':[]}
    for language,subs in out_video_metadata.subtitles.items():
        for sub in subs:
            if sub['MD5'] in sub_same_md5:
                sub_same_md5[sub['MD5']].append(sub)
            else:
                sub_same_md5[sub['MD5']] = [sub]
    for sub_md5,subs in sub_same_md5.items():
        codec = sub['ffprobe']["codec_name"].lower()
        if len(subs) > 1:
            have_srt_sub = False
            for sub in subs:
                if sub['Format'].lower() in tools.sub_type_near_srt and (not have_srt_sub):
                    have_srt_sub = True
                    keep_sub["srt"].append(sub)
                else:
                    sub['keep'] = False
            if (not have_srt_sub):
                subs[0]['keep'] = True
                if codec not in tools.sub_type_not_encodable:
                    keep_sub["ass"].append(sub)
        else:
            if sub['Format'].lower() in tools.sub_type_near_srt:
                keep_sub["srt"].append(sub)
            elif codec not in tools.sub_type_not_encodable:
                keep_sub["ass"].append(sub)
    
    if len(keep_sub["srt"]) and len(keep_sub["ass"]):
        not_keep_ass_converted_in_srt(out_path_tmp_file_name_split,keep_sub["ass"],keep_sub["srt"])
                
    generate_merge_command_insert_ID_sub_track_set_not_default(final_insert,out_video_metadata.subtitles,set(),list_track_order)
    final_insert.extend(["-D", out_path_tmp_file_name_split])
    final_insert.extend(ffmpeg_cmd_dict['metadata_cmd'])
    final_insert.extend(["--track-order", f"0:0,1:"+",1:".join(list_track_order)])
    tools.launch_cmdExt(final_insert)