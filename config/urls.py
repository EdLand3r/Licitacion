from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect

from apps.authentication.views import dashboard_view, unauthorized_view, auditoria_view
from apps.maintenance.views import (
    ordenes_lista,
    orden_detalle,
    ordenes_crear,
    orden_actualizar_avance,
    solicitar_insumo_ot,
    gestionar_solicitud_insumo,
    reasignar_tecnico_ot,
)
from apps.inventory.views import inventario_lista
from apps.warehouse.views import (
    almacen_lista,
    insumos_tecnicos_view,
    dotar_insumo_tecnico,
    devolver_insumo_tecnico,
    registrar_consumo_insumo,
)
from apps.contracts.views import (
    contratos_lista,
    licitacion_crear,
    licitacion_detalle,
    licitacion_asignar_tecnico,
    licitacion_desasignar_tecnico,
    licitacion_reservar_insumo,
    licitacion_cargar_equipos_csv,
)

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

    # Módulo de Órdenes de Trabajo y Mantenimiento Preventivo (P4 - P7, P9)
    path('ordenes/', ordenes_lista, name='ordenes_lista'),
    path('ordenes/<int:pk>/', orden_detalle, name='orden_detalle'),
    path('ordenes/<int:pk>/avance/', orden_actualizar_avance, name='orden_actualizar_avance'),
    path('ordenes/nueva/', ordenes_crear, name='ordenes_crear'),
    path('ordenes/<int:pk>/solicitar-insumo/', solicitar_insumo_ot, name='solicitar_insumo_ot'),
    path('ordenes/solicitud-insumo/<int:solicitud_id>/gestionar/', gestionar_solicitud_insumo, name='gestionar_solicitud_insumo'),
    path('ordenes/<int:pk>/reasignar-tecnico/', reasignar_tecnico_ot, name='reasignar_tecnico_ot'),

    # Módulo de Inventario y Arquitectura de Computadoras (P3)
    path('inventario/', inventario_lista, name='inventario_lista'),

    # Módulo de Refacciones, Auditoría e Insumos Técnicos
    path('almacen/', almacen_lista, name='almacen_lista'),
    path('refacciones/', almacen_lista, name='refacciones_alias'),
    path('auditoria/', auditoria_view, name='auditoria_view'),
    path('insumos-tecnicos/', insumos_tecnicos_view, name='insumos_tecnicos'),
    path('insumos-tecnicos/dotar/', dotar_insumo_tecnico, name='dotar_insumo_tecnico'),
    path('insumos-tecnicos/devolver/', devolver_insumo_tecnico, name='devolver_insumo_tecnico'),
    path('insumos-tecnicos/consumir/', registrar_consumo_insumo, name='registrar_consumo_insumo'),

    # Módulo de Licitaciones y Contratos SLA (P2)
    path('contratos/', contratos_lista, name='contratos_lista'),
    path('contratos/nueva/', licitacion_crear, name='licitacion_crear'),
    path('contratos/<int:pk>/', licitacion_detalle, name='licitacion_detalle'),
    path('contratos/<int:pk>/tecnicos/asignar/', licitacion_asignar_tecnico, name='licitacion_asignar_tecnico'),
    path('contratos/<int:pk>/tecnicos/<int:tecnico_id>/desasignar/', licitacion_desasignar_tecnico, name='licitacion_desasignar_tecnico'),
    path('contratos/<int:pk>/insumos/reservar/', licitacion_reservar_insumo, name='licitacion_reservar_insumo'),
    path('contratos/<int:pk>/equipos/csv/', licitacion_cargar_equipos_csv, name='licitacion_cargar_equipos_csv'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
