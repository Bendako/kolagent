"""
Zchut Voice Assistant API

This module provides the main FastAPI application that:
1. Handles voice/text queries about rights in Israel
2. Connects to the knowledge base to retrieve relevant information
3. Processes and returns appropriate responses
"""

import os
import sys
import logging
from typing import Dict, List, Any, Optional
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn

# Add parent directory to path to ensure imports work
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Import the knowledge base retriever
from src.knowledge_base.retrieval import ZchutKnowledgeBase

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("zchut_api")

# Initialize the knowledge base
try:
    knowledge_base = ZchutKnowledgeBase()
    logger.info("Knowledge base initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize knowledge base: {e}")
    knowledge_base = None

# Initialize FastAPI app
app = FastAPI(
    title="Zchut Voice Assistant API",
    description="API for retrieving rights information from Kol Zchut using natural language queries",
    version="0.1.0"
)

# Set up CORS to allow requests from the frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For development; restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Path to static files for the web interface
static_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "static")
if os.path.exists(static_path):
    app.mount("/static", StaticFiles(directory=static_path), name="static")
    logger.info(f"Mounted static files from {static_path}")
else:
    logger.warning(f"Static directory not found at {static_path}")

# Define Pydantic models for request/response validation
class QueryRequest(BaseModel):
    query: str
    language: str = "he"  # Default to Hebrew
    max_results: int = 5

class QueryResponse(BaseModel):
    query: str
    results: List[Dict[str, Any]]
    answer: str
    sources: List[Dict[str, Any]]

@app.get("/")
async def root():
    """Root endpoint that returns basic API information"""
    return {
        "name": "Zchut Voice Assistant API",
        "status": "active",
        "endpoints": [
            {"path": "/", "method": "GET", "description": "This information"},
            {"path": "/query", "method": "GET", "description": "Simple query endpoint"},
            {"path": "/api/query", "method": "POST", "description": "Full query endpoint with more options"}
        ]
    }

@app.get("/status")
async def status():
    """Check API and knowledge base status"""
    if knowledge_base is None:
        return {
            "api_status": "active",
            "kb_status": "not_initialized",
            "message": "Knowledge base failed to initialize"
        }
    
    # Get knowledge base stats
    try:
        kb_stats = knowledge_base.get_collection_stats()
        return {
            "api_status": "active",
            "kb_status": "active",
            "kb_stats": kb_stats
        }
    except Exception as e:
        logger.error(f"Error getting knowledge base stats: {e}")
        return {
            "api_status": "active",
            "kb_status": "error",
            "message": str(e)
        }

@app.get("/query")
async def simple_query(q: str = Query(..., description="The query text")):
    """Simple GET endpoint for querying the knowledge base"""
    if knowledge_base is None:
        raise HTTPException(
            status_code=503, 
            detail="Knowledge base not initialized"
        )
    
    # Log the incoming query
    logger.info(f"Received query: {q}")
    
    # Query the knowledge base
    try:
        results = knowledge_base.query(q)
        
        # Format a simple answer from the results
        if results:
            # Use the top result for a simple answer
            answer = results[0]["content"]
            sources = [{"title": item["metadata"]["title"], "url": item["metadata"]["url"]} 
                      for item in results[:3]]  # Top 3 sources
        else:
            answer = "לא נמצא מידע רלוונטי. נסו לנסח את השאלה אחרת."  # No relevant info found
            sources = []
        
        return {
            "query": q,
            "answer": answer,
            "sources": sources
        }
    except Exception as e:
        logger.error(f"Error processing query: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing query: {str(e)}"
        )

@app.post("/api/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    """Full-featured POST endpoint for querying the knowledge base"""
    if knowledge_base is None:
        raise HTTPException(
            status_code=503, 
            detail="Knowledge base not initialized"
        )
    
    # Log the incoming query
    logger.info(f"Received query: {request.query} (lang: {request.language})")
    
    # Query the knowledge base
    try:
        results = knowledge_base.query(request.query, top_k=request.max_results)
        
        # Format an answer from the results
        if results:
            # Here we would normally use an LLM to generate a proper answer
            # but for simplicity we'll just use the top result
            answer = results[0]["content"]
            
            # Extract source information
            sources = []
            for item in results[:3]:  # Top 3 sources
                source = {
                    "title": item["metadata"]["title"],
                    "url": item["metadata"]["url"],
                    "category": item["metadata"].get("category", ""),
                    "relevance": item["relevance_score"]
                }
                if source not in sources:  # Avoid duplicates
                    sources.append(source)
        else:
            answer = "לא נמצא מידע רלוונטי. נסו לנסח את השאלה אחרת."  # No relevant info found
            sources = []
        
        return {
            "query": request.query,
            "results": results,
            "answer": answer,
            "sources": sources
        }
    except Exception as e:
        logger.error(f"Error processing query: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing query: {str(e)}"
        )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler to ensure clean error responses"""
    logger.error(f"Uncaught exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": f"An unexpected error occurred: {str(exc)}"}
    )

def start():
    """Function to start the server programmatically"""
    uvicorn.run("src.api.main:app", host="0.0.0.0", port=8000, reload=True)

if __name__ == "__main__":
    # Run the API server
    logger.info("Starting Zchut Voice Assistant API server")
    uvicorn.run(app, host="0.0.0.0", port=8000)