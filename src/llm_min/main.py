import logging
import os
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
    input_folder: Path | None = typer.Option(
        None,
        "--input-folder",
        "-i",
        exists=True,
        file_okay=False,
        dir_okay=True,
        writable=True,
        readable=True,
        resolve_path=True,
        help="A folder directory path to scan recursively for *.md, *.txt, and *.rst files. Web crawling will be skipped if this is provided.",
    ),
    package_name_input: str | None = typer.Option(
        None,
        "--package",
        "-pkg",
        help="A single package name (e.g., 'requests' or 'pydantic==2.1').",
    ),
    doc_url: str | None = typer.Option(
        None,
        "--doc-url",
        "-u",
        help="A single direct documentation URL to crawl.",
    ),
    library_version: str | None = typer.Option(
        None,
        "--library-version",
        "-V",
        help="The version of the library when using --doc-url or --input-folder. Optional.",
    ),
    output_folder_name_override: str | None = typer.Option(
        None,
        "--output-name",
        "-n",
        help="Override the default output folder name with this name.",
    ),
    output_dir: str = typer.Option(
        "llm_min_docs",
        "--output-dir",
        "-o",
        help="Directory to save the generated documentation.",
    ),
    max_crawl_pages: int | None = typer.Option(
        200,
        "--max-crawl_pages",
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
        0,
        "--chunk-size",
        "-c",
        help="Chunk size (in characters) for LLM compaction. Default: 0 (auto-calculate based on content size). Set explicitly to override.",
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
        "gemini-2.5-flash-lite-preview-06-17",
        "--gemini-model",
        "-m",
        help="The Gemini model to use for compaction and search.",
    ),
    force_reprocess: bool = typer.Option(
        False,
        "--force-reprocess",
        help="Force reprocessing even if llm-full.txt exists and ignore intermediate files",
        is_flag=True,
    ),
    save_fragments: bool = typer.Option(
        True,
        "--save-fragments/--no-save-fragments",
        help="Save intermediate fragments for debugging and retry capability. Default: True.",
    ),
):
    """
    Generates LLM context by scraping and summarizing documentation for Python libraries.

    You must provide one input source: --requirements-file, --input-folder, --package, or --doc-url.
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
        "chunk_size": chunk_size,  # Pass chunk_size as part of llm_config
        "max_crawl_pages": max_crawl_pages,  # Pass crawl limits as part of llm_config
        "max_crawl_depth": max_crawl_depth,
        "save_fragments": save_fragments,  # Pass fragment saving option
        "force_reprocess": force_reprocess,  # Pass force reprocess option
    }

    # Note: output directory is handled by the generator

    # Initialize the generator with updated configuration
    generator = LLMMinGenerator(
        output_dir=output_dir,
        output_folder_name_override=output_folder_name_override,
        llm_config=llm_config,
        force_reprocess=force_reprocess,
    )

    # Validate input options: Exactly one of input_folder, package_name, or doc_url must be provided
    # Validate input options: Exactly one of input_folder, package_name_input, or doc_url must be provided
    input_sources_provided = sum([bool(input_folder), bool(package_name_input), bool(doc_url)])
    if input_sources_provided != 1:
        logger.error("Error: Please provide exactly one input source: --input-folder, --package, or --doc-url.")
        raise typer.Exit(code=1)

    if input_folder:
        logger.info(f"Processing files from input folder: {input_folder}")
        # Collect content from specified file types recursively
        input_content = ""
        allowed_extensions = [".md", ".txt", ".rst"]
        files_found = 0
        for ext in allowed_extensions:
            for file_path in input_folder.rglob(f"*{ext}"):
                try:
                    with open(file_path, encoding="utf-8") as f:
                        file_content = f.read()
                        if file_content.strip():  # Only add non-empty files
                            input_content += f"# File: {file_path.name}\n\n{file_content}\n\n---\n\n"
                            files_found += 1
                    logger.debug(f"Read content from {file_path}")
                except Exception as e:
                    logger.warning(f"Could not read file {file_path}: {e}")

        if not input_content or files_found == 0:
            logger.warning(f"No valid content found in files matching {allowed_extensions} in {input_folder}")
            raise typer.Exit(code=1)

        logger.info(f"Successfully collected content from {files_found} files")

        # Use the collected content for generation
        try:
            # Generate a meaningful source name from the input folder
            # Use the folder name or a default if it's just a path
            source_name = output_folder_name_override or input_folder.name or "local_docs"

            logger.info(f"Starting processing with source name: '{source_name}'")
            generator.generate_from_text(input_content, source_name=source_name, library_version=library_version)
            logger.info(f"Successfully generated documentation from input folder {input_folder}")
        except Exception as e:
            logger.error(f"Failed to generate documentation from input folder {input_folder}: {e}")
            raise typer.Exit(code=1)

    elif package_name_input:  # Only process package if no input_folder is provided and package_name is provided
        logger.info(f"Processing package: {package_name_input}")
        try:
            generator.generate_from_package(package_name_input, library_version)
        except Exception as e:
            logger.error(f"Failed to generate documentation for package {package_name_input}: {e}")

    elif doc_url:  # Only process doc_url if no input_folder or package_name is provided and doc_url is provided
        logger.info(f"Processing URL: {doc_url}")
        try:
            generator.generate_from_url(doc_url, library_version)
        except Exception as e:
            logger.error(f"Failed to generate documentation from URL {doc_url}: {e}")


if __name__ == "__main__":
    app()
