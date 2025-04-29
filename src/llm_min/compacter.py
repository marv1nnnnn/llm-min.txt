import logging
from pathlib import Path  # Import Path
from string import Template

# Import from .llm subpackage (now points to gemini via __init__.py)
from .llm import (
    chunk_content,
    generate_text_response,
)

logger = logging.getLogger(__name__)


# Function to read the PCS guide content directly from file
def _load_pcs_guide() -> str:
    """Loads the PCS guide content directly from the file."""
    # Get the directory of the current file (compacter.py)
    current_file_dir = Path(__file__).parent
    guide_file_path = current_file_dir / "pcs-guide.md"

    try:
        content = guide_file_path.read_text(encoding="utf-8")
        # Strip potential surrounding ```markdown blocks
        content = content.strip()
        # Corrected stripping logic for ```md
        if content.startswith("```md") and content.endswith("```"):
            content = content[5:-3].strip()  # Remove ```md prefix
        elif content.startswith("```") and content.endswith("```"):
            content = content[3:-3].strip()  # Remove ``` prefix
        return content
    except FileNotFoundError as e:
        logger.error(
            f"PCS guide file not found at expected path: {guide_file_path}. "
            f"Ensure 'pcs-guide.md' is in the same directory as compacter.py."
        )
        return f"ERROR: PCS GUIDE FILE NOT FOUND ({guide_file_path}). Details: {e}"
    except Exception as e:
        logger.error(f"Error reading PCS guide file from {guide_file_path}: {e}")
        return f"ERROR: COULD NOT READ PCS GUIDE FILE: {e}"


# Load the guide content once when the module is imported
_pcs_guide_content = _load_pcs_guide()

# Define the template for generating PCS fragments from chunks using string.Template syntax
FRAGMENT_GENERATION_PROMPT_TEMPLATE_STR = """
Objective: Generate an **ultra-compressed** technical software index fragment in
**PackedCodeSyntax (PCS)** format (guide below). Extract **all structural code
information and directly associated metadata** (signatures, types, defaults,
optionality, inheritance, modifiers, returns, exceptions, status, constants,
enums, attributes, critical notes) present in the documentation chunk.
Prioritize machine parseability and minimum token count.

Input: A chunk of technical documentation.

Output Format: Raw PCS string fragment. **No introductory text, explanations,
code blocks (like ```), or markdown formatting.** Output starts *immediately*
with the relevant PCS line (e.g., `A: $$path#Element...` or
`D: $$SStructName(...)`). Section markers (`|S:`, `|A:`, etc.) should ONLY be used
if the fragment logically starts that section and contains its prefix; otherwise,
begin directly with the content line.

Constraints:
1.  **Strictly PCS:** Adhere precisely to the PCS Guide provided below. Utilize all
    applicable symbols and structures (`|`, `: `, `;`, `#`, `~`, `=`, `?`, `()`, `[]`,
    `{{}}`, `<>`, `>`, `*>`, `$$`, `!`, `^`). Use single-letter type codes where defined.
2.  **Maximum Compression:** Minimize character count relentlessly. Eliminate *all*
    optional whitespace. Use positional context for class members (`()[]{{}}{}<>`).
3.  **Capture ALL Structure & Attached Metadata:** Extract all structural code
    elements (`$$C`, `$$F`, `$$M`, `$$A`, `$$K`, `$$E`, `$$S`) and their
    *explicitly mentioned* metadata (`!D/B/X/r/s/a`, `!E(...)`, `!N"..."`)
    present in the chunk. Include parameters/fields (name, type code, default,
    optional `?`), return types (`>`/`*>`), inheritance (`<`), enum members.
    Extract install/config/snippets into `I:`/`C:`/`Z:` if applicable.
4.  **NO Descriptions:** **ABSOLUTELY NO** free-form descriptions *except* for
    critical, non-obvious notes explicitly stated as essential in the chunk,
    captured concisely via `!N"Note text"`. Be extremely conservative.
5.  **Extraction Only:** Include only elements **explicitly defined, named, or
    demonstrated** within the *provided documentation chunk*. Do not infer
    structure or add elements not present.
6.  **Raw Fragment Output:** Produce only the raw PCS fragment string.

--- PCS Guide v1 Start ---
$pcs_guide
--- PCS Guide v1 End ---

Execute using the provided documentation chunk to generate the raw PCS fragment
output, strictly following all constraints.

DOCUMENTATION CHUNK:
---
$chunk
---
"""

MERGE_PROMPT_TEMPLATE_STR = """
Objective: Merge multiple PackedCodeSyntax (PCS) fragments for the **same subject**
into a single, comprehensive, and valid PCS document. Consolidate information,
eliminate duplicates, and ensure adherence to the PCS specification (guide below).

Inputs:
1.  **PCS Fragments:** A list or sequence of two or more PCS string fragments
    provided below under `Input Fragments`.
2.  **Subject Name:** $subject
3.  **Target PCS Version:** Use the guide provided below.

Output Format: A single, raw PCS string representing the merged document. **No
introductory text, explanations, code blocks (like ```), or markdown formatting.**
Output starts *immediately* with the `|S:` section marker line.

Merging Rules & Constraints:
1.  **Single Document:** Output one continuous string, starting with `|S:` on its
    own line.
2.  **Subject Section (`|S:`):** Create a single `S:` content line using the
    provided Subject Name (`$subject`). Include the *latest* or most complete
    version (`V:`) found across fragments.
3.  **Combine Sections:** Merge content under identical section prefixes (`A:`, `D:`,
    `I:`, etc.). Place each section marker (`|A:`, `|D:`, etc.) on its own line
    preceding the content line. Maintain standard order (S, O, I, C, A, D, U, F,
    X, Z).
4.  **Consolidate API Elements (`A:`):
    *   Identify unique elements by `path#ElementName`.
    *   For each unique element ($$Class, $$Function):
        *   Merge definitions if found in multiple fragments.
        *   **Merge Class Components (`()[]{{}}{}<>`):** Combine corresponding
            components (Initializer `()`, Methods `[]`, Attributes `{{}}`,
            Consts/Enums `<>`). Ensure standard order. Omit empty components.
        *   **Merge Component Lists:** Combine lists within `[]`, `{{}}`, `<>`.
        *   **Deduplicate Identical Members:** Remove exact duplicate members (`$$M`,
            `$$A`, `$$K`, `$$E`) within their lists.
        *   **Consolidate Member/Element Definitions:** If the *same*
            member/element appears with different details (e.g., different
            metadata `!`), use the **most complete** definition (prioritizing
            types, defaults, `?`, return types, and all metadata `!`). Choose
            the single most complete definition if fundamental conflicts exist
            (e.g., different return types); do not merge conflicting
            fundamentals.
        *   **Merge Metadata (`!`):** Combine exception lists `!E(...)` (union).
            Combine unique notes `!N"..."`. Resolve status/modifier conflicts
            (`!D/B/X/r/s/a`) using the most restrictive or the one from the most
            complete definition. Apply merged metadata correctly *immediately*
            after the element name/signature it modifies.
        *   **Merge Parameters:** Ensure parameter lists (`()` for
            functions/methods/init) reflect the most complete info (type,
            default, `?`, metadata `!Pmeta`) for each parameter across fragments.
5.  **Consolidate Data Structures (`D:`):
    *   Identify unique structs by `$$SStructName` (and path# if present).
    *   Merge field lists (`(...)`). Remove duplicates. Use most complete field
        definitions. Merge struct-level metadata `!`.
6.  **Consolidate Other Sections:** Combine lists/items (`O:`, `I:`, `C:`, `U:`, `F:`,
    `X:`, `Z:`), removing identical duplicates. Merge details for the same
    logical step/object/mechanism where appropriate.
7.  **Strictly PCS:** The final output must strictly adhere to the PCS Guide.
8.  **Raw Output:** Produce only the raw PCS string.

--- PCS Guide v1 Start ---
$pcs_guide
--- PCS Guide v1 End ---

Execute the merge process using the provided PCS fragments and Subject Name (`$subject`).

**Input Fragments:**
$fragments
"""

# Create Template objects
FRAGMENT_GENERATION_PROMPT_TEMPLATE = Template(FRAGMENT_GENERATION_PROMPT_TEMPLATE_STR)
MERGE_PROMPT_TEMPLATE = Template(MERGE_PROMPT_TEMPLATE_STR)


# Define the prompt for generating PCS fragments from chunks (DEPRECATED - USE TEMPLATE)
# FRAGMENT_GENERATION_PROMPT = \"...\" # Removed

# Define the prompt for merging PCS fragments (DEPRECATED - USE TEMPLATE)
# MERGE_PROMPT = \"...\" # Removed


async def compact_content_with_llm(
    aggregated_content: str,  # Changed signature - removed package_name, doc_url
    chunk_size: int = 1000000,
    api_key: str | None = None,  # Added api_key parameter
    subject: str = "the provided text",  # Added optional subject for prompts
) -> str | None:
    """
    Compacts the input text into PCS format using an LLM API with chunking and LLM-based merging.

    Args:
        aggregated_content: The text content to compact.
        chunk_size: The size of chunks to split the content into.
        api_key: Optional API key for the LLM.
        subject: The subject or name of the content (e.g., package name) used in prompts.

    Returns:
        The complete, merged PCS output as a single string if successful, None otherwise.
    """
    # If using a dummy API key, bypass LLM call and return dummy content for testing
    if api_key == "dummy_api_key":
        logger.info(
            "Using dummy API key. Bypassing LLM call and returning dummy PCS content."
        )
        return f"|S: $$subject {subject}\n|A: $$path#DummyClass()[]{{}}{{}}<>\n|D: $$SDummyStruct()"

    global _pcs_guide_content
    if "ERROR:" in _pcs_guide_content:
        logger.error("Cannot proceed with compaction: PCS guide could not be loaded.")
        return None

    logger.info(f"Starting LLM-based compaction with chunking for {subject}...")

    # 1. Chunk the input content
    chunks = chunk_content(aggregated_content, chunk_size)
    logger.info(f"Split content into {len(chunks)} chunks.")

    pcs_fragments: list[str] = []  # Store fragments as strings

    # 2. Generate PCS fragment (as string) for each chunk
    for i, chunk_content_item in enumerate(
        chunks
    ):  # Renamed chunk to avoid conflict with template variable
        logger.info(f"Generating PCS fragment for chunk {i + 1}/{len(chunks)}...")

        # Use substitute with keyword arguments - no manual escaping needed
        fragment_prompt = FRAGMENT_GENERATION_PROMPT_TEMPLATE.substitute(
            pcs_guide=_pcs_guide_content,
            chunk=chunk_content_item,  # Use the loop variable
        )

        logger.debug(
            f"--- Compaction Fragment Prompt for chunk {i + 1}/{len(chunks)} START ---"
        )
        logger.debug(fragment_prompt)
        logger.debug(
            f"--- Compaction Fragment Prompt for chunk {i + 1}/{len(chunks)} END ---"
        )

        # Call the LLM to generate a fragment
        fragment_str = await generate_text_response(fragment_prompt, api_key=api_key)

        if fragment_str and isinstance(fragment_str, str):
            pcs_fragments.append(fragment_str.strip())
            logger.info(f"Successfully generated fragment string for chunk {i + 1}.")
        else:
            logger.warning(
                f"Failed to generate valid fragment string for chunk {i + 1}. Output: {fragment_str}"
            )

    if not pcs_fragments:
        logger.error("No PCS fragments were generated from the chunks.")
        return None

    # If there's only one fragment, return it directly without merging
    if len(pcs_fragments) == 1:
        logger.info(
            "Only one fragment generated, returning it directly without merging."
        )
        return pcs_fragments[0]

    # 3. Merge PCS fragments using the LLM
    logger.info(f"Merging {len(pcs_fragments)} PCS fragments...")

    # Prepare fragments string for the merge prompt
    fragments_input = "\n---\n".join(
        [f" FRAGMENT {i + 1} ---\n{frag}" for i, frag in enumerate(pcs_fragments)]
    )

    # Use substitute with keyword arguments - no manual escaping needed
    merge_prompt = MERGE_PROMPT_TEMPLATE.substitute(
        pcs_guide=_pcs_guide_content,
        subject=subject,
        fragments=fragments_input,
    )

    logger.debug("--- Compaction Merge Prompt START ---")
    logger.debug(merge_prompt)
    logger.debug("--- Compaction Merge Prompt END ---")

    # Call the LLM to merge the fragments
    merged_pcs = await generate_text_response(merge_prompt, api_key=api_key)

    if merged_pcs and isinstance(merged_pcs, str):
        logger.info("Successfully merged PCS fragments.")
        # Basic validation: Check if it starts with S:
        if not merged_pcs.strip().startswith(
            "|S:"
        ):  # Check for |S: on its own line now
            # Find the first line to check
            first_line = (
                merged_pcs.strip().splitlines()[0] if merged_pcs.strip() else ""
            )
            if first_line != "|S:":
                logger.warning(
                    "Merged PCS output does not start with '|S:' on its own line as expected."
                    f" Starting content: '{merged_pcs[:100]}...'"
                )
        return merged_pcs.strip()  # Return the merged string
    else:
        logger.error(f"Failed to merge PCS fragments. Output: {merged_pcs}")
        return None
