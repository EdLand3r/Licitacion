from django.test import TestCase, Client
from django.urls import reverse
from datetime import date, timedelta
from apps.authentication.models import User
from apps.contracts.models import Contrato, Sede
from apps.inventory.models import Equipo
from apps.maintenance.models import OrdenTrabajo, FirmaDigitalOT


class MultiTenancyIsolationTestCase(TestCase):
    def setUp(self):
        self.client = Client()

        # 1. Enlace ITSE (Cliente 1)
        self.enlace_itse = User.objects.create_user(
            username='enlace_itse_test',
            password='testpassword123',
            role=User.Role.ENLACE,
            dependencia_o_empresa='Instituto Tecnológico Superior de Escárcega (ITSE)'
        )

        # 2. Enlace SEDUC (Cliente 2)
        self.enlace_seduc = User.objects.create_user(
            username='enlace_seduc_test',
            password='testpassword123',
            role=User.Role.ENLACE,
            dependencia_o_empresa='Secretaría de Educación de Campeche (SEDUC)'
        )

        # 3. Admin / Coordinador
        self.coordinador = User.objects.create_user(
            username='coord_test',
            password='testpassword123',
            role=User.Role.COORDINADOR
        )

        # Contrato ITSE
        self.contrato_itse = Contrato.objects.create(
            numero_contrato='CT-ITSE-TEST-001',
            numero_licitacion='LIC-ITSE-2026',
            dependencia_cliente='Instituto Tecnológico Superior de Escárcega (ITSE)',
            fecha_inicio=date.today() - timedelta(days=30),
            fecha_fin=date.today() + timedelta(days=300),
            sla_horas_respuesta=4,
            sla_horas_solucion=24,
            activo=True
        )
        self.sede_itse = Sede.objects.create(
            contrato=self.contrato_itse,
            nombre='Campus ITSE Escárcega',
            direccion='Km 3.5 Carretera Candelaria',
            enlace_responsable=self.enlace_itse
        )
        self.eq_itse = Equipo.objects.create(
            contrato=self.contrato_itse,
            sede=self.sede_itse,
            numero_serie='SRV-ITSE-1111',
            marca='Dell',
            modelo='OptiPlex ITSE',
            tipo_equipo=Equipo.TipoEquipo.DESKTOP
        )
        self.ot_itse = OrdenTrabajo.objects.create(
            numero_orden='OTP-ITSE-001',
            tipo_servicio=OrdenTrabajo.TipoMantenimiento.PREVENTIVO,
            equipo=self.eq_itse,
            coordinador=self.coordinador,
            estatus=OrdenTrabajo.EstatusOT.CERRADA_CONFORME,
            porcentaje_avance=100
        )
        FirmaDigitalOT.objects.create(
            orden=self.ot_itse,
            tipo_firmante=FirmaDigitalOT.TipoFirmante.ENLACE_CLIENTE,
            nombre_firmante='Ing. Iván Molina',
            firma_digital_data='FIRMA_OK',
            hash_seguridad='SHA256:TEST_HASH'
        )

        # Contrato SEDUC
        self.contrato_seduc = Contrato.objects.create(
            numero_contrato='CT-SEDUC-TEST-002',
            numero_licitacion='LIC-SEDUC-2026',
            dependencia_cliente='Secretaría de Educación de Campeche (SEDUC)',
            fecha_inicio=date.today() - timedelta(days=30),
            fecha_fin=date.today() + timedelta(days=300),
            sla_horas_respuesta=2,
            sla_horas_solucion=12,
            activo=True
        )
        self.sede_seduc = Sede.objects.create(
            contrato=self.contrato_seduc,
            nombre='Oficinas SEDUC Campeche',
            direccion='Av. Maestros Campechanos',
            enlace_responsable=self.enlace_seduc
        )
        self.eq_seduc = Equipo.objects.create(
            contrato=self.contrato_seduc,
            sede=self.sede_seduc,
            numero_serie='SRV-SEDUC-2222',
            marca='HP',
            modelo='ProLiant SEDUC',
            tipo_equipo=Equipo.TipoEquipo.SERVIDOR
        )
        self.ot_seduc = OrdenTrabajo.objects.create(
            numero_orden='OTP-SEDUC-002',
            tipo_servicio=OrdenTrabajo.TipoMantenimiento.PREVENTIVO,
            equipo=self.eq_seduc,
            coordinador=self.coordinador,
            estatus=OrdenTrabajo.EstatusOT.EN_EJECUCION,
            porcentaje_avance=40
        )

    def test_dashboard_multi_tenancy_isolation_enlace(self):
        """
        Verifica que el cliente ITSE únicamente visualice sus propios equipos y órdenes en /dashboard/,
        sin ver datos de SEDUC, sin tarjeta de refacciones y sin enlace de auditoría.
        """
        self.client.login(username='enlace_itse_test', password='testpassword123')
        res = self.client.get(reverse('dashboard'))
        self.assertEqual(res.status_code, 200)

        # Contenido de su propia dependencia presente
        self.assertContains(res, 'OTP-ITSE-001')
        self.assertContains(res, 'OptiPlex ITSE')
        self.assertContains(res, 'Amparados en Licitación')

        # Contenido ajeno (SEDUC) ESTRICTAMENTE AUSENTE
        self.assertNotContains(res, 'OTP-SEDUC-002')
        self.assertNotContains(res, 'ProLiant SEDUC')
        self.assertNotContains(res, 'CT-SEDUC-TEST-002')

        # Tarjeta de Almacén Refacciones ELIMINADA para el rol Cliente
        self.assertNotContains(res, 'Almacén Refacciones')

        # Enlace de Auditoría y Monitoreo OCULTO en subheader
        self.assertNotContains(res, 'Auditoría y Monitoreo en Tiempo Real')

        # Botón para nueva orden / ticket OCULTO para el rol Cliente (Exclusivo para Coordinador)
        self.assertNotContains(res, '+ Nueva Orden / Ticket')
        self.assertNotContains(res, 'Nueva Orden Preventiva')

    def test_navbar_simplification_for_enlace(self):
        """
        Navbar para rol Cliente:
        - Visibles: Dashboard, Órdenes (Tickets) y Contratos SLA.
        - Ocultos: Refacciones e Inventario Cómputo.
        """
        self.client.login(username='enlace_itse_test', password='testpassword123')
        res = self.client.get(reverse('dashboard'))
        self.assertEqual(res.status_code, 200)

        # Módulos visibles
        self.assertContains(res, 'Dashboard')
        self.assertContains(res, 'Órdenes (Tickets)')
        self.assertContains(res, 'Contratos SLA (Licitación)')

        # Módulos restringidos/ocultos en la barra
        self.assertNotContains(res, 'Refacciones')
        self.assertNotContains(res, 'Inventario Cómputo')

    def test_block_direct_url_access_to_alien_ot(self):
        """
        Bloquea el acceso directo por URL a detalles de OTs de dependencias ajenas
        devolviendo un error 403 Forbidden.
        """
        # Cliente ITSE intentando acceder al reporte de SEDUC
        self.client.login(username='enlace_itse_test', password='testpassword123')
        res = self.client.get(reverse('orden_detalle', args=[self.ot_seduc.id]))
        self.assertEqual(res.status_code, 403)

        # Pero SÍ puede acceder a su propia orden
        res_propia = self.client.get(reverse('orden_detalle', args=[self.ot_itse.id]))
        self.assertEqual(res_propia.status_code, 200)

    def test_block_direct_url_access_to_refacciones_and_auditoria(self):
        """
        Bloquea el acceso directo por URL a /refacciones/, /almacen/ y /auditoria/
        para el rol Cliente (Enlace), denegando el acceso.
        """
        self.client.login(username='enlace_itse_test', password='testpassword123')

        # 1. /refacciones/
        res_ref = self.client.get('/refacciones/')
        self.assertEqual(res_ref.status_code, 302)
        self.assertIn(reverse('unauthorized'), res_ref.url)

        # 2. /almacen/
        res_alm = self.client.get(reverse('almacen_lista'))
        self.assertEqual(res_alm.status_code, 302)
        self.assertIn(reverse('unauthorized'), res_alm.url)

        # 3. /auditoria/
        res_aud = self.client.get(reverse('auditoria_view'))
        self.assertEqual(res_aud.status_code, 302)
        self.assertIn(reverse('unauthorized'), res_aud.url)

    def test_multi_tenancy_equipos_and_contratos_isolation(self):
        """
        El inventario y listado de contratos debe mostrar única y exclusivamente
        los registros de la dependencia del Enlace.
        """
        self.client.login(username='enlace_itse_test', password='testpassword123')

        # Equipos
        res_eq = self.client.get(reverse('inventario_lista'))
        self.assertEqual(res_eq.status_code, 200)
        self.assertContains(res_eq, 'SRV-ITSE-1111')
        self.assertNotContains(res_eq, 'SRV-SEDUC-2222')

        # Contratos
        res_ct = self.client.get(reverse('contratos_lista'))
        self.assertEqual(res_ct.status_code, 200)
        self.assertContains(res_ct, 'CT-ITSE-TEST-001')
        self.assertNotContains(res_ct, 'CT-SEDUC-TEST-002')

    def test_dashboard_conformidad_actions_on_closed_orders(self):
        """
        Verifica que en las órdenes cerradas con conformidad se muestren las acciones
        de ver conformidad firmada y descargar/exportar a PDF.
        """
        self.client.login(username='enlace_itse_test', password='testpassword123')
        res = self.client.get(reverse('dashboard'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Conformidad')
        self.assertContains(res, '?print=1')
