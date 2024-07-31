import os
import logging
from langchain_community.embeddings import OllamaEmbeddings
from langchain_community.vectorstores import Chroma
from chromadb.config import Settings

logger = logging.getLogger(__name__)

class DBManager:
    def __init__(self, persist_directory):
        self.persist_directory = os.path.abspath(persist_directory)
        self.embeddings = OllamaEmbeddings(model="nomic-embed-text")
        self.db = self._load_or_create_db()

    def _load_or_create_db(self):
        try:
            # Ensure the persist directory exists
            os.makedirs(self.persist_directory, exist_ok=True)
            
            # Create or load the Chroma database
            db = Chroma(
                persist_directory=self.persist_directory,
                embedding_function=self.embeddings,
                client_settings=Settings(
                    anonymized_telemetry=False,
                    is_persistent=True
                )
            )
            
            logger.info(f"Database loaded from or created in: {self.persist_directory}")
            logger.info(f"Chroma is storing files in: {self.persist_directory}")
            return db
        except Exception as e:
            logger.error(f"Error creating/loading database: {str(e)}")
            raise

    def add_texts(self, texts, metadatas=None):
        try:
            self.db.add_texts(texts, metadatas=metadatas)
            self.db.persist()
            logger.info(f"Added {len(texts)} texts to the database and persisted changes")
        except Exception as e:
            logger.error(f"Error adding texts to database: {str(e)}")
            raise

    def similarity_search(self, query, k=4):
        return self.db.similarity_search(query, k=k)

    def remove_documents(self, metadata_filter):
        try:
            self.db._collection.delete(where=metadata_filter)
            self.db.persist()
            logger.info(f"Documents removed with filter: {metadata_filter} and changes persisted")
        except Exception as e:
            logger.error(f"Error removing documents: {str(e)}")
            raise

    def get_all_sources(self):
        try:
            results = self.db.get()
            if results and 'metadatas' in results:
                sources = set(meta.get('source', '') for meta in results['metadatas'] if meta and 'source' in meta)
            else:
                sources = set()
            logger.debug(f"All sources in database: {sources}")
            return sources
        except Exception as e:
            logger.error(f"Error getting all sources: {str(e)}")
            return set()

    def clear_database(self):
        logger.info("Clearing database...")
        try:
            # Get all document IDs
            all_ids = self.db.get()['ids']
            
            # Delete all documents
            if all_ids:
                self.db._collection.delete(ids=all_ids)
                self.db.persist()
                logger.info(f"Deleted {len(all_ids)} documents from the database")
            else:
                logger.info("No documents to delete. Database is already empty.")
            
            logger.info("Database cleared and changes persisted")
        except Exception as e:
            logger.error(f"Error clearing database: {str(e)}")
            raise