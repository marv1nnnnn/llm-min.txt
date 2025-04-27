# Design Specification: LLM Context Generator from requirements.txt

**Version:** 1.0
**Date:** 2025-04-27
**Author:** Solution Architect (AI)
**Task ID:** task-design-001

## 1. Overview

This document outlines the design for a Python function (`generate_context_from_requirements`) that generates concise LLM context by scraping and summarizing documentation for Python libraries listed in a `requirements.txt` file.

The process involves:
1.  Parsing the `requirements.txt` file to extract library names and optional versions.
2.  Searching the web (using DuckDuckGo via MCP) for the official documentation URL of each library.
3.  Performing a deep crawl of the identified documentation URLs using Crawl4AI, focusing on relevant content.
4.  Compacting the scraped text content using an external LLM API call.
5.  Aggregating the compacted context into a single output file.

## 2. Project Structure

```
llm-context-generator/
├── .specs/
│   └── context_generator_design.md  # This document
├── src/
│   ├── context_generator.py         # Main function and core logic
│   └── utils/                       # Optional: Helper functions (parsing, API calls)
│       └── __init__.py
│       └── requirements_parser.py
│       └── web_search.py
│       └── llm_compactor.py
├── requirements.txt                 # Input: Python dependencies list
├── context_output.md                # Output: Generated context file (Markdown format)
├── project_state.json               # Project state tracking
├── pyproject.toml                   # Project metadata and dependencies
└── README.md                        # Project overview
```

## 3. Core Function: `generate_context_from_requirements`

**File:** `src/context_generator.py`

**Signature:**

```python
from typing import List, Dict, Optional
import asyncio

async def generate_context_from_requirements(
    requirements_path: str,
    output_path: str,
    max_search_results: int = 3,
    crawl_depth: int = 2,
    max_pages_per_library: int = 20,
    llm_api_key: Optional[str] = None,
    llm_model_name: str = "gemini-pro" # Or other suitable model
) -> None:
    """
    Generates LLM context by finding, crawling, and summarizing documentation
    for libraries in a requirements.txt file.

    Args:
        requirements_path: Path to the requirements.txt file.
        output_path: Path to save the generated Markdown context file.
        max_search_results: Max documentation URLs to check per library.
        crawl_depth: Max depth for Crawl4AI deep crawling (beyond root URL).
        max_pages_per_library: Max pages Crawl4AI should crawl per library doc site.
        llm_api_key: API key for the compaction LLM service.
        llm_model_name: Name of the LLM model to use for compaction.
    """
    # Implementation details below
    pass
```

**Workflow:**

1.  **Parse Requirements:**
    *   Use a helper function (e.g., `src.utils.requirements_parser.parse`) to read `requirements_path` and extract library names (e.g., `requests`, `numpy`). Handle version specifiers if present but primarily focus on the library name for searching.
2.  **Find Documentation URLs:**
    *   For each library name:
        *   Construct search queries (e.g., `f"{library_name} documentation"`, `f"{library_name} python docs"`).
        *   Use the `ddg-search` MCP tool (`search` function) to find potential documentation URLs. Limit to `max_search_results`.
        *   Prioritize official-looking URLs (e.g., `readthedocs.io`, `python.org`, library's own domain).
3.  **Crawl Documentation:**
    *   For each promising documentation URL found:
        *   Configure `Crawl4AI`:
            *   `scraping_strategy`: Use `LXMLWebScrapingStrategy` (default or explicit).
            *   `deep_crawl_strategy`: Use `BestFirstCrawlingStrategy`.
                *   `max_depth`: Use `crawl_depth` parameter.
                *   `include_external`: `False` (to stay within the doc site).
                *   `max_pages`: Use `max_pages_per_library`.
                *   `url_scorer`: Use `KeywordRelevanceScorer` with keywords like library name, "api", "usage", "guide", "examples", "reference", "tutorial". Assign appropriate weight.
                *   `filter_chain`: Use `FilterChain` with:
                    *   `URLPatternFilter`: Allow patterns like `*/docs/*`, `*/api/*`, `*/reference/*`, `*/guides/*`, `*/tutorials/*`. Block patterns like `*/blog/*`, `*/forums/*`, `*/download/*`.
                    *   `ContentTypeFilter`: Allow `text/html`.
            *   `stream`: `True` (process results as they arrive).
            *   `verbose`: `False` (or configurable).
        *   Initialize `AsyncWebCrawler`.
        *   Run the crawl: `await crawler.arun(doc_url, config=config)`.
        *   Collect text content from successful crawl results (`result.content`). Concatenate relevant text for the library. Limit total text size per library if necessary before compaction.
4.  **Compact Text:**
    *   For each library's collected text:
        *   Use a helper function (e.g., `src.utils.llm_compactor.compact_text`) that interacts with an LLM API (e.g., Google Gemini API).
        *   Provide the `llm_api_key` and `llm_model_name`.
        *   Use a prompt like: "Summarize the following documentation for the Python library '{library_name}'. Focus on key API usage, core concepts, and common examples. Extract the most important information for a developer needing a quick reference. Output should be concise Markdown."
        *   Store the compacted Markdown summary.
5.  **Generate Output File:**
    *   Combine the compacted Markdown summaries for all libraries into a single string.
    *   Structure the output with clear headings for each library (e.g., `## Library: requests`).
    *   Write the combined content to `output_path`.

## 4. Dependencies

*   `crawl4ai`: For web crawling.
*   `requests` or `httpx`: Potentially needed by Crawl4AI or for direct API calls.
*   `beautifulsoup4` / `lxml`: For HTML parsing (likely dependencies of Crawl4AI).
*   `google-generativeai` or `openai`: LLM client library for text compaction.
*   `uv`: For project/dependency management (as seen in workspace).

These should be listed in `pyproject.toml`.

## 5. Output Format (`context_output.md`)

A Markdown file containing compacted documentation summaries.

```markdown
# LLM Context: Project Dependencies

## Library: requests

[Compacted summary of requests documentation focusing on key usage, API, examples]

---

## Library: numpy

[Compacted summary of numpy documentation focusing on key usage, API, examples]

---

## Library: [Other Library]

[Compacted summary...]

---
```

## 6. Error Handling & Considerations

*   **Web Search Failures:** Handle cases where no suitable documentation URL is found. Log a warning and skip the library.
*   **Crawling Errors:** Handle network errors, timeouts, or empty results during crawling. Log appropriately.
*   **LLM API Errors:** Handle API key issues, rate limits, or errors from the compaction service. Include raw (or partially processed) text as a fallback if compaction fails.
*   **Rate Limiting:** Be mindful of potential rate limits for web searches, crawling, and LLM API calls. Implement delays if necessary.
*   **Configuration:** Make key parameters like depth, max pages, and LLM model configurable.
*   **Security:** Handle the `llm_api_key` securely (e.g., environment variable, not hardcoded).

## 7. Future Enhancements

*   Support for different requirements file formats (e.g., `pyproject.toml`).
*   More sophisticated URL scoring and filtering.
*   Caching of crawled/compacted results.
*   Allowing user-provided documentation URLs.
*   Alternative compaction strategies (e.g., local models, non-LLM summarization).