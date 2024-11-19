import os
import shutil
import string
import configparser

import numpy as np
from numpy import dot
from numpy.linalg import norm

from connor import (
    data_path, MISCELLANEOUS_FOLDER_NAME
)
from connor.reader import read_files


# pre-processesing the text to focus on relevant content
def preprocess(text, stop_words):
    text = text.translate(str.maketrans('', '', string.punctuation))
    text = [word.lower() for word in text.split() if word.lower() not in stop_words]
    return ' '.join(text)


# Returns a tuple of files names and corresponding content and the ones which are not text-based (i.e. misc)
def get_file_word_list(path, word_limit, stop_words):
    raw_text_based, misc = read_files(path, word_limit)
    text_based = [(file, preprocess(content, stop_words)) for file, content in raw_text_based if content]
    return text_based, misc


# Cosine similarity calculation
def calculate_similarity(embeddings):
    return dot(embeddings[0], embeddings[1]) / (norm(embeddings[0]) * norm(embeddings[1]))


# Files that have a similarity score over a certain threshold are grouped together
def sim_organize(model, simlarity_threshold, files_words_list, misc_list):
    grouped_files = set()
    file_groups = {}
    embeddings = model.encode([w[1] for w in files_words_list], convert_to_tensor=True)

    for i, parent_files in enumerate(files_words_list):
        if parent_files[0] not in grouped_files:
            is_misc = True
            for j, other_files in enumerate(files_words_list):
                if i != j and other_files[0] not in grouped_files:
                    score = calculate_similarity([embeddings[i], embeddings[j]])

                    if score >= simlarity_threshold: # similarity threshold decided by user (default: 50%)
                        if parent_files[0] not in file_groups:
                            file_groups[parent_files[0]] = [parent_files[0]]

                        file_groups[parent_files[0]].append(other_files[0])
                        grouped_files.add(other_files[0])
                        is_misc = False

            grouped_files.add(parent_files[0])
            if is_misc:
                misc_list.append(parent_files[0])

    return file_groups, misc_list


# Generating names for the folders 
def name_category(vectorizer, lda_model, text_list, folder_word_limit=5, delimiter="_"):
    if not text_list:
        return "Untitled"
    
    text_vectorized = vectorizer.transform(text_list)
    topic_distribution = lda_model.transform(text_vectorized)
    dominant_topic_index = np.argmax(topic_distribution, axis=1)[0]

    feature_names = vectorizer.get_feature_names_out()
    topic_words = lda_model.components_[dominant_topic_index]
    top_word_indices = topic_words.argsort()[-folder_word_limit:][::-1] # Folder word length limit
    top_words = [feature_names[i] for i in top_word_indices]
    
    capitalized_words = [word.capitalize() for word in top_words]
    folder_name = delimiter.join(capitalized_words)
    
    return folder_name


# Handling files that cannot be organized (misc)
def misc_handler(misc_files):
    config = configparser.ConfigParser()
    config.read(os.path.join(data_path, "config.ini"))
    exts = config['Extension_Map']
    misc_dir = {MISCELLANEOUS_FOLDER_NAME: {}}

    for misc_file in misc_files:
        file_ext = os.path.splitext(misc_file)[1][1:]
        parent = None
        for key, value in exts.items():
            if file_ext in value.split():
                parent = key
                break

        if parent:
            if parent not in misc_dir[MISCELLANEOUS_FOLDER_NAME]:
                misc_dir[MISCELLANEOUS_FOLDER_NAME][parent] = []
            misc_dir[MISCELLANEOUS_FOLDER_NAME][parent].append(misc_file)
        else:
            if file_ext not in misc_dir[MISCELLANEOUS_FOLDER_NAME]:
                misc_dir[MISCELLANEOUS_FOLDER_NAME][file_ext] = []
            misc_dir[MISCELLANEOUS_FOLDER_NAME][file_ext].append(misc_file)

    return misc_dir


# Re-name the folders with the names determined using topic modeling
def rename_folders(vectorizer, lda_model, folder_dict, files_words_list, folder_word_limit, misc_files):
    renamed_dict = {}
    for _, similar_files in folder_dict.items():
        content = [files[1] for files in files_words_list if files[0] in similar_files]
        folder_name = name_category(vectorizer, lda_model, content, folder_word_limit)
        renamed_dict[folder_name] = similar_files
    misc_dict = misc_handler(misc_files)

    return {**renamed_dict, **misc_dict}


# Handles moving files
def move_file(path, file_name, destination_path):
    source_file = os.path.join(path, file_name)
    destination_file = os.path.join(destination_path, file_name)

    if os.path.exists(source_file):
        shutil.move(source_file, destination_file)


# Organizing files that are similar (determined using NLP)
def base_organize(path, folder_dict):
    for folder, folder_content in folder_dict.items():
        folder_path = os.path.join(path, folder)

        if not os.path.exists(folder_path):
            os.mkdir(folder_path)
        
        # For sub-folders
        if isinstance(folder_content, dict):
            base_organize(folder_path, folder_content)

        # For misc-folder
        if isinstance(folder_content, dict) and folder == MISCELLANEOUS_FOLDER_NAME:
            for sub_folder, file_names in folder_content.items():
                for file_name in file_names:
                    move_file(path, file_name, os.path.join(folder_path, sub_folder))

        if isinstance(folder_content, list):
            for file_name in folder_content:
                move_file(path, file_name, folder_path)


# Organizing inside the generated folders
def sub_organize(path, folder_dict, word_limit, folder_word_limit):
    for folder, folder_content in folder_dict.items():
        sub_folder = os.path.join(path, folder)

        if len(folder_content) > 6:
            sub_file_word_list = get_file_word_list(sub_folder, word_limit)[0]
            sub_folder_dict = sim_organize(0.75, sub_file_word_list) # Grouped only if similarity >=75%

            if len(sub_folder_dict) > 1:
                sub_renamed_dict = rename_folders(sub_folder_dict, sub_file_word_list, folder_word_limit, misc_files={})
                base_organize(sub_folder, sub_renamed_dict)


# Organizing the folder provided by the user
def organize(path, folder_dict, word_limit, folder_word_limit):
    base_organize(path, folder_dict)
    sub_organize(path, folder_dict, word_limit, folder_word_limit)

    return
