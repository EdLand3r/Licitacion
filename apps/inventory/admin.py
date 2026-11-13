from django.contrib import admin
from .models import Equipo, EspecificacionHardware


class EspecificacionHardwareInline(admin.StackedInline):
    model = EspecificacionHardware
    can_delete = False
    verbose_name = 'Detalle de Hardware (Arquitectura)'


@admin.register(Equipo)
class EquipoAdmin(admin.ModelAdmin):
    list_display = ('numero_serie', 'marca', 'modelo', 'tipo_equipo', 'sede', 'contrato', 'estatus_operativo')
    list_filter = ('tipo_equipo', 'estatus_operativo', 'contrato', 'sede')
    search_fields = ('numero_serie', 'codigo_inventario_interno', 'marca', 'modelo', 'usuario_asignado_nombre')
    inlines = [EspecificacionHardwareInline]


@admin.register(EspecificacionHardware)
class EspecificacionHardwareAdmin(admin.ModelAdmin):
    list_display = ('equipo', 'cpu_marca_modelo', 'ram_capacidad_gb', 'ram_tecnologia', 'almacenamiento_tipo', 'almacenamiento_capacidad_gb')
    search_fields = ('equipo__numero_serie', 'cpu_marca_modelo', 'motherboard_marca_modelo')
