# Spartan PC &mdash; GMAO / CMMS para Licitaciones y Mantenimiento de TI

Sistema de Gestión de Mantenimiento Asistido por Ordenador (GMAO / CMMS) especializado en el cumplimiento y comprobación de contratos y licitaciones de servicios de TI para dependencias del sector público y corporativos.

Desarrollado con base en los requerimientos del proyecto de **Arquitectura de Computadoras** del **Instituto Tecnológico Superior de Escárcega (ITSE)**.

---

## 🌟 Características Principales

1. **Gestión de Licitaciones y Sedes (P2):**
   * Registro de pliegos, contratos, vigencias y penalizaciones por hora de retraso.
   * Parametrización estricta de tiempos máximos de respuesta y solución (**SLA Contractual**).
2. **Inventario y Arquitectura de Computadoras (P3):**
   * Ficha técnica detallada por activo: Procesador (CPU), Tarjeta Madre (Factor de forma ATX, Micro-ATX), Memoria RAM (DDR4/DDR5), Almacenamiento (SSD NVMe PCIe / SATA / HDD), GPU, Fuente de Poder (PSU) y Sistema Operativo.
   * Registro del estado estético inicial y accesorios recibidos (protección legal ante quejas del cliente).
3. **Mantenimientos Preventivos y Checklists Oficiales (P4, P7):**
   * Calendario de intervenciones periódicas semestrales / anuales.
   * Checklist técnico exhaustivo con medidas de seguridad (pulsera antiestática, mesa no conductora), limpieza de hardware (filtros, soplado, limpieza de contactos dorados con solvente dieléctrico, pasta térmica) y mantenimiento lógico (TRIM en SSD, parches, antivirus, backups).
4. **Mesa de Ayuda y Flujo Correctivo (P5, P6):**
   * Apertura de tickets por parte del enlace de la dependencia con cálculo automático de fecha límite SLA.
   * Asignación y despacho a técnicos operativos de campo.
5. **Control de Refacciones y Almacén (P8):**
   * Catálogo de piezas de repuesto (discos, pasta térmica, pilas CR2032, fuentes).
   * Alertas automáticas cuando el stock cae por debajo del punto de reorden.
6. **Reporte Técnico Oficial de Mantenimiento (P9, P10):**
   * Maqueta digital fiel al formato oficial foliado (página 21 del documento ITSE) con diagnóstico trifásico (Falla reportada, Causa raíz, Solución aplicada paso a paso).
   * Firmas electrónicas de validación y conformidad (técnico y enlace cliente).
   * Listo para impresión en PDF para comprobación ante órganos fiscalizadores y auditorías.

---

## 🚀 Puesta en Marcha Rápida (Local con SQLite)

El proyecto viene preconfigurado con SQLite para desarrollo inmediato:

```bash
# 1. Activar entorno virtual
source .venv/bin/activate

# 2. Aplicar migraciones
python manage.py migrate

# 3. Cargar datos de prueba del ITSE (usuarios, contrato, equipos y OTs)
python manage.py seed_data

# 4. Iniciar servidor de desarrollo
python manage.py runserver
```

Abre tu navegador en: [http://127.0.0.1:8000](http://127.0.0.1:8000)

---

## 🐳 Despliegue con Docker Compose (MySQL 8.0)

Para ejecutar el entorno completo en contenedores con base de datos MySQL:

```bash
# Construir e iniciar contenedores
docker compose up -d --build

# Ejecutar poblado de datos inicial en el contenedor web
docker compose exec web python manage.py seed_data
```

---

## 👥 Cuentas de Demostración Preconfiguradas (7 Roles)

Todas las cuentas vienen con contraseña `nombre_rol + 123`:

| Rol en el Sistema | Usuario | Contraseña | Propósito |
| :--- | :--- | :--- | :--- |
| **Coordinador** | `coordinador` | `coordinador123` | Supervisión de OTs, asignación a técnicos y semáforos SLA |
| **Técnico** | `tecnico` | `tecnico123` | Ejecución en sitio, llenado de checklists y firmas |
| **Enlace Dependencia (Cliente)** | `enlace` | `enlace123` | Levantamiento de tickets y firma de recepción conforme |
| **Responsable Licitaciones** | `licitaciones` | `licitaciones123` | Gestión de contratos, SLAs y reportes de auditoría |
| **Encargado de Almacén** | `almacen` | `almacen123` | Existencias y despacho de refacciones |
| **Administrador del Sistema** | `admin` | `admin123` | Catálogos globales y panel `/admin/` de Django |
