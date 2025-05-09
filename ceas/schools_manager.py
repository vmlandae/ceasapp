"""
schools_manager.py

Maneja la tabla "schools" (colegios y/o "oficina_central") en Google Sheets.

Schema 'schools':
  school_id     number (PK)
  school_name   string
  comuna        string
  address       string
  status        string (activo / inactivo)
  type          string (colegio / oficina_central)
  version       int (opcional, para concurrency)

Roles:
  - 'owner','admin' => pueden crear, editar, eliminar
  - 'oficina_central' => (opcional) solo lectura o edición si lo deseas
  - 'colegio' => sin acceso al CRUD, solo podrían ver "su" school?

La idea es que admin_panel.py llame a estas funciones para gestionar la tabla.
"""

import ceas.config as cfg
import pickle
import streamlit as st
import pandas as pd
import datetime
from streamlit_gsheets import GSheetsConnection
from ceas.connections_manager import get_random_connection
def get_schools_conn(ttl=0):
    """
    Crea la conexión a la hoja "app_name + Schools",    
    """
    
    try:
        # elegir al azar una de las conexiones disponibles
        rand_conn = get_random_connection()
        conn = st.connection(rand_conn, type=GSheetsConnection, ttl=ttl)

    except Exception as e:
        st.error(f"Error al conectar con la base 'schools': {e}")
        return None
    
    return conn

    

def get_all_schools() -> pd.DataFrame:
    """
    Lee la hoja "app_name + Schools" y retorna un DataFrame con:
      [school_id(int), school_name(str), comuna(str), address(str),
       status(str), type(str), version(int?)]
    Roles:
      'owner','admin' => full
      'oficina_central' => (decidir si solo read)
      'colegio' => usualmente no ve todo, o en read-only, se define.

    Filtra si se desea, p.ej. si un 'colegio' no debe ver otras schools.
    Por default, devolvemos todo si es un rol alto, 
    y devolvemos su "school" si es admin_colegio o user_colegio, etc. (Podrías implementarlo).
    """
    role = st.session_state.role
    if role not in ["owner","admin","oficina_central","admin_colegio","user_colegio"]:
        st.warning("No tienes acceso para ver la lista de colegios.")
        return pd.DataFrame()

    conn = get_schools_conn()
    if not conn:
        return pd.DataFrame()

    worksheet_name = st.session_state["app_name"] + "Schools"
    try:
        df = conn.read(worksheet=worksheet_name)
    except Exception as e:
        st.error(f"Error leyendo la hoja '{worksheet_name}': {e}")
        print(e)
        return pd.DataFrame()

    # parse school_id => int
    if "school_id" in df.columns:
        df["school_id"] = pd.to_numeric(df["school_id"], errors="coerce").fillna(0).astype(int)

    # Si quieres filtrar a 'colegio' => solo su school_id
    if role in ["directivo_colegio","docente_colegio"]:
        # si NO deseas que vean otros
        # user_school_id = st.session_state["user_info"].get("school_id",0)
        # df = df[df["school_id"]==user_school_id]
        pass

    return df

def get_next_school_id(df:pd.DataFrame) -> int:
    """
    Retorna el siguiente ID => max + 1 o 1 si df empty.
    """
    if df.empty:
        return 1
    return df["school_id"].max() + 1

def create_school(school_name:str, comuna:str, address:str, status:str="activo", type_:str="colegio") -> bool:
    """
    Crea una fila en la tabla 'schools'.
    roles => 'owner','admin' => a discreción
    Se genera school_id => autoincrement
    Se maneja concurrency si la col "version" existe => new row => version=1
    """
    role = st.session_state.role
    if role not in ["owner","admin"]:
        st.error("No tienes permiso para crear un colegio.")
        return False

    conn = get_schools_conn()
    if not conn:
        return False

    ws_name = st.session_state["app_name"] + "Schools"
    try:
        df_orig = conn.read(worksheet=ws_name)
    except Exception as e:
        st.error(f"Error leyendo la hoja 'Schools': {e}")
        return False

    df_mod = df_orig.copy()
    if "school_id" in df_mod.columns:
        df_mod["school_id"] = pd.to_numeric(df_mod["school_id"], errors='coerce').fillna(0).astype(int)

    new_id = get_next_school_id(df_mod)
    new_row = {
        "school_id": new_id,
        "school_name": school_name,
        "comuna": comuna,
        "address": address,
        "status": status,
        "type": type_,
        "version": 1  # concurrency
    }

    row_df = pd.DataFrame([new_row])
    df_mod = pd.concat([df_mod, row_df], ignore_index=True)

    try:
        conn.update(data = df_mod, worksheet=ws_name)
        return True
    except Exception as e:
        st.error(f"Error creando colegio: {e}")
        return False

def update_school(school_id:int, updates:dict) -> bool:
    """
    Actualiza un registro en 'schools' dado por school_id con 'updates' dict.
    concurrency => si 'version' col existe => incrementa 
    roles => 'owner','admin' => se define 
    """
    role = st.session_state.role
    if role not in ["owner","admin"]:
        st.error("No tienes permiso para actualizar un colegio.")
        return False

    conn = get_schools_conn()
    if not conn:
        return False

    ws_name = st.session_state["app_name"] + "Schools"
    try:
        df_orig = conn.read(worksheet=ws_name)
    except Exception as e:
        st.error(f"Error leyendo 'Schools': {e}")
        return False

    df_mod = df_orig.copy()
    if "school_id" in df_mod.columns:
        df_mod["school_id"] = pd.to_numeric(df_mod["school_id"], errors='coerce').fillna(0).astype(int)

    row_index = df_mod.index[df_mod["school_id"]==school_id]
    if len(row_index)==0:
        st.error(f"No se encontró school_id={school_id}")
        return False
    idx = row_index[0]

    # concurrency => version
    if "version" in df_mod.columns:
        old_ver = df_mod.at[idx,"version"]
        new_ver = old_ver + 1

    for k,v in updates.items():
        if k in df_mod.columns:
            df_mod.at[idx,k] = v

    if "version" in df_mod.columns:
        df_mod.at[idx,"version"] = new_ver

    try:
        conn.update(data = df_mod, worksheet=ws_name)
        return True
    except Exception as e:
        st.error(f"Error actualizando colegio: {e}")
        return False

def delete_school(school_id:int) -> bool:
    """
    Elimina la fila con school_id en 'schools'.
    Requiere rol => 'owner','admin'.
    Chequear si no hay users con school_id => integridad (opcional).
    """
    role = st.session_state.role
    if role not in ["owner","admin"]:
        st.error("No tienes permiso para eliminar un colegio.")
        return False

    conn = get_schools_conn()
    if not conn:
        return False

    ws_name = st.session_state["app_name"] + "Schools"
    try:
        df_orig = conn.read(worksheet=ws_name)
    except Exception as e:
        st.error(f"Error leyendo 'Schools': {e}")
        return False

    df_mod = df_orig.copy()
    if "school_id" in df_mod.columns:
        df_mod["school_id"] = pd.to_numeric(df_mod["school_id"], errors='coerce').fillna(0).astype(int)

    idx = df_mod.index[df_mod["school_id"]==school_id]
    if len(idx)==0:
        st.error(f"No se encontró school_id={school_id}")
        return False

    # (Opcional) Chequear si hay users => integridad
    # from ceas.user_management import ...
    # if users exist => st.error("No se puede eliminar un colegio con usuarios asignados.")

    df_mod.drop(idx, inplace=True)
    try:
        conn.update(data = df_mod, worksheet=ws_name)
        return True
    except Exception as e:
        st.error(f"Error al eliminar colegio: {e}")
        return False

@st.dialog("Editar colegio")
def edit_school_dialog(school_id:int):
    """
    Abre un diálogo para editar un colegio.
    roles => 'owner','admin'

    args:
        school_id: int

    returns:
    
    """
    pass

def get_school_requests(app_name):

    conn = get_schools_conn()
    df = conn.read(worksheet=app_name + "Requests")
    return df



def get_candidates_to_validate(app_name):
    conn = get_schools_conn()
    df = conn.read(worksheet=app_name + "Candidates")
    return df

def validate_candidate(email, df_candidates):
    df_candidates.loc[df_candidates["email"] == email, "validated"] = True
    conn = get_schools_conn()
    try:
        conn.update(data=df_candidates, worksheet=st.session_state["app_name"] + "Candidates")
        return True, df_candidates
    except Exception as e:
        st.error(f"Error al validar el candidato: {e}")
        return False, df_candidates

def get_available_candidates(app_name):
    conn = get_schools_conn()
    df = conn.read(worksheet=app_name + "Candidates")
    if df.empty:
        return pd.DataFrame()
    else:
        return df[df["validated"] == True]
    

def select_candidate(email, df_candidates):
    df_candidates.loc[df_candidates["email"] == email, "selected"] = True
    conn = get_schools_conn()
    try:
        conn.update(data=df_candidates, worksheet=st.session_state["app_name"] + "Candidates")
        return True, df_candidates
    except Exception as e:
        st.error(f"Error al seleccionar el candidato: {e}")
        return False, df_candidates

def get_proposed_candidates(app_name):
    conn = get_schools_conn()
    df = conn.read(worksheet=app_name + "Candidates")
    if df.empty:
        return pd.DataFrame()
    else:
        return df[df["selected"] == True]

def choose_candidate(email, df_proposed_candidates):
    df_proposed_candidates.loc[df_proposed_candidates["email"] == email, "chosen"] = True
    conn = get_schools_conn()
    try:
        conn.update(data=df_proposed_candidates, worksheet=st.session_state["app_name"] + "Candidates")
        return True, df_proposed_candidates
    except Exception as e:
        st.error(f"Error al elegir el candidato: {e}")
        return False, df_proposed_candidates

def get_service_receptions(app_name):
    conn = get_schools_conn()
    df = conn.read(worksheet=app_name + "Receptions")
    return df

def register_reception(email, rating, df_receptions):
    df_receptions.loc[df_receptions["email"] == email, "rating"] = rating
    conn = get_schools_conn()
    try:
        conn.update(data=df_receptions, worksheet=st.session_state["app_name"] + "Receptions")
        return True, df_receptions
    except Exception as e:
        st.error(f"Error al registrar la recepción: {e}")
        return False, df_receptions