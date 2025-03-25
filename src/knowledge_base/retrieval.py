"""
Knowledge Base Builder for Zchut Voice Assistant

This module:
1. Loads the raw scraped content from JSON files
2. Processes and splits the content into appropriate chunks
3. Creates embeddings using a multilingual model 
4. Stores these embeddings in a ChromaDB vector database
5. Provides query functions for retrieval
"""

import os
import json
import logging
from typing import List, Dict, Any, Tuple
import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions
from chromadb.errors import InvalidCollectionException
from langchain.text_splitter import RecursiveCharacterTextSplitter
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("knowledge_base")

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RAW_DATA_DIR = os.path.join(BASE_DIR, "data", "raw")
DB_DIR = os.path.join(BASE_DIR, "data", "processed", "chroma_db")

# Ensure directories exist
os.makedirs(DB_DIR, exist_ok=True)

class ZchutKnowledgeBase:
    def __init__(self, collection_name="zchut_articles"):
        """Initialize the knowledge base with ChromaDB and multilingual embeddings."""
        self.collection_name = collection_name
        
        # Initialize ChromaDB client
        self.client = chromadb.PersistentClient(
            path=DB_DIR,
            settings=Settings(anonymized_telemetry=False)
        )
        
        # Use multilingual sentence-transformers model for Hebrew
        # This model has good support for Hebrew text
        self.embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="paraphrase-multilingual-mpnet-base-v2"
        )
        
        # Get or create collection
        try:
            self.collection = self.client.get_collection(
                name=collection_name,
                embedding_function=self.embedding_function
            )
            logger.info(f"Connected to existing collection '{collection_name}'")
        except InvalidCollectionException:
            self.collection = self.client.create_collection(
                name=collection_name,
                embedding_function=self.embedding_function
            )
            logger.info(f"Created new collection '{collection_name}'")
        
        # Text splitter for chunking
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,  # Characters per chunk
            chunk_overlap=200,  # Overlap to maintain context
            separators=["\n\n", "\n", ".", " ", ""],  # Preferred split points
            is_separator_regex=False,
        )

    def load_raw_data(self) -> List[Any]:
        """Load all JSON files from the raw data directory."""
        articles = []
        
        # Check if directory exists
        if not os.path.exists(RAW_DATA_DIR):
            logger.error(f"Raw data directory '{RAW_DATA_DIR}' does not exist. Please run the scraper first.")
            # Create sample data for testing
            logger.info("Creating a sample article for testing purposes...")
            sample_article = {
                "title": "Sample Rights Article",
                "content": "This is a sample article about rights in Israel. This is used for testing the knowledge base system.",
                "url": "https://example.com/sample",
                "category": "Testing",
                "last_updated": datetime.now().isoformat()
            }
            articles.append(sample_article)
            return articles
            
        for filename in os.listdir(RAW_DATA_DIR):
            if filename.endswith(".json"):
                file_path = os.path.join(RAW_DATA_DIR, filename)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        article_data = json.load(f)
                        articles.append(article_data)
                        logger.debug(f"Loaded article from {filename}")
                except Exception as e:
                    logger.error(f"Error loading {file_path}: {e}")
        
        if not articles:
            logger.warning("No articles found in the raw data directory. Creating a sample article for testing...")
            sample_article = {
                "title": "Sample Rights Article",
                "content": "This is a sample article about rights in Israel. This is used for testing the knowledge base system.",
                "url": "https://example.com/sample",
                "category": "Testing",
                "last_updated": datetime.now().isoformat()
            }
            articles.append(sample_article)
        
        logger.info(f"Loaded {len(articles)} articles from raw data directory")
        return articles

    def process_and_store(self, articles: List[Any]) -> None:
        """Process articles and store them in the vector database."""
        total_chunks = 0
        
        for article in articles:
            # Check if article is a list or a dictionary
            if isinstance(article, list):
                logger.info(f"Article is in list format, processing each item separately")
                for item in article:
                    self._process_single_article(item)
                    total_chunks += 1
                continue
                
            # Process as dictionary
            self._process_single_article(article)
            total_chunks += 1
            
        logger.info(f"Total documents added to the database: {total_chunks}")
    
    def _process_single_article(self, article: Dict[str, Any]) -> None:
        """Process a single article and add it to the database."""
        # Extract relevant fields, with safe fallbacks
        article_id = article.get("id", str(hash(str(article.get("url", "")) + str(article.get("title", "")))))
        title = article.get("title", "")
        content = article.get("content", "")
        url = article.get("url", "")
        category = article.get("category", "")
        last_updated = article.get("last_updated", datetime.now().isoformat())
            
        # Combine title and content for better context
        full_text = f"{title}\n\n{content}"
        
        # Skip empty content
        if not full_text.strip():
            logger.warning(f"Skipping article with empty content: {article_id}")
            return
            
        # Split into chunks
        chunks = self.text_splitter.split_text(full_text)
        chunk_ids = [f"{article_id}-{i}" for i in range(len(chunks))]
        
        # Prepare metadata for each chunk
        metadatas = [{
            "title": title,
            "url": url,
            "category": category,
            "last_updated": last_updated,
            "chunk_index": i,
            "total_chunks": len(chunks),
            "is_title_chunk": i == 0  # First chunk contains the title
        } for i in range(len(chunks))]
        
        # Add to collection (batched for efficiency)
        try:
            self.collection.add(
                ids=chunk_ids,
                documents=chunks,
                metadatas=metadatas
            )
            logger.info(f"Processed article: {title} - {len(chunks)} chunks")
        except Exception as e:
            logger.error(f"Error adding article '{title}' to database: {e}")

    def query(self, question: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Query the knowledge base for relevant chunks."""
        results = self.collection.query(
            query_texts=[question],
            n_results=top_k,
            include=["documents", "metadatas", "distances"]
        )
        
        logger.info(f"Query: '{question}' - Found {len(results['documents'][0])} results")
        
        # Format the results for easier consumption
        formatted_results = []
        for i, (doc, metadata, distance) in enumerate(zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0]
        )):
            formatted_results.append({
                "content": doc,
                "metadata": metadata,
                "relevance_score": 1 - (distance / 2),  # Normalize to 0-1 scale
                "rank": i + 1
            })
            
        return formatted_results

    def get_collection_stats(self) -> Dict[str, Any]:
        """Get statistics about the collection."""
        count = self.collection.count()
        return {
            "collection_name": self.collection_name,
            "document_count": count,
            "embedding_model": "paraphrase-multilingual-mpnet-base-v2",
            "database_path": DB_DIR
        }


def main():
    """Main function to build the knowledge base."""
    logger.info("Starting knowledge base building process...")
    
    kb = ZchutKnowledgeBase()
    
    # Load raw data
    articles = kb.load_raw_data()
    
    if not articles:
        logger.error("No articles found. Make sure you've run the web scraper first.")
        return
    
    # Process and store articles
    kb.process_and_store(articles)
    
    # Show collection stats
    stats = kb.get_collection_stats()
    logger.info(f"Knowledge base built successfully: {stats}")
    
    # Run a test query in Hebrew
    test_query = "מהן הזכויות שלי כפנסיונר?"  # "What are my rights as a pensioner?"
    results = kb.query(test_query)
    
    logger.info(f"Test query results: {len(results)} matches found")
    for i, result in enumerate(results):
        logger.info(f"Result {i+1} - Score: {result['relevance_score']:.3f}")
        logger.info(f"Title: {result['metadata']['title']}")
        logger.info(f"URL: {result['metadata']['url']}")
        logger.info(f"First 100 chars: {result['content'][:100]}...")
        logger.info("---")


if __name__ == "__main__":
    main()