from django.test import TestCase, Client
from django.urls import reverse
from apps.authentication.models import User
from apps.warehouse.models import (
    Refaccion,
    MovimientoInventario,
    AsignacionInsumoTecnico,
    MovimientoInsumoTecnico,
)


class InsumosTecnicosTestCase(TestCase):
    def setUp(self):
        self.client = Client()

        # Usuarios con distintos roles RBAC
        self.admin = User.objects.create_user(
            username='admin_alm',
            password='testpassword123',
            role=User.Role.ADMIN
        )
        self.coordinador = User.objects.create_user(
            username='coord_alm',
            password='testpassword123',
            role=User.Role.COORDINADOR
        )
        self.almacen = User.objects.create_user(
            username='almacen_alm',
            password='testpassword123',
            role=User.Role.ALMACEN
        )
        self.tecnico1 = User.objects.create_user(
            username='tec1_alm',
            password='testpassword123',
            first_name='Michel',
            last_name='Morales',
            role=User.Role.TECNICO
        )
        self.tecnico2 = User.objects.create_user(
            username='tec2_alm',
            password='testpassword123',
            first_name='Cesar',
            last_name='Lozano',
            role=User.Role.TECNICO
        )
        self.enlace = User.objects.create_user(
            username='enlace_alm',
            password='testpassword123',
            role=User.Role.ENLACE
        )

        # Insumos en almacén central
        self.pasta = Refaccion.objects.create(
            codigo_parte='INS-TEST-PASTA-01',
            nombre='Pasta Térmica de Prueba',
            categoria=Refaccion.CategoriaRefaccion.REFRIGERACION,
            stock_actual=20,
            stock_minimo_alerta=5,
            unidad_medida='Jeringa'
        )
        self.alcohol = Refaccion.objects.create(
            codigo_parte='INS-TEST-ALCOHOL-01',
            nombre='Alcohol Isopropílico Test',
            categoria=Refaccion.CategoriaRefaccion.CONSUMIBLE,
            stock_actual=15,
            stock_minimo_alerta=3,
            unidad_medida='Botella'
        )

    def test_rbac_insumos_tecnicos_access(self):
        # 1. Enlace cliente no tiene permiso -> 302 a unauthorized
        self.client.login(username='enlace_alm', password='testpassword123')
        res = self.client.get(reverse('insumos_tecnicos'))
        self.assertEqual(res.status_code, 302)
        self.assertIn(reverse('unauthorized'), res.url)

        # 2. Técnico puede ver su propio kit (200)
        self.client.login(username='tec1_alm', password='testpassword123')
        res = self.client.get(reverse('insumos_tecnicos'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Mi Kit de Insumos')

        # 3. Almacén puede ver la gestión global de técnicos (200)
        self.client.login(username='almacen_alm', password='testpassword123')
        res = self.client.get(reverse('insumos_tecnicos'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Gestión de Insumos por Técnico')

    def test_dotacion_insumo_a_tecnico(self):
        # Encargado de almacén dota 4 jeringas de pasta térmica al técnico 1
        self.client.login(username='almacen_alm', password='testpassword123')
        post_data = {
            'tecnico_id': self.tecnico1.id,
            'insumo_id': self.pasta.id,
            'cantidad': '4',
            'observaciones': 'Dotación para kit de mantenimiento semestral'
        }
        res = self.client.post(reverse('dotar_insumo_tecnico'), post_data)
        self.assertEqual(res.status_code, 302)

        # Almacén central se descuenta de 20 a 16
        self.pasta.refresh_from_db()
        self.assertEqual(self.pasta.stock_actual, 16)

        # Técnico 1 recibe 4 piezas en su kit
        asig = AsignacionInsumoTecnico.objects.get(tecnico=self.tecnico1, insumo=self.pasta)
        self.assertEqual(asig.cantidad_disponible, 4)

        # Auditorías registradas
        mov_tec = MovimientoInsumoTecnico.objects.filter(tecnico=self.tecnico1, insumo=self.pasta).first()
        self.assertIsNotNone(mov_tec)
        self.assertEqual(mov_tec.tipo_operacion, MovimientoInsumoTecnico.TipoOperacion.DOTACION)
        self.assertEqual(mov_tec.cantidad, 4)
        self.assertEqual(mov_tec.autorizado_por, self.almacen)

        mov_alm = MovimientoInventario.objects.filter(refaccion=self.pasta).first()
        self.assertIsNotNone(mov_alm)
        self.assertEqual(mov_alm.tipo_movimiento, MovimientoInventario.TipoMovimiento.SALIDA_OT)
        self.assertEqual(mov_alm.cantidad, 4)

    def test_dotacion_stock_insuficiente(self):
        # Intentar dotar 50 jeringas cuando solo hay 20 disponibles
        self.client.login(username='almacen_alm', password='testpassword123')
        post_data = {
            'tecnico_id': self.tecnico1.id,
            'insumo_id': self.pasta.id,
            'cantidad': '50',
            'observaciones': 'Exceso intencional'
        }
        res = self.client.post(reverse('dotar_insumo_tecnico'), post_data)
        self.assertEqual(res.status_code, 302)

        self.pasta.refresh_from_db()
        self.assertEqual(self.pasta.stock_actual, 20)  # Sin cambios
        self.assertFalse(AsignacionInsumoTecnico.objects.filter(tecnico=self.tecnico1, insumo=self.pasta).exists())

    def test_devolucion_insumo_al_almacen(self):
        # Asignar previamente 5 unidades al técnico
        asig = AsignacionInsumoTecnico.objects.create(
            tecnico=self.tecnico1,
            insumo=self.alcohol,
            cantidad_disponible=5,
            stock_minimo_kit=2
        )
        self.alcohol.stock_actual = 10
        self.alcohol.save()

        # Técnico devuelve 2 botellas sobrantes
        self.client.login(username='tec1_alm', password='testpassword123')
        post_data = {
            'tecnico_id': self.tecnico1.id,
            'insumo_id': self.alcohol.id,
            'cantidad': '2',
            'observaciones': 'Sobrante tras jornada de preventivo'
        }
        res = self.client.post(reverse('devolver_insumo_tecnico'), post_data)
        self.assertEqual(res.status_code, 302)

        # En posesión del técnico quedan 3
        asig.refresh_from_db()
        self.assertEqual(asig.cantidad_disponible, 3)

        # En almacén central sube de 10 a 12
        self.alcohol.refresh_from_db()
        self.assertEqual(self.alcohol.stock_actual, 12)

        # Auditoría de devolución
        mov_tec = MovimientoInsumoTecnico.objects.filter(
            tecnico=self.tecnico1,
            insumo=self.alcohol,
            tipo_operacion=MovimientoInsumoTecnico.TipoOperacion.DEVOLUCION
        ).first()
        self.assertIsNotNone(mov_tec)
        self.assertEqual(mov_tec.cantidad, 2)

    def test_registrar_consumo_mantenimiento(self):
        # Asignar 3 piezas
        asig = AsignacionInsumoTecnico.objects.create(
            tecnico=self.tecnico1,
            insumo=self.pasta,
            cantidad_disponible=3,
            stock_minimo_kit=2
        )

        # Técnico consume 1 pieza en un mantenimiento preventivo
        self.client.login(username='tec1_alm', password='testpassword123')
        post_data = {
            'tecnico_id': self.tecnico1.id,
            'insumo_id': self.pasta.id,
            'cantidad': '1',
            'motivo': 'Aplicación en CPU de servidor OTP-202611-0001'
        }
        res = self.client.post(reverse('registrar_consumo_insumo'), post_data)
        self.assertEqual(res.status_code, 302)

        asig.refresh_from_db()
        self.assertEqual(asig.cantidad_disponible, 2)

        # Auditoría de consumo
        mov_tec = MovimientoInsumoTecnico.objects.filter(
            tecnico=self.tecnico1,
            insumo=self.pasta,
            tipo_operacion=MovimientoInsumoTecnico.TipoOperacion.CONSUMO_MANTENIMIENTO
        ).first()
        self.assertIsNotNone(mov_tec)
        self.assertEqual(mov_tec.cantidad, 1)
        self.assertIn('OTP-202611-0001', mov_tec.observaciones)

    def test_alerta_kit_bajo(self):
        # Cantidad disponible <= stock_minimo_kit -> kit_bajo debe ser True
        asig = AsignacionInsumoTecnico.objects.create(
            tecnico=self.tecnico1,
            insumo=self.pasta,
            cantidad_disponible=1,
            stock_minimo_kit=2
        )
        self.assertTrue(asig.kit_bajo)

        # Si se abastece por encima del mínimo -> kit_bajo debe ser False
        asig.cantidad_disponible = 3
        asig.save()
        self.assertFalse(asig.kit_bajo)
