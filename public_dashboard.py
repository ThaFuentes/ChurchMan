from flask import Blueprint, render_template
from db_handler import get_db_connection
import random

public_dashboard_bp = Blueprint('public_dashboard', __name__)

@public_dashboard_bp.route('/public_dashboard')
def public_dashboard():
    """Public dashboard accessible to all visitors without login"""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Upcoming Events
    cursor.execute("""
        SELECT event_name AS title,
               event_date || ' ' || event_time AS datetime,
               NULL AS posted_by
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
               NULL AS posted_by
        FROM prayers
        ORDER BY date_posted DESC
        LIMIT 5
    """)
    prayers = cursor.fetchall()

    # Recent Dreams & Visions
    cursor.execute("""
        SELECT d.title,
               d.date_posted AS datetime,
               u.username AS posted_by
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
               u.username AS posted_by
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
               u.username AS posted_by
        FROM sermons s
        LEFT JOIN users u ON s.uploaded_by = u.id
        ORDER BY s.uploaded_at DESC
        LIMIT 5
    """)
    sermons = cursor.fetchall()

    # Recent Announcements
    cursor.execute("""
        SELECT a.title,
               a.created_at,
               u.username AS posted_by
        FROM announcements a
        LEFT JOIN users u ON a.created_by = u.id
        WHERE a.is_active = 1
        ORDER BY a.created_at DESC
        LIMIT 5
    """)
    announcements = cursor.fetchall()

    conn.close()

    # Inlined sparkle/sprinkle generation
    sparkles = []
    for _ in range(20):
        sparkles.append({
            'left_pct': round(random.uniform(0, 100), 1),
            'top_pct': round(random.uniform(0, 100), 1),
            'size_px': random.randint(6, 16),
            'delay_s': round(random.uniform(0, 2), 2),
        })

    return render_template(
        'public_dashboard.html',
        events=events,
        prayers=prayers,
        dreams=dreams,
        prophecies=prophecies,
        sermons=sermons,
        announcements=announcements,
        sparkles=sparkles,
        has_public_prayer=False  # Flag to indicate public_prayer blueprint doesn't exist
    )

@public_dashboard_bp.route('/public_index')
def public_index():
    """Public index accessible to all visitors without login, mirroring public dashboard"""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Upcoming Events
    cursor.execute("""
        SELECT event_name AS title,
               event_date || ' ' || event_time AS datetime,
               NULL AS posted_by
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
               NULL AS posted_by
        FROM prayers
        ORDER BY date_posted DESC
        LIMIT 5
    """)
    prayers = cursor.fetchall()

    # Recent Dreams & Visions
    cursor.execute("""
        SELECT d.title,
               d.date_posted AS datetime,
               u.username AS posted_by
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
               u.username AS posted_by
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
               u.username AS posted_by
        FROM sermons s
        LEFT JOIN users u ON s.uploaded_by = u.id
        ORDER BY s.uploaded_at DESC
        LIMIT 5
    """)
    sermons = cursor.fetchall()

    # Recent Announcements
    cursor.execute("""
        SELECT a.title,
               a.created_at,
               u.username AS posted_by
        FROM announcements a
        LEFT JOIN users u ON a.created_by = u.id
        WHERE a.is_active = 1
        ORDER BY a.created_at DESC
        LIMIT 5
    """)
    announcements = cursor.fetchall()

    conn.close()

    # Inlined sparkle/sprinkle generation
    sparkles = []
    for _ in range(20):
        sparkles.append({
            'left_pct': round(random.uniform(0, 100), 1),
            'top_pct': round(random.uniform(0, 100), 1),
            'size_px': random.randint(6, 16),
            'delay_s': round(random.uniform(0, 2), 2),
        })

    return render_template(
        'public_dashboard.html',
        events=events,
        prayers=prayers,
        dreams=dreams,
        prophecies=prophecies,
        sermons=sermons,
        announcements=announcements,
        sparkles=sparkles,
        has_public_prayer=False  # Flag to indicate public_prayer blueprint doesn't exist
    )