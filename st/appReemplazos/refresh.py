import streamlit as st

# redirige a la página desde donde se llamó la función

def refresh_page():
    if "callback_page" not in st.session_state:
        st.session_state["callback_page"] = "app_reemplazos_v2.py"
    callback_page = st.session_state["callback_page"]

    del st.session_state["callback_page"]

    st.switch_page(callback_page)
def run():
    refresh_page()

if __name__ == "__page__":
    run()