from flask import Blueprint, render_template, request, redirect, url_for, flash, session, abort, jsonify
import sqlite3
import os
from functools import wraps

# Create a Blueprint for settings
settings_bp = Blueprint('settings', __name__, template_folder='templates')

DATABASE = 'church_management.db'


# Helper function to get a database connection
def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row  # Access columns by name
    return conn


def log_change(user_id, action, target_id=None, target_username=None, change_details=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO change_records (user_id, action, target_id, target_username, change_details)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, action, target_id, target_username, change_details))
    conn.commit()
    conn.close()


# Role required decorator
def role_required(required_roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session or session.get('user_role') not in required_roles:
                abort(403)  # Forbidden
            return f(*args, **kwargs)
        return decorated_function
    return decorator


# Initialize the settings table if it doesn't exist
def init_settings():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Create the settings table if it doesn't exist
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            export_location TEXT NOT NULL,
            church_name TEXT,
            tax_status TEXT,
            address TEXT,
            phone_number TEXT,
            pastor TEXT,
            icon_path TEXT
        )
    ''')

    # Ensure there is a default row in the settings table
    cursor.execute('SELECT COUNT(*) FROM settings')
    if cursor.fetchone()[0] == 0:
        cursor.execute('''
            INSERT INTO settings (
                export_location,
                church_name,
                tax_status,
                address,
                phone_number,
                pastor,
                icon_path
            )
            VALUES ('/default/path/', '', '', '', '', '', '')
        ''')
        conn.commit()

    conn.close()


@settings_bp.route('/general', methods=['GET', 'POST'])
@role_required(['Admin', 'Owner'])
def general_settings():
    init_settings()  # Ensure settings are initialized when the settings page is accessed

    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        # Retrieve form data
        export_location = request.form.get('export_location') or '/default/path/'
        church_name = request.form.get('church_name') or ''
        tax_status = request.form.get('tax_status') or ''
        address = request.form.get('address') or ''
        phone_number = request.form.get('phone_number') or ''
        pastor = request.form.get('pastor') or ''
        icon_file = request.files.get('icon_path')

        icon_path = None
        if icon_file:
            icon_dir = os.path.join('static', 'icons')
            if not os.path.exists(icon_dir):
                os.makedirs(icon_dir)
            icon_path = os.path.join(icon_dir, icon_file.filename)
            icon_file.save(icon_path)
        else:
            icon_path = cursor.execute('SELECT icon_path FROM settings LIMIT 1').fetchone()['icon_path']

        # Update the settings in the database
        try:
            cursor.execute('''
                UPDATE settings
                SET export_location = ?,
                    church_name = ?,
                    tax_status = ?,
                    address = ?,
                    phone_number = ?,
                    pastor = ?,
                    icon_path = ?
            ''', (export_location, church_name, tax_status, address, phone_number, pastor, icon_path))
            conn.commit()
            log_change(user_id=session.get('user_id'), action='update', change_details='Updated settings')
            flash('Settings updated successfully.')
        except Exception as e:
            print(f"Error occurred while updating settings: {e}")
            flash('An error occurred while updating the settings.')

        return redirect(url_for('settings.general_settings'))

    # Fetch the current settings
    cursor.execute('SELECT * FROM settings LIMIT 1')
    settings = cursor.fetchone()

    if settings is None:
        settings = {
            'export_location': '/default/path/',
            'church_name': '',
            'tax_status': '',
            'address': '',
            'phone_number': '',
            'pastor': '',
            'icon_path': ''
        }
        print("No settings found in the database. Using default values.")
    else:
        settings = dict(settings)  # Convert Row object to dictionary for easier handling
        print("Current Settings Fetched from Database:")
        print(settings)

    conn.close()

    return render_template('settings.html', settings=settings)


@settings_bp.route('/get_settings')
@role_required(['Admin', 'Owner'])
def get_settings():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM settings LIMIT 1')
    settings = cursor.fetchone()
    conn.close()

    return jsonify(dict(settings)) if settings else jsonify({"error": "No settings found"})


# Additional settings routes can go here

