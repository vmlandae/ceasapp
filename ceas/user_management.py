import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
import datetime
import time
from ceas.connections_manager import get_random_connection

def get_users_conn(ttl=0):
    """
    Función para obtener la conexión a la base de datos de usuarios.
    Args:
        ttl (int): Tiempo de vida de la conexión en segundos. Por defecto es 0.
    """
    try:
        rand_conn = get_random_connection()
        
        conn = st.connection(rand_conn, type= GSheetsConnection, ttl=ttl)
        # prints para debug de cuando se crea la conexión o cuando se reutiliza

    except Exception as e:
        st.error(f"Error al conectar con la base de datos de usuarios: {e}")
        return None
    return conn

def get_user_info(app_name: str,email):
    """
    Función para obtener la información del usuario activo de la app desde GSheets, entre ellos el rol.
    No requiere permisos especiales, y el email del usuario activo se obtiene de st.session_state.
    Args:
        app_name (str): Nombre de la app para buscar en la planilla de usuarios, la hoja correspondiente a la app, que tiene de nombre app_name + "Users"
    """
    
    if not email:
        st.error("No se pudo obtener la información del usuario")
        time.sleep(1)
        st.spinner("Cerrando sesión...")
        time.sleep(3)
        st.logout()
        return None

    email = str(email).lower().strip()
    
    # 2) Crear la conexión a GSheets
    conn = get_users_conn(ttl=0)
    
    # 3) Intentar leer la hoja app_name + "Users" 
    try: 
        df = conn.read(worksheet=app_name + "Users")  
    except Exception as e:
        st.error(f"Error al leer la hoja '{app_name}Users': {e}")
        return None

    # 4) Filtrar la fila para el email actual
    user_row = df.loc[df['email'].str.lower().str.strip() == email]
    if user_row.empty:
        st.error(f"No se encontró al usuario {st.session_state.user_data.email}. Cerrando sesión...")
        st.spinner("Cerrando sesión...")
        time.sleep(2)
        st.logout()
        return None
    # 5) Retornar la info (solo 1 fila)
    user_info = user_row.iloc[0].to_dict()
    return user_info

def get_all_users(reset=False):
    if st.session_state.role not in ["admin", "owner", "oficina_central"]:
        st.error("No tienes acceso a esta sección.")
        st.stop()
    
    conn = get_users_conn()
    if reset:
        conn.reset()
    if conn is None:
        st.stop("No se pudo conectar a la base de datos de usuarios.")
        return None
    df = conn.read(worksheet=st.session_state["app_name"] + "Users")
    return df

def change_user_role(email: str, new_role: str, df_users: pd.DataFrame):

    # 1) Verificaciones previas:
    # Chequear que el usuario tenga permisos para cambiar el rol
    if st.session_state.role not in ["admin", "owner", "oficina_central"]:
        st.error("No tienes acceso a esta sección.")
        st.stop()
    
    
    
    # 2) Crear la conexión a GSheets y leer la hoja correspondiente
    try:
        conn = get_users_conn()
        df = conn.read(worksheet=st.session_state["app_name"] + "Users")
    except Exception as e:
        st.error(f"Error al leer la hoja {st.session_state['app_name']}Users: {e}")
        return False, df_users
    
    # 3) Chequear que la hoja leída y el df_users sean iguales, es decir, que no haya habido cambios en la hoja mientras se leía
    if not df.equals(df_users):
        st.error("Hubo cambios en la base de datos de usuarios. Por favor, refresca la página y vuelve a intentarlo.")

        return False, df_users

    # 4) Cambiar el rol del usuario
    try:
        df_mod = df_users.copy()
        df_mod.loc[df["email"] == email, "role"] = new_role
        conn.update(data=df_mod, worksheet=st.session_state["app_name"] + "Users")
    except Exception as e:
        st.error(f"Error al escribir en la hoja {st.session_state['app_name']}Users: {e}. El rol no se cambió.")
        return False, df_users
    
    return True, df_mod

def delete_user(email: str, df_users: pd.DataFrame):
    # 1) Verificaciones previas:
    # Chequear que el usuario tenga permisos para cambiar el rol
    if st.session_state.role not in ["owner","admin","oficina_central"]:
        st.error("No tienes acceso a esta sección.")
        st.stop()
        # 2) Crear la conexión a GSheets y leer la hoja correspondiente
    try:
        conn = get_users_conn()
        df = conn.read(worksheet=st.session_state["app_name"] + "Users")
    except Exception as e:
        st.error(f"Error al leer la hoja {st.session_state['app_name']}Users: {e}")
        return False, df_users
    
    # 3) Chequear que la hoja leída y el df_users sean iguales, es decir, que no haya habido cambios en la hoja mientras se leía
    if not df.equals(df_users):
        st.error("Hubo cambios en la base de datos de usuarios. Por favor, refresca la página y vuelve a intentarlo.")

        return False, df_users
    # 4) Desactivar el usuario

    try:
        df_mod = df_users.copy()
        # delete en realidad es desactivar, cambiar status a inactive
        df_mod.loc[df_mod["email"] == email, "status"] = "inactive"
        conn = get_users_conn()
        conn.update(data=df_mod, worksheet=st.session_state["app_name"] + "Users")
    except Exception as e:
        st.error(f"Error al escribir en la hoja {st.session_state['app_name']}Users: {e}")
        return False, df_users
    return True, df_mod

def add_user(email: str, name: str, role: str, school_id: int, school_name: str, status: str):
    if st.session_state.role not in ["owner", "admin", "oficina_central"]:
        st.error("No tienes acceso a esta sección.")
        st.stop()
    
    conn = get_users_conn()
    df_users = conn.read(worksheet=st.session_state["app_name"] + "Users")
    # crear nueva fila: user_id, email, name, role, school_id, 'school_name', status, created_at, last_login
    # user_id es el máximo de la columna user_id + 1
    user_id = df_users["user_id"].max() + 1

    new_row = pd.DataFrame({
        "user_id": [user_id],
        "email": [email],
        "name": [name],
        "role": [role],
        "school_id": [school_id],
        "school_name": [school_name],
        "status": [status],
        # tz de chile, santiago
        "created_at": [datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
        "last_login": [None]
    })
    df_users = pd.concat([df_users, new_row], ignore_index=True)
    try:
        conn.update(data=df_users, worksheet=st.session_state["app_name"] + "Users")
    except Exception as e:
        st.error(f"Error al escribir en la hoja {st.session_state['app_name']}Users: {e}")
        return False, df_users
    return True, df_users




