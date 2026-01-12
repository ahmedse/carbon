"""
RAG Engine - Retrieval Augmented Generation
Carbon domain knowledge base with semantic search
"""

import os
from typing import List, Dict, Optional
from pathlib import Path

try:
    import chromadb
    from chromadb.config import Settings
    from sentence_transformers import SentenceTransformer
    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False


class RAGEngine:
    """
    Retrieval-Augmented Generation for carbon domain knowledge.
    Uses ChromaDB for vector storage and semantic search.
    """
    
    def __init__(self):
        if not CHROMA_AVAILABLE:
            raise ImportError("ChromaDB not installed. Run: pip install chromadb sentence-transformers")
        
        # Initialize embedding model
        self.embedder = SentenceTransformer('all-MiniLM-L6-v2')
        
        # Initialize ChromaDB
        persist_dir = os.getenv('CHROMA_PERSIST_DIR', './chroma_db')
        Path(persist_dir).mkdir(parents=True, exist_ok=True)
        
        self.client = chromadb.Client(Settings(
            persist_directory=persist_dir,
            anonymized_telemetry=False
        ))
        
        # Get or create collection
        self.collection = self.client.get_or_create_collection(
            name="carbon_knowledge",
            metadata={"hnsw:space": "cosine"}
        )
    
    def add_document(
        self, 
        doc_id: str, 
        text: str, 
        metadata: Optional[Dict] = None
    ):
        """
        Add document to knowledge base.
        
        Args:
            doc_id: Unique document identifier
            text: Document content
            metadata: Optional metadata (source, category, etc.)
        """
        # Generate embedding
        embedding = self.embedder.encode(text).tolist()
        
        # Store in ChromaDB
        self.collection.add(
            embeddings=[embedding],
            documents=[text],
            metadatas=[metadata or {}],
            ids=[doc_id]
        )
    
    def add_documents_batch(self, documents: List[Dict]):
        """
        Add multiple documents efficiently.
        
        Args:
            documents: List of {"id": str, "text": str, "metadata": dict}
        """
        if not documents:
            return
        
        texts = [doc["text"] for doc in documents]
        embeddings = self.embedder.encode(texts).tolist()
        
        self.collection.add(
            embeddings=embeddings,
            documents=texts,
            metadatas=[doc.get("metadata", {}) for doc in documents],
            ids=[doc["id"] for doc in documents]
        )
    
    async def retrieve(
        self, 
        query: str, 
        top_k: int = 3,
        filter_metadata: Optional[Dict] = None
    ) -> List[Dict]:
        """
        Semantic search for relevant documents.
        
        Args:
            query: Search query
            top_k: Number of results to return
            filter_metadata: Optional metadata filters
            
        Returns:
            List of {"text": str, "metadata": dict, "distance": float}
        """
        # Generate query embedding
        query_embedding = self.embedder.encode(query).tolist()
        
        # Search
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=filter_metadata
        )
        
        # Format results
        retrieved = []
        if results['documents']:
            for i, doc in enumerate(results['documents'][0]):
                retrieved.append({
                    "text": doc,
                    "metadata": results['metadatas'][0][i] if results['metadatas'] else {},
                    "distance": results['distances'][0][i] if results['distances'] else 0.0
                })
        
        return retrieved
    
    async def get_context_for_query(
        self, 
        query: str, 
        max_tokens: int = 1500
    ) -> str:
        """
        Retrieve and format context for LLM prompt.
        
        Args:
            query: User query
            max_tokens: Maximum context tokens (approx)
            
        Returns:
            Formatted context string
        """
        results = await self.retrieve(query, top_k=3)
        
        if not results:
            return "No relevant context found in knowledge base."
        
        context_parts = []
        total_chars = 0
        max_chars = max_tokens * 4  # Rough approximation
        
        for i, result in enumerate(results, 1):
            text = result["text"]
            source = result["metadata"].get("source", "Unknown")
            
            snippet = f"[Source {i}: {source}]\n{text}\n"
            
            if total_chars + len(snippet) > max_chars:
                break
            
            context_parts.append(snippet)
            total_chars += len(snippet)
        
        return "\n".join(context_parts)
    
    def seed_ghg_protocol_basics(self):
        """
        Seed knowledge base with essential GHG Protocol information.
        Call this during initial setup.
        """
        basic_knowledge = [
            {
                "id": "ghg_scopes_overview",
                "text": """
                The GHG Protocol defines three scopes for emissions:
                
                Scope 1: Direct emissions from owned or controlled sources (e.g., company vehicles, on-site fuel combustion)
                Scope 2: Indirect emissions from purchased electricity, steam, heating, and cooling
                Scope 3: All other indirect emissions in the value chain (e.g., business travel, supply chain, waste)
                
                Organizations must report Scope 1 and 2, and are encouraged to report Scope 3.
                """,
                "metadata": {"source": "GHG Protocol Corporate Standard", "category": "basics"}
            },
            {
                "id": "emission_calculation_formula",
                "text": """
                Basic GHG emission calculation formula:
                
                CO2e Emissions = Activity Data × Emission Factor × GWP
                
                Where:
                - Activity Data: Amount of activity (e.g., liters of fuel, kWh of electricity)
                - Emission Factor: Emissions per unit of activity (e.g., kg CO2 per liter)
                - GWP: Global Warming Potential (converts other gases to CO2 equivalent)
                
                For CO2: GWP = 1
                For CH4: GWP ≈ 28 (AR6, 100-year)
                For N2O: GWP ≈ 265 (AR6, 100-year)
                """,
                "metadata": {"source": "GHG Protocol", "category": "calculation"}
            },
            {
                "id": "data_quality_tiers",
                "text": """
                GHG Protocol data quality hierarchy (best to worst):
                
                Tier 1: Direct measurement (highest quality)
                - Continuous monitoring equipment
                - Calibrated meters
                
                Tier 2: Site-specific data
                - Invoices, receipts
                - Fuel logs
                
                Tier 3: Industry averages
                - National or regional averages
                - Sector-specific benchmarks
                
                Tier 4: Proxy data
                - Estimates based on similar activities
                - Financial data extrapolation
                
                Always aim for higher tiers and document data sources.
                """,
                "metadata": {"source": "GHG Protocol", "category": "data_quality"}
            },
            {
                "id": "organizational_boundaries",
                "text": """
                Two approaches to defining organizational boundaries:
                
                1. Equity Share Approach:
                   - Report emissions based on ownership percentage
                   - Example: 40% ownership = report 40% of emissions
                
                2. Control Approach:
                   - Financial Control: Report 100% if you have financial control
                   - Operational Control: Report 100% if you direct operations
                   
                Choose one approach and apply consistently.
                """,
                "metadata": {"source": "GHG Protocol", "category": "boundaries"}
            },
            {
                "id": "common_scope1_sources",
                "text": """
                Common Scope 1 emission sources:
                
                - Stationary Combustion: Boilers, furnaces, generators
                - Mobile Combustion: Company vehicles, forklifts
                - Process Emissions: Chemical reactions, manufacturing processes
                - Fugitive Emissions: Refrigerant leaks, natural gas leaks
                
                These require direct measurement or calculation based on fuel use.
                """,
                "metadata": {"source": "GHG Protocol", "category": "scope1"}
            }
        ]
        
        self.add_documents_batch(basic_knowledge)
        print(f"✅ Seeded {len(basic_knowledge)} knowledge base documents")


# Singleton instance
_rag_engine = None

def get_rag_engine() -> RAGEngine:
    """Get or create RAG engine instance."""
    global _rag_engine
    if _rag_engine is None:
        _rag_engine = RAGEngine()
    return _rag_engine
