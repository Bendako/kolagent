# api/utils/vector_db.py
"""
Vector Database Integration for Zchut Voice Assistant

This module:
1. Handles connection to Pinecone Vector Database
2. Provides functions for querying the database
3. Manages embedding generation using the sentence-transformers model
"""

import os
import logging
from typing import List, Dict, Any, Optional
from pinecone import Pinecone, ServerlessSpec
from sentence_transformers import SentenceTransformer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("vector_db")

# Initialize Pinecone client
try:
    pc = Pinecone(api_key=os.environ.get("PINECONE_API_KEY"))
    logger.info("Pinecone client initialized")
except Exception as e:
    logger.error(f"Failed to initialize Pinecone client: {e}")
    pc = None

# Initialize the embedding model
try:
    model = SentenceTransformer("paraphrase-multilingual-mpnet-base-v2")
    logger.info("SentenceTransformer model loaded")
except Exception as e:
    logger.error(f"Failed to load SentenceTransformer model: {e}")
    model = None

def create_index(force: bool = False) -> bool:
    """
    Create Pinecone index. Only needs to be run once during setup.
    
    Args:
        force: If True, recreate index even if it exists
        
    Returns:
        bool: Success status
    """
    if pc is None:
        logger.error("Cannot create index: Pinecone client not initialized")
        return False
        
    try:
        # Check if index already exists
        existing_indexes = [index.name for index in pc.list_indexes()]
        
        if "zchut-knowledge-base" in existing_indexes:
            if force:
                logger.info("Deleting existing index")
                pc.delete_index("zchut-knowledge-base")
            else:
                logger.info("Index already exists, skipping creation")
                return True
                
        # Create new index
        pc.create_index(
            name="zchut-knowledge-base",
            dimension=768,  # Dimension for multilingual-mpnet-base-v2
            metric="cosine",
            spec=ServerlessSpec(
                cloud="aws",
                region="us-west-2"
            )
        )
        logger.info("Created new Pinecone index: zchut-knowledge-base")
        return True
    except Exception as e:
        logger.error(f"Error creating index: {e}")
        return False

def get_index():
    """Get the Pinecone index object."""
    if pc is None:
        logger.error("Cannot get index: Pinecone client not initialized")
        return None
        
    try:
        return pc.Index("zchut-knowledge-base")
    except Exception as e:
        logger.error(f"Error getting index: {e}")
        return None

# Connect to existing index
index = get_index()

def query_knowledge_base(question: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """
    Query the knowledge base with a natural language question.
    
    Args:
        question: The question to ask
        top_k: Number of results to return
        
    Returns:
        List of formatted results
    """
    if model is None or index is None:
        logger.error("Cannot query: Model or index not initialized")
        return []
        
    try:
        # Generate embeddings for the query
        query_embedding = model.encode(question)
        
        # Query Pinecone
        results = index.query(
            vector=query_embedding.tolist(),
            top_k=top_k,
            include_metadata=True
        )
        
        # Format results
        formatted_results = []
        for match in results.matches:
            formatted_results.append({
                "content": match.metadata.get("content", ""),
                "metadata": {
                    "title": match.metadata.get("title", ""),
                    "url": match.metadata.get("url", ""),
                    "category": match.metadata.get("category", "")
                },
                "relevance_score": match.score,
            })
                
        logger.info(f"Query: '{question}' - Found {len(formatted_results)} results")
        return formatted_results
    except Exception as e:
        logger.error(f"Error querying knowledge base: {e}")
        return []

def get_db_stats() -> Dict[str, Any]:
    """Get statistics about the vector database."""
    if index is None:
        return {
            "status": "not_connected",
            "error": "Vector database not initialized"
        }
        
    try:
        index_stats = index.describe_index_stats()
        return {
            "status": "active",
            "vector_count": index_stats.get("total_vector_count", 0),
            "dimension": 768,
            "embedding_model": "paraphrase-multilingual-mpnet-base-v2"
        }
    except Exception as e:
        logger.error(f"Error getting database stats: {e}")
        return {
            "status": "error",
            "error": str(e)
        }

# Import functions (put this at the end of the script)
def add_documents(documents):
    """
    Add documents to the vector database
    
    Args:
        documents: List of document dictionaries with 'content', 'title', 'url', etc.
    """
    if model is None or index is None:
        logger.error("Cannot add documents: Model or index not initialized")
        return False
        
    try:
        vectors = []
        for i, doc in enumerate(documents):
            # Generate embedding for document
            embedding = model.encode(doc["content"])
            
            vectors.append({
                "id": doc.get("id", f"doc-{i}"),
                "values": embedding.tolist(),
                "metadata": {
                    "content": doc["content"],
                    "title": doc.get("title", ""),
                    "url": doc.get("url", ""),
                    "category": doc.get("category", ""),
                    "last_updated": doc.get("last_updated", "")
                }
            })
            
            # Batch updates (max 100 vectors per request)
            if len(vectors) >= 100:
                index.upsert(vectors=vectors)
                vectors = []
        
        # Insert any remaining vectors
        if vectors:
            index.upsert(vectors=vectors)
            
        return True
    except Exception as e:
        logger.error(f"Error adding documents: {e}")
        return False