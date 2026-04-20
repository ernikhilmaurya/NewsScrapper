import scrapy
from scrapy.exceptions import CloseSpider
import re

class TheIndianExpressSpider(scrapy.Spider):
    name = "theindianexpress"
    allowed_domains = ["indianexpress.com"]
    start_urls = ["https://indianexpress.com/"]
    
    # Limit the number of articles to scrape (optional)
    MAX_ARTICLES = 1000
    articles_scraped = 0

    def parse(self, response):
        # Extract all article links from the homepage
        # Look for links that typically lead to articles
        article_selectors = [
            'a[href*="/article/"]::attr(href)',
            'a[href*="/india/"]::attr(href)',
            'a[href*="/world/"]::attr(href)',
            'a[href*="/opinion/"]::attr(href)',
            'a[href*="/explained/"]::attr(href)',
            'a[href*="/cities/"]::attr(href)',
            'a[href*="/business/"]::attr(href)',
            'a[href*="/sports/"]::attr(href)',
            'a[href*="/entertainment/"]::attr(href)',
            'a[href*="/technology/"]::attr(href)',
        ]
        
        links = []
        for selector in article_selectors:
            links.extend(response.css(selector).getall())
        
        # Remove duplicates and filter
        unique_links = list(set(links))
        
        for link in unique_links:
            # Skip if it's not an article page (avoid pagination, category pages)
            if self.articles_scraped >= self.MAX_ARTICLES:
                self.logger.info(f"Reached maximum article limit ({self.MAX_ARTICLES})")
                return
                
            if self.is_article_url(link):
                yield response.follow(link, callback=self.parse_article)
                self.articles_scraped += 1

    def is_article_url(self, url):
        """Check if the URL is likely an article page"""
        # Skip common non-article patterns
        skip_patterns = [
            '/section/', '/photos/', '/videos/', '/web-stories/', 
            '/audio/', '/live-blog/', '/page/', '/?', '#',
            '/subscribe/', '/login/', '/profile/'
        ]
        
        for pattern in skip_patterns:
            if pattern in url:
                return False
        
        # Article URLs typically contain these patterns with numbers
        if '/article/' in url or re.search(r'/\d+/', url):
            return True
            
        return False

    def parse_article(self, response):
        """Extract article data from individual article pages"""
        
        # Try multiple selectors for title
        title_selectors = [
            'h1::text',
            'h1.entry-title::text',
            'h1.article-title::text',
            'h1.title::text',
            'meta[property="og:title"]::attr(content)'
        ]
        
        title = None
        for selector in title_selectors:
            title = response.css(selector).get()
            if title:
                break
        
        # Try multiple selectors for author
        author_selectors = [
            'span.author-name::text',
            'a.author-name::text',
            'span.byline-author::text',
            'div.byline a::text',
            'span.writer-name::text',
            'meta[name="author"]::attr(content)',
            'meta[property="article:author"]::attr(content)'
        ]
        
        author = None
        for selector in author_selectors:
            author = response.css(selector).get()
            if author:
                author = author.strip()
                break
        
        # Try multiple selectors for date
        date_selectors = [
            'span.pub-date::text',
            'time.published::text',
            'time.entry-date::text',
            'span.date::text',
            'meta[property="article:published_time"]::attr(content)',
            'meta[name="publish-date"]::attr(content)'
        ]
        
        date = None
        for selector in date_selectors:
            date = response.css(selector).get()
            if date:
                date = date.strip()
                break
        
        # Extract content - try multiple paragraph selectors
        content_selectors = [
            'div.articlebodycontent div.schemaDiv p::text',
            'div.articlebodycontent p::text',
            'div.story-details p::text',
            'div.entry-content p::text',
            'div.content-area p::text',
            'div.article-content p::text',
            'div.full-story p::text',
            'div.normal p::text'
        ]
        
        content_parts = []
        for selector in content_selectors:
            paragraphs = response.css(selector).getall()
            if paragraphs:
                content_parts.extend([p.strip() for p in paragraphs if p.strip()])
        
        # If no paragraphs found with specific selectors, try all paragraphs
        if not content_parts:
            content_parts = response.css('p::text').getall()
            content_parts = [p.strip() for p in content_parts if p.strip() and len(p.strip()) > 30]
        
        # Join content parts
        content = " ".join(content_parts) if content_parts else None
        
        # Get category/section
        category = None
        breadcrumbs = response.css('.breadcrumb a::text, .breadcrumbs a::text, nav a::text').getall()
        if breadcrumbs and len(breadcrumbs) > 1:
            category = breadcrumbs[1].strip()
        
        # Extract image URL if available
        image_selectors = [
            'meta[property="og:image"]::attr(content)',
            'figure img::attr(src)',
            '.featured-image img::attr(src)',
            'img.wp-post-image::attr(src)'
        ]
        
        image_url = None
        for selector in image_selectors:
            image_url = response.css(selector).get()
            if image_url:
                break
        
        # Only yield if we have at least title and some content
        if title and content:
            yield {
                "title": title.strip() if title else None,
                "author": author,
                "date": date,
                "category": category,
                "content": content,
                "url": response.url,
                "image_url": image_url,
                "word_count": len(content.split()) if content else 0
            }
        else:
            self.logger.debug(f"Incomplete data for URL: {response.url}")
            
            # Still yield partial data for debugging
            yield {
                "title": title.strip() if title else None,
                "author": author,
                "date": date,
                "category": category,
                "content": content,
                "url": response.url,
                "image_url": image_url,
                "word_count": len(content.split()) if content else 0
            }