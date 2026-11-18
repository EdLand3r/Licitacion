from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db.models import Q
from datetime import timedelta

from apps.authentication.decorators import role_required
from apps.authentication.models import User
from apps.authentication.multitenancy import (
    get_user_sedes,
    get_user_contratos,
    get_user_equipos,
    get_user_ordenes,
    enlace_puede_acceder_ot,
)
from apps.inventory.models import Equipo
from apps.contracts.models import Contrato, validar_disponibilidad_tecnico
from apps.warehouse.models import Refaccion
from .models import (
    OrdenTrabajo,
    SolicitudServicio,
    ChecklistPreventivo,
    FirmaDigitalOT,
    SolicitudRefaccionOT,
)


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
    - Búsqueda directa por Folio de Licitación y Folio de OT.
    - Filtro por Técnico de mantenimiento y Licitación / Contrato.
    - Agrupación por Licitación como organización principal.
    - Aislamiento estricto: Técnico solo ve sus propias órdenes; Cliente solo sus sedes.
    """
    query = request.GET.get('q', '').strip()
    licitacion_folio = request.GET.get('licitacion_folio', '').strip()
    tecnico_id = request.GET.get('tecnico', '').strip()
    licitacion_id = request.GET.get('licitacion', '').strip()
    agrupar = request.GET.get('agrupar', 'licitacion').strip()  # Predeterminado agrupado

    ordenes_qs = (
        get_user_ordenes(request.user)
        .filter(tipo_servicio=OrdenTrabajo.TipoMantenimiento.PREVENTIVO)
        .select_related('equipo', 'equipo__sede', 'equipo__contrato', 'tecnico_asignado', 'coordinador')
    )

    # Restricción RBAC estricta: Cada técnico ve ÚNICA Y EXCLUSIVAMENTE sus órdenes
    if request.user.role == User.Role.TECNICO:
        ordenes_qs = ordenes_qs.filter(tecnico_asignado=request.user)

    # Búsqueda por Folio de Licitación directo
    if licitacion_folio:
        ordenes_qs = ordenes_qs.filter(
            Q(equipo__contrato__numero_licitacion__icontains=licitacion_folio) |
            Q(equipo__contrato__numero_contrato__icontains=licitacion_folio)
        )

    # Búsqueda general
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

    # Filtrado por Técnico
    if tecnico_id and request.user.role != User.Role.TECNICO:
        ordenes_qs = ordenes_qs.filter(tecnico_asignado_id=tecnico_id)

    # Filtrado por Licitación / Contrato
    if licitacion_id:
        ordenes_qs = ordenes_qs.filter(equipo__contrato_id=licitacion_id)

    # Agrupación por Licitación como organización principal
    contratos_todos = get_user_contratos(request.user)
    ordenes_agrupadas = None
    es_agrupado = agrupar in ['1', 'licitacion', 'true']

    if es_agrupado:
        ordenes_agrupadas = []
        for c in contratos_todos:
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

    context = {
        'ordenes': ordenes_qs,
        'ordenes_agrupadas': ordenes_agrupadas,
        'agrupado': es_agrupado,
        'tecnicos': tecnicos,
        'contratos': contratos_todos,
        'query': query,
        'licitacion_folio': licitacion_folio,
        'tecnico_seleccionado': tecnico_id,
        'licitacion_seleccionada': licitacion_id,
    }
    return render(request, 'maintenance/ordenes_lista.html', context)


@login_required
def orden_detalle(request, pk):
    """
    Vista del Reporte de Mantenimiento Preventivo:
    - Incluye sección estructurada de DATOS DE LA LICITACIÓN.
    - Permite reasignar técnico (con validación de agenda) a Coordinadores y Admins.
    - Permite al técnico o coordinador solicitar insumos para la orden.
    - Aislamiento estricto: Técnico solo puede ver su propia orden asignada.
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

    # Restricción RBAC y Aislamiento por Técnico: Prohibido ver órdenes ajenas
    if request.user.role == User.Role.TECNICO:
        if orden.tecnico_asignado != request.user:
            messages.error(request, "Acceso restringido: Esta orden de trabajo está asignada a otro técnico.")
            return render(request, 'unauthorized.html', {
                'mensaje': 'Acceso Denegado: Solo cuenta con autorización para visualizar órdenes asignadas a su propio usuario.'
            }, status=403)

    # Verificación de seguridad Multi-tenancy para Enlace
    if request.user.role == User.Role.ENLACE:
        if not enlace_puede_acceder_ot(request.user, orden):
            messages.error(request, "Acceso no autorizado: No cuenta con permisos para consultar órdenes de otra dependencia.")
            return render(request, 'unauthorized.html', {
                'mensaje': 'Acceso Restringido: La orden solicitada pertenece a una dependencia o licitación ajena a su usuario.'
            }, status=403)

    # PROCESAMIENTO DE ACCIONES EN EL REPORTE (POST)
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

        # Acción 2: Edición manual de campos técnicos (Técnico asignado, Coordinador o Admin)
        if request.user.role in [User.Role.ADMIN, User.Role.COORDINADOR, User.Role.TECNICO]:
            orden.domicilio_laboratorio = request.POST.get('domicilio_laboratorio', orden.domicilio_laboratorio)
            orden.telefono_extension_tecnico = request.POST.get('telefono_extension_tecnico', orden.telefono_extension_tecnico)
            orden.telefono_whatsapp_cliente = request.POST.get('telefono_whatsapp_cliente', orden.telefono_whatsapp_cliente)

            orden.diagnostico_preliminar = limpiar_saltos(request.POST.get('diagnostico_preliminar', orden.diagnostico_preliminar))
            orden.causa_raiz = limpiar_saltos(request.POST.get('causa_raiz', orden.causa_raiz))
            orden.trabajo_realizado = limpiar_saltos(request.POST.get('trabajo_realizado', orden.trabajo_realizado))
            orden.observaciones_recomendaciones = limpiar_saltos(request.POST.get('observaciones_recomendaciones', orden.observaciones_recomendaciones))

            avance_val = request.POST.get('porcentaje_avance')
            if avance_val is not None:
                try:
                    orden.porcentaje_avance = max(0, min(100, int(avance_val)))
                except ValueError:
                    pass

            orden.save()
            messages.success(request, "✓ ¡Cambios del Reporte Preventivo guardados correctamente!")
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
    puede_reasignar_tecnico = request.user.role in [User.Role.ADMIN, User.Role.COORDINADOR]

    # Insumos y solicitudes para la orden
    insumos_disponibles = Refaccion.objects.filter(stock_actual__gt=0)
    solicitudes_insumos = orden.refacciones_usadas.select_related('refaccion').all()
    tecnicos_todos = User.objects.filter(role=User.Role.TECNICO)

    context = {
        'orden': orden,
        'puede_editar': puede_editar,
        'puede_firmar_cliente': puede_firmar_cliente,
        'puede_reasignar_tecnico': puede_reasignar_tecnico,
        'insumos_disponibles': insumos_disponibles,
        'solicitudes_insumos': solicitudes_insumos,
        'tecnicos_todos': tecnicos_todos,
    }
    return render(request, 'maintenance/orden_detalle.html', context)


@login_required
@role_required([User.Role.ADMIN, User.Role.COORDINADOR, User.Role.TECNICO])
def solicitar_insumo_ot(request, pk):
    """
    Permite al técnico (o coordinador) enviar una solicitud de insumo/refacción
    para ser utilizada en el servicio de la orden de trabajo.
    """
    orden = get_object_or_404(OrdenTrabajo, pk=pk)
    if request.user.role == User.Role.TECNICO and orden.tecnico_asignado != request.user:
        return render(request, 'unauthorized.html', status=403)

    if request.method == 'POST':
        refaccion_id = request.POST.get('refaccion_id')
        cantidad_str = request.POST.get('cantidad', '1')

        refaccion = get_object_or_404(Refaccion, pk=refaccion_id)
        try:
            cantidad = int(cantidad_str)
            if cantidad <= 0:
                raise ValueError
        except ValueError:
            messages.error(request, "Cantidad inválida.")
            return redirect('orden_detalle', pk=pk)

        SolicitudRefaccionOT.objects.create(
            orden=orden,
            refaccion=refaccion,
            cantidad=cantidad,
            estatus=SolicitudRefaccionOT.EstatusSolicitudRefaccion.SOLICITADA
        )
        messages.success(request, f"✓ Solicitud de {cantidad} {refaccion.unidad_medida}(s) de '{refaccion.nombre}' registrada para aprobación de Almacén/Coordinación.")

    return redirect('orden_detalle', pk=pk)


@login_required
@role_required([User.Role.ADMIN, User.Role.COORDINADOR, User.Role.ALMACEN])
def gestionar_solicitud_insumo(request, solicitud_id):
    """
    Aprobación o rechazo de solicitudes de insumos realizadas por los técnicos.
    Al aprobar, descuenta existencias operativas del inventario.
    """
    solicitud = get_object_or_404(SolicitudRefaccionOT, pk=solicitud_id)

    if request.method == 'POST':
        decision = request.POST.get('decision')
        if decision == 'aprobar':
            if solicitud.refaccion.stock_actual >= solicitud.cantidad:
                solicitud.refaccion.stock_actual -= solicitud.cantidad
                solicitud.refaccion.save(update_fields=['stock_actual'])
                solicitud.estatus = SolicitudRefaccionOT.EstatusSolicitudRefaccion.SURTIDA
                solicitud.despachado_en = timezone.now()
                solicitud.save()
                messages.success(request, f"✓ Insumo '{solicitud.refaccion.nombre}' aprobado y despachado.")
            else:
                messages.error(request, f"Existencia insuficiente en almacén (Disponible: {solicitud.refaccion.stock_actual}).")
        elif decision == 'rechazar':
            solicitud.estatus = SolicitudRefaccionOT.EstatusSolicitudRefaccion.RECHAZADA_AGOTADA
            solicitud.save()
            messages.warning(request, f"Solicitud de '{solicitud.refaccion.nombre}' rechazada.")

    return redirect('orden_detalle', pk=solicitud.orden_id)


@login_required
@role_required([User.Role.ADMIN, User.Role.COORDINADOR])
def reasignar_tecnico_ot(request, pk):
    """
    Reasignación de Técnico en una Orden de Trabajo con validación estricta de disponibilidad
    y prevención de traslapes en fechas de servicio.
    """
    orden = get_object_or_404(OrdenTrabajo, pk=pk)

    if request.method == 'POST':
        tecnico_id = request.POST.get('nuevo_tecnico_id')
        if tecnico_id:
            tecnico = get_object_or_404(User, pk=tecnico_id, role=User.Role.TECNICO)
            f_inicio = orden.fecha_inicio_atencion.date() if orden.fecha_inicio_atencion else timezone.now().date()
            f_fin = orden.fecha_estimada_entrega.date() if orden.fecha_estimada_entrega else f_inicio

            disponible, msg_error = validar_disponibilidad_tecnico(
                tecnico, f_inicio, f_fin, licitacion_actual_id=orden.equipo.contrato_id
            )
            if not disponible:
                messages.error(request, msg_error)
                return redirect('orden_detalle', pk=pk)

            orden.tecnico_asignado = tecnico
            if tecnico.phone:
                orden.telefono_extension_tecnico = tecnico.phone
            orden.save(update_fields=['tecnico_asignado', 'telefono_extension_tecnico'])
            messages.success(request, f"✓ Técnico reasignado exitosamente a {tecnico.get_full_name() or tecnico.username}.")
        else:
            orden.tecnico_asignado = None
            orden.save(update_fields=['tecnico_asignado'])
            messages.info(request, "Se ha desasignado al técnico de la orden de trabajo.")

    return redirect('orden_detalle', pk=pk)


@login_required
@role_required([User.Role.ADMIN, User.Role.COORDINADOR, User.Role.TECNICO])
def orden_actualizar_avance(request, pk):
    """
    Alterna ítems de checklist preventivo y recalcula el porcentaje de avance en tiempo real.
    """
    orden = get_object_or_404(OrdenTrabajo, pk=pk)

    # Restricción por técnico
    if request.user.role == User.Role.TECNICO and orden.tecnico_asignado != request.user:
        return render(request, 'unauthorized.html', status=403)

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
@role_required([User.Role.COORDINADOR])
def ordenes_crear(request):
    """
    Creación de Órdenes de Mantenimiento Preventivo:
    - Restricción estricta: Exclusivo para el rol COORDINADOR de Operaciones.
    - Se deniega el acceso a todos los demás roles (incluyendo Técnico, Cliente/Enlace, Almacén, Licitaciones, Admin).
    """
    if request.user.role != User.Role.COORDINADOR and not request.user.is_superuser:
        messages.error(request, "Acceso denegado: Únicamente el Coordinador de Operaciones tiene autorización para dar de alta órdenes de trabajo.")
        return render(request, 'unauthorized.html', status=403)

    equipos = Equipo.objects.filter(contrato__activo=True).select_related('sede', 'contrato')
    tecnicos = User.objects.filter(role=User.Role.TECNICO)

    if request.method == 'POST':
        equipo_id = request.POST.get('equipo_id')
        tecnico_id = request.POST.get('tecnico_id')
        punto_revision = request.POST.get('punto_revision', 'Mantenimiento Preventivo Calendarizado')
        hallazgos_iniciales = request.POST.get('hallazgos_iniciales', 'Equipo en operación normal para servicio de rutina')

        equipo = get_object_or_404(Equipo, pk=equipo_id)

        tecnico = None
        if tecnico_id:
            tecnico = User.objects.filter(pk=tecnico_id, role=User.Role.TECNICO).first()
            if tecnico:
                hoy = timezone.now().date()
                f_estimada = hoy + timedelta(hours=equipo.contrato.sla_horas_solucion)
                disponible, msg_error = validar_disponibilidad_tecnico(
                    tecnico, hoy, f_estimada, licitacion_actual_id=equipo.contrato_id
                )
                if not disponible:
                    messages.error(request, msg_error)
                    return render(request, 'maintenance/ordenes_crear.html', {'equipos': equipos, 'tecnicos': tecnicos})

        ot = OrdenTrabajo.objects.create(
            tipo_servicio=OrdenTrabajo.TipoMantenimiento.PREVENTIVO,
            equipo=equipo,
            coordinador=request.user if request.user.role == User.Role.COORDINADOR else None,
            tecnico_asignado=tecnico,
            estatus=OrdenTrabajo.EstatusOT.ASIGNADA if tecnico else OrdenTrabajo.EstatusOT.PROGRAMADA,
            diagnostico_preliminar=limpiar_saltos(punto_revision),
            causa_raiz=limpiar_saltos(hallazgos_iniciales),
            trabajo_realizado='1. Desconexión de energía con pulsera antiestática.\n2. Soplado de disipadores y ventiladores.\n3. Limpieza de memoria RAM con dieléctrico.\n4. Renovación de pasta térmica.\n5. Optimización del sistema operativo.',
            observaciones_recomendaciones='- Mantener ventilado el área de trabajo.\n- Próximo servicio preventivo en 6 meses.',
            porcentaje_avance=15 if tecnico else 0,
            domicilio_laboratorio='Calle Principal S/N, Parque Industrial Tecnológico, Taller Central TI',
            telefono_extension_tecnico=tecnico.phone if (tecnico and tecnico.phone) else 'Ext. 104',
            telefono_whatsapp_cliente=equipo.sede.telefono_contacto if (equipo.sede and equipo.sede.telefono_contacto) else ''
        )

        # Pre-cargar pasos de checklist preventivo
        pasos_preventivos = [
            (ChecklistPreventivo.CategoriaChecklist.SEGURIDAD, 'Mesa de trabajo aislante y pulsera antiestática colocada a tierra'),
            (ChecklistPreventivo.CategoriaChecklist.SEGURIDAD, 'Desconexión total de energía eléctrica y periféricos'),
            (ChecklistPreventivo.CategoriaChecklist.HARDWARE_FISICO, 'Retiro de paneles y lavado/secado de filtros de polvo'),
            (ChecklistPreventivo.CategoriaChecklist.HARDWARE_FISICO, 'Soplado con aire a presión en disipador y ventiladores sin forzar aspas'),
            (ChecklistPreventivo.CategoriaChecklist.HARDWARE_FISICO, 'Remoción de residuos en tarjeta madre con brocha suave'),
            (ChecklistPreventivo.CategoriaChecklist.HARDWARE_FISICO, 'Limpieza de contactos dorados de RAM con goma blanda y dieléctrico'),
            (ChecklistPreventivo.CategoriaChecklist.HARDWARE_FISICO, 'Renovación de pasta térmica disipadora en procesador (CPU)'),
            (ChecklistPreventivo.CategoriaChecklist.HARDWARE_FISICO, 'Limpieza externa de periféricos y lubricación de ventiladores'),
            (ChecklistPreventivo.CategoriaChecklist.HARDWARE_FISICO, 'Peinado y sujeción de cables con bridas plásticas'),
            (ChecklistPreventivo.CategoriaChecklist.SOFTWARE_LOGICO, 'Instalación de actualizaciones de SO, parches y controladores'),
            (ChecklistPreventivo.CategoriaChecklist.SOFTWARE_LOGICO, 'Liberación de espacio en disco (temporales y caché)'),
            (ChecklistPreventivo.CategoriaChecklist.SOFTWARE_LOGICO, 'Optimización TRIM en SSD / Desfragmentación en HDD'),
            (ChecklistPreventivo.CategoriaChecklist.SOFTWARE_LOGICO, 'Escaneo integral con antivirus actualizado'),
            (ChecklistPreventivo.CategoriaChecklist.SOFTWARE_LOGICO, 'Depuración de programas de inicio y respaldo de archivos críticos'),
        ]
        for cat, tarea in pasos_preventivos:
            ChecklistPreventivo.objects.create(orden=ot, categoria=cat, tarea=tarea, realizado=False)

        messages.success(request, f"✓ ¡Orden Preventiva {ot.numero_orden} generada exitosamente bajo la licitación {equipo.contrato.numero_licitacion}!")
        return redirect('orden_detalle', pk=ot.id)

    return render(request, 'maintenance/ordenes_crear.html', {
        'equipos': equipos,
        'tecnicos': tecnicos,
    })
