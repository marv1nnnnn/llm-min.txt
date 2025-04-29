# LLM Minimal Documentation Generator

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT) <!-- Optional: Add relevant badges -->

## Overview

LLM Minimal Documentation Generator is a command-line tool designed to automatically scrape and process technical documentation for Python libraries. It generates two key outputs for each library:

1.  `llm-full.txt`: The complete, raw text content crawled from the documentation website.
2.  `llm-min.txt`: A compact, structured summary of the documentation, optimized for consumption by Large Language Models (LLMs), generated using Google Gemini.

This tool facilitates the creation of focused context files, enabling LLMs to provide more accurate and relevant information about specific libraries.

## Features

*   **Automatic Documentation Discovery:** Finds official documentation URLs for specified Python packages.
*   **Web Crawling:** Efficiently scrapes documentation websites (powered by `crawl4ai`).
*   **LLM-Powered Compaction:** Uses Google Gemini to condense crawled documentation into a structured, minimal format (SHDF).
*   **Flexible Input:** Accepts package lists from:
    *   `requirements.txt` files.
    *   Folders containing a `requirements.txt` file.
    *   Direct string input.
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

3.  **Configure API Key:**
    *   Copy the `.env.example` file to `.env`:
      ```bash
      cp .env.example .env
      ```
    *   Edit the `.env` file and add your Google Gemini API key:
      ```dotenv
      GEMINI_API_KEY=YOUR_API_KEY_HERE
      ```
    *   Alternatively, you can provide the key directly via the `--gemini-api-key` command-line option.

## Usage

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

```bash
llm-min-generator --requirements-file sample_requirements.txt --output-dir generated_docs --max-crawl-pages 50
```

This command will:
1.  Read packages from `sample_requirements.txt`.
2.  Crawl up to 50 pages for each package.
3.  Use the Gemini API key from the `.env` file (or prompt if not set and not provided via `-k`).
4.  Save the `llm-full.txt` and `llm-min.txt` files into subdirectories within `generated_docs`.

## Output Structure

The generated files will be placed in the specified output directory, organized by package name:

```
<output_directory>/
├── package_one/
│   ├── llm-full.txt
│   └── llm-min.txt
└── package_two/
    ├── llm-full.txt
    └── llm-min.txt
```

## Contributing

Contributions are welcome! Please follow standard Git workflow:
1.  Fork the repository.
2.  Create a new branch (`git checkout -b feature/your-feature`).
3.  Make your changes.
4.  Commit your changes (`git commit -am 'Add some feature'`).
5.  Push to the branch (`git push origin feature/your-feature`).
6.  Create a new Pull Request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details (assuming a LICENSE file exists or will be created).
