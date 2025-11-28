import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import smtplib
import ssl
import random
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import subprocess
import threading

app = Flask(__name__)
app.secret_key = os.urandom(24)
app.permanent_session_lifetime = timedelta(days=7)
DATABASE = 'gesture_recognition.db'
otp_store = {}

# Email config
SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 587
SENDER_EMAIL = os.getenv('SENDER_EMAIL', 'yogeshraju60@gmail.com')
SENDER_PASSWORD = os.getenv('SENDER_PASSWORD','vuchwemeloypgjvr')

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        full_name TEXT NOT NULL,
        is_active BOOLEAN DEFAULT 1,
        is_admin BOOLEAN DEFAULT 0,
        email_verified BOOLEAN DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_login TIMESTAMP
    )
    ''')
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS feedback (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        name TEXT,
        email TEXT,
        message TEXT,
        submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    conn.commit()
    conn.close()

def send_email(to_email, subject, body):
    message = MIMEMultipart('alternative')
    message['Subject'] = subject
    message['From'] = SENDER_EMAIL
    message['To'] = to_email
    part = MIMEText(body, 'plain')
    message.attach(part)
    context = ssl.create_default_context()
    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls(context=context)
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, to_email, message.as_string())
        print(f"Email sent to {to_email}")
        return True
    except Exception as e:
        print(f"Failed to send email: {e}")
        return False

def generate_otp():
    return ''.join(random.choices('0123456789', k=6))

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email'].strip().lower()
        full_name = request.form['full_name'].strip()
        password = request.form['password']
        confirm = request.form['confirm']
        if not email or not full_name or not password:
            flash('Please fill all fields.', 'error')
            return render_template('register.html')
        if password != confirm:
            flash('Passwords do not match.', 'error')
            return render_template('register.html')
        conn = get_db_connection()
        user_exists = conn.execute('SELECT 1 FROM users WHERE email = ?', (email,)).fetchone()
        conn.close()
        if user_exists:
            flash('Email already registered.', 'error')
            return render_template('register.html')
        otp = generate_otp()
        otp_store[email] = {
            'code': otp,
            'expires': datetime.now() + timedelta(minutes=10),
            'full_name': full_name,
            'password': password
        }
        subject = "Your OTP Code - Hand Gesture Recognition"
        body = f"Hello {full_name},\n\nYour one-time verification code is {otp}. It expires in 10 minutes.\n\nThank you!"
        if not send_email(email, subject, body):
            flash('Failed to send OTP email. Please try later.', 'error')
            return render_template('register.html')
        session['pending_user'] = email
        flash('OTP sent to your email. Please verify below.', 'info')
        return redirect(url_for('verify_otp'))
    return render_template('register.html')

@app.route('/verify_otp', methods=['GET', 'POST'])
def verify_otp():
    email = session.get('pending_user')
    if not email or email not in otp_store:
        flash('No OTP request found. Please register again.', 'error')
        return redirect(url_for('register'))
    if request.method == 'POST':
        code_entered = request.form['otp'].strip()
        record = otp_store.get(email)
        if record and record['code'] == code_entered and datetime.now() < record['expires']:
            conn = get_db_connection()
            password_hash = generate_password_hash(record['password'])
            conn.execute(
                'INSERT INTO users (email, password_hash, full_name) VALUES (?, ?, ?)',
                (email, password_hash, record['full_name'])
            )
            conn.commit()
            conn.close()
            otp_store.pop(email, None)
            session.pop('pending_user', None)
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login'))
        else:
            flash('Invalid or expired OTP. Please try again.', 'error')
    return render_template('verify_otp.html')

@app.route('/resend_otp', methods=['POST'])
def resend_otp():
    data = request.get_json()
    email = data.get('email')
    if not email or email not in otp_store:
        return jsonify({'success': False, 'error': 'No pending OTP found for this email.'})
    otp = generate_otp()
    otp_store[email]['code'] = otp
    otp_store[email]['expires'] = datetime.now() + timedelta(minutes=10)
    full_name = otp_store[email]['full_name']
    subject = "Your New OTP Code - Hand Gesture Recognition"
    body = f"Hello {full_name},\n\nYour new verification code is {otp}. It expires in 10 minutes.\n\nThank you!"
    if send_email(email, subject, body):
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'Failed to send email.'})

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email'].strip().lower()
        password = request.form['password']
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        conn.close()
        if user and check_password_hash(user['password_hash'], password):
            session.permanent = True
            session['user_id'] = user['id']
            session['user_name'] = user['full_name']
            flash(f"Welcome back, {user['full_name']}!", 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password.', 'error')
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('dashboard.html', name=session.get('user_name'))

@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    conn = get_db_connection()
    user = conn.execute('SELECT full_name, email FROM users WHERE id = ?', (user_id,)).fetchone()
    conn.close()
    if not user:
        flash('User not found.', 'error')
        return redirect(url_for('login'))
    return render_template('profile.html', name=user['full_name'], email=user['email'])

@app.route('/gesture-recognition')
def gesture_recognition():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('gesture_recognition.html')

def run_gesture_app():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    gesture_script = os.path.join(base_dir, 'gesture_control.py')
    subprocess.Popen(['python', gesture_script])


@app.route('/launch-app', methods=['POST'])
def launch_app():
    threading.Thread(target=run_gesture_app).start()
    return jsonify({'success': True, 'message': 'Gesture recognition app launched.'})

# --------- FEEDBACK ROUTE (NEW) ----------
@app.route('/feedback', methods=['GET', 'POST'])
def feedback():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        message = request.form.get('message', '').strip()
        user_id = session.get('user_id')
        if not message:
            flash('Please enter your feedback message.', 'error')
        else:
            conn = get_db_connection()
            conn.execute('INSERT INTO feedback (user_id, name, email, message) VALUES (?, ?, ?, ?)',
                         (user_id, name, email, message))
            conn.commit()
            conn.close()
            flash('Thank you for your feedback!', 'success')
            return redirect(url_for('feedback'))
    return render_template('feedback.html')

# --------- ABOUT ROUTE (NEW) ----------
@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
