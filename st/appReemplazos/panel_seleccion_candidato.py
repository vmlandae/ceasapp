import streamlit as st
import copy
from ceas import schools_manager
from ceas.config import INTERIM_DATA_DIR
from ceas.utils import (
    create_columns_panel,
    on_enviar_correo,
    filter_applicants_by_request,
    cleanup_applicants,
    render_cascade_filters,
    build_selector_definitions,
    render_selectors,
    filter_df_by_filters,
)
import pandas as pd
from ceas.serialize_data import deserialize_request_from_sheets
st.title("Panel de Selección de Candidatos")

def checkbox_render_fn(row,disabled=True,widget_key=None,*args, **kwargs):
    """
    Función para renderizar el widget st.checkbox en la columna "Checkbox" de la tabla.
    """
    st.checkbox(label="Seleccionar",key = widget_key,value = False,label_visibility="collapsed",disabled=disabled)
def cv_link_render_fn(row,disabled=True,widget_key=None,*args, **kwargs):
    """
    Función para renderizar el widget st.checkbox en la columna "Checkbox" de la tabla.
    """
    #st.markdown(f"[{row['cv_link']}]({row['cv_link']})")
    st.markdown(f"[CV]({row['cv_link']})", unsafe_allow_html=True)    

def load_request(load_from:str, solicitud:int) -> pd.DataFrame:
    """
    Cargar la solicitud desde un pickle o desde la base de datos.
    """
    if load_from == "pickle":
        try:
            data = pd.read_pickle(INTERIM_DATA_DIR/"requests"/f"request_{int(solicitud)}.pickle")
        except Exception as e:
            st.error(f"No se pudo cargar la solicitud desde el pickle: {e}")
            print(f"No se pudo cargar la solicitud desde el pickle por el siguiente error: {e}")
            print("Intentando cargar desde la base de datos...")
            load_from = "db"
    if load_from == "db":
        data = st.session_state['dfs']['requests'].loc[st.session_state['dfs']['requests']['replacement_id'] == int(solicitud)].copy()
        data = data.to_dict(orient="records")[0]
        # deserializar
        data = deserialize_request_from_sheets(data)
    else:
        st.error("No se pudo cargar la solicitud desde la base de datos.")
        print("No se pudo cargar la solicitud desde la base de datos.")
        return None

    return data



if "data" not in st.session_state:
    st.session_state["data"] = None
def panel(solicitud):

    
    # Cargar datos

    # 1. Cargar datos de la solicitud:
    #    Puede ser mediante un pickle o mediante una lectura de la base de datos.
    data = load_request(load_from="db", solicitud=solicitud)
    
    st.session_state["data"] = data

    
    
    
    # escribimos numero de solicitud : replacement_id
    st.subheader(f"Solicitud: {int(data['replacement_id'])}")
    # solicitante, institución, fecha de creación de solicitud
    c1, c2, c3 = st.columns(3)
    with c1:
        st.write(f"Solicitante: {data['created_by']}")
        st.write(f"Institución: {data['school_name']}")
    # Si la solicitud fue creada por un usuario de la oficina central, mostrar el nombre de la oficina
    with c2:
        st.write(f"Origen: {data['created_with']}")
        st.write(f"Fecha de creación: {data['created_at']}")
    with c3:
        st.write(f"Fecha de inicio: {data['fecha_inicio']}")
        st.write(f"Fecha de fin: {data['fecha_fin']}")
        
    
    
    # Mostrar los datos de la solicitud:
    # asignaturas, nivel educativo, dias_seleccionados
    for nivel, subject in data['asignatura'].items():
        if isinstance(subject, list):
            subject = ", ".join(subject)
        st.write(f"nivel educativo: {nivel}")
        st.write(f"asignaturas: {subject}")
    st.divider()

    # Parámetros de búsqueda (basados en la solicitud), editables opcionalmente
    st.subheader("Parámetros de búsqueda")
    edit_params = st.checkbox("Editar parámetros de búsqueda", value=False, key="edit_params")
    # Obtener valores iniciales desde la solicitud
    req = st.session_state["data"]
    # Deshabilitar campos si no estamos en modo edición
    disabled = not edit_params
    # Botón para restaurar solicitud inicial si no estamos editando parámetros
    if not edit_params:
        if st.button("Restaurar solicitud inicial", key="restore_initial"):
            # Reset filters to original request values
            req = st.session_state["data"]
            st.session_state["genero_filtro"] = req.get("genero", "Indiferente")
            st.session_state["anios_egreso_filtro"] = int(req.get("anios_egreso", 0))
            st.session_state["disponibilidad_filtro"] = req.get("disponibilidad", "Completa")
            st.rerun()
    # Layout de filtros
    c1, c2, c3 = st.columns(3)
    with c1:
        genero = st.radio(
            "Género",
            options=["Indiferente", "Femenino", "Masculino"],
            index=["Indiferente", "Femenino", "Masculino"].index(req.get("genero", "Indiferente")),
            key="genero_filtro",
            disabled=disabled,
            label_visibility="visible"
        )
    with c2:
        st.write("Años de egreso:", req.get("anios_egreso", 0))
        anios_egreso = st.slider(
            "Mínimo años de egreso",
            min_value=0, max_value=10,
            value=int(req.get("anios_egreso", 0)) if req.get("anios_egreso") is not None else 0,
            key="anios_egreso_filtro",
            disabled=disabled,
            label_visibility="visible",
            step=1,
        )
    with c3:
        disponibilidad = st.radio(
            "Disponibilidad",
            options=["Completa", "Parcial"],
            index=["Completa", "Parcial"].index(req.get("disponibilidad", "Completa")),
            key="disponibilidad_filtro",
            disabled=disabled,
            label_visibility="visible"
        )
    st.divider()

    # Aplicar filtros al DataFrame de candidatos usando los parámetros (clone de solicitud)
    cleaned_applicants = st.session_state['dfs']['cleaned_applicants']
    # Construir request modificado
    mod_req = copy.deepcopy(req)
    mod_req["genero"] = genero
    mod_req["anios_egreso"] = anios_egreso
    mod_req["disponibilidad"] = disponibilidad
    df_filtered_applicants = filter_applicants_by_request(mod_req, cleaned_applicants)

    # Selector de columnas a mostrar
    available_columns = [
        {"header": "", "type": "custom", "render_fn": checkbox_render_fn, "width": 0.3},
        {"header": "Email", "field": "email", "type": "text", "width": 2},
        {"header": "Nombre", "field": "first_name", "type": "text", "width": 1},
        {"header": "Apellido", "field": "last_name", "type": "text", "width": 1},
        {"header": "Teléfono", "field": "phone", "type": "text", "width": 1},
        {"header": "Comuna", "field": "comuna_residencia", "type": "text", "width": 1},
        {"header": "CV", "type": "custom", "render_fn": cv_link_render_fn, "width": 1},
    ]
    # Multiselect para elegir columnas (excluyendo la primera custom)
    col_headers = [c["header"] for c in available_columns[1:]]
    selected = st.multiselect("Selecciona columnas a mostrar", col_headers, default=col_headers)
    # Construir columns_info según selección
    columns_info = [available_columns[0]]  # checkbox siempre primero
    for col_cfg in available_columns[1:]:
        if col_cfg["header"] in selected:
            columns_info.append(col_cfg)

    create_columns_panel(
        df_filtered_applicants,
        columns_info,
        key_prefix="panel_seleccion_candidato",
        enable_sort_pills=True
    )

def run():
    # Verificar permisos
    if st.session_state.role not in ["owner", "admin", "oficina_central"]:
        st.error("No tienes acceso a esta sección.")
        st.stop()

    
    # Verificar si hay un request_id en los query params
    qp = st.query_params.to_dict()
    print(qp)
    if "request_id" in qp:
        # Si hay un request_id en los query params, cargar el panel
        print("request_id", qp["request_id"][0], "desde query params")
        st.session_state["request_id"] = int(qp["request_id"][0])
        panel(st.session_state["request_id"])
        # borramos el request_id de los query params

    
    elif "request_id" in st.session_state and st.session_state["request_id"] is not None:
        # Si hay un request_id en la session state, cargar el panel
        print("request_id", st.session_state["request_id"], "desde session state")
        panel(st.session_state["request_id"])
    # Si no hay un request_id en la session state, verificar si hay uno en los query params
    
    
    # Si no hay uno en los query params, mostrar un selectbox para seleccionar una solicitud

    
    elif "request_id" not in st.session_state or st.session_state["request_id"] is None:
        solicitud= st.selectbox("Selecciona una solicitud", st.session_state['dfs']['requests']['replacement_id'], key="request_id_select")
        if st.button("Seleccionar solicitud"):
            st.session_state["request_id"] = solicitud
            print("request_id", st.session_state["request_id"], "desde selectbox")
        if st.button("Borrar selección"):
            del st.session_state["request_id"]
            # Cargar panel
            panel(solicitud = st.session_state["request_id"])

        st.divider()
    else:
        st.error("No hay solicitudes disponibles.")
        st.stop()


if __name__ =="__page__":
    run()