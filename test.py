import asyncio
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig
from crawl4ai.deep_crawling import BestFirstCrawlingStrategy
# For deep crawling strategies, the metadata in CrawlResult often includes 'depth'.

async def main():
    # Configure the browser (optional, but good for verbose logging)
    browser_config = BrowserConfig(
        verbose=True  # Enable detailed logging for browser setup
    )

    # 1. Initialize BestFirstCrawlingStrategy
    # For BestFirstCrawlingStrategy, 'max_depth' controls how many levels deep to crawl.
    # 'url_scorer' is another important parameter for this strategy to prioritize URLs,
    # but it's optional. We'll omit it here for simplicity, relying on default behavior.
    deep_crawl_strategy = BestFirstCrawlingStrategy(
        max_depth=1,  # Crawl the starting page and pages linked directly from it.
        include_external=False # Keep the crawl within example.com for this test
    )

    # 2. Initialize CrawlerRunConfig
    # This configures a specific crawl operation.
    # We pass the deep_crawl_strategy and specify tags to exclude.
    # If "header" and "footer" are CSS classes (e.g., .header) or IDs (e.g., #footer),
    # you should use excluded_selector=".header, .footer" instead of excluded_tags.
    run_config = CrawlerRunConfig(
        deep_crawl_strategy=deep_crawl_strategy,
        excluded_tags=["header", "footer"],  # Assumes <header> and <footer> HTML tags
        verbose=True,  # Enable detailed logging for this specific crawl run
        # cache_mode=CacheMode.BYPASS # Uncomment to bypass cache for testing
    )

    # 3. Initialize AsyncWebCrawler and run the crawl
    # The 'async with' statement ensures resources are properly managed.
    async with AsyncWebCrawler(config=browser_config) as crawler:
        target_url = "https://example.com"
        print(f"Starting crawl for {target_url} using BestFirstCrawlingStrategy.")
        print(f"Configuration: max_depth={deep_crawl_strategy.max_depth}, excluding tags: {run_config.excluded_tags}")

        # When a deep_crawl_strategy is used, crawler.arun() typically returns a list of CrawlResult objects.
        crawl_results = await crawler.arun(
            url=target_url,
            config=run_config
        )

        print(f"\nCrawled {len(crawl_results)} page(s) in total.")

        if not crawl_results:
            print("No pages were crawled.")
            return

        for i, result in enumerate(crawl_results):
            print(f"\n--- Page {i+1} Information ---")
            print(f"  URL: {result.url}")
            print(f"  Depth: {result.metadata.get('depth', 'N/A')}") # Depth is often added by deep crawl strategies

            if result.success:
                print(f"  Status: Success")
                
                # Check raw HTML for presence of tags before cleaning (for info only)
                # The exclusion happens during the cleaning/scraping process.
                raw_html_lower = result.html.lower() if result.html else ""
                if "<header" in raw_html_lower:
                    print("  INFO: Raw HTML contained '<header>' tag(s).")
                if "<footer" in raw_html_lower:
                    print("  INFO: Raw HTML contained '<footer>' tag(s).")

                if result.markdown:
                    # result.markdown can be a string or a MarkdownGenerationResult object.
                    # Access .raw_markdown if it's an object, or use the string directly.
                    markdown_content = ""
                    if hasattr(result.markdown, 'raw_markdown') and result.markdown.raw_markdown is not None:
                        markdown_content = result.markdown.raw_markdown
                    elif isinstance(result.markdown, str):
                        markdown_content = result.markdown
                    else: # Fallback if markdown is an object but not MarkdownGenerationResult or is None
                        markdown_content = str(result.markdown) if result.markdown is not None else ""
                        
                    print(f"  Markdown (first 300 chars): {markdown_content[:300]}...")
                    
                    # A simple check if the words "header" or "footer" appear in the final markdown.
                    # This is not definitive proof of tag exclusion but can be an indicator.
                    # True exclusion means the <header>...</header> elements are gone.
                    if "header" in markdown_content.lower() and "<header" not in markdown_content.lower():
                         print("  NOTE: The word 'header' appears in markdown text (could be legitimate content).")
                    if "footer" in markdown_content.lower() and "<footer" not in markdown_content.lower():
                         print("  NOTE: The word 'footer' appears in markdown text (could be legitimate content).")

                else:
                    print("  No markdown content generated for this page.")
                
                # You can inspect other parts of the result, e.g.:
                # print(f"  Cleaned HTML (first 100 chars): {result.cleaned_html[:100] if result.cleaned_html else 'N/A'}...")
                # print(f"  Links found: {len(result.links.get('internal', [])) if result.links else 0} internal, {len(result.links.get('external', [])) if result.links else 0} external")

            else:
                print(f"  Status: Failed")
                print(f"  Error: {result.error_message}")
                if result.status_code:
                    print(f"  Status Code: {result.status_code}")
        
        print("\nCrawl finished.")

if __name__ == "__main__":
    asyncio.run(main())