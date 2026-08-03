# importexport/serializers.py
from rest_framework import serializers
from .models import ExportProject, ImportJob, ExportJob


class ExportProjectSerializer(serializers.ModelSerializer):
    owner_name = serializers.StringRelatedField(source='owner', read_only=True)
    data_table_title = serializers.StringRelatedField(source='data_table', read_only=True)
    job_count = serializers.SerializerMethodField()

    class Meta:
        model = ExportProject
        fields = [
            'id', 'name', 'slug', 'description', 'data_table', 'data_table_title',
            'format', 'filters', 'is_active', 'owner', 'owner_name',
            'job_count', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'slug', 'job_count', 'created_at', 'updated_at']

    def get_job_count(self, obj):
        return obj.jobs.count()

    def create(self, validated_data):
        if 'owner' not in validated_data or not validated_data['owner']:
            validated_data['owner'] = self.context['request'].user
        return super().create(validated_data)


class ImportJobSerializer(serializers.ModelSerializer):
    user_name = serializers.StringRelatedField(source='user', read_only=True)
    data_table_title = serializers.StringRelatedField(source='data_table', read_only=True)
    source_name = serializers.StringRelatedField(source='source', read_only=True)

    class Meta:
        model = ImportJob
        fields = [
            'id', 'data_table', 'data_table_title', 'source', 'source_name',
            'file', 'format', 'status', 'row_count', 'error_count', 'log',
            'user', 'user_name', 'started_at', 'finished_at', 'created_at',
        ]
        read_only_fields = [
            'id', 'status', 'row_count', 'error_count', 'log',
            'started_at', 'finished_at', 'created_at',
        ]


class ExportJobSerializer(serializers.ModelSerializer):
    user_name = serializers.StringRelatedField(source='user', read_only=True)
    data_table_title = serializers.StringRelatedField(source='data_table', read_only=True)
    export_project_name = serializers.StringRelatedField(source='export_project', read_only=True)
    download_url = serializers.SerializerMethodField()

    class Meta:
        model = ExportJob
        fields = [
            'id', 'export_project', 'export_project_name', 'data_table', 'data_table_title',
            'format', 'filters', 'file', 'status', 'row_count', 'user', 'user_name',
            'started_at', 'finished_at', 'created_at', 'download_url',
        ]
        read_only_fields = [
            'id', 'file', 'status', 'row_count', 'started_at', 'finished_at', 'created_at',
        ]

    def get_download_url(self, obj):
        if obj.file and obj.status == 'ready':
            return obj.file.url
        return None
