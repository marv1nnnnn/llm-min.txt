import logging
import re
from datetime import datetime, timezone
from string import Template  # We will use $variable for substitution in prompts
import os
import shutil

from .utils import count_tokens

# Assuming .llm.generate_text_response is your async function to call the LLM
# Assuming .llm.chunk_content is your utility for chunking large text
from .llm import chunk_content, generate_text_response

logger = logging.getLogger(__name__)

# --- SKF/1.4 LA PROMPTS (Language Agnostic - Sourced from prompt.txt) ---

# LLM Call 1: Glossary Generation (per chunk)
SKF_PROMPT_CALL1_GLOSSARY_STR = """
SYSTEM: You are an ultra-efficient Lexicographer AI. Your sole task is to scan the provided technical document CHUNK and extract an extremely dense GLOSSARY of *top-level, code-relevant technical entities* (main Components, Services, Modules, key DataTypes, Interfaces, Enums, standalone Functions, and important global Constants). Adhere strictly to the SKF/1.4 LA protocol. Your output should ONLY be the GLOSSARY items, each on a new line. Assign sequential `Gxxx` IDs starting from `G001` *for this chunk's output only*.

USER:
**TASK: Generate Local Entity Glossary Fragment from Document Chunk (Part 1 of IKM - SKF/1.4 LA)**

**OUTPUT SPECIFICATION (GLOSSARY ITEMS ONLY - LOCAL IDs FOR THIS CHUNK):**
*   Start your output *directly* with the first GLOSSARY item. NO IKM headers, NO section headers.
*   Format: `Gxxx:[TYP] EntityName - "Hyper-concise differentiating keywords." @DocRef`
    *   `Gxxx`: Sequential numeric ID (G001, G002...) **local to this chunk's output.**
    *   `[TYP]`: Abbreviated Type Code from SKF/1.4 LA Enum: `Component, DataType, Interface, Enum, Service, APIEndpoint, Function, Module, Library, Algorithm, Constant`. (Use `Component` for classes/structs, `DataType` for data-focused structures, `Function` for standalone functions).
    *   `EntityName`: Canonical name.
    *   `"Hyper-concise differentiating keywords"`: Max 3-5 keywords for programming relevance.
    *   `@DocRef`: Shortest possible documentation reference from THIS CHUNK that best identifies the entity's source (e.g., `@ClassName_docs`, `@config/feature_x_from_chunk`).
*   **PRIORITIZE:** Entities that are directly made available in an API (imported, instantiated, called), configured, or represent key data types in a public API, as described *in this chunk*.

**INSTRUCTIONS:**
1.  **Identify Top-Level Entities *within this chunk*:** Focus on distinct, programmatically significant components mentioned.
2.  **Ruthless Selection for Code Relevance:** Exclude purely conceptual or documentation-organizational items unless they map directly to a code component *explicitly detailed in this chunk*.
3.  **Extreme Conciseness & Chunk-Local IDs:** Ensure `Gxxx` are sequential (G001, G002...) *for your output from this chunk*.
4.  **One entry per line.**

**INPUT DOCUMENT CHUNK:**
```text
$input_document_text
```

INSTRUCTIONS (CONTINUED):
Begin generating ONLY the top-level GLOSSARY (Gxxx) entries for THIS CHUNK now.
"""
SKF_PROMPT_CALL1_GLOSSARY_TEMPLATE = Template(SKF_PROMPT_CALL1_GLOSSARY_STR)

# LLM Call 1.5: Glossary Consolidation
SKF_PROMPT_CALL1_5_MERGE_GLOSSARY_STR = """
SYSTEM: You are a Glossary Consolidator AI. Given several SKF glossary fragments (each containing Gxxx IDs local to that fragment), your task is to merge them into a single, globally consistent SKF Glossary. Resolve duplicate entities (same `EntityName` and similar context/DocRef/keywords) into one canonical entry. Re-number all Gxxx IDs to be sequential and globally unique (G001, G002, ...) in the final merged output. Maintain the exact SKF line format for glossary items. Your output should ONLY be the final list of merged and re-indexed glossary items.

USER:
**TASK: Consolidate and Finalize SKF Glossary Fragments into a Global Glossary (SKF/1.4 LA)**

**INPUT GLOSSARY FRAGMENTS (Concatenated, potentially separated by '--- FRAGMENT BREAK ---'):**
```text
$concatenated_glossary_fragments
```

INSTRUCTIONS:

Identify Duplicates: Entities with the same EntityName and broadly similar DocRef or keywords across different fragments are likely duplicates. Consider the context provided by @DocRef and keywords.

Canonicalize Duplicates: For each set of identified duplicates, create a single, canonical entry in your final output. Synthesize the most representative [TYP], EntityName, keywords, and @DocRef from the duplicates. If types conflict, choose the most encompassing or primary one (e.g., Component over DataType if it has operations).

Global Sequential Gxxx IDs: Assign new, globally unique, sequential Gxxx IDs (starting from G001) to all entities in the final merged glossary. Strive for G001, G002, etc. (Final sequential numbering will be ensured by the system if needed, but your consistent numbering is preferred.)

Output Format: Produce only the final list of merged glossary items, each on a new line, adhering to the SKF format: Gxxx:[TYP] EntityName - "Hyper-concise differentiating keywords." @DocRef. NO other text or headers.

Preserve Uniques: Ensure all unique entities from all fragments are present in the final output.

INSTRUCTIONS (CONTINUED):
Begin generating the consolidated and re-indexed global SKF Glossary now.
"""
SKF_PROMPT_CALL1_5_MERGE_GLOSSARY_TEMPLATE = Template(SKF_PROMPT_CALL1_5_MERGE_GLOSSARY_STR)

# LLM Call 2: Definitions & Interactions (Single Chunk Logic)
SKF_PROMPT_CALL2_DETAILS_SINGLE_CHUNK_STR = """
SYSTEM: You are a Knowledge Synthesizer AI with exceptional precision. Given a GLOBAL SKF GLOSSARY and a single DOCUMENT CHUNK, your task is to:
1. Create compact, highly accurate definitions for each top-level entity from the Glossary relevant to this document chunk. This includes its logical namespace path (relative to a stated `PrimaryNamespace`), critical public operations, key public attributes, and important constants. Bundle these on a single primary definition line per entity where feasible using SKF/1.4 LA.
2. Detail dynamic interactions found in this document chunk.
Adhere strictly to SKF/1.4 LA. Your output should ONLY be the DEFINITIONS and INTERACTIONS sections, including their headers if content exists. `Dxxx` and `Ixxx` IDs should be sequential starting from D001 and I001 respectively *for this chunk's output*.

USER:
**TASK: Generate SKF Definitions & Interactions from Single Document Chunk (Part 2 of IKM - SKF/1.4 LA)**

**INPUTS:**
1.  **SKF HIERARCHICAL GLOSSARY (GLOBAL & FINALIZED - Provided Below):** Contains globally unique `Gxxx` IDs and `EntityNames`. All type references MUST map to these `Gxxx` IDs or SKF primitives.
2.  **DOCUMENT CHUNK (Provided Below Glossary):** The single source material for analysis.
3.  **PrimaryNamespace for Scoping (from IKM Header):** `$primary_namespace`

**OUTPUT SPECIFICATION (DEFINITIONS and INTERACTIONS SECTIONS FOR THIS CHUNK):**
*   If DEFINITIONS items are found, start with the `# SECTION: DEFINITIONS (Prefix: D)` header, its format line, the `---` separator, then the D_ID items (starting D001 *for this chunk's output*).
*   If INTERACTIONS items are found, follow with the `# SECTION: INTERACTIONS (Prefix: I)` header, its format line, the `---` separator, then the I_ID items (starting I001 *for this chunk's output*).
*   If a section is empty, omit its header, format line, separator, and content entirely.

**SECTION FORMATS from SKF/1.4 LA Protocol (Reminder):**
`# SECTION: DEFINITIONS (Prefix: D)`
`# Format_PrimaryDef: Dxxx:Gxxx_Entity [DEF_TYP] [NAMESPACE "relative.path"] [OPERATIONS {op1:RetT(p1N:p1T); op2_static:RetT()}] [ATTRIBUTES {attr1:AttrT1("Def:Val","RO")}] [CONSTANTS {c1:ValT1("Val")}] ("Note")`
`#   DEF_TYP: Enum(CompDef, DTDef, IfceDef, EnmDef, ModDef)`
`#   NAMESPACE: Path relative to PrimaryNamespace. Use "." for direct under PrimaryNamespace. Omit if not applicable.`
`#   OPERATIONS: `OpName:ReturnType(param1Name:Param1Type, ...)`. `_static` suffix for static/class-level. Precise types: `List[T]`, `Map[K,V]`, `Opt[T]`, `Uni[T1,T2]`, `Stream[YieldT]`, `AsyncStream[YieldT]` (or `AGen[YieldT]`).`
`#   ATTRIBUTES: `AttrName:AttrType("Def:DefaultValue", "RO", "WO", "RW")`.`
`#   CONSTANTS: `ConstName:ConstType("Value")`.`
`# Format_Standalone_Relation_Attribute: Dxxx:Gxxx_Subject DEF_KEY Gxxx_Object_Or_Literal ("Note")`
`#   DEF_KEY: Enum(IMPLEMENTS, EXTENDS, USES_ALGORITHM, API_REQUEST, API_RESPONSE, PARAM_DETAIL)`
`# ---`

`# SECTION: INTERACTIONS (Prefix: I)`
`# Format: Ixxx:Source_Ref INT_VERB Target_Ref_Or_Literal ("Note_Conditions_Error(Gxxx_ErrorType)")`
`# INT_VERB Enum: INVOKES, USES_COMPONENT, AWAITS_INVOKE, PRODUCES_EVENT, CONSUMES_EVENT, TRIGGERS, CONFIGURED_BY, RAISES_ERROR(Gxxx_ErrorType), HANDLES_ERROR(Gxxx_ErrorType), READS_FROM, WRITES_TO, DATA_FLOW(SourceRef -> TargetRef)`
`# ---`

**INSTRUCTIONS:**
1.  **Reference GLOBAL GLOSSARY:** All `Gxxx` references are to IDs from INPUT 1.
2.  **Analyze DOCUMENT CHUNK:** Identify all relevant definitions and interactions *from this chunk*.
3.  **Primary Definition Line:** For each `Gxxx` from GLOSSARY detailed *in this chunk*, create its primary definition line, bundling its `[NAMESPACE]`, public `[OPERATIONS {}]`, key `[ATTRIBUTES {}]`, and `[CONSTANTS {}]`.
4.  **Import Paths (`[NAMESPACE]`):** Provide the module path relative to `PrimaryNamespace`.
5.  **Error Handling in Interactions:** If documentation in this chunk specifies that an operation can raise a particular named error/exception (`G_ID`), use `RAISES_ERROR(Gxxx_ErrorType)` and note the condition.
6.  **Validate Gxxx References & Selectivity & Brevity & Unique IDs (D001..., I001... *for this chunk's output*).**

**INPUT 1: SKF HIERARCHICAL GLOSSARY (GLOBAL & FINALIZED)**
```text
$skf_glossary_content
```

INPUT 2: DOCUMENT CHUNK
```text
$document_chunk
```

PrimaryNamespace for Scoping: $primary_namespace

INSTRUCTIONS (CONTINUED):
Begin generating the DEFINITIONS and INTERACTIONS sections for this document chunk. Output Dxxx/Ixxx IDs starting D001/I001 for this chunk's content.
"""
SKF_PROMPT_CALL2_DETAILS_SINGLE_CHUNK_TEMPLATE = Template(SKF_PROMPT_CALL2_DETAILS_SINGLE_CHUNK_STR)

# LLM Call 2: Definitions & Interactions (Iterative Logic for N > 1 Chunks)
SKF_PROMPT_CALL2_DETAILS_ITERATIVE_STR = """
SYSTEM: You are a Knowledge Extractor AI with exceptional precision. Your task is to analyze the CURRENT DOCUMENT CHUNK and identify **NEW Definitions and Interactions** related to entities in the GLOBAL SKF GLOSSARY. You will be given PREVIOUSLY EXTRACTED SKF Definitions & Interactions for context, to help you avoid duplicating information. Your output should ONLY contain items newly identified from the CURRENT CHUNK.

USER:
**TASK: Extract NEW SKF Definitions & Interactions from CURRENT Document Chunk (SKF/1.4 LA)**

**INPUTS:**
1.  **SKF HIERARCHICAL GLOSSARY (GLOBAL & FINALIZED - Provided Below):** Contains globally unique `Gxxx` IDs. All type references MUST map to these `Gxxx` IDs or SKF primitives. This is your primary reference for entities.
2.  **PREVIOUS CHUNKS' SKF DEFINITIONS & INTERACTIONS OUTPUT (CONTEXT ONLY - Provided Below Glossary):** This is the accumulated knowledge so far. Use this to understand what has already been documented. **DO NOT repeat items from this section unless the CURRENT CHUNK provides significant new details (e.g., new operations for an already defined Gxxx, a more complete namespace).**
3.  **CURRENT DOCUMENT CHUNK (Provided Below Previous Output):** The new source material for analysis.
4.  **PrimaryNamespace for Scoping (from IKM Header):** `$primary_namespace`

**OUTPUT SPECIFICATION (ONLY NEW DEFINITIONS and INTERACTIONS from CURRENT CHUNK):**
*   Generate SKF formatted D-items and I-items that are **newly found or significantly augmented** based *solely on the CURRENT DOCUMENT CHUNK*.
*   For any D-items or I-items you generate, use chunk-local sequential IDs starting from `D001` and `I001` *for your output from this current chunk only*. These IDs will be re-assigned globally later.
*   If DEFINITIONS items are found, start with the `# SECTION: DEFINITIONS (Prefix: D)` header, its format line, the `---` separator, then the D_ID items.
*   If INTERACTIONS items are found, follow with the `# SECTION: INTERACTIONS (Prefix: I)` header, its format line, the `---` separator, then the I_ID items.
*   If a section yields no new items from the CURRENT CHUNK, omit its header, format line, separator, and content.

**SECTION FORMATS from SKF/1.4 LA Protocol (Reminder):**
`# SECTION: DEFINITIONS (Prefix: D)`
`# Format_PrimaryDef: Dxxx:Gxxx_Entity [DEF_TYP] [NAMESPACE "relative.path"] [OPERATIONS {op1:RetT(p1N:p1T); op2_static:RetT()}] [ATTRIBUTES {attr1:AttrT1("Def:Val","RO")}] [CONSTANTS {c1:ValT1("Val")}] ("Note")`
`#   ... (all sub-formats and enums for DEFINITIONS)`
`# ---`

`# SECTION: INTERACTIONS (Prefix: I)`
`# Format: Ixxx:Source_Ref INT_VERB Target_Ref_Or_Literal ("Note_Conditions_Error(Gxxx_ErrorType)")`
`#   ... (all sub-formats and enums for INTERACTIONS)`
`# ---`

**INSTRUCTIONS FOR EXTRACTING FROM CURRENT CHUNK:**
1.  **Reference GLOBAL GLOSSARY:** All `Gxxx` entity references in your output MUST use IDs from INPUT 1.
2.  **Analyze CURRENT DOCUMENT CHUNK:** Identify definitions (namespaces, operations, attributes, constants for Gxxx entities) and interactions.
3.  **Focus on NEW Information:**
    *   **New `Gxxx` Primary Definitions:** If CURRENT CHUNK details a `Gxxx` *not yet having a primary definition line* in PREVIOUS OUTPUT (INPUT 2), create its new primary `Dxxx:Gxxx_Entity [DEF_TYP]...` line.
    *   **Augmentations to Existing `Gxxx`:** If CURRENT CHUNK reveals *new members* (operations, attributes, constants) or a more complete `[NAMESPACE]` for a `Gxxx` that *already has a primary definition line* in PREVIOUS OUTPUT:
        *   Create a D-line that *only includes these new/augmented details*. For example, if `G001` was defined with `op1` and CURRENT CHUNK adds `op2`, your D-line for `G001` might be `Dxxx:G001_EntityName [OPERATIONS {op2:RetT()}]`. (The system will merge this intelligently later).
    *   **New Standalone Facts/Interactions:** Add new `IMPLEMENTS`, `EXTENDS`, or new `INTERACTIONS` (`Ixxx` lines) found in CURRENT CHUNK that are not in PREVIOUS OUTPUT.
4.  **Local ID Sequencing:** Use `D001, D002...` and `I001, I002...` for the items you generate *from this chunk only*.
5.  **Avoid Duplicates:** Critically, **do not repeat identical facts or interactions already present in PREVIOUS CHUNK'S OUTPUT (INPUT 2).** Your goal is to provide only the delta from the CURRENT CHUNK.
6.  **Error Handling & Conditional Notes:** Capture specific error types (`Gxxx_ErrorType`) and conditions.

**INPUT 1: SKF HIERARCHICAL GLOSSARY (GLOBAL & FINALIZED)**
```text
$skf_glossary_content
```

INPUT 2: PREVIOUS CHUNK'S SKF DEFINITIONS & INTERACTIONS OUTPUT (CONTEXT ONLY)
```text
$previous_chunk_skf_details_content
```

INPUT 3: CURRENT DOCUMENT CHUNK (FOR ANALYSIS)
```text
$current_document_chunk
```

PrimaryNamespace for Scoping: $primary_namespace

INSTRUCTIONS (CONTINUED):
Begin generating ONLY THE NEW Definitions and Interactions sections based on the CURRENT DOCUMENT CHUNK. Use local Dxxx/Ixxx IDs for your output.
"""
SKF_PROMPT_CALL2_DETAILS_ITERATIVE_TEMPLATE = Template(SKF_PROMPT_CALL2_DETAILS_ITERATIVE_STR)

# LLM Call 3: Usage Patterns Generation (Single Chunk Logic)
SKF_PROMPT_CALL3_USAGE_SINGLE_CHUNK_STR = """
SYSTEM: You are a Workflow Illustrator AI. Given a GLOBAL SKF GLOSSARY, complete SKF DEFINITIONS & INTERACTIONS, and a single DOCUMENT CHUNK (containing usage examples, tutorials, or quick-start guides), your task is to identify and describe the *most critical and illustrative* USAGE_PATTERNS found in this chunk. These patterns must be concise, use correct hierarchical notation (`Gxxx` for top-level entities, `Gxxx.MemberName` for their operations/attributes), and accurately reflect common and important ways to use the described system/library, including setup and error handling if prominent. Adhere strictly to SKF/1.4 LA. Your output should ONLY be the USAGE_PATTERNS section, including its header if content exists.

USER:
**TASK: Generate Hierarchical SKF Usage Patterns from Single Document Chunk (Part 3 of IKM - Critical Examples - SKF/1.4 LA)**

**INPUTS:**
1.  **SKF HIERARCHICAL GLOSSARY (GLOBAL & FINALIZED - Provided Below):** Contains `Gxxx` IDs for top-level entities.
2.  **SKF HIERARCHICAL DEFINITIONS & INTERACTIONS (ALL ASSEMBLED - Provided Below):** Details members of `Gxxx` entities (operations, attributes, import paths), their relationships, and dynamic behaviors. This is CRUCIAL for constructing valid pattern steps.
3.  **DOCUMENT CHUNK (Portions relevant to usage, examples, tutorials - Provided Below Inputs 1 & 2):** The source material for usage patterns.

**OUTPUT SPECIFICATION (USAGE_PATTERNS SECTION ONLY):**
*   If USAGE_PATTERNS items are found, start with `# SECTION: USAGE_PATTERNS (Prefix: U)` header, its format line, the `---` separator, then `U_ID` items.
*   If no patterns are found, output `# No distinct critical usage patterns identified in this chunk.`
*   `U_Name` should be descriptive (e.g., `U_BasicCrawl`, `U_DeepCrawlSetup`). `U_Name.N` steps should be sequential starting from N=1 for each distinct pattern.

**SECTION FORMAT from SKF/1.4 LA Protocol (Reminder):**
`# SECTION: USAGE_PATTERNS (Prefix: U)`
`# Format: U_Name:PatternTitleKeyword`
`#         U_Name.N:[Actor_Or_Ref] ACTION_KEYWORD (Target_Or_Data_Involving_Ref) -> [Result_Or_State_Change_Involving_Ref]`
`# ACTION_KEYWORD Enum: CREATE (instance), CONFIGURE (object/settings), INVOKE (operation/method), GET_ATTR (read attribute/property), SET_ATTR (write attribute/property), PROCESS_DATA, CHECK_STATE, ITERATE (over a collection/stream, e.g., async for), RAISE_ERR, HANDLE_ERR(Gxxx_ErrorType)`
`# ---`

**INSTRUCTIONS:**
1.  **Focus on DOCUMENT CHUNK:** Extract usage patterns *only from the provided DOCUMENT CHUNK*.
2.  **Utilize Full Knowledge Context (Glossary, D&I):**
    *   Refer to top-level entities by `Gxxx` (from GLOSSARY).
    *   Refer to members (operations, attributes, constants) using `Gxxx.MemberName` (e.g., `G001.OpName`, `G003.AttrName`), ensuring these are consistent with the DEFINITIONS input.
    *   Pattern steps MUST be consistent with operation signatures (parameters, return types) and attribute types from DEFINITIONS.
3.  **Select MOST CRITICAL & ILLUSTRATIVE Patterns:**
    *   Prioritize patterns that demonstrate the **setup, invocation, and typical outcome of CORE FEATURES** of the library/system. For example, if features like "Deep Crawling," "Structured LLM Extraction," "Session Management," or "Basic Page Scraping" are highlighted or exemplified in THIS DOCUMENT CHUNK, strive to create a usage pattern for them.
    *   Include core "happy path" workflows.
    *   Include essential setup/configuration sequences for key components if they form a distinct usage pattern.
    *   Showcase interactions between several distinct `Gxxx` components if that's a common or important pattern.
    *   If documented in this chunk, include a prominent error handling flow.
    *   Avoid trivial patterns (e.g., getting/setting a single simple field unless it's part of a larger critical setup sequence).
4.  **Concrete Implementations in `CREATE` Steps:** If a pattern involves creating an object of an interface type (`[Ifce]`), the `CREATE` step must specify a concrete implementation `Gxxx` (a `[Component]` or `[DataType]`) of that interface, as identifiable from `IMPLEMENTS` relationships in the DEFINITIONS input.
5.  **Conciseness and Abstraction:**
    *   Use the defined `ACTION_KEYWORD`s.
    *   While the overall number of patterns should be limited to the most critical ones found in THIS CHUNK, ensure that each *selected* pattern has enough steps (e.g., 3-7 steps) to clearly illustrate the setup and use of the feature it represents.
6.  **Focus on Sequence & Interaction Flow:** Describe the ordered flow of operations that a user or system would perform.
7.  **Unique IDs:** `U_Name` should be unique and descriptive within this output. `U_Name.N` steps must be sequential within each pattern.

**INPUT 1: SKF HIERARCHICAL GLOSSARY (GLOBAL & FINALIZED)**
```text
$skf_glossary_content
```

INPUT 2: SKF HIERARCHICAL DEFINITIONS & INTERACTIONS (ALL ASSEMBLED)
```text
$final_skf_definitions_interactions_content
```

INPUT 3: DOCUMENT CHUNK (Relevant usage examples, tutorials)
```text
$document_chunk_for_usage
```

INSTRUCTIONS (CONTINUED):
Begin generating ONLY the USAGE_PATTERNS section for this document chunk.
"""
SKF_PROMPT_CALL3_USAGE_SINGLE_CHUNK_TEMPLATE = Template(SKF_PROMPT_CALL3_USAGE_SINGLE_CHUNK_STR)

# LLM Call 3: Usage Patterns Generation (Iterative Logic for N > 1 Chunks)
SKF_PROMPT_CALL3_USAGE_ITERATIVE_STR = """
SYSTEM: You are a Workflow Illustrator AI, adept at incrementally building a knowledge base of usage patterns. Given a GLOBAL SKF GLOSSARY, the CUMULATIVE SKF DEFINITIONS & INTERACTIONS, the USAGE_PATTERNS SKF generated from PREVIOUS CHUNKS, and the CURRENT DOCUMENT CHUNK, your task is to:
1. Identify new critical and illustrative USAGE_PATTERNS from the CURRENT CHUNK.
2. Append these new patterns to the PREVIOUS CHUNKS' USAGE_PATTERNS SKF output. If CURRENT CHUNK provides additional steps for a pattern (`U_Name`) already initiated in PREVIOUS OUTPUT, append these steps sequentially. Ensure `U_Name` identifiers for distinct scenarios remain unique across the combined output.
Adhere strictly to SKF/1.4 LA. Your output should be the *complete, updated* USAGE_PATTERNS section, including its header if content exists.

USER:
**TASK: Incrementally Generate Hierarchical SKF Usage Patterns (Part 3 of IKM - Critical Examples - SKF/1.4 LA)**

**INPUTS:**
1.  **SKF HIERARCHICAL GLOSSARY (GLOBAL & FINALIZED - Provided Below).**
2.  **SKF HIERARCHICAL DEFINITIONS & INTERACTIONS (ALL CUMULATIVE - Provided Below).** This is CRUCIAL for constructing valid pattern steps.
3.  **PREVIOUS CHUNK'S SKF USAGE_PATTERNS OUTPUT (Provided Below D&I):** Accumulated patterns so far. If empty or just a header with no patterns, this is effectively the first chunk for patterns.
4.  **CURRENT DOCUMENT CHUNK (Portions relevant to usage, examples, tutorials - Provided Below Previous Output).**

**OUTPUT SPECIFICATION (COMPLETE & UPDATED USAGE_PATTERNS SECTION):**
*   Output the *entire* USAGE_PATTERNS section, reflecting combined knowledge from PREVIOUS OUTPUT and new findings from CURRENT CHUNK.
*   If PREVIOUS OUTPUT was empty (or just a "no patterns" message) and CURRENT CHUNK also yields no patterns, output `# No distinct critical usage patterns identified.` (but still include the full section header block).
*   If PREVIOUS OUTPUT had patterns, and CURRENT CHUNK adds more, ensure the combined output is well-formed.
*   `U_Name` IDs for distinct scenarios should be unique. `U_Name.N` steps must be sequential within each pattern.
*   Adhere to SKF/1.4 LA section format.

**SECTION FORMAT from SKF/1.4 LA Protocol (Reminder):**
`# SECTION: USAGE_PATTERNS (Prefix: U)`
`# Format: U_Name:PatternTitleKeyword`
`#         U_Name.N:[Actor_Or_Ref] ACTION_KEYWORD (Target_Or_Data_Involving_Ref) -> [Result_Or_State_Change_Involving_Ref]`
`# ACTION_KEYWORD Enum: CREATE (instance), CONFIGURE (object/settings), INVOKE (operation/method), GET_ATTR (read attribute/property), SET_ATTR (write attribute/property), PROCESS_DATA, CHECK_STATE, ITERATE (over a collection/stream, e.g., async for), RAISE_ERR, HANDLE_ERR(Gxxx_ErrorType)`
`# ---`

**INSTRUCTIONS FOR INCREMENTAL PROCESSING:**
1.  **Utilize Full Knowledge Context (Glossary, D&I):**
    *   Refer to top-level entities by `Gxxx` (from GLOSSARY).
    *   Refer to members using `Gxxx.MemberName` (as defined in DEFINITIONS).
    *   Pattern steps MUST be consistent with operation signatures and attribute types from DEFINITIONS.
2.  **Analyze CURRENT DOCUMENT CHUNK:** Identify new usage patterns or continuations of patterns described in PREVIOUS CHUNK'S OUTPUT (if any).
3.  **Integrate with PREVIOUS CHUNK'S OUTPUT (INPUT 3):**
    *   **New Patterns:** If a new distinct scenario is found in CURRENT CHUNK that doesn't clearly extend an existing one from PREVIOUS OUTPUT, add it with a new unique `U_Name`.
    *   **Augment Existing Patterns:** If CURRENT CHUNK provides more steps for a `U_Name` already in PREVIOUS OUTPUT, append these steps, continuing the `U_Name.N` numbering for that specific pattern.
4.  **Select MOST CRITICAL & ILLUSTRATIVE Patterns:**
    *   When adding new patterns or deciding to augment existing ones, prioritize those that demonstrate the **setup, invocation, and typical outcome of CORE FEATURES** of the library/system. For example, if "Deep Crawling," "Structured LLM Extraction," or "Session Management" are key features, and examples appear in CURRENT CHUNK, ensure they are represented.
    *   Include core "happy path" workflows, essential setup sequences, key component interactions, and prominent error handling flows.
5.  **Concrete Implementations in `CREATE` Steps:** If creating an object of an interface type (`[Ifce]`), the `CREATE` step must specify a concrete implementation `Gxxx`.
6.  **Conciseness and Abstraction:**
    *   Use defined `ACTION_KEYWORD`s.
    *   Ensure each selected pattern has enough steps (e.g., 3-7) to clearly illustrate the feature.
7.  **ID Sequencing (`U_Name.N`):** Ensure step numbers are sequential *within each unique `U_Name` pattern* across the combined output.
8.  **Avoid Duplicates:** Do not repeat identical pattern steps already present in PREVIOUS CHUNK'S OUTPUT for the same `U_Name`.

**INPUT 1: SKF HIERARCHICAL GLOSSARY (GLOBAL & FINALIZED)**
```text
$skf_glossary_content
```

INPUT 2: SKF HIERARCHICAL DEFINITIONS & INTERACTIONS (ALL CUMULATIVE)
```text
$cumulative_skf_details_content
```

INPUT 3: PREVIOUS CHUNK'S SKF USAGE_PATTERNS OUTPUT (CONTEXT ONLY)
```text
$previous_chunk_skf_usage_content
```

INPUT 4: CURRENT DOCUMENT CHUNK (FOR ANALYSIS)
```text
$current_document_chunk_for_usage
```

INSTRUCTIONS (CONTINUED):
Begin generating ONLY THE NEW Usage Patterns or new steps for existing patterns based on the CURRENT DOCUMENT CHUNK.
"""
SKF_PROMPT_CALL3_USAGE_ITERATIVE_TEMPLATE = Template(SKF_PROMPT_CALL3_USAGE_ITERATIVE_STR)


def get_next_id(prefix: str, existing_ids: set[str]) -> str:
    """Generates the next sequential ID (e.g., G001, D010)."""
    max_num = 0
    for eid in existing_ids:
        if eid.startswith(prefix):
            try:
                num = int(eid[len(prefix) :])
                if num > max_num:
                    max_num = num
            except ValueError:
                continue  # Should not happen with valid IDs
    return f"{prefix}{max_num + 1:03d}"


def parse_skf_lines(text: str, section_prefix: str) -> list[str]:
    """Parses SKF content and returns lines belonging to a specific prefix (G, D, I)."""
    if not text or not text.strip():
        return []
    return [line.strip() for line in text.splitlines() if line.strip().startswith(section_prefix)]


def extract_entity_from_g_line(g_line: str) -> str | None:
    """Extracts EntityName from a Gxxx line. Gxxx:[TYP] EntityName - ..."""
    match = re.match(r"G\d{3,}:\s*\[[^\]]+\]\s*([^-\s]+)", g_line)
    return match.group(1) if match else None


def extract_gxxx_from_d_line(d_line: str) -> str | None:
    """Extracts Gxxx from a Dxxx primary definition line. Dxxx:Gxxx_Entity ..."""
    match = re.match(r"D\d{3,}:\s*(G\d{3,})", d_line)
    return match.group(1) if match else None


def re_id_glossary_items(glossary_text: str) -> tuple[str, dict[str, str]]:
    """
    Re-numbers Gxxx IDs in a glossary text to be globally sequential.
    Returns the new glossary text and a mapping from old GIDs to new GIDs.
    Handles cases where LLM might output Gxxx, Gyy, Gzz etc.
    """
    if not glossary_text.strip():
        return "", {}

    lines = glossary_text.splitlines()
    new_lines = []
    old_to_new_gid_map: dict[str, str] = {}
    current_g_id_val = 0

    # First pass: map old GIDs to new GIDs
    processed_entities_for_new_gids: set[str] = set()  # To ensure unique new GIDs per unique entity

    for line in lines:
        line = line.strip()
        if not line or not line.startswith("G"):  # Skip empty or non-glossary lines
            if line:
                new_lines.append(line)  # Keep other lines like comments or ---
            continue

        match = re.match(r"(G\w+):(\s*\[.*?\]\s*.*)", line)  # Gxxx:, G1:, G_temp:
        if match:
            old_gid_str = match.group(1)
            entity_part = match.group(2).strip()  # [TYP] EntityName - "Keywords" @DocRef

            # Create a canonical key for the entity to handle semantic duplicates if LLM didn't
            # This is a simple heuristic; more complex merging might be needed
            entity_name_match = re.match(r"\[[^\]]+\]\s*([^-]+)", entity_part)
            entity_name = entity_name_match.group(1).strip() if entity_name_match else entity_part

            if entity_name not in processed_entities_for_new_gids:
                current_g_id_val += 1
                new_gid = f"G{current_g_id_val:03d}"
                old_to_new_gid_map[old_gid_str] = new_gid
                processed_entities_for_new_gids.add(entity_name)
                new_lines.append(f"{new_gid}:{entity_part}")
            else:
                # This is a duplicate entity that the LLM didn't consolidate, or we are re-IDing
                # We'll map its old ID to the new ID of the first instance we saw
                # This assumes the first encountered is canonical if LLM failed to merge.
                # For robust merging, the LLM call 1.5 is critical.
                # This re-ID mainly ensures Gxxx are sequential AFTER LLM consolidation.
                # If LLM consolidates properly, this branch for duplicates is less likely.
                # Find the new_gid associated with this entity_name
                # This is a bit tricky here, this re_id function assumes LLM did the merge
                # and is mostly about making Gxxx sequential. If LLM produces G1, G2 for the same thing,
                # this re-ID won't merge them, only re-ID G1 to G001, G2 to G002.
                # The prompt for Call 1.5 is key for actual merging.
                # This function is now simplified to just re-number whatever distinct lines it gets.
                current_g_id_val += 1
                new_gid = f"G{current_g_id_val:03d}"
                old_to_new_gid_map[old_gid_str] = new_gid
                new_lines.append(f"{new_gid}:{entity_part}")

        elif line:  # Non-matching lines (e.g. format lines, comments)
            new_lines.append(line)

    # Second pass: update Gxxx references within the new glossary items (e.g. in @DocRef or keywords if they were GIDs)
    # This is less common for glossary but good practice. For D/I/U this is crucial.
    # final_re_id_lines = []
    # for line in new_lines:
    #     updated_line = line
    #     for old_gid, new_gid in old_to_new_gid_map.items():
    #         # Ensure whole word replacement to avoid G1 becoming NewG10 if G10 exists
    #         updated_line = re.sub(r'\b' + re.escape(old_gid) + r'\b', new_gid, updated_line)
    #     final_re_id_lines.append(updated_line)

    return "\n".join(new_lines), old_to_new_gid_map


def update_gxxx_references(text_content: str, gid_map: dict[str, str]) -> str:
    """Updates all Gxxx references in a given text based on the old_to_new_gid_map."""
    # Ensure we always return a string, never None
    if not text_content:
        return ""
    
    if not isinstance(text_content, str):
        return str(text_content) if text_content is not None else ""
    
    if not gid_map:
        return text_content

    # Don't process error messages
    if text_content.startswith("ERROR:"):
        return text_content

    updated_text = text_content
    # Sort keys by length descending to replace longer GIDs first (e.g., G10 before G1)
    sorted_old_gids = sorted(gid_map.keys(), key=len, reverse=True)
    for old_gid in sorted_old_gids:
        new_gid = gid_map[old_gid]
        # Use regex to ensure replacement of Gxxx as a whole word/identifier
        updated_text = re.sub(r"\b" + re.escape(old_gid) + r"\b", new_gid, updated_text)
    return updated_text


# --- Main Pipeline Function ---


async def _generate_global_glossary(
    document_chunks: list[str],
    api_key: str | None = None,
    model_name: str | None = None,
) -> tuple[str, dict[str, str]]:
    logger.info("SKF Pipeline - Step 1: Generating Global Glossary...")
    partial_glossary_outputs: list[str] = []
    num_doc_chunks = len(document_chunks)
    for i, doc_chunk_text in enumerate(document_chunks):
        logger.debug(f"Step 1: Processing glossary for document chunk {i + 1}/{num_doc_chunks}")
        prompt_c1 = SKF_PROMPT_CALL1_GLOSSARY_TEMPLATE.substitute(input_document_text=doc_chunk_text)
        glossary_chunk_output = await generate_text_response(prompt_c1, api_key=api_key, model_name=model_name)
        
        # Handle error responses and None values safely
        if (glossary_chunk_output 
            and isinstance(glossary_chunk_output, str) 
            and not glossary_chunk_output.startswith("ERROR:")
            and glossary_chunk_output.strip()):
            partial_glossary_outputs.append(glossary_chunk_output.strip())
        else:
            error_msg = glossary_chunk_output if glossary_chunk_output else "No response"
            logger.warning(f"Glossary generation failed for chunk {i + 1}: {error_msg}")

    if not partial_glossary_outputs:
        logger.warning("Step 1: No glossary fragments generated from chunks. Final glossary will be empty.")
        raw_consolidated_glossary = ""
    else:
        logger.info(f"Step 1.5: Consolidating {len(partial_glossary_outputs)} glossary fragment(s)...")
        concatenated_fragments = "\n---\n".join(partial_glossary_outputs)
        prompt_c1_5 = SKF_PROMPT_CALL1_5_MERGE_GLOSSARY_TEMPLATE.substitute(
            concatenated_glossary_fragments=concatenated_fragments
        )
        raw_consolidated_glossary = await generate_text_response(prompt_c1_5, api_key=api_key, model_name=model_name)
        
        # Handle consolidation errors
        if (not raw_consolidated_glossary 
            or not isinstance(raw_consolidated_glossary, str)
            or raw_consolidated_glossary.startswith("ERROR:")):
            error_msg = raw_consolidated_glossary if raw_consolidated_glossary else "No response"
            logger.error(f"Step 1.5: Glossary consolidation by LLM failed: {error_msg}. Using raw fragments.")
            raw_consolidated_glossary = concatenated_fragments
        raw_consolidated_glossary = raw_consolidated_glossary.strip()

    final_skf_glossary_content, gid_map = re_id_glossary_items(raw_consolidated_glossary)
    if not final_skf_glossary_content.strip() and partial_glossary_outputs:
        logger.warning(
            "Post re-ID, glossary content is empty. This might indicate issues in re_id_glossary_items or LLM output for consolidation."
        )

    logger.info(
        f"SKF Pipeline - Step 1 Complete: Global Glossary generated ({count_tokens(final_skf_glossary_content)} tokens, {len(gid_map)} map items). Kept in memory."
    )
    return final_skf_glossary_content, gid_map


async def _generate_definitions_and_interactions(
    document_chunks: list[str],
    final_skf_glossary_content: str,
    library_name_param: str,
    gid_map: dict[str, str],
    api_key: str | None = None,
    model_name: str | None = None,
) -> str:
    logger.info("SKF Pipeline - Step 2: Generating Definitions & Interactions...")
    cumulative_definitions_items: list[str] = []
    cumulative_interactions_items: list[str] = []
    num_doc_chunks = len(document_chunks)

    definitions_header_block = (
        "# SECTION: DEFINITIONS (Prefix: D)\n"
        '# Format_PrimaryDef: Dxxx:Gxxx_Entity [DEF_TYP] [NAMESPACE "relative.path"] [OPERATIONS {op1:RetT(p1N:p1T); op2_static:RetT()}] [ATTRIBUTES {attr1:AttrT1("Def:Val","RO")}] [CONSTANTS {c1:ValT1("Val")}] ("Note")\n'
        '# ---"'
    )
    interactions_header_block = (
        "# SECTION: INTERACTIONS (Prefix: I)\n"
        '# Format: Ixxx:Source_Ref INT_VERB Target_Ref_Or_Literal ("Note_Conditions_Error(Gxxx_ErrorType)")\n'
        '# ---"'
    )

    def assemble_di_text(definitions: list[str], interactions: list[str]) -> str:
        d_text = (
            f"{definitions_header_block}\n" + "\n".join(definitions)
            if definitions
            else definitions_header_block + "\n# No definitions identified."
        )
        i_text = (
            f"{interactions_header_block}\n" + "\n".join(interactions)
            if interactions
            else interactions_header_block + "\n# No interactions identified."
        )
        return f"{d_text}\n\n{i_text}"

    current_d_id = 0
    current_i_id = 0

    for i, doc_chunk_text in enumerate(document_chunks):
        logger.debug(f"Step 2: Processing D&I for document chunk {i + 1}/{num_doc_chunks}")
        previous_di_content_for_context = assemble_di_text(cumulative_definitions_items, cumulative_interactions_items)

        if i == 0:
            prompt_c2_chunk = SKF_PROMPT_CALL2_DETAILS_SINGLE_CHUNK_TEMPLATE.substitute(
                skf_glossary_content=final_skf_glossary_content,
                document_chunk=doc_chunk_text,
                primary_namespace=library_name_param,
            )
        else:
            prompt_c2_chunk = SKF_PROMPT_CALL2_DETAILS_ITERATIVE_TEMPLATE.substitute(
                skf_glossary_content=final_skf_glossary_content,
                previous_chunk_skf_details_content=previous_di_content_for_context,
                current_document_chunk=doc_chunk_text,
                primary_namespace=library_name_param,
            )

        chunk_di_output_raw = await generate_text_response(prompt_c2_chunk, api_key=api_key, model_name=model_name)

        # Handle error responses and None values safely
        if (chunk_di_output_raw 
            and isinstance(chunk_di_output_raw, str) 
            and not chunk_di_output_raw.startswith("ERROR:")):
            chunk_di_output = chunk_di_output_raw  # update_gxxx_references(chunk_di_output_raw, gid_map) # Safety net

            raw_d_items_from_chunk = parse_skf_lines(chunk_di_output, "D")
            raw_i_items_from_chunk = parse_skf_lines(chunk_di_output, "I")

            for d_item_text_from_chunk in raw_d_items_from_chunk:
                cleaned_d_item = re.sub(r"^D\d{3,}:\s*", "", d_item_text_from_chunk)
                if not any(cleaned_d_item in cdi for cdi in cumulative_definitions_items):
                    current_d_id += 1
                    cumulative_definitions_items.append(f"D{current_d_id:03d}:{cleaned_d_item}")

            for i_item_text_from_chunk in raw_i_items_from_chunk:
                cleaned_i_item = re.sub(r"^I\d{3,}:\s*", "", i_item_text_from_chunk)
                if not any(cleaned_i_item in cii for cii in cumulative_interactions_items):
                    current_i_id += 1
                    cumulative_interactions_items.append(f"I{current_i_id:03d}:{cleaned_i_item}")
        else:
            error_msg = chunk_di_output_raw if chunk_di_output_raw else "No response"
            logger.warning(f"D&I generation failed for chunk {i + 1}: {error_msg}")

    final_skf_definitions_interactions_content = assemble_di_text(
        cumulative_definitions_items, cumulative_interactions_items
    )
    logger.info(
        f"SKF Pipeline - Step 2 Complete: D&I ({count_tokens(final_skf_definitions_interactions_content)} tokens)."
    )
    return final_skf_definitions_interactions_content


async def _generate_usage_patterns(
    document_chunks: list[str],
    final_skf_glossary_content: str,
    final_skf_definitions_interactions_content: str,
    gid_map: dict[str, str],
    api_key: str | None = None,
    model_name: str | None = None,
) -> str:
    logger.info("SKF Pipeline - Step 3: Generating Usage Patterns...")
    num_doc_chunks = len(document_chunks)
    usage_patterns_header_block = (
        "# SECTION: USAGE_PATTERNS (Prefix: U)\n"
        "# Format: U_Name:PatternTitleKeyword\n"
        "#         U_Name.N:[Actor_Or_Ref] ACTION_KEYWORD (Target_Or_Data_Involving_Ref) -> [Result_Or_State_Change_Involving_Ref]\n"
        '# ---"'
    )

    cumulative_usage_patterns_text = f"""{usage_patterns_header_block}
# No distinct critical usage patterns identified.
# ---"""

    for i, doc_chunk_text_for_usage in enumerate(document_chunks):
        logger.debug(f"Step 3: Processing Usage for document chunk {i + 1}/{num_doc_chunks}")
        chunk_usage_output = None
        if i == 0:
            prompt_c3_chunk = SKF_PROMPT_CALL3_USAGE_SINGLE_CHUNK_TEMPLATE.substitute(
                skf_glossary_content=final_skf_glossary_content,
                final_skf_definitions_interactions_content=final_skf_definitions_interactions_content,
                document_chunk_for_usage=doc_chunk_text_for_usage,
            )
            chunk_usage_output_raw = await generate_text_response(
                prompt_c3_chunk, api_key=api_key, model_name=model_name
            )
            
            # Handle error responses and None values safely
            if (chunk_usage_output_raw 
                and isinstance(chunk_usage_output_raw, str) 
                and not chunk_usage_output_raw.startswith("ERROR:")):
                chunk_usage_output = update_gxxx_references(chunk_usage_output_raw, gid_map)
            else:
                error_msg = chunk_usage_output_raw if chunk_usage_output_raw else "No response"
                logger.warning(f"Usage patterns generation failed for chunk {i + 1}: {error_msg}")
                chunk_usage_output = ""
            
            if (
                chunk_usage_output
                and isinstance(chunk_usage_output, str)
                and "# No distinct critical usage patterns identified" not in chunk_usage_output
                and chunk_usage_output.strip().startswith("# SECTION: USAGE_PATTERNS")
            ):
                cumulative_usage_patterns_text = chunk_usage_output.strip()
        else:
            prompt_c3_iterative = SKF_PROMPT_CALL3_USAGE_ITERATIVE_TEMPLATE.substitute(
                skf_glossary_content=final_skf_glossary_content,
                cumulative_skf_details_content=final_skf_definitions_interactions_content,
                previous_chunk_skf_usage_content=cumulative_usage_patterns_text,
                current_document_chunk_for_usage=doc_chunk_text_for_usage,
            )
            chunk_usage_output_raw = await generate_text_response(
                prompt_c3_iterative, api_key=api_key, model_name=model_name
            )
            
            # Handle error responses and None values safely  
            if (chunk_usage_output_raw 
                and isinstance(chunk_usage_output_raw, str) 
                and not chunk_usage_output_raw.startswith("ERROR:")):
                chunk_usage_output = update_gxxx_references(chunk_usage_output_raw, gid_map)
            else:
                error_msg = chunk_usage_output_raw if chunk_usage_output_raw else "No response"
                logger.warning(f"Usage patterns generation failed for chunk {i + 1}: {error_msg}")
                chunk_usage_output = ""
            
            if (
                chunk_usage_output
                and isinstance(chunk_usage_output, str)
                and chunk_usage_output.strip().startswith("# SECTION: USAGE_PATTERNS")
            ):
                cumulative_usage_patterns_text = chunk_usage_output.strip()

    final_skf_usage_patterns_content = cumulative_usage_patterns_text
    logger.info(
        f"SKF Pipeline - Step 3 Complete: Usage Patterns ({count_tokens(final_skf_usage_patterns_content)} tokens)."
    )
    return final_skf_usage_patterns_content


# --- Main Pipeline Function ---


async def compact_content_to_structured_text(
    full_content: str,
    library_name_param: str,
    library_version_param: str,
    chunk_size: int,
    api_key: str | None = None,
    model_name: str | None = None,
    output_path: str | None = None,  # New parameter for saving intermediate results
    force_reprocess: bool = False,  # New parameter to force reprocessing
    save_fragments: bool = True,  # New parameter to control fragment saving
) -> str:  # This will now return D, I, U only
    logger.info(
        f"Starting SKF LA manifest generation for '{library_name_param}' (v{library_version_param}). V2 Pipeline."
    )
    current_utc_timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    source_doc_identifiers = [f"{library_name_param}-{library_version_param}"]

    document_chunks = chunk_content(full_content, chunk_size)
    if not document_chunks:
        logger.error("Full content resulted in no document chunks. Aborting.")
        return ""
    num_doc_chunks = len(document_chunks)  # Used by helpers now
    logger.info(
        f"Initial content split into {num_doc_chunks} document chunk(s). Total length: {count_tokens(full_content)} tokens."
    )

    # Initialize intermediate file paths
    intermediate_dir = None
    glossary_file = None
    definitions_file = None
    
    if output_path and save_fragments:
        intermediate_dir = os.path.join(output_path, ".intermediate")
        os.makedirs(intermediate_dir, exist_ok=True)
        glossary_file = os.path.join(intermediate_dir, "glossary.txt")
        definitions_file = os.path.join(intermediate_dir, "definitions.txt")
    elif not save_fragments:
        logger.info("Fragment saving disabled, intermediate results will not be saved to disk")

    # Step 1: Generate Global Glossary (with resume capability)
    final_skf_glossary_content, gid_map = await _generate_global_glossary_with_resume(
        document_chunks, glossary_file, api_key, model_name, force_reprocess
    )

    # Step 2: Generate Definitions & Interactions (with resume capability)
    final_skf_definitions_interactions_content = await _generate_definitions_and_interactions_with_resume(
        document_chunks, final_skf_glossary_content, library_name_param, gid_map, definitions_file, api_key, model_name, force_reprocess
    )

    # Step 3: Generate Usage Patterns
    final_skf_usage_patterns_content = await _generate_usage_patterns(
        document_chunks,
        final_skf_glossary_content,
        final_skf_definitions_interactions_content,
        gid_map,
        api_key,
        model_name,
    )

    # Clean up intermediate files on success (but keep fragments for debugging)
    if intermediate_dir and os.path.exists(intermediate_dir):
        try:
            # Only remove main intermediate files, keep fragments directory for potential retry
            for file in os.listdir(intermediate_dir):
                file_path = os.path.join(intermediate_dir, file)
                if os.path.isfile(file_path) and not file.startswith('fragment'):
                    os.remove(file_path)
                    logger.debug(f"Removed intermediate file: {file}")
            logger.info("Cleaned up main intermediate files (kept fragments for potential retry)")
        except Exception as e:
            logger.warning(f"Could not clean up intermediate files: {e}")

    # --- Final Assembly (D, I, U only) ---
    final_skf_manifest_parts = [
        "# IntegratedKnowledgeManifest_SKF/1.4 LA",
        f"# SourceDocs: [{', '.join(source_doc_identifiers)}]",
        f"# GenerationTimestamp: {current_utc_timestamp}",
        f"# PrimaryNamespace: {library_name_param}",
        "",
        # Glossary is NOT included in the file output
        final_skf_definitions_interactions_content,  # Contains D and I sections
        "",
        final_skf_usage_patterns_content,
        "",
        "# END_OF_MANIFEST",
    ]
    final_skf_manifest = "\n".join(final_skf_manifest_parts)

    logger.info(
        f"Successfully assembled final SKF manifest (D, I, U) for '{library_name_param}'. Total length: {count_tokens(final_skf_manifest)} tokens."
    )
    return final_skf_manifest.strip()


async def _generate_global_glossary_with_resume(
    document_chunks: list[str],
    glossary_file: str | None = None,
    api_key: str | None = None,
    model_name: str | None = None,
    force_reprocess: bool = False,
) -> tuple[str, dict[str, str]]:
    """Generate global glossary with resume capability."""
    
    # Check for existing glossary file (unless force_reprocess is True)
    if not force_reprocess and glossary_file and os.path.exists(glossary_file):
        try:
            with open(glossary_file, 'r', encoding='utf-8') as f:
                existing_glossary = f.read().strip()
            if existing_glossary:
                logger.info(f"Resuming from existing glossary file: {glossary_file}")
                final_skf_glossary_content, gid_map = re_id_glossary_items(existing_glossary)
                logger.info(f"Loaded existing glossary with {len(gid_map)} entities")
                return final_skf_glossary_content, gid_map
        except Exception as e:
            logger.warning(f"Could not load existing glossary: {e}, starting fresh")
    elif force_reprocess and glossary_file and os.path.exists(glossary_file):
        logger.info("Force reprocessing enabled, ignoring existing glossary")
    
    # Generate new glossary with fragment-aware consolidation
    logger.info("SKF Pipeline - Step 1: Generating Global Glossary...")
    final_skf_glossary_content, gid_map = await _generate_global_glossary_with_fragment_handling(
        document_chunks, glossary_file, api_key, model_name
    )
    
    # Save intermediate result
    if glossary_file:
        try:
            with open(glossary_file, 'w', encoding='utf-8') as f:
                f.write(final_skf_glossary_content)
            logger.info(f"Saved glossary to {glossary_file}")
        except Exception as e:
            logger.warning(f"Could not save glossary: {e}")
    
    return final_skf_glossary_content, gid_map


async def _generate_global_glossary_with_fragment_handling(
    document_chunks: list[str],
    glossary_file: str | None = None,
    api_key: str | None = None,
    model_name: str | None = None,
) -> tuple[str, dict[str, str]]:
    """Generate global glossary with fragment handling for large datasets."""
    logger.info("SKF Pipeline - Step 1: Generating Global Glossary with fragment handling...")
    
    # Step 1: Generate individual fragment glossaries
    partial_glossary_outputs: list[str] = []
    num_doc_chunks = len(document_chunks)
    
    # Create fragment directory if we have a glossary file path
    fragment_dir = None
    if glossary_file:
        fragment_dir = os.path.join(os.path.dirname(glossary_file), "fragments")
        os.makedirs(fragment_dir, exist_ok=True)
    
    for i, doc_chunk_text in enumerate(document_chunks):
        logger.debug(f"Step 1: Processing glossary for document chunk {i + 1}/{num_doc_chunks}")
        
        # Check for existing fragment file
        fragment_file = None
        if fragment_dir:
            fragment_file = os.path.join(fragment_dir, f"glossary_fragment_{i+1:03d}.txt")
            if os.path.exists(fragment_file):
                try:
                    with open(fragment_file, 'r', encoding='utf-8') as f:
                        existing_fragment = f.read().strip()
                    if existing_fragment:
                        logger.info(f"Loading existing fragment {i+1}: {fragment_file}")
                        partial_glossary_outputs.append(existing_fragment)
                        continue
                except Exception as e:
                    logger.warning(f"Could not load fragment {i+1}: {e}, regenerating")
        
        # Generate new fragment
        prompt_c1 = SKF_PROMPT_CALL1_GLOSSARY_TEMPLATE.substitute(input_document_text=doc_chunk_text)
        glossary_chunk_output = await generate_text_response(prompt_c1, api_key=api_key, model_name=model_name)
        
        # Handle error responses and None values safely
        if (glossary_chunk_output 
            and isinstance(glossary_chunk_output, str) 
            and not glossary_chunk_output.startswith("ERROR:")
            and glossary_chunk_output.strip()):
            partial_glossary_outputs.append(glossary_chunk_output.strip())
            
            # Save fragment for future runs
            if fragment_file:
                try:
                    with open(fragment_file, 'w', encoding='utf-8') as f:
                        f.write(glossary_chunk_output.strip())
                    logger.debug(f"Saved fragment {i+1} to {fragment_file}")
                except Exception as e:
                    logger.warning(f"Could not save fragment {i+1}: {e}")
        else:
            error_msg = glossary_chunk_output if glossary_chunk_output else "No response"
            logger.warning(f"Glossary generation failed for chunk {i + 1}: {error_msg}")

    if not partial_glossary_outputs:
        logger.warning("Step 1: No glossary fragments generated from chunks. Final glossary will be empty.")
        return "", {}

    # Step 2: Consolidate fragments with size awareness
    logger.info(f"Step 1.5: Consolidating {len(partial_glossary_outputs)} glossary fragment(s)...")
    
    # Calculate total size of fragments to decide consolidation strategy
    total_fragment_size = sum(count_tokens(fragment) for fragment in partial_glossary_outputs)
    logger.info(f"Total fragment size: {total_fragment_size} tokens")
    
    # If fragments are small enough, consolidate in one go
    MAX_CONSOLIDATION_TOKENS = 50000  # Conservative limit for consolidation input
    
    if total_fragment_size <= MAX_CONSOLIDATION_TOKENS:
        # Single consolidation pass
        raw_consolidated_glossary = await _consolidate_fragments_single_pass(
            partial_glossary_outputs, api_key, model_name
        )
    else:
        # Multi-pass consolidation for large fragment sets
        logger.info(f"Fragment size ({total_fragment_size} tokens) exceeds limit. Using multi-pass consolidation.")
        raw_consolidated_glossary = await _consolidate_fragments_multi_pass(
            partial_glossary_outputs, fragment_dir, api_key, model_name
        )
    
    # Re-ID the final glossary
    final_skf_glossary_content, gid_map = re_id_glossary_items(raw_consolidated_glossary)
    if not final_skf_glossary_content.strip() and partial_glossary_outputs:
        logger.warning(
            "Post re-ID, glossary content is empty. This might indicate issues in re_id_glossary_items or LLM output for consolidation."
        )

    logger.info(
        f"SKF Pipeline - Step 1 Complete: Global Glossary generated ({count_tokens(final_skf_glossary_content)} tokens, {len(gid_map)} map items). Kept in memory."
    )
    return final_skf_glossary_content, gid_map


async def _consolidate_fragments_single_pass(
    fragments: list[str],
    api_key: str | None = None,
    model_name: str | None = None,
    retry_on_failure: bool = True,
) -> str:
    """Consolidate fragments in a single pass with retry mechanism."""
    concatenated_fragments = "\n---\n".join(fragments)
    
    # Calculate input size for logging
    input_size = count_tokens(concatenated_fragments)
    logger.debug(f"Attempting single-pass consolidation of {len(fragments)} fragments ({input_size} tokens)")
    
    prompt_c1_5 = SKF_PROMPT_CALL1_5_MERGE_GLOSSARY_TEMPLATE.substitute(
        concatenated_glossary_fragments=concatenated_fragments
    )
    
    # First attempt
    try:
        raw_consolidated_glossary = await generate_text_response(prompt_c1_5, api_key=api_key, model_name=model_name)
        
        # Check for successful consolidation
        if (raw_consolidated_glossary 
            and isinstance(raw_consolidated_glossary, str) 
            and not raw_consolidated_glossary.startswith("ERROR:")
            and raw_consolidated_glossary.strip()):
            
            output_size = count_tokens(raw_consolidated_glossary)
            logger.debug(f"Consolidation successful: {input_size} -> {output_size} tokens")
            return raw_consolidated_glossary.strip()
        
        # Check for MAX_TOKENS truncation specifically
        if raw_consolidated_glossary and "MAX_TOKENS" in str(raw_consolidated_glossary):
            logger.warning("Consolidation truncated due to MAX_TOKENS limit")
            raise ValueError("MAX_TOKENS_EXCEEDED")
        
        error_msg = raw_consolidated_glossary if raw_consolidated_glossary else "No response"
        logger.warning(f"Consolidation attempt failed: {error_msg}")
        
        if retry_on_failure and len(fragments) > 1:
            logger.info("Retrying consolidation with smaller batch size")
            # For large fragment sets, split more aggressively
            if len(fragments) > 4:
                # Split into quarters for very large sets
                quarter = len(fragments) // 4
                chunks = [
                    fragments[i:i+quarter] for i in range(0, len(fragments), quarter)
                ]
                # Consolidate each chunk separately
                consolidated_chunks = []
                for chunk in chunks:
                    if len(chunk) == 1:
                        consolidated_chunks.append(chunk[0])
                    else:
                        chunk_result = await _consolidate_fragments_single_pass(
                            chunk, api_key, model_name, retry_on_failure=False
                        )
                        consolidated_chunks.append(chunk_result)
                
                # Final consolidation of chunks
                return await _consolidate_fragments_single_pass(
                    consolidated_chunks, api_key, model_name, retry_on_failure=False
                )
            else:
                # Split in half for smaller sets
                mid_point = len(fragments) // 2
                first_half = fragments[:mid_point]
                second_half = fragments[mid_point:]
            
                # Consolidate each half separately, then combine
                first_consolidated = await _consolidate_fragments_single_pass(
                    first_half, api_key, model_name, retry_on_failure=False
                )
                second_consolidated = await _consolidate_fragments_single_pass(
                    second_half, api_key, model_name, retry_on_failure=False
                )
                
                # Final consolidation of the two halves
                return await _consolidate_fragments_single_pass(
                    [first_consolidated, second_consolidated], api_key, model_name, retry_on_failure=False
                )
        
    except Exception as e:
        logger.error(f"Exception during consolidation: {e}")
        if "MAX_TOKENS" in str(e) or "MAX_OUTPUT_TOKEN" in str(e):
            logger.warning("Hit token limit during consolidation, will use fallback")
        
    # Fallback: return raw fragments
    logger.warning("Consolidation failed, returning raw fragments")
    return concatenated_fragments


async def _consolidate_fragments_multi_pass(
    fragments: list[str],
    fragment_dir: str | None = None,
    api_key: str | None = None,
    model_name: str | None = None,
) -> str:
    """Consolidate fragments in multiple passes for large datasets."""
    logger.info("Starting multi-pass fragment consolidation")
    
    # Constants for multi-pass consolidation
    MAX_FRAGMENTS_PER_BATCH = 6  # Consolidate up to 6 fragments at once (increased for better context)
    MAX_BATCH_TOKENS = 20000     # More generous token limit per batch (increased from 8000)
    PROMPT_OVERHEAD_TOKENS = 2000  # Account for prompt template overhead (reduced for efficiency)
    
    current_fragments = fragments.copy()
    pass_number = 1
    
    while len(current_fragments) > 1:
        logger.info(f"Consolidation pass {pass_number}: processing {len(current_fragments)} fragments")
        
        next_fragments: list[str] = []
        batch_start = 0
        
        while batch_start < len(current_fragments):
            # Determine batch size based on token count and max fragments
            batch_end = batch_start
            batch_tokens = 0
            
            while (batch_end < len(current_fragments) and 
                   batch_end - batch_start < MAX_FRAGMENTS_PER_BATCH):
                fragment_tokens = count_tokens(current_fragments[batch_end])
                # Account for prompt overhead and safety margin
                effective_limit = MAX_BATCH_TOKENS - PROMPT_OVERHEAD_TOKENS
                if batch_tokens + fragment_tokens > effective_limit and batch_end > batch_start:
                    break
                batch_tokens += fragment_tokens
                batch_end += 1
            
            # Ensure we always include at least one fragment
            if batch_end == batch_start:
                batch_end = batch_start + 1
            
            batch_fragments = current_fragments[batch_start:batch_end]
            effective_tokens = batch_tokens + PROMPT_OVERHEAD_TOKENS
            logger.info(f"Consolidating batch {batch_start//MAX_FRAGMENTS_PER_BATCH + 1}: "
                       f"{len(batch_fragments)} fragments, {batch_tokens} content tokens, "
                       f"{effective_tokens} total estimated tokens")
            
            # Save batch fragments for debugging/recovery
            if fragment_dir:
                batch_file = os.path.join(fragment_dir, f"batch_pass{pass_number}_{batch_start:03d}_{batch_end:03d}.txt")
                try:
                    with open(batch_file, 'w', encoding='utf-8') as f:
                        f.write("\n---\n".join(batch_fragments))
                    logger.debug(f"Saved batch to {batch_file}")
                except Exception as e:
                    logger.warning(f"Could not save batch: {e}")
            
            # Consolidate this batch
            if len(batch_fragments) == 1:
                # Single fragment, no consolidation needed
                consolidated_batch = batch_fragments[0]
            else:
                # Multiple fragments, consolidate them
                try:
                    consolidated_batch = await _consolidate_fragments_single_pass(
                        batch_fragments, api_key, model_name, retry_on_failure=True
                    )
                    
                    # Check if consolidation failed or was truncated
                    if (not consolidated_batch or 
                        consolidated_batch.startswith("ERROR:") or
                        count_tokens(consolidated_batch) < count_tokens("\n---\n".join(batch_fragments)) * 0.5):
                        logger.warning(f"Batch consolidation may have failed, using raw fragments")
                        consolidated_batch = "\n---\n".join(batch_fragments)
                        
                except Exception as e:
                    logger.error(f"Error consolidating batch: {e}, using raw fragments")
                    consolidated_batch = "\n---\n".join(batch_fragments)
            
            next_fragments.append(consolidated_batch)
            batch_start = batch_end
        
        current_fragments = next_fragments
        pass_number += 1
        
        # Safety check to prevent infinite loops
        if pass_number > 10:
            logger.warning("Maximum consolidation passes reached, stopping")
            break
    
    final_result = current_fragments[0] if current_fragments else ""
    logger.info(f"Multi-pass consolidation complete after {pass_number-1} passes")
    return final_result


async def _generate_definitions_and_interactions_with_resume(
    document_chunks: list[str],
    final_skf_glossary_content: str,
    library_name_param: str,
    gid_map: dict[str, str],
    definitions_file: str | None = None,
    api_key: str | None = None,
    model_name: str | None = None,
    force_reprocess: bool = False,
) -> str:
    """Generate definitions and interactions with resume capability."""
    
    # Check for existing definitions file (unless force_reprocess is True)
    if not force_reprocess and definitions_file and os.path.exists(definitions_file):
        try:
            with open(definitions_file, 'r', encoding='utf-8') as f:
                existing_definitions = f.read().strip()
            if existing_definitions:
                logger.info(f"Resuming from existing definitions file: {definitions_file}")
                logger.info(f"Loaded existing definitions ({count_tokens(existing_definitions)} tokens)")
                return existing_definitions
        except Exception as e:
            logger.warning(f"Could not load existing definitions: {e}, starting fresh")
    elif force_reprocess and definitions_file and os.path.exists(definitions_file):
        logger.info("Force reprocessing enabled, ignoring existing definitions")
    
    # Generate new definitions and interactions
    logger.info("SKF Pipeline - Step 2: Generating Definitions & Interactions...")
    final_skf_definitions_interactions_content = await _generate_definitions_and_interactions(
        document_chunks, final_skf_glossary_content, library_name_param, gid_map, api_key, model_name
    )
    
    # Save intermediate result
    if definitions_file:
        try:
            with open(definitions_file, 'w', encoding='utf-8') as f:
                f.write(final_skf_definitions_interactions_content)
            logger.info(f"Saved definitions to {definitions_file}")
        except Exception as e:
            logger.warning(f"Could not save definitions: {e}")
    
    return final_skf_definitions_interactions_content
