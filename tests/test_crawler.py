from unittest.mock import MagicMock, patch

import pytest
from crawl4ai import CrawlerRunConfig, CrawlResult

from llm_min.crawler import crawl_documentation


@pytest.mark.asyncio
# Patch AsyncWebCrawler itself for more control
@patch("llm_min.crawler.AsyncWebCrawler")
async def test_crawl_documentation_success(MockAsyncWebCrawler):
    """Test successful crawl."""
    # --- Mock Setup --- Mocks the __aenter__ return value (the crawler instance)
    mock_crawler_instance = MockAsyncWebCrawler.return_value.__aenter__.return_value
    mock_arun = mock_crawler_instance.arun  # Get the mock arun method

    initial_result = CrawlResult(
        url="http://example.com",
        status_code=200,
        html="<html><body>Initial fetch</body></html>",
        success=True,
        error_message=None,
    )

    base_text = "Hello, world!"
    repeat_count = 50
    long_markdown_content = "\n\n".join([base_text] * repeat_count)
    html_content = f"<html><body>{'<p>' + base_text + '</p>' * repeat_count}</body></html>"

    deep_crawl_result = CrawlResult(
        url="http://example.com",
        status_code=200,
        html=html_content,
        success=True,
        error_message=None,
    )
    mock_markdown = MagicMock()
    mock_markdown.raw_markdown = long_markdown_content
    deep_crawl_result.markdown = mock_markdown  # No need for __bool__ hack anymore

    # Configure side effect for the two calls to arun
    mock_arun.side_effect = [
        [initial_result],  # Return value for first call (resolves redirect)
        [deep_crawl_result],  # Return value for second call (deep crawl)
    ]
    # --- End Mock Setup ---

    url = "http://example.com"
    content = await crawl_documentation(url, max_pages=10, max_depth=1)

    # Assertions
    assert mock_arun.call_count == 2
    # Check first call arguments
    assert mock_arun.call_args_list[0][0][0] == url  # url
    assert mock_arun.call_args_list[0][1].get("config") is None  # No config
    # Check second call arguments
    assert mock_arun.call_args_list[1][0][0] == url  # final_url (no redirect in this case)
    assert "config" in mock_arun.call_args_list[1][1]
    assert isinstance(mock_arun.call_args_list[1][1]["config"], CrawlerRunConfig)
    # Assert final content
    assert content == long_markdown_content


@pytest.mark.asyncio
@patch("llm_min.crawler.AsyncWebCrawler")
async def test_crawl_documentation_redirect(MockAsyncWebCrawler):
    """Test crawl with redirect."""
    # --- Mock Setup ---
    mock_crawler_instance = MockAsyncWebCrawler.return_value.__aenter__.return_value
    mock_arun = mock_crawler_instance.arun

    initial_url = "http://example.com/old"
    final_url = "http://example.com/new/docs/"
    initial_result = CrawlResult(
        url=initial_url,
        status_code=301,
        html="Redirecting...",
        success=True,
        error_message=None,
        redirected_url=final_url,  # Crucial for redirect logic
    )

    base_text = "New Docs!"
    repeat_count = 50
    long_markdown_content = "\n\n".join([base_text] * repeat_count)
    html_content = f"<html><body>{'<p>' + base_text + '</p>' * repeat_count}</body></html>"

    deep_crawl_result = CrawlResult(
        url=final_url,
        status_code=200,
        html=html_content,
        success=True,
        error_message=None,
    )
    mock_markdown = MagicMock()
    mock_markdown.raw_markdown = long_markdown_content
    deep_crawl_result.markdown = mock_markdown

    mock_arun.side_effect = [
        [initial_result],  # First call result triggers redirect logic
        [deep_crawl_result],  # Second call result
    ]
    # --- End Mock Setup ---

    content = await crawl_documentation(initial_url)

    # Assertions
    assert mock_arun.call_count == 2
    assert mock_arun.call_args_list[0][0][0] == initial_url
    assert mock_arun.call_args_list[1][0][0] == final_url  # Second call uses final_url
    assert "config" in mock_arun.call_args_list[1][1]
    assert isinstance(mock_arun.call_args_list[1][1]["config"], CrawlerRunConfig)
    assert content == long_markdown_content


@pytest.mark.asyncio
@patch("llm_min.crawler.AsyncWebCrawler")
async def test_crawl_documentation_initial_fetch_fails(MockAsyncWebCrawler):
    """Test when initial fetch fails."""
    # --- Mock Setup ---
    mock_crawler_instance = MockAsyncWebCrawler.return_value.__aenter__.return_value
    mock_arun = mock_crawler_instance.arun

    url = "http://example.com/404"
    initial_result = CrawlResult(url=url, status_code=404, html="", success=False, error_message="Not Found")

    base_text = "Fallback Content"
    repeat_count = 50
    long_markdown_content = "\n\n".join([base_text] * repeat_count)
    html_content = f"<html><body>{'<p>' + base_text + '</p>' * repeat_count}</body></html>"

    deep_crawl_result = CrawlResult(
        url=url,  # Second crawl still uses original url
        status_code=200,
        html=html_content,
        success=True,
        error_message=None,
    )
    mock_markdown = MagicMock()
    mock_markdown.raw_markdown = long_markdown_content
    deep_crawl_result.markdown = mock_markdown

    mock_arun.side_effect = [
        [initial_result],  # First call fails
        [deep_crawl_result],  # Second call result
    ]
    # --- End Mock Setup ---

    content = await crawl_documentation(url)

    # Assertions
    assert mock_arun.call_count == 2
    assert mock_arun.call_args_list[0][0][0] == url
    assert mock_arun.call_args_list[1][0][0] == url  # Second call uses original url
    assert "config" in mock_arun.call_args_list[1][1]
    assert isinstance(mock_arun.call_args_list[1][1]["config"], CrawlerRunConfig)
    assert content == long_markdown_content


@pytest.mark.asyncio
@patch("llm_min.crawler.AsyncWebCrawler")
async def test_crawl_documentation_deep_crawl_returns_none(MockAsyncWebCrawler):
    """Test when deep crawl returns no results."""
    # --- Mock Setup ---
    mock_crawler_instance = MockAsyncWebCrawler.return_value.__aenter__.return_value
    mock_arun = mock_crawler_instance.arun

    initial_result = CrawlResult(
        url="http://example.com",
        status_code=200,
        html="<html><body>Initial fetch</body></html>",
        success=True,
        error_message=None,
    )

    mock_arun.side_effect = [
        [initial_result],
        [],  # Empty list for deep crawl result
    ]
    # --- End Mock Setup ---

    url = "http://example.com"
    content = await crawl_documentation(url)
    assert mock_arun.call_count == 2
    assert content is None


@pytest.mark.asyncio
@patch("llm_min.crawler.AsyncWebCrawler")
async def test_crawl_documentation_deep_crawl_fails(MockAsyncWebCrawler):
    """Test when deep crawl raises exception."""
    # --- Mock Setup ---
    mock_crawler_instance = MockAsyncWebCrawler.return_value.__aenter__.return_value
    mock_arun = mock_crawler_instance.arun

    initial_result = CrawlResult(
        url="http://example.com",
        status_code=200,
        html="<html><body>Initial fetch</body></html>",
        success=True,
        error_message=None,
    )

    mock_arun.side_effect = [
        [initial_result],
        Exception("Deep crawl network error"),  # Exception for second call
    ]
    # --- End Mock Setup ---

    url = "http://example.com"
    content = await crawl_documentation(url)
    assert mock_arun.call_count == 2  # Should still attempt both
    assert content is None


@pytest.mark.asyncio
@patch("llm_min.crawler.AsyncWebCrawler")
async def test_crawl_documentation_no_markdown_content(MockAsyncWebCrawler):
    """Test when deep crawl succeeds but markdown generation yields empty string."""
    # --- Mock Setup ---
    mock_crawler_instance = MockAsyncWebCrawler.return_value.__aenter__.return_value
    mock_arun = mock_crawler_instance.arun

    initial_result = CrawlResult(
        url="http://example.com", status_code=200, html="Initial", success=True, error_message=None
    )

    deep_crawl_result = CrawlResult(
        url="http://example.com",
        status_code=200,
        html="<html><body><p>&nbsp;</p><div></div></body></html>",
        success=True,
        error_message=None,
    )
    mock_markdown = MagicMock()
    mock_markdown.raw_markdown = ""  # Empty string
    deep_crawl_result.markdown = mock_markdown

    mock_arun.side_effect = [
        [initial_result],
        [deep_crawl_result],  # Second call returns result with empty markdown
    ]
    # --- End Mock Setup ---

    url = "http://example.com"
    content = await crawl_documentation(url)

    assert mock_arun.call_count == 2
    # Expect None because raw_markdown is empty, failing the check in the list comprehension
    assert content is None
