import os
import time
import sqlite3
from datetime import datetime
from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    send_from_directory,
    current_app,
    jsonify
)
from functools import wraps
from werkzeug.utils import secure_filename
from db_handler import get_db_connection
from docx import Document as DocxDocument
import PyPDF2
from log_changes import log_change  # your existing logging function

# ----------------------------------------------------
# Blueprint setup
# ----------------------------------------------------
sermons_bp = Blueprint(
    'sermons',
    __name__,
    template_folder='templates',
    static_folder='sermons_uploads',
    static_url_path='/sermons/uploads'
)

# ----------------------------------------------------
# Configuration
# ----------------------------------------------------
ALLOWED_EXTENSIONS = {'pdf', 'mp3', 'mp4', 'jpg', 'png', 'docx', 'txt'}
BASE_DIR = os.path.dirname(__file__)
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'sermons_uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ----------------------------------------------------
# Helpers
# ----------------------------------------------------
def allowed_file(filename):
    ext = filename.rsplit('.', 1)[-1].lower()
    return ext in ALLOWED_EXTENSIONS

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in first.', 'error')
            return redirect(url_for('auth.login'))
        return fn(*args, **kwargs)
    return wrapper

# ----------------------------------------------------
# 1) Upload handler
# ----------------------------------------------------
@sermons_bp.route('/upload-sermon', methods=['GET', 'POST'])
@login_required
def upload_sermon():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        author = request.form.get('author', '').strip()
        details = request.form.get('details', '').strip()
        external_link = request.form.get('external_link', '').strip()
        notes_file = request.files.get('sermon_notes')
        sermon_file = request.files.get('sermon_file')
        user_id = session['user_id']

        if not title or not author:
            flash('Title and author are required.', 'error')
            return redirect(request.url)
        if not ((notes_file and notes_file.filename) or
                (sermon_file and sermon_file.filename) or
                external_link):
            flash('Upload notes, sermon file, or provide an external link.', 'error')
            return redirect(request.url)

        ts = int(time.time())
        notes_fn = None
        sermon_fn = None

        try:
            if notes_file and notes_file.filename:
                if not allowed_file(notes_file.filename):
                    raise ValueError('Notes file type not allowed.')
                fn = secure_filename(notes_file.filename)
                notes_fn = f"{user_id}_{ts}_{fn}"
                notes_file.save(os.path.join(UPLOAD_FOLDER, notes_fn))

            if sermon_file and sermon_file.filename:
                if not allowed_file(sermon_file.filename):
                    raise ValueError('Sermon file type not allowed.')
                fn = secure_filename(sermon_file.filename)
                sermon_fn = f"{user_id}_{ts}_{fn}"
                sermon_file.save(os.path.join(UPLOAD_FOLDER, sermon_fn))

            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO sermons
                  (title, author, notes, details, sermon_file, external_link, uploaded_by)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                title,
                author,
                notes_fn,
                details,
                sermon_fn,
                external_link or None,
                user_id
            ))
            sermon_id = cursor.lastrowid
            conn.commit()
            conn.close()

            log_change(
                user_id=user_id,
                action='create',
                target_id=sermon_id,
                target_username=title,
                change_details=f"Uploaded sermon: {title}"
            )

            flash('Sermon uploaded successfully.', 'success')
            return redirect(url_for('sermons.sermons'))

        except Exception as e:
            current_app.logger.exception('Upload error')
            flash(f'Upload failed: {e}', 'error')
            return redirect(request.url)

    return render_template('upload_sermon.html')

# ----------------------------------------------------
# 2) List + inline notes + comments display
# ----------------------------------------------------
@sermons_bp.route('/sermons')
@login_required
def sermons():
    user_id = session['user_id']
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Fetch sermons
    cursor.execute("""
        SELECT
          s.id,
          s.title,
          s.author,
          s.notes,
          s.details,
          s.sermon_file,
          s.external_link,
          s.uploaded_at,
          s.uploaded_by,
          u.username AS uploader
        FROM sermons s
        LEFT JOIN users u ON s.uploaded_by = u.id
        ORDER BY s.uploaded_at DESC
    """)
    sermon_rows = cursor.fetchall()

    sermons = []
    for row in sermon_rows:
        sermon = dict(row)

        # Load notes content
        content = None
        fn = sermon['notes']
        if fn:
            path = os.path.join(UPLOAD_FOLDER, fn)
            ext = fn.rsplit('.', 1)[-1].lower()
            try:
                if ext == 'txt':
                    with open(path, 'r', encoding='utf-8') as f:
                        content = f.read()
                elif ext == 'docx':
                    doc = DocxDocument(path)
                    content = "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())
                elif ext == 'pdf':
                    reader = PyPDF2.PdfReader(path)
                    pages = [p.extract_text() or '' for p in reader.pages]
                    content = "\n\n".join(pages)
            except Exception:
                content = None
        sermon['notes_content'] = content

        # Fetch comments for this sermon (now including user_id & role)
        cursor.execute("""
            SELECT
              c.id,
              c.comment,
              c.date_added,
              c.user_id,
              u.username   AS commenter,
              u.role       AS commenter_role
            FROM sermon_comments c
            LEFT JOIN users u ON c.user_id = u.id
            WHERE c.sermon_id = ?
            ORDER BY c.date_added ASC
        """, (sermon['id'],))
        comment_rows = cursor.fetchall()
        sermon['comments'] = [dict(c) for c in comment_rows]

        sermons.append(sermon)

    conn.close()

    log_change(
        user_id=user_id,
        action='view',
        target_username='Sermons List',
        change_details='Viewed sermons list'
    )

    return render_template('sermons.html', sermons=sermons)

# ----------------------------------------------------
# 3) Edit handler
# ----------------------------------------------------
@sermons_bp.route('/sermons/edit/<int:sermon_id>', methods=['GET', 'POST'])
@login_required
def edit_sermon(sermon_id):
    user_id = session['user_id']
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM sermons WHERE id = ?", (sermon_id,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        flash('Sermon not found.', 'error')
        return redirect(url_for('sermons.sermons'))

    sermon = dict(row)
    if sermon['uploaded_by'] != user_id:
        conn.close()
        flash('Not authorized to edit.', 'error')
        return redirect(url_for('sermons.sermons'))

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        author = request.form.get('author', '').strip()
        details = request.form.get('details', '').strip()
        external_link = request.form.get('external_link', '').strip()
        notes_file = request.files.get('sermon_notes')
        sermon_file = request.files.get('sermon_file')

        if not title or not author:
            flash('Title and author are required.', 'error')
            return redirect(request.url)

        updates = []
        params = []

        if notes_file and notes_file.filename:
            if not allowed_file(notes_file.filename):
                flash('Notes file type not allowed.', 'error')
                return redirect(request.url)
            fn = secure_filename(notes_file.filename)
            notes_fn = f"{user_id}_{int(time.time())}_{fn}"
            notes_file.save(os.path.join(UPLOAD_FOLDER, notes_fn))
            old = sermon['notes']
            if old:
                try:
                    os.remove(os.path.join(UPLOAD_FOLDER, old))
                except OSError:
                    pass
            updates.append("notes = ?")
            params.append(notes_fn)

        if sermon_file and sermon_file.filename:
            if not allowed_file(sermon_file.filename):
                flash('Sermon file type not allowed.', 'error')
                return redirect(request.url)
            fn = secure_filename(sermon_file.filename)
            media_fn = f"{user_id}_{int(time.time())}_{fn}"
            sermon_file.save(os.path.join(UPLOAD_FOLDER, media_fn))
            old = sermon['sermon_file']
            if old:
                try:
                    os.remove(os.path.join(UPLOAD_FOLDER, old))
                except OSError:
                    pass
            updates.append("sermon_file = ?")
            params.append(media_fn)

        updates.extend([
            "title = ?", "author = ?",
            "details = ?", "external_link = ?"
        ])
        params.extend([title, author, details, external_link or None])
        params.append(sermon_id)

        sql = f"UPDATE sermons SET {', '.join(updates)} WHERE id = ?"
        cursor.execute(sql, params)
        conn.commit()
        conn.close()

        log_change(
            user_id=user_id,
            action='update',
            target_id=sermon_id,
            target_username=title,
            change_details=f"Updated sermon: {title}"
        )

        flash('Sermon updated.', 'success')
        return redirect(url_for('sermons.sermons'))

    conn.close()
    return render_template('edit_sermon.html', sermon=sermon)

# ----------------------------------------------------
# 4) Delete handler
# ----------------------------------------------------
@sermons_bp.route('/sermons/delete/<int:sermon_id>', methods=['POST'])
@login_required
def delete_sermon(sermon_id):
    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT notes, sermon_file, uploaded_by, title FROM sermons WHERE id = ?", (sermon_id,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        flash('Not found.', 'error')
        return redirect(url_for('sermons.sermons'))

    notes_fn, media_fn, owner, title = row
    if owner != user_id:
        conn.close()
        flash('Not authorized.', 'error')
        return redirect(url_for('sermons.sermons'))

    cursor.execute("DELETE FROM sermons WHERE id = ?", (sermon_id,))
    conn.commit()
    conn.close()

    for fn in (notes_fn, media_fn):
        if fn:
            try:
                os.remove(os.path.join(UPLOAD_FOLDER, fn))
            except OSError:
                current_app.logger.warning(f"Could not delete file {fn}")

    log_change(
        user_id=user_id,
        action='delete',
        target_id=sermon_id,
        target_username=title,
        change_details=f"Deleted sermon: {title}"
    )

    flash('Sermon deleted.', 'success')
    return redirect(url_for('sermons.sermons'))

# ----------------------------------------------------
# 5) Serve uploaded files
# ----------------------------------------------------
@sermons_bp.route('/uploads/<filename>')
@login_required
def uploaded_file(filename):
    user_id = session['user_id']
    log_change(
        user_id=user_id,
        action='view',
        target_username=filename,
        change_details=f"Viewed file: {filename}"
    )
    return send_from_directory(UPLOAD_FOLDER, filename)

# ----------------------------------------------------
# 6) Search handler (JSON)
# ----------------------------------------------------
@sermons_bp.route('/search')
@login_required
def search_sermons():
    q = request.args.get('q', '').strip()
    date_filter = request.args.get('date_filter')
    is_potluck = request.args.get('is_potluck')

    conn = get_db_connection()
    try:
        like_q = f'%{q}%'
        query = """
            SELECT * FROM sermons
            WHERE title LIKE ? OR author LIKE ? OR details LIKE ?
        """
        params = [like_q, like_q, like_q]

        if date_filter == 'upcoming':
            query += " AND uploaded_at > ?"
            params.append(datetime.now().strftime('%Y-%m-%d'))
        elif date_filter == 'today':
            query += " AND DATE(uploaded_at) = ?"
            params.append(datetime.now().strftime('%Y-%m-%d'))
        elif date_filter == 'past':
            query += " AND uploaded_at < ?"
            params.append(datetime.now().strftime('%Y-%m-%d'))

        if is_potluck is not None:
            query += " AND is_potluck = ?"
            params.append(int(is_potluck))

        rows = conn.execute(query, tuple(params)).fetchall()
        sermons = [dict(r) for r in rows]
    except sqlite3.Error:
        sermons = []
    finally:
        conn.close()

    return jsonify(sermons)

# ----------------------------------------------------
# 7) Add a comment to a sermon
# ----------------------------------------------------
@sermons_bp.route('/sermons/<int:sermon_id>/comment', methods=['POST'])
@login_required
def add_comment(sermon_id):
    user_id = session['user_id']
    comment_text = request.form.get('comment', '').strip()

    if not comment_text:
        flash('Comment cannot be empty.', 'error')
        return redirect(url_for('sermons.sermons'))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO sermon_comments (sermon_id, user_id, comment)
        VALUES (?, ?, ?)
    """, (sermon_id, user_id, comment_text))
    conn.commit()
    conn.close()

    log_change(
        user_id=user_id,
        action='create',
        target_id=sermon_id,
        target_username='Sermon Comment',
        change_details=f"Added comment to sermon: {comment_text[:30]}..."
    )

    flash('Comment added successfully.', 'success')
    return redirect(url_for('sermons.sermons'))

# ----------------------------------------------------
# 8) Edit a comment
# ----------------------------------------------------
@sermons_bp.route('/sermons/<int:sermon_id>/comment/<int:comment_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_comment(sermon_id, comment_id):
    user_id = session['user_id']
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM sermon_comments WHERE id = ?", (comment_id,))
    comment = cursor.fetchone()

    if not comment or comment['user_id'] != user_id:
        conn.close()
        flash('Not authorized to edit this comment.', 'error')
        return redirect(url_for('sermons.sermons'))

    if request.method == 'POST':
        new_text = request.form.get('comment', '').strip()
        if not new_text:
            flash('Comment cannot be empty.', 'error')
            conn.close()
            return redirect(request.url)

        cursor.execute("""
            UPDATE sermon_comments
            SET comment = ?, date_added = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (new_text, comment_id))
        conn.commit()
        conn.close()

        log_change(
            user_id=user_id,
            action='update',
            target_id=sermon_id,
            target_username='Sermon Comment',
            change_details=f"Edited comment to: {new_text[:30]}..."
        )

        flash('Comment updated.', 'success')
        return redirect(url_for('sermons.sermons'))

    conn.close()
    return render_template('edit_comment.html', sermon_id=sermon_id, comment=dict(comment))

# ----------------------------------------------------
# 9) Delete a comment
# ----------------------------------------------------
@sermons_bp.route('/sermons/<int:sermon_id>/comment/<int:comment_id>/delete', methods=['POST'])
@login_required
def delete_comment(sermon_id, comment_id):
    user_id = session['user_id']
    role = session.get('role')
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM sermon_comments WHERE id = ?", (comment_id,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        flash('Comment not found.', 'error')
        return redirect(url_for('sermons.sermons'))

    owner = row[0]
    # only owner or admin, or staff deleting non-admin
    if owner != user_id and role != 'admin':
        if role != 'staff':
            conn.close()
            flash('Not authorized to delete comment.', 'error')
            return redirect(url_for('sermons.sermons'))
        cursor.execute("SELECT role FROM users WHERE id = ?", (owner,))
        owner_role = cursor.fetchone()[0]
        if owner_role == 'admin':
            conn.close()
            flash('Not authorized to delete comment.', 'error')
            return redirect(url_for('sermons.sermons'))

    cursor.execute("DELETE FROM sermon_comments WHERE id = ?", (comment_id,))
    conn.commit()
    conn.close()

    log_change(
        user_id=user_id,
        action='delete',
        target_id=sermon_id,
        target_username='Sermon Comment',
        change_details=f"Deleted comment {comment_id}"
    )

    flash('Comment deleted.', 'success')
    return redirect(url_for('sermons.sermons'))


# ----------------------------------------------------
# 8) Update comment handler
# ----------------------------------------------------
@sermons_bp.route('/sermons/<int:sermon_id>/comment/<int:comment_id>/update', methods=['POST'])
@login_required
def update_comment(sermon_id, comment_id):
    user_id = session['user_id']
    new_comment_text = request.form.get('comment', '').strip()

    if not new_comment_text:
        flash('Comment cannot be empty.', 'error')
        return redirect(url_for('sermons.sermons'))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""SELECT user_id FROM sermon_comments WHERE id = ?""", (comment_id,))
    comment_owner = cursor.fetchone()

    if not comment_owner:
        flash('Comment not found.', 'error')
        return redirect(url_for('sermons.sermons'))

    if comment_owner['user_id'] != user_id:
        flash('Not authorized to edit this comment.', 'error')
        return redirect(url_for('sermons.sermons'))

    cursor.execute("""
        UPDATE sermon_comments
        SET comment = ?
        WHERE id = ?
    """, (new_comment_text, comment_id))
    conn.commit()
    conn.close()

    log_change(
        user_id=user_id,
        action='update',
        target_id=comment_id,
        target_username='Sermon Comment',
        change_details=f"Updated comment: {new_comment_text[:30]}..."
    )

    flash('Comment updated successfully.', 'success')
    return redirect(url_for('sermons.sermons'))
