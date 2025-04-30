import logging
import os

from dotenv import load_dotenv

# Import genai again
from google import genai
from google.genai.types import GenerateContentResponse, GenerationConfig

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


async def generate_text_response(
    prompt: str,
    api_key: str | None = None,
    max_output_tokens: int | None = None,  # Optional: Add parameter to control max tokens
) -> str:
    """
    Generates a text response using the Google Gemini API (Async - though the call itself is sync).
    Checks for completion status (finish_reason).

    Args:
        prompt: The input prompt for the LLM.
        api_key: Optional Gemini API Key. If not provided, tries GEMINI_API_KEY env var.
        max_output_tokens: Optional maximum number of tokens for the response.

    Returns:
        The response string, or an error message string if failed or incomplete in certain ways.
        Logs warnings if truncated due to MAX_TOKENS.
    """
    effective_api_key = api_key or os.getenv("GEMINI_API_KEY")

    if not effective_api_key:
        logger.error("Gemini API key is required but was not provided.")
        return "ERROR: Gemini API key is required but was not provided."

    try:
        # Instantiate the client with the API key
        client = genai.Client(api_key=effective_api_key)

        # Prepare generation config if max_output_tokens is specified
        generation_config = None
        if max_output_tokens is not None:
            # Ensure you are using the correct GenerationConfig object
            # Check the library's documentation for the exact import and structure
            # Assuming google.generativeai.types.GenerationConfig
            generation_config = GenerationConfig(
                max_output_tokens=max_output_tokens,
                # You can add other config here like temperature, top_p etc.
            )

        # Use the client to generate content
        response: GenerateContentResponse = client.models.generate_content(
            model="gemini-2.5-flash-preview-0417",  # Use the specific model you intend
            contents=prompt,
            config=generation_config,  # Pass the config
        )

        # 1. Check for blocking first (often indicated in prompt_feedback)
        if response.prompt_feedback and response.prompt_feedback.block_reason:
            reason = response.prompt_feedback.block_reason.name  # Get enum name
            logger.warning(f"Gemini content generation blocked for prompt. Reason: {reason}")
            return f"ERROR: Gemini content generation blocked. Reason: {reason}"

        # 2. Check if there are candidates and parts
        if not response.candidates:
            logger.warning("Gemini response did not contain any candidates.")
            # This might happen if blocked for other reasons not in prompt_feedback
            # Or if the response structure is unexpected.
            # Check finish_reason even if parts are missing, it might still be informative
            # (Though usually SAFETY/OTHER if no content)
            return "ERROR: Gemini response contained no candidates."

        # Assume the first candidate is the primary one
        candidate = response.candidates[0]

        # 3. Check the finish reason for the candidate
        finish_reason = candidate.finish_reason.name  # Get enum name (e.g., "STOP", "MAX_TOKENS")

        if finish_reason == "STOP":
            logger.info("Gemini generation finished naturally (STOP).")
            # Proceed to extract text - likely complete
        elif finish_reason == "MAX_TOKENS":
            logger.warning("Gemini generation stopped due to MAX_TOKENS limit. Output may be truncated.")
            # Output is technically returned, but flagged as potentially incomplete.
            # You might choose to return an error, or the truncated text with a warning.
            # Let's return the text but the log indicates the issue.
        elif finish_reason == "SAFETY":
            logger.warning("Gemini generation stopped due to SAFETY filters on the output.")
            # Often, text might be missing or empty in this case.
            # Even if some text exists, it was stopped pre-emptively.
            # Return error for safety stop? Or empty string? Depends on desired behavior.
            return "ERROR: Gemini generation stopped due to SAFETY filters on the output."
        elif finish_reason == "RECITATION":
            logger.warning("Gemini generation stopped due to RECITATION filters.")
            return "ERROR: Gemini generation stopped due to RECITATION filters."
        else:  # OTHER or unexpected reasons
            logger.warning(f"Gemini generation finished with reason: {finish_reason}")
            # Treat as potentially problematic or incomplete.

        # 4. Extract text (handle potential lack of text even if not blocked)
        try:
            # Access text via parts is generally safer if structure is complex
            # but response.text often works for simple text responses.
            # Check if content and parts exist before accessing text
            if candidate.content and candidate.content.parts:
                response_text = "".join(part.text for part in candidate.content.parts if hasattr(part, "text"))
            else:
                # Fallback or if .text shortcut is preferred and reliable for your model/use case
                response_text = response.text  # This might raise ValueError if no text part exists
        except ValueError:
            # This might happen if finish_reason was SAFETY or other issues
            # even after the initial checks.
            logger.warning(
                f"Gemini response candidate had no valid text content despite finish_reason"
                f" '{finish_reason}'. Candidate: {candidate}"
            )
            # Decide on return value, maybe empty string or error based on finish_reason
            if finish_reason in ["SAFETY", "RECITATION"]:
                # Already handled returning an error above for these
                # This path might be redundant but safe to keep
                return f"ERROR: Gemini generation stopped due to {finish_reason} and produced no text."
            else:
                return "ERROR: Gemini response contained no valid text content."

        return response_text.strip()

    except Exception as e:
        logger.error(f"Error during Gemini API text generation: {e}", exc_info=True)
        # Add specific handling for google.api_core.exceptions if needed
        return f"ERROR: Gemini API call failed: {e}"
