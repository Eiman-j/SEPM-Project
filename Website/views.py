from flask import Blueprint, render_template, flash, redirect, url_for, request
from flask_login import login_required, current_user
views = Blueprint('views', __name__)
from . import db
from . models import Messages, Rooms, Bookings, Users
import pandas as pd
from flask import jsonify
from sqlalchemy import func
from . models import Messages
from . models import Rooms, RoomTimeslot, TimeSlot,Admin_approvals
from datetime import datetime

# --- PLACEHOLDER AI FUNCTIONS ---
# These functions simulate the core AI/ML logic. You will replace the internal content later.

def get_smart_schedule_recommendation(date_str, preferred_time_str, user_id):
    """
    MOCK: This function would contain the AI logic to analyze bookings,
    room usage, and user history to recommend the best room.
    """
    # For now, return a mock recommendation result structure
    return {
        'room_name': 'Lab 405 (AI Recommended)',
        'capacity': 30,
        'reason': 'Optimal size for typical faculty course, and available at the requested time.',
        'available_slots': ['10:00 - 11:00 AM'] # Example of a smart-filtered slot
    }

def analyze_messages_for_alerts():
    """
    MOCK: This function analyzes Messages/Contact forms for recurring
    issues (e.g., 'Projector broken in Room 301') and flags them as alerts.
    """
    # Fetch all contact messages that are not yet marked as seen
    unseen_messages = Messages.query.filter_by(seen=False).all()
    alerts = []
    
    # Simple keyword-based AI mock logic
    keywords = {'projector', 'wifi', 'broken', 'faulty', 'leak'}
    
    for msg in unseen_messages:
        content_lower = msg.content.lower()
        if any(keyword in content_lower for keyword in keywords):
            alerts.append({
                'message_id': msg.id,
                'content': msg.content,
                'sender_name': msg.name,
                'is_critical': True 
            })
    return alerts

def get_availability_insights():
    """
    MOCK: This function calculates and returns predictive availability insights.
    """
    # Get top 3 most booked rooms for predictive insight
    room_popularity = (
        db.session.query(Rooms.room_name, func.count(Bookings.booking_id).label('booking_count'))
        .join(Bookings, Rooms.id == Bookings.r_id)
        .group_by(Rooms.room_name)
        .order_by(func.count(Bookings.booking_id).desc())
        .limit(3)
        .all()
    )
    
    # Get total pending approvals (a key insight for Admin)
    pending_approvals_count = Admin_approvals.query.filter_by(status='Pending').count()
    
    return {
        'top_rooms': room_popularity,
        'pending_approvals': pending_approvals_count,
        'forecast': 'High demand predicted for Wednesdays and Fridays from 9:00 AM to 1:00 PM.'
    }

# End of AI Functions





@views.route('/')
def home():
    return render_template('base.html')

@views.route('/admin')
@login_required
def admin_portal():
    if current_user.role != 'admin':
        flash('Access denied: Admins only.', 'error')
        return redirect(url_for('views.home'))

    return render_template('admin_portal.html', user=current_user)

@views.route('/student')
@login_required
def student_portal():
    if current_user.role != 'student':
        flash('Access denied: Students only.', 'error')
        return redirect(url_for('views.home'))

    return render_template('student_portal.html', user=current_user)

@views.route('/faculty')
@login_required
def faculty_portal():
    if current_user.role != 'faculty':
        flash('Access denied: Faculty only.', 'error')
        return redirect(url_for('views.home'))

    return render_template('faculty_portal.html', user=current_user)

@views.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name = request.form.get('first_name')
        email = request.form.get('email')
        content = request.form.get('mssg')

        new_message = Messages(name=name, email=email, content=content)
        db.session.add(new_message)
        db.session.commit()

        flash('Your message has been sent!', category='success')
        return redirect(url_for('views.contact'))

    return render_template('base.html')

@views.route('/view-rooms', methods=['GET'])
@login_required
def view_rooms():
    min_capacity = request.args.get('capacity', type=int)
    location = request.args.get('location', '')

    query = Rooms.query


    if min_capacity:
        query = query.filter(Rooms.capacity >= min_capacity)

    if location:
        query = query.filter(Rooms.location.ilike(f'%{location}%'))

    rooms = query.all()

    return render_template('view_rooms.html', rooms=rooms, user=current_user, selected_filters={
        'capacity': min_capacity if min_capacity else '',
        'location': location
    })


@views.route('/manage_room', methods=['GET', 'POST'])
@login_required
def manage_rooms():
    if request.method == 'POST':
        # If the request contains room data for adding a room
        if 'add_room' in request.form:
            room_name = request.form.get('room_name')
            capacity = request.form.get('capacity')
            location = request.form.get('location')
            amenities = request.form.get('amenities')

            # Create a new room entry
            new_room = Rooms(room_name=room_name, capacity=capacity, location=location, amenities=amenities)
            db.session.add(new_room)
            db.session.commit()

            flash('Room added successfully!', 'success')

        # If the request contains room data for deleting a room
        elif 'delete_room' in request.form:
            room_id = request.form.get('room_id')

            # Find the room to delete
            room_to_delete = Rooms.query.get(room_id)
            if room_to_delete:
                db.session.delete(room_to_delete)
                db.session.commit()
                flash('Room deleted successfully!', 'success')
            else:
                flash('Room not found!', 'error')

        return redirect(url_for('views.manage_rooms'))  # Redirect back to manage rooms page

    # If the request is GET, render the manage rooms page with the list of rooms
    rooms = Rooms.query.all()  # Get all rooms from the database
    return render_template('manage_rooms.html', rooms=rooms)


@views.route('/admin/contact-messages')
@login_required
def view_contact_messages():
    if current_user.role != 'admin':
        flash('Access denied.')
        return redirect(url_for('views.home'))

    messages = Messages.query.order_by(Messages.timestamp.desc()).all()
    return render_template('view_contact_messages.html', messages=messages)

@views.route('/admin/mark-seen/<int:message_id>', methods=['POST'])
@login_required
def mark_message_seen(message_id):
    if current_user.role != 'admin':
        flash('Access denied.')
        return redirect(url_for('views.home'))

    message = Messages.query.get_or_404(message_id)
    message.seen = True
    db.session.commit()
    flash('Message marked as seen.')
    return redirect(url_for('views.view_contact_messages'))

@views.route('/admin/admin_dashboard')
@login_required
def admin_dashboard():
    user_type_filter = request.args.get('user_type')
    date_filter = request.args.get('date')  # format: YYYY-MM-DD

    base_query = Bookings.query.join(Users)

    # Apply filters
    if user_type_filter:
        base_query = base_query.filter(Users.role == user_type_filter)

    if date_filter:
        try:
            parsed_date = datetime.strptime(date_filter, "%Y-%m-%d")
            base_query = base_query.filter(Bookings.date >= parsed_date)
        except ValueError:
            flash("Invalid date format. Use YYYY-MM-DD.", category="error")

    # Booking counts by user role (without filters to show full overview)
    student_count = Bookings.query.join(Users).filter(Users.role == 'student').count()
    faculty_count = Bookings.query.join(Users).filter(Users.role == 'faculty').count()
    admin_count = Bookings.query.join(Users).filter(Users.role == 'admin').count()
    user_type_data = [student_count, faculty_count, admin_count]

    # Room popularity (based on filtered bookings)
    room_stats = (
        base_query
        .join(Rooms)
        .with_entities(Rooms.room_name, func.count(Bookings.booking_id))
        .group_by(Rooms.room_name)
        .all()
    )
    room_labels = [room[0] for room in room_stats]
    room_data = [room[1] for room in room_stats]

    return render_template('admin_statistics.html',
                           user_type_data=user_type_data,
                           room_labels=room_labels,
                           room_data=room_data,
                           back_url=url_for('views.admin_portal'))

@views.route('/bookings')
def bookings():
    rooms = Rooms.query.all()
    return render_template('bookings.html', rooms=rooms)

@views.route('/bookings/room/<int:room_id>', methods=['GET'])
@login_required
def view_schedule(room_id):
    room = Rooms.query.get_or_404(room_id)
    room_timeslots = RoomTimeslot.query.filter_by(room_id=room_id).all()

    # Group by timeslot ID
    timeslot_groups = {}
    for ts in room_timeslots:
        timeslot_groups.setdefault(ts.timeslot_id, []).append(ts)

    # Get all bookings for the room
    existing_bookings = Bookings.query.filter_by(r_id=room_id).all()
    booked_slots = {(b.room_timeslot_id, b.booking_date.strftime('%A')): b for b in existing_bookings}

    # Build structured schedule
    grouped_schedule = {
        ts_id: {
            'timeslot': ts_list[0].timeslot,
            'days': {}
        } for ts_id, ts_list in timeslot_groups.items()
    }

    for ts_id, ts_list in timeslot_groups.items():
        for ts in ts_list:
            day = ts.day_of_week
            key = (ts.id, day)
            grouped_schedule[ts_id]['days'][day] = {
                'is_booked': key in booked_slots,
                'booking_info': booked_slots.get(key),
                'timeslot': ts
            }

    return render_template("schedule.html", room=room, grouped_schedule=grouped_schedule)


@views.route('/bookings/book/<int:room_timeslot_id>', methods=['POST'])
@login_required
def book_slot(room_timeslot_id):
    slot = RoomTimeslot.query.get_or_404(room_timeslot_id)
    user = current_user
    # Check if already booked
    existing_booking = Bookings.query.filter_by(
        room_timeslot_id=slot.id,
        booking_date=datetime.utcnow().date()
    ).first()
    if existing_booking and existing_booking.status == "Approved":
        flash("This slot is already booked.", "warning")
        return redirect(request.referrer or url_for('views.view_schedule', room_id=slot.room_id))
    elif existing_booking and existing_booking.status == "Pending" and existing_booking.user_id == user.id:
        flash("Request Already sent. Await admin approval", "warning")
        return redirect(request.referrer or url_for('views.view_schedule', room_id=slot.room_id))

    # Set booking status
    status = "Confirmed" if current_user.role in ["faculty", "admin"] else "Pending"
    check_in_time = datetime.utcnow() if status == "Confirmed" else None

    # Create booking
    booking = Bookings(
        user_id=current_user.id,
        r_id=slot.room_id,
        room_timeslot_id=slot.id,
        booking_date=datetime.utcnow().date(),
        status=status,
        check_in_time=check_in_time
    )
    db.session.add(booking)
    db.session.flush()  # get booking.booking_id before commit

    # Create admin approval
    approval_status = "Approved" if current_user.role in ["faculty", "admin"] else "Pending"
    approval = Admin_approvals(
        booking_id=booking.booking_id,
        status=approval_status,
        reviewed_by=current_user.id if status == "Confirmed" else None
    )
    db.session.add(approval)

    # Mark slot unavailable
    if approval_status == "Approved":

        slot.is_available = False
        db.session.commit()

    else:
        slot.is_available = True
        db.session.commit()

    if status == "Confirmed":
        flash("Booking confirmed successfully!", "success")
    else:
        flash("Booking submitted. Awaiting admin approval.", "info")

    return redirect(url_for('views.view_schedule', room_id=slot.room_id))

@views.route('/admin/pending-bookings')
@login_required
def pending_bookings():
    if current_user.role != 'admin':
        flash('Access denied.', category='error')
        return redirect(url_for('views.home'))

    bookings = Bookings.query.filter_by(status='Pending').all()
    return render_template('admin_approvals.html', bookings=bookings)


@views.route('/admin/handle-approval/<int:booking_id>/<string:action>', methods=['POST'])
@login_required
def handle_approval(booking_id, action):
    booking = Bookings.query.get(booking_id)

    if not booking:
        flash('Booking not found.', category='error')
        return redirect(url_for('views.pending_bookings'))

    if current_user.role != 'admin':
        flash('Unauthorized access.', category='error')
        return redirect(url_for('views.pending_bookings'))

    if action == 'approve':
        booking.status = 'Approved'
    elif action == 'deny':
        booking.status = 'Denied'
    else:
        flash('Invalid action.', category='error')
        return redirect(url_for('views.pending_bookings'))

    approval = Admin_approvals(
        booking_id=booking.booking_id,
        status=booking.status,
        reviewed_by=current_user.id
    )
    db.session.add(approval)
    db.session.commit()
    flash(f'Booking {action}d successfully.', category='success')
    return redirect(url_for('views.pending_bookings'))



@views.route('/my-bookings')
@login_required
def view_my_bookings():
    # Fetch all bookings made by the currently logged-in student
    bookings = (
        Bookings.query
        .filter_by(user_id=current_user.id)
        .order_by(Bookings.booking_date.desc())
        .all()
    )
    
    return render_template('student_bookings_status.html', bookings=bookings)


@views.route('/ai-scheduling-tool', methods=['GET', 'POST'])
@login_required
def ai_scheduling_tool():
    """
    Renders the Smart Scheduling page and processes the recommendation request.
    """
    recommendation = None
    
    if request.method == 'POST':
        # 1. Get user input from the form
        course_name = request.form.get('course_name')
        preferred_date = request.form.get('preferred_date') 
        preferred_time = request.form.get('preferred_time')
        
        if not course_name or not preferred_date or not preferred_time:
             flash('Please fill in all required fields for the smart schedule request.', 'error')
             return redirect(url_for('views.ai_scheduling_tool'))
        
        # 2. Call the AI logic
        try:
            # The AI function returns the best room based on the complex criteria
            recommendation = get_smart_schedule_recommendation(preferred_date, preferred_time, current_user.id)
            flash(f"AI Recommended Room: {recommendation['room_name']} ({recommendation['reason']})", 'success')
            
            # Optional: Auto-book the recommended slot (if user is faculty/admin)
            # This is complex and usually done in a separate step or API call
            
        except Exception as e:
            flash(f"An internal error occurred during AI scheduling: {e}", 'error')
            
    # 3. Render the template, passing the recommendation data
    return render_template('ai_scheduling.html', recommendation=recommendation, user=current_user)


@views.route('/ai-maintenance-alerts')
@login_required
def ai_maintenance_alerts():
    """
    Displays the Automated Maintenance Alerts generated by analyzing contact messages.
    Access restricted to Admins and Faculty.
    """
    if current_user.role not in ['admin', 'faculty']:
        flash('Access denied: Admins and Faculty only.', 'error')
        return redirect(url_for('views.home'))
        
    # Get the AI-analyzed alerts from contact messages
    maintenance_alerts = analyze_messages_for_alerts()
    
    return render_template('ai_maintenance.html', 
                           alerts=maintenance_alerts, 
                           user=current_user)

@views.route('/ai-availability-insights')
@login_required
def ai_availability_insights():
    """
    Displays the Predictive Room Availability Insights and usage statistics.
    """
    # Get the statistical data/forecast from the AI placeholder function
    insights_data = get_availability_insights()
    
    return render_template('ai_insights.html', 
                           insights=insights_data, 
                           user=current_user)


@views.route('/ai-chatbot')
@login_required
def ai_chatbot():
    """
    Renders the Smart Recommendations (Chatbot) interface.
    """
    return render_template('ai_recommendations.html', user=current_user)

@views.route('/api/chatbot-response', methods=['POST'])
@login_required
def chatbot_api():
    """
    API endpoint for the chatbot to send a message and receive a response.
    The frontend JS must call this endpoint.
    """
    # Ensure content is JSON
    if not request.is_json:
        return jsonify({"error": "Missing JSON in request"}), 400
        
    user_message = request.json.get('message')
    
    # Placeholder for actual chatbot logic (e.g., call a large language model API)
    if 'available' in user_message.lower() or 'free' in user_message.lower():
        response = "I can check availability. Please specify a room and a time."
    elif 'help' in user_message.lower():
        response = "I am a smart recommendation assistant. I can guide you to available rooms or forward you to the Smart Scheduling tool."
    else:
        response = f"I am currently processing your request: '{user_message}'. Please try asking about room availability or booking help."
        
    return jsonify({'response': response})


