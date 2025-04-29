# Technical Design: Object-Oriented Python Interface for llm-min

**Task ID:** refactor-organic-python-tech-design

**Version:** 1.0

**Date:** 2025-04-29

**Author:** Solution Architect AI

## 1. Overview

This document outlines the design for a new Python class, `LLMMinClient`, within the `llm_min` library. The goal is to provide a more intuitive, object-oriented interface for programmatic usage, particularly for the content compaction functionality, moving away from the current standalone function-based approach.

## 2. Goals

*   Provide a clear, easy-to-use class-based API for `llm-min` functionalities.
*   Encapsulate configuration (API keys, model selection, etc.) within the class instance.
*   Offer a straightforward method for content compaction.
*   Improve maintainability and extensibility for future features.

## 3. Proposed Class Structure: `LLMMinClient`

A new class named `LLMMinClient` will be introduced, likely within a new file `src/llm_min/client.py` or potentially integrated into `src/llm_min/main.py` or `src/llm_min/__init__.py` for easier import (`from llm_min import LLMMinClient`).

```python
# Potential location: src/llm_min/client.py
import logging
import os
import pathlib
from string import Template
from typing import Optional

# Assuming LLM utilities are accessible
from .llm.gemini import chunk_content, generate_text_response
# Import existing constants/templates if they remain separate
from .compacter import (
    FRAGMENT_GENERATION_PROMPT_TEMPLATE_STR,
    MERGE_PROMPT_TEMPLATE_STR,
    _find_project_root, # Or make it a private method
)

logger = logging.getLogger(__name__)

class LLMMinClient:
    """
    Client for interacting with llm-min functionalities programmatically.
    """

    DEFAULT_MODEL = "gemini-1.5-flash"
    DEFAULT_MAX_TOKENS_PER_CHUNK = 10000
    PCS_GUIDE_FILENAME = "pcs-guide.md"
    API_KEY_ENV_VAR = "GEMINI_API_KEY" # Or a more generic name if supporting multiple LLMs

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = DEFAULT_MODEL,
        max_tokens_per_chunk: int = DEFAULT_MAX_TOKENS_PER_CHUNK,
        pcs_guide_path: Optional[str] = None,
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
            raise ValueError(
                f"API key must be provided or set via the "
                f"'{self.API_KEY_ENV_VAR}' environment variable."
            )

        self.model = model
        self.max_tokens_per_chunk = max_tokens_per_chunk

        # Load PCS Guide
        guide_path_to_load = pcs_guide_path
        if not guide_path_to_load:
            project_root = _find_project_root(os.path.dirname(__file__)) # Adjust start path if needed
            if project_root:
                guide_path_to_load = str(project_root / self.PCS_GUIDE_FILENAME)
            else:
                 # Fallback: Check current dir or raise error?
                 # For now, assume it might be relative or raise
                 logger.warning(f"Could not find project root. Looking for {self.PCS_GUIDE_FILENAME} relatively.")
                 guide_path_to_load = self.PCS_GUIDE_FILENAME


        self._pcs_guide_content = self._load_pcs_guide(guide_path_to_load)

        # Pre-compile templates
        self._fragment_template = Template(FRAGMENT_GENERATION_PROMPT_TEMPLATE_STR)
        self._merge_template = Template(MERGE_PROMPT_TEMPLATE_STR)


    def _load_pcs_guide(self, file_path: str) -> str:
        """Loads and preprocesses the PCS guide content."""
        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read().strip()
                # Strip markdown code fences if present
                if content.startswith("```") and content.endswith("```"):
                    content = '\n'.join(content.splitlines()[1:-1]).strip()
                return content
        except FileNotFoundError:
            logger.error(f"PCS guide file not found at {file_path}")
            raise FileNotFoundError(f"PCS guide file not found at {file_path}")
        except Exception as e:
            logger.error(f"Error reading PCS guide file at {file_path}: {e}")
            raise IOError(f"Could not read PCS guide file at {file_path}: {e}") from e

    def compact(self, content: str) -> str:
        """
        Compacts the given content into PCS format using the configured LLM.

        Args:
            content: The string content to compact.

        Returns:
            The compacted content in PCS format.

        Raises:
            Exception: If the LLM API call fails.
        """
        if not content.strip():
            logger.warning("Input content is empty or whitespace only. Returning empty string.")
            return ""

        chunks = chunk_content(content, self.max_tokens_per_chunk)
        pcs_fragments = []

        logger.info(f"Starting compaction using model '{self.model}'...")

        for i, chunk in enumerate(chunks):
            logger.info(f"Generating PCS fragment for chunk {i + 1}/{len(chunks)}...")
            fragment_prompt = self._fragment_template.substitute(
                pcs_guide=self._pcs_guide_content, documentation_chunk=chunk
            )

            try:
                fragment = generate_text_response(
                    prompt=fragment_prompt,
                    api_key=self.api_key,
                    model_name=self.model,
                )
                if fragment:
                    pcs_fragments.append(fragment.strip())
                else:
                    logger.warning(f"Received empty fragment for chunk {i + 1}.")

            except Exception as e:
                logger.error(f"Error generating fragment for chunk {i + 1}: {e}")
                # Decide on error handling: raise immediately, collect errors, skip chunk?
                # For now, re-raise to signal failure.
                raise RuntimeError(f"Failed to generate fragment for chunk {i + 1}") from e


        if not pcs_fragments:
            logger.warning("No PCS fragments were generated. Returning empty string.")
            return ""

        logger.info("Merging generated PCS fragments...")
        combined_fragments = "\n---\n".join(pcs_fragments) # Use a clear separator

        merge_prompt = self._merge_template.substitute(
            pcs_guide=self._pcs_guide_content, pcs_fragments=combined_fragments
        )

        try:
            final_pcs = generate_text_response(
                prompt=merge_prompt,
                api_key=self.api_key,
                model_name=self.model,
            )
            logger.info("Compaction completed successfully.")
            return final_pcs.strip() if final_pcs else ""

        except Exception as e:
            logger.error(f"Error merging PCS fragments: {e}")
            # Decide on error handling
            raise RuntimeError("Failed to merge PCS fragments") from e

# Example Usage (Illustrative)
# if __name__ == "__main__":
#     logging.basicConfig(level=logging.INFO)
#     try:
#         # Assumes GEMINI_API_KEY is set in environment
#         client = LLMMinClient()
#         # Or provide key directly: client = LLMMinClient(api_key="your_key_here")
#         # Or specify model/guide: client = LLMMinClient(model="gemini-pro", pcs_guide_path="custom_guide.md")
#
#         sample_content = """
#         # My Library
#
#         ## Function: add
#         Adds two numbers together.
#         Args:
#             a (int): The first number.
#             b (int): The second number.
#         Returns:
#             int: The sum of a and b.
#         """
#         compacted_result = client.compact(sample_content)
#         print("Compacted Result:\n", compacted_result)
#
#     except (ValueError, FileNotFoundError, IOError, RuntimeError) as e:
#         print(f"An error occurred: {e}")

```

## 4. Configuration Management

*   **API Key:** The `api_key` is the primary configuration. It can be passed directly during instantiation or read from the `GEMINI_API_KEY` environment variable. If neither is available, `ValueError` is raised.
*   **Model & Max Tokens:** These have defaults (`DEFAULT_MODEL`, `DEFAULT_MAX_TOKENS_PER_CHUNK`) but can be overridden during instantiation.
*   **PCS Guide:** The path can be explicitly provided. If not, the client attempts to find `pcs-guide.md` relative to the project root (identified by `pyproject.toml`). If the root or file isn't found, it raises `FileNotFoundError` or `IOError`. The guide content is loaded during `__init__`.

## 5. Compaction Functionality

*   The `compact(content: str)` method provides the primary interface.
*   It encapsulates the logic previously in `compact_content_with_llm`:
    *   Chunking the input `content`.
    *   Iterating through chunks, generating a PCS fragment for each using the fragment prompt template, instance configuration (`api_key`, `model`), and the loaded PCS guide (`_pcs_guide_content`).
    *   Merging the generated fragments using the merge prompt template.
    *   Returning the final compacted PCS string.
*   Error handling within the `compact` method should catch exceptions during LLM calls and potentially raise custom exceptions or return specific error indicators. The example above re-raises `RuntimeError`.

## 6. Helper Functions/Constants

*   `_load_pcs_guide`: Becomes a private instance method.
*   `_find_project_root`: Can remain a module-level function imported from `compacter` or become a static/private method within the class if preferred. Keeping it separate might be slightly better for SRP if other parts of the library need it.
*   Prompt Templates (`FRAGMENT_GENERATION_PROMPT_TEMPLATE_STR`, `MERGE_PROMPT_TEMPLATE_STR`): Can be defined as class constants or remain in `compacter.py` and imported. Defining them within the class keeps things self-contained.
*   Constants (`DEFAULT_MODEL`, `DEFAULT_MAX_TOKENS_PER_CHUNK`, etc.): Defined as class attributes for clarity and ease of modification.

## 7. Dependencies

*   The class depends on `os`, `pathlib`, `logging`, `string.Template`.
*   It requires the LLM utility functions (`chunk_content`, `generate_text_response`) from `.llm.gemini`.
*   It needs access to the prompt templates and potentially `_find_project_root`.

## 8. Open Questions/Considerations

*   **Error Handling Strategy:** How should errors during LLM calls (fragment generation, merging) be handled? Raise immediately? Collect errors? Return partial results? (Current design: Raise immediately).
*   **Location of the Class:** `src/llm_min/client.py` vs. `src/llm_min/main.py` vs. `src/llm_min/__init__.py`? (`client.py` seems cleanest).
*   **Extensibility:** How will other functionalities (e.g., search, crawl) integrate? Add methods to `LLMMinClient`? Create separate client classes? (Focus is compaction for now, but keep in mind).
*   **PCS Guide Loading:** What's the best fallback if `pcs-guide.md` isn't found in the project root or specified path? Raise error? Use a hardcoded default? (Current design: Raises error).
*   **API Key Env Var Name:** Should `GEMINI_API_KEY` be generalized if other LLMs are supported in the future (e.g., `LLM_MIN_API_KEY`)?

## 9. Acceptance Criteria Checklist

*   [X] A clear class structure is defined (`LLMMinClient`).
*   [X] The design addresses how API keys and other configurations are managed (`__init__`, env vars, defaults).
*   [X] The design outlines how the compaction functionality will be accessed through the class (`compact` method).
*   [X] The design is documented in a way that can be easily understood by the implementation team (This document).