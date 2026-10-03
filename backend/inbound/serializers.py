from rest_framework import serializers

from .models import InboundBatch, InboundCartridge, InboundCommitRun, InboundTemplate


class InboundBatchSerializer(serializers.ModelSerializer):
    prepared_by_username = serializers.CharField(
        source='prepared_by.username', read_only=True, default=None,
    )
    committed_by_username = serializers.CharField(
        source='committed_by.username', read_only=True, default=None,
    )
    target_label = serializers.SerializerMethodField()
    reject_count = serializers.SerializerMethodField()

    class Meta:
        model = InboundBatch
        fields = [
            'id', 'kind', 'target_key', 'target_label', 'status',
            'original_filename', 'sha256', 'encoding', 'delimiter',
            'headers', 'sample', 'row_count', 'mapping', 'smoke',
            'reject_count',
            'prepared_by', 'prepared_by_username',
            'committed_by', 'committed_by_username',
            'prepared_at', 'committed_at', 'created_at', 'updated_at',
        ]
        read_only_fields = fields

    def get_target_label(self, obj):
        from . import registry
        try:
            return registry.get(obj.target_key)['label']
        except KeyError:
            return obj.target_key

    def get_reject_count(self, obj):
        smoke = obj.smoke or {}
        return smoke.get('reject')


class InboundCommitRunSerializer(serializers.ModelSerializer):
    """Durable commit-run record for the People Import progress surface.

    Includes the run's own fields plus the SoD identities (who prepared the
    batch and who committed it), so the client can render "Committing as …"
    and "Prepared by … · committed by …" from one payload.
    """

    requested_by_username = serializers.CharField(
        source='requested_by.username', read_only=True, default=None,
    )
    prepared_by_username = serializers.SerializerMethodField()
    committed_by_username = serializers.SerializerMethodField()
    target_key = serializers.CharField(source='batch.target_key', read_only=True)

    class Meta:
        model = InboundCommitRun
        fields = [
            'id', 'batch', 'target_key', 'status', 'progress', 'log',
            'written', 'reconcile', 'error',
            'requested_by', 'requested_by_username',
            'prepared_by_username', 'committed_by_username',
            'started_at', 'finished_at', 'created_at', 'updated_at',
        ]
        read_only_fields = fields

    def get_prepared_by_username(self, obj):
        return getattr(obj.batch.prepared_by, 'username', None)

    def get_committed_by_username(self, obj):
        return getattr(obj.batch.committed_by, 'username', None)


class InboundCartridgeSerializer(serializers.ModelSerializer):
    bound = serializers.SerializerMethodField()
    batch_count = serializers.SerializerMethodField()
    last_status = serializers.SerializerMethodField()
    recent_batches = serializers.SerializerMethodField()

    class Meta:
        model = InboundCartridge
        fields = (
            'id', 'key', 'kind', 'label', 'label_ar', 'owner_app', 'fields',
            'enabled', 'bound', 'batch_count', 'last_status', 'recent_batches',
            'created_at', 'updated_at',
        )
        read_only_fields = (
            'id', 'owner_app', 'bound', 'batch_count', 'last_status', 'recent_batches',
            'created_at', 'updated_at',
        )

    def get_bound(self, obj):
        return bool(self.context.get('bound', {}).get(obj.key))

    def get_batch_count(self, obj):
        return int(self.context.get('batch_counts', {}).get(obj.key) or 0)

    def get_last_status(self, obj):
        return self.context.get('last_status', {}).get(obj.key) or ''

    def get_recent_batches(self, obj):
        """Retrieve only. The list stays a count plus last status."""
        view = self.context.get('view')
        if getattr(view, 'action', None) != 'retrieve':
            return []
        rows = InboundBatch.objects.filter(target_key=obj.key).order_by('-id')[:10]
        return [
            {
                'id': row.id,
                'kind': row.kind,
                'status': row.status,
                'original_filename': row.original_filename,
                'reject': (row.smoke or {}).get('reject'),
            }
            for row in rows
        ]


class InboundTemplateSerializer(serializers.ModelSerializer):
    owner_username = serializers.CharField(
        source='owner.username', read_only=True, default=None,
    )

    class Meta:
        model = InboundTemplate
        fields = [
            'id', 'name', 'kind', 'target_key', 'mapping',
            'owner', 'owner_username', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'owner', 'owner_username', 'created_at', 'updated_at']
