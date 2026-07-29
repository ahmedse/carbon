"""
Services package initialization
"""

# Lazy imports to allow graceful degradation when AI packages are not installed

POEClient = None
get_poe_client = None
ConversationMemory = None
get_conversation_memory = None
RAGEngine = None
get_rag_engine = None
ContextEngine = None
get_context_engine = None

def _lazy_import_poe():
    global POEClient, get_poe_client
    if POEClient is None:
        from .poe_client import POEClient as _POEClient, get_poe_client as _get_poe_client
        POEClient = _POEClient
        get_poe_client = _get_poe_client

def _lazy_import_memory():
    global ConversationMemory, get_conversation_memory
    if ConversationMemory is None:
        from .memory import ConversationMemory as _ConversationMemory, get_conversation_memory as _get
        ConversationMemory = _ConversationMemory
        get_conversation_memory = _get

def _lazy_import_rag():
    global RAGEngine, get_rag_engine
    if RAGEngine is None:
        from .rag_engine import RAGEngine as _RAGEngine, get_rag_engine as _get
        RAGEngine = _RAGEngine
        get_rag_engine = _get

def _lazy_import_context():
    global ContextEngine, get_context_engine
    if ContextEngine is None:
        from .context_engine import ContextEngine as _ContextEngine, get_context_engine as _get
        ContextEngine = _ContextEngine
        get_context_engine = _get

__all__ = [
    'get_poe_client', 
    'POEClient', 
    'ConversationMemory', 
    'get_conversation_memory',
    'RAGEngine',
    'get_rag_engine',
    'ContextEngine',
    'get_context_engine',
]
