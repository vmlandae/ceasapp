import streamlit as st

import re
import time
from ceas.reemplazos.refresh import refresh_dataframes
from ceas.utils import get_days_between_dates, create_replacement_request,create_request_dict

import datetime




def form_crear_solicitud_reemplazo(rol,institucion):
    if "form_reemplazo_data" not in st.session_state:
        st.session_state["form_reemplazo_data"] = {}


    st.header("Datos Requeridos")
    # Solicitante: se muestra el nombre del usuario logueado, sin posibilidad de edición
    
    st.session_state["form_reemplazo_data"]["solicitante"] = st.text_input("Solicitante", value=st.session_state['user_info']['email'],disabled=True)

    # si el rol es admin_colegio, user_colegio, se muestra el nombre de la institución sin posibilidad de edición
    if rol in ["admin_colegio", "user_colegio"]:
        st.session_state["form_reemplazo_data"]["inst"] = st.selectbox("Institución", options=[institucion],disabled=True)
        
    elif rol in ["owner", "admin", "oficina_central"]:
        # on_change: guardar la institución seleccionada en la variable st.session_state["selected_institution"]
      st.session_state["form_reemplazo_data"]["inst"] = st.selectbox( "Institución", index=None,
                                options=st.session_state['dfs']['schools'].query("type == 'colegio'")['school_name'].values, # las instituciones excepto Oficina Central
                                key="institucion")


    if "inst" in st.session_state['form_reemplazo_data'] and st.session_state['form_reemplazo_data']["inst"] is not None:      
            # Nivel educativo: multiselect con las siguientes opciones:
            # "Inicial (PreKinder/Kinder)", "Básica", "Media", "Técnico Profesional", "Educación Diferencial"

            # Curso(s): multiselect de cursos, dependiendo del nivel educativo seleccionado
            # en el caso de "Inicial (PreKinder/Kinder)", los cursos son "PreKinder" y "Kinder"
            # en el caso de "Básica", los cursos son "1° Básico", "2° Básico", ..., "8° Básico"
            # en el caso de "Media", los cursos son "1° Medio", "2° Medio", "3° Medio", "4° Medio"
            # en el caso de "Técnico Profesional", los cursos podrían ser  "3° Medio", "4° Medio" 
            # en el caso de "Educación Diferencial", los cursos podrían ser desde PreKinder hasta 4° Medio
            st.divider()
            st.subheader("Ciclo Educativo")
            nivel_educativo = st.multiselect("Nivel Educativo", options=st.session_state['niveles_educativos'], key="nivel_educativo",default=None)
            
            st.session_state["form_reemplazo_data"]["nivel_educativo"] = nivel_educativo
            jefatura = st.selectbox("¿Con o sin jefatura?", options=["Con Jefatura", "Sin Jefatura", "No Aplica"],index=None,  key="jefatura")
            st.session_state["form_reemplazo_data"]["jefatura"] = jefatura
            st.session_state['form_reemplazo_data']["cursos"] = {}
            st.session_state['form_reemplazo_data']["asignaturas"] = {}
            st.divider()
            if "nivel_educativo" in st.session_state['form_reemplazo_data'] and st.session_state['form_reemplazo_data']["nivel_educativo"] is not None and len(st.session_state['form_reemplazo_data']["nivel_educativo"]) > 0:
                st.subheader("Asignaturas y niveles por Ciclo Educativo")
                for nivel in nivel_educativo:
                    st.write(f"Nivel Educativo: {nivel}")
                    
                    st.session_state['form_reemplazo_data']["asignaturas"][nivel] = st.multiselect(f"Asignaturas de {nivel}", options=st.session_state['asignaturas_por_nivel_educativo'][nivel], key=f"asignaturas_{nivel}")

                    st.session_state['form_reemplazo_data']["cursos"][nivel] = st.multiselect(f"Niveles de {nivel}", options=st.session_state['cursos_por_nivel_educativo'][nivel], key=f"cursos_{nivel}")
                    
                    st.divider()
                if st.session_state['form_reemplazo_data']["nivel_educativo"] is not None and st.session_state['form_reemplazo_data']["asignaturas"] is not None and st.session_state['form_reemplazo_data']["cursos"] is not None:
                    st.subheader("Fechas y Horarios")
                    # Fecha de inicio: date_input
                    fecha_inicio = st.date_input("Fecha de Inicio", key="fecha_inicio",min_value=datetime.date.today())
                    st.session_state['form_reemplazo_data']["fecha_inicio"] = fecha_inicio


                    # Fecha de fin: date_input
                    fecha_fin = st.date_input("Fecha de Fin", key="fecha_fin",min_value=datetime.date.today())
                    st.session_state['form_reemplazo_data']["fecha_fin"] = fecha_fin
                    # Días de la semana: checkbox para cada día de la semana
                    # lunes, martes, miércoles, jueves, viernes
                    dias_de_la_semana = st.multiselect("Días de la semana", options=["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"], key="dias_de_la_semana", default=["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"])
                    st.session_state['form_reemplazo_data']["dias_de_la_semana"] = dias_de_la_semana


                    st.divider()
                    

                    # bloque horario: Indicar horario de inicio y fin de la jornada por día
                    # primero, extraer los días seleccionados entre fecha de inicio y fecha de fin. 
                    # Considerar que se deben mostrar los días de la semana (sacando sábado y domingo) entre las fechas seleccionadas, incluyendo la fecha de inicio y fin
                    dias_seleccionados = get_days_between_dates(fecha_inicio, fecha_fin, dias_de_la_semana)

                    # st.write con los días que necesitan reemplazo (días de la semana entre fecha de inicio y fecha de fin que no sean sábado ni domingo ni feriado)
                    # unir dias_seleccionados["str_weekdays"] y dias_seleccionados["str_days"] con un espacio
                    dias_que_necesitan_reemplazo = [f"{dia} {fecha}" for dia, fecha in zip(dias_seleccionados["str_weekdays"], dias_seleccionados["str_days"])]
    
                    # concatenamos los elementos en dias_que_necesitan_reemplazo con una coma y un espacio

                    texto_dias = ", ".join(dias_que_necesitan_reemplazo)
                    st.write(f"Días que necesitan reemplazo: {texto_dias}")
                    # TODO: si son todos los días de la semana (Lunes a Viernes), mostrar solo los días de inicio y fin y la cantidad de días
                    st.session_state['form_reemplazo_data']['dias'] = dias_seleccionados["str_weekdays"]
                    st.session_state['form_reemplazo_data']["days"] = dias_seleccionados["days"].strftime("%Y-%m-%d").tolist()


                    st.subheader("Horario")
                    # mostrar un selectbox para indicar la cantidad de horas de contrato: de 1 a 44 horas
                    horas_contrato = st.selectbox("Cantidad de horas de contrato", options=[i for i in range(1, 45)], key="horas_contrato")
                    st.session_state['form_reemplazo_data']["horas_contrato"] = horas_contrato
                    # mostrar un checkbox para ver si se desea especificar el horario de inicio y fin de la jornada
                    especificar_horario = st.checkbox("Especificar horario de inicio y fin de la jornada", key="especificar_horario")
                    if especificar_horario:
                    
                        # columnas: día de la semana, hora de inicio, hora de fin
                        
                        st.session_state['form_reemplazo_data']['horarios'] = {}
                        for j,dia in enumerate(st.session_state['form_reemplazo_data']["days"]):
                            cols = st.columns(5)
                            with cols[0]:
                                if j == 0:
                                    st.write("Día:")
                                st.write(f"{dia}:",)
                                st.session_state['form_reemplazo_data']['horarios'][dia] ={}
                            with cols[1]:
                                if j == 0:
                                    st.write("Hora de inicio:")

                                horario_inicio = st.time_input(f"Horario de inicio de jornada", key=f"horario_inicio_{j}", value="08:00")

                                st.session_state['form_reemplazo_data']['horarios'][dia]['horario_inicio'] = horario_inicio
                            with cols[2]:
                                if j == 0:
                                    st.write("Hora de término:")
                                horario_fin = st.time_input(f"Hora de término de jornada", key=f"horario_fin_{j}", value="16:00")
                                st.session_state['form_reemplazo_data']['horarios'][dia]['horario_fin'] = horario_fin
                            with cols[3]:
                                st.empty()
                            with cols[4]:
                                st.empty()
                    else:
                        st.session_state['form_reemplazo_data']['horarios'] = {}                        
                    
                    st.divider()
                    #¿Debe tener alguna mención, especialidad o postítulo?, ¿Cuál?\nEj.: Educador/a Diferencial mención en TEL o NEEP',
                    # text_input para indicar la mención, especialidad o postítulo requerido
                    mencion_especialidad_postitulo = st.text_input("¿Debe tener alguna mención, especialidad o postítulo?, ¿Cuál?", key="mencion_especialidad_postitulo", placeholder="Ej.: Educador/a Diferencial mención en TEL o NEEP")
                    st.session_state["form_reemplazo_data"]['mencion_especialidad_postitulo'] = mencion_especialidad_postitulo

                    # ¿La vacante es confidencial?
                    # selectbox con opciones "Sí", "No"
                    vacante_confidencial = st.selectbox("¿La vacante es confidencial?", options=["Sí", "No"], index=None, key="vacante_confidencial")
                    st.session_state["form_reemplazo_data"]['vacante_confidencial'] = vacante_confidencial


                    st.divider()
                    # Preferencias: opciones de preferencias para el reemplazo, optativas
                    st.subheader("Preferencias")
                    # Género: radio button con opciones "Masculino", "Femenino", "Indiferente"
                    genero = st.radio("Género", options=["Indiferente", "Femenino", "Masculino"], key="genero")
                    st.session_state["form_reemplazo_data"]['genero'] = genero
                    # mínimo de años de egreso: slider de 0 a 10 años
                    anios_egreso = st.slider("Mínimo de años de egreso", min_value=0, max_value=10, key="anios_egreso")
                    st.session_state["form_reemplazo_data"]['anios_egreso'] = anios_egreso
                    # disponibilidad de días de la semana completa o parcial: radio button con opciones "Completa", "Parcial"
                    # si la disponibilidad es completa,
                    disponibilidad = st.radio("Disponibilidad de días", options=["Completa", "Parcial"], key="disponibilidad_dias_completa")
                    st.session_state["form_reemplazo_data"]['disponibilidad'] = disponibilidad
                    # si la disponibilidad es parcial, cuando se haga el match se mostrarán todos los candidatos que tengan al menos un día de la semana disponible, 
                    # y se mostrará en la tabla de resultados cuántos días de la semana tiene disponible cada candidato. Si es completa, se mostrarán los candidatos que tengan todos los días de la semana requeridos disponibles.
                    
                    # candidato preferido: text_input para indicar nombres, apellidos, rut, correo y teléfono de contacto del candidato preferido (si tienen un candidato previo, independiente si está inscrito o no en la plataforma/formulario)
                    candidato_preferido = st.text_input("Candidato Preferido", key="candidato_preferido", placeholder="Nombre, Apellido, Rut, Correo, Teléfono")
                    st.session_state["form_reemplazo_data"]['candidato_preferido'] = candidato_preferido

            

            st.divider()
            # otras preferencias: text_area para indicar otras preferencias
            otras_preferencias = st.text_area("Otras Preferencias", key="otras_preferencias", placeholder="Otras preferencias")
            st.session_state["form_reemplazo_data"]['otras_preferencias'] = otras_preferencias
            
            
            
            # Botón de enviar: form_submit_button
            submitted = st.button("Enviar Solicitud")
            
            if submitted:
                st.session_state['submitted_form_reemplazo'] = True # revisar y eliminar si no es necesario

                dict_reemplazo_data = st.session_state['form_reemplazo_data'].copy()
                # primero creamos un request_dict
                request_dict = create_request_dict(dict_reemplazo_data)

                
                status, df_requests = create_replacement_request(request_dict=request_dict,
                                            df_requests=st.session_state['dfs']['requests'])
                if status:
                    # si la solicitud se creó correctamente, se muestra un mensaje de éxito y se ofrecen tres links/botones:
                    # 1) ir a la tabla de solicitudes de reemplazo
                    # 2) ir al panel de selección de candidatos para la solicitud recién creada
                    # 3) crear otra solicitud de reemplazo
                    st.success("Solicitud de reemplazo creada correctamente")
                    del st.session_state['form_reemplazo_data']
                    # refrescamos el dataframe de solicitudes de reemplazo
                    st.session_state['refresh_list'] = ["appReemplazosRequests"]
                    refresh_dataframes()
                    # mostramos los links/botones
                    st.write("Ir a:")
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        
                        st.page_link(st.session_state['pages'].get("panel_solicitudes_colegios"))
                        
                    with col2:
                        st.page_link(st.session_state['pages'].get("panel_seleccion_candidatos"))
                        #st.page_link(st.session_state['pages'].get("panel_solicitudes_colegios"))
                        
                        
                    with col3:  
                        
                        st.empty()
                        
                else:
                    st.error("Error al crear la solicitud de reemplazo. Por favor, inténtalo nuevamente.")
                    del st.session_state['submitted_form_reemplazo'], st.session_state['form_reemplazo_data']
                    st.stop()

  


def panel(rol,institucion):
    # definimos tabs: "Solicitudes de Reemplazo", "Crear Solicitud de Reemplazo"

        form_crear_solicitud_reemplazo(rol,institucion)



def run():
    # verificar permisos y definir títulos:
    # si el rol es owner, admin, oficina_central: el título es "Panel de Solicitudes de Colegios"
    # si el rol es admin_colegio, user_colegio: el título es "Solicitudes de Reemplazo"

    
    panel(rol = st.session_state.role,institucion = st.session_state['user_info']['school_name'])


    


if __name__ == "__page__":
    run()

