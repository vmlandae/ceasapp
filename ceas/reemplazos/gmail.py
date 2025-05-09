import os
import ceas.config as cfg
from ceas.reemplazos.gmail_fixed import (
    authenticate_fixed,
    create_html_message,
    send_message
)

def send_candidates_email(
    institucion: str,
    asignatura: str,
    nivel_educativo: str,
    dias: str,
    solicitante: str,
    lista_candidatos: str,
    to_email: str,
    subject: str = "Opciones de candidatos",
    template_path: str = "email_candidates_template.html"
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
    # token path
    token_path = cfg.PROJ_ROOT / 'token_fixed.pickle'
    token_path = str(token_path)
    print("token_path:", token_path)
    # Check if token file exists
    if not os.path.exists(token_path):
        print(f"Token file {token_path} not found.")
        #return False
    # Check if template file exists

    
    template_path = cfg.PROJ_ROOT / template_path
    try:
        service = authenticate_fixed(path=token_path)  # Autentica a personas@ceas.cl
        context = {
            "institucion": institucion,
            "asignatura": asignatura,
            "nivel_educativo": nivel_educativo,
            "solicitante": solicitante,
            "lista_candidatos": lista_candidatos
        }
        # Create HTML message
        message_dict = create_html_message(
            sender="personas@ceas.cl",
            to=to_email,
            subject=subject,
            template_path=template_path,
            context=context
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