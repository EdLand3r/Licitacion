from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = 'ADMIN', 'Administrador del Sistema'
        RESPONSABLE_LICITACIONES = 'RESPONSABLE_LICITACIONES', 'Responsable de Licitaciones'
        COORDINADOR = 'COORDINADOR', 'Coordinador de Mantenimiento'
        TECNICO = 'TECNICO', 'Técnico de Mantenimiento'
        ENLACE = 'ENLACE', 'Enlace de la Dependencia (Cliente)'
        ALMACEN = 'ALMACEN', 'Encargado de Almacén'
        CORREO_EXTERNO = 'CORREO_EXTERNO', 'Servicio de Correo Externo'

    role = models.CharField(
        max_length=30,
        choices=Role.choices,
        default=Role.COORDINADOR,
        verbose_name='Rol en el Sistema'
    )
    phone = models.CharField(
        max_length=20,
        blank=True,
        verbose_name='Teléfono de Contacto'
    )
    dependencia_o_empresa = models.CharField(
        max_length=150,
        blank=True,
        verbose_name='Dependencia o Empresa',
        help_text='Nombre de la dependencia pública o empresa contratante'
    )
    cargo = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Puesto o Cargo'
    )

    class Meta:
        verbose_name = 'Usuario'
        verbose_name_plural = 'Usuarios'
        ordering = ['last_name', 'first_name', 'username']

    def __str__(self):
        full_name = self.get_full_name()
        return f"{full_name if full_name else self.username} ({self.get_role_display()})"

    @property
    def is_admin_sistema(self):
        return self.role == self.Role.ADMIN or self.is_superuser

    @property
    def is_responsable_licitaciones(self):
        return self.role == self.Role.RESPONSABLE_LICITACIONES

    @property
    def is_coordinador(self):
        return self.role == self.Role.COORDINADOR

    @property
    def is_tecnico(self):
        return self.role == self.Role.TECNICO

    @property
    def is_enlace_cliente(self):
        return self.role == self.Role.ENLACE

    @property
    def is_encargado_almacen(self):
        return self.role == self.Role.ALMACEN
