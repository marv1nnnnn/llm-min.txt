import logging
import datetime # Added for timestamp
from string import Template
import json # Only needed for the final build structure potentially, not validation.

# Import from .llm subpackage (now points to gemini via __init__.py)
from .llm import (
    chunk_content,
    generate_text_response,
)

logger = logging.getLogger(__name__)

# --- Prompts remain the same - instructing LLM to *attempt* JSON array format ---

# Optimized for extreme token efficiency (positional array output)
FRAGMENT_GENERATION_PROMPT_TEMPLATE_STR = """
Role: AIU Extractor.
Goal: Extract concise AIUs for LLM library usage guide. Focus: What lib *does* & *how*, not full API spec.
Input: Doc chunk.
Output: Plain text lines ONLY, where each line *attempts* to be a valid JSON array following the specified structure. One conceptual AIU per line. Empty line if no AIUs found. Min whitespace. Use `T`/`F` for bools. Use JSON `null` for absent optional values. Use `""` for empty strings.

AIU JSON Array Structure (Positional - Aim for exactly 9 elements):
Index | Meaning    | Value Type        | Notes (Attempt this structure precisely)
------|------------|-------------------|----------------------------------------------
0     | id         | String            | Generate a Unique ID (e.g., 'feat1'). MUST BE UNIQUE within this output batch.
1     | typ        | String            | Feat, CfgObj, Func, etc. (See Key Abbreviations)
2     | name       | String            | Canonical name
3     | purp       | String            | Concise purpose
4     | in         | String(JSON Array)| String representation `[[p, t, d, def, ex], ...]`. Use '[]' if none. Attempt valid JSON structure.
5     | out        | String(JSON Array)| String representation `[[f, t, d], ...]`. Use '[]' if none. Attempt valid JSON structure.
6     | use        | String            | Minimal code/config example. Use {id} placeholders.
7     | rel        | String(JSON Array)| String representation `[[id, typ], ...]`. Use '[]' if none. Attempt valid JSON structure. Ensure related IDs exist *within this output batch*.
8     | src        | String            | Source chunk ID (MUST BE "$chunk_id")

Key Abbreviations: (Same as previous)

Constraints & Focus (Apply to Extraction Logic):
1.  **Format Adherence (Best Effort):** Output ONLY plain text lines attempting the 9-element JSON array structure. Assign "$chunk_id" to index 8 (`src`). Ensure generated IDs (index 0) are unique in this output. Ensure nested lists (indices 4, 5, 7) *look like* valid JSON arrays or '[]'.
2.  **Focus:** High-level types (`Feat`/`HowTo`/`Patt`/`Scen`). Needs clear, runnable `use` (index 6).
3.  **Selectivity:** Essential details only.
4.  **Links (index 7 `rel`):** Selective, relevant. Referenced IDs must exist in this output batch.
5.  **Extraction Only:** Info explicitly from chunk.
6.  **Concise:** Keep text values brief.
7.  **Source:** Use "$chunk_id" exactly for index 8.
8.  **Impact:** Fewer, impactful AIUs > exhaustive detail.

Process CHUNK:
---
$chunk
---
"""
FRAGMENT_GENERATION_PROMPT_TEMPLATE = Template(FRAGMENT_GENERATION_PROMPT_TEMPLATE_STR)


# --- Merge Prompt (instructing LLM to *attempt* JSON array format) ---
AIU_MERGE_PROMPT_TEMPLATE_STR = AIU_MERGE_PROMPT_TEMPLATE_STR = """
Role: AIU Merger and Refiner.
Goal: Integrate information from a new document chunk into an existing set of AIU lines, producing a refined, consolidated set of AIU lines. **Focus on essential updates and additions, maximizing conciseness to save tokens.**
Input:
1.  `EXISTING_AIUS`: A list of plain text lines (one per line), each *attempting* to be an AIU JSON array from previous chunks.
2.  `NEXT_CHUNK`: The raw text content of the next document chunk.

Output: A NEW list of plain text lines ONLY, one line per AIU, attempting the same JSON array structure. Represents the *merged and refined* information from BOTH inputs. **Be extremely brief.** Use `T`/`F` for bools, `null` for absent optionals. Empty line if no AIUs should remain.

AIU JSON Array Structure (Positional - Aim for exactly 9 elements):
Index | Meaning    | Value Type        | Notes (Attempt this structure precisely)
------|------------|-------------------|----------------------------------------------
0     | id         | String            | Unique ID. **Crucially: Reuse IDs from EXISTING_AIUS if the AIU is fundamentally the same, even if updated. Generate NEW unique IDs (unique across the *entire new output list*) ONLY for genuinely new concepts introduced by NEXT_CHUNK.**
1     | typ        | String            | Feat, CfgObj, Func, etc.
2     | name       | String            | **Concise** canonical name
3     | purp       | String            | **Extremely Concise** purpose (potentially updated/merged)
4     | in         | String(JSON Array)| Updated/merged inputs `[[p, t, d, def, ex], ...]`. Use '[]' if none. Attempt valid JSON structure. Keep descriptions `d` **very brief**.
5     | out        | String(JSON Array)| Updated/merged outputs `[[f, t, d], ...]`. Use '[]' if none. Attempt valid JSON structure. Keep descriptions `d` **very brief**.
6     | use        | String            | Updated/merged **minimal** usage example. Use {id} placeholders.
7     | rel        | String(JSON Array)| Updated/merged relationships `[[id, typ], ...]`. Use '[]' if none. Attempt valid JSON structure. Ensure related IDs exist *in the final output list*. Only include **essential** relationships.
8     | src        | String            | Source chunk ID. **If AIU is NEW or significantly modified by NEXT_CHUNK, use "$chunk_id". If AIU is primarily from EXISTING_AIUS and largely unchanged, RETAIN its original 'src' value (found near index 8 of the input line).**

Merge & Refine Logic:
1.  Review BOTH inputs. Identify IDs (index 0) and sources (index 8) in existing lines.
2.  Identify Overlap: Find concepts in `NEXT_CHUNK` corresponding to existing AIU lines.
3.  **Update/Merge (Significant Changes Only):** If `NEXT_CHUNK` provides **substantial new information, corrects an error, or significantly clarifies** an existing AIU, update that line, *reusing its original ID* (index 0). Merge info logically. Update `src` (index 8) to "$chunk_id" if significantly modified, else keep original `src`. Ensure resulting line *attempts* the 9-element JSON array format. **Ignore minor rephrasing or trivial additions.**
4.  **Add New:** If `NEXT_CHUNK` introduces entirely new concepts, create *new* lines. Generate *new, unique IDs* (index 0) not clashing with reused or other new IDs. Set `src` (index 8) to "$chunk_id". Ensure line *attempts* the 9-element JSON array format.
5.  **Consolidate/Remove (Cautiously):** If `NEXT_CHUNK` reveals *obvious and direct* redundancy between two existing lines, merge them into one (choose one ID to keep, consolidate essential info). Omit lines only if they are *clearly* irrelevant based on `NEXT_CHUNK`. **Prioritize updates/additions over complex merges.**
6.  Relationships (`rel`): Update index 7. Ensure referenced IDs exist in the *final output list*. Only add/update relationships if they represent **key workflows or configurations.**
7.  Source (`src`): Assign index 8 based on the logic in points 3 & 4.
8.  Format (Best Effort): Output ONLY the final list of plain text lines, one per line, attempting the 9-element JSON array structure. Ensure all IDs (index 0) in the output are unique. No explanations.
9.  **Extreme Conciseness:** Keep ALL text fields (name, purp, descriptions in 'in'/'out', 'use' examples) as brief as possible while retaining core meaning. **Avoid elaboration.** Use abbreviations if standard and clear. Aim for minimal token usage per line.

EXISTING_AIUS:
---
$existing_aius
---

NEXT_CHUNK:
---
$next_chunk
---
"""
AIU_MERGE_PROMPT_TEMPLATE = Template(AIU_MERGE_PROMPT_TEMPLATE_STR)


def _build_llm_min_text(
    raw_aiu_lines: str, # Changed name to reflect it's raw lines
    library_name: str = "unknown_lib",
    library_version: str = "1.0"
) -> str:
    """
    Builds the final LLM_MIN.TXT structured text string according to the new guideline,
    using the raw lines provided by the last LLM step.

    Args:
        raw_aiu_lines: A string containing all the AIU lines from the last step,
                       separated by newlines. Assumed to be already cleaned.
        library_name: The name of the library (subject).
        library_version: The version of the library.

    Returns:
        The fully formatted LLM_MIN.TXT string.
    """
    # Sanitize library name for the header line if necessary
    safe_library_name = library_name.replace(" ", "_").replace("#", "")

    # Part 1: Meta Line
    current_utc_time = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    meta_line = f"#META#L:{safe_library_name}#V:{library_version}#D:{current_utc_time}#"

    # Part 2: Schema Line - Define the standard mappings
    aiu_map = "A:id;B:typ;C:name;D:purp;E:in;F:out;G:use;H:rel;I:src"
    in_map = "IN:a:p;b:t;c:d;d:def;e:ex"
    out_map = "OUT:f:f;g:t;h:d"
    rel_map = "REL:i:id;j:typ"
    schema_line = f"#SCHEMA#{aiu_map}#{in_map}#{out_map}#{rel_map}#"

    # Part 3: AIU List (use the raw lines directly)
    # The input `raw_aiu_lines` is assumed to be already stripped and newline-separated.
    aiu_list_content = raw_aiu_lines # No further stripping needed here if processed correctly before

    # Combine parts
    return f"{meta_line}\n{schema_line}\n{aiu_list_content}"


# --- Simplified Line Processing (No JSON Validation) ---
def _process_llm_output_lines(
    raw_llm_output: str | None,
    chunk_id: str
) -> str:
    """
    Processes raw LLM output: cleans up whitespace and joins non-empty lines.
    No validation or ID extraction is performed.

    Args:
        raw_llm_output: The string output from the LLM.
        chunk_id: The ID of the current chunk being processed (for logging).

    Returns:
        A string containing the processed AIU lines, separated by newlines,
        or an empty string if the input was None/empty or contained only whitespace.
    """
    if not raw_llm_output or not isinstance(raw_llm_output, str):
        logger.warning(f"[{chunk_id}] LLM output was empty or invalid type.")
        return ""

    processed_lines = []
    # Split lines first, then strip each one
    raw_lines = raw_llm_output.splitlines()
    logger.debug(f"[{chunk_id}] Processing {len(raw_lines)} raw lines from LLM output.")

    for line in raw_lines:
        cleaned_line = line.strip()
        if cleaned_line:
            processed_lines.append(cleaned_line)
        # Skip empty lines silently

    final_aiu_string = "\n".join(processed_lines)
    if processed_lines:
        logger.info(f"[{chunk_id}] Processed {len(processed_lines)} non-empty lines.")
    else:
        logger.info(f"[{chunk_id}] LLM output contained no non-empty lines after processing.")
    return final_aiu_string


async def compact_content_to_structured_text(
    aggregated_content: str,
    chunk_size: int = 1000000, # Adjust based on LLM context window limits
    api_key: str | None = None,
    subject: str = "the provided text", # Library name used for #META# line
    model_name: str | None = None,
) -> str:
    """
    Orchestrates compaction using sequential merge, treating LLM output as raw strings,
    and generating the final llm_min.txt format with #META# and #SCHEMA# lines.
    Relies entirely on LLM for format and ID management based on prompts.

    Args:
        aggregated_content: The text content to process.
        chunk_size: The size of chunks for splitting.
        api_key: Optional API key for the LLM.
        subject: The subject or name of the content (library name).
        model_name: Optional model name for the LLM.

    Returns:
        A string containing the serialized llm_min.txt content, or an empty string on failure.
    """
    logger.info(f"Starting sequential LLM-based AIU extraction/merge for {subject} (Output: llm_min.txt format v2, Raw Lines)...")

    # 1. Chunk the input content
    chunks = chunk_content(aggregated_content, chunk_size)
    if not chunks:
        logger.warning(f"[{subject}] Input content resulted in zero chunks.")
        return ""
    logger.info(f"[{subject}] Split content into {len(chunks)} chunks.")

    # Stores the raw string output from the previous LLM step (after basic cleaning)
    accumulated_aiu_lines_str = ""

    # 2. Process chunks sequentially
    for i, chunk_item_content in enumerate(chunks):
        chunk_id = f"chunk_{i}" # Use 0-based index for chunk ID
        logger.info(f"Processing chunk {i + 1}/{len(chunks)} (ID: {chunk_id})...")

        prompt: str
        is_merge_step = i > 0

        if not is_merge_step:
            # --- First Chunk: Extraction ---
            logger.info(f"[{chunk_id}] Stage: Initial Extraction.")
            prompt = FRAGMENT_GENERATION_PROMPT_TEMPLATE.substitute(
                chunk=chunk_item_content,
                chunk_id=chunk_id
            )
            prompt_type = "Extraction"
        else:
            # --- Subsequent Chunks: Merge ---
            logger.info(f"[{chunk_id}] Stage: Merging with previous AIU lines.")
            # Pass the raw accumulated lines string from the previous step
            prompt = AIU_MERGE_PROMPT_TEMPLATE.substitute(
                existing_aius=accumulated_aiu_lines_str, # Pass even if empty string
                next_chunk=chunk_item_content,
                chunk_id=chunk_id
            )
            prompt_type = "Merge"

        # Log the prompt (optional, can be verbose)
        # logger.debug(f"--- {prompt_type} Prompt for chunk {i + 1}/{len(chunks)} START ---")
        # logger.debug(prompt)
        # logger.debug(f"--- {prompt_type} Prompt for chunk {i + 1}/{len(chunks)} END ---")

        # Call the LLM
        raw_llm_output = await generate_text_response(
            prompt, api_key=api_key, model_name=model_name
        )

        # Process lines (just clean whitespace, split lines)
        processed_aiu_str_for_step = _process_llm_output_lines(
            raw_llm_output,
            chunk_id
        )

        # Update the accumulated state for the next iteration
        # The result of this step becomes the input for the next
        accumulated_aiu_lines_str = processed_aiu_str_for_step
        logger.info(f"[{chunk_id}] Step complete. Current accumulated lines count: {len(accumulated_aiu_lines_str.splitlines()) if accumulated_aiu_lines_str else 0}.")

        # Check for fatal error only on the first chunk if it yields nothing
        if i == 0 and not accumulated_aiu_lines_str:
            logger.error(f"[{chunk_id}] Failed to generate any output lines from the first chunk. Aborting.")
            # Return empty string, or perhaps the headers-only structure?
            # Let's return headers only for consistency with the final step.
            return _build_llm_min_text("", library_name=subject).strip()


    # 3. Final Assembly
    # If accumulated_aiu_lines_str is empty after all chunks, build the structure
    # with an empty AIU list content.
    if not accumulated_aiu_lines_str:
        logger.warning(f"[{subject}] No AIU lines remained after processing all chunks. Final file will contain only headers.")

    logger.info(f"[{subject}] Finished processing all {len(chunks)} chunks. Assembling final structured text.")
    # Pass the final accumulated raw lines to the build function
    final_structured_text = _build_llm_min_text(
        accumulated_aiu_lines_str,
        library_name=subject
        )

    logger.info(f"[{subject}] LLM-MIN text generation complete.")
    return final_structured_text.strip()