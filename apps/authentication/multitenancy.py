from django.db.models import Q
from apps.authentication.models import User
from apps.contracts.models import Contrato, Sede
from apps.inventory.models import Equipo
from apps.maintenance.models import OrdenTrabajo


def get_user_sedes(user):
    """
    Retorna el QuerySet de Sedes permitidas para el usuario autenticado.
    - Superusuario / Admin / Coordinador: Todas las sedes.
    - Rol Enlace (Cliente): Únicamente sus sedes asignadas o de su dependencia.
    - Rol Técnico: Sedes de las licitaciones donde está asignado.
    """
    if not user.is_authenticated:
        return Sede.objects.none()

    if user.is_superuser:
        return Sede.objects.all()

    if user.role == User.Role.ENLACE:
        qs = Sede.objects.filter(enlace_responsable=user)
        if not qs.exists() and user.dependencia_o_empresa:
            qs = Sede.objects.filter(contrato__dependencia_cliente__icontains=user.dependencia_o_empresa)
        return qs

    if user.role == User.Role.TECNICO:
        return Sede.objects.filter(contrato__tecnicos_asignados=user).distinct()

    return Sede.objects.all()


def get_user_contratos(user):
    """
    Retorna los Contratos y Licitaciones permitidos para el usuario.
    - Rol Cliente (Enlace): Solo contratos vinculados a sus sedes o dependencia.
    - Rol Técnico: Licitaciones donde el técnico está asignado.
    - Otros roles autorizados: Todos los contratos.
    """
    if not user.is_authenticated:
        return Contrato.objects.none()

    if user.is_superuser:
        return Contrato.objects.all()

    if user.role == User.Role.ENLACE:
        sedes = get_user_sedes(user)
        return Contrato.objects.filter(sedes__in=sedes).distinct()

    if user.role == User.Role.TECNICO:
        return Contrato.objects.filter(tecnicos_asignados=user).distinct()

    return Contrato.objects.all()


def get_user_equipos(user):
    """
    Retorna los Equipos de Cómputo permitidos.
    - Rol Cliente (Enlace): Solo equipos amparados en sus sedes/licitación.
    - Rol Técnico: Equipos de licitaciones asignadas o con OTs asignadas al técnico.
    - Otros roles: Todo el inventario.
    """
    if not user.is_authenticated:
        return Equipo.objects.none()

    if user.is_superuser:
        return Equipo.objects.all()

    if user.role == User.Role.ENLACE:
        sedes = get_user_sedes(user)
        return Equipo.objects.filter(sede__in=sedes)

    if user.role == User.Role.TECNICO:
        return Equipo.objects.filter(
            Q(contrato__tecnicos_asignados=user) |
            Q(ordenes_trabajo__tecnico_asignado=user)
        ).distinct()

    return Equipo.objects.all()


def get_user_ordenes(user):
    """
    Retorna las Órdenes de Trabajo permitidas:
    - Rol Cliente (Enlace): Solo órdenes correspondientes a equipos de sus sedes/licitación.
    - Rol Técnico: Aislamiento estricto, únicamente las órdenes donde está asignado como técnico.
    - Otros roles: Todas las órdenes de trabajo.
    """
    if not user.is_authenticated:
        return OrdenTrabajo.objects.none()

    if user.is_superuser:
        return OrdenTrabajo.objects.all()

    if user.role == User.Role.ENLACE:
        sedes = get_user_sedes(user)
        return OrdenTrabajo.objects.filter(equipo__sede__in=sedes)

    if user.role == User.Role.TECNICO:
        return OrdenTrabajo.objects.filter(tecnico_asignado=user)

    return OrdenTrabajo.objects.all()


def enlace_puede_acceder_ot(user, orden):
    """
    Verifica si un usuario Enlace de la Dependencia tiene permiso para consultar
    o interactuar con una orden de trabajo específica.
    """
    if not user.is_authenticated:
        return False

    if user.is_superuser or user.role != User.Role.ENLACE:
        return True

    sedes_permitidas_ids = get_user_sedes(user).values_list('id', flat=True)
    return orden.equipo.sede_id in sedes_permitidas_ids
