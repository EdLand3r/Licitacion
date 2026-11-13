from django.db import models
from apps.contracts.models import Contrato, Sede


class Equipo(models.Model):
    class TipoEquipo(models.TextChoices):
        DESKTOP = 'DESKTOP', 'Computadora de Escritorio'
        LAPTOP = 'LAPTOP', 'Laptop / Portátil'
        ALL_IN_ONE = 'AIO', 'All-in-One (Todo en Uno)'
        SERVIDOR = 'SERVIDOR', 'Servidor de Red'
        IMPRESORA = 'IMPRESORA', 'Impresora / Multifuncional'
        PERIFERICO = 'PERIFERICO', 'Periférico / Dispositivo Especial'

    class EstatusOperativo(models.TextChoices):
        OPERATIVO = 'OPERATIVO', 'Operativo / En Funcionamiento'
        EN_MANTENIMIENTO = 'EN_MANTENIMIENTO', 'En Mantenimiento (OT Abierta)'
        EN_FALLA = 'EN_FALLA', 'Falla Reportada (Ticket Abierto)'
        BAJA = 'BAJA', 'Baja Técnica / Retirado de Servicio'

    contrato = models.ForeignKey(
        Contrato,
        on_delete=models.CASCADE,
        related_name='equipos',
        verbose_name='Contrato Vigente'
    )
    sede = models.ForeignKey(
        Sede,
        on_delete=models.CASCADE,
        related_name='equipos',
        verbose_name='Sede / Ubicación'
    )
    numero_serie = models.CharField(
        max_length=100,
        unique=True,
        verbose_name='Número de Serie / Service Tag',
        help_text='Identificador único del fabricante. Imprescindible para auditorías y control legal'
    )
    codigo_inventario_interno = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Código de Inventario Cliente / Pliego',
        help_text='Etiqueta de inventario oficial de la dependencia gubernamental'
    )
    tipo_equipo = models.CharField(
        max_length=20,
        choices=TipoEquipo.choices,
        default=TipoEquipo.DESKTOP,
        verbose_name='Tipo de Equipo'
    )
    marca = models.CharField(
        max_length=100,
        verbose_name='Marca',
        help_text='Ej: Dell, HP, Lenovo, Asus, Apple'
    )
    modelo = models.CharField(
        max_length=150,
        verbose_name='Modelo',
        help_text='Ej: OptiPlex 7090, ThinkCentre M720q, ProBook 450'
    )
    area_o_departamento = models.CharField(
        max_length=150,
        blank=True,
        verbose_name='Área o Departamento',
        help_text='Ej: Subdirección de Recursos Materiales, Laboratorio 2'
    )
    usuario_asignado_nombre = models.CharField(
        max_length=150,
        blank=True,
        verbose_name='Usuario o Funcionario Asignado',
        help_text='Nombre del empleado público o custodio que usa el equipo'
    )
    estatus_operativo = models.CharField(
        max_length=20,
        choices=EstatusOperativo.choices,
        default=EstatusOperativo.OPERATIVO,
        verbose_name='Estatus Operativo'
    )
    accesorios_incluidos = models.TextField(
        blank=True,
        verbose_name='Accesorios y Periféricos Vinculados',
        help_text='Cargador, cable de poder, ratón, teclado, monitor auxiliar, fundas'
    )
    estado_estetico_inicial = models.TextField(
        blank=True,
        verbose_name='Condición Física / Estética Inicial',
        help_text='Rayones, golpes en gabinete, tornillos faltantes, roturas (protege legalmente al proveedor)'
    )
    pin_o_contraseña_acceso = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='PIN / Usuario de Acceso SO',
        help_text='Contraseña temporal o confirmación de si se entregó desbloqueado'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Equipo de Cómputo'
        verbose_name_plural = 'Inventario de Equipos'
        ordering = ['contrato', 'sede', 'tipo_equipo', 'numero_serie']

    def __str__(self):
        return f"{self.numero_serie} | {self.marca} {self.modelo} ({self.get_tipo_equipo_display()})"


class EspecificacionHardware(models.Model):
    class FactorFormaMotherboard(models.TextChoices):
        ATX = 'ATX', 'ATX Estándar'
        MICRO_ATX = 'MICRO_ATX', 'Micro-ATX'
        MINI_ITX = 'MINI_ITX', 'Mini-ITX'
        PROPIETARIO = 'PROPIETARIO', 'Propietario / OEM (Dell/HP/Lenovo)'

    class TipoRAM(models.TextChoices):
        DDR5 = 'DDR5', 'DDR5 SDRAM'
        DDR4 = 'DDR4', 'DDR4 SDRAM'
        DDR3 = 'DDR3', 'DDR3 SDRAM'
        OTRO = 'OTRO', 'Otro estándar'

    class TipoAlmacenamiento(models.TextChoices):
        SSD_NVME = 'SSD_NVME', 'SSD NVMe M.2 (PCIe)'
        SSD_SATA = 'SSD_SATA', 'SSD SATA III (2.5")'
        HDD_MECANICO = 'HDD', 'Disco Duro Mecánico (HDD 3.5" / 2.5")'
        HIBRIDO = 'HIBRIDO', 'Almacenamiento Dual (SSD + HDD)'

    equipo = models.OneToOneField(
        Equipo,
        on_delete=models.CASCADE,
        related_name='especificaciones',
        verbose_name='Equipo Vinculado'
    )
    # Procesador (CPU)
    cpu_marca_modelo = models.CharField(
        max_length=150,
        blank=True,
        verbose_name='Procesador (CPU)',
        help_text='Ej: Intel Core i7-13700, AMD Ryzen 5 5600G, Intel Pentium G3250'
    )
    cpu_nucleos_hilos = models.CharField(
        max_length=50,
        blank=True,
        verbose_name='Núcleos / Hilos CPU'
    )
    cpu_frecuencia_base = models.CharField(
        max_length=50,
        blank=True,
        verbose_name='Frecuencia Base / Turbo (GHz)'
    )
    # Placa Base / Motherboard
    motherboard_marca_modelo = models.CharField(
        max_length=150,
        blank=True,
        verbose_name='Tarjeta Madre (Motherboard)'
    )
    motherboard_factor_forma = models.CharField(
        max_length=20,
        choices=FactorFormaMotherboard.choices,
        default=FactorFormaMotherboard.MICRO_ATX,
        verbose_name='Factor de Forma Motherboard'
    )
    chipset = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Chipset de la Placa'
    )
    bios_uefi_version = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Versión de BIOS / UEFI'
    )
    # Memoria RAM
    ram_capacidad_gb = models.PositiveIntegerField(
        default=8,
        verbose_name='Capacidad Total de RAM (GB)'
    )
    ram_tecnologia = models.CharField(
        max_length=10,
        choices=TipoRAM.choices,
        default=TipoRAM.DDR4,
        verbose_name='Tecnología de Memoria'
    )
    ram_frecuencia_mhz = models.CharField(
        max_length=50,
        blank=True,
        verbose_name='Frecuencia RAM (MHz)',
        help_text='Ej: 2666 MHz, 3200 MHz, 5600 MHz'
    )
    ram_ranuras_ocupadas = models.CharField(
        max_length=50,
        blank=True,
        verbose_name='Ranuras Ocupadas / Disponibles',
        help_text='Ej: 1 de 2 ranuras (DIMM / SO-DIMM)'
    )
    # Almacenamiento
    almacenamiento_tipo = models.CharField(
        max_length=20,
        choices=TipoAlmacenamiento.choices,
        default=TipoAlmacenamiento.SSD_NVME,
        verbose_name='Tipo de Disco / Almacenamiento'
    )
    almacenamiento_capacidad_gb = models.PositiveIntegerField(
        default=512,
        verbose_name='Capacidad de Almacenamiento (GB)',
        help_text='Capacidad en Gigabytes (ej: 256, 512, 1000)'
    )
    # Tarjeta Gráfica
    gpu_descripcion = models.CharField(
        max_length=150,
        blank=True,
        verbose_name='Tarjeta Gráfica (GPU)',
        help_text='Integrada (Intel UHD / Radeon) o Dedicada (NVIDIA RTX / AMD Radeon)'
    )
    # Energía y Refrigeración
    psu_watts = models.CharField(
        max_length=50,
        blank=True,
        verbose_name='Fuente de Alimentación (PSU)',
        help_text='Potencia (Watts) y conector (ATX 500W, OEM 260W 80 Plus)'
    )
    tipo_refrigeracion = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Sistema de Refrigeración',
        default='Disipador térmico con ventilador por aire'
    )
    # Sistema Operativo y Software
    sistema_operativo = models.CharField(
        max_length=100,
        default='Windows 11 Pro 64 bits',
        verbose_name='Sistema Operativo Instalado'
    )
    antivirus = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Solución Antivirus / Endpoint'
    )

    class Meta:
        verbose_name = 'Especificación de Hardware'
        verbose_name_plural = 'Especificaciones de Hardware'

    def __str__(self):
        return f"Specs de {self.equipo.numero_serie} ({self.cpu_marca_modelo}, {self.ram_capacidad_gb}GB RAM, {self.almacenamiento_capacidad_gb}GB {self.get_almacenamiento_tipo_display()})"
