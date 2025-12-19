from . import db
from flask_login import UserMixin
from datetime import datetime

class Messages(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    seen = db.Column(db.Boolean, default=False)

class Users(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    first_name = db.Column(db.String(150), nullable=False)
    password = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False)

    bookings = db.relationship('Bookings', back_populates='user')
    approvals_reviewed = db.relationship('Admin_approvals', back_populates='reviewer')

class Rooms(db.Model):
    room_id = db.Column(db.Integer, primary_key=True)
    room_name = db.Column(db.String(100), nullable=False)
    capacity = db.Column(db.Integer, nullable=False)
    location = db.Column(db.String(100), nullable=False)
    amenities = db.Column(db.String(250), nullable=False)
    is_available = db.Column(db.Boolean, nullable=False, default=True)

    bookings = db.relationship('Bookings', back_populates='room')
    stats = db.relationship('Bookings_stats', back_populates='room', uselist=False)
    room_timeslots = db.relationship('RoomTimeslot', back_populates='room', foreign_keys='RoomTimeslot.room_id')

class TimeSlot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)

    room_timeslots = db.relationship('RoomTimeslot', back_populates='timeslot')

class RoomTimeslot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.Integer, db.ForeignKey('rooms.room_id'), nullable=False)
    timeslot_id = db.Column(db.Integer, db.ForeignKey('time_slot.id'), nullable=False)
    day_of_week = db.Column(db.String(20), nullable=False)  # e.g., Monday, Tuesday
    is_available = db.Column(db.Boolean, default=True)

    room = db.relationship('Rooms', back_populates='room_timeslots')
    timeslot = db.relationship('TimeSlot', back_populates='room_timeslots')

class Bookings(db.Model):
    booking_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    r_id = db.Column(db.Integer, db.ForeignKey('rooms.room_id'), nullable=False)
    room_timeslot_id = db.Column(db.Integer, db.ForeignKey('room_timeslot.id'), nullable=False)

    booking_date = db.Column(db.Date, nullable=False, default=datetime.utcnow().date())
    status = db.Column(db.String(50), nullable=False, default='Pending')
    check_in_time = db.Column(db.DateTime, default=datetime.utcnow, nullable=True)

    user = db.relationship('Users', back_populates='bookings')
    room = db.relationship('Rooms', back_populates='bookings')
    room_timeslot = db.relationship('RoomTimeslot')
    approvals = db.relationship('Admin_approvals', back_populates='booking')

class Bookings_stats(db.Model):
    stat_id = db.Column(db.Integer, primary_key=True)
    r_id = db.Column(db.Integer, db.ForeignKey('rooms.room_id'), nullable=False)
    total_bookings = db.Column(db.Integer)
    total_cancellations = db.Column(db.Integer)

    room = db.relationship('Rooms', back_populates='stats')

class Admin_approvals(db.Model):
    approval_id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('bookings.booking_id'), nullable=False)
    status = db.Column(db.String(20), nullable=False)
    reviewed_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    review_date = db.Column(db.DateTime, default=datetime.utcnow)

    booking = db.relationship('Bookings', back_populates='approvals')
    reviewer = db.relationship('Users', back_populates='approvals_reviewed')

    # --- NEW MODELS FOR DATE-BASED BOOKING SYSTEM ---

class RoomsList(db.Model):
    __tablename__ = 'rooms_list'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    capacity = db.Column(db.Integer, default=50)
    is_active = db.Column(db.Boolean, default=True)
    amenities = db.Column(db.Text, nullable=True)
    location = db.Column(db.String(100), nullable=True)
    
    # Relationships
    schedules = db.relationship('SemesterSchedule', backref='room', lazy=True)
    bookings = db.relationship('BookingsNew', backref='room', lazy=True)

class SemesterSchedule(db.Model):
    __tablename__ = 'semester_schedule'
    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.Integer, db.ForeignKey('rooms_list.id'), nullable=False)
    day_of_week = db.Column(db.String(15), nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    course_name = db.Column(db.String(100), nullable=True)

class BookingsNew(db.Model):
    __tablename__ = 'bookings_new'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    room_id = db.Column(db.Integer, db.ForeignKey('rooms_list.id'), nullable=False)
    booking_date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    status = db.Column(db.String(20), default='Pending') # 'Confirmed', 'Pending', 'Rejected'
    reason = db.Column(db.Text, nullable=True) # For > 6 PM applications
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationship to User (Assuming your Users table is named 'users')
    user = db.relationship('Users', backref='new_bookings')
