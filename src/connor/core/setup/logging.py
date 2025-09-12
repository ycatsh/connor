import logging


def setup_logging() -> logging.Logger:
    """
    Set up logging.

    Returns:
        Configured Logger object.
    """
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger()
    logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
    return logger
