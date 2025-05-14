# gmail_fixed.py
import ceas.config as cfg
import os
import base64
import pickle
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import jinja2

from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
import google_auth_oauthlib.flow  as gflow
from googleapiclient.discovery import build

import os

SCOPES = ['https://www.googleapis.com/auth/gmail.send']

# -------------------------------------------------------------
# Herramienta para obtener rutas de token y client_secret desde
# variables de entorno: GMAIL_TOKEN_PATH y GMAIL_CLIENT_SECRET.
# Si no existen, usa valores por defecto en PROJ_ROOT.
# -------------------------------------------------------------
def _get_paths():
    import os, pathlib
    token_path  = os.getenv("GMAIL_TOKEN_PATH",
                            str(cfg.PROJ_ROOT / "token_fixed.pickle"))
    client_path = os.getenv("GMAIL_CLIENT_SECRET",
                            str(cfg.PROJ_ROOT / "client_secret11.json"))
    # Expand ~ and relative segments
    token_path  = str(pathlib.Path(token_path).expanduser().resolve())
    client_path = str(pathlib.Path(client_path).expanduser().resolve())
    return token_path, client_path

#
# -------------------------------------------------------------
# authenticate_fixed
#  - Lee token de GMAIL_TOKEN_PATH (o argumento `path`)
#  - Si el token es inválido o Google responde invalid_grant,
#    borra el token y relanza el flujo OAuth.
# -------------------------------------------------------------
def authenticate_fixed(path: str | None = None):
    """
    Autentica usando client_secret.json, genera/lee token.pickle.
    Retorna un service para enviar con la cuenta personas@ceas.cl
    """
    token_path, client_path = _get_paths()
    if path:
        token_path = path

    creds = None
    # Leer token si existe
    if os.path.exists(token_path):
        try:
            with open(token_path, 'rb') as f:
                creds = pickle.load(f)
        except Exception as e:
            print(f"[GMAIL] No se pudo leer token: {e}")
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(client_path, SCOPES)
            print(flow.redirect_uri)
            print(flow.client_config)
            creds = flow.run_local_server(port=8080, host='localhost', open_browser=True, redirect_uri_trailing_slash=False)
        with open(token_path, 'wb') as f:
            pickle.dump(creds, f)
    service = build('gmail','v1', credentials=creds)
    return service

# -------------------------------------------------------------
# Validar si el token vigente sigue autorizado. Realiza una
# petición ligera y, si falla con invalid_grant, borra el token
# y retorna False.
# -------------------------------------------------------------
def token_is_valid() -> bool:
    token_path, _ = _get_paths()
    if not os.path.exists(token_path):
        return False
    try:
        svc = authenticate_fixed()
        # llamada trivial: perfil del usuario
        svc.users().getProfile(userId="me").execute()
        return True
    except Exception as e:
        if "invalid_grant" in str(e):
            print("[GMAIL] invalid_grant detectado; se eliminará token.")
            os.remove(token_path)
            return False
        return False

#
# -------- create_html_message ---------
def create_html_message(
    sender: str,
    to: str,
    subject: str,
    cc: str | None = None,
    bcc: str | None = None,
    template_path: str | None = None,
    context: dict | None = None,
    custom_html: str | None = None,
    attachments: list | None = None,
) -> dict:
    """
    Crea un mensaje MIME listo para ser enviado por Gmail API.

    Args
    ----
    sender        : cuenta remitente (ej. 'personas@ceas.cl')
    to            : destinatario principal
    subject       : asunto del correo
    template_path : ruta a template Jinja2 (se usa si `custom_html` es None)
    context       : contexto para renderizar el template
    custom_html   : HTML ya construido (tiene prioridad sobre template)
    attachments   : lista de dicts  {filename:str, data:bytes, mime_type:str}
                    o lista de UploadedFile de Streamlit.
    """
    # ------------------- Generar HTML -------------------
    if custom_html is not None:
        # Respetar saltos de línea convirtiendo \n en <br>
        rendered_html = custom_html.replace("\n", "<br>")
    else:
        if template_path is None:
            raise ValueError("Debe proveer template_path o custom_html")
        if context is None:
            context = {}
        with open(template_path, "r", encoding="utf-8") as tf:
            template_str = tf.read()
        template = jinja2.Template(template_str)
        rendered_html = template.render(**context).replace("\n", "<br>")

    # ------------------- Construir MIME -------------------
    # Multipart general (tipo 'mixed' para permitir adjuntos)
    message = MIMEMultipart()
    message["From"] = sender
    message["To"] = to
    message["Subject"] = subject
    if cc:
        message["Cc"] = cc
    if bcc:
        message["Bcc"] = bcc

    # Parte alternativa solo con HTML
    alt_part = MIMEMultipart("alternative")
    mime_html = MIMEText(rendered_html, "html", "utf-8")
    alt_part.attach(mime_html)
    message.attach(alt_part)

    # ------------------- Adjuntos -------------------
    if attachments:
        import mimetypes
        from email import encoders
        from email.mime.base import MIMEBase

        # Normalizar: si vienen UploadedFile de Streamlit, conviértelos
        normalized = []
        for att in attachments:
            if hasattr(att, "read"):  # UploadedFile
                data = att.read()
                normalized.append({"filename": att.name, "data": data, "mime_type": att.type or "application/octet-stream"})
            elif isinstance(att, dict):
                normalized.append(att)
            else:
                # ignorar formatos desconocidos
                continue

        for att in normalized:
            if len(att["data"]) > 25_000_000:
                # Gmail no acepta adjuntos >25 MB; omitir y advertir en HTML
                rendered_html += f"<br><b>Adjunto omitido por tamaño &gt;25 MB:</b> {att['filename']}"
                continue
            maintype, subtype = (att["mime_type"].split("/", 1)
                                 if "/" in att["mime_type"] else ("application", "octet-stream"))
            mime_part = MIMEBase(maintype, subtype)
            mime_part.set_payload(att["data"])
            encoders.encode_base64(mime_part)
            mime_part.add_header("Content-Disposition", "attachment", filename=att["filename"])
            message.attach(mime_part)

    # ------------------- Codificar -------------------
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    return {"raw": raw}

def send_message(service, user_id, message):
    sent = service.users().messages().send(userId=user_id, body=message).execute()
    return sent

if __name__=="__main__":
    svc = authenticate_fixed()
    ctx = {"nombre": "Victor", "mensaje": "Esto es un test de envío de correo con Jinja2."}
    msg = create_html_message("personas@ceas.cl", "paylwin@ceas.cl", "test", "email_template.html", ctx)
    result = send_message(svc, "me", msg)
    print("Enviado:", result["id"])