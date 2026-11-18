from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from apps.authentication.decorators import role_required
from apps.authentication.models import User
from apps.authentication.multitenancy import get_user_equipos
from .models import Equipo


@login_required
@role_required([User.Role.ADMIN, User.Role.COORDINADOR, User.Role.TECNICO, User.Role.RESPONSABLE_LICITACIONES, User.Role.ENLACE])
def inventario_lista(request):
    """
    Inventario de Equipos de Cómputo con aislamiento multi-tenancy:
    El Enlace de la Dependencia solo consulta en modo lectura los equipos amparados en su licitación.
    """
    equipos_qs = (
        get_user_equipos(request.user)
        .select_related('especificaciones', 'sede', 'contrato')
    )
    return render(request, 'inventory/equipo_lista.html', {'equipos': equipos_qs})

