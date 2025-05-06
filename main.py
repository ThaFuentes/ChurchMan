from flask import Flask, render_template, redirect, url_for, request, session, flash, abort
import re
from werkzeug.security import generate_password_hash, check_password_hash
from members_directory import members_bp  # Import the blueprint for members directory
from donations import donations_bp  # Import the blueprint for donations
from event import event_bp  # Import the blueprint for events
from settings import settings_bp  # Import the blueprint for settings
from auth import auth_bp  # Import the authentication blueprint
from profile import profile_bp  # Import the blueprint for user profiles
from sermons import sermons_bp  # Import the blueprint for sermon uploads
from functools import wraps
import random
import string
from flask_mail import Mail, Message
from db_handler import get_db_connection
from init_db import init_db
from owner_exists import owner_exists
from prayer import prayer_bp
from dashboard import dashboard_bp  # Import the dashboard blueprint
from dreams import dreams_bp  # Import the blueprint for dreams
from prophecy import prophecy_bp  # Import the blueprint for prophecy
from announcements import announcements_bp  # Import the announcements blueprint
from web_email import web_email_bp  # Import the web_email blueprint
from flask_login import LoginManager, current_user  # Import LoginManager

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Initialize the database and create necessary tables
init_db()

# Check if an Owner exists (this may create side effects as needed)
owner_exists()

# Initialize the LoginManager
login_manager = LoginManager()
login_manager.init_app(app)


# Role required decorator
def role_required(required_role):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session or session.get('user_role') not in required_role:
                abort(403)  # Forbidden
            return f(*args, **kwargs)

        return decorated_function

    return decorator


# User loader function for Flask-Login
@login_manager.user_loader
def load_user(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user


@app.route('/')
def index():
    # Check if the owner exists and redirect accordingly
    if owner_exists():
        return redirect(url_for('auth.login'))
    else:
        return redirect(url_for('setup'))


@app.route('/setup', methods=['GET', 'POST'])
def setup():
    if owner_exists():
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        email = request.form['email']
        confirm_email = request.form['confirm_email']
        phone = request.form['phone']
        address = request.form['address']
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        accepts_emails = request.form.get('accepts_emails') == 'Yes'

        # Validate email format
        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            flash('Invalid email format. Please enter a valid email address.')
            return redirect(url_for('setup'))

        # Check if email matches confirmation
        if email != confirm_email:
            flash('Emails do not match. Please enter the same email in both fields.')
            return redirect(url_for('setup'))

        # Check if passwords match
        if password != confirm_password:
            flash('Passwords do not match. Please enter the same password in both fields.')
            return redirect(url_for('setup'))

        hashed_password = generate_password_hash(password)

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO users (first_name, last_name, email, phone, address, username, password, role, accepts_emails)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'Owner', ?)
        ''', (first_name, last_name, email, phone, address, username, hashed_password, accepts_emails))
        conn.commit()
        user_id = cursor.lastrowid
        conn.close()

        # Log the creation of the owner account
        log_change(user_id=user_id, action='create', target_id=user_id, target_username=username,
                   change_details='Created owner account.')

        flash('Owner account created successfully. Please log in.')
        return redirect(url_for('auth.login'))

    return render_template('setup.html')


def log_change(user_id, action, target_id=None, target_username=None, change_details=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO change_records (user_id, action, target_id, target_username, change_details)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, action, target_id, target_username, change_details))
    conn.commit()
    conn.close()


@app.route('/dashboard')
@role_required(['Admin', 'Owner', 'Staff', 'Member'])
def dashboard():
    # Ensure user is logged in
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    conn = get_db_connection()
    cursor = conn.cursor()

    # Get the user role
    cursor.execute('SELECT role FROM users WHERE id = ?', (session['user_id'],))
    role = cursor.fetchone()[0]

    # Birthdays this month
    cursor.execute("""
        SELECT first_name, last_name, birthday
        FROM users
        WHERE show_birthday = 1
          AND strftime('%m', birthday) = strftime('%m', 'now')
        ORDER BY strftime('%d', birthday) ASC
    """)
    birthdays = cursor.fetchall()

    # Upcoming birthdays in next 30 days
    cursor.execute("""
        SELECT first_name, last_name, birthday
        FROM users
        WHERE show_birthday = 1
          AND strftime('%m-%d', birthday)
            BETWEEN strftime('%m-%d', 'now')
                AND strftime('%m-%d', 'now', '+30 days')
        ORDER BY strftime('%m-%d', birthday) ASC
    """)
    birthdays_upcoming = cursor.fetchall()

    # Upcoming Events
    cursor.execute("""
        SELECT event_name AS title,
               event_date || ' ' || event_time AS datetime,
               NULL              AS posted_by
        FROM events
        WHERE event_date >= DATE('now')
        ORDER BY event_date ASC
        LIMIT 5
    """)
    events = cursor.fetchall()

    # Recent Prayer Requests
    cursor.execute("""
        SELECT title,
               date_posted AS datetime,
               NULL        AS posted_by
        FROM prayers
        ORDER BY date_posted DESC
        LIMIT 5
    """)
    prayers = cursor.fetchall()

    # Recent Dreams & Visions
    cursor.execute("""
        SELECT d.title,
               d.date_posted AS datetime,
               u.username    AS posted_by
        FROM dreams d
        LEFT JOIN users u ON d.user_id = u.id
        ORDER BY d.date_posted DESC
        LIMIT 5
    """)
    dreams = cursor.fetchall()

    # Recent Prophecies
    cursor.execute("""
        SELECT p.title,
               p.date_posted AS datetime,
               u.username    AS posted_by
        FROM prophecies p
        LEFT JOIN users u ON p.user_id = u.id
        ORDER BY p.date_posted DESC
        LIMIT 5
    """)
    prophecies = cursor.fetchall()

    # Recent Sermons
    cursor.execute("""
        SELECT s.title,
               s.uploaded_at AS datetime,
               u.username    AS posted_by
        FROM sermons s
        LEFT JOIN users u ON s.uploaded_by = u.id
        ORDER BY s.uploaded_at DESC
        LIMIT 5
    """)
    sermons = cursor.fetchall()

    # Recent Announcements (no alias)
    cursor.execute("""
        SELECT a.title,
               a.created_at,
               u.username   AS posted_by
        FROM announcements a
        LEFT JOIN users u ON a.created_by = u.id
        WHERE a.is_active = 1
        ORDER BY a.created_at DESC
        LIMIT 5
    """)
    announcements = cursor.fetchall()

    conn.close()

    # — Inlined sparkle/sprinkle generation —
    sparkles = []
    for _ in range(20):
        sparkles.append({
            'left_pct': round(random.uniform(0, 100), 1),
            'top_pct': round(random.uniform(0, 100), 1),
            'size_px': random.randint(6, 16),
            'delay_s': round(random.uniform(0, 2), 2),
        })

    return render_template(
        'dashboard.html',
        username=session['username'],
        role=role,
        birthdays=birthdays,
        birthdays_upcoming=birthdays_upcoming,
        events=events,
        prayers=prayers,
        dreams=dreams,
        prophecies=prophecies,
        sermons=sermons,
        announcements=announcements,
        sparkles=sparkles
    )


@app.route('/change-records')
@role_required(['Owner', 'Admin'])
def change_records():
    search_query = request.args.get('search', '')
    sort_by = request.args.get('sort_by', 'timestamp')
    sort_order = request.args.get('sort_order', 'desc')
    page = int(request.args.get('page', 1))
    per_page = 25
    offset = (page - 1) * per_page

    conn = get_db_connection()
    cursor = conn.cursor()

    # Build the base query
    query = '''
        SELECT cr.id, cr.user_id, u.username, cr.action, cr.target_id, cr.target_username, cr.change_details, cr.timestamp
        FROM change_records cr
        JOIN users u ON cr.user_id = u.id
    '''

    # Apply the search filter if there's a search query
    if search_query:
        query += '''
            WHERE cr.user_id LIKE ? 
            OR u.username LIKE ? 
            OR cr.action LIKE ? 
            OR cr.target_id LIKE ? 
            OR cr.target_username LIKE ? 
            OR cr.change_details LIKE ? 
            OR cr.timestamp LIKE ?
        '''
        search_term = f"%{search_query}%"
        params = (search_term,) * 7
    else:
        params = ()

    # Apply sorting and limit for pagination
    query += f' ORDER BY {sort_by} {sort_order.upper()} LIMIT {per_page} OFFSET {offset}'

    cursor.execute(query, params)
    records = cursor.fetchall()

    # Get the total number of records
    cursor.execute('SELECT COUNT(*) FROM change_records')
    total_records = cursor.fetchone()[0]
    total_pages = (total_records + per_page - 1) // per_page

    conn.close()

    next_sort_order = 'asc' if sort_order == 'desc' else 'desc'

    return render_template(
        'change_records.html',
        records=records,
        search_query=search_query,
        sort_by=sort_by,
        sort_order=sort_order,
        next_sort_order=next_sort_order,
        page=page,
        total_pages=total_pages
    )


@app.route('/delete-record/<int:id>', methods=['POST'])
@role_required(['Owner'])
def delete_record(id):
    conn = get_db_connection()
    cursor = conn.cursor()

    # Ensure the record being deleted is not the system message for deleting all records
    cursor.execute('SELECT * FROM change_records WHERE id = ?', (id,))
    record = cursor.fetchone()

    if record and "Deleted all change records" not in record['change_details']:
        cursor.execute('DELETE FROM change_records WHERE id = ?', (id,))
        conn.commit()

    conn.close()
    return redirect(url_for('change_records', page=request.args.get('page', 1)))


@app.route('/delete-all-records', methods=['POST'])
@role_required(['Owner'])
def delete_all_records():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Delete all records except the log of deleting all records
    cursor.execute('''
        DELETE FROM change_records
        WHERE change_details NOT LIKE 'Deleted all change records%'
    ''')
    conn.commit()

    # Log the deletion of all records
    log_change(user_id=session['user_id'], action='delete_all', change_details="Deleted all change records")

    conn.close()
    return redirect(url_for('change_records'))


@app.route('/confirm-delete-all-records', methods=['GET', 'POST'])
@role_required(['Owner'])
def confirm_delete_all_records():
    if request.method == 'POST':
        password = request.form['password']

        # Verify the password
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT password FROM users WHERE id = ?', (session['user_id'],))
        user = cursor.fetchone()

        if user and check_password_hash(user['password'], password):
            # Password is correct, delete all records
            return redirect(url_for('delete_all_records'))
        else:
            flash('Incorrect password. Please try again.')
            return redirect(url_for('confirm_delete_all_records'))

    return render_template('confirm_delete_all_records.html')


def clear_all_tables():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Clear each table
    cursor.execute('DELETE FROM change_records')
    # cursor.execute('DELETE FROM donations')
    cursor.execute('DELETE FROM events')
    # cursor.execute('DELETE FROM users')
    cursor.execute('DELETE FROM settings')

    conn.commit()
    conn.close()

    print("All tables have been cleared.")


# Uncomment the line below to clear all tables when running the script
# clear_all_tables()

# Register the blueprints. Note that auth_bp is registered with the URL prefix '/auth',
# so its routes (login, logout, request-reset-password, forgot-username) will be accessible under /auth.
login_manager.login_view = "auth.login"  # Specify the login route here
app.register_blueprint(prayer_bp, url_prefix='/prayers')
app.register_blueprint(auth_bp, url_prefix='/auth')
app.register_blueprint(profile_bp, url_prefix='/profile')
app.register_blueprint(members_bp, url_prefix='/members')
app.register_blueprint(donations_bp, url_prefix='/donations')
app.register_blueprint(event_bp, url_prefix='/events')
app.register_blueprint(settings_bp, url_prefix='/settings')
app.register_blueprint(dashboard_bp, url_prefix='/dashboard')
app.register_blueprint(sermons_bp, url_prefix='/sermons')
app.register_blueprint(dreams_bp, url_prefix='/dreams')
app.register_blueprint(prophecy_bp, url_prefix='/prophecies')
app.register_blueprint(announcements_bp, url_prefix='/announcements')
app.register_blueprint(web_email_bp, url_prefix='/email')  # You can optionally set a URL prefix

if __name__ == '__main__':
    init_db()  # Initialize the database and create tables if they don't exist
    app.run(debug=False, host='0.0.0.0')
