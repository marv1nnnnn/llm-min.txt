# Changelog

## v0.2.4 - 2025-06-01
- Refactored asset handling for `llm_min_guideline.md`:
    - Moved guideline to `src/llm_min/assets/llm_min_guideline.md`.
    - Updated `src/llm_min/generator.py` to use `importlib.resources` to load the guideline.
    - Updated `pyproject.toml` to correctly package the assets.
## v0.2.3 - 2025-05-16
- Fix version issue
  
## v0.2.2 - 2025-05-16
- Fixed titoken import error

## v0.2.1 - 2025-05-16

- Moved `count_tokens` utility function to `src/llm_min/utils.py`.
- Added `generate_from_text` method to `LLMMinGenerator` in `src/llm_min/generator.py`. Fix [#2](https://github.com/marv1nnnnn/llm-min.txt/issues/2)
- Updated dependencies in `uv.lock`.
- Added new sample file `sample/agno/llm-full.txt`.