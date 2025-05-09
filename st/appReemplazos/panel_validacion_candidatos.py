import streamlit as st
from ceas import schools_manager

st.title("Panel de Validación de Candidatos")

# Verificar permisos
if st.session_state.role not in ["owner", "admin", "oficina_central"]:
    st.error("No tienes acceso a esta sección.")
    st.stop()


# Mostrar candidatos a validar
# df_candidates = schools_manager.get_candidates_to_validate(st.session_state["app_name"])
# st.dataframe(df_candidates)


st.dataframe(st.session_state['dfs']['applicants'])

# Validar candidato
email = st.text_input("Email del candidato a validar")
if st.button("Validar Candidato"):
    success, df_candidates = schools_manager.validate_candidate(email, st.session_state['dfs']['applicants'])
    if success:
        st.success("Candidato validado exitosamente")
    else:
        st.error("Error al validar el candidato")
