# File: backend/app/db_operations.py

import os
import logging
from .utils import is_valid_document

logger = logging.getLogger(__name__)

def get_document_processor(documents_dir):
    from .document_processor import DocumentProcessor
    return DocumentProcessor(documents_dir)

def get_db_manager(db_dir):
    from .db_manager import DBManager
    return DBManager(db_dir)

def cleanup_database(db_manager, document_processor, documents_dir):
    logger.info("Starting database cleanup")
    try:
        current_files = set(f for f in os.listdir(documents_dir) 
                            if os.path.isfile(os.path.join(documents_dir, f)) and is_valid_document(f))
        db_documents = db_manager.get_all_sources()
        
        logger.debug(f"Current files in documents directory: {current_files}")
        logger.debug(f"Documents in database before cleanup: {db_documents}")

        # If there's any mismatch between files and database, recreate the database
        if current_files != db_documents:
            logger.info("Mismatch detected. Recreating database...")
            db_manager.recreate_database()
            
            # Add all current documents to the new database
            for file in current_files:
                logger.info(f"Adding document to database: {file}")
                file_path = os.path.join(documents_dir, file)
                chunks = document_processor.process_file(file)
                metadata = [{"source": file} for _ in chunks]
                db_manager.add_texts(chunks, metadata)
        
        # Verify the database state after cleanup
        final_db_documents = db_manager.get_all_sources()
        logger.debug(f"Documents in database after cleanup: {final_db_documents}")
        
        logger.info("Database cleanup completed.")
    except Exception as e:
        logger.error(f"Error during database cleanup: {str(e)}", exc_info=True)