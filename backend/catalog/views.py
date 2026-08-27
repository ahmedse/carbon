# catalog/views.py
from django.db.models import Count, Q
from django.utils.text import slugify
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import filters, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404

from accounts.permissions import ReadAnyWriteAdmin
from accounts.models import ScopedRole
from accounts.rbac_utils import user_has_global_role, ADMIN_ROLES
from core.feedback import AppFeedback
from .audit_utils import emit_governance_event
from .filters import GovernanceEventFilter
from dataschema.models import DataTable
from .models import (
    DataDomain, GlossaryTerm, Tag, AssetProfile, GovernanceEvent, GovernancePolicy,
    LineageEdge, FreshnessPolicy, Note, NoteComment, NoteReaction,
)
from .serializers import (
    DataDomainSerializer, GlossaryTermSerializer, TagSerializer,
    AssetProfileSerializer, GovernanceEventSerializer, GovernancePolicySerializer, LineageEdgeSerializer,
    FreshnessPolicySerializer, NoteListSerializer, NoteCreateSerializer,
    NoteCommentSerializer, NoteCommentCreateSerializer, NoteReactionToggleSerializer,
)
from .services import ensure_asset_profiles


class GovernanceEventPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 500


class DataDomainViewSet(viewsets.ModelViewSet):
    queryset = DataDomain.objects.all().order_by('name')
    serializer_class = DataDomainSerializer
    permission_classes = [ReadAnyWriteAdmin]
    required_write_capability = 'catalog:manage_metadata'

    def perform_create(self, serializer):
        serializer.save(slug=slugify(serializer.validated_data['name']))

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        return Response(
            {
                'detail': 'Hard delete not supported; use PATCH {"is_active": false} to archive this resource.',
                'resource': 'DataDomain',
            },
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )


class GlossaryTermViewSet(viewsets.ModelViewSet):
    queryset = GlossaryTerm.objects.all().order_by('term')
    serializer_class = GlossaryTermSerializer
    permission_classes = [ReadAnyWriteAdmin]
    required_write_capability = 'catalog:manage_metadata'

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        return Response(
            {
                'detail': 'Hard delete not supported; use PATCH {"is_active": false} to archive this resource.',
                'resource': 'GlossaryTerm',
            },
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def perform_create(self, serializer):
        instance = serializer.save(slug=slugify(serializer.validated_data['term']))
        emit_governance_event(
            entity_type='GlossaryTerm',
            entity_id=instance.id,
            action='create',
            before={},
            after={
                'term': instance.term,
                'definition': instance.definition,
                'status': instance.status,
                'steward': instance.steward_id,
                'domain': instance.domain_id,
            },
            user=self.request.user,
        )

    def perform_update(self, serializer):
        old = self.get_object()
        before = {
            'term': old.term,
            'definition': old.definition,
            'status': old.status,
            'steward': old.steward_id,
            'domain': old.domain_id,
        }
        instance = serializer.save()
        after = {
            'term': instance.term,
            'definition': instance.definition,
            'status': instance.status,
            'steward': instance.steward_id,
            'domain': instance.domain_id,
        }
        changed = {k: after[k] for k in before if before.get(k) != after.get(k)}
        if changed:
            emit_governance_event(
                entity_type='GlossaryTerm',
                entity_id=instance.id,
                action='update',
                before={k: before[k] for k in changed},
                after=changed,
                user=self.request.user,
            )

    def perform_destroy(self, instance):
        before = {'term': instance.term, 'definition': instance.definition, 'status': instance.status}
        entity_id = instance.id
        instance.delete()
        emit_governance_event(
            entity_type='GlossaryTerm',
            entity_id=entity_id,
            action='delete',
            before=before,
            after={'deleted': True},
            user=self.request.user,
        )


class TagViewSet(viewsets.ModelViewSet):
    queryset = Tag.objects.all().order_by('name')
    serializer_class = TagSerializer
    permission_classes = [ReadAnyWriteAdmin]
    required_write_capability = 'catalog:manage_metadata'

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        return Response(
            {
                'detail': 'Hard delete not supported; use PATCH {"is_active": false} to archive this resource.',
                'resource': 'Tag',
            },
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def perform_create(self, serializer):
        serializer.save(slug=slugify(serializer.validated_data['name']))


class AssetProfileViewSet(viewsets.ModelViewSet):
    serializer_class = AssetProfileSerializer
    permission_classes = [ReadAnyWriteAdmin]
    required_write_capability = 'catalog:manage_products'
    http_method_names = ['get', 'post', 'patch', 'put', 'head', 'options']  # profiles are auto-managed; no create/delete

    @extend_schema(
        description='Archive multiple asset profiles in one request.',
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'ids': {'type': 'array', 'items': {'type': 'integer'}},
                },
                'required': ['ids'],
            },
        },
        responses={200: 'Per-item success/failure summary', 400: 'Invalid request'},
    )
    @action(detail=False, methods=['post'], url_path='archive-bulk')
    def archive_bulk(self, request):
        """POST /catalog/assets/archive-bulk/ — archive multiple asset profiles at once."""
        ids = request.data.get('ids', [])
        if not isinstance(ids, list) or not ids:
            return Response({'error': 'ids must be a non-empty list'}, status=status.HTTP_400_BAD_REQUEST)

        results = {'success': [], 'failed': []}
        for asset_id in ids:
            try:
                asset = AssetProfile.objects.get(pk=asset_id)
            except AssetProfile.DoesNotExist:
                results['failed'].append({'id': asset_id, 'error': 'AssetProfile not found'})
                continue

            asset.is_active = False
            asset.save(update_fields=['is_active'])
            emit_governance_event(
                entity_type='AssetProfile',
                entity_id=asset.id,
                action='delete',
                before={'is_active': True},
                after={'is_active': False},
                user=request.user,
            )
            results['success'].append(asset.id)

        return Response(results, status=status.HTTP_200_OK)

    def get_queryset(self):
        ensure_asset_profiles()
        qs = AssetProfile.objects.select_related(
            'data_table', 'data_field', 'data_field__data_table',
            'domain', 'owner', 'steward', 'glossary_term',
        ).prefetch_related('tags')
        
        # RBAC: Scope to user's org units (superusers/staff see all)
        user = self.request.user
        if not (user.is_superuser or user.is_staff):
            org_units = list(
                ScopedRole.objects.filter(
                    user=user, is_active=True
                ).values_list('org_unit_id', flat=True).distinct()
            )
            if not org_units:
                return AssetProfile.objects.none()
            qs = qs.filter(
                Q(data_table__module__org_unit_id__in=org_units) |
                Q(data_field__data_table__module__org_unit_id__in=org_units)
            )
        
        p = self.request.query_params
        if p.get('classification'):
            qs = qs.filter(classification=p['classification'])
        if p.get('quality_status'):
            qs = qs.filter(quality_status=p['quality_status'])
        if p.get('domain'):
            qs = qs.filter(domain_id=p['domain'])
        if p.get('owner'):
            qs = qs.filter(owner_id=p['owner'])
        if p.get('tag'):
            qs = qs.filter(tags__id=p['tag'])
        if p.get('module_id'):
            mid = p['module_id']
            qs = qs.filter(Q(data_table__module_id=mid) | Q(data_field__data_table__module_id=mid))
        if p.get('data_table'):
            qs = qs.filter(data_table_id=p['data_table'])
        return qs.distinct().order_by('id')

    def perform_update(self, serializer):
        instance = self.get_object()
        before = {
            'owner': instance.owner_id,
            'steward': instance.steward_id,
            'classification': instance.classification,
            'domain': instance.domain_id,
            'glossary_term': instance.glossary_term_id,
            'quality_status': instance.quality_status,
            'quality_score': instance.quality_score,
        }
        obj = serializer.save(updated_by=self.request.user)
        after = {
            'owner': obj.owner_id,
            'steward': obj.steward_id,
            'classification': obj.classification,
            'domain': obj.domain_id,
            'glossary_term': obj.glossary_term_id,
            'quality_status': obj.quality_status,
            'quality_score': obj.quality_score,
        }
        changed = {k: after[k] for k in before if before.get(k) != after.get(k)}
        if changed:
            emit_governance_event(
                entity_type='AssetProfile',
                entity_id=obj.id,
                action='update',
                before={k: before[k] for k in changed},
                after=changed,
                user=self.request.user,
                asset_profile=obj,
            )


class GovernanceEventViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = GovernanceEvent.objects.all().order_by('-timestamp')
    serializer_class = GovernanceEventSerializer
    permission_classes = [ReadAnyWriteAdmin]
    required_write_capability = 'catalog:view_governance'
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = GovernanceEventFilter
    ordering = ['-timestamp']
    ordering_fields = ['timestamp', 'entity_type', 'action']
    pagination_class = GovernanceEventPagination


class GovernanceComplianceView(APIView):
    permission_classes = [ReadAnyWriteAdmin]
    required_write_capability = 'catalog:view_governance'

    @extend_schema(
        description='Summarize governance events for a recent time window.',
        parameters=[
            OpenApiParameter('days', type=int, description='Number of days to include', required=False),
        ],
        responses={200: 'Compliance summary of recent governance activity'},
    )
    def get(self, request):
        days = int(request.query_params.get('days', 30))
        cutoff = timezone.now() - timezone.timedelta(days=days)
        qs = GovernanceEvent.objects.filter(timestamp__gte=cutoff)
        return Response({
            'window_days': days,
            'total_events': qs.count(),
            'by_action': list(qs.values('action').annotate(count=Count('action')).order_by().values('action', 'count')),
            'by_entity_type': list(qs.values('entity_type').annotate(count=Count('entity_type')).order_by().values('entity_type', 'count')),
            'recent_events': GovernanceEventSerializer(qs.order_by('-timestamp')[:10], many=True).data,
        })


class GovernancePolicyViewSet(viewsets.ModelViewSet):
    """
    Admin-managed governance policies. Read for authenticated users,
    write for global admins only. A policy that is enabled and has been
    enforced (usage_count > 0) cannot be deleted — only disabled.
    """
    queryset = GovernancePolicy.objects.all()
    serializer_class = GovernancePolicySerializer
    permission_classes = [ReadAnyWriteAdmin]
    required_write_capability = 'catalog:manage_policies'

    def perform_create(self, serializer):
        serializer.save(updated_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()

        # Cannot delete an active policy that is actively enforcing rules.
        if instance.enabled and instance.usage_count > 0:
            raise AppFeedback(
                code="policy_in_use",
                title="Cannot delete an active policy",
                detail=f"'{instance.name}' is enabled and has been enforced {instance.usage_count} time(s).",
                reasons=[
                    "This policy is currently active.",
                    f"It has already blocked {instance.usage_count} action(s), so it is in use.",
                ],
                remediation=[
                    "Disable the policy first if you no longer want it enforced.",
                    "Once disabled, it can be safely deleted.",
                ],
                context={"policy_id": instance.id, "usage_count": instance.usage_count},
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        return super().destroy(request, *args, **kwargs)


class LineageEdgeViewSet(viewsets.ModelViewSet):
    """
    CRUD operations on lineage edges.
    - GET /lineage/ — list all edges (paginated; filter by source/target)
    - POST /lineage/ — create edge (admin only)
    - DELETE /lineage/{id}/ — delete edge (admin only)
    """
    queryset = LineageEdge.objects.all().select_related(
        'source_table__module', 'target_table__module',
        'source_field', 'target_field', 'created_by'
    )
    serializer_class = LineageEdgeSerializer
    permission_classes = [ReadAnyWriteAdmin]
    required_write_capability = 'catalog:manage_metadata'
    http_method_names = ['get', 'post', 'delete', 'head', 'options']

    def get_queryset(self):
        qs = super().get_queryset()
        source_id = self.request.query_params.get('source')
        target_id = self.request.query_params.get('target')
        if source_id:
            qs = qs.filter(source_table_id=source_id)
        if target_id:
            qs = qs.filter(target_table_id=target_id)
        return qs

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user if self.request.user.is_authenticated else None)


class TableLineageView(APIView):
    """
    GET /tables/{table_id}/lineage/?direction=upstream|downstream|both
    Returns upstream and/or downstream lineage edges for a given table.
    """
    permission_classes = [ReadAnyWriteAdmin]

    def get(self, request, table_id):
        from .services import get_lineage
        direction = request.query_params.get('direction', 'both')
        if direction not in ('upstream', 'downstream', 'both'):
            return Response(
                {'error': 'direction must be one of: upstream, downstream, both'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        result = get_lineage(table_id, direction=direction)
        
        # Serialize edges
        data = {}
        if 'upstream' in result:
            data['upstream'] = LineageEdgeSerializer(result['upstream'], many=True).data
        if 'downstream' in result:
            data['downstream'] = LineageEdgeSerializer(result['downstream'], many=True).data
        
        return Response(data)


class TableImpactView(APIView):
    """
    GET /tables/{table_id}/impact/?depth=5
    Returns BFS impact analysis: which tables are affected by changes to this table.
    """
    permission_classes = [ReadAnyWriteAdmin]

    def get(self, request, table_id):
        from .services import get_impact
        depth = request.query_params.get('depth', 5)
        try:
            depth = int(depth)
        except ValueError:
            return Response(
                {'error': 'depth must be an integer'},
                status=status.HTTP_400_BAD_REQUEST
            )
        depth = max(1, min(depth, 10))  # cap at 10
        
        result = get_impact(table_id, depth=depth)
        return Response(result)


class FreshnessPolicyView(APIView):
    """
    GET/POST/DELETE /catalog/tables/{table_id}/freshness/

    Manage the FreshnessPolicy for a single DataTable. GET returns the policy
    plus the table's ``last_data_updated_at``; 404 when no policy exists.
    """
    permission_classes = [ReadAnyWriteAdmin]
    required_write_capability = 'catalog:manage_policies'

    def get(self, request, table_id):
        table = get_object_or_404(DataTable, pk=table_id)
        policy = get_object_or_404(FreshnessPolicy, table=table)
        return Response(FreshnessPolicySerializer(policy).data)

    def post(self, request, table_id):
        table = get_object_or_404(DataTable, pk=table_id)
        existing = FreshnessPolicy.objects.filter(table=table).first()
        serializer = FreshnessPolicySerializer(
            existing, data=request.data, partial=existing is not None)
        serializer.is_valid(raise_exception=True)
        serializer.save(table=table)
        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED if existing is None else status.HTTP_200_OK,
        )

    def delete(self, request, table_id):
        table = get_object_or_404(DataTable, pk=table_id)
        policy = get_object_or_404(FreshnessPolicy, table=table)
        policy.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Notes / Comments / Reactions (centralized annotation layer) ────────────
# Permission model (Jira/Collibra pattern):
#   • Any authenticated user: read (public + their own internal), create notes/comments,
#     toggle reactions on anything they can see.
#   • Author or global admin: edit / soft-delete notes and comments.
#   • Internal visibility: author + admins only.

class NotesPermission(permissions.BasePermission):
    """Authenticated read & create; edit/delete author-or-admin (object-level)."""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        # Reactions target any visible note/comment — not author-scoped.
        if getattr(view, 'action', None) in ('reactions',):
            return True
        if request.method in permissions.SAFE_METHODS:
            return True
        user = request.user
        if user.is_superuser:
            return True
        if getattr(obj, 'author_id', None) and obj.author_id == user.id:
            return True
        return user_has_global_role(user, ADMIN_ROLES)


class NotesPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


def _visible_notes(user):
    """Active public notes + internal notes authored by user (or all for admins)."""
    if user.is_superuser or user_has_global_role(user, ADMIN_ROLES):
        return Note.objects.filter(is_active=True)
    return Note.objects.filter(
        Q(visibility='public') | Q(author=user), is_active=True
    )


class NoteViewSet(viewsets.ModelViewSet):
    """Polymorphic notes on any entity. Lazy contract: list has counts, no comment bodies."""
    permission_classes = [NotesPermission]
    pagination_class = NotesPagination
    http_method_names = ['get', 'post', 'patch', 'delete']

    def get_queryset(self):
        qs = _visible_notes(self.request.user)
        qs = qs.annotate(
            comments_count=Count('comments', filter=Q(comments__is_active=True))
        ).order_by('-created_at', '-id')
        # Multi-anchor filter: ?anchor=et:ei&anchor=et:ei  → notes under ANY.
        anchors = self.request.query_params.getlist('anchor')
        if anchors:
            q = Q()
            for raw in anchors:
                try:
                    et, ei = raw.split(':', 1)
                    ei = int(ei)
                except (ValueError, TypeError):
                    continue
                q |= Q(entity_type=et, entity_id=ei) | Q(anchors__entity_type=et, anchors__entity_id=ei)
            if q:
                return qs.filter(q).distinct()
            return qs
        entity_type = self.request.query_params.get('entity_type')
        entity_id = self.request.query_params.get('entity_id')
        if entity_type and entity_id is not None:
            # Pair filter — must match BOTH, against primary OR any anchor.
            try:
                ei = int(entity_id)
            except (TypeError, ValueError):
                return qs.none()
            return qs.filter(
                Q(entity_type=entity_type, entity_id=ei)
                | Q(anchors__entity_type=entity_type, anchors__entity_id=ei)
            ).distinct()
        if entity_type:
            # Entity-type-only filter (no id): primary OR any anchor.
            return qs.filter(
                Q(entity_type=entity_type) | Q(anchors__entity_type=entity_type)
            ).distinct()
        if entity_id is not None:
            try:
                ei = int(entity_id)
            except (TypeError, ValueError):
                return qs.none()
            return qs.filter(
                Q(entity_id=ei) | Q(anchors__entity_id=ei)
            ).distinct()
        return qs

    def get_serializer_class(self):
        if self.action == 'create':
            return NoteCreateSerializer
        return NoteListSerializer

    def create(self, request, *args, **kwargs):
        """Create then respond with the full list payload (author, counts…)."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        instance = Note.objects.annotate(
            comments_count=Count('comments', filter=Q(comments__is_active=True))
        ).get(pk=serializer.instance.pk)
        out = NoteListSerializer(instance, context=self.get_serializer_context()).data
        headers = self.get_success_headers(out)
        return Response(out, status=status.HTTP_201_CREATED, headers=headers)

    def perform_create(self, serializer):
        # Visibility is IMPLICIT from the author's scope: admins → internal,
        # everyone else → public. Client-supplied visibility is ignored.
        is_admin = self.request.user.is_superuser or user_has_global_role(self.request.user, ADMIN_ROLES)
        note = serializer.save(
            author=self.request.user,
            visibility='internal' if is_admin else 'public',
        )
        anchors = [{'entity_type': note.entity_type, 'entity_id': note.entity_id}]
        anchors += list(note.anchors.values('entity_type', 'entity_id'))
        emit_governance_event(
            entity_type='note', entity_id=note.id, action='create',
            before={},
            after={'body': note.body, 'visibility': note.visibility, 'anchors': anchors},
            user=self.request.user,
        )

    def perform_update(self, serializer):
        old = self.get_object()
        before = {'body': old.body, 'visibility': old.visibility}
        # Entity identity is immutable — never changeable via PATCH.
        serializer.validated_data.pop('entity_type', None)
        serializer.validated_data.pop('entity_id', None)
        note = serializer.save()
        after = {'body': note.body, 'visibility': note.visibility}
        changed = {k: after[k] for k in before if before.get(k) != after.get(k)}
        if changed:
            emit_governance_event(
                entity_type='note', entity_id=note.id, action='update',
                before={k: before[k] for k in changed}, after=changed,
                user=self.request.user,
            )

    def destroy(self, request, *args, **kwargs):
        note = self.get_object()
        before = {'body': note.body, 'visibility': note.visibility,
                  'entity_type': note.entity_type, 'entity_id': note.entity_id}
        note.is_active = False
        note.save(update_fields=['is_active'])
        emit_governance_event(
            entity_type='note', entity_id=note.id, action='delete',
            before=before, after={'deleted': True}, user=request.user,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post'], url_path='reactions')
    def reactions(self, request, pk=None):
        note = self.get_object()
        serializer = NoteReactionToggleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reaction = serializer.validated_data['reaction']
        existing = NoteReaction.objects.filter(
            user=request.user, note=note, reaction=reaction).first()
        if existing:
            existing.delete()
        else:
            NoteReaction.objects.create(user=request.user, note=note, reaction=reaction)
        return Response(_reaction_payload(note, request.user))


class NoteCommentViewSet(viewsets.ModelViewSet):
    """1-level comments on a note — lazy endpoint per note id."""
    permission_classes = [NotesPermission]
    pagination_class = NotesPagination
    http_method_names = ['get', 'post', 'patch', 'delete']

    def get_queryset(self):
        note = get_object_or_404(_visible_notes(self.request.user), pk=self.kwargs['note_id'])
        return note.comments.all()

    def get_serializer_class(self):
        if self.action == 'create':
            return NoteCommentCreateSerializer
        return NoteCommentSerializer

    def create(self, request, *args, **kwargs):
        """Create then respond with the full comment payload (author, counts…)."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        comment = NoteComment.objects.get(pk=serializer.instance.pk)
        out = NoteCommentSerializer(comment, context=self.get_serializer_context()).data
        headers = self.get_success_headers(out)
        return Response(out, status=status.HTTP_201_CREATED, headers=headers)

    def perform_create(self, serializer):
        note = get_object_or_404(_visible_notes(self.request.user), pk=self.kwargs['note_id'])
        comment = serializer.save(note=note, author=self.request.user)
        emit_governance_event(
            entity_type='note_comment', entity_id=comment.id, action='create',
            before={}, after={'body': comment.body, 'note': note.id},
            user=self.request.user,
        )

    def perform_update(self, serializer):
        old = self.get_object()
        before = {'body': old.body}
        comment = serializer.save()
        after = {'body': comment.body}
        changed = {k: after[k] for k in before if before.get(k) != after.get(k)}
        if changed:
            emit_governance_event(
                entity_type='note_comment', entity_id=comment.id, action='update',
                before={k: before[k] for k in changed}, after=changed,
                user=self.request.user,
            )

    def destroy(self, request, *args, **kwargs):
        comment = self.get_object()
        before = {'body': comment.body, 'note': comment.note_id}
        comment.is_active = False
        comment.save(update_fields=['is_active'])
        emit_governance_event(
            entity_type='note_comment', entity_id=comment.id, action='delete',
            before=before, after={'deleted': True}, user=request.user,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post'], url_path='reactions')
    def reactions(self, request, note_id=None, pk=None):
        comment = self.get_object()
        serializer = NoteReactionToggleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reaction = serializer.validated_data['reaction']
        existing = NoteReaction.objects.filter(
            user=request.user, comment=comment, reaction=reaction).first()
        if existing:
            existing.delete()
        else:
            NoteReaction.objects.create(user=request.user, comment=comment, reaction=reaction)
        return Response(_reaction_payload(comment, request.user))


def _reaction_payload(obj, user):
    """Reaction toggle response — counts + the caller's current reaction."""
    counts = {
        choice: obj.reactions.filter(reaction=choice).count()
        for choice, _ in NoteReaction.REACTIONS
    }
    my_reaction = None
    if user and user.is_authenticated:
        first = obj.reactions.filter(user=user).first()
        my_reaction = first.reaction if first else None
    return {'reaction_counts': counts, 'my_reaction': my_reaction}
