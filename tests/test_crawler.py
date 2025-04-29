from unittest.mock import MagicMock, patch

import requests

from src.llm_min.crawler import crawl_url


# Mock the requests.get method
@patch("src.llm_min.crawler.requests.get")
def test_crawl_url_success(mock_get):
    # Configure the mock to return a successful response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "<html><body>Hello, world!</body></html>"
    mock_response.headers = {"Content-Type": "text/html"}
    mock_get.return_value = mock_response

    url = "http://example.com"
    content = crawl_url(url)

    mock_get.assert_called_once_with(url)
    assert content == "<html><body>Hello, world!</body></html>"


@patch("src.llm_min.crawler.requests.get")
def test_crawl_url_404(mock_get):
    # Configure the mock to return a 404 response
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_get.return_value = mock_response

    url = "http://example.com/nonexistent"
    content = crawl_url(url)

    mock_get.assert_called_once_with(url)
    assert content is None


@patch("src.llm_min.crawler.requests.get")
def test_crawl_url_network_error(mock_get):
    # Configure the mock to raise a requests.exceptions.RequestException
    mock_get.side_effect = requests.exceptions.RequestException("Network error")

    url = "http://example.com"
    content = crawl_url(url)

    mock_get.assert_called_once_with(url)
    assert content is None


@patch("src.llm_min.crawler.requests.get")
def test_crawl_url_non_html_content(mock_get):
    # Configure the mock to return a non-HTML content type
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "some non-html content"
    mock_response.headers = {"Content-Type": "application/json"}
    mock_get.return_value = mock_response

    url = "http://example.com/data.json"
    content = crawl_url(url)

    mock_get.assert_called_once_with(url)
    assert content is None
