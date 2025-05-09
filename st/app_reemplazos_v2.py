
import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import random
import pickle
import json
from ceas import config as cfg
from ceas.utils import create_clean_applicants_sheet
from ceas.serialize_data import read_all_dataframes
from ceas.utils import get_preprocessed_gform_requests, find_unprocessed_gform_requests

# ---- Modularized Initialization ----

def initialize_session_state():
    """
    Initialize Streamlit session state for connections, sheet names, roles, etc.
    """
    # Configuración de la página principal de Streamlit
    st.set_page_config(page_title="Sistema de Reemplazos Cortos CEAS", layout="wide")
    if "new_gform_ack" not in st.session_state:
        
        st.session_state["new_gform_ack"] = False
    

    # Load GForm mapping
    with open(cfg.PROJ_ROOT / "gform_map.json") as f:
        st.session_state['gform_map'] = json.load(f)

    # Fake data toggle
    st.session_state['fake_data'] = False  # Cambiar a True para usar datos falsos

    # Connections for main app sheets
    if st.session_state['fake_data']:
        st.session_state['connections'] = ["bd_reemplazos1_fake", "bd_reemplazos2_fake"]
    else:
        st.session_state['connections'] = ["bd_reemplazos1", "bd_reemplazos2"]

    # Connections for GForm sheets
    st.session_state['solicitudes_gform_connections'] = ["bd_solicitudes1", "bd_solicitudes2"]
    st.session_state['solicitudes_gform_sheet_name'] = "Respuestas de formulario 3"

    # App and sheet names
    st.session_state["app_name"] = "appReemplazos"
    base_sheets = ["Users", "Schools", "Applicants", "Candidates", "Requests",
                   "RequestCandidates", "Receptions", "UserValidations"]
    st.session_state['sheet_names'] = [
        st.session_state["app_name"] + name for name in base_sheets
    ]

    # Role definitions
    st.session_state['roles'] = ["owner", "admin", "oficina_central", "admin_colegio", "user_colegio"]
    st.session_state['roles_rank'] = {
        "owner": 0, "admin": 1, "oficina_central": 2, "admin_colegio": 3, "user_colegio": 4
    }

    # Education levels and mappings
    st.session_state['niveles_educativos'] = cfg.NIVELES_EDUCATIVOS
    st.session_state['cursos_por_nivel_educativo'] = cfg.CURSOS_POR_NIVEL_EDUCATIVO
    st.session_state['asignaturas_por_nivel_educativo'] = cfg.ASIGNATURAS_POR_NIVEL_EDUCATIVO


def load_dataframes():
    """
    Load all required Google Sheets into session_state['dfs'].
    """
    random_conn = random.choice(st.session_state['connections'])
    conn = st.connection(random_conn, type=GSheetsConnection)
    dfs = read_all_dataframes(st.session_state['sheet_names'], connection=conn)
    # simplify keys
    st.session_state['dfs'] = {
        k.replace(st.session_state["app_name"], "").lower(): v
        for k, v in dfs.items()
    }
def clean_applicants():
    """
    Clean the applicants dataframe and save it to session state.
    """
    # Clean applicants
    cleaned,df_serialized_cleaned = create_clean_applicants_sheet(st.session_state['dfs']['applicants'],write_to_gsheet=True)
    #print(cleaned.shape[0], "applicants cleaned", "from", st.session_state['dfs']['applicants'].shape[0])
    st.session_state['dfs']['cleaned_applicants'] = cleaned
    st.session_state['dfs']['cleaned_applicants_serialized'] = df_serialized_cleaned
    # create_clean_applicants_sheet
    print(cleaned.shape[0], "applicants cleaned", "from", st.session_state['dfs']['applicants'].shape[0])



def login_screen():
    """Pantalla de login."""
    st.image(cfg.PROJ_ROOT / "st" / "images" / "logo-ceas-2.png")
    st.header("Sistema de Reemplazos Cortos CEAS")
    st.subheader("Debes iniciar sesión para continuar.")
    st.button("Iniciar sesión con Google", on_click=st.login)


def configure_pages():
    """
    Define pages and navigation based on user role.
    """
    # Page objects
    app_name = st.session_state["app_name"]
    admin_users = st.Page(app_name + "/admin_users.py", title="Panel de Administración de Usuarios", icon=":material/dashboard:")
    admin_schools = st.Page(app_name + "/admin_schools.py", title="Panel de Administración de Colegios", icon=":material/dashboard:")
    panel_solicitudes_colegios = st.Page(app_name + "/panel_solicitudes_colegios.py", title="Panel de Solicitudes de Colegios", icon=":material/assignment:")
    form_solicitud_reemplazo = st.Page(app_name + "/form_solicitud_reemplazo.py", title="Formulario de Solicitud de Reemplazo", icon=":material/assignment:")
    panel_validacion_candidatos = st.Page(app_name + "/panel_validacion_candidatos.py", title="Panel de Validación de Candidatos", icon=":material/assignment_turned_in:")
    panel_seleccion_candidatos = st.Page(app_name + "/panel_seleccion_candidato.py", title="Panel de Selección de Candidatos", icon=":material/assignment_ind:")
    panel_eleccion_candidato_colegio = st.Page(app_name + "/panel_eleccion_candidato_colegio.py", title="Panel de Elección de Candidato", icon=":material/assignment_turned_in:")
    panel_recepciones = st.Page(app_name + "/panel_recepciones.py", title="Panel de Recepciones", icon=":material/thumb_up:")
    ajustes = st.Page(app_name + "/ajustes.py", title="Ajustes", icon=":material/settings:")
    logout_page = st.Page(st.logout, title="Cerrar sesión", icon=":material/logout:")
    login_page = st.Page(login_screen, title="Login", icon=":material/login:")

    page_dict = {}
    pages = {}
    role = st.session_state['role']
    if role in ["owner", "admin", "oficina_central"]:
        page_dict["Panel de Administración"] = [admin_users, admin_schools]
        page_dict["Panel de Solicitudes de Reemplazo"] = [panel_solicitudes_colegios, form_solicitud_reemplazo]
        page_dict["Panel de Validación de Candidatos"] = [panel_validacion_candidatos]
        page_dict["Panel de Selección de Candidatos"] = [panel_seleccion_candidatos]
        page_dict["Panel de Elección de Candidato"] = [panel_eleccion_candidato_colegio]
        page_dict["Panel de Recepciones"] = [panel_recepciones]
        page_dict["Ajustes"] = [ajustes, logout_page]
        pages = {
            "admin_users": admin_users,
            "admin_schools": admin_schools,
            "panel_solicitudes_colegios": panel_solicitudes_colegios,
            "form_solicitud_reemplazo": form_solicitud_reemplazo,
            "panel_validacion_candidatos": panel_validacion_candidatos,
            "panel_seleccion_candidatos": panel_seleccion_candidatos,
            "panel_eleccion_candidato_colegio": panel_eleccion_candidato_colegio,
            "panel_recepciones": panel_recepciones,
            "ajustes": ajustes,
            "logout_page": logout_page,
        }
    elif role in ["admin_colegio", "user_colegio"]:
        page_dict["Mis Solicitudes"] = [panel_solicitudes_colegios, form_solicitud_reemplazo, panel_eleccion_candidato_colegio]
        page_dict["Calificar Reemplazos"] = [panel_recepciones]
        page_dict["Ajustes"] = [ajustes, logout_page]
        pages = {
            "panel_solicitudes_colegios": panel_solicitudes_colegios,
            "panel_eleccion_candidato_colegio": panel_eleccion_candidato_colegio,
            "panel_recepciones": panel_recepciones,
            "ajustes": ajustes,
            "logout_page": logout_page,
        }
    else:
        page_dict["Login"] = [login_page]
    st.session_state['pages'] = pages
    return page_dict


def check_new_gform_requests():
    """
    Al iniciar sesión, calcula cuántas solicitudes nuevas hay en GForm
    y dispara un diálogo si hay (>0). Guarda el conteo y la confirmación
    en session_state.
    """
    # 1) Obtener y preprocesar GForm
    df_gform = get_preprocessed_gform_requests()

    # 2) Obtener df de solicitudes ya importadas desde gsheets
    random_conn = random.choice(st.session_state['connections'])
    conn = st.connection(random_conn, type=GSheetsConnection,max_entries=1)
    existing = conn.read(worksheet=st.session_state['app_name'] + "Requests")



    # 3) Encontrar no procesadas
    df_unproc = find_unprocessed_gform_requests(df_gform, existing)
    n_new = df_unproc.shape[0]

    # 4) Guardar el conteo (puede usarse en otros lugares)
    st.session_state["n_new_gform"] = n_new

    # 5) Si hay nuevas y aún no se reconoció el diálogo
    if n_new > 0 and st.session_state['new_gform_ack'] == False:
        @st.dialog("¡Nuevas Solicitudes desde Google Forms!")
        def _dialog():
            st.write(f"Hay **{n_new}** solicitudes nuevas sin importar.")
            st.markdown(
                "Ve al *Panel de Solicitudes de Colegios* y haz clic en **Importar GForm**."
            )
            
            if st.button("Entendido"):
                st.session_state["new_gform_ack"] = True
                st.rerun()
            
        _dialog()


# ---- Main Script: Initialization and Navigation ----

# Initialize session state
initialize_session_state()

# 1. If not logged in, show login and stop further execution
if not getattr(st.experimental_user, "is_logged_in", False):
    login_screen()
    st.stop()

# 2. If logged in but role not yet set, load data and determine role, then rerun
if st.session_state.get("role") is None:
    load_dataframes()
    # Determine user role from users sheet
    users_df = st.session_state['dfs']['users']
    user_email = st.experimental_user.email
    role_row = users_df.loc[users_df['email'] == user_email]
    if not role_row.empty:
        st.session_state["role"] = role_row.iloc[0]["role"]
        # Store user_info dict for downstream panels
        st.session_state["user_info"] = role_row.iloc[0].to_dict()
    else:
        st.session_state["role"] = None
        st.session_state["user_info"] = {}
    
    clean_applicants()
    # check new gform requests
    check_new_gform_requests()
    if st.session_state['new_gform_ack'] == True:
        st.rerun()
        

    # Rerun to refresh navigation now that role and user_info are set
    

# 3. User is logged in and role is set -> configure pages and run navigation
page_dict = configure_pages()
st.logo(cfg.PROJ_ROOT / "st" / "images" / "logo-ceas-2.png")
pg = st.navigation(page_dict)
pg.run()

