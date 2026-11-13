from django.contrib import admin
from .models import (
    SolicitudServicio,
    OrdenTrabajo,
    ChecklistPreventivo,
    EvidenciaFotografica,
    SolicitudRefaccionOT,
    FirmaDigitalOT,
)


class ChecklistInline(admin.TabularInline):
    model = ChecklistPreventivo
    extra = 0


class EvidenciaInline(admin.TabularInline):
    model = EvidenciaFotografica
    extra = 0


class RefaccionInline(admin.TabularInline):
    model = SolicitudRefaccionOT
    extra = 0


class FirmaInline(admin.StackedInline):
    model = FirmaDigitalOT
    extra = 0


@admin.register(SolicitudServicio)
class SolicitudServicioAdmin(admin.ModelAdmin):
    list_display = ('folio', 'equipo', 'solicitante_enlace', 'prioridad', 'estatus', 'fecha_solicitud', 'fecha_limite_sla')
    list_filter = ('prioridad', 'estatus', 'fecha_solicitud')
    search_fields = ('folio', 'equipo__numero_serie', 'falla_reportada')


@admin.register(OrdenTrabajo)
class OrdenTrabajoAdmin(admin.ModelAdmin):
    list_display = ('numero_orden', 'tipo_servicio', 'equipo', 'tecnico_asignado', 'coordinador', 'estatus', 'fecha_estimada_entrega', 'cumplio_sla')
    list_filter = ('tipo_servicio', 'estatus', 'cumplio_sla')
    search_fields = ('numero_orden', 'equipo__numero_serie', 'diagnostico_preliminar')
    inlines = [ChecklistInline, EvidenciaInline, RefaccionInline, FirmaInline]


@admin.register(ChecklistPreventivo)
class ChecklistPreventivoAdmin(admin.ModelAdmin):
    list_display = ('orden', 'categoria', 'tarea', 'realizado')
    list_filter = ('categoria', 'realizado')
    search_fields = ('tarea', 'orden__numero_orden')
