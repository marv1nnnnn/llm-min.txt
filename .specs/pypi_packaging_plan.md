# Technical Design: PyPI Packaging for llm-min

**Task:** `task-pypi-analyze-001`

**Objective:** Analyze the current project structure and configuration to define the necessary changes for packaging the project as `llm-min` on PyPI, including a functional CLI entry point.

## 1. Current State Analysis

*   **Project Root:** `c:/Users/PC/Documents/code/llm-min.txt`
*   **Source Code Directory:** `src/llm_min_generator/`
*   **Main Script:** `src/llm_min_generator/main.py`
*   **Configuration:** `pyproject.toml`
*   **Packaging Name:** `llm-min-generator` (in `pyproject.toml`)
*   **CLI Entry Point:** Defined as `llm-min = "llm_min_generator.main:app"` in `pyproject.toml`. The `main.py` uses `typer` for CLI argument parsing.

## 2. Proposed Changes

### 2.1. Target Directory Structure

The primary source code directory needs to be renamed to align with the desired package name.

*   **Rename:** `src/llm_min_generator/` -> `src/llm_min/`

The internal structure within `src/llm_min/` will remain the same initially.

```
src/
├── __init__.py
└── llm_min/           <-- Renamed directory
    ├── __init__.py
    ├── compacter.py
    ├── crawler.py
    ├── main.py        <-- Entry point script
    ├── parser.py
    ├── search.py
    └── llm/
        └── gemini.py
```

### 2.2. `pyproject.toml` Modifications

The following changes are required in `pyproject.toml`:

1.  **Update Project Name:**
    *   Change `[project].name` from `"llm-min-generator"` to `"llm-min"`.
2.  **Update CLI Script Entry Point:**
    *   Change `[project.scripts].llm-min` from `"llm_min_generator.main:app"` to `"llm_min.main:app"`.
3.  **(Optional but Recommended) Review Metadata:**
    *   Review and update `description`, `authors`, `license`, `keywords`, `classifiers`, etc., for PyPI suitability. This is outside the scope of the immediate structural change but important for a proper release.

**Example `pyproject.toml` Snippets (Changes Highlighted):**

```toml
[project]
# name = "llm-min-generator"  <-- Before
name = "llm-min"             # <-- After
version = "0.1.0" # Consider bumping version for release
description = "Generates minimal context for LLMs by scraping and summarizing documentation." # Example update
readme = "README.md"
requires-python = ">=3.11"
# ... other metadata ...
authors = [
  { name="Your Name", email="your.email@example.com" }, # Update author details
]
# ... dependencies ...

[project.scripts]
# llm-min = "llm_min_generator.main:app" # <-- Before
llm-min = "llm_min.main:app"           # <-- After
```

### 2.3. Code Modifications (`main.py`)

Based on the analysis of `src/llm_min_generator/main.py`:

*   **Relative Imports:** The script uses relative imports (e.g., `from .parser import parse_requirements`). Renaming the parent directory (`llm_min_generator` to `llm_min`) **should not** require changes to these imports, as they are relative to the package structure itself.
*   **CLI Logic:** The existing `typer` implementation is suitable for the `llm-min` entry point defined in `pyproject.toml`. No changes are needed here for the structural refactor.

**Conclusion:** No immediate code modifications within the Python files are anticipated solely due to the directory rename and `pyproject.toml` updates for packaging.

## 3. Implementation Sub-tasks

The following sub-tasks are proposed to implement these changes:

1.  **`task-pypi-refactor-structure-001` (Type: `chore`):**
    *   Rename the directory `src/llm_min_generator` to `src/llm_min`.
2.  **`task-pypi-config-toml-001` (Type: `chore`):**
    *   Modify `pyproject.toml` to update `[project].name` to `llm-min`.
    *   Modify `pyproject.toml` to update `[project.scripts].llm-min` to `llm_min.main:app`.
    *   (Optional) Review and update other project metadata in `pyproject.toml`.
3.  **`task-pypi-validate-001` (Type: `test`):**
    *   Install the package locally in editable mode (`pip install -e .` or `uv pip install -e .`).
    *   Run the CLI command (`llm-min --help` or a simple test command) to verify the entry point works correctly after the changes.
    *   Consider building the package (`uv build` or `python -m build`) to ensure the packaging process completes without errors.