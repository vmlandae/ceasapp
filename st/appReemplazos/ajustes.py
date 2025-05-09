import streamlit as st
from ceas.utils import cleanup_applicants,debug_cleanup_applicants
st.title("Ajustes")

# Verificar permisos
if st.session_state.role not in ["owner", "admin"]:
    st.error("No tienes acceso a esta sección.")
    st.stop()

# Configuración de ajustes
st.write("Aquí puedes configurar los ajustes de la aplicación.")
# mostrar st.session_state['dfs']['requests']
st.write("DataFrame de cleaned_applicants_serialized:")
df_a = st.session_state['dfs']['cleaned_applicants_serialized']

st.dataframe(df_a)
st.divider()
for col in df_a.columns:
    st.write(f"Columna: {col}")
    st.write(df_a[col].apply(type).value_counts())
    
# mostrar todas las st.session_state
# st.write("Estado de la sesión:")
# st.write(st.session_state)
