# Test Coverage Analysis Plan for `llm_min`

**Task:** task-test-analyze-001

**Objective:** Analyze the current test coverage for the `llm_min` package modules (`compacter`, `crawler`, `parser`, `search`, `main`) using `pytest-cov`, identify gaps, and document findings.

**Steps:**

1.  **Add Dependency:**
    *   Modify `pyproject.toml`.
    *   Add `"pytest-cov>=2.14"` (or latest stable version) to the `[project.optional-dependencies.dev]` list.
    *   Run `uv pip install -e .[dev]` to install the new dependency.

2.  **Run Coverage Analysis:**
    *   Execute the following command in the project root directory:
        ```bash
        pytest --cov=src/llm_min --cov-report=term-missing --cov-report=html tests/
        ```
    *   This command will:
        *   Run tests using `pytest`.
        *   Measure coverage for the `src/llm_min` directory.
        *   Generate a text report (`term-missing`) showing coverage percentages and missing lines directly in the terminal.
        *   Generate an HTML report in a `htmlcov/` directory for more detailed exploration.

3.  **Analyze and Document Results:**
    *   Examine the terminal output and the generated `htmlcov/index.html` report.
    *   Document the following in this spec file (or a separate results file linked here):
        *   **Overall Coverage Percentage:** The total coverage percentage reported.
        *   **Per-Module Coverage:**
            *   `src/llm_min/compacter.py`: XX%
            *   `src/llm_min/crawler.py`: XX%
            *   `src/llm_min/parser.py`: XX%
            *   `src/llm_min/search.py`: XX%
            *   `src/llm_min/main.py`: XX%
        *   **Identified Gaps:** List specific modules, functions, or lines identified as having low or no coverage. Prioritize critical functionality.

4.  **Define Follow-up Tasks:**
    *   Based on the analysis, define specific sub-tasks (e.g., `task-test-enhance-<module>-001`) to improve test coverage for the identified gaps.

**Expected Outputs:**

*   Updated `pyproject.toml` with `pytest-cov`.
*   Terminal output from the `pytest --cov` command.
*   Generated `htmlcov/` directory.
*   Updated documentation (this file or linked results) with coverage percentages and identified gaps.
*   Definitions for new sub-tasks to address coverage gaps.