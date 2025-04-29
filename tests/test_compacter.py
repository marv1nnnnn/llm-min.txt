from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from llm_min.client import LLMMinClient

# Corrected import path
from llm_min.compacter import (
    FRAGMENT_GENERATION_PROMPT_TEMPLATE,
    MERGE_PROMPT_TEMPLATE,
    _load_pcs_guide,
    _pcs_guide_content,
)


# Helper to mock importlib.resources.files().joinpath().read_text()
# Updated helper to mock pathlib.Path operations
def create_mock_path_api(content_to_return=None, exception_to_raise=None):
    mock_path_instance = MagicMock(spec=Path)
    mock_parent_dir = MagicMock(spec=Path)
    mock_guide_file = MagicMock(spec=Path)

    # Configure the chain Path(__file__).parent / "pcs-guide.md"
    mock_path_constructor = MagicMock(return_value=mock_path_instance)
    mock_path_instance.parent = mock_parent_dir
    mock_parent_dir.__truediv__.return_value = mock_guide_file  # Mock the / operator

    # Configure the read_text call on the final file path
    if exception_to_raise:
        mock_guide_file.read_text.side_effect = exception_to_raise
    else:
        mock_guide_file.read_text.return_value = content_to_return or ""

    return mock_path_constructor


# --- Test cases for the new _load_pcs_guide ---


# Patch the correct target: llm_min.compacter.Path
@patch(
    "llm_min.compacter.Path",
    new_callable=create_mock_path_api,
    content_to_return="This is the guide content.",
)
def test__load_pcs_guide_success(mock_Path):  # Renamed mock_files to mock_Path
    """Test successful loading using pathlib.Path."""
    guide_content = _load_pcs_guide()

    # Check the Path constructor was called (for __file__)
    # mock_Path.assert_called_once_with(__file__) # This assertion is unreliable when Path itself is mocked

    # Check the relevant methods were called on the mocked path objects
    mock_Path.return_value.parent.__truediv__.assert_called_once_with("pcs-guide.md")
    mock_Path.return_value.parent.__truediv__.return_value.read_text.assert_called_once_with(encoding="utf-8")

    assert guide_content == "This is the guide content."


@patch(
    "llm_min.compacter.Path",
    new_callable=create_mock_path_api,
    content_to_return="```\nContent inside fences\n```",
)
def test__load_pcs_guide_strip_markdown(mock_Path):
    """Test stripping ``` markdown fences."""
    guide_content = _load_pcs_guide()
    mock_Path.assert_called_once()
    assert guide_content == "Content inside fences"


@patch(
    "llm_min.compacter.Path",
    new_callable=create_mock_path_api,
    content_to_return="```md\nContent inside md fences\n```",
)
def test__load_pcs_guide_strip_markdown_md(mock_Path):
    """Test stripping ```md markdown fences."""
    guide_content = _load_pcs_guide()
    mock_Path.assert_called_once()
    assert guide_content == "Content inside md fences"


@patch(
    "llm_min.compacter.Path",
    new_callable=create_mock_path_api,
    exception_to_raise=FileNotFoundError("Mock file missing"),
)
def test__load_pcs_guide_file_not_found(mock_Path):
    """Test handling FileNotFoundError from Path.read_text."""
    guide_content = _load_pcs_guide()
    mock_Path.assert_called_once()
    assert "ERROR: PCS GUIDE FILE NOT FOUND" in guide_content
    assert "Mock file missing" in guide_content


@patch(
    "llm_min.compacter.Path",
    new_callable=create_mock_path_api,
    exception_to_raise=OSError("Mock OS error"),
)
def test__load_pcs_guide_other_exception(mock_Path):
    """Test handling other exceptions from Path.read_text."""
    guide_content = _load_pcs_guide()
    mock_Path.assert_called_once()
    assert "ERROR: COULD NOT READ PCS GUIDE FILE" in guide_content
    assert "Mock OS error" in guide_content


# --- Test cases for compact_content_with_llm (via LLMMinClient) ---

# Use the ACTUAL loaded guide content for prompt assertions
ACTUAL_PCS_GUIDE_CONTENT = _pcs_guide_content

# Ensure guide content is loaded for tests, handle error if loading failed
if "ERROR:" in ACTUAL_PCS_GUIDE_CONTENT:
    pytest.fail(
        "PCS guide could not be loaded for tests. Check pcs-guide.md and compacter.py loading logic.",
        pytrace=False,
    )


@pytest.mark.asyncio
@patch("llm_min.client.generate_text_response", new_callable=AsyncMock)
@patch("llm_min.client.chunk_content", return_value=["single chunk content"])
async def test_compact_content_with_llm_single_chunk_no_merge(mock_chunk_content, mock_generate_text_response):
    mock_generate_text_response.return_value = "Compacted single chunk."

    client = LLMMinClient(api_key="dummy_key")
    content = "This is some content to compact."
    compacted_content = await client.compact(content)

    mock_chunk_content.assert_called_once_with(content, client.max_tokens_per_chunk)
    mock_generate_text_response.assert_awaited_once()
    expected_fragment_prompt = FRAGMENT_GENERATION_PROMPT_TEMPLATE.substitute(
        pcs_guide=ACTUAL_PCS_GUIDE_CONTENT,
        chunk="single chunk content",
    )
    mock_generate_text_response.assert_awaited_once_with(
        prompt=expected_fragment_prompt,
        api_key=client.api_key,
    )
    assert compacted_content == "Compacted single chunk."


@pytest.mark.asyncio
@patch("llm_min.client.generate_text_response", new_callable=AsyncMock)
@patch("llm_min.client.chunk_content", return_value=["chunk 1", "chunk 2"])
async def test_compact_content_with_llm_multiple_chunks_merge_success(mock_chunk_content, mock_generate_text_response):
    mock_generate_text_response.side_effect = [
        "Compacted chunk 1.",
        "Compacted chunk 2.",
        "Merged compacted content.",
    ]

    client = LLMMinClient(api_key="dummy_key")
    content = "This is content that needs multiple chunks."
    compacted_content = await client.compact(content)

    mock_chunk_content.assert_called_once_with(content, client.max_tokens_per_chunk)
    assert mock_generate_text_response.await_count == 3

    expected_fragment_prompt_1 = FRAGMENT_GENERATION_PROMPT_TEMPLATE.substitute(
        pcs_guide=ACTUAL_PCS_GUIDE_CONTENT,
        chunk="chunk 1",
    )
    expected_fragment_prompt_2 = FRAGMENT_GENERATION_PROMPT_TEMPLATE.substitute(
        pcs_guide=ACTUAL_PCS_GUIDE_CONTENT,
        chunk="chunk 2",
    )
    mock_generate_text_response.assert_any_await(prompt=expected_fragment_prompt_1, api_key=client.api_key)
    mock_generate_text_response.assert_any_await(prompt=expected_fragment_prompt_2, api_key=client.api_key)

    expected_merge_prompt = MERGE_PROMPT_TEMPLATE.substitute(
        pcs_guide=ACTUAL_PCS_GUIDE_CONTENT,
        fragments="Compacted chunk 1.\n---\nCompacted chunk 2.",
        subject="technical documentation",
    )
    mock_generate_text_response.assert_any_await(prompt=expected_merge_prompt, api_key=client.api_key)
    assert compacted_content == "Merged compacted content."


@pytest.mark.asyncio
@patch("llm_min.client.generate_text_response", new_callable=AsyncMock)
@patch("llm_min.client.chunk_content", return_value=["single chunk content"])
async def test_compact_content_with_llm_with_subject(mock_chunk_content, mock_generate_text_response):
    mock_generate_text_response.return_value = "Compacted with subject."
    subject = "My Test Subject"

    client = LLMMinClient(api_key="dummy_key")
    content = "Content requiring subject."
    compacted_content = await client.compact(content, subject=subject)

    mock_chunk_content.assert_called_once_with(content, client.max_tokens_per_chunk)
    mock_generate_text_response.assert_awaited_once()
    expected_fragment_prompt = FRAGMENT_GENERATION_PROMPT_TEMPLATE.substitute(
        pcs_guide=ACTUAL_PCS_GUIDE_CONTENT,
        chunk="single chunk content",
    )
    mock_generate_text_response.assert_awaited_once_with(
        prompt=expected_fragment_prompt,
        api_key=client.api_key,
    )
    assert compacted_content == "Compacted with subject."  # Merge not called, result is single fragment


@pytest.mark.asyncio
@patch("llm_min.client.generate_text_response", new_callable=AsyncMock)
@patch("llm_min.client.chunk_content", return_value=["chunk 1", "chunk 2"])
async def test_compact_content_with_llm_multiple_chunks_merge_with_subject(
    mock_chunk_content, mock_generate_text_response
):
    mock_generate_text_response.side_effect = [
        "Compacted chunk 1 (subject).",
        "Compacted chunk 2 (subject).",
        "Merged compacted content (subject).",
    ]
    subject = "My Test Subject For Merge"

    client = LLMMinClient(api_key="dummy_key")
    content = "This is content that needs multiple chunks with subject."
    compacted_content = await client.compact(content, subject=subject)

    mock_chunk_content.assert_called_once_with(content, client.max_tokens_per_chunk)
    assert mock_generate_text_response.await_count == 3

    expected_merge_prompt = MERGE_PROMPT_TEMPLATE.substitute(
        pcs_guide=ACTUAL_PCS_GUIDE_CONTENT,
        fragments="Compacted chunk 1 (subject).\n---\nCompacted chunk 2 (subject).",
        subject=subject,
    )
    mock_generate_text_response.assert_any_await(prompt=expected_merge_prompt, api_key=client.api_key)
    assert compacted_content == "Merged compacted content (subject)."


@pytest.mark.asyncio
@patch(
    "llm_min.client.generate_text_response",
    new_callable=AsyncMock,
    side_effect=[
        "Compacted chunk 1.",
        Exception("Simulated API error for chunk 2"),
        "Merged with error.",
    ],
)
@patch("llm_min.client.chunk_content", return_value=["chunk 1", "chunk 2"])
async def test_compact_content_with_llm_fragment_generation_fails_partial(
    mock_chunk_content, mock_generate_text_response
):
    client = LLMMinClient(api_key="dummy_key")
    content = "Content for partial failure test."
    compacted_content = await client.compact(content)

    mock_chunk_content.assert_called_once_with(content, client.max_tokens_per_chunk)
    assert mock_generate_text_response.await_count == 3  # 2 fragment attempts, 1 merge attempt

    expected_fragment_prompt_1 = FRAGMENT_GENERATION_PROMPT_TEMPLATE.substitute(
        pcs_guide=ACTUAL_PCS_GUIDE_CONTENT, chunk="chunk 1"
    )
    expected_fragment_prompt_2 = FRAGMENT_GENERATION_PROMPT_TEMPLATE.substitute(
        pcs_guide=ACTUAL_PCS_GUIDE_CONTENT, chunk="chunk 2"
    )
    mock_generate_text_response.assert_any_await(prompt=expected_fragment_prompt_1, api_key=client.api_key)
    mock_generate_text_response.assert_any_await(prompt=expected_fragment_prompt_2, api_key=client.api_key)

    # Use actual newlines for comparison with the joined string
    expected_fragments_for_merge = (
        "Compacted chunk 1.\n---\nERROR: FRAGMENT GENERATION FAILED FOR CHUNK 2: Simulated API error for chunk 2"
    )
    expected_merge_prompt = MERGE_PROMPT_TEMPLATE.substitute(
        pcs_guide=ACTUAL_PCS_GUIDE_CONTENT,
        fragments=expected_fragments_for_merge,
        subject="technical documentation",
    )
    mock_generate_text_response.assert_any_await(prompt=expected_merge_prompt, api_key=client.api_key)
    assert compacted_content == "Merged with error."


@pytest.mark.asyncio
@patch(
    "llm_min.client.generate_text_response",
    new_callable=AsyncMock,
    side_effect=Exception("Simulated API error for all chunks"),
)
@patch("llm_min.client.chunk_content", return_value=["chunk 1", "chunk 2"])
async def test_compact_content_with_llm_fragment_generation_fails_all(mock_chunk_content, mock_generate_text_response):
    client = LLMMinClient(api_key="dummy_key")
    content = "Content for total failure test."
    compacted_content = await client.compact(content)

    mock_chunk_content.assert_called_once_with(content, client.max_tokens_per_chunk)
    assert mock_generate_text_response.await_count == 2  # Only fragment attempts fail, no merge call
    assert "ERROR: ALL FRAGMENT GENERATION FAILED" in compacted_content


@pytest.mark.asyncio
@patch(
    "llm_min.client.generate_text_response",
    new_callable=AsyncMock,
    side_effect=[
        "Compacted chunk 1.",
        "Compacted chunk 2.",
        Exception("Simulated merge API error"),
    ],
)
@patch("llm_min.client.chunk_content", return_value=["chunk 1", "chunk 2"])
async def test_compact_content_with_llm_merge_fails(mock_chunk_content, mock_generate_text_response):
    client = LLMMinClient(api_key="dummy_key")
    content = "Content for merge failure test."
    compacted_content = await client.compact(content)

    mock_chunk_content.assert_called_once_with(content, client.max_tokens_per_chunk)
    assert mock_generate_text_response.await_count == 3  # 2 fragments + 1 merge attempt
    assert "ERROR: FRAGMENT MERGE FAILED" in compacted_content
    assert "Simulated merge API error" in compacted_content


@pytest.mark.asyncio
@patch("llm_min.client.generate_text_response", new_callable=AsyncMock)
@patch("llm_min.client.chunk_content", return_value=["single chunk content"])
async def test_compact_content_with_llm_custom_chunk_size(mock_chunk_content, mock_generate_text_response):
    mock_generate_text_response.return_value = "Compacted content."
    mock_chunk_content.return_value = ["single chunk content"]

    client = LLMMinClient(api_key="dummy_key", max_tokens_per_chunk=500)
    content = "Content for custom chunk size test."
    custom_chunk_size = 200
    await client.compact(content, chunk_size=custom_chunk_size)

    mock_chunk_content.assert_called_once_with(content, custom_chunk_size)
    mock_generate_text_response.assert_awaited_once()
    expected_fragment_prompt = FRAGMENT_GENERATION_PROMPT_TEMPLATE.substitute(
        pcs_guide=ACTUAL_PCS_GUIDE_CONTENT, chunk="single chunk content"
    )
    mock_generate_text_response.assert_awaited_once_with(
        prompt=expected_fragment_prompt,
        api_key=client.api_key,
    )


@pytest.mark.asyncio
@patch("llm_min.client.generate_text_response", new_callable=AsyncMock)
@patch("llm_min.client.chunk_content")
async def test_compact_content_with_llm_dummy_api_key(mock_chunk_content, mock_generate_text_response):
    """Tests that using the literal 'dummy_api_key' bypasses LLM calls and returns dummy PCS."""
    client = LLMMinClient(api_key="dummy_api_key")  # Use the specific dummy key
    content = "Some input content that should be ignored."
    subject = "DummySubject"

    # Call the compact method
    compacted_content = await client.compact(content, subject=subject)

    # Assert that chunking and LLM calls were NOT made
    mock_chunk_content.assert_not_called()
    mock_generate_text_response.assert_not_awaited()

    # Assert that the expected dummy PCS string is returned
    expected_dummy_pcs = f"|S: $$subject {subject}\n|A: $$path#DummyClass()[]{{}}{{}}<>\n|D: $$SDummyStruct()"
    assert compacted_content == expected_dummy_pcs


# Additional test cases can be added here if needed.
