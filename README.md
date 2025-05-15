# llm-min.txt: Min.js Style Compression of Tech Docs for LLM Context 🤖

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/downloads/)
[![Gemini API](https://img.shields.io/badge/Gemini-API-green)](https://console.cloud.google.com/apis/api/gemini.googleapis.com/overview?project=llm-min)

## 📜 Table of Contents

- [llm-min.txt: Min.js Style Compression of Tech Docs for LLM Context 🤖](#llm-mintxt-minjs-style-compression-of-tech-docs-for-llm-context-)
  - [📜 Table of Contents](#-table-of-contents)
  - [What is `llm-min.txt` and Why is it Important?](#what-is-llm-mintxt-and-why-is-it-important)
  - [Understanding `llm-min.txt`: A Machine-Optimized Format 🧩](#understanding-llm-mintxt-a-machine-optimized-format-)
  - [Does it Really Work? Visualizing the Impact](#does-it-really-work-visualizing-the-impact)
  - [Quick Start 🚀](#quick-start-)
  - [Output Directory Structure 📂](#output-directory-structure-)
  - [Choosing the Right AI Model (Why Gemini) 🧠](#choosing-the-right-ai-model-why-gemini-)
  - [How it Works: A Look Inside (src/llm\_min) ⚙️](#how-it-works-a-look-inside-srcllm_min-️)
  - [What's Next? Future Plans 🔮](#whats-next-future-plans-)
  - [Common Questions (FAQ) ❓](#common-questions-faq-)
  - [Want to Help? Contributing 🤝](#want-to-help-contributing-)
  - [License 📜](#license-)

---

## What is `llm-min.txt` and Why is it Important?

If you've ever used an AI coding assistant (like GitHub Copilot, Cursor, or others powered by Large Language Models - LLMs), you've likely encountered situations where they don't know about the latest updates to programming libraries. This knowledge gap exists because AI models have a "knowledge cutoff" – a point beyond which they haven't learned new information. Since software evolves rapidly, this limitation can lead to outdated recommendations and broken code.

Several innovative approaches have emerged to address this challenge:
- <a href="https://llmstxt.org/"><img src="https://llmstxt.org/logo.png" alt="llms.txt logo" width="60" style="vertical-align:middle; margin-right:8px;"/></a> [llms.txt](https://llmstxt.org/)
  A community-driven initiative where contributors create reference files (`llms.txt`) containing up-to-date library information specifically formatted for AI consumption.

- <a href="https://context7.com/"><img src="https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcRbPuwKNduEABBD5gAZO_AS9z0FyUAml72j3g&s" alt="Context7 logo" width="60" style="vertical-align:middle; margin-left:4px;"/></a> [Context7](https://context7.com/)
  A service that dynamically provides contextual information to AIs, often by intelligently summarizing documentation.

While these solutions are valuable, they face certain limitations:
- `llms.txt` files can become extraordinarily large – some exceeding **800,000** tokens (word fragments). This size can overwhelm many AI systems' context windows.
  
    <img src="assets/token.png" alt="Token comparison for llms.txt" width="500"/>
    
    Many shorter `llms.txt` variants simply contain links to official documentation, requiring the AI to fetch and process those documents separately. Even the comprehensive versions (`llms-full.txt`) often exceed what most AI assistants can process at once. Additionally, these files may not always reflect the absolute latest documentation.

- `Context7` operates somewhat as a "black box" – while useful, its precise information selection methodology isn't fully transparent to users. It primarily works with GitHub code repositories or existing `llms.txt` files, rather than any arbitrary software package.

**`llm-min.txt` offers a fresh approach:**

<img src="assets/icon.png" alt="llm-min.txt icon" width="300"/>

Inspired by `min.js` files in web development (JavaScript with unnecessary elements removed), `llm-min.txt` adopts a similar philosophy for technical documentation. Instead of feeding an AI a massive, verbose manual, we leverage another AI to distill that documentation into a super-condensed, highly structured summary. The resulting `llm-min.txt` file captures only the most essential information needed to understand a library's usage, packaged in a format optimized for AI assistants rather than human readers.

Modern AI reasoning capabilities excel at this distillation process, creating remarkably efficient knowledge representations that deliver maximum value with minimal token consumption.

---
## Understanding `llm-min.txt`: A Machine-Optimized Format 🧩

The `llm-min.txt` file utilizes the **Structured Knowledge Format (SKF)** – a compact, machine-optimized format designed for efficient AI parsing rather than human readability. This format organizes technical information into distinct, highly structured sections with precise relationships.

**Key Elements of the SKF Format:**

1.  **Header Metadata:** Every file begins with essential contextual information:
    *   `# IntegratedKnowledgeManifest_SKF`: Format identifier and version
    *   `# SourceDocs: [...]`: Original documentation sources
    *   `# GenerationTimestamp: ...`: Creation timestamp
    *   `# PrimaryNamespace: ...`: Top-level package/namespace, critical for understanding import paths

2.  **Three Core Structured Sections:** The content is organized into distinct functional categories:
    *   `# SECTION: DEFINITIONS (Prefix: D)`: Describes the static aspects of the library:
        *   Canonical component definitions with unique global IDs (e.g., `D001:G001_MyClass`)
        *   Namespace paths relative to `PrimaryNamespace`
        *   Method signatures with parameters and return types
        *   Properties/fields with types and access modifiers
        *   Static relationships like inheritance or interface implementation
        *   **Important:** This section effectively serves as the glossary for the file, as the traditional glossary (`G` section) is used during generation but deliberately omitted from the final output to save space.

    *   `# SECTION: INTERACTIONS (Prefix: I)`: Captures dynamic behaviors within the library:
        *   Method invocations (`INVOKES`)
        *   Component usage patterns (`USES_COMPONENT`)
        *   Event production/consumption
        *   Error raising and handling logic, with references to specific error types

    *   `# SECTION: USAGE_PATTERNS (Prefix: U)`: Provides concrete usage examples:
        *   Common workflows for core functionality
        *   Step-by-step sequences involving object creation, configuration, method invocation, and error handling
        *   Each pattern has a descriptive name (e.g., `U_BasicCrawl`) with numbered steps (`U_BasicCrawl.1`, `U_BasicCrawl.2`)

3.  **Line-Based Structure:** Each item appears on its own line following precise formatting conventions that enable reliable machine parsing.

**Example SKF Format (Simplified):**

```text
# IntegratedKnowledgeManifest_SKF/1.4 LA
# SourceDocs: [example-lib-docs]
# GenerationTimestamp: 2024-05-28T12:00:00Z
# PrimaryNamespace: example_lib

# SECTION: DEFINITIONS (Prefix: D)
# Format_PrimaryDef: Dxxx:Gxxx_Entity [DEF_TYP] [NAMESPACE "relative.path"] [OPERATIONS {op1:RetT(p1N:p1T)}] [ATTRIBUTES {attr1:AttrT1}] ("Note")
# ---
D001:G001_Greeter [CompDef] [NAMESPACE "."] [OPERATIONS {greet:Str(name:Str)}] ("A simple greeter class")
D002:G002_AppConfig [CompDef] [NAMESPACE "config"] [ATTRIBUTES {debug_mode:Bool("RO")}] ("Application configuration")
# ---

# SECTION: INTERACTIONS (Prefix: I)
# Format: Ixxx:Source_Ref INT_VERB Target_Ref_Or_Literal ("Note_Conditions_Error(Gxxx_ErrorType)")
# ---
I001:G001_Greeter.greet INVOKES G003_Logger.log ("Logs greeting activity")
# ---

# SECTION: USAGE_PATTERNS (Prefix: U)
# Format: U_Name:PatternTitleKeyword
#         U_Name.N:[Actor_Or_Ref] ACTION_KEYWORD (Target_Or_Data_Involving_Ref) -> [Result_Or_State_Change_Involving_Ref]
# ---
U_BasicGreeting:Basic User Greeting
U_BasicGreeting.1:[User] CREATE (G001_Greeter) -> [greeter_instance]
U_BasicGreeting.2:[greeter_instance] INVOKE (greet name='Alice') -> [greeting_message]
# ---
# END_OF_MANIFEST
```

The `llm-min-guideline.md` file (generated alongside `llm-min.txt`) provides detailed decoding instructions and schema definitions that enable an AI to correctly interpret the SKF format. It serves as the essential companion document explaining the notation, field meanings, and relationship types used throughout the file.

---

## Does it Really Work? Visualizing the Impact

`llm-min.txt` achieves dramatic token reduction while preserving the essential knowledge needed by AI assistants. The chart below compares token counts between original library documentation (`llm-full.txt`) and the compressed `llm-min.txt` versions:

![Token Compression Comparison](assets/comparison.png)

These results demonstrate token reductions typically ranging from 90-95%, with some cases exceeding 97%. This extreme compression, combined with the highly structured SKF format, enables AI tools to ingest and process library documentation far more efficiently than with raw text.

In our samples directory, you can examine these impressive results firsthand:
*   `sample/crawl4ai/llm-full.txt`: Original documentation (uncompressed)
*   `sample/crawl4ai/llm-min.txt`: The compressed SKF representation
*   `sample/crawl4ai/llm-min-guideline.md`: The format decoder companion file

Most compressed files contain around 10,000 tokens – well within the processing capacity of modern AI assistants.

**How to use it?**

Simply reference the files in your AI-powered IDE's conversation, and watch your assistant immediately gain detailed knowledge of the library:

![Demo](assets/demo.gif)

---

## Quick Start 🚀

Getting started with `llm-min` is straightforward:

**1. Installation:**

*   **For regular users (recommended):**
    ```bash
    pip install llm-min

    # Install required browser automation tools
    playwright install
    ```

*   **For contributors and developers:**
    ```bash
    # Clone the repository (if not already done)
    # git clone https://github.com/your-repo/llm-min.git
    # cd llm-min

    # Create and activate a virtual environment
    python -m venv .venv
    source .venv/bin/activate  # On Windows: .venv\Scripts\activate

    # Install dependencies with UV (faster than pip)
    uv sync
    uv pip install -e .

    # Optional: Set up pre-commit hooks for code quality
    # uv pip install pre-commit
    # pre-commit install
    ```

**2. Set Up Your Gemini API Key:** 🔑

`llm-min` uses Google's Gemini AI to generate compressed documentation. You'll need a Gemini API key to proceed:

*   **Best practice:** Set an environment variable named `GEMINI_API_KEY` with your key value:
    ```bash
    # Linux/macOS
    export GEMINI_API_KEY=your_api_key_here
    
    # Windows (Command Prompt)
    set GEMINI_API_KEY=your_api_key_here
    
    # Windows (PowerShell)
    $env:GEMINI_API_KEY="your_api_key_here"
    ```

*   **Alternative:** Supply your key directly via the `--gemini-api-key` command-line option.

You can obtain a Gemini API key from the [Google AI Studio](https://aistudio.google.com/app/apikey) or Google Cloud Console.

**3. Generate Your First `llm-min.txt` File:** 💻

Choose one of the following input sources:

| Option              | Short | Type      | What it does                                                                 |
|---------------------|-------|-----------|------------------------------------------------------------------------------|
| `--output-dir`      | `-o`  | `DIRECTORY` | Where to save the generated files (default is a folder named `llm_min_docs`).|
| `--output-name`     | `-n`  | `TEXT`    | Give a custom name for the subfolder inside `output-dir`.                    |
| `--max-crawl-pages` | `-p`  | `INTEGER` | Max web pages to read (default: 200; 0 means no limit).                      |
| `--max-crawl-depth` | `-D`  | `INTEGER` | How many links deep to follow on a website (default: 2).                     |
| `--chunk-size`      | `-c`  | `INTEGER` | How much text to give the AI at once (default: 600,000 characters).          |
| `--gemini-api-key`  | `-k`  | `TEXT`    | Your Gemini API Key (if not set as an environment variable).                 |
| `--gemini-model`    | `-m`  | `TEXT`    | Which Gemini model to use (default: `gemini-2.5-flash-preview-04-17`).       |
| `--verbose`         | `-v`  |           | Show more detailed messages while it's working.                              |

**Key Command-Line Options:**

*   Process the Python package `typer`, read up to 50 web pages, and save to a folder called `my_docs`:
    ```bash
    llm-min -pkg "typer" -o my_docs -p 50 --gemini-api-key YOUR_API_KEY_HERE
    ```

**Example Commands:**

```bash
# Process the "typer" package, save to "my_docs" folder
llm-min -pkg "typer" -o my_docs -p 50

# Process the FastAPI documentation website
llm-min -u "https://fastapi.tiangolo.com/" -o my_docs -p 50

# Process documentation files in a local folder
llm-min -i "./docs" -o my_docs
```

**4. Programmatic Usage in Python:** 🐍

You can also integrate `llm-min` directly into your Python applications:

```python
from llm_min import LLMMinGenerator
import os

# Configuration for the AI processing
llm_config = {
    "api_key": os.environ.get("GEMINI_API_KEY"),  # Use environment variable
    "model_name": "gemini-2.5-flash-preview-04-17",  # Recommended model
    "chunk_size": 600000,  # Characters per AI processing batch
    "max_crawl_pages": 200,  # Maximum pages to crawl
    "max_crawl_depth": 3,  # Link following depth
}

# Initialize the generator (output files will go to ./my_output_docs/[package_name]/)
generator = LLMMinGenerator(output_dir="./my_output_docs", llm_config=llm_config)

# Generate llm-min.txt for the 'requests' package
try:
    generator.generate_from_package("requests")
    print("✅ Successfully created documentation for 'requests'!")
except Exception as e:
    print(f"❌ Error processing 'requests': {e}")

# Generate llm-min.txt from a documentation URL
try:
    generator.generate_from_url("https://bun.sh/llms-full.txt")
    print("✅ Successfully processed 'https://bun.sh/llms-full.txt'!")
except Exception as e:
    print(f"❌ Error processing URL: {e}")
```

For a complete list of command-line options, run:
```bash
llm-min --help
```
---

## Output Directory Structure 📂

When `llm-min` completes its processing, it creates the following organized directory structure:

```text
your_chosen_output_dir/
└── name_of_package_or_website/
    ├── llm-full.txt             # Complete documentation text (original content)
    ├── llm-min.txt              # Compressed SKF/1.4 LA structured summary
    └── llm-min-guideline.md     # Essential format decoder for AI interpretation
```

For example, running `llm-min -pkg "requests" -o my_llm_docs` produces:

```text
my_llm_docs/
└── requests/
    ├── llm-full.txt             # Original documentation
    ├── llm-min.txt              # Compressed SKF format (D, I, U sections)
    └── llm-min-guideline.md     # Format decoding instructions
```

**Important:** The `llm-min-guideline.md` file is a critical companion to `llm-min.txt`. It provides the detailed schema definitions and format explanations that an AI needs to correctly interpret the structured data. When using `llm-min.txt` with an AI assistant, always include this guideline file as well.

---

## Choosing the Right AI Model (Why Gemini) 🧠

`llm-min` utilizes Google's Gemini family of AI models for document processing. While you can select a specific Gemini model via the `--gemini-model` option, we strongly recommend using the default: `gemini-2.5-flash-preview-04-17`.

This particular model offers an optimal combination of capabilities for documentation compression:

1.  **Advanced Reasoning:** Excels at understanding complex technical documentation and extracting the essential structural relationships needed for the SKF format.

2.  **Exceptional Context Window:** With a 1-million token input capacity, it can process large documentation chunks at once, enabling more coherent and comprehensive analysis.

3.  **Cost Efficiency:** Provides an excellent balance of capability and affordability compared to other large-context models.

The default model has been carefully selected to deliver the best results for the `llm-min` compression process across a wide range of documentation styles and technical domains.

---

## How it Works: A Look Inside (src/llm_min) ⚙️

The `llm-min` tool employs a sophisticated multi-stage process to transform verbose documentation into a compact, machine-optimized SKF manifest:

1.  **Input Processing:** Based on your command-line options (e.g., `--package "requests"`), `llm-min` gathers documentation from the appropriate source (PyPI, web crawling, or local files).

2.  **Text Preparation:** The collected documentation is cleaned and segmented into manageable chunks for processing. The original text is preserved as `llm-full.txt`.

3.  **Three-Step AI Analysis Pipeline (Gemini):** This is the heart of the SKF manifest generation, orchestrated by the `compact_content_to_structured_text` function in `compacter.py`:

    *   **Step 1: Global Glossary Generation (Internal Only):**
        *   Each document chunk is analyzed using the `SKF_PROMPT_CALL1_GLOSSARY_TEMPLATE` prompt to identify key technical entities and generate a *chunk-local* glossary fragment with temporary `Gxxx` IDs.
        *   These fragments are consolidated via the `SKF_PROMPT_CALL1_5_MERGE_GLOSSARY_TEMPLATE` prompt, which resolves duplicates and creates a unified entity list.
        *   The `re_id_glossary_items` function then assigns globally sequential `Gxxx` IDs (G001, G002, etc.) to these consolidated entities.
        *   This global glossary is maintained in memory throughout the process but is **not included in the final `llm-min.txt` output** to conserve space.

    *   **Step 2: Definitions & Interactions (D & I) Generation:**
        *   For the first document chunk (or if there's only one chunk), the AI uses the `SKF_PROMPT_CALL2_DETAILS_SINGLE_CHUNK_TEMPLATE` with the global glossary to generate initial D and I items.
        *   For subsequent chunks, the `SKF_PROMPT_CALL2_DETAILS_ITERATIVE_TEMPLATE` is used, providing both the global glossary and previously generated D&I items as context to avoid duplication.
        *   As each chunk is processed, newly identified D and I items are accumulated and assigned sequential global IDs (D001, D002, etc. and I001, I002, etc.).

    *   **Step 3: Usage Patterns (U) Generation:**
        *   Similar to Step 2, the first chunk uses `SKF_PROMPT_CALL3_USAGE_SINGLE_CHUNK_TEMPLATE`, receiving the global glossary, all accumulated D&I items, and the current chunk text.
        *   Subsequent chunks use `SKF_PROMPT_CALL3_USAGE_ITERATIVE_TEMPLATE`, which additionally receives previously generated U-items to enable pattern continuation and avoid duplication.
        *   Usage patterns are identified with descriptive names (e.g., `U_BasicNetworkFetch`) and contain numbered steps (e.g., `U_BasicNetworkFetch.1`, `U_BasicNetworkFetch.2`).

4.  **Final Assembly:** The complete `llm-min.txt` file is created by combining:
    *   The SKF manifest header (protocol version, source docs, timestamp, primary namespace)
    *   The accumulated `DEFINITIONS` section
    *   The accumulated `INTERACTIONS` section
    *   The accumulated `USAGE_PATTERNS` section
    *   A final `# END_OF_MANIFEST` marker

**Conceptual Pipeline Overview:**

```
User Input      →  Doc Gathering   →  Text Processing   →  AI Step 1: Glossary   →  In-Memory Global    →  AI Step 2: D&I     →  Accumulated D&I
(CLI/Python)       (Package/URL)      (Chunking)           (Extract + Merge)        Glossary (Gxxx)        (Per chunk)          (Dxxx, Ixxx)
                                                                                                                                     ↓
           ┌─────────────────────────────────────────────────────────────────────────────────────────────────┐                      ↓
           ↓                                                                                                 ↑                      ↓
Final SKF Manifest   ←   Assembly   ←   Accumulated Usage   ←   AI Step 3: Usage   ←   Global Glossary + Accumulated D&I
(llm-min.txt)            (D,I,U)        Patterns (U_Name.N)      (Per chunk)           (Required context for generating valid U-items)
```

This multi-stage approach ensures that the SKF manifest is comprehensive, avoids duplication across chunks, and maintains consistent cross-references between entities, definitions, interactions, and usage patterns.

---

## What's Next? Future Plans 🔮

We're exploring several exciting directions to evolve `llm-min`:

*   **Public Repository for Pre-Generated Files** 🌐
    A central hub where the community could share and discover `llm-min.txt` files for popular libraries would be valuable. This would eliminate the need for individual users to generate these files repeatedly and ensure consistent, high-quality information. Key challenges include quality control, version management, and hosting infrastructure costs.

*   **Code-Based Documentation Inference** 💻
    An intriguing possibility is using source code analysis (via Abstract Syntax Trees) to automatically generate or augment documentation summaries. While initial experiments have shown this to be technically challenging, particularly for complex libraries with dynamic behaviors, it remains a promising research direction that could enable even more accurate documentation.

*   **Model Control Protocol Integration** 🤔
    While technically feasible, implementing `llm-min` as an MCP server doesn't fully align with our current design philosophy. The strength of `llm-min.txt` lies in providing reliable, static context – a deterministic reference that reduces the uncertainty sometimes associated with dynamic AI integrations. We're monitoring user needs to determine if a server-based approach might deliver value in the future.

We welcome community input on these potential directions!

---

## Common Questions (FAQ) ❓

**Q: Do I need a reasoning-capable model to generate an `llm-min.txt` file?** 🧠

A: Yes, generating an `llm-min.txt` file requires a model with strong reasoning capabilities like Gemini. The process involves complex information extraction, entity relationship mapping, and structured knowledge representation. However, once generated, the `llm-min.txt` file can be effectively used by any competent coding model (e.g., Claude 3.5 Sonnet) to answer library-specific questions.

**Q: Does `llm-min.txt` preserve all information from the original documentation?** 📚

A: No, `llm-min.txt` is explicitly designed as a lossy compression format. It prioritizes programmatically relevant details (classes, methods, parameters, return types, core usage patterns) while deliberately omitting explanatory prose, conceptual discussions, and peripheral information. This selective preservation is what enables the dramatic token reduction while maintaining the essential technical reference information an AI assistant needs.

**Q: Why does generating an `llm-min.txt` file take time?** ⏱️

A: Creating an `llm-min.txt` file involves a sophisticated multi-stage AI pipeline:
1. Gathering and preprocessing documentation
2. Analyzing each chunk to identify entities (glossary generation)
3. Consolidating entities across chunks
4. Extracting detailed definitions and interactions from each chunk
5. Generating representative usage patterns

This intensive process can take several minutes, particularly for large libraries. However, once created, the resulting `llm-min.txt` file can be reused indefinitely, providing much faster reference information for AI assistants.

**Q: I received a "Gemini generation stopped due to MAX_TOKENS limit" error. What should I do?** 🛑

A: This error indicates that the Gemini model reached its output limit while processing a particularly dense or complex documentation chunk. Try reducing the `--chunk-size` option (e.g., from 600,000 to 300,000 characters) to give the model smaller batches to process. While this might slightly increase API costs due to more separate calls, it often resolves token limit errors.

**Q: What's the typical cost for generating one `llm-min.txt` file?** 💰

A: Processing costs vary based on documentation size and complexity, but for a moderate-sized library, expect to spend between **$0.01 and $1.00 USD** in Gemini API charges. Key factors affecting cost include:
- Total documentation size
- Number of chunks processed
- Complexity of the library's structure
- Selected Gemini model

For current pricing details, refer to the [Google Cloud AI pricing page](https://cloud.google.com/vertex-ai/pricing#gemini).

**Q: Was this project developed using an AI pair programming approach?** 🤖

A: Yes, this project was developed using [Roocode](https://roocode.com/) with a custom configuration called [Rooroo](https://github.com/marv1nnnnn/rooroo), demonstrating the potential of human-AI collaboration in creating tools that enhance AI capabilities.

---

## Want to Help? Contributing 🤝

We welcome contributions to make `llm-min` even better! 🎉 

Whether you're reporting bugs, suggesting features, or submitting code changes via pull requests, your involvement helps improve this tool for everyone. Check our GitHub repository for contribution guidelines and open issues.

---

## License 📜

This project is licensed under the MIT License. See the `LICENSE` file for complete details.
