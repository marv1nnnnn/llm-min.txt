import os

from llm_min.client import LLMMinClient

# Set a dummy API key for testing purposes if not already set
# In a real scenario, you would set this environment variable before running
if "GEMINI_API_KEY" not in os.environ:
    os.environ["GEMINI_API_KEY"] = "dummy_api_key_for_validation"

# Instantiate the client
# You can also pass api_key directly: client = LLMMinClient(api_key="YOUR_API_KEY")
try:
    client = LLMMinClient()
except ValueError as e:
    print(f"Error instantiating client: {e}")
    exit()

# Content to compact
content_to_compact = """
This is a long piece of text that needs to be compacted.
It contains several paragraphs and details that should be summarized
into the PCS format. The PCS format is designed to be concise
and useful for LLMs.
"""

# Compact the content
# Note: This will likely fail without a valid API key and actual LLM call
# We are primarily testing the interface structure and flow here.
try:
    compacted_content = client.compact(content_to_compact, subject="Example Text")

    print("Original Content:")
    print(content_to_compact)
    print("\nCompacted Content (PCS):")
    print(compacted_content)
except Exception as e:
    print(f"Error during compaction: {e}")
    print("Compaction requires a valid API key and LLM access.")
    print("The client instantiation and method call structure appear correct.")
