from django.db import models
from django.conf import settings


class Refaccion(models.Model):
    class CategoriaRefaccion(models.TextChoices):
        ALMACENAMIENTO = 'ALMACENAMIENTO', 'Unidades de Almacenamiento (SSD / HDD)'
        MEMORIA_RAM = 'RAM', 'Módulos de Memoria RAM'
        REFRIGERACION = 'REFRIGERACION', 'Pasta Térmica / Ventiladores / Coolers'
        ENERGIA = 'ENERGIA', 'Fuentes de Alimentación (PSU) / Cables de Poder'
        PILA_CMOS = 'PILA_CMOS', 'Pilas CMOS / CR2032 de BIOS'
        PERIFERICOS = 'PERIFERICOS', 'Teclados / Mouse / Cables de Video'
        TARJETAS = 'TARJETAS', 'Tarjetas de Red / Expansión'
        CONSUMIBLE = 'CONSUMIBLE', 'Insumos de Limpieza (Alcohol isopropílico, microfibra)'

    codigo_parte = models.CharField(
        max_length=100,
        unique=True,
        verbose_name='Número de Parte / Código Refacción',
        help_text='Ej: PART-SSD-512GB-NVME, PASTA-TERM-SILVER'
    )
    nombre = models.CharField(
        max_length=150,
        verbose_name='Descripción de la Refacción o Insumo'
    )
    categoria = models.CharField(
        max_length=20,
        choices=CategoriaRefaccion.choices,
        default=CategoriaRefaccion.CONSUMIBLE,
        verbose_name='Categoría de Componente'
    )
    stock_actual = models.PositiveIntegerField(
        default=0,
        verbose_name='Existencia en Almacén'
    )
    stock_minimo_alerta = models.PositiveIntegerField(
        default=5,
        verbose_name='Punto de Reorden / Stock Mínimo'
    )
    costo_unitario = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        verbose_name='Costo Unitario ($ MXN)'
    )
    unidad_medida = models.CharField(
        max_length=50,
        default='Pieza',
        verbose_name='Unidad de Medida'
    )

    class Meta:
        verbose_name = 'Refacción e Insumo'
        verbose_name_plural = 'Almacén de Refacciones'
        ordering = ['categoria', 'nombre']

    def __str__(self):
        return f"{self.codigo_parte} - {self.nombre} (Stock: {self.stock_actual})"

    @property
    def stock_bajo(self):
        return self.stock_actual <= self.stock_minimo_alerta


class MovimientoInventario(models.Model):
    class TipoMovimiento(models.TextChoices):
        ENTRADA = 'ENTRADA', 'Entrada / Adquisición a Almacén'
        SALIDA_OT = 'SALIDA_OT', 'Salida / Surtido para Orden de Trabajo'
        AJUSTE = 'AJUSTE', 'Ajuste de Auditoría'

    refaccion = models.ForeignKey(
        Refaccion,
        on_delete=models.CASCADE,
        related_name='movimientos',
        verbose_name='Refacción'
    )
    tipo_movimiento = models.CharField(
        max_length=20,
        choices=TipoMovimiento.choices,
        verbose_name='Tipo de Movimiento'
    )
    cantidad = models.PositiveIntegerField(
        verbose_name='Cantidad'
    )
    orden_trabajo_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name='ID de Orden de Trabajo Asociada'
    )
    responsable = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name='Encargado de Almacén'
    )
    nota = models.TextField(
        blank=True,
        verbose_name='Nota o Justificación'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha y Hora de Movimiento'
    )

    class Meta:
        verbose_name = 'Movimiento de Almacén'
        verbose_name_plural = 'Movimientos de Almacén'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_tipo_movimiento_display()} ({self.cantidad}) - {self.refaccion.nombre}"


class AsignacionInsumoTecnico(models.Model):
    """
    Control de inventario en posesión de cada técnico de mantenimiento (Kit de campo).
    """
    tecnico = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='insumos_en_posesion',
        verbose_name='Técnico de Mantenimiento'
    )
    insumo = models.ForeignKey(
        Refaccion,
        on_delete=models.CASCADE,
        related_name='asignaciones_tecnicos',
        verbose_name='Insumo / Refacción'
    )
    cantidad_disponible = models.PositiveIntegerField(
        default=0,
        verbose_name='Cantidad en Posesión del Técnico'
    )
    stock_minimo_kit = models.PositiveIntegerField(
        default=2,
        verbose_name='Stock Mínimo en Maletín / Kit',
        help_text='Punto de reabastecimiento del kit personal'
    )
    fecha_ultima_dotacion = models.DateTimeField(
        auto_now=True,
        verbose_name='Fecha de Última Dotación'
    )

    class Meta:
        verbose_name = 'Insumo Asignado a Técnico'
        verbose_name_plural = 'Insumos en Posesión de Técnicos'
        unique_together = ('tecnico', 'insumo')
        ordering = ['tecnico', 'insumo__categoria', 'insumo__nombre']

    def __str__(self):
        nombre_tec = self.tecnico.get_full_name() or self.tecnico.username
        return f"{nombre_tec} &bull; {self.insumo.nombre}: {self.cantidad_disponible} {self.insumo.unidad_medida}(s)"

    @property
    def kit_bajo(self):
        return self.cantidad_disponible <= self.stock_minimo_kit


class MovimientoInsumoTecnico(models.Model):
    """
    Trazabilidad y auditoría de insumos entregados, consumidos o devueltos por técnicos.
    """
    class TipoOperacion(models.TextChoices):
        DOTACION = 'DOTACION', 'Dotación / Entrega desde Almacén Central'
        CONSUMO_MANTENIMIENTO = 'CONSUMO', 'Consumo en Servicio Preventivo'
        DEVOLUCION = 'DEVOLUCION', 'Devolución al Almacén Central'
        AJUSTE = 'AJUSTE', 'Ajuste de Inventario de Kit'

    tecnico = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='movimientos_insumos',
        verbose_name='Técnico de Mantenimiento'
    )
    insumo = models.ForeignKey(
        Refaccion,
        on_delete=models.CASCADE,
        related_name='movimientos_tecnicos',
        verbose_name='Insumo / Refacción'
    )
    tipo_operacion = models.CharField(
        max_length=20,
        choices=TipoOperacion.choices,
        default=TipoOperacion.DOTACION,
        verbose_name='Tipo de Operación'
    )
    cantidad = models.PositiveIntegerField(
        verbose_name='Cantidad'
    )
    orden_trabajo_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name='ID de Orden de Trabajo (si aplica)'
    )
    autorizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='dotaciones_autorizadas',
        verbose_name='Autorizado / Entregado por'
    )
    observaciones = models.TextField(
        blank=True,
        verbose_name='Observaciones o Justificación'
    )
    fecha = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha y Hora del Movimiento'
    )

    class Meta:
        verbose_name = 'Movimiento de Insumo de Técnico'
        verbose_name_plural = 'Historial de Insumos de Técnicos'
        ordering = ['-fecha']

    def __str__(self):
        return f"{self.get_tipo_operacion_display()} ({self.cantidad}) - {self.insumo.nombre} a {self.tecnico.username}"
