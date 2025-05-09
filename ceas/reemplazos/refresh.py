import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
def refresh_dataframes(dfs = "dfs", refresh_list = "refresh_list",file_callback=None):
    """Refresca los DataFrames de las hojas de la spreadsheet y retorna un diccionario con los DataFrames con la estructura {sheet_name: df}, usando la conexión de GSheets.

    Returns:
        dict: Diccionario con los DataFrames de las hojas de la spreadsheet.
    """
    if dfs in st.session_state and refresh_list in st.session_state:
        
        print("Refrescando información de la base de datos")

        refresh_conn = st.connection(st.session_state["connections"][1], type=GSheetsConnection)
            
            # leemos las hojas que necesitan ser refrescadas
        if st.session_state[refresh_list] is not None:
            for sheet_name in st.session_state[refresh_list]:
                print(f"Refrescando hoja {sheet_name}")
                st.session_state['dfs'][sheet_name] = refresh_conn.read(worksheet=sheet_name,ttl=0,max_entries=1)
                

            del st.session_state['refresh_list']
            st.session_state['dfs'] = {k.replace(st.session_state["app_name"],"").lower():v for k,v in st.session_state['dfs'].items()}
            
    elif dfs in st.session_state and refresh_list not in st.session_state:
        print("No hay hojas que refrescar")
    else:
        print("No hay DataFrames para refrescar")
    if file_callback is not None:

        return file_callback, st.session_state['dfs']
    