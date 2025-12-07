from flask import Blueprint, render_template, request, flash, redirect, url_for 
from .models import Users
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, login_required, logout_user, current_user

from . import db  #means from __init__.py import db


auth = Blueprint('auth', __name__)

@auth.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        user = Users.query.filter_by(email=email).first()

        if user:
            if check_password_hash(user.password, password):
                login_user(user, remember=True)
                if user.role == 'admin':
                    flash('Welcome Admin! You have successfully logged in.', category='success')
                    return redirect(url_for('views.admin_portal'))
                elif user.role == 'faculty':
                    flash('Welcome Faculty! You have successfully logged in.', category='success')
                    return redirect(url_for('views.faculty_portal'))
                elif user.role == 'student':
                    flash('Welcome Student! You have successfully logged in.', category='success')
                    return redirect(url_for('views.student_portal'))
                else:
                    flash('Unknown user role. Please contact admin.', category='error')
                    return redirect(url_for('auth.login'))
                
            else:
                flash('Incorrect password, Please try again.', category = 'error')
        else:
            flash('No account found with that email address. Please try again.')
    return render_template("login.html", user=current_user)

@auth.route('/logout')
@login_required # makes sure we cannot access this page unless user is logged in
def logout():
    logout_user()
    return redirect(url_for('auth.login'))


@auth.route('/sign-up', methods=['GET', 'POST'])
def sign_up():
    if request.method == 'POST':
        email = request.form.get('email')
        first_name = request.form.get('first_name')
        password1 = request.form.get('password1')
        password2 = request.form.get('password2')
        role = request.form.get('role')  # 'student', 'faculty', or 'admin'

        user = Users.query.filter_by(email=email).first()
        if user:
            flash('Email already exists', category='error')
        elif len(email) < 4:
            flash('Email must be greater than 3 characters.', category='error')
        elif len(first_name) < 2:
            flash('First name must be greater than 1 character.', category='error')
        elif password1 != password2:
            flash('Passwords don\'t match', category='error')
        elif len(password1) < 7:
            flash('Password must be at least 7 characters.', category='error')
        elif role not in ['student', 'faculty', 'admin']:
            flash('Invalid role selected.', category='error')
        else:
            hashed_password = generate_password_hash(password1, method='pbkdf2:sha256')
            new_user = Users(email=email, first_name=first_name, password=hashed_password, role=role)
            db.session.add(new_user)
            db.session.commit()
            login_user(new_user, remember=True)
            flash('Account created!', category='success')
            return redirect(url_for('auth.login'))

    return render_template("sign_up.html", user=current_user)

