# backend/app/components.py

import os
from .document_processor import DocumentProcessor
from .db_manager import DBManager

# Initialize components
document_processor = DocumentProcessor()
db_manager = DBManager("./data/db")
documents_dir = os.path.abspath("./data/documents")

# Ensure documents directory exists
os.makedirs(documents_dir, exist_ok=True)