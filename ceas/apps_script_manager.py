"""
apps_script_manager.py

Módulo para interactuar con Apps Script (ej. un script que maneje forms dinámicas, etc.)
Podrías usar la 'Apps Script Execution API' con google-api-python-client, 
o mandar requests a un "webapp" en Apps Script.

Pros:
 - Reutilizas tu script Apps Script avanzado
Cons:
 - Debes implementar la publish del script, la oauth, domain-wide delegation, etc.
"""

import streamlit as st
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

def get_apps_script_service(sa_credentials_file:str, subject_email:str) -> object:
    """
    Crea un 'script' service usando la Apps Script Execution API, 
    domain-wide delegation si la policy lo permite, 
    subject_email => la cuenta a impersonar.
    Requiere habilitar la API 'Google Apps Script API'
    en tu Cloud project.
    """
    SCOPES = ["https://www.googleapis.com/auth/spreadsheets", 
              "https://www.googleapis.com/auth/script.external_request",
              "https://www.googleapis.com/auth/drive",
              # ... lo que tu script necesite
             ]
    creds = Credentials.from_service_account_file(sa_credentials_file, scopes=SCOPES)
    delegated = creds.with_subject(subject_email)
    service = build('script', 'v1', credentials=delegated)
    return service

def call_apps_script_function(script_id:str, function_name:str, parameters:list):
    """
    Llama a la function 'function_name' en el Apps Script con 'script_id',
    pasándole un array 'parameters'.
    Return => result
    """
    # script_id => El ID del script
    # function_name => la función que definiste en tu Apps Script .gs
    # parameters => array de params
    try:
        service = st.session_state["apps_script_service"] # o llamas get_apps_script_service(...) en setup
        request = {
            "function": function_name,
            "parameters": parameters,
            "devMode": False
        }
        response = service.scripts().run(scriptId=script_id, body=request).execute()
        if "error" in response:
            error = response["error"]["details"][0]
            st.error(f"Error en la función de Apps Script: {error['errorMessage']}")
            return None
        else:
            return response.get("response", {}).get("result", None)
    except Exception as e:
        st.error(f"Error llamando function '{function_name}': {e}")
        return None

def example_create_gform(script_id:str, form_title:str):
    """
    Ejemplo de función para invocar una function 'createGForm' en tu Apps Script,
    que cree un Form con 'form_title'.
    """
    result = call_apps_script_function(script_id, "createGForm", [form_title])
    if result:
        st.write("Form creado con ID:", result.get("formId"))
    else:
        st.error("No se pudo crear GForm")

# Pros y Contras de este approach:
# - PRO: Reutilizas la potencia de Apps Script (manejar forms, triggers, etc.)
# - CON: Requieres un script_id y la API habilitada. 
#         La domain-wide delegation es compleja. 
# - Si tu script es un "webapp" => otra approach => mandar requests a la URL con fetch.
#
# Sugerencia:
# - Manejar un dict de "script_id" => "myASscriptID" en st.secrets
# - Llamar call_apps_script_function(...) con la function name. 
#