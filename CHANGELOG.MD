# Changelog

## v0.3.0 - 2025-06-05
- **Enhanced Local Documentation Processing:**
    - Introduced `--input-folder` option for recursively scanning local directories (`.md`, `.txt`, `.rst` files).
    - Added file name headers when combining local content for better context.
- **Improved LLM Interaction and Robustness:**
    - Implemented dynamic chunk size calculation (`_calculate_optimal_chunk_size`) to adapt to content length, preventing `MAX_TOKENS` errors and improving reliability for large documents.
    - Set default `chunk_size` to `0` in CLI, which triggers optimal calculation.
    - Added conditional logic to use optimal chunk size when `0` is provided, otherwise use the specified value.
    - Introduced resume capabilities for definition generation, allowing processing to continue from existing intermediate files.
    - Added options to force reprocessing (`--force-reprocess`) and save intermediate fragments (`--save-fragments`).
    - Made Gemini API response handling more robust.
- **Documentation Updates:**
    - Updated `README.md` to reflect new input source options, configuration options, and detailed local folder processing.
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