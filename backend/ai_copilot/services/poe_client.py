"""
POE API Client
Low-cost LLM access via POE platform
"""

import os
import asyncio
import logging
from typing import List, Dict, AsyncIterator
import fastapi_poe as fp
from django.conf import settings

logger = logging.getLogger('ai_copilot')


class POEClient:
    """
    Client for POE API - cost-effective access to GPT-4, Claude, etc.
    """
    
    def __init__(self):
        self.api_key = os.getenv('POE_API_KEY')
        self.model = os.getenv('ACTIVE_POE_MODEL', 'gpt-4o')
        
        if not self.api_key:
            raise ValueError("POE_API_KEY not set in environment")
    
    async def chat(
        self, 
        messages: List[Dict[str, str]], 
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> str:
        """
        Send chat completion request to POE.
        
        Args:
            messages: List of {"role": "user/assistant/system", "content": "..."}
            temperature: Randomness (0-1)
            max_tokens: Maximum response length
            
        Returns:
            Assistant's response text
        """
        logger.info(f"POE: Calling API with model={self.model}, messages={len(messages)}")
        # Convert to POE message format
        poe_messages = [
            fp.ProtocolMessage(role=msg["role"], content=msg["content"])
            for msg in messages
        ]
        
        # Collect streaming response
        response_text = ""
        chunk_count = 0
        
        try:
            async for partial in fp.get_bot_response(
                messages=poe_messages,
                bot_name=self.model,
                api_key=self.api_key,
                temperature=temperature
            ):
                response_text += partial.text
                chunk_count += 1
            
            logger.info(f"POE: Response complete, {len(response_text)} chars in {chunk_count} chunks")
        except Exception as e:
            logger.error(f"POE: API call failed: {e}")
            raise
        
        return response_text
    
    async def chat_stream(
        self, 
        messages: List[Dict[str, str]], 
        temperature: float = 0.7
    ) -> AsyncIterator[str]:
        """
        Streaming chat completion.
        
        Yields:
            Chunks of assistant's response
        """
        poe_messages = [
            fp.ProtocolMessage(role=msg["role"], content=msg["content"])
            for msg in messages
        ]
        
        async for partial in fp.get_bot_response(
            messages=poe_messages,
            bot_name=self.model,
            api_key=self.api_key,
            temperature=temperature
        ):
            yield partial.text
    
    def count_tokens(self, text: str) -> int:
        """
        Approximate token count.
        Rule of thumb: 1 token ≈ 4 characters
        """
        return len(text) // 4
    
    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """
        Estimate cost in USD.
        POE pricing varies but roughly:
        - GPT-4o: ~$0.005 per 1K tokens (combined)
        """
        total_tokens = input_tokens + output_tokens
        cost_per_1k = 0.005  # Approximate
        
        return (total_tokens / 1000) * cost_per_1k


# Singleton instance
_poe_client = None

def get_poe_client() -> POEClient:
    """Get or create POE client instance."""
    global _poe_client
    if _poe_client is None:
        _poe_client = POEClient()
    return _poe_client
