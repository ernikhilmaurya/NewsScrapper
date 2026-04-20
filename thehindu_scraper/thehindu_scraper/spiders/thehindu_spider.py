import scrapy
from scrapy.http import HtmlResponse
import re
from datetime import datetime

class TheHinduSpider(scrapy.Spider):
    name = "thehindu"
    allowed_domains = ["thehindu.com"]
    start_urls = ["https://www.thehindu.com/"]
    
    custom_settings = {
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 2,
        'CONCURRENT_REQUESTS': 4,
    }

    def parse(self, response):
        """Parse the homepage and extract article links"""
        
        # Extract all article links from the homepage
        article_selectors = [
            'a[href*="/article"]::attr(href)',
            'a[href*="/news/"]::attr(href)',
            'a[href*="/opinion/"]::attr(href)',
            'a[href*="/business/"]::attr(href)',
            'a[href*="/sport/"]::attr(href)',
            'a[href*="/entertainment/"]::attr(href)',
            'a[href*="/sci-tech/"]::attr(href)',
            'a[href*="/data/"]::attr(href)',
            'a[href*="/education/"]::attr(href)',
        ]
        
        links = []
        for selector in article_selectors:
            links.extend(response.css(selector).getall())
        
        # Remove duplicates and filter
        unique_links = list(set(links))
        
        self.logger.info(f"Found {len(unique_links)} article links on homepage")
        
        for link in unique_links:
            # Follow only article links (contain /article/ or specific patterns)
            if '/article' in link or self.is_article_url(link):
                yield response.follow(link, callback=self.parse_article)

    def is_article_url(self, url):
        """Check if URL is likely an article"""
        article_patterns = [
            r'/article\d+\.ece',
            r'/news/',
            r'/opinion/',
            r'/business/',
            r'/sport/',
            r'/entertainment/',
            r'/sci-tech/',
        ]
        return any(re.search(pattern, url) for pattern in article_patterns)

    def parse_article(self, response):
        """Parse individual article pages"""
        
        # Extract title - multiple possible selectors
        title = (
            response.css('h1.title::text').get() or
            response.css('h1.article-title::text').get() or
            response.css('meta[property="og:title"]::attr(content)').get() or
            response.css('h1::text').get()
        )
        
        # Clean title
        if title:
            title = title.strip()
        
        # Extract author information
        author_selectors = [
            'a.person-name::text',
            'span.author-name::text',
            'div.by-line a::text',
            'meta[name="author"]::attr(content)',
            'a[rel="author"]::text',
        ]
        
        author = None
        for selector in author_selectors:
            author = response.css(selector).get()
            if author:
                break
        
        # Clean author
        if author:
            author = author.strip()
        
        # Extract publication date
        date_selectors = [
            'meta[property="article:published_time"]::attr(content)',
            'span.pub-date::text',
            'span.updated-time::attr(data-published)',
            'time::attr(datetime)',
            'span.date::text',
        ]
        
        date = None
        for selector in date_selectors:
            date = response.css(selector).get()
            if date:
                break
        
        # Extract article content
        content_parts = []
        
        # Try multiple content selectors
        content_selectors = [
            'div.articlebodycontent p::text',
            'div.articlebodycontent div p::text',
            'div.content p::text',
            'div.article-text p::text',
            'div#content p::text',
            'div.schemaDiv p::text',
        ]
        
        for selector in content_selectors:
            content_parts.extend(response.css(selector).getall())
        
        # Also try to get content from paragraphs with specific classes
        content_parts.extend(response.css('p[class*="body"]::text').getall())
        
        # Clean and join content
        cleaned_content = []
        for part in content_parts:
            if part and part.strip():
                cleaned_content.append(part.strip())
        
        # Extract article category/section
        section_selectors = [
            'a.label::text',
            'div.label a::text',
            'meta[property="article:section"]::attr(content)',
            'a[class*="section"]::text',
        ]
        
        section = None
        for selector in section_selectors:
            section = response.css(selector).get()
            if section:
                break
        
        # Extract image URL
        image_selectors = [
            'meta[property="og:image"]::attr(content)',
            'div.picture img::attr(src)',
            'figure img::attr(src)',
        ]
        
        image_url = None
        for selector in image_selectors:
            image_url = response.css(selector).get()
            if image_url and 'http' in image_url:
                break
        
        # Extract video information if present
        video_id = None
        video_url = None
        
        # Check for JWPlayer videos
        jwplayer_script = response.xpath('//script[contains(text(), "jwplatform.com/players/")]/text()').get()
        if jwplayer_script:
            video_match = re.search(r'players/([a-zA-Z0-9]+)-', jwplayer_script)
            if video_match:
                video_id = video_match.group(1)
                video_url = f"https://content.jwplatform.com/videos/{video_id}.mp4"
        
        # Check for iframe videos
        iframe_video = response.css('iframe[src*="youtube"]::attr(src), iframe[src*="jwplatform"]::attr(src)').get()
        if iframe_video:
            video_url = iframe_video
        
        # Extract key points or summary
        summary = (
            response.css('div.sub-text::text').get() or
            response.css('h2.summary::text').get() or
            response.css('div.article-summary::text').get()
        )
        
        # Check if it's premium content
        is_premium = bool(
            response.css('.premium-label::text') or
            response.css('span.premium::text') or
            'premium' in response.url
        )
        
        # Extract tags
        tags = response.css('a.tag::text, a[href*="/topic/"]::text').getall()
        tags = [tag.strip() for tag in tags if tag and tag.strip()]
        
        yield {
            'title': title,
            'author': author,
            'date': date,
            'section': section.strip() if section else None,
            'content': ' '.join(cleaned_content) if cleaned_content else None,
            'summary': summary.strip() if summary else None,
            'url': response.url,
            'image_url': image_url,
            'video_id': video_id,
            'video_url': video_url,
            'tags': tags,
            'is_premium': is_premium,
            'word_count': len(' '.join(cleaned_content).split()) if cleaned_content else 0,
        }