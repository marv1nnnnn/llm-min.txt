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
Role: Expert curator extracting Atomic Information Units (AIUs).
Goal: Create structured text for another LLM to understand library usage for practical tasks. Focus on what the library *does* and *how to use it*, not exhaustive API details. Output AIUs strictly in the format below.

Input: Technical documentation chunk.

Output: ONLY AIU blocks (`#AIU#...#END_AIU`). No other text, explanations, or markdown. If no AIUs, output nothing.

AIU Format:
- Delimiters: `#AIU#...#END_AIU`.
- Fields: Separated by `;`, format `abbrev:value`.
   - id: Unique AIU identifier.
   - typ: AIU Type (Feat:Feature, CfgObj:ConfigObject, APIEnd:API_Endpoint, Func:Function, ClsMth:ClassMethod, DataObj:DataObject, ParamSet:ParameterSet, Patt:Pattern, HowTo, Scen:Scenario, BestPr:BestPractice, Tool).
   - name: Canonical name.
   - purp: Concise purpose (string, may contain spaces).
   - in: Input params/configs list. Format: `[{p:name;t:type;d:desc;def:val;ex:ex_val}]`.
       - p: Param name.
       - t: Param type (e.g., int, str, list_str, dict, AIU_id, `T`/`F` for bool).
       - d: Brief description.
       - def: Default value (if any; `T`/`F` for bool).
       - ex: Concise example value/structure (`T`/`F` for bool).
   - out: Output/return fields list. Format: `[{f:name;t:type;d:desc}]`.
       - f: Field/output name.
       - t: Output type (e.g., AIU_id, `T`/`F` for bool).
       - d: Brief description.
   - use: Minimal code/config pattern for core usage. Use `{obj_id}` for related ID placeholders.
   - rel: Relationships list. Format: `[{id:related_id;typ:rel_type}]`.
       - id: Related AIU ID.
       - typ: Rel Type (U:USES, C:CONFIGURES, R:RETURNS, A:ACCEPTS_AS_INPUT, P:IS_PART_OF, I:INSTANCE_OF, HM:HAS_METHOD, HP:HAS_PATTERN, HwC:HELPS_WITH_COMPATIBILITY, HwP:HELPS_WITH_PERFORMANCE).
   - src: Source chunk identifier.

Example Output:
#AIU#id:example_id;typ:Feat;name:ExampleFeature;purp:"This is an example feature.";in:[{p:param1;t:str;d:A parameter.;def:default;ex:example_val}];out:[{f:result;t:T;d:The result.}];use:"example_function({obj_id})";rel:[{id:related_id;typ:U}];src:"chunk_source_1"#END_AIU

Constraints:
1.  Strict Format: Adhere precisely to AIU Format. Output ONLY AIU blocks.
2.  Prioritize Practical, High-Level AIUs: Focus on `Feat`, `HowTo`, `Patt`, `Scen`. Their `use` field needs clear, runnable code snippets, self-contained or `rel` to essentials.
3.  Selective API Detail: Extract only details essential for an LLM to decide *what to do* or *how to do it practically*. LLM_MIN.TXT is a usage guide, not a full API spec.
    - For `ClsMth`/`Func`: `purp` must be user-goal focused. `in` lists only common user-changed params (summarize/omit others). `out` focuses on common workflow outputs.
    - For `CfgObj`: `in` lists only common/impactful params, with practical `ex`.
    - Avoid AIUs for internal/rarely-used APIs unless key for user-facing `Feat`/`Patt`/`HowTo`.
4.  Strategic `rel` Linking: Be selective. Prioritize `rel` links showing:
    - `Patt`/`HowTo`/`Scen` *using* a core `Feat`/`CfgObj`.
    - Essential configurations for a feature.
    - Components in a common, user-facing workflow.
    - Avoid `rel` to low-level internals not directly used/configured by users.
5.  Extraction Only: Only info explicitly from the chunk. No inference.
6.  Conciseness & Clarity: Keep `purp`, descriptions (`d`), and examples (`ex`) concise. `name` must be canonical.
7.  Source Reference (`src`): Always include the original chunk ID.
8.  Curated Selectivity: Fewer, impactful AIUs over exhaustive minor details. Summarize many small, related items under one abstract `Feat` or `Patt`.
9.  Composite Patterns (`Patt`, `HowTo`, `Scen`, `BestPr`):
    - If chunk describes a multi-step pattern, advanced scenario, or best practice, extract as a `Patt`, `HowTo`, `Scen`, or `BestPr` AIU.
    - AIU needs: unique `id`, concise `name`, clear `purp` (overall goal), `use` (complete, cohesive code/config or summary).
    - `rel` must link to key constituent AIUs, explaining composition.
10. Minimize Whitespace: Use minimal whitespace within `[]` and `{}` (e.g., `[{p:val}]`), and around `;`. For booleans, use `T` or `F`.

Execute on DOCUMENTATION CHUNK. Strictly follow all constraints.

DOCUMENTATION CHUNK:
---
$chunk
---
"""

MERGE_PROMPT_TEMPLATE_STR = """
Objective: Process a list of raw AIU strings to produce a refined, cohesive, and less redundant set of AIUs. Then, assemble these refined AIUs into a single structured text string adhering strictly to the specified Structured Text Structure.

Input:
- A list of individual AIU strings (variable: raw_aiu_strings). Each is a complete, compressed #AIU#...#END_AIU# block.
- The LLM_MIN.TXT Structure for Assembly (provided below).

Output:
A single, raw structured text string. ABSOLUTELY NO other text, explanations, or markdown. Output starts with `#LIB...`.

Core Tasks for AIU Refinement (Before Final Assembly):

1.  **Identify and Handle Duplicates/Near-Duplicates:**
    *   **Definition of Duplicate:** AIUs with identical `id` fields are direct duplicates. AIUs with highly similar `name`, `typ`, and `purp` fields, and very similar `use` field content, should be considered semantic duplicates, even if their `id` or `src` differ.
    *   **Action for Exact ID Duplicates:** If multiple AIUs have the exact same `id`, select the one that appears to be most complete or best described (e.g., longer `purp`, more detailed `use`). Discard the others.
    *   **Action for Semantic Duplicates:**
        *   If one is clearly a subset or less detailed version of another, discard the less detailed one. Keep the more comprehensive one.
        *   If they offer slightly different but complementary details in `purp` or `use`, attempt to MERGE them into a single, more comprehensive AIU.
            *   **Merging Strategy:** Choose one AIU as the base (preferably the one with a more canonical `name` or appearing earlier in the input).
            *   Retain its `id`, `name`, and `typ`.
            *   Synthesize a combined `purp` that incorporates key information from both.
            *   Synthesize a combined `use` field that is the most comprehensive or best example.
            *   Merge their `in`, `out`, and `rel` lists, avoiding duplicate entries within these lists. For `rel` lists, if both AIUs pointed to the same related ID, ensure it only appears once in the merged list.
            *   The `src` field for a merged AIU can list both source IDs if different (e.g., `src:"chunk_A,chunk_B"`), or pick the primary one.
        *   **Update Relationships:** If an AIU is discarded or merged, any other AIUs that had `rel` entries pointing to the discarded/merged AIU's original `id` MUST be updated to point to the `id` of the AIU that was kept or became the merged result. This is CRITICAL.

2.  **Identify and Enhance Complementary AIUs (Potential Hierarchical Linking):**
    *   **Definition:** Look for groups of AIUs where some represent granular components (e.g., several `Func` or `ClsMth` AIUs) that logically support or are used by a higher-level AIU (e.g., a `Patt`, `HowTo`, or `Feat`).
    *   **Action:**
        *   If a clear higher-level AIU already exists that describes the overarching concept, ensure its `rel` field correctly links to these supporting granular AIUs (e.g., using `typ:U` (USES) or `typ:P` (IS_PART_OF)). Add these relationships if missing.
        *   If no such higher-level AIU exists but a clear pattern of usage among several granular AIUs is evident (e.g., "function A is often called, then function B, to achieve X"), consider if a NEW `Patt` or `HowTo` AIU should be synthesized to describe this combined usage.
            *   The new AIU's `id` must be unique.
            *   Its `name` and `purp` should describe the combined pattern/goal.
            *   Its `use` field should demonstrate the sequence or combination.
            *   Its `rel` field must link to the constituent granular AIUs.
            *   Its `src` can be a composite of the sources of its constituents.
        *   This step should be applied conservatively to avoid creating spurious AIUs. Focus on clear, common combinations.

3.  **Review and Consolidate Relationships (`rel` field):**
    *   After deduplication and potential merging/linking, review the `rel` fields of all retained/new AIUs.
    *   Ensure `rel` entries point to valid, existing AIU `id`s within the refined set.
    *   Ensure relationship types (`rel.typ`) are logical (e.g., a `Patt` might USE (`U`) a `Func`).

Assembly Instructions (After AIU Refinement):
1.  **Adherence:** Strictly follow the "Structured Text Structure for Assembly" below using the REFINED set of AIUs.
2.  **Header:** Generate the header line using `llm-min`, `1.0`, and the current UTC timestamp (format: `YYYY-MM-DDTHH:mm:ssZ`).
3.  **Schema:** Copy the "Schema Definition Block" LITERALLY as provided.
4.  **AIU Concatenation:** Insert ALL REFINED AIUs, in a logical order (e.g., grouping related AIUs if possible, or maintaining original relative order where sensible), between the `#AIU_LIST_BEGIN` and `#AIU_LIST_END` markers. Ensure each AIU is correctly formatted.
5.  **Raw Output Only:** The final output must be only the assembled LLM_MIN.TXT string.

--- Structured Text Structure for Assembly Start ---
The final output string must be constructed as follows:

PART 1: Header Line
`#LIB:llm-min#VER:1.0#DATE:YYYY-MM-DDTHH:mm:ssZ`
(Replace `YYYY-MM-DDTHH:mm:ssZ` with the current UTC timestamp)

PART 2: Schema Definition Block (COPY THIS LITERALLY)
#SCHEMA_DEF_BEGIN
AIU_FIELDS:id;typ;name;purp;in;out;use;rel;src
IN_FIELDS:p;t;d;def;ex
OUT_FIELDS:f;t;d
REL_FIELDS:id;typ
#SCHEMA_DEF_END

PART 3: AIU List Block
#AIU_LIST_BEGIN
(Insert all REFINED AIU strings here, one after another. Each AIU must be a complete #AIU#...#END_AIU# block.)
#AIU_LIST_END
--- Structured Text Structure for Assembly End ---

Input Raw AIU Strings (variable: raw_aiu_strings):
$raw_aiu_strings
"""
# Create Template objects
FRAGMENT_GENERATION_PROMPT_TEMPLATE = Template(FRAGMENT_GENERATION_PROMPT_TEMPLATE_STR)
MERGE_PROMPT_TEMPLATE = Template(MERGE_PROMPT_TEMPLATE_STR)


async def compact_content_to_structured_text(
    aggregated_content: str,
    chunk_size: int = 1000000,
    api_key: str | None = None,
    subject: str = "the provided text",
    model_name: str | None = None,
) -> str:
    """
    Orchestrates the compaction pipeline to generate structured text from input content.

    This function performs the following stages:
    Stage 0/1: Chunking and AIU Extraction using an LLM.
    Stage 2: Merging AIU strings using an LLM.

    Args:
        aggregated_content: The text content to process.
        chunk_size: The size of chunks for initial content splitting.
        api_key: Optional API key for the LLM used in Stage 1.
        subject: The subject or name of the content (e.g., package name) used in logging and prompts.
        model_name: Optional model name for the LLM.

    Returns:
        A string containing the serialized structured text content.
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
        return ""  # Return empty string if no AIUs were generated

    logger.info(f"Successfully extracted {len(aiu_strings)} AIU strings. Proceeding to merge.")

    # Join the individual AIU strings for the prompt input
    input_aiu_strings_for_prompt = "\n".join(aiu_strings)

    # Use the MERGE_PROMPT_TEMPLATE to construct the final merge prompt
    merge_prompt = MERGE_PROMPT_TEMPLATE.substitute(
       raw_aiu_strings=input_aiu_strings_for_prompt
    )

    logger.debug(f"--- AIU Merge Prompt START ---")
    logger.debug(merge_prompt)
    logger.debug(f"--- AIU Merge Prompt END ---")

    # 4. Call the LLM to merge the AIU strings
    # Note: The LLM is now only responsible for combining the pre-formatted AIUs
    # and adding the header/schema/list delimiters.
    merged_kb_content = await generate_text_response(merge_prompt, api_key=api_key, model_name=model_name)

    if merged_kb_content and isinstance(merged_kb_content, str):
        logger.info("Successfully merged AIU strings into a single structured text string.")
        # 5. Return the merged content
        return merged_kb_content.strip()
    else:
        logger.error(f"Failed to merge AIU strings. Output: {merged_kb_content}")
        return ""  # Return empty string or raise an error
