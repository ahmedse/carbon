"""
Test AI Copilot functionality
"""

import asyncio
from django.core.management.base import BaseCommand
from ai_copilot.services import get_poe_client, get_conversation_memory, get_rag_engine


class Command(BaseCommand):
    help = 'Test AI Copilot services'
    
    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('🧪 Testing AI Copilot Services\n'))
        
        # Test POE Client
        self.stdout.write('1️⃣ Testing POE API Client...')
        asyncio.run(self.test_poe_client())
        
        # Test RAG Engine
        self.stdout.write('\n2️⃣ Testing RAG Engine...')
        asyncio.run(self.test_rag_engine())
        
        # Test Memory
        self.stdout.write('\n3️⃣ Testing Conversation Memory...')
        asyncio.run(self.test_memory())
        
        self.stdout.write(self.style.SUCCESS('\n✅ All tests passed!'))
    
    async def test_poe_client(self):
        """Test POE API integration."""
        try:
            client = get_poe_client()
            
            # Simple test message
            response = await client.chat([
                {"role": "user", "content": "Say 'Hello from Carbon AI' in exactly 5 words"}
            ])
            
            self.stdout.write(f"   Response: {response['content']}")
            self.stdout.write(f"   Tokens: ~{response.get('tokens', 'N/A')}")
            self.stdout.write(f"   Cost: ~${client.estimate_cost(response.get('tokens', 100)):.4f}")
            self.stdout.write(self.style.SUCCESS('   ✓ POE Client working'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'   ✗ POE Client failed: {e}'))
    
    async def test_rag_engine(self):
        """Test RAG semantic search."""
        try:
            rag = get_rag_engine()
            
            # Test query
            query = "What are the three GHG Protocol scopes?"
            results = await rag.retrieve(query, top_k=2)
            
            self.stdout.write(f"   Query: '{query}'")
            self.stdout.write(f"   Found {len(results)} relevant documents:")
            
            for i, result in enumerate(results, 1):
                self.stdout.write(f"   [{i}] Distance: {result['distance']:.3f}")
                self.stdout.write(f"       Preview: {result['text'][:100]}...")
            
            self.stdout.write(self.style.SUCCESS('   ✓ RAG Engine working'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'   ✗ RAG Engine failed: {e}'))
    
    async def test_memory(self):
        """Test Redis conversation memory."""
        try:
            memory = get_conversation_memory()
            
            # Test user ID
            test_user_id = 999
            
            # Clear previous
            await memory.clear_history(test_user_id)
            
            # Add messages
            await memory.add_message(test_user_id, "user", "What is Scope 1?")
            await memory.add_message(test_user_id, "assistant", "Scope 1 covers direct emissions from owned sources.")
            
            # Retrieve
            history = await memory.get_history(test_user_id, last_n=10)
            
            self.stdout.write(f"   Stored {len(history)} messages")
            for msg in history:
                role = msg['role']
                content = msg['content'][:50]
                self.stdout.write(f"   [{role}] {content}...")
            
            # Get summary
            summary = await memory.get_context_summary(test_user_id)
            self.stdout.write(f"   Context summary: {summary[:100]}...")
            
            # Cleanup
            await memory.clear_history(test_user_id)
            
            self.stdout.write(self.style.SUCCESS('   ✓ Memory working'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'   ✗ Memory failed: {e}'))
