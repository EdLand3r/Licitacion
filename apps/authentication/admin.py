from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Información Institucional y Rol', {
            'fields': ('role', 'phone', 'dependencia_o_empresa', 'cargo')
        }),
    )
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'dependencia_o_empresa', 'is_active')
    list_filter = ('role', 'is_active', 'is_staff')
    search_fields = ('username', 'first_name', 'last_name', 'email', 'dependencia_o_empresa')
