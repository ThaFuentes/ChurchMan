import sqlite3
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, abort, jsonify
from db_handler import get_db_connection
from functools import wraps
from datetime import datetime
from log_changes import log_change  # assuming log_change is defined in your 'log_changes' module

announcements_bp = Blueprint('announcements', __name__)

# Roles allowed to create/edit/delete
REQUIRED_ROLES = ['Admin', 'Owner', 'Staff']


def role_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = session.get('user_id')
        user_role = session.get('user_role')
        if not user_id or user_role not in REQUIRED_ROLES:
            abort(403)
        return f(*args, **kwargs)

    return decorated_function


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)

    return decorated


@announcements_bp.route('/', methods=['GET'])
@login_required
def view_announcements():
    search_query = request.args.get('q', '').strip()

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT a.id, a.title, a.content, a.user_id,
               a.created_at, a.effective_date, a.expiration_date, a.comments_enabled, a.is_active,
               u.username AS creator_username
        FROM announcements a
        LEFT JOIN users u ON a.created_by = u.id
        WHERE a.title LIKE ? OR a.content LIKE ? OR u.username LIKE ?
        ORDER BY a.created_at DESC
    """, (f'%{search_query}%', f'%{search_query}%', f'%{search_query}%'))

    rows = cursor.fetchall()

    announcements = []
    for a in rows:
        aid = a['id']
        cursor.execute("""
            SELECT ac.id, ac.comment, ac.date_added, u.username
            FROM announcement_comments ac
            JOIN users u ON ac.user_id = u.id
            WHERE ac.announcement_id = ?
            ORDER BY ac.date_added ASC
        """, (aid,))
        comments = cursor.fetchall()

        announcements.append({
            'id': aid,
            'title': a['title'],
            'content': a['content'],
            'user_id': a['user_id'],
            'created_at': a['created_at'],
            'effective_date': a['effective_date'],
            'expiration_date': a['expiration_date'],
            'comments_enabled': a['comments_enabled'],
            'is_active': a['is_active'],  # Include the active status in the data
            'creator_username': a['creator_username'],
            'comments': comments,
            'comment_count': len(comments)
        })

    conn.close()

    log_change(
        user_id=session['user_id'],
        action='view',
        target_username='Announcements Page',
        change_details='Viewed announcements list'
    )

    return render_template('announcements.html', announcements=announcements)


@announcements_bp.route('/<int:ann_id>/comment', methods=['POST'])
@login_required
def add_comment(ann_id):
    text = request.form.get('comment', '').strip()
    if not text:
        flash('Comment cannot be empty.', 'error')
        return redirect(url_for('announcements.view_announcements') + f"#details-{ann_id}")

    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.utcnow().isoformat()
    cursor.execute("""
        INSERT INTO announcement_comments
            (announcement_id, user_id, comment, date_added)
        VALUES (?, ?, ?, ?)
    """, (ann_id, session['user_id'], text, now))
    conn.commit()
    conn.close()

    # Log the comment addition
    log_change(
        user_id=session['user_id'],
        action='create',
        target_id=ann_id,
        target_username='Comment on Announcement',
        change_details=f'Added comment: {text[:30]}...'  # Logs first 30 chars of comment
    )

    flash('Comment added.', 'success')
    return redirect(url_for('announcements.view_announcements') + f"#details-{ann_id}")


@announcements_bp.route('/new', methods=['GET', 'POST'])
@role_required
def create_announcement():
    if request.method == 'POST':
        title = request.form['title'].strip()
        content = request.form['content'].strip()
        effective_date = request.form.get('effective_date') or None
        expiration_date = request.form.get('expiration_date') or None
        comments_enabled = 1 if request.form.get('comments_enabled') == 'on' else 0
        is_active = 1 if request.form.get('is_active') == 'on' else 0
        now = datetime.utcnow().isoformat()
        uid = session['user_id']
        username = session['username']  # Get the logged-in user's username

        if not title or not content:
            flash('Title and content are required.', 'error')
            return redirect(url_for('announcements.create_announcement'))

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO announcements
            (title, content, user_id, created_at, updated_at,
             effective_date, expiration_date, is_active, comments_enabled,
             created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (title, content, uid, now, now,
              effective_date, expiration_date,
              is_active, comments_enabled, uid))
        conn.commit()
        conn.close()

        # Log the announcement creation including who created it
        log_change(
            user_id=uid,
            action='create',
            target_id=session['user_id'],
            target_username=username,  # Log the username of the person creating the announcement
            change_details=f'Created announcement: {title}, created by: {username}'  # Logs the creator's name
        )

        flash('Announcement created successfully.', 'success')
        return redirect(url_for('announcements.view_announcements'))

    return render_template('create_announcement.html')


@announcements_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@role_required
def edit_announcement(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM announcements WHERE id = ?", (id,))
    a = cursor.fetchone()
    if not a:
        conn.close()
        abort(404)

    if request.method == 'POST':
        title = request.form['title'].strip()
        content = request.form['content'].strip()
        effective_date = request.form.get('effective_date') or None
        expiration_date = request.form.get('expiration_date') or None
        comments_enabled = 1 if request.form.get('comments_enabled') == 'on' else 0
        is_active = 1 if request.form.get('is_active') == 'on' else 0
        now = datetime.utcnow().isoformat()
        uid = session['user_id']

        if not title or not content:
            flash('Title and content are required.', 'error')
            return redirect(url_for('announcements.edit_announcement', id=id))

        cursor.execute("""
            UPDATE announcements
            SET title=?, content=?, updated_at=?, effective_date=?,
                expiration_date=?, is_active=?, comments_enabled=?, updated_by=?
            WHERE id=?
        """, (title, content, now, effective_date, expiration_date,
              is_active, comments_enabled, uid, id))
        conn.commit()
        conn.close()

        # Log the announcement update
        log_change(
            user_id=session['user_id'],
            action='update',
            target_id=id,
            target_username=title,
            change_details=f'Updated announcement: {title}'
        )

        flash('Announcement updated.', 'success')
        return redirect(url_for('announcements.view_announcements'))

    conn.close()
    return render_template('edit_announcement.html', announcement=a)


@announcements_bp.route('/<int:id>/delete', methods=['POST'])
@role_required
def delete_announcement(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM announcements WHERE id=?", (id,))  # Delete the announcement entirely
    conn.commit()
    conn.close()

    # Log the deletion
    log_change(
        user_id=session['user_id'],
        action='delete',
        target_id=id,
        target_username='Announcement Deleted',
        change_details=f'Deleted announcement with id: {id}'
    )

    flash('Announcement deleted permanently.', 'success')
    return redirect(url_for('announcements.view_announcements'))


@announcements_bp.route('/search', methods=['GET'])
@login_required
def search_announcements():
    search_query = request.args.get('q', '').strip()
    is_active = request.args.get('is_active')  # Get the filter for active/inactive announcements

    # Build the query based on search and filter criteria
    query = """
        SELECT a.id, a.title, a.content, a.user_id,
               a.created_at, a.effective_date, a.expiration_date, a.comments_enabled, a.is_active,
               u.username AS creator_username
        FROM announcements a
        LEFT JOIN users u ON a.created_by = u.id
        WHERE (a.title LIKE ? OR a.content LIKE ? OR u.username LIKE ?)
    """

    # Add condition for active/inactive filter
    if is_active is not None:
        query += " AND a.is_active = ?"

    query += " ORDER BY a.created_at DESC"

    conn = get_db_connection()
    cursor = conn.cursor()

    if is_active is not None:
        cursor.execute(query, (f'%{search_query}%', f'%{search_query}%', f'%{search_query}%', is_active))
    else:
        cursor.execute(query, (f'%{search_query}%', f'%{search_query}%', f'%{search_query}%'))

    rows = cursor.fetchall()

    announcements = []
    for a in rows:
        aid = a['id']
        cursor.execute("""
            SELECT ac.id, ac.comment, ac.date_added, u.username
            FROM announcement_comments ac
            JOIN users u ON ac.user_id = u.id
            WHERE ac.announcement_id = ?
            ORDER BY ac.date_added ASC
        """, (aid,))
        comments = cursor.fetchall()

        announcements.append({
            'id': aid,
            'title': a['title'],
            'content': a['content'],
            'user_id': a['user_id'],
            'created_at': a['created_at'],
            'effective_date': a['effective_date'],
            'expiration_date': a['expiration_date'],
            'comments_enabled': a['comments_enabled'],
            'is_active': a['is_active'],
            'creator_username': a['creator_username'],
            'comments': comments,
            'comment_count': len(comments)
        })

    conn.close()

    return jsonify(announcements)
