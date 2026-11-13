from django.contrib import admin
from .models import Refaccion, MovimientoInventario, AsignacionInsumoTecnico, MovimientoInsumoTecnico


@admin.register(Refaccion)
class RefaccionAdmin(admin.ModelAdmin):
    list_display = ('codigo_parte', 'nombre', 'categoria', 'stock_actual', 'stock_minimo_alerta', 'costo_unitario', 'stock_bajo')
    list_filter = ('categoria',)
    search_fields = ('codigo_parte', 'nombre')


@admin.register(MovimientoInventario)
class MovimientoInventarioAdmin(admin.ModelAdmin):
    list_display = ('refaccion', 'tipo_movimiento', 'cantidad', 'orden_trabajo_id', 'responsable', 'created_at')
    list_filter = ('tipo_movimiento', 'created_at')
    search_fields = ('refaccion__codigo_parte', 'refaccion__nombre', 'nota')


@admin.register(AsignacionInsumoTecnico)
class AsignacionInsumoTecnicoAdmin(admin.ModelAdmin):
    list_display = ('tecnico', 'insumo', 'cantidad_disponible', 'stock_minimo_kit', 'kit_bajo', 'fecha_ultima_dotacion')
    list_filter = ('tecnico', 'insumo__categoria')
    search_fields = ('tecnico__username', 'tecnico__first_name', 'tecnico__last_name', 'insumo__nombre', 'insumo__codigo_parte')


@admin.register(MovimientoInsumoTecnico)
class MovimientoInsumoTecnicoAdmin(admin.ModelAdmin):
    list_display = ('tecnico', 'insumo', 'tipo_operacion', 'cantidad', 'autorizado_por', 'fecha')
    list_filter = ('tipo_operacion', 'tecnico', 'fecha')
    search_fields = ('tecnico__username', 'insumo__nombre', 'observaciones')
