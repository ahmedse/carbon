# catalog/serializers.py
from rest_framework import serializers
from .models import (
    DataDomain, GlossaryTerm, Tag, AssetProfile, GovernanceEvent, GovernancePolicy,
    LineageEdge, FreshnessPolicy, Note, NoteAnchor, NoteComment, NoteReaction,
)


class DataDomainSerializer(serializers.ModelSerializer):
    class Meta:
        model = DataDomain
        fields = ['id', 'name', 'slug', 'description', 'parent', 'owner', 'created_at', 'updated_at']
        read_only_fields = ['id', 'slug', 'created_at', 'updated_at']


class GlossaryTermSerializer(serializers.ModelSerializer):
    class Meta:
        model = GlossaryTerm
        fields = ['id', 'term', 'slug', 'definition', 'domain', 'synonyms', 'steward', 'status', 'created_at', 'updated_at']
        read_only_fields = ['id', 'slug', 'created_at', 'updated_at']


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ['id', 'name', 'slug', 'color']
        read_only_fields = ['id', 'slug']


class AssetProfileSerializer(serializers.ModelSerializer):
    asset_type = serializers.SerializerMethodField()
    title = serializers.SerializerMethodField()
    tags = serializers.PrimaryKeyRelatedField(many=True, queryset=Tag.objects.all(), required=False)

    class Meta:
        model = AssetProfile
        fields = [
            'id', 'asset_type', 'title', 'data_table', 'data_field',
            'description', 'domain', 'owner', 'steward', 'classification',
            'semantic_type', 'glossary_term', 'tags',
            'quality_status', 'quality_score', 'updated_at', 'updated_by',
        ]
        read_only_fields = [
            'id', 'asset_type', 'title', 'data_table', 'data_field',
            'quality_status', 'quality_score', 'updated_at', 'updated_by',
        ]

    def get_asset_type(self, obj):
        return 'field' if obj.data_field_id else 'table'

    def get_title(self, obj):
        if obj.data_field_id:
            return f"{obj.data_field.label} ({obj.data_field.data_table.title})"
        return obj.data_table.title if obj.data_table_id else ''


class GovernanceEventSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True, allow_null=True)

    class Meta:
        model = GovernanceEvent
        fields = ['id', 'asset', 'entity_type', 'entity_id', 'action', 'before', 'after', 'user', 'username', 'timestamp']
        read_only_fields = ['id', 'timestamp']


class GovernancePolicySerializer(serializers.ModelSerializer):
    updated_by_username = serializers.CharField(source='updated_by.username', read_only=True, allow_null=True)
    
    class Meta:
        model = GovernancePolicy
        fields = [
            'id', 'policy_type', 'name', 'description', 'enabled', 
            'config', 'created_at', 'updated_at', 'updated_by', 'updated_by_username'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'updated_by', 'updated_by_username']


class LineageEdgeSerializer(serializers.ModelSerializer):
    source_table_name = serializers.CharField(source='source_table.title', read_only=True)
    target_table_name = serializers.CharField(source='target_table.title', read_only=True)
    source_field_name = serializers.CharField(source='source_field.label', read_only=True, allow_null=True)
    target_field_name = serializers.CharField(source='target_field.label', read_only=True, allow_null=True)
    created_by_username = serializers.CharField(source='created_by.username', read_only=True, allow_null=True)

    class Meta:
        model = LineageEdge
        fields = [
            'id', 'source_table', 'target_table', 'source_field', 'target_field',
            'source_table_name', 'target_table_name', 'source_field_name', 'target_field_name',
            'edge_type', 'transform_description', 'created_by', 'created_by_username', 'created_at'
        ]
        read_only_fields = ['id', 'source_table_name', 'target_table_name', 'source_field_name', 
                            'target_field_name', 'created_by', 'created_by_username', 'created_at']


class FreshnessPolicySerializer(serializers.ModelSerializer):
    table_title = serializers.CharField(source='table.title', read_only=True)
    last_data_updated_at = serializers.DateTimeField(
        source='table.last_data_updated_at', read_only=True, allow_null=True)

    class Meta:
        model = FreshnessPolicy
        fields = [
            'id', 'table', 'table_title', 'max_age_hours', 'alert_level',
            'enabled', 'last_checked_at', 'last_alerted_at', 'last_data_updated_at',
        ]
        read_only_fields = [
            'id', 'table', 'table_title', 'last_checked_at', 'last_alerted_at',
            'last_data_updated_at',
        ]


# ── Notes / Comments / Reactions (centralized annotation layer) ────────────

def _author_payload(author):
    """Compact author object; NULL author = system/background action."""
    if author is None:
        return None
    return {
        'id': author.id,
        'username': author.username,
        'full_name': author.get_full_name() or author.username,
    }


class ReactionCountsMixin:
    """Adds per-target reaction_counts + my_reaction for the requesting user.

    Requires ``self.context['request']`` and ``self.instance`` to be the model
    instance (note XOR comment).
    """

    def get_reaction_counts(self, obj):
        qs = obj.reactions.all()
        return {
            choice: qs.filter(reaction=choice).count()
            for choice, _ in NoteReaction.REACTIONS
        }

    def get_my_reaction(self, obj):
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        if not (user and user.is_authenticated):
            return None
        qs = obj.reactions.filter(user=user)
        first = qs.first()
        return first.reaction if first else None


class NoteListSerializer(serializers.ModelSerializer, ReactionCountsMixin):
    """Compact list payload for the drawer — NO comment bodies (lazy contract)."""
    author = serializers.SerializerMethodField()
    comments_count = serializers.IntegerField(read_only=True)
    reaction_counts = serializers.SerializerMethodField()
    my_reaction = serializers.SerializerMethodField()
    can_edit = serializers.SerializerMethodField()
    is_removed = serializers.SerializerMethodField()
    anchors = serializers.SerializerMethodField()

    class Meta:
        model = Note
        fields = [
            'id', 'entity_type', 'entity_id', 'anchors', 'body', 'author', 'visibility',
            'created_at', 'updated_at', 'comments_count', 'reaction_counts',
            'my_reaction', 'can_edit', 'is_removed',
        ]
        read_only_fields = ['id', 'visibility', 'created_at', 'updated_at']

    def get_author(self, obj):
        return _author_payload(obj.author)

    def get_can_edit(self, obj):
        return _can_edit_note(self.context.get('request'), obj)

    def get_is_removed(self, obj):
        return not obj.is_active

    def get_anchors(self, obj):
        """All anchors — PRIMARY (entity_type/entity_id) first, then extras."""
        primary = {'entity_type': obj.entity_type, 'entity_id': obj.entity_id}
        extras = list(obj.anchors.values('entity_type', 'entity_id'))
        return [primary, *extras]


class NoteDetailSerializer(NoteListSerializer):
    """Detail payload — same fields; comments fetched separately (lazy)."""

    class Meta(NoteListSerializer.Meta):
        fields = NoteListSerializer.Meta.fields


class NoteCommentSerializer(serializers.ModelSerializer, ReactionCountsMixin):
    author = serializers.SerializerMethodField()
    reaction_counts = serializers.SerializerMethodField()
    my_reaction = serializers.SerializerMethodField()
    can_edit = serializers.SerializerMethodField()
    is_removed = serializers.SerializerMethodField()

    class Meta:
        model = NoteComment
        fields = [
            'id', 'body', 'author', 'created_at', 'updated_at',
            'reaction_counts', 'my_reaction', 'can_edit', 'is_removed',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_author(self, obj):
        return _author_payload(obj.author)

    def get_can_edit(self, obj):
        return _can_edit_note(self.context.get('request'), obj)

    def get_is_removed(self, obj):
        return not obj.is_active


class NoteAnchorItemSerializer(serializers.Serializer):
    """One extra entity anchor: ``{entity_type, entity_id}`` (no FK)."""
    entity_type = serializers.CharField(max_length=40)
    entity_id = serializers.IntegerField(min_value=0)


class NoteCreateSerializer(serializers.ModelSerializer):
    """Create payload — entity_type + entity_id + body + optional extra anchors.

    ``anchors`` is a list of ADDITIONAL entity pairs the note should also
    surface under (e.g. the domain app). The first/primary anchor stays in
    ``entity_type``/``entity_id``. Visibility is IMPLICIT: server-derived from
    the author's scope (admin → internal, otherwise public) — never client-set.
    """

    anchors = NoteAnchorItemSerializer(many=True, required=False, allow_empty=True)

    class Meta:
        model = Note
        fields = ['entity_type', 'entity_id', 'body', 'visibility', 'anchors']
        read_only_fields = ['visibility']
        extra_kwargs = {
            'entity_type': {'required': True, 'allow_blank': False, 'max_length': 40},
            'entity_id': {'required': True},
            'body': {'required': True, 'allow_blank': False},
        }

    def create(self, validated_data):
        anchors = validated_data.pop('anchors', None) or []
        note = Note.objects.create(**validated_data)
        self._attach_anchors(note, anchors)
        return note

    @staticmethod
    def _attach_anchors(note, anchors):
        """Persist extra anchors, skipping any pair that duplicates the primary
        or another extra anchor (unique per note)."""
        seen = {(note.entity_type, note.entity_id)}
        for item in anchors:
            pair = (item['entity_type'], item['entity_id'])
            if pair in seen:
                continue
            seen.add(pair)
            NoteAnchor.objects.create(
                note=note, entity_type=item['entity_type'], entity_id=item['entity_id'],
            )


class NoteCommentCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = NoteComment
        fields = ['body']
        extra_kwargs = {'body': {'required': True, 'allow_blank': False}}


class NoteReactionToggleSerializer(serializers.Serializer):
    """Toggle a reaction on a note or comment. POST with the same reaction removes it."""
    reaction = serializers.ChoiceField(choices=[c for c, _ in NoteReaction.REACTIONS])

    def to_representation(self, instance):
        request = self.context.get('request')
        counts = {
            choice: instance.reactions.filter(reaction=choice).count()
            for choice, _ in NoteReaction.REACTIONS
        }
        user = getattr(request, 'user', None)
        my_reaction = None
        if user and user.is_authenticated:
            first = instance.reactions.filter(user=user).first()
            my_reaction = first.reaction if first else None
        return {'reaction_counts': counts, 'my_reaction': my_reaction}


def _can_edit_note(request, obj):
    """Author or global admin can edit/delete a note/comment."""
    from accounts.rbac_utils import user_has_global_role, ADMIN_ROLES
    user = getattr(request, 'user', None)
    if not (user and user.is_authenticated):
        return False
    if user.is_superuser:
        return True
    if obj.author_id and obj.author_id == user.id:
        return True
    return user_has_global_role(user, ADMIN_ROLES)
