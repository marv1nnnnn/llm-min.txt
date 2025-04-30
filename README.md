# LLM-Min: Generate Compact Docs for LLMs

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Problem:** Large Language Models (LLMs) work best with focused, concise context. Feeding them entire documentation websites is inefficient and often counterproductive.

**Solution:** `llm-min-generator` automatically crawls Python library documentation and uses Google Gemini to generate compact, structured summaries (`llm-min.txt`) optimized for LLM consumption. It also saves the full crawled text (`llm-full.txt`) for reference.

Stop wasting tokens! Give your LLMs the focused context they need.

## Key Features

*   **Automated Crawling:** Finds and scrapes official Python package docs.
*   **LLM-Powered Summarization:** Creates concise, structured summaries using the PCS (Progressive Compaction Strategy) via Google Gemini.
*   **Flexible Input:** Process packages from `requirements.txt`, folders, or direct input.
*   **Easy Integration:** Use via CLI or the Python `LLMMinClient`.
*   **Organized Output:** Saves results neatly per package (`output_dir/package_name/`).

## Quick Start

**1. Installation:**

**Using pip (Recommended for users):**

```bash
pip install llm-min
```

**For Development/Contribution (Using uv):**

```bash
# Clone (if you haven't already)
# git clone <repository_url>
# cd llm-min-generator

# Install dependencies (using uv)
python -m venv .venv
source .venv/bin/activate # or .venv\Scripts\activate on Windows
uv pip install -r requirements.txt
uv pip install -e .

# Install browser binaries for crawling
playwright install

# Optional: Install pre-commit hooks for development
# uv pip install pre-commit
# pre-commit install
```

**2. Configure API Key:**

*   **Recommended:** Copy `.env.example` to `.env` and add your `GEMINI_API_KEY`. The application will automatically load it.
*   **Alternatively:** You can provide the key directly using the `--gemini-api-key` CLI flag or pass it as the `api_key` parameter when initializing `LLMMinClient` in Python.

**3. Generate Docs (CLI Example):**

Process packages from a requirements file and save to `my_llm_docs`:

```bash
llm-min-generator -f path/to/your/requirements.txt -o my_llm_docs
```

*   Use `-pkg "requests\ntyper"` for direct package input.
*   Use `-d /path/to/project` to find `requirements.txt` in a folder.
*   See `llm-min-generator --help` for more options (crawl depth, chunk size, etc.).

**4. Generate Docs (Python Client Example):**

```python
from llm_min.client import LLMMinClient
import os

# Assumes GEMINI_API_KEY is in .env or environment
try:
    client = LLMMinClient()

    # Example: Compact existing text content
    long_text = "Your very long documentation text here..."
    subject = "My Custom Library"
    compacted_text = client.compact(content=long_text, subject=subject)

    print(f"--- Compacted {subject} ---")
    print(compacted_text)

    # You can also use client.process_package("package_name")
    # or client.process_requirements("path/to/requirements.txt")
    # See client documentation for details.

except (ValueError, FileNotFoundError) as e:
    print(f"Error initializing client (API Key or PCS Guide missing?): {e}")
except Exception as e:
    print(f"An error occurred: {e}")

```

## Output

For each package, you'll get:

```
output_dir/
└── package_name/
    ├── llm-full.txt  # Raw crawled content
    └── llm-min.txt   # Compacted PCS content for LLMs

```

## What is PCS (Packed Code Syntax)?

PCS is a highly condensed, machine-centric format designed for representing code structure and essential metadata with maximum information density. It uses single-character codes, minimal delimiters, and positional context to create a compact, single-string representation optimized for LLM context windows.

Think of it as a "minified" version of code documentation, focusing purely on the structural elements and relationships an LLM needs to understand an API or library, discarding natural language explanations. The full specification can be found in `docs/pcs-guide.md`.

## Contributing

Contributions are welcome! See `CONTRIBUTING.md` (if available) or focus on improving discovery, compaction, LLM support, or tests.

## License

MIT License.
