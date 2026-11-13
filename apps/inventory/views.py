from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from apps.authentication.decorators import role_required
from apps.authentication.models import User
from .models import Equipo


@login_required
@role_required([User.Role.ADMIN, User.Role.COORDINADOR, User.Role.TECNICO, User.Role.RESPONSABLE_LICITACIONES, User.Role.ENLACE])
def inventario_lista(request):
    equipos_qs = (
        Equipo.objects
        .select_related('especificaciones', 'sede', 'contrato')
        .all()
    )
    # Regla RBAC para Enlace de la Dependencia: ver sólo equipos de sus sedes asignadas
    if request.user.role == User.Role.ENLACE:
        equipos_qs = equipos_qs.filter(sede__enlace_responsable=request.user)

    return render(request, 'inventory/equipo_lista.html', {'equipos': equipos_qs})
