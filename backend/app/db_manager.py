# backend/app/db_manager.py

import os
from langchain_community.embeddings import OllamaEmbeddings
from langchain_community.vectorstores import Chroma

class DBManager:
    def __init__(self, persist_directory):
        self.persist_directory = persist_directory
        self.embeddings = OllamaEmbeddings(model="nomic-embed-text")
        self.db = self._load_or_create_db()

    def _load_or_create_db(self):
        if os.path.exists(self.persist_directory):
            return Chroma(persist_directory=self.persist_directory, embedding_function=self.embeddings)
        return Chroma(persist_directory=self.persist_directory, embedding_function=self.embeddings)

    def add_texts(self, texts, metadatas=None):
        self.db.add_texts(texts, metadatas=metadatas)
        self.db.persist()

    def similarity_search(self, query, k=4):
        return self.db.similarity_search(query, k=k)

# Usage example:
# db_manager = DBManager("path/to/persist/directory")
# db_manager.add_texts(["Some text"], [{"source": "document1.pdf"}])
# results = db_manager.similarity_search("query")