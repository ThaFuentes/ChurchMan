import sqlite3
from flask import Blueprint, render_template, request, redirect, \
    url_for, flash, session, abort, jsonify
from collections import defaultdict
from datetime import datetime
from functools import wraps
from db_handler import get_db_connection

prayer_bp = Blueprint('prayer', __name__)


# ----------------------------------------------------
# Helpers
# ----------------------------------------------------
def log_change(user_id, action, target_id=None, target_name=None, change_details=None):
    """Insert an audit record into change_records."""
    if not user_id:
        return
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        '''
        INSERT INTO change_records
          (user_id, action, target_id, target_username, change_details)
        VALUES (?, ?, ?, ?, ?)
        ''',
        (user_id, action, target_id, target_name, change_details)
    )
    conn.commit()
    conn.close()


def role_required(required_roles):
    """Decorator to restrict access based on session['user_role']."""

    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if 'user_id' not in session or session.get('user_role') not in required_roles:
                abort(403)
            return f(*args, **kwargs)

        return wrapped

    return decorator


# ----------------------------------------------------
# 1) View all prayer requests
# ----------------------------------------------------
@prayer_bp.route('/')
@role_required(['Member', 'Staff', 'Admin', 'Owner'])
def prayers():
    user_id = session['user_id']
    conn = get_db_connection()

    # Fetch requests
    rows = conn.execute('''
        SELECT
            p.id,
            p.title,
            p.description,
            p.date_posted,
            p.user_id        AS creator_id,
            u.first_name     AS creator_first_name,
            u.last_name      AS creator_last_name
        FROM prayers p
        JOIN users u ON p.user_id = u.id
        ORDER BY p.date_posted DESC
    ''').fetchall()

    prayers_by_date = defaultdict(list)
    for row in rows:
        prayer = dict(row)

        # Fetch contributions
        added = conn.execute('''
            SELECT
                pa.id,
                pa.prayer,
                pa.date_added,
                u.first_name,
                u.last_name
            FROM prayers_added pa
            JOIN users u ON pa.user_id = u.id
            WHERE pa.prayer_request_id = ?
            ORDER BY pa.date_added
        ''', (prayer['id'],)).fetchall()

        prayer['added_prayers'] = [
            {
                'id': p['id'],
                'prayer': p['prayer'],
                'date_added': p['date_added'],
                'first_name': p['first_name'],
                'last_name': p['last_name']
            }
            for p in added
        ]
        prayer['response_count'] = len(prayer['added_prayers'])
        prayer['last_responder'] = prayer['added_prayers'][-1] if prayer['added_prayers'] else None

        # Group by date
        try:
            d = datetime.strptime(prayer['date_posted'], '%Y-%m-%d').date()
            prayers_by_date[d].append(prayer)
        except ValueError:
            flash(f"Invalid date format for request: {prayer['title']}")

    conn.close()

    # Log view
    log_change(
        user_id=user_id,
        action='view',
        target_name='Prayer Requests Page',
        change_details='Viewed all prayer requests'
    )

    return render_template('prayers.html', prayers_by_date=prayers_by_date)


# ----------------------------------------------------
# 2) Add a new prayer request
# ----------------------------------------------------
@prayer_bp.route('/add', methods=['GET', 'POST'])
@role_required(['Member', 'Staff', 'Admin', 'Owner'])
def add_prayer_request():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        user_id = session['user_id']

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO prayers
              (title, description, user_id, date_posted)
            VALUES (?, ?, ?, DATE('now'))
        ''', (title, description, user_id))
        prayer_id = cursor.lastrowid
        conn.commit()
        conn.close()

        # Log creation
        log_change(
            user_id=user_id,
            action='create',
            target_id=prayer_id,
            target_name=title,
            change_details=f"Posted prayer request: {title}"
        )

        flash('Prayer request added successfully!')
        return redirect(url_for('prayer.prayers'))

    return render_template('add_prayer.html')


# ----------------------------------------------------
# 3) Add a prayer to an existing request
# ----------------------------------------------------
@prayer_bp.route('/add_prayer/<int:prayer_request_id>', methods=['POST'])
@role_required(['Member', 'Staff', 'Admin', 'Owner'])
def add_prayer_to_request(prayer_request_id):
    prayer_text = request.form.get('prayer', '').strip()
    user_id = session['user_id']

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO prayers_added
          (prayer_request_id, user_id, prayer, date_added)
        VALUES (?, ?, ?, DATE('now'))
    ''', (prayer_request_id, user_id, prayer_text))
    added_id = cursor.lastrowid
    conn.commit()
    conn.close()

    # Log contribution
    log_change(
        user_id=user_id,
        action='contribute',
        target_id=prayer_request_id,
        target_name=prayer_text[:50],  # first 50 chars
        change_details='Added prayer to request'
    )

    flash('Your prayer has been added.')
    return redirect(url_for('prayer.prayers'))


# ----------------------------------------------------
# 4) Edit a prayer request
# ----------------------------------------------------
@prayer_bp.route('/edit_prayer/<int:prayer_id>', methods=['GET', 'POST'])
@role_required(['Member', 'Staff', 'Admin', 'Owner'])
def edit_prayer(prayer_id):
    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM prayers WHERE id = ?', (prayer_id,))
    prayer = cursor.fetchone()

    if not prayer:
        conn.close()
        flash('Prayer request not found.')
        return redirect(url_for('prayer.prayers'))

    # Permissions
    creator_id = prayer['user_id']
    user_role = session.get('user_role')
    if user_id != creator_id:
        if user_role == 'Staff':
            cursor.execute('SELECT role FROM users WHERE id = ?', (creator_id,))
            creator_role = cursor.fetchone()[0]
            if creator_role != 'Member':
                conn.close()
                flash('Not allowed to edit this request.')
                return redirect(url_for('prayer.prayers'))
        elif user_role not in ['Admin', 'Owner']:
            conn.close()
            flash('Not allowed to edit this request.')
            return redirect(url_for('prayer.prayers'))

    if request.method == 'POST':
        new_title = request.form.get('title', '').strip()
        new_description = request.form.get('description', '').strip()
        cursor.execute('''
            UPDATE prayers
            SET title = ?, description = ?, date_posted = DATE('now')
            WHERE id = ?
        ''', (new_title, new_description, prayer_id))
        conn.commit()
        conn.close()

        # Log update
        log_change(
            user_id=user_id,
            action='update',
            target_id=prayer_id,
            target_name=new_title,
            change_details='Updated prayer request'
        )

        flash('Prayer request updated successfully!')
        return redirect(url_for('prayer.prayers'))

    conn.close()
    return render_template('edit_prayer.html', prayer=prayer)


# ----------------------------------------------------
# 5) Delete a prayer request
# ----------------------------------------------------
@prayer_bp.route('/delete/<int:prayer_request_id>', methods=['POST'])
@role_required(['Admin', 'Owner'])
def delete_prayer_request(prayer_request_id):
    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor()

    # Fetch title for logging
    cursor.execute('SELECT title FROM prayers WHERE id = ?', (prayer_request_id,))
    row = cursor.fetchone()
    title = row['title'] if row else None

    cursor.execute('DELETE FROM prayers WHERE id = ?', (prayer_request_id,))
    conn.commit()
    conn.close()

    # Log deletion
    log_change(
        user_id=user_id,
        action='delete',
        target_id=prayer_request_id,
        target_name=title,
        change_details='Deleted prayer request'
    )

    flash('Prayer request deleted successfully.')
    return redirect(url_for('prayer.prayers'))


# ----------------------------------------------------
# 6) Delete an individual prayer
# ----------------------------------------------------
@prayer_bp.route('/delete_prayer/<int:prayer_id>', methods=['POST'])
@role_required(['Member', 'Staff', 'Admin', 'Owner'])
def delete_prayer(prayer_id):
    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('SELECT prayer, user_id FROM prayers_added WHERE id = ?', (prayer_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        flash('Prayer not found.')
        return redirect(url_for('prayer.prayers'))

    prayer_text, owner_id = row['prayer'], row['user_id']
    user_role = session.get('user_role')
    if user_id != owner_id and user_role not in ['Admin', 'Owner']:
        conn.close()
        flash('Not allowed to delete this prayer.')
        return redirect(url_for('prayer.prayers'))

    cursor.execute('DELETE FROM prayers_added WHERE id = ?', (prayer_id,))
    conn.commit()
    conn.close()

    # Log deletion
    log_change(
        user_id=user_id,
        action='delete',
        target_id=prayer_id,
        target_name=prayer_text[:50],
        change_details='Deleted individual prayer'
    )

    flash('Prayer deleted successfully.')
    return redirect(url_for('prayer.prayers'))


@prayer_bp.route('/search')
@role_required(['Member', 'Staff', 'Admin', 'Owner'])
def search_prayers():
    q = request.args.get('q', '').strip()
    has_responses = request.args.get('has_responses', None)

    like_q = f'%{q}%'
    sql = '''
      SELECT
        p.id,
        p.title,
        p.description,
        p.date_posted,
        p.user_id       AS creator_id,
        u.first_name    AS creator_first,
        u.last_name     AS creator_last,
        (SELECT COUNT(*) FROM prayers_added pa
           WHERE pa.prayer_request_id = p.id
        ) AS response_count
      FROM prayers p
      JOIN users u ON p.user_id = u.id
      WHERE (p.title       LIKE ?
          OR p.description LIKE ?
          OR u.first_name  LIKE ?
          OR u.last_name   LIKE ?
      )
    '''
    params = [like_q, like_q, like_q, like_q]

    if has_responses == '1':
        sql += ' AND response_count > 0'
    elif has_responses == '0':
        sql += ' AND response_count = 0'

    sql += ' ORDER BY p.date_posted DESC'

    conn = get_db_connection()
    rows = conn.execute(sql, params).fetchall()
    conn.close()

    # serialize to list of dicts
    results = []
    for r in rows:
        d = dict(r)
        # optionally include description snippet or creator name
        d['creator_name'] = f"{r['creator_first']} {r['creator_last']}"
        results.append(d)
    return jsonify(results)
