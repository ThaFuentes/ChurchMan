import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from cryptography.fernet import Fernet
from flask import Blueprint, request, flash, jsonify, render_template
from db_handler import get_db_connection

# ——— KEY MANAGEMENT ———
KEYFILE = os.path.join(os.path.dirname(__file__), 'config_data.bin')  # Obfuscated filename
ENV_KEY = os.environ.get('APP_SECRET')  # Obfuscated env var

# Load or generate key
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
    """Decrypt token when using it (returns empty string on failure)."""
    if not token:
        return ''
    try:
        return cipher.decrypt(token.encode()).decode().strip()
    except Exception:
        return ''


# ——— Blueprint Setup ———
web_email_bp = Blueprint('email', __name__, template_folder='templates')


def get_email_settings():
    """
    Fetch SMTP settings from the settings table,
    decrypt password, and return (host, port, user, pass).
    """
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

    host, port, user, encrypted_pw = row

    # Validation
    if not all([host, port, user, encrypted_pw]):
        raise ValueError("Missing one or more SMTP settings in the settings table.")

    try:
        port = int(port)
    except ValueError:
        raise ValueError(f"Invalid outgoing_port: {port!r}")

    pw = decrypt_value(encrypted_pw)
    if not pw:
        raise ValueError("Failed to decrypt the outgoing email password.")

    return host, port, user, pw


def send_email(to_email: str, subject: str, body: str):
    """Send an email using the SMTP credentials from the database."""
    try:
        host, port, user, pw = get_email_settings()

        # Connect & secure
        if port == 465:
            server = smtplib.SMTP_SSL(host, port)
        else:
            server = smtplib.SMTP(host, port)
            server.ehlo()
            server.starttls()
            server.ehlo()

        server.login(user, pw)

        # Compose the email
        msg = MIMEMultipart()
        msg['From'] = user
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        # Send the email
        server.sendmail(user, to_email, msg.as_string())
        server.quit()

        flash("Email sent successfully!", "success")

    except Exception as e:
        flash(f"Failed to send email: {e}", "error")


# ——— Routes ———

@web_email_bp.route('/send-email', methods=['GET', 'POST'])
def send_email_route():
    """Route to send an email through Flask and trigger email via SMTP settings."""
    if request.method == 'POST':
        try:
            to_email = request.form['to_email']
            subject = request.form['subject']
            body = request.form['body']

            if not to_email or not subject or not body:
                raise ValueError("All fields are required.")

            # Call the email sending function
            send_email(to_email, subject, body)

            return jsonify({"message": "Email sent successfully!"}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 400
    else:
        # Render the email form template if it's a GET request
        return render_template('send_email.html')
