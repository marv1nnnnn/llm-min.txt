import logging

import tiktoken

logger = logging.getLogger(__name__)


def count_tokens(text: str, model_name: str = "gpt-4o") -> int:
    """Counts the number of tokens in a text string using tiktoken."""
    if not text:
        return 0
    try:
        encoding = tiktoken.encoding_for_model(model_name)
    except KeyError:
        logger.warning(f"Warning: model {model_name} not found. Using cl100k_base encoding.")
        encoding = tiktoken.get_encoding("cl100k_base")
    return len(encoding.encode(text))
