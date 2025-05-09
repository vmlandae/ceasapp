### Descripción:
# Este script es el punto de entrada de la aplicación de reemplazos cortos.
# En esta primera versión, se incluirán como usuarios solo a personas de la oficina central y a directivos de los colegios CEAS. No se incluirán docentes externos ni otros roles.
# La aplicación permitirá a los directivos de los colegios solicitar reemplazos cortos mediante un formulario con un requerimiento estandarizado y específico, 
# a la oficina central validar a los candidatos, seleccionar una terna de candidatos, contactarlos para confirmar disponibilidad,
# luego el colegio elige a uno de los candidatos, registrando la elección, y finalmente luego de la realización del reemplazo, 
# el colegio registra la recepción del servicio y la calificación del candidato.

# roles/tipos de usuarios y sus permisos:
# - owner: Dueño de la aplicación, puede ver y modificar todo, solo no puede eliminarse a sí mismo.
# - admin: Administrador de la aplicación, puede ver y modificar casi todo. No puede eliminar a owner, ni a los admin. 
# No puede modificar su propio rol.
# - oficina_central: puede ver todas las solicitudes de reemplazo,
#  validar a los candidatos, seleccionar a los candidatos,contactar a los candidatos,  
# ver las recepciones y enviar notificaciones y correos a los colegios y a los candidatos.
# - admin_colegio: puede ver las solicitudes de reemplazo de su colegio (activas y anteriores), puede editar las solicitudes de reemplazo de su colegio (con registro de la edición), 
#   puede crear nuevas solicitudes de reemplazo, seleccionar a los candidatos, elegir a un candidato, registrar la recepción del servicio y calificar al candidato.
# - user_colegio: puede ver las solicitudes de reemplazo hechas por el mismo, puede editar las solicitudes de reemplazo hechas por el mismo (con registro de la edición),
#   puede crear nuevas solicitudes de reemplazo, seleccionar a los candidatos, elegir a un candidato, registrar la recepción del servicio y calificar al candidato, pero solo de las solicitudes hechas por el mismo.


import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
if st.experimental_user.is_logged_in:
    print("Usuario logueado")
    print(st.experimental_user.to_dict())
st.session_state['connections'] = ["bd_reemplazos1", "bd_reemplazos2"]
# Importa los módulos de la carpeta ceas y de las páginas de la app
from ceas import schools_manager, user_management
from ceas.reemplazos import *
from ceas import config as cfg
import time

# Configuración de la página principal de Streamlit
st.set_page_config(page_title="Sistema de Reemplazos Cortos CEAS", layout="wide")

# Define el header principal
header = "Sistema de Reemplazos Cortos CEAS"
# Guarda el nombre de la app en session_state para que los managers lean la hoja correcta 
st.session_state["app_name"] = "app"


# vamos a definir las connections que se usarán en la app, 
# tanto por los archivos que leen como por los service accounts disponibles, para cuidar rate limits

st.session_state['connections'] = ["bd_reemplazos1", "bd_reemplazos2"]  
    
# Pantalla de login
def login_screen(header=header):
    """Pantalla de login."""
    st.image(cfg.PROJ_ROOT / "st" / "images" / "logo-ceas-2.png")
    st.header(header)
    st.subheader("Debes iniciar sesión para continuar.")
    # Botón para iniciar sesión con Google, que llama a st.login (configurado con OAuth)
    st.button("Iniciar sesión con Google", on_click=st.login)

# Inicialización del rol en session_state
if "role" not in st.session_state:
    st.session_state["role"] = None

# Si el usuario ya está logueado y aún no se ha asignado rol, obtenemos la info del usuario
if st.experimental_user.is_logged_in and st.session_state["role"] is None:
    try:
        st.session_state["user_data"] = st.experimental_user
        st.session_state["user_info"] = user_management.get_user_info(app_name=st.session_state["app_name"])
    except Exception as e:
        st.error("No se pudo obtener la información del usuario.")
        st.stop()
    # Asigna el rol (por ejemplo, "owner", "admin", "user", "admin_colegio", etc.)
    st.session_state["role"] = st.session_state["user_info"]["role"]

# Definición de páginas utilizando st.Page (suponiendo que cada uno es un script en st/compras/)
# admin_panel: Panel de administración de usuarios y colegios
# permisos: owner, admin pueden ver y editar casi todo
# oficina_central puede ver todo, pero no editar usuarios
# admin_colegio puede ver su colegio y sus usuarios, y no puede editar nada
# user_colegio no puede ver nada
admin_panel = st.Page(st.session_state["app_name"] + "/admin_panel.py", title="Panel de Administración de Usuarios", icon=":material/dashboard:")

# panel de solicitudes de colegios: Panel de solicitudes de reemplazos de los colegios
# owner, admin y oficina_central pueden ver todo. Admin y owner pueden editar. 
# Oficina_central no puede editar, pero puede enviar notificaciones/correos y puede asignar o reasignar responsables en las solicitudes.

# casilla personas@ceas.cl donde se envía una notificación cuando se crea una nueva solicitud, y cualquier miembro del equipo puede abrir la solicitud y asignar un responsable (que puede ser él mismo)

# admin_colegio y user_colegio pueden ver y editar las solicitudes de su colegio.
# admin_colegio y user_colegio pueden crear una nueva solicitud con formulario prellenado con los datos de su colegio
# en pantalla o con un botón que abra formulario de google prellenado, con el link al formulario de google para compartirlo. 

panel_solicitudes_colegios = st.Page(st.session_state["app_name"] + "/panel_solicitudes_colegios.py", title="Panel de Solicitudes de Colegios", icon=":material/assignment:")

# panel_validacion_candidatos: Panel de validación de candidatos, donde la oficina central puede validar a los candidatos inscritos en el formulario de reemplazos.
# owner, admin y oficina_central pueden ver todo. Admin, owner y oficina_central pueden editar.
# admin_colegio y user_colegio no pueden ver ni editar.
panel_validacion_candidatos = st.Page(st.session_state["app_name"] + "/panel_validacion_candidatos.py", title="Panel de Validación de Candidatos", icon=":material/assignment_turned_in:")


# panel_seleccion_candidatos: Panel de elección de candidatos, donde la oficina central busca candidatos acordes con los requerimientos de la solicitud,
#  que estén previamente validados, selecciona a los candidatos, los envía al colegio para que contacte y elija a uno
# owner, admin y oficina_central pueden ver todo. Admin, owner y oficina_central pueden editar.
# admin_colegio y user_colegio no pueden ver ni editar.

# QUE SEA MÁS AUTOMATIZADO: 
# - seleccionar 3 candidatos (tener una sugerencia automática), 
# - botón para enviar correo al colegio con los antecedentes de los candidatos y un link para que el colegio elija a uno.
# - a quién se lo envía? a quien lo solicita con copia al director del colegio, coordinador, administrador, etc.
# 

panel_seleccion_candidatos = st.Page(st.session_state["app_name"] + "/panel_seleccion_candidato.py", title="Panel de Selección de Candidatos", icon=":material/assignment_ind:")

# panel_eleccion_candidato_colegio: Panel de elección de candidato por parte del colegio, 
# donde el colegio contacta a el/los candidatos, elige a un candidato y registra la elección.
# owner, admin y oficina_central pueden ver todo. Oficina central no puede editar.
# admin_colegio y user_colegio pueden ver y elegir candidatos de las solicitudes de su colegio.
panel_eleccion_candidato_colegio = st.Page(st.session_state["app_name"] + "/panel_eleccion_candidato_colegio.py", title="Panel de Elección de Candidato", icon=":material/assignment_turned_in:")

# panel_recepciones: Panel de recepciones de servicios, donde el colegio registra la recepción del servicio y califica al candidato.
# owner, admin y oficina_central pueden ver todo. Oficina central no puede editar.
# admin_colegio y user_colegio pueden ver y calificar las recepciones de servicios de su colegio.
panel_recepciones = st.Page(st.session_state["app_name"] + "/panel_recepciones.py", title="Panel de Recepciones", icon=":material/thumb_up:")
# ajustes: Panel de ajustes de la aplicación
# owner y admin pueden ver y editar todo.
ajustes = st.Page(st.session_state["app_name"] + "/ajustes.py", title="Ajustes", icon=":material/settings:")
logout_page = st.Page(st.logout, title="Cerrar sesión", icon=":material/logout:")
login_page = st.Page(login_screen, title="Login", icon=":material/login:")

# Configuración del diccionario de navegación en función del rol
page_dict = {}

if st.session_state.role in ["owner", "admin"]:
    page_dict["Panel de Administración"] = [admin_panel]
    page_dict["Panel de Solicitudes de Colegios"] = [panel_solicitudes_colegios]
    page_dict["Panel de Validación de Candidatos"] = [panel_validacion_candidatos]
    page_dict["Panel de Selección de Candidatos"] = [panel_seleccion_candidatos]
    page_dict["Panel de Elección de Candidato"] = [panel_eleccion_candidato_colegio]
    page_dict["Panel de Recepciones"] = [panel_recepciones]
    page_dict["Ajustes"] = [ajustes, logout_page]
elif st.session_state.role in ["oficina_central"]:
    page_dict["Panel de Solicitudes de Colegios"] = [panel_solicitudes_colegios]
    page_dict["Panel de Validación de Candidatos"] = [panel_validacion_candidatos]
    page_dict["Panel de Selección de Candidatos"] = [panel_seleccion_candidatos]
    page_dict["Panel de Elección de Candidato"] = [panel_eleccion_candidato_colegio]
    page_dict["Panel de Recepciones"] = [panel_recepciones]
    page_dict["Ajustes"] = [ajustes, logout_page]
elif st.session_state.role in ["admin_colegio", "user_colegio"]:
    page_dict["Mis Solicitudes"] = [panel_solicitudes_colegios,panel_eleccion_candidato_colegio]
    page_dict["Calificar Reemplazos"] = [panel_recepciones]
    page_dict["Ajustes"] = [ajustes, logout_page]

# Si no hay un rol definido, mostramos la pantalla de login
if not page_dict:
    page_dict["Login"] = [login_page]

# Muestra el logo (opcional) y lanza la navegación
st.logo(cfg.PROJ_ROOT / "st" / "images" / "logo-ceas-2.png")
pg = st.navigation(page_dict)

pg.run()

