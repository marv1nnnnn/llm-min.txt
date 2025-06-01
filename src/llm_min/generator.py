import asyncio  # Added for running async functions
import os
import shutil
import importlib.resources

from llm_min.compacter import compact_content_to_structured_text
from llm_min.crawler import crawl_documentation
from llm_min.search import find_documentation_url


class LLMMinGenerator:
    """
    Generates llm_min.txt from a Python package name or a documentation URL.
    """

    def __init__(
        self, output_dir: str = ".", output_folder_name_override: str | None = None, llm_config: dict | None = None
    ):
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

    def generate_from_text(self, input_content: str, source_name: str, library_version: str | None = None):
        """
        Generates llm_min.txt from provided text content.

        Args:
            input_content (str): The text content to process.
            source_name (str): Identifier for the output directory.
            library_version (str): The version of the library.

        Raises:
            Exception: If compaction fails.
        """
        print("Compacting provided text content...")
        try:
            min_content = asyncio.run(
                compact_content_to_structured_text(
                    input_content,
                    library_name_param=source_name,
                    library_version_param=library_version,
                    chunk_size=self.llm_config.get("chunk_size", 1000000),
                    api_key=self.llm_config.get("api_key"),
                    model_name=self.llm_config.get("model_name"),
                )
            )
            self._write_output_files(source_name, input_content, min_content)
        except Exception as e:
            raise Exception(f"Compaction failed for source '{source_name}': {e}") from e

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
        try:
            # Use importlib.resources to access the packaged guideline file
            # Use importlib.resources.files() for Python 3.9+
            guideline_source_resource = importlib.resources.files('llm_min.assets') / 'llm_min_guideline.md'
            with importlib.resources.as_file(guideline_source_resource) as guideline_source_path:
                shutil.copy(guideline_source_path, guideline_file_path)
        except FileNotFoundError:
            print(f"Warning: Could not find packaged llm_min_guideline.md. Guideline file not copied.")
        except Exception as e:
            print(f"Warning: An unexpected error occurred while copying guideline: {e}. Guideline file not copied.")

        print("Output files written successfully.")
