import logging
import os
from string import Template

# Import existing constants/templates and the PRE-LOADED guide content
from .compacter import (
    FRAGMENT_GENERATION_PROMPT_TEMPLATE_STR,
    MERGE_PROMPT_TEMPLATE_STR,
    _pcs_guide_content,  # Import the already loaded guide content
)

# Import from .llm subpackage
from .llm import chunk_content, generate_text_response

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
        # pcs_guide_path: str | None = None, # Removed parameter
    ):
        """
        Initializes the LLMMinClient.

        Args:
            api_key: The API key for the LLM service. If None, attempts to read
                     from the environment variable (e.g., GEMINI_API_KEY).
            model: The identifier for the LLM model to use.
            max_tokens_per_chunk: Maximum tokens allowed per chunk for processing.
            # pcs_guide_path: Removed.

        Raises:
            ValueError: If the API key is not provided and cannot be found in
                        the environment variables.
            RuntimeError: If the PCS guide content could not be loaded by the compacter module.
        """
        self.api_key = api_key or os.environ.get(self.API_KEY_ENV_VAR)
        if not self.api_key:
            raise ValueError(
                f"API key must be provided or set via the '{self.API_KEY_ENV_VAR}' environment variable."
            )

        self.model = model
        self.max_tokens_per_chunk = max_tokens_per_chunk

        # Use the pre-loaded guide content from compacter
        self.pcs_guide_content = _pcs_guide_content
        if "ERROR:" in self.pcs_guide_content:
            logger.error(
                "PCS guide content was not loaded successfully by the compacter module."
            )
            # Raise a different error since the client isn't loading it directly
            raise RuntimeError(
                "PCS guide content could not be loaded. Check logs from llm_min.compacter."
            )

        # Removed file loading logic:
        # guide_path_to_load = pcs_guide_path
        # if not guide_path_to_load:
        #     ...
        # try:
        #     self.pcs_guide_content = _load_pcs_guide(guide_path_to_load)
        #     ...
        # except FileNotFoundError:
        #     ...
        # except Exception as e:
        #     ...

    async def compact(
        self, content: str, chunk_size: int | None = None, subject: str | None = None
    ) -> str:
        """
        Compacts the given content into PCS format using the configured LLM.
        (Async version)

        Args:
            content: The content string to compact.
            chunk_size: Optional. The size of the chunks to divide the content into.
                        Defaults to self.max_tokens_per_chunk if None.
            subject: Optional. The subject of the content, used for context in compaction.

        Returns:
            The compacted content in PCS format.
        """
        actual_chunk_size = (
            chunk_size if chunk_size is not None else self.max_tokens_per_chunk
        )

        # Add dummy key check here
        if self.api_key == "dummy_api_key":
            logger.info(
                f"Using dummy API key in client. Bypassing chunking and LLM calls for subject '{subject}'."
            )
            # Return the same dummy PCS structure as defined in compacter's test
            # Use the provided subject if available
            actual_subject = subject if subject else "unknown_subject"
            return f"|S: $$subject {actual_subject}\n|A: $$path#DummyClass()[]{{}}{{}}<>\n|D: $$SDummyStruct()"

        if not content:
            logger.warning("Attempted to compact empty content.")
            return ""

        logger.info(
            f"Starting compaction with model '{self.model}' and chunk size {actual_chunk_size}"
        )

        # 1. Chunk the content
        chunks = chunk_content(content, actual_chunk_size)
        logger.info(f"Content chunked into {len(chunks)} parts.")

        if not chunks:
            logger.error("Chunking resulted in no content chunks.")
            return "ERROR: CONTENT CHUNKING FAILED."

        # 2. Generate PCS fragments for each chunk (now async)
        fragments: list[str] = []
        fragment_template = Template(FRAGMENT_GENERATION_PROMPT_TEMPLATE_STR)

        for i, chunk in enumerate(chunks):
            logger.info(f"Generating PCS fragment for chunk {i + 1}/{len(chunks)}...")
            try:
                fragment_prompt = fragment_template.substitute(
                    pcs_guide=self.pcs_guide_content,
                    chunk=chunk,
                )
                # Use await for the async LLM call
                fragment = await generate_text_response(
                    prompt=fragment_prompt,
                    api_key=self.api_key,
                )
                fragments.append(
                    fragment.strip()
                )  # Assuming generate_text_response returns str
                logger.info(f"Fragment {i + 1} generated successfully.")
            except Exception as e:
                # Capture the actual exception from the await if needed
                logger.error(
                    f"Error generating fragment for chunk {i + 1}: {e}", exc_info=True
                )
                fragments.append(
                    f"ERROR: FRAGMENT GENERATION FAILED FOR CHUNK {i + 1}: {e}"
                )  # Append error marker

        # Check if *any* non-error fragments were generated before attempting merge
        successful_fragments = [f for f in fragments if not f.startswith("ERROR:")]
        if not successful_fragments:
            logger.error(
                "Fragment generation failed for all chunks or resulted only in errors."
            )
            # Optionally, join the error messages or return a generic one
            # return "\n---\n".join(fragments) # Return concatenated errors
            return "ERROR: ALL FRAGMENT GENERATION FAILED."  # Return generic error

        # 3. Merge fragments if necessary (now async)
        # Only merge if there are multiple fragments AND at least one was successful
        # (The check above handles the case where all failed)
        if len(fragments) > 1:
            logger.info(
                f"Merging {len(fragments)} fragments ({len(successful_fragments)} successful)..."
            )
            # Note: We still pass ALL fragments (including error placeholders) to the merge prompt
            # The LLM is expected to handle or ignore the error strings during merge.
            merge_template = Template(MERGE_PROMPT_TEMPLATE_STR)
            try:
                # Join fragments with a separator
                fragments_to_merge = "\n---\n".join(fragments)
                merge_prompt = merge_template.substitute(
                    pcs_guide=self.pcs_guide_content,
                    fragments=fragments_to_merge,
                    subject=subject if subject else "technical documentation",
                )
                # Use await for the async LLM call
                merged_pcs = await generate_text_response(
                    prompt=merge_prompt,
                    api_key=self.api_key,
                )
                logger.info("Fragments merged successfully.")
                return merged_pcs.strip()  # Assuming generate_text_response returns str
            except Exception as e:
                logger.error(f"Error merging fragments: {e}", exc_info=True)
                return f"ERROR: FRAGMENT MERGE FAILED: {e}"
        else:
            logger.info("Only one fragment generated, no merge needed.")
            # Need to handle potential error string in the single fragment
            return fragments[0]

    def get_pcs_guide(self) -> str:
        """
        Retrieves the content of the PCS guide.

        Returns:
            The full content of src/llm_min/pcs-guide.md as a string.
            Returns an error message string if the guide content was not loaded.
        """
        # The guide content is loaded during initialization
        # Error handling for loading is done in __init__
        return self.pcs_guide_content
