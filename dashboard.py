from flask import Blueprint, render_template, session, redirect, url_for, flash
from flask_login import login_required, current_user  # current_user can be handy!
from db_handler import get_db_connection
import sqlite3
from datetime import datetime
import traceback  # For more detailed error logging, just in case!

# Define the Blueprint for the dashboard
dashboard_bp = Blueprint('dashboard', __name__)


# --- Helper function to fetch data (optional, but can keep route clean) ---
# You could move query logic here, but for now, we'll keep it in the route
# for clarity, similar to your original structure.

# --- Dashboard Route ---
@dashboard_bp.route('/')
@login_required  # Ensures the user is logged in before accessing the dashboard
def dashboard():
    """
    Displays the main dashboard page, fetching relevant data like birthdays,
    upcoming events, recent prayers, and enabled widgets for the logged-in user.
    """
    # 1) Basic User Check (Flask-Login's @login_required handles most of this)
    # We can rely on current_user provided by Flask-Login now!
    # Although, using session directly is fine too as you did. Let's keep your way.
    if 'user_id' not in session:
        flash("Oops! You need to be logged in to see the dashboard. 😉", "warning")
        return redirect(url_for('auth.login'))

    user_id = session['user_id']
    username = session.get('username', 'User')  # Use .get for safety
    role = session.get('role', 'Guest')  # Use .get for safety

    # Initialize data containers
    birthdays = []
    prayers = []
    all_events = []
    upcoming_events = []
    widgets = []
    conn = None  # Ensure conn is defined for the finally block

    try:
        # 2) Connect to DB and Fetch Data
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row  # Get rows that act like dictionaries
        cursor = conn.cursor()

        # --- Fetch Today's Birthdays (excluding self) ---
        try:
            today_str = datetime.now().strftime('%m-%d')
            cursor.execute("""
                SELECT first_name, last_name, birthday
                  FROM users
                 WHERE strftime('%m-%d', birthday) = ?
                   AND id != ?
                 ORDER BY last_name, first_name
            """, (today_str, user_id))
            birthdays = cursor.fetchall()
            if birthdays:
                print(f"🎂 Fetched {len(birthdays)} birthday(s) for today!")
            else:
                print("🎂 No birthdays found for other users today.")
        except Exception as e:
            print(f"❌ Error fetching birthdays: {e}")
            traceback.print_exc()  # Print full traceback for debugging
            flash("Could not load birthday information.", "error")

        # --- Fetch Recent Prayer Requests (Limit 5) ---
        try:
            cursor.execute("""
                SELECT title, description, user_id, date_posted
                  FROM prayers
                 ORDER BY date_posted DESC
                 LIMIT 5
            """)
            prayers = cursor.fetchall()
            if prayers:
                print(f"🙏 Fetched {len(prayers)} recent prayer requests.")
            else:
                print("🙏 No recent prayers found.")
        except Exception as e:
            print(f"❌ Error fetching prayers: {e}")
            traceback.print_exc()
            flash("Could not load prayer requests.", "error")

        # --- Fetch ALL Events (Filtering done in Python below) ---
        try:
            cursor.execute("""
                SELECT event_name, event_date, event_time, description
                  FROM events
                 ORDER BY event_date, event_time /* Optional: pre-sort */
            """)
            all_events = cursor.fetchall()
            if all_events:
                print(f"🗓️ Fetched {len(all_events)} total events.")
            else:
                print("🗓️ No events found in the database.")
        except Exception as e:
            print(f"❌ Error fetching events: {e}")
            traceback.print_exc()
            flash("Could not load event information.", "error")

        # --- Fetch Enabled Widgets for the User ---
        try:
            cursor.execute("""
                SELECT w.slug, w.display_name, w.description
                  FROM widget_definitions w
             LEFT JOIN user_widgets uw
                    ON uw.user_id = ? AND uw.widget_name = w.slug
                 WHERE COALESCE(uw.is_enabled, 1) = 1 /* Default to enabled */
              ORDER BY w.display_name /* Or w.slug, depending on desired order */
            """, (user_id,))
            widgets = cursor.fetchall()
            if widgets:
                print(f"✨ Fetched {len(widgets)} enabled widgets for the user.")
            else:
                print("✨ No widgets enabled or defined for the user.")
        except Exception as e:
            print(f"❌ Error fetching widgets: {e}")
            traceback.print_exc()
            flash("Could not load widget information.", "error")

    except sqlite3.Error as db_err:
        print(f"🚨 DATABASE ERROR in dashboard: {db_err}")
        traceback.print_exc()
        flash("A database error occurred. Please try again later or contact support.", "danger")
        # Decide where to redirect on major DB error, maybe login or an error page
        return redirect(url_for('auth.login'))
    except Exception as e:
        print(f"🚨 UNEXPECTED ERROR in dashboard data fetching: {e}")
        traceback.print_exc()
        flash("An unexpected error occurred while loading dashboard data.", "danger")
        # Decide where to redirect
        return redirect(url_for('auth.login'))
    finally:
        # 3) Close DB Connection - ALWAYS do this!
        if conn:
            conn.close()
            print("🔒 Database connection closed.")

    # 4) Process Events - Filter for Upcoming (Top 5)
    # Doing this *after* closing the DB connection is fine
    today = datetime.today().date()
    parsed_upcoming = []
    for event_row in all_events:
        # Convert sqlite3.Row to a dictionary for easier processing if needed,
        # though direct access should work fine.
        event_dict = dict(event_row)
        try:
            # Ensure date parsing is robust
            event_date_str = event_dict.get('event_date')
            if not event_date_str:
                print(f"⚠️ Skipping event with missing date: {event_dict.get('event_name')}")
                continue

            event_date = datetime.strptime(event_date_str, '%Y-%m-%d').date()

            if event_date >= today:
                # Add the parsed date object for sorting, maybe remove later if not needed
                event_dict['_parsed_date'] = event_date
                parsed_upcoming.append(event_dict)

        except ValueError:
            print(
                f"⚠️ Skipping event with invalid date format '{event_dict.get('event_date')}': {event_dict.get('event_name')}")
        except Exception as e:
            print(f"⚠️ Error processing event '{event_dict.get('event_name')}': {e}")

    # Sort the valid upcoming events by date
    parsed_upcoming.sort(key=lambda x: x['_parsed_date'])
    upcoming_events = parsed_upcoming[:5]  # Take the top 5

    if upcoming_events:
        print(f"🗓️ Filtered {len(upcoming_events)} upcoming events.")
    else:
        print("🗓️ No upcoming events found.")

    # 5) Render the Template
    # Pass all the fetched and processed data to the HTML template
    return render_template(
        'dashboard.html',
        username=username,
        role=role,
        birthdays=birthdays,
        events=upcoming_events,  # Pass the filtered & sorted list
        prayers=prayers,
        widgets=widgets
    )
