import logging
from urllib.parse import urlparse  # Import urlparse and urljoin

from crawl4ai import AsyncWebCrawler, CrawlerRunConfig
from crawl4ai.content_filter_strategy import (
    PruningContentFilter,
)  # Import PruningContentFilter
from crawl4ai.deep_crawling import (
    BestFirstCrawlingStrategy,
)  # Import BestFirstCrawlingStrategy for deep crawling
from crawl4ai.deep_crawling.filters import FilterChain, URLPatternFilter
from crawl4ai.markdown_generation_strategy import (
    DefaultMarkdownGenerator,
)  # Import DefaultMarkdownGenerator

logger = logging.getLogger(__name__)


def _get_base_path(url: str) -> str:
    """Extracts the base path (directory) from a URL."""
    parsed = urlparse(url)
    path = parsed.path
    # If the path ends with a filename (contains '.'), get the parent directory
    if "." in path.split("/")[-1]:
        path_parts = path.split("/")[:-1]
    else:
        # If it ends with a directory, ensure it ends with '/'
        path_parts = path.rstrip("/").split("/")

    base_directory_path = "/".join(path_parts) + "/"
    # Reconstruct the URL with only the scheme, netloc, and base directory path
    base_url = f"{parsed.scheme}://{parsed.netloc}{base_directory_path}"
    # Ensure the base URL ends with a slash
    if not base_url.endswith("/"):
        base_url += "/"
    return base_url


async def crawl_documentation(url: str, max_pages: int | None = 100, max_depth: int = 3) -> str | None:
    """Crawls a documentation URL using crawl4ai's deep crawling with content pruning,
    restricted to the same directory path as the final resolved URL after redirects.

    Args:
        url: The root URL to start crawling from.
        max_pages: Maximum number of pages to crawl (default: 500).
        max_depth: Maximum crawl depth relative to the starting URL (default: 2).

    Returns:
        Aggregated and pruned text content from crawled pages, or None if crawling fails.
    """
    logger.info(f"Starting crawl process for initial URL: {url} (max_pages={max_pages}, max_depth={max_depth})")
    try:
        logger.debug(f"Attempting crawl process for initial URL: {url}")
        async with AsyncWebCrawler() as crawler:
            # 1. Run initial fetch to resolve redirects without specific config
            logger.info(f"Performing initial fetch for URL: {url} to resolve redirects.")
            initial_result_list = await crawler.arun(url)  # Use default config for simple fetch

            final_url = url  # Default to original URL
            # Check if the initial fetch was successful and yielded a result
            if not initial_result_list or not initial_result_list[0].success:
                logger.warning(
                    f"Initial fetch failed or returned no success for URL: {url}. "
                    f"Proceeding with original URL for deep crawl."
                )
                # Log initial and final URLs even if fetch failed
                logger.info(f"Initial URL: {url}")
                logger.info(f"Final URL (using original due to fetch issue): {final_url}")
            else:
                initial_result = initial_result_list[0]  # Get the first page result
                # Determine the final URL to use for the deep crawl based on redirect
                if initial_result.redirected_url and initial_result.redirected_url != url:
                    final_url = initial_result.redirected_url
                    logger.info(f"Initial URL: {url}")
                    logger.info(f"Redirected to Final URL: {final_url}")
                else:
                    # No redirect or same URL, final_url remains the original url
                    logger.info(f"Initial URL: {url}")
                    logger.info(f"Final URL (no redirect): {final_url}")

            # --- Path Restriction Logic (Based on final_url) ---
            base_path_url = _get_base_path(final_url)  # Calculate base path from the final URL
            # The pattern ensures we stay within the directory structure of the final URL.
            pattern = f"^{base_path_url}.*"  # Match base path prefix + anything after
            logger.info(f"Restricting deep crawl to pattern based on final URL: {pattern}")
            path_filter = URLPatternFilter(patterns=[pattern])
            filter_chain = FilterChain(filters=[path_filter])
            # --- End Path Restriction Logic ---

            # 1. Configure the Content Filter (as before)
            prune_filter = PruningContentFilter(threshold=0.5, threshold_type="fixed", min_word_threshold=50)
            # 2. Configure the Markdown Generator with the filter (as before)
            md_generator = DefaultMarkdownGenerator(
                content_filter=prune_filter,  # Re-enable filter for testing
                options={"ignore_links": True},  # Optionally ignore links if desired
            )

            # Determine the effective max_pages for the crawler (as before)
            effective_max_pages = max_pages if max_pages is not None else 1_000_000
            logger.info(f"Effective max_pages for crawler: {effective_max_pages}")

            # 3. Configure the Crawler Run for Deep Crawl
            run_config = CrawlerRunConfig(
                deep_crawl_strategy=BestFirstCrawlingStrategy(
                    max_depth=max_depth,
                    max_pages=effective_max_pages,
                    filter_chain=filter_chain,  # Apply the path filter chain based on final_url
                    include_external=False,
                    # Optional: Add scorer
                ),
                markdown_generator=md_generator,
                word_count_threshold=40,  # Content filter is primary, but keep this low
                verbose=True,
            )

            # 4. Run the deep crawl using the final URL and the configured run_config
            logger.info(f"Starting deep crawl for resolved URL: {final_url} with config: {run_config}")
            # arun now uses the configured markdown generator and deep crawl strategy on the final URL
            results = await crawler.arun(final_url, config=run_config)  # Use final_url here

        # --- Aggregate Results (as before) ---
        if not results:
            logger.warning(f"Deep crawling returned no results starting from URL: {final_url} (original: {url})")
            return None

        aggregated_content = "\n\n---\n\n".join(
            [
                page.markdown.raw_markdown
                for page in results
                # Revert back to the original, simpler check
                if page.success and page.markdown and page.markdown.raw_markdown
            ]
        )

        if not aggregated_content:
            logger.warning(
                f"Deep crawling resulted in empty aggregated content for URL: {final_url} "
                f"(original: {url}) (possibly due to pruning filter)"
            )
            return None

        logger.info(
            f"Successfully deep crawled {len(results)} pages starting from {final_url} "
            f"(original: {url}). Aggregated content length after pruning: {len(aggregated_content)}"
        )
        return aggregated_content

    except Exception as e:
        # Log the original URL in case of error for better context
        logger.error(
            f"Crawling failed for initial URL {url} "
            f"(resolved to {final_url if 'final_url' in locals() else 'N/A'}): {e}",
            exc_info=True,
        )
        return None
