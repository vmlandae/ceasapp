import streamlit as st
from ceas import schools_manager

st.title("Panel de Elección de Candidato")

# Verificar permisos
if st.session_state.role not in ["owner", "admin", "oficina_central", "directivo_colegio", "user_colegio"]:
    st.error("No tienes acceso a esta sección.")
    st.stop()

# Mostrar candidatos propuestos
df_proposed_candidates = schools_manager.get_proposed_candidates(st.session_state["app_name"])
st.dataframe(df_proposed_candidates)

# Elegir candidato
email = st.text_input("Email del candidato a elegir")
if st.button("Elegir Candidato"):
    success, df_proposed_candidates = schools_manager.choose_candidate(email, df_proposed_candidates)
    if success:
        st.success("Candidato elegido exitosamente")
    else:
        st.error("Error al elegir el candidato")
