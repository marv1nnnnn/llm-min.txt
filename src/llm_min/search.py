import logging

from duckduckgo_search import DDGS

from .llm.gemini import generate_text_response  # Import the Gemini function

logger = logging.getLogger(__name__)


def search_for_documentation_urls(package_name: str, num_results: int = 10) -> list[dict]:
    """Searches DuckDuckGo for potential documentation URLs for a package."""
    query = f"{package_name} document website"
    logger.info(f"Searching for '{package_name}' documentation with query: '{query}'")
    try:
        with DDGS() as ddgs:
            # Use text search for general web results
            results = list(ddgs.text(query, max_results=num_results))
        logger.info(f"Found {len(results)} potential documentation links for {package_name}.")
        # Ensure results have expected keys, even if empty
        sanitized_results = [
            {
                "title": r.get("title", ""),
                "href": r.get("href", ""),
                "body": r.get("body", ""),
            }
            for r in results
        ]
        logger.info(f"Sanitized results: {sanitized_results}")
        return sanitized_results
    except Exception as e:
        logger.error(f"DuckDuckGo search failed for '{package_name}': {e}", exc_info=True)
        return []


def select_best_url_with_llm(package_name: str, search_results: list[dict], api_key: str | None = None) -> str | None:
    """Uses an LLM to select the most likely official documentation URL from search results."""
    if not search_results:
        logger.warning(f"No search results provided for {package_name} to select from.")
        return None

    # Prepare context for the LLM
    results_text = "\n".join(
        [
            f"Title: {res.get('title', '')}\nURL: {res.get('href', '')}\nSnippet: {res.get('body', '')}\n---"
            for res in search_results
        ]
    )
    prompt = (
        f"Analyze the following search results for the Python package '{package_name}'. "
        f"Identify the single most likely URL pointing to the official or primary documentation root page. "
        f"STRONGLY PRIORITIZE URLs from readthedocs.io and github.io as they are common and reliable documentation sources. "
        f"AVOID URLs from cloud service providers (e.g., google.cloud, aws.amazon.com, azure.microsoft.com) unless they are the only documentation source. "
        f"Also consider URLs containing the package name itself in the domain/path. "
        f"Prioritize official documentation sites over tutorials, blogs, or Stack Overflow. "
        f"DO NOT select PyPI (pypi.org) pages as they are not documentation sites. "
        f"Look for dedicated documentation sites that are specifically built for this project. "
        f"Output ONLY the selected URL, and nothing else. If no suitable URL is found, output 'None'."
        f"\n\nSearch Results:\n{results_text}"
    )

    logger.info(f"Asking LLM to select the best documentation URL for {package_name}.")
    try:
        # Call the LLM using Gemini provider, passing the API key
        llm_response = generate_text_response(prompt, api_key=api_key)  # Pass api_key
        logger.debug(f"LLM Response for {package_name}: {llm_response}")

        if not llm_response or llm_response.strip().lower() == "none":
            logger.warning(f"LLM could not identify a suitable documentation URL for {package_name}")
            return None

        selected_url = llm_response.strip()

        # Validate URL format
        if not selected_url.startswith(("http://", "https://")):
            logger.warning(f"LLM returned an invalid URL format for {package_name}: {selected_url}")
            return None

        logger.info(f"LLM selected documentation URL for {package_name}: {selected_url}")
        return selected_url

    except Exception as e:
        logger.error(
            f"LLM call failed during URL selection for {package_name}: {e}",
            exc_info=True,
        )
        return None


def find_documentation_url(package_name: str, api_key: str | None = None) -> str | None:
    """Finds the most likely documentation URL for a package using search and LLM selection."""
    search_results = search_for_documentation_urls(package_name)
    if not search_results:
        return None
    # Pass results and api_key to LLM for selection
    best_url_raw = select_best_url_with_llm(package_name, search_results, api_key=api_key)  # Pass api_key
    if best_url_raw:
        # Remove trailing 'index.html' if it exists
        best_url = (
            best_url_raw.replace("/index.html", "").replace("/master", "").replace("/latest", "").replace("/en", "")
        )
        # Remove trailing '/' if it exists
        if best_url.endswith("/"):
            best_url = best_url[:-1]
        return best_url
    return None  # Return None if LLM selection failed
