from django.contrib import admin

from .models import (
    Correspondence,
    WorkflowPolicy,
    WorkflowPolicyStep,
    CorrespondenceEvent,
    CorrespondenceAttachment,
    CorrespondenceRegistry,
    Delegation,
    Notification,
)


@admin.register(Correspondence)
class CorrespondenceAdmin(admin.ModelAdmin):
    list_display = ('reference_no', 'title', 'status', 'corr_type', 'requester')
    list_filter = ('status', 'corr_type')
    search_fields = ('reference_no', 'title')


@admin.register(WorkflowPolicy)
class WorkflowPolicyAdmin(admin.ModelAdmin):
    list_display = ('name', 'corr_type', 'version', 'is_active')
    list_filter = ('corr_type', 'is_active')


@admin.register(WorkflowPolicyStep)
class WorkflowPolicyStepAdmin(admin.ModelAdmin):
    list_display = ('policy', 'order', 'role', 'intent')
    list_filter = ('role', 'intent')


@admin.register(CorrespondenceEvent)
class CorrespondenceEventAdmin(admin.ModelAdmin):
    list_display = ('correspondence', 'seq', 'event_type', 'to_status')
    list_filter = ('event_type',)


@admin.register(CorrespondenceAttachment)
class CorrespondenceAttachmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'correspondence', 'mime_type', 'size')
    list_filter = ('mime_type',)


@admin.register(CorrespondenceRegistry)
class CorrespondenceRegistryAdmin(admin.ModelAdmin):
    list_display = ('year', 'counter')
    list_filter = ('year',)


@admin.register(Delegation)
class DelegationAdmin(admin.ModelAdmin):
    list_display = ('delegator', 'delegate', 'scope', 'is_active')
    list_filter = ('scope', 'is_active')


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'title', 'type', 'is_read')
    list_filter = ('type', 'is_read')
