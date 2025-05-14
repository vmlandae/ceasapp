# --- Standard imports ---
import streamlit as st
import copy
from ceas import schools_manager

from ceas.config import INTERIM_DATA_DIR, TEMPLATES_DIR
import pandas as pd
import numpy as np
import tempfile, requests, pathlib, time, mimetypes
import re
# --- Extra imports for email dialog ---
from jinja2 import Environment, FileSystemLoader, select_autoescape
# --- Required ceas imports ---
from ceas.utils import (
    create_columns_panel,
    on_enviar_correo,
    filter_applicants_by_request,
    cleanup_applicants,
    render_cascade_filters,
    build_selector_definitions,
    render_selectors,
    filter_df_by_filters,
    fetch_drive_pdf,
    append_sent_cvs,
    load_sent_cvs_df,
)
# --- Ensure these imports for cascade filters and request formatting ---
from ceas.serialize_data import deserialize_request_from_sheets, format_request_for_panel_display,format_candidates_for_panel_display, format_request_data_for_email
from ceas.utils import render_cascade_filters, build_selector_definitions, filter_df_by_filters
# --- Extra imports for email dialog ---
from jinja2 import Environment, FileSystemLoader, select_autoescape
if "cv_cache" not in st.session_state:
    st.session_state["cv_cache"] = {}  # url -> bytes

if "sent_cvs" not in st.session_state:
    # cargar desde GSheets
    df_log = load_sent_cvs_df()
    st.session_state["sent_cvs"] = {
        rid: set(grp["email"]) for rid, grp in df_log.groupby("replacement_id")
    }
def drive_to_download(url: str) -> str:
    """
    Convierte diferentes formatos de Google Drive a link de descarga directa.
    """
    m = re.search(r"/d/([A-Za-zA-Z0-9_-]+)/", url)          # .../d/<ID>/
    if not m:
        m = re.search(r"open\?id=([A-Za-zA-Z0-9_-]+)", url) # open?id=<ID>
    if m:
        file_id = m.group(1)
        return f"https://drive.google.com/uc?export=download&id={file_id}"
    return url

st.title("Panel de Selección de Candidatos")

def checkbox_render_fn(row, disabled=True, widget_key=None, *_, **__):
    sent = st.session_state.get("sent_set_current", set())
    already = row["email"] in sent
    st.checkbox(
        "Enviado" if already else "Seleccionar",
        key=widget_key,
        value=False,
        label_visibility="collapsed",
        disabled=disabled or already,
    )
def cv_link_render_fn(row,disabled=True,widget_key=None,*args, **kwargs):
    """
    Función para renderizar el widget st.checkbox en la columna "Checkbox" de la tabla.
    """
    #st.markdown(f"[{row['cv_link']}]({row['cv_link']})")
    st.markdown(f"[CV]({row['cv_link']})", unsafe_allow_html=True)

# --- Helper to collect seleccionados ---
def get_selected_rows(df: pd.DataFrame, key_prefix: str = "panel_seleccion_candidato") -> pd.DataFrame:
    """
    Devuelve las filas del DataFrame cuyo checkbox (columna 0) está marcado.
    create_columns_panel usa keys f"{key_prefix}_0_<row_index>" para la primera columna.
    """
    idxs = []
    for i in df.index:
        if st.session_state.get(f"{key_prefix}_0_{i}", False):
            idxs.append(i)
    return df.loc[idxs]

# --- Dialog para enviar el correo ---
def show_email_dialog(selected_df: pd.DataFrame, request_data: dict):
    """Abre un diálogo con plantilla editable y control de destinatarios."""
    rd = format_request_data_for_email(request_data)
    #rd = request_data
    @st.dialog("Enviar correo adjuntando candidatos", width="large")
    def _dlg():
        request_data =  rd
        # debuging
        #st.write("selected_df", selected_df)
        #st.write(rd)
        st.markdown(f"#### {request_data['school_name']}")
        st.dataframe(st.session_state["dfs"]["users"].query("school_name==@request_data['school_name']")[['email','name','cargo']],hide_index=True)
        # --- Destinatarios ---
        col1, col2, col3 = st.columns(3)
        with col1:
            to_val = st.text_input("Para", value=request_data.get("created_by", ""), key="dlg_to")
        with col2:
            cc_val = st.text_input("CC", value="personas@ceas.cl", key="dlg_cc")
        with col3:
            bcc_val = st.text_input("CCO", value="", key="dlg_bcc")

        # --- Asunto ---
         
        subj_default = f"CV disponibles - Reemplazo docente - Solicitud {int(request_data['replacement_id'])} -{request_data['asignatura']} - {request_data['school_name']}"
        subject = st.text_input("Asunto", value=subj_default, key="dlg_subj")

        # --- Cuerpo (template Jinja2) ---
        env = Environment(
            loader=FileSystemLoader(str(TEMPLATES_DIR)),
            autoescape=select_autoescape()
        )
        cand_list = [
            f"- {r['first_name']} {r['last_name']} ({r['email']})"
            for _, r in selected_df.iterrows()
        ]
        dias = request_data.get("dias_seleccionados", [])
        try:
            template = env.get_template("email_candidates_template.html")
            rendered = template.render(
                institucion=request_data["school_name"],
                solicitante=request_data["created_by"],
                asignatura=request_data["asignatura"],
                nivel_educativo=request_data["nivel_educativo"],
                lista_candidatos="\n".join(cand_list),
            )
        except Exception:
            rendered = (
                f"Estimado/a,\n\nAdjunto lista de candidatos:\n" +
                "\n".join(cand_list)
            )
        body = st.text_area("Cuerpo del correo", value=rendered, height=350)

        st.markdown("#### CVs de candidatos")
        temp_dir = pathlib.Path(tempfile.mkdtemp(prefix="cvs_"))
        attachments = []
        cv_cols = st.columns([0.5, 0.5])
        for idx, r in selected_df.iterrows():
            if not r.get("cv_link"):
                continue
            name = f"{r['first_name']} {r['last_name']}"
            # ----------------------------------------------------------
            # Descargar archivo (Drive API primero; si falla pública)
            # ----------------------------------------------------------
            cache_key = r["cv_link"]
            if cache_key in st.session_state["cv_cache"]:
                file_bytes = st.session_state["cv_cache"][cache_key]
            else:
                file_bytes = fetch_drive_pdf(r["cv_link"], use_sa=True)
                if file_bytes is None:
                    dl_url = drive_to_download(r["cv_link"])
                    try:
                        resp = requests.get(dl_url, timeout=20)
                        resp.raise_for_status()
                        file_bytes = resp.content
                    except Exception as e:
                        st.warning(f"No se pudo descargar CV de {name}: {e}")
                        continue
                st.session_state["cv_cache"][cache_key] = file_bytes

            # ---- Detectar extensión por magic-bytes ----------
            if file_bytes[:4] == b"%PDF":
                ext = ".pdf"
            elif file_bytes[:2] == b"PK":
                ext = ".docx"
            elif file_bytes[:4] == b"\xd0\xcf\x11\xe0":
                ext = ".doc"
            else:
                ext = ".bin"
            safe_fname = f"{name.replace(' ', '_')}_{idx}{ext}"

            cv_path = pathlib.Path(temp_dir) / safe_fname
            cv_path.write_bytes(file_bytes)

            with cv_cols[0]:
                attach_flag = st.checkbox(
                    f"Adjuntar {name}", value=True, key=f"chk_attach_{idx}"
                )
            with cv_cols[1]:
                st.download_button(
                    label=f"Descargar archivo",
                    data=file_bytes,
                    file_name=safe_fname,
                    mime="application/octet-stream",
                    key=f"btn_dl_{idx}"
                )

            if attach_flag:
                attachments.append({
                    "filename": safe_fname,
                    "data": file_bytes,
                    "mime_type": "application/octet-stream"
                })

        # Previsualización deshabilitada por ahora

        # --- Opción para adjuntar archivos adicionales ---
        st.file_uploader(
            "Adjuntar archivos adicionales",
            accept_multiple_files=True,
            key="dlg_attachments"
        )

        # --- Botones ---
        col_ok, col_cancel = st.columns(2)
        with col_ok:
            if st.button("Enviar", key="dlg_send"):
                # Se delega a send_candidates_email para enviar
                try:
                    from ceas.reemplazos.gmail import send_candidates_email
                    status = send_candidates_email(
                        institucion=request_data["school_name"],
                        asignatura=request_data["asignatura"],
                        nivel_educativo=request_data["nivel_educativo"],
                        dias=dias,
                        solicitante=request_data["created_by"],
                        lista_candidatos="\n".join(cand_list),
                        to_email=to_val,
                        cc=cc_val if cc_val else None,
                        bcc=bcc_val if bcc_val else None,
                        subject=subject,
                        template_path=None,
                        custom_html=body,
                        attachments=attachments,
                    )
                    if status:
                        st.success("Correo enviado correctamente.")
                        # Registrar enviados
                        req_id = request_data["replacement_id"]
                        sent = st.session_state["sent_cvs"].get(req_id, set())
                        sent.update(selected_df["email"].tolist())
                        st.session_state["sent_cvs"][req_id] = sent
                        append_sent_cvs(req_id, list(selected_df["email"]))
                        time.sleep(2)
                        st.rerun()
                    else:
                        st.error("No se pudo enviar el correo.")
                except Exception as e:
                    st.error(f"Error al enviar: {e}")
        with col_cancel:
            if st.button("Cancelar", key="dlg_cancel"):
                st.info("Cancelado.")
    _dlg()
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



if "request" not in st.session_state:
    st.session_state["request"] = None
def panel(solicitud):

    # Cargar datos

    # 1. Cargar datos de la solicitud:
    #    Puede ser mediante un pickle o mediante una lectura de la base de datos.
    data = load_request(load_from="db", solicitud=solicitud)
    st.session_state["request"] = data
    #print(data)

    # 2. Cargar datos de los candidatos
    df_applicants = st.session_state['dfs']['cleaned_applicants']
    # --- Selector de modo: automático (por solicitud) o manual ---
    manual_mode = st.toggle("Selección manual de candidatos", value=False, key="sel_manual_toggle")

    if manual_mode:
        # ===== MODO MANUAL =====
        st.info("Filtra candidatos manualmente.")
        # Opciones dinámicas
        subj_options = sorted({s for sublist in df_applicants["subjects"] for s in sublist})
        ed_options   = sorted({e for edlist in df_applicants["ed_licence_level"] for e in edlist})
        uni_options  = sorted(df_applicants["university"].dropna().unique())
        gen_options  = ["Indiferente"] + sorted(df_applicants["genero"].dropna().unique())
        com_options  = sorted(df_applicants["comuna_residencia"].dropna().unique())

        c1,c2,c3 = st.columns(3)
        with c1:
            sel_subjects = st.multiselect("Asignaturas", subj_options, key="manual_subj")
            sel_ed       = st.multiselect("Nivel educativo", ed_options, key="manual_ed")
        with c2:
            sel_unis     = st.multiselect("Universidad", uni_options, key="manual_uni")
            sel_comunas  = st.multiselect("Comuna residencia", com_options, key="manual_comuna")
        with c3:
            sel_gen      = st.selectbox("Género", gen_options, key="manual_gen")

        # Filtrado
        df_manual = df_applicants.copy()
        if sel_subjects:
            df_manual = df_manual[
                df_manual["subjects"].apply(lambda ss: any(s in ss for s in sel_subjects))
            ]
        if sel_ed:
            df_manual = df_manual[
                df_manual["ed_licence_level"].apply(lambda ee: any(e in ee for e in sel_ed))
            ]
        if sel_unis:
            df_manual = df_manual[df_manual["university"].isin(sel_unis)]
        if sel_comunas:
            df_manual = df_manual[df_manual["comuna_residencia"].isin(sel_comunas)]
        if sel_gen != "Indiferente":
            df_manual = df_manual[df_manual["genero"] == sel_gen]

        # --- Métrica: número de candidatos filtrados ---
        st.metric("Candidatos encontrados", len(df_manual))

        


        st.dataframe(df_manual)

        st.divider()

        # Reutilizar columnas
        available_columns = [
            {"header": "", "type": "custom", "render_fn": checkbox_render_fn, "width": 0.3},
            {"header": "Email", "field": "email", "type": "text", "width": 2},
            {"header": "Nombre", "field": "full_name", "type": "text", "width": 1},
            {"header": "Teléfono", "field": "phone", "type": "text", "width": 1},
            {"header": "Comuna", "field": "comuna_residencia", "type": "text", "width": 1},
            {"header": "Años de egreso", "field": "anios_egreso", "type": "text", "width": 1},
            {"header": "Género", "field": "genero", "type": "text", "width": 1},
            {"header": "Nivel educativo", "field": "ed_licence_level", "type": "text", "width": 1},
            {"header": "Asignaturas", "field": "subjects", "type": "text", "width": 1},
            {"header": "Universidad", "field": "university", "type": "text", "width": 1},
            {"header": "CV", "type": "custom", "render_fn": cv_link_render_fn, "width": 1},
        ]
        col_headers = [c["header"] for c in available_columns[1:]]
        selected_cols = st.multiselect("Columnas a mostrar", col_headers, default=col_headers, key="manual_cols")
        columns_info = [available_columns[0]] + [c for c in available_columns[1:] if c["header"] in selected_cols]

        create_columns_panel(
            df_manual,
            columns_info,
            key_prefix="manual_panel",
            enable_sort_pills=True
        )

        # Botón de correo
        selected_df = get_selected_rows(df_manual, key_prefix="manual_panel")
        if not selected_df.empty:
            if st.button("Enviar CVs", key="btn_send_email_manual"):
                # request_data vacío -> usar dict con valores mínimos
                pseudo_req = {"created_by":"", "school_name":"", "replacement_id":"manual",
                              "asignatura": sel_subjects, "nivel_educativo": sel_ed,
                              "dias_seleccionados": []}
                show_email_dialog(selected_df, pseudo_req)
        st.stop()
    else:
        # escribimos numero de solicitud : replacement_id
        st.subheader(f"Solicitud: {int(data['replacement_id'])}")
        # Botón para cerrar la solicitud y volver a selector
        if st.button("Cerrar solicitud", key="btn_close_request"):
            # Limpiar request_id del session_state y recargar la página
            st.session_state["request_id"] = None
            st.rerun()
        # solicitante, institución, fecha de creación de solicitud
        c1, c3, c4 = st.columns([2,1,2])
        #c3,
        
        with c1:
            st.write(f"Solicitante: {data['created_by']}")
            st.write(f"Institución: {data['school_name']}")
            st.write(f"Fecha de creación: {data['created_at']}")
            st.write(f"Fecha de procesamiento: {data['processed_at']}")
            st.write(f"Origen: {data['created_with']}")
            st.write(f"Fecha de inicio: {data['fecha_inicio']}")
            st.write(f"Fecha de fin: {data['fecha_fin']}")
        # Si la solicitud fue creada por un usuario de la oficina central, mostrar el nombre de la oficina
        # with c2:
            
        #     st.write(f"Estado: {data['status']}")
        with c3:
            # Nivel y asignatura(s), imprimir key y values para cada key
            st.write("Nivel educativo y asignaturas:")
            for nivel, asignaturas in data['asignatura'].items():
                st.write(f"{nivel}: {", ".join(asignaturas)}")
            # días de la semana seleccionados
            st.write("Días seleccionados:")
            # imprimir días de la semana en orden (Lunes, Martes, Miércoles, Jueves, Viernes)
            dias_de_la_semana = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"]
            dias_seleccionados = [d for d in dias_de_la_semana if d in data['dias_de_la_semana']]
            st.write(", ".join(dias_seleccionados))

        # Si la solicitud fue creada por un usuario de la oficina central, mostrar el nombre de la oficina
        with c4:
            comentario = st.text_area("Comentarios", value="", disabled=False )
            if st.button("Guardar comentario", key="guardar_comentario"):
                # Guardar comentario en la base de datos
                st.session_state['dfs']['requests'].loc[st.session_state['dfs']['requests']['replacement_id'] == int(solicitud), 'comentarios'] = comentario
                st.success("Comentario guardado.")
        st.divider()

        # Parámetros de búsqueda (basados en la solicitud), editables opcionalmente
        st.subheader("Parámetros de búsqueda")
        edit_params = st.checkbox("Editar parámetros de búsqueda", value=False, key="edit_params")
        # Obtener valores iniciales desde la solicitud
        req = st.session_state["request"]
        # Deshabilitar campos si no estamos en modo edición
        disabled = not edit_params
        # Botón para restaurar solicitud inicial si no estamos editando parámetros
        if not edit_params:
            if st.button("Restaurar solicitud inicial", key="restore_initial"):
                # Reset filters to original request values
                req = st.session_state["request"]
                st.session_state["genero_filtro"] = req.get("genero", "Indiferente")
                st.session_state["anios_egreso_filtro"] = int(req.get("anios_egreso", 0))
                st.session_state["disponibilidad_filtro"] = req.get("disponibilidad", "Completa")
                st.session_state["asignaturas_filtro"] = req.get("asignatura", [])
                st.session_state["nivel_educativo_filtro"] = req.get("nivel_educativo", [])
                st.rerun()
        # Layout de filtros (añadimos columna para días disponibles)
        c1, c2, c3, c4, c5, c6 = st.columns(6)
        with c1:
            # asignaturas, nivel educativo, dias_seleccionados
            asignaturas_por_nivel = req.get("asignatura", {})
            asignaturas = []
            niveles_educativos = req.get("nivel_educativo", [])
            for nivel, asignaturas_nivel in asignaturas_por_nivel.items():
                if nivel in req.get("nivel_educativo", []):
                    asignaturas.extend(asignaturas_nivel)
            # Eliminar duplicados
            asignaturas = list(set(asignaturas))
            # multiselect para asignaturas
            subject = st.multiselect(
                "Asignaturas",
                options=asignaturas,
                default=asignaturas,
                key="asignaturas_filtro",
                disabled=disabled,
                label_visibility="visible",
            )
        with c2:
            #nivel educativo
            nivel = st.multiselect(
                "Nivel educativo",
                options=niveles_educativos,
                default=niveles_educativos,
                key="nivel_filtro",
                disabled=disabled,
                label_visibility="visible",
            )

        with c3:
            genero = st.radio(
                "Género",
                options=["Indiferente", "Femenino", "Masculino"],
                index=["Indiferente", "Femenino", "Masculino"].index(req.get("genero", "Indiferente")),
                key="genero_filtro",
                disabled=disabled,
                label_visibility="visible"
            )
        with c4:
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
        with c5:
            disponibilidad = st.radio(
                "Disponibilidad",
                options=["Completa", "Parcial"],
                index=["Completa", "Parcial"].index(req.get("disponibilidad", "Completa")),
                key="disponibilidad_filtro",
                disabled=disabled,
                label_visibility="visible"
            )
        with c6:
            # Días disponibles (lista original en request['dias_de_la_semana'])
            dias_disp_options = req.get("dias_de_la_semana", []) 
            dias_disp_options = list(set(dias_disp_options))
            dias_disp_options.sort(key=lambda x: ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"].index(x))    
            dias_seleccionados = st.multiselect(
                "Días disp.",
                options=dias_disp_options,
                default=dias_disp_options,
                key="dias_filtro",
                disabled=disabled,
                label_visibility="visible",
            )
        st.divider()

        # Aplicar filtros al DataFrame de candidatos usando los parámetros (clone de solicitud)
        cleaned_applicants = st.session_state['dfs']['cleaned_applicants']
        # Construir request modificado
        mod_req = copy.deepcopy(req)
        mod_req["genero"] = genero
        mod_req["anios_egreso"] = anios_egreso
        mod_req["disponibilidad"] = disponibilidad
        mod_req["asignatura"] = subject
        mod_req["nivel_educativo"] = nivel
        mod_req["dias_de_la_semana"] = dias_seleccionados
        df_filtered_applicants = filter_applicants_by_request(mod_req, cleaned_applicants)
        # --- Métrica: número de candidatos filtrados ---
        st.metric("Candidatos encontrados", len(df_filtered_applicants))
        df_filtered_applicants_formatted = format_candidates_for_panel_display(df_filtered_applicants)

        # --- Marcar candidatos ya enviados ---
        sent_set_req = st.session_state["sent_cvs"].get(req["replacement_id"], set())
        st.session_state["sent_set_current"] = sent_set_req         # para los checkboxes
        df_filtered_applicants_formatted["Enviado"] = df_filtered_applicants_formatted[
            "email"
        ].apply(lambda x: "Sí" if x in sent_set_req else "")

        # --- Tabla de candidatos ---
        # Selector de columnas a mostrar
        available_columns = [
            {"header": "", "type": "custom", "render_fn": checkbox_render_fn, "width": 0.3},
            {"header": "Enviado", "field": "Enviado", "type": "text", "width": 0.6},
            {"header": "Email", "field": "email", "type": "text", "width": 2},
            {"header": "Nombre", "field": "full_name", "type": "text", "width": 1},

            {"header": "Teléfono", "field": "phone", "type": "text", "width": 1},
            {"header": "Comuna", "field": "comuna_residencia", "type": "text", "width": 1},
            {"header": "Años eg.", "field": "anios_egreso_f", "type": "text", "width": 0.5},
            {"header": "Género", "field": "genero_f", "type": "text", "width": 0.75},
            {"header": "Niveles", "field": "ed_licence_level_f", "type": "text", "width": 1},
            {"header": "Asignaturas", "field": "subjects_f", "type": "text", "width": 1},
            {"header": "Universidad", "field": "university", "type": "text", "width": 1},
            {"header": "Días de la semana", "field": "available_days_f", "type": "text", "width": 1},
            {"header": "Horas", "field": "max_hours_per_week_f", "type": "text", "width": 1},
            
            
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
        c1,c2 = st.columns([0.9,0.1])
        with c1:
            create_columns_panel(
                df_filtered_applicants_formatted,
                columns_info,
                key_prefix="panel_seleccion_candidato",
                enable_sort_pills=True
            )

        with c2:
                # --- Botón para enviar correo si hay selección ---
            selected_df = get_selected_rows(df_filtered_applicants)
            if not selected_df.empty:
                if st.button("Enviar CVs", key="btn_send_email"):
                    show_email_dialog(selected_df, req)

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

    elif "request_id" not in st.session_state or st.session_state["request_id"] is None:
        st.markdown("## Selecciona una solicitud")
        # --- Cargar y deserializar todas las solicitudes ---
        raw_req = st.session_state['dfs']['requests'].copy()
        if raw_req.empty:
            st.info("No hay solicitudes disponibles.")
            st.stop()

        df_requests = pd.DataFrame([deserialize_request_from_sheets(r)
                                    for r in raw_req.to_dict(orient="records")])
        df_requests = format_request_for_panel_display(df_requests)

        # --- Filtros en cascada (simples) ---
        selectors = {
            "created_with": {"label": "Origen", "widget": "selectbox", "default": None},
            "school_name": {"label": "Institución", "widget": "multiselect", "default": []},
            "created_by": {"label": "Creado por", "widget": "multiselect", "default": []},
            "nivel_educativo_f": {"label": "Nivel Educativo", "widget": "multiselect", "default": []},
            "asignatura_f": {"label": "Asignatura", "widget": "multiselect", "default": []},
            "created_at": {"label": "Fecha de Creación", "widget": "date_input", "default": None},
        }

        df_filtered = render_cascade_filters(
            df_requests,
            selectors,
            key_prefix="selcand_cascade",
            n_cols=6,
            widths=[0.6, 1, 1, 1, 1, 0.75],
            label_visibility="visible"
        )

        st.markdown("---")
        if df_filtered.empty:
            st.warning("No hay solicitudes con esos filtros.")
            st.stop()
        
        # Mostrar tabla simplificada
        simple_cols = ["replacement_id", "created_at", "school_name", "created_by","nivel_educativo_f","asignatura_f", "fecha_inicio", "fecha_fin"]
        # creamos columnas iguales a las de simple_cols pero con labels en español
        simple_cols_labels = {
            "replacement_id": "ID",
            "created_at": "Fecha de Creación",
            "school_name": "Institución",
            "created_by": "Creado por",
            "nivel_educativo_f": "Nivel Educativo",
            "asignatura_f": "Asignatura",
            "fecha_inicio": "Fecha Inicio",
            "fecha_fin": "Fecha Fin"
        }
        # copiamos las columnas en df_filtered con los nuevos labels
        df_simple_cols = df_filtered[simple_cols].copy()

        df_simple_cols = df_simple_cols.rename(columns=simple_cols_labels)
        # Selector de solicitud resultante: al seleccionar una fila del dataframe df_simple_cols,
        #  que se extraiga el id de la solicitud y que aparezca el botón de cargar solicitud

        # --- Renderizar tabla con columnas seleccionadas ---

        # Seleccionar filas del dataframe df_filtered para mostrarlas en el dataframe df_simple_cols
        # y permitir la selección de una fila

        df_sc = st.dataframe(df_simple_cols, hide_index=True,
                              use_container_width=True,
                                selection_mode="single-row",
                                on_select="rerun",
                                  key="df_simple_cols")
        
        solicitud_id = st.session_state.get("df_simple_cols", None)
        try:
            solicitud_id = solicitud_id["selection"]["rows"][0]
        except Exception as e:
            pass
        id_solicitud = None
        if isinstance(solicitud_id, int):
            id_solicitud = df_simple_cols.iloc[solicitud_id]["ID"]

        

            col_ok, col_reset = st.columns([0.2, 0.2])
            with col_ok:
                if st.button("Cargar solicitud", key="btn_load_req"):
                    st.session_state["request_id"] = id_solicitud
                    st.rerun()
            with col_reset:
                if st.button("Limpiar filtros", key="btn_clear_sel_req"):
                    for f in selectors:
                        st.session_state.pop(f"selcand_cascade_{f}", None)
                    st.session_state.pop("df_simple_cols", None)
                    st.rerun()

        st.stop()
    else:
        st.error("No hay solicitudes disponibles.")
        st.stop()


if __name__ =="__page__":
    run()