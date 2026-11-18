from django.contrib import admin
from .models import Contrato, Sede, ReservaInsumoLicitacion


class SedeInline(admin.TabularInline):
    model = Sede
    extra = 1


class ReservaInsumoInline(admin.TabularInline):
    model = ReservaInsumoLicitacion
    extra = 1


@admin.register(Contrato)
class ContratoAdmin(admin.ModelAdmin):
    list_display = ('numero_licitacion', 'numero_contrato', 'dependencia_cliente', 'estatus', 'fecha_inicio', 'fecha_fin', 'sla_horas_solucion', 'activo')
    list_filter = ('estatus', 'activo', 'fecha_inicio', 'fecha_fin')
    search_fields = ('numero_licitacion', 'numero_contrato', 'dependencia_cliente', 'titulo')
    filter_horizontal = ('tecnicos_asignados',)
    inlines = [SedeInline, ReservaInsumoInline]


@admin.register(Sede)
class SedeAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'contrato', 'enlace_responsable', 'telefono_contacto')
    list_filter = ('contrato',)
    search_fields = ('nombre', 'direccion', 'contrato__numero_contrato', 'contrato__numero_licitacion')


@admin.register(ReservaInsumoLicitacion)
class ReservaInsumoLicitacionAdmin(admin.ModelAdmin):
    list_display = ('contrato', 'insumo', 'cantidad_asignada', 'fecha_asignacion')
    list_filter = ('contrato', 'insumo')
    search_fields = ('contrato__numero_licitacion', 'insumo__nombre')

