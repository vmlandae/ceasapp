import streamlit as st
from ceas.user_management import get_all_users, change_user_role, delete_user, add_user
from ceas.schools_manager import get_all_schools, create_school, update_school, delete_school
import re
from ceas.utils import validate_new_user
import time
from ceas.reemplazos.refresh import refresh_dataframes


def manage_schools_panel():
    st.subheader("Gestión de Colegios")
    if st.session_state.role not in ["owner", "admin, oficina_central"]:
        st.warning("Solo 'owner','admin' y oficina_central pueden gestionar colegios.")
        st.stop()
    

    df_sch = st.session_state['dfs']['schools']
    if not df_sch.empty:
        for i, row in df_sch.iterrows():
            col1, col2, col3, col4, col5, col6, col7, col8 = st.columns([0.5, 1.5, 1, 1.5, 1, 1, 1, 1])
            with col1:
                if i==0:
                    st.write("ID")
                st.write(row['school_id'])
            with col2:
                if i==0:
                    st.write("Nombre")
                st.write(row['school_name'])
            with col3:
                if i==0:
                    st.write("Comuna")
                st.write(row['comuna'])
            with col4:
                if i==0:
                    st.write("Dirección")
                st.write(row['address'])
            with col5:
                if i==0:
                    st.write("Estado")
                st.write(row['status'])
            with col6:
                if i==0:
                    st.write("Tipo")
                st.write(row['type'])
            with col7:

                if st.button(f"Editar", key=f"editSch_{row['school_id']}"):
                    st.session_state["editing_school"] = int(row["school_id"])
            with col8:
                if st.button(f"Eliminar", key=f"deleteSch_{row['school_id']}"):
                    st.session_state["deleting_school"] = int(row["school_id"])
                    

        if 'editing_school' in st.session_state:
            sc_id = st.session_state['editing_school']
            row_edit = df_sch[df_sch["school_id"] == sc_id]
            if row_edit.empty:
                st.error(f"No se encontró el Colegio con school_id = {sc_id}")
            else:
                row_e = row_edit.iloc[0]
                st.subheader(f"Editar colegio {row_e['school_name']}")
                new_name = st.text_input("Nombre", value=row_e["school_name"])
                new_comuna = st.text_input("Comuna", value=row_e["comuna"])
                new_address = st.text_input("Dirección", value=row_e["address"])
                new_status = st.selectbox("Estado", ["activo", "inactivo"], index=0 if row_e["status"] == "activo" else 1)
                new_type = st.selectbox("Tipo", ["colegio", "oficina_central"], index=0 if row_e["type"] == "colegio" else 1)
                if st.button("Guardar cambios"):
                    upds = {
                        "school_name": new_name,
                        "comuna": new_comuna,
                        "address": new_address,
                        "status": new_status,
                        "type": new_type
                    }
                    ok2 = update_school(sc_id, upds)
                    if ok2:
                        st.success("Colegio actualizado.")
                        st.session_state.pop('editing_school')
                        st.session_state['refresh_list'] = ["appReemplazosSchools"]
                        refresh_dataframes()
                        # activar un widget para refrescar la lista de colegios

                        if st.button("Actualizar"):
                            st.spinner("Actualizando...")
                            time.sleep(1)


        if 'deleting_school' in st.session_state:
            sc_id = st.session_state['deleting_school']
            conf = st.checkbox("Confirmar eliminación")
            if conf:
                d_ok = delete_school(sc_id)
                if d_ok:
                    st.success("Colegio eliminado.")
                    st.session_state.pop('deleting_school')
                    st.session_state['refresh_list'] = ["appReemplazosSchools"]
                    refresh_dataframes()
                    if st.button("Actualizar"):
                        st.spinner("Actualizando...")
                        time.sleep(1)

                    



def admin_panel():
    st.title("Panel de Administración de Colegios")
    if st.session_state.get("role") not in ["owner", "admin", "oficina_central"]:
        st.error("No tienes acceso a esta sección")
        st.stop()
    manage_schools_panel()
    

        

def run():
    
    admin_panel()
    


if __name__ == "__page__":
    
    run()
