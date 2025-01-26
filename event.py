from flask import Blueprint, render_template, request, redirect, url_for, flash, session, abort
import sqlite3
from collections import defaultdict
from datetime import datetime
from functools import wraps

DATABASE = 'church_management.db'

event_bp = Blueprint('event', __name__)

# Function to connect to the database
def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

# Function to log changes in the change_records table
def log_change(user_id, action, target_id=None, target_name=None, change_details=None):
    if not user_id:
        print("User ID is missing; cannot log the action.")
        return
    print(f"Logging action: {action} for user: {user_id}, target: {target_name}, details: {change_details}")
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO change_records (user_id, action, target_id, target_username, change_details)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, action, target_id, target_name, change_details))
        conn.commit()
    except sqlite3.Error as e:
        print(f"Error logging action: {e}")
    finally:
        conn.close()

# Role required decorator
def role_required(required_roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session or session.get('user_role') not in required_roles:
                abort(403)  # Forbidden
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# Route to display all events
@event_bp.route('/')
@role_required(['Staff', 'Admin', 'Owner'])
def events():
    conn = get_db_connection()
    try:
        events = conn.execute('SELECT * FROM events').fetchall()
    except sqlite3.Error as e:
        flash(f"An error occurred while fetching events: {str(e)}")
        events = []
    finally:
        conn.close()

    # Organize events by year
    events_by_year = defaultdict(list)
    for event in events:
        try:
            event_year = datetime.strptime(event['event_date'], '%Y-%m-%d').year
            events_by_year[event_year].append(event)
        except ValueError:
            flash(f"Invalid date format for event: {event['event_name']}")

    # Sort years in descending order
    events_by_year = dict(sorted(events_by_year.items(), reverse=True))

    # Log the page access
    log_change(user_id=session['user_id'], action='access', change_details='Accessed the events page')

    return render_template('event.html', events=events, events_by_year=events_by_year)

# Route to add a new event
@event_bp.route('/add', methods=['GET', 'POST'])
@role_required(['Staff', 'Admin', 'Owner'])
def add_event():
    if request.method == 'POST':
        # Process the form and insert event into the database
        try:
            event_name = request.form['event_name']
            event_date = request.form['event_date']
            event_time = request.form['event_time']
            location = request.form['location']
            description = request.form['description']
            speaker_host = request.form['speaker_host']
            special_guests = request.form['special_guests']
            theme = request.form['theme']
            agenda = request.form['agenda']
            registration_info = request.form['registration_info']
            cost_fees = request.form['cost_fees']
            contact_info = request.form['contact_info']
            childcare_availability = request.form['childcare_availability']
            accessibility = request.form['accessibility']
            promotional_materials = request.form['promotional_materials']
            volunteer_opportunities = request.form['volunteer_opportunities']
            parking_info = request.form['parking_info']
            dress_code = request.form['dress_code']
            food_beverages = request.form['food_beverages']
            event_sponsor = request.form['event_sponsor']
            social_media_hashtag = request.form['social_media_hashtag']
            donation_info = request.form['donation_info']
            safety_protocols = request.form['safety_protocols']
            follow_up = request.form['follow_up']
            event_coordinator = request.form['event_coordinator']
            announcements_reminders = request.form['announcements_reminders']
            feedback_form = request.form['feedback_form']
            live_streaming_details = request.form['live_streaming_details']
            event_objectives = request.form['event_objectives']

            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO events (
                    event_name, event_date, event_time, location, description, speaker_host, special_guests, theme, agenda, 
                    registration_info, cost_fees, contact_info, childcare_availability, accessibility, promotional_materials, 
                    volunteer_opportunities, parking_info, dress_code, food_beverages, event_sponsor, social_media_hashtag, 
                    donation_info, safety_protocols, follow_up, event_coordinator, announcements_reminders, feedback_form, 
                    live_streaming_details, event_objectives
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
            event_name, event_date, event_time, location, description, speaker_host, special_guests, theme, agenda,
            registration_info, cost_fees, contact_info, childcare_availability, accessibility, promotional_materials,
            volunteer_opportunities, parking_info, dress_code, food_beverages, event_sponsor, social_media_hashtag,
            donation_info, safety_protocols, follow_up, event_coordinator, announcements_reminders, feedback_form,
            live_streaming_details, event_objectives))
            conn.commit()
            event_id = cursor.lastrowid

            # Log the creation of the event
            log_change(user_id=session['user_id'], action='create', target_id=event_id, target_name=event_name,
                       change_details=f"Created event: {event_name}")
            flash('Event created successfully!')

        except sqlite3.Error as e:
            flash(f"An error occurred while adding the event: {str(e)}")
        finally:
            conn.close()

        return redirect(url_for('event.events'))

    return render_template('add_event.html')

# Route to edit an existing event
@event_bp.route('/edit/<int:event_id>', methods=['GET', 'POST'])
@role_required(['Admin', 'Owner'])
def edit_event(event_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        # Update the event details
        try:
            event_name = request.form['event_name']
            event_date = request.form['event_date']
            event_time = request.form['event_time']
            location = request.form['location']
            description = request.form['description']
            speaker_host = request.form['speaker_host']
            special_guests = request.form['special_guests']
            theme = request.form['theme']
            agenda = request.form['agenda']
            registration_info = request.form['registration_info']
            cost_fees = request.form['cost_fees']
            contact_info = request.form['contact_info']
            childcare_availability = request.form['childcare_availability']
            accessibility = request.form['accessibility']
            promotional_materials = request.form['promotional_materials']
            volunteer_opportunities = request.form['volunteer_opportunities']
            parking_info = request.form['parking_info']
            dress_code = request.form['dress_code']
            food_beverages = request.form['food_beverages']
            event_sponsor = request.form['event_sponsor']
            social_media_hashtag = request.form['social_media_hashtag']
            donation_info = request.form['donation_info']
            safety_protocols = request.form['safety_protocols']
            follow_up = request.form['follow_up']
            event_coordinator = request.form['event_coordinator']
            announcements_reminders = request.form['announcements_reminders']
            feedback_form = request.form['feedback_form']
            live_streaming_details = request.form['live_streaming_details']
            event_objectives = request.form['event_objectives']

            cursor.execute('''
                UPDATE events SET
                    event_name = ?, event_date = ?, event_time = ?, location = ?, description = ?, speaker_host = ?, 
                    special_guests = ?, theme = ?, agenda = ?, registration_info = ?, cost_fees = ?, contact_info = ?, 
                    childcare_availability = ?, accessibility = ?, promotional_materials = ?, volunteer_opportunities = ?, 
                    parking_info = ?, dress_code = ?, food_beverages = ?, event_sponsor = ?, social_media_hashtag = ?, 
                    donation_info = ?, safety_protocols = ?, follow_up = ?, event_coordinator = ?, announcements_reminders = ?, 
                    feedback_form = ?, live_streaming_details = ?, event_objectives = ?
                WHERE id = ?
            ''', (
            event_name, event_date, event_time, location, description, speaker_host, special_guests, theme, agenda,
            registration_info, cost_fees, contact_info, childcare_availability, accessibility, promotional_materials,
            volunteer_opportunities, parking_info, dress_code, food_beverages, event_sponsor, social_media_hashtag,
            donation_info, safety_protocols, follow_up, event_coordinator, announcements_reminders, feedback_form,
            live_streaming_details, event_objectives, event_id))
            conn.commit()

            # Log the event update
            log_change(user_id=session['user_id'], action='update', target_id=event_id, target_name=event_name,
                       change_details=f"Updated event: {event_name}")
            flash('Event updated successfully!')

        except sqlite3.Error as e:
            flash(f"An error occurred while updating the event: {str(e)}")
        finally:
            conn.close()

        return redirect(url_for('event.events'))

    # Fetch the event details for the form
    event = conn.execute('SELECT * FROM events WHERE id = ?', (event_id,)).fetchone()
    conn.close()
    if event is None:
        flash('Event not found.')
        return redirect(url_for('event.events'))

    return render_template('edit_event.html', event=event)

# Route to delete an event
@event_bp.route('/delete/<int:event_id>', methods=['POST'])
@role_required(['Admin', 'Owner'])
def delete_event(event_id):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM events WHERE id = ?', (event_id,))
        conn.commit()

        # Log the deletion of the event
        log_change(user_id=session['user_id'], action='delete', target_id=event_id,
                   change_details=f"Deleted event with ID: {event_id}")
        flash('Event deleted successfully.')

    except sqlite3.Error as e:
        flash(f"An error occurred while deleting the event: {str(e)}")

    finally:
        conn.close()

    return redirect(url_for('event.events'))

