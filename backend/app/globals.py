# File: backend/app/globals.py

import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_DIR = os.path.join(BASE_DIR, "data", "db")
DOCUMENTS_DIR = os.path.join(BASE_DIR, "data", "documents")

SELECTED_FOLDER = None
db_manager = None
document_processor = None

# Ensure these directories exist
os.makedirs(DB_DIR, exist_ok=True)
os.makedirs(DOCUMENTS_DIR, exist_ok=True)