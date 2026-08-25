"""
AI Maturity & Expertise Metrics — visibility into Pulse's learning progress.

GET  /carbon-api/ai/pulse/maturity/  — expertise scores, learning velocity, domain coverage

This surface answers: "How good is Pulse? Is it learning?" by aggregating
scoped rows from the learning, feedback, knowledge, and skill models into
domain-expertise scores, skill acquisition curves, and knowledge-depth metrics.

User-facing panel: "AI Expertise Dashboard" (admin console).
"""
import logging
from datetime import datetime, timedelta, timezone

from django.db.models import Avg, Count, Q, Sum
from django.utils import timezone as dj_timezone

from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.ai_scoping import scope_ai_queryset
from accounts.permissions import AdminOrSuperuserOnly

from ai.models.core import (
    Feedback,
    KnowledgeEntity,
    Skill,
    Run,
    RunStep,
)
from ai.models.knowledge_graph import KnowledgeNode, KnowledgeEdge
from ai.models.workspace import AIConversation, AIMessage

logger = logging.getLogger("carbon.ai.maturity")


class AIMaturityView(APIView):
    """GET maturity/ — AI expertise & learning progress metrics.
    
    Returns a dashboard payload showing:
    - Overall maturity score (0-100)
    - Skills learned (draft → promoted progression)
    - Knowledge depth (entities, nodes, edges)
    - Success rate (feedback analysis)
    - Learning velocity (30-day trends)
    - Domain expertise breakdown (per app_identifier)
    """

    permission_classes = [AdminOrSuperuserOnly]
    required_capability = "ai:view_console"

    def get(self, request):
        user = request.user
        now = dj_timezone.now()
        thirty_days_ago = now - timedelta(days=30)

        # ── Skills Maturity ─────────────────────────────────────────────────
        skills_qs = scope_ai_queryset(Skill.objects, user)
        total_skills = skills_qs.count()
        promoted_skills = skills_qs.filter(status="instance_promoted").count()
        draft_skills = skills_qs.filter(status="draft").count()
        
        # Last 30 days skill growth
        skills_last_30d = skills_qs.filter(created_at__gte=thirty_days_ago).count()
        promoted_last_30d = skills_qs.filter(
            status="instance_promoted",
            promoted_at__gte=thirty_days_ago
        ).count()

        # ── Knowledge Depth ─────────────────────────────────────────────────
        entities_qs = scope_ai_queryset(KnowledgeEntity.objects, user)
        nodes_qs = scope_ai_queryset(KnowledgeNode.objects, user)
        edges_qs = scope_ai_queryset(KnowledgeEdge.objects, user)

        total_entities = entities_qs.count()
        total_nodes = nodes_qs.count()
        total_edges = edges_qs.count()

        # Last 30 days growth (KnowledgeEntity uses last_introspected, not created_at)
        entities_last_30d = entities_qs.filter(last_introspected__gte=thirty_days_ago).count()
        nodes_last_30d = nodes_qs.filter(created_at__gte=thirty_days_ago).count()

        # ── Task Success Rate ───────────────────────────────────────────────
        feedback_qs = scope_ai_queryset(Feedback.objects, user)
        total_feedback = feedback_qs.count()
        # rating > 0 = positive, rating <= 0 = negative
        positive_feedback = feedback_qs.filter(rating__gt=0).count()
        negative_feedback = feedback_qs.filter(rating__lte=0).count()

        success_rate = (
            round((positive_feedback / total_feedback) * 100, 1)
            if total_feedback > 0 else 0
        )

        # ── Conversation Complexity ─────────────────────────────────────────
        conversations_qs = scope_ai_queryset(AIConversation.objects, user)
        # AIMessage doesn't have app_identifier - scope through conversation
        messages_qs = AIMessage.objects.filter(conversation__in=conversations_qs)

        total_conversations = conversations_qs.count()
        total_messages = messages_qs.count()
        avg_turns = (
            round(total_messages / total_conversations, 1)
            if total_conversations > 0 else 0
        )

        # Plans (multi-step agent tasks)
        runs_qs = scope_ai_queryset(Run.objects, user)
        total_plans = runs_qs.count()
        completed_plans = runs_qs.filter(status="completed").count()
        
        steps_qs = scope_ai_queryset(RunStep.objects, user)
        total_steps = steps_qs.count()
        avg_steps_per_plan = (
            round(total_steps / total_plans, 1)
            if total_plans > 0 else 0
        )

        # ── Domain Expertise Breakdown ──────────────────────────────────────
        # Group conversations by app_identifier
        domain_breakdown = list(
            conversations_qs.exclude(app_identifier__isnull=True)
            .exclude(app_identifier="")
            .values("app_identifier")
            .annotate(conversations=Count("id"))
            .order_by("-conversations")[:10]
        )

        # Add success rates per domain
        for domain in domain_breakdown:
            app_id = domain["app_identifier"]
            domain_messages = messages_qs.filter(conversation__app_identifier=app_id)
            domain_message_ids = list(domain_messages.values_list('id', flat=True))
            domain_feedback = feedback_qs.filter(message_id__in=domain_message_ids)
            
            domain_total = domain_feedback.count()
            # rating > 0 = positive
            domain_positive = domain_feedback.filter(rating__gt=0).count()
            
            domain["success_rate"] = (
                round((domain_positive / domain_total) * 100, 1)
                if domain_total > 0 else 0
            )
            domain["feedback_count"] = domain_total

        # ── Overall Maturity Score ──────────────────────────────────────────
        # Weighted composite score (0-100)
        # - 30%: Skills maturity (promoted ratio)
        # - 25%: Knowledge depth (logarithmic scale)
        # - 25%: Success rate
        # - 20%: Domain coverage (unique apps)
        
        skills_score = (
            (promoted_skills / total_skills) * 30
            if total_skills > 0 else 0
        )
        
        # Log scale for knowledge: score saturates at 1000 entities, 5000 nodes
        import math
        knowledge_score = min(
            (math.log10(max(total_entities, 1)) / math.log10(1000)) * 12.5 +
            (math.log10(max(total_nodes, 1)) / math.log10(5000)) * 12.5,
            25
        )
        
        success_score = (success_rate / 100) * 25
        
        domain_count = len(domain_breakdown)
        domain_score = min((domain_count / 5) * 20, 20)  # Saturates at 5 domains
        
        maturity_score = round(
            skills_score + knowledge_score + success_score + domain_score,
            1
        )

        # ── Learning Velocity (30-day trend) ────────────────────────────────
        learning_velocity = {
            "skills_acquired": skills_last_30d,
            "skills_promoted": promoted_last_30d,
            "entities_added": entities_last_30d,
            "nodes_added": nodes_last_30d,
        }

        # ── Expertise Level Label ───────────────────────────────────────────
        if maturity_score < 20:
            expertise_level = "Novice"
            expertise_description = "Learning basic patterns and procedures"
        elif maturity_score < 40:
            expertise_level = "Developing"
            expertise_description = "Building domain knowledge and skills"
        elif maturity_score < 60:
            expertise_level = "Competent"
            expertise_description = "Handles routine tasks effectively"
        elif maturity_score < 80:
            expertise_level = "Proficient"
            expertise_description = "Deep domain expertise, reliable execution"
        else:
            expertise_level = "Expert"
            expertise_description = "Mastery across domains, proactive insights"

        return Response({
            "maturity_score": maturity_score,
            "expertise_level": expertise_level,
            "expertise_description": expertise_description,
            "skills": {
                "total": total_skills,
                "promoted": promoted_skills,
                "draft": draft_skills,
                "promotion_rate": round((promoted_skills / total_skills) * 100, 1) if total_skills > 0 else 0,
            },
            "knowledge": {
                "entities": total_entities,
                "nodes": total_nodes,
                "edges": total_edges,
                "graph_density": round(total_edges / total_nodes, 2) if total_nodes > 0 else 0,
            },
            "performance": {
                "success_rate": success_rate,
                "total_feedback": total_feedback,
                "positive": positive_feedback,
                "negative": negative_feedback,
            },
            "complexity": {
                "total_conversations": total_conversations,
                "total_messages": total_messages,
                "avg_turns_per_conversation": avg_turns,
                "total_plans": total_plans,
                "completed_plans": completed_plans,
                "avg_steps_per_plan": avg_steps_per_plan,
            },
            "learning_velocity": learning_velocity,
            "domain_expertise": domain_breakdown,
        })
