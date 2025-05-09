# ceasApp - Sistema de Compras

<a target="_blank" href="https://cookiecutter-data-science.drivendata.org/">
    <img src="https://img.shields.io/badge/CCDS-Project%20template-328F97?logo=cookiecutter" />
</a>



CeasApp es una webapp diseñadas para la gestión y monitoreo de entregas de órdenes de compra para CEAS. La aplicación permite administrar compras globales, distribuir órdenes a colegios, gestionar incidencias y recepciones, y ofrece paneles personalizados según el rol del usuario.

## Características Principales

- **Gestión de Compras Globales:**  
  Permite crear, actualizar y eliminar registros de compras (purchases) que representan la compra global de un producto a un proveedor, incluyendo datos como producto, proveedor, departamento, costo unitario y cantidad total.

- **Distribución de Órdenes (Orders):**  
  Las compras se distribuyen a los colegios mediante órdenes (orders) que asignan la cantidad de producto que recibe cada institución. Se registra el estado de entrega de cada orden.

- **Gestión de Incidencias:**  
  Los usuarios pueden reportar problemas en la entrega (faltantes, defectos, etc.), que se registran como incidencias. Las incidencias pueden ser actualizadas, reasignadas y tienen un historial de acciones (incidence actions).

- **Recepciones:**  
  Cada colegio puede registrar recepciones (receipts) que confirmen la entrega de los productos, permitiendo actualizaciones parciales y correcciones.

- **Panel de Administración:**  
  Usuarios con roles "owner", "admin" o "oficina_central" tienen acceso a paneles administrativos para gestionar usuarios, colegios, incidencias y notificaciones.

- **Notificaciones:**  
  Se integran notificaciones vía correo electrónico (Gmail API o SMTP) y se exploran opciones para notificaciones vía WhatsApp.

- **Integración con Google Sheets y Apps Script:**  
  Los datos se almacenan en Google Sheets siguiendo un esquema relacional. Además, se cuenta con un módulo para interactuar con Google Apps Script para tareas específicas.

## Estructura del Proyecto

ceasApp/
├── README.md
├── requirements.txt
├── setup.cfg
├── ceas/
│   ├── init.py
│   ├── config.py
│   ├── user_management.py
│   ├── purchases_manager.py
│   ├── orders_manager.py
│   ├── incidences_manager.py
│   ├── incidence_actions_manager.py
│   ├── receipts_manager.py
│   ├── notifications.py
│   └── apps_script_manager.py
└── st/
├── app_compras.py
├── images/
└── compras/
├── admin_panel.py
├── panel_incidencias.py
├── sistema_compras.py
├── ajustes.py
└── receipts_panel.py


## Requisitos y Dependencias

- Python 3.10 o superior
- Streamlit
- streamlit_gsheets
- google-api-python-client
- google-auth
- pandas

Instala las dependencias con:

```bash
pip install -r requirements.txt
```

## Configuración
- **Google Sheets API:** 
Se utiliza la API de Google Sheets mediante un service account. Configura las credenciales y comparte las hojas necesarias con el email del service account.

- **Autenticación en Streamlit:**
La app utiliza la autenticación de Google (st.experimental_user) para gestionar sesiones y roles. Asegúrate de configurar correctamente el OAuth.

- **Apps Script y Notificaciones:**
Revisa el módulo apps_script_manager.py y notifications.py para la integración con Google Apps Script y el envío de notificaciones.

## Cómo Ejecutar la Aplicación
Desde la raíz del proyecto, ejecuta:

```bash
streamlit run st/app_compras.py
```

La aplicación se desplegará y podrás navegar entre las distintas páginas (Admin Panel, Sistema de Compras, Recepciones, Ajustes) según el rol del usuario autenticado.

## Futuras Mejoras
Notificaciones vía WhatsApp:
Explora la integración con Twilio o la API oficial de WhatsApp Business para notificaciones automáticas.

## Auditoría y Logs:
Implementa una tabla de auditoría para registrar cambios críticos en los datos (creación, actualización, eliminación).

## Mejor Gestión de Concurrency:
Añade validación de versiones en cada operación de update para evitar conflictos de edición concurrente.

## Optimización y Escalabilidad:
Considera migrar a una base de datos relacional si la cantidad de datos o la concurrencia aumenta considerablemente.

## Contribuciones
Si deseas contribuir, por favor abre un issue o envía un pull request con tus mejoras y sugerencias.

