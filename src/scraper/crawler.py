import requests
from bs4 import BeautifulSoup
import json
import os
import logging
import time
import re
import urllib.parse
from datetime import datetime

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('kol_zchut_scraper')

# Create data directories if they don't exist
os.makedirs('data/raw', exist_ok=True)

class KolZchutScraper:
    def __init__(self):
        self.base_url = 'https://www.kolzchut.org.il'
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept-Language': 'he,en-US;q=0.9,en;q=0.8',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        }
        self.visited_urls = set()
        self.articles = []
        
    def fetch_page(self, url):
        """Fetch a webpage and return the soup object."""
        logger.info(f"Fetching page: {url}")
        try:
            # Add a small delay to avoid overwhelming the server
            time.sleep(1)
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return BeautifulSoup(response.content, 'html.parser')
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return None

    def extract_article_content(self, soup, url):
        """Extract article content from the soup."""
        if not soup:
            return None
            
        # Find the main content area
        content_div = soup.find('div', {'id': 'mw-content-text'})
        if not content_div:
            logger.warning(f"No content found on {url}")
            return None
            
        # Extract title
        title_elem = soup.find('h1', {'id': 'firstHeading'})
        title = title_elem.text.strip() if title_elem else "Unknown Title"
        
        # Extract categories
        categories = []
        category_links = soup.select('div.mw-normal-catlinks ul li a')
        for cat in category_links:
            categories.append(cat.text)
            
        # Extract the main text, removing navigation elements, tables, etc.
        paragraphs = []
        for p in content_div.find_all(['p', 'h2', 'h3', 'h4', 'li']):
            # Skip if it's hidden or part of navigation
            if p.parent.get('class') and ('toc' in p.parent.get('class') or 'navbox' in p.parent.get('class')):
                continue
                
            text = p.get_text().strip()
            if text:
                paragraphs.append(text)
                
        # Extract "See also" links for further crawling
        see_also_links = []
        see_also_section = soup.find('span', {'id': 'ראו_גם'})
        if see_also_section and see_also_section.parent:
            ul = see_also_section.parent.find_next('ul')
            if ul:
                for li in ul.find_all('li'):
                    link = li.find('a')
                    if link and link.get('href') and not link.get('href').startswith('#'):
                        see_also_links.append(self.base_url + link.get('href'))
        
        # Create article object
        article = {
            'title': title,
            'url': url,
            'categories': categories,
            'content': '\n'.join(paragraphs),
            'see_also': see_also_links,
            'crawled_at': datetime.now().isoformat()
        }
        
        return article
        
    def extract_links(self, soup, current_url):
        """Extract relevant links from the page for further crawling."""
        if not soup:
            return []
            
        links = []
        content_div = soup.find('div', {'id': 'mw-content-text'})
        if not content_div:
            return links
            
        # Find all links in the main content
        for a in content_div.find_all('a', href=True):
            href = a.get('href')
            
            # Skip external links, special pages, anchors, etc.
            if href.startswith('#') or ':' in href or 'action=' in href:
                continue
                
            # Ensure it's a full URL
            if href.startswith('/'):
                href = self.base_url + href
            elif not href.startswith(self.base_url):
                continue
                
            links.append(href)
            
        return links

    def crawl(self, start_url, max_articles=100):
        """Crawl the Kol Zchut website starting from the given URL."""
        # Start with the main page to find major categories
        main_page_url = "https://www.kolzchut.org.il/he/%D7%A2%D7%9E%D7%95%D7%93_%D7%A8%D7%90%D7%A9%D7%99"
        main_soup = self.fetch_page(main_page_url)
        
        if not main_soup:
            logger.error(f"Failed to fetch main page: {main_page_url}")
            return
            
        # Extract links from the main page
        to_visit = set(self.extract_links(main_soup, main_page_url))
        logger.info(f"Found {len(to_visit)} initial links from main page")
        
        # Add the original start URL if it's not in our list
        if start_url not in to_visit:
            to_visit.add(start_url)
        
        # Now start crawling
        while to_visit and len(self.articles) < max_articles:
            # Get next URL to visit
            current_url = to_visit.pop()
            
            # Skip if already visited
            if current_url in self.visited_urls:
                continue
                
            # Mark as visited
            self.visited_urls.add(current_url)
            
            # Fetch the page
            soup = self.fetch_page(current_url)
            if not soup:
                continue
                
            # Extract article content
            article = self.extract_article_content(soup, current_url)
            if article:
                self.articles.append(article)
                logger.info(f"Extracted article: {article['title']} ({len(self.articles)}/{max_articles})")
                
                # Save articles periodically
                if len(self.articles) % 10 == 0:
                    self.save_articles()
                    
                # Add "see also" links to visit
                for link in article['see_also']:
                    if link not in self.visited_urls:
                        to_visit.add(link)
            
            # Extract more links to visit
            new_links = self.extract_links(soup, current_url)
            for link in new_links:
                if link not in self.visited_urls:
                    to_visit.add(link)
                    
        # Save all articles at the end
        self.save_articles()
        logger.info(f"Crawling complete. Processed {len(self.articles)} articles.")
        
    def save_articles(self):
        """Save the extracted articles to a JSON file."""
        if not self.articles:
            logger.warning("No articles to save")
            return
            
        filename = f"data/raw/kol_zchut_articles_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.articles, f, ensure_ascii=False, indent=2)
            
        logger.info(f"Saved {len(self.articles)} articles to {filename}")

if __name__ == "__main__":
    scraper = KolZchutScraper()
    # Start with the main categories page instead of a specific rights page
    scraper.crawl("https://www.kolzchut.org.il/he/%D7%A2%D7%9E%D7%95%D7%93_%D7%A8%D7%90%D7%A9%D7%99", max_articles=50)