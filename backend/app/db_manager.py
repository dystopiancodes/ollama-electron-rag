import logging
from langchain_community.embeddings import OllamaEmbeddings
from langchain_community.vectorstores import Chroma
from chromadb.config import Settings
from langchain.schema import Document

logger = logging.getLogger(__name__)

class DBManager:
    def __init__(self, persist_directory):
        self.persist_directory = persist_directory
        self.embeddings = OllamaEmbeddings(model="nomic-embed-text")
        self.db = self._load_or_create_db()

    def _load_or_create_db(self):
        try:
            db = Chroma(
                persist_directory=self.persist_directory,
                embedding_function=self.embeddings,
                client_settings=Settings(
                    anonymized_telemetry=False,
                    is_persistent=True
                )
            )
            logger.info(f"Database loaded from or created in: {self.persist_directory}")
            return db
        except Exception as e:
            logger.error(f"Error creating/loading database: {str(e)}")
            raise

    def similarity_search(self, query, k=4):
        try:
            # Reload the database before each search to ensure it's up to date
            self.db = self._load_or_create_db()
            
            logger.info(f"Performing similarity search for query: {query}")
            results = self.db.similarity_search(query, k=k)
            logger.info(f"Similarity search returned {len(results)} results")
            
            valid_results = [doc for doc in results if doc.page_content is not None]
            
            if not valid_results:
                logger.warning("No valid results found after filtering")
                return [Document(page_content="No relevant information found.", metadata={})]
            
            logger.info(f"Returning {len(valid_results)} valid results")
            return valid_results
        except Exception as e:
            logger.error(f"Error during similarity search: {str(e)}", exc_info=True)
            return [Document(page_content=f"An error occurred during the search: {str(e)}", metadata={})]

    def add_texts(self, texts, metadatas=None):
        try:
            # Validate and clean the input data
            valid_texts = []
            valid_metadatas = []
            for i, item in enumerate(texts):
                if isinstance(item, tuple):
                    text, metadata = item
                else:
                    text = item
                    metadata = metadatas[i] if metadatas else None

                if text is not None and isinstance(text, str) and text.strip() != "":
                    valid_texts.append(text)
                    valid_metadatas.append(metadata)
                else:
                    logger.warning(f"Skipping invalid text at index {i}")

            if not valid_texts:
                logger.warning("No valid texts to add to the database")
                return

            self.db.add_texts(valid_texts, metadatas=valid_metadatas)
            self.db.persist()
            logger.info(f"Added {len(valid_texts)} texts to the database and persisted changes")
        except Exception as e:
            logger.error(f"Error adding texts to database: {str(e)}")
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
            all_ids = self.db.get()['ids']
            
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
    
    def remove_documents(self, metadata_filter):
        try:
            self.db._collection.delete(where=metadata_filter)
            self.db.persist()
            logger.info(f"Documents removed with filter: {metadata_filter} and changes persisted")
            # Reload the database to ensure it's up to date
            self.db = self._load_or_create_db()
        except Exception as e:
            logger.error(f"Error removing documents: {str(e)}")
            raise

    def recreate_database(self):
        logger.info("Recreating database...")
        try:
            # Clear existing database
            self.clear_database()
            # Create a new database instance
            self.db = self._load_or_create_db()
            logger.info("Database recreated successfully")
        except Exception as e:
            logger.error(f"Error recreating database: {str(e)}")
            raise