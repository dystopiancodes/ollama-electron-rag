# File: backend/app/file_watcher.py
import threading
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
            logger.info(f"New file detected: {event.src_path}")
            self._process_file(event.src_path)

    def on_modified(self, event):
        if not event.is_directory:
            logger.info(f"File modified: {event.src_path}")
            self._process_file(event.src_path)

    def _process_file(self, file_path):
        try:
            logger.info(f"Starting to process file: {file_path}")
            chunks = self.document_processor.process_file(file_path)
            logger.info(f"File processed, got {len(chunks)} chunks")
            metadata = {"source": os.path.basename(file_path)}
            self.db_manager.add_texts(chunks, [metadata] * len(chunks))
            logger.info(f"Processed and added to database: {file_path}")
        except Exception as e:
            logger.error(f"Error processing file {file_path}: {str(e)}", exc_info=True)

    def on_deleted(self, event):
        if not event.is_directory:
            logger.info(f"File deleted: {event.src_path}")
            self._remove_file_from_db(event.src_path)

    def _remove_file_from_db(self, file_path):
        try:
            filename = os.path.basename(file_path)
            logger.info(f"Removing file from database: {filename}")
            self.db_manager.remove_documents({"source": filename})
            logger.info(f"Removed from database: {filename}")
        except Exception as e:
            logger.error(f"Error removing file {file_path} from database: {str(e)}", exc_info=True)

class FileWatcher:
    def __init__(self, path_to_watch, db_manager, document_processor):
        self.path_to_watch = path_to_watch
        self.handler = DocumentHandler(db_manager, document_processor, path_to_watch)
        self.observer = Observer()
        self.stop_event = threading.Event()

    def run(self):
        self.observer.schedule(self.handler, self.path_to_watch, recursive=False)
        self.observer.start()
        try:
            while not self.stop_event.is_set():
                self.stop_event.wait(1)
        finally:
            self.observer.stop()
            self.observer.join()

    def stop(self):
        self.stop_event.set()
        if self.observer.is_alive():
            self.observer.stop()
            self.observer.join()