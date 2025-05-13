import pandas as pd
import json
import datetime
from typing import List, Dict, Any
def serialize_request_for_sheets(request: dict) -> dict:
    """
    Takes the internal request dictionary (with lists/dicts/datetimes)
    and returns a new dictionary with all fields converted to string-friendly format.
    - lists -> 'val1,val2,...'
    - dict -> json.dumps(...)
    - datetimes -> 'YYYY-MM-DD'
    - times -> 'HH:MM'
    """
    out = {}
    for k, v in request.items():
        if isinstance(v, list):
            # convert to "val1,val2"
            out[k] = ",".join(map(str,v))
            #print(f"serialize_request_for_sheets: {k} => list")
        elif isinstance(v, dict):
            # convert to JSON
            out[k] = json.dumps(v, default=str)
            #print(f"serialize_request_for_sheets: {k} => dict")
        elif isinstance(v, datetime.datetime):
            # convert datetime to iso-like string with YYYY-MM-DD HH:MM:SS
            out[k] = v.isoformat()[:19]
        elif isinstance(v, (datetime.date)):
            # convert date to iso-like string
            out[k] = v.isoformat()[:10]  # "YYYY-MM-DD"
            #print(f"serialize_request_for_sheets: {k} => datetime.date")
        elif isinstance(v, datetime.time):
            out[k] = v.isoformat()[:5]   # "HH:MM"
            #print(f"serialize_request_for_sheets: {k} => datetime.time")
        elif isinstance(v, int):
            out[k] = int(v)
            #print(f"serialize_request_for_sheets: {k} => int")
        
        elif isinstance(v, float):
            out[k] = float(v)
            #print(f"serialize_request_for_sheets: {k} => float")
        else:
            # fallback => string
            
            out[k] = str(v) if v is not None else ""
            #if out[k] == "":
            #    print(f"serialize_request_for_sheets: {k} => None")
            #else:
            #    print(f"serialize_request_for_sheets: {k} => str")
            
        #print(f"serialize_request_for_sheets: {k} {v} => {out[k]}")
        #print(f"{k}: {type(v)}=> {type(out[k])}")
    return out

def deserialize_request_from_sheets(row: dict) -> dict:
    """
    row => dict con strings. Reconstruye list, dict, date, etc.
    We guess field by field. (Requires some knowledge about which fields are lists, which are dict.)
    """
    out = {}
    # supongamos que "nivel_educativo" es un string "Media,Básica"
    # "asignatura" es un JSON
    # "fecha_inicio" es "YYYY-MM-DD"
    # ...
    # We'll do a manual approach or a definition of schema.

    for k, v in row.items():
        # listas
        if k in ["nivel_educativo","dias_seleccionados","dias_de_la_semana",]:
            out[k] = v.split(",") if v else []
        elif k in ["asignatura","curso","horarios_seleccionados",]:
            # assume JSON
            try:
                out[k] = json.loads(v)
            except:
                out[k] = {}
        elif k in ["fecha_inicio","fecha_fin"]:
            # parse date from 'YYYY-MM-DD'
            try:
                out[k] = datetime.datetime.strptime(v, "%Y-%m-%d").date()
            except:
                out[k] = None
        elif k in ["created_at"]:
            # parse time from 'YYYY-MM-DD HH:MM:SS'
            try:
                out[k] = datetime.datetime.strptime(v, "%Y-%m-%d %H:%M:%S")
            except:
                out[k] = None
            
        else:
            # fallback
            out[k] = v
    return out

def format_candidates_for_panel_display(df_candidates: pd.DataFrame) -> pd.DataFrame:
    """
    "Format the candidates for display in the panel."
    """

    # extraer los valores de la lista y hacer un join con comas para los siguientes campos:
    fields_to_format_list = ["subjects", "ed_licence_level", "available_days"]
    for field in fields_to_format_list:
        df_candidates[field+"_f"] = df_candidates[field].apply(lambda x: ", ".join(x) if isinstance(x, list) else x)
    # para genero, vamos a cambiar "Masculino" por "M" y "Femenino" por "F"
    df_candidates["genero_f"] = df_candidates["genero"].apply(lambda x: "M" if x == "Masculino" else "F" if x == "Femenino" else x)
    # para anios_egreso y max_hours_per_week, vamos a hacer que sea int si es un float o int que no sea nan
    fields_to_format_int = ["anios_egreso", "max_hours_per_week"]
    for field in fields_to_format_int:
        df_candidates[field+"_f"] = df_candidates[field].apply(lambda x: int(x) if isinstance(x, (float, int)) and not pd.isna(x) else x)
    
    return df_candidates

def format_request_for_panel_display(df_request: pd.DataFrame) -> pd.DataFrame:
    """"
    "Format the request for display in the panel."
    """
    # Para nivel educativo y dias, extraer los valores de los diccionarios y hacer un join con comas
    df_request["nivel_educativo_f"] = df_request["nivel_educativo"].apply(lambda x: ", ".join(x) if isinstance(x, list) else x)
    df_request["dias_seleccionados_f"] = df_request["dias_seleccionados"].apply(lambda x: ", ".join(x) if isinstance(x, list) else x)
    # para asignaturas, es un diccionario cuya clave es el nivel educativo y el valor es una lista de asignaturas.
    # necesito extraer las asignaturas de los distintos niveles educativos en una lista, convertirla a un set para eliminar duplicados, y luego a un string con comas
    df_request["asignatura_f"] = df_request["asignatura"].apply(lambda x: ", ".join(set([item for sublist in x.values() for item in sublist])) if isinstance(x, dict) else x)
    
    # para comentarios, si es nan, poner ""
    df_request["comentarios_f"] = df_request["comentarios"].apply(lambda x: x if isinstance(x, str) else "")
    # retornar el dataframe
    return df_request 
def read_all_dataframes(sheet_name_list: list, connection) -> dict:
    """
    Lee múltiples hojas de Google Sheets y retorna un diccionario
    {sheet_name: DataFrame} usando la conexión provista.
    """
    dataframes = {}
    for sheet_name in sheet_name_list:
        df = connection.read(worksheet=sheet_name,max_entries=1)
        dataframes[sheet_name] = df
    return dataframes

def format_request_data_for_email(request: dict) -> dict:
    """
    Formatea los datos de la solicitud para el correo electrónico.
    Convierte listas y diccionarios a cadenas de texto.
    """
    # Convertir listas a cadenas de texto
    for key, value in request.items():
        if isinstance(value, list):
            request[key] = ", ".join(value)
        # diccionarios que tienen como keys strings y como valores listas
        # extraemos los valores de las listas, hacemos set y luego list para eliminar duplicados y luego unimos con comas
        elif isinstance(value, dict):
            # Convertir diccionario a cadena de texto
            # extraer los valores de las listas, hacer set y luego list para eliminar duplicados y luego unimos con comas
            request[key] = ", ".join(set([item for sublist in value.values() for item in sublist]))     
        elif isinstance(value, datetime.datetime):
            # Convertir datetime a cadena de texto
            request[key] = value.strftime("%Y-%m-%d %H:%M:%S")
        elif isinstance(value, datetime.date):
            # Convertir fecha a cadena de texto
            request[key] = value.strftime("%Y-%m-%d")
    return request
    
