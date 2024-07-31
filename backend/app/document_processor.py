import os
import pdfplumber
import xml.etree.ElementTree as ET
from typing import List, Dict

class DocumentProcessor:
    def __init__(self):
        self.chunk_size = 1000
        self.chunk_overlap = 200

    def process_pdf(self, file_path):
        """Process a PDF file and return a list of text chunks."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        with pdfplumber.open(file_path) as pdf:
            text = ""
            for page in pdf.pages:
                text += page.extract_text() + "\n"

        return self.split_text(text)

    def process_xml(self, file_path):
        """Process any XML file and return a list of text chunks."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        tree = ET.parse(file_path)
        root = tree.getroot()

        flattened_data = self._flatten_xml(root)
        formatted_text = self._format_flattened_data(flattened_data)
        return self.split_text(formatted_text)

    def _flatten_xml(self, element, parent_path=''):
        """Recursively flatten XML into a dictionary of key-value pairs."""
        items = {}
        for child in element:
            child_path = f"{parent_path}/{child.tag}" if parent_path else child.tag
            if len(child) == 0:
                items[child_path] = child.text.strip() if child.text else ''
            else:
                items.update(self._flatten_xml(child, child_path))
        return items

    def _format_flattened_data(self, data: Dict[str, str]) -> str:
        """Format flattened data into a more structured, hierarchical output."""
        formatted_output = []
        current_document = {}
        current_section = None

        for key, value in data.items():
            parts = key.split('/')
            if 'FatturaElettronicaBody' in parts:
                doc_index = parts.index('FatturaElettronicaBody')
                section = '/'.join(parts[doc_index+1:doc_index+3])
                subsection = '/'.join(parts[doc_index+3:])
            else:
                section = 'Header'
                subsection = '/'.join(parts)

            if section != current_section:
                if current_document:
                    formatted_output.append(self._format_document(current_document))
                    current_document = {}
                current_section = section

            if section not in current_document:
                current_document[section] = {}
            
            if subsection not in current_document[section]:
                current_document[section][subsection] = []
            current_document[section][subsection].append(f"{parts[-1]}: {value}")

        if current_document:
            formatted_output.append(self._format_document(current_document))

        return '\n\n'.join(formatted_output)

    def _format_document(self, document: Dict) -> str:
        """Format a single document structure into a string."""
        doc_parts = []
        for section, subsections in document.items():
            doc_parts.append(f"--- {section} ---")
            for subsection, items in subsections.items():
                doc_parts.append(f"  {subsection}:")
                doc_parts.extend(f"    {item}" for item in items)
        return '\n'.join(doc_parts)

    def split_text(self, text: str) -> List[str]:
        """Split the text into chunks."""
        chunks = []
        words = text.split()
        current_chunk = []

        for word in words:
            if len(' '.join(current_chunk)) + len(word) > self.chunk_size and current_chunk:
                chunks.append(' '.join(current_chunk))
                current_chunk = []
            current_chunk.append(word)

        if current_chunk:
            chunks.append(' '.join(current_chunk))

        return chunks

    def process_file(self, file_path):
        """Process a file based on its extension."""
        _, ext = os.path.splitext(file_path)
        if ext.lower() == '.pdf':
            return self.process_pdf(file_path)
        elif ext.lower() == '.xml':
            return self.process_xml(file_path)
        else:
            raise ValueError(f"Unsupported file type: {ext}")