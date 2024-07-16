import os
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from .components import document_processor, db_manager, documents_dir
from .file_watcher import FileWatcher
from .conf import config
import threading
import logging
from langchain.prompts import PromptTemplate
from langchain_community.llms import Ollama
import json
import asyncio

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = FastAPI()

logger.debug(f"Documents directory: {documents_dir}")

# Start file watcher in a separate thread
file_watcher = FileWatcher(documents_dir, document_processor, db_manager)
watcher_thread = threading.Thread(target=file_watcher.run, daemon=True)
watcher_thread.start()
logger.debug("File watcher thread started")

# Initialize Ollama LLM
llm = Ollama(model="mistral")

class Query(BaseModel):
    text: str

class PromptTemplateUpdate(BaseModel):
    template: str

def cleanup_database():
    logger.info("Starting database cleanup")
    try:
        # Get the current list of files in the documents directory
        current_files = set([f for f in os.listdir(documents_dir) if os.path.isfile(os.path.join(documents_dir, f))])
        
        # Get the list of documents in the database
        db_documents = db_manager.get_all_sources()
        
        # Remove documents from the database that no longer exist in the directory
        for doc in db_documents - current_files:
            logger.info(f"Removing document from database: {doc}")
            db_manager.remove_documents({"source": doc})
        
        # Add new documents to the database
        for file in current_files - db_documents:
            logger.info(f"Adding new document to database: {file}")
            file_path = os.path.join(documents_dir, file)
            chunks = document_processor.process_file(file_path)
            metadata = {"source": file}
            db_manager.add_texts(chunks, [metadata] * len(chunks))
        
        logger.info("Database cleanup completed")
    except Exception as e:
        logger.error(f"Error during database cleanup: {str(e)}")

@app.on_event("startup")
async def startup_event():
    cleanup_database()

async def query_stream(query: str):
    try:
        # Retrieve relevant documents
        docs = db_manager.similarity_search(query, k=3)
        
        # Prepare context
        context = "\n".join([doc.page_content for doc in docs])
        
        # Generate prompt using the current template from config
        prompt_template = PromptTemplate(
            input_variables=["context", "question"],
            template=config.get_prompt_template()
        )
        prompt = prompt_template.format(context=context, question=query)
        
        # Generate response using LLM
        response = ""
        sources = list(set([doc.metadata.get("source") for doc in docs]))  # Unique sources
        yield json.dumps({"sources": sources}) + "\n"

        for chunk in llm.stream(prompt):
            response += chunk
            yield json.dumps({"answer": chunk}) + "\n"
            await asyncio.sleep(0.1)  # Small delay to simulate streaming
        
    except Exception as e:
        logger.error(f"Error during query: {str(e)}")
        yield json.dumps({"error": str(e)}) + "\n"

@app.post("/query")
async def query_documents(query: Query):
    return StreamingResponse(query_stream(query.text), media_type="application/json")

@app.get("/documents")
async def list_documents():
    try:
        documents = [f for f in os.listdir(documents_dir) if os.path.isfile(os.path.join(documents_dir, f))]
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

@app.get("/")
async def root():
    return {"message": "Local RAG App Backend is running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)