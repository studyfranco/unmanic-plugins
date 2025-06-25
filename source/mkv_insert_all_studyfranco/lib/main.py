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
import multiprocessing

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='This script process mkv,mp4 file to generate best file', formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("-f", "--file", metavar='file', type=str,
                       required=True, help="File processed")
    parser.add_argument("-s", "--source", metavar='source', type=str,
                       required=True, help="File source")
    parser.add_argument("-o","--out", metavar='outfile', type=str, required=True, help="Output file")
    parser.add_argument("-l","--louis", metavar='louis', type=str, default="False", help="louis parametres")
    parser.add_argument("--tmp", metavar='tmpdir', type=str,
                        default="/tmp", help="Folder where send temporar files")
    args = parser.parse_args()
    
    chdir(args.pwd)
    tools.tmpFolder = path.join(args.tmp,"mkv_insert_"+str(datetime.now().strftime("%Y-%m-%d_%H:%M:%S")))
    
    try:
        if args.louis == "True":
            tools.louis = True

        if (not tools.make_dirs(tools.tmpFolder)):
            raise Exception("Impossible to create the temporar dir")

        tools.core_to_use = multiprocessing.cpu_count()

        import mergeVideo
        import video
        
        video.ffmpeg_pool_audio_convert = Pool(processes=tools.core_to_use)
        video.ffmpeg_pool_big_job = Pool(processes=multiprocessing.cpu_count())

        mergeVideo.merge_videos(args.file, args.source, args.out)
        tools.remove_dir(tools.tmpFolder)
    except:
        tools.remove_dir(tools.tmpFolder)
        traceback.print_exc()
        exit(1)
    exit(0)