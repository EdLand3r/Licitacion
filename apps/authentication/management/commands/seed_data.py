from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta, date
from apps.contracts.models import Contrato, Sede
from apps.inventory.models import Equipo, EspecificacionHardware
from apps.warehouse.models import Refaccion, MovimientoInventario, AsignacionInsumoTecnico, MovimientoInsumoTecnico
from apps.maintenance.models import (
    SolicitudServicio,
    OrdenTrabajo,
    ChecklistPreventivo,
    SolicitudRefaccionOT,
    FirmaDigitalOT,
)

User = get_user_model()


class Command(BaseCommand):
    help = 'Inicializa usuarios (SRS IEEE 830), contratos, equipos, refacciones y órdenes de prueba'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.NOTICE("Creando usuarios del sistema (SRS IEEE 830)..."))

        # 1. Administrador del sistema
        admin_user, _ = User.objects.get_or_create(
            username='admin',
            defaults={
                'first_name': 'Juan Edward',
                'last_name': 'Landeros Vazquez',
                'email': 'edwardLanderos@gmail.com',
                'role': User.Role.ADMIN,
                'is_staff': True,
                'is_superuser': True,
                'cargo': 'Administrador General de Sistemas'
            }
        )
        admin_user.set_password('admin123')
        admin_user.save()

        # 2. Responsable de licitaciones
        lic_user, _ = User.objects.get_or_create(
            username='licitaciones',
            defaults={
                'first_name': 'Carlos',
                'last_name': 'Mendoza Peña',
                'email': 'licitaciones@spartanpc.local',
                'role': User.Role.RESPONSABLE_LICITACIONES,
                'is_staff': True,
                'cargo': 'Responsable Jurídico y Licitaciones'
            }
        )
        lic_user.set_password('licitaciones123')
        lic_user.save()

        # 3. Coordinador de mantenimiento
        coord_user, _ = User.objects.get_or_create(
            username='coordinador',
            defaults={
                'first_name': 'Leonardo',
                'last_name': 'Cruz Navarrete',
                'email': 'coordinador@spartanpc.local',
                'role': User.Role.COORDINADOR,
                'is_staff': True,
                'cargo': 'Coordinador General de Mantenimiento'
            }
        )
        coord_user.set_password('coordinador123')
        coord_user.save()

        # 4. Técnicos de mantenimiento (2 técnicos para pruebas de búsqueda)
        tec_user, _ = User.objects.get_or_create(
            username='tecnico',
            defaults={
                'first_name': 'Michel Lizbeth',
                'last_name': 'Morales Gómez',
                'email': 'michel.morales@spartanpc.local',
                'role': User.Role.TECNICO,
                'phone': '614-987-6543 Ext. 104',
                'cargo': 'Técnico Especialista en Hardware y Redes'
            }
        )
        tec_user.set_password('tecnico123')
        tec_user.save()

        tec2_user, _ = User.objects.get_or_create(
            username='tecnico2',
            defaults={
                'first_name': 'Cesar Alejandro',
                'last_name': 'Lozano Guzmán',
                'email': 'CesarAlejandroGuzman@gmail.com',
                'role': User.Role.TECNICO,
                'phone': '614-987-6543 Ext. 108',
                'cargo': 'Técnico de Campo Senior'
            }
        )
        tec2_user.set_password('tecnico123')
        tec2_user.save()

        # 5. Enlace de la dependencia (Cliente ITSE)
        enlace_user, _ = User.objects.get_or_create(
            username='enlace',
            defaults={
                'first_name': 'Iván Eduardo',
                'last_name': 'Molina Rodríguez',
                'email': 'enlace.itse@itse.edu.mx',
                'role': User.Role.ENLACE,
                'phone': '982-123-4567',
                'dependencia_o_empresa': 'Instituto Tecnológico Superior de Escárcega (ITSE)',
                'cargo': 'Enlace de Recursos Materiales y TI'
            }
        )
        enlace_user.dependencia_o_empresa = 'Instituto Tecnológico Superior de Escárcega (ITSE)'
        enlace_user.set_password('enlace123')
        enlace_user.save()

        # 5b. Enlace de la dependencia (Cliente SEDUC Campeche para pruebas de aislamiento)
        enlace_seduc_user, _ = User.objects.get_or_create(
            username='enlace_seduc',
            defaults={
                'first_name': 'Patricia',
                'last_name': 'Canto Pech',
                'email': 'patricia.canto@seduc.campeche.gob.mx',
                'role': User.Role.ENLACE,
                'phone': '981-811-2233 Ext. 102',
                'dependencia_o_empresa': 'Secretaría de Educación del Estado de Campeche (SEDUC)',
                'cargo': 'Jefa de Departamento de Informática y Cómputo'
            }
        )
        enlace_seduc_user.dependencia_o_empresa = 'Secretaría de Educación del Estado de Campeche (SEDUC)'
        enlace_seduc_user.set_password('enlace123')
        enlace_seduc_user.save()

        # 6. Encargado de almacén
        alm_user, _ = User.objects.get_or_create(
            username='almacen',
            defaults={
                'first_name': 'Roberto',
                'last_name': 'Sánchez Ruiz',
                'email': 'almacen@spartanpc.local',
                'role': User.Role.ALMACEN,
                'cargo': 'Encargado de Control de Refacciones y Almacén'
            }
        )
        alm_user.set_password('almacen123')
        alm_user.save()

        self.stdout.write(self.style.SUCCESS("✓ Usuarios creados con perfiles SRS IEEE 830"))

        # 2. Contratos y Sedes (2 Licitaciones para agrupación)
        self.stdout.write(self.style.NOTICE("Creando Contratos de Licitación para pruebas de agrupación..."))
        contrato_itse, _ = Contrato.objects.get_or_create(
            numero_contrato='CT-ITSE-2026-088',
            defaults={
                'numero_licitacion': 'LIC-ITSE-ESTATAL-2026-01',
                'dependencia_cliente': 'Instituto Tecnológico Superior de Escárcega (ITSE)',
                'descripcion': 'Servicio integral de mantenimiento preventivo semestral y correctivo con refacciones para el parque de cómputo del ITSE.',
                'fecha_inicio': date(2026, 8, 1),
                'fecha_fin': date(2027, 1, 31),
                'sla_horas_respuesta': 4,
                'sla_horas_solucion': 24,
                'penalizacion_por_retraso': 350.00,
                'responsable_licitaciones': lic_user,
                'activo': True
            }
        )

        contrato_seduc, _ = Contrato.objects.get_or_create(
            numero_contrato='CT-SEDUC-2026-015',
            defaults={
                'numero_licitacion': 'LIC-SEDUC-CAMPECHE-2026-04',
                'dependencia_cliente': 'Secretaría de Educación del Estado de Campeche (SEDUC)',
                'descripcion': 'Mantenimiento preventivo y correctivo de servidores y equipos de cómputo para centros educativos estatales.',
                'fecha_inicio': date(2026, 9, 1),
                'fecha_fin': date(2027, 8, 31),
                'sla_horas_respuesta': 2,
                'sla_horas_solucion': 12,
                'penalizacion_por_retraso': 500.00,
                'responsable_licitaciones': lic_user,
                'activo': True
            }
        )

        sede_central, _ = Sede.objects.get_or_create(
            contrato=contrato_itse,
            nombre='Campus Principal - Laboratorios y Docencia',
            defaults={
                'direccion': 'Km 3.5 Carretera Escárcega-Candelaria, Escárcega, Campeche',
                'enlace_responsable': enlace_user,
                'telefono_contacto': '982-123-4567'
            }
        )

        sede_admin, _ = Sede.objects.get_or_create(
            contrato=contrato_itse,
            nombre='Edificio A - Dirección y Servicios Escolares',
            defaults={
                'direccion': 'Km 3.5 Carretera Escárcega-Candelaria, Planta Alta',
                'enlace_responsable': enlace_user,
                'telefono_contacto': '982-123-4568'
            }
        )

        sede_seduc, _ = Sede.objects.get_or_create(
            contrato=contrato_seduc,
            nombre='Complejo Administrativo SEDUC Campeche',
            defaults={
                'direccion': 'Av. Maestros Campechanos S/N, San Francisco de Campeche',
                'enlace_responsable': enlace_seduc_user,
                'telefono_contacto': '981-811-2233'
            }
        )
        if sede_seduc.enlace_responsable != enlace_seduc_user:
            sede_seduc.enlace_responsable = enlace_seduc_user
            sede_seduc.save(update_fields=['enlace_responsable'])

        # 3. Refacciones en Almacén
        ref_pasta, _ = Refaccion.objects.get_or_create(
            codigo_parte='INS-PASTA-SILV-30G',
            defaults={
                'nombre': 'Jeringa Pasta Térmica Silver de Alta Densidad (30g)',
                'categoria': Refaccion.CategoriaRefaccion.REFRIGERACION,
                'stock_actual': 25,
                'stock_minimo_alerta': 5,
                'costo_unitario': 180.00,
                'unidad_medida': 'Jeringa'
            }
        )

        ref_ssd, _ = Refaccion.objects.get_or_create(
            codigo_parte='REF-SSD-NVME-512GB',
            defaults={
                'nombre': 'Unidad de Estado Sólido Kingston NVMe PCIe M.2 512GB',
                'categoria': Refaccion.CategoriaRefaccion.ALMACENAMIENTO,
                'stock_actual': 12,
                'stock_minimo_alerta': 3,
                'costo_unitario': 750.00,
                'unidad_medida': 'Pieza'
            }
        )

        ref_alcohol, _ = Refaccion.objects.get_or_create(
            codigo_parte='INS-ALCOHOL-ISOP-1L',
            defaults={
                'nombre': 'Alcohol Isopropílico 99.8% Grado Electrónico (1 Litro)',
                'categoria': Refaccion.CategoriaRefaccion.CONSUMIBLE,
                'stock_actual': 30,
                'stock_minimo_alerta': 6,
                'costo_unitario': 95.00,
                'unidad_medida': 'Botella'
            }
        )

        ref_aire, _ = Refaccion.objects.get_or_create(
            codigo_parte='INS-AIRE-COMP-440ML',
            defaults={
                'nombre': 'Lata de Aire Comprimido Removedor de Polvo (440ml)',
                'categoria': Refaccion.CategoriaRefaccion.CONSUMIBLE,
                'stock_actual': 24,
                'stock_minimo_alerta': 5,
                'costo_unitario': 85.00,
                'unidad_medida': 'Lata'
            }
        )

        ref_pila, _ = Refaccion.objects.get_or_create(
            codigo_parte='INS-PILA-CMOS-CR2032',
            defaults={
                'nombre': 'Pila de Litio Tipo Botón CR2032 3V para BIOS/CMOS',
                'categoria': Refaccion.CategoriaRefaccion.PILA_CMOS,
                'stock_actual': 50,
                'stock_minimo_alerta': 10,
                'costo_unitario': 25.00,
                'unidad_medida': 'Pieza'
            }
        )

        ref_pano, _ = Refaccion.objects.get_or_create(
            codigo_parte='INS-PANO-MICRO-ANTI',
            defaults={
                'nombre': 'Paño de Microfibra Antiestática Lavable (Pack)',
                'categoria': Refaccion.CategoriaRefaccion.CONSUMIBLE,
                'stock_actual': 40,
                'stock_minimo_alerta': 8,
                'costo_unitario': 35.00,
                'unidad_medida': 'Paño'
            }
        )

        # 4. Inventario de Equipos
        eq1, _ = Equipo.objects.get_or_create(
            numero_serie='MXL-9482019-B',
            defaults={
                'contrato': contrato_itse,
                'sede': sede_central,
                'codigo_inventario_interno': 'ITSE-CC-PC-014',
                'tipo_equipo': Equipo.TipoEquipo.DESKTOP,
                'marca': 'AOC',
                'modelo': 'E970Swn MicroTower',
                'area_o_departamento': 'Laboratorio de Cómputo B',
                'usuario_asignado_nombre': 'Prof. Juan Pérez Gómez',
                'estatus_operativo': Equipo.EstatusOperativo.OPERATIVO,
                'accesorios_incluidos': 'Cable de poder trifásico, teclado USB español, mouse óptico USB',
                'estado_estetico_inicial': 'Gabinete en buen estado general, signos leves de desgaste por polvo',
            }
        )
        EspecificacionHardware.objects.get_or_create(
            equipo=eq1,
            defaults={
                'cpu_marca_modelo': 'Intel Pentium G3250 3.20GHz',
                'motherboard_marca_modelo': 'Asus Essentials H61-M / Micro-ATX',
                'ram_capacidad_gb': 8,
                'ram_tecnologia': EspecificacionHardware.TipoRAM.DDR4,
                'almacenamiento_tipo': EspecificacionHardware.TipoAlmacenamiento.SSD_NVME,
                'almacenamiento_capacidad_gb': 512,
                'sistema_operativo': 'Windows 11 Pro 64 bits'
            }
        )

        eq2, _ = Equipo.objects.get_or_create(
            numero_serie='DL-LAT-5420-781A',
            defaults={
                'contrato': contrato_itse,
                'sede': sede_admin,
                'codigo_inventario_interno': 'ITSE-DIR-LAP-002',
                'tipo_equipo': Equipo.TipoEquipo.LAPTOP,
                'marca': 'Dell',
                'modelo': 'Latitude 5420',
                'area_o_departamento': 'Dirección General',
                'usuario_asignado_nombre': 'Dirección Académica',
                'estatus_operativo': Equipo.EstatusOperativo.EN_MANTENIMIENTO,
                'accesorios_incluidos': 'Cargador original USB-C 65W, maletín acolchado',
                'estado_estetico_inicial': 'Impecable, sin rayones',
            }
        )
        EspecificacionHardware.objects.get_or_create(
            equipo=eq2,
            defaults={
                'cpu_marca_modelo': 'Intel Core i5-1145G7 vPro',
                'motherboard_marca_modelo': 'Dell Inc. 0M76GF',
                'ram_capacidad_gb': 16,
                'ram_tecnologia': EspecificacionHardware.TipoRAM.DDR4,
                'almacenamiento_tipo': EspecificacionHardware.TipoAlmacenamiento.SSD_NVME,
                'almacenamiento_capacidad_gb': 512,
                'sistema_operativo': 'Windows 11 Pro 64 bits'
            }
        )

        eq3, _ = Equipo.objects.get_or_create(
            numero_serie='HP-SRV-PROL-994X',
            defaults={
                'contrato': contrato_seduc,
                'sede': sede_seduc,
                'codigo_inventario_interno': 'SEDUC-SRV-001',
                'tipo_equipo': Equipo.TipoEquipo.SERVIDOR,
                'marca': 'HP Enterprise',
                'modelo': 'ProLiant ML350 Gen10',
                'area_o_departamento': 'Centro de Datos Central',
                'usuario_asignado_nombre': 'Ing. Coordinador SEDUC',
                'estatus_operativo': Equipo.EstatusOperativo.OPERATIVO,
            }
        )
        EspecificacionHardware.objects.get_or_create(
            equipo=eq3,
            defaults={
                'cpu_marca_modelo': 'Intel Xeon Silver 4210R 2.40GHz',
                'motherboard_marca_modelo': 'HPE Server Board Dual Socket',
                'ram_capacidad_gb': 64,
                'ram_tecnologia': EspecificacionHardware.TipoRAM.DDR4,
                'almacenamiento_tipo': EspecificacionHardware.TipoAlmacenamiento.HIBRIDO,
                'almacenamiento_capacidad_gb': 2000,
                'sistema_operativo': 'Windows Server 2022 Datacenter'
            }
        )

        # 5. Órdenes de Trabajo con Porcentaje de Avance y Nuevo Formato
        ahora = timezone.now()

        # OT 1: Preventivo ITSE (100% de avance, cerrada con reporte comercial completo)
        ot_prev, _ = OrdenTrabajo.objects.get_or_create(
            numero_orden='OTP-202611-0001',
            defaults={
                'tipo_servicio': OrdenTrabajo.TipoMantenimiento.PREVENTIVO,
                'equipo': eq1,
                'coordinador': coord_user,
                'tecnico_asignado': tec_user,
                'estatus': OrdenTrabajo.EstatusOT.CERRADA_CONFORME,
                'porcentaje_avance': 100,
                'domicilio_laboratorio': 'Calle Principal S/N, Parque Industrial Tecnológico, Taller Central TI',
                'telefono_extension_tecnico': '614-987-6543 Ext. 104',
                'telefono_whatsapp_cliente': '982-123-4567',
                'fecha_recibido': ahora - timedelta(days=2),
                'fecha_estimada_entrega': ahora - timedelta(days=1, hours=20),
                'fecha_inicio_atencion': ahora - timedelta(days=2, hours=2),
                'fecha_real_entrega': ahora - timedelta(days=1, hours=22),
                'diagnostico_preliminar': 'Mantenimiento semestral preventivo programado según calendario contractual.',
                'causa_raiz': 'Acumulación moderada de polvo en disipador de CPU y aspas del ventilador.',
                'trabajo_realizado': '1. Desconexión de energía con pulsera antiestática.\n2. Soplado controlado de disipadores y ventiladores.\n3. Limpieza de pines de memoria RAM con goma de borrar blanda y solvente dieléctrico.\n4. Reemplazo de pasta térmica por compuesto disipador de alta densidad.\n5. Ejecución de TRIM en unidad SSD y limpieza de archivos temporales del SO.\n6. Actualización de firmas de antivirus y parches de seguridad.',
                'observaciones_recomendaciones': '- Mantener el equipo separado al menos 15 cm de la pared para garantizar flujo de aire óptimo.\n- Próximo preventivo programado para Mayo 2027.',
                'costo_total': 0.00,
                'dias_garantia': 30,
                'cumplio_sla': True
            }
        )

        # Pasos del checklist para OT 1
        checklist_data = [
            (ChecklistPreventivo.CategoriaChecklist.SEGURIDAD, 'Mesa de trabajo amplia, limpia e iluminada no conductora', True),
            (ChecklistPreventivo.CategoriaChecklist.SEGURIDAD, 'Uso de pulsera antiestática conectada a tierra', True),
            (ChecklistPreventivo.CategoriaChecklist.SEGURIDAD, 'Apagado total del equipo y desconexión física de la red eléctrica', True),
            (ChecklistPreventivo.CategoriaChecklist.HARDWARE_FISICO, 'Retiro de paneles laterales y lavado/secado de filtros de polvo', True),
            (ChecklistPreventivo.CategoriaChecklist.HARDWARE_FISICO, 'Soplado con aire a presión en disipador y ventilador sin sobregirar aspas', True),
            (ChecklistPreventivo.CategoriaChecklist.HARDWARE_FISICO, 'Remoción de residuos adheridos a tarjeta madre con brocha suave', True),
            (ChecklistPreventivo.CategoriaChecklist.HARDWARE_FISICO, 'Extracción y limpieza de contactos dorados de RAM con goma blanda y dieléctrico', True),
            (ChecklistPreventivo.CategoriaChecklist.HARDWARE_FISICO, 'Renovación de pasta térmica disipadora en procesador (CPU)', True),
            (ChecklistPreventivo.CategoriaChecklist.HARDWARE_FISICO, 'Limpieza externa de teclado, mouse óptico y monitor (sin abrir monitor)', True),
            (ChecklistPreventivo.CategoriaChecklist.HARDWARE_FISICO, 'Peinado y sujeción de cableado interno con bridas', True),
            (ChecklistPreventivo.CategoriaChecklist.SOFTWARE_LOGICO, 'Instalación de actualizaciones acumulativas de SO y drivers', True),
            (ChecklistPreventivo.CategoriaChecklist.SOFTWARE_LOGICO, 'Liberación de espacio en disco (archivos temporales y caché)', True),
            (ChecklistPreventivo.CategoriaChecklist.SOFTWARE_LOGICO, 'Optimización de unidades de almacenamiento (comando TRIM en SSD)', True),
            (ChecklistPreventivo.CategoriaChecklist.SOFTWARE_LOGICO, 'Escaneo de seguridad con antivirus actualizado', True),
            (ChecklistPreventivo.CategoriaChecklist.SOFTWARE_LOGICO, 'Depuración de programas innecesarios en el inicio del sistema', True),
        ]
        for cat, tarea, realizado in checklist_data:
            ChecklistPreventivo.objects.get_or_create(
                orden=ot_prev,
                tarea=tarea,
                defaults={'categoria': cat, 'realizado': realizado}
            )

        SolicitudRefaccionOT.objects.get_or_create(
            orden=ot_prev,
            refaccion=ref_pasta,
            defaults={'cantidad': 1, 'estatus': SolicitudRefaccionOT.EstatusSolicitudRefaccion.SURTIDA}
        )

        FirmaDigitalOT.objects.get_or_create(
            orden=ot_prev,
            tipo_firmante=FirmaDigitalOT.TipoFirmante.TECNICO,
            defaults={
                'nombre_firmante': 'Tec. Michel Lizbeth Morales Gómez',
                'cargo': 'Técnico Especialista Spartan PC',
                'firma_digital_data': 'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="200" height="60"><path d="M10,40 Q50,10 90,40 T170,30" stroke="#1e3a8a" stroke-width="2" fill="none"/></svg>',
                'hash_seguridad': 'SHA256:7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b'
            }
        )

        FirmaDigitalOT.objects.get_or_create(
            orden=ot_prev,
            tipo_firmante=FirmaDigitalOT.TipoFirmante.ENLACE_CLIENTE,
            defaults={
                'nombre_firmante': 'Ing. Iván Eduardo Molina Rodríguez',
                'cargo': 'Enlace de TI - ITSE',
                'firma_digital_data': 'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="200" height="60"><path d="M15,35 Q60,55 110,25 T180,45" stroke="#047857" stroke-width="2" fill="none"/></svg>',
                'hash_seguridad': 'SHA256:8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c'
            }
        )

        # OT 2: Preventivo Semestral Laptop ITSE (55% de avance, en ejecución por Técnico 1)
        ot_corr, _ = OrdenTrabajo.objects.get_or_create(
            numero_orden='OTP-202611-0002',
            defaults={
                'tipo_servicio': OrdenTrabajo.TipoMantenimiento.PREVENTIVO,
                'equipo': eq2,
                'coordinador': coord_user,
                'tecnico_asignado': tec_user,
                'estatus': OrdenTrabajo.EstatusOT.EN_EJECUCION,
                'porcentaje_avance': 55,
                'domicilio_laboratorio': 'Calle Principal S/N, Parque Industrial Tecnológico, Taller Central TI',
                'telefono_extension_tecnico': '614-987-6543 Ext. 104',
                'telefono_whatsapp_cliente': '982-123-4568',
                'fecha_recibido': ahora - timedelta(hours=5),
                'fecha_estimada_entrega': ahora + timedelta(hours=19),
                'fecha_inicio_atencion': ahora - timedelta(hours=2),
                'diagnostico_preliminar': 'Mantenimiento preventivo semestral: inspección térmica de turbina, desensamble de chasis y optimización de SO.',
                'causa_raiz': 'Polvo acumulado en la rejilla de salida de aire y degradación del compuesto térmico original de fábrica.',
                'trabajo_realizado': '1. Desarmado de tapa inferior y retiro de batería.\n2. Limpieza de aspas de turbina con aire comprimido regulado.\n3. Aplicación de pasta térmica de alta densidad.\n4. Ajuste de tornillería interna de bisagras.',
                'observaciones_recomendaciones': '- Evitar usar el equipo sobre superficies acolchadas o telas.\n- Próximo mantenimiento preventivo programado en 6 meses.',
                'cumplio_sla': True
            }
        )

        # OT 3: Preventivo Servidor SEDUC (25% de avance, asignado a Técnico 2)
        ot_seduc, _ = OrdenTrabajo.objects.get_or_create(
            numero_orden='OTP-202611-0003',
            defaults={
                'tipo_servicio': OrdenTrabajo.TipoMantenimiento.PREVENTIVO,
                'equipo': eq3,
                'coordinador': coord_user,
                'tecnico_asignado': tec2_user,
                'estatus': OrdenTrabajo.EstatusOT.EN_DIAGNOSTICO,
                'porcentaje_avance': 25,
                'domicilio_laboratorio': 'Calle Principal S/N, Parque Industrial Tecnológico, Taller Central TI',
                'telefono_extension_tecnico': '614-987-6543 Ext. 108',
                'telefono_whatsapp_cliente': '981-811-2233',
                'fecha_recibido': ahora - timedelta(hours=2),
                'fecha_estimada_entrega': ahora + timedelta(hours=10),
                'fecha_inicio_atencion': ahora - timedelta(minutes=45),
                'diagnostico_preliminar': 'Mantenimiento preventivo de infraestructura de servidor: verificación de salud SMART y limpieza de filtros frontales.',
                'causa_raiz': 'Filtro frontal de chasis saturado de partículas ambientales; fuentes redundantes funcionando correctamente.',
                'trabajo_realizado': '1. Inspección de bahías hot-swap sin interrupción de servicio.\n2. Limpieza de filtros antipolvo con brocha antiestática.\n3. Verificación de firmware en controladora Smart Array.',
                'observaciones_recomendaciones': '- Mantener la temperatura de la sala del centro de datos entre 18°C y 22°C.\n- Próximo servicio preventivo en Abril 2027.',
                'cumplio_sla': True
            }
        )

        # 6. Insumos y Maletín de Herramientas de Técnicos (SRS IEEE 830)
        self.stdout.write(self.style.NOTICE("Configurando kits de insumos de técnicos..."))

        # Asignaciones para Técnico 1 (Michel Lizbeth)
        asig_tec1_pasta, _ = AsignacionInsumoTecnico.objects.get_or_create(
            tecnico=tec_user,
            insumo=ref_pasta,
            defaults={
                'cantidad_disponible': 4,
                'stock_minimo_kit': 2,
            }
        )
        asig_tec1_alcohol, _ = AsignacionInsumoTecnico.objects.get_or_create(
            tecnico=tec_user,
            insumo=ref_alcohol,
            defaults={
                'cantidad_disponible': 3,
                'stock_minimo_kit': 1,
            }
        )
        asig_tec1_aire, _ = AsignacionInsumoTecnico.objects.get_or_create(
            tecnico=tec_user,
            insumo=ref_aire,
            defaults={
                'cantidad_disponible': 1, # Bajo mínimo intencional para verificar alerta visual
                'stock_minimo_kit': 2,
            }
        )
        asig_tec1_pila, _ = AsignacionInsumoTecnico.objects.get_or_create(
            tecnico=tec_user,
            insumo=ref_pila,
            defaults={
                'cantidad_disponible': 8,
                'stock_minimo_kit': 3,
            }
        )
        asig_tec1_pano, _ = AsignacionInsumoTecnico.objects.get_or_create(
            tecnico=tec_user,
            insumo=ref_pano,
            defaults={
                'cantidad_disponible': 5,
                'stock_minimo_kit': 2,
            }
        )

        # Movimientos históricos para Técnico 1 (idempotente)
        if not MovimientoInsumoTecnico.objects.filter(tecnico=tec_user, insumo=ref_pasta, tipo_operacion=MovimientoInsumoTecnico.TipoOperacion.DOTACION).exists():
            MovimientoInsumoTecnico.objects.create(
                tecnico=tec_user,
                insumo=ref_pasta,
                tipo_operacion=MovimientoInsumoTecnico.TipoOperacion.DOTACION,
                cantidad=5,
                autorizado_por=alm_user,
                observaciones='Dotación quincenal inicial para mantenimiento preventivo ITSE.'
            )
        if not MovimientoInsumoTecnico.objects.filter(tecnico=tec_user, insumo=ref_pasta, tipo_operacion=MovimientoInsumoTecnico.TipoOperacion.CONSUMO_MANTENIMIENTO).exists():
            MovimientoInsumoTecnico.objects.create(
                tecnico=tec_user,
                insumo=ref_pasta,
                tipo_operacion=MovimientoInsumoTecnico.TipoOperacion.CONSUMO_MANTENIMIENTO,
                cantidad=1,
                autorizado_por=tec_user,
                observaciones='Consumo en servicio preventivo OTP-202611-0001 (MicroTower AOC).'
            )
        if not MovimientoInsumoTecnico.objects.filter(tecnico=tec_user, insumo=ref_aire, tipo_operacion=MovimientoInsumoTecnico.TipoOperacion.DOTACION).exists():
            MovimientoInsumoTecnico.objects.create(
                tecnico=tec_user,
                insumo=ref_aire,
                tipo_operacion=MovimientoInsumoTecnico.TipoOperacion.DOTACION,
                cantidad=2,
                autorizado_por=alm_user,
                observaciones='Entrega de latas de aire comprimido para limpieza de turbinas.'
            )
        if not MovimientoInsumoTecnico.objects.filter(tecnico=tec_user, insumo=ref_aire, tipo_operacion=MovimientoInsumoTecnico.TipoOperacion.CONSUMO_MANTENIMIENTO).exists():
            MovimientoInsumoTecnico.objects.create(
                tecnico=tec_user,
                insumo=ref_aire,
                tipo_operacion=MovimientoInsumoTecnico.TipoOperacion.CONSUMO_MANTENIMIENTO,
                cantidad=1,
                autorizado_por=tec_user,
                observaciones='Consumo en mantenimiento preventivo OTP-202611-0002 (Laptop HP).'
            )

        # Asignaciones para Técnico 2 (César Alejandro)
        AsignacionInsumoTecnico.objects.get_or_create(
            tecnico=tec2_user,
            insumo=ref_pasta,
            defaults={
                'cantidad_disponible': 3,
                'stock_minimo_kit': 2,
            }
        )
        AsignacionInsumoTecnico.objects.get_or_create(
            tecnico=tec2_user,
            insumo=ref_alcohol,
            defaults={
                'cantidad_disponible': 2,
                'stock_minimo_kit': 1,
            }
        )
        AsignacionInsumoTecnico.objects.get_or_create(
            tecnico=tec2_user,
            insumo=ref_pila,
            defaults={
                'cantidad_disponible': 6,
                'stock_minimo_kit': 2,
            }
        )
        if not MovimientoInsumoTecnico.objects.filter(tecnico=tec2_user, insumo=ref_alcohol, tipo_operacion=MovimientoInsumoTecnico.TipoOperacion.DOTACION).exists():
            MovimientoInsumoTecnico.objects.create(
                tecnico=tec2_user,
                insumo=ref_alcohol,
                tipo_operacion=MovimientoInsumoTecnico.TipoOperacion.DOTACION,
                cantidad=3,
                autorizado_por=coord_user,
                observaciones='Dotación para inspección de servidores SEDUC Campeche.'
            )
        if not MovimientoInsumoTecnico.objects.filter(tecnico=tec2_user, insumo=ref_alcohol, tipo_operacion=MovimientoInsumoTecnico.TipoOperacion.DEVOLUCION).exists():
            MovimientoInsumoTecnico.objects.create(
                tecnico=tec2_user,
                insumo=ref_alcohol,
                tipo_operacion=MovimientoInsumoTecnico.TipoOperacion.DEVOLUCION,
                cantidad=1,
                autorizado_por=alm_user,
                observaciones='Devolución de botella sobrante por reajuste de cuadrilla.'
            )

        self.stdout.write(self.style.SUCCESS("✓ Base de datos poblada exitosamente con órdenes preventivas exclusivas, técnicos, insumos y avance!"))
