import logging
import os

from dotenv import load_dotenv

# Import genai again
from google import genai

load_dotenv()  # Load environment variables from .env file

logger = logging.getLogger(__name__)

# Removed _stream_gemini_response


def chunk_content(content: str, chunk_size: int) -> list[str]:
    """Splits content into chunks of approximately chunk_size."""
    chunks = []
    start = 0
    while start < len(content):
        end = start + chunk_size
        if end > len(content):
            end = len(content)
        # Try to find a natural break point (like a newline) near the end of the chunk
        last_newline = content.rfind("\n", start, end)
        if last_newline > start:
            end = last_newline + 1  # Include the newline character
        chunks.append(content[start:end])
        start = end
    return chunks


# Removed merge_json_outputs


# Add generate_text_response back
async def generate_text_response(prompt: str, api_key: str | None = None) -> str:
    """
    Generates a text response using the Google Gemini API (Async).

    Args:
        prompt: The input prompt for the LLM.
        api_key: Optional Gemini API Key. If not provided, tries GEMINI_API_KEY env var.

    Returns:
        The response string, or an error message string if failed.
    """
    effective_api_key = api_key or os.getenv("GEMINI_API_KEY")

    if not effective_api_key:
        logger.error("Gemini API key is required but was not provided.")
        # Return error message instead of None to match test expectations
        return "ERROR: Gemini API key is required but was not provided."

    try:
        # Removed genai.configure()
        # Instantiate the client with the API key
        client = genai.Client(api_key=effective_api_key)

        # Use the client to generate content (Note: this call might be synchronous)
        # Using model name from docs examples
        response = client.models.generate_content(model="gemini-2.5-flash-preview-04-17", contents=prompt)

        # Check for response content before accessing text
        # Accessing response.text directly might raise if there's no valid candidate/content
        # A more robust check involves examining parts and candidates if necessary.
        # For simplicity matching the previous test structure, we access .text
        # but wrap in case of issues.
        try:
            response_text = response.text
        except ValueError:
            # Handle cases where response.text might be invalid (e.g., blocked content)
            logger.warning(f"Gemini response for prompt did not contain valid text. Response: {response}")
            # Consider checking response.prompt_feedback for block reasons
            block_reason = getattr(response.prompt_feedback, "block_reason", None)
            if block_reason:
                return f"ERROR: Gemini content generation blocked. Reason: {block_reason}"
            return "ERROR: Gemini response contained no valid text content."

        return response_text.strip()

    except Exception as e:
        logger.error(f"Error during Gemini API text generation: {e}", exc_info=True)
        return f"ERROR: Gemini API call failed: {e}"
