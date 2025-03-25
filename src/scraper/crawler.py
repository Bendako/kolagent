"""
Kol Zchut Web Scraper

This module contains functions to scrape content from the Kol Zchut website (כל זכות)
and store it in a structured format for later processing.
"""

import os
import json
import time
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("scraper.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("kol_zchut_scraper")

# Constants
BASE_URL = "https://www.kolzchut.org.il"
HEADERS = {
    "User-Agent": "Zchut Voice Assistant Project/1.0 (Educational Purpose) Contact: your.email@example.com",
    "Accept-Language": "he-IL,he;q=0.9,en-US;q=0.8,en;q=0.7"
}
DELAY = 1  # Delay between requests in seconds to avoid overloading the server

# Ensure the data directory exists
os.makedirs("data/raw", exist_ok=True)

def get_page_content(url: str) -> Optional[BeautifulSoup]:
    """
    Fetch the content of a webpage and parse it with BeautifulSoup.
    
    Args:
        url: The URL to fetch
        
    Returns:
        BeautifulSoup object or None if request fails
    """
    try:
        logger.info(f"Fetching page: {url}")
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()
        
        # Ensure correct encoding for Hebrew content
        response.encoding = 'utf-8'
        
        soup = BeautifulSoup(response.text, 'html.parser')
        time.sleep(DELAY)  # Be respectful to the server
        return soup
    except Exception as e:
        logger.error(f"Error fetching {url}: {str(e)}")
        return None

def extract_article_content(soup: BeautifulSoup) -> Dict[str, Any]:
    """
    Extract the relevant content from a Kol Zchut article page.
    
    Args:
        soup: BeautifulSoup object of the article page
        
    Returns:
        Dictionary containing the structured article data
    """
    # Initialize the article data structure
    article_data = {
        "title": "",
        "summary": "",
        "sections": [],
        "categories": [],
        "last_updated": "",
        "source_url": ""
    }
    
    try:
        # Extract the article title
        title_elem = soup.find('h1', class_='firstHeading')
        if title_elem:
            article_data["title"] = title_elem.text.strip()
        
        # Extract the article content
        content_div = soup.find('div', id='mw-content-text')
        if not content_div:
            return article_data
        
        # Extract summary (typically first paragraph)
        summary = content_div.find('p')
        if summary:
            article_data["summary"] = summary.text.strip()
        
        # Extract sections
        sections = []
        current_section = {"title": "Main", "content": ""}
        
        for element in content_div.find_all(['h2', 'h3', 'p', 'ul']):
            if element.name in ['h2', 'h3']:
                # Save the previous section if it has content
                if current_section["content"].strip():
                    sections.append(current_section)
                
                # Start a new section
                current_section = {
                    "title": element.text.strip(),
                    "content": ""
                }
            elif element.name == 'p':
                current_section["content"] += element.text.strip() + "\n\n"
            elif element.name == 'ul':
                # Process list items
                for li in element.find_all('li'):
                    current_section["content"] += "• " + li.text.strip() + "\n"
                current_section["content"] += "\n"
        
        # Add the last section
        if current_section["content"].strip():
            sections.append(current_section)
        
        article_data["sections"] = sections
        
        # Extract categories
        category_div = soup.find('div', id='catlinks')
        if category_div:
            categories = [cat.text.strip() for cat in category_div.find_all('a') if cat.text.strip()]
            article_data["categories"] = categories
        
        # Extract last updated date
        footer = soup.find('div', id='footer')
        if footer:
            last_updated = footer.find('li', id='lastmod')
            if last_updated:
                article_data["last_updated"] = last_updated.text.strip()
                
        # Add current URL
        article_data["source_url"] = soup.find('meta', property='og:url')['content'] if soup.find('meta', property='og:url') else ""
        
    except Exception as e:
        logger.error(f"Error extracting content: {str(e)}")
    
    return article_data

def extract_links_from_page(soup: BeautifulSoup, base_url: str) -> List[str]:
    """
    Extract all internal links from a page that point to articles.
    
    Args:
        soup: BeautifulSoup object
        base_url: The base URL for creating absolute URLs
        
    Returns:
        List of article URLs
    """
    links = []
    
    try:
        # Find the main content div
        content_div = soup.find('div', id='mw-content-text')
        if not content_div:
            return links
        
        # Extract all links
        for a_tag in content_div.find_all('a', href=True):
            href = a_tag['href']
            
            # Skip external links, special pages, and non-article links
            if (href.startswith('/he/') and 
                not href.startswith('/he/Special:') and 
                not href.startswith('/he/File:')):
                
                # Create absolute URL
                abs_url = urljoin(base_url, href)
                links.append(abs_url)
                
    except Exception as e:
        logger.error(f"Error extracting links: {str(e)}")
    
    return links

def crawl_category_page(category_url: str) -> List[str]:
    """
    Crawl a category page and extract all article links.
    
    Args:
        category_url: URL of the category page
        
    Returns:
        List of article URLs
    """
    article_urls = []
    soup = get_page_content(category_url)
    
    if not soup:
        return article_urls
    
    # Find the category members div
    category_members = soup.find('div', id='mw-pages')
    if not category_members:
        return article_urls
    
    # Extract all article links
    for a_tag in category_members.find_all('a', href=True):
        href = a_tag['href']
        
        # Skip non-article links
        if href.startswith('/he/') and not href.startswith('/he/Category:'):
            abs_url = urljoin(BASE_URL, href)
            article_urls.append(abs_url)
    
    # Check for next page link
    next_page = None
    for a_tag in category_members.find_all('a', href=True):
        if a_tag.text.strip() == 'הדף הבא':  # "Next page" in Hebrew
            next_url = urljoin(BASE_URL, a_tag['href'])
            next_page_urls = crawl_category_page(next_url)
            article_urls.extend(next_page_urls)
            break
    
    return article_urls

def save_article_data(article_data: Dict[str, Any], filename: str):
    """
    Save the article data to a JSON file.
    
    Args:
        article_data: Dictionary containing article data
        filename: Filename to save to
    """
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(article_data, f, ensure_ascii=False, indent=2)
        logger.info(f"Saved article data to {filename}")
    except Exception as e:
        logger.error(f"Error saving article data to {filename}: {str(e)}")

def crawl_and_save_articles(start_url: str, max_articles: int = 50):
    """
    Crawl the Kol Zchut website starting from a URL and save articles.
    
    Args:
        start_url: The URL to start crawling from
        max_articles: Maximum number of articles to crawl
    """
    visited_urls = set()
    to_visit = [start_url]
    article_count = 0
    
    while to_visit and article_count < max_articles:
        current_url = to_visit.pop(0)
        
        if current_url in visited_urls:
            continue
            
        visited_urls.add(current_url)
        soup = get_page_content(current_url)
        
        if not soup:
            continue
        
        # Check if this is an article page (has firstHeading and content)
        if soup.find('h1', class_='firstHeading') and soup.find('div', id='mw-content-text'):
            # Extract and save article content
            article_data = extract_article_content(soup)
            
            if article_data["title"]:
                # Create a filename based on the article title
                safe_title = "".join([c if c.isalnum() or c in [' ', '-', '_'] else '_' for c in article_data["title"]])
                safe_title = safe_title.replace(' ', '_')
                filename = f"data/raw/{safe_title}_{article_count}.json"
                
                save_article_data(article_data, filename)
                article_count += 1
                logger.info(f"Processed article {article_count}/{max_articles}: {article_data['title']}")
        
        # Extract links from the page
        new_links = extract_links_from_page(soup, BASE_URL)
        for link in new_links:
            if link not in visited_urls:
                to_visit.append(link)
    
    logger.info(f"Crawling complete. Processed {article_count} articles.")

def main():
    """Main entry point for the scraper."""
    # Example: start crawling from the main page
    start_url = "https://www.kolzchut.org.il/he/זכויות_אזרחיות_ופוליטיות"
    
    # Alternatively, crawl from a category page
    # start_url = "https://www.kolzchut.org.il/he/Category:זכויות_עובדים"
    
    logger.info("Starting Kol Zchut web scraper")
    crawl_and_save_articles(start_url, max_articles=10)  # Start with a small number for testing

if __name__ == "__main__":
    main()