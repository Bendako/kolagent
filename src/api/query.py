from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse
import json
import os
import logging

# Import the vector database utilities
from .utils.vector_db import query_knowledge_base

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("api_query")

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        """Handle GET requests to the /api/query endpoint"""
        try:
            # Parse URL and query parameters
            parsed_url = urlparse(self.path)
            query_params = parse_qs(parsed_url.query)
            
            # Get the query parameter 'q'
            q = query_params.get('q', [''])[0]
            
            if not q:
                self._send_response(400, {"error": "Missing query parameter 'q'"})
                return
                
            # Query the knowledge base
            results = query_knowledge_base(q, top_k=5)
            
            # Format a simple answer from the results
            if results:
                # Use the top result for a simple answer
                answer = results[0]["content"]
                sources = [
                    {
                        "title": item["metadata"]["title"], 
                        "url": item["metadata"]["url"]
                    } 
                    for item in results[:3]  # Top 3 sources
                ]
            else:
                answer = "לא נמצא מידע רלוונטי. נסו לנסח את השאלה אחרת."  # No relevant info found
                sources = []
            
            # Send the response
            self._send_response(200, {
                "query": q,
                "answer": answer,
                "sources": sources
            })
                
        except Exception as e:
            logger.error(f"Error processing query: {e}")
            self._send_response(500, {"error": f"Server error: {str(e)}"})
    
    def _send_response(self, status_code, data):
        """Helper method to send JSON responses"""
        self.send_response(status_code)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        
        # Ensure proper encoding of Hebrew characters
        response_data = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.wfile.write(response_data)