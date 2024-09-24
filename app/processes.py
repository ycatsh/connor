import os
import shutil
import string
import numpy as np
import configparser

from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer
from sklearn.decomposition import LatentDirichletAllocation
from sklearn.feature_extraction.text import TfidfVectorizer
from sentence_transformers import SentenceTransformer, util

from app.reader import read_files
from app import data_path


# Initializing the dependencies for the model and other functions
model = SentenceTransformer('sentence-transformers/paraphrase-MiniLM-L6-v2')
stop_words = set(stopwords.words('english'))
lemmatizer = WordNetLemmatizer()
TOPICS = 100

# Initializing the LDA model and Vectorizer
lda_model = LatentDirichletAllocation(n_components=TOPICS, learning_decay=0.7, random_state=0)
vectorizer = TfidfVectorizer(max_df=0.8, min_df=3, stop_words='english')


# pre-processesing the text to focus on relevant content
def preprocess(text):
    text = text.translate(str.maketrans('', '', string.punctuation))
    text = [lemmatizer.lemmatize(word.lower()) for word in text.split() if word.lower() not in stop_words]
    return ' '.join(text)


# Returns a tuple of files names and corresponding content
def get_file_word_list(path, word_limit):
    return [(file, preprocess(content)) for file, content in read_files(path, word_limit)]


# Cosine similarity calculation
def calculate_similarity(first, rest):
    embeddings = model.encode([first, rest], convert_to_tensor=True)
    sim = util.cos_sim(embeddings[0], embeddings[1]).item()

    return sim


# Files that have a similarity score over a certain threshold are grouped together
def sim_organize(simlarity_threshold, words_list, file_names=False):
    grouped_files = set()
    file_groups = {}

    for parent_files in words_list:
        if parent_files[0] not in grouped_files:
            for other_files in words_list:
                if parent_files != other_files and other_files[0] not in grouped_files:
                    if file_names:
                        score = calculate_similarity(parent_files[0], other_files[0])
                    else:
                        score = calculate_similarity(parent_files[0]+parent_files[1], other_files[1])

                    if score >= simlarity_threshold: # similarity threshold decided by user (default: 50%)
                        if parent_files[0] not in file_groups:
                            file_groups[parent_files[0]] = [parent_files[0]]

                        file_groups[parent_files[0]].append(other_files[0])
                        grouped_files.add(other_files[0])

            grouped_files.add(parent_files[0])

    return file_groups


# Generating names for the folders 
def name_category(text_list, folder_word_limit):
    topic_words = {}

    text_vectorized = vectorizer.transform(text_list)
    topic_distribution = lda_model.transform(text_vectorized)
    feature_names = vectorizer.get_feature_names_out()

    for topic, comp in enumerate(lda_model.components_):
        top_words = [feature_names[i] for i in comp.argsort()[-folder_word_limit:]] # Folder word length limit 
        topic_words[topic] = top_words

    max_topic_index = np.argmax(topic_distribution)
    sorted_topic_indices = np.argsort(topic_distribution, axis=1)[0][::-1]

    for topic_index in sorted_topic_indices:
        if topic_index in topic_words:
            max_topic_index = topic_index
            break

    topic_words[max_topic_index] = [word.capitalize() for word in topic_words[max_topic_index]]
    new_folder_name = "_".join(topic_words[max_topic_index])

    return new_folder_name


# Handles moving files
def move_file(parent_dir, file_name, category_dir):
    source_path = os.path.join(parent_dir, file_name)
    destination_path = os.path.join(category_dir, file_name)

    shutil.move(source_path, destination_path)


# Organizing files that are similar (determined using NLP)
def move_organize(path, folders_dict, words_list, file_names, folder_word_limit):
    for _, similar_files in folders_dict.items():

        content = [os.path.splitext(files[0])[0] if file_names else files[1] for files in words_list if files[0] in similar_files]
        new_dir = os.path.join(path, name_category(content, folder_word_limit)) # Name of the folder determined using topic modeling

        if not os.path.exists(new_dir):
            os.mkdir(new_dir)

        for file_name in similar_files:
            move_file(path, file_name, new_dir)


# Handling files that cannot be organized (misc)
def misc_organize(path):
    config = configparser.ConfigParser()
    config.read(os.path.join(data_path, "config.ini"))
    exts = config['Extension_Map']

    misc_files =  [file.name for file in os.scandir(path) if file.is_file()]

    misc_dir = os.path.join(path, "Miscellaneous")
    if not os.path.exists(misc_dir):
        os.mkdir(misc_dir)

    for misc_file in misc_files:
        file_ext = os.path.splitext(misc_file)[1]
        file_ext = file_ext[1:]
        parent_path = None
        for key, value in exts.items():
            if file_ext in value.split():
                parent_path = os.path.join(misc_dir, key.capitalize())
                break

        parent_path = os.path.join(misc_dir, key.capitalize()) if parent_path else os.path.join(misc_dir, file_ext)

        if os.path.exists(parent_path):
            move_file(path, misc_file, parent_path)
        else:
            os.mkdir(parent_path)
            move_file(path, misc_file, parent_path)


# Organizing inside the generated folders
def sub_organize(path, word_limit, file_names, folder_word_limit):
    for folder in os.listdir(path):
        sub_folder = os.path.join(path, folder)
        files = os.listdir(sub_folder)

        if len(files) > 6:
            sub_file_word_list = get_file_word_list(sub_folder, word_limit)
            sub_folder_dict = sim_organize(0.8, sub_file_word_list, file_names) # Grouped only if similarity >=80%
            
            if len(sub_folder_dict) > 1:
                move_organize(sub_folder, sub_folder_dict, sub_file_word_list, file_names, folder_word_limit)


# Organizing the folder provided by the user
def organize(path, file_dict, word_list, file_names, word_limit, folder_word_limit):
    move_organize(path, file_dict, word_list, file_names, folder_word_limit)
    misc_organize(path)
    sub_organize(path, word_limit, file_names, folder_word_limit)

    return
