import os
import ceas.config as cfg
from ceas.reemplazos.gmail_fixed import (
    authenticate_fixed,
    create_html_message,
    send_message,
    token_is_valid,
)

def send_candidates_email(
    institucion: str,
    asignatura: str,
    nivel_educativo: str,
    dias: str,
    solicitante: str,
    lista_candidatos: str,
    to_email: str,
    cc: str | None = None,
    bcc: str | None = None,
    subject: str = "Opciones de candidatos",
    template_path: str = "email_candidates_template.html",
    custom_html: str | None = None,
    attachments: list | None = None,
):
    """
    Envía un correo HTML usando tu template jinja2 para notificar sobre candidatos disponibles.
    Requiere:
      - institucion (str)
      - asignatura (str)
      - nivel_educativo (str)
      - solicitante (str)
      - lista_candidatos (str)
      - to_email (str) => el email destino
      - subject (str) => asunto del correo
      - template_path (str) => ruta al template jinja2
    
    Ejemplo de template jinja2 (email_candidates_template.html):
    
    {% raw %}
    Estimado equipo de {{ institucion }}:

    En respuesta a su solicitud de docente de {{ asignatura }} para {{ nivel_educativo }}, envío opciones de candidatos que se ajustan a lo requerido.
    En caso de necesitar ampliar la búsqueda, por favor contáctenos.

    Saludos cordiales,
    {{ solicitante }}

    {{ lista_candidatos }}
    {% endraw %}
    
    Retorna True/False según éxito.
    """
    # -------- Validar token antes de autenticar ----------
    # El token se obtiene automáticamente vía GMAIL_TOKEN_PATH en gmail_fixed._get_paths()
    if not token_is_valid():
        import streamlit as st
        st.warning("Se requiere reautorizar Gmail: se abrirá ventana OAuth.")

    # Si custom_html está provisto, ignorar template y contexto
    if custom_html is not None:
        template_path_full = None
        context = None
    else:
        # Si se quiere usar template, construir contexto y ruta completa
        template_path_full = cfg.PROJ_ROOT / template_path if template_path else None
        context = {
            "institucion": institucion,
            "asignatura": asignatura,
            "nivel_educativo": nivel_educativo,
            "solicitante": solicitante,
            "lista_candidatos": lista_candidatos
        }
    try:
        service = authenticate_fixed()  # Autentica con token en GMAIL_TOKEN_PATH
        # Create HTML message
        message_dict = create_html_message(
            sender="personas@ceas.cl",
            to=to_email,
            cc=cc,
            bcc=bcc,
            subject=subject,
            template_path=template_path_full,
            context=context,
            custom_html=custom_html,
            attachments=attachments,
        )
        # Send
        result = send_message(service, user_id="me", message=message_dict)
        print("Correo enviado. ID:", result["id"])
        return True
    except Exception as e:
        print("Error al enviar el correo:", e)
        return False

# Example usage:
if __name__ == "__main__":
    success = send_candidates_email(
        institucion="Colegio ABC",
        asignatura="Matemáticas",
        nivel_educativo="Educación Media",
        dias="Lunes, Miércoles y Viernes",
        solicitante="solicitante@ceas.cl",
        lista_candidatos="- Juan Pérez\n- María González",
        to_email="vmlandae@gmail.com",
        subject="Opciones de candidatos para reemplazo",
        template_path="email_candidates_template.html"
    )
    if success:
        print("Correo enviado exitosamente.")
    else:
        print("Hubo un error al enviar el correo.")