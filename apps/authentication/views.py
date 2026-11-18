from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import F, Q
from apps.authentication.decorators import role_required
from apps.authentication.models import User
from apps.authentication.multitenancy import (
    get_user_sedes,
    get_user_contratos,
    get_user_equipos,
    get_user_ordenes,
)
from apps.inventory.models import Equipo
from apps.maintenance.models import OrdenTrabajo, FirmaDigitalOT
from apps.warehouse.models import Refaccion, MovimientoInventario, MovimientoInsumoTecnico


@login_required
def dashboard_view(request):
    """
    Panel de Control Principal con Aislamiento Estricto Multi-tenancy y Filtro por Folio:
    - Rol Enlace (Cliente): Filtra exclusivamente los equipos, órdenes y contratos
      amparados en su propia dependencia / licitación.
    - Rol Técnico: Aislamiento estricto, únicamente visualiza sus propias OTs asignadas.
    - Búsqueda ágil por Folio de Licitación.
    - Enfoque 100% operativo sin referencias financieras ni tarjeta de refacciones.
    """
    es_cliente = request.user.role == User.Role.ENLACE
    es_tecnico = request.user.role == User.Role.TECNICO
    licitacion_folio = request.GET.get('licitacion_folio', '').strip()

    # Equipos filtrados por pertenencia y folio
    equipos_qs = get_user_equipos(request.user)
    if licitacion_folio:
        equipos_qs = equipos_qs.filter(
            Q(contrato__numero_licitacion__icontains=licitacion_folio) |
            Q(contrato__numero_contrato__icontains=licitacion_folio)
        )
    total_equipos = equipos_qs.count()

    # Órdenes de trabajo filtradas
    ots_qs = get_user_ordenes(request.user)
    if licitacion_folio:
        ots_qs = ots_qs.filter(
            Q(equipo__contrato__numero_licitacion__icontains=licitacion_folio) |
            Q(equipo__contrato__numero_contrato__icontains=licitacion_folio)
        )
    ots_activas = ots_qs.exclude(estatus=OrdenTrabajo.EstatusOT.CERRADA_CONFORME)
    total_ots_activas = ots_activas.count()
    ots_preventivas = ots_activas.filter(tipo_servicio=OrdenTrabajo.TipoMantenimiento.PREVENTIVO).count()
    ots_correctivas = ots_activas.filter(tipo_servicio=OrdenTrabajo.TipoMantenimiento.CORRECTIVO).count()

    # Cálculo dinámico de cumplimiento SLA para el tenant
    total_ots_historico = ots_qs.count()
    if total_ots_historico > 0:
        cumplidas_sla = ots_qs.filter(cumplio_sla=True).count()
        sla_porcentaje = f"{int((cumplidas_sla / total_ots_historico) * 100)}%"
    else:
        sla_porcentaje = "100%"

    # Contratos y licitaciones del usuario
    contratos_qs = get_user_contratos(request.user).filter(activo=True)
    if licitacion_folio:
        contratos_qs = contratos_qs.filter(
            Q(numero_licitacion__icontains=licitacion_folio) |
            Q(numero_contrato__icontains=licitacion_folio)
        )
    total_licitaciones_activas = contratos_qs.count()
    es_unica_licitacion = (total_licitaciones_activas <= 1)
    licitacion_activa = contratos_qs.first()

    # Bandeja operativa de órdenes de trabajo filtrada
    ordenes_recientes = (
        ots_qs
        .select_related('equipo', 'equipo__sede', 'equipo__contrato', 'tecnico_asignado')
        .all()[:20]
    )

    context = {
        'es_cliente': es_cliente,
        'es_tecnico': es_tecnico,
        'licitacion_folio': licitacion_folio,
        'total_equipos': total_equipos,
        'total_ots_activas': total_ots_activas,
        'ots_preventivas': ots_preventivas,
        'ots_correctivas': ots_correctivas,
        'sla_porcentaje': sla_porcentaje,
        'total_licitaciones_activas': total_licitaciones_activas,
        'es_unica_licitacion': es_unica_licitacion,
        'licitacion_activa': licitacion_activa,
        'ordenes_recientes': ordenes_recientes,
    }
    return render(request, 'dashboard.html', context)


@login_required
@role_required([User.Role.ADMIN, User.Role.COORDINADOR, User.Role.RESPONSABLE_LICITACIONES])
def auditoria_view(request):
    """
    Vista de Auditoría y Monitoreo reservada estrictamente para roles Administradores y Supervisores.
    El acceso para clientes (Enlace) o no autorizados es bloqueado con 403 Forbidden.
    """
    movimientos_almacen = MovimientoInventario.objects.select_related('refaccion', 'responsable').all()[:30]
    movimientos_kits = MovimientoInsumoTecnico.objects.select_related('tecnico', 'insumo', 'autorizado_por').all()[:30]
    firmas = FirmaDigitalOT.objects.select_related('orden', 'orden__equipo').all()[:20]

    return render(request, 'audit/auditoria.html', {
        'movimientos_almacen': movimientos_almacen,
        'movimientos_kits': movimientos_kits,
        'firmas': firmas,
    })


def unauthorized_view(request):
    """
    Vista protegida de Acceso Denegado por Rol (RBAC / Multi-tenancy 403 Forbidden).
    """
    return render(request, 'unauthorized.html', status=403)


