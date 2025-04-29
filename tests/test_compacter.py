import unittest
from string import Template
from unittest.mock import AsyncMock, patch

import pytest

from llm_min.client import LLMMinClient  # Import the new client

# Corrected import path
from llm_min.compacter import (
    FRAGMENT_GENERATION_PROMPT_TEMPLATE_STR,
    MERGE_PROMPT_TEMPLATE_STR,
    _load_pcs_guide,  # Keep for potential direct testing later, though currently skipped
    # compact_content_with_llm, # Removed as we will use the client
)


# Test cases for _load_pcs_guide
@patch("builtins.open", new_callable=unittest.mock.mock_open)
def test__load_pcs_guide_success(mock_open):
    """Test successful loading of the PCS guide file."""
    guide_path = "/fake/path/to/pcs-guide.md"
    mock_open.return_value.read.return_value = "This is the guide content."

    guide_content = _load_pcs_guide(guide_path)

    mock_open.assert_called_once_with(guide_path, encoding="utf-8")
    assert guide_content == "This is the guide content."


@patch("builtins.open", new_callable=unittest.mock.mock_open)
def test__load_pcs_guide_strip_markdown(mock_open):
    """Test stripping ``` markdown fences."""
    guide_path = "/fake/guide.md"
    mock_open.return_value.read.return_value = "```\nContent inside fences\n```"

    guide_content = _load_pcs_guide(guide_path)

    mock_open.assert_called_once_with(guide_path, encoding="utf-8")
    assert guide_content == "Content inside fences"


@patch("builtins.open", new_callable=unittest.mock.mock_open)
def test__load_pcs_guide_strip_markdown_md(mock_open):
    """Test stripping ```md markdown fences."""
    guide_path = "/fake/guide.md"
    mock_open.return_value.read.return_value = "```md\nContent inside md fences\n```"

    guide_content = _load_pcs_guide(guide_path)

    mock_open.assert_called_once_with(guide_path, encoding="utf-8")
    assert guide_content == "Content inside md fences"


@patch("builtins.open", side_effect=FileNotFoundError("File missing"))
def test__load_pcs_guide_file_not_found(mock_open):
    """Test handling FileNotFoundError during guide loading."""
    guide_path = "/non/existent/path/pcs-guide.md"

    guide_content = _load_pcs_guide(guide_path)

    mock_open.assert_called_once_with(guide_path, encoding="utf-8")
    assert "ERROR: PCS GUIDE FILE NOT FOUND" in guide_content
    assert "File missing" in guide_content  # Check if original exception message is included


@patch("builtins.open", side_effect=OSError("Disk full"))
def test__load_pcs_guide_other_exception(mock_open):
    """Test handling other exceptions (e.g., OSError) during guide loading."""
    guide_path = "/fake/path/pcs-guide.md"

    guide_content = _load_pcs_guide(guide_path)

    mock_open.assert_called_once_with(guide_path, encoding="utf-8")
    assert "ERROR:" in guide_content
    assert "Disk full" in guide_content  # Check if original exception message is included


# Test cases for compact_content_with_llm, now updated for LLMMinClient
# Mock the dependencies of LLMMinClient: _load_pcs_guide and generate_text_response
@pytest.mark.asyncio  # Mark test as async
@patch("llm_min.client._load_pcs_guide", return_value="Mocked guide content")
@patch("llm_min.client.generate_text_response", new_callable=AsyncMock)  # Use AsyncMock
@patch("llm_min.client.chunk_content", return_value=["single chunk content"])
async def test_compact_content_with_llm_single_chunk_no_merge(
    mock_chunk_content, mock_generate_text_response, mock_load_guide
):
    # Mock generate_text_response for the single chunk
    mock_generate_text_response.return_value = "Compacted single chunk."

    client = LLMMinClient(api_key="dummy_key")
    content = "This is some content to compact."
    # Await the async method call
    compacted_content = await client.compact(content)

    # Assertions
    mock_load_guide.assert_called_once()  # _load_pcs_guide is called during client init
    mock_chunk_content.assert_called_once_with(content, client.max_tokens_per_chunk)
    # Check generate_text_response was awaited
    mock_generate_text_response.assert_awaited_once()  # Use assert_awaited_once
    # Check the prompt used for the single chunk (fragment generation)
    expected_fragment_prompt_template = Template(FRAGMENT_GENERATION_PROMPT_TEMPLATE_STR)
    expected_fragment_prompt = expected_fragment_prompt_template.substitute(
        pcs_guide=mock_load_guide.return_value,
        chunk="single chunk content",
    )
    # Check call arguments
    mock_generate_text_response.assert_awaited_once_with(  # Use assert_awaited_once_with
        prompt=expected_fragment_prompt,
        api_key=client.api_key,
    )

    assert compacted_content == "Compacted single chunk."


@pytest.mark.asyncio  # Mark test as async
@patch("llm_min.client._load_pcs_guide", return_value="Mocked guide content")
@patch("llm_min.client.generate_text_response", new_callable=AsyncMock)  # Use AsyncMock
@patch("llm_min.client.chunk_content", return_value=["chunk 1", "chunk 2"])
async def test_compact_content_with_llm_multiple_chunks_merge_success(
    mock_chunk_content, mock_generate_text_response, mock_load_guide
):
    # Mock generate_text_response for fragment generation and merging
    mock_generate_text_response.side_effect = [
        "Compacted chunk 1.",
        "Compacted chunk 2.",
        "Merged compacted content.",
    ]

    client = LLMMinClient(api_key="dummy_key")
    content = "This is content that needs multiple chunks."
    # Await the async method call
    compacted_content = await client.compact(content)

    # Assertions
    mock_load_guide.assert_called_once()
    mock_chunk_content.assert_called_once_with(content, client.max_tokens_per_chunk)
    assert mock_generate_text_response.await_count == 3  # Check await_count

    # Check calls for fragment generation
    expected_fragment_prompt_template = Template(FRAGMENT_GENERATION_PROMPT_TEMPLATE_STR)
    expected_fragment_prompt_1 = expected_fragment_prompt_template.substitute(
        pcs_guide=mock_load_guide.return_value,
        chunk="chunk 1",
    )
    expected_fragment_prompt_2 = expected_fragment_prompt_template.substitute(
        pcs_guide=mock_load_guide.return_value,
        chunk="chunk 2",
    )
    # Check prompts passed to the mock
    mock_generate_text_response.assert_any_await(prompt=expected_fragment_prompt_1, api_key=client.api_key)
    mock_generate_text_response.assert_any_await(prompt=expected_fragment_prompt_2, api_key=client.api_key)

    # Check call for merging
    expected_merge_prompt_template = Template(MERGE_PROMPT_TEMPLATE_STR)
    expected_merge_prompt = expected_merge_prompt_template.substitute(
        pcs_guide=mock_load_guide.return_value,
        fragments="Compacted chunk 1.\n---\nCompacted chunk 2.",
        subject="technical documentation",
    )
    # Check prompt passed to the mock for merge call
    mock_generate_text_response.assert_any_await(prompt=expected_merge_prompt, api_key=client.api_key)

    assert compacted_content == "Merged compacted content."


@pytest.mark.asyncio  # Mark test as async
@patch("llm_min.client._load_pcs_guide", return_value="Mocked guide content")
@patch("llm_min.client.generate_text_response", new_callable=AsyncMock)  # Use AsyncMock
@patch("llm_min.client.chunk_content")  # Keep standard mock for chunk_content
async def test_compact_content_with_llm_custom_chunk_size(
    mock_chunk_content, mock_generate_text_response, mock_load_guide
):
    mock_generate_text_response.return_value = "Compacted content."
    mock_chunk_content.return_value = ["single chunk content"]

    client = LLMMinClient(api_key="dummy_key", max_tokens_per_chunk=500)
    content = "Content for custom chunk size test."
    custom_chunk_size = 200

    # Await the async method call
    await client.compact(content, chunk_size=custom_chunk_size)

    mock_load_guide.assert_called_once()
    mock_chunk_content.assert_called_once_with(content, custom_chunk_size)
    mock_generate_text_response.assert_awaited_once()  # Check awaited
    # Check fragment prompt
    expected_fragment_prompt_template = Template(FRAGMENT_GENERATION_PROMPT_TEMPLATE_STR)
    expected_fragment_prompt = expected_fragment_prompt_template.substitute(
        pcs_guide=mock_load_guide.return_value, chunk="single chunk content"
    )
    mock_generate_text_response.assert_awaited_once_with(  # Check awaited with args
        prompt=expected_fragment_prompt,
        api_key=client.api_key,
    )


@pytest.mark.asyncio  # Mark test as async
@patch("llm_min.client._load_pcs_guide", return_value="Mocked guide content")
# Use AsyncMock and provide appropriate return values for awaited calls
@patch(
    "llm_min.client.generate_text_response",
    new_callable=AsyncMock,
    side_effect=["Compacted chunk 1.", "ERROR: LLM failed.", "ERROR: MERGE FAILED"],
)  # Added merge error return
@patch("llm_min.client.chunk_content", return_value=["chunk 1", "chunk 2"])
async def test_compact_content_with_llm_fragment_generation_fails_partial(
    mock_chunk_content, mock_generate_text_response, mock_load_guide
):
    client = LLMMinClient(api_key="dummy_key")
    content = "Content for partial failure test."

    # Await the async method call
    compacted_content = await client.compact(content)

    mock_load_guide.assert_called_once()
    mock_chunk_content.assert_called_once_with(content, client.max_tokens_per_chunk)
    assert mock_generate_text_response.await_count == 3  # All calls should be awaited

    # Check calls for fragment generation
    expected_fragment_prompt_template = Template(FRAGMENT_GENERATION_PROMPT_TEMPLATE_STR)
    expected_fragment_prompt_1 = expected_fragment_prompt_template.substitute(
        pcs_guide=mock_load_guide.return_value,
        chunk="chunk 1",
    )
    expected_fragment_prompt_2 = expected_fragment_prompt_template.substitute(
        pcs_guide=mock_load_guide.return_value,
        chunk="chunk 2",
    )
    mock_generate_text_response.assert_any_await(prompt=expected_fragment_prompt_1, api_key=client.api_key)
    mock_generate_text_response.assert_any_await(prompt=expected_fragment_prompt_2, api_key=client.api_key)

    # The merge call should still happen
    expected_merge_prompt_template = Template(MERGE_PROMPT_TEMPLATE_STR)
    expected_merge_prompt = expected_merge_prompt_template.substitute(
        pcs_guide=mock_load_guide.return_value,
        fragments="Compacted chunk 1.\n---\nERROR: LLM failed.",  # Include error in fragments passed to merge
        subject="technical documentation",
    )
    mock_generate_text_response.assert_any_await(prompt=expected_merge_prompt, api_key=client.api_key)

    # Expecting the final result to be the merge error from the side_effect
    assert "ERROR: MERGE FAILED" in compacted_content


@pytest.mark.asyncio  # Mark test as async
@patch("llm_min.client._load_pcs_guide", return_value="Mocked guide content")
@patch(
    "llm_min.client.generate_text_response",
    new_callable=AsyncMock,
    side_effect=["ERROR: LLM failed 1.", "ERROR: LLM failed 2.", "ERROR: MERGE FAILED"],
)  # Add merge error
@patch("llm_min.client.chunk_content", return_value=["chunk 1", "chunk 2"])
async def test_compact_content_with_llm_fragment_generation_fails_all(
    mock_chunk_content, mock_generate_text_response, mock_load_guide
):
    client = LLMMinClient(api_key="dummy_key")
    content = "Content for all failure test."

    # Await the async method call
    compacted_content = await client.compact(content)

    mock_load_guide.assert_called_once()
    mock_chunk_content.assert_called_once_with(content, client.max_tokens_per_chunk)
    assert mock_generate_text_response.await_count == 3

    # Expecting the compacted content to indicate the merge failure
    assert "ERROR: MERGE FAILED" in compacted_content


@pytest.mark.asyncio  # Mark test as async
@patch("llm_min.client._load_pcs_guide", return_value="Mocked guide content")
@patch(
    "llm_min.client.generate_text_response",
    new_callable=AsyncMock,  # Use AsyncMock
    side_effect=["Compacted chunk 1.", "Compacted chunk 2.", Exception("Simulated merge API error")],
)
@patch("llm_min.client.chunk_content", return_value=["chunk 1", "chunk 2"])
async def test_compact_content_with_llm_merge_fails(mock_chunk_content, mock_generate_text_response, mock_load_guide):
    client = LLMMinClient(api_key="dummy_key")
    content = "Content for merge failure test."

    # Await the async method call
    compacted_content = await client.compact(content)

    mock_load_guide.assert_called_once()
    mock_chunk_content.assert_called_once_with(content, client.max_tokens_per_chunk)
    assert mock_generate_text_response.await_count == 3

    # Expecting the compacted content to indicate the merge failure and include the exception message
    assert "ERROR: FRAGMENT MERGE FAILED: Simulated merge API error" in compacted_content


@pytest.mark.asyncio  # Mark test as async
@patch("llm_min.client._load_pcs_guide", return_value="Mocked guide content")
@patch("llm_min.client.generate_text_response", new_callable=AsyncMock)  # Use AsyncMock
@patch("llm_min.client.chunk_content", return_value=["single chunk content"])
async def test_compact_content_with_llm_with_subject(mock_chunk_content, mock_generate_text_response, mock_load_guide):
    mock_generate_text_response.return_value = "Compacted single chunk with subject."

    client = LLMMinClient(api_key="dummy_key")
    content = "This is some content to compact."
    subject = "Test Subject"
    # Await the async method call
    compacted_content = await client.compact(content, subject=subject)

    mock_load_guide.assert_called_once()
    mock_chunk_content.assert_called_once_with(content, client.max_tokens_per_chunk)
    mock_generate_text_response.assert_awaited_once()  # Check awaited

    # Check the prompt used, ensuring the subject is included
    expected_fragment_prompt_template = Template(FRAGMENT_GENERATION_PROMPT_TEMPLATE_STR)
    expected_fragment_prompt = expected_fragment_prompt_template.substitute(
        pcs_guide=mock_load_guide.return_value,
        chunk="single chunk content",
    )
    mock_generate_text_response.assert_awaited_once_with(  # Check awaited with args
        prompt=expected_fragment_prompt,
        api_key=client.api_key,
    )

    assert compacted_content == "Compacted single chunk with subject."


@pytest.mark.asyncio  # Mark test as async
@patch("llm_min.client._load_pcs_guide", return_value="Mocked guide content")
@patch("llm_min.client.generate_text_response", new_callable=AsyncMock)  # Use AsyncMock
@patch("llm_min.client.chunk_content", return_value=["chunk 1", "chunk 2"])
async def test_compact_content_with_llm_multiple_chunks_merge_with_subject(
    mock_chunk_content, mock_generate_text_response, mock_load_guide
):
    mock_generate_text_response.side_effect = [
        "Compacted chunk 1.",
        "Compacted chunk 2.",
        "Merged compacted content with subject.",
    ]

    client = LLMMinClient(api_key="dummy_key")
    content = "This is content that needs multiple chunks."
    subject = "Another Test Subject"
    # Await the async method call
    compacted_content = await client.compact(content, subject=subject)

    mock_load_guide.assert_called_once()
    mock_chunk_content.assert_called_once_with(content, client.max_tokens_per_chunk)
    assert mock_generate_text_response.await_count == 3  # Check await_count

    # Check calls for fragment generation with subject
    expected_fragment_prompt_template = Template(FRAGMENT_GENERATION_PROMPT_TEMPLATE_STR)
    expected_fragment_prompt_1 = expected_fragment_prompt_template.substitute(
        pcs_guide=mock_load_guide.return_value,
        chunk="chunk 1",
    )
    expected_fragment_prompt_2 = expected_fragment_prompt_template.substitute(
        pcs_guide=mock_load_guide.return_value,
        chunk="chunk 2",
    )
    mock_generate_text_response.assert_any_await(prompt=expected_fragment_prompt_1, api_key=client.api_key)
    mock_generate_text_response.assert_any_await(prompt=expected_fragment_prompt_2, api_key=client.api_key)

    # Check call for merging with subject
    expected_merge_prompt_template = Template(MERGE_PROMPT_TEMPLATE_STR)
    expected_merge_prompt = expected_merge_prompt_template.substitute(
        pcs_guide=mock_load_guide.return_value,
        fragments="Compacted chunk 1.\n---\nCompacted chunk 2.",
        subject=subject,
    )
    mock_generate_text_response.assert_any_await(prompt=expected_merge_prompt, api_key=client.api_key)

    assert compacted_content == "Merged compacted content with subject."
