from flask import Blueprint, render_template, flash, redirect, url_for, request, jsonify
from flask_login import login_required, current_user
from sqlalchemy import func
from datetime import datetime
import random 

from . import db
from .models import Messages, Rooms, Bookings, Users, RoomTimeslot, TimeSlot, Admin_approvals

views = Blueprint('views', __name__)

# =========================================================
#  AI HELPER FUNCTIONS (Logic for your 4 AI Features)
# =========================================================

def analyze_messages_for_alerts():
    """
    AI MAINTENANCE: Scans contact messages for keywords like 'broken', 'wifi', etc.
    Returns a list of flagged alerts.
    """
    messages = Messages.query.order_by(Messages.timestamp.desc()).limit(50).all()
    alerts = []
    # Keywords that trigger the AI flag
    keywords = ['broken', 'wifi', 'projector', 'leak', 'faulty', 'not working', 'damage']
    
    for msg in messages:
        if any(word in msg.content.lower() for word in keywords):
            alerts.append({
                'is_critical': True,
                'content': msg.content,
                'sender_name': msg.name,
                'id': msg.id
            })
    return alerts

def get_availability_insights():
    """
    AI INSIGHTS: Aggregates booking data to predict demand and show stats.
    """
    # 1. Get Top 3 Popular Rooms
    top_rooms_query = (
        db.session.query(Rooms.room_name, func.count(Bookings.booking_id).label('booking_count'))
        .join(Bookings, Rooms.room_id == Bookings.r_id)
        .group_by(Rooms.room_name)
        .order_by(func.count(Bookings.booking_id).desc())
        .limit(3)
        .all()
    )
    
    # Convert query result to list of dicts for the template
    top_rooms = [{'room_name': r[0], 'booking_count': r[1]} for r in top_rooms_query]

    # 2. Count Pending Approvals
    pending_count = Admin_approvals.query.filter_by(status='Pending').count()

    # 3. Generate Mock Forecast (In real AI, this would use regression models)
    forecasts = [
        "High demand expected next Tuesday between 10 AM and 2 PM.",
        "Fridays are currently showing low utilization. Good for rescheduling.",
        "Lab 405 is trending as the most requested room this month."
    ]
    
    return {
        'forecast': random.choice(forecasts),
        'top_rooms': top_rooms,
        'pending_approvals': pending_count
    }

def get_smart_schedule_recommendation(form_data):
    """
    AI SCHEDULING: Takes form data and recommends a room.
    """
    # MOCK LOGIC: In a real app, check constraints against RoomTimeslot
    # Here we just pick a room that "fits" randomly for demonstration
    
    all_rooms = Rooms.query.all()
    if not all_rooms:
        return None
        
    recommended = random.choice(all_rooms)
    
    return {
        'room_name': recommended.room_name,
        'capacity': recommended.capacity,
        'reason': f"Based on your request for {form_data.get('preferred_time')}, this room offers the best equipment match.",
        'available_slots': [f"{form_data.get('preferred_time')} - {int(form_data.get('preferred_time')[:2])+1}:00"]
    }

# --- Helper for Chatbot API ---
def get_room_status_summary():
    rooms = Rooms.query.limit(5).all()
    today = datetime.utcnow().date()
    summary = "Here is the current room status:\n"
    for room in rooms:
        active_booking = Bookings.query.filter_by(r_id=room.room_id, booking_date=today, status='Confirmed').first()
        status = "Occupied" if active_booking else "Available"
        summary += f"- {room.room_name}: {status}\n"
    return summary

def generate_mock_response(user_message):
    msg = user_message.lower()
    if "hello" in msg or "hi" in msg:
        return "Hello! I am your Smart Classroom Assistant. Ask me about room availability or recommendations."
    elif "status" in msg or "free" in msg:
        return get_room_status_summary()
    elif "recommend" in msg:
        rec = Rooms.query.first()
        return f"I recommend {rec.room_name} (Capacity: {rec.capacity}) based on historical usage."
    elif "maintenance" in msg:
        return "You can report maintenance issues via the Contact page. Our AI scans these for critical alerts."
    else:
        return "I'm not sure. Try asking 'Which rooms are free?' or 'Recommend a room'."

# =========================================================
#  AI FEATURE ROUTES
# =========================================================

@views.route('/ai/recommendations')
@login_required
def ai_recommendations():
    """Renders the Chatbot Interface"""
    return render_template('ai_recommendations.html', user=current_user)

@views.route('/ai/maintenance')
@login_required
def ai_maintenance():
    """Renders the Maintenance Alerts Page"""
    # Only allow admins to see maintenance logs
    if current_user.role != 'admin':
        flash("Access Denied: Admin Only", "error")
        return redirect(url_for('views.home'))
        
    alerts = analyze_messages_for_alerts()
    return render_template('ai_maintenance.html', alerts=alerts, user=current_user)

@views.route('/ai/insights')
@login_required
def ai_insights():
    """Renders the Predictive Insights Page"""
    insights_data = get_availability_insights()
    return render_template('ai_insights.html', insights=insights_data, user=current_user)

@views.route('/ai/scheduling', methods=['GET', 'POST'])
@login_required
def ai_scheduling_tool():
    """Renders the Smart Scheduling Tool"""
    recommendation = None
    
    if request.method == 'POST':
        # Capture form data
        form_data = {
            'course_name': request.form.get('course_name'),
            'preferred_date': request.form.get('preferred_date'),
            'preferred_time': request.form.get('preferred_time')
        }
        # Run AI logic
        recommendation = get_smart_schedule_recommendation(form_data)
        
    return render_template('ai_scheduling.html', recommendation=recommendation, user=current_user)

# =========================================================
#  STANDARD ROUTES
# =========================================================

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
        if 'add_room' in request.form:
            room_name = request.form.get('room_name')
            capacity = request.form.get('capacity')
            location = request.form.get('location')
            amenities = request.form.get('amenities')
            new_room = Rooms(room_name=room_name, capacity=capacity, location=location, amenities=amenities)
            db.session.add(new_room)
            db.session.commit()
            flash('Room added successfully!', 'success')
        elif 'delete_room' in request.form:
            room_id = request.form.get('room_id')
            room_to_delete = Rooms.query.get(room_id)
            if room_to_delete:
                db.session.delete(room_to_delete)
                db.session.commit()
                flash('Room deleted successfully!', 'success')
            else:
                flash('Room not found!', 'error')
        return redirect(url_for('views.manage_rooms'))
    rooms = Rooms.query.all()
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
    # Basic Stats for dashboard
    user_type_filter = request.args.get('user_type')
    date_filter = request.args.get('date')
    base_query = Bookings.query.join(Users)

    if user_type_filter:
        base_query = base_query.filter(Users.role == user_type_filter)
    if date_filter:
        try:
            parsed_date = datetime.strptime(date_filter, "%Y-%m-%d")
            base_query = base_query.filter(Bookings.date >= parsed_date)
        except ValueError:
            flash("Invalid date format. Use YYYY-MM-DD.", category="error")

    student_count = Bookings.query.join(Users).filter(Users.role == 'student').count()
    faculty_count = Bookings.query.join(Users).filter(Users.role == 'faculty').count()
    admin_count = Bookings.query.join(Users).filter(Users.role == 'admin').count()
    user_type_data = [student_count, faculty_count, admin_count]

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
    timeslot_groups = {}
    for ts in room_timeslots:
        timeslot_groups.setdefault(ts.timeslot_id, []).append(ts)
    existing_bookings = Bookings.query.filter_by(r_id=room_id).all()
    booked_slots = {(b.room_timeslot_id, b.booking_date.strftime('%A')): b for b in existing_bookings}
    grouped_schedule = {
        ts_id: {'timeslot': ts_list[0].timeslot, 'days': {}} for ts_id, ts_list in timeslot_groups.items()
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
    existing_booking = Bookings.query.filter_by(room_timeslot_id=slot.id, booking_date=datetime.utcnow().date()).first()
    
    if existing_booking:
        if existing_booking.status == "Approved":
            flash("This slot is already booked.", "warning")
            return redirect(request.referrer or url_for('views.view_schedule', room_id=slot.room_id))
        elif existing_booking.status == "Pending" and existing_booking.user_id == user.id:
            flash("Request Already sent. Await admin approval", "warning")
            return redirect(request.referrer or url_for('views.view_schedule', room_id=slot.room_id))

    status = "Confirmed" if current_user.role in ["faculty", "admin"] else "Pending"
    check_in_time = datetime.utcnow() if status == "Confirmed" else None

    booking = Bookings(
        user_id=current_user.id,
        r_id=slot.room_id,
        room_timeslot_id=slot.id,
        booking_date=datetime.utcnow().date(),
        status=status,
        check_in_time=check_in_time
    )
    db.session.add(booking)
    db.session.flush()

    approval_status = "Approved" if current_user.role in ["faculty", "admin"] else "Pending"
    approval = Admin_approvals(booking_id=booking.booking_id, status=approval_status, reviewed_by=current_user.id if status == "Confirmed" else None)
    db.session.add(approval)

    slot.is_available = (approval_status != "Approved")
    db.session.commit()

    flash("Booking confirmed successfully!" if status == "Confirmed" else "Booking submitted. Awaiting admin approval.", "success" if status == "Confirmed" else "info")
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
    if not booking or current_user.role != 'admin':
        flash('Error processing request.', category='error')
        return redirect(url_for('views.pending_bookings'))

    if action == 'approve':
        booking.status = 'Approved'
    elif action == 'deny':
        booking.status = 'Denied'
    
    approval = Admin_approvals(booking_id=booking.booking_id, status=booking.status, reviewed_by=current_user.id)
    db.session.add(approval)
    db.session.commit()
    flash(f'Booking {action}d successfully.', category='success')
    return redirect(url_for('views.pending_bookings'))

@views.route('/my-bookings')
@login_required
def view_my_bookings():
    bookings = Bookings.query.filter_by(user_id=current_user.id).order_by(Bookings.booking_date.desc()).all()
    return render_template('student_bookings_status.html', bookings=bookings)

# =========================================================
#  MOCK CHATBOT API
# =========================================================

@views.route('/api/chatbot-response', methods=['POST'])
@login_required
def chatbot_api():
    if not request.is_json:
        return jsonify({"error": "Missing JSON"}), 400
    data = request.json
    try:
        ai_reply = generate_mock_response(data.get('message', ''))
    except Exception as e:
        print(f"Mock AI Error: {e}")
        ai_reply = "I am having trouble accessing the system right now."
    return jsonify({'response': ai_reply})