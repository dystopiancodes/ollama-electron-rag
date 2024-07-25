# backend/app/document_processor.py


import os
import pdfplumber
from langchain_text_splitters import RecursiveCharacterTextSplitter
import xml.etree.ElementTree as ET

class DocumentProcessor:
    def __init__(self):
        self.text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)

    def process_pdf(self, file_path):
        """Process a PDF file and return a list of text chunks."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        with pdfplumber.open(file_path) as pdf:
            text = ""
            for page in pdf.pages:
                text += page.extract_text() + "\n"

        return self.text_splitter.split_text(text)

    def process_xml(self, file_path):
        """Process any XML file and return a list of text chunks."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        tree = ET.parse(file_path)
        root = tree.getroot()

        text = "\n".join(self._xml_to_text(root))
        return self.text_splitter.split_text(text)

    def _xml_to_text(self, element, path=''):
        """Recursively convert XML element to text, including the element path."""
        text = []
        current_path = f"{path}/{element.tag}" if path else element.tag

        # Add attributes if any
        if element.attrib:
            attrs = ", ".join(f"{k}={v}" for k, v in element.attrib.items())
            text.append(f"{current_path} ({attrs})")
        else:
            text.append(current_path)

        # Add text content if any
        if element.text and element.text.strip():
            text.append(f"{current_path}: {element.text.strip()}")

        # Process child elements
        for child in element:
            text.extend(self._xml_to_text(child, current_path))

        return text

    def process_file(self, file_path):
        """Process a file based on its extension."""
        _, ext = os.path.splitext(file_path)
        if ext.lower() == '.pdf':
            return self.process_pdf(file_path)
        elif ext.lower() == '.xml':
            return self.process_xml(file_path)
        else:
            raise ValueError(f"Unsupported file type: {ext}")


# Usage example:
# processor = DocumentProcessor()
# chunks = processor.process_file("path/to/your/document.xml")