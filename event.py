from flask import Blueprint, render_template, request, redirect, url_for, flash, session, abort
import sqlite3
from collections import defaultdict
from datetime import datetime
from functools import wraps
import logging

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
@role_required(['Staff', 'Admin', 'Owner', 'Members'])
def events():
    # Open a connection to fetch events.
    conn = get_db_connection()
    try:
        events = conn.execute('SELECT * FROM events').fetchall()
    except sqlite3.Error as e:
        flash(f"An error occurred while fetching events: {str(e)}")
        events = []
    finally:
        conn.close()

    # Organize events by year and attach potluck contributions where applicable.
    events_by_year = defaultdict(list)
    new_events = []
    conn2 = get_db_connection()
    for event in events:
        # Convert the row to a dictionary.
        event_dict = dict(event)
        # Organize by year.
        try:
            event_year = datetime.strptime(event_dict['event_date'], '%Y-%m-%d').year
            events_by_year[event_year].append(event_dict)
        except ValueError:
            flash(f"Invalid date format for event: {event_dict.get('event_name')}")

        # If this event is a potluck, fetch contributions including the id field.
        if event_dict.get('is_potluck') == 1:
            contributions = conn2.execute(
                '''SELECT pc.id, pc.contribution, u.first_name, u.last_name 
                   FROM potluck_contributions pc 
                   JOIN users u ON pc.user_id = u.id 
                   WHERE pc.event_id = ?''',
                (event_dict['id'],)
            ).fetchall()
            # Convert contributions to a list of dictionaries.
            event_dict['potluck_contributions'] = [dict(c) for c in contributions]
        else:
            event_dict['potluck_contributions'] = []
        new_events.append(event_dict)
    conn2.close()

    # Sort years in descending order.
    events_by_year = dict(sorted(events_by_year.items(), reverse=True))
    log_change(user_id=session['user_id'], action='access', change_details='Accessed the events page')

    return render_template('event.html', events=new_events, events_by_year=events_by_year)


# Route to add a new event
@event_bp.route('/add', methods=['GET', 'POST'])
@role_required(['Staff', 'Admin', 'Owner'])
def add_event():
    conn = None
    if request.method == 'POST':
        print("Received POST request for add_event")

        # Helper function to get a field from the form; returns None if empty.
        def get_field(field_name, default=None):
            value = request.form.get(field_name, default)
            if value == '':
                return None
            return value

        try:
            # Retrieve form fields using the helper
            event_name = get_field('event_name')
            event_date = get_field('event_date')
            event_time = get_field('event_time')
            location = get_field('location')
            description = get_field('description')
            speaker_host = get_field('speaker_host')
            special_guests = get_field('special_guests')
            theme = get_field('theme')
            agenda = get_field('agenda')
            registration_info = get_field('registration_info')
            cost_fees = get_field('cost_fees', 0)  # if empty, set to 0 (or you can choose None)
            contact_info = get_field('contact_info')
            childcare_availability = get_field('childcare_availability')
            accessibility = get_field('accessibility')
            promotional_materials = get_field('promotional_materials')
            volunteer_opportunities = get_field('volunteer_opportunities')
            parking_info = get_field('parking_info')
            dress_code = get_field('dress_code')
            food_beverages = get_field('food_beverages')
            event_sponsor = get_field('event_sponsor')
            social_media_hashtag = get_field('social_media_hashtag')
            donation_info = get_field('donation_info')
            safety_protocols = get_field('safety_protocols')
            follow_up = get_field('follow_up')
            event_coordinator = get_field('event_coordinator')
            announcements_reminders = get_field('announcements_reminders')
            feedback_form = get_field('feedback_form')
            live_streaming_details = get_field('live_streaming_details')
            event_objectives = get_field('event_objectives')

            # Retrieve the is_potluck value from the checkbox.
            # If the checkbox is checked, its value will be "1"; if not, it will be absent.
            is_potluck = request.form.get('is_potluck')
            if is_potluck == "1":
                is_potluck = 1
            else:
                is_potluck = 0

            # Create a tuple of exactly 30 values (note the additional is_potluck value).
            data_tuple = (
                event_name, event_date, event_time, location, description, speaker_host, special_guests,
                theme, agenda, registration_info, cost_fees, contact_info, childcare_availability,
                accessibility, promotional_materials, volunteer_opportunities, parking_info, dress_code,
                food_beverages, event_sponsor, social_media_hashtag, donation_info, safety_protocols,
                follow_up, event_coordinator, announcements_reminders, feedback_form,
                live_streaming_details, event_objectives, is_potluck
            )
            print(f"Loading into DB: {data_tuple}")

            conn = get_db_connection()
            cursor = conn.cursor()
            query = '''
                INSERT INTO events (
                    event_name, event_date, event_time, location, description, speaker_host, special_guests, theme, agenda, 
                    registration_info, cost_fees, contact_info, childcare_availability, accessibility, promotional_materials, 
                    volunteer_opportunities, parking_info, dress_code, food_beverages, event_sponsor, social_media_hashtag, 
                    donation_info, safety_protocols, follow_up, event_coordinator, announcements_reminders, feedback_form, 
                    live_streaming_details, event_objectives, is_potluck
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            '''
            cursor.execute(query, data_tuple)
            conn.commit()
            event_id = cursor.lastrowid
            print(f"Successfully input: Data inserted with event_id: {event_id}")

            log_change(
                user_id=session['user_id'],
                action='create',
                target_id=event_id,
                target_name=event_name,
                change_details=f"Created event: {event_name}"
            )
            flash('Event created successfully!')
        except Exception as e:
            print(f"Error occurred while adding event: {e}")
            flash(f"An error occurred while adding the event: {str(e)}")
        finally:
            if conn is not None:
                conn.close()
                print("Database connection closed.")
        return redirect(url_for('event.events'))
    return render_template('add_event.html')


# Route to edit an existing event
@event_bp.route('/edit/<int:event_id>', methods=['GET', 'POST'])
@role_required(['Admin', 'Owner'])
def edit_event(event_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        try:
            # Get form data
            event_name = request.form.get('event_name')
            event_date = request.form.get('event_date')
            event_time = request.form.get('event_time')
            location = request.form.get('location')
            description = request.form.get('description')
            speaker_host = request.form.get('speaker_host')
            special_guests = request.form.get('special_guests')
            theme = request.form.get('theme')
            agenda = request.form.get('agenda')
            registration_info = request.form.get('registration_info')
            cost_fees = request.form.get('cost_fees')
            contact_info = request.form.get('contact_info')
            is_potluck = request.form.get('is_potluck', 0)  # Default to 0 (No) if not set

            # Convert 'is_potluck' to integer (because form values are strings)
            is_potluck = 1 if is_potluck == "1" else 0

            # Update the event in the database
            cursor.execute('''
                UPDATE events SET
                    event_name = ?, event_date = ?, event_time = ?, location = ?, description = ?, 
                    speaker_host = ?, special_guests = ?, theme = ?, agenda = ?, registration_info = ?, 
                    cost_fees = ?, contact_info = ?, is_potluck = ?
                WHERE id = ?
            ''', (
                event_name, event_date, event_time, location, description,
                speaker_host, special_guests, theme, agenda, registration_info,
                cost_fees, contact_info, is_potluck, event_id
            ))
            conn.commit()

            # Log the event update
            log_change(user_id=session['user_id'], action='update', target_id=event_id,
                       target_name=event_name, change_details=f"Updated event: {event_name}")
            flash('Event updated successfully!')

        except sqlite3.Error as e:
            flash(f"An error occurred while updating the event: {str(e)}")
        finally:
            conn.close()

        return redirect(url_for('event.events'))

    # Fetch event details for editing
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


@event_bp.route('/potluck/add/<int:event_id>', methods=['POST'])
@role_required(['Owner', 'Admin', 'Staff', 'Members'])
def add_potluck_contribution(event_id):
    contribution = request.form.get('contribution')
    if not contribution:
        flash("Please enter a contribution.")
        return redirect(url_for('event.events'))

    conn = get_db_connection()
    try:
        # Verify that the event exists and is a potluck event (using indexing instead of .get())
        event = conn.execute('SELECT * FROM events WHERE id = ?', (event_id,)).fetchone()
        if not event or int(event['is_potluck'] or 0) != 1:
            flash("This event is not marked as a potluck event.")
            return redirect(url_for('event.events'))

        conn.execute(
            'INSERT INTO potluck_contributions (event_id, user_id, contribution) VALUES (?, ?, ?)',
            (event_id, session['user_id'], contribution)
        )
        conn.commit()
        flash("Contribution added successfully!")

        log_change(
            user_id=session['user_id'],
            action='contribute',
            target_id=event_id,
            target_name=event['event_name'],
            change_details="Added potluck contribution"
        )
    except sqlite3.Error as e:
        flash(f"An error occurred while adding your contribution: {str(e)}")
    finally:
        conn.close()

    return redirect(url_for('event.events'))


@event_bp.route('/potluck/edit/<int:contribution_id>', methods=['GET', 'POST'])
@role_required(['Owner', 'Admin', 'Staff', 'Members'])
def edit_potluck_contribution(contribution_id):
    conn = get_db_connection()
    contribution = conn.execute(
        'SELECT * FROM potluck_contributions WHERE id = ?', (contribution_id,)
    ).fetchone()
    if not contribution:
        conn.close()
        flash("Contribution not found.")
        return redirect(url_for('event.events'))

    # Allow editing if the current user owns the contribution,
    # or if the user has an elevated role (Owner/Admin).
    allowed_roles = ['Owner', 'Admin']
    if session['user_id'] != contribution['user_id'] and session.get('user_role') not in allowed_roles:
        conn.close()
        flash("You do not have permission to edit this contribution.")
        return redirect(url_for('event.events'))

    if request.method == 'POST':
        new_text = request.form.get('contribution')
        if not new_text:
            flash("Contribution text cannot be empty.")
            return redirect(url_for('event.edit_potluck_contribution', contribution_id=contribution_id))
        try:
            conn.execute(
                'UPDATE potluck_contributions SET contribution = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                (new_text, contribution_id)
            )
            conn.commit()
            flash("Contribution updated successfully!")
        except sqlite3.Error as e:
            flash(f"An error occurred while updating the contribution: {str(e)}")
        finally:
            conn.close()
        return redirect(url_for('event.events'))

    conn.close()
    return render_template('edit_potluck_contribution.html', contribution=contribution)


@event_bp.route('/potluck/delete/<int:contribution_id>', methods=['POST'])
@role_required(['Owner', 'Admin', 'Staff', 'Members'])
def delete_potluck_contribution(contribution_id):
    conn = get_db_connection()
    contribution = conn.execute(
        'SELECT * FROM potluck_contributions WHERE id = ?', (contribution_id,)
    ).fetchone()
    if not contribution:
        conn.close()
        flash("Contribution not found.")
        return redirect(url_for('event.events'))

    allowed_roles = ['Owner', 'Admin']
    if session['user_id'] != contribution['user_id'] and session.get('user_role') not in allowed_roles:
        conn.close()
        flash("You do not have permission to delete this contribution.")
        return redirect(url_for('event.events'))

    try:
        conn.execute('DELETE FROM potluck_contributions WHERE id = ?', (contribution_id,))
        conn.commit()
        flash("Contribution deleted successfully!")
    except sqlite3.Error as e:
        flash(f"An error occurred while deleting the contribution: {str(e)}")
    finally:
        conn.close()

    return redirect(url_for('event.events'))


@event_bp.route('/view_events')
@role_required(['Owner', 'Admin', 'Staff', 'Members'])
def view_events():
    conn = get_db_connection()
    try:
        events = conn.execute('SELECT * FROM events').fetchall()
    except sqlite3.Error as e:
        flash(f"An error occurred while fetching events: {str(e)}")
        events = []
    finally:
        conn.close()

    # Optional: Organize events by year or any other grouping you need.
    # For example:
    events_by_year = defaultdict(list)
    for event in events:
        try:
            event_year = datetime.strptime(event['event_date'], '%Y-%m-%d').year
            events_by_year[event_year].append(event)
        except ValueError:
            flash(f"Invalid date format for event: {event['event_name']}")
    events_by_year = dict(sorted(events_by_year.items(), reverse=True))

    return render_template('view_events.html', events=events, events_by_year=events_by_year)
