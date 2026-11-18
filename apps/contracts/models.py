from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import timedelta


class Contrato(models.Model):
    class EstatusLicitacion(models.TextChoices):
        ACTIVA = 'ACTIVA', 'Activa'
        POR_VENCER = 'POR_VENCER', 'Por Vencer (< 30 días)'
        CERRADA = 'CERRADA', 'Cerrada / Concluida'

    numero_licitacion = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Folio de Licitación',
        help_text='Ejemplo: LIC-2026-0001 (Se genera automáticamente si se deja vacío)'
    )
    numero_contrato = models.CharField(
        max_length=100,
        unique=True,
        blank=True,
        verbose_name='Número de Contrato',
        help_text='Ejemplo: CT-ITSE-2026-001'
    )
    titulo = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='Título / Objeto de la Licitación',
        help_text='Ej: Mantenimiento Preventivo Integral de Equipos de Cómputo y Servidores 2026'
    )
    dependencia_cliente = models.CharField(
        max_length=200,
        verbose_name='Dependencia Contratante / Cliente',
        help_text='Entidad pública o privada que contrata el servicio (ej. ITSE, SEDUC)'
    )
    descripcion = models.TextField(
        blank=True,
        verbose_name='Descripción del Alcance Técnico',
        help_text='Detalle de servicios preventivos, cronogramas y especificaciones de atención'
    )
    fecha_inicio = models.DateField(
        verbose_name='Fecha de Inicio de Vigencia'
    )
    fecha_fin = models.DateField(
        verbose_name='Fecha de Fin de Vigencia'
    )
    sla_horas_respuesta = models.PositiveIntegerField(
        default=4,
        verbose_name='SLA Tiempo Máximo de Respuesta (Horas)',
        help_text='Tiempo máximo contractual para contactar y despachar al técnico'
    )
    sla_horas_solucion = models.PositiveIntegerField(
        default=24,
        verbose_name='SLA Tiempo Máximo de Solución (Horas)',
        help_text='Tiempo contractual máximo para diagnosticar, resolver y entregar el equipo funcional'
    )
    # Campo heredado preserved for DB backwards-compatibility; excluded completely from UI/forms/views
    penalizacion_por_retraso = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        blank=True,
        verbose_name='Deducción Contractual SLA (Operativa)'
    )
    responsable_licitaciones = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='contratos_administrados',
        verbose_name='Responsable de Licitaciones'
    )
    tecnicos_asignados = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='licitaciones_asignadas',
        blank=True,
        verbose_name='Técnicos Asignados Exclusivos'
    )
    estatus = models.CharField(
        max_length=20,
        choices=EstatusLicitacion.choices,
        default=EstatusLicitacion.ACTIVA,
        verbose_name='Estatus de la Licitación'
    )
    activo = models.BooleanField(
        default=True,
        verbose_name='Contrato Vigente / Activo'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Licitación y Contrato SLA'
        verbose_name_plural = 'Licitaciones y Contratos SLA'
        ordering = ['-fecha_fin', 'numero_licitacion']

    def __str__(self):
        return f"{self.numero_licitacion} - {self.dependencia_cliente} ({self.numero_contrato})"

    def save(self, *args, **kwargs):
        año = self.fecha_inicio.year if self.fecha_inicio else timezone.now().year
        # Generación automática de Folio secuencial si viene vacío (LIC-YYYY-XXXX)
        if not self.numero_licitacion:
            total = Contrato.objects.filter(fecha_inicio__year=año).count() + 1
            self.numero_licitacion = f"LIC-{año}-{total:04d}"

        # Generación automática de Número de Contrato si viene vacío (CT-[SIGLAS]-YYYY-XXX)
        if not self.numero_contrato:
            dep_clean = self.dependencia_cliente or "DEP"
            siglas = "".join([w[0].upper() for w in dep_clean.replace('(', '').replace(')', '').split() if len(w) > 2])[:5] or "DEP"
            total = Contrato.objects.count() + 1
            self.numero_contrato = f"CT-{siglas}-{año}-{total:03d}"

        if not self.titulo:
            self.titulo = f"Licitación {self.numero_licitacion} - {self.dependencia_cliente}"

        # Ajuste de estatus dinámico por fecha
        if self.fecha_fin:
            hoy = timezone.now().date()
            if not self.activo or self.fecha_fin < hoy:
                self.estatus = self.EstatusLicitacion.CERRADA
            elif self.fecha_fin <= hoy + timedelta(days=30):
                self.estatus = self.EstatusLicitacion.POR_VENCER
            else:
                self.estatus = self.EstatusLicitacion.ACTIVA

        super().save(*args, **kwargs)

    @property
    def esta_vigente(self):
        hoy = timezone.now().date()
        return self.activo and (self.fecha_inicio <= hoy <= self.fecha_fin)


class Sede(models.Model):
    contrato = models.ForeignKey(
        Contrato,
        on_delete=models.CASCADE,
        related_name='sedes',
        verbose_name='Licitación Vinculada'
    )
    nombre = models.CharField(
        max_length=150,
        verbose_name='Nombre de la Sede / Ubicación',
        help_text='Ej: Campus Central, Unidad Administrativa, Laboratorio Cómputo B'
    )
    direccion = models.TextField(
        verbose_name='Dirección Física Completa'
    )
    enlace_responsable = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sedes_asignadas',
        verbose_name='Usuario Enlace de la Dependencia'
    )
    telefono_contacto = models.CharField(
        max_length=30,
        blank=True,
        verbose_name='Teléfono de la Sede'
    )

    class Meta:
        verbose_name = 'Sede'
        verbose_name_plural = 'Sedes'
        ordering = ['contrato', 'nombre']

    def __str__(self):
        return f"{self.nombre} ({self.contrato.numero_licitacion})"


class ReservaInsumoLicitacion(models.Model):
    """
    Gestión e Insumos vinculados exclusivamente a una Licitación:
    Permite comprometer y reservar existencias de almacén para atender dicha licitación
    sin referencias a costos financieros o dinero.
    """
    contrato = models.ForeignKey(
        Contrato,
        on_delete=models.CASCADE,
        related_name='insumos_reservados',
        verbose_name='Licitación'
    )
    insumo = models.ForeignKey(
        'warehouse.Refaccion',
        on_delete=models.CASCADE,
        related_name='reservas_licitacion',
        verbose_name='Insumo / Refacción'
    )
    cantidad_asignada = models.PositiveIntegerField(
        default=1,
        verbose_name='Cantidad Asignada / Reservada'
    )
    notas = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='Notas o Destino de Uso'
    )
    fecha_asignacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Insumo Reservado para Licitación'
        verbose_name_plural = 'Insumos Reservados para Licitaciones'
        unique_together = ('contrato', 'insumo')

    def __str__(self):
        return f"{self.insumo.nombre}: {self.cantidad_asignada} {self.insumo.unidad_medida}(s) para {self.contrato.numero_licitacion}"


def validar_disponibilidad_tecnico(tecnico, fecha_inicio, fecha_fin, licitacion_actual_id=None):
    """
    Validación estricta de disponibilidad (Conflictos de Agenda):
    Verifica si el técnico ya tiene asignada otra licitación activa que se traslape
    en el rango de fechas [fecha_inicio, fecha_fin].
    Regla: (c.fecha_inicio <= fecha_fin) and (c.fecha_fin >= fecha_inicio).
    Retorna (True, None) si no hay traslape, o (False, mensaje_error) si está ocupado.
    """
    if not fecha_inicio or not fecha_fin:
        return True, None

    qs = Contrato.objects.filter(
        activo=True,
        tecnicos_asignados=tecnico,
        fecha_inicio__lte=fecha_fin,
        fecha_fin__gte=fecha_inicio
    )
    if licitacion_actual_id:
        qs = qs.exclude(pk=licitacion_actual_id)

    conflicto = qs.first()
    if conflicto:
        nombre_tec = tecnico.get_full_name() or tecnico.username
        msg = (
            f"Conflicto de Agenda: El técnico '{nombre_tec}' ya se encuentra asignado a la licitación "
            f"'{conflicto.numero_licitacion}' ({conflicto.dependencia_cliente}) "
            f"vigente del {conflicto.fecha_inicio.strftime('%d/%m/%Y')} al {conflicto.fecha_fin.strftime('%d/%m/%Y')}. "
            f"No es posible empalmar su asignación."
        )
        return False, msg
    return True, None
