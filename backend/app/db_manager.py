import os
import shutil
import logging
import tempfile
from langchain_community.embeddings import OllamaEmbeddings
from langchain_community.vectorstores import Chroma

logger = logging.getLogger(__name__)

def is_valid_document(filename):
    return (not filename.startswith('.') and 
            os.path.splitext(filename)[1].lower() in ['.pdf', '.xml'])

class DBManager:
    def __init__(self, persist_directory):
        self.persist_directory = persist_directory
        self.temp_directory = tempfile.mkdtemp()
        self.embeddings = OllamaEmbeddings(model="nomic-embed-text")
        self.db = self._load_or_create_db()

    def _load_or_create_db(self):
        try:
            # Use the temporary directory for the database
            db = Chroma(persist_directory=self.temp_directory, embedding_function=self.embeddings)
            logger.info(f"Database created in temporary directory: {self.temp_directory}")
            return db
        except Exception as e:
            logger.error(f"Error creating/loading database: {str(e)}")
            raise

    def add_texts(self, texts, metadatas=None):
        try:
            self.db.add_texts(texts, metadatas=metadatas)
            self._persist_to_permanent_location()
        except Exception as e:
            logger.error(f"Error adding texts to database: {str(e)}")
            raise

    def _persist_to_permanent_location(self):
        try:
            # Ensure the permanent directory exists
            os.makedirs(self.persist_directory, exist_ok=True)
            
            # Copy from temporary to permanent location
            for item in os.listdir(self.temp_directory):
                s = os.path.join(self.temp_directory, item)
                d = os.path.join(self.persist_directory, item)
                if os.path.isdir(s):
                    shutil.copytree(s, d, dirs_exist_ok=True)
                else:
                    shutil.copy2(s, d)
            
            logger.info(f"Database persisted to permanent location: {self.persist_directory}")
        except Exception as e:
            logger.error(f"Error persisting database to permanent location: {str(e)}")
            raise

    def similarity_search(self, query, k=4):
        return self.db.similarity_search(query, k=k)

    def remove_documents(self, metadata_filter):
        self.db._collection.delete(where=metadata_filter)
        self._persist_to_permanent_location()

    def get_all_sources(self):
        try:
            results = self.db.get()
            if isinstance(results, dict) and 'metadatas' in results:
                return set(meta.get('source', '') for meta in results['metadatas'] 
                           if isinstance(meta, dict) and is_valid_document(meta.get('source', '')))
            else:
                logger.warning("Unexpected format returned by Chroma get() method")
                return set()
        except Exception as e:
            logger.error(f"Error getting all sources: {str(e)}")
            return set()

    def clear_database(self):
        """Clear all documents from the database by recreating it."""
        logger.info("Clearing database...")
        try:
            del self.db
        except Exception as e:
            logger.warning(f"Error deleting existing database object: {str(e)}")

        try:
            if os.path.exists(self.temp_directory):
                shutil.rmtree(self.temp_directory)
            self.temp_directory = tempfile.mkdtemp()
            logger.info(f"Created new temporary directory: {self.temp_directory}")

            if os.path.exists(self.persist_directory):
                shutil.rmtree(self.persist_directory)
                logger.info(f"Removed existing permanent database directory: {self.persist_directory}")
        except Exception as e:
            logger.error(f"Error removing database directories: {str(e)}")
            raise

        try:
            self.db = self._load_or_create_db()
            logger.info("New database created successfully")
        except Exception as e:
            logger.error(f"Error creating new database: {str(e)}")
            raise

    def __del__(self):
        # Clean up the temporary directory when the object is destroyed
        if os.path.exists(self.temp_directory):
            shutil.rmtree(self.temp_directory)
            logger.info(f"Removed temporary directory: {self.temp_directory}")

# Usage example:
# db_manager = DBManager("path/to/persist/directory")