import os
import sys
from typing import Set
from unittest.mock import patch
from pathlib import Path # Import Path

import pytest
from click.testing import CliRunner

from src.llm_min.main import (
    cli,
    process_package,
    process_direct_url,
    process_requirements,
    write_full_text_file,
    write_min_text_file,
)


# Mock the search and crawler functions
@patch("src.llm_min.search.search")
@patch("src.llm_min.crawler.crawler")
def test_cli_doc_url(mock_crawler, mock_search):
    """Test the CLI with --doc-url argument."""
    runner = CliRunner()
    doc_url = "http://example.com/docs"
    result = runner.invoke(cli, ["--doc-url", doc_url])

    assert result.exit_code == 0
    mock_search.assert_not_called()
    mock_crawler.assert_called_once_with(doc_url)


@patch("src.llm_min.search.search")
@patch("src.llm_min.crawler.crawler")
def test_cli_basic(mock_crawler, mock_search):
    """Test the CLI with no arguments."""
    runner = CliRunner()
    result = runner.invoke(cli)

    assert result.exit_code == 0
    mock_search.assert_called_once()  # Assuming search is called by default
    mock_crawler.assert_not_called()
    # Add more assertions based on expected default output if known
    # assert "Expected output" in result.output


@patch("src.llm_min.main.process_requirements")
@patch("src.llm_min.main.parse_requirements")
@patch("src.llm_min.search.search")
@patch("src.llm_min.crawler.crawler")
def test_cli_requirements_file(
    mock_crawler,
    mock_search,
    mock_parse_requirements,
    mock_process_requirements,
    tmp_path,
):
    """Test the CLI with --requirements-file argument."""
    runner = CliRunner()
    req_file = tmp_path / "requirements.txt"
    req_file.write_text("package1\npackage2")
    mock_parse_requirements.return_value = {"package1", "package2"}

    result = runner.invoke(cli, ["--requirements-file", str(req_file)])

    assert result.exit_code == 0
    mock_parse_requirements.assert_called_once_with(req_file)
    mock_process_requirements.assert_called_once()
    args, kwargs = mock_process_requirements.call_args
    assert kwargs["packages"] == {"package1", "package2"}
    assert "output_dir" in kwargs
    assert "max_crawl_pages" in kwargs
    assert "max_crawl_depth" in kwargs
    assert "chunk_size" in kwargs
    assert "gemini_api_key" in kwargs
    mock_search.assert_not_called()
    mock_crawler.assert_not_called()


@patch("src.llm_min.main.process_requirements")
@patch("src.llm_min.main.parse_requirements")
@patch("src.llm_min.search.search")
@patch("src.llm_min.crawler.crawler")
def test_cli_input_folder(
    mock_crawler,
    mock_search,
    mock_parse_requirements,
    mock_process_requirements,
    tmp_path,
):
    """Test the CLI with --input-folder argument."""
    runner = CliRunner()
    input_folder = tmp_path / "my_project"
    input_folder.mkdir()
    req_file = input_folder / "requirements.txt"
    req_file.write_text("package3\npackage4")
    mock_parse_requirements.return_value = {"package3", "package4"}

    result = runner.invoke(cli, ["--input-folder", str(input_folder)])

    assert result.exit_code == 0
    mock_parse_requirements.assert_called_once_with(req_file)
    mock_process_requirements.assert_called_once()
    args, kwargs = mock_process_requirements.call_args
    assert kwargs["packages"] == {"package3", "package4"}
    assert "output_dir" in kwargs
    assert "max_crawl_pages" in kwargs
    assert "max_crawl_depth" in kwargs
    assert "chunk_size" in kwargs
    assert "gemini_api_key" in kwargs
    mock_search.assert_not_called()
    mock_crawler.assert_not_called()


@patch("src.llm_min.main.process_requirements")
@patch("src.llm_min.search.search")
@patch("src.llm_min.crawler.crawler")
def test_cli_packages_string(mock_crawler, mock_search, mock_process_requirements):
    """Test the CLI with --packages argument."""
    runner = CliRunner()
    package_string = "package5\npackage6==1.0"

    result = runner.invoke(cli, ["--packages", package_string])

    assert result.exit_code == 0
    mock_process_requirements.assert_called_once()
    args, kwargs = mock_process_requirements.call_args
    assert kwargs["packages"] == {"package5", "package6==1.0"}
    assert "output_dir" in kwargs
    assert "max_crawl_pages" in kwargs
    assert "max_crawl_depth" in kwargs
    assert "chunk_size" in kwargs
    assert "gemini_api_key" in kwargs
    mock_search.assert_not_called()
    mock_crawler.assert_not_called()


@patch("src.llm_min.main.process_direct_url")
@patch("src.llm_min.search.find_documentation_url")
@patch("src.llm_min.crawler.crawl_documentation")
def test_cli_doc_url_direct(mock_crawl_documentation, mock_find_documentation_url, mock_process_direct_url):
    """Test the CLI with --doc-url argument (direct processing)."""
    runner = CliRunner()
    doc_url = "http://example.com/docs/package7"

    result = runner.invoke(cli, ["--doc-url", doc_url])

    assert result.exit_code == 0
    mock_find_documentation_url.assert_not_called()  # Should bypass search
    mock_crawl_documentation.assert_not_called()  # Should be handled by process_direct_url
    mock_process_direct_url.assert_called_once()
    args, kwargs = mock_process_direct_url.call_args
    assert kwargs["doc_url"] == doc_url
    assert "package_name" in kwargs  # Check if package name is inferred/set
    assert "output_dir" in kwargs
    assert "max_crawl_pages" in kwargs
    assert "max_crawl_depth" in kwargs
    assert "chunk_size" in kwargs
    assert "gemini_api_key" in kwargs


def test_cli_no_input():
    """Test the CLI with no input arguments."""
    runner = CliRunner()
    result = runner.invoke(cli)

    # Should exit with an error code
    assert result.exit_code != 0
    assert "Error: Please provide exactly one input source" in result.output


def test_cli_multiple_inputs(tmp_path):
    """Test the CLI with multiple input arguments."""
    runner = CliRunner()
    req_file = tmp_path / "requirements.txt"
    req_file.write_text("package1")

    result = runner.invoke(cli, ["--requirements-file", str(req_file), "--packages", "package2"])

    # Should exit with an error code
    assert result.exit_code != 0
    assert "Error: Please provide exactly one input source" in result.output

    result = runner.invoke(cli, ["--doc-url", "http://example.com", "--input-folder", str(tmp_path)])

    # Should exit with an error code
    assert result.exit_code != 0
    assert "Error: Please provide exactly one input source" in result.output


# Test default values
@patch("src.llm_min.main.process_requirements")
@patch("src.llm_min.main.parse_requirements")
def test_cli_default_args(mock_parse_requirements, mock_process_requirements, tmp_path):
    """Test the CLI with default argument values."""
    runner = CliRunner()
    req_file = tmp_path / "requirements.txt"
    req_file.write_text("package1")
    mock_parse_requirements.return_value = {"package1"}

    result = runner.invoke(cli, ["--requirements-file", str(req_file)])

    assert result.exit_code == 0
    mock_process_requirements.assert_called_once()
    args, kwargs = mock_process_requirements.call_args
    assert kwargs["output_dir"] == Path("my_docs")
    assert kwargs["max_crawl_pages"] == 200
    assert kwargs["max_crawl_depth"] == 2
    assert kwargs["chunk_size"] == 1_000_000
    # gemini_api_key default is None if not set in env, or the env value


@patch("src.llm_min.main.process_requirements")
@patch("src.llm_min.main.parse_requirements")
def test_cli_max_crawl_pages_zero(mock_parse_requirements, mock_process_requirements, tmp_path):
    """Test the CLI with --max-crawl-pages set to 0."""
    runner = CliRunner()
    req_file = tmp_path / "requirements.txt"
    req_file.write_text("package1")
    mock_parse_requirements.return_value = {"package1"}

    result = runner.invoke(cli, ["--requirements-file", str(req_file), "--max-crawl-pages", "0"])

    assert result.exit_code == 0
    mock_process_requirements.assert_called_once()
    args, kwargs = mock_process_requirements.call_args
    assert kwargs["max_crawl_pages"] is None  # 0 should be converted to None by the callback


# Test file writing functions
@patch("src.llm_min.main.logger")
def test_write_full_text_file(mock_logger, tmp_path):
    """Test writing full text content to a file."""
    output_dir = tmp_path / "output"
    package_name = "test_package"
    content = "This is the full text content."

    write_full_text_file(output_dir, package_name, content)

    file_path = output_dir / package_name / "llm-full.txt"
    assert file_path.is_file()
    assert file_path.read_text() == content
    mock_logger.info.assert_called_with(f"Successfully wrote full text content for {package_name} to {file_path}")


@patch("src.llm_min.main.logger")
def test_write_min_text_file(mock_logger, tmp_path):
    """Test writing minimal text content to a file."""
    output_dir = tmp_path / "output"
    package_name = "test_package"
    content = "This is the minimal text content."

    write_min_text_file(output_dir, package_name, content)

    file_path = output_dir / package_name / "llm-min.txt"
    assert file_path.is_file()
    assert file_path.read_text() == content
    mock_logger.info.assert_called_with(f"Successfully wrote minimal text content for {package_name} to {file_path}")


# Test process_package function
@pytest.mark.asyncio
@patch("src.llm_min.main.write_min_text_file")
@patch("src.llm_min.main.write_full_text_file")
@patch("src.llm_min.main.compact_content_with_llm")
@patch("src.llm_min.main.crawl_documentation")
@patch("src.llm_min.main.find_documentation_url")
@patch("src.llm_min.main.logger")
async def test_process_package_success(
    mock_logger,
    mock_find_documentation_url,
    mock_crawl_documentation,
    mock_compact_content_with_llm,
    mock_write_full,
    mock_write_min,
    tmp_path,
):
    """Test successful processing of a single package."""
    package_name = "test_package"
    output_dir = tmp_path / "output"
    doc_url = "http://example.com/docs/test_package"
    crawled_content = "Full documentation content."
    compacted_content = "Minimal documentation content."

    mock_find_documentation_url.return_value = doc_url
    mock_crawl_documentation.return_value = crawled_content
    mock_compact_content_with_llm.return_value = compacted_content

    result = await process_package(
        package_name=package_name,
        output_dir=output_dir,
        max_crawl_pages=10,
        max_crawl_depth=2,
        chunk_size=1000,
        gemini_api_key="fake_key",
    )

    assert result is True
    mock_find_documentation_url.assert_called_once_with(package_name, api_key="fake_key")
    mock_crawl_documentation.assert_called_once_with(doc_url, max_pages=10, max_depth=2)
    mock_write_full.assert_called_once_with(output_dir, package_name, crawled_content)
    mock_compact_content_with_llm.assert_called_once_with(
        aggregated_content=crawled_content,
        chunk_size=1000,
        api_key="fake_key",
        subject=package_name,
    )
    mock_write_min.assert_called_once_with(output_dir, package_name, compacted_content)
    mock_logger.info.assert_any_call(f"--- Processing package: {package_name} ---")
    mock_logger.info.assert_any_call(f"Found documentation URL for {package_name}: {doc_url}")
    mock_logger.info.assert_any_call(
        f"Successfully crawled content for {package_name}. Total size: {len(crawled_content)} characters."
    )
    mock_logger.info.assert_any_call(f"Compacting content for {package_name}...")
    mock_logger.info.assert_any_call(
        f"Successfully compacted content for {package_name}. Compacted size: {len(compacted_content)} characters."
    )
    mock_logger.info.assert_any_call(f"Finished processing package: {package_name}")


@pytest.mark.asyncio
@patch("src.llm_min.main.write_min_text_file")
@patch("src.llm_min.main.write_full_text_file")
@patch("src.llm_min.main.compact_content_with_llm")
@patch("src.llm_min.main.crawl_documentation")
@patch("src.llm_min.main.find_documentation_url")
@patch("src.llm_min.main.logger")
async def test_process_package_no_doc_url(
    mock_logger,
    mock_find_documentation_url,
    mock_crawl_documentation,
    mock_compact_content_with_llm,
    mock_write_full,
    mock_write_min,
    tmp_path,
):
    """Test processing a package when no doc URL is found."""
    package_name = "test_package"
    output_dir = tmp_path / "output"

    mock_find_documentation_url.return_value = None

    result = await process_package(
        package_name=package_name,
        output_dir=output_dir,
        max_crawl_pages=10,
        max_crawl_depth=2,
        chunk_size=1000,
        gemini_api_key="fake_key",
    )

    assert result is False
    mock_find_documentation_url.assert_called_once_with(package_name, api_key="fake_key")
    mock_crawl_documentation.assert_not_called()
    mock_write_full.assert_not_called()
    mock_compact_content_with_llm.assert_not_called()
    mock_write_min.assert_not_called()
    mock_logger.warning.assert_called_once_with(f"Could not find documentation URL for {package_name}. Skipping.")


@pytest.mark.asyncio
@patch("src.llm_min.main.write_min_text_file")
@patch("src.llm_min.main.write_full_text_file")
@patch("src.llm_min.main.compact_content_with_llm")
@patch("src.llm_min.main.crawl_documentation")
@patch("src.llm_min.main.find_documentation_url")
@patch("src.llm_min.main.logger")
async def test_process_package_no_crawled_content(
    mock_logger,
    mock_find_documentation_url,
    mock_crawl_documentation,
    mock_compact_content_with_llm,
    mock_write_full,
    mock_write_min,
    tmp_path,
):
    """Test processing a package when no content is crawled."""
    package_name = "test_package"
    output_dir = tmp_path / "output"
    doc_url = "http://example.com/docs/test_package"

    mock_find_documentation_url.return_value = doc_url
    mock_crawl_documentation.return_value = ""  # No crawled content

    result = await process_package(
        package_name=package_name,
        output_dir=output_dir,
        max_crawl_pages=10,
        max_crawl_depth=2,
        chunk_size=1000,
        gemini_api_key="fake_key",
    )

    assert result is False
    mock_find_documentation_url.assert_called_once_with(package_name, api_key="fake_key")
    mock_crawl_documentation.assert_called_once_with(doc_url, max_pages=10, max_depth=2)
    mock_write_full.assert_not_called()  # Should not write full file if no content
    mock_compact_content_with_llm.assert_not_called()
    mock_write_min.assert_not_called()
    mock_logger.warning.assert_called_once_with(f"No content crawled for {package_name}. Skipping.")


@pytest.mark.asyncio
@patch("src.llm_min.main.write_min_text_file")
@patch("src.llm_min.main.write_full_text_file")
@patch("src.llm_min.main.compact_content_with_llm")
@patch("src.llm_min.main.crawl_documentation")
@patch("src.llm_min.main.find_documentation_url")
@patch("src.llm_min.main.logger")
async def test_process_package_compaction_empty(
    mock_logger,
    mock_find_documentation_url,
    mock_crawl_documentation,
    mock_compact_content_with_llm,
    mock_write_full,
    mock_write_min,
    tmp_path,
):
    """Test processing a package when compaction results in empty content."""
    package_name = "test_package"
    output_dir = tmp_path / "output"
    doc_url = "http://example.com/docs/test_package"
    crawled_content = "Full documentation content."

    mock_find_documentation_url.return_value = doc_url
    mock_crawl_documentation.return_value = crawled_content
    mock_compact_content_with_llm.return_value = ""  # Empty compacted content

    result = await process_package(
        package_name=package_name,
        output_dir=output_dir,
        max_crawl_pages=10,
        max_crawl_depth=2,
        chunk_size=1000,
        gemini_api_key="fake_key",
    )

    assert result is False
    mock_find_documentation_url.assert_called_once_with(package_name, api_key="fake_key")
    mock_crawl_documentation.assert_called_once_with(doc_url, max_pages=10, max_depth=2)
    mock_write_full.assert_called_once_with(
        output_dir, package_name, crawled_content
    )  # Full file should still be written
    mock_compact_content_with_llm.assert_called_once_with(
        aggregated_content=crawled_content,
        chunk_size=1000,
        api_key="fake_key",
        subject=package_name,
    )
    mock_write_min.assert_not_called()  # Should not write min file if compaction is empty
    mock_logger.warning.assert_called_once_with(
        f"Compaction resulted in empty content for {package_name}. Skipping writing min file."
    )


@pytest.mark.asyncio
@patch("src.llm_min.main.write_min_text_file")
@patch("src.llm_min.main.write_full_text_file")
@patch("src.llm_min.main.compact_content_with_llm")
@patch("src.llm_min.main.crawl_documentation")
@patch("src.llm_min.main.find_documentation_url")
@patch("src.llm_min.main.logger")
async def test_process_package_exception(
    mock_logger,
    mock_find_documentation_url,
    mock_crawl_documentation,
    mock_compact_content_with_llm,
    mock_write_full,
    mock_write_min,
    tmp_path,
):
    """Test processing a package when an exception occurs."""
    package_name = "test_package"
    output_dir = tmp_path / "output"

    mock_find_documentation_url.side_effect = Exception("Search failed")

    result = await process_package(
        package_name=package_name,
        output_dir=output_dir,
        max_crawl_pages=10,
        max_crawl_depth=2,
        chunk_size=1000,
        gemini_api_key="fake_key",
    )

    assert result is False
    mock_find_documentation_url.assert_called_once_with(package_name, api_key="fake_key")
    mock_crawl_documentation.assert_not_called()
    mock_write_full.assert_not_called()
    mock_compact_content_with_llm.assert_not_called()
    mock_write_min.assert_not_called()
    mock_logger.error.assert_called_once()  # Check if error was logged


# Test process_direct_url function
@pytest.mark.asyncio
@patch("src.llm_min.main.write_min_text_file")
@patch("src.llm_min.main.write_full_text_file")
@patch("src.llm_min.main.compact_content_with_llm")
@patch("src.llm_min.main.crawl_documentation")
@patch("src.llm_min.main.logger")
async def test_process_direct_url_success(
    mock_logger,
    mock_crawl_documentation,
    mock_compact_content_with_llm,
    mock_write_full,
    mock_write_min,
    tmp_path,
):
    """Test successful processing of a direct URL."""
    package_name = "crawled_doc"
    doc_url = "http://example.com/direct/docs"
    output_dir = tmp_path / "output"
    crawled_content = "Full documentation content from direct URL."
    compacted_content = "Minimal documentation content from direct URL."

    mock_crawl_documentation.return_value = crawled_content
    mock_compact_content_with_llm.return_value = compacted_content

    result = await process_direct_url(
        package_name=package_name,
        doc_url=doc_url,
        output_dir=output_dir,
        max_crawl_pages=10,
        max_crawl_depth=2,
        chunk_size=1000,
        gemini_api_key="fake_key",
    )

    assert result is True
    mock_crawl_documentation.assert_called_once_with(doc_url, max_pages=10, max_depth=2)
    mock_write_full.assert_called_once_with(output_dir, package_name, crawled_content)
    mock_compact_content_with_llm.assert_called_once_with(
        aggregated_content=crawled_content,
        chunk_size=1000,
        api_key="fake_key",
        subject=package_name,
    )
    mock_write_min.assert_called_once_with(output_dir, package_name, compacted_content)
    mock_logger.info.assert_any_call(f"--- Processing direct URL for {package_name}: {doc_url} ---")
    mock_logger.info.assert_any_call(
        f"Successfully crawled content from {doc_url}. Total size: {len(crawled_content)} characters."
    )
    mock_logger.info.assert_any_call(f"Compacting content for {package_name}...")
    mock_logger.info.assert_any_call(
        f"Successfully compacted content for {package_name}. Compacted size: {len(compacted_content)} characters."
    )
    mock_logger.info.assert_any_call(f"Finished processing direct URL: {doc_url}")


@pytest.mark.asyncio
@patch("src.llm_min.main.write_min_text_file")
@patch("src.llm_min.main.write_full_text_file")
@patch("src.llm_min.main.compact_content_with_llm")
@patch("src.llm_min.main.crawl_documentation")
@patch("src.llm_min.main.logger")
async def test_process_direct_url_no_crawled_content(
    mock_logger,
    mock_crawl_documentation,
    mock_compact_content_with_llm,
    mock_write_full,
    mock_write_min,
    tmp_path,
):
    """Test processing a direct URL when no content is crawled."""
    package_name = "crawled_doc"
    doc_url = "http://example.com/direct/docs"
    output_dir = tmp_path / "output"

    mock_crawl_documentation.return_value = ""  # No crawled content

    result = await process_direct_url(
        package_name=package_name,
        doc_url=doc_url,
        output_dir=output_dir,
        max_crawl_pages=10,
        max_crawl_depth=2,
        chunk_size=1000,
        gemini_api_key="fake_key",
    )

    assert result is False
    mock_crawl_documentation.assert_called_once_with(doc_url, max_pages=10, max_depth=2)
    mock_write_full.assert_not_called()
    mock_compact_content_with_llm.assert_not_called()
    mock_write_min.assert_not_called()
    mock_logger.warning.assert_called_once_with(f"No content crawled from {doc_url}. Skipping.")


@pytest.mark.asyncio
@patch("src.llm_min.main.write_min_text_file")
@patch("src.llm_min.main.write_full_text_file")
@patch("src.llm_min.main.compact_content_with_llm")
@patch("src.llm_min.main.crawl_documentation")
@patch("src.llm_min.main.logger")
async def test_process_direct_url_compaction_empty(
    mock_logger,
    mock_crawl_documentation,
    mock_compact_content_with_llm,
    mock_write_full,
    mock_write_min,
    tmp_path,
):
    """Test processing a direct URL when compaction results in empty content."""
    package_name = "crawled_doc"
    doc_url = "http://example.com/direct/docs"
    output_dir = tmp_path / "output"
    crawled_content = "Full documentation content from direct URL."

    mock_crawl_documentation.return_value = crawled_content
    mock_compact_content_with_llm.return_value = ""  # Empty compacted content

    result = await process_direct_url(
        package_name=package_name,
        doc_url=doc_url,
        output_dir=output_dir,
        max_crawl_pages=10,
        max_crawl_depth=2,
        chunk_size=1000,
        gemini_api_key="fake_key",
    )

    assert result is False
    mock_crawl_documentation.assert_called_once_with(doc_url, max_pages=10, max_depth=2)
    mock_write_full.assert_called_once_with(output_dir, package_name, crawled_content)
    mock_compact_content_with_llm.assert_called_once_with(
        aggregated_content=crawled_content,
        chunk_size=1000,
        api_key="fake_key",
        subject=package_name,
    )
    mock_write_min.assert_not_called()
    mock_logger.warning.assert_called_once_with(
        f"Compaction resulted in empty content for {package_name}. Skipping writing min file."
    )


@pytest.mark.asyncio
@patch("src.llm_min.main.write_min_text_file")
@patch("src.llm_min.main.write_full_text_file")
@patch("src.llm_min.main.compact_content_with_llm")
@patch("src.llm_min.main.crawl_documentation")
@patch("src.llm_min.main.logger")
async def test_process_direct_url_exception(
    mock_logger,
    mock_crawl_documentation,
    mock_compact_content_with_llm,
    mock_write_full,
    mock_write_min,
    tmp_path,
):
    """Test processing a direct URL when an exception occurs."""
    package_name = "crawled_doc"
    doc_url = "http://example.com/direct/docs"
    output_dir = tmp_path / "output"

    mock_crawl_documentation.side_effect = Exception("Crawl failed")

    result = await process_direct_url(
        package_name=package_name,
        doc_url=doc_url,
        output_dir=output_dir,
        max_crawl_pages=10,
        max_crawl_depth=2,
        chunk_size=1000,
        gemini_api_key="fake_key",
    )

    assert result is False
    mock_crawl_documentation.assert_called_once_with(doc_url, max_pages=10, max_depth=2)
    mock_write_full.assert_not_called()
    mock_compact_content_with_llm.assert_not_called()
    mock_write_min.assert_not_called()
    mock_logger.error.assert_called_once()  # Check if error was logged


# Test process_requirements function
@pytest.mark.asyncio
@patch("src.llm_min.main.process_package")
@patch("src.llm_min.main.logger")
async def test_process_requirements_success(mock_logger, mock_process_package, tmp_path):
    """Test successful processing of multiple packages."""
    packages = {"package1", "package2"}
    output_dir = tmp_path / "output"

    # Mock process_package to return True for success
    mock_process_package.return_value = True

    await process_requirements(
        packages=packages,
        output_dir=output_dir,
        max_crawl_pages=10,
        max_crawl_depth=2,
        chunk_size=1000,
        gemini_api_key="fake_key",
    )

    assert mock_process_package.call_count == len(packages)
    # Check if process_package was called for each package with correct args
    calls = mock_process_package.call_args_list
    called_packages = {call[1]["package_name"] for call in calls}
    assert called_packages == packages
    for call in calls:
        kwargs = call[1]
        assert kwargs["output_dir"] == output_dir
        assert kwargs["max_crawl_pages"] == 10
        assert kwargs["max_crawl_depth"] == 2
        assert kwargs["chunk_size"] == 1000
        assert kwargs["gemini_api_key"] == "fake_key"


@pytest.mark.asyncio
@patch("src.llm_min.main.process_package")
@patch("src.llm_min.main.logger")
async def test_process_requirements_empty_list(mock_logger, mock_process_package, tmp_path):
    """Test processing an empty list of packages."""
    packages: set[str] = set()
    output_dir = tmp_path / "output"

    with pytest.raises(SystemExit) as excinfo:
        await process_requirements(
            packages=packages,
            output_dir=output_dir,
            max_crawl_pages=10,
            max_crawl_depth=2,
            chunk_size=1000,
            gemini_api_key="fake_key",
        )

    assert excinfo.value.code == 0  # Should exit with code 0
    mock_logger.warning.assert_called_once_with("No packages provided for processing. Exiting.")
    mock_process_package.assert_not_called()


@pytest.mark.asyncio
@patch("src.llm_min.main.process_package")
@patch("src.llm_min.main.logger")
async def test_process_requirements_partial_failure(mock_logger, mock_process_package, tmp_path):
    """Test processing multiple packages with partial failures."""
    packages = {"package1", "package2", "package3"}
    output_dir = tmp_path / "output"

    # Mock process_package to fail for package2
    def side_effect(package_name, **kwargs):
        if package_name == "package2":
            return False
        return True

    mock_process_package.side_effect = side_effect

    await process_requirements(
        packages=packages,
        output_dir=output_dir,
        max_crawl_pages=10,
        max_crawl_depth=2,
        chunk_size=1000,
        gemini_api_key="fake_key",
    )

    assert mock_process_package.call_count == len(packages)
    # Check if process_package was called for each package
    called_packages = {call[1]["package_name"] for call in mock_process_package.call_args_list}
    assert called_packages == packages
    # No specific assertion needed for return value here, as gather handles exceptions


# Test URL inference for --doc-url
def test_cli_doc_url_url_inference():
    """Test URL inference for package name with --doc-url."""
    runner = CliRunner()

    # Test with path parts
    result = runner.invoke(cli, ["--doc-url", "https://docs.python.org/3/library/os.html"])
    assert result.exit_code == 0
    # Check if 'os.html' or similar was inferred and passed to process_direct_url (requires mocking process_direct_url)

    # Test with domain only
    result = runner.invoke(cli, ["--doc-url", "https://requests.readthedocs.io/"])
    assert result.exit_code == 0
    # Check if 'requests' or similar was inferred and passed to process_direct_url (requires mocking process_direct_url)

    # Test with no path or domain parts (should use default)
    result = runner.invoke(cli, ["--doc-url", "http://localhost"])
    assert result.exit_code == 0
    # Check if 'crawled_doc' was inferred and passed to process_direct_url (requires mocking process_direct_url)


# Add mocks for process_direct_url to check inferred package name
@patch("src.llm_min.main.process_direct_url")
def test_cli_doc_url_url_inference_mocked(mock_process_direct_url):
    """Test URL inference for package name with --doc-url using mock."""
    runner = CliRunner()

    # Test with path parts
    runner.invoke(cli, ["--doc-url", "https://docs.python.org/3/library/os.html"])
    args, kwargs = mock_process_direct_url.call_args
    assert kwargs["package_name"] == "3.library.os.html"  # Check inferred name

    # Test with domain only
    mock_process_direct_url.reset_mock()
    runner.invoke(cli, ["--doc-url", "https://requests.readthedocs.io/"])
    args, kwargs = mock_process_direct_url.call_args
    assert kwargs["package_name"] == "requests"  # Check inferred name

    # Test with no path or domain parts (should use default)
    mock_process_direct_url.reset_mock()
    runner.invoke(cli, ["--doc-url", "http://localhost"])
    args, kwargs = mock_process_direct_url.call_args
    assert kwargs["package_name"] == "crawled_doc"  # Check inferred name

    # Test with complex URL
    mock_process_direct_url.reset_mock()
    runner.invoke(cli, ["--doc-url", "https://example.com/path/to/docs/v1.2/index.html"])
    args, kwargs = mock_process_direct_url.call_args
    assert kwargs["package_name"] == "path.to.docs.v1.2.index.html"  # Check inferred name


# Test GEMINI_API_KEY environment variable
@patch.dict(os.environ, {"GEMINI_API_KEY": "env_fake_key"})
@patch("src.llm_min.main.process_requirements")
@patch("src.llm_min.main.parse_requirements")
def test_cli_gemini_api_key_env(mock_parse_requirements, mock_process_requirements, tmp_path):
    """Test GEMINI_API_KEY is picked up from environment variable."""
    runner = CliRunner()
    req_file = tmp_path / "requirements.txt"
    req_file.write_text("package1")
    mock_parse_requirements.return_value = {"package1"}

    result = runner.invoke(cli, ["--requirements-file", str(req_file)])

    assert result.exit_code == 0
    mock_process_requirements.assert_called_once()
    args, kwargs = mock_process_requirements.call_args
    assert kwargs["gemini_api_key"] == "env_fake_key"


# Test --gemini-api-key command line argument overrides environment variable
@patch.dict(os.environ, {"GEMINI_API_KEY": "env_fake_key"})
@patch("src.llm_min.main.process_requirements")
@patch("src.llm_min.main.parse_requirements")
def test_cli_gemini_api_key_override(mock_parse_requirements, mock_process_requirements, tmp_path):
    """Test --gemini-api-key argument overrides environment variable."""
    runner = CliRunner()
    req_file = tmp_path / "requirements.txt"
    req_file.write_text("package1")
    mock_parse_requirements.return_value = {"package1"}

    result = runner.invoke(cli, ["--requirements-file", str(req_file), "--gemini-api-key", "cli_fake_key"])

    assert result.exit_code == 0
    mock_process_requirements.assert_called_once()
    args, kwargs = mock_process_requirements.call_args
    assert kwargs["gemini_api_key"] == "cli_fake_key"


# Test --gemini-api-key command line argument without environment variable
@patch.dict(os.environ, {}, clear=True)  # Clear environment variables
@patch("src.llm_min.main.process_requirements")
@patch("src.llm_min.main.parse_requirements")
def test_cli_gemini_api_key_cli_only(mock_parse_requirements, mock_process_requirements, tmp_path):
    """Test --gemini-api-key argument when environment variable is not set."""
    runner = CliRunner()
    req_file = tmp_path / "requirements.txt"
    req_file.write_text("package1")
    mock_parse_requirements.return_value = {"package1"}

    result = runner.invoke(cli, ["--requirements-file", str(req_file), "--gemini-api-key", "cli_fake_key"])

    assert result.exit_code == 0
    mock_process_requirements.assert_called_once()
    args, kwargs = mock_process_requirements.call_args
    assert kwargs["gemini_api_key"] == "cli_fake_key"


# Test no GEMINI_API_KEY provided (neither env nor cli)
@patch.dict(os.environ, {}, clear=True)  # Clear environment variables
@patch("src.llm_min.main.process_requirements")
@patch("src.llm_min.main.parse_requirements")
def test_cli_no_gemini_api_key(mock_parse_requirements, mock_process_requirements, tmp_path):
    """Test no GEMINI_API_KEY is passed when neither env nor cli arg is provided."""
    runner = CliRunner()
    req_file = tmp_path / "requirements.txt"
    req_file.write_text("package1")
    mock_parse_requirements.return_value = {"package1"}

    result = runner.invoke(cli, ["--requirements-file", str(req_file)])

    assert result.exit_code == 0
    mock_process_requirements.assert_called_once()
    args, kwargs = mock_process_requirements.call_args
    assert kwargs["gemini_api_key"] is None


# Test output directory creation
@patch("src.llm_min.main.process_requirements")
@patch("src.llm_min.main.parse_requirements")
def test_cli_output_dir_creation(mock_parse_requirements, mock_process_requirements, tmp_path):
    """Test that the output directory is created if it doesn't exist."""
    runner = CliRunner()
    req_file = tmp_path / "requirements.txt"
    req_file.write_text("package1")
    mock_parse_requirements.return_value = {"package1"}
    output_dir = tmp_path / "non_existent_output"

    assert not output_dir.exists()

    result = runner.invoke(cli, ["--requirements-file", str(req_file), "--output-dir", str(output_dir)])

    assert result.exit_code == 0
    assert output_dir.is_dir()
    mock_process_requirements.assert_called_once()
    args, kwargs = mock_process_requirements.call_args
    assert kwargs["output_dir"] == output_dir


# Test output directory creation with existing directory
@patch("src.llm_min.main.process_requirements")
@patch("src.llm_min.main.parse_requirements")
def test_cli_output_dir_exists(mock_parse_requirements, mock_process_requirements, tmp_path):
    """Test that the output directory is not recreated if it already exists."""
    runner = CliRunner()
    req_file = tmp_path / "requirements.txt"
    req_file.write_text("package1")
    mock_parse_requirements.return_value = {"package1"}
    output_dir = tmp_path / "existing_output"
    output_dir.mkdir()

    assert output_dir.is_dir()

    result = runner.invoke(cli, ["--requirements-file", str(req_file), "--output-dir", str(output_dir)])

    assert result.exit_code == 0
    assert output_dir.is_dir()  # Still exists
    mock_process_requirements.assert_called_once()
    args, kwargs = mock_process_requirements.call_args
    assert kwargs["output_dir"] == output_dir


# Test input_folder validation (no requirements.txt)
@patch("src.llm_min.main.process_requirements")
@patch("src.llm_min.main.parse_requirements")
def test_cli_input_folder_no_requirements_file(mock_parse_requirements, mock_process_requirements, tmp_path):
    """Test --input-folder validation when no requirements.txt is found."""
    runner = CliRunner()
    input_folder = tmp_path / "my_project_empty"
    input_folder.mkdir()

    result = runner.invoke(cli, ["--input-folder", str(input_folder)])

    assert result.exit_code != 0
    assert f"Error: Could not find requirements.txt in folder: {input_folder}" in result.output
    mock_parse_requirements.assert_not_called()
    mock_process_requirements.assert_not_called()


# Test requirements_file validation (does not exist)
@patch("src.llm_min.main.process_requirements")
@patch("src.llm_min.main.parse_requirements")
def test_cli_requirements_file_not_exists(mock_parse_requirements, mock_process_requirements, tmp_path):
    """Test --requirements-file validation when the file does not exist."""
    runner = CliRunner()
    req_file = tmp_path / "non_existent_requirements.txt"

    assert not req_file.exists()

    result = runner.invoke(cli, ["--requirements-file", str(req_file)])

    assert result.exit_code != 0
    # Typer handles the "exists=True" validation, so the error message comes from Typer
    assert (
        'Path "non_existent_requirements.txt" does not exist' in result.output
        or "file not found" in result.output.lower()
    )
    mock_parse_requirements.assert_not_called()
    mock_process_requirements.assert_not_called()


# Test requirements_file validation (is a directory)
@patch("src.llm_min.main.process_requirements")
@patch("src.llm_min.main.parse_requirements")
def test_cli_requirements_file_is_dir(mock_parse_requirements, mock_process_requirements, tmp_path):
    """Test --requirements-file validation when the path is a directory."""
    runner = CliRunner()
    req_file = tmp_path / "my_directory"
    req_file.mkdir()

    assert req_file.is_dir()

    result = runner.invoke(cli, ["--requirements-file", str(req_file)])

    assert result.exit_code != 0
    # Typer handles the "file_okay=True, dir_okay=False" validation
    assert 'Path "my_directory" is a directory' in result.output
    mock_parse_requirements.assert_not_called()
    mock_process_requirements.assert_not_called()


# Test input_folder validation (is a file)
@patch("src.llm_min.main.process_requirements")
@patch("src.llm_min.main.parse_requirements")
def test_cli_input_folder_is_file(mock_parse_requirements, mock_process_requirements, tmp_path):
    """Test --input-folder validation when the path is a file."""
    runner = CliRunner()
    input_folder = tmp_path / "my_file.txt"
    input_folder.write_text("content")

    assert input_folder.is_file()

    result = runner.invoke(cli, ["--input-folder", str(input_folder)])

    assert result.exit_code != 0
    # Typer handles the "file_okay=False, dir_okay=True" validation
    assert 'Path "my_file.txt" is a file' in result.output
    mock_parse_requirements.assert_not_called()
    mock_process_requirements.assert_not_called()


# Test main execution block
@patch("src.llm_min.main.app")
def test_main_execution_block(mock_app):
    """Test that app() is called when the script is run directly."""
    # This test is a bit tricky as it tests the __main__ block.
    # We can simulate running the script directly by checking if app() is called.
    # This requires temporarily modifying sys.modules or using a helper script,
    # but a simpler approach for this context is to just check if the app.command()
    # decorator is used correctly, which the previous tests implicitly do.
    # However, to explicitly test the `if __name__ == "__main__": app()` part,
    # we can use a technique to simulate the script being run directly.

    # Save the original __name__
    original_name = __name__
    # Temporarily set __name__ to "__main__"
    with patch("src.llm_min.main.__name__", "__main__"):
        # Reload the module to trigger the __main__ block
        import importlib

        importlib.reload(sys.modules["src.llm_min.main"])

        # Check if app() was called
        mock_app.assert_called_once()

    # Restore the original __name__
    with patch("src.llm_min.main.__name__", original_name):
        import importlib

        importlib.reload(sys.modules["src.llm_min.main"])


# Test logging configuration (basic check)
@patch("src.llm_min.main.logging.basicConfig")
@patch("src.llm_min.main.logging.getLogger")
def test_logging_config(mock_getLogger, mock_basicConfig):
    """Test that logging is configured."""
    # This is implicitly tested by other tests that use the logger,
    # but we can add a direct check for basicConfig call.
    # Since logging is configured at import time, we need to reload the module.
    import importlib

    importlib.reload(sys.modules["src.llm_min.main"])

    mock_basicConfig.assert_called_once()
    # Check for specific logger level calls if needed, but basicConfig is the main part.


# Test environment variable loading
@patch("src.llm_min.main.load_dotenv")
def test_load_dotenv_called(mock_load_dotenv):
    """Test that load_dotenv is called."""
    # load_dotenv is called at import time, so we need to reload the module.
    import importlib

    importlib.reload(sys.modules["src.llm_min.main"])

    mock_load_dotenv.assert_called_once()


# Test process_requirements with no packages (should exit)
@pytest.mark.asyncio
@patch("src.llm_min.main.logger")
async def test_process_requirements_no_packages(mock_logger, tmp_path):
    """Test process_requirements exits when no packages are provided."""
    output_dir = tmp_path / "output"
    packages: set[str] = set()

    with pytest.raises(SystemExit) as excinfo:
        await process_requirements(
            packages=packages,
            output_dir=output_dir,
            max_crawl_pages=10,
            max_crawl_depth=2,
            chunk_size=1000,
            gemini_api_key="fake_key",
        )

    assert excinfo.value.code == 0
    mock_logger.warning.assert_called_once_with("No packages provided for processing. Exiting.")


# Test process_direct_url with URL inference edge cases
@patch("src.llm_min.main.process_direct_url")
def test_cli_doc_url_url_inference_edge_cases_mocked(mock_process_direct_url):
    """Test URL inference for package name with --doc-url edge cases using mock."""
    runner = CliRunner()

    # Test with URL having only domain and trailing slash
    mock_process_direct_url.reset_mock()
    runner.invoke(cli, ["--doc-url", "https://example.com/"])
    args, kwargs = mock_process_direct_url.call_args
    assert kwargs["package_name"] == "example"  # Should use domain

    # Test with URL having only domain (no slash)
    mock_process_direct_url.reset_mock()
    runner.invoke(cli, ["--doc-url", "https://example.com"])
    args, kwargs = mock_process_direct_url.call_args
    assert kwargs["package_name"] == "example"  # Should use domain

    # Test with URL having only path (no domain - unlikely but test)
    mock_process_direct_url.reset_mock()
    runner.invoke(cli, ["--doc-url", "/path/to/docs"])
    args, kwargs = mock_process_direct_url.call_args
    assert kwargs["package_name"] == "path.to.docs"  # Should use path

    # Test with empty URL (should fail Typer validation before reaching inference)
    # This case is handled by Typer's URL validation if applicable, or will likely raise an error.
    # We can skip explicit testing here as Typer handles it.


# Test write_full_text_file exception handling
@patch("src.llm_min.main.logger")
@patch("builtins.open", side_effect=OSError("Disk full"))
def test_write_full_text_file_exception(mock_open, mock_logger, tmp_path):
    """Test exception handling in write_full_text_file."""
    output_dir = tmp_path / "output"
    package_name = "test_package"
    content = "Some content."

    # The function should catch the exception and log it, not re-raise
    write_full_text_file(output_dir, package_name, content)

    mock_logger.error.assert_called_once()
    args, kwargs = mock_logger.error.call_args
    assert f"Failed to write full text file for {package_name}" in args[0]
    assert "Disk full" in str(args[0])
    assert kwargs["exc_info"] is True


# Test write_min_text_file exception handling
@patch("src.llm_min.main.logger")
@patch("builtins.open", side_effect=OSError("Permission denied"))
def test_write_min_text_file_exception(mock_open, mock_logger, tmp_path):
    """Test exception handling in write_min_text_file."""
    output_dir = tmp_path / "output"
    package_name = "test_package"
    content = "Some content."

    # The function should catch the exception and log it, not re-raise
    write_min_text_file(output_dir, package_name, content)

    mock_logger.error.assert_called_once()
    args, kwargs = mock_logger.error.call_args
    assert f"Failed to write minimal text file for {package_name}" in args[0]
    assert "Permission denied" in str(args[0])
    assert kwargs["exc_info"] is True


# Test process_package with write_full_text_file failure
@pytest.mark.asyncio
@patch("src.llm_min.main.write_min_text_file")
@patch("src.llm_min.main.write_full_text_file", side_effect=Exception("Write full failed"))
@patch("src.llm_min.main.compact_content_with_llm")
@patch("src.llm_min.main.crawl_documentation")
@patch("src.llm_min.main.find_documentation_url")
@patch("src.llm_min.main.logger")
async def test_process_package_write_full_failure(
    mock_logger,
    mock_find_documentation_url,
    mock_crawl_documentation,
    mock_compact_content_with_llm,
    mock_write_full,
    mock_write_min,
    tmp_path,
):
    """Test process_package continues if write_full_text_file fails."""
    package_name = "test_package"
    output_dir = tmp_path / "output"
    doc_url = "http://example.com/docs/test_package"
    crawled_content = "Full documentation content."
    compacted_content = "Minimal documentation content."

    mock_find_documentation_url.return_value = doc_url
    mock_crawl_documentation.return_value = crawled_content
    mock_compact_content_with_llm.return_value = compacted_content

    result = await process_package(
        package_name=package_name,
        output_dir=output_dir,
        max_crawl_pages=10,
        max_crawl_depth=2,
        chunk_size=1000,
        gemini_api_key="fake_key",
    )

    assert result is True  # Process should still succeed overall
    mock_find_documentation_url.assert_called_once_with(package_name, api_key="fake_key")
    mock_crawl_documentation.assert_called_once_with(doc_url, max_pages=10, max_depth=2)
    mock_write_full.assert_called_once_with(output_dir, package_name, crawled_content)
    mock_compact_content_with_llm.assert_called_once_with(
        aggregated_content=crawled_content,
        chunk_size=1000,
        api_key="fake_key",
        subject=package_name,
    )
    mock_write_min.assert_called_once_with(output_dir, package_name, compacted_content)
    mock_logger.error.assert_called_once()  # Check if write_full error was logged


# Test process_package with write_min_text_file failure
@pytest.mark.asyncio
@patch("src.llm_min.main.write_min_text_file", side_effect=Exception("Write min failed"))
@patch("src.llm_min.main.write_full_text_file")
@patch("src.llm_min.main.compact_content_with_llm")
@patch("src.llm_min.main.crawl_documentation")
@patch("src.llm_min.main.find_documentation_url")
@patch("src.llm_min.main.logger")
async def test_process_package_write_min_failure(
    mock_logger,
    mock_find_documentation_url,
    mock_crawl_documentation,
    mock_compact_content_with_llm,
    mock_write_full,
    mock_write_min,
    tmp_path,
):
    """Test process_package continues if write_min_text_file fails."""
    package_name = "test_package"
    output_dir = tmp_path / "output"
    doc_url = "http://example.com/docs/test_package"
    crawled_content = "Full documentation content."
    compacted_content = "Minimal documentation content."

    mock_find_documentation_url.return_value = doc_url
    mock_crawl_documentation.return_value = crawled_content
    mock_compact_content_with_llm.return_value = compacted_content

    result = await process_package(
        package_name=package_name,
        output_dir=output_dir,
        max_crawl_pages=10,
        max_crawl_depth=2,
        chunk_size=1000,
        gemini_api_key="fake_key",
    )

    assert result is True  # Process should still succeed overall
    mock_find_documentation_url.assert_called_once_with(package_name, api_key="fake_key")
    mock_crawl_documentation.assert_called_once_with(doc_url, max_pages=10, max_depth=2)
    mock_write_full.assert_called_once_with(output_dir, package_name, crawled_content)
    mock_compact_content_with_llm.assert_called_once_with(
        aggregated_content=crawled_content,
        chunk_size=1000,
        api_key="fake_key",
        subject=package_name,
    )
    mock_write_min.assert_called_once_with(output_dir, package_name, compacted_content)
    mock_logger.error.assert_called_once()  # Check if write_min error was logged


# Test process_direct_url with write_full_text_file failure
@pytest.mark.asyncio
@patch("src.llm_min.main.write_min_text_file")
@patch("src.llm_min.main.write_full_text_file", side_effect=Exception("Write full failed"))
@patch("src.llm_min.main.compact_content_with_llm")
@patch("src.llm_min.main.crawl_documentation")
@patch("src.llm_min.main.logger")
async def test_process_direct_url_write_full_failure(
    mock_logger,
    mock_crawl_documentation,
    mock_compact_content_with_llm,
    mock_write_full,
    mock_write_min,
    tmp_path,
):
    """Test process_direct_url continues if write_full_text_file fails."""
    package_name = "crawled_doc"
    doc_url = "http://example.com/direct/docs"
    output_dir = tmp_path / "output"
    crawled_content = "Full documentation content from direct URL."
    compacted_content = "Minimal documentation content from direct URL."

    mock_crawl_documentation.return_value = crawled_content
    mock_compact_content_with_llm.return_value = compacted_content

    result = await process_direct_url(
        package_name=package_name,
        doc_url=doc_url,
        output_dir=output_dir,
        max_crawl_pages=10,
        max_crawl_depth=2,
        chunk_size=1000,
        gemini_api_key="fake_key",
    )

    assert result is True  # Process should still succeed overall
    mock_crawl_documentation.assert_called_once_with(doc_url, max_pages=10, max_depth=2)
    mock_write_full.assert_called_once_with(output_dir, package_name, crawled_content)
    mock_compact_content_with_llm.assert_called_once_with(
        aggregated_content=crawled_content,
        chunk_size=1000,
        api_key="fake_key",
        subject=package_name,
    )
    mock_write_min.assert_called_once_with(output_dir, package_name, compacted_content)
    mock_logger.error.assert_called_once()  # Check if write_full error was logged


# Test process_direct_url with write_min_text_file failure
@pytest.mark.asyncio
@patch("src.llm_min.main.write_min_text_file", side_effect=Exception("Write min failed"))
@patch("src.llm_min.main.write_full_text_file")
@patch("src.llm_min.main.compact_content_with_llm")
@patch("src.llm_min.main.crawl_documentation")
@patch("src.llm_min.main.logger")
async def test_process_direct_url_write_min_failure(
    mock_logger,
    mock_crawl_documentation,
    mock_compact_content_with_llm,
    mock_write_full,
    mock_write_min,
    tmp_path,
):
    """Test process_direct_url continues if write_min_text_file fails."""
    package_name = "crawled_doc"
    doc_url = "http://example.com/direct/docs"
    output_dir = tmp_path / "output"
    crawled_content = "Full documentation content from direct URL."
    compacted_content = "Minimal documentation content from direct URL."

    mock_crawl_documentation.return_value = crawled_content
    mock_compact_content_with_llm.return_value = compacted_content

    result = await process_direct_url(
        package_name=package_name,
        doc_url=doc_url,
        output_dir=output_dir,
        max_crawl_pages=10,
        max_crawl_depth=2,
        chunk_size=1000,
        gemini_api_key="fake_key",
    )

    assert result is True  # Process should still succeed overall
    mock_crawl_documentation.assert_called_once_with(doc_url, max_pages=10, max_depth=2)
    mock_write_full.assert_called_once_with(output_dir, package_name, crawled_content)
    mock_compact_content_with_llm.assert_called_once_with(
        aggregated_content=crawled_content,
        chunk_size=1000,
        api_key="fake_key",
        subject=package_name,
    )
    mock_write_min.assert_called_once_with(output_dir, package_name, compacted_content)
    mock_logger.error.assert_called_once()  # Check if write_min error was logged
