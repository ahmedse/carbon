from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User

class CustomUserAdmin(UserAdmin):
    # Display these fields in the user list
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'is_staff', 'is_active')
    # Add 'role' to the fieldsets so it's editable in the admin
    fieldsets = UserAdmin.fieldsets + (
        ('Custom Fields', {'fields': ('role',)}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Custom Fields', {'fields': ('role',)}),
    )
    # Add search by role
    search_fields = UserAdmin.search_fields + ('role',)
    # Add filtering by role
    list_filter = UserAdmin.list_filter + ('role',)

# Unregister the default User admin, if registered, and register the custom one
# admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)