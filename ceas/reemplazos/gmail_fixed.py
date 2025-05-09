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

SCOPES = ['https://www.googleapis.com/auth/gmail.send']

def authenticate_fixed(path=None):
    """
    Autentica usando client_secret.json, genera/lee token.pickle.
    Retorna un service para enviar con la cuenta personas@ceas.cl
    """
    creds = None
    if path is not None:
        try:
            with open(path, 'rb') as f:
                creds = pickle.load(f)
        except Exception as e:
            print(f"Error loading credentials from {path}: {e}")
    if os.path.exists('token_fixed.pickle') and creds is None:
        with open('token_fixed.pickle', 'rb') as f:
            creds = pickle.load(f)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(cfg.PROJ_ROOT/'client_secret11.json', SCOPES)
            print(flow.redirect_uri)
            print(flow.client_config)
            #flow = gflow.Flow.from_client_secrets_file('client_secret.json', scopes=SCOPES)
            creds = flow.run_local_server(port=8080, host = 'localhost', open_browser=True,redirect_uri_trailing_slash=False)
        with open('token_fixed.pickle','wb') as f:
            pickle.dump(creds, f)
    service = build('gmail','v1', credentials=creds)
    return service

def create_html_message(sender, to, subject, template_path, context):
    """
    Crea un mensaje HTML usando un template Jinja2.
    """
    with open(template_path, "r", encoding="utf-8") as tf:
        template_str = tf.read()
    template = jinja2.Template(template_str)
    print("template_str", template_str)
    print("template", template)
    print("context", context)
    rendered_html = template.render(**context)
    print("rendered_html", rendered_html)

    message = MIMEMultipart("alternative")
    message["From"] = sender
    message["To"] = to
    message["Subject"] = subject

    mime_html = MIMEText(rendered_html, "html", "utf-8")
    message.attach(mime_html)

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