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
from langchain.schema import HumanMessage, SystemMessage


# Configure logging
logging.basicConfig(level=logging.INFO)
logging.getLogger("chromadb").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# Suppress noisy loggers
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

app = FastAPI()

logger.info(f"Documents directory: {documents_dir}")

# Start file watcher in a separate thread
file_watcher = FileWatcher(documents_dir, document_processor, db_manager)
watcher_thread = threading.Thread(target=file_watcher.run, daemon=True)
watcher_thread.start()
logger.info("File watcher thread started")

# Initialize Ollama LLM
#llm = Ollama(model="mistral")
llm = Ollama(model="orca2")

class Query(BaseModel):
    text: str

class PromptTemplateUpdate(BaseModel):
    template: str

def cleanup_database():
    logger.info("Starting database cleanup")
    try:
        current_files = set([f for f in os.listdir(documents_dir) if os.path.isfile(os.path.join(documents_dir, f))])
        db_documents = db_manager.get_all_sources()
        
        for doc in db_documents - current_files:
            logger.info(f"Removing document from database: {doc}")
            db_manager.remove_documents({"source": doc})
        
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
        docs = db_manager.similarity_search(query, k=3)
        context = "\n".join([doc.page_content for doc in docs])
        prompt_template = PromptTemplate(
            input_variables=["context", "question"],
            template=config.get_prompt_template()
        )
        prompt = prompt_template.format(context=context, question=query)
        
        system_message = "Sei un assistente AI che risponde solo in italiano. Fornisci risposte brevi e concise, senza spiegazioni o ragionamenti. Usa solo la lingua italiana."
        full_prompt = f"{system_message}\n\n{prompt}"

        response = ""
        sources = list(set([doc.metadata.get("source") for doc in docs]))
        yield json.dumps({"sources": sources}) + "\n"

        for chunk in llm.stream(full_prompt):
            response += chunk
            yield json.dumps({"answer": chunk}) + "\n"
            await asyncio.sleep(0.1)
        
    except Exception as e:
        logger.error(f"Error during query: {str(e)}")
        yield json.dumps({"error": str(e)}) + "\n"

@app.post("/query")
async def query_documents(query: Query):
    return StreamingResponse(query_stream(query.text), media_type="application/json")

@app.get("/documents")
async def list_documents():
    try:
        documents = [f for f in os.listdir(documents_dir) if os.path.isfile(os.path.join(documents_dir, f)) and f.lower().endswith(('.pdf', '.xml'))]
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


from .db_manager import is_valid_document


@app.post("/reset-and-rescan")
async def reset_and_rescan():
    async def rescan_generator():
        try:
            # Clear the existing database
            db_manager.clear_database()
            yield json.dumps({"status": "Database cleared"}) + "\n"

            # Get list of valid documents
            documents = [f for f in os.listdir(documents_dir) 
                         if os.path.isfile(os.path.join(documents_dir, f)) and is_valid_document(f)]
            total_documents = len(documents)
            logger.info(f"Found {total_documents} valid documents to process")

            for index, filename in enumerate(documents, start=1):
                try:
                    file_path = os.path.join(documents_dir, filename)
                    logger.info(f"Processing file {index}/{total_documents}: {filename}")
                    chunks = document_processor.process_file(file_path)
                    logger.info(f"File {filename} processed into {len(chunks)} chunks")
                    metadata = [{"source": filename} for _ in chunks]
                    db_manager.add_texts(chunks, metadata)
                    logger.info(f"Added {len(chunks)} chunks from {filename} to the database")
                    
                    progress = (index / total_documents) * 100
                    yield json.dumps({
                        "status": "Processing",
                        "progress": f"{progress:.2f}%",
                        "current": index,
                        "total": total_documents
                    }) + "\n"
                except Exception as e:
                    logger.error(f"Error processing file {filename}: {str(e)}")
                    yield json.dumps({
                        "status": "Error",
                        "file": filename,
                        "error": str(e)
                    }) + "\n"

            logger.info("Document processing completed")
            yield json.dumps({"status": "Completed"}) + "\n"
        except Exception as e:
            logger.error(f"Error during rescan: {str(e)}")
            yield json.dumps({"error": str(e)}) + "\n"

    return StreamingResponse(rescan_generator(), media_type="application/json")




@app.get("/")
async def root():
    return {"message": "Local RAG App Backend is running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)