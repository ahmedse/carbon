"""
Seed GHG Protocol knowledge into RAG database.
Run this to initialize the AI Copilot's knowledge base.
"""

import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from ai_copilot.services.rag_engine import get_rag_engine


def main():
    """Seed GHG Protocol basics into ChromaDB."""
    print("🚀 Initializing AI Copilot Knowledge Base...")
    
    try:
        rag_engine = get_rag_engine()
        print("✅ Connected to ChromaDB")
        
        # Seed basic GHG Protocol knowledge
        rag_engine.seed_ghg_protocol_basics()
        
        print("\n🎉 Knowledge base seeded successfully!")
        print("📊 The AI Copilot can now answer questions about:")
        print("  - GHG Protocol scopes")
        print("  - Emission calculation formulas")
        print("  - Data quality tiers")
        print("  - Organizational boundaries")
        print("  - Common Scope 1 sources")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
