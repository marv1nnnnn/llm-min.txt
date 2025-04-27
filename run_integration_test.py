import asyncio
import os
import sys
import logging
from typing import Dict, Any, List

# Ensure src is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))

from context_generator import generate_context_from_requirements

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Mock MCP Context ---
# Since we don't have the real MCP environment, we mock the tool call.
class MockMCPContext:
    async def use_tool(self, server_name: str, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"[MOCK MCP] Called use_tool: server='{server_name}', tool='{tool_name}', args={arguments}")
        query = arguments.get("query", "")
        results: List[Dict[str, str]] = []
        if server_name == "ddg-search" and tool_name == "search":
            if "requests python documentation" in query:
                results = [
                    {"url": "https://requests.readthedocs.io/en/latest/", "title": "Requests Docs", "snippet": "..."},
                    {"url": "https://docs.python-requests.org/en/master/", "title": "Requests Docs (alt)", "snippet": "..."},
                    {"url": "https://www.python-requests.org/", "title": "Requests Website", "snippet": "..."}, # Add a valid-looking one
                ]
            elif "numpy python documentation" in query:
                 results = [
                    {"url": "https://numpy.org/doc/stable/", "title": "NumPy Docs", "snippet": "..."},
                    {"url": "https://numpy.org/doc/stable/reference/index.html", "title": "NumPy Reference", "snippet": "..."},
                ]
            elif "nonexistent-pkg python documentation" in query:
                 results = [] # Simulate no results
            else:
                 results = [{"url": f"https://example.com/{query.split(' ')[0]}", "title": "Mock Result", "snippet": "..."}]

            logger.info(f"[MOCK MCP] Returning {len(results)} results for query '{query}'")
            return {"results": results}
        else:
            logger.warning(f"[MOCK MCP] Unknown tool call: {server_name}/{tool_name}")
            return {"error": f"Mock tool {server_name}/{tool_name} not implemented"}

# --- Test Setup ---
TEST_REQ_FILE = "requirements_integration_test.txt"
TEST_OUTPUT_FILE = "context_integration_test.md"
REQUIREMENTS_CONTENT = "requests\nnumpy\nnonexistent-pkg\n"

async def run_test():
    # 1. Create dummy requirements file
    logger.info(f"Creating dummy requirements file: {TEST_REQ_FILE}")
    with open(TEST_REQ_FILE, "w", encoding="utf-8") as f:
        f.write(REQUIREMENTS_CONTENT)

    # 2. Get API Key (optional)
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        logger.warning("GOOGLE_API_KEY not set. LLM compaction will be skipped.")
    else:
        logger.info("GOOGLE_API_KEY found. LLM compaction will be attempted.")

    # 3. Create Mock Context
    mock_context = MockMCPContext()

    # 4. Run the function
    logger.info("--- Running generate_context_from_requirements --- ")
    try:
        await generate_context_from_requirements(
            requirements_path=TEST_REQ_FILE,
            output_path=TEST_OUTPUT_FILE,
            mcp_context=mock_context, # Use the mock context
            llm_api_key=api_key,
            # Optional: Adjust other parameters like crawl_depth if needed
            # crawl_depth=1,
            # max_pages_per_library=5,
        )
        logger.info(f"--- Function execution completed --- ")
        logger.info(f"Output potentially generated at: {TEST_OUTPUT_FILE}")
        logger.info("Please inspect the output file for correctness.")

    except Exception as e:
        logger.error(f"An error occurred during generate_context_from_requirements: {e}", exc_info=True)

    finally:
        # 5. Clean up
        logger.info("Cleaning up temporary files...")
        if os.path.exists(TEST_REQ_FILE):
            os.remove(TEST_REQ_FILE)
            logger.info(f"Removed: {TEST_REQ_FILE}")
        # Keep the output file for inspection by default
        # if os.path.exists(TEST_OUTPUT_FILE):
        #     os.remove(TEST_OUTPUT_FILE)
        #     logger.info(f"Removed: {TEST_OUTPUT_FILE}")


if __name__ == "__main__":
    logger.info("Starting integration test script...")
    # Check if crawl4ai is potentially available (basic check)
    try:
        import crawl4ai
        logger.info(f"crawl4ai seems to be installed (version: {getattr(crawl4ai, '__version__', 'unknown')}). Crawling might occur.")
    except ImportError:
        logger.warning("crawl4ai not found. Crawling will be skipped by the function.")

    asyncio.run(run_test())
    logger.info("Integration test script finished.") 