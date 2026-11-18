from django.test import TestCase, Client
from django.urls import reverse
from datetime import date, timedelta
from apps.authentication.models import User
from apps.contracts.models import Contrato, Sede
from apps.inventory.models import Equipo, EspecificacionHardware
from apps.maintenance.models import OrdenTrabajo, ChecklistPreventivo
from apps.maintenance.views import limpiar_saltos


class GMAORBACTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            username='admin_test',
            password='testpassword123',
            role=User.Role.ADMIN
        )
        self.licitaciones = User.objects.create_user(
            username='lic_test',
            password='testpassword123',
            role=User.Role.RESPONSABLE_LICITACIONES
        )
        self.coordinador = User.objects.create_user(
            username='coordinador_test',
            password='testpassword123',
            role=User.Role.COORDINADOR
        )
        self.tecnico = User.objects.create_user(
            username='tecnico_test',
            password='testpassword123',
            role=User.Role.TECNICO
        )
        self.enlace = User.objects.create_user(
            username='enlace_test',
            password='testpassword123',
            role=User.Role.ENLACE
        )
        self.almacen = User.objects.create_user(
            username='almacen_test',
            password='testpassword123',
            role=User.Role.ALMACEN
        )

        self.contrato = Contrato.objects.create(
            numero_licitacion='LIC-TEST-2026',
            numero_contrato='CT-TEST-001',
            dependencia_cliente='TecNM ITSE Test',
            fecha_inicio=date.today(),
            fecha_fin=date.today() + timedelta(days=180),
            sla_horas_respuesta=4,
            sla_horas_solucion=24,
            activo=True
        )
        self.sede = Sede.objects.create(
            contrato=self.contrato,
            nombre='Sede Central Test',
            direccion='Calle Tecnológico #100',
            enlace_responsable=self.enlace
        )
        self.equipo = Equipo.objects.create(
            contrato=self.contrato,
            sede=self.sede,
            numero_serie='SRV-TEST-999',
            marca='Dell',
            modelo='OptiPlex 7090',
            tipo_equipo=Equipo.TipoEquipo.DESKTOP
        )
        self.specs = EspecificacionHardware.objects.create(
            equipo=self.equipo,
            cpu_marca_modelo='Intel Core i7-11700',
            ram_capacidad_gb=16,
            almacenamiento_capacidad_gb=512
        )

        self.ot = OrdenTrabajo.objects.create(
            tipo_servicio=OrdenTrabajo.TipoMantenimiento.PREVENTIVO,
            equipo=self.equipo,
            coordinador=self.coordinador,
            tecnico_asignado=self.tecnico,
            diagnostico_preliminar='Revisión semestral',
            causa_raiz='Polvo acumulado',
            trabajo_realizado='1. Desarmado.\n2. Soplado.\n3. Pasta térmica.',
            observaciones_recomendaciones='Mantener ventilado.',
            porcentaje_avance=30
        )

    def test_rbac_route_protection(self):
        # 1. Técnico intentando acceder a Contratos -> Debe ser redirigido a unauthorized
        self.client.login(username='tecnico_test', password='testpassword123')
        res = self.client.get(reverse('contratos_lista'))
        self.assertEqual(res.status_code, 302)
        self.assertIn(reverse('unauthorized'), res.url)

        # 2. Responsable de licitaciones accede a Contratos -> Permitido (200)
        self.client.login(username='lic_test', password='testpassword123')
        res = self.client.get(reverse('contratos_lista'))
        self.assertEqual(res.status_code, 200)

        # 3. Enlace intentando acceder a Almacén -> Denegado (302 a unauthorized)
        self.client.login(username='enlace_test', password='testpassword123')
        res = self.client.get(reverse('almacen_lista'))
        self.assertEqual(res.status_code, 302)
        self.assertIn(reverse('unauthorized'), res.url)

        # 4. Almacén accede a Almacén -> Permitido (200)
        self.client.login(username='almacen_test', password='testpassword123')
        res = self.client.get(reverse('almacen_lista'))
        self.assertEqual(res.status_code, 200)

    def test_limpiar_saltos_linea(self):
        # Verifica la corrección de cadenas que imprimen literalmente '\n'
        texto_con_escapes = r"1. Paso uno\n2. Paso dos\n3. Paso tres"
        resultado = limpiar_saltos(texto_con_escapes)
        self.assertNotIn(r"\n", resultado)
        self.assertIn("\n", resultado)
        lineas = resultado.split("\n")
        self.assertEqual(len(lineas), 3)

    def test_modo_edicion_manual_reporte(self):
        # Técnico edita manualmente el reporte preventivo sin bloqueo
        self.client.login(username='tecnico_test', password='testpassword123')
        post_data = {
            'accion': 'guardar',
            'domicilio_laboratorio': 'Taller Central Modificado',
            'telefono_extension_tecnico': '614-999-0000 Ext. 500',
            'telefono_whatsapp_cliente': '982-000-1111',
            'diagnostico_preliminar': 'Puntos de revisión actualizados',
            'causa_raiz': 'Hallazgos modificados por técnico',
            'trabajo_realizado': '1. Acción uno realizada\n2. Acción dos realizada',
            'observaciones_recomendaciones': 'Recomendación personalizada',
            'porcentaje_avance': '80'
        }
        res = self.client.post(reverse('orden_detalle', args=[self.ot.id]), post_data)
        self.assertEqual(res.status_code, 302)

        self.ot.refresh_from_db()
        self.assertEqual(self.ot.domicilio_laboratorio, 'Taller Central Modificado')
        self.assertEqual(self.ot.porcentaje_avance, 80)
        self.assertEqual(self.ot.diagnostico_preliminar, 'Puntos de revisión actualizados')
        self.assertIn('Acción uno realizada', self.ot.trabajo_realizado)

    def test_reporte_exclusivamente_preventivo_headers(self):
        self.client.login(username='coordinador_test', password='testpassword123')
        res = self.client.get(reverse('orden_detalle', args=[self.ot.id]))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'REPORTE DE MANTENIMIENTO - PREVENTIVO')
        self.assertContains(res, 'DIAGNÓSTICO TÉCNICO COMERCIAL')
        self.assertContains(res, 'Actividad / Punto de Revisión')
        self.assertContains(res, 'Hallazgos / Condición Encontrada')
        self.assertContains(res, 'Solución / Trabajo Realizado')
        self.assertNotContains(res, 'Mantenimiento Correctivo')

    def test_only_coordinador_can_crear_ordenes(self):
        """
        Regla de negocio: Únicamente el Coordinador de Operaciones puede crear órdenes.
        Todos los demás roles (Técnico, Enlace, Almacén, Licitaciones) están bloqueados.
        """
        # 1. Coordinador accede exitosamente (200)
        self.client.login(username='coordinador_test', password='testpassword123')
        res_coord = self.client.get(reverse('ordenes_crear'))
        self.assertEqual(res_coord.status_code, 200)
        self.assertContains(res_coord, 'Nueva Orden de Mantenimiento Preventivo')

        # Y el botón está visible en el dashboard y en la lista de órdenes
        res_dash = self.client.get(reverse('dashboard'))
        self.assertContains(res_dash, 'Nueva Orden Preventiva')

        # 2. Técnico bloqueado
        self.client.login(username='tecnico_test', password='testpassword123')
        res_tec = self.client.get(reverse('ordenes_crear'), follow=True)
        self.assertEqual(res_tec.status_code, 403)
        res_dash_tec = self.client.get(reverse('dashboard'))
        self.assertNotContains(res_dash_tec, 'Nueva Orden Preventiva')

        # 3. Enlace (Cliente) bloqueado
        self.client.login(username='enlace_test', password='testpassword123')
        res_enlace = self.client.get(reverse('ordenes_crear'), follow=True)
        self.assertEqual(res_enlace.status_code, 403)
        res_dash_enlace = self.client.get(reverse('dashboard'))
        self.assertNotContains(res_dash_enlace, 'Nueva Orden Preventiva')
        self.assertNotContains(res_dash_enlace, reverse('ordenes_crear'))

        # 4. Responsable de Licitaciones bloqueado
        self.client.login(username='lic_test', password='testpassword123')
        res_lic = self.client.get(reverse('ordenes_crear'), follow=True)
        self.assertEqual(res_lic.status_code, 403)

        # 5. Almacén bloqueado
        self.client.login(username='almacen_test', password='testpassword123')
        res_alm = self.client.get(reverse('ordenes_crear'), follow=True)
        self.assertEqual(res_alm.status_code, 403)

    def test_tecnico_isolation_in_ordenes_lista_and_detalle(self):
        """
        Requerimiento 5: Aislamiento de OTs por técnico:
        Cada técnico solo debe ver sus órdenes asignadas y se bloquea el acceso a órdenes ajenas.
        """
        otro_tecnico = User.objects.create_user(
            username='otro_tecnico_test',
            password='testpassword123',
            role=User.Role.TECNICO
        )
        ot_ajena = OrdenTrabajo.objects.create(
            tipo_servicio=OrdenTrabajo.TipoMantenimiento.PREVENTIVO,
            equipo=self.equipo,
            coordinador=self.coordinador,
            tecnico_asignado=otro_tecnico,
            diagnostico_preliminar='OT de otro técnico',
            porcentaje_avance=10
        )

        # Login como tecnico_test
        self.client.login(username='tecnico_test', password='testpassword123')

        # 1. En la lista de órdenes, solo ve la suya (self.ot), NO la ajena
        res = self.client.get(reverse('ordenes_lista'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, self.ot.numero_orden)
        self.assertNotContains(res, ot_ajena.numero_orden)

        # 2. Intento de acceder al detalle de la orden ajena -> 403 Forbidden
        res_detalle = self.client.get(reverse('orden_detalle', args=[ot_ajena.id]))
        self.assertEqual(res_detalle.status_code, 403)

    def test_reporte_datos_licitacion_section(self):
        """
        Requerimiento 6: Sección estructurada para DATOS DE LA LICITACIÓN inmediatamente
        entre DATOS DEL CLIENTE y DESCRIPCIÓN DEL EQUIPO.
        """
        self.client.login(username='coordinador_test', password='testpassword123')
        res = self.client.get(reverse('orden_detalle', args=[self.ot.id]))
        self.assertEqual(res.status_code, 200)
        content = res.content.decode('utf-8')

        self.assertIn('Datos de la licitación', content)
        self.assertIn('Folio de Licitación:', content)
        self.assertIn('Niveles de Servicio SLA:', content)
        self.assertIn(self.contrato.numero_licitacion, content)

        # Verificar orden: 'Datos del cliente' aparece ANTES de 'Datos de la licitación'
        # y 'Datos de la licitación' aparece ANTES de 'Descripción del equipo'
        idx_cliente = content.find('Datos del cliente')
        idx_licitacion = content.find('Datos de la licitación')
        idx_equipo = content.find('Descripción del equipo')

        self.assertTrue(idx_cliente < idx_licitacion < idx_equipo)

    def test_solicitar_and_gestionar_insumo_ot(self):
        """
        Requerimiento 4: Solicitud de insumos dentro de la OT por técnico
        y aprobación / despacho por coordinación o almacén.
        """
        from apps.warehouse.models import Refaccion
        from apps.maintenance.models import SolicitudRefaccionOT

        insumo = Refaccion.objects.create(
            codigo_parte='INS-TEST-01',
            nombre='Alcohol Isopropílico 1L',
            unidad_medida='Litro',
            stock_actual=10,
            stock_minimo_alerta=2
        )

        # 1. Técnico solicita 2 litros
        self.client.login(username='tecnico_test', password='testpassword123')
        url_solicitar = reverse('solicitar_insumo_ot', args=[self.ot.id])
        res = self.client.post(url_solicitar, {
            'refaccion_id': insumo.id,
            'cantidad': '2'
        })
        self.assertEqual(res.status_code, 302)

        solicitud = SolicitudRefaccionOT.objects.get(orden=self.ot, refaccion=insumo)
        self.assertEqual(solicitud.cantidad, 2)
        self.assertEqual(solicitud.estatus, SolicitudRefaccionOT.EstatusSolicitudRefaccion.SOLICITADA)

        # 2. Coordinador aprueba la solicitud
        self.client.login(username='coordinador_test', password='testpassword123')
        url_gestionar = reverse('gestionar_solicitud_insumo', args=[solicitud.id])
        res2 = self.client.post(url_gestionar, {'decision': 'aprobar'})
        self.assertEqual(res2.status_code, 302)

        solicitud.refresh_from_db()
        insumo.refresh_from_db()
        self.assertEqual(solicitud.estatus, SolicitudRefaccionOT.EstatusSolicitudRefaccion.SURTIDA)
        self.assertEqual(insumo.stock_actual, 8) # 10 - 2 = 8
