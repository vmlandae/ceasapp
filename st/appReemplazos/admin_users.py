import streamlit as st
import ceas.config as cfg
from ceas.user_management import get_all_users, change_user_role, delete_user, add_user
import re
from ceas.utils import validate_new_user, create_columns_panel, disable_role_change, on_change_role,role_options,on_delete_user, on_enviar_correo, read_requests_from_gsheet
from ceas.utils import clean_gform_requests,process_requests_from_gsheet,create_request_dict_from_gform
import time
from ceas.reemplazos.refresh import refresh_dataframes
import pandas as pd
from ceas.notifications import *
# Let's define a rank dictionary to compare roles easily
# data = st.session_state['dfs']['requests'].loc[st.session_state['dfs']['requests']['replacement_id'] == 1]
# st.session_state["data"] = data


def user_panel_v2():
    """
    Listado de usuarios activos con la posibilidad de cambiar roles y eliminar usuarios (en realidad se desactivan, status = "inactive")
    Se usa la función create_columns_panel para crear las columnas de la tabla.
    El listado se muestra en una tabla con ciertas columnas, y trae también algunos filtros para buscar usuarios.
    args:
        data (dict): diccionario con los dataframes de users, schools
    returns:
        None
        
    """
    st.header("Listado de Usuarios Activos")

    df_users = st.session_state['dfs']['users'].copy().query("status == 'active'")

    df_schools = st.session_state['dfs']['schools'].copy()
    

    
    columns_info = [
    {"header":"Email",   "field":"email", "type":"text", "width":2},
      {"header":"Nombre",  "field":"name",  "type":"text", "width":1},
      {"header":"Rol",  "field":"role","type":"text", "width":1},
      {
        "header":"Cambiar rol",
        "button_label":"Cambiar",
        "type":"button",
        "width":1,
        
        "disable_fn": {"callable":disable_role_change, 
                       "args": [], 
                       "kwargs": {"user_role":st.session_state['role'],
                                   "ROLE_RANK":st.session_state['roles_rank']}},
        "on_click":{"callable":on_change_role, "args": [], 
                    "kwargs": {
                                "user_role":st.session_state['role'],
                                "ROLE_RANK":st.session_state['roles_rank'],
                                }}
      },
      {
        "header":"Eliminar usuario",
        "button_label":"Eliminar",
        "type":"button",
        "width":1,
        "disable_fn":{"callable":disable_role_change, 
                       "args": [], 
                       "kwargs": {"user_role":st.session_state['role'],
                                   "ROLE_RANK":st.session_state['roles_rank']}},
        "on_click": {"callable":on_delete_user, "args": [], "kwargs": {"user_role":st.session_state['role'],
                                   "ROLE_RANK":st.session_state['roles_rank']}}
      },
    #  {
    #     "header":"Enviar contacto a colegio",
    #     "button_label":"Enviar",
    #     "type":"button",
    #     "width":1,
    #     "disable_fn": False,
    #     "on_click":{"callable": on_enviar_correo,
    #                  "args": [], 
    #                 "kwargs": {"data":st.session_state['data'].to_dict(orient="records") }
    #                 }
    #   }

    ]
    # defin
    create_columns_panel(df_users, columns_info,key_prefix="user_panel")



def inactive_users(df_users = st.session_state['dfs']['users']):
    st.header("Usuarios desactivados")
    df_users = st.session_state['dfs']['users'].copy().query("status == 'inactive'")
    columns_info = [
        {"header":"Email",   "field":"email", "type":"text", "width":2},
        {"header":"Nombre",  "field":"name",  "type":"text", "width":1},
        {"header":"Rol",  "field":"role","type":"text", "width":1},
        {"header":"Institución",  "field":"school_name","type":"text", "width":1},
        {"header":"Estado",  "field":"status","type":"text", "width":1},
        {"header":"Cambiar estado",  "button_label":"Cambiar","type":"button", "width":1},
        
    ]
    create_columns_panel(df_users, columns_info, key_prefix="inactive_users_panel")

    



def add_new_user_form(roles_list ):
    role = st.session_state['role']
    if role not in ["owner", "admin", "oficina_central"]:
        st.warning("Solo 'owner', 'admin' y 'oficina_central' pueden agregar usuarios.")
        st.stop()
    form = st.form(key="add_user_form")
    new_email = form.text_input("Email", key="new_email")
    new_name = form.text_input("Nombre", key="new_name")
    new_role = form.selectbox("Rol", roles_list, index=0, key="new_role")
    df_schools = st.session_state['dfs']['schools'].copy()
    
    
    new_school = form.selectbox("Institución", df_schools["school_name"].tolist())
    new_status = "new"
    if form.form_submit_button("Agregar"):
        if not validate_new_user:
            st.error(f"Error al validar los datos del nuevo usuario.")
            return
        else:
            school_id = df_schools.loc[df_schools["school_name"] == new_school, "school_id"].values[0]
            add_user(new_email, new_name, new_role, school_id, new_school, new_status)
            st.success(f"Usuario {new_email} agregado")
            time.sleep(2)
            st.session_state['refresh_list'] = ['appReemplazosUsers']
            refresh_dataframes()
            form.empty()
            
        
                            
def new_user_panel():
    with st.expander("Agregar un nuevo usuario"):
        add_new_user_form(roles_list=st.session_state["roles"])
    st.divider()

    st.header("Usuarios nuevos por validar")
    # explicar que estos son los usuarios nuevos que no han confirmado su correo electrónico,
    # que se les debe enviar un correo con un código de validación y que al confirmar su correo
    # se les cambiará el estado automáticamente a "active"
    
    # mostrar panel con los usuarios nuevos sin confirmar correo electrónico
    # definimos columns_info con la información de las columnas de la tabla
    df_users = st.session_state['dfs']['users'].copy().query("status == 'new'")
    try:
        df_validations = st.session_state['dfs']['uservalidations'].copy()
    except KeyError:
        df_validations = pd.DataFrame()
    
    if df_users.empty:
        st.error("No hay usuarios nuevos por validar")
        st.stop()
    df_users = df_users.merge(df_validations, how="left", on=['user_id','email'])
    columns_info = [
        {"header":"Email",   "field":"email", "type":"text", "width":2},
        {"header":"Nombre",  "field":"name",  "type":"text", "width":1},
        {"header":"Institución",  "field":"school_name","type":"text", "width":1},
        {"header":"Fecha de creación del usuario",  "field":"role","type":"text", "width":1},
        {"header":"Código de validación",  "field":"validation_code","type":"text", "width":1},
        {"header":"Enviar código", "button_label":"Enviar", "type":"button", "width":1}, # se desactiva el botón si ya se ha enviado el código
        {"header": "Fecha de envío", "field":"code_sent_at", "type":"text", "width":1},
        {"header": "Estado validación", "field":"confirmation", "type":"text", "width":1},
        {"header":"Fecha de confirmación", "field":"confirmed_at", "type":"text", "width":1},
        {"header": "Confirmado por", "field":"confirmed_by", "type":"text", "width":1},
        {"header": "Confirmación manual", "button_label":"Confirmar", "type":"button", "width":1},
        
    ]
    create_columns_panel(df_users, columns_info, key_prefix="new_users_panel")
    # agregar botón para enviar correo de confirmación

 
def gform_requests_panel():
    st.empty()
    # df = read_requests_from_gsheet()
    # df = clean_gform_requests(df,cols_map=st.session_state['gform_map']['cols_map'],
    #                           school_name_map=st.session_state['gform_map']['school_name_map'],
    #                           ED_MAPPING=st.session_state['gform_map']['ED_MAPPING'])
    


    # st.dataframe(df)
    # #df.to_pickle(cfg.INTERIM_DATA_DIR/"df_gform.pkl")
    


def admin_panel():

    manage_users_tab, new_users_tab, inactive_users_tab, gform_requests_tab = st.tabs(["Administrar Usuarios", "Agregar/Validar Usuarios", "Usuarios Inactivos", "Gform Requests"])
    with manage_users_tab:
        #user_panel()
        user_panel_v2()
    with new_users_tab:
    # mostrar un expander para agregar un nuevo usuario solo si el rol del usuario es "owner", "admin" o "oficina_central"
        if st.session_state.role in ["owner", "admin", "oficina_central"]:
            new_user_panel()     
        else:
            st.empty()
    with inactive_users_tab:
        inactive_users()        
    with gform_requests_tab:
        gform_requests_panel()

        

def run():
    st.title("Panel de Administración")
    if st.button("Actualizar"):
        st.spinner("Actualizando...")
        time.sleep(1)

    if st.session_state.get("role") not in ["owner", "admin", "oficina_central"]:
        st.error("No tienes acceso a esta sección")
        st.stop()
    admin_panel()
    



if __name__ == "__page__":
    
    run()