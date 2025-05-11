import asyncio
import logging
import os
import sys
from pathlib import Path

import typer  # Import typer
from dotenv import load_dotenv  # Added dotenv import

from .generator import LLMMinGenerator

# Load environment variables from .env file
load_dotenv()

# Configure logging
# logging.basicConfig(
#     level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
# ) # Will configure later based on verbose flag
# Reduce verbosity from libraries
logging.getLogger("duckduckgo_search").setLevel(logging.WARNING)
logging.getLogger("crawl4ai").setLevel(logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


app = typer.Typer(help="Generates LLM context by scraping and summarizing documentation for Python libraries.")


@app.command()
def main(
    package_string: str | None = typer.Option(
        None,
        "--packages",
        "-pkg",
        help="A comma-separated string of package names (e.g., 'requests,pydantic==2.1').",
    ),
    doc_urls: str | None = typer.Option(
        None,
        "--doc-urls",
        "-u",
        help="A comma-separated string of direct documentation URLs to crawl.",
    ),
    output_dir: str = typer.Option(
        "llm_min_docs",
        "--output-dir",
        "-o",
        help="Directory to save the generated documentation.",
    ),
    max_crawl_pages: int | None = typer.Option(
        200,
        "--max-crawl-pages",
        "-p",
        help="Maximum number of pages to crawl per package. Default: 200. Set to 0 for unlimited.",
        callback=lambda v: None if v == 0 else v,
    ),
    max_crawl_depth: int = typer.Option(
        3,
        "--max-crawl-depth",
        "-D",
        help="Maximum depth to crawl from the starting URL. Default: 2.",
    ),
    chunk_size: int = typer.Option(
        600_000,
        "--chunk-size",
        "-c",
        help="Chunk size (in characters) for LLM compaction. Default: 1,000,000.",
    ),
    gemini_api_key: str | None = typer.Option(
        lambda: os.environ.get("GEMINI_API_KEY"),
        "--gemini-api-key",
        "-k",
        help="Gemini API Key. Can also be set via the GEMINI_API_KEY environment variable.",
        show_default=False,
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose logging (DEBUG level).",
        is_flag=True,
    ),
    gemini_model: str = typer.Option(
        "gemini-2.5-flash-preview-04-17",
        "--gemini-model",
        help="The Gemini model to use for compaction and search.",
    ),
):
    """
    Generates LLM context by scraping and summarizing documentation for Python libraries.

    You must provide one input source: --requirements-file, --input-folder, --packages, or --doc-url.
    """
    # Configure logging level based on the verbose flag
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=log_level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    # Reduce verbosity from libraries (can be kept here or moved after basicConfig)
    logging.getLogger("duckduckgo_search").setLevel(logging.WARNING)
    logging.getLogger("crawl4ai").setLevel(logging.INFO)  # Keep crawl4ai at INFO unless verbose?
    logging.getLogger("httpx").setLevel(logging.WARNING)

    logger.info(f"Verbose logging {'enabled' if verbose else 'disabled'}.")  # Log if verbose is active
    logger.debug(f"Gemini API Key received in main: {gemini_api_key}")
    logger.debug(f"Gemini Model received in main: {gemini_model}")

    # Prepare LLM config for the generator
    llm_config = {
        "api_key": gemini_api_key,
        "model_name": gemini_model,
        "chunk_size": chunk_size, # Pass chunk_size as part of llm_config
        "max_crawl_pages": max_crawl_pages, # Pass crawl limits as part of llm_config
        "max_crawl_depth": max_crawl_depth,
    }

    generator = LLMMinGenerator(output_dir=output_dir, llm_config=llm_config)

    # Validate input options: At least one of packages or doc_urls must be provided
    if not package_string and not doc_urls:
        logger.error(
            "Error: Please provide at least one input source: --packages and/or --doc-urls."
        )
        raise typer.Exit(code=1)

    if package_string:
        logger.info(f"Processing packages from --packages: {package_string}")
        packages_to_process_names = [pkg.strip() for pkg in package_string.split(',') if pkg.strip()]
        for package_name in packages_to_process_names:
            try:
                generator.generate_from_package(package_name)
            except Exception as e:
                logger.error(f"Failed to generate documentation for package {package_name}: {e}")

    if doc_urls:
        logger.info(f"Processing URLs from --doc-urls: {doc_urls}")
        individual_doc_urls = [url.strip() for url in doc_urls.split(',') if url.strip()]
        for target_doc_url in individual_doc_urls:
            try:
                generator.generate_from_url(target_doc_url)
            except Exception as e:
                logger.error(f"Failed to generate documentation from URL {target_doc_url}: {e}")


if __name__ == "__main__":
    app()
