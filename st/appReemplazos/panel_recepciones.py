import streamlit as st
from ceas import schools_manager

st.title("Panel de Recepciones")

# Verificar permisos
if st.session_state.role not in ["owner", "admin", "oficina_central", "directivo_colegio", "user_colegio"]:
    st.error("No tienes acceso a esta sección.")
    st.stop()

# Mostrar recepciones de servicios
df_receptions = schools_manager.get_service_receptions(st.session_state["app_name"])
st.dataframe(df_receptions)

# Registrar recepción de servicio
email = st.text_input("Email del candidato")
rating = st.slider("Calificación", 1, 5)
if st.button("Registrar Recepción"):
    success, df_receptions = schools_manager.register_reception(email, rating, df_receptions)
    if success:
        st.success("Recepción registrada exitosamente")
    else:
        st.error("Error al registrar la recepción")
