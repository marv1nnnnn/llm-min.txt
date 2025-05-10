import logging
from pathlib import Path  # Import Path
from string import Template

# Import from .llm subpackage (now points to gemini via __init__.py)
from .llm import (
    chunk_content,
    generate_text_response,
)

# Import the new AIU processing function
# from .aiu_processing import process_aius_stage_2 # Removed as LLM handles merging
# from .kb_serialization import serialize_knowledge_base # Removed as LLM handles serialization

logger = logging.getLogger(__name__)


# Function to read the PCS guide content directly from file
# Define the template for generating AIUs from chunks using string.Template syntax
FRAGMENT_GENERATION_PROMPT_TEMPLATE_STR = """
Objective: Extract Atomic Information Units (AIUs) from the provided documentation chunk and represent each strictly in the compressed KNOWLEDGE_BASE AIU format defined below.

Input: A chunk of technical documentation.

Output Format: One or more AIU blocks. Crucially, the output must contain ONLY the AIU blocks, with absolutely no other text, explanations, code block formatting (like ```json or ```), or markdown outside of the `#AIU#...#END_AIU` delimiters. If no AIUs are found, output nothing.

Compressed AIU Format Guideline:
- Each AIU is delimited by `#AIU#...#END_AIU`.
- Within an AIU, fields are separated by `;` and have the format `abbrev:value`.
   - id: Unique identifier for the AIU.
   - typ: Type of the AIU (e.g., Feature, ConfigObject, API_Endpoint, Function, ClassMethod, DataObject, ParameterSet, Pattern, HowTo, Scenario, BestPractice).
   - name: Canonical name.
   - purp: Concise purpose description (string, may contain spaces).
   - in: List of input parameters/configurations. Each item is a dictionary:
       - p: Parameter name.
       - t: Parameter type (e.g., int, str, bool, list_str, dict, or an id of another AIU representing an object type).
       - d: Brief description.
       - def: Default value (if any).
       - ex: Concise example value or structure.
   - out: List of outputs/return fields. Each item is a dictionary:
       - f: Field/output name.
       - t: Output type (can also be an id of another AIU like a DataObject).
       - d: Brief description.
   - use: Minimal code/config pattern showing core usage. {obj_id} can be used as a placeholder for related object IDs.
   - rel: List of relationships to other AIUs. Each item is a dictionary:
       - id: ID of the related AIU.
       - typ: Relationship type (e.g., USES, CONFIGURES, RETURNS, ACCEPTS_AS_INPUT, IS_PART_OF, INSTANCE_OF).
   - src: Source reference (original chunk source identifier).

Example of expected output (one or more AIU blocks, nothing else):
#AIU#id:example_id;typ:Feature;name:ExampleFeature;purp:"This is an example feature.";in:[{p:param1;t:str;d:A parameter.;def:default;ex:example_value}];out:[{f:result;t:bool;d:The result.}];use:"example_function({obj_id})";rel:[{id:related_id;typ:USES}];src:"chunk_source_1"#END_AIU

Constraints:
1.  Strict Format: Adhere precisely to the Compressed AIU Format Guideline provided above.
2.  Extraction Only: Include only information explicitly defined, named, or
   demonstrated within the provided documentation chunk. Do not infer
   information or add elements not present.
3.  Conciseness: Keep PURPOSE, brief descriptions, and examples concise.
4.  Relationships: Identify and list relationships to other potential AIUs mentioned in the text using the rel field. Use appropriate relationship types.
5.  Source Reference: Include the original chunk source identifier in the src field.
6.  Multiple AIUs: If a single chunk describes multiple distinct AIUs, output multiple AIU blocks sequentially.
7.  Composite Patterns & Best Practices: If the documentation chunk describes a multi-step usage pattern, advanced scenario, or best practice (such as a code sample, workflow, or recommended configuration), extract it as a separate AIU of type Pattern, HowTo, Scenario, or BestPractice. 
    - The AIU should have a unique id, a concise name, a clear purpose, and a use field containing the code/config pattern or summary.
    - Use the rel field to link to all atomic AIUs (features, classes, methods, etc.) involved in the pattern.
    - This applies universally, regardless of the domain or technology.

Execute using the provided documentation chunk to extract AIUs and generate the output, strictly following all constraints.

DOCUMENTATION CHUNK:
---
$chunk
---
"""

MERGE_PROMPT_TEMPLATE_STR = """
Objective: Combine the provided individual AIU strings, generated from different chunks of the same document, into a single, cohesive KNOWLEDGE_BASE string that strictly follows the KNOWLEDGE_BASE Format Guideline provided below.

Input:
- A list of individual AIU strings, each already formatted according to the guideline's #AIU#...#END_AIU structure.
- The KNOWLEDGE_BASE Format Guideline, including schema definitions.

Output Format: A single, raw KNOWLEDGE_BASE string. No introductory text, explanations, code blocks (like ```), or markdown formatting. The output must start with the `#LIB...` header and include the schema definition and the merged AIU list.

Merging Rules & Constraints:
1.  **Strict Format:** Adhere precisely to the KNOWLEDGE_BASE Format Guideline.
2.  **Header:** Start the output with the `#LIB...` header. Use placeholders like `llm-min`, `1.0`, and the current timestamp (YYYY-MM-DDTHH:mm:ssZ) for LibraryName, Version, and Timestamp respectively.
3.  **Schema Definition:** Include the `#SCHEMA_DEF_BEGIN...#SCHEMA_DEF_END` block exactly as it appears in the provided guideline content.
4.  **AIU List:** Place all provided individual AIU strings within the `#AIU_LIST_BEGIN...#AIU_LIST_END` block.
5.  **Order:** Maintain the order of AIUs as provided in the input list.
6.  **Raw Output:** Produce only the raw KNOWLEDGE_BASE string.

--- KNOWLEDGE_BASE Format Guideline Start ---
$guideline
--- KNOWLEDGE_BASE Format Guideline End ---

Input AIU Strings (already in #AIU#...#END_AIU format):
$aiu_strings
"""

# Create Template objects
FRAGMENT_GENERATION_PROMPT_TEMPLATE = Template(FRAGMENT_GENERATION_PROMPT_TEMPLATE_STR)
MERGE_PROMPT_TEMPLATE = Template(MERGE_PROMPT_TEMPLATE_STR)


# Define the prompt for generating PCS fragments from chunks (DEPRECATED - USE TEMPLATE)
# FRAGMENT_GENERATION_PROMPT = \"...\" # Removed

# Define the prompt for merging PCS fragments (DEPRECATED - USE TEMPLATE)
# MERGE_PROMPT = \"...\" # Removed


async def compact_content_to_knowledge_base(
    aggregated_content: str,
    chunk_size: int = 1000000,
    api_key: str | None = None,
    subject: str = "the provided text",
) -> str:
    """
    Orchestrates the compaction pipeline to generate a knowledge base from input content.

    This function performs the following stages:
    Stage 0/1: Chunking and AIU Extraction using an LLM.
    Stage 2: Merging AIU strings using an LLM.

    Args:
        aggregated_content: The text content to process.
        chunk_size: The size of chunks for initial content splitting.
        api_key: Optional API key for the LLM used in Stage 1.
        subject: The subject or name of the content (e.g., package name) used in logging and prompts.

    Returns:
        A string containing the serialized knowledge base content.
    """
    # If using a dummy API key, bypass LLM call and return dummy content for testing
    if api_key == "dummy_api_key":
        logger.info("Using dummy API key. Bypassing LLM call and returning dummy KNOWLEDGE_BASE content.")
        # Construct a dummy KNOWLEDGE_BASE string that conforms to the full format
        dummy_header = "#LIB:llm-min#VER:1.0#DATE:2023-01-01T00:00:00Z" # Use a fixed timestamp for dummy data
        dummy_schema = """#SCHEMA_DEF_BEGIN
            # Define the schema for AIUs here
            # Example:
            # AIU_TYPE: Feature
            # FIELDS: id, typ, name, purp, in, out, use, rel, src
            # RELATIONSHIP_TYPE: USES, CONFIGURES, RETURNS, ACCEPTS_AS_INPUT, IS_PART_OF, INSTANCE_OF
            #SCHEMA_DEF_END"""
        dummy_aiu_list = """
        #AIU#id:dummy_id_1;typ:Feature;name:DummyFeature1;purp:"This is dummy feature 1.";in:[];out:[];use:"dummy_usage1()";rel:[];src:"dummy_source_chunk_1"#END_AIU
        #AIU#id:dummy_id_2;typ:Feature;name:DummyFeature2;purp:"This is dummy feature 2.";in:[];out:[];use:"dummy_usage2()";rel:[];src:"dummy_source_chunk_2"#END_AIU"""

        return f"""{dummy_header}
            {dummy_schema}
            #AIU_LIST_BEGIN
            {dummy_aiu_list}
            #AIU_LIST_END"""


    logger.info(f"Starting LLM-based AIU extraction with chunking for {subject}...")

    # 1. Chunk the input content
    chunks = chunk_content(aggregated_content, chunk_size)
    logger.info(f"Split content into {len(chunks)} chunks.")

    aiu_strings: list[str] = []  # Store AIU strings

    # 2. Generate AIU string for each chunk
    for i, chunk_content_item in enumerate(chunks):
        logger.info(f"Generating AIU for chunk {i + 1}/{len(chunks)}...")

        # Use substitute with keyword arguments - no manual escaping needed
        fragment_prompt = FRAGMENT_GENERATION_PROMPT_TEMPLATE.substitute(
            chunk=chunk_content_item,
        )

        logger.debug(f"--- AIU Extraction Prompt for chunk {i + 1}/{len(chunks)} START ---")
        logger.debug(fragment_prompt)
        logger.debug(f"--- AIU Extraction Prompt for chunk {i + 1}/{len(chunks)} END ---")

        # Call the LLM to generate an AIU string
        aiu_str = await generate_text_response(fragment_prompt, api_key=api_key)

        if aiu_str and isinstance(aiu_str, str):
            aiu_strings.append(aiu_str.strip())
            logger.info(f"Successfully generated AIU string for chunk {i + 1}.")
        else:
            logger.warning(f"Failed to generate valid AIU string for chunk {i + 1}. Output: {aiu_str}")


    if not aiu_strings:
        logger.error("No AIU strings were generated from the chunks.")
        return "" # Return empty string if no AIUs were generated

    logger.info(f"Successfully extracted {len(aiu_strings)} AIU strings. Proceeding to merge.")

    # Read the content of the guideline file
    try:
        with open("assets/guideline.md", "r", encoding="utf-8") as f:
            guideline_content = f.read()
    except FileNotFoundError:
        logger.error("Guideline file not found at assets/guideline.md")
        return "" # Or raise an exception
    except Exception as e:
        logger.error(f"Error reading guideline file: {e}")
        return "" # Or raise an exception


    # Join the individual AIU strings for the prompt input
    input_aiu_strings_for_prompt = "\n".join(aiu_strings)

    # Substitute the template with the guideline and AIU strings
    # Need to extract the schema definition part from the guideline content
    schema_start = guideline_content.find("#SCHEMA_DEF_BEGIN")
    schema_end = guideline_content.find("#SCHEMA_DEF_END") + len("#SCHEMA_DEF_END")
    schema_def_content = guideline_content[schema_start:schema_end] if schema_start != -1 and schema_end != -1 else ""

    # Construct the final merge prompt including header, schema, and list delimiters
    # Use current timestamp for the header
    import datetime
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat().replace('+00:00', 'Z')
    header = f"#LIB:llm-min#VER:1.0#DATE:{timestamp}"

    # Use the MERGE_PROMPT_TEMPLATE to construct the final merge prompt
    merge_prompt = MERGE_PROMPT_TEMPLATE.substitute(
        guideline=guideline_content,
        aiu_strings=input_aiu_strings_for_prompt
    )

    logger.debug(f"--- AIU Merge Prompt START ---")
    logger.debug(merge_prompt)
    logger.debug(f"--- AIU Merge Prompt END ---")

    # 4. Call the LLM to merge the AIU strings
    # Note: The LLM is now only responsible for combining the pre-formatted AIUs
    # and adding the header/schema/list delimiters.
    merged_kb_content = await generate_text_response(merge_prompt, api_key=api_key)

    if merged_kb_content and isinstance(merged_kb_content, str):
        logger.info("Successfully merged AIU strings into a single KNOWLEDGE_BASE string.")
        # 5. Return the merged content
        return merged_kb_content.strip()
    else:
        logger.error(f"Failed to merge AIU strings. Output: {merged_kb_content}")
        return "" # Return empty string or raise an error
