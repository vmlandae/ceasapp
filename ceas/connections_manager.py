import streamlit as st
import random

def get_random_connection():
    try:
    # elegir al azar una de las conexiones disponibles
        rand_conn = random.choice(st.session_state["connections"])
        return rand_conn
    except Exception as e:
        st.error(f"Error al obtener una conexión: {e}")
        return None
    
