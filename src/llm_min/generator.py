import asyncio  # Added for running async functions
import os
import shutil

from llm_min.compacter import compact_content_to_structured_text
from llm_min.crawler import crawl_documentation
from llm_min.search import find_documentation_url


class LLMMinGenerator:
    """
    Generates llm_min.txt from a Python package name or a documentation URL.
    """

    def __init__(self, output_dir: str = ".", output_folder_name_override: str | None = None, llm_config: dict | None = None):
        """
        Initializes the LLMMinGenerator instance.

        Args:
            output_dir (str): The base directory where the generated files will be saved.
            output_folder_name_override (Optional[str]): Override for the final output folder name.
            llm_config (Optional[Dict]): Configuration for the LLM.
        """
        self.base_output_dir = output_dir
        self.output_folder_name_override = output_folder_name_override
        self.llm_config = llm_config or {}  # Use empty dict if None

    def generate_from_package(self, package_name: str, library_version: str | None = None):
        """
        Generates llm_min.txt for a given Python package name.

        Args:
            package_name (str): The name of the Python package.
            library_version (str): The version of the library.

        Raises:
            Exception: If no documentation URL is found or if any step fails.
        """
        print(f"Searching for documentation for package: {package_name}")
        # search_for_documentation_urls is likely synchronous, if it were async, it would need asyncio.run too
        doc_url = asyncio.run(
            find_documentation_url(
                package_name, api_key=self.llm_config.get("api_key"), model_name=self.llm_config.get("model_name")
            )
        )

        if not doc_url:
            raise Exception(f"No documentation URL found for package: {package_name}")

        print(f"Found documentation URL: {doc_url}")
        self._crawl_and_compact(doc_url, package_name, library_version)

    def generate_from_url(self, doc_url: str, library_version: str | None = None):
        """
        Generates llm_min.txt from a direct documentation URL.

        Args:
            doc_url (str): The direct URL to the documentation.
            library_version (str): The version of the library.

        Raises:
            Exception: If crawling or compaction fails.
        """
        print(f"Generating from URL: {doc_url}")
        # Derive a directory name from the URL
        url_identifier = doc_url.replace("https://", "").replace("http://", "").replace("/", "_").replace(".", "_")
        self._crawl_and_compact(doc_url, url_identifier, library_version)

    def _crawl_and_compact(self, url: str, identifier: str, library_version: str | None = None):
        """
        Handles the crawling and compaction steps.

        Args:
            url (str): The documentation URL.
            identifier (str): Identifier for the output directory (package name or URL derivative).
        """
        print(f"Crawling documentation from: {url}")
        # crawl_documentation is async, so we run it in an event loop
        # Pass crawl parameters from llm_config
        full_content = asyncio.run(
            crawl_documentation(
                url, max_pages=self.llm_config.get("max_crawl_pages"), max_depth=self.llm_config.get("max_crawl_depth")
            )
        )

        print("Compacting documentation...")
        # compact_content_to_structured_text is async
        min_content = asyncio.run(
            compact_content_to_structured_text(
                full_content,
                library_name_param=identifier,
                library_version_param=library_version,
                chunk_size=self.llm_config.get("chunk_size", 1000000),  # Default from compacter.py
                api_key=self.llm_config.get("api_key"),
                model_name=self.llm_config.get("model_name"),
            )
        )

        self._write_output_files(identifier, full_content, min_content)

    def _write_output_files(self, identifier: str, full_content: str, min_content: str):
        """
        Handles writing the output files.

        Args:
            identifier (str): Identifier for the output directory.
            full_content (str): The full documentation content.
            min_content (str): The compacted documentation content.
        """
        # Use the override name if provided, otherwise use the identifier
        final_folder_name = self.output_folder_name_override if self.output_folder_name_override else identifier
        output_path = os.path.join(self.base_output_dir, final_folder_name)
        os.makedirs(output_path, exist_ok=True)

        full_file_path = os.path.join(output_path, "llm-full.txt")
        min_file_path = os.path.join(output_path, "llm-min.txt")
        guideline_file_path = os.path.join(output_path, "llm-min-guideline.md")

        print(f"Writing llm-full.txt to: {full_file_path}")
        with open(full_file_path, "w", encoding="utf-8") as f:
            f.write(full_content)

        print(f"Writing llm-min.txt to: {min_file_path}")
        with open(min_file_path, "w", encoding="utf-8") as f:
            f.write(min_content)

        print(f"Copying guideline to: {guideline_file_path}")
        # Ensure the assets directory is correctly referenced.
        # Assuming 'assets/llm_min_guideline.md' is relative to the project root
        # or where the script is executed from.
        # If generator.py is in a subdirectory, this path might need adjustment
        # or be made absolute. For now, assuming it's correct.
        try:
            shutil.copy("assets/llm_min_guideline.md", guideline_file_path)
        except FileNotFoundError:
            # Try a path relative to this file's directory if the first fails
            # This makes it more robust if the script is run from different working directories
            current_dir = os.path.dirname(os.path.abspath(__file__))
            # project_root_assets = os.path.join(
            # current_dir, "..", "..", "assets", "llm_min_guideline.md"
            # ) # Adjust based on actual structure
            # A more robust way would be to pass the assets path or determine it globally
            # For now, let's assume the original path or a simple relative one.
            # If assets is at the same level as src:
            assets_path_alt = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "llm_min_guideline.md"
            )

            try:
                shutil.copy(assets_path_alt, guideline_file_path)
            except FileNotFoundError:
                print(
                    f"Warning: Could not find llm_min_guideline.md at 'assets/llm_min_guideline.md' or '{assets_path_alt}'. Guideline file not copied."
                )

        print("Output files written successfully.")
