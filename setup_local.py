"""
One-time setup script for Zchut Voice Assistant

This script:
1. Creates the Pinecone vector database index
2. Can optionally load initial data
"""

import os
import sys
import logging
import json
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("setup")

# Check for API key
if "PINECONE_API_KEY" not in os.environ:
    api_key = input("Enter your Pinecone API key: ").strip()
    os.environ["PINECONE_API_KEY"] = api_key
    logger.info("Set Pinecone API key from input")

# Set up Python path to find the modules
current_dir = Path(__file__).parent
sys.path.append(str(current_dir))

# Import after setting up the environment
try:
    from api.utils.vector_db import create_index, add_documents, get_db_stats
    logger.info("Successfully imported vector database utilities")
except ImportError as e:
    logger.error(f"Error importing modules: {e}")
    logger.error("Make sure you're running this script from the project root")
    sys.exit(1)

def main():
    """Run the setup process"""
    logger.info("Starting Pinecone index setup...")
    
    # Create the index
    success = create_index()
    if not success:
        logger.error("Failed to create index - see previous errors")
        return
    
    logger.info("Index creation successful!")
    
    # Show stats
    stats = get_db_stats()
    logger.info(f"Database stats: {json.dumps(stats, indent=2)}")
    
    # Ask if user wants to load sample data
    load_samples = input("Do you want to load sample data? (y/n): ").lower().strip() == 'y'
    if load_samples:
        # Create some sample documents
        sample_docs = [
            {
                "id": "sample-1",
                "title": "זכויות פנסיה בישראל",
                "content": "פנסיה היא תוכנית חיסכון ארוכת טווח, שנועדה להבטיח לחוסכים בה הכנסה חודשית קבועה לאחר פרישתם משוק העבודה.",
                "url": "https://www.kolzchut.org.il/he/פנסיה",
                "category": "זכויות כלכליות"
            },
            {
                "id": "sample-2",
                "title": "זכויות עובדים בישראל",
                "content": "חוקי העבודה בישראל מקנים לעובדים זכויות רבות, כגון שכר מינימום, ימי חופשה, דמי הבראה וזכויות נוספות.",
                "url": "https://www.kolzchut.org.il/he/זכויות_עובדים",
                "category": "זכויות בעבודה"
            }
        ]
        
        success = add_documents(sample_docs)
        if success:
            logger.info("Sample data loaded successfully!")
        else:
            logger.error("Failed to load sample data")
    
    logger.info("Setup complete!")

if __name__ == "__main__":
    main()