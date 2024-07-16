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

    def remove_documents(self, metadata_filter):
        self.db._collection.delete(where=metadata_filter)
        self.db.persist()

    def get_all_documents(self):
        return self.db.get()

    def get_all_sources(self):
        results = self.db.get()
        return set([meta.get('source') for meta in results['metadatas'] if meta.get('source')])