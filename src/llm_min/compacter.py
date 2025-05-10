import logging
from string import Template

# Import from .llm subpackage (now points to gemini via __init__.py)
from .llm import (
    chunk_content,
    generate_text_response,
)

# Import the new AIU processing function

logger = logging.getLogger(__name__)


# Function to read the PCS guide content directly from file
# Define the template for generating AIUs from chunks using string.Template syntax
FRAGMENT_GENERATION_PROMPT_TEMPLATE_STR = """
Objective: Act as an expert curator to extract Atomic Information Units (AIUs) from the provided documentation chunk. The primary goal is to create a KNOWLEDGE_BASE that enables another LLM to understand *how to use* the library for practical tasks and common scenarios, focusing on what the library *does* and *how to make it do things*, rather than exhaustively listing all API details. Represent each extracted AIU strictly in the compressed KNOWLEDGE_BASE AIU format defined below.

Input: A chunk of technical documentation.

Output Format: One or more AIU blocks. Crucially, the output must contain ONLY the AIU blocks, with absolutely no other text, explanations, code block formatting (like ```json or ```), or markdown outside of the `#AIU#...#END_AIU` delimiters. If no AIUs are found, output nothing.

Compressed AIU Format Guideline:
- Each AIU is delimited by `#AIU#...#END_AIU`.
- Within an AIU, fields are separated by `;` and have the format `abbrev:value`.
   - id: Unique identifier for the AIU.
   - typ: Type of the AIU. Abbreviated values:
       - Feature -> Feat
       - ConfigObject -> CfgObj
       - API_Endpoint -> APIEnd
       - Function -> Func
       - ClassMethod -> ClsMth
       - DataObject -> DataObj
       - ParameterSet -> ParamSet
       - Pattern -> Patt
       - HowTo -> HowTo
       - Scenario -> Scen
       - BestPractice -> BestPr
       - Tool -> Tool
   - name: Canonical name.
   - purp: Concise purpose description (string, may contain spaces).
   - in: List of input parameters/configurations. Each item is a dictionary. Minimize whitespace: `[{p:name;t:type;d:desc;def:val;ex:ex_val}]`.
       - p: Parameter name.
       - t: Parameter type (e.g., int, str, list_str, dict, an id of another AIU, or bool represented as `T`/`F`).
       - d: Brief description.
       - def: Default value (if any, `T`/`F` for booleans).
       - ex: Concise example value or structure (`T`/`F` for booleans).
   - out: List of outputs/return fields. Each item is a dictionary. Minimize whitespace: `[{f:name;t:type;d:desc}]`.
       - f: Field/output name.
       - t: Output type (can also be an id of another AIU or bool represented as `T`/`F`).
       - d: Brief description.
   - use: Minimal code/config pattern showing core usage. `{obj_id}` can be used as a placeholder for related object IDs.
   - rel: List of relationships to other AIUs. Each item is a dictionary. Minimize whitespace: `[{id:related_id;typ:rel_type}]`.
       - id: ID of the related AIU.
       - typ: Relationship type. Abbreviated values:
           - USES -> U
           - CONFIGURES -> C
           - RETURNS -> R
           - ACCEPTS_AS_INPUT -> A
           - IS_PART_OF -> P
           - INSTANCE_OF -> I
           - HAS_METHOD -> HM
           - HAS_PATTERN -> HP
           - HELPS_WITH_COMPATIBILITY -> HwC
           - HELPS_WITH_PERFORMANCE -> HwP
   - src: Source reference (original chunk source identifier).

Example of expected output (one or more AIU blocks, nothing else):
#AIU#id:example_id;typ:Feat;name:ExampleFeature;purp:"This is an example feature.";in:[{p:param1;t:str;d:A parameter.;def:default;ex:example_val}];out:[{f:result;t:T;d:The result.}];use:"example_function({obj_id})";rel:[{id:related_id;typ:U}];src:"chunk_source_1"#END_AIU

Constraints:
1.  Strict Format: Adhere precisely to the Compressed AIU Format Guideline provided above.
2.  Prioritize Practical Usage & High-Level AIUs: 
    - Actively identify and extract AIUs representing Features (`Feat`), How-To Guides (`HowTo`), Usage Patterns (`Patt`), and Scenarios (`Scen`). These are of highest importance.
    - The `use` field for these AIUs must contain clear, concise, and ideally runnable code snippets demonstrating practical application. These examples should be self-contained or clearly reference other essential AIUs via `rel`.
3.  Purpose-Driven Abstraction & API Detail Selectivity:
    - For each piece of information, ask: "Is this detail essential for another LLM to decide *what task to perform* or *how to execute that task at a practical, high-level*?" If not, it should be summarized or omitted. The KNOWLEDGE_BASE is a usage guide, not an exhaustive API specification.
    - For lower-level elements like ClassMethods (`ClsMth`) or Functions (`Func`): 
        - Focus their `purp` field on their *purpose in achieving a user-facing goal* or enabling a feature.
        - Their `in` field should only list parameters that a user *commonly needs to change or understand* for typical usage. Other parameters can be omitted or their presence generally noted in `purp` (e.g., "accepts various formatting options").
        - Their `out` field should similarly focus on return values/fields directly used in common workflows.
    - If documenting a ConfigObject (`CfgObj`), highlight only the most commonly used or impactful parameters in the `in` field, providing practical examples in `ex`.
    - Avoid creating AIUs for highly internal, deeply nested, or rarely used API components unless they are truly essential for understanding a key user-facing `Feat`, `Patt`, or `HowTo`.
4.  Strategic Relationship (`rel`) Linking:
    - Be selective about `rel` links. Prioritize relationships that:
        - Show how a `Patt`, `HowTo`, or `Scen` *uses* a core `Feat` or critical `CfgObj`.
        - Illustrate essential configurations needed for a feature.
        - Link components in a common, user-facing workflow.
    - Avoid creating `rel` links to very low-level internal methods or data objects if they aren't directly interacted with or configured by the user in typical scenarios or within a primary usage pattern.
5.  Extraction Only: Include only information explicitly defined, named, or demonstrated within the provided documentation chunk. Do not infer information or add elements not present.
6.  Conciseness & Clarity: Keep `purp`, brief descriptions (`d`), and examples (`ex`) concise and focused on practical understanding. The `name` should be canonical and recognizable.
7.  Source Reference (`src`): Include the original chunk source identifier in the `src` field.
8.  Curated Selectivity: Prefer fewer, more impactful AIUs that describe significant capabilities or usage patterns over an exhaustive list of minor details. If a chunk details many small, related items, consider if they can be summarized under a single, more abstract `Feat` or `Patt` AIU.
9.  Composite Patterns & Best Practices (`Patt`, `HowTo`, `Scen`, `BestPr`):
    - If the documentation chunk describes a multi-step usage pattern, advanced scenario, or best practice, extract it as a separate AIU of type `Patt`, `HowTo`, `Scen`, or `BestPr`.
    - The AIU should have a unique `id`, a concise `name`, a clear `purp` (explaining the overall goal of the pattern), and a `use` field containing the complete, cohesive code/config pattern or summary.
    - The `rel` field for these AIUs should clearly link to the key constituent AIUs (`Feat`, `CfgObj`, `ClsMth`, etc.) that are components of that pattern/scenario, explaining the composition.
10. Minimize Whitespace: Use minimal whitespace within list/dict structures (e.g., `[{p:val}]` not `[{p: val}]`) and around the `;` delimiter. For boolean values, use `T` or `F`.

Execute using the provided documentation chunk to extract AIUs and generate the output, strictly following all constraints.

DOCUMENTATION CHUNK:
---
$chunk
---
"""

MERGE_PROMPT_TEMPLATE_STR = """
Objective: Combine the provided individual AIU strings, which are focused on practical library usage and high-level features, into a single, cohesive KNOWLEDGE_BASE string. This string must strictly follow the KNOWLEDGE_BASE Format Guideline. The input AIU strings are already in the desired compressed format.

Input:
- A list of individual AIU strings, each already formatted according to the guideline's #AIU#...#END_AIU structure (including abbreviations, minimal whitespace, and a focus on practical usage).
- The KNOWLEDGE_BASE Format Guideline, including schema definitions and compression rules.

Output Format: A single, raw KNOWLEDGE_BASE string. No introductory text, explanations, code blocks (like ```), or markdown formatting. The output must start with the `#LIB...` header and include the schema definition and the merged AIU list.

Merging Rules & Constraints:
1.  **Strict Format:** Adhere precisely to the KNOWLEDGE_BASE Format Guideline.
2.  **Header:** Start the output with the `#LIB...` header. Use placeholders like `llm-min`, `1.0`, and the current timestamp (YYYY-MM-DDTHH:mm:ssZ) for LibraryName, Version, and Timestamp respectively.
3.  **Schema Definition:** Include the `#SCHEMA_DEF_BEGIN...#SCHEMA_DEF_END` block exactly as it appears in the provided guideline content (this will reflect the new compressed format).
4.  **AIU List:** Place all provided individual AIU strings within the `#AIU_LIST_BEGIN...#AIU_LIST_END` block.
5.  **Order:** Maintain the order of AIUs as provided in the input list.
6.  **Raw Output:** Produce only the raw KNOWLEDGE_BASE string.
7.  **Preserve Compression**: The input AIU strings are already compressed. Do not alter their internal structure, add whitespace, or expand abbreviations. Your role is to correctly assemble them into the final KNOWLEDGE_BASE structure.

--- KNOWLEDGE_BASE Format Guideline Start ---
$guideline
--- KNOWLEDGE_BASE Format Guideline End ---

Input AIU Strings (already in #AIU#...#END_AIU compressed format):
$aiu_strings
"""

# Create Template objects
FRAGMENT_GENERATION_PROMPT_TEMPLATE = Template(FRAGMENT_GENERATION_PROMPT_TEMPLATE_STR)
MERGE_PROMPT_TEMPLATE = Template(MERGE_PROMPT_TEMPLATE_STR)


async def compact_content_to_knowledge_base(
    aggregated_content: str,
    chunk_size: int = 1000000,
    api_key: str | None = None,
    subject: str = "the provided text",
    model_name: str | None = None,
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
        aiu_str = await generate_text_response(fragment_prompt, api_key=api_key, model_name=model_name)

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
    merged_kb_content = await generate_text_response(merge_prompt, api_key=api_key, model_name=model_name)

    if merged_kb_content and isinstance(merged_kb_content, str):
        logger.info("Successfully merged AIU strings into a single KNOWLEDGE_BASE string.")
        # 5. Return the merged content
        return merged_kb_content.strip()
    else:
        logger.error(f"Failed to merge AIU strings. Output: {merged_kb_content}")
        return "" # Return empty string or raise an error
