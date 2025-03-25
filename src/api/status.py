from http.server import BaseHTTPRequestHandler
import json
import logging

# Import the vector database utilities
from .utils.vector_db import get_db_stats

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("api_status")

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        """Handle GET requests to the /api/status endpoint"""
        try:
            # Get database stats
            db_stats = get_db_stats()
            
            # Prepare the response
            response = {
                "api_status": "active",
                "kb_status": db_stats.get("status", "unknown"),
                "kb_stats": db_stats
            }
            
            # Send the response
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            # Ensure proper encoding of Hebrew characters
            response_data = json.dumps(response, ensure_ascii=False).encode('utf-8')
            self.wfile.write(response_data)
                
        except Exception as e:
            logger.error(f"Error getting status: {e}")
            
            # Send error response
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            error_data = json.dumps({
                "api_status": "error",
                "error": str(e)
            }).encode('utf-8')
            self.wfile.write(error_data)