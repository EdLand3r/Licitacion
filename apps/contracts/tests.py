from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from datetime import date, timedelta
import io

from apps.authentication.models import User
from apps.contracts.models import Contrato, Sede, ReservaInsumoLicitacion, validar_disponibilidad_tecnico
from apps.inventory.models import Equipo
from apps.warehouse.models import Refaccion


class LicitacionesComprehensiveTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            username='admin_lic_test',
            password='testpassword123',
            role=User.Role.ADMIN
        )
        self.coordinador = User.objects.create_user(
            username='coordinador_lic_test',
            password='testpassword123',
            role=User.Role.COORDINADOR
        )
        self.tecnico1 = User.objects.create_user(
            username='tecnico1_lic_test',
            password='testpassword123',
            role=User.Role.TECNICO,
            first_name='Carlos',
            last_name='Mendoza'
        )
        self.tecnico2 = User.objects.create_user(
            username='tecnico2_lic_test',
            password='testpassword123',
            role=User.Role.TECNICO,
            first_name='Laura',
            last_name='Ramos'
        )
        self.enlace = User.objects.create_user(
            username='enlace_lic_test',
            password='testpassword123',
            role=User.Role.ENLACE,
            dependencia_o_empresa='ITSE'
        )

        self.insumo = Refaccion.objects.create(
            codigo_parte='REF-PASTA-01',
            nombre='Pasta Térmica Arctic MX-4',
            unidad_medida='Pieza',
            stock_actual=50,
            stock_minimo_alerta=5
        )

    def test_auto_folio_generation(self):
        """
        Verifica que al guardar un Contrato sin número de licitación o contrato,
        se generen automáticamente los folios únicos secuenciales.
        """
        c1 = Contrato.objects.create(
            dependencia_cliente='Instituto Tecnológico de Campeche',
            fecha_inicio=date.today(),
            fecha_fin=date.today() + timedelta(days=90),
            sla_horas_respuesta=4,
            sla_horas_solucion=24,
            activo=True
        )
        self.assertTrue(c1.numero_licitacion.startswith(f"LIC-{date.today().year}-"))
        self.assertTrue(c1.numero_contrato.startswith("CT-"))

        c2 = Contrato.objects.create(
            dependencia_cliente='SEDUC Campeche',
            fecha_inicio=date.today(),
            fecha_fin=date.today() + timedelta(days=90),
            sla_horas_respuesta=2,
            sla_horas_solucion=12,
            activo=True
        )
        self.assertNotEqual(c1.numero_licitacion, c2.numero_licitacion)

    def test_validar_disponibilidad_tecnico_overlap(self):
        """
        Verifica la validación matemática estricta de traslapes de agenda:
        c.fecha_inicio <= fecha_fin and c.fecha_fin >= fecha_inicio.
        """
        f_inicio = date.today()
        f_fin = date.today() + timedelta(days=60)

        # Crear licitación asignada a tecnico1
        lic1 = Contrato.objects.create(
            numero_licitacion='LIC-2026-0010',
            numero_contrato='CT-ITSE-0010',
            dependencia_cliente='ITSE',
            fecha_inicio=f_inicio,
            fecha_fin=f_fin,
            activo=True
        )
        lic1.tecnicos_asignados.add(self.tecnico1)

        # Caso 1: Mismo período para tecnico1 -> Conflicto (False)
        disponible, err = validar_disponibilidad_tecnico(self.tecnico1, f_inicio, f_fin)
        self.assertFalse(disponible)
        self.assertIn('Conflicto de Agenda', err)

        # Caso 2: Período traslapado parcialmente (inicio en el día 30 al 90) -> Conflicto (False)
        disponible, err = validar_disponibilidad_tecnico(
            self.tecnico1, f_inicio + timedelta(days=30), f_fin + timedelta(days=30)
        )
        self.assertFalse(disponible)

        # Caso 3: Período posterior sin traslape (día 70 al 120) -> Disponible (True)
        disponible, err = validar_disponibilidad_tecnico(
            self.tecnico1, f_fin + timedelta(days=10), f_fin + timedelta(days=60)
        )
        self.assertTrue(disponible)
        self.assertIsNone(err)

        # Caso 4: tecnico2 no está asignado a lic1 -> Disponible (True)
        disponible, err = validar_disponibilidad_tecnico(self.tecnico2, f_inicio, f_fin)
        self.assertTrue(disponible)

    def test_licitacion_crear_view_and_tecnico_overlap_rejection(self):
        """
        Verifica la creación mediante formulario web y el rechazo si el técnico
        seleccionado tiene conflicto de fechas.
        """
        self.client.login(username='admin_lic_test', password='testpassword123')

        f_inicio = date.today()
        f_fin = date.today() + timedelta(days=30)

        # 1. Asignar previamente a tecnico1 a un contrato existente
        contrato_previo = Contrato.objects.create(
            numero_licitacion='LIC-2026-0099',
            dependencia_cliente='Dependencia Previa',
            fecha_inicio=f_inicio,
            fecha_fin=f_fin,
            activo=True
        )
        contrato_previo.tecnicos_asignados.add(self.tecnico1)

        # 2. Intentar crear nueva licitación seleccionando a tecnico1 en las mismas fechas
        url_crear = reverse('licitacion_crear')
        data = {
            'numero_licitacion': 'LIC-2026-0100',
            'dependencia_cliente': 'Nuevo Cliente',
            'titulo': 'Mantenimiento Preventivo Red',
            'fecha_inicio': f_inicio.strftime('%Y-%m-%d'),
            'fecha_fin': f_fin.strftime('%Y-%m-%d'),
            'sla_horas_respuesta': '4',
            'sla_horas_solucion': '24',
            'tecnicos_ids': [self.tecnico1.id],
        }
        res = self.client.post(url_crear, data)
        # Debe fallar la validación y no crearse
        self.assertEqual(res.status_code, 200)
        self.assertFalse(Contrato.objects.filter(numero_licitacion='LIC-2026-0100').exists())

        # 3. Intentar con tecnico2 (disponible) -> Éxito (302 redirect a detalle)
        data['tecnicos_ids'] = [self.tecnico2.id]
        res2 = self.client.post(url_crear, data)
        self.assertEqual(res2.status_code, 302)
        nueva_lic = Contrato.objects.get(numero_licitacion='LIC-2026-0100')
        self.assertIn(self.tecnico2, nueva_lic.tecnicos_asignados.all())

    def test_reserva_insumos_licitacion(self):
        """
        Verifica la asignación de insumos a una licitación sin referencias monetarias.
        """
        self.client.login(username='coordinador_lic_test', password='testpassword123')
        lic = Contrato.objects.create(
            numero_licitacion='LIC-2026-0200',
            dependencia_cliente='ITSE',
            fecha_inicio=date.today(),
            fecha_fin=date.today() + timedelta(days=90),
            activo=True
        )

        url_reserva = reverse('licitacion_reservar_insumo', kwargs={'pk': lic.id})
        res = self.client.post(url_reserva, {
            'insumo_id': self.insumo.id,
            'cantidad': '10',
            'notas': 'Lote para limpieza profunda'
        })
        self.assertEqual(res.status_code, 302)

        reserva = ReservaInsumoLicitacion.objects.get(contrato=lic, insumo=self.insumo)
        self.assertEqual(reserva.cantidad_asignada, 10)
        self.assertEqual(reserva.notas, 'Lote para limpieza profunda')

    def test_mass_csv_equipment_upload(self):
        """
        Verifica la importación masiva de equipos mediante archivo CSV.
        """
        self.client.login(username='admin_lic_test', password='testpassword123')
        lic = Contrato.objects.create(
            numero_licitacion='LIC-2026-0300',
            dependencia_cliente='ITSE Campus',
            fecha_inicio=date.today(),
            fecha_fin=date.today() + timedelta(days=90),
            activo=True
        )

        csv_content = (
            "numero_serie,marca,modelo,tipo_equipo,area,sede\n"
            "SRV-CSV-001,Dell,OptiPlex 3080,DESKTOP,Laboratorio 1,Campus Principal\n"
            "SRV-CSV-002,Lenovo,ThinkCentre M70,DESKTOP,Dirección,Campus Principal\n"
        )
        csv_file = io.BytesIO(csv_content.encode('utf-8'))
        csv_file.name = 'equipos.csv'

        url_csv = reverse('licitacion_cargar_equipos_csv', kwargs={'pk': lic.id})
        res = self.client.post(url_csv, {'archivo_csv': csv_file})
        self.assertEqual(res.status_code, 302)

        self.assertEqual(Equipo.objects.filter(contrato=lic).count(), 2)
        eq1 = Equipo.objects.get(numero_serie='SRV-CSV-001')
        self.assertEqual(eq1.marca, 'Dell')
        self.assertEqual(eq1.area_o_departamento, 'Laboratorio 1')

    def test_contratos_lista_zero_financial_references(self):
        """
        Verifica que en el listado de contratos/licitaciones no aparezcan referencias
        financieras ni símbolos de moneda ($).
        """
        self.client.login(username='admin_lic_test', password='testpassword123')
        lic = Contrato.objects.create(
            numero_licitacion='LIC-2026-0400',
            dependencia_cliente='ITSE Técnico',
            fecha_inicio=date.today(),
            fecha_fin=date.today() + timedelta(days=90),
            sla_horas_respuesta=4,
            sla_horas_solucion=24,
            penalizacion_por_retraso=500, # Campo en BD que NO debe mostrarse
            activo=True
        )

        res = self.client.get(reverse('contratos_lista'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'LIC-2026-0400')
        self.assertContains(res, 'SLA Respuesta / Solución')
        # Verificar ausencia total de signos de pesos o penalización financiera
        self.assertNotContains(res, '$500')
        self.assertNotContains(res, 'Penalización por Retraso')
