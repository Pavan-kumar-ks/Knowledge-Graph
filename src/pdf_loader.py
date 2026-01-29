"""
PDF loading and text extraction module.
Handles PDF file processing and text extraction.
"""

import logging
from pathlib import Path
from typing import Dict

from PyPDF2 import PdfReader

logger = logging.getLogger(__name__)


class PDFLoader:
    """Loads and extracts text from PDF files."""
    
    def __init__(self, pdf_dir: Path):
        """
        Initialize PDF loader.
        
        Args:
            pdf_dir: Directory containing PDF files
            
        Raises:
            ValueError: If directory doesn't exist
        """
        self.pdf_dir = Path(pdf_dir)
        if not self.pdf_dir.exists():
            raise ValueError(f"PDF directory not found: {self.pdf_dir}")
        logger.info(f"Initialized PDFLoader with directory: {self.pdf_dir}")
    
    def load_pdf_text(self, pdf_path: Path) -> str:
        """
        Extract text from a single PDF file.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Extracted text content
            
        Raises:
            FileNotFoundError: If PDF file not found
            Exception: If extraction fails
        """
        pdf_path = Path(pdf_path)
        
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
        
        try:
            reader = PdfReader(pdf_path)
            text = ""
            for page_num, page in enumerate(reader.pages):
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
            
            logger.info(f"Extracted text from {pdf_path.name} ({len(reader.pages)} pages)")
            return text
        except Exception as e:
            logger.error(f"Failed to extract text from {pdf_path.name}: {e}")
            raise
    
    def load_all_pdfs(self) -> Dict[str, str]:
        """
        Load text from all PDF files in directory.
        
        Returns:
            Dictionary mapping filename to extracted text
        """
        docs = {}
        pdf_files = list(self.pdf_dir.glob("*.pdf"))
        
        if not pdf_files:
            logger.warning(f"No PDF files found in {self.pdf_dir}")
            return docs
        
        logger.info(f"Found {len(pdf_files)} PDF files")
        
        for pdf_file in pdf_files:
            try:
                text = self.load_pdf_text(pdf_file)
                docs[pdf_file.name] = text
            except Exception as e:
                logger.error(f"Skipping {pdf_file.name}: {e}")
                continue
        
        logger.info(f"Successfully loaded {len(docs)} PDFs")
        return docs


# Legacy functions for backward compatibility
def load_pdf_text(pdf_path: str) -> str:
    """Load text from a PDF file (legacy function)."""
    loader = PDFLoader(Path(pdf_path).parent)
    return loader.load_pdf_text(Path(pdf_path))


def load_all_pdfs(folder: str) -> Dict[str, str]:
    """Load all PDFs from a folder (legacy function)."""
    loader = PDFLoader(folder)
    return loader.load_all_pdfs()


if __name__ == "__main__":
    from config import config
    
    try:
        loader = PDFLoader(config.PDF_DIR)
        docs = loader.load_all_pdfs()
        print(f"Loaded documents: {list(docs.keys())}")
    except Exception as e:
        logger.error(f"Failed to load PDFs: {e}")
