# backend/app/main.py


import os
import threading
import json
import asyncio
import logging
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from langchain.prompts import PromptTemplate
from langchain_community.llms import Ollama

# Import custom modules
from .document_processor import DocumentProcessor
from .db_manager import DBManager
from .file_watcher import FileWatcher
from .conf import config
from .utils import is_valid_document

# Configure logging
logging.basicConfig(level=logging.INFO)
#ogging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Suppress noisy loggers
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

app = FastAPI()


# At the top of your main.py, after imports
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_DIR = os.path.join(BASE_DIR, "data", "db")
DOCUMENTS_DIR = os.path.join(BASE_DIR, "data", "documents")

logger.debug(f"Base directory: {BASE_DIR}")
logger.debug(f"Database directory: {DB_DIR}")
logger.debug(f"Documents directory: {DOCUMENTS_DIR}")

# Ensure these directories exist
os.makedirs(DB_DIR, exist_ok=True)
os.makedirs(DOCUMENTS_DIR, exist_ok=True)

# Initialize components
document_processor = DocumentProcessor()
db_manager = DBManager(DB_DIR)


file_watcher = FileWatcher(DOCUMENTS_DIR, document_processor, db_manager)


# Start file watcher in a separate thread

watcher_thread = threading.Thread(target=file_watcher.run, daemon=True)
watcher_thread.start()
logger.info("File watcher thread started")
db_manager = DBManager("./data/db")
# Initialize Ollama LLM
llm = Ollama(model="llama3.1")

class QueryInput(BaseModel):
    text: str
    k: int = 10  # Default value is 3

class PromptTemplateUpdate(BaseModel):
    template: str

def cleanup_database():
    logger.info("Starting database cleanup")
    try:
        current_files = set(f for f in os.listdir(DOCUMENTS_DIR) 
                            if os.path.isfile(os.path.join(DOCUMENTS_DIR, f)) and is_valid_document(f))
        db_documents = db_manager.get_all_sources()
        
        logger.debug(f"Current files in documents directory: {current_files}")
        logger.debug(f"Documents in database before cleanup: {db_documents}")

        # Remove documents from the database that no longer exist in the directory
        for doc in db_documents - current_files:
            logger.info(f"Removing document from database: {doc}")
            db_manager.remove_documents({"source": doc})
        
        # Add only new documents to the database
        new_files = current_files - db_documents
        for file in new_files:
            logger.info(f"Adding new document to database: {file}")
            file_path = os.path.join(DOCUMENTS_DIR, file)
            chunks = document_processor.process_file(file_path)
            metadata = [{"source": file} for _ in chunks]
            db_manager.add_texts(chunks, metadata)
        
        # Verify the database state after cleanup
        final_db_documents = db_manager.get_all_sources()
        logger.debug(f"Documents in database after cleanup: {final_db_documents}")
        
        # Check if the database directory is empty
        db_files = os.listdir(DB_DIR)
        logger.debug(f"Files in database directory after cleanup: {db_files}")
        
        logger.info(f"Database cleanup completed. Added {len(new_files)} new documents.")
    except Exception as e:
        logger.error(f"Error during database cleanup: {str(e)}", exc_info=True)


@app.on_event("startup")
async def startup_event():
    cleanup_database()

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

async def query_stream(query: str, k: int):
    try:
        logger.info(f"Received query: {query}, k={k}")
        yield json.dumps({"debug": f"Received query: {query}, k={k}"}) + "\n"

        docs = db_manager.similarity_search(query, k=k)
        logger.info(f"Similarity search returned {len(docs)} documents")
        yield json.dumps({"debug": f"Similarity search returned {len(docs)} documents"}) + "\n"

        if not docs or (len(docs) == 1 and "An error occurred during the search" in docs[0].page_content):
            error_message = docs[0].page_content if docs else "No documents found"
            logger.error(f"Error in similarity search: {error_message}")
            yield json.dumps({"error": error_message}) + "\n"
            return

        context = "\n".join([doc.page_content for doc in docs])
        #logger.debug(f"Full Context: {context}")
        #yield json.dumps({"debug": f"Full Context: {context}"}) + "\n"

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


        response = ""
        for chunk in llm.stream(prompt):
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
async def query_documents(query_input: QueryInput):
    return StreamingResponse(query_stream(query_input.text, query_input.k), media_type="application/json")



@app.get("/documents")
async def list_documents():
    try:
        documents = [f for f in os.listdir(DOCUMENTS_DIR) if os.path.isfile(os.path.join(DOCUMENTS_DIR, f)) and is_valid_document(f)]
        return {"documents": documents}
    except Exception as e:
        logger.error(f"Error listing documents: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/refresh-documents")
async def refresh_documents():
    try:
        cleanup_database()
        return {"message": "Documents refreshed successfully"}
    except Exception as e:
        logger.error(f"Error refreshing documents: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/config")
async def get_config():
    return {"prompt_template": config.get_prompt_template()}

@app.post("/config")
async def update_config(prompt_template: PromptTemplateUpdate):
    config.set_prompt_template(prompt_template.template)
    return {"message": "Config updated successfully"}

@app.post("/config/reset")
async def reset_config():
    config.reset_to_default()
    return {"message": "Config reset to default"}

@app.post("/reset-and-rescan")
async def reset_and_rescan():
    try:
        db_manager.clear_database()
        documents_dir = "./data/documents"
        for filename in os.listdir(documents_dir):
            if filename.endswith(('.pdf', '.xml')):
                file_path = os.path.join(documents_dir, filename)
                logger.info(f"Processing file: {filename}")
                chunks = document_processor.process_file(file_path)
                db_manager.add_texts(chunks)
        return {"message": "Reset and rescan completed successfully"}
    except Exception as e:
        logger.error(f"Error during reset and rescan: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
async def root():
    return {"message": "Local RAG App Backend is running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)