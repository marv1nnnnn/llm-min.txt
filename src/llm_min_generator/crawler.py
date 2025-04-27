import logging
from typing import Optional
from urllib.parse import urlparse, urljoin # Import urlparse and urljoin

from crawl4ai import AsyncWebCrawler, CrawlerRunConfig
from crawl4ai.deep_crawling import BestFirstCrawlingStrategy # Import BestFirstCrawlingStrategy for deep crawling
from crawl4ai.deep_crawling.filters import URLPatternFilter, FilterChain
from crawl4ai.content_filter_strategy import PruningContentFilter # Import PruningContentFilter
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator # Import DefaultMarkdownGenerator

logger = logging.getLogger(__name__)


def _get_base_path(url: str) -> str:
    """Extracts the base path (directory) from a URL."""
    parsed = urlparse(url)
    path = parsed.path
    # If the path ends with a filename (contains '.'), get the parent directory
    if '.' in path.split('/')[-1]:
        path_parts = path.split('/')[:-1]
    else:
        # If it ends with a directory, ensure it ends with '/'
        path_parts = path.rstrip('/').split('/')
    
    base_directory_path = "/".join(path_parts) + "/"
    # Reconstruct the URL with only the scheme, netloc, and base directory path
    base_url = f"{parsed.scheme}://{parsed.netloc}{base_directory_path}"
    # Ensure the base URL ends with a slash
    if not base_url.endswith('/'):
        base_url += '/'
    return base_url


async def crawl_documentation(url: str, max_pages: Optional[int] = 100, max_depth: int = 3) -> Optional[str]:
    """Crawls a documentation URL using crawl4ai's deep crawling with content pruning,
    restricted to the same directory path.

    Args:
        url: The root URL to start crawling from.
        max_pages: Maximum number of pages to crawl (default: 500).
        max_depth: Maximum crawl depth relative to the starting URL (default: 2).

    Returns:
        Aggregated and pruned text content from crawled pages, or None if crawling fails.
    """
    logger.info(f"Starting deep crawl for URL: {url} (max_pages={max_pages}, max_depth={max_depth}) with pruning and path restriction")
    try:
        # --- Path Restriction Logic ---
        base_path_url = _get_base_path(url)
        # We escape potential regex characters in the base_path_url just in case,
        # although URL characters are usually safe. For robustness, basic escaping helps.
        # The pattern ensures we stay within the directory structure.
        pattern = f"^{base_path_url}.*" # Simpler pattern: Match base path prefix + anything after
        logger.info(f"Restricting crawl to pattern: {pattern}")
        path_filter = URLPatternFilter(patterns=[pattern])
        filter_chain = FilterChain(filters=[path_filter])
        # --- End Path Restriction Logic ---

        # 1. Configure the Content Filter
        prune_filter = PruningContentFilter(
            threshold=0.5,
            threshold_type="fixed",
            min_word_threshold=50
        )
        # 2. Configure the Markdown Generator with the filter
        md_generator = DefaultMarkdownGenerator(
            content_filter=prune_filter,
            options={"ignore_links": True} # Optionally ignore links if desired
        )


        # Determine the effective max_pages for the crawler
        # Use a large number if None is provided, effectively simulating no limit
        effective_max_pages = max_pages if max_pages is not None else 1_000_000
        logger.info(f"Effective max_pages for crawler: {effective_max_pages}")

        # 3. Configure the Crawler Run
        run_config = CrawlerRunConfig(
            deep_crawl_strategy=BestFirstCrawlingStrategy(
                max_depth=max_depth,
                max_pages=effective_max_pages, # Use the determined effective value
                filter_chain=filter_chain, # <--- Apply the path filter chain
                include_external=False, # Assuming we want to stay within the domain
                # Optional: Add a scorer here if needed, e.g., url_scorer=KeywordRelevanceScorer(...)
            ),
            markdown_generator=md_generator, # Use the custom markdown generator
            word_count_threshold=40, # Apply filter logic instead of simple word count
            verbose=True # Enable verbose logging for debugging
        )

        logger.debug(f"Attempting to run deep crawl for URL: {url} with config: {run_config}")
        async with AsyncWebCrawler() as crawler:
            # arun now uses the configured markdown generator with the filter
            results = await crawler.arun(url, config=run_config)

        if not results:
            logger.warning(f"Crawling returned no results for URL: {url}")
            return None

        # Aggregate the already filtered content from successful crawled pages
        aggregated_content = "\n\n---\n\n".join(
            [page.markdown.raw_markdown for page in results if page.success and page.markdown and page.markdown.raw_markdown]
        )

        if not aggregated_content:
            # Log that content might have been pruned away entirely
            logger.warning(f"Crawling resulted in empty aggregated content for URL: {url} (possibly due to pruning filter)")
            return None

        logger.info(f"Successfully crawled {len(results)} pages starting from {url}. Aggregated content length after pruning: {len(aggregated_content)}")
        return aggregated_content

    except Exception as e:
        logger.error(f"Crawling failed for URL {url}: {e}", exc_info=True)
        return None