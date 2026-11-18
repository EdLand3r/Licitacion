from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from apps.inventory.models import Equipo
from apps.contracts.models import Contrato, Sede


class SolicitudServicio(models.Model):
    class Prioridad(models.TextChoices):
        BAJA = 'BAJA', 'Baja (48h)'
        MEDIA = 'MEDIA', 'Media (24h)'
        ALTA = 'ALTA', 'Alta (12h)'
        CRITICA = 'CRITICA', 'Crítica (4h)'

    class EstatusSolicitud(models.TextChoices):
        NUEVA = 'NUEVA', 'Nueva / Por Revisar'
        ASIGNADA = 'ASIGNADA', 'Asignada a Orden de Trabajo'
        EN_PROCESO = 'EN_PROCESO', 'En Atención Técnica'
        RESUELTA = 'RESUELTA', 'Resuelta / Validada'
        CANCELADA = 'CANCELADA', 'Cancelada'

    folio = models.CharField(
        max_length=50,
        unique=True,
        verbose_name='Folio de Ticket'
    )
    equipo = models.ForeignKey(
        Equipo,
        on_delete=models.CASCADE,
        related_name='solicitudes_correctivas',
        verbose_name='Equipo Afectado'
    )
    solicitante_enlace = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='solicitudes_creadas',
        verbose_name='Enlace Solicitante (Cliente)'
    )
    falla_reportada = models.TextField(
        verbose_name='Falla Reportada por el Cliente',
        help_text='Síntomas observados: no enciende, se reinicia, ruidos, pantalla azul, etc.'
    )
    prioridad = models.CharField(
        max_length=15,
        choices=Prioridad.choices,
        default=Prioridad.MEDIA,
        verbose_name='Prioridad de Atención'
    )
    estatus = models.CharField(
        max_length=20,
        choices=EstatusSolicitud.choices,
        default=EstatusSolicitud.NUEVA,
        verbose_name='Estatus de la Solicitud'
    )
    fecha_solicitud = models.DateTimeField(
        default=timezone.now,
        verbose_name='Fecha y Hora de Recepción'
    )
    fecha_limite_sla = models.DateTimeField(
        verbose_name='Fecha Límite Contractual (SLA)',
        help_text='Calculada con base en los tiempos de respuesta del contrato vigente'
    )

    class Meta:
        verbose_name = 'Solicitud Correctiva (Ticket)'
        verbose_name_plural = 'Solicitudes Correctivas (Tickets)'
        ordering = ['-fecha_solicitud']

    def __str__(self):
        return f"{self.folio} - {self.equipo.numero_serie} ({self.get_prioridad_display()})"

    def save(self, *args, **kwargs):
        if not self.folio:
            count = SolicitudServicio.objects.count() + 1
            self.folio = f"TCK-{timezone.now().strftime('%Y%m')}-{count:04d}"
        if not self.fecha_limite_sla:
            horas_sla = self.equipo.contrato.sla_horas_solucion
            self.fecha_limite_sla = self.fecha_solicitud + timedelta(hours=horas_sla)
        super().save(*args, **kwargs)


class OrdenTrabajo(models.Model):
    class TipoMantenimiento(models.TextChoices):
        PREVENTIVO = 'PREVENTIVO', 'Mantenimiento Preventivo (Programado)'
        CORRECTIVO = 'CORRECTIVO', 'Mantenimiento Correctivo (Atención a Falla)'
        GARANTIA = 'GARANTIA', 'Servicio por Garantía / Reincidencia'

    class EstatusOT(models.TextChoices):
        PROGRAMADA = 'PROGRAMADA', 'Programada en Calendario'
        ASIGNADA = 'ASIGNADA', 'Asignada a Técnico'
        EN_DIAGNOSTICO = 'EN_DIAGNOSTICO', 'En Diagnóstico / Pruebas'
        EN_EJECUCION = 'EN_EJECUCION', 'En Ejecución / Reparación'
        ESPERA_REFACCION = 'ESPERA_REFACCION', 'En Espera de Refacción'
        PENDIENTE_VALIDACION = 'PENDIENTE_VALIDACION', 'Finalizada - Pendiente Validación Cliente'
        CERRADA_CONFORME = 'CERRADA_CONFORME', 'Cerrada con Conformidad del Cliente'
        RECHAZADA = 'RECHAZADA', 'Rechazada por Cliente (Reapertura)'

    numero_orden = models.CharField(
        max_length=50,
        unique=True,
        verbose_name='Número de Orden / Folio OT'
    )
    tipo_servicio = models.CharField(
        max_length=20,
        choices=TipoMantenimiento.choices,
        default=TipoMantenimiento.PREVENTIVO,
        verbose_name='Tipo de Mantenimiento'
    )
    equipo = models.ForeignKey(
        Equipo,
        on_delete=models.CASCADE,
        related_name='ordenes_trabajo',
        verbose_name='Equipo de Cómputo'
    )
    solicitud_origen = models.OneToOneField(
        SolicitudServicio,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='orden_trabajo',
        verbose_name='Ticket Origen (Correctivo)'
    )
    coordinador = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='ordenes_coordinadas',
        verbose_name='Coordinador Responsable'
    )
    tecnico_asignado = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ordenes_asignadas',
        verbose_name='Técnico Asignado en Campo'
    )
    estatus = models.CharField(
        max_length=25,
        choices=EstatusOT.choices,
        default=EstatusOT.PROGRAMADA,
        verbose_name='Estatus de la Orden'
    )

    # Porcentaje de avance y datos complementarios de reporte comercial
    porcentaje_avance = models.PositiveIntegerField(
        default=0,
        verbose_name='Porcentaje de Avance (%)',
        help_text='Progreso de atención y ejecución técnica (0 a 100%)'
    )
    domicilio_laboratorio = models.CharField(
        max_length=255,
        default='Calle Principal S/N, Parque Industrial Tecnológico, Taller Central TI',
        verbose_name='Domicilio del Laboratorio'
    )
    telefono_extension_tecnico = models.CharField(
        max_length=50,
        blank=True,
        verbose_name='Teléfono / Extensión del Técnico'
    )
    telefono_whatsapp_cliente = models.CharField(
        max_length=50,
        blank=True,
        verbose_name='Teléfono / WhatsApp del Cliente'
    )

    # Fechas operativas (Metadatos según formato oficial pág. 17 y 21)
    fecha_recibido = models.DateTimeField(
        default=timezone.now,
        verbose_name='Fecha y Hora de Recibido'
    )
    fecha_estimada_entrega = models.DateTimeField(
        verbose_name='Fecha Estimada de Entrega (Compromiso SLA)'
    )
    fecha_inicio_atencion = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha y Hora Inicio de Atención'
    )
    fecha_real_entrega = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha Real de Entrega / Cierre'
    )

    # Diagnóstico Técnico y Resolución (Fase B de Taller)
    diagnostico_preliminar = models.TextField(
        blank=True,
        verbose_name='Diagnóstico Técnico Preliminar / Pruebas Realizadas'
    )
    causa_raiz = models.TextField(
        blank=True,
        verbose_name='Causa Raíz Identificada'
    )
    trabajo_realizado = models.TextField(
        blank=True,
        verbose_name='Trabajo Realizado / Solución Aplicada (Paso a Paso)'
    )

    # Observaciones y Cierre (Páginas 20-21)
    observaciones_recomendaciones = models.TextField(
        blank=True,
        verbose_name='Observaciones y Recomendaciones al Cliente'
    )
    costo_total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        verbose_name='Costo Total ($ MXN)',
        help_text='Indicar costo o especificar si está cubierto por contrato de licitación'
    )
    dias_garantia = models.PositiveIntegerField(
        default=30,
        verbose_name='Días de Garantía del Servicio'
    )
    cumplio_sla = models.BooleanField(
        default=True,
        verbose_name='Cumplió con los Tiempos de SLA'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Orden de Trabajo'
        verbose_name_plural = 'Órdenes de Trabajo'
        ordering = ['-fecha_recibido']

    def __str__(self):
        return f"{self.numero_orden} - {self.get_tipo_servicio_display()} | {self.equipo.numero_serie}"

    def save(self, *args, **kwargs):
        if not self.numero_orden:
            prefix = "OTP" if self.tipo_servicio == self.TipoMantenimiento.PREVENTIVO else "OTC"
            count = OrdenTrabajo.objects.count() + 1
            self.numero_orden = f"{prefix}-{timezone.now().strftime('%Y%m')}-{count:04d}"
        if not self.fecha_estimada_entrega:
            horas = self.equipo.contrato.sla_horas_solucion
            self.fecha_estimada_entrega = self.fecha_recibido + timedelta(hours=horas)
        if not self.telefono_extension_tecnico and self.tecnico_asignado:
            self.telefono_extension_tecnico = self.tecnico_asignado.phone or ""
        if not self.telefono_whatsapp_cliente and self.equipo and self.equipo.sede:
            self.telefono_whatsapp_cliente = self.equipo.sede.telefono_contacto or ""
        if self.estatus == self.EstatusOT.CERRADA_CONFORME and self.porcentaje_avance < 100:
            self.porcentaje_avance = 100
        super().save(*args, **kwargs)

    def actualizar_avance_desde_checklist(self):
        total = self.checklists.count()
        if total > 0:
            completados = self.checklists.filter(realizado=True).count()
            self.porcentaje_avance = int((completados / total) * 100)
            self.save(update_fields=['porcentaje_avance'])
        return self.porcentaje_avance

    @property
    def esta_vencida(self):
        if self.fecha_real_entrega:
            return self.fecha_real_entrega > self.fecha_estimada_entrega
        return timezone.now() > self.fecha_estimada_entrega

    @property
    def nombre_tecnico(self):
        if self.tecnico_asignado:
            return self.tecnico_asignado.get_full_name() or self.tecnico_asignado.username
        return "Sin Asignar (Despacho pendiente)"


class ChecklistPreventivo(models.Model):
    class CategoriaChecklist(models.TextChoices):
        SEGURIDAD = 'SEGURIDAD', '1. Preparación, Herramientas y Medidas de Seguridad'
        HARDWARE_FISICO = 'HARDWARE', '2. Mantenimiento del Hardware (Limpieza Física)'
        SOFTWARE_LOGICO = 'SOFTWARE', '3. Mantenimiento del Software (Lógico y del Sistema)'

    orden = models.ForeignKey(
        OrdenTrabajo,
        on_delete=models.CASCADE,
        related_name='checklists',
        verbose_name='Orden de Trabajo'
    )
    categoria = models.CharField(
        max_length=20,
        choices=CategoriaChecklist.choices,
        verbose_name='Fase de Mantenimiento'
    )
    tarea = models.CharField(
        max_length=255,
        verbose_name='Paso / Actividad Técnica'
    )
    realizado = models.BooleanField(
        default=False,
        verbose_name='¿Completado / Verificado?'
    )
    observacion = models.CharField(
        max_length=255,
        blank=True,
        verbose_name='Observación Técnica'
    )

    class Meta:
        verbose_name = 'Ítem de Lista de Verificación'
        verbose_name_plural = 'Checklist de Mantenimiento'
        ordering = ['categoria', 'id']

    def __str__(self):
        estado = "✓" if self.realizado else "✗"
        return f"[{estado}] {self.tarea}"


class EvidenciaFotografica(models.Model):
    class EtapaEvidencia(models.TextChoices):
        ANTES = 'ANTES', 'Antes del Servicio (Condición Inicial)'
        DURANTE = 'DURANTE', 'Durante la Ejecución (Desarme / Pruebas)'
        DESPUES = 'DESPUES', 'Después del Servicio (Equipo Limpio / Funcionando)'

    orden = models.ForeignKey(
        OrdenTrabajo,
        on_delete=models.CASCADE,
        related_name='evidencias',
        verbose_name='Orden de Trabajo'
    )
    etapa = models.CharField(
        max_length=15,
        choices=EtapaEvidencia.choices,
        default=EtapaEvidencia.DESPUES,
        verbose_name='Etapa de la Fotografía'
    )
    imagen = models.ImageField(
        upload_to='evidencias/%Y/%m/',
        verbose_name='Archivo de Fotografía'
    )
    descripcion = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='Descripción de la Evidencia'
    )
    fecha_captura = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de Captura'
    )

    class Meta:
        verbose_name = 'Evidencia Fotográfica'
        verbose_name_plural = 'Evidencias Fotográficas'


class SolicitudRefaccionOT(models.Model):
    class EstatusSolicitudRefaccion(models.TextChoices):
        SOLICITADA = 'SOLICITADA', 'Solicitada por Técnico'
        SURTIDA = 'SURTIDA', 'Surtida por Almacén'
        RECHAZADA_AGOTADA = 'AGOTADA', 'Sin Existencia / Denegada'

    orden = models.ForeignKey(
        OrdenTrabajo,
        on_delete=models.CASCADE,
        related_name='refacciones_usadas',
        verbose_name='Orden de Trabajo'
    )
    refaccion = models.ForeignKey(
        'warehouse.Refaccion',
        on_delete=models.PROTECT,
        verbose_name='Refacción Solicitada'
    )
    cantidad = models.PositiveIntegerField(
        default=1,
        verbose_name='Cantidad Solicitada'
    )
    estatus = models.CharField(
        max_length=20,
        choices=EstatusSolicitudRefaccion.choices,
        default=EstatusSolicitudRefaccion.SOLICITADA,
        verbose_name='Estatus de Surtido'
    )
    solicitado_en = models.DateTimeField(auto_now_add=True)
    despachado_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Refacción Empleada en OT'
        verbose_name_plural = 'Refacciones Empleadas en OTs'


class FirmaDigitalOT(models.Model):
    class TipoFirmante(models.TextChoices):
        TECNICO = 'TECNICO', 'Técnico Encargado (Aprobación Técnica)'
        ENLACE_CLIENTE = 'ENLACE_CLIENTE', 'Enlace de la Dependencia (Firma de Conformidad)'

    orden = models.ForeignKey(
        OrdenTrabajo,
        on_delete=models.CASCADE,
        related_name='firmas',
        verbose_name='Orden de Trabajo'
    )
    tipo_firmante = models.CharField(
        max_length=20,
        choices=TipoFirmante.choices,
        verbose_name='Tipo de Firmante'
    )
    nombre_firmante = models.CharField(
        max_length=150,
        verbose_name='Nombre Completo del Firmante'
    )
    cargo = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Cargo o Puesto'
    )
    firma_digital_data = models.TextField(
        verbose_name='Trazo Vectorial / Base64 Firma'
    )
    hash_seguridad = models.CharField(
        max_length=64,
        blank=True,
        verbose_name='Sello Criptográfico SHA-256'
    )
    fecha_firmado = models.DateTimeField(
        default=timezone.now,
        verbose_name='Fecha y Hora de Firma'
    )

    class Meta:
        verbose_name = 'Firma de Conformidad'
        verbose_name_plural = 'Firmas de Conformidad'
        unique_together = ('orden', 'tipo_firmante')
