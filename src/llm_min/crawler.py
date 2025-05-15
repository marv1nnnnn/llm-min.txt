import tiktoken
import logging
# Deduplicate pages with identical or extremely similar raw_markdown
from difflib import SequenceMatcher

from urllib.parse import urlparse  # Import urlparse

from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, BrowserConfig
from crawl4ai.content_filter_strategy import PruningContentFilter
from crawl4ai.content_scraping_strategy import LXMLWebScrapingStrategy
from crawl4ai.deep_crawling import (
    BestFirstCrawlingStrategy,
)  # Import BestFirstCrawlingStrategy for deep crawling
from crawl4ai.deep_crawling.filters import FilterChain, URLPatternFilter
from crawl4ai.markdown_generation_strategy import (
    DefaultMarkdownGenerator,
)  # Import DefaultMarkdownGenerator

logger = logging.getLogger(__name__)


def count_tokens(text: str, model_name: str = "gpt-4o") -> int:
    """Counts the number of tokens in a text string using tiktoken."""
    if not text:
        return 0
    try:
        encoding = tiktoken.encoding_for_model(model_name)
    except KeyError:
        logger.warning(f"Warning: model {model_name} not found. Using cl100k_base encoding.")
        encoding = tiktoken.get_encoding("cl100k_base")
    return len(encoding.encode(text))

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


async def crawl_documentation(url: str, max_pages: int | None = 200, max_depth: int = 3) -> str | None:
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
        browser_config = BrowserConfig(
            text_mode=True,  # Potentially faster by not rendering visual elements
            headless=True, # Keep headless
            java_script_enabled=True # Keep JS enabled for now, doc sites often need it
        )
        logger.debug(f"Attempting crawl process for initial URL: {url}")
        async with AsyncWebCrawler(config=browser_config) as crawler: # Pass browser_config
            # --- Path Restriction Logic (Based on initial url) ---
            base_path_url = _get_base_path(url)  # Calculate base path from the initial URL
            # The pattern ensures we stay within the directory structure of the final URL.
            pattern = f"{base_path_url}*"  # Match base path prefix + anything after
            logger.info(f"Restricting deep crawl to pattern based on final URL: {pattern}")
            path_filter = URLPatternFilter(patterns=[pattern])
            filter_chain = FilterChain(filters=[path_filter])
            # --- End Path Restriction Logic ---

            # 1. Configure the Content Filter
            prune_filter = PruningContentFilter(min_word_threshold=50) # Re-enable and configure filter
            # 2. Configure the Markdown Generator with the filter
            md_generator = DefaultMarkdownGenerator(
                content_filter=prune_filter,  # Use the pruning filter
                options={"ignore_links": True, "ignore_images": True},  # Optionally ignore links and images if desired
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
                scraping_strategy=LXMLWebScrapingStrategy(),
                verbose=True,
                # Relevance and Speed Optimizations:
                target_elements=["article", "main", "[role=main]", ".content", "#content"], # Focus on main content areas
                excluded_selector="nav, footer, header, aside, .sidebar, .menu, #navigation, #footer, .hero, .banner, .header, .footer, .nav, .toc, .table-of-contents, [role=navigation], [role=banner], [role=complementary]", # Exclude common irrelevant sections
                wait_until="load",  # Potentially faster than "domcontentloaded"
                semaphore_count=10,  # Increase concurrency
                page_timeout=45000, # Slightly reduced page timeout (default 60000)
            )

            # 4. Run the deep crawl using the final URL and the configured run_config
            # arun now uses the configured markdown generator and deep crawl strategy on the final URL
            results = await crawler.arun(url, config=run_config)  # Use initial url here

        # --- Aggregate Results (as before) ---
        if not results:
            logger.warning(f"Deep crawling returned no results starting from URL: {url} (original: {url})")
            return None

        def is_similar(a, b, threshold=0.97):
            # Use a high threshold for "extremely similar"
            return SequenceMatcher(None, a, b).ratio() >= threshold

        seen = []
        deduped_markdowns = []
        for page in results:
            if not (page.success and page.markdown and page.markdown.raw_markdown):
                continue
            raw_md = page.markdown.raw_markdown
            # Only deduplicate if the page is longer than 10,000 characters
            if len(raw_md) > 10_000:
                if any(raw_md == s or is_similar(raw_md, s) for s in seen):
                    continue
                seen.append(raw_md)
            deduped_markdowns.append(raw_md)

        aggregated_content = "\n\n---\n\n".join(deduped_markdowns)

        if not aggregated_content:
            logger.warning(
                f"Deep crawling resulted in empty aggregated content for URL: {url} "
                f"(original: {url}) (possibly due to pruning filter)"
            )
            return None

        logger.info(
            f"Successfully deep crawled {len(results)} pages starting from {url} "
            f"(original: {url}). Aggregated content token count after pruning: {count_tokens(aggregated_content)}"
            f"token characters: {len(aggregated_content)}"
        )
        return aggregated_content

    except Exception as e:
        # Log the original URL in case of error for better context
        logger.error(
            f"Crawling failed for initial URL {url} (resolved to {url if 'url' in locals() else 'N/A'}): {e}",
            exc_info=True,
        )
        return None
