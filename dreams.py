from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from functools import wraps
from db_handler import get_db_connection
from log_changes import log_change  # existing logging function

# Blueprint for dreams and visions

dreams_bp = Blueprint('dreams', __name__)


def login_required(fn):
    """Decorator to ensure the user is logged in."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in first.', 'error')
            return redirect(url_for('auth.login'))
        return fn(*args, **kwargs)
    return wrapper


@dreams_bp.route('/dreams', methods=['GET', 'POST'])
@login_required
def dreams():
    """
    Display all dreams with optional search,
    show their comments inline, and handle new comment submissions.
    """
    search_query = request.args.get('q', '').strip()

    # Handle new inline comment submissions
    if request.method == 'POST':
        dream_id = request.form.get('dream_id')
        comment_text = request.form.get('comment', '').strip()
        if dream_id and comment_text:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                '''INSERT INTO dream_comments (dream_id, user_id, comment, date_posted)
                   VALUES (?, ?, ?, CURRENT_TIMESTAMP)''',
                (dream_id, session['user_id'], comment_text)
            )
            conn.commit()
            conn.close()
            flash('Your comment has been added.', 'success')
            return redirect(url_for('dreams.dreams', q=search_query))

    # Fetch dreams matching the search
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        '''SELECT d.id, d.user_id, d.title, d.description, d.date_posted,
                  d.is_personal, d.visibility, u.username AS poster_username
           FROM dreams d
           LEFT JOIN users u ON d.user_id = u.id
           WHERE d.title LIKE ? OR d.description LIKE ?
           ORDER BY d.date_posted DESC''',
        (f'%{search_query}%', f'%{search_query}%')
    )
    rows = cursor.fetchall()

    dream_data = []
    for row in rows:
        d = dict(row)
        # load comments for this dream
        cursor.execute(
            '''SELECT dc.id AS id, dc.user_id, dc.comment, dc.date_posted,
                      u.username AS commenter_username
               FROM dream_comments dc
               JOIN users u ON dc.user_id = u.id
               WHERE dc.dream_id = ?
               ORDER BY dc.date_posted ASC''',
            (d['id'],)
        )
        comment_rows = cursor.fetchall()
        d['comments'] = [dict(c) for c in comment_rows]
        dream_data.append(d)

    conn.close()

    # Log that the user viewed the dreams page
    log_change(
        user_id=session['user_id'],
        action='view',
        target_username='Dreams Page',
        change_details='Viewed dreams list'
    )

    return render_template(
        'dreamsandvisions.html',
        dream_data=dream_data,
        search_query=search_query
    )


@dreams_bp.route('/submit_dream', methods=['GET', 'POST'])
@login_required
def submit_dream():
    """Handle submission of a new dream or vision."""
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        if title and description:
            user_id = session['user_id']
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                '''INSERT INTO dreams (user_id, title, description, date_posted)
                   VALUES (?, ?, ?, CURRENT_TIMESTAMP)''',
                (user_id, title, description)
            )
            dream_id = cursor.lastrowid
            conn.commit()
            conn.close()

            log_change(
                user_id=user_id,
                action='create',
                target_id=dream_id,
                target_username=title,
                change_details=f"Submitted dream: {title}"
            )
            flash('Your dream has been submitted successfully!', 'success')
            return redirect(url_for('dreams.dreams'))
        flash('Title and description cannot be empty.', 'error')
    return render_template('submit_dream.html')


@dreams_bp.route('/edit_dream/<int:dream_id>', methods=['GET', 'POST'])
@login_required
def edit_dream(dream_id):
    """Handle editing an existing dream."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM dreams WHERE id = ?', (dream_id,))
    dream = cursor.fetchone()
    if not dream:
        conn.close()
        flash('Dream not found.', 'error')
        return redirect(url_for('dreams.dreams'))

    if dream['user_id'] != session['user_id'] and session.get('role') != 'admin':
        conn.close()
        flash('You are not authorized to edit this dream.', 'error')
        return redirect(url_for('dreams.dreams'))

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        if title and description:
            cursor.execute(
                '''UPDATE dreams
                   SET title = ?, description = ?, date_posted = CURRENT_TIMESTAMP
                   WHERE id = ?''',
                (title, description, dream_id)
            )
            conn.commit()
            conn.close()

            log_change(
                user_id=session['user_id'],
                action='update',
                target_id=dream_id,
                target_username=title,
                change_details=f"Updated dream: {title}"
            )
            flash('Your dream has been updated successfully!', 'success')
            return redirect(url_for('dreams.dreams'))
        flash('Title and description cannot be empty.', 'error')

    conn.close()
    return render_template('edit_dream.html', dream=dream)


@dreams_bp.route('/delete_dream/<int:dream_id>', methods=['POST'])
@login_required
def delete_dream(dream_id):
    """Handle deletion of a dream."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM dreams WHERE id = ?', (dream_id,))
    dream = cursor.fetchone()
    if not dream:
        conn.close()
        flash('Dream not found.', 'error')
        return redirect(url_for('dreams.dreams'))

    role = session.get('role')
    owner_id = dream['user_id']
    can_delete = (
        owner_id == session['user_id'] or
        role == 'admin' or
        (role == 'staff' and owner_id != session['user_id'] and
         conn.execute('SELECT role FROM users WHERE id = ?', (owner_id,)).fetchone()['role'] == 'member')
    )
    if not can_delete:
        conn.close()
        flash('You are not authorized to delete this dream.', 'error')
        return redirect(url_for('dreams.dreams'))

    cursor.execute('DELETE FROM dreams WHERE id = ?', (dream_id,))
    conn.commit()
    conn.close()

    log_change(
        user_id=session['user_id'],
        action='delete',
        target_id=dream_id,
        target_username=dream['title'],
        change_details=f"Deleted dream: {dream['title']}"
    )
    flash('Your dream has been deleted successfully!', 'success')
    return redirect(url_for('dreams.dreams'))


@dreams_bp.route('/update_comment/<int:dream_id>/<int:comment_id>', methods=['POST'])
@login_required
def update_comment(dream_id, comment_id):
    """Update a specific comment for a given dream."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM dream_comments WHERE id = ?', (comment_id,))
    comment = cursor.fetchone()
    if not comment:
        conn.close()
        flash('Comment not found.', 'error')
        return redirect(url_for('dreams.dreams'))

    if comment['user_id'] != session['user_id'] and session.get('role') != 'admin':
        conn.close()
        flash('You are not authorized to edit this comment.', 'error')
        return redirect(url_for('dreams.dreams'))

    new_text = request.form.get('comment', '').strip()
    if not new_text:
        conn.close()
        flash('Comment cannot be empty.', 'error')
        return redirect(url_for('dreams.dreams'))

    cursor.execute(
        'UPDATE dream_comments SET comment = ?, date_posted = CURRENT_TIMESTAMP WHERE id = ?',
        (new_text, comment_id)
    )
    conn.commit()
    conn.close()

    log_change(
        user_id=session['user_id'],
        action='update',
        target_id=dream_id,
        target_username='Dream Comment',
        change_details=f"Updated comment: {new_text[:30]}..."
    )
    flash('Your comment has been updated successfully!', 'success')
    return redirect(url_for('dreams.dreams'))


@dreams_bp.route('/delete_comment/<int:dream_id>/<int:comment_id>', methods=['POST'])
@login_required
def delete_comment(dream_id, comment_id):
    """Delete a specific comment under a dream."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # ensure the comment exists
    cursor.execute('SELECT * FROM dream_comments WHERE id = ?', (comment_id,))
    comment = cursor.fetchone()
    if not comment:
        conn.close()
        flash('Comment not found.', 'error')
        return redirect(url_for('dreams.dreams'))

    # only the author or an admin may delete
    if comment['user_id'] != session['user_id'] and session.get('role') != 'admin':
        conn.close()
        flash('You are not authorized to delete this comment.', 'error')
        return redirect(url_for('dreams.dreams'))

    # perform deletion
    cursor.execute('DELETE FROM dream_comments WHERE id = ?', (comment_id,))
    conn.commit()
    conn.close()

    log_change(
        user_id=session['user_id'],
        action='delete',
        target_id=dream_id,
        target_username='Dream Comment',
        change_details=f"Deleted comment ID {comment_id}"
    )
    flash('Your comment has been deleted.', 'success')
    return redirect(url_for('dreams.dreams'))
