from django.contrib import admin
from .models import Contrato, Sede


class SedeInline(admin.TabularInline):
    model = Sede
    extra = 1


@admin.register(Contrato)
class ContratoAdmin(admin.ModelAdmin):
    list_display = ('numero_contrato', 'numero_licitacion', 'dependencia_cliente', 'fecha_inicio', 'fecha_fin', 'sla_horas_solucion', 'activo')
    list_filter = ('activo', 'fecha_inicio', 'fecha_fin')
    search_fields = ('numero_contrato', 'numero_licitacion', 'dependencia_cliente')
    inlines = [SedeInline]


@admin.register(Sede)
class SedeAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'contrato', 'enlace_responsable', 'telefono_contacto')
    list_filter = ('contrato',)
    search_fields = ('nombre', 'direccion', 'contrato__numero_contrato')
