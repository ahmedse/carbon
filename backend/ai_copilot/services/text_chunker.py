"""
Text Chunking Service
Implements intelligent chunking strategies for RAG ingestion.
"""

from typing import List, Dict, Optional
from dataclasses import dataclass, field
import re
import logging

logger = logging.getLogger(__name__)


@dataclass
class Chunk:
    """A chunk of text with metadata."""
    content: str
    chunk_index: int
    start_char: int
    end_char: int
    metadata: Dict = field(default_factory=dict)
    
    @property
    def word_count(self) -> int:
        return len(self.content.split())
    
    @property
    def char_count(self) -> int:
        return len(self.content)


class TextChunker:
    """
    Chunks text using multiple strategies optimized for RAG retrieval.
    
    Strategies:
    - recursive: Split by paragraphs, then sentences, then words (default)
    - semantic: Split at semantic boundaries (headers, sections)
    - fixed: Fixed size chunks with overlap
    - sentence: Split by sentences, combine up to chunk_size
    """
    
    # Separators for recursive chunking (in order of priority)
    SEPARATORS = [
        "\n\n\n",  # Multiple blank lines (section breaks)
        "\n\n",    # Paragraph breaks
        "\n",      # Line breaks
        ". ",      # Sentence ends
        "! ",
        "? ",
        "; ",      # Clause separators
        ", ",
        " ",       # Word breaks
        "",        # Character-level (last resort)
    ]
    
    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        strategy: str = 'recursive',
        min_chunk_size: int = 100,
    ):
        """
        Initialize the text chunker.
        
        Args:
            chunk_size: Target chunk size in characters (~200-250 tokens)
            chunk_overlap: Overlap between chunks for context continuity
            strategy: Chunking strategy ('recursive', 'semantic', 'fixed', 'sentence')
            min_chunk_size: Minimum chunk size (smaller chunks are merged)
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.strategy = strategy
        self.min_chunk_size = min_chunk_size
    
    def chunk(self, text: str, metadata: Optional[Dict] = None) -> List[Chunk]:
        """
        Split text into chunks using the configured strategy.
        
        Args:
            text: Full document text
            metadata: Document metadata to inherit to all chunks
            
        Returns:
            List of Chunk objects with content and metadata
        """
        if not text or not text.strip():
            return []
        
        metadata = metadata or {}
        
        # Select strategy
        if self.strategy == 'recursive':
            raw_chunks = self._recursive_chunk(text)
        elif self.strategy == 'semantic':
            raw_chunks = self._semantic_chunk(text)
        elif self.strategy == 'fixed':
            raw_chunks = self._fixed_chunk(text)
        elif self.strategy == 'sentence':
            raw_chunks = self._sentence_chunk(text)
        else:
            raise ValueError(f"Unknown chunking strategy: {self.strategy}")
        
        # Build Chunk objects with metadata
        chunks = []
        current_pos = 0
        
        for i, chunk_text in enumerate(raw_chunks):
            # Find the actual position in original text
            start_pos = text.find(chunk_text[:50], current_pos)
            if start_pos == -1:
                start_pos = current_pos
            
            end_pos = start_pos + len(chunk_text)
            current_pos = max(current_pos, end_pos - self.chunk_overlap)
            
            # Inherit document metadata and add chunk-specific info
            chunk_metadata = {
                **metadata,
                'chunk_index': i,
                'chunk_total': len(raw_chunks),
                'chunk_start': start_pos,
                'chunk_end': end_pos,
            }
            
            # Add section header if this chunk starts with one
            header = self._extract_header(chunk_text)
            if header:
                chunk_metadata['section'] = header
            
            chunks.append(Chunk(
                content=chunk_text.strip(),
                chunk_index=i,
                start_char=start_pos,
                end_char=end_pos,
                metadata=chunk_metadata
            ))
        
        return chunks
    
    def _recursive_chunk(self, text: str, separators: Optional[List[str]] = None) -> List[str]:
        """
        Recursively split text by separators until chunks are small enough.
        
        This is the most effective strategy for maintaining semantic coherence
        while respecting size limits.
        """
        separators = separators or self.SEPARATORS
        
        # Base case: text is small enough
        if len(text) <= self.chunk_size:
            return [text] if text.strip() else []
        
        # Try each separator in order
        for sep in separators:
            if sep and sep in text:
                splits = text.split(sep)
                
                # Recombine small splits with overlap
                chunks = []
                current_chunk = ""
                
                for split in splits:
                    # If adding this split would exceed size, save current and start new
                    test_chunk = current_chunk + sep + split if current_chunk else split
                    
                    if len(test_chunk) > self.chunk_size:
                        if current_chunk:
                            chunks.append(current_chunk)
                        
                        # If single split is too large, recursively chunk it
                        if len(split) > self.chunk_size:
                            # Try with remaining separators
                            remaining_seps = separators[separators.index(sep) + 1:]
                            sub_chunks = self._recursive_chunk(split, remaining_seps)
                            chunks.extend(sub_chunks)
                            current_chunk = ""
                        else:
                            current_chunk = split
                    else:
                        current_chunk = test_chunk
                
                if current_chunk:
                    chunks.append(current_chunk)
                
                # Add overlap between chunks
                chunks = self._add_overlap(chunks)
                
                return chunks
        
        # No separator found, force split by size
        return self._fixed_chunk(text)
    
    def _semantic_chunk(self, text: str) -> List[str]:
        """
        Split at semantic boundaries (headers, sections).
        
        Ideal for structured documents like markdown or documentation.
        """
        chunks = []
        
        # Split by markdown headers
        header_pattern = re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE)
        
        # Find all header positions
        headers = list(header_pattern.finditer(text))
        
        if not headers:
            # No headers found, fall back to recursive
            return self._recursive_chunk(text)
        
        # Split by headers
        last_end = 0
        for i, header in enumerate(headers):
            # Get text before this header (if any)
            if header.start() > last_end:
                before_text = text[last_end:header.start()].strip()
                if before_text:
                    # Chunk the pre-header text
                    chunks.extend(self._recursive_chunk(before_text))
            
            # Get text from this header to next (or end)
            next_start = headers[i + 1].start() if i + 1 < len(headers) else len(text)
            section_text = text[header.start():next_start].strip()
            
            # If section is too large, chunk it
            if len(section_text) > self.chunk_size:
                # Keep header with first chunk
                sub_chunks = self._recursive_chunk(section_text)
                chunks.extend(sub_chunks)
            else:
                chunks.append(section_text)
            
            last_end = next_start
        
        # Add overlap
        chunks = self._add_overlap(chunks)
        
        return chunks
    
    def _fixed_chunk(self, text: str) -> List[str]:
        """
        Split into fixed-size chunks with overlap.
        
        Simple but may break in the middle of sentences.
        """
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + self.chunk_size
            
            # Try to break at a good boundary (space, newline)
            if end < len(text):
                # Look for a good break point in the last 20% of the chunk
                search_start = max(start, end - int(self.chunk_size * 0.2))
                best_break = end
                
                for sep in ['\n\n', '\n', '. ', ' ']:
                    last_sep = text.rfind(sep, search_start, end)
                    if last_sep > search_start:
                        best_break = last_sep + len(sep)
                        break
                
                end = best_break
            
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            # Move start with overlap
            start = end - self.chunk_overlap
            if start >= len(text):
                break
        
        return chunks
    
    def _sentence_chunk(self, text: str) -> List[str]:
        """
        Split by sentences, then combine sentences up to chunk_size.
        
        Preserves complete sentences for better readability.
        """
        # Simple sentence splitting (handles common cases)
        sentence_pattern = re.compile(r'(?<=[.!?])\s+(?=[A-Z])')
        sentences = sentence_pattern.split(text)
        
        chunks = []
        current_chunk = ""
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            
            # Test if adding this sentence exceeds limit
            test_chunk = current_chunk + " " + sentence if current_chunk else sentence
            
            if len(test_chunk) > self.chunk_size:
                if current_chunk:
                    chunks.append(current_chunk)
                
                # If single sentence is too long, use fixed chunking
                if len(sentence) > self.chunk_size:
                    chunks.extend(self._fixed_chunk(sentence))
                    current_chunk = ""
                else:
                    current_chunk = sentence
            else:
                current_chunk = test_chunk
        
        if current_chunk:
            chunks.append(current_chunk)
        
        # Add overlap
        chunks = self._add_overlap(chunks)
        
        return chunks
    
    def _add_overlap(self, chunks: List[str]) -> List[str]:
        """
        Add overlap between chunks by prepending context from previous chunk.
        """
        if not chunks or self.chunk_overlap <= 0:
            return chunks
        
        overlapped = []
        
        for i, chunk in enumerate(chunks):
            if i == 0:
                overlapped.append(chunk)
            else:
                # Get end of previous chunk for context
                prev_chunk = chunks[i - 1]
                overlap_text = prev_chunk[-self.chunk_overlap:] if len(prev_chunk) > self.chunk_overlap else prev_chunk
                
                # Find a good break point in overlap
                break_point = overlap_text.rfind('. ')
                if break_point > 0:
                    overlap_text = overlap_text[break_point + 2:]
                
                # Prepend overlap to current chunk
                overlapped.append(overlap_text + " " + chunk if overlap_text.strip() else chunk)
        
        return overlapped
    
    def _extract_header(self, text: str) -> Optional[str]:
        """Extract markdown header from the beginning of text if present."""
        lines = text.strip().split('\n')
        if lines:
            first_line = lines[0].strip()
            if first_line.startswith('#'):
                return re.sub(r'^#+\s*', '', first_line)
        return None
    
    def merge_small_chunks(self, chunks: List[Chunk]) -> List[Chunk]:
        """
        Merge chunks that are smaller than min_chunk_size.
        
        Args:
            chunks: List of chunks to process
            
        Returns:
            List with small chunks merged into neighbors
        """
        if not chunks:
            return chunks
        
        merged = []
        current = None
        
        for chunk in chunks:
            if chunk.char_count < self.min_chunk_size:
                # Try to merge with current
                if current:
                    # Combine content
                    combined_content = current.content + "\n\n" + chunk.content
                    current = Chunk(
                        content=combined_content,
                        chunk_index=current.chunk_index,
                        start_char=current.start_char,
                        end_char=chunk.end_char,
                        metadata={**current.metadata, 'merged': True}
                    )
                else:
                    current = chunk
            else:
                if current:
                    # Save current and any small chunk merged into it
                    if current.char_count >= self.min_chunk_size:
                        merged.append(current)
                    else:
                        # Merge small current with this chunk
                        combined = current.content + "\n\n" + chunk.content
                        chunk = Chunk(
                            content=combined,
                            chunk_index=chunk.chunk_index,
                            start_char=current.start_char,
                            end_char=chunk.end_char,
                            metadata={**chunk.metadata, 'merged': True}
                        )
                merged.append(chunk)
                current = None
        
        # Don't forget the last chunk
        if current:
            merged.append(current)
        
        # Re-index
        for i, chunk in enumerate(merged):
            chunk.chunk_index = i
            chunk.metadata['chunk_index'] = i
            chunk.metadata['chunk_total'] = len(merged)
        
        return merged
