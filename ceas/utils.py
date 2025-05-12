
# -- Ensure these imports at the top --
    
import numpy as np
    
    
import streamlit as st
import pandas as pd
import datetime
import ceas.config as cfg
import time
# importando librerías para validación de emails
import re
from typing import Union
from ceas.reemplazos.refresh import refresh_dataframes
from ceas.user_management import get_all_users, change_user_role, delete_user
from ceas.reemplazos.gmail import send_candidates_email
from ceas.serialize_data import serialize_request_for_sheets
import holidays
from datetime import date
import datetime
from ceas.schools_manager import get_schools_conn
import pickle
import random
from streamlit_gsheets import GSheetsConnection
def get_gform_solicitudes_conn():
    """
    Función que obtiene la conexión a la hoja de Google Sheets con los datos de las solicitudes de reemplazo ingresadas por los colegios.
    """
    try:
        # elegir al azar una de las conexiones disponibles
        rand_conn = random.choice(st.session_state["solicitudes_gform_connections"])
        print("rand_conn:",rand_conn)
        conn = st.connection(rand_conn, type=GSheetsConnection, ttl=0,max_entries=1)

    except Exception as e:
        st.error(f"Error al conectar con la base 'solicitudes': {e}")
        return None
    
    return conn
def read_requests_from_gsheet():
    """
    Función que lee la hoja de Google Sheets con los datos de las solicitudes de reemplazo ingresadas por los colegios,
    y devuelve el DataFrame resultante.
    """

    conn = get_gform_solicitudes_conn()
    df = conn.read(worksheet=st.session_state["solicitudes_gform_sheet_name"])
    if df.empty:
        st.warning("No hay solicitudes de reemplazo.")
        return None
    else:
        return df

def get_preprocessed_gform_requests() -> pd.DataFrame:
    """
    Lee las respuestas del Google Form, las limpia y estandariza,
    devolviendo un DataFrame listo para comparar o importar.
    """
    

    df_raw = read_requests_from_gsheet()
    if df_raw is None or df_raw.empty:
        return pd.DataFrame()
    return process_requests_from_gsheet(df_raw)

def clean_gform_requests(df,cols_map,school_name_map,ED_MAPPING):
    """
    Función que limpia y estandariza el dataframe de solicitudes de formularios de Google, para que sea compatible con el formulario interno de st/form_solicitud_reemplazo.py
    """

    # Keep only mapped columns: keys in cols_map
    df = df[list(cols_map.keys())]

    # Rename columns to match the internal format
    df = df.rename(columns=cols_map) 

    # Parse created_at flexiblemente (día primero), convirtiendo errores en NaT
    df['created_at'] = pd.to_datetime(df['created_at'], dayfirst=True, errors='coerce')
    # filter rows with created_at after 2025-04-03
    df = df[df['created_at'] > pd.to_datetime("2025-04-03")]
    # school_name: mapeo con school_name 
    df['school_name'] = df['school_name'].map(school_name_map)
    # nivel_educativo: mapeo con ED_MAPPING, pero OJO:
    # Antes de hacer el mapeo, hay que ver si hay más de un valor en la celda
    # y si es así, hay que separar los valores por coma y luego hacer el mapeo
    # y luego volver a unir los valores por coma

    # nivel_educativo: separar por coma y luego hacer el mapeo
    df['nivel_educativo'] = df['nivel_educativo'].str.split(", ").apply(lambda x: [ED_MAPPING[i] for i in x if i in ED_MAPPING.keys()])

    # asignatura: separar en lista, preservando "Historia, geografía y Ciencias Sociales"
    def parse_asignaturas(s):
        if not isinstance(s, str) or not s.strip():
            return []
        key = "Historia, geografía y Ciencias Sociales"
        parts = []
        if key in s:
            parts.append(key)
            s = s.replace(key, "")
        for item in [p.strip() for p in s.split(",") if p.strip()]:
            parts.append(item)
        return parts
    df['asignatura'] = df['asignatura'].apply(parse_asignaturas)

    # fecha_inicio: convertir a datetime.date
    df['fecha_inicio'] = pd.to_datetime(df['fecha_inicio'], format='%d/%m/%Y').dt.date
    # fecha_fin: convertir a datetime.date
    df['fecha_fin'] = pd.to_datetime(df['fecha_fin'], format='%d/%m/%Y').dt.date

    # horas_contrato: convertir a int
    df['horas_contrato'] = df['horas_contrato'].astype(int)

    # Convertir columnas de listas a tuplas para poder usar drop_duplicates
    for col in ['nivel_educativo', 'asignatura']:
        df[col] = df[col].apply(lambda x: tuple(x) if isinstance(x, list) else x)

    df = df.drop_duplicates()

    # Convertir tuplas de nuevo a listas luego de drop_duplicates
    for col in ['nivel_educativo', 'asignatura']:
        df[col] = df[col].apply(lambda x: list(x) if isinstance(x, tuple) else x)

    # Remove empty rows
    df = df.dropna(how='all')

    # Reset index
    df.reset_index(drop=True, inplace=True)

    return df

def process_requests_from_gsheet(df):
    """ función que procesa el dataframe de solicitudes de reemplazo del formulario de google.
     Lee el formulario a un df, limpia y estandariza los datos para que sean similares a los de webapp
     y devuelve el dataframe resultante."""
    # Limpieza y estandarización inicial usando los mapeos de configuración
    df_clean = clean_gform_requests(
        df,
        cfg.GFORM_COLS_MAP,
        cfg.SCHOOL_NAME_MAP,
        cfg.ED_MAPPING
    )
    # Inicializar columnas nuevas
    df_clean['dias_seleccionados'] = None
    df_clean['dias_de_la_semana'] = None
    df_clean['school_id'] = None
    # Cálculo de días hábiles y asignación de school_id
    for i, row in df_clean.iterrows():
        dias = get_days_between_dates(row["fecha_inicio"], row["fecha_fin"])
        df_clean.at[i, "dias_seleccionados"] = [d.strftime("%Y-%m-%d") for d in dias["days"]]
        df_clean.at[i, "dias_de_la_semana"] = dias["str_weekdays"]
        df_clean.at[i, "school_id"] = st.session_state["dfs"]["schools"] \
            .loc[
                st.session_state["dfs"]["schools"]["school_name"] == row["school_name"],
                "school_id"
            ].values[0]
    return df_clean
def create_request_dict_from_gform(gform_row:dict) -> dict:
    """
    Función que crea un diccionario con los datos de la solicitud de reemplazo.
    """
    school_id = gform_row["school_id"]
    school_name = gform_row["school_name"]
    created_by = gform_row["created_by"]

    # Nivel educativo como lista
    nivel_educativo = gform_row.get("nivel_educativo", [])
    if isinstance(nivel_educativo, str):
        nivel_educativo = [s.strip() for s in nivel_educativo.split(",")]

    # Asignaturas: dict[nivel -> list]
    raw_asigs = gform_row.get("asignatura", [])
    asignatura = {niv: raw_asigs for niv in nivel_educativo}

    # Cursos: dict[nivel -> list], vacío
    curso = {niv: [] for niv in nivel_educativo}

    # Días seleccionados: ISO-formatted strings
    raw_days = gform_row.get("dias_seleccionados", [])
    dias_seleccionados = [
        d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d)
        for d in raw_days
    ]
    dias_de_la_semana = gform_row.get("dias_de_la_semana", [])

    fecha_inicio = gform_row["fecha_inicio"]
    fecha_fin = gform_row["fecha_fin"]
    jefatura = gform_row.get("jefatura", None)
    horas_contrato = gform_row.get("horas_contrato", None)
    mencion_especialidad_postitulo = gform_row.get("mencion_especialidad_postitulo", "")
    vacante_confidencial = gform_row.get("vacante_confidencial", False)
    horarios_seleccionados = gform_row.get("horarios_seleccionados", {})
    genero = gform_row.get("genero", "Indiferente")
    anios_egreso = gform_row.get("anios_egreso", 0)
    disponibilidad = gform_row.get("disponibilidad", "Completa")
    candidato_preferido = gform_row.get("candidato_preferido", "")
    otras_preferencias = gform_row.get("otras_preferencias", "")
    comentarios = gform_row.get("comentarios", "")
    status = "creada"
    created_with = "gform"
    raw_created = gform_row.get("created_at", None)
    # Si no vino o es NaT (coercionado), usamos now()
    if raw_created is None or pd.isna(raw_created):
        created_at = datetime.datetime.now()
    else:
        created_at = raw_created

    processed_at = datetime.datetime.now()
    updated_at = None
        # after existing logic...
    # Asegurémonos de que created_at y processed_at sean strings ISO
    created_at = created_at.strftime("%Y-%m-%d %H:%M:%S")
    processed_at = processed_at.strftime("%Y-%m-%d %H:%M:%S")

    request_dict = {
        "school_id": school_id,
        "school_name": school_name,
        "created_by": created_by,
        "nivel_educativo": nivel_educativo,
        "asignatura": asignatura,
        "curso": curso,
        "fecha_inicio": fecha_inicio,
        "fecha_fin": fecha_fin,
        "dias_seleccionados": dias_seleccionados,
        "dias_de_la_semana": dias_de_la_semana,
        "jefatura": jefatura,
        "horas_contrato": horas_contrato,
        "mencion_especialidad_postitulo": mencion_especialidad_postitulo,
        "vacante_confidencial": vacante_confidencial,
        "horarios_seleccionados": horarios_seleccionados,
        "genero": genero,
        "anios_egreso": anios_egreso,
        "disponibilidad": disponibilidad,
        "candidato_preferido": candidato_preferido,
        "otras_preferencias": otras_preferencias,
        "comentarios": comentarios,
        "status": status,
        "created_with": created_with,
        "created_at": created_at,
        "processed_at": processed_at,
        "updated_at": updated_at,
    }
    return request_dict

def create_clean_applicants_sheet(df_applicants: pd.DataFrame, write_to_gsheet: bool) -> pd.DataFrame:
    """ 
    Función que limpia el DataFrame de los aplicantes y lo prepara para ser usado en las funciones de filtrado y validación.

    Args:
        df_applicants (pd.DataFrame): DataFrame de los aplicantes.

    Returns:
        pd.DataFrame: DataFrame limpio de los aplicantes.
    """
    cleaned_applicants = cleanup_applicants(df_applicants)
    
    if write_to_gsheet:
        rand_conn = random.choice(st.session_state["connections"])
        print("rand_conn in create_clean_applicants:",rand_conn)
        conn = st.connection(rand_conn, type=GSheetsConnection, ttl=0,max_entries=1)
        
        serialized_cleaned_applicants_dict = {}
        
        for i, row in cleaned_applicants.iterrows():
            # Convertir cada fila a un diccionario
            row_dict = row.to_dict()
            # Serializar el diccionario
            serialized_row = serialize_request_for_sheets(row_dict)
            serialized_cleaned_applicants_dict[i] = serialized_row

        # serialized_cleaned_applicants = serialize_request_for_sheets(cleaned_applicants)
        # # 1. Convertir serialized_request a un dict
        # serialized_row = {}
        # for key, value in serialized_cleaned_applicants.items():
        #     serialized_row[key] = [value]
        # # 2. Convertir serialized_row a un DataFrame
        df_serialized_cleaned_applicants = pd.DataFrame(serialized_cleaned_applicants_dict).T
        try:        
            #print(df_serialized_cleaned_applicants.head())
            conn.update(data=df_serialized_cleaned_applicants, worksheet=st.session_state["app_name"] + "CleanApplicants")
            
        except Exception as e:
            st.error(f"Error al actualizar la hoja de Google Sheets: {e}")
            return cleaned_applicants, df_serialized_cleaned_applicants
    else:
        return cleaned_applicants, None

    
    return cleaned_applicants, df_serialized_cleaned_applicants



def create_request_dict(form_reemplazo_data:dict ) -> dict:

    """ 
    Función que crea un diccionario con los datos de la solicitud de reemplazo.

    Args:
        form_reemplazo_data (dict): Diccionario con los datos del formulario de reemplazo.

    Returns:
        dict: Diccionario con los datos de la solicitud de reemplazo.

    """
    school_name = form_reemplazo_data["inst"]
    # school_id
    school_id = st.session_state['dfs']['schools'].loc[st.session_state['dfs']['schools']["school_name"] == school_name, "school_id"].values[0]
    
    created_by = form_reemplazo_data["solicitante"]
    nivel_educativo = form_reemplazo_data["nivel_educativo"]
    asignatura = form_reemplazo_data["asignaturas"]
    curso  = form_reemplazo_data["cursos"]
    fecha_inicio = form_reemplazo_data["fecha_inicio"]
    fecha_fin = form_reemplazo_data["fecha_fin"]
    dias_seleccionados = form_reemplazo_data["days"]
    dias_de_la_semana = form_reemplazo_data["dias"]
    horarios_seleccionados = form_reemplazo_data["horarios"]
    genero = form_reemplazo_data["genero"]
    anios_egreso = form_reemplazo_data["anios_egreso"]
    disponibilidad = form_reemplazo_data["disponibilidad"]
    candidato_preferido = form_reemplazo_data["candidato_preferido"]
    otras_preferencias = form_reemplazo_data["otras_preferencias"]
    comentarios=""
    status="creada"
    jefatura = form_reemplazo_data["jefatura"]
    horas_contrato = form_reemplazo_data["horas_contrato"]
    mencion_especialidad_postitulo = form_reemplazo_data["mencion_especialidad_postitulo"]
    vacante_confidencial = form_reemplazo_data["vacante_confidencial"]
    created_with = "webapp"
    request_dict = {"school_id": school_id,
                    "school_name": school_name, "created_by": created_by,
                    "nivel_educativo": nivel_educativo, "asignatura": asignatura,
                    "curso": curso, "fecha_inicio": fecha_inicio, "fecha_fin": fecha_fin,
                    "dias_seleccionados": dias_seleccionados, "dias_de_la_semana": dias_de_la_semana,
                    "jefatura": jefatura, "horas_contrato": horas_contrato, "mencion_especialidad_postitulo": mencion_especialidad_postitulo,
                    "vacante_confidencial": vacante_confidencial,
                    "horarios_seleccionados": horarios_seleccionados, "genero": genero,
                    "anios_egreso": anios_egreso, "disponibilidad": disponibilidad, 
                    "candidato_preferido": candidato_preferido, "otras_preferencias": otras_preferencias,
                    "comentarios": comentarios, "status": status, "updated_at": None, "created_with": created_with}
    

    return request_dict


    # # usar el registro para filtrar los candidatos
    
    # cleaned_applicants = st.session_state['dfs']['cleanapplicants'].copy()
    # filtered_applicants = filter_applicants_by_request(request_dict, cleaned_applicants)



    # # # guardar los candidatos filtrados en un pickle
    # # # para poder revisar el filtered_applicants en caso de error

    # # filename = f"filtered_applicants_{int(request_dict["replacement_id"])}.pickle"
    # # path = cfg.INTERIM_DATA_DIR / "requests" / filename
    # # with open(path, "wb") as f:
    # #     pickle.dump(filtered_applicants, f)

def create_replacement_request( request_dict: dict, df_requests: pd.DataFrame,save_pickle:bool = False) -> tuple: 
    # Calculate replacement_id directly from df_requests argument
    if df_requests.empty:
        replacement_id = 1
    else:
        replacement_id = int(df_requests["replacement_id"].max()) + 1
    request_dict["replacement_id"] = replacement_id
    if request_dict['created_with'] == "webapp":
        request_dict["created_at"] = datetime.datetime.now()
    


    # validar el registro
    isValid, errors = validate_request(request_dict)
    if not isValid:
        st.error(f"Error al validar la solicitud: {errors}")
        return False, df_requests
    
    # serializar los datos para luego guardarlos en la hoja de Google Sheets
    serialized_request = serialize_request_for_sheets(request_dict)
    # serialized_row será primero un dict donde las keys son iguales a las de serialized_request,
    # y los values son [value], para luego convertirlo a un DataFrame y concatenarlo con df_requests
    # 1. Convertir serialized_request a un dict
    serialized_row = {}
    for key, value in serialized_request.items():
        serialized_row[key] = [value]
    # 2. Convertir serialized_row a un DataFrame
    serialized_row = pd.DataFrame(serialized_row)
    

    # Agregar la nueva fila al DataFrame existente
    # y actualizar la hoja de Google Sheets
    df_requests = pd.concat([df_requests, serialized_row], ignore_index=True)
    
    try:
        conn = get_schools_conn()
        conn.update(data=df_requests, worksheet=st.session_state["app_name"] + "Requests")

        if save_pickle:
        # guardar en un pickle la solicitud (request_dict)
        # para poder revisar el request_dict en caso de error
        
            filename = f"request_{int(replacement_id)}.pickle"
            path = cfg.INTERIM_DATA_DIR / "requests" / filename
            with open(path, "wb") as f:
                pickle.dump(request_dict, f)
        return True, df_requests
    except Exception as e:
        st.error(f"Error al crear la solicitud de reemplazo en la hoja {st.session_state["app_name"] + "Requests"}: {e}")
        return False, df_requests
def render_email_container_draft(row,data):
    """
    Función que renderiza el contenedor de envío de correos.
    """
    pass

@st.dialog("Enviar Correo",width="large")
def on_enviar_correo(row,data):
    
    st.subheader("Confirmar datos de envío")
    institucion = data['school_name']
    solicitante = data['created_by']
    asignatura = data['asignatura']
    nivel_educativo = data['nivel_educativo']
    dias = data['dias_seleccionados']
    lista_candidatos = row['first_name']+" "+row['last_name']+" ("+row['email']+")"
    to_email = "vmlandae@gmail.com"
    subject = f"Solicitud de reemplazo {data['replacement_id']} - {institucion}"
    template_path = str(cfg.PROJ_ROOT/"email_candidates_template.html")
    st.write(f"Institución: {institucion}")
    st.write(f"Asignatura: {asignatura}")
    st.write(f"Nivel educativo: {nivel_educativo}")

    

    st.write(f"Puedes agregar emails adicionales separados por comas.")
    to_email = st.text_input("emails separados por comas", value=to_email, label_visibility="visible")
    time.sleep(2)
    if st.button("Enviar"):
        try:
            status = send_candidates_email(
                institucion=institucion,
                asignatura=asignatura,
                nivel_educativo=nivel_educativo,
                dias =dias,
                solicitante=solicitante,
                lista_candidatos=lista_candidatos,
                to_email=to_email,
                subject=subject,
                template_path=template_path
            )

            if status:
                st.success(f"Correo enviado a {to_email}")
                # refrescar la tabla

                # cerrar el dialog
                
                st.rerun()
            else:
                st.error("Error al enviar el correo.")
                time.sleep(2)
                st.rerun()
        except Exception as e:
            st.error(f"Error del programa: {e}")
            time.sleep(2)
            st.rerun()
                
    if st.button("Cancelar"):
        st.info("Cancelado.")
        time.sleep(2)
        st.rerun()
def get_days_between_dates(date1: str, date2: str):
    """
    extrae los días entre dos fechas, contando la fecha inicial y la fecha final, y excluyendo los fines de semana y festivos en Chile.
    retorna un diccionario con las siguientes llaves:
    
    - "days": una lista con los días hábiles entre las dos fechas incluidas, en formato 'YYYY-MM-DD'.
    - "str_days": una lista con los días hábiles entre las dos fechas incluidas en formato "27 de Marzo" para  2025-03-27, etc.
    - "weekdays": una lista con los días de la semana correspondientes a los días hábiles, en formato datetime
    - "str_weekdays": una lista con los días de la semana correspondientes a los días hábiles en formato "Lunes", "Martes", etc.

    


    Args:
        date1 (str): Fecha inicial en formato 'YYYY-MM-DD'.
        date2 (str): Fecha final en formato 'YYYY-MM-DD'.

    Returns:
        dict: Diccionario con las llaves "days", "str_days", "weekdays", "str_weekdays".

    """ 
    # desactivar los FutureWarnings de pandas
    pd.options.mode.chained_assignment = None  # default='warn'
        # Convertimos las fechas a objetos datetime
    date1 = pd.to_datetime(date1)
    date2 = pd.to_datetime(date2)

    
    # en la librería 'holidays' se encuentran los festivos en Chile
    current_date = datetime.datetime.now()
    current_year = current_date.year
    chilean_holidays = holidays.country_holidays(country="CL",years=current_year,observed=True)
    

    
    # Extraemos los días hábiles entre las dos fechas
    days = pd.date_range(date1, date2, freq='B') # freq='B' es para extraer solo los días hábiles
    
    # luego filtramos los días que no sean festivos
    # TODO: arreglamos FutureWarning: "the behavior of 'isin' with dtype='datetime64[ns]' and castable values (e.g. strings) is deprecated and will raise in a future version. Use 'pd.to_datetime' to convert the values to datetime64[ns] before calling 'isin'."

    days = days[~days.isin(chilean_holidays.keys())]
    
    str_days = days.strftime('%d de %B').tolist()
    str_weekdays = days.strftime('%A').tolist()
    # convertimos str_weekdays a español si es necesario
    en_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    day_map = {
        "Monday": "Lunes",
        "Tuesday": "Martes",
        "Wednesday": "Miércoles",
        "Thursday": "Jueves",
        "Friday": "Viernes"
    }
    # si algún día está en inglés, lo convertimos
    for day in str_weekdays:
        if day in en_days:
            str_weekdays[str_weekdays.index(day)] = day_map[day]
            
    


    
    weekdays = days.to_pydatetime().tolist()
    
    return {"days": days, "str_days": str_days, "weekdays": weekdays, "str_weekdays": str_weekdays}

    
def validate_email(email: str,domain = None) -> bool:
    """
    Valida si un email es válido o no.
    
    Args:
        email (str): Email a validar.
        domain (str): Dominio del email. Por defecto es None.
    
    Returns:
        bool: True si el email es válido, False si no.

    """
    # Si el domain es None, se valida cualquier dominio
    if domain:
        # Definimos la expresión regular para validar emails (sacada de emailregex.com)
        regex = r"(^[a-zA-Z0-9_.+-]+@{}$)".format(domain)
    else:
        regex = r"(^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$)"
    
    # Hacemos el match de la expresión regular con el email
    if re.search(regex,email):
        return True
    else:
        if domain:
            st.error(f"El email {email} no es válido. Debe ser de la forma: 'nombre@{domain}'")
        else:
            st.error(f"El email {email} no es válido.")
        return False
    
def validate_new_user(email: str, name: str, role: str, school_id: Union[str,int], school_name: str, status: str) -> bool:
    """
    Valida si los datos de un nuevo usuario son válidos o no.
    
    Args:
        email (str): Email del nuevo usuario.
        name (str): Nombre del nuevo usuario.
        role (str): Rol del nuevo usuario.
        school_id (Union[str,int]): ID del colegio del nuevo usuario.
        school_name (str): Nombre del colegio del nuevo usuario.
        status (str): Estado del nuevo usuario.
    
    Returns:
        bool: True si los datos son válidos, False si no.
    """
    # Validamos que el email sea único en la base de datos
    if email in get_all_users()["email"].values:
        st.error("El email ya está registrado.")
        return False
    # validamos que el email sea válido
    if not validate_email(email):
        
        return False

    # Validamos el nombre
    if not name or (name.tolower().strip() in st.session_state['dfs']['users']['name'].str.lower().str.strip().values) or (name.tolower().strip() == ""):
        if not name or (name.tolower().strip() == ""):
            st.error("El nombre no puede estar vacío.")
        if name.tolower().strip() in st.session_state['dfs']['users']['name'].str.lower().str.strip().values:
            st.error("El nombre ya está registrado.")
        return False
    # Validamos el rol
    if role not in ["owner", "admin", "oficina_central", "admin_colegio", "user_colegio"]:
        st.error("Rol no válido.")
        return False
    # Validamos el school_id
    if not school_id:
        st.error("ID del colegio no puede estar vacío.")
        return False
    # Validamos el school_name
    if not school_name:
        st.error("Nombre del colegio no puede estar vacío.")
        return False
    # Validamos el status
    if status not in ["new"]:
        st.error("Estado no válido.")
        return False
    return True


def create_columns_panel(
    df,
    columns_config,
    key_prefix="panel",
    enable_sort_pills: bool = False,
    ):
    """
    Renders a DataFrame row-by-row in st.columns according to columns_config.
        Parameters:
    -----------
    df : pandas.DataFrame
        The DataFrame to iterate over (e.g. df_users).
    columns_config : list of dict
        Configuration for each "column" of st.columns.
        Each dict can have:
          - "header": str        (header label for that column)
          - "field": str or None (the name of df column to read from row; can be None if there's no direct mapping)
          - "type": str          (one of ["text", "selectbox", "button", "custom"], can define how to render)
          - "width": int/float   (width ratio for st.columns)
          - "options": list      (if type == "selectbox", the options for it)
          - "disable_fn": callable or bool (to disable the widget, e.g. for role-based logic.)
          - "on_click": callable (function called when a button is pressed or a selectbox changes)
          - ... (any other custom parameters you want to handle)
    key_prefix : str
        A prefix to ensure widget keys are unique in the Streamlit app.
    enable_sort_pills : bool
        If True, enables sorting pills in st.columns
    
    Returns:

    -----------
    if a parameter is callable, it will be called with the row as the first argument, and then *args and **kwargs will be passed.
    except if it's a selectbox in which case row and new_val will be passed, then *args and **kwargs.
    callables in columns_config should be passed as dictionaries with the following format:
        {
            "callable": a function, "args": [...], "kwargs": {...}
        }
    
    Example columns_config entry:
columns_config = [
    {
        "header": "Email",
        "field": "email",
        "type": "text",
        "width": 2
    },
    {
        "header": "Rol",
        "field": "role",
        "type": "selectbox",
        "width": 1,
        "options": ["owner","admin","oficina_central","admin_colegio","user_colegio"],
        "disable_fn": {
        "callable": my_disable_role,
        "args": [],
        "kwargs": {}
        },
        "on_click": {
        "callable": my_on_selectbox_change,
        "args": [],
        "kwargs": {}
        }
    }
    ]
    
    The 'disable_fn' dictionary is used to evaluate if the widget is disabled.
    The 'on_click' dictionary is used to handle the event (button press, or selectbox changed).
    
    Types supported:
      - "text"
      - "selectbox"
      - "button"
      - "custom"
    
    If 'field' is None, we won't retrieve a value from the row. 
    If 'options' is a callable, we call it with (row) to get the list of options.
    """

    if df.empty:
        st.write("No data to display.")
        return

    # build a list of widths
    col_widths = [cfg.get("width", 1) for cfg in columns_config]

    # Render headers in their own row
    header_cols = st.columns(col_widths,)
    for idx, col_cfg in enumerate(columns_config):
        with header_cols[idx]:
            st.markdown(f"**{col_cfg.get('header', '')}**",
                unsafe_allow_html=True,
            )
 

    # --- Optional sorting with pills under headers ---
    if enable_sort_pills:
        # Determine which field is currently active (first non-empty pill)
        active_field = None
        active_dir = None
        for col_cfg in columns_config:
            field = col_cfg.get("field")
            if field:
                key = f"{key_prefix}_sort_pill_{field}"
                val = st.session_state.get(key, None)
                if val in ["▲", "▼"]:
                    active_field = field
                    active_dir = val
                    break

        # Render pills under each header
        pill_cols = st.columns(col_widths)
        for idx, col_cfg in enumerate(columns_config):
            field = col_cfg.get("field")
            ctype = col_cfg.get("type")
            if field and ctype == "text":
                with pill_cols[idx]:
                    disabled = active_field is not None and field != active_field
                    st.session_state.setdefault(f"{key_prefix}_sort_pill_{field}", None)
                    header = col_cfg.get("header", "")
                    st.pills(
                        header,
                        options=["▲", "▼"],
                        default=None,
                        key=f"{key_prefix}_sort_pill_{field}",
                        selection_mode="single",
                        label_visibility="collapsed",
                        disabled=disabled
                    )

        # Apply sort if a pill is active
        if active_field and active_dir:
            asc = True if active_dir == "▲" else False
            df = df.sort_values(by=active_field, ascending=asc, inplace=False)

    for row_i, row in df.iterrows():
        cols = st.columns(col_widths)
        for j, col_cfg in enumerate(columns_config):
            with cols[j]:
                # read config
                header = col_cfg.get("header","")
                field  = col_cfg.get("field", None)
                button_label = col_cfg.get("button_label", "Button")
                ctype  = col_cfg.get("type", "text")
                options= col_cfg.get("options", [])
                label_visibility = col_cfg.get("label_visibility", "collapsed")

                # Possibly a dictionary describing the "disable_fn"
                disable_dict = col_cfg.get("disable_fn", None)
                if isinstance(disable_dict, dict):
                    disable_callable = disable_dict.get("callable", None)
                    disable_args = disable_dict.get("args", [])
                    disable_kwargs = disable_dict.get("kwargs", {})
                    if callable(disable_callable):
                        disabled = disable_callable(row, *disable_args, **disable_kwargs)
                    else:
                        disabled = False
                else:
                    # fallback if it's just a bool or None
                    disabled = bool(disable_dict) if disable_dict else False

                # Possibly a dictionary describing the "on_click"
                on_click_dict = col_cfg.get("on_click", None)
                #print("on_click_dict:",on_click_dict)
                if isinstance(on_click_dict, dict):
                    #print("on_click_dict is a dict:")
                    onclick_callable = on_click_dict.get("callable", None)
                    onclick_args = on_click_dict.get("args", [])
                    onclick_kwargs = on_click_dict.get("kwargs", {})
                                        
                else:
                    onclick_callable = None
                    onclick_args = []
                    onclick_kwargs = {}

                # Retrieve the cell value if field is not None
                value = row[field] if field else None

                # unique key
                widget_key = f"{key_prefix}_{j}_{row_i}"

                # handle different ctype
                if ctype == "text":
                    st.write(value if value is not None else "-")

                elif ctype == "selectbox":
                    # If 'options' is a callable, call it to get the list
                    if callable(options):
                        ops = options(row)
                    else:
                        ops = options
                    # find index of 'value' if present
                    idx = 0
                    if value in ops:
                        idx = ops.index(value)
                    new_val = st.selectbox(
                        label="selectbox",
                        options=ops,
                        index=idx,
                        disabled=disabled,
                        label_visibility=label_visibility,
                        key=widget_key
                    )
                    # if changed => call on_click
                    if onclick_callable and new_val != value:
                        onclick_callable(row, new_val, *onclick_args, **onclick_kwargs)

                elif ctype == "button":
                    # use the 'field' as the label or a default
                    btn_label = str(field) if field else button_label
                    if st.button(btn_label, disabled=disabled, key=widget_key):
                        #print("button pressed, button_label:",btn_label,"disabled:",disabled,"widget_key:",widget_key,"onclick_callable", onclick_callable)
                        if onclick_callable:
                            onclick_callable(row, *onclick_args, **onclick_kwargs)

                elif ctype == "custom":
                    # a custom function to render something
                    custom_fn = col_cfg.get("render_fn")
                    if custom_fn:
                        custom_fn(row, disabled, widget_key, *onclick_args, **onclick_kwargs)
                    else:
                        st.write("(no custom fn provided)")

                else:
                    # fallback
                    st.write(str(value) if value is not None else "-")





def disable_role_change(row,user_role: str, ROLE_RANK:dict) -> bool:
    """
    Returns True if cell_role is equal or 'greater' (or same rank or higher) than user_role,
    so that the role change is not allowed.
    Otherwise, False.
    
    Example: if user_role = "admin_colegio" (rank 3),
             and cell_role = "oficina_central" (rank 2),
             we check if rank(cell_role) >= rank(user_role).
    """
    cell_role = row["role"]
    #print(f"cell_role={cell_role}, user_role={user_role}, ROLE_RANK={ROLE_RANK}")
    # user_role is the role of the user who is *trying* to do the change
    # cell_role is the role of the row being displayed
    return ROLE_RANK[cell_role] <= ROLE_RANK[user_role]
    # ^ if you interpret "cell_role >= user_role" as "owner < admin" you'd invert the sign.
    # But based on your request:
    # "disable_role_change => returns true when cell_role is equal or greater than user_role"
    # We interpret "greater" as smaller rank index, since 'owner' is 0?
    # This can be confusing, so double-check your logic:
    #   If 'owner' (0) tries to change 'admin' (1), is cell_role "equal or greater"? 
    #   We'll re-check the sign below.

    # Alternatively, if your rank means "owner" is the top, then user_colegio is the 'lowest'.
    # Then a bigger integer = lower privilege. So "cell_role >= user_role" means numeric rank(cell_role) >= rank(user_role).
    # We'll do it in the sense that "owner=0 is the top, user_colegio=4 is bottom".
    # If cell_role has rank 2 and user_role is rank 1, 2 >= 1 => true => disable => not allowed to downgrade an 'admin' if you are just "oficina_central"? 
    # It's best to test it in practice. We'll keep it consistent with your request:

def role_options(user_role: str,ROLE_RANK:dict) -> list:
    """
    If disable_role_change is True, return [cell_role].
    If not, return a list of roles that are strictly 'less' (i.e. lower rank) than user_role.
    
    So if user_role is 'admin' (rank=1),
    we only return roles that have rank > 1 (like 'oficina_central'=2, 'admin_colegio'=3, 'user_colegio'=4)
    or might do the opposite if you prefer the direction.
    
    Clarify your logic carefully:
    - "menores que user_role" means "with rank > rank(user_role)" if your scale is 0=owner,4=user_colegio?
    """
    

    # Return roles strictly *lower rank than user_role?*
    # or if you want "strictly bigger rank integer"? 
    # We'll interpret "less than user_role" means rank is bigger since 'owner'=0 is top
    # Let's do:
    user_rank = ROLE_RANK[user_role]
    # pick all roles whose rank > user_rank
    all_roles = list(ROLE_RANK.keys())
    # but in an order we might want from your st.session_state['roles']
    # We'll just filter:
    valid = []
    for r in all_roles:
        if ROLE_RANK[r] > user_rank:
            valid.append(r)
    # If you'd prefer all roles that are strictly "below" in rank, invert the sign
    return valid



@st.dialog("Cambiar Rol",)
def on_change_role(row, user_role:str,ROLE_RANK:dict):
    cell_role = row["role"]
    st.write(f"Cambiando el rol de {row['email']}, de {cell_role} a:")
    options_list = role_options(user_role,ROLE_RANK)
    # sacar de la lista el rol actual
    options_list = [role for role in options_list if role != cell_role]
    new_role = st.selectbox("New Role", options_list, key="new_role_select")
    if st.button("Cambiar Rol"):
        try:
            status,df_users = change_user_role(row["email"], new_role, st.session_state['dfs']['users'])
            if status:
                st.success(f"Rol cambiado a {new_role}")
                # refrescar la tabla
                st.session_state['refresh_list'] = ['appReemplazosUsers']
                refresh_dataframes()
                # cerrar el dialog
                
                st.rerun()
            else:
                st.error("Error al cambiar el rol.")
                time.sleep(2)
                st.rerun()
        except Exception as e:
            st.error(f"Error al cambiar el rol: {e}")
            time.sleep(2)
            st.rerun()
                
    if st.button("Cancelar"):
        st.info("Cancelado.")


@st.dialog("Eliminar Usuario",)
def on_delete_user(row, user_role:str,ROLE_RANK:dict):
    cell_user = row["email"]
    st.write(f"Eliminando al usuario {cell_user}.")
    
    if st.button("Eliminar"):
        try:
            status,df_users = delete_user(cell_user, st.session_state['dfs']['users'])
            if status:
                st.success(f"Usuario desactivado")
                # refrescar la tabla
                st.session_state['refresh_list'] = ['appReemplazosUsers']
                refresh_dataframes()
                # cerrar el dialog
                
                st.rerun()
            else:
                st.error("Error al cambiar el rol.")
                time.sleep(2)
                st.rerun()
        except Exception as e:
            st.error(f"Error al cambiar el rol: {e}")
            time.sleep(2)
            st.rerun()
                
    if st.button("Cancelar"):
        st.info("Cancelado.")
        time.sleep(2)
        st.rerun()



def validate_request(new_request):
    """
    Validate a new replacement request record according to general, obvious criteria.
    Returns (is_valid: bool, error_messages: list) so the caller can handle them.

    new_request is expected to be a dict or Series-like object with fields:
      - nivel_educativo (list or None)
      - asignatura (dict or list, or None)
      - curso (dict or list, or None)
      - fecha_inicio (datetime.date or None)
      - fecha_fin (datetime.date or None)
      - dias_seleccionados (list of weekdays or None)
      - horarios_seleccionados (dict or None)
      - genero (str)
      - anios_egreso (int)
      - disponibilidad (str)
      - candidato_preferido (str)
      - otras_preferencias (str)
      - comentarios (str)
      - status (str)
      - created_at (datetime)

    Example checks:
      1. fecha_inicio <= fecha_fin
      2. nivel_educativo / asignatura / curso must not be empty
      3. dias_seleccionados / horarios no empty if there's a range of dates
      4. status in an allowed set (e.g. ["creada","aprobada","rechazada"]?)

    We'll be as general as possible. Adjust or expand as needed.
    """
    errors = []
    # 1) Check date range
    fi = new_request.get("fecha_inicio")
    ff = new_request.get("fecha_fin")
    if fi is None or ff is None:
        errors.append("Fechas de inicio/fin no definidas.")
    else:
        if fi > ff:
            errors.append("La fecha de inicio no puede ser posterior a la fecha de fin.")

    # 2) Check that there's at least one 'nivel_educativo'
    nivel_educ = new_request.get("nivel_educativo", [])
    if not nivel_educ or len(nivel_educ) == 0:
        errors.append("Debe seleccionar al menos un nivel educativo.")

    # Flag indicating whether the request is ONLY Educación Diferencial
    ed_diferencial_included = "Educación Diferencial" in nivel_educ

    # 3) Check asignatura (except when Educación Diferencial está presente)
    if not ed_diferencial_included:
        asig = new_request.get("asignatura", {})
        total_asig = 0
        if isinstance(asig, dict):
            for niv, arr in asig.items():
                total_asig += len(arr)
        elif isinstance(asig, list):
            total_asig += len(asig)
        if total_asig == 0:
            errors.append("Debe especificar al menos una asignatura para el reemplazo.")

    # 4) Check curso (except Educación Diferencial) and only for webapp
    if not ed_diferencial_included and new_request.get("created_with") != "gform":
        curso_val = new_request.get("curso", {})
        total_cursos = 0
        if isinstance(curso_val, dict):
            for niv, arr in curso_val.items():
                total_cursos += len(arr)
        elif isinstance(curso_val, list):
            total_cursos += len(curso_val)
        if total_cursos == 0:
            errors.append("Debe seleccionar al menos uno o varios cursos/niveles.")

    # 5) If we have a date range, presumably we have dias_seleccionados
    dias = new_request.get("dias_seleccionados", [])
    if (fi is not None and ff is not None) and (fi <= ff):
        if not dias:
            errors.append("No se detectaron días entre las fechas seleccionadas, verifique la selección.")

    # 6) Check for 'status'
    valid_statuses = ["creada","aprobada","rechazada","finalizada"]
    status_val = new_request.get("status", "")
    if status_val not in valid_statuses:
        errors.append(f"Estado (status) inválido: {status_val} (debe estar en {valid_statuses}).")

    # 7) Check horas_contrato
    horas_contrato = new_request.get("horas_contrato", None)
    if horas_contrato is None:
        errors.append("Debe seleccionar las horas de contrato.")

    # 8) Check if 'jefatura' is not None
    jefatura = new_request.get("jefatura", None)
    if jefatura is None:
        errors.append("Debe seleccionar una jefatura.")

    # 8) check basic field presence
    if not new_request.get("school_name"):
        errors.append("Falta school_name en la solicitud.")
    if not new_request.get("created_by"):
        errors.append("Falta created_by en la solicitud.")

    

    is_valid = (len(errors) == 0)
    return (is_valid, errors)


def filter_applicants_by_request(request: dict, cleaned_applicants: "pd.DataFrame") -> "pd.DataFrame":
    """
    Filtra el DataFrame 'cleaned_applicants' (ya limpio con cleanup_applicants) 
    en función de un 'request' que contiene los criterios de búsqueda.

    Criterios:
    1. Genero (si request['genero'] != "Indiferente", se filtra applicant['genero']).
    2. ed_licence_level y cursos:
       - Revisamos request["nivel_educativo"]. Ejemplo: ["Básica","Media"].
       - Si "Básica" se combina con cursos "7° Básico" o "8° Básico", permitimos "Media" en vez de "Básica".
         (p.ej. un docente con ed_licence_level=["Media"] califica si se requieren 7° u 8°).
    3. subjects: 
       - Se filtra solo si el request incluye alguno de los niveles que requieran asignaturas:
         * "Básica"
         * "Media"
         * "Técnico Profesional"
       - Si el request solo contiene "Inicial (PreKinder/Kinder)" o "Educación Diferencial", 
         NO se filtra por subjects (no se hace intersección).
       - Si sí se filtra: con al menos una coincidencia (OR).
    4. disponibilidad (Completa vs. Parcial):
       - "Completa" => applicant["available_days"] contiene *todos* los días en request["dias_de_la_semana"].
       - "Parcial" => al menos un día.
    5. anios_egreso => applicant["anios_egreso"] >= request["anios_egreso"] (si es > 0).
    6. (Comentado) comuna_residencia => no implementado ahora.
    7. (Comentado) horarios => no implementado (applicants no tienen horarios).

    Args:
        request (dict): 
            - genero: "Indiferente", "Femenino", "Masculino"
            - nivel_educativo: list[str], p.ej. ["Básica","Media"]
            - curso: dict => e.g. {"Básica": ["7° Básico","8° Básico"], ...}
            - asignatura: dict => e.g. {"Básica":["Matemáticas"], "Media":["Inglés"]} 
              o list => ["Matemáticas","Inglés"]
            - dias_de_la_semana: list[str], e.g. ["Wednesday","Thursday"]
            - disponibilidad: "Completa" or "Parcial"
            - anios_egreso: int
            ...
        cleaned_applicants (pd.DataFrame): 
            - "genero", "ed_licence_level", "subjects", "available_days", "anios_egreso", etc.

    Returns:
        pd.DataFrame: subset de 'cleaned_applicants' que cumple con los criterios.
    """


    subset = cleaned_applicants.copy()
    print("filter_applicants_by_request: filtering...")
    # print subset columns types using a for where each column goes through apply(type).unique()
    
    # 1) Genero
    genero_req = request.get("genero", "Indiferente")
    if genero_req != "Indiferente":
        subset = subset[ subset["genero"] == genero_req ]

    # 2) Determinación de "effective_levels" con la excepción de 7°/8° Básico => "Media"
    niv_req = request.get("nivel_educativo", [])
    curso_dict = request.get("curso", {})  # dict p.ej. {"Básica":["7° Básico","8° Básico"]}
    effective_levels = set(niv_req)

    # Filtramos => ed_licence_level intersecte con effective_levels
    if effective_levels:
        subset = subset[
            subset["ed_licence_level"].apply(
                lambda levs: any(niv in levs for niv in effective_levels)
            )
        ]

    # 3) Filtrar por subjects solo si hay algún nivel que requiera asignaturas
    #    "Básica", "Media", "Técnico Profesional" => exigen asignaturas
    #    "Inicial (PreKinder/Kinder)" o "Educación Diferencial" => sin asignatura => skip subject filter
    levels_requiring_subj = {"Básica Generalista","Básica con Mención","Media","Técnico Profesional"}
    # si intersection de effective_levels con levels_requiring_subj está vacío => skip
    if effective_levels.intersection(levels_requiring_subj):
        # Flatten request["asignatura"]
        asig_val = request.get("asignatura", {})
        requested_subjs = []
        if isinstance(asig_val, dict):
            for _, arr in asig_val.items():
                requested_subjs.extend(arr)
        elif isinstance(asig_val, list):
            requested_subjs = asig_val
        requested_subjs = list(set(requested_subjs))  # unique

        if requested_subjs:
            # al menos 1 coincidencia
            subset = subset[
                subset["subjects"].apply(
                    lambda s: len(set(s).intersection(requested_subjs)) > 0
                )
            ]

    # 4) Disponibilidad => "Completa" vs "Parcial"
    disp_type = request.get("disponibilidad","Parcial")
    days_req = request.get("dias_de_la_semana", [])
    days_req = list(set(days_req))  # unique
    # ordenar días de la semana
    days_req = sorted(days_req, key=lambda x: ["Lunes","Martes","Miércoles","Jueves","Viernes"].index(x))
    if days_req:
        if disp_type == "Completa":
            print("days_req:",days_req)
            #print("available_days:",subset["available_days"].tolist())
            subset = subset[
                subset["available_days"].apply(
                    lambda dd: all(d in dd for d in days_req)
                )
            ]
        else:

            subset = subset[
                subset["available_days"].apply(
                    lambda dd: any(d in dd for d in days_req)
                )
            ]

    # 5) anios_egreso
    req_anios = request.get("anios_egreso", 0)
    if req_anios > 0:
        subset = subset[ subset["anios_egreso"] >= req_anios ]

    # 6) (Comentado) Filtrar comuna_residencia => no implementado
    # 7) (Comentado) Filtrar horarios => no implementado

    return subset



def find_unprocessed_gform_requests(
    df_gform: pd.DataFrame,
    df_existing: pd.DataFrame
) -> pd.DataFrame:
    """
    Dado el df preprocesado de GForm y el df de solicitudes ya importadas
    (appReemplazosRequests), retorna solo las filas de GForm que aún no
    aparecen en la tabla existente, comparando por (created_at|created_by|school_name).
    """
    # Extraer solo las importadas por GForm
    df_exist_gf = df_existing[df_existing["created_with"] == "gform"].copy()
    if df_exist_gf.empty:
        return df_gform.copy()

    # Normalizar timestamps y construir claves únicas
    df_exist_gf["created_at_dt"] = pd.to_datetime(
        df_exist_gf["created_at"], dayfirst=True, errors="coerce"
    )
    df_exist_gf["__key"] = df_exist_gf.apply(
        lambda r: f"{r['created_at_dt'].strftime('%Y-%m-%d %H:%M:%S')}|{r['created_by']}|{r['school_name']}",
        axis=1
    )
    existing_keys = set(df_exist_gf["__key"])

    # Hacer lo mismo en el df de GForm
    df = df_gform.copy()
    df["created_at_dt"] = pd.to_datetime(df["created_at"], dayfirst=True, errors="coerce")
    df["__key"] = df.apply(
        lambda r: f"{r['created_at_dt'].strftime('%Y-%m-%d %H:%M:%S')}|{r['created_by']}|{r['school_name']}",
        axis=1
    )

    # Filtrar aquellos que NO están en existing_keys
    df_unproc = df[~df["__key"].isin(existing_keys)].copy()
    # Limpiar columnas auxiliares
    return df_unproc.drop(columns=["created_at_dt", "__key"])

def cleanup_applicants(df):
    """
    Limpia y estandariza un DataFrame 'df' de postulantes, incorporando los criterios siguientes:

    1) phone => crea primero df['phone_raw'] con la columna original,
       luego normaliza df['phone'] según las reglas:
         - quitar todo caracter no numérico (+, espacios, guiones, etc.)
         - si tras quitar no-numéricos:
           * si tiene 11 dígitos y los primeros 3 son '569': agrega '+' al inicio => +569XXXXXXXX
           * si tiene 9 dígitos y el primero es '9': => '+56' + 9 dígitos => +569XXXXXXXX
           * si tiene 8 dígitos => '+569' + 8 dígitos => +569XXXXXXXX
           * en otro caso => NaN
    2) undergrad_year => parse a date con formato '%d/%m/%Y'
       => si es a futuro => anios_egreso=0
       => si son más de 80 años => anios_egreso=NaN
    3) available_days => se pasa a lista y se transforman los días a inglés (Lunes=>Monday, etc.)
    4) subjects => crea subjects_raw con la columna original,
       filtra cada item que aparezca en la LISTA_OFICIAL. 
       El resto => se ignora o no se incluye. 
       (p. ej. si se detecta un chunk no está en la lista => se descarta. 
        Si la lista resultante queda vacía => vacía)
    5) ed_licence_level => se crea ed_licence_level_raw con la original,
       luego se parsea por comas. 
       Se mapea con ED_MAPPING => 'Educación Media [7° a IV medio]' => 'Media', etc.
    """


    # Copiamos df
    newdf = df.copy()

    
    # --- 0) Email normalization: lowercase and strip whitespace ---
    if "email" in newdf.columns:
        newdf["email"] = newdf["email"].astype(str).str.lower().str.strip()

    # --- 0.b) Normalize RUT: convert to string, strip, uppercase, handle missing ---
    if "rut" in newdf.columns:
        # Fill NaN/None with empty string, then strip and uppercase
        newdf["rut"] = newdf["rut"].fillna("").astype(str).str.strip().str.upper()
        # Convert any representations of nan back to empty
        newdf.loc[newdf["rut"].isin(["NAN", "NONE"]), "rut"] = ""
    
    # --- 0.a) Remove duplicate applicants by 'rut' and by 'email', keeping last record ---
    # drop_duplicates solo para los ruts duplicados y no nulos, conservando todos los nulos
    if "rut" in newdf.columns :
        nulls = newdf[newdf["rut"]==""].copy()
        dupes = newdf[newdf["rut"] != ""].drop_duplicates(subset=["rut"], keep="last")
        newdf = pd.concat([dupes, nulls], ignore_index=True)

    # Drop duplicates by 'email'
    newdf = newdf.drop_duplicates(subset=["email"], keep="last").reset_index(drop=True)

    # --- 1) PHONE normalización ---
    # Creamos 'phone_raw'
    
    newdf["phone_raw"] = newdf["phone"].copy()
    newdf["phone"] = newdf["phone"].astype(str).str.strip()

    def normalize_phone(p):
        if not isinstance(p, str) or not p.strip():
            return np.nan
        # quitar todo caracter no numérico
        digits = re.sub(r'[^0-9]', '', p)
        # reglas:
        # 1) si len=11 y primeros 3='569' => '+569XXXXXXXX'
        if len(digits) == 11 and digits.startswith("569"):
            return f"+{digits}"
        # 2) si len=9 y empieza con '9' => +56 + 9 => +569XXXXXXXX
        if len(digits) == 9 and digits[0] == '9':
            return f"+56{digits}"
        # 3) si len=8 => +569 + 8 => +569XXXXXXXX
        if len(digits) == 8:
            return f"+569{digits}"
        # en otro caso => nan
        return np.nan

    if "phone" in newdf.columns:
        
        # Normalizamos
        newdf["phone"] = newdf["phone"].apply(normalize_phone)
    else:
        newdf["phone"] = np.nan

    # --- 2) parse undergrad_year => date, anios_egreso => int ---
    def parse_undergrad_date(dstr):
        try:
            return datetime.datetime.strptime(str(dstr).strip(), "%d/%m/%Y").date()
        except:
            return None

    if "undergrad_year" in newdf.columns:
        newdf["undergrad_year"] = newdf["undergrad_year"].apply(parse_undergrad_date)
    

    # calculamos anios_egreso
    def calc_anios_egreso(dt):
        # dt es un date o None
        if dt is None:
            return None
        today = datetime.date.today()
        # si dt > hoy => 0
        if dt > today:
            return 0
        diff = today.year - dt.year
        # si diff > 80 => np.nan
        if diff > 80:
            return None
        return diff
    
    newdf["anios_egreso"] = newdf["undergrad_year"].apply(calc_anios_egreso)
    # --- 3) available_days => lista en inglés ---
    def parse_days_and_translate(x):
        if not isinstance(x, str) or not x.strip():
            return []
        # Use mapping from config
        return [cfg.DAY_MAP.get(d.strip(), d.strip()) for d in x.split(",") if d.strip()]

    if "available_days" in newdf.columns:
    # check if days are written in English
        if all(day in cfg.DAY_MAP.values() for day in newdf["available_days"].dropna().unique()):
            # already in spanish, no need to pase
            pass
        else:
            # parse days and translate
            newdf["available_days"] = newdf["available_days"].apply(parse_days_and_translate)
        

    
    # --- 4) parse subjects => keep raw, filtrar en lista permitida ---
    if "subjects" not in newdf.columns:
        newdf["subjects"] = [[] for _ in range(len(newdf))]
        newdf["subjects_raw"] = ["" for _ in range(len(newdf))]
    else:
        # Guardamos columna original
        newdf["subjects_raw"] = newdf["subjects"].copy()

        def parse_subjects_and_unparsed(subj_str):
            """
            Devuelve una tupla (parsed, unparsed) donde:
              - parsed   -> lista de asignaturas válidas según cfg.ALLOWED_SUBJECTS + SPECIAL_SUBJECT
              - unparsed -> lista de chunks que no se reconocieron
            """
            if not isinstance(subj_str, str) or not subj_str.strip():
                return [], []

            cleaned   = []
            unparsed  = []

            special = cfg.SPECIAL_SUBJECT

            # Caso especial (contiene una coma interna)
            if special in subj_str:
                cleaned.append(special)
                subj_str = subj_str.replace(special, "")

            # Procesamos el resto por comas
            for chunk in [s.strip() for s in subj_str.split(",") if s.strip()]:
                if chunk in cfg.ALLOWED_SUBJECTS:
                    cleaned.append(chunk)
                else:
                    unparsed.append(chunk)
            return cleaned, unparsed

        # Aplicamos la función y separamos en dos columnas
        parsed_series = newdf["subjects"].apply(parse_subjects_and_unparsed)
        newdf["subjects"] = parsed_series.apply(lambda t: t[0])
        newdf["unparseable_subjects"] = parsed_series.apply(lambda t: t[1])

    # --- 5) ed_licence_level => keep raw, map con ED_MAPPING ---
    if "ed_licence_level" not in newdf.columns:
        newdf["ed_licence_level"] = [[] for _ in range(len(newdf))]
        newdf["ed_licence_level_raw"] = ["" for _ in range(len(newdf))]
    else:
        newdf["ed_licence_level_raw"] = newdf["ed_licence_level"].copy()
       
        def parse_ed_level(ed_str):
            if not isinstance(ed_str, str) or not ed_str.strip():
                return []
            return [
                cfg.ED_MAPPING[chunk.strip()]
                for chunk in ed_str.split(",")
                if chunk.strip() in cfg.ED_MAPPING.keys()
            ]
        newdf["ed_licence_level"] = newdf["ed_licence_level"].apply(parse_ed_level)

    return newdf

# transformar listas en dummies
def transform_list_to_dummies(df, column_name, prefix):
    """
    Transforms a column with lists into multiple dummy columns.
    """
    # Create dummy columns
    dummies = df[column_name].apply(lambda x: pd.Series(1, index=x)).fillna(0).astype(int)
    # Rename columns
    dummies.columns = [f"{prefix}_{col}" for col in dummies.columns]
    # Concatenate with original dataframe
    df = pd.concat([df, dummies], axis=1)
    return df


# --- Dynamic selectors: new general filter widgets ---
def build_selector_definitions(df: pd.DataFrame, selectors: dict, include_none: bool = True) -> dict:
    """
    Genera definiciones de selectores con opciones basadas en el DataFrame.
    selectors: dict con field->{label, widget, options (callable o list), default}
    - For widget == "date_input", allows an extra key "operator_options" in cfg, defaults to ["<=", ">="].
    """
    defs = {}
    for field, cfg in selectors.items():
        label = cfg.get("label", field)
        widget = cfg.get("widget", "selectbox")
        opts = cfg.get("options", None)
        # resolver opciones
        options = opts(df) if callable(opts) else list(opts) if opts is not None else []
        default = cfg.get("default", None)
        definition = {
            "label": label,
            "widget": widget,
            "options": options,
            "default": default
        }
        # allow per-field width if provided
        if "width" in cfg:
            definition["width"] = cfg["width"]
        # para selectbox incluimos None como opción "Todos"
        if include_none and widget == "selectbox":
            definition["options"] = [None] + options
        # For date_input, allow operator_options
        if widget == "date_input":
            definition["operator_options"] = cfg.get("operator_options", ["<=", ">=","=="])
        defs[field] = definition
    return defs



from typing import Union

def render_selectors(defs: dict, layout: Union[int, dict] = None, label_visibility: str = "collapsed") -> dict:
    """
    Creates widgets for each selector definition.
    Date inputs render as two separate columns: an operator selectbox and a date_input.
    Returns a dict mapping each original field to its selected value:
      - For non-date fields: value or list of values.
      - For date fields: a dict {"op": operator, "value": date}.
    """
    filter_values = {}

    # Determine layout configuration
    n_cols = 3
    containers = None
    widths = None
    if isinstance(layout, dict):
        n_cols = layout.get("n_cols", n_cols)
        containers = layout.get("containers", None)
        widths = layout.get("widths", None)
    elif isinstance(layout, int):
        n_cols = layout

    # Flatten definitions into items: date_input splits into two items
    items = []
    for field, cfg in defs.items():
        if cfg["widget"] == "date_input":

            # Date picker
            items.append((
                field,
                {
                    "label": cfg["label"],
                    "widget": "date_input",
                    "default": cfg.get("default", None),
                    "width": cfg.get("width", 1)
                }
            ))
            # Operator selector
            items.append((
                f"{field}_op",
                {
                    "label": "Operador",
                    "widget": "selectbox",
                    "options": cfg.get("operator_options", ["<=", ">=", "=="]),
                    "default": cfg.get("default_op", cfg.get("operator_options", ["<=", ">=", "=="])[0]),
                    "width": cfg.get("width", 1)
                }
            ))
        else:
            # Regular selector occupies one column
            item_cfg = cfg.copy()
            item_cfg.setdefault("width", 1)
            items.append((field, item_cfg))

    # Build column widths list
    if widths is not None:
        col_widths = widths
    else:
        col_widths = [cfg.get("width", 1) for _, cfg in items]

    # Instantiate columns
    cols = st.columns(col_widths) if containers is None else containers

    # Render widgets
    for i, (field, cfg) in enumerate(items):
        with cols[i]:
            widget = cfg["widget"]
            label = cfg["label"]
            key = f"filter_{field}"
            if widget == "selectbox":
                options = cfg.get("options", [])
                default = cfg.get("default", None)
                val = st.selectbox(
                    label,
                    options,
                    index=options.index(default) if default in options else 0,
                    key=key,
                    format_func=lambda x: "Todos" if x is None else str(x),
                    label_visibility=label_visibility,
                )
                filter_values[field] = val

            elif widget == "multiselect":
                options = cfg.get("options", [])
                default = cfg.get("default", [])
                val = st.multiselect(
                    label,
                    options,
                    default=default,
                    key=key,
                    label_visibility=label_visibility,
                )
                filter_values[field] = val

            elif widget == "date_input":
                # Capture date; operator was captured in separate item
                default = cfg.get("default", None)
                val = st.date_input(
                    label,
                    value=default,
                    key=key,
                    label_visibility=label_visibility,
                )
                filter_values[field] = val

            else:
                # fallback: no widget
                filter_values[field] = None

    # Combine operator and date into single dict for each date field
    for field, cfg in defs.items():
        if cfg["widget"] == "date_input":
            op_key = f"{field}_op"
            date_val = filter_values.pop(field, None)
            op_val = filter_values.pop(op_key, None)
            filter_values[field] = {"op": op_val, "value": date_val}

    return filter_values


def filter_df_by_filters(df: pd.DataFrame, filters: dict) -> pd.DataFrame:
    """
    Aplica filtros de igualdad y rango de fecha a df según dict filters.
    - selectbox/multiselect: igualdad o isin
    - date_input: supports dict {"op": op, "value": value} for operator and value
    """
    df_out = df.copy()
    for field, val in filters.items():
        if val is None or (isinstance(val, list) and len(val) == 0):
            continue
        # Enhanced date filter: if val is dict with "op" and "value"
        if isinstance(val, dict) and "op" in val and "value" in val:
            op = val["op"]
            value = val["value"]
            if value is None or value == "":
                continue
            if op == ">=":
                df_out = df_out[pd.to_datetime(df_out[field]) >= pd.to_datetime(value)]
            else:
                df_out = df_out[pd.to_datetime(df_out[field]) <= pd.to_datetime(value)]
        elif isinstance(val, (datetime.date, pd.Timestamp)):
            df_out = df_out[pd.to_datetime(df_out[field]) >= pd.to_datetime(val)]
        elif isinstance(val, list):
            df_out = df_out[df_out[field].isin(val)]
        else:
            df_out = df_out[df_out[field] == val]
    return df_out


# --- Sorting controls for DataFrame panels ---
def build_sort_definitions(sort_fields: list, levels: int = 2) -> dict:
    """
    Genera definiciones de widgets para ordenar el DataFrame.
    - sort_fields: lista de nombres de columnas disponibles para ordenar.
    - levels: cantidad de niveles de orden (primer nivel, segundo nivel, ...).
    Retorna un dict listo para pasar a render_selectors().
    """
    selectors = {}
    for i in range(1, levels + 1):
        selectors[f"sort_key_{i}"] = {
            "label": f"Orden {i}",
            "widget": "selectbox",
            "options": [None] + sort_fields,
            "default": None
        }
        selectors[f"sort_dir_{i}"] = {
            "label": f"Dirección {i}",
            "widget": "selectbox",
            "options": ["ASC", "DESC"],
            "default": "ASC"
        }
    return selectors


def apply_sort_df(df: pd.DataFrame, sorters: dict) -> pd.DataFrame:
    """
    Aplica ordenamiento al DataFrame según el dict `sorters` obtenido de render_selectors.
    Busca keys 'sort_key_i' y 'sort_dir_i' y construye las listas para sort_values.
    """
    keys = []
    asc = []
    for key, val in sorters.items():
        if key.startswith("sort_key_") and val:
            level = key.split("_")[-1]
            dir_key = f"sort_dir_{level}"
            direction = sorters.get(dir_key, "ASC")
            keys.append(val)
            asc.append(True if direction == "ASC" else False)
    if keys:
        return df.sort_values(by=keys, ascending=asc, inplace=False)
    return df

def render_manage_button(
    row: dict,
    disabled: bool = False,
    widget_key: str = None,
    page: str = "appReemplazos/panel_seleccion_candidato.py",
    header: str = "Ir",
):
    """
    Renderiza un botón 'Gestionar' en la tabla.
    Al hacer clic, asigna session_state['request_id'] y cambia de página con st.switch_page.
    """
    if st.button(header, disabled=disabled, key=widget_key):
        # 1) Guardar el ID en session_state
        st.session_state["request_id"] = int(row["replacement_id"])
        # 2) Navegar a la página de selección de candidato
        st.switch_page(page)


# --- Cascading filters for DataFrames ---
def render_cascade_filters(
    df: pd.DataFrame,
    selectors: dict,
    key_prefix: str = "cascade",
    n_cols: int = 3,
    widths: list = None,
    label_visibility: str = "collapsed"
) -> pd.DataFrame:
    """
    Renders cascading filters: each widget filters the DataFrame for subsequent filters.
    Returns the filtered DataFrame.
    selectors: dict field->{label, widget, default}
      - widget: "selectbox", "multiselect", or "date_input"
      - options key is ignored: dynamic options are taken from df at each step.
    """
    df_current = df.copy()
    # Instantiate columns with custom widths if provided
    if widths:
        cols = st.columns(widths+[1])
    else:
        cols = st.columns(n_cols+1)
    # idx = 0
    # for field, cfg in selectors.items():
    #     col = cols[idx % len(cols)]
    # Renderizamos cada filtro en su propia columna (excepto la última, que será el botón)
    for idx, (field, cfg) in enumerate(selectors.items()):
        col = cols[idx]
        label = cfg.get("label", field)
        widget = cfg.get("widget", "selectbox")
        default = cfg.get("default", None)
        key = f"{key_prefix}_{field}"
        with col:
            if widget == "selectbox":
                opts = sorted(df_current[field].dropna().unique().tolist())
                opts = [None] + opts
                val = st.selectbox(
                    label,
                    opts,
                    index=opts.index(default) if default in opts else 0,
                    key=key,
                    label_visibility=label_visibility,
                    format_func=lambda x: "Todos" if x is None else str(x)
                )
                if val is not None:
                    df_current = df_current[df_current[field] == val]

            elif widget == "multiselect":
                opts = sorted(df_current[field].dropna().unique().tolist())
                val = st.multiselect(
                    label,
                    opts,
                    default=default or [],
                    key=key,
                    label_visibility=label_visibility,
                )
                if val:
                    df_current = df_current[df_current[field].isin(val)]

            elif widget == "date_input":
                val = st.date_input(
                    label,
                    value=default,
                    key=key,
                    label_visibility=label_visibility,
                )
                if isinstance(val, (datetime.date, pd.Timestamp)):
                    df_current = df_current[pd.to_datetime(df_current[field]) >= pd.to_datetime(val)]

            else:
                # unsupported widget: skip
                pass

    # Finalmente, renderizamos el botón de limpiar filtros en la columna extra
    with cols[-1]:
        if st.button("Limpiar Filtros", key=f"{key_prefix}_clear"):
            for field in selectors:
                print(f"Limpiando {key_prefix}_{field}")
                print(f"st.session_state[{key_prefix}_{field}]:", st.session_state.get(f"{key_prefix}_{field}"))
                st.session_state.pop(f"{key_prefix}_{field}", None)
                print(f"st.session_state[{key_prefix}_{field}] actualizado:", st.session_state.get(f"{key_prefix}_{field}", None))
            return df.copy()
 
    return df_current
        


