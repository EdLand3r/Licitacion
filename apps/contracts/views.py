from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from apps.authentication.decorators import role_required
from apps.authentication.models import User
from .models import Contrato


@login_required
@role_required([User.Role.ADMIN, User.Role.RESPONSABLE_LICITACIONES, User.Role.COORDINADOR])
def contratos_lista(request):
    contratos = Contrato.objects.prefetch_related('sedes__enlace_responsable').all()
    return render(request, 'contracts/contrato_lista.html', {'contratos': contratos})
