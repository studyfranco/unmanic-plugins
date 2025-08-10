#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
    Written by:              studyfranco
    Date:                    2025-07-16

    Copyright:
        Copyright (C) 2025 studyfranco

        This program is free software: you can redistribute it and/or modify it under the terms of the GNU General
        Public License as published by the Free Software Foundation, version 3.

        This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the
        implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License
        for more details.

        You should have received a copy of the GNU General Public License along with this program.
        If not, see <https://www.gnu.org/licenses/>.

"""
import logging
from re import compile,IGNORECASE
import os
from datetime import date, timedelta, datetime
from sqlalchemy import create_engine, Column, String, Date, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from unmanic.libs.directoryinfo import UnmanicDirectoryInfo
from unmanic.libs.unplugins.settings import PluginSettings

# Configure plugin logger
logger = logging.getLogger("Unmanic.Plugin.file_selector_studyfranco")


class Settings(PluginSettings):
    settings = {
        "name_patterns": ".*\\.mkv$,.*\\.mp4$,.*\\.avi$",
        "exclude_patterns": "",
        "database_url": "sqlite:///config/.unmanic/unmanic_processed_files.db",
        "case_sensitive": True,
        "exclude_files_younger_than": 0,
    }
    

    def __init__(self, *args, **kwargs):
        super(Settings, self).__init__(*args, **kwargs)
        self.form_settings = {
            "name_patterns": {
                "label": "Motifs de nom de fichier (regex séparés par des virgules)",
                "input_type": "textarea",
            },
            "exclude_patterns": {
                "label": "Motifs à exclure (regex séparés par des virgules)",
                "input_type": "textarea",
            },
            "database_url": {
                "label": "URL de la base de données (sqlite:///path/to/db.sqlite ou postgresql://user:pass@host/dbname)",
                "input_type": "textarea",
            },
            "case_sensitive": {
                "label": "Recherche sensible à la casse",
            },
            "exclude_files_younger_than": {
                "label": "Exclure les fichiers plus récents que (en jours)",
                "input_type":     "slider",
                "slider_options": {
                    "min": 0,
                    "max": 366,
                },
            },
        }

Base = declarative_base()

class ProcessedFile(Base):
    """Table de suivi des traitements."""

    __tablename__ = "processed_files"

    path = Column(String, primary_key=True)
    date_processed = Column(Date, nullable=False, index=True)

def setup_database(database_url, create_tables=True):
    """Configuration complète de la base de données"""
    # Créer l'engine
    engine = create_engine(database_url, echo=True)
    
    # Créer les tables si demandé
    if create_tables:
        Base.metadata.create_all(engine)
    
    # Configurer la session
    Session = sessionmaker(bind=engine)

    return Session()

def on_library_management_file_test(data):
    """
    Runner function - enables additional actions during the library management file tests.

    The 'data' object argument includes:
        path                            - String containing the full path to the file being tested.
        issues                          - List of currently found issues for not processing the file.
        add_file_to_pending_tasks       - Boolean, is the file currently marked to be added to the queue for processing.

    :param data:
    :return:

    """
    # Get the path to the file
    abspath = data.get('path')
    basename = os.path.basename(abspath)

    # Configure settings object
    settings = Settings(library_id=data.get('library_id'))
    
    # Check if the file is excluded based on the exclude_files_younger_than setting
    exclude_files_younger_than = settings.get_setting('exclude_files_younger_than')
    if exclude_files_younger_than == 0 or datetime.fromtimestamp(os.stat(abspath).st_mtime) < (datetime.now() - timedelta(days=exclude_files_younger_than)):
        file_to_include = False
        flags = 0 if settings.get_setting('case_sensitive') else IGNORECASE
        
        for regex in settings.get_setting('name_patterns').split(','):
            if len(regex) and (not file_to_include):
                if compile(regex,flags=flags).match(basename):
                    file_to_include = True
                    logger.debug("File '{}' matches name pattern '{}'.".format(abspath, regex))
        
        if file_to_include:
            for regex in settings.get_setting('exclude_patterns').split(','):
                if len(regex):
                    if compile(regex,flags=flags).match(basename):
                        data['add_file_to_pending_tasks'] = False
                        data['issues'].append("File '{}' matches exclude pattern '{}'.".format(abspath, regex))
                        logger.debug("File '{}' matches exclude pattern '{}'.".format(abspath, regex))
                        return data
        else:
            data['add_file_to_pending_tasks'] = False
            data['issues'].append("File '{}' does not match any include patterns.".format(abspath))
            logger.debug("File '{}' does not match any include patterns.".format(abspath))
            return data
    else:
        data['add_file_to_pending_tasks'] = False
        data['issues'].append("File '{}' is younger than the exclude_files_younger_than setting.".format(abspath))
        logger.debug("File '{}' is younger than the exclude_files_younger_than setting.".format(abspath))
        return data

    try:
        with setup_database(settings.get_setting('database_url')) as db_session:
            if len(db_session.query(ProcessedFile).filter(ProcessedFile.path == abspath).all()):
                data['add_file_to_pending_tasks'] = False
                data['issues'].append("File '{}' has already been processed.".format(abspath))
                logger.debug("File '{}' has already been processed.".format(abspath))
                return data
    except Exception as e:
        logger.error(f"Database error while checking processed files: {e}")
        # In case of database error, allow processing to continue
        logger.warning(f"Continuing with file processing due to database error: {abspath}")

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
    # If the task was successful, mark the file as processed
    if data.get('task_processing_success') and data.get('file_move_processes_success'):
        settings = Settings(library_id=data.get('library_id'))
        database_url = settings.get_setting('database_url')
        
        # Get the source file path
        source_path = data.get('source_data', {}).get('abspath')
        if source_path != None and source_path != "":
            try:
                with setup_database(settings.get_setting('database_url')) as db_session:
                    # Add the processed file to the database
                    processed_file = ProcessedFile(
                        path=source_path,
                        date_processed=date.today()
                    )
                    db_session.add(processed_file)  # Use merge to handle duplicates
                    db_session.commit()
                    logger.info(f"Marked file as processed: {source_path}")
            except Exception as e:
                logger.error(f"Failed to mark file as processed: {e}")
    
    return data