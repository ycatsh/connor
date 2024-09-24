import os
import shutil
import string
import numpy as np
import configparser
import warnings
import logging

from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer
from sklearn.decomposition import LatentDirichletAllocation
from sklearn.feature_extraction.text import TfidfVectorizer
from sentence_transformers import SentenceTransformer, util

from app.reader import read_files
from app import data_path


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
warnings.filterwarnings("ignore")
TOPICS = 100

def initialize_dependencies():
    logger.info("Initializing Sentence Transformer model...")
    try:
        model = SentenceTransformer('sentence-transformers/paraphrase-MiniLM-L6-v2')
        logger.info("Sentence Transformer model downloaded successfully.")
    except Exception as e:
        logger.error("Error downloading Sentence Transformer model: %s", e)
        return None, None, None, None

    logger.info("Setting up NLTK stop words and lemmatizer...")
    stop_words = set(stopwords.words('english'))
    lemmatizer = WordNetLemmatizer()
    logger.info("NLTK components set up successfully.")

    logger.info("Initializing LDA model with %d topics...", TOPICS)
    lda_model = LatentDirichletAllocation(n_components=TOPICS, learning_decay=0.7, random_state=0)
    logger.info("LDA model initialized successfully.")

    logger.info("Initializing TF-IDF Vectorizer...")
    vectorizer = TfidfVectorizer(max_df=0.8, min_df=3, stop_words='english')
    logger.info("TF-IDF Vectorizer initialized successfully.")

    return model, stop_words, lemmatizer, lda_model, vectorizer

# Check if initialization file exists
if not os.path.exists(os.path.join(data_path, "init.txt")):
    model, stop_words, lemmatizer, lda_model, vectorizer = initialize_dependencies()

    with open(os.path.join(data_path, "init.txt"), 'w') as f:
        f.write('initialized')
else:
    model = SentenceTransformer('sentence-transformers/paraphrase-MiniLM-L6-v2')
    stop_words = set(stopwords.words('english'))
    lemmatizer = WordNetLemmatizer()
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
def calculate_similarity(embeddings):
    return util.cos_sim(embeddings[0], embeddings[1]).item()


# Files that have a similarity score over a certain threshold are grouped together
def sim_organize(simlarity_threshold, words_list):
    grouped_files = set()
    file_groups = {}
    embeddings = model.encode([w[1] for w in words_list], convert_to_tensor=True)

    for i, parent_files in enumerate(words_list):
        if parent_files[0] not in grouped_files:
            for j, other_files in enumerate(words_list):
                if i != j and other_files[0] not in grouped_files:
                    score = calculate_similarity([embeddings[i], embeddings[j]])

                    if score >= simlarity_threshold: # similarity threshold decided by user (default: 50%)
                        if parent_files[0] not in file_groups:
                            file_groups[parent_files[0]] = [parent_files[0]]

                        file_groups[parent_files[0]].append(other_files[0])
                        grouped_files.add(other_files[0])

            grouped_files.add(parent_files[0])

    return file_groups


# Generating names for the folders 
def name_category(text_list, folder_word_limit=5, delimiter="_"):
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


# Handles moving files
def move_file(parent_dir, file_name, category_dir):
    source_path = os.path.join(parent_dir, file_name)
    destination_path = os.path.join(category_dir, file_name)

    shutil.move(source_path, destination_path)


# Organizing files that are similar (determined using NLP)
def move_organize(path, folders_dict, words_list, folder_word_limit):
    for _, similar_files in folders_dict.items():
        content = [files[1] for files in words_list if files[0] in similar_files]
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
        file_ext = os.path.splitext(misc_file)[1][1:]
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
def sub_organize(path, word_limit, folder_word_limit):
    for folder in os.listdir(path):
        sub_folder = os.path.join(path, folder)
        files = os.listdir(sub_folder)

        if len(files) > 6:
            sub_file_word_list = get_file_word_list(sub_folder, word_limit)
            sub_folder_dict = sim_organize(0.8, sub_file_word_list) # Grouped only if similarity >=80%
            
            if len(sub_folder_dict) > 1:
                move_organize(sub_folder, sub_folder_dict, sub_file_word_list,  folder_word_limit)


# Organizing the folder provided by the user
def organize(path, file_dict, word_list, word_limit, folder_word_limit):
    move_organize(path, file_dict, word_list, folder_word_limit)
    misc_organize(path)
    sub_organize(path, word_limit, folder_word_limit)

    return
