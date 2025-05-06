import sqlite3
from flask import Blueprint, render_template, redirect, url_for, request, session, flash
from db_handler import get_db_connection
from werkzeug.security import generate_password_hash
from functools import wraps

profile_bp = Blueprint('profile', __name__)


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        return fn(*args, **kwargs)
    return wrapper


@profile_bp.route('/', methods=['GET', 'POST'])
@login_required
def profile():
    user_id = session['user_id']

    # Open connection and configure row factory
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Handle profile updates
    if request.method == 'POST':
        first_name     = request.form['first_name'].strip()
        last_name      = request.form['last_name'].strip()
        email          = request.form['email'].strip()
        phone          = request.form['phone'].strip()
        address        = request.form['address'].strip()
        birthday       = request.form.get('birthday', '').strip()          # YYYY-MM-DD
        show_birthday  = 1 if request.form.get('show_birthday') == '1' else 0
        old_password   = request.form.get('old_password')
        new_password   = request.form.get('new_password')
        confirm_pw     = request.form.get('confirm_password')

        if new_password and new_password != confirm_pw:
            flash('New passwords do not match.', 'error')
        else:
            # Update profile fields including birthday and its visibility
            cursor.execute(
                '''
                UPDATE users
                   SET first_name     = ?,
                       last_name      = ?,
                       email          = ?,
                       phone          = ?,
                       address        = ?,
                       birthday       = ?,
                       show_birthday  = ?
                 WHERE id = ?
                ''',
                (first_name, last_name, email, phone, address, birthday, show_birthday, user_id)
            )
            # If user provided both old and new password, update it
            if old_password and new_password:
                hashed_pw = generate_password_hash(new_password)
                cursor.execute(
                    'UPDATE users SET password = ? WHERE id = ?',
                    (hashed_pw, user_id)
                )
            conn.commit()
            flash('Profile updated successfully.', 'success')

    # Load current user
    cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
    user = cursor.fetchone()

    # Incoming pending requests (to me)
    cursor.execute(
        '''
        SELECT fr.id,
               u.first_name || ' ' || u.last_name AS name,
               fr.relation_type
          FROM family_relations fr
          JOIN users u ON fr.user_id = u.id
         WHERE fr.relative_user_id = ?
           AND fr.status = 'pending'
         ORDER BY fr.created_at DESC
        ''',
        (user_id,)
    )
    pending_requests = cursor.fetchall()

    # Approved family (either direction)
    cursor.execute(
        '''
        SELECT fr.id,
               CASE
                 WHEN fr.user_id = ? THEN u2.first_name || ' ' || u2.last_name
                 ELSE u1.first_name || ' ' || u1.last_name
               END AS name,
               fr.relation_type AS relationship
          FROM family_relations fr
     LEFT JOIN users u1 ON fr.user_id = u1.id
     LEFT JOIN users u2 ON fr.relative_user_id = u2.id
         WHERE fr.status = 'approved'
           AND (? IN (fr.user_id, fr.relative_user_id))
         ORDER BY name
        ''',
        (user_id, user_id)
    )
    family = cursor.fetchall()

    # Suggested users: same last name, exclude self & existing relations
    last_name = user['last_name']
    cursor.execute(
        '''
        SELECT u.id,
               u.first_name,
               u.last_name
          FROM users u
     LEFT JOIN family_relations fr
       ON (
            (fr.user_id = :me AND fr.relative_user_id = u.id)
         OR (fr.user_id = u.id AND fr.relative_user_id = :me)
          )
      AND fr.status IN ('pending','approved')
         WHERE u.id <> :me
           AND LOWER(TRIM(u.last_name)) = LOWER(TRIM(:ln))
           AND fr.id IS NULL
         ORDER BY u.first_name, u.last_name
        ''',
        {"me": user_id, "ln": last_name}
    )
    suggested_users = cursor.fetchall()

    conn.close()

    return render_template(
        'profile.html',
        user=user,
        pending_requests=pending_requests,
        family=family,
        suggested_users=suggested_users
    )


@profile_bp.route('/add-family', methods=['POST'])
@login_required
def add_family():
    user_id     = session['user_id']
    relative_id = int(request.form['relative_user_id'])
    relation    = request.form['relationship'].strip()

    if user_id == relative_id:
        flash('You cannot add yourself.', 'error')
        return redirect(url_for('profile.profile'))

    conn   = get_db_connection()
    cursor = conn.cursor()

    # 1) Remove any prior *rejected* requests so you can resend
    cursor.execute("""
        DELETE FROM family_relations
         WHERE ((user_id = ? AND relative_user_id = ?)
             OR  (user_id = ? AND relative_user_id = ?))
           AND status = 'rejected'
    """, (user_id, relative_id, relative_id, user_id))

    # 2) Now prevent only pending or already-approved
    cursor.execute("""
        SELECT 1
          FROM family_relations
         WHERE ((user_id = ? AND relative_user_id = ?)
             OR  (user_id = ? AND relative_user_id = ?))
           AND status IN ('pending','approved')
    """, (user_id, relative_id, relative_id, user_id))

    if cursor.fetchone():
        flash('A pending or approved request already exists.', 'error')
        conn.close()
        return redirect(url_for('profile.profile'))

    # 3) Insert your fresh pending request
    cursor.execute("""
        INSERT INTO family_relations
            (user_id, relative_user_id, relation_type, status)
        VALUES (?, ?, ?, 'pending')
    """, (user_id, relative_id, relation))

    conn.commit()
    conn.close()
    flash('Request sent—awaiting their approval.', 'success')
    return redirect(url_for('profile.profile'))


@profile_bp.route('/approve-family/<int:fr_id>', methods=['POST'])
@login_required
def approve_family(fr_id):
    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        '''
        UPDATE family_relations
           SET status      = 'approved',
               approved_by = ?
         WHERE id = ?
           AND relative_user_id = ?
           AND status = 'pending'
        ''',
        (user_id, fr_id, user_id)
    )
    if cursor.rowcount:
        flash('Family request approved.', 'success')
    else:
        flash('Cannot approve that request.', 'error')

    conn.commit()
    conn.close()
    return redirect(url_for('profile.profile'))


@profile_bp.route('/reject-family/<int:fr_id>', methods=['POST'])
@login_required
def reject_family(fr_id):
    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        '''
        UPDATE family_relations
           SET status = 'rejected'
         WHERE id = ?
           AND relative_user_id = ?
           AND status = 'pending'
        ''',
        (fr_id, user_id)
    )
    if cursor.rowcount:
        flash('Family request rejected.', 'success')
    else:
        flash('Cannot reject that request.', 'error')

    conn.commit()
    conn.close()
    return redirect(url_for('profile.profile'))


@profile_bp.route('/remove-family/<int:fr_id>', methods=['POST'])
@login_required
def remove_family(fr_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        'DELETE FROM family_relations WHERE id = ? AND status = "approved"',
        (fr_id,)
    )
    if cursor.rowcount:
        flash('Family relationship removed.', 'success')
    else:
        flash('Could not remove that relationship.', 'error')

    conn.commit()
    conn.close()
    return redirect(url_for('profile.profile'))
