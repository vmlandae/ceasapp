"""
notifications.py

Módulo para manejar notificaciones y envíos de mensajes.
Incluye ejemplos de:
 - Conexión a Gmail API (google-api-python-client)
 - Alternativa con smtplib
 - Funciones send_email(), notify_incidence_created()
 - Opciones de notificaciones vía WhatsApp / Twilio / api.whatsapp.com links
"""

import streamlit as st
import os
import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
import smtplib

def gmail_service_account_auth(credentials_file:str):
    """
    Crea un servicio Gmail usando un service account (solo funciona
    si la cuenta de servicio está impersonando una cuenta con Gmail 
    y la domain policy lo permite).
    OJO: Este approach a veces no es trivial, 
    GSuite Admin debe habilitar domain-wide delegation.
    Returns: service (gmail) 
    """
    SCOPES = ['https://www.googleapis.com/auth/gmail.send']
    creds = Credentials.from_service_account_file(credentials_file, scopes=SCOPES)
    # Requiere domain-wide delegation => creds.with_subject("user@domain.com")
    delegated_creds = creds.with_subject("tu_correo_admin@tudominio.com")  
    service = build('gmail', 'v1', credentials=delegated_creds)
    return service

def send_email_gmail_api(to_email:str, subject:str, body_html:str,
                         credentials_file:str) -> bool:
    """
    Envía un correo usando la Gmail API con domain-wide delegation.
    Args:
      to_email (str): destinatario
      subject (str)
      body_html (str): contenido HTML
      credentials_file (str): path al service account JSON

    Returns True si éxito, False si falla.
    """
    try:
        service = gmail_service_account_auth(credentials_file)
        # Construir el mensaje
        mime_msg = MIMEMultipart('alternative')
        mime_msg['to'] = to_email
        mime_msg['subject'] = subject
        # Body en HTML
        mime_msg.attach(MIMEText(body_html, 'html'))
        raw = base64.urlsafe_b64encode(mime_msg.as_bytes()).decode('utf-8')
        message_body = {'raw': raw}

        send_result = service.users().messages().send(userId="me", body=message_body).execute()
        st.write("Send message result:", send_result)
        return True
    except Exception as e:
        st.error(f"Error enviando email via Gmail API: {e}")
        return False

def send_email_smtp(to_email:str, subject:str, body:str,
                    smtp_server:str, port:int,
                    login_user:str, login_pass:str,
                    use_tls=True) -> bool:
    """
    Envía un correo usando SMTP.
    Args:
      to_email: destinatario
      subject: asunto
      body: texto plano
      smtp_server: e.g. 'smtp.gmail.com'
      port: e.g. 587
      login_user: credenciales
      login_pass: ...
      use_tls: bool
    """
    try:
        server = smtplib.SMTP(smtp_server, port)
        if use_tls:
            server.starttls()
        server.login(login_user, login_pass)
        msg = f"Subject: {subject}\n\n{body}"
        server.sendmail(login_user, to_email, msg)
        server.quit()
        return True
    except Exception as e:
        st.error(f"Error enviando email via SMTP: {e}")
        return False

def notify_incidence_created(incidence_id:int, assigned_to_email:str):
    """
    Notifica que se ha creado una incidencia. 
    Podrías expandir para buscar la info de la incidencia y mandar un correo 
    con detalles.
    Por ejemplo:
      - Leer la inc. en incidences_manager
      - mandar email a assigned_to_email con el subject: "Nueva incidencia..."
    """
    subject = f"[Sistema Compras] Incidencia #{incidence_id} creada"
    body_html = f"<p>Se ha creado la incidencia {incidence_id}. Revisa el panel de incidencias.</p>"
    # Ejemplo usando la API de Gmail con un service account
    # ajusta el path del credentials_file a lo que tengas
    credentials_file = "/path/to/gmail_sa.json"
    send_email_gmail_api(assigned_to_email, subject, body_html, credentials_file)

# -------------------------------------------------------------
# SUGERENCIAS / HERRAMIENTAS para Notificaciones via WhatsApp
# 
# 1) Links a la API oficial de WhatsApp (Business) => 
#    Documentación en https://developers.facebook.com/docs/whatsapp
#    Pros: Envío confiable, pero requires 
#    una cuenta de WhatsApp Business y tokens.
# 
# 2) Twilio WhatsApp:
#    - Twilio posee una API de WhatsApp. 
#    - Envías un POST a Twilio con to=whatsapp:+XXXXXXXX, from=whatsapp:+TwilioNumber, body=...
#    - Requiere suscripción Twilio y credenciales (account SID, auth token).
#    Pros: Rápido, escalable, 
#    Contras: tiene costo por mensaje.
#
# 3) Simple "api.whatsapp.com" links 
#    - Solo abren la app de WhatsApp con un chat prellenado. 
#    - Ejemplo: "https://api.whatsapp.com/send?phone=XXXXXXXXXX&text=Texto"
#    - No envía el msg automáticamente, el usuario debe pulsar "enviar".
#    Pros: sumamente sencillo, no requiere costos, 
#    Contras: no es automatizado completamente, el usuario final debe confirmar el envío
# 
# 4) Recomendación:
#    - Si deseas "notificaciones automáticas" => Twilio o la API oficial de WhatsApp Business.
#    - Si deseas algo "manual" => el link de "api.whatsapp.com" es suficiente.
#
# Tools / Librerías:
#    - "requests" para Twilio => POST a https://api.twilio.com/2010-04-01/Accounts/XXXX/Messages.json
#    - "whatsapp-business-api" => 
#    - "pywhatkit" (con limitaciones, + no oficial).
#
# Ejemplo de code snippet Twilio:
#
# def send_whatsapp_twilio(to_number:str, body:str):
#     from twilio.rest import Client
#     account_sid = "TU_SID"
#     auth_token = "TU_TOKEN"
#     client = Client(account_sid, auth_token)
#     message = client.messages.create(
#         body=body,
#         from_="whatsapp:+123456789", # tu Twilio sandbox
#         to=f"whatsapp:{to_number}"
#     )
#     st.write("Mensaje enviado con ID:", message.sid)
#
#
# FIN DE SUGERENCIAS