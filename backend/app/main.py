import os
import threading
import json
import asyncio
import logging
from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from langchain_community.llms import Ollama
import subprocess
import time

# Import custom modules
from .document_processor import DocumentProcessor
from .db_manager import DBManager
from .file_watcher import FileWatcher
from .conf import config
from .utils import is_valid_document
from .db_operations import cleanup_database, get_db_manager, get_document_processor

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    return {"status": "ok"}


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

def initialize_components():
    global db_manager, document_processor, file_watcher, watcher_thread

    try:
        logger.info("Initializing document processor")
        document_processor = get_document_processor(DOCUMENTS_DIR)

        logger.info("Initializing database manager")
        db_manager = get_db_manager(DB_DIR)

        logger.info("Initializing file watcher")
        if file_watcher:
            logger.info("Stopping existing file watcher")
            file_watcher.stop()

        file_watcher = FileWatcher(DOCUMENTS_DIR, db_manager, document_processor)

        logger.info("Starting file watcher thread")
        if watcher_thread and watcher_thread.is_alive():
            logger.info("Stopping existing watcher thread")
            watcher_thread.join()

        watcher_thread = threading.Thread(target=file_watcher.run, daemon=True)
        watcher_thread.start()
        logger.info("File watcher thread started")

    except Exception as e:
        logger.error(f"Error initializing components: {str(e)}")
        raise

initialize_components()

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
    k: int = 5

class ConfigUpdate(BaseModel):
    template: str
    folder: str
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


@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"Received request: {request.method} {request.url}")
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    logger.info(f"Finished processing request: {request.method} {request.url} (took {process_time:.2f}s)")
    return response




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


from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import asyncio
import json

class QueryInput(BaseModel):
    text: str
    k: int = 5

@app.post("/query")
async def query_documents(query_input: QueryInput, request: Request):
    logger.info(f"Received query: {query_input}")
    if not SELECTED_FOLDER:
        raise HTTPException(status_code=400, detail="No folder selected. Please select a folder first.")
    
    return StreamingResponse(query_stream(query_input.text, query_input.k, request), media_type="application/json")

async def query_stream(query: str, k: int, request: Request):
    try:
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
    models = get_installed_ollama_models()
    return {
        "prompt_template": config.get_prompt_template(),
        "model": config.get("model", "mistral:latest"),
        "k": config.get("k", 5),
        "folder_selected": SELECTED_FOLDER is not None,
        "current_folder": SELECTED_FOLDER or "No folder selected",
        "available_models": models
    }

@app.post("/config")
async def update_config(config_update: ConfigUpdate):
    config.set_prompt_template(config_update.template)
    config.set("model", config_update.model)
    config.set("k", config_update.k)
    config.set("folder_selected", config_update.folder)
    config.set("current_folder", config_update.folder)
    create_llm()  # Recreate the LLM instance with the new model
    return {"message": "Config updated successfully"}

@app.post("/config/reset")
async def reset_config():
    config.reset_to_default()
    create_llm()  # Recreate the LLM instance with the default model
    return {"message": "Config reset to default"}


@app.post("/reset-and-rescan")
async def reset_and_rescan():
    if not SELECTED_FOLDER:
        raise HTTPException(status_code=400, detail="No folder selected. Please select a folder first.")
    
    try:
        db_manager.clear_database()
        for filename in os.listdir(DOCUMENTS_DIR):
            if filename.endswith(('.pdf', '.xml')):  # Adjust the extensions as needed
                file_path = os.path.join(DOCUMENTS_DIR, filename)
                chunks = document_processor.process_file(file_path)
                metadata = [{"source": filename} for _ in chunks]
                db_manager.add_texts(chunks, metadata)
        return {"message": "Reset and rescan completed successfully"}
    except Exception as e:
        logger.error(f"Error during reset and rescan: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error during reset and rescan: {str(e)}")

@app.post("/set-folder")
async def set_folder(folder: FolderPath):
    global SELECTED_FOLDER, DB_DIR, DOCUMENTS_DIR, db_manager, document_processor, file_watcher, watcher_thread

    try:
        logger.info(f"Setting folder: {folder.path}")
        
        if not os.path.exists(folder.path):
            logger.error(f"Folder does not exist: {folder.path}")
            raise HTTPException(status_code=400, detail="Folder does not exist")
        
        if not os.access(folder.path, os.R_OK | os.W_OK):
            logger.error(f"No read/write permission for folder: {folder.path}")
            raise HTTPException(status_code=403, detail="No permission to access folder")

        SELECTED_FOLDER = folder.path
        DB_DIR = os.path.join(SELECTED_FOLDER, '.raggy_db')
        DOCUMENTS_DIR = folder.path

        try:
            os.makedirs(DB_DIR, exist_ok=True)
            initialize_components()
            await reset_and_rescan()  # Ensure this function is awaited as it's an async function
        except OSError as e:
            logger.error(f"Error creating directories: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to create necessary directories: {str(e)}")
        
        logger.info(f"Successfully set folder to {SELECTED_FOLDER}")
        return {"message": f"Folder set to {SELECTED_FOLDER}"}

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.exception(f"Unexpected error setting folder: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

async def periodic_refresh():
    while True:
        await asyncio.sleep(60)  # Refresh every 60 seconds
        logger.info("Performing periodic database refresh")
        cleanup_database()


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
    



@app.get("/")
async def root():
    return {"message": "Local RAG App Backend is running"}

@app.on_event("startup")
async def startup_event():
    cleanup_database()
    #asyncio.create_task(periodic_refresh())



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)