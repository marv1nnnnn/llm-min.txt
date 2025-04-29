# LLM Minimal Documentation Generator

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT) <!-- Optional: Add relevant badges -->

## Overview

LLM Minimal Documentation Generator is a tool designed to automatically scrape and process technical documentation for Python libraries. It generates two key outputs for each library:

1.  `llm-full.txt`: The complete, raw text content crawled from the documentation website.
2.  `llm-min.txt`: A compact, structured summary of the documentation, optimized for consumption by Large Language Models (LLMs), generated using Google Gemini according to the PCS (Progressive Compaction Strategy) guide.

This tool facilitates the creation of focused context files, enabling LLMs to provide more accurate and relevant information about specific libraries.

## Features

*   **Automatic Documentation Discovery:** Finds official documentation URLs for specified Python packages.
*   **Web Crawling:** Efficiently scrapes documentation websites (powered by `crawl4ai`).
*   **LLM-Powered Compaction:** Uses Google Gemini to condense crawled documentation into a structured, minimal format (PCS).
*   **Flexible Input:** Accepts package lists from:
    *   `requirements.txt` files.
    *   Folders containing a `requirements.txt` file.
    *   Direct string input.
*   **Programmatic Usage:** Provides a Python client (`LLMMinClient`) for integration into other workflows.
*   **Configurable Crawling:** Control maximum pages and depth for the web crawler.
*   **Organized Output:** Saves results in a structured directory format (`output_dir/package_name/`).

## Installation

1.  **Clone the repository:**
    ```bash
    git clone <repository_url> # Replace with actual URL
    cd llm-min-generator       # Or your project directory name
    ```

2.  **Set up the environment and install dependencies using `uv`:**
    ```bash
    # Ensure you have uv installed (https://github.com/astral-sh/uv)
    python -m venv .venv
    source .venv/bin/activate # or .venv\Scripts\activate on Windows
    uv pip install -r requirements.txt # Or use the appropriate requirements file
    uv pip install -e . # Install the package in editable mode
    ```

3.  **Install Playwright Browsers:**
    The documentation crawler uses Playwright. After installing the package, you need to download the necessary browser binaries:
    ```bash
    playwright install
    ```
    *Note: Depending on your environment (e.g., containers), you might need to install system dependencies for Playwright. See the [Playwright documentation](https://playwright.dev/docs/intro#system-requirements) for details.*

5.  **Install and Set up Pre-commit Hooks:**
   Pre-commit hooks help maintain code quality by running checks before you commit.
   ```bash
   pip install pre-commit
   pre-commit install
   ```
   After installation, the hooks will run automatically on `git commit`. You can also run them manually on all files with `pre-commit run --all-files`.

6.  **Configure API Key:**
    *   Copy the `.env.example` file to `.env`:
      ```bash
      cp .env.example .env
      ```
    *   Edit the `.env` file and add your Google Gemini API key:
      ```dotenv
      GEMINI_API_KEY=YOUR_API_KEY_HERE
      ```
    *   Alternatively, you can provide the key directly via the `--gemini-api-key` command-line option or when initializing `LLMMinClient`.

## Usage (Command Line)

The tool is run via the `llm-min-generator` command (if installed correctly) or `python -m llm_min_generator.main`.

**Command Structure:**

```bash
llm-min-generator [OPTIONS]
```

**Input Options (Choose ONE):**

*   `--requirements-file PATH` or `-f PATH`:
    Path to a `requirements.txt` file.
    ```bash
    llm-min-generator -f sample_requirements.txt
    ```
*   `--input-folder PATH` or `-d PATH`:
    Path to a folder containing a `requirements.txt` file.
    ```bash
    llm-min-generator -d /path/to/your/project/
    ```
*   `--packages "PKG1\nPKG2"` or `-pkg "PKG1\nPKG2"`:
    A string containing package names, separated by newlines (`\n`).
    ```bash
    llm-min-generator --packages "requests\npydantic>=2.0"
    ```

*   `--doc-url URL` or `-u URL`:
    Directly specify the documentation URL for a single package, bypassing the automatic search. This is useful if the search fails or if you want to target a specific version's documentation. When using this option, only provide *one* package via `--packages` or ensure your `--requirements-file`/`--input-folder` contains only one package.
    ```bash
    llm-min-generator --packages "requests" --doc-url "https://requests.readthedocs.io/en/latest/"
    ```
**Common Options:**

*   `--output-dir PATH` or `-o PATH`:
    Directory to save the generated documentation. (Default: `my_docs`)
*   `--max-crawl-pages N` or `-p N`:
    Maximum number of pages to crawl per package. Set to `0` for unlimited. (Default: `200`)
*   `--max-crawl-depth N` or `-D N`:
    Maximum depth to crawl from the starting URL. (Default: `2`)
*   `--chunk-size N` or `-c N`:
    Chunk size (in characters) for LLM compaction. (Default: `1000000`)
*   `--gemini-api-key KEY` or `-k KEY`:
    Your Google Gemini API Key (overrides the `.env` file).

**Example:**

Generate documentation for packages in `sample_requirements.txt`, saving to `output_docs`, crawling up to 100 pages:

```bash
llm-min-generator -f sample_requirements.txt -o output_docs -p 100
```

## Programmatic Usage (Python)

Beyond the command-line interface, you can use `llm-min-generator` programmatically in your Python projects via the `LLMMinClient`.

### Initialization

First, import the client:

```python
from llm_min.client import LLMMinClient
```

To initialize the client, you need to provide your Google Gemini API key. You can do this either by setting the `GEMINI_API_KEY` environment variable or by passing the key directly to the constructor. The client also requires the `pcs-guide.md` file to be present in the project root directory (or provide a custom path).

```python
import os

# Option 1: Using environment variable (Recommended)
# Ensure 'GEMINI_API_KEY' is set in your environment
# export GEMINI_API_KEY='YOUR_API_KEY_HERE'
try:
    # Assumes pcs-guide.md is in the project root
    client = LLMMinClient()
except ValueError as e:
    print(f"Error initializing client (API Key?): {e}")
    # Handle missing API key
except FileNotFoundError as e:
    print(f"Error initializing client (PCS Guide?): {e}")
    # Handle missing pcs-guide.md

# Option 2: Passing API key directly
api_key = os.environ.get("GEMINI_API_KEY", "YOUR_FALLBACK_API_KEY_HERE") # Get from env or use placeholder
custom_guide_path = "/path/to/your/custom/pcs-guide.md" # Optional

try:
    client_direct_key = LLMMinClient(
        api_key=api_key
        # Optionally specify model, chunk size, or PCS guide path:
        # model="gemini-pro",
        # max_tokens_per_chunk=5000,
        # pcs_guide_path=custom_guide_path
    )
except ValueError as e:
    print(f"Error initializing client (API Key?): {e}")
except FileNotFoundError as e:
    print(f"Error initializing client (PCS Guide?): {e}")

```

### Compacting Content

Once initialized, use the `compact` method to process your text content:

```python
# Assuming 'client' is an initialized LLMMinClient instance from Option 1 above
long_text_content = """
# Your extensive documentation or text content goes here...
# For example, the raw content scraped from a website or a large text file.
# This content will be automatically chunked based on the client's configuration
# and then compacted using the LLM according to the PCS guide.
# ... (potentially thousands of lines) ...
# It will be automatically chunked and compacted.
"""

subject_of_content = "My Library Documentation" # Optional, but helpful context for the LLM

if 'client' in locals(): # Check if client was initialized successfully
    try:
        compacted_pcs_output = client.compact(
            content=long_text_content,
            subject=subject_of_content
        )
        print("Compacted Output (PCS Format):")
        print(compacted_pcs_output)

        # You can save this output to a file, e.g., llm-min.txt
        # output_filename = f"{subject_of_content.lower().replace(' ', '_')}-llm-min.txt"
        # with open(output_filename, "w", encoding="utf-8") as f:
        #     f.write(compacted_pcs_output)
        # print(f"Saved compacted output to {output_filename}")

    except Exception as e:
        print(f"An error occurred during compaction: {e}")
else:
    print("LLMMinClient was not initialized successfully.")

```

This allows you to integrate the documentation compaction process directly into your Python workflows.

## Output Structure

The tool generates the following structure in the specified output directory:

```
output_dir/
├── package_name_1/
│   ├── llm-full.txt  # Raw crawled content
│   └── llm-min.txt   # Compacted PCS content
├── package_name_2/
│   ├── llm-full.txt
│   └── llm-min.txt
└── ...
```

## Contributing

Contributions are welcome! Please refer to the `CONTRIBUTING.md` file (if available) for guidelines.

Key areas for contribution:
*   Improving documentation discovery logic.
*   Enhancing the compaction prompts/strategy (PCS guide).
*   Adding support for more LLM providers.
*   Improving error handling and reporting.
*   Writing tests.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details (if available, otherwise assume MIT).
