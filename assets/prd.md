1. Introduction & Goals
1.1. Purpose: This document outlines the design for a multi-stage pipeline that transforms extensive software library documentation into a highly compressed, structured, and machine-readable "Knowledge Base" (KB). This KB, along with a corresponding "Interpretation Guideline," will serve as efficient and effective context for a downstream Large Language Model (LLM) assistant, enabling it to answer user queries and generate code for the documented library.
1.2. Primary Goals:
Universality: The core pipeline logic and data structures should be adaptable to various software libraries with minimal library-specific customization in the prompts.
Token Efficiency: The final KB output must be extremely concise to minimize token consumption when used as LLM context.
Machine Readability: The KB format must be easily parsable and interpretable by an LLM, guided by an explicit schema.
Accuracy & Completeness: The KB should accurately represent the core functionalities, configurations, inputs, outputs, and relationships within the library.
Problem Solving: The KB + Guideline must enable a downstream LLM to map complex user intents (e.g., specific configurations, output modifications) to library features or suggest valid workarounds.
1.3. Non-Goals:
Generation of human-readable narrative tutorials from the KB.
Real-time updates to the KB based on live documentation changes (this is a batch process).
2. System Architecture & Pipeline Stages
The pipeline consists of four main stages:
Stage 0: Source Preparation & Intelligent Chunking (External/Semi-Automated)
Stage 1: Atomic Information Unit (AIU) Extraction (LLM-driven)
Stage 2: AIU Graph Construction & Refinement (Programmatic + Optional LLM)
Stage 3: Knowledge Base Serialization (Programmatic)
A separate "Interpretation Guideline" is also generated for the downstream LLM.
3. Detailed Stage Descriptions
3.1. Stage 0: Source Preparation & Intelligent Chunking
3.1.1. Input: Collection of raw source documentation files (formats: Markdown, HTML, PDF, ReStructuredText, etc.).
3.1.2. Process:
Filtering: Remove irrelevant documents (e.g., 404s, site navigation, non-technical blogs).
Normalization: Convert documents to a consistent plain text or simplified Markdown format where possible.
Intelligent Chunking: Segment the normalized documents into small, semantically coherent chunks. Each chunk should ideally describe a single, atomic software element (e.g., a function, a class method, a specific configuration object, a distinct feature paragraph).
Implementation Note: This stage may leverage external libraries or tools specialized in semantic chunking, layout-aware parsing, or even a preliminary LLM pass focused on segmentation. The output quality of this stage is critical.
3.1.3. Output: A list/collection of text chunks. Each chunk should have a unique source identifier (e.g., doc_filename:section_heading:chunk_index).
3.2. Stage 1: Atomic Information Unit (AIU) Extraction
3.2.1. Input: A single text chunk from Stage 0.
3.2.2. Process: For each input chunk, an LLM (e.g., GPT-4, Claude 3 Opus) will execute a prompt to extract information into a predefined textual AIU format.
3.2.3. AIU Textual Format (Output of LLM in this stage):
AIU_BEGIN
ID: {unique_chunk_id_or_derived_feature_hash}
TYPE: {Feature | ConfigObject | API_Endpoint | Function | ClassMethod | DataObject | ParameterSet}
NAME: {canonical_name_of_the_element}
PURPOSE: "{concise_purpose_description}"
INPUTS: [{PARAM:"{param_name}",TYPE:"{param_type}",DESC:"{brief_desc}",DEFAULT:"{default_val}",EXAMPLE:"{example_val_or_pattern}"}, ...]
OUTPUTS: [{FIELD:"{output_name}",TYPE:"{output_type}",DESC:"{brief_desc_of_output}"}, ...]
USAGE_PATTERN: "{core_code_pattern_or_config_structure_example}"
RELATES_TO: [{ID:"{id_of_related_aiu}",TYPE:"{relationship_type (e.g., USES, CONFIGURES, RETURNS, ACCEPTS_AS_INPUT, IS_PART_OF, INSTANCE_OF)}"}, ...]
SOURCE_REF: "{original_chunk_source_identifier}"
AIU_END
Use code with caution.
3.2.4. LLM Prompt for AIU Extraction: (As defined in the previous response, emphasizing strict adherence to the format, conciseness, and factual extraction).
3.2.5. Output: A collection of textual AIU strings, one for each processed input chunk.
3.3. Stage 2: AIU Graph Construction & Refinement
3.3.1. Input: The collection of textual AIU strings from Stage 1.
3.3.2. Process:
Parsing: Programmatically parse each textual AIU string into an internal structured representation (e.g., Python objects, dictionary graph). Validate format compliance.
ID Canonicalization:
Establish a canonical ID for each unique software element.
Resolve variations in NAME fields from AIUs to map to these canonical IDs.
Update ID fields in AIUs and RELATES_TO.ID references to use canonical IDs.
Implementation Note: This may involve string similarity, alias lists, or an optional LLM pass for entity resolution if ambiguity is high.
AIU De-duplication: Identify and merge AIUs that represent the exact same software element extracted from different source chunks. Merge criteria will be based on canonical NAME, TYPE, and high similarity of PURPOSE, INPUTS, and OUTPUTS. An LLM can act as a final arbiter for complex merge decisions.
Relationship Graph Building & Enrichment:
Construct a directed graph where nodes are canonical AIUs and edges are defined by RELATES_TO fields.
Validate existing relationships (e.g., type consistency).
Infer implicit or missing relationships (e.g., if A USES B which RETURNS C, then A indirectly depends on C). An optional LLM pass can be used for inferring new relationships based on co-occurrence or semantic similarity of purposes.
Ensure bidirectional links where appropriate (e.g., CONFIGURES / IS_CONFIGURED_BY).
3.3.3. Output: A refined, de-duplicated set of AIUs, stored internally as a graph structure or a list of structured objects with validated relationships.
3.4. Stage 3: Knowledge Base (KB) Serialization
3.4.1. Input: The refined AIU graph/list from Stage 2.
3.4.2. Process: Programmatically traverse the AIU data structure and serialize it into the final, highly compressed textual KB format.
3.4.3. KB Textual Format (Final Output):
#LIB:{LibraryName}#VER:{LibraryVersion}#DATE:{Timestamp}
#SCHEMA_DEF_BEGIN
#AIU_F:id,typ,name,purp,in,out,use,rel,src # AIU fields
#IN_F:p,t,d,def,ex # Input item fields
#OUT_F:f,t,d # Output item fields
#REL_F:id,typ # Relates_to item fields
#SCHEMA_DEF_END

#AIU_L_BEGIN # AIU List
#AIU#id:{id1};typ:{type1};name:{name1};purp:"{purp1}";in:[{p:p1,t:t1,d:"d1",def:def1,ex:"ex1"}];out:[{f:f1,t:t1,d:"d1"}];use:"{use1}";rel:[{id:idx,typ:typx}]#END_AIU
#AIU#id:{id2};typ:{type2};name:{name2};purp:"{purp2}";in:[...];out:[...];use:"{use2}";rel:[...]#END_AIU
#AIU_L_END
Use code with caution.
Field name abbreviations (e.g., AIU_F, IN_F, purp, rel) are explicitly defined in SCHEMA_DEF.
Values containing spaces or special characters (like purpose descriptions or usage patterns) must be enclosed in double quotes. Quotes within these strings must be escaped (e.g., \").
Lists are [...], dictionaries/objects are {...}. Key-value pairs are key:value.
3.4.4. Output: A single plain text file containing the compressed Knowledge Base.
4. Interpretation Guideline for Downstream LLM
4.1. Purpose: To be provided to the downstream LLM along with the KB, instructing it on how to parse, interpret, and utilize the KB.
4.2. Content: (As defined in the previous response, under "Decompression Guideline / LLM System Prompt"). This guideline will explain:
The overall KB structure (#LIB, #SCHEMA_DEF, #AIU_L).
The meaning of abbreviations defined in SCHEMA_DEF.
How to interpret AIU fields (id, typ, name, purp, in, out, use, rel).
How to traverse relationships (rel) to find connected information.
How to map user intent to AIU in parameters and use patterns.
Crucially, how to handle cases where a user's specific constraint (e.g., "markdown with no headers") does not directly map to an available configuration in an AIU, instructing the LLM to state the limitation and propose valid workarounds (like post-processing) rather than inventing non-existent features.
5. Data Structures (Internal)
5.1. Chunk Object (Post-Stage 0):
source_id: Unique identifier of the source chunk.
text_content: Plain text of the chunk.
metadata: (Optional) Original document filename, section titles, etc.
5.2. Atomic Information Unit (AIU) Object (Internal representation post-Stage 1 parsing & during Stage 2):
id: String (canonical, unique)
type: Enum (Feature, ConfigObject, API_Endpoint, Function, ClassMethod, DataObject, ParameterSet)
name: String (canonical name)
purpose: String
inputs: List of InputParameter Objects
InputParameter Object: param_name, param_type (String, can be an AIU ID for object types), description, default_value, example_value
outputs: List of OutputField Objects
OutputField Object: field_name, output_type (String, can be an AIU ID for object types), description
usage_pattern: String (code or config template)
relationships: List of Relationship Objects
Relationship Object: target_aiu_id, relationship_type (Enum: USES, CONFIGURES, etc.)
source_references: List of String (original chunk source_ids that contributed to this AIU)
6. Error Handling & Validation
Stage 1: LLM output may not perfectly adhere to format. Implement robust parsing for textual AIUs with fallback mechanisms or re-prompting for malformed outputs.
Stage 2: Validate consistency of IDs and relationship types. Log unresolved references.
Stage 3: Ensure proper escaping of characters during serialization.
7. Evaluation Metrics (Conceptual)
Compression Ratio: (Size of original docs) / (Size of final KB).
Information Recall (Qualitative/Sampled): Does the KB contain the necessary information to address common use cases?
Downstream LLM Performance:
Accuracy of answers to test queries using the KB.
Correctness of generated code snippets.
Ability to correctly identify when a user's specific constraint cannot be met directly by the library and to suggest valid workarounds.
8. Technology Stack Considerations (Illustrative)