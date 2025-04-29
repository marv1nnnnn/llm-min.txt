from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from llm_min.search import (
    find_documentation_url,
    search_for_documentation_urls,
    select_best_url_with_llm,
)


# Mock DDGS for search_for_documentation_urls tests
@patch("llm_min.search.DDGS")
def test_search_for_documentation_urls_success(mock_ddgs):
    """Tests successful search with results."""
    mock_instance = MagicMock()
    mock_ddgs.return_value.__enter__.return_value = mock_instance
    mock_instance.text.return_value = [
        {"title": "Result 1", "href": "http://example.com/doc1", "body": "Snippet 1"},
        {
            "title": "Result 2",
            "href": "http://anothersite.org/doc2",
            "body": "Snippet 2",
        },
    ]

    package_name = "test_package"
    results = search_for_documentation_urls(package_name)

    mock_ddgs.assert_called_once()
    mock_instance.text.assert_called_once_with(f"{package_name} package documentation website", max_results=10)
    assert len(results) == 2
    assert results[0]["title"] == "Result 1"
    assert results[0]["href"] == "http://example.com/doc1"
    assert results[1]["body"] == "Snippet 2"


@patch("llm_min.search.DDGS")
def test_search_for_documentation_urls_no_results(mock_ddgs):
    """Tests search when no results are found."""
    mock_instance = MagicMock()
    mock_ddgs.return_value.__enter__.return_value = mock_instance
    mock_instance.text.return_value = []

    package_name = "no_docs_package"
    results = search_for_documentation_urls(package_name)

    mock_ddgs.assert_called_once()
    mock_instance.text.assert_called_once_with(f"{package_name} package documentation website", max_results=10)
    assert len(results) == 0
    assert results == []


@patch("llm_min.search.DDGS")
def test_search_for_documentation_urls_exception(mock_ddgs):
    """Tests search when an exception occurs."""
    mock_ddgs.side_effect = Exception("Search failed")

    package_name = "error_package"
    results = search_for_documentation_urls(package_name)

    mock_ddgs.assert_called_once()
    assert len(results) == 0
    assert results == []


@patch("llm_min.search.DDGS")
def test_search_for_documentation_urls_custom_num_results(mock_ddgs):
    """Tests search with a custom number of results."""
    mock_instance = MagicMock()
    mock_ddgs.return_value.__enter__.return_value = mock_instance
    mock_instance.text.return_value = [
        {
            "title": f"Result {i}",
            "href": f"http://example.com/doc{i}",
            "body": f"Snippet {i}",
        }
        for i in range(5)
    ]

    package_name = "custom_results_package"
    num_results = 5
    results = search_for_documentation_urls(package_name, num_results=num_results)

    mock_ddgs.assert_called_once()
    mock_instance.text.assert_called_once_with(f"{package_name} package documentation website", max_results=num_results)
    assert len(results) == num_results


# Mock generate_text_response for select_best_url_with_llm tests
@pytest.mark.asyncio
@patch("llm_min.search.generate_text_response", new_callable=AsyncMock)
async def test_select_best_url_with_llm_success(mock_generate_text_response):
    """Tests successful LLM selection of a valid URL."""
    mock_generate_text_response.return_value = "http://example.com/official/docs"

    package_name = "test_package"
    search_results = [
        {"title": "Result 1", "href": "http://example.com/doc1", "body": "Snippet 1"},
        {
            "title": "Result 2",
            "href": "http://anothersite.org/doc2",
            "body": "Snippet 2",
        },
    ]
    api_key = "fake_api_key"

    selected_url = await select_best_url_with_llm(package_name, search_results, api_key=api_key)

    mock_generate_text_response.assert_awaited_once()
    assert (
        "Analyze the following search results for the Python package 'test_package'."
        in mock_generate_text_response.await_args[0][0]
    )
    assert mock_generate_text_response.await_args[1]["api_key"] == api_key
    assert selected_url == "http://example.com/official/docs"


@pytest.mark.asyncio
@patch("llm_min.search.generate_text_response", new_callable=AsyncMock)
async def test_select_best_url_with_llm_returns_none(mock_generate_text_response):
    """Tests LLM returning 'None'."""
    mock_generate_text_response.return_value = "None"

    package_name = "test_package"
    search_results = [{"title": "Result 1", "href": "http://example.com/doc1", "body": "Snippet 1"}]

    selected_url = await select_best_url_with_llm(package_name, search_results)

    mock_generate_text_response.assert_awaited_once()
    assert selected_url is None


@pytest.mark.asyncio
@patch("llm_min.search.generate_text_response", new_callable=AsyncMock)
async def test_select_best_url_with_llm_returns_empty_string(
    mock_generate_text_response,
):
    """Tests LLM returning an empty string."""
    mock_generate_text_response.return_value = ""

    package_name = "test_package"
    search_results = [{"title": "Result 1", "href": "http://example.com/doc1", "body": "Snippet 1"}]

    selected_url = await select_best_url_with_llm(package_name, search_results)

    mock_generate_text_response.assert_awaited_once()
    assert selected_url is None


@pytest.mark.asyncio
@patch("llm_min.search.generate_text_response", new_callable=AsyncMock)
async def test_select_best_url_with_llm_invalid_url_format(mock_generate_text_response):
    """Tests LLM returning an invalid URL format."""
    mock_generate_text_response.return_value = "not a url"

    package_name = "test_package"
    search_results = [{"title": "Result 1", "href": "http://example.com/doc1", "body": "Snippet 1"}]

    selected_url = await select_best_url_with_llm(package_name, search_results)

    mock_generate_text_response.assert_awaited_once()
    assert selected_url is None


@pytest.mark.asyncio
@patch("llm_min.search.generate_text_response", new_callable=AsyncMock)
async def test_select_best_url_with_llm_empty_search_results(
    mock_generate_text_response,
):
    """Tests select_best_url_with_llm with empty search results input."""
    package_name = "test_package"
    search_results = []

    selected_url = await select_best_url_with_llm(package_name, search_results)

    mock_generate_text_response.assert_not_awaited()
    assert selected_url is None


@pytest.mark.asyncio
@patch("llm_min.search.generate_text_response", new_callable=AsyncMock)
async def test_select_best_url_with_llm_exception(mock_generate_text_response):
    """Tests select_best_url_with_llm when an exception occurs during LLM call."""
    mock_generate_text_response.side_effect = Exception("LLM error")

    package_name = "test_package"
    search_results = [{"title": "Result 1", "href": "http://example.com/doc1", "body": "Snippet 1"}]

    selected_url = await select_best_url_with_llm(package_name, search_results)

    mock_generate_text_response.assert_awaited_once()
    assert selected_url is None


# Mock both DDGS and generate_text_response for find_documentation_url tests
@pytest.mark.asyncio
@patch("llm_min.search.select_best_url_with_llm", new_callable=AsyncMock)
@patch("llm_min.search.search_for_documentation_urls")
async def test_find_documentation_url_success(mock_search, mock_select_url):
    """Tests successful end-to-end flow for find_documentation_url."""
    mock_search.return_value = [
        {"title": "Result 1", "href": "http://example.com/doc1", "body": "Snippet 1"},
        {
            "title": "Result 2",
            "href": "http://anothersite.org/doc2",
            "body": "Snippet 2",
        },
    ]
    mock_select_url.return_value = "http://example.com/official/docs"

    package_name = "test_package"
    api_key = "fake_api_key"
    found_url = await find_documentation_url(package_name, api_key=api_key)

    mock_search.assert_called_once_with(package_name)
    mock_select_url.assert_awaited_once_with(package_name, mock_search.return_value, api_key=api_key)
    assert found_url == "http://example.com/official/docs"


@pytest.mark.asyncio
@patch("llm_min.search.select_best_url_with_llm", new_callable=AsyncMock)
@patch("llm_min.search.search_for_documentation_urls")
async def test_find_documentation_url_no_search_results(mock_search, mock_select_url):
    """Tests find_documentation_url when search returns no results."""
    mock_search.return_value = []

    package_name = "test_package"
    found_url = await find_documentation_url(package_name)

    mock_search.assert_called_once_with(package_name)
    mock_select_url.assert_not_awaited()
    assert found_url is None


@pytest.mark.asyncio
@patch("llm_min.search.select_best_url_with_llm", new_callable=AsyncMock)
@patch("llm_min.search.search_for_documentation_urls")
async def test_find_documentation_url_llm_returns_none(mock_search, mock_select_url):
    """Tests find_documentation_url when LLM returns None."""
    mock_search.return_value = [
        {"title": "Result 1", "href": "http://example.com/doc1", "body": "Snippet 1"},
    ]
    mock_select_url.return_value = None

    package_name = "test_package"
    found_url = await find_documentation_url(package_name)

    mock_search.assert_called_once_with(package_name)
    mock_select_url.assert_awaited_once_with(package_name, mock_search.return_value, api_key=None)
    assert found_url is None


@pytest.mark.asyncio
@patch("llm_min.search.select_best_url_with_llm", new_callable=AsyncMock)
@patch("llm_min.search.search_for_documentation_urls")
async def test_find_documentation_url_url_cleaning(mock_search, mock_select_url):
    """Tests URL cleaning in find_documentation_url."""
    mock_search.return_value = [{"title": "Result 1", "href": "http://example.com/doc1", "body": "Snippet 1"}]

    test_cases = [
        ("http://example.com/docs/index.html", "http://example.com/docs"),
        ("http://example.com/docs/master/", "http://example.com/docs"),
        ("http://example.com/docs/latest", "http://example.com/docs"),
        ("http://example.com/docs/en/", "http://example.com/docs"),
        ("http://example.com/docs/", "http://example.com/docs"),
        ("http://example.com/docs", "http://example.com/docs"),
        (
            "http://example.com/docs/index.html/master/en/",
            "http://example.com/docs",
        ),  # Test multiple removals
    ]

    package_name = "test_package"
    for raw_url, cleaned_url in test_cases:
        mock_select_url.reset_mock()
        mock_select_url.return_value = raw_url
        found_url = await find_documentation_url(package_name)
        assert found_url == cleaned_url, f"Expected {cleaned_url} for {raw_url}, got {found_url}"
        mock_select_url.assert_awaited_once()


@pytest.mark.asyncio
@patch("llm_min.search.select_best_url_with_llm", new_callable=AsyncMock)
@patch("llm_min.search.search_for_documentation_urls")
async def test_find_documentation_url_dummy_api_key(mock_search, mock_select_url):
    """Tests find_documentation_url correctly handles the dummy API key."""
    package_name = "dummy_package"
    api_key = "dummy_api_key"

    # Call the function with the dummy key
    found_url = await find_documentation_url(package_name, api_key=api_key)

    # Assert that search and LLM selection were NOT called
    mock_search.assert_not_called()
    mock_select_url.assert_not_awaited()

    # Assert that the expected dummy URL is returned
    expected_dummy_url = f"https://dummy-docs.example.com/{package_name}/latest"
    assert found_url == expected_dummy_url
