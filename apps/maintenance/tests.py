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
