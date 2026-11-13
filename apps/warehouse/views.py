from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from apps.authentication.decorators import role_required
from apps.authentication.models import User
from .models import Refaccion, MovimientoInventario, AsignacionInsumoTecnico, MovimientoInsumoTecnico


@login_required
@role_required([User.Role.ADMIN, User.Role.ALMACEN, User.Role.COORDINADOR, User.Role.TECNICO])
def almacen_lista(request):
    refacciones = Refaccion.objects.all()
    return render(request, 'warehouse/refaccion_lista.html', {'refacciones': refacciones})


@login_required
@role_required([User.Role.ADMIN, User.Role.COORDINADOR, User.Role.ALMACEN, User.Role.TECNICO])
def insumos_tecnicos_view(request):
    """
    Apartado de Gestión y Control de Insumos por Técnico de Mantenimiento:
    - Permite ver el kit de insumos en posesión de cada técnico.
    - Los técnicos ven su propio inventario de insumos asignados.
    - Almacén, Coordinador y Admin pueden dotar, recibir devoluciones o registrar consumos.
    """
    tecnicos = User.objects.filter(role=User.Role.TECNICO)
    es_tecnico = request.user.role == User.Role.TECNICO

    # Si el usuario es un técnico, se fija su perfil. De lo contrario, se permite seleccionar.
    if es_tecnico:
        tecnico_seleccionado = request.user
    else:
        tecnico_id = request.GET.get('tecnico', '')
        if tecnico_id:
            tecnico_seleccionado = get_object_or_404(User, pk=tecnico_id, role=User.Role.TECNICO)
        else:
            tecnico_seleccionado = tecnicos.first()

    # Insumos asignados al técnico seleccionado
    asignaciones = []
    movimientos = []
    total_piezas_kit = 0
    insumos_bajos = 0

    if tecnico_seleccionado:
        asignaciones = (
            AsignacionInsumoTecnico.objects
            .filter(tecnico=tecnico_seleccionado)
            .select_related('insumo')
            .all()
        )
        movimientos = (
            MovimientoInsumoTecnico.objects
            .filter(tecnico=tecnico_seleccionado)
            .select_related('insumo', 'autorizado_por')
            .all()[:25]
        )
        total_piezas_kit = sum(a.cantidad_disponible for a in asignaciones)
        insumos_bajos = sum(1 for a in asignaciones if a.kit_bajo)

    # Catálogo de insumos en almacén central disponibles para dotar
    insumos_almacen = Refaccion.objects.filter(stock_actual__gt=0)

    context = {
        'tecnicos': tecnicos,
        'tecnico_actual': tecnico_seleccionado,
        'es_tecnico': es_tecnico,
        'asignaciones': asignaciones,
        'movimientos': movimientos,
        'total_piezas_kit': total_piezas_kit,
        'insumos_bajos': insumos_bajos,
        'insumos_almacen': insumos_almacen,
        'puede_dotar': request.user.role in [User.Role.ADMIN, User.Role.COORDINADOR, User.Role.ALMACEN],
    }
    return render(request, 'warehouse/insumos_tecnicos.html', context)


@login_required
@role_required([User.Role.ADMIN, User.Role.COORDINADOR, User.Role.ALMACEN])
def dotar_insumo_tecnico(request):
    """
    Entrega / Dotación de insumos del almacén central al maletín del técnico.
    Descuenta de almacén general y suma a la posesión del técnico.
    """
    if request.method == 'POST':
        tecnico_id = request.POST.get('tecnico_id')
        insumo_id = request.POST.get('insumo_id')
        cantidad_str = request.POST.get('cantidad', '1')
        observaciones = request.POST.get('observaciones', '').strip()

        tecnico = get_object_or_404(User, pk=tecnico_id, role=User.Role.TECNICO)
        insumo = get_object_or_404(Refaccion, pk=insumo_id)

        try:
            cantidad = int(cantidad_str)
            if cantidad <= 0:
                raise ValueError
        except ValueError:
            messages.error(request, "La cantidad a dotar debe ser un número entero positivo.")
            return redirect(f"/insumos-tecnicos/?tecnico={tecnico.id}")

        if insumo.stock_actual < cantidad:
            messages.error(
                request,
                f"Existencia insuficiente en almacén central. Solo hay {insumo.stock_actual} {insumo.unidad_medida}(s) de {insumo.nombre}."
            )
            return redirect(f"/insumos-tecnicos/?tecnico={tecnico.id}")

        # 1. Descontar del almacén central
        insumo.stock_actual -= cantidad
        insumo.save(update_fields=['stock_actual'])

        # 2. Sumar a la posesión del técnico
        asig, _ = AsignacionInsumoTecnico.objects.get_or_create(
            tecnico=tecnico,
            insumo=insumo,
            defaults={'cantidad_disponible': 0}
        )
        asig.cantidad_disponible += cantidad
        asig.save()

        # 3. Registrar auditoría de movimiento
        MovimientoInsumoTecnico.objects.create(
            tecnico=tecnico,
            insumo=insumo,
            tipo_operacion=MovimientoInsumoTecnico.TipoOperacion.DOTACION,
            cantidad=cantidad,
            autorizado_por=request.user,
            observaciones=observaciones or "Dotación regular para kit de mantenimiento preventivo de campo."
        )

        # 4. Registrar salida en auditoría de almacén
        MovimientoInventario.objects.create(
            refaccion=insumo,
            tipo_movimiento=MovimientoInventario.TipoMovimiento.SALIDA_OT,
            cantidad=cantidad,
            responsable=request.user,
            nota=f"Dotación a kit de técnico: {tecnico.get_full_name() or tecnico.username}"
        )

        messages.success(
            request,
            f"✓ Se entregaron con éxito {cantidad} {insumo.unidad_medida}(s) de {insumo.nombre} a {tecnico.get_full_name() or tecnico.username}."
        )
        return redirect(f"/insumos-tecnicos/?tecnico={tecnico.id}")

    return redirect('insumos_tecnicos')


@login_required
@role_required([User.Role.ADMIN, User.Role.COORDINADOR, User.Role.ALMACEN, User.Role.TECNICO])
def devolver_insumo_tecnico(request):
    """
    Devolución de insumos sobrantes desde la posesión del técnico de regreso al almacén central.
    """
    if request.method == 'POST':
        tecnico_id = request.POST.get('tecnico_id')
        insumo_id = request.POST.get('insumo_id')
        cantidad_str = request.POST.get('cantidad', '1')
        observaciones = request.POST.get('observaciones', '').strip()

        tecnico = get_object_or_404(User, pk=tecnico_id, role=User.Role.TECNICO)
        insumo = get_object_or_404(Refaccion, pk=insumo_id)

        try:
            cantidad = int(cantidad_str)
            if cantidad <= 0:
                raise ValueError
        except ValueError:
            messages.error(request, "La cantidad a devolver debe ser mayor a 0.")
            return redirect(f"/insumos-tecnicos/?tecnico={tecnico.id}")

        asig = get_object_or_404(AsignacionInsumoTecnico, tecnico=tecnico, insumo=insumo)

        if asig.cantidad_disponible < cantidad:
            messages.error(
                request,
                f"El técnico solo cuenta con {asig.cantidad_disponible} {insumo.unidad_medida}(s) en su kit."
            )
            return redirect(f"/insumos-tecnicos/?tecnico={tecnico.id}")

        # Descontar de posesión
        asig.cantidad_disponible -= cantidad
        asig.save(update_fields=['cantidad_disponible'])

        # Reintegrar a almacén central
        insumo.stock_actual += cantidad
        insumo.save(update_fields=['stock_actual'])

        # Auditoría
        MovimientoInsumoTecnico.objects.create(
            tecnico=tecnico,
            insumo=insumo,
            tipo_operacion=MovimientoInsumoTecnico.TipoOperacion.DEVOLUCION,
            cantidad=cantidad,
            autorizado_por=request.user,
            observaciones=observaciones or "Devolución de material sobrante a almacén central."
        )

        MovimientoInventario.objects.create(
            refaccion=insumo,
            tipo_movimiento=MovimientoInventario.TipoMovimiento.ENTRADA,
            cantidad=cantidad,
            responsable=request.user,
            nota=f"Reingreso por devolución de técnico: {tecnico.get_full_name() or tecnico.username}"
        )

        messages.success(
            request,
            f"✓ Se reintegraron {cantidad} {insumo.unidad_medida}(s) de {insumo.nombre} al almacén central."
        )
        return redirect(f"/insumos-tecnicos/?tecnico={tecnico.id}")

    return redirect('insumos_tecnicos')


@login_required
@role_required([User.Role.ADMIN, User.Role.COORDINADOR, User.Role.TECNICO])
def registrar_consumo_insumo(request):
    """
    Registra el consumo directo de un insumo desde el kit del técnico para una intervención técnica.
    """
    if request.method == 'POST':
        tecnico_id = request.POST.get('tecnico_id')
        insumo_id = request.POST.get('insumo_id')
        cantidad_str = request.POST.get('cantidad', '1')
        motivo = request.POST.get('motivo', '').strip()

        tecnico = get_object_or_404(User, pk=tecnico_id, role=User.Role.TECNICO)
        insumo = get_object_or_404(Refaccion, pk=insumo_id)

        try:
            cantidad = int(cantidad_str)
            if cantidad <= 0:
                raise ValueError
        except ValueError:
            messages.error(request, "Cantidad inválida.")
            return redirect(f"/insumos-tecnicos/?tecnico={tecnico.id}")

        asig = get_object_or_404(AsignacionInsumoTecnico, tecnico=tecnico, insumo=insumo)

        if asig.cantidad_disponible < cantidad:
            messages.error(
                request,
                f"No cuenta con suficiente cantidad en su kit ({asig.cantidad_disponible} disponibles)."
            )
            return redirect(f"/insumos-tecnicos/?tecnico={tecnico.id}")

        asig.cantidad_disponible -= cantidad
        asig.save(update_fields=['cantidad_disponible'])

        MovimientoInsumoTecnico.objects.create(
            tecnico=tecnico,
            insumo=insumo,
            tipo_operacion=MovimientoInsumoTecnico.TipoOperacion.CONSUMO_MANTENIMIENTO,
            cantidad=cantidad,
            autorizado_por=request.user,
            observaciones=motivo or "Consumo en servicio de mantenimiento preventivo."
        )

        messages.success(
            request,
            f"✓ Se registró el consumo de {cantidad} {insumo.unidad_medida}(s) de {insumo.nombre}."
        )
        return redirect(f"/insumos-tecnicos/?tecnico={tecnico.id}")

    return redirect('insumos_tecnicos')
