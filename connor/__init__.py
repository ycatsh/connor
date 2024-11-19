import warnings
import logging
import sys
import os


# Managing Paths
def get_path(relative_path):
    if getattr(sys, 'frozen', False):
        base_path = os.path.dirname(sys.executable)
    else:
        base_path = os.path.abspath(os.path.dirname(__file__))

    return os.path.join(base_path, relative_path)

static_path = get_path('static')
font_path = get_path('fonts')
data_path = get_path('data')
tmp_path = get_path('tmp')


# Organization Parameters and Models
TOPICS = 30
MISCELLANEOUS_FOLDER_NAME = "_misc"

def initialize_dependencies():
    # Load imports on demand
    from sklearn.decomposition import LatentDirichletAllocation
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sentence_transformers import SentenceTransformer
    from nltk.corpus import stopwords
    import nltk
    
    # Logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)
    logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
    warnings.filterwarnings("ignore")

    print("Downloading dependencies...")
    logger.info("Initializing Sentence Transformer model...")
    try:
        model = SentenceTransformer('sentence-transformers/paraphrase-MiniLM-L6-v2')
        logger.info("Sentence Transformer model downloaded successfully.")
    except Exception as e:
        logger.error("Error downloading Sentence Transformer model: %s", e)
        return None, None, None, None

    logger.info("Setting up NLTK stop words...")
    nltk.download('stopwords', quiet=True)
    stop_words = set(stopwords.words('english'))
    logger.info("NLTK component set up successfully.")

    logger.info("Initializing LDA model with %d topics...", TOPICS)
    lda_model = LatentDirichletAllocation(n_components=TOPICS, learning_decay=0.7, random_state=0)
    logger.info("LDA model initialized successfully.")

    logger.info("Initializing TF-IDF Vectorizer...")
    vectorizer = TfidfVectorizer(max_df=0.8, min_df=2, stop_words='english')
    logger.info("TF-IDF Vectorizer initialized successfully.")

    return model, stop_words, lda_model, vectorizer


# Initialize models
def init():
    if not os.path.exists(os.path.join(data_path, "init.txt")):
        with open(os.path.join(data_path, "init.txt"), 'w') as f:
            f.write('initialized')
        return initialize_dependencies()
    else:
        # Load imports on demand
        from sklearn.decomposition import LatentDirichletAllocation
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sentence_transformers import SentenceTransformer
        from nltk.corpus import stopwords

        model = SentenceTransformer('sentence-transformers/paraphrase-MiniLM-L6-v2')
        stop_words = set(stopwords.words('english'))
        lda_model = LatentDirichletAllocation(n_components=TOPICS, learning_decay=0.7, random_state=0)
        vectorizer = TfidfVectorizer(max_df=0.8, min_df=2, stop_words='english')
        return model, stop_words, lda_model, vectorizer