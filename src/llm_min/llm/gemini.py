import logging
import os

from dotenv import load_dotenv

# Import genai again
from google import genai
from google.genai.types import GenerateContentResponse, GenerateContentConfig, ThinkingConfig

load_dotenv()  # Load environment variables from .env file

logger = logging.getLogger(__name__)


def chunk_content(content: str, chunk_size: int) -> list[str]:
    """
    Splits concatenated Markdown content into chunks of approximately chunk_size.
    Tries to respect paragraph and line breaks for more natural splitting.
    A small, fixed overlap is added between chunks.
    """
    if not content.strip():
        return []

    chunks = []
    current_pos = 0
    # Define a small overlap, e.g., 10% of chunk_size or a fixed number of characters
    # For simplicity with the current signature, we'll make it a small fixed value or derived.
    # Let's make it a small portion of chunk_size for now.
    # If we could add chunk_overlap to the signature, that would be more flexible.
    chunk_overlap = max(10, chunk_size // 20)  # e.g., 5% of chunk_size, but at least 10 chars

    while current_pos < len(content):
        # Determine the ideal end position for this chunk
        ideal_end_pos = current_pos + chunk_size

        # If ideal end is beyond content length, just take the rest
        if ideal_end_pos >= len(content):
            chunks.append(content[current_pos:])
            break

        # Look for preferred break points within a reasonable window around ideal_end_pos
        # Window: from a bit before ideal_end_pos to ideal_end_pos
        search_start = max(current_pos, ideal_end_pos - chunk_size // 2)  # Don't search too far back
        actual_end_pos = ideal_end_pos

        # 1. Try to find a double newline (paragraph break)
        # We search backwards from ideal_end_pos
        paragraph_break = content.rfind(
            "\n\n", search_start, ideal_end_pos + 2
        )  # +2 to catch it if it's right at the end
        if paragraph_break != -1 and paragraph_break > current_pos:
            actual_end_pos = paragraph_break + 2  # Include the double newline
        else:
            # 2. Try to find a single newline (line break)
            line_break = content.rfind("\n", search_start, ideal_end_pos + 1)
            if line_break != -1 and line_break > current_pos:
                actual_end_pos = line_break + 1  # Include the newline
            # else:
            # 3. If no good break found, just take chunk_size (or what's left)
            #    This is covered by ideal_end_pos, but we ensure it doesn't exceed content length.
            #    actual_end_pos remains ideal_end_pos, capped at len(content)

        # Ensure we don't go past the end of the content
        actual_end_pos = min(actual_end_pos, len(content))

        # If after finding a break, the chunk is extremely small (e.g., < 10% of chunk_size),
        # it might be better to take the hard cut at chunk_size to avoid tiny chunks.
        # This can happen if a good break point is very close to current_pos.
        if actual_end_pos - current_pos < chunk_size // 10 and ideal_end_pos < len(content):
            actual_end_pos = min(ideal_end_pos, len(content))

        chunk_text = content[current_pos:actual_end_pos]
        if chunk_text.strip():  # Only add non-empty chunks
            chunks.append(chunk_text)

        # Move current_pos for the next chunk, considering overlap
        # The next chunk should start `chunk_overlap` characters before `actual_end_pos`
        # but not before the beginning of the current chunk if it was very short.
        if actual_end_pos >= len(content):  # Reached the end
            break

        current_pos = max(current_pos + 1, actual_end_pos - chunk_overlap)  # Ensure progress

        # Safety break to prevent infinite loops if logic is flawed
        if not chunk_text and current_pos < len(content):
            # This shouldn't happen if logic is correct, but as a safeguard
            # print("Warning: Empty chunk detected, forcing progress.")
            current_pos += 1

    # A final pass to filter out any accidental empty strings if they slipped through
    return [c for c in chunks if c.strip()]


async def generate_text_response(
    prompt: str,
    model_name: str,
    api_key: str | None = None,
    max_output_tokens: int | None = None,  # Optional: Add parameter to control max tokens
    temperature: float = 0.1,  # Added temperature
) -> str:
    """
    Generates a text response using the Google Gemini API (Async - though the call itself is sync).
    Checks for completion status (finish_reason).

    Args:
        Args:
            prompt: The input prompt for the LLM.
            model_name: The name of the Gemini model to use.
            api_key: Optional Gemini API Key. If not provided, tries GEMINI_API_KEY env var.
            max_output_tokens: Optional maximum number of tokens for the response.
            temperature: The sampling temperature for generation (e.g., 0.0 for deterministic, higher for more random). Defaults to 0.1.
    Returns:
        The response string, or an error message string if failed or incomplete in certain ways.
        Logs warnings if truncated due to MAX_TOKENS.
    """
    effective_api_key = api_key or os.getenv("GEMINI_API_KEY")

    if not effective_api_key:
        logger.error("Gemini API key is required but was not provided.")
        return "ERROR: Gemini API key is required but was not provided."

    # Instantiate the client with the API key
    client = genai.Client(api_key=effective_api_key)

    # Prepare generation config
    generation_config_obj = GenerateContentConfig(temperature=temperature)

    logger.info(f"Attempting to generate content with Gemini model: {model_name}")  # Log the model name

    response: GenerateContentResponse | None = None
    finish_reason: str | None = None
    retries = 0
    max_retries = 1 # Retry once

    while retries <= max_retries:
        try:
            # Use the client to generate content
            response = client.models.generate_content(
                model=model_name,  # Use the specific model you intend
                contents=prompt,
                config=generation_config_obj,
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
                break # Exit retry loop on success
            elif finish_reason == "MAX_TOKENS":
                logger.warning(f"Gemini generation stopped due to MAX_TOKENS limit (Attempt {retries + 1}/{max_retries + 1}).")
                if retries < max_retries:
                    retries += 1
                    logger.info(f"Retrying Gemini generation...")
                    continue # Retry
                else:
                    logger.warning("Max retries reached for MAX_TOKENS. Output may be truncated.")
                    break # Exit loop after max retries
            elif finish_reason == "SAFETY":
                logger.warning("Gemini generation stopped due to SAFETY filters on the output.")
                return "ERROR: Gemini generation stopped due to SAFETY filters on the output."
            elif finish_reason == "RECITATION":
                logger.warning("Gemini generation stopped due to RECITATION filters.")
                return "ERROR: Gemini generation stopped due to RECITATION filters."
            else:  # OTHER or unexpected reasons
                logger.warning(f"Gemini generation finished with reason: {finish_reason}")
                # Treat as potentially problematic or incomplete.
                break # Exit loop for other reasons

        except Exception as e:
            logger.error(f"Error during Gemini API text generation (Attempt {retries + 1}/{max_retries + 1}): {e}", exc_info=True)
            if retries < max_retries:
                retries += 1
                logger.info(f"Retrying Gemini generation after error...")
                continue # Retry on exception
            else:
                logger.error("Max retries reached after error.")
                return f"ERROR: Gemini API call failed after multiple retries: {e}"

    # After the loop, check if a valid response was obtained
    if response is None or not response.candidates:
        return "ERROR: Gemini generation failed after retries."

    # 4. Extract text (handle potential lack of text even if not blocked)
    candidate = response.candidates[0] # Get the candidate from the last attempt
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

