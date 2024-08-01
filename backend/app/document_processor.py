import os
import pdfplumber
import xml.etree.ElementTree as ET
from typing import List, Dict, Tuple

class DocumentProcessor:
    def __init__(self, chunk_size=1000, chunk_overlap=200):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def process_file(self, file_path):
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