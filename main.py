from flask import Flask, render_template, redirect, url_for, request, session, flash, abort
import sqlite3
import re
from werkzeug.security import generate_password_hash, check_password_hash
from members_directory import members_bp  # Import the blueprint for members directory
from donations import donations_bp  # Import the blueprint for donations
from event import event_bp  # Import the blueprint for events
from settings import settings_bp  # Import the blueprint for settings
from functools import wraps
import random
import string
from flask_mail import Mail, Message

app = Flask(__name__)
app.secret_key = 'your_secret_key'

app.config['MAIL_SERVER'] = 'smtp.zoho.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USE_TLS'] = False  # Disable TLS since SSL is used
app.config['MAIL_USE_SSL'] = True  # Enable SSL
app.config['MAIL_USERNAME'] = ''
app.config['MAIL_PASSWORD'] = ''
app.config['MAIL_DEFAULT_SENDER'] = 'churchfreelymanagementsystem@zohomail.com'

mail = Mail(app)  # Initialize the Mail object
DATABASE = 'church_management.db'


# Function to connect to the database
def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


# Initialize the database and create necessary tables
def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Create users table if it doesn't exist
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            email TEXT UNIQUE,
            phone TEXT,
            address TEXT,
            username TEXT UNIQUE,
            password TEXT,
            role TEXT NOT NULL,
            accepts_emails BOOLEAN,
            created_by INTEGER,
            last_edited_by INTEGER
        )
    ''')

    # Create donations table if it doesn't exist
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS donations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            amount REAL NOT NULL,
            date TEXT NOT NULL,
            method TEXT NOT NULL,
            notes TEXT
        )
    ''')

    # Create change records table if it doesn't exist
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS change_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT NOT NULL,
            target_id INTEGER,
            target_username TEXT,
            change_details TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    ''')

    # Create events table if it doesn't exist
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_name TEXT NOT NULL,
            event_date TEXT NOT NULL,
            event_time TEXT NOT NULL,
            location TEXT,
            description TEXT,
            speaker_host TEXT,
            special_guests TEXT,
            theme TEXT,
            agenda TEXT,
            registration_info TEXT,
            cost_fees REAL,
            contact_info TEXT,
            childcare_availability TEXT,
            accessibility TEXT,
            promotional_materials TEXT,
            volunteer_opportunities TEXT,
            parking_info TEXT,
            dress_code TEXT,
            food_beverages TEXT,
            event_sponsor TEXT,
            social_media_hashtag TEXT,
            donation_info TEXT,
            safety_protocols TEXT,
            follow_up TEXT,
            event_coordinator TEXT,
            announcements_reminders TEXT,
            feedback_form TEXT,
            live_streaming_details TEXT,
            event_objectives TEXT
        )
    ''')

    # Create settings table if it doesn't exist without inserting any default values
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            export_location TEXT,
            sermon_folder_location TEXT,
            church_name TEXT,
            tax_status TEXT,
            address TEXT,
            phone_number TEXT,
            pastor TEXT,
            icon_path TEXT,
            email_server TEXT,
            email_port INTEGER,
            smtp_server TEXT,
            smtp_port INTEGER,
            email_mode TEXT,
            email_address TEXT,
            email_password TEXT
        )
    ''')

    # No insertion of default settings

    conn.close()


# Function to check if an Owner exists
def owner_exists():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM users WHERE role = ?', ('Owner',))
    count = cursor.fetchone()[0]
    conn.close()
    return count > 0


# Function to log changes with detailed information
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
def role_required(required_role):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session or session.get('user_role') not in required_role:
                abort(403)  # Forbidden
            return f(*args, **kwargs)

        return decorated_function

    return decorator


@app.route('/')
def index():
    if owner_exists():
        return redirect(url_for('login'))
    else:
        return redirect(url_for('setup'))


@app.route('/setup', methods=['GET', 'POST'])
def setup():
    if owner_exists():
        return redirect(url_for('login'))

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
        return redirect(url_for('login'))

    return render_template('setup.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if not owner_exists():
        return redirect(url_for('setup'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Automatically deny login if username or password is empty
        if not username or not password:
            flash('Invalid credentials. Please try again.')
            return redirect(url_for('login'))

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
        user = cursor.fetchone()
        conn.close()

        if user and check_password_hash(user[7], password):
            session['user_id'] = user[0]
            session['username'] = user[6]
            session['user_role'] = user[8]  # Capture user role in session
            # Log the login action
            log_change(user_id=user[0], action='login', change_details='User logged in.')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid credentials. Please try again.')

    return render_template('login.html')


@app.route('/request-reset-password', methods=['GET', 'POST'])
def request_reset_password():
    if request.method == 'POST':
        email = request.form['email']

        # Check if the email exists in the database
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT id, username FROM users WHERE email = ?', (email,))
        user = cursor.fetchone()

        if user:
            # Generate a 10-digit reset code
            reset_code = ''.join(random.choices(string.digits, k=10))

            # Hash the reset code before storing it as a password
            hashed_reset_code = generate_password_hash(reset_code)

            # Update the user's password in the database with the hashed reset code
            cursor.execute('UPDATE users SET password = ? WHERE id = ?', (hashed_reset_code, user['id']))
            conn.commit()
            conn.close()

            # Send an email with the reset code
            msg = Message('Password Reset Request', recipients=[email])
            msg.body = f'Your password has been reset. Use the following code to log in: {reset_code}\nPlease change your password after logging in.'
            mail.send(msg)

            flash('A reset code has been sent to your email.')
            return redirect(url_for('login'))
        else:
            conn.close()
            flash('Email address not found. Please check and try again.')
            return redirect(url_for('request_reset_password'))

    return render_template('request_reset_password.html')


@app.route('/request-reset-password')
def request_reset_page():
    return render_template('request_reset_password.html')


@app.route('/forgot-username', methods=['GET', 'POST'])
def forgot_username():
    if request.method == 'POST':
        email = request.form['email']

        # Check if the email exists in the database
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT username FROM users WHERE email = ?', (email,))
        user = cursor.fetchone()
        conn.close()

        if user:
            # Send an email with the username
            msg = Message('Your Username', recipients=[email])
            msg.body = f'Your username is: {user["username"]}'
            mail.send(msg)

            flash('Your username has been sent to your email.')
        else:
            flash('Email address not found. Please check and try again.')

        return redirect(url_for('login'))  # Redirect to login after the email is sent

    return render_template('forgot_username.html')


@app.route('/dashboard')
@role_required(['Admin', 'Owner'])
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT role FROM users WHERE id = ?', (session['user_id'],))
    role = cursor.fetchone()[0]
    conn.close()

    return render_template('dashboard.html', username=session['username'], role=role)


@app.route('/change-records')
@role_required(['Owner'])
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


# Route to delete an individual record
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


# Route to confirm deletion of all records
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


@app.route('/logout')
def logout():
    user_id = session.get('user_id')
    if user_id:
        # Log the logout action
        log_change(user_id=user_id, action='logout', change_details='User logged out.')
    session.clear()
    return redirect(url_for('login'))


# Function to clear all tables in the database
def clear_all_tables():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Clear each table
    cursor.execute('DELETE FROM change_records')
    #    cursor.execute('DELETE FROM donations')
    cursor.execute('DELETE FROM events')
    #    cursor.execute('DELETE FROM users')
    cursor.execute('DELETE FROM settings')

    conn.commit()
    conn.close()

    print("All tables have been cleared.")


# Uncomment the line below to clear all tables when running the script
# clear_all_tables()

# Register the blueprints
app.register_blueprint(members_bp, url_prefix='/members')  # Registering the members directory blueprint
app.register_blueprint(donations_bp, url_prefix='/donations')  # Registering the donations blueprint
app.register_blueprint(event_bp, url_prefix='/events')  # Registering the events blueprint
app.register_blueprint(settings_bp, url_prefix='/settings')  # Registering the settings blueprint

if __name__ == '__main__':
    init_db()  # Initialize the database and create tables if they don't exist
    app.run(debug=False, host='0.0.0.0')
