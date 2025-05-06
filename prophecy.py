import sqlite3
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from functools import wraps
from db_handler import get_db_connection
from log_changes import log_change

prophecy_bp = Blueprint('prophecy', __name__, url_prefix='/prophecies')


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in first.', 'error')
            return redirect(url_for('auth.login'))
        return fn(*args, **kwargs)

    return wrapper


@prophecy_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add_prophecy():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        desc = request.form.get('description', '').strip()
        if not title or not desc:
            flash('Both title and description are required.', 'error')
            return redirect(url_for('prophecy.add_prophecy'))

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('''
            INSERT INTO prophecies (title, description, user_id, date_posted)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        ''', (title, desc, session['user_id']))
        pid = cur.lastrowid
        conn.commit()
        conn.close()

        log_change(
            user_id=session['user_id'],
            action='create',
            target_id=pid,
            target_username=title,
            change_details=f'Added prophecy: {title}'
        )
        flash('Prophecy added!', 'success')
        return redirect(url_for('prophecy.list_prophecies'))

    return render_template('add_prophecy.html')


@prophecy_bp.route('/', methods=['GET', 'POST'])
@login_required
def list_prophecies():
    # handle inline comment POST
    if request.method == 'POST':
        pid = request.form.get('prophecy_id')
        txt = request.form.get('comment', '').strip()
        if pid and txt:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute(''' 
                INSERT INTO prophecy_comments 
                  (prophecy_id, user_id, comment, date_added)
                VALUES (?,?,?,CURRENT_TIMESTAMP)
            ''', (pid, session['user_id'], txt))
            conn.commit()
            conn.close()
            flash('Comment added.', 'success')
            return redirect(url_for('prophecy.list_prophecies'))

    # handle search query
    search_query = request.args.get('q', '').strip()

    # fetch prophecies + their comments based on search query
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute('''
        SELECT p.id, p.title, p.description, p.date_posted, p.user_id, u.username
        FROM prophecies p
        LEFT JOIN users u ON p.user_id = u.id
        WHERE p.title LIKE ? OR p.description LIKE ? OR u.username LIKE ? OR p.date_posted LIKE ?
        ORDER BY p.date_posted DESC
    ''', (f'%{search_query}%', f'%{search_query}%', f'%{search_query}%', f'%{search_query}%'))

    prows = cur.fetchall()
    prophecy_data = []
    for r in prows:
        p = dict(r)
        cur.execute('''
            SELECT pc.id, pc.user_id, pc.comment, pc.date_added, u.username AS commenter_username
            FROM prophecy_comments pc
            JOIN users u ON pc.user_id = u.id
            WHERE pc.prophecy_id = ?
            ORDER BY pc.date_added ASC
        ''', (p['id'],))
        p['comments'] = [dict(c) for c in cur.fetchall()]
        prophecy_data.append(p)

    conn.close()

    log_change(
        user_id=session['user_id'],
        action='view',
        target_username='Prophecies Page',
        change_details='Viewed prophecies list'
    )

    return render_template('prophecies.html', prophecies=prophecy_data, search_query=search_query)


@prophecy_bp.route('/edit/<int:prophecy_id>', methods=['GET', 'POST'])
@login_required
def edit_prophecy(prophecy_id):
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute('SELECT * FROM prophecies WHERE id=?', (prophecy_id,))
    row = cur.fetchone()
    conn.close()

    if not row:
        flash('Not found.', 'error')
        return redirect(url_for('prophecy.list_prophecies'))

    p = dict(row)
    if p['user_id'] != session['user_id'] and session.get('user_role') not in ['Admin', 'Owner']:
        flash('Not authorized.', 'error')
        return redirect(url_for('prophecy.list_prophecies'))

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        desc = request.form.get('description', '').strip()
        if not title or not desc:
            flash('All fields required.', 'error')
            return redirect(request.url)

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('''
            UPDATE prophecies
            SET title=?, description=?, date_posted=CURRENT_TIMESTAMP
            WHERE id=?
        ''', (title, desc, prophecy_id))
        conn.commit()
        conn.close()

        log_change(
            user_id=session['user_id'],
            action='update',
            target_id=prophecy_id,
            target_username=title,
            change_details=f'Edited prophecy: {title}'
        )
        flash('Prophecy updated.', 'success')
        return redirect(url_for('prophecy.list_prophecies'))

    return render_template('edit_prophecy.html', prophecy=p)


@prophecy_bp.route('/delete/<int:prophecy_id>', methods=['POST'])
@login_required
def delete_prophecy(prophecy_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT title,user_id FROM prophecies WHERE id=?', (prophecy_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        flash('Not found.', 'error')
        return redirect(url_for('prophecy.list_prophecies'))
    title, owner = row
    if owner != session['user_id'] and session.get('user_role') not in ['Admin', 'Owner']:
        conn.close()
        flash('Not authorized.', 'error')
        return redirect(url_for('prophecy.list_prophecies'))

    cur.execute('DELETE FROM prophecies WHERE id=?', (prophecy_id,))
    conn.commit()
    conn.close()

    log_change(
        user_id=session['user_id'],
        action='delete',
        target_id=prophecy_id,
        target_username=title,
        change_details=f'Deleted prophecy: {title}'
    )
    flash('Prophecy removed.', 'success')
    return redirect(url_for('prophecy.list_prophecies'))


@prophecy_bp.route('/comment/edit/<int:prophecy_id>/<int:comment_id>', methods=['POST'])
@login_required
def update_comment(prophecy_id, comment_id):
    text = request.form.get('comment', '').strip()
    if not text:
        flash('Comment cannot be empty.', 'error')
        return redirect(url_for('prophecy.list_prophecies'))

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT user_id FROM prophecy_comments WHERE id=?', (comment_id,))
    owner = cur.fetchone()
    if owner and (owner[0] == session['user_id'] or session.get('user_role') in ['Admin', 'Owner']):
        cur.execute('''
            UPDATE prophecy_comments
            SET comment=?, date_added=CURRENT_TIMESTAMP
            WHERE id=?
        ''', (text, comment_id))
        conn.commit()
        flash('Comment updated.', 'success')
    else:
        flash('Not authorized.', 'error')
    conn.close()
    return redirect(url_for('prophecy.list_prophecies'))


@prophecy_bp.route('/comment/delete/<int:prophecy_id>/<int:comment_id>', methods=['POST'])
@login_required
def delete_comment(prophecy_id, comment_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT user_id FROM prophecy_comments WHERE id=?', (comment_id,))
    owner = cur.fetchone()
    if owner and (owner[0] == session['user_id'] or session.get('user_role') in ['Admin', 'Owner']):
        cur.execute('DELETE FROM prophecy_comments WHERE id=?', (comment_id,))
        conn.commit()
        flash('Comment deleted.', 'success')
    else:
        flash('Not authorized.', 'error')
    conn.close()
    return redirect(url_for('prophecy.list_prophecies'))
