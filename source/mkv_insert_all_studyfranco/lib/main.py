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

import argparse
from datetime import datetime
from multiprocessing import Pool
from os import path,chdir
import traceback
import tools
import json
import multiprocessing

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='This script process mkv,mp4 file to generate best file', formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("-f", "--file", metavar='file', type=str,
                       required=True, help="File processed")
    parser.add_argument("-s", "--source", metavar='source', type=str,
                       required=True, help="File source")
    parser.add_argument("-o","--out", metavar='outfile', type=str, required=True, help="Output file")
    parser.add_argument("-l","--louis", metavar='louis', type=str, default="False", help="louis parametres")
    parser.add_argument("--pwd", metavar='pwd', type=str,
                        default=".", help="Path to the software, put it if you use the folder from another folder")
    parser.add_argument("--tmp", metavar='tmpdir', type=str,
                        default="/tmp", help="Folder where send temporar files")
    parser.add_argument("--language_keep", metavar='language_keep', type=str,default="", help="List of languages to keep in the format iso 2 letter: fr,en,de")
    parser.add_argument("--remove_sub_language_not_keep", metavar='remove_sub_language_not_keep', type=str,default="False", help="Remove the subtitles not in the language to keep")
    args = parser.parse_args()
    
    chdir(args.pwd)
    tools.tmpFolder = path.join(args.tmp,"mkv_insert_"+str(datetime.now().strftime("%Y-%m-%d_%H:%M:%S")))
    tools.tmpFolder_original = tools.tmpFolder
    
    try:
        if args.louis == "True":
            tools.louis = True
        
        if args.language_keep != "":
            tools.keep_only_language = True
            tools.language_to_keep = args.language_keep.split(",")
        
            if args.remove_sub_language_not_keep == "True":
                tools.remove_sub_language_not_keep = True

        if (not tools.make_dirs(tools.tmpFolder)):
            raise Exception("Impossible to create the temporar dir")

        tools.core_to_use = multiprocessing.cpu_count()-2
        if tools.core_to_use < 1:
            tools.core_to_use = 1

        import mergeVideo
        import video
        
        video.ffmpeg_pool_audio_convert = Pool(processes=tools.core_to_use)
        video.ffmpeg_pool_big_job = Pool(processes=1)
        
        with open("titles_subs_group.json") as titles_subs_group_file:
            tools.group_title_sub = json.load(titles_subs_group_file)

        mergeVideo.merge_videos(args.file, args.source, args.out)
        tools.remove_dir(tools.tmpFolder)
    except:
        tools.remove_dir(tools.tmpFolder)
        traceback.print_exc()
        exit(1)
    exit(0)