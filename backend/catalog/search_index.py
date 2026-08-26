"""
Signal handlers to maintain full-text search vectors for catalog models.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.postgres.search import SearchVector
from dataschema.models import DataTable
from .models import DataDomain


@receiver(post_save, sender=DataTable)
def update_datatable_search_vector(sender, instance, **kwargs):
    """
    Update search_vector for DataTable on post_save.
    Uses queryset.update() to bypass triggering post_save again.
    """
    search_vector = (
        SearchVector('title', weight='A') +
        SearchVector('name', weight='A') +
        SearchVector('description', weight='B')
    )
    DataTable.objects.filter(pk=instance.pk).update(search_vector=search_vector)


@receiver(post_save, sender=DataDomain)
def update_datadomain_search_vector(sender, instance, **kwargs):
    """
    Update search_vector for DataDomain on post_save.
    Uses queryset.update() to bypass triggering post_save again.
    """
    search_vector = (
        SearchVector('name', weight='A') +
        SearchVector('description', weight='B')
    )
    DataDomain.objects.filter(pk=instance.pk).update(search_vector=search_vector)
