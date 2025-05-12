import logging
import re  # Import re

from duckduckgo_search import DDGS

from .llm import generate_text_response  # Import from .llm

logger = logging.getLogger(__name__)


def search_for_documentation_urls(package_name: str, num_results: int = 10) -> list[dict]:
    """Searches DuckDuckGo for potential documentation URLs for a package."""
    query = f"{package_name} package documentation website"
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


async def select_best_url_with_llm(
    package_name: str, search_results: list[dict], api_key: str | None = None, model_name: str | None = None
) -> str | None:
    """Uses an LLM to select the most likely official documentation URL from search results.
    (Async version)
    """
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
        f"Analyze the following search results for the package '{package_name}'. "
        f"Identify the single most likely URL pointing to the official or primary documentation root page. "
        f"STRONGLY PRIORITIZE URLs from readthedocs.io and github.io as they are common and reliable "
        f"documentation sources. "
        f"AVOID URLs from cloud service providers (e.g., google.cloud, aws.amazon.com, "
        f"azure.microsoft.com) unless they are the only documentation source. "
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
        llm_response = await generate_text_response(
            prompt, api_key=api_key, model_name=model_name
        )  # Await the async call
        logger.debug(f"LLM Response for {package_name}: {llm_response}")

        # llm_response is now a string (or error string)
        if not llm_response or llm_response.strip().lower() == "none" or "ERROR:" in llm_response:
            logger.warning(
                f"LLM could not identify a suitable documentation URL for {package_name}. Response: {llm_response}"
            )
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


async def find_documentation_url(
    package_name: str, api_key: str | None = None, model_name: str | None = None
) -> str | None:
    """Finds the most likely documentation URL for a package using search and LLM selection.
    (Async version)
    """
    search_results = search_for_documentation_urls(package_name)
    if not search_results:
        return None
    # Pass results and api_key and model_name to LLM for selection
    best_url_raw = await select_best_url_with_llm(
        package_name, search_results, api_key=api_key, model_name=model_name
    )  # Await async call
    if best_url_raw:
        # Clean the URL iteratively
        cleaned_url = best_url_raw
        previous_url = None
        while cleaned_url != previous_url:
            previous_url = cleaned_url
            # Remove common index files first
            cleaned_url = re.sub(r"/index\.html?$", "", cleaned_url)
            cleaned_url = re.sub(r"/index\.php$", "", cleaned_url)
            # Remove common version/language segments (including optional trailing slash)
            cleaned_url = re.sub(r"/(?:latest|stable|master|main|current|en)/?$", "", cleaned_url)
            # Remove trailing slash
            if cleaned_url.endswith("/"):
                cleaned_url = cleaned_url[:-1]

        logger.info(f"Cleaned URL for {package_name}: {cleaned_url} (from {best_url_raw})")
        return cleaned_url
    return None  # Return None if LLM selection failed
