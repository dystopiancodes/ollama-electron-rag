
# File: __init__.py


# File: components.py

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
# File: conf.py

# backend/app/conf.py

import json
import os

class Config:
    def __init__(self, config_file='config.json'):
        self.config_file = config_file
        self.default_config = {
            "prompt_template": """<|start_header_id|>system<|end_header_id|>
Sei un assistente AI esperto in analisi di documenti. Utilizza le seguenti informazioni estratte da un documento per rispondere alla domanda. Rispondi in modo conciso e diretto in italiano, fornendo solo le informazioni richieste. Se l'informazione non è presente nei dati forniti, indica che non è disponibile.
<|eot_id|>
<|start_header_id|>user<|end_header_id|>
Contesto:
{context}

Domanda: {question}

Basandoti sul contesto fornito, rispondi alla domanda in modo conciso ma informativo. Se non trovi una risposta adeguata nel contesto, dillo esplicitamente.
<|eot_id|>
<|start_header_id|>assistant<|end_header_id|>
""",
            "model": "mistral:latest",
            "k": 5
        }
        self.config = self.load_config()

    def load_config(self):
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r') as f:
                return json.load(f)
        return self.default_config.copy()

    def save_config(self):
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=2)

    def get_prompt_template(self):
        return self.config.get('prompt_template', self.default_config['prompt_template'])

    def set_prompt_template(self, new_template):
        self.config['prompt_template'] = new_template
        self.save_config()

    def get(self, key, default=None):
        return self.config.get(key, default)

    def set(self, key, value):
        self.config[key] = value
        self.save_config()

    def reset_to_default(self):
        self.config = self.default_config.copy()
        self.save_config()

config = Config()
# File: db_manager.py

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
# File: db_operations.py

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
# File: document_processor.py

import os
import pdfplumber
import xml.etree.ElementTree as ET
from typing import List, Dict, Tuple

class DocumentProcessor:
    def __init__(self, documents_dir, chunk_size=1000, chunk_overlap=200):
        self.documents_dir = documents_dir
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    
    def process_file(self, file_name):
        file_path = os.path.join(self.documents_dir, file_name)
        """Process a file based on its extension."""
        _, ext = os.path.splitext(file_path)
        if ext.lower() == '.pdf':
            return self.process_pdf(file_path)
        elif ext.lower() == '.xml':
            return self.process_xml(file_path)
        else:
            raise ValueError(f"Unsupported file type: {ext}")

    def process_pdf(self, file_path):
        """Process a PDF file and return a list of text chunks with metadata."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        with pdfplumber.open(file_path) as pdf:
            text = ""
            for page in pdf.pages:
                text += page.extract_text() + "\n"

        return self.split_text(text, os.path.basename(file_path))

    def process_xml(self, file_path):
        """Process any XML file and return a list of text chunks with metadata."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        try:
            tree = ET.parse(file_path)
            root = tree.getroot()

            flattened_data = self._flatten_xml(root)
            formatted_text = self._format_flattened_data(flattened_data)
            return self.split_text(formatted_text, os.path.basename(file_path))
        except ET.ParseError as e:
            raise ValueError(f"Error parsing XML file {file_path}: {str(e)}")

    def _flatten_xml(self, element, parent_path=''):
        """Recursively flatten XML into a dictionary of key-value pairs."""
        items = {}
        for child in element:
            child_path = f"{parent_path}/{self._strip_namespace(child.tag)}" if parent_path else self._strip_namespace(child.tag)
            if len(child) == 0:
                items[child_path] = child.text.strip() if child.text else ''
            else:
                items.update(self._flatten_xml(child, child_path))
        return items

    def _strip_namespace(self, tag):
        return tag.split('}')[-1] if '}' in tag else tag

    def _format_flattened_data(self, data: Dict[str, str]) -> str:
        """Format flattened data into the desired compact output format."""
        formatted_output = []
        current_group = None
        current_group_data = {}

        for key, value in data.items():
            parts = key.split('/')
            group = parts[-2] if len(parts) > 1 else 'root'
            subkey = parts[-1]

            if group != current_group:
                if current_group_data:
                    formatted_output.append(self._format_group(current_group, current_group_data))
                current_group = group
                current_group_data = {}

            if value is not None and value.strip() != "":
                current_group_data[subkey] = value

        if current_group_data:
            formatted_output.append(self._format_group(current_group, current_group_data))

        return ' '.join(formatted_output)

    def _format_group(self, group: str, data: Dict[str, str]) -> str:
        """Format a group of related data into a string."""
        if group == 'root':
            return ' '.join(f"{k}: {v}" for k, v in data.items())
        return f"{group}: " + ' '.join(f"{k}: {v}" for k, v in data.items())

    def split_text(self, text: str, source_file: str) -> List[Tuple[str, Dict]]:
        """Split the text into chunks with metadata."""
        chunks = []
        words = text.split()
        current_chunk = []

        for i, word in enumerate(words):
            if len(' '.join(current_chunk)) + len(word) > self.chunk_size and current_chunk:
                chunk_text = ' '.join(current_chunk)
                if chunk_text.strip():  # Only add non-empty chunks
                    chunks.append((chunk_text, {"source": source_file, "chunk_index": len(chunks)}))
                overlap_start = max(0, len(current_chunk) - self.chunk_overlap)
                current_chunk = current_chunk[overlap_start:]
            current_chunk.append(word)

        if current_chunk:
            chunk_text = ' '.join(current_chunk)
            if chunk_text.strip():  # Only add non-empty chunks
                chunks.append((chunk_text, {"source": source_file, "chunk_index": len(chunks)}))

        return chunks
# File: file_watcher.py

# File: backend/app/file_watcher.py

import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import os
import logging
from .db_operations import cleanup_database

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class DocumentHandler(FileSystemEventHandler):
    def __init__(self, db_manager, document_processor, documents_dir):
        self.db_manager = db_manager
        self.document_processor = document_processor
        self.documents_dir = documents_dir

    def on_created(self, event):
        if not event.is_directory:
            logger.debug(f"New file detected: {event.src_path}")
            self._process_file(event.src_path)

    def on_modified(self, event):
        if not event.is_directory:
            logger.debug(f"File modified: {event.src_path}")
            self._process_file(event.src_path)

    def on_deleted(self, event):
        if not event.is_directory:
            logger.debug(f"File deleted: {event.src_path}")
            self._remove_file_from_db(event.src_path)

    def _process_file(self, file_path):
        try:
            logger.debug(f"Starting to process file: {file_path}")
            chunks = self.document_processor.process_file(file_path)
            logger.debug(f"File processed, got {len(chunks)} chunks")
            metadata = {"source": os.path.basename(file_path)}
            self.db_manager.add_texts(chunks, [metadata] * len(chunks))
            logger.debug(f"Processed and added to database: {file_path}")
        except Exception as e:
            logger.error(f"Error processing file {file_path}: {str(e)}")

    def _remove_file_from_db(self, file_path):
        try:
            filename = os.path.basename(file_path)
            logger.debug(f"Removing file from database: {filename}")
            self.db_manager.remove_documents({"source": filename})
            logger.info(f"Removed from database: {filename}")
            # Trigger a full database cleanup
            cleanup_database(self.db_manager, self.document_processor, self.documents_dir)
        except Exception as e:
            logger.error(f"Error removing file {file_path} from database: {str(e)}")

class FileWatcher:
    def __init__(self, path_to_watch, db_manager, document_processor):
        self.path_to_watch = path_to_watch
        self.handler = DocumentHandler(db_manager, document_processor, path_to_watch)
        self.observer = Observer()

    def run(self):
        logger.debug(f"Starting file watcher on path: {self.path_to_watch}")
        self.observer.schedule(self.handler, self.path_to_watch, recursive=False)
        self.observer.start()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.observer.stop()
        self.observer.join()
# File: globals.py

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
# File: main.py

import os
import threading
import json
import asyncio
import logging
from fastapi import FastAPI, HTTPException, Request, Depends

from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ValidationError
from langchain.prompts import PromptTemplate
from langchain_community.llms import Ollama
import subprocess

# Import custom modules
from . import globals
from .document_processor import DocumentProcessor
from .db_manager import DBManager
from .file_watcher import FileWatcher
from .conf import config
from .utils import is_valid_document
from .db_operations import cleanup_database, get_db_manager, get_document_processor

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Suppress noisy loggers
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

app = FastAPI()


# Global variables
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DB_DIR = os.path.join(BASE_DIR, "data", "db")
DEFAULT_DOCUMENTS_DIR = os.path.join(BASE_DIR, "data", "documents")

SELECTED_FOLDER = None
DB_DIR = DEFAULT_DB_DIR
DOCUMENTS_DIR = DEFAULT_DOCUMENTS_DIR
db_manager = None
document_processor = None
file_watcher = None
watcher_thread = None

# Ensure default directories exist
os.makedirs(DEFAULT_DB_DIR, exist_ok=True)
os.makedirs(DEFAULT_DOCUMENTS_DIR, exist_ok=True)

document_processor = get_document_processor(DOCUMENTS_DIR)
db_manager = get_db_manager(DB_DIR)

# Initialize file watcher
file_watcher = FileWatcher(DOCUMENTS_DIR, db_manager, document_processor)

# Start file watcher in a separate thread
watcher_thread = threading.Thread(target=file_watcher.run, daemon=True)
watcher_thread.start()

logger.info("File watcher thread started")

def create_llm():
    global llm
    model_name = config.get("model", "mistral:latest")
    logger.info(f"Creating new LLM instance with model: {model_name}")
    try:
        llm = Ollama(model=model_name)
        logger.info(f"LLM instance created successfully with model: {model_name}")
    except Exception as e:
        logger.error(f"Error creating LLM instance: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error creating LLM instance: {str(e)}")


# Create initial LLM instance
create_llm()

class QueryInput(BaseModel):
    text: str
    k: int = 5  # Default value is 3

class PromptTemplateUpdate(BaseModel):
    template: str

class ConfigUpdate(BaseModel):
    template: str
    model: str
    k: int

class FolderPath(BaseModel):
    path: str

def get_selected_folder():
    if globals.SELECTED_FOLDER is None:
        raise HTTPException(status_code=400, detail="Folder not selected")
    return globals.SELECTED_FOLDER



def cleanup_database():
    logger.info("Starting database cleanup")
    try:
        current_files = set(f for f in os.listdir(DOCUMENTS_DIR) 
                            if os.path.isfile(os.path.join(DOCUMENTS_DIR, f)) and is_valid_document(f))
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
                file_path = os.path.join(DOCUMENTS_DIR, file)
                chunks = document_processor.process_file(file_path)
                metadata = [{"source": file} for _ in chunks]
                db_manager.add_texts(chunks, metadata)
        
        # Verify the database state after cleanup
        final_db_documents = db_manager.get_all_sources()
        logger.debug(f"Documents in database after cleanup: {final_db_documents}")
        
        logger.info("Database cleanup completed.")
    except Exception as e:
        logger.error(f"Error during database cleanup: {str(e)}", exc_info=True)




@app.get("/db-state")
async def get_db_state():
    try:
        db_documents = db_manager.get_all_sources()
        db_files = os.listdir(DB_DIR)
        return {
            "documents_in_db": list(db_documents),
            "files_in_db_directory": db_files
        }
    except Exception as e:
        logger.error(f"Error getting database state: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))    

async def query_stream(query: str, k: int, request: Request):
    try:
        logger.info(f"Received query: {query}, k={k}")
        yield json.dumps({"debug": f"Received query: {query}, k={k}"}) + "\n"

        logger.info(f"Performing similarity search with k={k}")
        docs = db_manager.similarity_search(query, k=k)
        logger.info(f"Similarity search returned {len(docs)} documents")
        yield json.dumps({"debug": f"Similarity search returned {len(docs)} documents"}) + "\n"

        if not docs or (len(docs) == 1 and "An error occurred during the search" in docs[0].page_content):
            error_message = docs[0].page_content if docs else "No documents found"
            logger.error(f"Error in similarity search: {error_message}")
            yield json.dumps({"error": error_message}) + "\n"
            return

        context = "\n".join([doc.page_content for doc in docs])

        sources = [doc.metadata.get("source", "Unknown") for doc in docs]
        unique_sources = list(set(sources))
        logger.info(f"All sources: {sources}")
        logger.info(f"Unique sources: {unique_sources}")
        yield json.dumps({"debug": f"All sources: {sources}"}) + "\n"
        yield json.dumps({"debug": f"Unique sources: {unique_sources}"}) + "\n"
        yield json.dumps({"sources": unique_sources}) + "\n"

        prompt = config.get_prompt_template().format(context=context, question=query)
        logger.debug(f"Full Generated prompt: {prompt}")
        yield json.dumps({"debug": f"Full Generated prompt: {prompt}"}) + "\n"

        logger.info(f"Using LLM with model: {llm.model}")
        yield json.dumps({"debug": f"Using LLM with model: {llm.model}"}) + "\n"

        response = ""
        for chunk in llm.stream(prompt):
            if await request.is_disconnected():
                logger.info("Client disconnected, stopping generation")
                break
            response += chunk
            yield json.dumps({"answer": chunk}) + "\n"
            await asyncio.sleep(0.1)
        
        if not response.strip():
            logger.warning("No response generated")
            yield json.dumps({"answer": "Mi dispiace, non ho trovato una risposta adeguata basata sul contesto fornito."}) + "\n"
            yield json.dumps({"debug": "No response generated"}) + "\n"
        else:
            logger.info("Response generated successfully")
            yield json.dumps({"debug": "Response generated successfully"}) + "\n"
        
    except Exception as e:
        logger.error(f"Error during query processing: {str(e)}", exc_info=True)
        yield json.dumps({"error": f"Si è verificato un errore durante l'elaborazione della query: {str(e)}"}) + "\n"

@app.post("/query")
async def query_documents(query_input: QueryInput, request: Request):
    if not SELECTED_FOLDER:
        raise HTTPException(status_code=400, detail="No folder selected. Please select a folder first.")
    
    global db_manager
    try:
        docs = db_manager.similarity_search(query_input.text, k=query_input.k)
        # ... (rest of the query logic)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")

# Updated documents endpoint
@app.get("/documents")
async def list_documents():
    if not SELECTED_FOLDER:
        raise HTTPException(status_code=400, detail="No folder selected. Please select a folder first.")
    
    try:
        documents = [f for f in os.listdir(DOCUMENTS_DIR) if os.path.isfile(os.path.join(DOCUMENTS_DIR, f)) and is_valid_document(f)]
        return {"documents": documents}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing documents: {str(e)}")

# Updated refresh-documents endpoint
@app.get("/refresh-documents")
async def refresh_documents():
    if not SELECTED_FOLDER:
        raise HTTPException(status_code=400, detail="No folder selected. Please select a folder first.")
    
    try:
        cleanup_database(db_manager, document_processor, DOCUMENTS_DIR)
        return {"message": "Documents refreshed successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error refreshing documents: {str(e)}")


@app.get("/config")
async def get_config():
    return {
        "prompt_template": config.get_prompt_template(),
        "model": config.get("model", "mistral:latest"),
        "k": config.get("k", 5),
        "folder_selected": SELECTED_FOLDER is not None,
        "current_folder": SELECTED_FOLDER or "No folder selected"
    }

# Updated config update endpoint
@app.post("/config")
async def update_config(config_update: ConfigUpdate, folder: str = Depends(get_selected_folder)):
    try:
        config.set_prompt_template(config_update.template)
        config.set("model", config_update.model)
        config.set("k", config_update.k)
        
        # Recreate the LLM instance with the new model
        create_llm()
        
        return {"message": "Config updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating config: {str(e)}")

# Updated config reset endpoint
@app.post("/config/reset")
async def reset_config(folder: str = Depends(get_selected_folder)):
    try:
        config.reset_to_default()
        return {"message": "Config reset to default"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error resetting config: {str(e)}")


@app.post("/reset-and-rescan")
async def reset_and_rescan():
    if not SELECTED_FOLDER:
        raise HTTPException(status_code=400, detail="No folder selected. Please select a folder first.")
    
    try:
        db_manager.clear_database()
        for filename in os.listdir(DOCUMENTS_DIR):
            if filename.endswith(('.pdf', '.xml')):
                file_path = os.path.join(DOCUMENTS_DIR, filename)
                chunks = document_processor.process_file(filename)
                db_manager.add_texts(chunks)
        return {"message": "Reset and rescan completed successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error during reset and rescan: {str(e)}")

    
async def periodic_refresh():
    while True:
        await asyncio.sleep(60)  # Refresh every 60 seconds
        logger.info("Performing periodic database refresh")
        cleanup_database()

@app.on_event("startup")
async def startup_event():
    cleanup_database()
    #asyncio.create_task(periodic_refresh())


def get_installed_ollama_models():
    try:
        logger.info("Attempting to run 'ollama list'")
        result = subprocess.run(["ollama", "list"], capture_output=True, text=True)
        
        if result.returncode != 0:
            logger.error(f"Error running 'ollama list': {result.stderr}")
            return []
        
        logger.info(f"Raw output from 'ollama list': {result.stdout}")
        
        # Parse the output to extract model names
        models = []
        for line in result.stdout.split('\n')[1:]:  # Skip the header line
            if line.strip():
                model_name = line.split()[0]  # The model name is the first column
                models.append(model_name)
        
        logger.info(f"Parsed models: {models}")
        return models
    except Exception as e:
        logger.error(f"Exception in get_installed_ollama_models: {str(e)}", exc_info=True)
        return []

@app.get("/models")
async def list_models():
    try:
        models = get_installed_ollama_models()
        return {"models": models}
    except Exception as e:
        logger.error(f"Error listing models: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error listing models: {str(e)}")
    
@app.post("/set-folder")
async def set_folder(folder: FolderPath):
    global SELECTED_FOLDER, DB_DIR, DOCUMENTS_DIR, db_manager, document_processor, file_watcher, watcher_thread
    SELECTED_FOLDER = folder.path
    DB_DIR = os.path.join(SELECTED_FOLDER, '.raggy_db')
    DOCUMENTS_DIR = os.path.join(SELECTED_FOLDER, 'documents')
    
    os.makedirs(DB_DIR, exist_ok=True)
    os.makedirs(DOCUMENTS_DIR, exist_ok=True)
    
    db_manager = get_db_manager(DB_DIR)
    document_processor = get_document_processor(DOCUMENTS_DIR)
    
    cleanup_database(db_manager, document_processor, DOCUMENTS_DIR)
    
    # Stop the existing file watcher
    if file_watcher:
        file_watcher.observer.stop()
        watcher_thread.join()
    
    # Create a new file watcher for the new directory
    file_watcher = FileWatcher(DOCUMENTS_DIR, db_manager, document_processor)
    watcher_thread = threading.Thread(target=file_watcher.run, daemon=True)
    watcher_thread.start()
    
    return {"message": f"Folder set to {SELECTED_FOLDER}"}


@app.get("/")
async def root():
    return {"message": "Local RAG App Backend is running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
# File: utils.py

# backend/app/utils.py


import os

def is_valid_document(filename):
    return (not filename.startswith('.') and 
            os.path.splitext(filename)[1].lower() in ['.pdf', '.xml'])