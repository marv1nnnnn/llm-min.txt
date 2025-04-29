import asyncio
import logging
import os
import sys
from pathlib import Path

import typer  # Import typer
from dotenv import load_dotenv  # Added dotenv import

from .client import LLMMinClient  # Import LLMMinClient
from .compacter import compact_content_with_llm
from .crawler import crawl_documentation
from .parser import parse_requirements
from .search import find_documentation_url

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
        logger.info(
            f"Successfully wrote full text content for {package_name} to {file_path}"
        )
    except Exception as e:
        logger.error(
            f"Failed to write full text file for {package_name}: {e}", exc_info=True
        )
        # Do not re-raise, allow the process to continue for other packages


def write_min_text_file(output_base_dir: str | Path, package_name: str, content: str):
    """Writes the compacted text content to a file within the package-specific directory."""
    try:
        # Construct the package-specific directory path
        package_dir = Path(output_base_dir) / package_name
        package_dir.mkdir(parents=True, exist_ok=True)

        # Define the output file path
        file_path = package_dir / "llm-min.txt"

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info(
            f"Successfully wrote minimal text content for {package_name} to {file_path}"
        )
    except Exception as e:
        logger.error(
            f"Failed to write minimal text file for {package_name}: {e}", exc_info=True
        )
        # Do not re-raise, allow the process to continue for other packages


async def process_package(
    package_name: str,
    output_dir: Path,
    max_crawl_pages: int | None,  # Use Optional
    max_crawl_depth: int,
    chunk_size: int,
    gemini_api_key: str | None,  # Add gemini_api_key parameter
):
    """Processes a single package: finds docs, crawls, compacts, and writes files."""
    logger.info(f"--- Processing package: {package_name} ---")
    try:
        # Pass the gemini_api_key to find_documentation_url
        doc_url = await find_documentation_url(package_name, api_key=gemini_api_key)
        if not doc_url:
            logger.warning(
                f"Could not find documentation URL for {package_name}. Skipping."
            )
            return False

        logger.info(f"Found documentation URL for {package_name}: {doc_url}")

        # If using a dummy API key, bypass crawling and provide dummy content
        if gemini_api_key == "dummy_api_key":
            logger.info(
                "Using dummy API key. Bypassing crawling and using dummy content."
            )
            crawled_content = (
                f"This is dummy crawled content for {package_name} from {doc_url}."
            )
        else:
            crawled_content = await crawl_documentation(
                doc_url, max_pages=max_crawl_pages, max_depth=max_crawl_depth
            )

        if not crawled_content:
            logger.warning(f"No content crawled for {package_name}. Skipping.")
            return False

        logger.info(
            f"Successfully crawled content for {package_name}. Total size: {len(crawled_content)} characters."
        )

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
            subject=package_name,  # Pass package_name as subject
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


async def process_requirements(
    packages: set[str],  # Accept parsed packages directly
    output_dir: Path,
    max_crawl_pages: int | None,  # Use Optional
    max_crawl_depth: int,
    chunk_size: int,
    gemini_api_key: str | None,  # Add gemini_api_key parameter
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
            gemini_api_key,  # Pass key down
        )
        for package_name in packages
    ]
    await asyncio.gather(*tasks)


app = typer.Typer(
    help="Generates LLM context by scraping and summarizing documentation for Python libraries."
)


@app.command()
def main(
    requirements_file: Path | None = typer.Option(
        None,
        "--requirements-file",
        "-f",
        help="Path to a requirements.txt file.",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
    input_folder: Path | None = typer.Option(
        None,
        "--input-folder",
        "-d",
        help="Path to a folder containing a requirements.txt file.",
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
    ),
    package_string: str | None = typer.Option(
        None,
        "--packages",
        "-pkg",
        help="A string containing package names, one per line (e.g., 'requests\\npydantic==2.1').",
    ),
    output_dir: str = typer.Option(
        "my_docs",
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
        2,
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
    doc_url: str | None = typer.Option(
        None,
        "--doc-url",
        "-u",
        help="Direct URL to documentation to crawl, bypassing search.",
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
):
    """
    Generates LLM context by scraping and summarizing documentation for Python libraries.

    You must provide one input source: --requirements-file, --input-folder, --packages, or --doc-url.
    """
    # Configure logging level based on the verbose flag
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=log_level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    # Reduce verbosity from libraries (can be kept here or moved after basicConfig)
    logging.getLogger("duckduckgo_search").setLevel(logging.WARNING)
    logging.getLogger("crawl4ai").setLevel(
        logging.INFO
    )  # Keep crawl4ai at INFO unless verbose?
    logging.getLogger("httpx").setLevel(logging.WARNING)

    logger.info(
        f"Verbose logging {'enabled' if verbose else 'disabled'}."
    )  # Log if verbose is active
    logger.debug(f"Gemini API Key received in main: {gemini_api_key}")

    # Ensure output_dir is converted to a Path object
    logger.info(f"Type of output_dir: {type(output_dir)}")
    logger.info(f"Value of output_dir: {output_dir}")
    logger.info(
        f"Before Path conversion - Type of output_dir: {type(output_dir)}, Value: {output_dir}"
    )
    output_dir_path = Path(str(output_dir))  # Explicitly convert to string before Path
    logger.info(
        f"After Path conversion - Type of output_dir_path: {type(output_dir_path)}, Value: {output_dir_path}"
    )
    output_dir_path.mkdir(parents=True, exist_ok=True)

    # Instantiate the client
    # The client handles the API key validation and guide loading internally
    try:
        client = LLMMinClient(api_key=gemini_api_key)
    except (ValueError, RuntimeError) as e:
        logger.error(f"Client initialization error: {e}")
        raise typer.Exit(code=1)

    # Get the PCS guide content and write it to the output directory root
    try:
        pcs_guide_content = client.get_pcs_guide()
        if "ERROR:" in pcs_guide_content:
            logger.error(f"Failed to retrieve PCS guide content: {pcs_guide_content}")
            # Decide if this should be a hard error or just a warning
            # For now, let's make it a warning and continue with package processing
            logger.warning(
                "Proceeding without writing PCS guide due to retrieval error."
            )
        else:
            guide_file_path = output_dir_path / "pcs-guide.md"
            with open(guide_file_path, "w", encoding="utf-8") as f:
                f.write(pcs_guide_content)
            logger.info(f"Successfully wrote PCS guide to {guide_file_path}")
    except Exception as e:
        logger.error(
            f"An error occurred while writing the PCS guide: {e}", exc_info=True
        )
        # Decide if this should be a hard error or just a warning
        logger.warning(
            "Proceeding without writing PCS guide due to file writing error."
        )

    # Validate input options: Exactly one must be provided
    input_options = [requirements_file, input_folder, package_string, doc_url]
    if sum(opt is not None for opt in input_options) != 1:
        logger.error(
            "Error: Please provide exactly one input source: --requirements-file, "
            "--input-folder, --packages, or --doc-url."
        )
        raise typer.Exit(code=1)

    packages_to_process: set[str] = set()
    target_doc_url: str | None = None

    # Determine packages or doc_url based on input type
    if requirements_file:
        logger.info(f"Processing requirements file: {requirements_file}")
        packages_to_process = parse_requirements(requirements_file)
    elif input_folder:
        req_file_in_folder = input_folder / "requirements.txt"
        if not req_file_in_folder.is_file():
            logger.error(
                f"Error: Could not find requirements.txt in folder: {input_folder}"
            )
            raise typer.Exit(code=1)
        logger.info(
            f"Processing requirements file found in folder: {req_file_in_folder}"
        )
        packages_to_process = parse_requirements(req_file_in_folder)
    elif package_string:
        logger.info("Processing packages from input string.")
        packages_to_process = set(
            pkg.strip() for pkg in package_string.splitlines() if pkg.strip()
        )
    elif doc_url:
        logger.info(f"Processing direct documentation URL: {doc_url}")
        target_doc_url = doc_url
        # For direct URL, we treat the "package name" as the last part of the URL path
        # This is a simplification; a more robust approach might involve parsing the URL
        # or requiring a package name argument with --doc-url.
        # For now, let's extract a name from the URL for file writing purposes.
        # Example: https://docs.python.org/3/library/os.html -> os
        # Example: https://requests.readthedocs.io/en/latest/ -> requests
        try:
            from urllib.parse import urlparse

            parsed_url = urlparse(doc_url)
            path_parts = [part for part in parsed_url.path.split("/") if part]
            if path_parts:
                # Use the last non-empty path part as the package name
                package_name_from_url = ".".join(path_parts)
                packages_to_process.add(package_name_from_url)
                logger.info(f"Inferred package name from URL: {package_name_from_url}")
            else:
                # If no path parts, use the domain name (simplified)
                domain_parts = parsed_url.netloc.split(".")
                package_name_from_url = (
                    domain_parts[0] if domain_parts else "crawled_doc"
                )
                packages_to_process.add(package_name_from_url)
                logger.info(
                    f"Inferred package name from domain: {package_name_from_url}"
                )

        except Exception as e:
            logger.warning(
                f"Could not infer package name from URL {doc_url}: {e}. Using 'crawled_doc'."
            )
            packages_to_process.add("crawled_doc")

    # If a direct URL is provided, process only that URL
    if target_doc_url:
        # Assuming only one package name is inferred or set for a direct URL
        package_name = (
            list(packages_to_process)[0] if packages_to_process else "crawled_doc"
        )
        asyncio.run(
            process_direct_url(
                package_name=package_name,
                doc_url=target_doc_url,
                output_dir=output_dir_path,
                max_crawl_pages=max_crawl_pages,
                max_crawl_depth=max_crawl_depth,
                chunk_size=chunk_size,
                gemini_api_key=gemini_api_key,
            )
        )

    # If no direct URL is provided, process packages from other sources
    elif packages_to_process:
        # Run the processing asynchronously
        asyncio.run(
            process_requirements(
                packages=packages_to_process,
                output_dir=output_dir_path,  # Pass the Path object
                max_crawl_pages=max_crawl_pages,
                max_crawl_depth=max_crawl_depth,
                chunk_size=chunk_size,
                gemini_api_key=gemini_api_key,
            )
        )


async def process_direct_url(
    package_name: str,
    doc_url: str,
    output_dir: Path,
    max_crawl_pages: int | None,
    max_crawl_depth: int,
    chunk_size: int,
    gemini_api_key: str | None,
):
    """Processes a single direct documentation URL."""
    logger.info(f"--- Processing direct URL for {package_name}: {doc_url} ---")
    try:
        crawled_content = await crawl_documentation(
            doc_url, max_pages=max_crawl_pages, max_depth=max_crawl_depth
        )

        if not crawled_content:
            logger.warning(f"No content crawled from {doc_url}. Skipping.")
            return False

        logger.info(
            f"Successfully crawled content from {doc_url}. Total size: {len(crawled_content)} characters."
        )

        # Write the full crawled content to a file
        write_full_text_file(output_dir, package_name, crawled_content)

        # Compact the content
        logger.info(f"Compacting content for {package_name}...")
        compacted_content = await compact_content_with_llm(
            aggregated_content=crawled_content,
            chunk_size=chunk_size,
            api_key=gemini_api_key,
            subject=package_name,
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
