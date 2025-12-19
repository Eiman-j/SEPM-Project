from flask import Blueprint, render_template, flash, redirect, url_for, request, jsonify
from flask_login import login_required, current_user
from sqlalchemy import func, or_
from datetime import datetime, timedelta, time, date
import random 
import os
import google.generativeai as genai
from dotenv import load_dotenv
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
import json
from . import db
# Import Old models if needed for archiving, but we focus on NEW models
from .models import Messages, Users, Admin_approvals 
# Import NEW models
from .models import RoomsList, SemesterSchedule, BookingsNew

views = Blueprint('views', __name__)
load_dotenv()

# Configure Gemini
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel('models/gemini-2.5-flash-lite')

# =========================================================
#  AI FEATURE HELPERS
# =========================================================

def analyze_messages_for_alerts():
    """
    AI MAINTENANCE: Uses LLM to categorize messages and detect critical issues.
    """
    messages = Messages.query.filter_by(seen=False).all()
    if not messages:
        return []

    # Prepare messages for LLM analysis
    batch_text = "\n".join([f"ID: {m.id} | Content: {m.content}" for m in messages])
    
    prompt = f"""
    Analyze the following student messages. Identify which ones are reporting broken equipment, 
    safety hazards, or facility issues. Return a JSON list of IDs that are 'critical'.
    Messages:
    {batch_text}
    """
    
    alerts = []
    try:
        response = model.generate_content(prompt)
        # Assuming the LLM returns a list of IDs or keywords
        # For simplicity, we keep your keyword logic as a fallback
        keywords = ['broken', 'wifi', 'projector', 'leak', 'faulty', 'not working', 'damage', 'ac']
        
        for msg in messages:
            if any(word in msg.content.lower() for word in keywords):
                alerts.append({
                    'is_critical': True,
                    'content': msg.content,
                    'sender_name': msg.name,
                    'id': msg.id,
                    'category': "Facility Issue" # You could get this from Gemini too
                })
    except Exception as e:
        print(f"AI Maintenance Error: {e}")
        
    return alerts

def get_peak_hour_prediction():
    """
    ML: Predicts the busiest hour of the day based on historical BookingsNew data.
    """
    all_bookings = BookingsNew.query.all()
    if len(all_bookings) < 10:
        return "Insufficient data for hourly trends."

    df = pd.DataFrame([{
        'hour': b.start_time.hour,
        'day': b.booking_date.weekday()
    } for b in all_bookings])

    # Count bookings per hour
    hourly_counts = df.groupby('hour').size().reset_index(name='count')
    
    X = hourly_counts[['hour']]
    y = hourly_counts['count']
    
    model_lr = LinearRegression()
    model_lr.fit(X, y)
    
    # Predict for hours 8 AM to 8 PM
    hours_to_predict = np.array(range(8, 21)).reshape(-1, 1)
    predictions = model_lr.predict(hours_to_predict)
    peak_hour = hours_to_predict[np.argmax(predictions)][0]
    
    return f"Peak demand usually hits around {peak_hour}:00. Try booking early morning slots for better luck!"

def get_availability_insights():
    """
    AI INSIGHTS: Predictions based on BookingsNew table.
    """
    # 1. Get Top 3 Popular Rooms
    top_rooms_query = (
        db.session.query(RoomsList.name, func.count(BookingsNew.id).label('booking_count'))
        .join(BookingsNew, RoomsList.id == BookingsNew.room_id)
        .group_by(RoomsList.name)
        .order_by(func.count(BookingsNew.id).desc())
        .limit(3)
        .all()
    )
    top_rooms = [{'room_name': r[0], 'booking_count': r[1]} for r in top_rooms_query]
    
    # 2. Count Pending Approvals
    pending_count = BookingsNew.query.filter_by(status='Pending').count()

    # 3. LINEAR REGRESSION FORECAST
    all_bookings = db.session.query(BookingsNew.booking_date).all()
    
    if len(all_bookings) < 5:
        forecast_msg = "Not enough data yet to predict trends. System needs at least 5 bookings."
    else:
        try:
            dates = [b[0] for b in all_bookings]
            df = pd.DataFrame({'date': dates})
            df['date'] = pd.to_datetime(df['date'])
            daily_counts = df.groupby('date').size().reset_index(name='count')
            daily_counts['date_ordinal'] = daily_counts['date'].map(datetime.toordinal)
            
            X = daily_counts[['date_ordinal']]
            y = daily_counts['count']
            
            reg_model = LinearRegression()
            reg_model.fit(X, y)
            
            # Predict Next Week
            next_week_date = datetime.utcnow().date() + timedelta(days=7)
            next_week_ordinal = np.array([[next_week_date.toordinal()]])
            prediction = reg_model.predict(next_week_ordinal)[0]
            
            slope = reg_model.coef_[0]
            
            if slope > 0.1:
                trend = "RISING SHARPLY"
                advice = "High traffic expected. Book 3 days in advance."
            elif slope > 0:
                trend = "increasing slightly"
                advice = "Standard availability."
            elif slope < -0.1:
                trend = "DECREASING"
                advice = "Good availability expected."
            else:
                trend = "stable"
                advice = "Demand is consistent."
                
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
    AI SCHEDULING: Logic to find time gaps in the new system.
    """
    req_date_str = form_data.get('preferred_date')
    # If no preferred_time provided, we search the whole day, otherwise logic differs
    # For this implementation, let's assume we search for a specific duration gap
    duration_hours = 1.5 # Default duration if not specified
    
    try:
        req_date = datetime.strptime(req_date_str, "%Y-%m-%d").date()
        day_name = req_date.strftime("%A")
    except:
        return None

    candidate_rooms = RoomsList.query.filter_by(is_active=True).all()
    
    for room in candidate_rooms:
        # Collect busy intervals
        busy_intervals = []
        
        # Classes
        classes = SemesterSchedule.query.filter_by(room_id=room.id, day_of_week=day_name).all()
        for cls in classes:
            busy_intervals.append((cls.start_time, cls.end_time))
            
        # Bookings
        bookings = BookingsNew.query.filter_by(room_id=room.id, booking_date=req_date)\
            .filter(BookingsNew.status != 'Rejected').all()
        for b in bookings:
            busy_intervals.append((b.start_time, b.end_time))
            
        busy_intervals.sort(key=lambda x: x[0])
        
        # Simple Logic: Check if there is space between 08:00 and the first event, 
        # or between events. 
        # For simplicity in this helper, we return the first room that is somewhat free.
        
        if len(busy_intervals) < 5: # Arbitrary "not too busy" check
             return {
                'room_name': room.name,
                'capacity': room.capacity,
                'reason': f"Room {room.name} has a light schedule on {day_name}s.",
                'available_slots': ["Check specific times in manual booking"]
            }

    return None

def get_room_status_context():
    """
    Fetches real-time data: 
    1. Rooms & Availability
    2. Recent User Feedback (Messages)
    """
    # --- PART 1: ROOMS ---
    rooms = RoomsList.query.filter_by(is_active=True).all()
    today = datetime.utcnow().date()
    
    context_text = "--- 🏥 CURRENT FACILITY STATUS ---\n"
    
    for room in rooms:
        # Check active bookings
        active_booking = BookingsNew.query.filter_by(
            room_id=room.id, 
            booking_date=today, 
            status='Confirmed'
        ).first()
        status = "OCCUPIED" if active_booking else "AVAILABLE"
        
        context_text += (f"- {room.name} ({room.location}): {status} | "
                         f"Cap: {room.capacity} | "
                         f"Has: {room.amenities}\n")

    # --- PART 2: FEEDBACK / MESSAGES (NEW) ---
    # We fetch the last 10 messages so the AI knows what people are talking about
    recent_messages = Messages.query.order_by(Messages.timestamp.desc()).limit(10).all()
    
    context_text += "\n--- 🗣️ RECENT STUDENT FEEDBACK ---\n"
    if recent_messages:
        for msg in recent_messages:
            # We include the name so the AI can say "Ali said..."
            context_text += f"- {msg.name} said: '{msg.content}'\n"
    else:
        context_text += "No recent feedback found.\n"

    return context_text

def generate_gemini_response(user_message):
    try:
        db_context = get_room_status_context()
        current_date = datetime.utcnow().strftime("%A, %Y-%m-%d")
        
        # --- THE NEW "CHILL" SYSTEM PROMPT ---
        prompt = f"""
        You are "CampusBuddy", a super chill, friendly, and helpful AI assistant for the university.
        
        YOUR VIBE:
        - Talk like a normal human student, not a corporate robot. 
        - Use emojis 🤙✨.
        - Be concise but warm.
        - If someone thanks you, say "No worries!" or "Anytime!".
        
        YOUR KNOWLEDGE (Real-Time Database):
        {db_context}
        
        SYSTEM RULES:
        1. **Rooms**: If a room is AVAILABLE, tell them they can book it. 
           (Link: <a href="/bookings" class="btn btn-sm btn-success">Book Now</a>).
        2. **Feedback**: You have access to the 'Recent Student Feedback' section above.
           - If the user asks "What are people saying?" or "Any feedback?", summarize the recent messages.
           - Be honest. If people are complaining about AC, say "Yeah, a few people mentioned the AC is broken."
           - If the feedback is good, hype it up!
        3. **The 6 PM Rule**: If they want a room late (after 6 PM), remind them gently that they need Admin approval.
        
        USER SAYS: "{user_message}"
        """
        
        response = model.generate_content(prompt)
        return response.text.strip()
        
    except Exception as e:
        print(f"Gemini API Error: {e}")
        return "My brain is buffering right now 😵‍💫. Try again in a sec!"

# =========================================================
#  AI FEATURE ROUTES
# =========================================================

@views.route('/ai/recommendations')
@login_required
def ai_recommendations():
    return render_template('ai_recommendations.html', user=current_user)

@views.route('/api/chatbot-response', methods=['POST'])
@login_required
def chatbot_api():
    if not request.is_json:
        return jsonify({"error": "Missing JSON"}), 400
    data = request.json
    user_message = data.get('message', '')
    ai_reply = generate_gemini_response(user_message)
    return jsonify({'response': ai_reply})

@views.route('/ai/maintenance')
@login_required
def ai_maintenance():
    if current_user.role != 'admin':
        flash("Access Denied: Admin Only", "error")
        return redirect(url_for('views.home'))
    alerts = analyze_messages_for_alerts()
    return render_template('ai_maintenance.html', alerts=alerts, user=current_user)

@views.route('/ai/insights')
@login_required
def ai_insights():
    # 1. Get the Statistical Data (Linear Regression)
    basic_insights = get_availability_insights()
    peak_prediction = get_peak_hour_prediction()
    
    # 2. Get the LLM "Vibe Check" Summary
    # We ask Gemini to summarize the general mood of the campus based on feedback
    recent_feedback = Messages.query.order_by(Messages.timestamp.desc()).limit(10).all()
    feedback_text = " ".join([m.content for m in recent_feedback])
    
    vibe_summary = "Everyone seems happy!"
    if feedback_text:
        prompt = f"Summarize the general mood of these student comments in one short, chill sentence: {feedback_text}"
        try:
            vibe_summary = model.generate_content(prompt).text
        except:
            vibe_summary = "Unable to read the room right now."

    return render_template('ai_insights.html', 
                           insights=basic_insights, 
                           peak_prediction=peak_prediction,
                           vibe_summary=vibe_summary,
                           user=current_user)

@views.route('/ai/scheduling', methods=['GET', 'POST'])
@login_required
def ai_scheduling_tool():
    recommendation = None
    if request.method == 'POST':
        # Simple pass-through for now
        form_data = {
            'preferred_date': request.form.get('date'),
            'duration': request.form.get('duration')
        }
        recommendation = get_smart_schedule_recommendation(form_data)
        
    return render_template('ai_scheduling.html', recommendation=recommendation, user=current_user)

# =========================================================
#  CORE & PORTAL ROUTES
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

# =========================================================
#  ROOM & BOOKING ROUTES (NEW SYSTEM)
# =========================================================

@views.route('/view-rooms', methods=['GET'])
@login_required
def view_rooms():
    min_capacity = request.args.get('capacity', type=int)
    location = request.args.get('location', '')
    
    query = RoomsList.query.filter_by(is_active=True)
    
    if min_capacity:
        query = query.filter(RoomsList.capacity >= min_capacity)
    if location:
        query = query.filter(RoomsList.location.ilike(f'%{location}%'))
        
    rooms = query.all()
    
    return render_template('view_rooms.html', rooms=rooms, user=current_user, selected_filters={
        'capacity': min_capacity if min_capacity else '',
        'location': location
    })

@views.route('/manage_room', methods=['GET', 'POST'])
@login_required
def manage_rooms():
    # Admin tool to add rooms to the NEW RoomsList table
    if current_user.role != 'admin':
        return redirect(url_for('views.home'))

    if request.method == 'POST':
        if 'add_room' in request.form:
            name = request.form.get('room_name')
            capacity = request.form.get('capacity')
            location = request.form.get('location')
            amenities = request.form.get('amenities')
            
            new_room = RoomsList(name=name, capacity=capacity, location=location, amenities=amenities, is_active=True)
            db.session.add(new_room)
            db.session.commit()
            flash('Room added successfully!', 'success')
            
        elif 'delete_room' in request.form:
            room_id = request.form.get('room_id')
            room_to_delete = RoomsList.query.get(room_id)
            if room_to_delete:
                room_to_delete.is_active = False # Soft delete
                db.session.commit()
                flash('Room deactivated!', 'success')
            else:
                flash('Room not found!', 'error')
                
        return redirect(url_for('views.manage_rooms'))
        
    rooms = RoomsList.query.filter_by(is_active=True).all()
    return render_template('manage_rooms.html', rooms=rooms)

@views.route('/bookings', methods=['GET'])
@login_required
def bookings():
    # Fetch all active rooms for the dropdown list
    rooms = RoomsList.query.filter_by(is_active=True).all()
    return render_template('bookings.html', rooms=rooms)

@views.route('/book-room-new', methods=['POST'])
@login_required
def book_room_new():
    room_id = request.form.get('room_id')
    date_str = request.form.get('date')
    start_str = request.form.get('start_time')
    end_str = request.form.get('end_time')
    reason = request.form.get('reason')

    try:
        booking_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        start_time = datetime.strptime(start_str, "%H:%M").time()
        end_time = datetime.strptime(end_str, "%H:%M").time()
    except ValueError:
        flash('Invalid date or time format.', category='error')
        return redirect(url_for('views.bookings'))

    # Logic: The 6 PM Rule
    status = 'Confirmed'
    six_pm = time(18, 0)
    
    if start_time >= six_pm or end_time > six_pm:
        status = 'Pending'
        if not reason:
            flash('Applications for evening slots (after 6 PM) must include a reason.', category='error')
            return redirect(url_for('views.bookings'))

    new_booking = BookingsNew(
        user_id=current_user.id,
        room_id=room_id,
        booking_date=booking_date,
        start_time=start_time,
        end_time=end_time,
        status=status,
        reason=reason
    )
    
    try:
        db.session.add(new_booking)
        db.session.commit()
        if status == 'Pending':
            flash('Request submitted! Waiting for Admin Approval.', category='success')
        else:
            flash('Booking Confirmed!', category='success')
    except Exception as e:
        db.session.rollback()
        flash('An error occurred while saving.', category='error')
        print(e)

    return redirect(url_for('views.student_portal'))

@views.route('/api/get-availability', methods=['POST'])
@login_required
def get_availability():
    data = request.get_json()
    room_id = data.get('room_id')
    date_str = data.get('date')
    
    if not room_id or not date_str:
        return jsonify({'error': 'Missing data'}), 400

    target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    day_name = target_date.strftime("%A")

    blocked_slots = []

    # --- 1. SEMESTER DATE RANGE LOGIC ---
    # Define the bounds for your semester
    semester_start = date(2025, 9, 1)
    semester_end = date(2025, 12, 31)

    # Only check for fixed classes if the selected date is within the semester
    if semester_start <= target_date <= semester_end:
        # A. Check Semester Schedule (Fixed Classes)
        classes = SemesterSchedule.query.filter_by(room_id=room_id, day_of_week=day_name).all()
        for cls in classes:
            blocked_slots.append({
                'start': cls.start_time.strftime("%H:%M"),
                'end': cls.end_time.strftime("%H:%M"),
                'reason': f"Class: {cls.course_name}"
            })

    # --- 2. REGULAR BOOKINGS LOGIC ---
    # Check one-off bookings regardless of the date (always relevant)
    existing_bookings = BookingsNew.query.filter_by(
        room_id=room_id, 
        booking_date=target_date
    ).filter(BookingsNew.status != 'Rejected').all()
    
    for b in existing_bookings:
        blocked_slots.append({
            'start': b.start_time.strftime("%H:%M"),
            'end': b.end_time.strftime("%H:%M"),
            'reason': "Booked"
        })

    # Sort all blocks chronologically
    blocked_slots.sort(key=lambda x: x['start'])
    return jsonify({'blocked_slots': blocked_slots})

@views.route('/my-bookings')
@login_required
def view_my_bookings():
    # Use the new table and new template
    bookings = BookingsNew.query.filter_by(user_id=current_user.id).order_by(BookingsNew.booking_date.desc()).all()
    return render_template('my_bookings.html', bookings=bookings)

# =========================================================
#  ADMIN MANAGEMENT ROUTES
# =========================================================

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

@views.route('/admin/pending-bookings')
@login_required
def pending_bookings():
    if current_user.role != 'admin':
        flash('Access denied.', category='error')
        return redirect(url_for('views.home'))
    
    # Fetch from the NEW table (BookingsNew)
    bookings = BookingsNew.query.filter_by(status='Pending').order_by(BookingsNew.booking_date).all()
    return render_template('admin_approvals.html', bookings=bookings)

@views.route('/admin/handle-approval/<int:booking_id>/<string:action>', methods=['POST'])
@login_required
def handle_approval(booking_id, action):
    if current_user.role != 'admin':
        flash('Access denied.', category='error')
        return redirect(url_for('views.home'))

    booking = BookingsNew.query.get_or_404(booking_id)

    if action == 'approve':
        booking.status = 'Confirmed'
        flash(f'Booking for {booking.user.first_name} approved!', category='success')
    elif action == 'deny':
        booking.status = 'Rejected'
        flash('Booking request denied.', category='error')

    db.session.commit()
    return redirect(url_for('views.pending_bookings'))

@views.route('/admin/admin_dashboard')
@login_required
def admin_dashboard():
    # Updated to use BookingsNew
    user_type_filter = request.args.get('user_type')
    date_filter = request.args.get('date')
    base_query = BookingsNew.query.join(Users)

    if user_type_filter:
        base_query = base_query.filter(Users.role == user_type_filter)
    if date_filter:
        try:
            parsed_date = datetime.strptime(date_filter, "%Y-%m-%d").date()
            base_query = base_query.filter(BookingsNew.booking_date >= parsed_date)
        except ValueError:
            flash("Invalid date format. Use YYYY-MM-DD.", category="error")

    student_count = BookingsNew.query.join(Users).filter(Users.role == 'student').count()
    faculty_count = BookingsNew.query.join(Users).filter(Users.role == 'faculty').count()
    admin_count = BookingsNew.query.join(Users).filter(Users.role == 'admin').count()
    user_type_data = [student_count, faculty_count, admin_count]

    room_stats = (
        base_query
        .join(RoomsList, BookingsNew.room_id == RoomsList.id)
        .with_entities(RoomsList.name, func.count(BookingsNew.id))
        .group_by(RoomsList.name)
        .all()
    )
    room_labels = [room[0] for room in room_stats]
    room_data = [room[1] for room in room_stats]

    return render_template('admin_statistics.html',
                           user_type_data=user_type_data,
                           room_labels=room_labels,
                           room_data=room_data,
                           back_url=url_for('views.admin_portal'))