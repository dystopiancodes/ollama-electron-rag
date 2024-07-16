import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import os
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class DocumentHandler(FileSystemEventHandler):
    def __init__(self, document_processor, db_manager):
        self.document_processor = document_processor
        self.db_manager = db_manager

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
            logger.debug(f"Removed from database: {filename}")
        except Exception as e:
            logger.error(f"Error removing file {file_path} from database: {str(e)}")

class FileWatcher:
    def __init__(self, path_to_watch, document_processor, db_manager):
        self.path_to_watch = path_to_watch
        self.handler = DocumentHandler(document_processor, db_manager)
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