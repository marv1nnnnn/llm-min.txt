import logging
import os
from string import Template

# Import existing constants/templates and the PRE-LOADED guide content
from .compacter import compact_content_to_knowledge_base


logger = logging.getLogger(__name__)


class LLMMinClient:
    """
    Client for interacting with llm-min functionalities programmatically.
    """

    DEFAULT_MODEL = "gemini-2.5-flash"
    DEFAULT_MAX_TOKENS_PER_CHUNK = 10000
    # PCS_GUIDE_FILENAME = "pcs-guide.md" # No longer needed
    API_KEY_ENV_VAR = "GEMINI_API_KEY"

    def __init__(
        self,
        api_key: str | None = None,
        model: str = DEFAULT_MODEL,
        max_tokens_per_chunk: int = DEFAULT_MAX_TOKENS_PER_CHUNK,
    ):
        """
        Initializes the LLMMinClient.

        Args:
            api_key: The API key for the LLM service. If None, attempts to read
                     from the environment variable (e.g., GEMINI_API_KEY).
            model: The identifier for the LLM model to use.
            max_tokens_per_chunk: Maximum tokens allowed per chunk for processing.

        Raises:
            ValueError: If the API key is not provided and cannot be found in
                        the environment variables.
            RuntimeError: If the PCS guide content could not be loaded by the compacter module.
        """
        self.api_key = api_key or os.environ.get(self.API_KEY_ENV_VAR)
        if not self.api_key:
            raise ValueError(f"API key must be provided or set via the '{self.API_KEY_ENV_VAR}' environment variable.")

        self.model = model
        self.max_tokens_per_chunk = max_tokens_per_chunk

    async def compact(self, content: str, chunk_size: int | None = None, subject: str | None = None) -> str:
        """
        Compacts the given content into a knowledge base using the configured LLM.
        (Async version)

        Args:
            content: The content string to compact.
            chunk_size: Optional. The size of the chunks to divide the content into.
                        Defaults to self.max_tokens_per_chunk if None.
            subject: Optional. The subject of the content, used for context in compaction.

        Returns:
            The serialized knowledge base content.
        """
        actual_chunk_size = chunk_size if chunk_size is not None else self.max_tokens_per_chunk

        # Call the refactored compact_content_to_knowledge_base function
        knowledge_base_content = await compact_content_to_knowledge_base(
            aggregated_content=content,
            chunk_size=actual_chunk_size,
            api_key=self.api_key,
            subject=subject if subject is not None else "unknown_subject",
        )

        return knowledge_base_content
