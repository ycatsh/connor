import os
import warnings
from typing import Any, Set, Tuple

from sklearn.decomposition import LatentDirichletAllocation
from sklearn.feature_extraction.text import TfidfVectorizer
from sentence_transformers import SentenceTransformer

from .config import get_model_cache_dir, load_stopwords


def initialize_models(topics: int = 50) -> Tuple[Any, Set[str], LatentDirichletAllocation, TfidfVectorizer]:
    """
    Loads stopwords, loads SentenceTransformer, LDA model, and TF-IDF vectorizer.

    Args:
        topics: Number of topics for LDA model. Defaults to 50.

    Returns:
        Tuple containing:
            SentenceTransformer model
            Set of stopwords
            LDA model
            TF-IDF vectorizer
    """
    warnings.filterwarnings("ignore")

    print("Loading dependencies...")

    cache_dir = get_model_cache_dir()
    os.environ["TRANSFORMERS_CACHE"] = str(cache_dir)
    os.environ["SENTENCE_TRANSFORMERS_HOME"] = str(cache_dir)

    print(f"Using model cache directory: {cache_dir}")

    model = SentenceTransformer('sentence-transformers/paraphrase-MiniLM-L6-v2')
    print("Sentence Transformer loaded.")

    stop_words = load_stopwords()
    print("Stopwords loaded.")

    lda_model = LatentDirichletAllocation(n_components=topics, learning_decay=0.7, random_state=0)
    print("LDA model initialized.")

    vectorizer = TfidfVectorizer(max_df=0.8, min_df=2, stop_words='english')
    print("TF-IDF vectorizer initialized.")

    return model, stop_words, lda_model, vectorizer
