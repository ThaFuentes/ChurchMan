# auth.py
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app
from werkzeug.security import generate_password_hash, check_password_hash
from flask_mail import Message
import random
import string
from db_handler import get_db_connection
from log_changes import log_change
from emailer import send_email  # or wherever your send_email function lives

auth_bp = Blueprint('auth', __name__)


# Login Route
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if not username or not password:
            flash('Invalid credentials. Please try again.')
            return render_template('login.html')

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
        user = cursor.fetchone()
        conn.close()

        if user:
            # If account is still pending approval, block login
            if user['role'] == 'pending':
                flash(
                    'Your account is pending approval. Please wait for an administrator to approve your registration.')
                return render_template('login.html')

            # Check if account is banned
            if user['role'] == 'banned':
                flash('Your account has been banned. Please contact support for more information.')
                return render_template('login.html')

            # Check password match
            if check_password_hash(user['password'], password):
                session['user_id'] = user['id']
                session['username'] = user['username']
                session['user_role'] = user['role']

                log_change(
                    user_id=user['id'],
                    action='login',
                    change_details='User logged in.'
                )

                return redirect(url_for('dashboard'))
            else:
                flash('Invalid credentials. Please try again.')
        else:
            flash('Invalid credentials. Please try again.')

    return render_template('login.html')


# Logout Route
@auth_bp.route('/logout')
def logout():
    user_id = session.get('user_id')
    if user_id:
        log_change(
            user_id=user_id,
            action='logout',
            change_details='User logged out.'
        )
    session.clear()
    return redirect(url_for('auth.login'))


# Registration Route
@auth_bp.route('/register', methods=['POST'])
def register():
    first_name = request.form.get('first_name', '').strip()
    last_name = request.form.get('last_name', '').strip()
    email = request.form.get('email', '').strip().lower()
    phone = request.form.get('phone', '').strip()
    address = request.form.get('address', '').strip()
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')
    confirm_password = request.form.get('confirm_password', '')

    # validation
    if not (first_name and last_name and email and username and password):
        flash('All required fields must be filled out.')
        return redirect(url_for('auth.login'))
    if password != confirm_password:
        flash('Passwords do not match.')
        return redirect(url_for('auth.login'))

    hashed_pw = generate_password_hash(password)
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO users (
                first_name, last_name, email, phone,
                address, username, password, role
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            first_name, last_name, email, phone,
            address, username, hashed_pw, 'pending'
        ))
        conn.commit()
        new_id = cursor.lastrowid

        # Notify admins by email
        cursor.execute("SELECT email FROM users WHERE role IN ('Admin', 'Owner')")
        admin_emails = [row['email'] for row in cursor.fetchall()]
        subject = "New User Registration Pending Approval"
        body = (
            f"A new user has registered and is pending approval:\n\n"
            f"Name: {first_name} {last_name}\n"
            f"Username: {username}\n"
            f"Email: {email}\n"
            f"Please review and approve or deny the registration in the admin panel."
        )

        for admin_email in admin_emails:
            try:
                send_email(admin_email, subject, body)
            except Exception as e:
                # Log email sending failure but don't stop registration
                print(f"Failed to send admin notification to {admin_email}: {e}")

        log_change(
            user_id=new_id,
            action='register',
            change_details=f"New user '{username}' registered (pending approval)."
        )
        flash('Registration submitted – pending admin approval.')
    except Exception as e:
        conn.rollback()
        flash(f'Registration failed: {str(e)}')
    finally:
        conn.close()

    return redirect(url_for('auth.login'))


# Request Reset Password Route
@auth_bp.route('/request-reset-password', methods=['GET', 'POST'])
def request_reset_password():
    if request.method == 'POST':
        email = request.form.get('email')
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM users WHERE email = ?', (email,))
        user = cursor.fetchone()

        if user:
            reset_code = ''.join(random.choices(string.digits, k=10))
            hashed_reset_code = generate_password_hash(reset_code)

            cursor.execute(
                'UPDATE users SET password = ? WHERE id = ?',
                (hashed_reset_code, user['id'])
            )
            conn.commit()
            conn.close()

            subject = 'Password Reset Request'
            body = (
                f'Your password has been reset.\n\n'
                f'Temporary Login Code: {reset_code}\n\n'
                'Please change your password after logging in.'
            )

            try:
                send_email(email, subject, body)
                flash('A reset code has been sent to your email.')
            except Exception as e:
                flash(f"Failed to send email: {str(e)}")
        else:
            conn.close()
            flash('Email address not found. Please check and try again.')

        return redirect(url_for('auth.login'))

    return render_template('request_reset_password.html')


# Forgot Username Route
@auth_bp.route('/forgot-username', methods=['GET', 'POST'])
def forgot_username():
    if request.method == 'POST':
        email = request.form.get('email')
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT username FROM users WHERE email = ?', (email,))
        user = cursor.fetchone()
        conn.close()

        if user:
            subject = 'Your Username'
            body = f'Your username is: {user["username"]}'

            try:
                send_email(email, subject, body)
                flash('Your username has been sent to your email.')
            except Exception as e:
                flash(f"Failed to send email: {str(e)}")
        else:
            flash('Email address not found. Please check and try again.')

        return redirect(url_for('auth.login'))

    return render_template('forgot_username.html')
