"""
AI Copilot API Views
"""

import json
import os
import logging
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
from .services import get_poe_client, get_conversation_memory, get_rag_engine, get_context_engine
from dataschema.models import DataTable, DataField, DataRow

logger = logging.getLogger('ai_copilot')


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
        logger.info(f"Chat request received: {request.data}")
        serializer = ChatRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = request.user
        message = serializer.validated_data['message']
        project_id = serializer.validated_data.get('project_id')
        stream = serializer.validated_data.get('stream', False)
        logger.info(f"Processing message from user {user.username}: '{message}' (stream={stream})")
        
        try:
            if stream:
                response = StreamingHttpResponse(
                    self._stream_response_sync(user, message, project_id),
                    content_type='text/event-stream'
                )
                response['Cache-Control'] = 'no-cache'
                response['X-Accel-Buffering'] = 'no'
                return response

            response_data = async_to_sync(self._process_message)(user, message, project_id)
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
        
        # Get real database context
        context_engine = get_context_engine()
        db_context = await context_engine.get_project_context(user, project_id)
        db_context_text = context_engine.format_context_for_prompt(db_context)
        
        # Get relevant context from RAG
        rag_engine = get_rag_engine()
        rag_results = await rag_engine.retrieve(message, top_k=3)
        rag_context = self._format_rag_context(rag_results)
        sources = self._format_rag_sources(rag_results)
        
        # Combined context
        full_context = f"{db_context_text}\n\n{rag_context}"

        # User preferences
        preferences, _ = await sync_to_async(UserAIPreference.objects.get_or_create)(
            user=user
        )
        
        # Build system prompt
        system_prompt = self._build_system_prompt(user, project_id, full_context, preferences)
        
        # Get conversation history
        history = await memory.get_history(user.id, project_id, last_n=10)
        
        # Get POE client
        poe_client = get_poe_client()
        logger.info(f"Calling Poe API with {len(history)} history messages")
        
        # Convert assistant role to bot for Poe API
        poe_history = [
            {"role": "bot" if msg["role"] == "assistant" else msg["role"], "content": msg["content"]}
            for msg in history
        ]
        
        # Get response
        response_text = await poe_client.chat(
            messages=[
                {"role": "system", "content": system_prompt},
                *poe_history,
                {"role": "user", "content": message}
            ]
        )
        logger.info(f"Poe API response received: {len(response_text)} chars")

        if not response_text.strip():
            response_text = "I'm here to help. Ask me about your emissions data, scopes, or reporting requirements."

        # Token estimates
        input_text = "\n".join([system_prompt] + [h.get("content", "") for h in history] + [message])
        input_tokens = poe_client.count_tokens(input_text)
        output_tokens = poe_client.count_tokens(response_text)
        
        # Save to memory
        await memory.add_message(user.id, "user", message, project_id)
        await memory.add_message(user.id, "assistant", response_text, project_id)
        
        # Save to database (sync operation)
        await sync_to_async(ConversationMessage.objects.create)(
            user=user,
            project_id=project_id,
            role="user",
            content=message,
            token_count=poe_client.count_tokens(message),
            metadata={
                "input_tokens": input_tokens,
                "output_tokens": output_tokens
            }
        )
        
        assistant_msg = await sync_to_async(ConversationMessage.objects.create)(
            user=user,
            project_id=project_id,
            role="assistant",
            content=response_text,
            token_count=output_tokens,
            metadata={
                "input_tokens": input_tokens,
                "output_tokens": output_tokens
            }
        )
        
        # Format response
        response_data = {
            'response': response_text,
            'conversation_id': assistant_msg.id,
            'tokens_used': output_tokens,
            'cost_estimate': poe_client.estimate_cost(input_tokens, output_tokens),
            'created_at': assistant_msg.created_at,
            'sources': sources
        }

        if self._debug_enabled():
            response_data['debug'] = self._build_debug_payload(
                model=poe_client.model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                sources=sources
            )
        
        return response_data
    
    def _stream_response_sync(self, user, message, project_id):
        """Sync streaming generator for server-sent events (WSGI-safe)."""
        try:
            logger.info(f"Stream: Starting for user {user.username}")
            memory = get_conversation_memory()
            
            # Get real database context
            context_engine = get_context_engine()
            db_context = async_to_sync(context_engine.get_project_context)(user, project_id)
            db_context_text = context_engine.format_context_for_prompt(db_context)
            
            # Get RAG context
            rag_engine = get_rag_engine()
            rag_results = async_to_sync(rag_engine.retrieve)(message, top_k=3)
            rag_context = self._format_rag_context(rag_results)
            sources = self._format_rag_sources(rag_results)
            logger.info(f"Stream: RAG retrieved {len(sources)} sources")
            
            # Combined context
            full_context = f"{db_context_text}\n\n{rag_context}"

            preferences, _ = UserAIPreference.objects.get_or_create(user=user)
            system_prompt = self._build_system_prompt(user, project_id, full_context, preferences)

            history = async_to_sync(memory.get_history)(user.id, project_id, last_n=10)
            poe_client = get_poe_client()
            logger.info(f"Stream: Calling Poe API with {len(history)} history messages")

            # Convert assistant role to bot for Poe API
            poe_history = [
                {"role": "bot" if msg["role"] == "assistant" else msg["role"], "content": msg["content"]}
                for msg in history
            ]

            input_text = "\n".join([system_prompt] + [h.get("content", "") for h in history] + [message])
            input_tokens = poe_client.count_tokens(input_text)

            response_text = async_to_sync(poe_client.chat)(
                messages=[
                    {"role": "system", "content": system_prompt},
                    *poe_history,
                    {"role": "user", "content": message}
                ]
            )
            logger.info(f"Stream: Poe API returned {len(response_text)} chars")

            if not response_text.strip():
                response_text = "I'm here to help. Ask me about your emissions data, scopes, or reporting requirements."

            for chunk in self._chunk_text(response_text, chunk_size=120):
                yield f"data: {json.dumps({'chunk': chunk})}\n\n"

            async_to_sync(memory.add_message)(user.id, "user", message, project_id)
            async_to_sync(memory.add_message)(user.id, "assistant", response_text, project_id)

            output_tokens = poe_client.count_tokens(response_text)

            ConversationMessage.objects.create(
                user=user,
                project_id=project_id,
                role="user",
                content=message,
                token_count=poe_client.count_tokens(message),
                metadata={
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens
                }
            )

            assistant_msg = ConversationMessage.objects.create(
                user=user,
                project_id=project_id,
                role="assistant",
                content=response_text,
                token_count=output_tokens,
                metadata={
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens
                }
            )

            final_payload = {
                'done': True,
                'conversation_id': assistant_msg.id,
                'tokens_used': output_tokens,
                'cost_estimate': poe_client.estimate_cost(input_tokens, output_tokens),
                'created_at': assistant_msg.created_at.isoformat(),
                'sources': sources
            }

            if self._debug_enabled():
                final_payload['debug'] = self._build_debug_payload(
                    model=poe_client.model,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    sources=sources
                )

            yield f"data: {json.dumps(final_payload)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
    
    def _build_system_prompt(self, user, project_id, context, preferences):
        """Build system prompt with user context, preferences, and RAG knowledge."""
        detail_level = getattr(preferences, 'response_detail_level', 'balanced')
        detail_instructions = {
            'concise': 'Provide short, direct answers with minimal explanation.',
            'balanced': 'Provide clear answers with helpful context and concise reasoning.',
            'detailed': 'Provide comprehensive answers with examples and practical guidance.'
        }.get(detail_level, 'Provide clear answers with helpful context and concise reasoning.')

        base_prompt = f"""You are Carbon Intelligence, an AI assistant specialized in carbon emissions management and GHG Protocol compliance.

User: {user.get_full_name() or user.email}
Role: Help analyze carbon data, provide insights, and guide on emissions reduction strategies.
Response detail level: {detail_level}

Knowledge Base Context:
{context}

Guidelines:
- Provide accurate, actionable advice based on GHG Protocol standards
- Reference specific emission factors and calculation methods when relevant
- Suggest data quality improvements when appropriate
- Be concise but thorough in explanations
- If unsure, acknowledge limitations and suggest consulting official documentation
{detail_instructions}
"""
        return base_prompt

    def _chunk_text(self, text, chunk_size=120):
        """Split text into chunks for pseudo-streaming."""
        for i in range(0, len(text), chunk_size):
            yield text[i:i + chunk_size]

    def _debug_enabled(self) -> bool:
        return os.getenv('AI_DEBUG', 'false').lower() in ('1', 'true', 'yes')

    def _build_debug_payload(self, model, input_tokens, output_tokens, sources):
        return {
            'model': model,
            'input_tokens': input_tokens,
            'output_tokens': output_tokens,
            'sources_count': len(sources)
        }

    def _format_rag_context(self, results, max_tokens=1500):
        """Format RAG results for prompt context."""
        if not results:
            return "No relevant context found in knowledge base."

        context_parts = []
        total_chars = 0
        max_chars = max_tokens * 4

        for i, result in enumerate(results, 1):
            text = result.get("text", "")
            source = result.get("metadata", {}).get("source", "Unknown")
            snippet = f"[Source {i}: {source}]\n{text}\n"
            if total_chars + len(snippet) > max_chars:
                break
            context_parts.append(snippet)
            total_chars += len(snippet)

        return "\n".join(context_parts)

    def _format_rag_sources(self, results):
        """Format RAG results for client-side citations."""
        sources = []
        for result in results or []:
            text = result.get("text", "")
            meta = result.get("metadata", {}) or {}
            sources.append({
                "source": meta.get("source", "Unknown"),
                "category": meta.get("category", "unknown"),
                "distance": result.get("distance", 0.0),
                "snippet": text[:240]
            })
        return sources
    
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

    @action(detail=True, methods=['post'])
    def react(self, request, pk=None):
        """
        Persist reaction on a message.

        POST /api/ai/chat/{id}/react/
        Body: {"reaction": "up"|"down"|null}
        """
        reaction = request.data.get('reaction')
        if reaction not in ('up', 'down', None):
            return Response({'error': 'Invalid reaction'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            message = ConversationMessage.objects.get(id=pk, user=request.user)
        except ConversationMessage.DoesNotExist:
            return Response({'error': 'Message not found'}, status=status.HTTP_404_NOT_FOUND)

        metadata = message.metadata or {}
        metadata['reaction'] = reaction
        message.metadata = metadata
        message.save(update_fields=['metadata'])

        return Response({'success': True, 'reaction': reaction})


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
            queryset = queryset.filter(type=insight_type)
        
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


class QAViewSet(viewsets.ViewSet):
    """
    Lightweight data quality checks for AI quick actions.
    """
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['post'])
    def run(self, request):
        """
        Run basic QA to detect missing required fields.

        POST /api/ai/qa/run/
        Body: {"project_id": int}
        """
        project_id = request.data.get('project_id')
        if not project_id:
            return Response({'error': 'project_id is required'}, status=status.HTTP_400_BAD_REQUEST)

        tables = DataTable.objects.filter(module__project_id=project_id, is_archived=False)

        results = []
        total_missing_rows = 0

        for table in tables:
            required_fields = DataField.objects.filter(
                data_table=table,
                required=True,
                is_active=True,
                is_archived=False
            ).values_list('name', flat=True)

            if not required_fields:
                continue

            rows = DataRow.objects.filter(data_table=table, is_archived=False)
            missing_rows = 0
            missing_fields_set = set()

            for row in rows:
                values = row.values or {}
                for field_name in required_fields:
                    if values.get(field_name) in (None, '', []):
                        missing_rows += 1
                        missing_fields_set.add(field_name)
                        break

            if missing_rows > 0:
                total_missing_rows += missing_rows
                results.append({
                    'table_id': table.id,
                    'table_title': table.title,
                    'module_id': table.module_id,
                    'module_name': table.module.name,
                    'missing_required_rows': missing_rows,
                    'total_rows': rows.count(),
                    'missing_fields': sorted(list(missing_fields_set)),
                    'action_url': f"/dataschema/entry/{table.module_id}/{table.id}"
                })

        results.sort(key=lambda r: r['missing_required_rows'], reverse=True)

        return Response({
            'project_id': project_id,
            'tables_with_issues': len(results),
            'total_missing_rows': total_missing_rows,
            'tables': results
        })
