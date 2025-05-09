"""
receipts_manager.py

Módulo para administrar la tabla "receipts" en Google Sheets.

Schema 'receipts':
  - receipt_id     number (PK)
  - order_id       number (FK: orders.order_id)
  - user_id        number (FK: users.user_id)
  - receipt_date   date/time
  - status         string (e.g., "recibido completo", "faltan x", "defectuoso")
  - comments       string

Cada función incluye controles básicos, manejo de errores y versionado si se desea (aquí se omite versionado para simplificar).
"""

import streamlit as st
import pandas as pd
import datetime
from streamlit_gsheets import GSheetsConnection
from ceas.connections_manager import get_random_connection

def get_receipts_conn(ttl=0):
    """
    Establece la conexión con la hoja 'app_nameReceipts' en Google Sheets.
    
    Args:
      ttl (int): Tiempo en segundos para cachear la conexión (por defecto 3 segundos para reflejar cambios casi real-time).
    
    Returns:
      Conexión (GSheetsConnection) o None en caso de error.
    """
    try:
        rand_conn = get_random_connection()
        conn = st.connection(rand_conn, type=GSheetsConnection, ttl=ttl)
    except Exception as e:
        st.error(f"Error al conectar con la base de datos de recepciones: {e}")
        return None
    return conn

def get_all_receipts() -> pd.DataFrame:
    """
    Lee la hoja de Receipts y retorna un DataFrame con:
      [receipt_id (int), order_id (int), user_id (int),
       receipt_date (str/datetime), status (str), comments (str)]
    
    Returns:
      DataFrame con la información de todas las recepciones.
    """
    conn = get_receipts_conn()
    if conn is None:
        st.stop("No se pudo conectar a la base de datos de recepciones.")
        return None
    df = conn.read(worksheet=st.session_state["app_name"] + "Receipts")
    return df

def get_next_receipt_id(df: pd.DataFrame) -> int:
    """
    Calcula el siguiente receipt_id basado en el DataFrame actual.
    
    Args:
      df (DataFrame): DataFrame con la columna 'receipt_id'.
    
    Returns:
      int: El siguiente ID (max + 1) o 1 si el DataFrame está vacío.
    """
    if df.empty:
        return 1
    return df["receipt_id"].max() + 1

def create_receipt(order_id: int, user_id: int, status: str, comments: str) -> bool:
    """
    Crea un nuevo registro en la tabla 'receipts'.
    
    Args:
      order_id (int): ID del order al que se asocia la recepción.
      user_id (int): ID del usuario que reporta la recepción.
      status (str): Estado de la recepción ("recibido completo", "faltan x", "defectuoso").
      comments (str): Comentarios adicionales.
      
    Returns:
      bool: True si la creación fue exitosa, False en caso de error.
    """
    conn = get_receipts_conn()
    if not conn:
        return False
    ws_name = st.session_state["app_name"] + "Receipts"
    try:
        df_orig = conn.read(worksheet=ws_name)
    except Exception as e:
        st.error(f"Error leyendo la hoja 'Receipts': {e}")
        return False
    df_mod = df_orig.copy()
    
    # Aseguramos que 'receipt_id' se trate como int
    if "receipt_id" in df_mod.columns:
        df_mod["receipt_id"] = pd.to_numeric(df_mod["receipt_id"], errors="coerce").fillna(0).astype(int)
    
    new_id = get_next_receipt_id(df_mod)
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    new_row = {
        "receipt_id": new_id,
        "order_id": order_id,
        "user_id": user_id,
        "receipt_date": now_str,
        "status": status,
        "comments": comments
    }
    new_df = pd.DataFrame([new_row])
    df_mod = pd.concat([df_mod, new_df], ignore_index=True)
    
    try:
        conn.update(data = df_mod, worksheet=ws_name)
        return True
    except Exception as e:
        st.error(f"Error creando receipt: {e}")
        return False

def update_receipt(receipt_id: int, updates: dict) -> bool:
    """
    Actualiza un registro de receipt identificado por receipt_id.
    
    Args:
      receipt_id (int): ID del receipt a actualizar.
      updates (dict): Diccionario con las columnas a actualizar y sus nuevos valores.
    
    Returns:
      bool: True si la actualización fue exitosa, False en caso de error.
    """
    conn = get_receipts_conn()
    if not conn:
        return False
    ws_name = st.session_state["app_name"] + "Receipts"
    try:
        df_orig = conn.read(worksheet=ws_name)
    except Exception as e:
        st.error(f"Error leyendo 'Receipts': {e}")
        return False
    df_mod = df_orig.copy()
    
    if "receipt_id" in df_mod.columns:
        df_mod["receipt_id"] = pd.to_numeric(df_mod["receipt_id"], errors="coerce").fillna(0).astype(int)
    
    idx = df_mod.index[df_mod["receipt_id"] == receipt_id]
    if len(idx) == 0:
        st.error(f"No se encontró receipt_id={receipt_id}")
        return False
    irow = idx[0]
    
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for k, v in updates.items():
        if k in df_mod.columns:
            df_mod.at[irow, k] = v
    # Actualizamos la fecha de última actualización en 'receipt_date'
    df_mod.at[irow, "receipt_date"] = now_str
    
    try:
        conn.update(data = df_mod, worksheet=ws_name)
        return True
    except Exception as e:
        st.error(f"Error actualizando receipt: {e}")
        return False

def delete_receipt(receipt_id: int) -> bool:
    """
    Elimina un registro de receipt identificado por receipt_id.
    
    Args:
      receipt_id (int): ID del receipt a eliminar.
    
    Returns:
      bool: True si la eliminación fue exitosa, False en caso de error.
    """
    conn = get_receipts_conn()
    if not conn:
        return False
    ws_name = st.session_state["app_name"] + "Receipts"
    try:
        df_orig = conn.read(worksheet=ws_name)
    except Exception as e:
        st.error(f"Error leyendo 'Receipts': {e}")
        return False
    df_mod = df_orig.copy()
    
    if "receipt_id" in df_mod.columns:
        df_mod["receipt_id"] = pd.to_numeric(df_mod["receipt_id"], errors="coerce").fillna(0).astype(int)
    
    idx = df_mod.index[df_mod["receipt_id"] == receipt_id]
    if len(idx) == 0:
        st.error(f"No se encontró receipt_id={receipt_id}")
        return False
    df_mod.drop(idx, inplace=True)
    
    try:
        conn.update(data = df_mod, worksheet=ws_name)
        return True
    except Exception as e:
        st.error(f"Error eliminando receipt: {e}")
        return False