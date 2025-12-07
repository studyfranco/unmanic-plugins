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
from os import path
from time import strftime,gmtime
from threading import Thread
import tools
import video
from audioCorrelation import correlate, test_calcul_can_be
import gc
from decimal import *

max_stream = 85

def decript_merge_rules(stringRules):
    rules = {}
    egualRules = set()
    besterBy = []
    for subRules in stringRules.split(","):
        bester = None
        precedentSuperior = []
        for subSubRules in subRules.split(">"):
            if '*' in subSubRules:
                value,multValue = subSubRules.lower().split("*")
                multValue = float(multValue)
            else:
                value = subSubRules.lower()
                multValue = True
            value = value.split("=")
            for subValue in value:
                if subValue not in rules:
                    rules[subValue] = {}
            for sup in precedentSuperior:
                for subValue in value:
                    if sup[0] == subValue:
                        pass
                    elif isinstance(sup[1], float):
                        if subValue not in rules[sup[0]]:
                            rules[sup[0]][subValue] = sup[1]
                            rules[subValue][sup[0]] = False
                        elif subValue in rules[sup[0]] and isinstance(rules[sup[0]][subValue], bool) and (not rules[sup[0]][subValue]) and (not (isinstance(rules[subValue][sup[0]], bool) and rules[subValue][sup[0]]) ):
                            if rules[subValue][sup[0]] >= 1 and sup[1] >= 1:
                                rules[sup[0]][subValue] = sup[1]
                                
                    elif isinstance(sup[1], bool):
                        rules[sup[0]][subValue] = True
                        rules[subValue][sup[0]] = False
                    
                if isinstance(multValue, bool):
                    sup[1] = multValue
                elif isinstance(sup[1], float):
                    sup[1] = sup[1]*multValue
                    
            for subValue in value:
                precedentSuperior.append([subValue,multValue])
                for subValue2 in value:
                    if subValue2 != subValue:
                        egualRules.add((subValue,subValue2))
                        egualRules.add((subValue2,subValue))
                        
            if bester != None:
                for best in bester:
                    for subValue in value:
                        besterBy.append([best,subValue])
            
            if isinstance(multValue, bool) and multValue:
                bester = value
            else:
                bester = None
    
    for besterRules in besterBy:
        decript_merge_rules_bester(rules,besterRules[0],besterRules[1])
    
    for egualRule in egualRules:
        if egualRule[1] in rules[egualRule[0]]:
            del rules[egualRule[0]][egualRule[1]]
    
    return rules

def decript_merge_rules_bester(rules,best,weak):
    for rulesWeak in rules[weak].items():
        if (isinstance(rulesWeak[1], bool) and rulesWeak[1]) or (isinstance(rulesWeak[1], float) and rulesWeak[1] > 5):
            decript_merge_rules_bester(rules,best,rulesWeak[0])
    rules[weak][best] = False
    rules[best][weak] = True

def get_good_parameters_to_get_fidelity(videosObj,language,audioParam,maxTime):
    if maxTime < 60:
        timeTake = strftime('%H:%M:%S',gmtime(maxTime))
    else:
        timeTake = "00:01:00"
        maxTime = 60
    for videoObj in videosObj:
        videoObj.extract_audio_in_part(language,audioParam,cutTime=[["00:00:00",timeTake]])
        videoObj.wait_end_ffmpeg_progress_audio()
        if (not test_calcul_can_be(videoObj.tmpFiles['audio'][0][0],maxTime)):
            raise Exception(f"Audio parameters to get the fidelity not working with {videoObj.filePath}")

def prepare_get_delay_sub(videos_obj,language):
    audio_parameter_to_use_for_comparison = {'Format':"WAV",
                                             'codec':"pcm_s16le",
                                             'Channels':"2"}
    min_channel = video.get_less_channel_number(videos_obj,language)
    if min_channel == "1":
        audio_parameter_to_use_for_comparison['Channels'] = min_channel

    min_video_duration_in_sec = video.get_shortest_audio_durations(videos_obj,language)
    get_good_parameters_to_get_fidelity(videos_obj,language,audio_parameter_to_use_for_comparison,min_video_duration_in_sec)
    
    begin_in_second,length_time = video.generate_begin_and_length_by_segment(min_video_duration_in_sec)
    length_time_converted = strftime('%H:%M:%S',gmtime(length_time*2))
    list_cut_begin_length = video.generate_cut_with_begin_length(begin_in_second,length_time,length_time_converted)

    return begin_in_second,audio_parameter_to_use_for_comparison,length_time,length_time_converted,list_cut_begin_length

class get_delay_fidelity_thread(Thread):
    def __init__(self, video_obj_1_tmp_file,video_obj_2_tmp_file,lenghtTime):
        Thread.__init__(self)
        self.video_obj_1_tmp_file = video_obj_1_tmp_file
        self.video_obj_2_tmp_file = video_obj_2_tmp_file
        self.lenghtTime = lenghtTime
        self.delay_Fidelity_Values  = None

    def run(self):
        self.delay_Fidelity_Values = correlate(self.video_obj_1_tmp_file,self.video_obj_2_tmp_file,self.lenghtTime)

def get_delay_fidelity(video_obj_1,video_obj_2,lenghtTime,ignore_audio_couple=set()):
    delay_Fidelity_Values = {}
    delay_Fidelity_Values_jobs = []
    
    video_obj_1.wait_end_ffmpeg_progress_audio()
    video_obj_2.wait_end_ffmpeg_progress_audio()
    for i in range(0,len(video_obj_1.tmpFiles['audio'])):
        for j in range(0,len(video_obj_2.tmpFiles['audio'])):
            if f"{i}-{j}" not in ignore_audio_couple:
                delay_Fidelity_Values_jobs_between_audio = []
                delay_Fidelity_Values_jobs.append([f"{i}-{j}",delay_Fidelity_Values_jobs_between_audio])
                for h in range(0,video.number_cut):
                    delay_Fidelity_Values_jobs_between_audio.append(get_delay_fidelity_thread(video_obj_1.tmpFiles['audio'][i][h],video_obj_2.tmpFiles['audio'][j][h],lenghtTime))
                    delay_Fidelity_Values_jobs_between_audio[-1].start()
    
    for delay_Fidelity_Values_job in delay_Fidelity_Values_jobs:
        delay_between_two_audio = []
        delay_Fidelity_Values[delay_Fidelity_Values_job[0]] = delay_between_two_audio
        for delay_Fidelity_Values_job_between_audio in delay_Fidelity_Values_job[1]:
            delay_Fidelity_Values_job_between_audio.join()
            delay_between_two_audio.append(delay_Fidelity_Values_job_between_audio.delay_Fidelity_Values)

    gc.collect()
    return delay_Fidelity_Values

def find_differences_and_keep_best_audio(video_obj,language,audioRules):
    if len(video_obj.audios[language]) > 1:
        if tools.dev:
            sys.stderr.write(f"\t\tKeep the best audio for {language}\n")
        try:
            begin_in_second,audio_parameter_to_use_for_comparison,length_time,length_time_converted,list_cut_begin_length = prepare_get_delay_sub([video_obj],language)
            video_obj.extract_audio_in_part(language,audio_parameter_to_use_for_comparison,cutTime=list_cut_begin_length)

            ignore_compare = set([f"{i}-{i}" for i in range(len(video_obj.audios[language]))])
            for i in range(len(video_obj.audios[language])):
                for j in range(i+1,len(video_obj.audios[language])):
                    ignore_compare.add(f"{j}-{i}")
            delay_Fidelity_Values = get_delay_fidelity(video_obj,video_obj,length_time*2,ignore_audio_couple=ignore_compare)
            
            fileid_audio = {}
            validation = {}
            for audio in video_obj.audios[language]:
                fileid_audio[audio["audio_pos_file"]] = audio
                validation[audio["audio_pos_file"]] = {}

            to_compare = []
            for i in range(len(video_obj.audios[language])):
                to_compare.append(i)
                for j in range(i+1,len(video_obj.audios[language])):
                    from statistics import mean
                    if mean([fi[0] for fi in delay_Fidelity_Values[f"{i}-{j}"]]) >= 0.90:
                        set_delay = set()
                        for delay_fidelity in delay_Fidelity_Values[f"{i}-{j}"]:
                            set_delay.add(delay_fidelity[2])
                        if len(set_delay) == 1 and abs(list(set_delay)[0]) == 0:
                            validation[i][j] = True
                        elif len(set_delay) == 1 and abs(list(set_delay)[0]) < 128:
                            if tools.dev:
                                sys.stderr.write(f"find_differences_and_keep_best_audio set_delay {i}-{j}: {set_delay}\n")
                                sys.stderr.write(f"find_differences_and_keep_best_audio fidelity {i}-{j}: {[fi[0] for fi in delay_Fidelity_Values[f"{i}-{j}"]]}\n")
                            validation[i][j] = True
                        elif len(set_delay) == 1 and abs(list(set_delay)[0]) >= 128:
                            validation[i][j] = False
                            sys.stderr.write(f"Be carreful find_differences_and_keep_best_audio on {language} find a delay of {set_delay}\n")
                            sys.stderr.write(f"find_differences_and_keep_best_audio set_delay {i}-{j}: {set_delay}\n")
                            sys.stderr.write(f"find_differences_and_keep_best_audio fidelity {i}-{j}: {[fi[0] for fi in delay_Fidelity_Values[f"{i}-{j}"]]}\n")
                        elif len(set_delay) == 2 and abs(list(set_delay)[0]) < 128 and abs(list(set_delay)[1]) < 128:
                            if tools.dev:
                                sys.stderr.write(f"find_differences_and_keep_best_audio set_delay {i}-{j}: {set_delay}\n")
                                sys.stderr.write(f"find_differences_and_keep_best_audio fidelity {i}-{j}: {[fi[0] for fi in delay_Fidelity_Values[f"{i}-{j}"]]}\n")
                            validation[i][j] = True
                        else:
                            validation[i][j] = False
                    else:
                        validation[i][j] = False
            
            while len(to_compare):
                main = to_compare.pop(0)
                list_compatible = set()
                not_compatible = set()
                for i in validation[main].keys():
                    if tools.dev:
                        sys.stderr.write(f"find_differences_and_keep_best_audio validation[{main}][{i}]: {validation[main][i]}\n")
                    if validation[main][i] and i not in not_compatible:
                        list_compatible.add(i)
                        for j in validation[i].keys():
                            if tools.dev:
                                sys.stderr.write(f"find_differences_and_keep_best_audio validation[{i}][{j}]: {validation[i][j]}\n")
                            if (not(validation[i][j])):
                                not_compatible.add(j)
                list_compatible = list_compatible - not_compatible
                if len(list_compatible):
                    list_audio_metadata_compatible = [fileid_audio[main]]
                    for id_audio in list_compatible:
                        list_audio_metadata_compatible.append(fileid_audio[id_audio])
                    keep_best_audio(list_audio_metadata_compatible,audioRules)
                    if tools.dev:
                        sys.stderr.write(f"find_differences_and_keep_best_audio list_compatible: {list_compatible}\n")
                    to_compare = [x for x in to_compare if x not in list_compatible]
                
        except Exception as e:
            import traceback
            traceback.print_exc()
            sys.stderr.write(f"Error processing find_differences_and_keep_best_audio on {language}: {e}\n")
        finally:
            video_obj.remove_tmp_files(type_file="audio")

def keep_best_audio(list_audio_metadata,audioRules):
    '''
    Todo:
        Integrate https://github.com/Sg4Dylan/FLAD/tree/main
    '''
    for i,audio_1 in enumerate(list_audio_metadata):
        for j,audio_2 in enumerate(list_audio_metadata):
            if i == j or (not audio_2['keep']) or (not audio_1['keep']):
                pass
            elif audio_1['Format'].lower() == audio_2['Format'].lower():
                try:
                    if float(audio_1['Channels']) == float(audio_2['Channels']):
                        if int(audio_1['SamplingRate']) >= int(audio_2['SamplingRate']) and int(video.get_bitrate(audio_1)) >= int(video.get_bitrate(audio_2)):
                            audio_2['keep'] = False
                        elif int(audio_2['SamplingRate']) >= int(audio_1['SamplingRate']) and int(video.get_bitrate(audio_2)) > int(video.get_bitrate(audio_1)):
                            audio_1['keep'] = False
                    elif float(audio_1['Channels']) > float(audio_2['Channels']):
                        if int(audio_1['SamplingRate']) >= int(audio_2['SamplingRate']) and (float(video.get_bitrate(audio_1))/float(audio_1['Channels'])) > (float(video.get_bitrate(audio_2))/float(audio_2['Channels'])*0.95):
                            audio_2['keep'] = False
                    elif float(audio_2['Channels']) > float(audio_1['Channels']):
                        if int(audio_2['SamplingRate']) >= int(audio_1['SamplingRate']) and (float(video.get_bitrate(audio_2))/float(audio_2['Channels'])) > (float(video.get_bitrate(audio_1))/float(audio_1['Channels'])*0.95):
                            audio_1['keep'] = False
                except Exception as e:
                    sys.stderr.write(str(e))
            else:
                if audio_1['Format'].lower() in audioRules:
                    if audio_2['Format'].lower() in audioRules[audio_1['Format'].lower()]:
                        try:
                            if int(audio_1['SamplingRate']) >= int(audio_2['SamplingRate']) and float(audio_1['Channels']) >= float(audio_2['Channels']):
                                if isinstance(audioRules[audio_1['Format'].lower()][audio_2['Format'].lower()], bool):
                                    if audioRules[audio_1['Format'].lower()][audio_2['Format'].lower()]:
                                        audio_2['keep'] = False
                                elif isinstance(audioRules[audio_1['Format'].lower()][audio_2['Format'].lower()], float):
                                    if int(video.get_bitrate(audio_1)) > int(video.get_bitrate(audio_2))*audioRules[audio_1['Format'].lower()][audio_2['Format'].lower()]:
                                        audio_2['keep'] = False
                        except Exception as e:
                            sys.stderr.write(str(e))
                        
                        try:
                            if int(audio_2['SamplingRate']) >= int(audio_1['SamplingRate']) and float(audio_2['Channels']) >= float(audio_1['Channels']):
                                if isinstance(audioRules[audio_2['Format'].lower()][audio_1['Format'].lower()], bool):
                                    if audioRules[audio_2['Format'].lower()][audio_1['Format'].lower()]:
                                        audio_1['keep'] = False
                                elif isinstance(audioRules[audio_2['Format'].lower()][audio_1['Format'].lower()], float):
                                    if int(video.get_bitrate(audio_2)) > int(video.get_bitrate(audio_1))*audioRules[audio_2['Format'].lower()][audio_1['Format'].lower()]:
                                        audio_1['keep'] = False
                        except Exception as e:
                            sys.stderr.write(str(e))

def remove_sub_language(video_sub_track_list,language,number_sub_will_be_copy,number_max_sub_stream):
    if number_sub_will_be_copy > number_max_sub_stream:
        for sub in video_sub_track_list[language]:
            if (sub['keep']) and number_sub_will_be_copy > number_max_sub_stream:
                sub['keep'] = False
                number_sub_will_be_copy -= 1
    return number_sub_will_be_copy

def keep_one_ass(groupID_srt_type_in,number_sub_will_be_copy,number_max_sub_stream):
    for ass_name in ["forced_ass","hi_ass","dub_ass","ass"]:
        if number_sub_will_be_copy > number_max_sub_stream:
            for comparative_sub in groupID_srt_type_in.values():
                if ass_name in comparative_sub and len(comparative_sub[ass_name]) > 1:
                    for i in range(1,len(comparative_sub[ass_name])):
                        comparative_sub[ass_name][i]['keep'] = False
                    number_sub_will_be_copy -= (len(comparative_sub[ass_name]) - 1)
    return number_sub_will_be_copy

def sub_group_id_detector_and_clean_srt_when_ass_with_test(video_sub_track_list,language,language_groupID_srt_type_in,number_sub_will_be_copy,number_max_sub_stream):
    if number_sub_will_be_copy > number_max_sub_stream and language in video_sub_track_list:
        sub_group_id_detector(video_sub_track_list[language],tools.group_title_sub[language],language_groupID_srt_type_in[language])

        if number_sub_will_be_copy > number_max_sub_stream:
            number_sub_will_be_copy = clean_srt_when_ass(language_groupID_srt_type_in[language],"hi_ass","hi_srt",number_sub_will_be_copy)
        if number_sub_will_be_copy > number_max_sub_stream:
            number_sub_will_be_copy = clean_srt_when_ass(language_groupID_srt_type_in[language],"dub_ass","dub_srt",number_sub_will_be_copy)
        if number_sub_will_be_copy > number_max_sub_stream:
            number_sub_will_be_copy = clean_srt_when_ass(language_groupID_srt_type_in[language],"ass","srt",number_sub_will_be_copy)
    return number_sub_will_be_copy

def sub_group_id_detector(sub_list,group_title_sub_for_language,groupID_srt_type_in):
    for sub in sub_list:
        if (sub['keep']):
            codec = sub['ffprobe']["codec_name"].lower()
            if codec in tools.sub_type_near_srt:
                if test_if_hearing_impaired(sub):
                    insert_type_in_group_sub_title(clean_hearing_impaired_title(sub),"hi_srt",group_title_sub_for_language,groupID_srt_type_in,sub)
                elif test_if_dubtitle(sub):
                    insert_type_in_group_sub_title(clean_dubtitle_title(sub),"dub_srt",group_title_sub_for_language,groupID_srt_type_in,sub)
                elif (not test_if_forced(sub)):
                    insert_type_in_group_sub_title(clean_title(sub),"srt",group_title_sub_for_language,groupID_srt_type_in,sub)

            elif codec not in tools.sub_type_not_encodable:
                if test_if_hearing_impaired(sub):
                    insert_type_in_group_sub_title(clean_hearing_impaired_title(sub),"hi_ass",group_title_sub_for_language,groupID_srt_type_in,sub)
                elif test_if_dubtitle(sub):
                    insert_type_in_group_sub_title(clean_dubtitle_title(sub),"dub_ass",group_title_sub_for_language,groupID_srt_type_in,sub)
                elif (not test_if_forced(sub)):
                    insert_type_in_group_sub_title(clean_title(sub),"ass",group_title_sub_for_language,groupID_srt_type_in,sub)

def clean_srt_when_ass(groupID_srt_type_in,ass_name,srt_name,number_sub_will_be_copy):
    for comparative_sub in groupID_srt_type_in.values():
        if ass_name in comparative_sub and len(comparative_sub[ass_name]) and srt_name in comparative_sub and len(comparative_sub[srt_name]):
            for sub in comparative_sub[srt_name]:
                sub['keep'] = False
            number_sub_will_be_copy -= len(comparative_sub[srt_name])
        elif srt_name in comparative_sub and len(comparative_sub[srt_name]) > 1:
            for i in range(1,len(comparative_sub[srt_name])):
                comparative_sub[srt_name][i]['keep'] = False
            number_sub_will_be_copy -= (len(comparative_sub[srt_name]) - 1)
    return number_sub_will_be_copy

def get_sub_title_group_id(groups,sub_title):
    for i,group in enumerate(groups):
        if sub_title in group:
            return i
    return None

def insert_type_in_group_sub_title(sub_clean_title,type_sub,groups,groupID_srt_type_in,sub):
    group_id = get_sub_title_group_id(groups,sub_clean_title)
    if group_id == None:
        groups.append([sub_clean_title])
        group_id = len(groups)-1
    
    if group_id not in groupID_srt_type_in:
        groupID_srt_type_in[group_id] = {}
    if type_sub not in groupID_srt_type_in[group_id]:
        groupID_srt_type_in[group_id][type_sub] = [sub]
    else:
        groupID_srt_type_in[group_id][type_sub].append(sub)

def clean_title(sub):
    clean_title = ""
    if "Title" in sub:
        clean_title = re.sub(r'^\s*',"",clean_title)
        clean_title = re.sub(r'\s*$',"",clean_title)
    return clean_title

def clean_dubtitle_title(sub):
    clean_title = ""
    if "Title" in sub:
        clean_title = re.sub(r'\s*\({0,1}dubtitle\){0,1}\s*',"",sub["Title"].lower())
        clean_title = re.sub(r'^\s*',"",clean_title)
        clean_title = re.sub(r'\s*$',"",clean_title)
    return clean_title

def test_if_dubtitle(sub):
    if "Title" in sub and re.match(r".*dubtitle.*", sub["Title"].lower()):
        return True
    return False

def clean_hearing_impaired_title(sub):
    clean_title = ""
    if "Title" in sub:
        if re.match(r".*sdh.*", sub["Title"].lower()):
            clean_title = re.sub(r'\s*\({0,1}sdh\){0,1}\s*',"",sub["Title"].lower())
        elif re.match(r".*\(cc\).*", sub["Title"].lower()):
            clean_title = re.sub(r'\s*\(cc\)\s*',"",sub["Title"].lower())
        elif 'hi' == sub["Title"].lower() or 'cc' == sub["Title"].lower():
            clean_title = ""
        else:
            clean_title = sub["Title"].lower()
        clean_title = re.sub(r'^\s*',"",clean_title)
        clean_title = re.sub(r'\s*$',"",clean_title)
    return clean_title

def test_if_hearing_impaired(sub):
    if "Title" in sub:
        if re.match(r".*sdh.*", sub["Title"].lower()) or 'cc' == sub["Title"].lower() or 'hi' == sub["Title"].lower() or re.match(r".*\(cc\).*", sub["Title"].lower()):
            return True
    if ("flag_hearing_impaired" in sub['properties'] and sub['properties']["flag_hearing_impaired"]):
        return True
    return False

def clean_forced_title(sub):
    clean_title = ""
    if "Title" in sub:
        clean_title = re.sub(r'\s*\({0,1}forced\){0,1}\s*',"",sub["Title"].lower())
        clean_title = re.sub(r'\s*\({0,1}forcé\){0,1}\s*',"",clean_title)
        clean_title = re.sub(r'^\s*',"",clean_title)
        clean_title = re.sub(r'\s*$',"",clean_title)
    return clean_title

def test_if_forced(sub):
    if "Title" in sub and (re.match(r".*forced.*", sub["Title"].lower()) or re.match(r".*forcé.*", sub["Title"].lower())):
        return True
    return False

def clean_number_stream_to_be_lover_than_max(number_max_sub_stream,video_sub_track_list):
    try:
        unique_md5 = set()
        number_sub_will_be_copy = 0
        for language,subs in video_sub_track_list.items():
            for sub in subs:
                if sub['keep']:
                    if sub['MD5'] not in unique_md5:
                        number_sub_will_be_copy += 1
                        if sub['MD5'] != '':
                            unique_md5.add(sub['MD5'])
                    else:
                        sub['keep'] = False
        
        if number_sub_will_be_copy > number_max_sub_stream:
            language_groupID_srt_type_in = {}
            # Remove forced srt sub if we have an ass.
            for language,subs in video_sub_track_list.items():
                if language not in tools.group_title_sub:
                    tools.group_title_sub[language] = []
                groupID_srt_type_in = {}
                language_groupID_srt_type_in[language] = groupID_srt_type_in
                for sub in subs:
                    if (sub['keep']):
                        codec = sub['ffprobe']["codec_name"].lower()
                        if codec in tools.sub_type_near_srt and test_if_forced(sub):
                            insert_type_in_group_sub_title(clean_forced_title(sub),"forced_srt",tools.group_title_sub[language],groupID_srt_type_in,sub)
                        elif codec not in tools.sub_type_not_encodable and test_if_forced(sub):
                            insert_type_in_group_sub_title(clean_forced_title(sub),"forced_ass",tools.group_title_sub[language],groupID_srt_type_in,sub)
                number_sub_will_be_copy = clean_srt_when_ass(groupID_srt_type_in,"forced_ass","forced_srt",number_sub_will_be_copy)

            # Remove srt sub on not keep
            if number_sub_will_be_copy > number_max_sub_stream:
                language_to_clean = set(video_sub_track_list.keys()) - set(tools.language_to_keep) - set(tools.language_to_try_to_keep)
                for language in language_to_clean:
                    sub_group_id_detector(video_sub_track_list[language],tools.group_title_sub[language],language_groupID_srt_type_in[language])

                    number_sub_will_be_copy = clean_srt_when_ass(language_groupID_srt_type_in[language],"hi_ass","hi_srt",number_sub_will_be_copy)
                    number_sub_will_be_copy = clean_srt_when_ass(language_groupID_srt_type_in[language],"dub_ass","dub_srt",number_sub_will_be_copy)
                    number_sub_will_be_copy = clean_srt_when_ass(language_groupID_srt_type_in[language],"ass","srt",number_sub_will_be_copy)
                
                if number_sub_will_be_copy > number_max_sub_stream:
                    for language in tools.language_to_try_to_keep:
                        number_sub_will_be_copy = sub_group_id_detector_and_clean_srt_when_ass_with_test(video_sub_track_list,language,language_groupID_srt_type_in,number_sub_will_be_copy,number_max_sub_stream)
                    
                    if number_sub_will_be_copy > number_max_sub_stream:
                        for language in language_to_clean:
                            if number_sub_will_be_copy > number_max_sub_stream:
                                number_sub_will_be_copy = keep_one_ass(language_groupID_srt_type_in[language],number_sub_will_be_copy,number_max_sub_stream)
                        
                        if number_sub_will_be_copy > number_max_sub_stream:
                            for language in tools.language_to_keep:
                                number_sub_will_be_copy = sub_group_id_detector_and_clean_srt_when_ass_with_test(video_sub_track_list,language,language_groupID_srt_type_in,number_sub_will_be_copy,number_max_sub_stream)
                            
                            if number_sub_will_be_copy > number_max_sub_stream:
                                for language in language_to_clean:
                                    number_sub_will_be_copy = remove_sub_language(video_sub_track_list,language,number_sub_will_be_copy,number_max_sub_stream)
                                
                                if number_sub_will_be_copy > number_max_sub_stream:
                                    for language in tools.language_to_try_to_keep:
                                        number_sub_will_be_copy = keep_one_ass(language_groupID_srt_type_in[language],number_sub_will_be_copy,number_max_sub_stream)

    except Exception as e:
        import traceback
        traceback.print_exc()
        sys.stderr.write(f"Error processing clean_number_stream_to_be_lover_than_max: {e}\n")

def not_keep_ass_converted_in_srt(file_path,keep_sub_ass,keep_sub_srt):
    set_md5_ass = set()
    for sub in keep_sub_ass:
        if sub['keep']:
            stream_ID,md5 = video.subtitle_text_srt_md5(file_path,sub["StreamOrder"])
            if md5 != None:
                set_md5_ass.add(md5)
    for sub in keep_sub_srt:
        stream_ID,md5 = video.subtitle_text_srt_md5(file_path,sub["StreamOrder"])
        if md5 != None and md5 in set_md5_ass:
            if tools.dev:
                sys.stderr.write(f"\t\tThe sub stream {sub['StreamOrder']} is a ASS converted SRT for language {sub['Language']}.\n")
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
                    type_sub = '_uncodable'
                elif codec in tools.sub_type_near_srt:
                    type_sub = '_srt'
                else:
                    type_sub = '_all'
                
                merge_cmd.extend(["--default-track-flag", sub["StreamOrder"]+":0"])
                if test_if_forced(sub):
                    merge_cmd.extend(["--forced-display-flag", sub["StreamOrder"]+":1"])
                    language_and_type = language + '_forced' + type_sub
                    if language_and_type not in dic_language_list_track_ID:
                        dic_language_list_track_ID[language_and_type] = [sub["StreamOrder"]]
                    else:
                        dic_language_list_track_ID[language_and_type].append(sub["StreamOrder"])
                elif test_if_hearing_impaired(sub):
                    merge_cmd.extend(["--hearing-impaired-flag", sub["StreamOrder"]+":1"])
                    language_and_type = language + '_hearing' + type_sub
                    if language_and_type not in dic_language_list_track_ID:
                        dic_language_list_track_ID[language_and_type] = [sub["StreamOrder"]]
                    else:
                        dic_language_list_track_ID[language_and_type].append(sub["StreamOrder"])
                elif test_if_dubtitle(sub):
                    language_and_type = language + '_dubtitle' + type_sub
                    if language_and_type not in dic_language_list_track_ID:
                        dic_language_list_track_ID[language_and_type] = [sub["StreamOrder"]]
                    else:
                        dic_language_list_track_ID[language_and_type].append(sub["StreamOrder"])
                else:
                    language_and_type = language + '_aa' + type_sub
                    if language_and_type not in dic_language_list_track_ID:
                        dic_language_list_track_ID[language_and_type] = [sub["StreamOrder"]]
                    else:
                        dic_language_list_track_ID[language_and_type].append(sub["StreamOrder"])
                if tools.dev:
                    sys.stderr.write(f"\t\tTrack {sub["StreamOrder"]} with md5 {sub['MD5']} added for {language}.\n")
            else:
                track_to_remove.add(sub["StreamOrder"])
                if tools.dev:
                    if sub['MD5'] in md5_sub_already_added:
                        sys.stderr.write(f"\t\tTrack {sub["StreamOrder"]} with md5 {sub['MD5']} not added for {language}. It have the same md5 as other track added.\n")
                    else:
                        sys.stderr.write(f"\t\tTrack {sub["StreamOrder"]} with md5 {sub['MD5']} not added for {language}. It is not keep.\n")
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

def set_keep_language(video_obj):
    """
    Set the keep language for the video object
    :param video_obj: video object to set the keep language
    :return:
    """
    
    if len(video_obj.keys-tools.language_to_keep):
        for language,audios in video_obj.audios.items():
            if language not in tools.language_to_keep:
                for audio in audios:
                    audio['keep'] = False
                
    for language,audios in video_obj.commentary.items():
        if language not in tools.language_to_keep:
            for audio in audios:
                audio['keep'] = False
                
    for language,audios in video_obj.audiodesc.items():
        if language not in tools.language_to_keep:
            for audio in audios:
                audio['keep'] = False
    
    if tools.remove_sub_language_not_keep:
        for language,subs in video_obj.subtitles.items():
            if language not in tools.language_to_keep:
                for sub in subs:
                    sub['keep'] = False

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
    elif int(audio.get("StreamSize", 1)) == 0 or float(audio.get("Duration", 1)) == 0:
        sys.stderr.write(f"Skip the element {audio['StreamOrder']}, it seems to be empty\n")
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
                cmd_convert.extend(["-exact_rice_parameters", "1"])
        tmp_file_convert = path.join(tools.tmpFolder,f"{video_obj.fileBaseName}_{audio['StreamOrder']}_tmp.mkv")
        cmd_convert.extend(["-t", duration_best_video, tmp_file_convert])
        ffmpeg_cmd_dict['convert_process'].append(video.ffmpeg_pool_audio_convert.apply_async(tools.launch_cmdExt, (cmd_convert,)))
        sys.stderr.write(str(cmd_convert)+"\n")
        ffmpeg_cmd_dict['merge_cmd'].extend(["--no-global-tags", "-M", "-B", tmp_file_convert])
        return 1

def generate_new_file(video_obj,ffmpeg_cmd_dict,md5_audio_already_added,md5_sub_already_added,duration_best_video):
    base_cmd = [tools.software["ffmpeg"], "-err_detect", "crccheck", "-err_detect", "bitstream",
                    "-err_detect", "buffer", "-err_detect", "explode", "-fflags", "+genpts+igndts",
                    "-probesize", "500M",
                    "-threads", str(tools.core_to_use), "-vn"]
    
    number_track = 0
    for language,subs in video_obj.subtitles.items():
        for sub in subs:
            # Skip empty stream
            if int(sub.get("StreamSize", 1)) == 0 or float(sub.get("Duration", 1)) == 0:
                sys.stderr.write(f"Skip the element {sub['StreamOrder']}, it seems to be empty\n")
            elif (sub['keep'] and sub['MD5'] not in md5_sub_already_added):
                number_track += 1
                tmp_file_extract = path.join(tools.tmpFolder,f"{video_obj.fileBaseName}_{sub['StreamOrder']}_tmp_extr.mkv")
                extract_stream(video_obj, "subtitle", sub['StreamOrder'], tmp_file_extract)
                cmd_convert = base_cmd.copy()
                if (not sub["ffmpeg_compatible"]) and 'properties' in sub and 'codec' in sub['properties'] and sub['properties']['codec'].lower() in tools.to_convert_ffmpeg_type:
                    cmd_convert.append(tools.to_convert_ffmpeg_type[sub['properties']['codec'].lower()][0])
                cmd_convert.extend(["-i", tmp_file_extract,
                     "-map", "0:a?", "-map", "0:s?", "-map_metadata", "0", "-copy_unknown",
                     "-movflags", "use_metadata_tags", "-c", "copy"])
                
                if sub['MD5'] != '':
                    md5_sub_already_added.add(sub['MD5'])
                codec = sub["Format"].lower()
                if (not sub["ffmpeg_compatible"]) and 'properties' in sub and 'codec' in sub['properties'] and sub['properties']['codec'].lower() in tools.to_convert_ffmpeg_type:
                    cmd_convert.append(f"-c:s")
                    cmd_convert.append(tools.to_convert_ffmpeg_type[sub['properties']['codec'].lower()][1])
                elif codec in tools.sub_type_not_encodable:
                    cmd_convert.extend(["-copyts", "-avoid_negative_ts", "disabled"])
                    cmd_convert.remove("-fflags")
                    cmd_convert.remove("+genpts+igndts")
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
    source_video_metadata.calculate_md5_streams()
    
    if source_video_metadata.video['language_iso'] != "und":
        language = source_video_metadata.video['Language'].split("-")[0]
        tools.special_params["original_language"] = language
        tools.language_to_keep.append(language)
    
    generate_new_file(source_video_metadata,ffmpeg_cmd_dict,md5_audio_already_added,md5_sub_already_added,source_video_metadata.video['Duration'])
    
    out_path_tmp_file_name_split = path.join(tools.tmpFolder,f"{source_video_metadata.fileBaseName}_merged_split.mkv")
    merge_cmd = [tools.software["mkvmerge"], "-o", out_path_tmp_file_name_split]
    merge_cmd.extend(ffmpeg_cmd_dict['merge_cmd'])
    for convert_process in ffmpeg_cmd_dict['convert_process']:
        convert_process.get()
    try:
        tools.launch_cmdExt_with_timeout_reload(merge_cmd, 2, 1200)
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
                sys.stderr.write(str(e))
        else:
            raise e

    if tools.dev:
        sys.stderr.write(f'\t\tFile {out_path_tmp_file_name_split} produce\n')
    
    tools.launch_cmdExt_with_timeout_reload([tools.software["ffmpeg"], "-err_detect", "crccheck", "-err_detect", "bitstream",
                         "-err_detect", "buffer", "-err_detect", "explode", "-analyzeduration", "0", "-probesize", "500M", "-threads", str(tools.core_to_use),
                         "-i", out_path_tmp_file_name_split, "-map", "0", "-f", "null", "-c", "copy", "-"], 2, 360)
    
    if tools.dev:
        sys.stderr.write(f"\t\tGet metadata {out_path_tmp_file_name_split}\n")
    out_video_metadata = video.video(tools.tmpFolder,path.basename(out_path_tmp_file_name_split))
    out_video_metadata.get_mediadata()
    out_video_metadata.video = source_video_metadata.video
    if tools.dev:
        sys.stderr.write(f"\t\tCalculate the md5 for streams\n")
    out_video_metadata.calculate_md5_streams_split()
    
    if tools.dev:
        sys.stderr.write(f"\t\tPrepare the final command\n")

    final_insert = [tools.software["mkvmerge"], "-o", out]
    
    file_video_metadata = video.video(path.dirname(file),path.basename(file))
    file_video_metadata.get_mediadata()
    if file_video_metadata.multiples_video:
        final_insert.extend(["-A", "-S", "--no-chapters", "-M", "-B", "--no-global-tags", file_video_metadata.video['ID'], file])
    else:
        final_insert.extend(["-A", "-S", "--no-chapters", "-M", "-B", "--no-global-tags", file])
    
    list_track_order=[]
    global default_audio
    default_audio = True

    if tools.keep_only_language:
        set_keep_language(out_video_metadata)

    if tools.dev:
        sys.stderr.write(f"\t\tKeep the best audio\n")
    
    for audio_language in out_video_metadata.audios.keys():
        find_differences_and_keep_best_audio(out_video_metadata,audio_language,decript_merge_rules(tools.mergeRules['audio']))
    out_video_metadata.remove_tmp_files()

    number_track_audio = generate_merge_command_insert_ID_audio_track_to_remove_and_new_und_language(final_insert,out_video_metadata.audios,out_video_metadata.commentary,out_video_metadata.audiodesc,set(),list_track_order)
    
    for language,subs in out_video_metadata.subtitles.items():
        sub_same_md5 = {}
        keep_sub = {'ass':[],'srt':[]}
        for sub in subs:
            if sub['MD5'] in sub_same_md5:
                sub_same_md5[sub['MD5']].append(sub)
            else:
                sub_same_md5[sub['MD5']] = [sub]
        for sub_md5,subs in sub_same_md5.items():
            if len(subs) > 1:
                if tools.dev:
                    sys.stderr.write(f"\t\tMultiple MD5 text for {language}:\n")
                have_srt_sub = False
                have_ass_sub = False
                for sub in subs:
                    codec = sub['ffprobe']["codec_name"].lower()
                    if codec in tools.sub_type_near_srt and (not have_srt_sub):
                        have_srt_sub = True
                        keep_sub["srt"].append(sub)
                        if tools.dev:
                            sys.stderr.write(f"\t\t\tFirst SRT found for {language} with MD5 text\n")
                    elif codec in tools.sub_type_near_srt:
                        sub['keep'] = False
                        if tools.dev:
                            sys.stderr.write(f"\t\t\tAnother SRT found for {language} with MD5 text\n")
                    elif codec not in tools.sub_type_not_encodable:
                        sub['keep'] = False
                        if tools.dev:
                            sys.stderr.write(f"\t\t\tASS found for {language} with MD5 text\n")
                        have_ass_sub = True
                    else:
                        sub['keep'] = False
                if (not have_srt_sub):
                    subs[0]['keep'] = True
                    if tools.dev:
                        sys.stderr.write(f"\t\tNo SRT sub found for language {language} with MD5 text\n")
                    if subs[0]['ffprobe']["codec_name"].lower() not in tools.sub_type_not_encodable:
                        keep_sub["ass"].append(subs[0])
                        if tools.dev:
                            sys.stderr.write(f"\t\tSo, the stream {subs[0]['StreamOrder']} is a ASS for language {subs[0]['Language']} and it will be kept.\n")
                elif have_srt_sub and have_ass_sub:
                    if tools.dev:
                        sys.stderr.write(f"\t\tSRT and ASS found for {language} with same MD5 text\n")
                
            else:
                codec = subs[0]['ffprobe']["codec_name"].lower()
                if codec in tools.sub_type_near_srt:
                    keep_sub["srt"].append(subs[0])
                elif codec not in tools.sub_type_not_encodable:
                    keep_sub["ass"].append(subs[0])
        
        if len(keep_sub["srt"]) and len(keep_sub["ass"]):
            not_keep_ass_converted_in_srt(out_path_tmp_file_name_split,keep_sub["ass"],keep_sub["srt"])

    clean_number_stream_to_be_lover_than_max(max_stream-1-number_track_audio,out_video_metadata.subtitles)

    generate_merge_command_insert_ID_sub_track_set_not_default(final_insert,out_video_metadata.subtitles,set(),list_track_order)
    final_insert.extend(["-D", out_path_tmp_file_name_split])
    final_insert.extend(ffmpeg_cmd_dict['metadata_cmd'])
    final_insert.extend(["--track-order", f"0:0,1:"+",1:".join(list_track_order)])
    tools.launch_cmdExt_with_timeout_reload(final_insert, 2, 1200)
    if tools.dev:
        sys.stderr.write("\t\tFile produce\n")
    
    tools.launch_cmdExt_with_timeout_reload([tools.software["ffmpeg"], "-err_detect", "crccheck", "-err_detect", "bitstream",
                         "-err_detect", "buffer", "-err_detect", "explode", "-analyzeduration", "0", "-probesize", "500M", "-threads", str(tools.core_to_use),
                         "-i", out, "-map", "0", "-f", "null", "-c", "copy", "-"], 2, 360)