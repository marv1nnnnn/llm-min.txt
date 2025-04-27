import logging
from typing import Optional, Dict, Any, List
import json
import os # Import os to construct file path

# Assuming an LLM utility function exists, e.g., in ../tools/llm_api.py
from .llm.gemini import chunk_content, generate_text_response # Import chunking and generic text response

logger = logging.getLogger(__name__)

# Determine the absolute path to the guide file relative to this script
_script_dir = os.path.dirname(os.path.abspath(__file__))
_guide_file_path = os.path.join(_script_dir, "..", "..", "shdf-guide.md")

# Function to read the SHDF guide content
def _load_shdf_guide(file_path: str = _guide_file_path) -> str:
    """Loads the SHDF guide content from the specified file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            # Read the guide and strip potential surrounding ```markdown blocks
            content = f.read().strip()
            if content.startswith('```') and content.endswith('```'):
                content = content[3:-3].strip()
            elif content.startswith('```md') and content.endswith('```'):
                 content = content[5:-3].strip()
            return content
    except FileNotFoundError:
        logger.error(f"SHDF guide file not found at {file_path}")
        return "ERROR: SHDF GUIDE FILE NOT FOUND."
    except Exception as e:
        logger.error(f"Error reading SHDF guide file at {file_path}: {e}")
        return f"ERROR: COULD NOT READ SHDF GUIDE FILE: {e}"

# Load the guide content once when the module is imported
_shdf_guide_content = _load_shdf_guide()

# Define the template for generating SHDF fragments from chunks
FRAGMENT_GENERATION_PROMPT_TEMPLATE = '''
Objective: Generate an ultra-dense technical API/Data Structure index fragment for {subject} in Symbolic Hierarchical Delimited Format (SHDF), extracted from the provided chunk of documentation. This is a fragment, so it does not need to be a complete SHDF document, but should contain valid SHDF elements for the content in this chunk. Maximize information density for machine parsing (e.g., by an LLM provided with the SHDF v3 Guide below). Assume well-named elements are self-explanatory. Output must be raw SHDF v3 string fragment, starting immediately with the relevant section prefix (e.g., A:, D:, etc.), no explanations or Markdown ```.

Input: A chunk of technical documentation for {subject}.
Output Format: Raw SHDF v3 string fragment adhering strictly to the guide below, containing elements found in this chunk.

--- SHDF v3 Guide Start ---
{shdf_guide}
--- SHDF v3 Guide End ---

Execute using the provided documentation chunk for {subject} to generate the raw SHDF v3 fragment output.
DOCUMENTATION CHUNK:
---
{chunk}
---
'''

# Define the template for merging SHDF fragments
MERGE_PROMPT_TEMPLATE = '''
Objective: Merge the provided SHDF v3 fragments into a single, coherent, and complete SHDF v3 document for {subject}. Ensure the output strictly adheres to the SHDF v3 Guide provided below. Combine elements from the fragments into their respective sections (A:, D:, O:, etc.), removing duplicates and resolving any inconsistencies. The output must be a raw SHDF v3 string, starting immediately with S:, no explanations or Markdown ```.

Input: A list of SHDF v3 fragments generated from chunks of documentation for {subject}.
Output Format: A single, raw SHDF v3 string adhering strictly to the guide below.

--- SHDF v3 Guide Start ---
{shdf_guide}
--- SHDF v3 Guide End ---

Execute using the provided SHDF fragments for {subject} to generate the single, merged, raw SHDF v3 output.
SHDF FRAGMENTS TO MERGE:
---
{fragments}
---
'''

# Define the prompt for generating SHDF fragments from chunks (DEPRECATED - USE TEMPLATE)
# FRAGMENT_GENERATION_PROMPT = "..." # Removed

# Define the prompt for merging SHDF fragments (DEPRECATED - USE TEMPLATE)
# MERGE_PROMPT = "..." # Removed

def compact_content_with_llm(
    aggregated_content: str, # Changed signature - removed package_name, doc_url
    chunk_size: int = 8000,
    api_key: Optional[str] = None, # Added api_key parameter
    subject: str = "the provided text" # Added optional subject for prompts
) -> Optional[str]:
    """
    Compacts the input text into SHDF format using an LLM API with chunking and LLM-based merging.

    Args:
        aggregated_content: The text content to compact.
        chunk_size: The size of chunks to split the content into.
        api_key: Optional API key for the LLM.
        subject: The subject or name of the content (e.g., package name) used in prompts.

    Returns:
        The complete, merged SHDF output as a single string if successful, None otherwise.
    """
    global _shdf_guide_content
    if "ERROR:" in _shdf_guide_content:
        logger.error("Cannot proceed with compaction: SHDF guide could not be loaded.")
        return None

    logger.info(f"Starting LLM-based compaction with chunking for {subject}...")

    # 1. Chunk the input content
    chunks = chunk_content(aggregated_content, chunk_size)
    logger.info(f"Split content into {len(chunks)} chunks.")

    shdf_fragments: List[str] = [] # Store fragments as strings

    # 2. Generate SHDF fragment (as string) for each chunk
    for i, chunk in enumerate(chunks):
        logger.info(f"Generating SHDF fragment for chunk {i+1}/{len(chunks)}...")
        # Format the prompt with the loaded guide, subject, and chunk
        fragment_prompt = FRAGMENT_GENERATION_PROMPT_TEMPLATE.format(
            shdf_guide=_shdf_guide_content,
            subject=subject, # Use subject arg
            chunk=chunk
        )

        # Call the LLM to generate a fragment (expecting a string), passing the API key
        fragment_str = generate_text_response(fragment_prompt, api_key=api_key)

        if fragment_str and isinstance(fragment_str, str):
            shdf_fragments.append(fragment_str.strip()) # Store as string and strip whitespace
            logger.info(f"Successfully generated fragment string for chunk {i+1}.")
        else:
            logger.warning(f"Failed to generate valid fragment string for chunk {i+1}. Output: {fragment_str}")

    if not shdf_fragments:
        logger.error(f"No SHDF fragments were generated for {subject}.")
        return None

    # 3. If only one chunk, return its fragment directly
    if len(shdf_fragments) == 1:
        logger.info(f"Only one chunk for {subject}, returning its SHDF fragment directly.")
        return shdf_fragments[0] # Return the single fragment string

    # 4. Merge SHDF fragments using the LLM (expecting a string)
    logger.info(f"Merging {len(shdf_fragments)} SHDF fragments for {subject} using LLM...")

    # Join fragments with a clear separator for the merge prompt
    fragments_input_str = "\n---\n".join(shdf_fragments)

    # Format the merge prompt
    merge_prompt = MERGE_PROMPT_TEMPLATE.format(
        shdf_guide=_shdf_guide_content,
        subject=subject, # Use subject arg
        fragments=fragments_input_str
    )

    # Call the LLM for merging (expecting final string), passing the API key
    merged_shdf_str = generate_text_response(merge_prompt, api_key=api_key)

    if merged_shdf_str and isinstance(merged_shdf_str, str):
        logger.info(f"Successfully merged SHDF fragments for {subject}.")
        return merged_shdf_str.strip() # Return the final merged string, stripped
    else:
        logger.error(f"LLM merging of SHDF fragments failed or returned invalid type for {subject}. Output: {merged_shdf_str}")
        return None