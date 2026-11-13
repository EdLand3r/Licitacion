from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from apps.authentication.models import User


def role_required(allowed_roles, redirect_url='unauthorized'):
    """
    Decorador para proteger rutas en base al rol del usuario autenticado (RBAC).
    Si el usuario no tiene uno de los roles permitidos, se redirige a /unauthorized/
    o a la ruta especificada con un mensaje de alerta.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')

            # El superusuario o ADMIN tiene acceso a todas las rutas
            if request.user.is_superuser or request.user.role == User.Role.ADMIN:
                return view_func(request, *args, **kwargs)

            # Verificar si el rol del usuario está dentro de los permitidos
            if request.user.role in allowed_roles:
                return view_func(request, *args, **kwargs)

            # Acceso denegado: notificar y redirigir
            messages.error(
                request,
                f"Acceso restringido: Su rol actual ({request.user.get_role_display()}) no cuenta con permisos para acceder a este módulo."
            )
            return redirect(redirect_url)

        return _wrapped_view
    return decorator
