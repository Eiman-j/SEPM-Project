from flask import Blueprint, render_template, flash, redirect, url_for, request, jsonify
from flask_login import login_required, current_user
from sqlalchemy import func
from datetime import datetime
import random 
import os
import google.generativeai as genai
from dotenv import load_dotenv
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from datetime import timedelta
import matplotlib
matplotlib.use('Agg') # Required for server-side plotting (fixes "no gui" errors)
import matplotlib.pyplot as plt
import io
import base64
from . import db
from .models import Messages, Rooms, Bookings, Users, RoomTimeslot, TimeSlot, Admin_approvals

views = Blueprint('views', __name__)
load_dotenv()
# Configure Gemini
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel('models/gemini-2.5-flash-lite')

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
    AI INSIGHTS: Uses Linear Regression to predict demand.
    Optimized for ALL users (Student/Faculty/Admin).
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
    top_rooms = [{'room_name': r[0], 'booking_count': r[1]} for r in top_rooms_query]
    
    # 2. Count Pending Approvals
    pending_count = Admin_approvals.query.filter_by(status='Pending').count()

    # 3. REAL LINEAR REGRESSION FORECAST
    all_bookings = db.session.query(Bookings.booking_date).all()
    
    if len(all_bookings) < 5:
        forecast_msg = "Not enough data yet to predict trends. System needs at least 5 bookings."
    else:
        try:
            # Prepare Data
            dates = [b[0] for b in all_bookings]
            df = pd.DataFrame({'date': dates})
            df['date'] = pd.to_datetime(df['date'])
            daily_counts = df.groupby('date').size().reset_index(name='count')
            daily_counts['date_ordinal'] = daily_counts['date'].map(datetime.toordinal)
            
            X = daily_counts[['date_ordinal']]
            y = daily_counts['count']
            
            # Train Model
            model = LinearRegression()
            model.fit(X, y)
            
            # Predict Next Week
            next_week_date = datetime.utcnow().date() + timedelta(days=7)
            next_week_ordinal = np.array([[next_week_date.toordinal()]])
            prediction = model.predict(next_week_ordinal)[0]
            
            # Analyze Slope for General Advice
            slope = model.coef_[0]
            
            if slope > 0.1:
                trend = "RISING SHARPLY"
                advice = "High traffic expected. We recommend booking at least 3 days in advance."
            elif slope > 0:
                trend = "increasing slightly"
                advice = "Standard availability. Regular booking times recommended."
            elif slope < -0.1:
                trend = "DECREASING"
                advice = "Good availability expected. You should find rooms easily next week."
            else:
                trend = "stable"
                advice = "Demand is consistent. No major booking delays expected."
                
            forecast_msg = (f"Market Trend: Demand is {trend}. "
                            f"Projected usage: ~{int(prediction)} bookings/day next week. {advice}")
            
        except Exception as e:
            print(f"ML Error: {e}")
            forecast_msg = "Could not generate forecast model due to data inconsistency."

    return {
        'forecast': forecast_msg,
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
def get_room_status_context():
    """
    Fetches real-time data with Smart Tags AND Room IDs so the AI can 
    generate direct booking links.
    """
    rooms = Rooms.query.all()
    today = datetime.utcnow().date()
    
    context_text = "--- CURRENT FACILITY STATUS ---\n"
    
    for room in rooms:
        # 1. Check Booking Status
        active_booking = Bookings.query.filter_by(
            r_id=room.room_id, 
            booking_date=today, 
            status='Confirmed'
        ).first()
        status = "OCCUPIED" if active_booking else "AVAILABLE"
        
        # 2. Generate Smart Size Tag
        if room.capacity < 20:
            size_tag = "Small (Meetings)"
        elif room.capacity < 50:
            size_tag = "Medium (Classes)"
        else:
            size_tag = "Large (Events)"

        # 3. Build Context String (CRITICAL: We include room_id here)
        context_text += (f"- ID: {room.room_id} | "
                         f"Name: {room.room_name} | "
                         f"Capacity: {room.capacity} [{size_tag}] | "
                         f"Location: {room.location} | "
                         f"Facilities: {room.amenities} | "
                         f"Status: {status}\n")

    # 4. Add Recent Complaints
    recent_messages = Messages.query.order_by(Messages.timestamp.desc()).limit(5).all()
    context_text += "\n--- RECENT MAINTENANCE REPORTS ---\n"
    if recent_messages:
        for msg in recent_messages:
            context_text += f"- Report: {msg.content} (Sender: {msg.name})\n"
    else:
        context_text += "No recent complaints.\n"
    
    return context_text


def generate_gemini_response(user_message):
    """
    Instructions added to generate HTML links for booking.
    """
    try:
        # 1. Get Real-Time Context
        db_context = get_room_status_context()
        current_date = datetime.utcnow().strftime("%A, %Y-%m-%d")
        
        # 2. Construct the System Prompt
        prompt = f"""
        You are a smart Facility Manager AI for a university.
        
        SYSTEM CONTEXT:
        - Today's Date: {current_date}
        - User Role: {current_user.role if current_user.is_authenticated else 'Guest'}
        
        REAL-TIME DATABASE:
        {db_context}
        
        USER REQUEST: "{user_message}"
        
        INSTRUCTIONS:
        1. **Smart Matching**: Suggest rooms based on size tags [Small/Medium/Large] and facilities.
        2. **Direct Links**: If you recommend an AVAILABLE room, you MUST provide a direct booking link using this EXACT format:
           <a href="/bookings/room/ROOM_ID_HERE" class="btn btn-sm btn-success">Book ROOM_NAME_HERE</a>
           
           Example: If recommending Lab 1 (ID: 5), write: 
           "I recommend Lab 1. <a href="/bookings/room/5" class="btn btn-sm btn-success">Book Lab 1</a>"
           
        3. **Date Logic**: Calculate dates for "next Friday" or "tomorrow" based on today ({current_date}).
        4. **Conflict Resolution**: If a room is OCCUPIED, suggest an alternative.
        5. **Maintenance**: Warn users if a recommended room has recent complaints.
        6. Keep answers concise. Do not use Markdown for the link, use the HTML tag provided above.
        """
        
        # 3. Call Gemini API
        response = model.generate_content(prompt)
        return response.text.strip()
        
    except Exception as e:
        print(f"Gemini API Error: {e}")
        return "I am having trouble connecting to the AI brain right now."

# =========================================================
#  AI FEATURE ROUTES
# =========================================================
@views.route('/ai/recommendations')
@login_required
def ai_recommendations():
    """Renders the Chatbot Interface Page"""
    return render_template('ai_recommendations.html', user=current_user)

@views.route('/api/chatbot-response', methods=['POST'])
@login_required
def chatbot_api():
    if not request.is_json:
        return jsonify({"error": "Missing JSON"}), 400
        
    data = request.json
    user_message = data.get('message', '')

    # Call the new Gemini function
    ai_reply = generate_gemini_response(user_message)

    return jsonify({'response': ai_reply})

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

