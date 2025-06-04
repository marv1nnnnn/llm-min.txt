import asyncio  # Added for running async functions
import os
import shutil
import importlib.resources

from .compacter import compact_content_to_structured_text
from .crawler import crawl_documentation
from .search import find_documentation_url


class LLMMinGenerator:
    """
    Generates llm_min.txt from a Python package name or a documentation URL.
    """

    def __init__(
        self, output_dir: str = ".", output_folder_name_override: str | None = None, llm_config: dict | None = None, force_reprocess: bool = False
    ):
        """
        Initializes the LLMMinGenerator instance.

        Args:
            output_dir (str): The base directory where the generated files will be saved.
            output_folder_name_override (Optional[str]): Override for the final output folder name.
            llm_config (Optional[Dict]): Configuration for the LLM.
            force_reprocess (bool): Whether to force reprocessing of existing files.
        """
        self.base_output_dir = output_dir
        self.output_folder_name_override = output_folder_name_override
        self.llm_config = llm_config or {}  # Use empty dict if None
        self.force_reprocess = force_reprocess

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
        # Use the override name if provided, otherwise use the source_name
        final_folder_name = self.output_folder_name_override if self.output_folder_name_override else source_name
        output_path = os.path.join(self.base_output_dir, final_folder_name)
        os.makedirs(output_path, exist_ok=True)
        
        full_file_path = os.path.join(output_path, "llm-full.txt")
        
        # Check if llm-full.txt already exists and reuse it (unless force_reprocess is True)
        if not self.force_reprocess and os.path.exists(full_file_path):
            print(f"Found existing llm-full.txt at {full_file_path}, reusing it...")
            print("Use --force-reprocess to regenerate from source files")
            try:
                with open(full_file_path, 'r', encoding='utf-8') as f:
                    existing_content = f.read()
                if existing_content.strip():
                    input_content = existing_content
                    print(f"Successfully loaded existing content ({len(input_content)} characters)")
                else:
                    print("Existing llm-full.txt is empty, using provided content")
            except Exception as e:
                print(f"Could not read existing llm-full.txt: {e}, using provided content")
        elif self.force_reprocess and os.path.exists(full_file_path):
            print(f"Force reprocessing enabled, ignoring existing llm-full.txt")
            # Also clean up any intermediate files
            intermediate_dir = os.path.join(output_path, ".intermediate")
            if os.path.exists(intermediate_dir):
                try:
                    import shutil
                    shutil.rmtree(intermediate_dir)
                    print("Cleaned up existing intermediate files")
                except Exception as e:
                    print(f"Could not clean up intermediate files: {e}")
        
        print("Compacting provided text content...")
        
        # Calculate optimal chunk size based on content length
        content_length = len(input_content)
        optimal_chunk_size = self._calculate_optimal_chunk_size(content_length)
        print(f"Content length: {content_length:,} characters")
        print(f"Using chunk size: {optimal_chunk_size:,} characters")
        
        try:
            min_content = asyncio.run(
                compact_content_to_structured_text(
                    input_content,
                    library_name_param=source_name,
                    library_version_param=library_version,
                    chunk_size=optimal_chunk_size,
                    api_key=self.llm_config.get("api_key"),
                    model_name=self.llm_config.get("model_name"),
                    output_path=output_path,  # Pass output path for intermediate saving
                    force_reprocess=self.force_reprocess,  # Pass force_reprocess flag
                    save_fragments=self.llm_config.get("save_fragments", True),  # Pass save_fragments flag
                )
            )
            self._write_output_files(source_name, input_content, min_content)
        except Exception as e:
            raise Exception(f"Compaction failed for source '{source_name}': {e}") from e

    def _calculate_optimal_chunk_size(self, content_length: int) -> int:
        """
        Calculate optimal chunk size based on content length to avoid MAX_TOKEN issues.
        
        Args:
            content_length (int): Total character count of content
            
        Returns:
            int: Optimal chunk size in characters
        """
        # Get base chunk size from config, default to 600k
        base_chunk_size = self.llm_config.get("chunk_size", 600_000)
        
        # Rough estimate: 1 token ≈ 4 characters
        estimated_tokens = content_length // 4
        
        # Use much more conservative chunking to avoid MAX_TOKENS
        # Gemini has ~1M token context, but output is limited to ~8k tokens
        # Large docs like RenPy need very small chunks to avoid timeout/truncation
        
        if estimated_tokens < 25_000:  # < 25k tokens (very small)
            return min(base_chunk_size, 80_000)   # 80k chars ≈ 20k tokens
        elif estimated_tokens < 50_000:  # < 50k tokens (small)
            return min(base_chunk_size, 100_000)  # 100k chars ≈ 25k tokens
        elif estimated_tokens < 100_000:  # < 100k tokens (medium)
            return min(base_chunk_size, 120_000)  # 120k chars ≈ 30k tokens
        elif estimated_tokens < 200_000:  # < 200k tokens (large)
            return min(base_chunk_size, 100_000)  # 100k chars ≈ 25k tokens (back to smaller)
        elif estimated_tokens < 350_000:  # < 350k tokens (very large, like RenPy)
            return min(base_chunk_size, 80_000)   # 80k chars ≈ 20k tokens (much smaller)
        else:  # Extremely large content
            return min(base_chunk_size, 60_000)   # 60k chars ≈ 15k tokens (very conservative)
        
        # Note: For very large documentation sets, we prioritize avoiding 
        # MAX_TOKENS errors over processing efficiency

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
        # Use the override name if provided, otherwise use the identifier
        final_folder_name = self.output_folder_name_override if self.output_folder_name_override else identifier
        output_path = os.path.join(self.base_output_dir, final_folder_name)
        os.makedirs(output_path, exist_ok=True)
        
        min_content = asyncio.run(
            compact_content_to_structured_text(
                full_content,
                library_name_param=identifier,
                library_version_param=library_version,
                chunk_size=self.llm_config.get("chunk_size", 1000000),  # Default from compacter.py
                api_key=self.llm_config.get("api_key"),
                model_name=self.llm_config.get("model_name"),
                output_path=output_path,  # Pass output path for intermediate saving
                force_reprocess=self.force_reprocess,  # Pass force_reprocess flag
                save_fragments=self.llm_config.get("save_fragments", True),  # Pass save_fragments flag
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
