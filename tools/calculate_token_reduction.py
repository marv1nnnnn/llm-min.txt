import os
import re
import sys

import tiktoken


def count_tokens(filepath, encoding_name="cl100k_base"):
    """Reads a file and counts tokens using tiktoken."""
    # Check if the filepath looks like a python executable path
    if re.search(r"/?bin/python\d?(\.\d+)?$", filepath):
        print(f"Error: Argument '{filepath}' looks like a Python executable path, not a file path.", file=sys.stderr)
        sys.exit(1)
    try:
        # Assuming tiktoken is installed in the venv
        encoding = tiktoken.get_encoding(encoding_name)
        with open(filepath, encoding="utf-8") as f:
            content = f.read()
        num_tokens = len(encoding.encode(content))
        return num_tokens
    except FileNotFoundError:
        print(f"Error: File not found at {filepath}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        # Print tiktoken import errors clearly
        if isinstance(e, ModuleNotFoundError):
            print(
                "Error: 'tiktoken' module not found. Ensure it's installed in the venv: .venv/bin/python -m pip install tiktoken",
                file=sys.stderr,
            )
        else:
            print(f"An error occurred processing {filepath}: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python calculate_token_reduction.py <original_file_path> <reduced_file_path>", file=sys.stderr)
        sys.exit(1)

    original_file_path = sys.argv[1]
    reduced_file_path = sys.argv[2]

    print(f"Calculating token counts for {original_file_path} and {reduced_file_path}...")

    # Add validation checks before counting tokens

    tokens_original = count_tokens(original_file_path)
    tokens_reduced = count_tokens(reduced_file_path)

    if tokens_original is not None and tokens_reduced is not None:
        reduction = tokens_original - tokens_reduced
        percentage_reduction = (reduction / tokens_original * 100) if tokens_original > 0 else 0

        print(f"Tokens in {os.path.basename(original_file_path)}: {tokens_original}")
        print(f"Tokens in {os.path.basename(reduced_file_path)}: {tokens_reduced}")
        print(f"Token Reduction: {reduction}")
        print(f"Percentage Reduction: {percentage_reduction:.2f}%")
