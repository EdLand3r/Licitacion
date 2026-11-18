from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.utils import timezone
from datetime import datetime
import csv
import io

from apps.authentication.decorators import role_required
from apps.authentication.models import User
from apps.authentication.multitenancy import get_user_contratos
from apps.inventory.models import Equipo
from apps.warehouse.models import Refaccion
from .models import Contrato, Sede, ReservaInsumoLicitacion, validar_disponibilidad_tecnico


@login_required
@role_required([User.Role.ADMIN, User.Role.RESPONSABLE_LICITACIONES, User.Role.COORDINADOR, User.Role.ENLACE])
def contratos_lista(request):
    """
    Listado y Buscador Integral de Licitaciones y Contratos SLA:
    - Búsqueda directa por Folio de Licitación o Número de Contrato.
    - Filtro por Estatus (Activa, Por vencer, Cerrada).
    - Métricas operativas (Sedes, Equipos, Técnicos, Insumos) sin información monetaria.
    """
    folio_query = request.GET.get('folio', '').strip()
    q_query = request.GET.get('q', '').strip()
    estatus_filter = request.GET.get('estatus', '').strip()

    contratos_qs = (
        get_user_contratos(request.user)
        .prefetch_related('sedes', 'tecnicos_asignados', 'insumos_reservados__insumo', 'equipos')
        .all()
    )

    # Búsqueda directa por Folio
    if folio_query:
        contratos_qs = contratos_qs.filter(
            Q(numero_licitacion__icontains=folio_query) |
            Q(numero_contrato__icontains=folio_query)
        )

    # Búsqueda general
    if q_query:
        contratos_qs = contratos_qs.filter(
            Q(numero_licitacion__icontains=q_query) |
            Q(numero_contrato__icontains=q_query) |
            Q(dependencia_cliente__icontains=q_query) |
            Q(titulo__icontains=q_query) |
            Q(descripcion__icontains=q_query)
        )

    # Filtro por estatus
    if estatus_filter in Contrato.EstatusLicitacion.values:
        contratos_qs = contratos_qs.filter(estatus=estatus_filter)

    puede_crear = request.user.role in [User.Role.ADMIN, User.Role.RESPONSABLE_LICITACIONES, User.Role.COORDINADOR]

    context = {
        'contratos': contratos_qs,
        'folio_query': folio_query,
        'q_query': q_query,
        'estatus_filter': estatus_filter,
        'puede_crear': puede_crear,
    }
    return render(request, 'contracts/contrato_lista.html', context)


@login_required
@role_required([User.Role.ADMIN, User.Role.RESPONSABLE_LICITACIONES, User.Role.COORDINADOR])
def licitacion_crear(request):
    """
    Formulario de Alta y Captura de Datos Generales de la Licitación:
    - Generación automática de Folio único secuencial (ej. LIC-2026-0001).
    - Selección y validación estricta de disponibilidad de técnicos (sin traslapes).
    - Enfoque 100% operativo sin montos monetarios.
    """
    tecnicos = User.objects.filter(role=User.Role.TECNICO)
    hoy = timezone.now().date()
    año_actual = hoy.year
    total_año = Contrato.objects.filter(fecha_inicio__year=año_actual).count() + 1
    folio_sugerido = f"LIC-{año_actual}-{total_año:04d}"

    if request.method == 'POST':
        numero_licitacion = request.POST.get('numero_licitacion', '').strip() or folio_sugerido
        titulo = request.POST.get('titulo', '').strip()
        dependencia_cliente = request.POST.get('dependencia_cliente', '').strip()
        descripcion = request.POST.get('descripcion', '').strip()
        fecha_inicio_str = request.POST.get('fecha_inicio', '').strip()
        fecha_fin_str = request.POST.get('fecha_fin', '').strip()
        sla_respuesta = request.POST.get('sla_horas_respuesta', '4')
        sla_solucion = request.POST.get('sla_horas_solucion', '24')
        sede_nombre = request.POST.get('sede_nombre', '').strip()
        sede_direccion = request.POST.get('sede_direccion', '').strip()
        tecnicos_ids = request.POST.getlist('tecnicos_ids')

        # Validaciones de fecha
        try:
            fecha_inicio = datetime.strptime(fecha_inicio_str, '%Y-%m-%d').date()
            fecha_fin = datetime.strptime(fecha_fin_str, '%Y-%m-%d').date()
            if fecha_fin < fecha_inicio:
                messages.error(request, "La fecha de fin de vigencia debe ser posterior a la fecha de inicio.")
                return render(request, 'contracts/licitacion_crear.html', {'tecnicos': tecnicos, 'folio_sugerido': folio_sugerido})
        except ValueError:
            messages.error(request, "Formato de fechas inválido.")
            return render(request, 'contracts/licitacion_crear.html', {'tecnicos': tecnicos, 'folio_sugerido': folio_sugerido})

        # Validación estricta de disponibilidad de técnicos seleccionados
        tecnicos_a_asignar = []
        for tid in tecnicos_ids:
            tec = User.objects.filter(pk=tid, role=User.Role.TECNICO).first()
            if tec:
                disponible, msg_error = validar_disponibilidad_tecnico(tec, fecha_inicio, fecha_fin)
                if not disponible:
                    messages.error(request, msg_error)
                    return render(request, 'contracts/licitacion_crear.html', {'tecnicos': tecnicos, 'folio_sugerido': folio_sugerido})
                tecnicos_a_asignar.append(tec)

        # Crear Licitación
        contrato = Contrato(
            numero_licitacion=numero_licitacion,
            titulo=titulo or f"Licitación {numero_licitacion} - {dependencia_cliente}",
            dependencia_cliente=dependencia_cliente,
            descripcion=descripcion,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            sla_horas_respuesta=int(sla_respuesta or 4),
            sla_horas_solucion=int(sla_solucion or 24),
            responsable_licitaciones=request.user,
            activo=True
        )
        contrato.save()

        # Asignar técnicos validados
        if tecnicos_a_asignar:
            contrato.tecnicos_asignados.set(tecnicos_a_asignar)

        # Crear sede inicial si fue indicada
        if sede_nombre:
            Sede.objects.create(
                contrato=contrato,
                nombre=sede_nombre,
                direccion=sede_direccion or "Dirección de la dependencia"
            )

        messages.success(request, f"✓ Licitación '{contrato.numero_licitacion}' creada exitosamente.")
        return redirect('licitacion_detalle', pk=contrato.id)

    return render(request, 'contracts/licitacion_crear.html', {
        'tecnicos': tecnicos,
        'folio_sugerido': folio_sugerido,
    })


@login_required
@role_required([User.Role.ADMIN, User.Role.RESPONSABLE_LICITACIONES, User.Role.COORDINADOR, User.Role.ENLACE])
def licitacion_detalle(request, pk):
    """
    Vista de Gestión Integral de la Licitación:
    - Información general operativa y estado SLA.
    - Gestión de Técnicos asignados con control de agenda.
    - Reserva y asignación de insumos del almacén.
    - Inventario de equipos amparados con soporte para importación masiva CSV.
    - Órdenes de trabajo asociadas.
    """
    contrato = get_object_or_404(
        Contrato.objects.prefetch_related(
            'sedes',
            'tecnicos_asignados',
            'insumos_reservados__insumo',
            'equipos__sede',
            'sedes__equipos__ordenes_trabajo'
        ),
        pk=pk
    )

    # Validación multi-tenancy para Enlace
    if request.user.role == User.Role.ENLACE:
        contratos_permitidos_ids = get_user_contratos(request.user).values_list('id', flat=True)
        if contrato.id not in contratos_permitidos_ids:
            messages.error(request, "Acceso no autorizado a esta licitación.")
            return render(request, 'unauthorized.html', status=403)

    tecnicos_todos = User.objects.filter(role=User.Role.TECNICO)
    insumos_almacen = Refaccion.objects.filter(stock_actual__gt=0)
    equipos = Equipo.objects.filter(contrato=contrato).select_related('sede')
    sedes = contrato.sedes.all()

    # Órdenes de trabajo amparadas en esta licitación
    from apps.maintenance.models import OrdenTrabajo
    ordenes = OrdenTrabajo.objects.filter(equipo__contrato=contrato).select_related('equipo', 'tecnico_asignado')

    puede_gestionar = request.user.role in [User.Role.ADMIN, User.Role.RESPONSABLE_LICITACIONES, User.Role.COORDINADOR]

    context = {
        'contrato': contrato,
        'sedes': sedes,
        'equipos': equipos,
        'ordenes': ordenes,
        'tecnicos_todos': tecnicos_todos,
        'insumos_almacen': insumos_almacen,
        'puede_gestionar': puede_gestionar,
    }
    return render(request, 'contracts/licitacion_detalle.html', context)


@login_required
@role_required([User.Role.ADMIN, User.Role.RESPONSABLE_LICITACIONES, User.Role.COORDINADOR])
def licitacion_asignar_tecnico(request, pk):
    """
    Asigna un técnico a la licitación validando previamente que no existan traslapes de fechas.
    """
    contrato = get_object_or_404(Contrato, pk=pk)

    if request.method == 'POST':
        tecnico_id = request.POST.get('tecnico_id')
        tecnico = get_object_or_404(User, pk=tecnico_id, role=User.Role.TECNICO)

        disponible, msg_error = validar_disponibilidad_tecnico(
            tecnico, contrato.fecha_inicio, contrato.fecha_fin, licitacion_actual_id=contrato.id
        )

        if not disponible:
            messages.error(request, msg_error)
            return redirect('licitacion_detalle', pk=pk)

        contrato.tecnicos_asignados.add(tecnico)
        messages.success(request, f"✓ Técnico {tecnico.get_full_name() or tecnico.username} asignado exitosamente a la licitación.")

    return redirect('licitacion_detalle', pk=pk)


@login_required
@role_required([User.Role.ADMIN, User.Role.RESPONSABLE_LICITACIONES, User.Role.COORDINADOR])
def licitacion_desasignar_tecnico(request, pk, tecnico_id):
    """
    Remueve la asignación de un técnico de la licitación.
    """
    contrato = get_object_or_404(Contrato, pk=pk)
    tecnico = get_object_or_404(User, pk=tecnico_id)
    contrato.tecnicos_asignados.remove(tecnico)
    messages.success(request, f"Técnico {tecnico.get_full_name() or tecnico.username} desvinculado de la licitación.")
    return redirect('licitacion_detalle', pk=pk)


@login_required
@role_required([User.Role.ADMIN, User.Role.RESPONSABLE_LICITACIONES, User.Role.COORDINADOR])
def licitacion_reservar_insumo(request, pk):
    """
    Reserva y asigna insumos/refacciones del almacén para la atención de la licitación.
    """
    contrato = get_object_or_404(Contrato, pk=pk)

    if request.method == 'POST':
        insumo_id = request.POST.get('insumo_id')
        cantidad_str = request.POST.get('cantidad', '1')
        notas = request.POST.get('notas', '').strip()

        insumo = get_object_or_404(Refaccion, pk=insumo_id)
        try:
            cantidad = int(cantidad_str)
            if cantidad <= 0:
                raise ValueError
        except ValueError:
            messages.error(request, "La cantidad a reservar debe ser mayor a 0.")
            return redirect('licitacion_detalle', pk=pk)

        reserva, created = ReservaInsumoLicitacion.objects.get_or_create(
            contrato=contrato,
            insumo=insumo,
            defaults={'cantidad_asignada': cantidad, 'notas': notas}
        )
        if not created:
            reserva.cantidad_asignada += cantidad
            if notas:
                reserva.notas = notas
            reserva.save()

        messages.success(request, f"✓ Se reservaron {cantidad} {insumo.unidad_medida}(s) de '{insumo.nombre}' para esta licitación.")

    return redirect('licitacion_detalle', pk=pk)


@login_required
@role_required([User.Role.ADMIN, User.Role.RESPONSABLE_LICITACIONES, User.Role.COORDINADOR])
def licitacion_cargar_equipos_csv(request, pk):
    """
    Importación masiva de equipos mediante archivo CSV/Excel para una licitación.
    Formato esperado de encabezados:
    numero_serie,marca,modelo,tipo_equipo,area,sede
    """
    contrato = get_object_or_404(Contrato, pk=pk)

    if request.method == 'POST' and request.FILES.get('archivo_csv'):
        archivo = request.FILES['archivo_csv']
        if not archivo.name.endswith(('.csv', '.txt')):
            messages.error(request, "Por favor seleccione un archivo en formato CSV válido.")
            return redirect('licitacion_detalle', pk=pk)

        try:
            decoded_file = archivo.read().decode('utf-8-sig')
            io_string = io.StringIO(decoded_file)
            reader = csv.DictReader(io_string)

            sede_default = contrato.sedes.first()
            if not sede_default:
                sede_default = Sede.objects.create(
                    contrato=contrato,
                    nombre='Sede Principal',
                    direccion='Dirección central de la dependencia'
                )

            creados = 0
            omitidos = 0

            for row in reader:
                # Limpiar llaves a minúsculas
                data = {k.strip().lower(): v.strip() for k, v in row.items() if k}
                serie = data.get('numero_serie') or data.get('serie') or data.get('serial')
                if not serie:
                    continue

                marca = data.get('marca', 'Genérica')
                modelo = data.get('modelo', 'Estándar')
                tipo = data.get('tipo_equipo', 'DESKTOP').upper()
                if tipo not in Equipo.TipoEquipo.values:
                    tipo = Equipo.TipoEquipo.DESKTOP
                area = data.get('area', '')
                sede_nombre = data.get('sede', '')

                sede_destino = sede_default
                if sede_nombre:
                    sede_destino, _ = Sede.objects.get_or_create(
                        contrato=contrato,
                        nombre=sede_nombre,
                        defaults={'direccion': sede_default.direccion}
                    )

                equipo, created = Equipo.objects.get_or_create(
                    numero_serie=serie,
                    defaults={
                        'contrato': contrato,
                        'sede': sede_destino,
                        'marca': marca,
                        'modelo': modelo,
                        'tipo_equipo': tipo,
                        'area_o_departamento': area,
                    }
                )
                if created:
                    creados += 1
                else:
                    omitidos += 1

            messages.success(request, f"✓ Carga masiva completada: {creados} equipos registrados con éxito ({omitidos} omitidos por serie duplicada).")

        except Exception as e:
            messages.error(request, f"Error al procesar el archivo CSV: {str(e)}")

    return redirect('licitacion_detalle', pk=pk)
