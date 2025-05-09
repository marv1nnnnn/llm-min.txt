# LLM-Min: Generate Compact Docs for LLMs

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Problem:** LLMs often rely on outdated training data, leading to "vibe coding" where developers guess at API usage rather than working with current, accurate information. This makes development with rapidly evolving libraries challenging and error-prone.

**Solution:** `llm-min` automatically crawls Python library documentation (or a specified URL) and uses Google Gemini to generate compact, structured summaries (`llm-min.txt`) optimized for providing up-to-date context to LLMs. It also saves the full crawled text (`llm-full.txt`) for reference and copies the guideline used for structuring the summary (`llm-min-guideline.md`).

Give your LLMs the fresh, focused context they need to avoid hallucinations and generate accurate code.

## Key Features

*   **Automated Crawling:** Crawls provided documentation URLs for any language. Can also automatically find and scrape official Python package documentation via package name.
*   **LLM-Powered Summarization:** Creates concise, structured summaries using Google Gemini, generating a `llm_min.txt` composed of Atomic Information Units (AIUs).
*   **Flexible Input:** Process packages from comma-separated names or URLs.
*   **Organized Output:** Saves results neatly per package (`output_dir/package_name/`).


## Inspiration
* min.js (Code can be really compressed)
* LLM create new language (No need to restrict on current language, reasoning models are really good at abstract stuff)
* context7 (Solve the problem but have limit)

## Why not llms.txt?
Personally I love the concept of llms.txt, and apparently this is also the major inspiration.
*   Standard documentation often contains numerous redirect links, which LLMs may struggle to follow or interpret correctly.
*   Raw documentation is typically not optimized for token efficiency, leading to verbose input that can be costly or exceed LLM context window limits.
*   It can be difficult to ensure that an LLM is referencing the absolute latest version of online documentation. Developer might not update it frequently.

## Understanding `llm-min.txt` and Atomic Information Units (AIUs)

The `llm-min.txt` file contains a `KNOWLEDGE_BASE` specifically structured for LLM consumption. This KNOWLEDGE_BASE is composed of "Atomic Information Units" (AIUs). Each AIU represents a distinct piece of information about the library, such as a function, a class, a feature, or a usage pattern.

AIUs are designed to be:
*   **Atomic:** Representing a single, focused concept.
*   **Structured:** Containing specific fields like type (`typ`), name (`name`), purpose (`purp`), inputs (`in`), outputs (`out`), usage examples (`use`), and relationships to other AIUs (`rel`).
*   **Compact:** Using abbreviations and minimal syntax to maximize information density.

The goal of this format is to provide an LLM with a rich, interconnected understanding of the library's capabilities and how to use them, enabling it to answer questions and generate accurate code. The full specification for interpreting the KNOWLEDGE_BASE and AIU structure can be found in the `llm-min-guideline.md` file (which is a copy of `assets/guideline.md` from the `llm-min` package). This guideline details the fields, abbreviations, and overall schema.

Snippets of the KNOWLEDGE_BASE format include:

```text


```

## Sample Output & Compression

A sample output for the `crawl4ai` library is available in the `sample/crawl4ai/` directory. This can give you a concrete idea of what `llm-min` produces:

*   `sample/crawl4ai/llm-full.txt`: Contains the raw, complete text crawled from the `crawl4ai` documentation (Size: 124,424 token).
*   `sample/crawl4ai/llm-min.txt`: Contains the structured `KNOWLEDGE_BASE` generated by the LLM (Size: 22,422 token).
*   `sample/crawl4ai/llm-min-guideline.md`: A copy of the guideline used by the LLM for structuring the `llm-min.txt` content.

**Compression Achieved:**

In this specific example, `llm-min` reduced the input documentation size from approximately 511 KB to 76 KB. This represents a **compression of about 85%**, meaning the `llm-min.txt` file is roughly 15% of the original crawled text size.

This significant reduction in size, coupled with the structured format of `llm-min.txt`, makes the information much more digestible and efficient for Large Language Models, providing focused context without overwhelming them with raw documentation.

You can explore these files to see the transformation from verbose documentation to a compact, LLM-ready format.

**Use Case:**
For example, this tool can be used to provide context to AI coding assistants like Cursor to improve their understanding of new or rapidly changing libraries.

## Supported Languages

`llm-min` is designed to be language-agnostic when you provide direct documentation URLs using the `--doc-urls` option. This allows you to generate summaries for documentation written in any programming language (e.g., JavaScript, Java, Rust, Go, etc.) or even for non-programming related textual content.

When using the `--packages` option, `llm-min` currently leverages a search mechanism optimized for finding official Python package documentation. Therefore, this specific input method is best suited for Python libraries.

For all other languages and content types, please use the `--doc-urls` option.

## Quick Start

**1. Installation:**

**Using pip (Recommended for users):**

```bash
pip install llm-min
```

**For Development/Contribution (Using uv):**

```bash
# Clone (if you haven't already)
# cd llm-min

# Install dependencies (using uv)
python -m venv .venv
source .venv/bin/activate # or .venv\Scripts\activate on Windows
uv sync # Installs dependencies from pyproject.toml
uv pip install -e .

# Install browser binaries for crawling
playwright install

# Optional: Install pre-commit hooks for development
# uv pip install pre-commit
# pre-commit install
```

**2. Configure API Key:**

*   **Recommended:** Copy `.env.example` to `.env` and add your `GEMINI_API_KEY`. The application will automatically load it.
*   **Alternatively:** You can provide the key directly using the `--gemini-api-key` CLI flag.

**3. Generate Docs (CLI Usage):**

`llm-min` requires at least one input source (packages or URLs) and offers options to customize its behavior.

**Input Sources (provide at least one; can be combined):**
*   `-pkg, --packages TEXT`: Comma-separated string of package names (e.g., "requests,typer").
*   `-u, --doc-urls TEXT`: Comma-separated string of direct documentation URLs (e.g., "https://docs.python.org/3/,https://typer.tiangolo.com/").

**Common Options:**
*   `-o, --output-dir DIRECTORY`: Directory to save outputs (default: `llm_min_docs`).
*   `-p, --max-crawl-pages INTEGER`: Max pages to crawl per package (default: 200, 0 for unlimited).
*   `-D, --max-crawl-depth INTEGER`: Max crawl depth from start URL (default: 3).
*   `-c, --chunk-size INTEGER`: Character chunk size for LLM compaction (default: 1,000,000).
*   `-k, --gemini-api-key TEXT`: Gemini API Key (or use `GEMINI_API_KEY` env var).
*   `--gemini-model TEXT`: Gemini model (default: `gemini-2.5-flash-preview-04-17`).
*   `-v, --verbose`: Enable verbose logging.

**Example:**

Process the `typer` package and the FastAPI documentation URL, limiting crawl to 50 pages for each, and save to `my_docs`:
```bash
llm-min -pkg "typer" -u "https://fastapi.tiangolo.com/" -o my_docs -p 50 --gemini-api-key YOUR_API_KEY
```

For a full list of options and their descriptions, run:
```bash
llm-min --help
```

## Model choice

While you can specify different Gemini models using the `--gemini-model` option, we strongly recommend using `gemini-2.5-flash-preview-04-17` (the default).

Here's why:
1.  **Strong Reasoning:** This model offers robust reasoning capabilities, which are crucial for accurately understanding and structuring documentation content into the KNOWLEDGE_BASE format.
2.  **Long Context Window:** With a 1 million token context window, `gemini-2.5-flash-preview-04-17` is well-suited for processing extensive documentation, which is a common scenario for this tool.

Using the default model (`gemini-2.5-flash-preview-04-17`) provides a good balance of performance, cost, and capability for the task of generating compact LLM-friendly documentation.

## Workflow Overview (src/llm_min)

The core logic of `llm-min` processes inputs as follows. All I/O-bound operations (like web requests and LLM calls) for each input item are handled asynchronously for efficiency.

```text
[ User Runs CLI: llm-min ... ]
           |
           v
+--------------------------+
| Parse CLI Args (main.py) |
+--------------------------+
           |
           v
    +--------------+
    | Input Type?  |
    +--------------+
    /              \
   /                \
  v                  v
--packages      --doc-urls
  |                  |
  |                  |
  v                  v
[For each pkg name:] [For each direct URL:]
[Find Docs URL     ] [Use URL as is       ]
[(search.py)       ]
  \                  /
   \                /
    +----------------+
    | Combine URLs   |
    +----------------+
           |
           v
+---------------------------------+
| For each found/provided URL:    |
| Crawl Documentation (crawler.py)|
+---------------------------------+
                 |
                 v
+---------------------------------+
| For each crawled content:       |
| Compact Content using LLM       |
| (compacter.py & llm/gemini.py)  |
| (Uses assets/guideline.md)      |
+---------------------------------+
                 |
                 v
+---------------------------------+
| Save Outputs (main.py):         |
| - llm-full.txt (raw content)    |
| - llm-min.txt (compacted KB)    |
| - llm-min-guideline.md          |
+---------------------------------+

(All operations from URL processing to saving outputs
 occur in an async loop for each item)
```

**Brief Explanation:**

1.  **CLI Input (`main.py`):** The tool starts by parsing command-line arguments.
2.  **URL Discovery/Reception (`main.py`, `search.py`):**
    *   If package names are given (`--packages`), their documentation URLs are found using `search.py` (which employs an LLM and web search).
    *   If direct URLs are given (`--doc-urls`), they are used directly.
3.  **Crawling (`crawler.py`):** Each documentation URL is crawled to fetch its textual content.
4.  **Compaction (`compacter.py`, `llm/gemini.py`):** The crawled text is processed by a Gemini LLM, guided by `assets/guideline.md`, to produce a structured `KNOWLEDGE_BASE`.
5.  **Output (`main.py`):** The raw content (`llm-full.txt`), compacted `KNOWLEDGE_BASE` (`llm-min.txt`), and the guideline (`llm-min-guideline.md`) are saved.

All steps from URL discovery/reception through to output generation are performed for each package/URL, with I/O operations handled asynchronously.


## FAQ

**Q: What if the documentation for a package can't be found automatically when using `--packages`?**

A: `llm-min` uses a search engine to find the official documentation URL. If it fails, or picks the wrong one, you can use the `--doc-urls` option to provide the exact URL(s) for the documentation you want to process.

**Q: How does `llm-min` handle very large documentation sets?**

A: `llm-min` crawls documentation up to `max-crawl-pages` and `max-crawl-depth`. The crawled content is then split into chunks defined by `chunk-size` before being processed by the LLM. You might need to adjust these parameters for very large sites. The `gemini-2.5-flash-preview-04-17` model (default) has a large context window (1M tokens) which helps in processing substantial content effectively.

**Q: What should I do if I encounter an error or get poor results?**

A: Try running with the `--verbose` flag to get more detailed logs, which might indicate the issue. If a specific URL fails, test it in your browser. For poor summarization, you might experiment with a different Gemini model via `--gemini-model`, though the default is generally recommended. If problems persist, please open an issue on GitHub with details and logs.

**Q: Do you vibe code?


## Contributing

Contributions are welcome! Feel free to open issues or submit pull requests focusing on improving discovery, compaction, LLM support, or tests.

## License

MIT License.
