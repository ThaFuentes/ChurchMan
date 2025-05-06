from flask import Blueprint, render_template, request, redirect, url_for, flash, session, abort, jsonify
import sqlite3, os
from cryptography.fernet import Fernet
from functools import wraps

# ————— KEY MANAGEMENT —————
KEYFILE = os.path.join(os.path.dirname(__file__), 'config_data.bin')  # Obfuscated key file name
ENV_KEY = os.environ.get('APP_SECRET')  # Obfuscated environment variable name

# Check for key in environment variable or file, or generate a new one
if ENV_KEY:
    key = ENV_KEY.encode('utf-8')  # Convert to bytes
elif os.path.exists(KEYFILE):
    with open(KEYFILE, 'rb') as f:
        key = f.read()
else:
    # If no key exists, generate a secure one and store it
    key = Fernet.generate_key()
    with open(KEYFILE, 'wb') as f:
        f.write(key)  # Store the key securely in the file

cipher = Fernet(key)  # Create cipher suite with the generated key


# ————— ENCRYPTION / DECRYPTION FUNCTIONS —————
def encrypt_value(plaintext: str) -> str:
    """Encrypt the provided value using the stored key."""
    if not plaintext:
        return ''
    return cipher.encrypt(plaintext.encode()).decode()


def decrypt_value(token: str) -> str:
    """Decrypt the provided value using the stored key."""
    if not token:
        return ''
    try:
        return cipher.decrypt(token.encode()).decode()
    except Exception as e:
        print(f"Error decrypting value: {e}")
        return ''  # In case decryption fails


# ————— BLUEPRINT SETUP —————
settings_bp = Blueprint('settings', __name__, template_folder='templates')
DATABASE = 'church_management.db'


def get_db_connection():
    """Establish a database connection."""
    conn = sqlite3.connect(DATABASE, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def log_change(user_id, action, target_id=None, target_username=None, change_details=None):
    """Log changes in the system."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""
        INSERT INTO change_records
          (user_id, action, target_id, target_username, change_details)
        VALUES (?, ?, ?, ?, ?)
    """, (user_id, action, target_id, target_username, change_details))
    conn.commit()
    conn.close()


def role_required(allowed_roles):
    """Ensure the user has the correct role."""
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if 'user_id' not in session or session.get('user_role') not in allowed_roles:
                abort(403)
            return f(*args, **kwargs)

        return wrapped

    return decorator


# ————— SCHEMA ENSURE —————
def init_settings():
    """Initialize the settings table if not exists."""
    conn = get_db_connection()
    c = conn.cursor()

    # Create or alter settings table to include email fields
    c.execute("""
    CREATE TABLE IF NOT EXISTS settings (
      id                     INTEGER PRIMARY KEY AUTOINCREMENT,
      export_location        TEXT    NOT NULL,
      church_name            TEXT,
      tax_status             TEXT,
      address                TEXT,
      phone_number           TEXT,
      pastor                 TEXT,
      icon_path              TEXT,
      incoming_protocol      TEXT,
      incoming_server        TEXT,
      incoming_port          INTEGER,
      incoming_encryption    TEXT,
      incoming_username      TEXT,
      incoming_password      TEXT,
      outgoing_server        TEXT,
      outgoing_port          INTEGER,
      outgoing_encryption    TEXT,
      outgoing_username      TEXT,
      outgoing_password      TEXT
    );
    """)

    # Add missing columns if any
    existing = {r['name'] for r in c.execute("PRAGMA table_info(settings)").fetchall()}
    for col, col_type in [
        ('incoming_protocol', 'TEXT'), ('incoming_server', 'TEXT'), ('incoming_port', 'INTEGER'),
        ('incoming_encryption', 'TEXT'), ('incoming_username', 'TEXT'), ('incoming_password', 'TEXT'),
        ('outgoing_server', 'TEXT'), ('outgoing_port', 'INTEGER'), ('outgoing_encryption', 'TEXT'),
        ('outgoing_username', 'TEXT'), ('outgoing_password', 'TEXT')
    ]:
        if col not in existing:
            c.execute(f"ALTER TABLE settings ADD COLUMN {col} {col_type};")

    # Ensure single row exists
    c.execute("SELECT COUNT(*) AS cnt FROM settings")
    if c.fetchone()['cnt'] == 0:
        c.execute("""
          INSERT INTO settings
            (export_location, church_name, tax_status, address, phone_number, pastor, icon_path)
          VALUES (?, ?, ?, ?, ?, ?, ?)
        """, ('/default/path/', '', '', '', '', '', ''))

    conn.commit()
    conn.close()


# ————— ROUTES —————
@settings_bp.route('/general', methods=['GET', 'POST'])
@role_required(['Admin', 'Owner'])
def general_settings():
    """Handle general settings page."""
    init_settings()
    conn = get_db_connection()
    c = conn.cursor()

    if request.method == 'POST':
        form = request.form

        # Export Location
        if 'export_location' in form and 'church_name' not in form:
            c.execute("UPDATE settings SET export_location = ?", (form['export_location'],))
            conn.commit()
            log_change(session['user_id'], 'update_export_location', change_details=form['export_location'])
            flash('Export location updated.', 'success')
            conn.close()
            return redirect(url_for('settings.general_settings'))

        # Church Info
        if 'church_name' in form:
            vals = [form.get(k, '') for k in ('church_name', 'tax_status', 'address', 'phone_number', 'pastor')]
            c.execute("UPDATE settings SET church_name=?, tax_status=?, address=?, phone_number=?, pastor=?", vals)
            conn.commit()
            log_change(session['user_id'], 'update_church_info', change_details='church info')
            flash('Church information updated.', 'success')
            conn.close()
            return redirect(url_for('settings.general_settings'))

        # Email Settings (Encrypting sensitive data)
        enc = lambda p: encrypt_value(form.get(p, ''))
        vals = [
            form.get('incoming_protocol', ''), form.get('incoming_server', ''), int(form.get('incoming_port') or 0),
            form.get('incoming_encryption', ''),
            enc('incoming_username'), enc('incoming_password'),
            form.get('outgoing_server', ''), int(form.get('outgoing_port') or 0), form.get('outgoing_encryption', ''),
            enc('outgoing_username'), enc('outgoing_password')
        ]
        c.execute("""
          UPDATE settings SET
            incoming_protocol=?, incoming_server=?, incoming_port=?, incoming_encryption=?, incoming_username=?, incoming_password=?,
            outgoing_server=?, outgoing_port=?, outgoing_encryption=?, outgoing_username=?, outgoing_password=?
          WHERE id=1
        """, vals)

        conn.commit()
        log_change(session['user_id'], 'update_email_settings', change_details='incoming+outgoing')
        flash('Email settings updated.', 'success')
        conn.close()
        return redirect(url_for('settings.general_settings'))

    # GET: fetch settings
    row = conn.execute("SELECT * FROM settings LIMIT 1").fetchone()
    conn.close()
    if not row:
        abort(500, "Settings missing")

    s = dict(row)
    for key in ('incoming_username', 'incoming_password', 'outgoing_username', 'outgoing_password'):
        s[key] = decrypt_value(s.get(key, ''))

    log_change(session['user_id'], 'view_settings', change_details='viewed settings')
    return render_template('settings.html', settings=s)


@settings_bp.route('/get_settings')
@role_required(['Admin', 'Owner'])
def get_settings():
    """Fetch the settings via API."""
    init_settings()
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM settings LIMIT 1").fetchone()
    conn.close()
    if not row:
        return jsonify(error="No settings found"), 404

    data = dict(row)
    for key in ('incoming_username', 'incoming_password', 'outgoing_username', 'outgoing_password'):
        data[key] = decrypt_value(data.get(key, ''))

    log_change(session['user_id'], 'api_get_settings', change_details='api fetch')
    return jsonify(data)
