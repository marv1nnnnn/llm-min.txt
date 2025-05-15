import logging
import asyncio
import re
import tiktoken # Added for token counting
from string import Template # We will use $variable for substitution in prompts
from datetime import datetime, timezone
from typing import List, Dict, Tuple, Optional, Set
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

def get_next_id(prefix: str, existing_ids: Set[str]) -> str:
    """Generates the next sequential ID (e.g., G001, D010)."""
    max_num = 0
    for eid in existing_ids:
        if eid.startswith(prefix):
            try:
                num = int(eid[len(prefix):])
                if num > max_num:
                    max_num = num
            except ValueError:
                continue # Should not happen with valid IDs
    return f"{prefix}{max_num + 1:03d}"

def parse_skf_lines(text: str, section_prefix: str) -> List[str]:
    """Parses SKF content and returns lines belonging to a specific prefix (G, D, I)."""
    if not text or not text.strip():
        return []
    return [line.strip() for line in text.splitlines() if line.strip().startswith(section_prefix)]

def extract_entity_from_g_line(g_line: str) -> Optional[str]:
    """Extracts EntityName from a Gxxx line. Gxxx:[TYP] EntityName - ..."""
    match = re.match(r"G\d{3,}:\s*\[[^\]]+\]\s*([^-\s]+)", g_line)
    return match.group(1) if match else None

def extract_gxxx_from_d_line(d_line: str) -> Optional[str]:
    """Extracts Gxxx from a Dxxx primary definition line. Dxxx:Gxxx_Entity ..."""
    match = re.match(r"D\d{3,}:\s*(G\d{3,})", d_line)
    return match.group(1) if match else None

def re_id_glossary_items(glossary_text: str) -> Tuple[str, Dict[str, str]]:
    """
    Re-numbers Gxxx IDs in a glossary text to be globally sequential.
    Returns the new glossary text and a mapping from old GIDs to new GIDs.
    Handles cases where LLM might output Gxxx, Gyy, Gzz etc.
    """
    if not glossary_text.strip():
        return "", {}

    lines = glossary_text.splitlines()
    new_lines = []
    old_to_new_gid_map: Dict[str, str] = {}
    current_g_id_val = 0

    # First pass: map old GIDs to new GIDs
    temp_gid_map: Dict[str, str] = {} # Stores original GID string to new GID string

    processed_entities_for_new_gids: Set[str] = set() # To ensure unique new GIDs per unique entity

    for line in lines:
        line = line.strip()
        if not line or not line.startswith("G"): # Skip empty or non-glossary lines
            if line: new_lines.append(line) # Keep other lines like comments or ---
            continue

        match = re.match(r"(G\w+):(\s*\[.*?\]\s*.*)", line) # Gxxx:, G1:, G_temp:
        if match:
            old_gid_str = match.group(1)
            entity_part = match.group(2).strip() # [TYP] EntityName - "Keywords" @DocRef

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
                first_occurrence_new_gid = ""
                # Find the new_gid associated with this entity_name
                # This is a bit tricky here, this re_id function assumes LLM did the merge
                # and is mostly about making Gxxx sequential. If LLM produces G1, G2 for the same thing,
                # this re-ID won't merge them, only re-ID G1 to G001, G2 to G002.
                # The prompt for Call 1.5 is key for actual merging.
                # This function is now simplified to just re-number whatever distinct lines it gets.
                current_g_id_val +=1
                new_gid = f"G{current_g_id_val:03d}"
                old_to_new_gid_map[old_gid_str] = new_gid
                new_lines.append(f"{new_gid}:{entity_part}")

        elif line: # Non-matching lines (e.g. format lines, comments)
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


def update_gxxx_references(text_content: str, gid_map: Dict[str, str]) -> str:
    """Updates all Gxxx references in a given text based on the old_to_new_gid_map."""
    if not text_content or not gid_map:
        return text_content
    
    updated_text = text_content
    # Sort keys by length descending to replace longer GIDs first (e.g., G10 before G1)
    sorted_old_gids = sorted(gid_map.keys(), key=len, reverse=True)
    for old_gid in sorted_old_gids:
        new_gid = gid_map[old_gid]
        # Use regex to ensure replacement of Gxxx as a whole word/identifier
        updated_text = re.sub(r'\b' + re.escape(old_gid) + r'\b', new_gid, updated_text)
    return updated_text

def count_tokens(text: str, model_name: str = "gpt-4o") -> int:
    """Counts the number of tokens in a text string using tiktoken."""
    if not text:
        return 0
    try:
        encoding = tiktoken.encoding_for_model(model_name)
    except KeyError:
        logger.warning(f"Warning: model {model_name} not found. Using cl100k_base encoding.")
        encoding = tiktoken.get_encoding("cl100k_base")
    return len(encoding.encode(text))

# --- Main Pipeline Function ---

async def _generate_global_glossary(
    document_chunks: List[str],
    api_key: str | None = None,
    model_name: str | None = None,
) -> Tuple[str, Dict[str, str]]:
    logger.info("SKF Pipeline - Step 1: Generating Global Glossary...")
    partial_glossary_outputs: List[str] = []
    num_doc_chunks = len(document_chunks)
    for i, doc_chunk_text in enumerate(document_chunks):
        logger.debug(f"Step 1: Processing glossary for document chunk {i+1}/{num_doc_chunks}")
        prompt_c1 = SKF_PROMPT_CALL1_GLOSSARY_TEMPLATE.substitute(input_document_text=doc_chunk_text)
        glossary_chunk_output = await generate_text_response(prompt_c1, api_key=api_key, model_name=model_name)
        if glossary_chunk_output and isinstance(glossary_chunk_output, str) and glossary_chunk_output.strip():
            partial_glossary_outputs.append(glossary_chunk_output.strip())
    
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
        if not raw_consolidated_glossary or not isinstance(raw_consolidated_glossary, str):
            logger.error("Step 1.5: Glossary consolidation by LLM failed or returned empty. Using raw fragments.")
            raw_consolidated_glossary = concatenated_fragments
        raw_consolidated_glossary = raw_consolidated_glossary.strip()

    final_skf_glossary_content, gid_map = re_id_glossary_items(raw_consolidated_glossary)
    if not final_skf_glossary_content.strip() and partial_glossary_outputs:
        logger.warning("Post re-ID, glossary content is empty. This might indicate issues in re_id_glossary_items or LLM output for consolidation.")
    
    logger.info(f"SKF Pipeline - Step 1 Complete: Global Glossary generated ({count_tokens(final_skf_glossary_content)} tokens, {len(gid_map)} map items). Kept in memory.")
    return final_skf_glossary_content, gid_map

async def _generate_definitions_and_interactions(
    document_chunks: List[str],
    final_skf_glossary_content: str,
    library_name_param: str,
    gid_map: Dict[str, str],
    api_key: str | None = None,
    model_name: str | None = None,
) -> str:
    logger.info("SKF Pipeline - Step 2: Generating Definitions & Interactions...")
    cumulative_definitions_items: List[str] = []
    cumulative_interactions_items: List[str] = []
    num_doc_chunks = len(document_chunks)
    
    definitions_header_block = (
        "# SECTION: DEFINITIONS (Prefix: D)\n"
        "# Format_PrimaryDef: Dxxx:Gxxx_Entity [DEF_TYP] [NAMESPACE \"relative.path\"] [OPERATIONS {op1:RetT(p1N:p1T); op2_static:RetT()}] [ATTRIBUTES {attr1:AttrT1(\"Def:Val\",\"RO\")}] [CONSTANTS {c1:ValT1(\"Val\")}] (\"Note\")\n"
        "# ---\""
    )
    interactions_header_block = (
        "# SECTION: INTERACTIONS (Prefix: I)\n"
        "# Format: Ixxx:Source_Ref INT_VERB Target_Ref_Or_Literal (\"Note_Conditions_Error(Gxxx_ErrorType)\")\n"
        "# ---\""
    )

    def assemble_di_text(definitions: List[str], interactions: List[str]) -> str:
        d_text = f"{definitions_header_block}\n" + "\n".join(definitions) if definitions else definitions_header_block + "\n# No definitions identified."
        i_text = f"{interactions_header_block}\n" + "\n".join(interactions) if interactions else interactions_header_block + "\n# No interactions identified."
        return f"{d_text}\n\n{i_text}"

    current_d_id = 0
    current_i_id = 0

    for i, doc_chunk_text in enumerate(document_chunks):
        logger.debug(f"Step 2: Processing D&I for document chunk {i+1}/{num_doc_chunks}")
        previous_di_content_for_context = assemble_di_text(cumulative_definitions_items, cumulative_interactions_items)

        if i == 0:
            prompt_c2_chunk = SKF_PROMPT_CALL2_DETAILS_SINGLE_CHUNK_TEMPLATE.substitute(
                skf_glossary_content=final_skf_glossary_content,
                document_chunk=doc_chunk_text,
                primary_namespace=library_name_param
            )
        else:
            prompt_c2_chunk = SKF_PROMPT_CALL2_DETAILS_ITERATIVE_TEMPLATE.substitute(
                skf_glossary_content=final_skf_glossary_content,
                previous_chunk_skf_details_content=previous_di_content_for_context,
                current_document_chunk=doc_chunk_text,
                primary_namespace=library_name_param
            )

        chunk_di_output_raw = await generate_text_response(prompt_c2_chunk, api_key=api_key, model_name=model_name)
        
        if chunk_di_output_raw and isinstance(chunk_di_output_raw, str):
            chunk_di_output = chunk_di_output_raw # update_gxxx_references(chunk_di_output_raw, gid_map) # Safety net

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

    final_skf_definitions_interactions_content = assemble_di_text(
        cumulative_definitions_items, cumulative_interactions_items
    )
    logger.info(f"SKF Pipeline - Step 2 Complete: D&I ({count_tokens(final_skf_definitions_interactions_content)} tokens).")
    return final_skf_definitions_interactions_content

async def _generate_usage_patterns(
    document_chunks: List[str],
    final_skf_glossary_content: str,
    final_skf_definitions_interactions_content: str,
    gid_map: Dict[str, str],
    api_key: str | None = None,
    model_name: str | None = None,
) -> str:
    logger.info("SKF Pipeline - Step 3: Generating Usage Patterns...")
    num_doc_chunks = len(document_chunks)
    usage_patterns_header_block = (
        "# SECTION: USAGE_PATTERNS (Prefix: U)\n"
        "# Format: U_Name:PatternTitleKeyword\n"
        "#         U_Name.N:[Actor_Or_Ref] ACTION_KEYWORD (Target_Or_Data_Involving_Ref) -> [Result_Or_State_Change_Involving_Ref]\n"
        "# ---\""
    )
    
    cumulative_usage_patterns_text = f"""{usage_patterns_header_block}
# No distinct critical usage patterns identified.
# ---"""

    for i, doc_chunk_text_for_usage in enumerate(document_chunks):
        logger.debug(f"Step 3: Processing Usage for document chunk {i+1}/{num_doc_chunks}")
        chunk_usage_output = None
        if i == 0:
            prompt_c3_chunk = SKF_PROMPT_CALL3_USAGE_SINGLE_CHUNK_TEMPLATE.substitute(
                skf_glossary_content=final_skf_glossary_content,
                final_skf_definitions_interactions_content=final_skf_definitions_interactions_content,
                document_chunk_for_usage=doc_chunk_text_for_usage
            )
            chunk_usage_output_raw = await generate_text_response(prompt_c3_chunk, api_key=api_key, model_name=model_name)
            chunk_usage_output = update_gxxx_references(chunk_usage_output_raw, gid_map) if chunk_usage_output_raw else ""
            if chunk_usage_output and isinstance(chunk_usage_output, str) and \
               "# No distinct critical usage patterns identified" not in chunk_usage_output and \
               chunk_usage_output.strip().startswith("# SECTION: USAGE_PATTERNS"):
                cumulative_usage_patterns_text = chunk_usage_output.strip()
        else:
            prompt_c3_iterative = SKF_PROMPT_CALL3_USAGE_ITERATIVE_TEMPLATE.substitute(
                skf_glossary_content=final_skf_glossary_content,
                cumulative_skf_details_content=final_skf_definitions_interactions_content,
                previous_chunk_skf_usage_content=cumulative_usage_patterns_text,
                current_document_chunk_for_usage=doc_chunk_text_for_usage
            )
            chunk_usage_output_raw = await generate_text_response(prompt_c3_iterative, api_key=api_key, model_name=model_name)
            chunk_usage_output = update_gxxx_references(chunk_usage_output_raw, gid_map) if chunk_usage_output_raw else ""
            if chunk_usage_output and isinstance(chunk_usage_output, str) and \
               chunk_usage_output.strip().startswith("# SECTION: USAGE_PATTERNS"):
                cumulative_usage_patterns_text = chunk_usage_output.strip()

    final_skf_usage_patterns_content = cumulative_usage_patterns_text
    logger.info(f"SKF Pipeline - Step 3 Complete: Usage Patterns ({count_tokens(final_skf_usage_patterns_content)} tokens).")
    return final_skf_usage_patterns_content

# --- Main Pipeline Function ---

async def compact_content_to_structured_text(
    full_content: str,
    library_name_param: str,
    library_version_param: str,
    chunk_size: int,
    api_key: str | None = None,
    model_name: str | None = None,
) -> str: # This will now return D, I, U only
    logger.info(f"Starting SKF/1.4 LA manifest generation for '{library_name_param}' (v{library_version_param}). V2 Pipeline.")
    current_utc_timestamp = datetime.now(timezone.utc).isoformat(timespec='seconds')
    source_doc_identifiers = [f"{library_name_param}-{library_version_param}"]

    document_chunks = chunk_content(full_content, chunk_size)
    if not document_chunks:
        logger.error("Full content resulted in no document chunks. Aborting.")
        return ""
    num_doc_chunks = len(document_chunks) # Used by helpers now
    logger.info(f"Initial content split into {num_doc_chunks} document chunk(s).")

    # Step 1: Generate Global Glossary
    final_skf_glossary_content, gid_map = await _generate_global_glossary(
        document_chunks, api_key, model_name
    )

    # Step 2: Generate Definitions & Interactions
    final_skf_definitions_interactions_content = await _generate_definitions_and_interactions(
        document_chunks, final_skf_glossary_content, library_name_param, gid_map, api_key, model_name
    )

    # Step 3: Generate Usage Patterns
    final_skf_usage_patterns_content = await _generate_usage_patterns(
        document_chunks, final_skf_glossary_content, final_skf_definitions_interactions_content, gid_map, api_key, model_name
    )

    # --- Final Assembly (D, I, U only) ---
    final_skf_manifest_parts = [
        f"# IntegratedKnowledgeManifest_SKF/1.4 LA",
        f"# SourceDocs: [{', '.join(source_doc_identifiers)}]",
        f"# GenerationTimestamp: {current_utc_timestamp}",
        f"# PrimaryNamespace: {library_name_param}",
        "",
        # Glossary is NOT included in the file output
        final_skf_definitions_interactions_content, # Contains D and I sections
        "",
        final_skf_usage_patterns_content,
        "",
        "# END_OF_MANIFEST"
    ]
    final_skf_manifest = "\n".join(final_skf_manifest_parts)

    logger.info(f"Successfully assembled final SKF manifest (D, I, U) for '{library_name_param}'. Total length: {count_tokens(final_skf_manifest)} tokens.")
    return final_skf_manifest.strip()