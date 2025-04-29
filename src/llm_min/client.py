import logging
import os
from string import Template

# Import existing constants/templates and helper functions
from .compacter import (
    FRAGMENT_GENERATION_PROMPT_TEMPLATE_STR,
    MERGE_PROMPT_TEMPLATE_STR,
    _find_project_root,
    _load_pcs_guide,  # Import the helper function
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
    PCS_GUIDE_FILENAME = "pcs-guide.md"
    API_KEY_ENV_VAR = "GEMINI_API_KEY"

    def __init__(
        self,
        api_key: str | None = None,
        model: str = DEFAULT_MODEL,
        max_tokens_per_chunk: int = DEFAULT_MAX_TOKENS_PER_CHUNK,  # Corrected from DEFAULT_MAX_TOKENS_PER_CHUNK
        pcs_guide_path: str | None = None,
    ):
        """
        Initializes the LLMMinClient.

        Args:
            api_key: The API key for the LLM service. If None, attempts to read
                     from the environment variable (e.g., GEMINI_API_KEY).
            model: The identifier for the LLM model to use.
            max_tokens_per_chunk: Maximum tokens allowed per chunk for processing.
            pcs_guide_path: Optional path to a custom PCS guide file. If None,
                            attempts to locate 'pcs-guide.md' in the project root.

        Raises:
            ValueError: If the API key is not provided and cannot be found in
                        the environment variables.
            FileNotFoundError: If the specified or default pcs_guide_path cannot be found.
        """
        self.api_key = api_key or os.environ.get(self.API_KEY_ENV_VAR)
        if not self.api_key:
            raise ValueError(f"API key must be provided or set via the '{self.API_KEY_ENV_VAR}' environment variable.")

        self.model = model
        self.max_tokens_per_chunk = max_tokens_per_chunk

        # Load PCS Guide
        guide_path_to_load = pcs_guide_path
        if not guide_path_to_load:
            # Adjust start path for _find_project_root if necessary,
            # but os.path.dirname(__file__) is usually correct from within the module
            project_root = _find_project_root(os.path.dirname(__file__))
            if project_root:
                guide_path_to_load = str(project_root / self.PCS_GUIDE_FILENAME)
            else:
                # Fallback: Check current dir or raise error?
                # Raising FileNotFoundError seems more explicit if the guide isn't found
                logger.warning(
                    f"Could not find project root. Attempting to load {self.PCS_GUIDE_FILENAME} from current directory."
                )
                guide_path_to_load = self.PCS_GUIDE_FILENAME  # Try current directory as fallback

        try:
            self.pcs_guide_content = _load_pcs_guide(guide_path_to_load)
            if "ERROR" in self.pcs_guide_content:  # Check for error indicators from _load_pcs_guide
                raise FileNotFoundError(f"Failed to load PCS guide from {guide_path_to_load}")
            self.pcs_guide_path = guide_path_to_load  # Store the successfully loaded path
        except FileNotFoundError:
            logger.error(f"PCS guide file not found at {guide_path_to_load}")
            raise FileNotFoundError(f"PCS guide file not found at {guide_path_to_load}")
        except Exception as e:
            logger.error(f"Error loading PCS guide from {guide_path_to_load}: {e}")
            raise RuntimeError(f"Error loading PCS guide from {guide_path_to_load}: {e}")

    async def compact(self, content: str, chunk_size: int | None = None, subject: str | None = None) -> str:
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
        actual_chunk_size = chunk_size if chunk_size is not None else self.max_tokens_per_chunk

        if not content:
            logger.warning("Attempted to compact empty content.")
            return ""

        logger.info(f"Starting compaction with model '{self.model}' and chunk size {actual_chunk_size}")

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
                fragments.append(fragment.strip())  # Assuming generate_text_response returns str
                logger.info(f"Fragment {i + 1} generated successfully.")
            except Exception as e:
                # Capture the actual exception from the await if needed
                logger.error(f"Error generating fragment for chunk {i + 1}: {e}", exc_info=True)
                fragments.append(f"ERROR: FRAGMENT GENERATION FAILED FOR CHUNK {i + 1}: {e}")  # Append error marker

        if not fragments:
            logger.error("Fragment generation failed for all chunks.")
            return "ERROR: ALL FRAGMENT GENERATION FAILED."

        # 3. Merge fragments if necessary (now async)
        if len(fragments) > 1:
            logger.info("Merging fragments...")
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
