# Project Documentation: llm-min Documentation Generator

This project provides a tool to automatically generate minimal documentation context files (`llm-min.txt` and `llm-full.txt`) from package documentation URLs. These files are intended for use with Large Language Models (LLMs).

## Overview

The core functionality involves:
1. Reading package names from a specified requirements file.
2. Finding the official documentation URL for each package.
3. Crawling the documentation site (up to configurable limits).
4. Extracting the raw text content (`llm-full.txt`).
5. Generating a compacted summary using an LLM (`llm-min.txt`).

## Quick Start / Usage

To generate documentation:

```bash
uv run python -m src.llm_min_generator.main <path_to_requirements.txt> -o <output_directory> [--max-crawl-pages N] [--max-crawl-depth M]
```

**Example:**

```bash
uv run python -m src.llm_min_generator.main sample_requirements.txt --max-crawl-pages 100 --max-crawl-depth 3 -o my_docs
```

Refer to the main `README.md` for more details.

## Project Structure

The project is organized into the following key modules within the `src/` directory:

*   **`src/llm/gemini.py`**: Handles all interactions with the Google Gemini LLM. This includes:
    *   Generating text responses.
    *   Streaming responses.
    *   Chunking large input content to fit within model limits.
    *   Merging chunked JSON outputs (if applicable).
*   **`src/llm_min_generator/`**: Contains the core logic for the documentation generation pipeline.
    *   **`main.py`**: The main CLI entry point (using Typer). Orchestrates the workflow by calling other modules.
    *   **`parser.py`**: Responsible for finding and parsing dependency files (like `requirements.txt`, `pyproject.toml`, `package.json`) to extract package names. Can scan directories for these files.
    *   **`search.py`**: Finds potential documentation URLs for a given package name using DuckDuckGo search and then uses the LLM (`gemini.py`) to select the most likely official URL.
    *   **`crawler.py`**: Uses the `crawl4ai` library to crawl the identified documentation URL and extract the raw text content.
    *   **`compacter.py`**: Takes the raw crawled content and uses the LLM (`gemini.py`) with specific prompts (potentially guided by `shdf-guide.md`) to generate the compacted `llm-min.txt` summary.

## Contributing

*(Contribution guidelines to be added here)*

## License

*(License information to be added here)*