"""
Conversation Memory
Redis-backed short-term memory for chat context
"""

import os
import json
import redis
from typing import List, Dict, Optional
from datetime import datetime, timedelta


class ConversationMemory:
    """
    Manages conversation history with Redis backend.
    Provides fast access to recent conversation context.
    """
    
    def __init__(self):
        redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
        self.redis_client = redis.from_url(redis_url, decode_responses=True)
        self.max_messages = 20  # Keep last N messages per user
        self.ttl_seconds = 86400  # 24 hours
    
    def _get_key(self, user_id: int, project_id: Optional[int] = None) -> str:
        """Generate Redis key for user conversation."""
        if project_id:
            return f"chat:user:{user_id}:project:{project_id}"
        return f"chat:user:{user_id}:global"
    
    async def add_message(
        self, 
        user_id: int, 
        role: str, 
        content: str,
        project_id: Optional[int] = None,
        metadata: Optional[Dict] = None
    ):
        """
        Add message to conversation buffer.
        
        Args:
            user_id: User ID
            role: 'user', 'assistant', or 'system'
            content: Message text
            project_id: Optional project context
            metadata: Optional additional data
        """
        key = self._get_key(user_id, project_id)
        
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {}
        }
        
        # Add to list (left push)
        self.redis_client.lpush(key, json.dumps(message))
        
        # Trim to max length
        self.redis_client.ltrim(key, 0, self.max_messages - 1)
        
        # Set expiration
        self.redis_client.expire(key, self.ttl_seconds)
    
    async def get_history(
        self, 
        user_id: int, 
        project_id: Optional[int] = None,
        last_n: int = 10
    ) -> List[Dict]:
        """
        Retrieve recent conversation history.
        
        Args:
            user_id: User ID
            project_id: Optional project context
            last_n: Number of recent messages to return
            
        Returns:
            List of messages in chronological order (oldest first)
        """
        key = self._get_key(user_id, project_id)
        
        # Get from Redis (returns newest first)
        messages_json = self.redis_client.lrange(key, 0, last_n - 1)
        
        # Parse and reverse to get chronological order
        messages = [json.loads(msg) for msg in reversed(messages_json)]
        
        return messages
    
    async def clear_history(
        self, 
        user_id: int, 
        project_id: Optional[int] = None
    ):
        """Clear conversation history for user."""
        key = self._get_key(user_id, project_id)
        self.redis_client.delete(key)
    
    async def get_context_summary(
        self, 
        user_id: int, 
        project_id: Optional[int] = None
    ) -> str:
        """
        Generate a brief summary of conversation context.
        Useful for prompts.
        """
        history = await self.get_history(user_id, project_id, last_n=5)
        
        if not history:
            return "No previous conversation."
        
        summary_lines = []
        for msg in history[-3:]:  # Last 3 messages
            role = msg["role"]
            content = msg["content"][:100]  # Truncate
            summary_lines.append(f"{role}: {content}")
        
        return "\n".join(summary_lines)


# Singleton instance
_memory = None

def get_conversation_memory() -> ConversationMemory:
    """Get or create memory instance."""
    global _memory
    if _memory is None:
        _memory = ConversationMemory()
    return _memory
