import logging
import os
import json
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv
from google import genai # Use the new library

load_dotenv() # Load environment variables from .env file

logger = logging.getLogger(__name__)

def _stream_gemini_response(client: genai.Client, model_name: str, contents: Any) -> Optional[str]:
    """
    Helper function to handle streaming response from Gemini API.
    Collects all chunks and returns the complete text.
    """
    try:
        response_stream = client.models.generate_content_stream(
            model=model_name,
            contents=contents,
        )

        full_response = ""
        for chunk in response_stream:
            if chunk.text:
                full_response += chunk.text
        return full_response

    except Exception as e:
        logger.error(f"Error during Gemini API streaming: {e}")
        return None

def chunk_content(content: str, chunk_size: int) -> List[str]:
    """Splits content into chunks of approximately chunk_size."""
    chunks = []
    start = 0
    while start < len(content):
        end = start + chunk_size
        if end > len(content):
            end = len(content)
        # Try to find a natural break point (like a newline) near the end of the chunk
        last_newline = content.rfind('\n', start, end)
        if last_newline > start:
            end = last_newline + 1 # Include the newline character
        chunks.append(content[start:end])
        start = end
    return chunks

def merge_json_outputs(json_outputs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Merges a list of JSON outputs from chunk processing.
    Assumes the JSON structure is a dictionary with a key (e.g., 'components')
    containing a list of items to be merged.
    """
    merged_output: Dict[str, Any] = {}
    # Assuming the primary structure is a dictionary and we are merging lists within it
    # This needs to be adapted based on the actual expected JSON schema
    for output in json_outputs:
        for key, value in output.items():
            if isinstance(value, list):
                if key not in merged_output:
                    merged_output[key] = []
                merged_output[key].extend(value)
            else:
                # Handle other types if necessary, potentially overwriting or logging a warning
                if key not in merged_output:
                     merged_output[key] = value
                # else:
                #     logger.warning(f"Key '{key}' already exists in merged output with different value. Overwriting.")
                #     merged_output[key] = value

    return merged_output


def generate_text_response(prompt: str, api_key: Optional[str] = None) -> Optional[str]:
    """
    Generates a text response using the Google Gemini API.

    Args:
        prompt: The input prompt for the LLM.
        api_key: Optional Gemini API Key. If not provided, tries GEMINI_API_KEY env var.

    Returns:
        The response string if successful, None otherwise.
    """
    # Prioritize passed api_key, then environment variable
    effective_api_key = api_key or os.getenv("GEMINI_API_KEY")

    if not effective_api_key:
        logger.error("Gemini API Key not provided via argument or GEMINI_API_KEY environment variable.")
        return None

    try:
        # Initialize the client
        client = genai.Client(api_key=effective_api_key) # Use effective_api_key
        model_name = "gemini-1.5-flash-latest" # Use a model suitable for general text generation

        # Use the streaming helper function
        response_text = _stream_gemini_response(client, model_name, contents=prompt)

        if response_text:
            return response_text
        else:
            logger.error("Failed to get text response from Gemini API.")
            return None

    except Exception as e:
        logger.error(f"Error during Gemini API text generation: {e}")
        return None