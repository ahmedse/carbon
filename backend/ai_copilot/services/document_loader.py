"""
Document Loader Service
Handles PDF, Markdown, Text, and HTML documents for knowledge ingestion.
"""

from pathlib import Path
from typing import Dict, Optional, List
from datetime import datetime
import logging
import re

logger = logging.getLogger(__name__)


class DocumentLoader:
    """Loads and extracts text from various document formats."""
    
    SUPPORTED_EXTENSIONS = {'.pdf', '.md', '.txt', '.html', '.json', '.markdown'}
    
    def __init__(self):
        self._pdf_available = False
        self._bs4_available = False
        
        # Check for optional dependencies
        try:
            import pypdf
            self._pdf_available = True
        except ImportError:
            try:
                import PyPDF2
                self._pdf_available = True
            except ImportError:
                logger.warning("PDF support unavailable. Install: pip install pypdf")
        
        try:
            from bs4 import BeautifulSoup
            self._bs4_available = True
        except ImportError:
            logger.warning("HTML support limited. Install: pip install beautifulsoup4")
    
    def load(self, file_path: Path) -> Dict:
        """
        Load a document and return structured content.
        
        Args:
            file_path: Path to the document
            
        Returns:
            {
                'content': str,
                'metadata': {
                    'source': str,
                    'title': str,
                    'format': str,
                    'pages': int,
                    'word_count': int,
                    'char_count': int,
                    'created_at': str,
                }
            }
        
        Raises:
            ValueError: If file format not supported
            FileNotFoundError: If file doesn't exist
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        suffix = file_path.suffix.lower()
        
        if suffix not in self.SUPPORTED_EXTENSIONS:
            raise ValueError(f"Unsupported file format: {suffix}. Supported: {self.SUPPORTED_EXTENSIONS}")
        
        # Route to appropriate loader
        if suffix == '.pdf':
            return self.load_pdf(file_path)
        elif suffix in {'.md', '.markdown'}:
            return self.load_markdown(file_path)
        elif suffix == '.txt':
            return self.load_text(file_path)
        elif suffix == '.html':
            return self.load_html(file_path)
        elif suffix == '.json':
            return self.load_json(file_path)
        else:
            return self.load_text(file_path)
    
    def load_pdf(self, file_path: Path) -> Dict:
        """
        Extract text from PDF using pypdf or PyPDF2.
        
        Args:
            file_path: Path to PDF file
            
        Returns:
            Document dict with content and metadata
        """
        if not self._pdf_available:
            raise ImportError("PDF support not available. Install: pip install pypdf")
        
        file_path = Path(file_path)
        content_parts = []
        num_pages = 0
        
        try:
            # Try pypdf first (newer)
            try:
                import pypdf
                reader = pypdf.PdfReader(str(file_path))
                num_pages = len(reader.pages)
                for page in reader.pages:
                    text = page.extract_text()
                    if text:
                        content_parts.append(text)
            except ImportError:
                # Fall back to PyPDF2
                import PyPDF2
                with open(file_path, 'rb') as f:
                    reader = PyPDF2.PdfReader(f)
                    num_pages = len(reader.pages)
                    for page in reader.pages:
                        text = page.extract_text()
                        if text:
                            content_parts.append(text)
        
        except Exception as e:
            logger.error(f"Failed to read PDF {file_path}: {e}")
            raise
        
        content = "\n\n".join(content_parts)
        
        # Extract title from filename or first line
        title = self._extract_title(content, file_path.stem)
        
        return {
            'content': content,
            'metadata': {
                'source': str(file_path),
                'source_file': file_path.name,
                'title': title,
                'format': 'pdf',
                'pages': num_pages,
                'word_count': len(content.split()),
                'char_count': len(content),
                'created_at': datetime.now().isoformat(),
            }
        }
    
    def load_markdown(self, file_path: Path) -> Dict:
        """
        Load markdown file, preserving structure and extracting headers.
        
        Args:
            file_path: Path to markdown file
            
        Returns:
            Document dict with content and metadata
        """
        import json
        file_path = Path(file_path)
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Extract title from first H1 header or filename
        title = self._extract_markdown_title(content, file_path.stem)
        
        # Extract headers for structure metadata (serialize to JSON string)
        headers = self._extract_markdown_headers(content)
        headers_json = json.dumps(headers) if headers else "[]"
        
        return {
            'content': content,
            'metadata': {
                'source': str(file_path),
                'source_file': file_path.name,
                'title': title,
                'format': 'markdown',
                'headers': headers_json,  # Serialized as JSON string
                'section_count': len(headers),
                'word_count': len(content.split()),
                'char_count': len(content),
                'created_at': datetime.now().isoformat(),
            }
        }
    
    def load_text(self, file_path: Path) -> Dict:
        """
        Load plain text file.
        
        Args:
            file_path: Path to text file
            
        Returns:
            Document dict with content and metadata
        """
        file_path = Path(file_path)
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        title = self._extract_title(content, file_path.stem)
        
        return {
            'content': content,
            'metadata': {
                'source': str(file_path),
                'source_file': file_path.name,
                'title': title,
                'format': 'text',
                'word_count': len(content.split()),
                'char_count': len(content),
                'created_at': datetime.now().isoformat(),
            }
        }
    
    def load_html(self, file_path: Path) -> Dict:
        """
        Load HTML file, extracting text content.
        
        Args:
            file_path: Path to HTML file
            
        Returns:
            Document dict with content and metadata
        """
        file_path = Path(file_path)
        
        with open(file_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        # Extract text from HTML
        if self._bs4_available:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Remove script and style elements
            for element in soup(['script', 'style', 'nav', 'footer', 'header']):
                element.decompose()
            
            content = soup.get_text(separator='\n', strip=True)
            
            # Try to get title from HTML
            title_tag = soup.find('title')
            title = title_tag.get_text() if title_tag else file_path.stem
        else:
            # Basic HTML stripping without BeautifulSoup
            content = re.sub(r'<[^>]+>', '', html_content)
            content = re.sub(r'\s+', ' ', content).strip()
            title = file_path.stem
        
        return {
            'content': content,
            'metadata': {
                'source': str(file_path),
                'source_file': file_path.name,
                'title': title,
                'format': 'html',
                'word_count': len(content.split()),
                'char_count': len(content),
                'created_at': datetime.now().isoformat(),
            }
        }
    
    def load_json(self, file_path: Path) -> Dict:
        """
        Load JSON file containing document content.
        
        Expected JSON format:
        {
            "title": "Document Title",
            "content": "Document content...",
            "metadata": {...optional extra metadata...}
        }
        
        Args:
            file_path: Path to JSON file
            
        Returns:
            Document dict with content and metadata
        """
        import json
        
        file_path = Path(file_path)
        
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        content = data.get('content', data.get('text', ''))
        if not content:
            # If no content field, serialize the whole JSON as text
            content = json.dumps(data, indent=2)
        
        title = data.get('title', file_path.stem)
        extra_metadata = data.get('metadata', {})
        
        return {
            'content': content,
            'metadata': {
                'source': str(file_path),
                'source_file': file_path.name,
                'title': title,
                'format': 'json',
                'word_count': len(content.split()),
                'char_count': len(content),
                'created_at': datetime.now().isoformat(),
                **extra_metadata
            }
        }
    
    def _extract_title(self, content: str, fallback: str) -> str:
        """Extract title from content or use fallback."""
        # Try to get first non-empty line as title
        lines = content.strip().split('\n')
        for line in lines[:5]:  # Check first 5 lines
            line = line.strip()
            if line and len(line) < 200:  # Reasonable title length
                # Clean up common title markers
                line = re.sub(r'^#+\s*', '', line)  # Remove markdown headers
                line = re.sub(r'^Title:\s*', '', line, flags=re.IGNORECASE)
                if line:
                    return line
        
        # Convert fallback filename to title
        return fallback.replace('_', ' ').replace('-', ' ').title()
    
    def _extract_markdown_title(self, content: str, fallback: str) -> str:
        """Extract title from first H1 header in markdown."""
        # Look for # Title pattern
        match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        if match:
            return match.group(1).strip()
        
        return self._extract_title(content, fallback)
    
    def _extract_markdown_headers(self, content: str) -> List[Dict]:
        """Extract all headers from markdown for structure metadata."""
        headers = []
        header_pattern = re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE)
        
        for match in header_pattern.finditer(content):
            level = len(match.group(1))
            text = match.group(2).strip()
            headers.append({
                'level': level,
                'text': text,
                'position': match.start()
            })
        
        return headers
    
    def get_file_list(self, directory: Path, recursive: bool = True) -> List[Path]:
        """
        Get list of supported files in a directory.
        
        Args:
            directory: Directory to scan
            recursive: Whether to scan subdirectories
            
        Returns:
            List of file paths
        """
        directory = Path(directory)
        files = []
        
        pattern = '**/*' if recursive else '*'
        
        for file_path in directory.glob(pattern):
            if file_path.is_file() and file_path.suffix.lower() in self.SUPPORTED_EXTENSIONS:
                files.append(file_path)
        
        return sorted(files)
