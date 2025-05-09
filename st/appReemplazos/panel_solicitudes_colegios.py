import streamlit as st
import re
import time
from ceas.reemplazos.refresh import refresh_dataframes
from ceas.utils import create_columns_panel
import datetime
from ceas.utils import (
    create_columns_panel,
    create_request_dict_from_gform,
    get_preprocessed_gform_requests,
    find_unprocessed_gform_requests,
    create_replacement_request,
    render_manage_button,
)
from ceas.serialize_data import deserialize_request_from_sheets, format_request_for_panel_display
import pandas as pd
# Importar la función de filtros dinámicos
from ceas.utils import build_selector_definitions, render_selectors, filter_df_by_filters
# --- Import sorting controls ---
from ceas.utils import build_sort_definitions, apply_sort_df
# --- Import cascading filters ---
from ceas.utils import render_cascade_filters
if "request_id" not in st.session_state:
    st.session_state["request_id"] = None


def importar_nuevas_solicitudes():
    n_new = st.session_state.get("n_new_gform", 0)
    if n_new == 0:
        #st.button("Importar GForm", disabled=True, key="import_gform_disabled")
        pass

    elif n_new > 0:
        if st.button(f"Importar solicitudes de Google Forms ({n_new})", disabled=False, key="import_gform"):
            # 1) Preprocesar GForm
            df_gform = get_preprocessed_gform_requests()
            # 2) Filtrar sólo las no procesadas
            df_to_import = find_unprocessed_gform_requests(df_gform, st.session_state["dfs"]["requests"])
            added = 0
            for row in df_to_import.to_dict(orient="records"):
                req = create_request_dict_from_gform(row)
                success, new_df = create_replacement_request(req, st.session_state["dfs"]["requests"])
                if success:
                    added += 1
                    st.session_state["dfs"]["requests"] = new_df
                    st.session_state["n_new_gform"] -= 1
            if added > 0 and st.session_state["n_new_gform"] == 0:
                st.success(f"{added} solicitudes importadas.")
                time.sleep(3)
                st.rerun()
            else:
                st.info("No hay nuevas solicitudes para importar.")


def panel_solicitudes_reemplazo(rol,institucion):
    """
    Muestra un listado de solicitudes de reemplazo, de acuerdo al rol del usuario y la institución a la que pertenece.
        Se usa la función create_columns_panel para crear las columnas de la tabla.
    El listado se muestra en una tabla con ciertas columnas, y trae también algunos filtros para buscar usuarios.

    """
    # si el rol es owner, admin, oficina_central: el título es "Panel de Solicitudes de Colegios"
    # si el rol es admin_colegio, user_colegio: el título es "Mis Solicitudes de Reemplazo"

    if rol in ["owner", "admin", "oficina_central"]:
        st.title("Panel de Solicitudes de Colegios")
        
        # -- Importar nuevas solicitudes desde Google Form --
        importar_nuevas_solicitudes()
        # -- Fin de importación --
        # leer datos completos
        df_requests_serialized = st.session_state['dfs']['requests'].copy()
        # si df_requests está vacío, mostrar un mensaje de error
        if df_requests_serialized.empty:
            st.error("No hay solicitudes de reemplazo disponibles.")
            st.stop()

        df_requests = pd.DataFrame([deserialize_request_from_sheets(row) for row in df_requests_serialized.to_dict(orient="records")])
        # adecuamos algunos campos para que sean más legibles
        df_requests = format_request_for_panel_display(df_requests)
        
        # Toggle for cascading filters
        cascade_mode = st.checkbox("Filtros en cascada", value=True, key="cascade_mode")

        # Definición de selectores (parametrizable)
        selectors = {
            "created_with": {"label": "Origen", "widget": "selectbox", "default": None},
            "school_name": {"label": "Institución", "widget": "multiselect", "default": []},
            "created_by": {"label": "Creado por", "widget": "multiselect", "default": []},
            "nivel_educativo_f": {"label": "Nivel Educativo", "widget": "multiselect", "default": []},
            "created_at": {"label": "Fecha de Creación", "widget": "date_input", "default": None}
        }

        if cascade_mode:
            # Header and clear button for cascade filters
            header_col, body_col= st.columns([0.1, 0.9], vertical_alignment="top")
            with header_col:
                st.markdown("### Filtros")
            with body_col:
                # Cascading filters with custom widths matching panel layout
                df_filtered_requests = render_cascade_filters(
                    df_requests,
                    selectors,
                    key_prefix="cascade",
                    n_cols=5,
                    widths=[0.65, 1, 1, 1, 0.75],
                    label_visibility="visible"
                )

        else:
            # Standard filters
            defs = build_selector_definitions(df_requests, selectors)
            # Header for filters
            header, c1, c2 = st.columns([0.1, 0.8, 0.1], vertical_alignment="top")
            with header: st.markdown("### Filtros")
            with c1:
                filters = render_selectors(
                    defs,
                    layout={"n_cols": 5, "widths": [0.65, 1, 1, 1, 0.75,0.5]}, # hay 6 widths y 5 cols porque una columna es date_input y se convierte en dos selectores, por ahora se añade manualmente el width de date_input 
                    label_visibility="visible"
                )
            with c2:
                if st.button("Limpiar Filtros", key="clear_filters"):
                    for key in selectors:
                        st.session_state.pop(f"filter_{key}", None)
                    st.rerun()
            df_filtered_requests = filter_df_by_filters(df_requests, filters)

        # si df_filtered_requests está vacío, mostrar un mensaje de error
        if df_filtered_requests.empty:
            st.error("No hay solicitudes de reemplazo disponibles con los filtros seleccionados.")
            st.button("Limpiar Filtros", key="clear_filters_when_empty")
            st.stop()
        # crear las columnas de la tabla de acuerdo a los datos filtrados
        columns_info_dict = {
            "created_with":{"header":"Origen",  "field":"created_with",  "type":"text", "width":0.7},
            "created_by":{"header":"Creado por",  "field":"created_by",  "type":"text", "width":1.5},
            "created_at":{"header":"Fecha de creación",  "field":"created_at",  "type":"text", "width":0.75},
            "school_name":{"header":"Institución",  "field":"school_name",  "type":"text", "width":1.2},
            "nivel_educativo_f":{"header":"Nivel Educativo",  "field":"nivel_educativo_f",  "type":"text", "width":1},
            "asignatura_f":{"header": "Asignaturas",  "field": "asignatura_f" ,  "type":"text", "width":1},
            "fecha_inicio":{"header":"Fecha Inicio",  "field":"fecha_inicio",  "type":"text", "width":0.75},
            "fecha_fin":{"header":"Fecha Fin",  "field":"fecha_fin",  "type":"text", "width":0.75},
           # "dias_seleccionados_f":{"header":"Días",  "field":"dias_seleccionados_f",  "type":"text", "width":1},
        }



        columns_info = []
        # mostrar los "header" de cada columna en el panel
        
        
        column_headers = [value["header"] for key, value in columns_info_dict.items()]
            
            
        selected_columns = st.multiselect("Selecciona las columnas a mostrar", column_headers, default=column_headers)
        st.divider()

        for key, value in columns_info_dict.items():
            if value["header"] in selected_columns:
                # agregar la columna a la lista de columnas a mostrar
                columns_info.append(value)
            
        # agregar la columna de gestionar solicitud
        columns_info.append({
            "header": "Detalle",
            "type": "custom",
            "render_fn": render_manage_button,
            "width": 0.6
        })

        create_columns_panel(df_filtered_requests, columns_info,key_prefix="requests_panel",enable_sort_pills=True)


                
    elif rol in ["admin_colegio", "user_colegio"]:

        st.title("Mis Solicitudes de Reemplazo")
        # leer datos de solicitudes de reemplazo
        df_requests = st.session_state['dfs']['requests'].copy().query("school_name == @institucion")

        # si df_requests está vacío, mostrar un mensaje de error
        if df_requests.empty:
            st.error("No hay solicitudes de reemplazo disponibles.")
            st.stop()

        df_requests


def panel(rol,institucion):
    panel_solicitudes_reemplazo(rol,institucion)


def run():
    # verificar permisos y definir títulos:
    # si el rol es owner, admin, oficina_central: el título es "Panel de Solicitudes de Colegios"
    # si el rol es admin_colegio, user_colegio: el título es "Solicitudes de Reemplazo"
    
    panel(rol = st.session_state.role,institucion = st.session_state['user_info']['school_name'])


    
    


if __name__ == "__page__":
    run()

