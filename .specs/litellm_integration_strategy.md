# LiteLLM Integration Strategy

**Task ID:** `task-design-litellm-integration`

**Date:** 2025-04-28

**Author:** Solution Architect AI

## 1. Overview

This document outlines the strategy for integrating LiteLLM into the `llm-min-generator` project. The goal is to replace direct API calls to specific LLM providers (currently Google Gemini via `src/llm/gemini.py`) with a unified abstraction layer provided by LiteLLM. This will allow for greater flexibility in choosing LLM models and providers, simplify configuration, and make the codebase more maintainable.

## 2. Current Implementation Analysis

*   **`src/llm/gemini.py`:** Contains functions (`compact_content_with_llm`, `generate_text_response`) that directly interact with the Google Gemini API using the `google-genai` library and hardcoded model names (e.g., `gemini-2.5-flash-preview-04-17`). It relies on the `GEMINI_API_KEY` environment variable.
*   **`src/llm_min_generator/compacter.py`:** Imports and uses `compact_content_with_llm` (aliased as `call_llm_compact`) for documentation compaction.
*   **`src/llm_min_generator/search.py`:** Imports and uses `generate_text_response` for selecting the best documentation URL from search results.

## 3. Proposed Solution: LiteLLM Wrapper

We will introduce a new module, `src/llm/wrapper.py`, which will encapsulate all interactions with LLMs via LiteLLM.

### 3.1. Wrapper Module Interface (`src/llm/wrapper.py`)

A primary function will handle LLM calls:

```python
# src/llm/wrapper.py
import logging
import os
import litellm
from typing import Optional, List, Dict, Any, Union, Iterator

logger = logging.getLogger(__name__)

# Configure LiteLLM logging level (optional)
# litellm.set_verbose = True

def generate_completion(
    model: str,
    messages: List[Dict[str, str]],
    temperature: float = 0.2, # Default to lower temp for more deterministic output
    max_tokens: Optional[int] = None,
    stream: bool = False,
    **kwargs: Any # Allow passing other litellm params like api_base, api_key etc. if needed
) -> Union[Optional[str], Iterator[str]]:
    """
    Generates a completion using the specified model via LiteLLM.

    Handles API key retrieval from environment variables automatically via LiteLLM.

    Args:
        model: The LiteLLM model string (e.g., "gemini/gemini-pro", "openai/gpt-4o", "anthropic/claude-3-haiku-20240307").
               Model names should be configurable per use case.
        messages: A list of message dictionaries adhering to the OpenAI format
                  (e.g., [{"role": "user", "content": "..."}]).
        temperature: Sampling temperature. Lower values are better for factual tasks.
        max_tokens: Maximum tokens to generate. LiteLLM defaults might suffice.
        stream: Whether to stream the response. If True, returns an iterator.
        **kwargs: Additional parameters to pass directly to litellm.completion
                  (e.g., api_base, specific provider keys if not standard env vars).

    Returns:
        - If stream=False: The generated text content as a string, or None if an error occurs.
        - If stream=True: An iterator yielding response chunks (strings), or None if an error occurs.
                          Note: Error handling for streams needs careful implementation.
    """
    try:
        logger.debug(f"Calling LiteLLM model '{model}' with temperature={temperature}, stream={stream}")
        response = litellm.completion(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=stream,
            **kwargs
        )

        if stream:
            # Return the stream iterator directly
            # Caller needs to handle potential exceptions during iteration
            logger.info(f"LiteLLM stream initiated for model '{model}'.")
            return response # This is an iterator
        else:
            # Extract content from the non-streamed response
            # Accessing response content might vary slightly based on LiteLLM version, check docs
            # Assuming response object has 'choices' and 'message'/'content' attributes
            if response and response.choices and response.choices[0].message:
                 content = response.choices[0].message.content
                 logger.debug(f"LiteLLM response received (non-streamed): {content[:100]}...") # Log snippet
                 return content.strip() if content else None
            else:
                 logger.warning(f"LiteLLM returned an unexpected response structure for model '{model}': {response}")
                 return None

    except Exception as e:
        # Log detailed error information
        # Consider specific exception types LiteLLM might raise
        logger.error(f"LiteLLM completion failed for model '{model}': {e}", exc_info=True)
        # Potentially check for specific API errors (e.g., AuthenticationError, RateLimitError)
        # if 'AuthenticationError' in str(e):
        #     logger.error("Authentication error: Check API key environment variables.")
        # elif 'RateLimitError' in str(e):
        #     logger.error("Rate limit exceeded.")
        return None

# Example Usage (for illustration):
# if __name__ == '__main__':
#     # Ensure relevant API keys (e.g., GEMINI_API_KEY) are set as env vars
#     test_messages = [{"role": "user", "content": "Explain the purpose of LiteLLM in one sentence."}]
#     # Example: Using Gemini Pro (ensure GEMINI_API_KEY is set)
#     result = generate_completion(model="gemini/gemini-pro", messages=test_messages)
#     print(f"Gemini Response: {result}")
#
#     # Example: Streaming with a different model (ensure relevant key is set)
#     # stream_result = generate_completion(model="openai/gpt-3.5-turbo", messages=test_messages, stream=True)
#     # if stream_result:
#     #     print("Streaming Response:")
#     #     for chunk in stream_result:
#     #         # Process chunk (e.g., print content)
#     #         content_chunk = chunk.choices[0].delta.content
#     #         if content_chunk:
#     #             print(content_chunk, end='', flush=True)
#     #     print("\nStream finished.")

```

### 3.2. Configuration

*   **API Keys:** LiteLLM automatically reads API keys from standard environment variables (e.g., `GEMINI_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`). These need to be set in the environment (e.g., via `.env` file).
*   **Model Selection:** The specific model used for each task (compaction, search URL selection) should be configurable. We will use environment variables for this:
    *   `COMPACTER_LLM_MODEL`: Specifies the LiteLLM model string for the compaction task (e.g., `gemini/gemini-1.5-flash-preview-05-14`, `anthropic/claude-3-haiku-20240307`). Default: `gemini/gemini-1.5-flash-preview-05-14` (or similar latest flash).
    *   `SEARCH_LLM_MODEL`: Specifies the LiteLLM model string for the search URL selection task (e.g., `gemini/gemini-1.5-flash-preview-05-14`, `openai/gpt-3.5-turbo`). Default: `gemini/gemini-1.5-flash-preview-05-14`.
*   **`.env.example`:** Update `.env.example` to include these new environment variables.

```dotenv
# .env.example (Additions/Updates)

# --- LLM Configuration ---
# Set API keys for the providers you intend to use via LiteLLM
GEMINI_API_KEY=YOUR_GEMINI_API_KEY
# OPENAI_API_KEY=YOUR_OPENAI_API_KEY
# ANTHROPIC_API_KEY=YOUR_ANTHROPIC_API_KEY
# COHERE_API_KEY=YOUR_COHERE_API_KEY
# etc.

# Select LiteLLM models for different tasks
# See LiteLLM documentation for available model strings: https://docs.litellm.ai/docs/providers
COMPACTER_LLM_MODEL=gemini/gemini-1.5-flash-preview-05-14
SEARCH_LLM_MODEL=gemini/gemini-1.5-flash-preview-05-14
```

## 4. Refactoring Plan

### 4.1. `src/llm_min_generator/compacter.py`

1.  **Remove Dependency:** Delete the import `from src.llm.gemini import compact_content_with_llm as call_llm_compact`.
2.  **Add Dependency:** Add `import os` and `from src.llm.wrapper import generate_completion`.
3.  **Modify `compact_content_with_llm`:**
    *   Retrieve the model name: `model_name = os.getenv("COMPACTER_LLM_MODEL", "gemini/gemini-1.5-flash-preview-05-14")`.
    *   Construct the `messages` list: `messages = [{"role": "user", "content": content_with_prompt}]`.
    *   Replace the `call_llm_compact(...)` line with a call to the new wrapper: `compacted_output = generate_completion(model=model_name, messages=messages, temperature=0.1) # Use low temp`.
    *   Adjust the logic to handle the `compacted_output` string (or None).

### 4.2. `src/llm_min_generator/search.py`

1.  **Remove Dependency:** Delete the import `from src.llm.gemini import generate_text_response`.
2.  **Add Dependency:** Add `import os` and `from src.llm.wrapper import generate_completion`.
3.  **Modify `select_best_url_with_llm`:**
    *   Retrieve the model name: `model_name = os.getenv("SEARCH_LLM_MODEL", "gemini/gemini-1.5-flash-preview-05-14")`.
    *   Construct the `messages` list: `messages = [{"role": "user", "content": prompt}]`.
    *   Replace the `generate_text_response(prompt)` line with a call to the new wrapper: `llm_response = generate_completion(model=model_name, messages=messages, temperature=0.1) # Use low temp`.
    *   Adjust the logic to handle the `llm_response` string (or None).

### 4.3. `src/llm/gemini.py`

*   This file can be marked as deprecated or removed entirely once the refactoring of `compacter.py` and `search.py` is complete and verified.

## 5. Dependencies

*   Add `litellm` to the project dependencies (e.g., in `pyproject.toml` or `requirements.txt`).

```toml
# pyproject.toml (Example addition under [tool.poetry.dependencies] or similar)
litellm = "^1.35.20" # Check for latest stable version
```

*   Run `uv pip install litellm` or `poetry add litellm` to install.

## 6. Acceptance Criteria Check

*   [x] Create a design document or specification (.md file in .specs/) - This document.
*   [x] Specification outlines the proposed wrapper module's interface - Section 3.1.
*   [x] Specification details necessary configuration changes - Section 3.2.
*   [x] Specification outlines the steps needed to refactor existing code - Section 4.

## 7. Proposed Implementation Sub-tasks

*   `task-implement-litellm-wrapper`: Implement `src/llm/wrapper.py`. (Type: `feature`)
*   `task-refactor-search-litellm`: Refactor `src/llm_min_generator/search.py`. (Type: `refactor`)
*   `task-refactor-compacter-litellm`: Refactor `src/llm_min_generator/compacter.py`. (Type: `refactor`)
*   `task-update-config-litellm`: Update `.env.example`, `pyproject.toml`/`requirements.txt`, and potentially `README.md`. (Type: `chore`)