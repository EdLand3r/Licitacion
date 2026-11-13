from django.db import models
from django.conf import settings
from django.utils import timezone


class Contrato(models.Model):
    numero_licitacion = models.CharField(
        max_length=100,
        verbose_name='Número de Licitación',
        help_text='Ejemplo: LIC-FED-2026-TI-042'
    )
    numero_contrato = models.CharField(
        max_length=100,
        unique=True,
        verbose_name='Número de Contrato',
        help_text='Número oficial del contrato adjudicado'
    )
    dependencia_cliente = models.CharField(
        max_length=200,
        verbose_name='Dependencia Contratante / Cliente',
        help_text='Entidad pública o privada que contrata el servicio'
    )
    descripcion = models.TextField(
        blank=True,
        verbose_name='Descripción del Servicio'
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
    penalizacion_por_retraso = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        verbose_name='Penalización Económica por Incumplimiento SLA ($/Hora)',
        help_text='Cálculo contractual de deducción o sanción si se excede el SLA'
    )
    responsable_licitaciones = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='contratos_administrados',
        verbose_name='Responsable de Licitaciones'
    )
    activo = models.BooleanField(
        default=True,
        verbose_name='Contrato Vigente / Activo'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Contrato y Licitación'
        verbose_name_plural = 'Contratos y Licitaciones'
        ordering = ['-fecha_fin', 'numero_contrato']

    def __str__(self):
        return f"{self.numero_contrato} - {self.dependencia_cliente}"

    @property
    def esta_vigente(self):
        hoy = timezone.now().date()
        return self.activo and (self.fecha_inicio <= hoy <= self.fecha_fin)


class Sede(models.Model):
    contrato = models.ForeignKey(
        Contrato,
        on_delete=models.CASCADE,
        related_name='sedes',
        verbose_name='Contrato Vinculado'
    )
    nombre = models.CharField(
        max_length=150,
        verbose_name='Nombre de la Sede / Sucursal',
        help_text='Ej: Campus Central, Unidad Administrativa, Laboratorio 1'
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
        return f"{self.nombre} ({self.contrato.numero_contrato})"
