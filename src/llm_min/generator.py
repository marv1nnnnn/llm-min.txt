import os
import shutil
from typing import Optional, Dict

from .search import search_documentation_url
from .crawler import crawl_documentation
from .compacter import compact_documentation

class LLMMinGenerator:
    """
    Generates llm_min.txt from a Python package name or a documentation URL.
    """
    def __init__(self, output_dir: str = ".", llm_config: Optional[Dict] = None):
        """
        Initializes the LLMMinGenerator instance.

        Args:
            output_dir (str): The base directory where the generated files will be saved.
            llm_config (Optional[Dict]): Configuration for the LLM.
        """
        self.output_dir = output_dir
        self.llm_config = llm_config or {} # Use empty dict if None

    def generate_from_package(self, package_name: str):
        """
        Generates llm_min.txt for a given Python package name.

        Args:
            package_name (str): The name of the Python package.

        Raises:
            Exception: If no documentation URL is found or if any step fails.
        """
        print(f"Searching for documentation for package: {package_name}")
        doc_url = search_documentation_url(package_name)

        if not doc_url:
            raise Exception(f"No documentation URL found for package: {package_name}")

        print(f"Found documentation URL: {doc_url}")
        self._crawl_and_compact(doc_url, package_name)

    def generate_from_url(self, doc_url: str):
        """
        Generates llm_min.txt from a direct documentation URL.

        Args:
            doc_url (str): The direct URL to the documentation.

        Raises:
            Exception: If crawling or compaction fails.
        """
        print(f"Generating from URL: {doc_url}")
        # Derive a directory name from the URL
        url_identifier = doc_url.replace("https://", "").replace("http://", "").replace("/", "_").replace(".", "_")
        self._crawl_and_compact(doc_url, url_identifier)

    def _crawl_and_compact(self, url: str, identifier: str):
        """
        Handles the crawling and compaction steps.

        Args:
            url (str): The documentation URL.
            identifier (str): Identifier for the output directory (package name or URL derivative).
        """
        print(f"Crawling documentation from: {url}")
        full_content = crawl_documentation(url)

        print("Compacting documentation...")
        min_content = compact_documentation(full_content, llm_config=self.llm_config)

        self._write_output_files(identifier, full_content, min_content)

    def _write_output_files(self, identifier: str, full_content: str, min_content: str):
        """
        Handles writing the output files.

        Args:
            identifier (str): Identifier for the output directory.
            full_content (str): The full documentation content.
            min_content (str): The compacted documentation content.
        """
        output_path = os.path.join(self.output_dir, identifier)
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
        shutil.copy("assets/llm_min_guideline.md", guideline_file_path)

        print("Output files written successfully.")