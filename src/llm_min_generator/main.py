import os
import sys

import logging
import sys
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Set, Optional

import typer # Import typer
from dotenv import load_dotenv # Added dotenv import

from .parser import parse_requirements
from .search import find_documentation_url
from .crawler import crawl_documentation
from .compacter import compact_content_with_llm

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
# Reduce verbosity from libraries
logging.getLogger("duckduckgo_search").setLevel(logging.WARNING)
logging.getLogger("crawl4ai").setLevel(logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

def write_full_text_file(output_base_dir: str | Path, package_name: str, content: str):
    """Writes the full crawled text content to a file within the package-specific directory."""
    try:
        # Construct the package-specific directory path
        package_dir = Path(output_base_dir) / package_name
        package_dir.mkdir(parents=True, exist_ok=True)

        # Define the output file path
        file_path = package_dir / "llm-full.txt"

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        logger.info(f"Successfully wrote full text content for {package_name} to {file_path}")
    except Exception as e:
        logger.error(f"Failed to write full text file for {package_name}: {e}", exc_info=True)
        # Do not re-raise, allow the process to continue for other packages


def write_min_text_file(output_base_dir: str | Path, package_name: str, content: str):
    """Writes the compacted text content to a file within the package-specific directory."""
    try:
        # Construct the package-specific directory path
        package_dir = Path(output_base_dir) / package_name
        package_dir.mkdir(parents=True, exist_ok=True)

        # Define the output file path
        file_path = package_dir / "llm-min.txt"

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        logger.info(f"Successfully wrote minimal text content for {package_name} to {file_path}")
    except Exception as e:
        logger.error(f"Failed to write minimal text file for {package_name}: {e}", exc_info=True)
        # Do not re-raise, allow the process to continue for other packages


async def process_package(
    package_name: str,
    output_dir: Path,
    max_crawl_pages: Optional[int], # Use Optional
    max_crawl_depth: int,
    chunk_size: int,
    gemini_api_key: Optional[str] # Add gemini_api_key parameter
):
    """Processes a single package: finds docs, crawls, compacts, and writes files."""
    logger.info(f"--- Processing package: {package_name} ---")
    try:
        # TODO: Consider if find_documentation_url needs the API key for potential future LLM use
        doc_url = find_documentation_url(package_name)
        if not doc_url:
            logger.warning(f"Could not find documentation URL for {package_name}. Skipping.")
            return False

        logger.info(f"Found documentation URL for {package_name}: {doc_url}")

        crawled_content = await crawl_documentation(
            doc_url,
            max_pages=max_crawl_pages,
            max_depth=max_crawl_depth
        )

        if not crawled_content:
            logger.warning(f"No content crawled for {package_name}. Skipping.")
            return False

        logger.info(f"Successfully crawled content for {package_name}. Total size: {len(crawled_content)} characters.")

        # Write the full crawled content to a file
        write_full_text_file(output_dir, package_name, crawled_content)

        # Compact the content
        logger.info(f"Compacting content for {package_name}...")
        # Pass gemini_api_key to the compaction function
        # Also pass package_name as the subject
        compacted_content = await compact_content_with_llm(
            aggregated_content=crawled_content,
            chunk_size=chunk_size,
            api_key=gemini_api_key,
            subject=package_name # Pass package_name as subject
        )

        if not compacted_content:
            logger.warning(f"Compaction resulted in empty content for {package_name}. Skipping writing min file.")
            return False

        logger.info(f"Successfully compacted content for {package_name}. Compacted size: {len(compacted_content)} characters.")

        # Write the compacted content to a file
        write_min_text_file(output_dir, package_name, compacted_content)

        logger.info(f"Finished processing package: {package_name}")
        return True
    except Exception as e:
        logger.error(f"An error occurred while processing package {package_name}: {e}", exc_info=True)
        return False


async def process_requirements(
    packages: Set[str], # Accept parsed packages directly
    output_dir: Path,
    max_crawl_pages: Optional[int], # Use Optional
    max_crawl_depth: int,
    chunk_size: int,
    gemini_api_key: Optional[str] # Add gemini_api_key parameter
):
    """Processes a list of packages."""
    if not packages:
        logger.warning("No packages provided for processing. Exiting.")
        sys.exit(0)

    logger.info(f"Processing {len(packages)} packages: {', '.join(packages)}")

    tasks = [
        process_package(
            package_name,
            output_dir,
            max_crawl_pages,
            max_crawl_depth,
            chunk_size,
            gemini_api_key # Pass key down
        ) for package_name in packages
    ]
    await asyncio.gather(*tasks)


app = typer.Typer(help="Generates LLM context by scraping and summarizing documentation for Python libraries.")

@app.command()
def main(
    requirements_file: Optional[Path] = typer.Option( # Changed to Optional Option
        None, "--requirements-file", "-f", help="Path to a requirements.txt file.", exists=True, file_okay=True, dir_okay=False, readable=True
    ),
    input_folder: Optional[Path] = typer.Option( # Added input_folder option
        None, "--input-folder", "-d", help="Path to a folder containing a requirements.txt file.", exists=True, file_okay=False, dir_okay=True, readable=True
    ),
    package_string: Optional[str] = typer.Option( # Added package_string option
        None, "--packages", "-pkg", help="A string containing package names, one per line (e.g., 'requests\\npydantic==2.1')."
    ),
    output_dir: Path = typer.Option(
        "my_docs", "--output-dir", "-o", help="Directory to save the generated documentation."
    ),
    max_crawl_pages: Optional[int] = typer.Option( # Use Optional, Changed default
        200, "--max-crawl-pages", "-p", help="Maximum number of pages to crawl per package. Default: 200. Set to 0 for unlimited.", callback=lambda v: None if v == 0 else v # Handle 0 for unlimited
    ),
    max_crawl_depth: int = typer.Option(
        2, "--max-crawl-depth", "-D", help="Maximum depth to crawl from the starting URL. Default: 2." # Changed short option to avoid conflict
    ),
    chunk_size: int = typer.Option(
        1_000_000, "--chunk-size", "-c", help="Chunk size (in characters) for LLM compaction. Default: 1,000,000." # Changed default
    ),
    gemini_api_key: Optional[str] = typer.Option( # Added gemini_api_key option
        lambda: os.environ.get("GEMINI_API_KEY"), # Get from env var by default
        "--gemini-api-key",
        "-k",
        help="Gemini API Key. Can also be set via the GEMINI_API_KEY environment variable.",
        show_default=False, # Don't show potentially sensitive key in help
    ),
):
    """
    Generates LLM context by scraping and summarizing documentation for Python libraries.

    You must provide one input source: --requirements-file, --input-folder, or --packages.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Validate input options: Exactly one must be provided
    input_options = [requirements_file, input_folder, package_string]
    if sum(opt is not None for opt in input_options) != 1:
        logger.error("Error: Please provide exactly one input source: --requirements-file, --input-folder, or --packages.")
        raise typer.Exit(code=1)

    packages_to_process: Set[str] = set()

    # Determine packages based on input type
    if requirements_file:
        logger.info(f"Processing requirements file: {requirements_file}")
        packages_to_process = parse_requirements(requirements_file)
    elif input_folder:
        req_file_in_folder = input_folder / "requirements.txt"
        if not req_file_in_folder.is_file():
            logger.error(f"Error: Could not find requirements.txt in folder: {input_folder}")
            raise typer.Exit(code=1)
        logger.info(f"Processing requirements file found in folder: {req_file_in_folder}")
        packages_to_process = parse_requirements(req_file_in_folder)
    elif package_string:
        logger.info("Processing packages from input string.")
        # Simple split by newline and filter empty strings
        packages_to_process = set(pkg.strip() for pkg in package_string.split('\\n') if pkg.strip()) # Use \\n as specified in help


    # Run the processing asynchronously
    asyncio.run(
        process_requirements(
            packages=packages_to_process,
            output_dir=output_dir,
            max_crawl_pages=max_crawl_pages,
            max_crawl_depth=max_crawl_depth,
            chunk_size=chunk_size,
            gemini_api_key=gemini_api_key, # Pass key
        )
    )

if __name__ == "__main__":
    app()