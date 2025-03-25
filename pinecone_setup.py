"""
Pinecone setup script for Free Tier - uses the gcp-starter environment
"""

import os
import logging
import time
from pinecone import Pinecone

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("pinecone_setup")

def create_pinecone_index():
    """Create the Pinecone index for Zchut Voice Assistant using free tier."""
    # Check for API key
    api_key = os.environ.get("PINECONE_API_KEY")
    if not api_key:
        api_key = input("Enter your Pinecone API key: ").strip()
        os.environ["PINECONE_API_KEY"] = api_key
    
    try:
        # Initialize Pinecone client
        logger.info("Initializing Pinecone client...")
        pc = Pinecone(api_key=api_key)
        
        # Check if index already exists
        logger.info("Checking for existing indexes...")
        indexes = pc.list_indexes()
        existing_index_names = [index.name for index in indexes]
        
        if "zchut-knowledge-base" in existing_index_names:
            logger.info("Index 'zchut-knowledge-base' already exists.")
            recreate = input("Do you want to recreate the index? (y/n): ").lower().strip() == 'y'
            
            if recreate:
                logger.info("Deleting existing index...")
                pc.delete_index("zchut-knowledge-base")
                time.sleep(2)
            else:
                logger.info("Keeping existing index.")
                return True
        
        # Create new index - compatible with free tier (gcp-starter)
        logger.info("Creating new Pinecone index: zchut-knowledge-base")
        pc.create_index(
            name="zchut-knowledge-base",
            dimension=768,  # Dimension for multilingual-mpnet-base-v2
            metric="cosine"
            # No ServerlessSpec - use default cloud/region for free tier
        )
        
        # Wait for initialization
        logger.info("Waiting for index to initialize...")
        time.sleep(5)
        
        # Verify creation
        updated_indexes = pc.list_indexes()
        updated_index_names = [index.name for index in updated_indexes]
        
        if "zchut-knowledge-base" in updated_index_names:
            logger.info("✅ Index created successfully!")
            
            # Get more info about the index
            index = pc.Index("zchut-knowledge-base")
            description = index.describe_index_stats()
            logger.info(f"Index stats: {description}")
            
            return True
        else:
            logger.error("❌ Index creation failed: Index not found after creation")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error creating index: {e}")
        return False

def main():
    """Main function to run the setup process."""
    logger.info("Starting Pinecone index setup for free tier...")
    success = create_pinecone_index()
    
    if success:
        logger.info("✅ Setup completed successfully!")
        
        # Update the vector_db.py for compatibility with free tier
        logger.info("\nIMPORTANT: When using the vector_db.py file, make these changes:")
        logger.info("1. Remove the ServerlessSpec from create_index()")
        logger.info("2. Remove the spec parameter entirely")
        logger.info("3. Use just: pc.create_index(name=\"zchut-knowledge-base\", dimension=768, metric=\"cosine\")")
    else:
        logger.error("❌ Setup failed - see previous errors")
    
    logger.info("\nNext steps:")
    logger.info("1. Create the api/utils directory in your project")
    logger.info("2. Add the vector_db.py file there (with the modifications noted above)")
    logger.info("3. Deploy your project to Vercel")

if __name__ == "__main__":
    main()