import os
import warnings
from pathlib import Path
from typing import Any, Set, Tuple

from sentence_transformers import SentenceTransformer
from sklearn.feature_extraction.text import TfidfVectorizer

from .config import get_model_cache_dir, load_stopwords


def _setup_cache_environment(cache_dir: Path) -> None:
    """
    Configure environment variables for model caching.

    Args:
        cache_dir: Directory to store cached models.
    """
    os.makedirs(cache_dir, exist_ok=True)

    os.environ["HF_HOME"] = str(cache_dir)
    os.environ["HF_HUB_CACHE"] = str(cache_dir)


def _load_embedding_model(cache_dir: Path) -> SentenceTransformer:
    """
    Load the sentence embedding model with caching.

    Args:
        cache_dir: Directory for caching model files.

    Returns:
        Loaded SentenceTransformer model.
    """
    return SentenceTransformer(
        "BAAI/bge-base-en-v1.5",
        cache_folder=str(cache_dir),
    )


def _initialize_vectorizer() -> TfidfVectorizer:
    """
    Initialize TF-IDF vectorizer.

    Returns:
        Configured TfidfVectorizer instance.
    """
    return TfidfVectorizer(
        max_df=0.8,
        min_df=2,
        stop_words="english",
    )


def initialize_models() -> Tuple[Any, Set[str], TfidfVectorizer]:
    """
    Initialize all models and dependencies required for the pipeline.

    This includes:
    - Sentence embedding model (cached locally)
    - Stopwords
    - TF-IDF vectorizer

    Returns:
        Tuple containing:
            model: SentenceTransformer instance
            stop_words: Set of stopwords
            vectorizer: TF-IDF vectorizer
    """
    warnings.filterwarnings("ignore")

    print("Initializing models...")

    cache_dir = get_model_cache_dir()
    _setup_cache_environment(cache_dir)

    print(f"Cache directory: {cache_dir}")

    model = _load_embedding_model(cache_dir)
    print("Embedding model loaded")

    stop_words = load_stopwords()
    print("Stopwords loaded")

    vectorizer = _initialize_vectorizer()
    print("TF-IDF vectorizer ready")

    return model, stop_words, vectorizer
