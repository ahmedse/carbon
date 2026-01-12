"""
AI Copilot API Views
"""

import json
import asyncio
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.http import StreamingHttpResponse
from django.utils import timezone
from asgiref.sync import async_to_sync, sync_to_async

from .models import ConversationMessage, ProactiveInsight, UserAIPreference
from .serializers import (
    ConversationMessageSerializer,
    ProactiveInsightSerializer, 
    UserAIPreferenceSerializer,
    ChatRequestSerializer,
    ChatResponseSerializer
)
from .services import get_poe_client, get_conversation_memory, get_rag_engine


class ChatViewSet(viewsets.ViewSet):
    """
    AI Chat interface with RAG-enhanced responses.
    """
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['post'])
    def send_message(self, request):
        """
        Send a message to AI copilot and get response.
        
        POST /api/ai/chat/send_message/
        Body: {"message": str, "project_id": int, "stream": bool}
        """
        serializer = ChatRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = request.user
        message = serializer.validated_data['message']
        project_id = serializer.validated_data.get('project_id')
        stream = serializer.validated_data.get('stream', False)
        
        try:
            # Use async_to_sync to call async functions
            response_data = async_to_sync(self._process_message)(
                user, message, project_id
            )
            return Response(response_data, status=status.HTTP_200_OK)
                
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    async def _process_message(self, user, message, project_id):
        """Async processing of message."""
        # Get conversation memory
        memory = get_conversation_memory()
        
        # Get relevant context from RAG
        rag_engine = get_rag_engine()
        context = await rag_engine.get_context_for_query(message)
        
        # Build system prompt
        system_prompt = self._build_system_prompt(user, project_id, context)
        
        # Get conversation history
        history = await memory.get_history(user.id, project_id, last_n=10)
        
        # Get POE client
        poe_client = get_poe_client()
        
        # Get response
        response = await poe_client.chat(
            messages=[
                {"role": "system", "content": system_prompt},
                *history,
                {"role": "user", "content": message}
            ]
        )
        
        # Save to memory
        await memory.add_message(user.id, "user", message, project_id)
        await memory.add_message(user.id, "assistant", response['content'], project_id)
        
        # Save to database (sync operation)
        await sync_to_async(ConversationMessage.objects.create)(
            user=user,
            project_id=project_id,
            role="user",
            content=message,
            token_count=poe_client.count_tokens(message)
        )
        
        assistant_msg = await sync_to_async(ConversationMessage.objects.create)(
            user=user,
            project_id=project_id,
            role="assistant",
            content=response['content'],
            token_count=response.get('tokens', 0)
        )
        
        # Format response
        response_data = {
            'response': response['content'],
            'conversation_id': assistant_msg.id,
            'tokens_used': response.get('tokens', 0),
            'cost_estimate': poe_client.estimate_cost(response.get('tokens', 0)),
            'sources': []
        }
        
        return response_data
    
    async def _stream_response(self, poe_client, system_prompt, message, history, user, project_id, memory):
        """Stream response generator for server-sent events."""
        full_response = ""
        
        try:
            async for chunk in poe_client.chat_stream(
                messages=[
                    {"role": "system", "content": system_prompt},
                    *history,
                    {"role": "user", "content": message}
                ]
            ):
                full_response += chunk
                yield f"data: {json.dumps({'chunk': chunk})}\n\n"
            
            # Save after streaming complete
            await memory.add_message(user.id, "user", message, project_id)
            await memory.add_message(user.id, "assistant", full_response, project_id)
            
            yield f"data: {json.dumps({'done': True})}\n\n"
            
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
    
    def _build_system_prompt(self, user, project_id, context):
        """Build system prompt with user context and RAG knowledge."""
        base_prompt = f"""You are Carbon Intelligence, an AI assistant specialized in carbon emissions management and GHG Protocol compliance.

User: {user.get_full_name() or user.email}
Role: Help analyze carbon data, provide insights, and guide on emissions reduction strategies.

Knowledge Base Context:
{context}

Guidelines:
- Provide accurate, actionable advice based on GHG Protocol standards
- Reference specific emission factors and calculation methods when relevant
- Suggest data quality improvements when appropriate
- Be concise but thorough in explanations
- If unsure, acknowledge limitations and suggest consulting official documentation
"""
        return base_prompt
    
    @action(detail=False, methods=['get'])
    def history(self, request):
        """
        Get conversation history for current user.
        
        GET /api/ai/chat/history/?project_id=X&limit=20
        """
        project_id = request.query_params.get('project_id')
        limit = int(request.query_params.get('limit', 20))
        
        queryset = ConversationMessage.objects.filter(user=request.user)
        
        if project_id:
            queryset = queryset.filter(project_id=project_id)
        
        messages = queryset.order_by('-created_at')[:limit]
        serializer = ConversationMessageSerializer(messages, many=True)
        
        return Response(serializer.data)
    
    @action(detail=False, methods=['delete'])
    def clear_history(self, request):
        """
        Clear conversation history.
        
        DELETE /api/ai/chat/clear_history/?project_id=X
        """
        project_id = request.query_params.get('project_id')
        
        # Clear from Redis (async)
        memory = get_conversation_memory()
        async_to_sync(memory.clear_history)(request.user.id, project_id)
        
        # Clear from database
        queryset = ConversationMessage.objects.filter(user=request.user)
        if project_id:
            queryset = queryset.filter(project_id=project_id)
        
        count = queryset.delete()[0]
        
        return Response({
            'message': f'Cleared {count} messages',
            'success': True
        })


class InsightViewSet(viewsets.ModelViewSet):
    """
    Proactive insights management.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = ProactiveInsightSerializer
    
    def get_queryset(self):
        """Filter insights for current user."""
        queryset = ProactiveInsight.objects.filter(user=self.request.user)
        
        # Filter by project if specified
        project_id = self.request.query_params.get('project_id')
        if project_id:
            queryset = queryset.filter(project_id=project_id)
        
        # Filter by type if specified
        insight_type = self.request.query_params.get('type')
        if insight_type:
            queryset = queryset.filter(insight_type=insight_type)
        
        # Filter by acknowledged status
        acknowledged = self.request.query_params.get('acknowledged')
        if acknowledged is not None:
            queryset = queryset.filter(acknowledged=acknowledged.lower() == 'true')
        
        return queryset.order_by('-created_at')
    
    @action(detail=True, methods=['post'])
    def acknowledge(self, request, pk=None):
        """
        Mark insight as acknowledged.
        
        POST /api/ai/insights/{id}/acknowledge/
        """
        insight = self.get_object()
        insight.acknowledged = True
        insight.acknowledged_at = timezone.now()
        insight.save()
        
        serializer = self.get_serializer(insight)
        return Response(serializer.data)


class PreferenceViewSet(viewsets.ModelViewSet):
    """
    User AI preference management.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = UserAIPreferenceSerializer
    
    def get_queryset(self):
        """Get or create preferences for current user."""
        return UserAIPreference.objects.filter(user=self.request.user)
    
    def get_object(self):
        """Get or create user preferences."""
        preferences, created = UserAIPreference.objects.get_or_create(
            user=self.request.user
        )
        return preferences
    
    @action(detail=False, methods=['get'])
    def me(self, request):
        """
        Get current user's preferences.
        
        GET /api/ai/preferences/me/
        """
        preferences = self.get_object()
        serializer = self.get_serializer(preferences)
        return Response(serializer.data)
    
    @action(detail=False, methods=['patch'])
    def update_me(self, request):
        """
        Update current user's preferences.
        
        PATCH /api/ai/preferences/update_me/
        """
        preferences = self.get_object()
        serializer = self.get_serializer(preferences, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
