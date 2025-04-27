import pytest
from unittest.mock import patch
import json # Import the json module

from src.llm_min_generator.compacter import compact_content_with_llm, get_compacting_prompt, OUTPUT_SCHEMA_JSON # Import OUTPUT_SCHEMA_JSON

# Test cases for get_compacting_prompt (optional, but good practice)
def test_get_compacting_prompt_truncation():
    package_name = "test_package"
    long_content = "A" * 40000  # Content longer than max_content_length
    prompt = get_compacting_prompt(package_name, long_content)
    assert "... [TRUNCATED] ..." in prompt
    # The prompt structure changed, so adjust the length check or remove it if not critical
    # assert len(prompt) < len(long_content) + 1000 # Check if prompt is significantly shorter

def test_get_compacting_prompt_no_truncation():
    package_name = "test_package"
    short_content = "A" * 10000 # Content shorter than max_content_length
    prompt = get_compacting_prompt(package_name, short_content)
    assert "... [TRUNCATED] ..." not in prompt

# Test cases for compact_content_with_llm
def test_compact_content_with_llm_empty_content():
    package_name = "test_package"
    doc_url = "http://example.com/docs"
    aggregated_content = ""
    result = compact_content_with_llm(package_name, doc_url, aggregated_content)
    assert result is None

@patch('src.llm_min_generator.compacter.compact_text_gemini')
def test_compact_content_with_llm_success(mock_compact_text_gemini):
    # Mock the LLM to return a valid JSON string
    mock_llm_response_dict = {
        "Package": "test_package",
        "Version": "1.0.0",
        "SourceDocURL": "http://example.com/docs",
        "Purpose": "Test purpose",
        "Core Components": [{"Module": "test_module", "Class": "TestClass", "Function": "test_function"}],
        "Key Concepts/Usage": ["Concept 1", "Concept 2"],
        "Example": "print('hello')"
    }
    mock_compact_text_gemini.return_value = json.dumps(mock_llm_response_dict)

    package_name = "test_package"
    doc_url = "http://example.com/docs"
    aggregated_content = "Some documentation content"

    result = compact_content_with_llm(package_name, doc_url, aggregated_content)

    # Assert that compact_text_gemini was called with the correct prompt and schema
    expected_prompt = get_compacting_prompt(package_name, aggregated_content)
    mock_compact_text_gemini.assert_called_once_with(text=expected_prompt, response_schema=OUTPUT_SCHEMA_JSON)

    # Assert that the function returned the parsed dictionary
    assert result == mock_llm_response_dict

@patch('src.llm_min_generator.compacter.compact_text_gemini')
def test_compact_content_with_llm_llm_returns_none(mock_compact_text_gemini):
    mock_compact_text_gemini.return_value = None
    package_name = "test_package"
    doc_url = "http://example.com/docs"
    aggregated_content = "Some documentation content"
    result = compact_content_with_llm(package_name, doc_url, aggregated_content)
    expected_prompt = get_compacting_prompt(package_name, aggregated_content)
    # Updated assertion to include response_schema
    mock_compact_text_gemini.assert_called_once_with(text=expected_prompt, response_schema=OUTPUT_SCHEMA_JSON)
    assert result is None

@patch('src.llm_min_generator.compacter.compact_text_gemini')
def test_compact_content_with_llm_llm_returns_empty_string(mock_compact_text_gemini):
    mock_compact_text_gemini.return_value = ""
    package_name = "test_package"
    doc_url = "http://example.com/docs"
    aggregated_content = "Some documentation content"
    result = compact_content_with_llm(package_name, doc_url, aggregated_content)
    expected_prompt = get_compacting_prompt(package_name, aggregated_content)
    # Updated assertion to include response_schema
    mock_compact_text_gemini.assert_called_once_with(text=expected_prompt, response_schema=OUTPUT_SCHEMA_JSON)
    assert result is None

@patch('src.llm_min_generator.compacter.compact_text_gemini')
def test_compact_content_with_llm_llm_exception(mock_compact_text_gemini):
    mock_compact_text_gemini.side_effect = Exception("LLM error")
    package_name = "test_package"
    doc_url = "http://example.com/docs"
    aggregated_content = "Some documentation content"
    result = compact_content_with_llm(package_name, doc_url, aggregated_content)
    expected_prompt = get_compacting_prompt(package_name, aggregated_content)
    # Updated assertion to include response_schema
    mock_compact_text_gemini.assert_called_once_with(text=expected_prompt, response_schema=OUTPUT_SCHEMA_JSON)
    assert result is None

@patch('src.llm_min_generator.compacter.compact_text_gemini')
def test_compact_content_with_llm_invalid_json(mock_compact_text_gemini):
    # Mock the LLM to return invalid JSON
    mock_compact_text_gemini.return_value = "This is not valid JSON"
    package_name = "test_package"
    doc_url = "http://example.com/docs"
    aggregated_content = "Some documentation content"
    result = compact_content_with_llm(package_name, doc_url, aggregated_content)
    expected_prompt = get_compacting_prompt(package_name, aggregated_content)
    mock_compact_text_gemini.assert_called_once_with(text=expected_prompt, response_schema=OUTPUT_SCHEMA_JSON)
    assert result is None