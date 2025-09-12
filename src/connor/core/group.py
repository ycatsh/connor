from typing import List, Tuple, Dict, Any

from numpy import dot
from numpy.linalg import norm


def calculate_similarity(embeddings: List) -> float:
    """
    Calculate cosine similarity between two embeddings.
    """
    return dot(embeddings[0], embeddings[1]) / (norm(embeddings[0]) * norm(embeddings[1]))


def group_files_into_dict(
    model: Any,
    files_list: List[Tuple[str, str]],
    similarity_threshold: float
) -> Dict[str, List[str]]:
    """
    Organize files into a dictionary by similarity using cosine similarity.

    Args:
        model: The sentence-tranformers model.
        files_list: List of tuples (file_name, content).
        sim_threshold: Similarity threshold for grouping.

    Returns:
        Dictionary mapping a representative file to a list of similar files.
    """
    grouped_files = set()
    grouped_files_dict = {}
    embeddings = model.encode([pair[1] for pair in files_list], convert_to_tensor=True)

    for i, parent_files in enumerate(files_list):
        if parent_files[0] not in grouped_files:
            for j, other_files in enumerate(files_list):
                if i != j and other_files[0] not in grouped_files:
                    score = calculate_similarity([embeddings[i], embeddings[j]])

                    if score >= similarity_threshold:
                        if parent_files[0] not in grouped_files_dict:
                            grouped_files_dict[parent_files[0]] = [parent_files[0]]

                        grouped_files_dict[parent_files[0]].append(other_files[0])
                        grouped_files.add(other_files[0])

            grouped_files.add(parent_files[0])

    return grouped_files_dict