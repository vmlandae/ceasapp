import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import random
import pickle
import ceas.config as cfg
from ceas.utils import cleanup_applicants,read_requests_from_gsheet,clean_gform_requests
from ceas.serialize_data import serialize_request_for_sheets
import json
# Configuración de la página principal de Streamlit
st.set_page_config(page_title="Sistema de Reemplazos Cortos CEAS", layout="wide")

with open(cfg.PROJ_ROOT / "gform_map.json") as f:
    st.session_state['gform_map'] = json.load(f)



st.session_state['fake_data'] = False # Para usar datos falsos
#st.session_state['fake_data'] = False # Para usar datos reales

if st.session_state['fake_data']:
    st.session_state['connections'] = ["bd_reemplazos1_fake", "bd_reemplazos2_fake"]
else:
    st.session_state['connections'] = ["bd_reemplazos1", "bd_reemplazos2"]
# Importa los módulos de la carpeta ceas y de las páginas de la app

st.session_state['solicitudes_gform_connections'] = ["bd_solicitudes1", "bd_solicitudes2"]
st.session_state['solicitudes_gform_sheet_name'] = "Respuestas de formulario 3"

from ceas.reemplazos import *
from ceas import config as cfg
import time


# Guarda el nombre de la app en session_state para que los managers lean la hoja correcta 
st.session_state["app_name"] = "appReemplazos"
st.session_state['sheet_names'] = ["Users", "Schools", "Applicants", "Candidates", "Requests", 
                                   "RequestCandidates","Receptions", "UserValidations"]#
# sheet_names es una concatenación de app_name + sheet_name
st.session_state['sheet_names'] = [st.session_state["app_name"] + sheet_name for sheet_name in st.session_state['sheet_names']]

# definimos los roles que pueden tener los usuarios: ["owner", "admin", "oficina_central", "admin_colegio", "user_colegio"] y luego
# pasamos a una serie de pandas que tenga un orden categórico para poder comparar los roles

st.session_state['roles'] = ["owner", "admin", "oficina_central", "admin_colegio", "user_colegio"]
# ahora lo transformamos a una categoría ordenada
# st.session_state['roles_rank'] = {role: i for i, role in enumerate(st.session_state['roles'])}

st.session_state['roles_rank'] = {
    "owner": 0,
    "admin": 1,
    "oficina_central": 2,
    "admin_colegio": 3,
    "user_colegio": 4
}

# Nivel educativo: multiselect con las siguientes opciones:
# "Inicial (PreKinder/Kinder)", "Básica", "Media", "Técnico Profesional", "Educación Diferencial"

# Curso(s): multiselect de cursos, dependiendo del nivel educativo seleccionado
# en el caso de "Inicial (PreKinder/Kinder)", los cursos son "PreKinder" y "Kinder"
# en el caso de "Básica", los cursos son "1° Básico", "2° Básico", ..., "8° Básico"
# en el caso de "Media", los cursos son "1° Medio", "2° Medio", "3° Medio", "4° Medio"
# en el caso de "Técnico Profesional", los cursos podrían ser  "3° Medio", "4° Medio" 
# en el caso de "Educación Diferencial", los cursos podrían ser desde PreKinder hasta 4° Medio

# Asignatura(s): multiselect dependiente de los niveles/cursos seleccionados:
# en el caso de inicial no hay asignaturas (no se muestra el multiselect) #TODO: preguntar si es necesario
# en el caso de básica, las asignaturas son "Generalista", "Lenguaje y Comunicación", "Matemáticas", "Ciencias Naturales", "Historia, Geografía y Ciencias Sociales", "Educación Física y Salud", "Artes Visuales", "Artes Musicales", "Tecnología","Orientación", "Religión", "Inglés"
# en el caso de media, las asignaturas son "Lenguaje y Comunicación", "Matemáticas", "Ciencias Naturales", "Historia, Geografía y Ciencias Sociales", 
# "Educación Física y Salud", "Artes Visuales", "Artes Musicales", "Tecnología", "Orientación", "Religión", "Filosofía", "Inglés", "Física", "Química", "Biología", 
# en el caso de técnico profesional, las asignaturas son "Electricidad","Mecánica Automotriz","Construcción","Hotelería","Gastronomía","Atención de Párvulos","Administración","Telecomunicaciones","Enfermería","Laboratorio Clínico","Contabilidad"
# en el caso de educación diferencial, vamos a dejarlo sin asignaturas por ahora 
st.session_state['niveles_educativos'] = [
    "Inicial (PreKinder/Kinder)",
    "Básica Generalista",
    "Básica con Mención",
    "Media",
    "Técnico Profesional",
    "Educación Diferencial"
]

st.session_state['cursos_por_nivel_educativo'] = {
    "Inicial (PreKinder/Kinder)": ["PreKinder", "Kinder"],
    "Básica Generalista": [f"{i}° Básico" for i in range(1, 5)],
    "Básica con Mención": [f"{i}° Básico" for i in range(5, 7)],
    # en media: incluir 7° Básico y 8° Básico y de 1° Medio a 4° Medio
    # lista con [f"{i}° Básico" for i in range(7, 9)] y [f"{i}° Medio" for i in range(1, 5)]
    "Media": [f"{i}° Básico" for i in range(7, 9)] + [f"{i}° Medio" for i in range(1, 5)],
    "Técnico Profesional": [f"{i}° Medio" for i in range(3, 5)],
    "Educación Diferencial": ["PreKinder", "Kinder"] + [f"{i}° Básico" for i in range(1, 9)] + [f"{i}° Medio" for i in range(1, 5)]
}

st.session_state['asignaturas_por_nivel_educativo'] = {
    "Inicial (PreKinder/Kinder)": [""],# sin asignaturas
    "Básica Generalista": ["Generalista (Sin Mención)", "Lenguaje y Comunicación", "Matemática", "Ciencias Naturales", "Historia, geografía y Ciencias Sociales", "Educación Física y Salud", "Artes Visuales", "Artes Musicales", "Tecnología", "Orientación", "Religión", "Inglés"],
    "Básica con Mención": ["Lenguaje y Comunicación", "Matemática", "Ciencias Naturales", "Historia, geografía y Ciencias Sociales", "Educación Física y Salud", "Artes Visuales", "Artes Musicales", "Tecnología", "Orientación", "Religión", "Inglés"],
    "Media": ["Lenguaje y Comunicación", "Matemática", "Ciencias Naturales", "Historia, geografía y Ciencias Sociales", "Educación Física y Salud", "Artes Visuales", "Artes Musicales", "Tecnología", "Orientación", "Religión", "Filosofía", "Inglés", "Física (CN)", "Química", "Biología"],
    "Técnico Profesional": ["Telecomunicaciones","Mecánica Automotriz","Electricidad","Contabilidad"],
    "Educación Diferencial": [""]

}



def read_all_dataframes(sheet_name_list = None,connection = None):
    """Lee todas las hojas de la spreadsheet y retorna un diccionario con los DataFrames con la estructura {sheet_name: df}, usando la conexión de GSheets.

    Returns:
        dict: Diccionario con los DataFrames de las hojas de la spreadsheet.
    """
    dataframes = {}
    # elige una conexión de la lista de conexiones, de manera aleatoria
    
    
    for sheet_name in sheet_name_list:

        df = connection.read(worksheet=sheet_name,ttl=60,max_entries=10)
        dataframes[sheet_name] = df


    return dataframes        


# Pantalla de login
def login_screen():
    """Pantalla de login."""
    st.image(cfg.PROJ_ROOT / "st" / "images" / "logo-ceas-2.png")
    st.header("Sistema de Reemplazos Cortos CEAS")
    st.subheader("Debes iniciar sesión para continuar.")
    # Botón para iniciar sesión con Google, que llama a st.login (configurado con OAuth)
    st.button("Iniciar sesión con Google", on_click=st.login)


# Inicialización del rol en session_state
if "role" not in st.session_state:
    st.session_state["role"] = None
    print("Rol no definido")
if not st.experimental_user.is_logged_in and st.session_state["role"] is None:
    print("Usuario no loggeado, mostrando pantalla de login")
    
elif st.experimental_user.is_logged_in and st.session_state["role"] is None:
    try:
        st.session_state["user_data"] = st.experimental_user
        print(st.session_state["user_data"])
        random_connection = random.choice(st.session_state['connections'])
        print("Conexión aleatoria:", random_connection)
        conn = st.connection(random_connection, type=GSheetsConnection)
        
        st.session_state['dfs'] = read_all_dataframes(st.session_state['sheet_names'] ,connection=conn)
        # modificar keys para que queden más fáciles de leer
        # básicamente sacar app_name de prefijo y hacer lowercase
        st.session_state['dfs'] = {k.replace(st.session_state["app_name"],"").lower():v for k,v in st.session_state['dfs'].items()}
        #print(st.session_state['dfs'].keys())
        # cleanup applicants and update CleanApplicants
        cleaned_applicants = cleanup_applicants(st.session_state['dfs']['applicants'])

        st.session_state['dfs']['cleanup_applicants'] = cleaned_applicants.copy()
        with open(cfg.PROJ_ROOT / "data" / "interim" / "dfs_new.pkl", "wb") as f:
            pickle.dump(st.session_state['dfs'], f)
        # TODO: se cae este chunk cuando intento serializar el dataframe, no sé por qué: revisar
        # # serializing cleaned_applicants for uploading to gsheet
        # cleaned_applicants = serialize_request_for_sheets(cleaned_applicants)
        # print(cleaned_applicants.head())
        # #upload to gsheet
        # conn.update(worksheet=st.session_state["app_name"] + "CleanApplicants", df=cleaned_applicants)



        st.session_state['user_info'] = st.session_state['dfs']['users'].loc[st.session_state['dfs']['users']['email'] == st.session_state["user_data"].email].iloc[0].to_dict()
        print("Logged user info:\nname:",st.session_state['user_info']['name'],
              "email:",st.session_state['user_info']['email'],"institucion:",st.session_state['user_info']['school_name'],
              "role:",st.session_state['user_info']['role'])
        
        # # guardar los dfs en un pickle
        # with open(cfg.PROJ_ROOT / "data" / "interim" / "dfs.pkl", "wb") as f:
        #     pickle.dump(st.session_state['dfs'], f)

        

    except Exception as e:
        st.error("No se pudo obtener la información del usuario.")
        st.stop()
    st.session_state["role"] = st.session_state["user_info"]["role"]
    
    


admin_users = st.Page(st.session_state["app_name"] + "/admin_users.py", title="Panel de Administración de Usuarios", icon=":material/dashboard:")
admin_schools = st.Page(st.session_state["app_name"] + "/admin_schools.py", title="Panel de Administración de Colegios", icon=":material/dashboard:")
panel_solicitudes_colegios = st.Page(st.session_state["app_name"] + "/panel_solicitudes_colegios.py", title="Panel de Solicitudes de Colegios", icon=":material/assignment:")
form_solicitud_reemplazo = st.Page(st.session_state["app_name"] + "/form_solicitud_reemplazo.py", title="Formulario de Solicitud de Reemplazo", icon=":material/assignment:")
panel_validacion_candidatos = st.Page(st.session_state["app_name"] + "/panel_validacion_candidatos.py", title="Panel de Validación de Candidatos", icon=":material/assignment_turned_in:")

panel_seleccion_candidatos = st.Page(st.session_state["app_name"] + "/panel_seleccion_candidato.py", title="Panel de Selección de Candidatos", icon=":material/assignment_ind:")
panel_eleccion_candidato_colegio = st.Page(st.session_state["app_name"] + "/panel_eleccion_candidato_colegio.py", title="Panel de Elección de Candidato", icon=":material/assignment_turned_in:")
panel_recepciones = st.Page(st.session_state["app_name"] + "/panel_recepciones.py", title="Panel de Recepciones", icon=":material/thumb_up:")
ajustes = st.Page(st.session_state["app_name"] + "/ajustes.py", title="Ajustes", icon=":material/settings:")

logout_page = st.Page(st.logout, title="Cerrar sesión", icon=":material/logout:")
login_page = st.Page(login_screen, title="Login", icon=":material/login:")

# Configuración del diccionario de navegación en función del rol
page_dict = {}
pages = {}
if st.session_state.role in ["owner", "admin", "oficina_central"]:
    page_dict["Panel de Administración"] = [admin_users, admin_schools]
    page_dict["Panel de Solicitudes de Reemplazo"] = [panel_solicitudes_colegios, form_solicitud_reemplazo]
    page_dict["Panel de Validación de Candidatos"] = [panel_validacion_candidatos]
    page_dict["Panel de Selección de Candidatos"] = [panel_seleccion_candidatos]
    page_dict["Panel de Elección de Candidato"] = [panel_eleccion_candidato_colegio]
    page_dict["Panel de Recepciones"] = [panel_recepciones]
    page_dict["Ajustes"] = [ajustes, logout_page]
    # pages tiene "admin_panel" : admin_panel, "panel_solicitudes_colegios" : panel_solicitudes_colegios, etc.
    pages = {"admin_users":admin_users,"admin_schools":admin_schools,
               "panel_solicitudes_colegios" : panel_solicitudes_colegios, "form_solicitud_reemplazo" : form_solicitud_reemplazo,
               "panel_validacion_candidatos" : panel_validacion_candidatos,
                 "panel_seleccion_candidatos" : panel_seleccion_candidatos, "panel_eleccion_candidato_colegio" : panel_eleccion_candidato_colegio, 
                 "panel_recepciones" : panel_recepciones, "ajustes" : ajustes, "logout_page" : logout_page}


elif st.session_state.role in ["admin_colegio", "user_colegio"]:
    page_dict["Mis Solicitudes"] = [panel_solicitudes_colegios, form_solicitud_reemplazo, panel_eleccion_candidato_colegio]
    page_dict["Calificar Reemplazos"] = [panel_recepciones]
    page_dict["Ajustes"] = [ajustes, logout_page]
    pages = {"panel_solicitudes_colegios" : panel_solicitudes_colegios, "panel_eleccion_candidato_colegio" : panel_eleccion_candidato_colegio, "panel_recepciones" : panel_recepciones, "ajustes" : ajustes, "logout_page" : logout_page}

# # Si no hay un rol definido, mostramos la pantalla de login
if not page_dict:
    page_dict["Login"] = [login_page]
else:
    st.session_state['pages'] = pages

# Muestra el logo (opcional) y lanza la navegación
st.logo(cfg.PROJ_ROOT / "st" / "images" / "logo-ceas-2.png")
pg = st.navigation(page_dict)

pg.run()

