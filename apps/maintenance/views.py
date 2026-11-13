from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db.models import Q
from datetime import timedelta

from apps.authentication.decorators import role_required
from apps.authentication.models import User
from apps.inventory.models import Equipo
from apps.contracts.models import Contrato
from .models import OrdenTrabajo, SolicitudServicio, ChecklistPreventivo, FirmaDigitalOT


def limpiar_saltos(texto):
    """
    Corrige cadenas que contienen secuencias de caracteres literales '\\n'
    y las convierte en saltos de línea reales de Python ('\n').
    """
    if not texto:
        return ""
    return str(texto).replace(r'\n', '\n').replace('\\n', '\n').strip()


@login_required
def ordenes_lista(request):
    """
    Lista de Órdenes de Mantenimiento Preventivo con:
    - Búsqueda por Técnico de mantenimiento
    - Búsqueda general por texto (serie, modelo, folio, contrato)
    - Filtrado y Agrupación por Licitación
    - Medidor visual del Porcentaje de Avance
    - Filtro de seguridad RBAC para Enlace de Cliente
    """
    query = request.GET.get('q', '').strip()
    tecnico_id = request.GET.get('tecnico', '').strip()
    licitacion_id = request.GET.get('licitacion', '').strip()
    agrupar = request.GET.get('agrupar', '').strip()

    # Exclusivamente Mantenimiento Preventivo (Requerimiento Obligatorio)
    ordenes_qs = (
        OrdenTrabajo.objects
        .filter(tipo_servicio=OrdenTrabajo.TipoMantenimiento.PREVENTIVO)
        .select_related('equipo', 'equipo__sede', 'equipo__contrato', 'tecnico_asignado', 'coordinador')
        .all()
    )

    # Regla RBAC para Enlace: ver solo órdenes de sus sedes asignadas
    if request.user.role == User.Role.ENLACE:
        ordenes_qs = ordenes_qs.filter(equipo__sede__enlace_responsable=request.user)

    # Filtrado por búsqueda de texto
    if query:
        ordenes_qs = ordenes_qs.filter(
            Q(numero_orden__icontains=query) |
            Q(equipo__numero_serie__icontains=query) |
            Q(equipo__marca__icontains=query) |
            Q(equipo__modelo__icontains=query) |
            Q(equipo__contrato__numero_contrato__icontains=query) |
            Q(equipo__contrato__numero_licitacion__icontains=query) |
            Q(tecnico_asignado__first_name__icontains=query) |
            Q(tecnico_asignado__last_name__icontains=query) |
            Q(tecnico_asignado__username__icontains=query)
        )

    # Filtrado por Técnico de mantenimiento
    if tecnico_id:
        ordenes_qs = ordenes_qs.filter(tecnico_asignado_id=tecnico_id)

    # Filtrado por Licitación / Contrato
    if licitacion_id:
        ordenes_qs = ordenes_qs.filter(equipo__contrato_id=licitacion_id)

    # Agrupación por Licitación
    ordenes_agrupadas = None
    if agrupar in ['1', 'licitacion']:
        contratos = Contrato.objects.all()
        ordenes_agrupadas = []
        for c in contratos:
            ots_contrato = [ot for ot in ordenes_qs if ot.equipo.contrato_id == c.id]
            if ots_contrato:
                promedio_avance = int(sum(ot.porcentaje_avance for ot in ots_contrato) / len(ots_contrato))
                ordenes_agrupadas.append({
                    'contrato': c,
                    'ordenes': ots_contrato,
                    'total': len(ots_contrato),
                    'promedio_avance': promedio_avance
                })

    tecnicos = User.objects.filter(role=User.Role.TECNICO)
    contratos_todos = Contrato.objects.all()

    context = {
        'ordenes': ordenes_qs,
        'ordenes_agrupadas': ordenes_agrupadas,
        'agrupado': agrupar in ['1', 'licitacion'],
        'tecnicos': tecnicos,
        'contratos': contratos_todos,
        'query': query,
        'tecnico_seleccionado': tecnico_id,
        'licitacion_seleccionada': licitacion_id,
    }
    return render(request, 'maintenance/ordenes_lista.html', context)


@login_required
def orden_detalle(request, pk):
    """
    Vista del Reporte de Mantenimiento Preventivo ('Documento sin título').
    Permite:
    1. Visualización y Edición Manual Abierta (inputs/textareas sin bloqueo).
    2. Guardado de cambios técnicos en base de datos.
    3. Firma digital de conformidad para Enlaces de la Dependencia.
    """
    orden = get_object_or_404(
        OrdenTrabajo.objects
        .select_related(
            'equipo',
            'equipo__especificaciones',
            'equipo__contrato',
            'equipo__sede',
            'tecnico_asignado',
            'coordinador',
            'solicitud_origen'
        )
        .prefetch_related('checklists', 'refacciones_usadas__refaccion', 'firmas'),
        pk=pk
    )

    # Verificación de seguridad RBAC para Enlace de la dependencia
    if request.user.role == User.Role.ENLACE:
        if orden.equipo.sede.enlace_responsable != request.user and not request.user.is_superuser:
            messages.error(request, "No tiene autorización para visualizar reportes de sedes ajenas.")
            return redirect('unauthorized')

    # PROCESAMIENTO DE EDICIÓN MANUAL DEL REPORTE (POST)
    if request.method == 'POST':
        accion = request.POST.get('accion', 'guardar')

        # Acción 1: Firma de conformidad por parte del Enlace Cliente
        if accion == 'firmar_cliente':
            if request.user.role in [User.Role.ENLACE, User.Role.ADMIN]:
                nombre = request.POST.get('nombre_firmante', request.user.get_full_name() or request.user.username)
                FirmaDigitalOT.objects.update_or_create(
                    orden=orden,
                    tipo_firmante=FirmaDigitalOT.TipoFirmante.ENLACE_CLIENTE,
                    defaults={
                        'nombre_firmante': nombre,
                        'cargo': request.user.cargo or 'Enlace de la Dependencia',
                        'firma_digital_data': 'CONFORMIDAD_DIGITAL_APROBADA',
                        'hash_seguridad': f"SHA256:{timezone.now().timestamp()}"
                    }
                )
                orden.estatus = OrdenTrabajo.EstatusOT.CERRADA_CONFORME
                orden.porcentaje_avance = 100
                orden.fecha_real_entrega = timezone.now()
                orden.save()
                messages.success(request, "✓ ¡Firma de conformidad registrada! Orden cerrada exitosamente.")
                return redirect('orden_detalle', pk=pk)

        # Acción 2: Edición manual de campos técnicos (Técnico, Coordinador o Admin)
        if request.user.role in [User.Role.ADMIN, User.Role.COORDINADOR, User.Role.TECNICO]:
            # Guardar campos editables del reporte
            orden.domicilio_laboratorio = request.POST.get('domicilio_laboratorio', orden.domicilio_laboratorio)
            orden.telefono_extension_tecnico = request.POST.get('telefono_extension_tecnico', orden.telefono_extension_tecnico)
            orden.telefono_whatsapp_cliente = request.POST.get('telefono_whatsapp_cliente', orden.telefono_whatsapp_cliente)

            # Campos de Diagnóstico y Trabajo Realizado (normalizando saltos de línea \n)
            orden.diagnostico_preliminar = limpiar_saltos(request.POST.get('diagnostico_preliminar', orden.diagnostico_preliminar))
            orden.causa_raiz = limpiar_saltos(request.POST.get('causa_raiz', orden.causa_raiz))
            orden.trabajo_realizado = limpiar_saltos(request.POST.get('trabajo_realizado', orden.trabajo_realizado))
            orden.observaciones_recomendaciones = limpiar_saltos(request.POST.get('observaciones_recomendaciones', orden.observaciones_recomendaciones))

            # Ajuste de porcentaje de avance si fue modificado
            avance_val = request.POST.get('porcentaje_avance')
            if avance_val is not None:
                try:
                    orden.porcentaje_avance = max(0, min(100, int(avance_val)))
                except ValueError:
                    pass

            orden.save()
            messages.success(request, "✓ ¡Cambios del Reporte Preventivo guardados correctamente! El documento está listo para imprimir o exportar a PDF.")
            return redirect('orden_detalle', pk=pk)
        else:
            messages.error(request, "Su rol no cuenta con permisos para modificar los campos técnicos del reporte.")
            return redirect('orden_detalle', pk=pk)

    # Limpiar cadenas para el renderizado inicial en pantalla
    orden.diagnostico_preliminar = limpiar_saltos(orden.diagnostico_preliminar)
    orden.causa_raiz = limpiar_saltos(orden.causa_raiz)
    orden.trabajo_realizado = limpiar_saltos(orden.trabajo_realizado)
    orden.observaciones_recomendaciones = limpiar_saltos(orden.observaciones_recomendaciones)

    puede_editar = request.user.role in [User.Role.ADMIN, User.Role.COORDINADOR, User.Role.TECNICO]
    puede_firmar_cliente = request.user.role in [User.Role.ADMIN, User.Role.ENLACE]

    context = {
        'orden': orden,
        'puede_editar': puede_editar,
        'puede_firmar_cliente': puede_firmar_cliente,
    }
    return render(request, 'maintenance/orden_detalle.html', context)


@login_required
@role_required([User.Role.ADMIN, User.Role.COORDINADOR, User.Role.TECNICO])
def orden_actualizar_avance(request, pk):
    """
    Alterna ítems de checklist preventivo y recalcula el porcentaje de avance en tiempo real.
    """
    orden = get_object_or_404(OrdenTrabajo, pk=pk)

    if request.method == 'POST':
        checklist_id = request.POST.get('checklist_id')
        if checklist_id:
            item = get_object_or_404(ChecklistPreventivo, pk=checklist_id, orden=orden)
            item.realizado = not item.realizado
            item.save()
            nuevo_avance = orden.actualizar_avance_desde_checklist()
            messages.success(request, f"Paso '{item.tarea}' actualizado. Avance total recalculado: {nuevo_avance}%.")
            return redirect('orden_detalle', pk=pk)

        nuevo_avance = request.POST.get('porcentaje_avance')
        if nuevo_avance is not None:
            try:
                val = max(0, min(100, int(nuevo_avance)))
                orden.porcentaje_avance = val
                if val == 100:
                    orden.estatus = OrdenTrabajo.EstatusOT.PENDIENTE_VALIDACION
                elif val > 0 and orden.estatus == OrdenTrabajo.EstatusOT.PROGRAMADA:
                    orden.estatus = OrdenTrabajo.EstatusOT.EN_EJECUCION
                orden.save()
                messages.success(request, f"Porcentaje de avance actualizado al {val}%.")
            except ValueError:
                messages.error(request, "Valor de avance inválido.")

    return redirect('orden_detalle', pk=pk)


@login_required
@role_required([User.Role.ADMIN, User.Role.COORDINADOR, User.Role.RESPONSABLE_LICITACIONES])
def ordenes_crear(request):
    """
    Creación exclusiva de Órdenes de Mantenimiento Preventivo (SRS IEEE 830).
    """
    equipos = Equipo.objects.select_related('sede', 'contrato').filter(contrato__activo=True)
    tecnicos = User.objects.filter(role=User.Role.TECNICO)

    if request.method == 'POST':
        equipo_id = request.POST.get('equipo_id')
        tecnico_id = request.POST.get('tecnico_id')
        punto_revision = request.POST.get('punto_revision', 'Mantenimiento Preventivo Semestral Calendarizado')
        hallazgos_iniciales = request.POST.get('hallazgos_iniciales', 'Equipo en operación normal para servicio preventivo de rutina')

        equipo = get_object_or_404(Equipo, pk=equipo_id)
        tecnico = User.objects.filter(pk=tecnico_id).first() if tecnico_id else None

        # Exclusivamente Preventivo
        ot = OrdenTrabajo.objects.create(
            tipo_servicio=OrdenTrabajo.TipoMantenimiento.PREVENTIVO,
            equipo=equipo,
            coordinador=request.user if request.user.role == User.Role.COORDINADOR else None,
            tecnico_asignado=tecnico,
            estatus=OrdenTrabajo.EstatusOT.ASIGNADA if tecnico else OrdenTrabajo.EstatusOT.PROGRAMADA,
            diagnostico_preliminar=limpiar_saltos(punto_revision),
            causa_raiz=limpiar_saltos(hallazgos_iniciales),
            trabajo_realizado='1. Desconexión de energía con pulsera antiestática.\n2. Soplado de filtros y disipadores.\n3. Limpieza de pines de RAM con goma blanda y dieléctrico.\n4. Renovación de pasta térmica.\n5. Ejecución de TRIM en SSD y limpieza de temporales.',
            observaciones_recomendaciones='- Mantener el equipo a 15 cm de muros para asegurar flujo de aire.\n- Próximo mantenimiento preventivo programado en 6 meses.',
            porcentaje_avance=15 if tecnico else 0,
            domicilio_laboratorio='Calle Principal S/N, Parque Industrial Tecnológico, Taller Central TI',
            telefono_extension_tecnico=tecnico.phone if (tecnico and tecnico.phone) else 'Ext. 104',
            telefono_whatsapp_cliente=equipo.sede.telefono_contacto if (equipo.sede and equipo.sede.telefono_contacto) else ''
        )

        # Pre-cargar el checklist preventivo
        pasos_preventivos = [
            (ChecklistPreventivo.CategoriaChecklist.SEGURIDAD, 'Mesa de trabajo aislante y pulsera antiestática colocada a tierra'),
            (ChecklistPreventivo.CategoriaChecklist.SEGURIDAD, 'Desconexión total de energía eléctrica y periféricos'),
            (ChecklistPreventivo.CategoriaChecklist.HARDWARE_FISICO, 'Retiro de paneles y lavado/secado de filtros de polvo'),
            (ChecklistPreventivo.CategoriaChecklist.HARDWARE_FISICO, 'Soplado con aire a presión en disipador y ventiladores sin forzar aspas'),
            (ChecklistPreventivo.CategoriaChecklist.HARDWARE_FISICO, 'Remoción de residuos en tarjeta madre con brocha suave'),
            (ChecklistPreventivo.CategoriaChecklist.HARDWARE_FISICO, 'Limpieza de contactos dorados de RAM con goma blanda y dieléctrico'),
            (ChecklistPreventivo.CategoriaChecklist.HARDWARE_FISICO, 'Renovación de pasta térmica disipadora en procesador (CPU)'),
            (ChecklistPreventivo.CategoriaChecklist.HARDWARE_FISICO, 'Limpieza externa de periféricos (sin abrir monitor por alta tensión)'),
            (ChecklistPreventivo.CategoriaChecklist.HARDWARE_FISICO, 'Peinado y sujeción de cables con bridas plásticas'),
            (ChecklistPreventivo.CategoriaChecklist.SOFTWARE_LOGICO, 'Instalación de actualizaciones de SO, parches y controladores'),
            (ChecklistPreventivo.CategoriaChecklist.SOFTWARE_LOGICO, 'Liberación de espacio en disco (temporales y caché)'),
            (ChecklistPreventivo.CategoriaChecklist.SOFTWARE_LOGICO, 'Optimización TRIM en SSD / Desfragmentación en HDD'),
            (ChecklistPreventivo.CategoriaChecklist.SOFTWARE_LOGICO, 'Escaneo integral con antivirus actualizado'),
            (ChecklistPreventivo.CategoriaChecklist.SOFTWARE_LOGICO, 'Depuración de programas de inicio y respaldo de archivos críticos'),
        ]
        for cat, tarea in pasos_preventivos:
            ChecklistPreventivo.objects.create(orden=ot, categoria=cat, tarea=tarea, realizado=False)

        messages.success(request, f"✓ ¡Orden Preventiva {ot.numero_orden} generada exitosamente con compromiso SLA contractual!")
        return redirect('orden_detalle', pk=ot.id)

    return render(request, 'maintenance/ordenes_crear.html', {
        'equipos': equipos,
        'tecnicos': tecnicos,
    })
