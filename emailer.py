import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from cryptography.fernet import Fernet
from flask import Blueprint, request, flash, render_template, session
from db_handler import get_db_connection

# ——— KEY MANAGEMENT ———
KEYFILE = os.path.join(os.path.dirname(__file__), 'config_data.bin')  # Obfuscated filename
ENV_KEY = os.environ.get('APP_SECRET')  # Obfuscated env var

if ENV_KEY:
    key = ENV_KEY.encode('utf-8')
elif os.path.exists(KEYFILE):
    with open(KEYFILE, 'rb') as f:
        key = f.read()
else:
    key = Fernet.generate_key()
    with open(KEYFILE, 'wb') as f:
        f.write(key)

cipher = Fernet(key)


def decrypt_value(token: str) -> str:
    if not token:
        return ''
    try:
        return cipher.decrypt(token.encode()).decode().strip()
    except Exception:
        return ''


# ——— Blueprint Setup ———
emailer_bp = Blueprint('emailer', __name__, template_folder='templates')


def get_email_settings():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT outgoing_server, outgoing_port, outgoing_username, outgoing_password
        FROM settings
        ORDER BY id DESC
        LIMIT 1
    """)
    row = cur.fetchone()
    conn.close()

    if not row:
        raise ValueError("No email settings found in the settings table.")

    host, port, user_encrypted, pw_encrypted = row

    if not all([host, port, user_encrypted, pw_encrypted]):
        raise ValueError("Missing one or more SMTP settings in the settings table.")

    try:
        port = int(port)
    except ValueError:
        raise ValueError(f"Invalid outgoing_port: {port!r}")

    return host, port, user_encrypted, pw_encrypted


def send_email(to_email: str, subject: str, body: str):
    host, port, user_enc, pw_enc = get_email_settings()
    user = decrypt_value(user_enc)
    pw = decrypt_value(pw_enc)

    if not user or not pw:
        raise ValueError("Failed to decrypt SMTP credentials.")

    if port == 465:
        server = smtplib.SMTP_SSL(host, port)
    else:
        server = smtplib.SMTP(host, port)
        server.ehlo()
        server.starttls()
        server.ehlo()

    server.login(user, pw)

    msg = MIMEMultipart()
    msg['From'] = user
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    server.sendmail(user, to_email, msg.as_string())
    server.quit()


# Your existing Flask route to send email via form
@emailer_bp.route('/send-email', methods=['GET', 'POST'])
def send_email_route():
    to_email = ''
    subject = ''
    body = ''

    if request.method == 'POST':
        to_email = request.form.get('to_email', '').strip()
        subject = request.form.get('subject', '').strip()
        body = request.form.get('body', '').strip()

        if not to_email or not subject or not body:
            flash("All fields are required.", "error")
        else:
            try:
                send_email(to_email, subject, body)
                flash("Email sent successfully!", "success")
                to_email = subject = body = ''
            except Exception as e:
                flash(f"Failed to send email: {e}", "error")

    return render_template('send_email.html',
                           to_email=to_email,
                           subject=subject,
                           body=body)


# Additional helper functions for automated emails below:

def email_password_updated(user_email: str, username: str):
    subject = "Your password has been updated"
    body = (f"Hello {username},\n\nYour password was successfully updated.\n\nIf you did not perform this action, "
            f"please contact support immediately.")
    send_email(user_email, subject, body)


def email_event_invite(user_email: str, event_name: str, event_date: str):
    subject = f"Invitation to Event: {event_name}"
    body = f"Dear member,\n\nYou are invited to our upcoming event: {event_name} on {event_date}.\n\nHope to see you there!"
    send_email(user_email, subject, body)
