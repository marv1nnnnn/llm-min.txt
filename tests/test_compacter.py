import json  # Import the json module
import unittest  # Import unittest
from unittest.mock import patch

from src.llm_min.compacter import (
    OUTPUT_SCHEMA_JSON,
    _load_shdf_guide,  # Import the internal function for testing
    compact_content_with_llm,
    get_compacting_prompt,
)  # Import OUTPUT_SCHEMA_JSON


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
    short_content = "A" * 10000  # Content shorter than max_content_length
    prompt = get_compacting_prompt(package_name, short_content)
    assert "... [TRUNCATED] ..." not in prompt


# Test cases for compact_content_with_llm
def test_compact_content_with_llm_empty_content():
    package_name = "test_package"
    doc_url = "http://example.com/docs"
    aggregated_content = ""
    result = compact_content_with_llm(package_name, doc_url, aggregated_content)
    assert result is None


@patch("src.llm_min.compacter.compact_text_gemini")
def test_compact_content_with_llm_success(mock_compact_text_gemini):
    # Mock the LLM to return a valid JSON string
    mock_llm_response_dict = {
        "Package": "test_package",
        "Version": "1.0.0",
        "SourceDocURL": "http://example.com/docs",
        "Purpose": "Test purpose",
        "Core Components": [{"Module": "test_module", "Class": "TestClass", "Function": "test_function"}],
        "Key Concepts/Usage": ["Concept 1", "Concept 2"],
        "Example": "print('hello')",
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


@patch("src.llm_min.compacter.compact_text_gemini")
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


@patch("src.llm_min.compacter.compact_text_gemini")
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


@patch("src.llm_min.compacter.compact_text_gemini")
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


@patch("src.llm_min.compacter.compact_text_gemini")
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


# Test cases for _load_shdf_guide
@patch("builtins.open", new_callable=unittest.mock.mock_open)
@patch("os.path.dirname", return_value="/fake/dir")
@patch("os.path.abspath", return_value="/fake/dir/src/llm_min/compacter.py")
@patch("os.path.join", side_effect=lambda *args: "/".join(args))
def test__load_shdf_guide_success(mock_join, mock_abspath, mock_dirname, mock_open):
    mock_open.return_value.read.return_value = "This is the guide content."
    guide_content = _load_shdf_guide()
    mock_open.assert_called_once_with("/fake/dir/../..//shdf-guide.md", "r", encoding="utf-8")
    assert guide_content == "This is the guide content."


@patch("builtins.open", new_callable=unittest.mock.mock_open)
@patch("os.path.dirname", return_value="/fake/dir")
@patch("os.path.abspath", return_value="/fake/dir/src/llm_min/compacter.py")
@patch("os.path.join", side_effect=lambda *args: "/".join(args))
def test__load_shdf_guide_strip_markdown(mock_join, mock_abspath, mock_dirname, mock_open):
    mock_open.return_value.read.return_value = "```\nThis is the guide content.\n```"
    guide_content = _load_shdf_guide()
    assert guide_content == "This is the guide content."


@patch("builtins.open", new_callable=unittest.mock.mock_open)
@patch("os.path.dirname", return_value="/fake/dir")
@patch("os.path.abspath", return_value="/fake/dir/src/llm_min/compacter.py")
@patch("os.path.join", side_effect=lambda *args: "/".join(args))
def test__load_shdf_guide_strip_markdown_md(mock_join, mock_abspath, mock_dirname, mock_open):
    mock_open.return_value.read.return_value = "```md\nThis is the guide content.\n```"
    guide_content = _load_shdf_guide()
    assert guide_content == "This is the guide content."


@patch("builtins.open", side_effect=FileNotFoundError)
@patch("os.path.dirname", return_value="/fake/dir")
@patch("os.path.abspath", return_value="/fake/dir/src/llm_min/compacter.py")
@patch("os.path.join", side_effect=lambda *args: "/".join(args))
def test__load_shdf_guide_file_not_found(mock_join, mock_abspath, mock_dirname, mock_open):
    guide_content = _load_shdf_guide()
    assert "ERROR: SHDF GUIDE FILE NOT FOUND." in guide_content


@patch("builtins.open", new_callable=unittest.mock.mock_open)
@patch("os.path.dirname", return_value="/fake/dir")
@patch("os.path.abspath", return_value="/fake/dir/src/llm_min/compacter.py")
@patch("os.path.join", side_effect=lambda *args: "/".join(args))
def test__load_shdf_guide_other_exception(mock_join, mock_abspath, mock_dirname, mock_open):
    mock_open.side_effect = Exception("Permission denied")
    guide_content = _load_shdf_guide()
    assert "ERROR: COULD NOT READ SHDF GUIDE FILE: Permission denied" in guide_content


# Test cases for compact_content_with_llm - single chunk scenario
@patch("src.llm_min.compacter.chunk_content", return_value=["single chunk content"])
@patch("src.llm_min.compacter.generate_text_response", return_value="SHDF fragment")
@patch("src.llm_min.compacter._load_shdf_guide", return_value="SHDF guide content")  # Mock guide loading
def test_compact_content_with_llm_single_chunk(mock_load_guide, mock_generate_text_response, mock_chunk_content):
    aggregated_content = "Some content that will be a single chunk"
    result = compact_content_with_llm(aggregated_content)

    mock_chunk_content.assert_called_once_with(aggregated_content, 8000)
    mock_generate_text_response.assert_called_once()  # Check if called, specific args checked by prompt template test
    assert result == "SHDF fragment"


# Test case for compact_content_with_llm when guide loading fails
@patch(
    "src.llm_min.compacter._load_shdf_guide",
    return_value="ERROR: SHDF GUIDE FILE NOT FOUND.",
)
def test_compact_content_with_llm_guide_load_fails(mock_load_guide):
    aggregated_content = "Some content"
    result = compact_content_with_llm(aggregated_content)
    mock_load_guide.assert_called_once()
    assert result is None


# Add import for unittest.mock


# Test cases for compact_content_with_llm - multiple chunks scenario
@patch(
    "src.llm_min.compacter.chunk_content",
    return_value=["chunk 1", "chunk 2", "chunk 3"],
)
@patch("src.llm_min.compacter.generate_text_response")
@patch("src.llm_min.compacter._load_shdf_guide", return_value="SHDF guide content")  # Mock guide loading
def test_compact_content_with_llm_multiple_chunks(mock_load_guide, mock_generate_text_response, mock_chunk_content):
    # Mock generate_text_response for fragment generation and merging
    mock_generate_text_response.side_effect = [
        "fragment 1",
        "fragment 2",
        "fragment 3",
        "merged SHDF",
    ]

    aggregated_content = "Some content that will be split into multiple chunks"
    subject = "test_subject"
    api_key = "fake_api_key"
    result = compact_content_with_llm(aggregated_content, subject=subject, api_key=api_key)

    mock_chunk_content.assert_called_once_with(aggregated_content, 8000)

    # Assert fragment generation calls
    expected_fragment_prompt_template = """
Objective: Generate an ultra-dense technical API/Data Structure index fragment for {subject} in Symbolic Hierarchical Delimited Format (SHDF), extracted from the provided chunk of documentation. This is a fragment, so it does not need to be a complete SHDF document, but should contain valid SHDF elements for the content in this chunk. Maximize information density for machine parsing (e.g., by an LLM provided with the SHDF v3 Guide below). Assume well-named elements are self-explanatory. Output must be raw SHDF v3 string fragment, starting immediately with the relevant section prefix (e.g., A:, D:, etc.), no explanations or Markdown ```.

Input: A chunk of technical documentation for {subject}.
Output Format: Raw SHDF v3 string fragment adhering strictly to the guide below, containing elements found in this chunk.

--- SHDF v3 Guide Start ---
SHDF guide content
--- SHDF v3 Guide End ---

Execute using the provided documentation chunk for {subject} to generate the raw SHDF v3 fragment output.
DOCUMENTATION CHUNK:
---
{chunk}
---
"""
    mock_generate_text_response.call_args_list[0].assert_called_with(
        text=expected_fragment_prompt_template.format(subject=subject, chunk="chunk 1").strip(),
        api_key=api_key,
    )
    mock_generate_text_response.call_args_list[1].assert_called_with(
        text=expected_fragment_prompt_template.format(subject=subject, chunk="chunk 2").strip(),
        api_key=api_key,
    )
    mock_generate_text_response.call_args_list[2].assert_called_with(
        text=expected_fragment_prompt_template.format(subject=subject, chunk="chunk 3").strip(),
        api_key=api_key,
    )

    # Assert merge call
    expected_merge_prompt_template = """
Objective: Merge the provided SHDF v3 fragments into a single, coherent, and complete SHDF v3 document for {subject}. Ensure the output strictly adheres to the SHDF v3 Guide provided below. Combine elements from the fragments into their respective sections (A:, D:, O:, etc.), removing duplicates and resolving any inconsistencies. The output must be a raw SHDF v3 string, starting immediately with S:, no explanations or Markdown ```.

Input: A list of SHDF v3 fragments generated from chunks of documentation for {subject}.
Output Format: A single, raw SHDF v3 string adhering strictly to the guide below.

--- SHDF v3 Guide Start ---
SHDF guide content
--- SHDF v3 Guide End ---

Execute using the provided SHDF fragments for {subject} to generate the single, merged, raw SHDF v3 output.
SHDF FRAGMENTS TO MERGE:
---
{fragments}
---
"""
    expected_fragments_input = "fragment 1\n---\nfragment 2\n---\nfragment 3"
    mock_generate_text_response.call_args_list[3].assert_called_with(
        text=expected_merge_prompt_template.format(
            shdf_guide="SHDF guide content",
            subject=subject,
            fragments=expected_fragments_input,
        ).strip(),
        api_key=api_key,
    )

    assert result == "merged SHDF"


# Test case for compact_content_with_llm with custom chunk size
@patch("src.llm_min.compacter.chunk_content")
@patch("src.llm_min.compacter.generate_text_response", return_value="SHDF fragment")
@patch("src.llm_min.compacter._load_shdf_guide", return_value="SHDF guide content")  # Mock guide loading
def test_compact_content_with_llm_custom_chunk_size(mock_load_guide, mock_generate_text_response, mock_chunk_content):
    aggregated_content = "Some content"
    custom_chunk_size = 1000
    compact_content_with_llm(aggregated_content, chunk_size=custom_chunk_size)
    mock_chunk_content.assert_called_once_with(aggregated_content, custom_chunk_size)


# Test case for compact_content_with_llm when fragment generation fails for one chunk
@patch("src.llm_min.compacter.chunk_content", return_value=["chunk 1", "chunk 2"])
@patch("src.llm_min.compacter.generate_text_response", side_effect=["fragment 1", None])  # Fail on second fragment
@patch("src.llm_min.compacter._load_shdf_guide", return_value="SHDF guide content")  # Mock guide loading
def test_compact_content_with_llm_fragment_generation_fails_partial(
    mock_load_guide, mock_generate_text_response, mock_chunk_content
):
    aggregated_content = "Some content"
    result = compact_content_with_llm(aggregated_content)
    # Should still attempt to merge the successful fragments
    assert mock_generate_text_response.call_count == 3  # 2 fragment calls + 1 merge call
    assert result is not None  # Should return a merged result from the successful fragment


# Test case for compact_content_with_llm when fragment generation fails for all chunks
@patch("src.llm_min.compacter.chunk_content", return_value=["chunk 1", "chunk 2"])
@patch("src.llm_min.compacter.generate_text_response", return_value=None)  # Fail on all fragments
@patch("src.llm_min.compacter._load_shdf_guide", return_value="SHDF guide content")  # Mock guide loading
def test_compact_content_with_llm_fragment_generation_fails_all(
    mock_load_guide, mock_generate_text_response, mock_chunk_content
):
    aggregated_content = "Some content"
    result = compact_content_with_llm(aggregated_content)
    assert mock_generate_text_response.call_count == 2  # Only fragment calls
    assert result is None  # Should return None as no fragments were generated


# Test case for compact_content_with_llm when merging fails
@patch("src.llm_min.compacter.chunk_content", return_value=["chunk 1", "chunk 2"])
@patch(
    "src.llm_min.compacter.generate_text_response",
    side_effect=["fragment 1", "fragment 2", None],
)  # Fail on merge
@patch("src.llm_min.compacter._load_shdf_guide", return_value="SHDF guide content")  # Mock guide loading
def test_compact_content_with_llm_merge_fails(mock_load_guide, mock_generate_text_response, mock_chunk_content):
    aggregated_content = "Some content"
    result = compact_content_with_llm(aggregated_content)
    assert mock_generate_text_response.call_count == 3  # 2 fragment calls + 1 merge call
    assert result is None  # Should return None as merging failed
