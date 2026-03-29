from typing import List, Tuple, Dict, Any
from collections import defaultdict

import numpy as np
from sklearn.cluster import KMeans


def group_files_into_dict(
    model: Any,
    files_list: List[Tuple[str, str]],
) -> Dict[str, List[str]]:
    """
    Organize files into clusters using KMeans.

    Args:
        model: SentenceTransformer model.
        files_list: List of tuples (file_name, content).

    Returns:
        Dictionary mapping a representative file to a list of similar files.
    """

    if not files_list:
        return {}

    file_names = [pair[0] for pair in files_list]
    texts = [pair[1] for pair in files_list]

    embeddings = model.encode(texts, normalize_embeddings=True)
    X = np.array(embeddings)

    n_clusters = int(len(files_list) ** 0.5)

    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    labels = kmeans.fit_predict(X)

    raw_clusters = defaultdict(list)

    for name, label in zip(file_names, labels):
        raw_clusters[label].append(name)

    grouped_files_dict = {}

    for label, files in raw_clusters.items():
        parent = files[0]
        grouped_files_dict[parent] = files

    return grouped_files_dict