from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import F
from apps.inventory.models import Equipo
from apps.maintenance.models import OrdenTrabajo
from apps.warehouse.models import Refaccion


@login_required
def dashboard_view(request):
    total_equipos = Equipo.objects.count()
    ots_activas = OrdenTrabajo.objects.exclude(estatus=OrdenTrabajo.EstatusOT.CERRADA_CONFORME)
    total_ots_activas = ots_activas.count()
    ots_preventivas = ots_activas.filter(tipo_servicio=OrdenTrabajo.TipoMantenimiento.PREVENTIVO).count()
    ots_correctivas = ots_activas.filter(tipo_servicio=OrdenTrabajo.TipoMantenimiento.CORRECTIVO).count()

    total_refacciones = Refaccion.objects.count()
    stock_bajo = Refaccion.objects.filter(stock_actual__lte=F('stock_minimo_alerta')).count()

    ordenes_recientes = (
        OrdenTrabajo.objects
        .select_related('equipo', 'equipo__sede', 'equipo__contrato', 'tecnico_asignado')
        .all()[:20]
    )

    context = {
        'total_equipos': total_equipos,
        'total_ots_activas': total_ots_activas,
        'ots_preventivas': ots_preventivas,
        'ots_correctivas': ots_correctivas,
        'total_refacciones': total_refacciones,
        'stock_bajo': stock_bajo,
        'ordenes_recientes': ordenes_recientes,
    }
    return render(request, 'dashboard.html', context)


def unauthorized_view(request):
    """
    Vista protegida de Acceso Denegado por Rol (RBAC).
    """
    return render(request, 'unauthorized.html', status=403)

