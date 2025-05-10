import asyncio
import logging
import os
import sys
from pathlib import Path

import typer  # Import typer
from dotenv import load_dotenv  # Added dotenv import

from .crawler import crawl_documentation
from .search import find_documentation_url
from .compacter import compact_content_to_structured_text

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


def write_full_text_file(output_base_dir: str | Path, package_name: str, content: str):
    """Writes the full crawled text content to a file within the package-specific directory."""
    try:
        # Construct the package-specific directory path
        package_dir = Path(output_base_dir) / package_name
        package_dir.mkdir(parents=True, exist_ok=True)

        # Define the output file path
        file_path = package_dir / "llm-full.txt"

        with open(file_path, "w", encoding="utf-8") as f:
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

        with open("assets/llm_min_guideline.md", "r", encoding="utf-8") as f:
            llm_min_guideline = f.read()

        if not os.path.exists(os.path.join(package_dir, "llm-min_guideline.md")):
            with open(os.path.join(package_dir, "llm-min-guideline.md"), "w", encoding="utf-8") as f:
                f.write(llm_min_guideline)

        # Define the output file path
        file_path = package_dir / "llm-min.txt"

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info(f"Successfully wrote minimal text content for {package_name} to {file_path}")
    except Exception as e:
        logger.error(f"Failed to write minimal text file for {package_name}: {e}", exc_info=True)
        # Do not re-raise, allow the process to continue for other packages


async def process_package(
    package_name: str,
    output_dir: Path,
    max_crawl_pages: int | None,  # Use Optional
    max_crawl_depth: int,
    chunk_size: int,
    gemini_api_key: str | None,  # Add gemini_api_key parameter
    model_name: str,  # Add model_name parameter
):
    """Processes a single package: finds docs, crawls, compacts, and writes files."""
    logger.info(f"--- Processing package: {package_name} ---")
    try:
        # Pass the gemini_api_key and model_name to find_documentation_url
        doc_url = await find_documentation_url(package_name, api_key=gemini_api_key, model_name=model_name)
        if not doc_url:
            logger.warning(f"Could not find documentation URL for {package_name}. Skipping.")
            return False

        logger.info(f"Found documentation URL for {package_name}: {doc_url}")

        # If using a dummy API key, bypass crawling and provide dummy content
        if gemini_api_key == "dummy_api_key":
            logger.info("Using dummy API key. Bypassing crawling and using dummy content.")
            crawled_content = f"This is dummy crawled content for {package_name} from {doc_url}."
        else:
            crawled_content = await crawl_documentation(doc_url, max_pages=max_crawl_pages, max_depth=max_crawl_depth)

        if not crawled_content:
            logger.warning(f"No content crawled for {package_name}. Skipping.")
            return False

        logger.info(f"Successfully crawled content for {package_name}. Total size: {len(crawled_content)} characters.")

        # Write the full crawled content to a file
        # Write the full crawled content to chunked files
        write_full_text_file(output_dir, package_name, crawled_content)

        # Compact the content
        logger.info(f"Compacting content for {package_name}...")
        # Pass gemini_api_key and model_name to the compaction function
        # Also pass package_name as the subject
        compacted_content = await compact_content_to_structured_text(
            aggregated_content=crawled_content,
            chunk_size=chunk_size,
            api_key=gemini_api_key,
            subject=package_name,  # Pass package_name as subject
            model_name=model_name,  # Pass model_name
        )

        if not compacted_content or "ERROR:" in compacted_content:
            log_message = (
                f"Compaction failed or resulted in empty content for {package_name}. "
                f"Skipping writing min file. Detail: {compacted_content}"
            )
            logger.warning(log_message)
            return False

        logger.info(
            f"Successfully compacted content for {package_name}. Compacted size: {len(compacted_content)} characters."
        )

        # Write the compacted content to a file
        write_min_text_file(output_dir, package_name, compacted_content)

        logger.info(f"Finished processing package: {package_name}")
        return True
    except Exception as e:
        logger.error(
            f"An error occurred while processing package {package_name}: {e}",
            exc_info=True,
        )
        return False


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
        1_000_000,
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

    output_dir_path = Path(str(output_dir))
    output_dir_path.mkdir(parents=True, exist_ok=True)

    # Validate input options: At least one of packages or doc_urls must be provided
    if not package_string and not doc_urls:
        logger.error(
            "Error: Please provide at least one input source: --packages and/or --doc-urls."
        )
        raise typer.Exit(code=1)

    tasks = []
    packages_to_process_names: set[str] = set()

    if package_string:
        logger.info(f"Processing packages from --packages: {package_string}")
        packages_to_process_names = set(pkg.strip() for pkg in package_string.split(',') if pkg.strip())
        for package_name in packages_to_process_names:
            tasks.append(
                process_package(
                    package_name,
                    output_dir_path,
                    max_crawl_pages,
                    max_crawl_depth,
                    chunk_size,
                    gemini_api_key,
                    gemini_model,
                )
            )

    if doc_urls:
        logger.info(f"Processing URLs from --doc-urls: {doc_urls}")
        individual_doc_urls = [url.strip() for url in doc_urls.split(',') if url.strip()]
        for target_doc_url in individual_doc_urls:
            # Infer package name from URL for directory structure
            try:
                from urllib.parse import urlparse
                parsed_url = urlparse(target_doc_url)
                path_parts = [part for part in parsed_url.path.split("/") if part]
                if path_parts:
                    package_name_from_url = "_".join(path_parts).replace(".html", "").replace(".htm", "")
                else:
                    domain_parts = parsed_url.netloc.split(".")
                    package_name_from_url = domain_parts[0] if domain_parts else "crawled_doc"
                # Ensure uniqueness if a package name and a URL-derived name conflict
                original_package_name_from_url = package_name_from_url
                counter = 1
                while package_name_from_url in packages_to_process_names:
                    package_name_from_url = f"{original_package_name_from_url}_{counter}"
                    counter += 1
                packages_to_process_names.add(package_name_from_url) # Add to set to track for uniqueness

            except Exception as e:
                logger.warning(f"Could not infer package name from URL {target_doc_url}: {e}. Using hash.")
                import hashlib
                package_name_from_url = hashlib.md5(target_doc_url.encode()).hexdigest()[:10]
            
            logger.info(f"Inferred package name for URL {target_doc_url}: {package_name_from_url}")
            tasks.append(
                process_direct_url(
                    package_name=package_name_from_url,
                    doc_url=target_doc_url,
                    output_dir=output_dir_path,
                    max_crawl_pages=max_crawl_pages,
                    max_crawl_depth=max_crawl_depth,
                    chunk_size=chunk_size,
                    gemini_api_key=gemini_api_key,
                    model_name=gemini_model,
                )
            )

    async def run_all_tasks(tasks_to_await):
        """Helper coroutine to await a list of tasks using asyncio.gather."""
        return await asyncio.gather(*tasks_to_await)

    if tasks:
        logger.info(f"Collected {len(tasks)} tasks to run.")
        asyncio.run(run_all_tasks(tasks)) # Call asyncio.run with the wrapper coroutine
    else:
        logger.info("No tasks to run.")


async def process_direct_url(
    package_name: str,
    doc_url: str,
    output_dir: Path,
    max_crawl_pages: int | None,
    max_crawl_depth: int,
    chunk_size: int,
    gemini_api_key: str | None,
    model_name: str,  # Add model_name parameter
):
    """Processes a single direct documentation URL."""
    logger.info(f"--- Processing direct URL for {package_name}: {doc_url} ---")
    try:
        crawled_content = await crawl_documentation(doc_url, max_pages=max_crawl_pages, max_depth=max_crawl_depth)

        if not crawled_content:
            logger.warning(f"No content crawled from {doc_url}. Skipping.")
            return False

        logger.info(f"Successfully crawled content from {doc_url}. Total size: {len(crawled_content)} characters.")

        # Write the full crawled content to a file
        write_full_text_file(output_dir, package_name, crawled_content)

        # Compact the content
        logger.info(f"Compacting content for {package_name}...")
        compacted_content = await compact_content_to_structured_text(
            aggregated_content=crawled_content,
            chunk_size=chunk_size,
            api_key=gemini_api_key,
            subject=package_name,
            model_name=model_name,  # Pass model_name
        )

        if not compacted_content or "ERROR:" in compacted_content:
            log_message = (
                f"Compaction failed or resulted in empty content for {package_name}. "
                f"Skipping writing min file. Detail: {compacted_content}"
            )
            logger.warning(log_message)
            return False

        logger.info(
            f"Successfully compacted content for {package_name}. Compacted size: {len(compacted_content)} characters."
        )

        # Write the compacted content to a file
        write_min_text_file(output_dir, package_name, compacted_content)

        logger.info(f"Finished processing direct URL: {doc_url}")
        return True
    except Exception as e:
        logger.error(
            f"An error occurred while processing direct URL {doc_url}: {e}",
            exc_info=True,
        )
        return False


if __name__ == "__main__":
    app()
