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

        text = self._xml_to_text(root)
        return self.text_splitter.split_text(text)

    def _xml_to_text(self, element, indent=''):
        """Recursively convert XML element to text."""
        text = f"{indent}{element.tag}:"
        
        if element.text and element.text.strip():
            text += f" {element.text.strip()}\n"
        else:
            text += "\n"

        for child in element:
            text += self._xml_to_text(child, indent + '  ')

        if element.tail and element.tail.strip():
            text += f"{indent}{element.tail.strip()}\n"

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