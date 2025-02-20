#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
    plugins.plugin.py

    Written by:               rosscop123 <rosscop123@me.com>
    Date:                     20 Feburary 2025, (21:49 PM)

    Copyright:
        Copyright (C) 2025 Ross McQuillan

        This program is free software: you can redistribute it and/or modify it under the terms of the GNU General
        Public License as published by the Free Software Foundation, version 3.

        This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the
        implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License
        for more details.

        You should have received a copy of the GNU General Public License along with this program.
        If not, see <https://www.gnu.org/licenses/>.

"""

import logging
import requests
import re

from unmanic.libs.unplugins.settings import PluginSettings

# Configure plugin logger
logger = logging.getLogger("Unmanic.Plugin.49916090")

class Settings(PluginSettings):
    settings = {
        "Radarr URL": "http://localhost:7878",
        "Radarr API Key": "",
        "Include/Exclude Tags": "Include",
        "Tags": "tag1, tag2",
    }
    form_settings = {
        "Include/Exclude Tags": {
            "input_type":     "select",
            "select_options": [
                {
                    'value': "include",
                    'label': "Include",
                },
                {
                    'value': "exclude",
                    'label': "Exclude",
                }
            ],
        },
    }

    def __init__(self, *args, **kwargs):
        super(Settings, self).__init__(*args, **kwargs)


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
    settings = Settings(library_id=data.get('library_id'))
    
    url = settings.get_setting("Radarr URL")
    api_key = settings.get_setting("Radarr API Key")

    include_tags = settings.get_setting("Include/Exclude Tags") == "include"
    tags = settings.get_setting("Tags").split(",")
    
    data_path = data["path"]
    match = re.search(r"\{tmdb-(\d+)\}", data_path)
    movie_id = match.group(1) if match else None

    tag_ids = get_tag_ids(url, api_key, tags)

    if movie_id is None:
        logger.error(f"Ignoring movie as no ID: {data_path}")
        data['add_file_to_pending_tasks'] = True
    else:
        movie_tags = get_movie_tags(url, api_key, movie_id)

        tag_has_been_found = False
        for tag in movie_tags:
            if tag in tag_ids:
                if include_tags:
                    # Tag found and trying to include movies based off of tags so add it to pending
                    tag_has_been_found = True
                    data['add_file_to_pending_tasks'] = True
                    continue
                else:
                    # Tag found and trying to exclude movies based off of tags so remove it to pending
                    tag_has_been_found = True
                    data['add_file_to_pending_tasks'] = False
                    data['issues'].append({
                        'id':      'Check For Tags',
                        'message': "Movie is contains at least one of the exclude tags",
                    })
                    continue
        
        if not tag_has_been_found:
            if include_tags:
                # Tag not found and trying to include movies based off of tags so remove it to pending
                data['add_file_to_pending_tasks'] = False
                data['issues'].append({
                    'id':      'Check For Tags',
                    'message': "Movie is missing at least one of the include tags",
                })
            else:
                # Tag not found and trying to exclude movies based off of tags so add it to pending
                data['add_file_to_pending_tasks'] = True

    return data

def get_movie_tags(url, api_key, movie_id):
    response = requests.get(f"{url}/api/v3/movie", params={"apiKey": api_key, "tmdbId": movie_id})
    
    tags = []

    if response.status_code != 200:
        logger.error(f"Error fetching movie {movie_id}: {response.text}")
    try:
        movies = response.json()
        if movies:
            tags = movies[0]['tags']
            if tags:
                logger.error(f"{tags}")
    except requests.exceptions.JSONDecodeError as e:
        logger.error(f"❌ Error decoding JSON: {e}")
        logger.error(f"❌ Response body: {response.text}")
    except Exception as e:
        logger.error(f"Error getting tags: {e}")
        logger.error(f"{response.json()}")

    return tags

def get_tag_ids(url, api_key, tag_names):
    tag_ids = []

    for tag_name in tag_names:
        response = requests.get(f"{url}/api/v3/tag", params={"apiKey": api_key})
        
        if response.status_code != 200:
            print(f"❌ Error fetching tags: {response.text}")
            return None
        
        tags = response.json()
        for tag in tags:
            if tag["label"].lower() == tag_name.rstrip().lower():
                tag_ids.append(tag["id"])
    
    return tag_ids