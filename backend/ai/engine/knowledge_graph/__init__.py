"""
knowledge_graph — Stage 1 Knowledge Graph Foundation for Pulse V1.1.

Provides KnowledgeNode, KnowledgeEdge, KnowledgeGraphStore, migration, and
graph-aware context assembly. Replaces flat KnowledgeEntity retrieval with
a three-layer graph: SQLite (structure), ChromaDB (semantic search),
and an in-memory adjacency list (fast traversal).
"""
