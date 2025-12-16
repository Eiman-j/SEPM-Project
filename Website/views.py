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
from transformers import pipeline # Import Hugging Face pipeline
import os
# --- PLACEHOLDER AI FUNCTIONS ---
# These functions simulate the core AI/ML logic. You will replace the internal content later.


print("Loading AI Model... please wait...")
try:
    # We use a 'text-generation' pipeline
    chatbot_pipeline = pipeline("text-generation", model="openai-community/gpt2")
    print("AI Model Loaded Successfully!")
except Exception as e:
    print(f"Error loading model: {e}")
    chatbot_pipeline = None

# --- AI HELPER FUNCTIONS (CONTEXT FOR CHATBOT) ---

def get_live_availability_context():
    """
    Scans the database to create a text summary of specific rooms.
    GPT-2 has a small context window, so we must be brief.
    """
    rooms = Rooms.query.all()
    # We limit to first 5 rooms to avoid overwhelming GPT-2
    context_data = "Current Room Status:\n"
    today = datetime.utcnow().date()

    count = 0
    for room in rooms:
        if count > 5: break 
        
        # Check bookings
        slots = RoomTimeslot.query.filter_by(room_id=room.room_id).all()
        is_free_now = True
        
        # Simple check: is there ANY booking for this room today?
        # (Simplified for GPT-2 brevity)
        active_booking = Bookings.query.filter_by(r_id=room.room_id, booking_date=today, status='Confirmed').first()
        
        status = "OCCUPIED" if active_booking else "FREE"
        context_data += f"- {room.room_name} is currently {status}.\n"
        count += 1
    
    return context_data
    """
    Calculates historical popularity based on total booking counts.
    Helps the AI recommend 'quiet' vs 'popular' rooms.
    """
    # Count total bookings per room
    stats = (
        db.session.query(Rooms.room_name, func.count(Bookings.booking_id))
        .join(Bookings, Rooms.room_id == Bookings.r_id)
        .group_by(Rooms.room_name)
        .all()
    )
    
    context_data = "\n--- HISTORICAL POPULARITY CONTEXT ---\n"
    if not stats:
        return context_data + "No historical data available yet.\n"

    # Calculate average to define 'High Demand'
    counts = [s[1] for s in stats]
    avg_bookings = sum(counts) / len(counts) if counts else 0
    
    for room_name, count in stats:
        demand = "High Demand" if count > avg_bookings else "Low Demand"
        context_data += f"{room_name}: {demand} ({count} past bookings).\n"
        
    return context_data

# --- OTHER AI PLACEHOLDERS (Kept as requested) ---

def get_smart_schedule_recommendation(date_str, preferred_time_str, user_id):
    """MOCK: Recommendation logic."""
    return {
        'room_name': 'Lab 405 (AI Recommended)',
        'capacity': 30,
        'reason': 'Optimal size for typical faculty course, and available at the requested time.',
        'available_slots': ['10:00 - 11:00 AM']
    }

def analyze_messages_for_alerts():
    """MOCK: Maintenance alerts logic."""
    unseen_messages = Messages.query.filter_by(seen=False).all()
    alerts = []
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
    """MOCK: Availability insights logic."""
    room_popularity = (
        db.session.query(Rooms.room_name, func.count(Bookings.booking_id).label('booking_count'))
        .join(Bookings, Rooms.room_id == Bookings.r_id)
        .group_by(Rooms.room_name)
        .order_by(func.count(Bookings.booking_id).desc())
        .limit(3)
        .all()
    )
    pending_approvals_count = Admin_approvals.query.filter_by(status='Pending').count()
    return {
        'top_rooms': room_popularity,
        'pending_approvals': pending_approvals_count,
        'forecast': 'High demand predicted for Wednesdays and Fridays from 9:00 AM to 1:00 PM.'
    }


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
        .join(Bookings, Rooms.room_id == Bookings.r_id)
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


@views.route('/api/chatbot-response', methods=['POST'])
@login_required
def chatbot_api():
    if not request.is_json:
        return jsonify({"error": "Missing JSON"}), 400
        
    user_message = request.json.get('message')
    
    # 1. Get simple context
    context = get_live_availability_context()
    
    # 2. Format Prompt for GPT-2
    # GPT-2 is a "completion" engine. We must format it like a script.
    prompt = f"""
Database:
{context}

User: {user_message}
Assistant:"""

    try:
        if chatbot_pipeline:
            # Generate text
            response = chatbot_pipeline(
                prompt, 
                max_new_tokens=40,  # Keep answer short
                num_return_sequences=1,
                pad_token_id=50256,
                truncation=True
            )
            
            # Extract the new text generated (remove the prompt part)
            full_text = response[0]['generated_text']
            ai_reply = full_text.replace(prompt, "").strip()
            
            # Clean up: GPT-2 sometimes rambles, stop at the first new line or period
            if "\n" in ai_reply:
                ai_reply = ai_reply.split("\n")[0]
        else:
            ai_reply = "Error: AI model failed to load on server start."
            
    except Exception as e:
        print(f"AI Error: {e}")
        ai_reply = "I am having trouble thinking right now."

    return jsonify({'response': ai_reply})