from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect

from apps.authentication.views import dashboard_view, unauthorized_view
from apps.maintenance.views import ordenes_lista, orden_detalle, ordenes_crear, orden_actualizar_avance
from apps.inventory.views import inventario_lista
from apps.warehouse.views import (
    almacen_lista,
    insumos_tecnicos_view,
    dotar_insumo_tecnico,
    devolver_insumo_tecnico,
    registrar_consumo_insumo,
)
from apps.contracts.views import contratos_lista

urlpatterns = [
    # Panel de Administración de Django
    path('admin/', admin.site.urls),

    # Redirección raíz
    path('', lambda request: redirect('dashboard'), name='root'),

    # Autenticación de Usuarios
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('unauthorized/', unauthorized_view, name='unauthorized'),

    # Dashboard Principal
    path('dashboard/', dashboard_view, name='dashboard'),

    # Módulo de Órdenes de Trabajo y Mantenimiento (P4 - P7, P9)
    path('ordenes/', ordenes_lista, name='ordenes_lista'),
    path('ordenes/<int:pk>/', orden_detalle, name='orden_detalle'),
    path('ordenes/<int:pk>/avance/', orden_actualizar_avance, name='orden_actualizar_avance'),
    path('ordenes/nueva/', ordenes_crear, name='ordenes_crear'),

    # Módulo de Inventario y Arquitectura de Computadoras (P3)
    path('inventario/', inventario_lista, name='inventario_lista'),

    # Módulo de Refacciones y Almacén (P8)
    path('almacen/', almacen_lista, name='almacen_lista'),
    path('insumos-tecnicos/', insumos_tecnicos_view, name='insumos_tecnicos'),
    path('insumos-tecnicos/dotar/', dotar_insumo_tecnico, name='dotar_insumo_tecnico'),
    path('insumos-tecnicos/devolver/', devolver_insumo_tecnico, name='devolver_insumo_tecnico'),
    path('insumos-tecnicos/consumir/', registrar_consumo_insumo, name='registrar_consumo_insumo'),

    # Módulo de Licitaciones y Contratos SLA (P2)
    path('contratos/', contratos_lista, name='contratos_lista'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
