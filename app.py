from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import sqlite3
from datetime import datetime
import hashlib
import os

app = Flask(__name__)
app.secret_key = 'college_events_secret_2024'
DATABASE = 'college_events.db'

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'committee'
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS students (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        roll_no TEXT,
        department TEXT,
        joined_on TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT,
        venue TEXT,
        date TEXT,
        time TEXT,
        status TEXT DEFAULT 'upcoming',
        created_by INTEGER,
        FOREIGN KEY(created_by) REFERENCES users(id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS event_updates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id INTEGER NOT NULL,
        message TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        FOREIGN KEY(event_id) REFERENCES events(id)
    )''')

    admin_pw = hashlib.sha256('admin123'.encode()).hexdigest()
    c.execute("INSERT OR IGNORE INTO users (name, email, password, role) VALUES (?,?,?,?)",
              ('Admin', 'admin@college.edu', admin_pw, 'admin'))

    comm_pw = hashlib.sha256('comm123'.encode()).hexdigest()
    c.execute("INSERT OR IGNORE INTO users (name, email, password, role) VALUES (?,?,?,?)",
              ('Tech Committee', 'tech@college.edu', comm_pw, 'committee'))

    c.execute("SELECT COUNT(*) FROM events")
    if c.fetchone()[0] == 0:
        c.execute("""INSERT INTO events (title, description, venue, date, time, status, created_by)
                     VALUES (?,?,?,?,?,?,?)""",
                  ('TechFest 2024', 'Annual technical festival with coding, robotics and more.',
                   'Main Auditorium', '2024-12-20', '10:00', 'live', 2))
        c.execute("""INSERT INTO events (title, description, venue, date, time, status, created_by)
                     VALUES (?,?,?,?,?,?,?)""",
                  ('Cultural Night', 'Celebrate diversity with music, dance and art.',
                   'Open Air Theatre', '2024-12-25', '18:00', 'upcoming', 2))
        c.execute("""INSERT INTO event_updates (event_id, message, timestamp) VALUES (?,?,?)""",
                  (1, 'Registration desk is now open!', '09:45'))
        c.execute("""INSERT INTO event_updates (event_id, message, timestamp) VALUES (?,?,?)""",
                  (1, 'Coding competition started in Lab 3', '10:05'))
        c.execute("""INSERT INTO event_updates (event_id, message, timestamp) VALUES (?,?,?)""",
                  (1, 'Guest speaker Prof. Sharma has arrived', '10:30'))

    conn.commit()
    conn.close()

def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

@app.route('/')
def home():
    conn = get_db()
    live = conn.execute(
        "SELECT e.*, u.name as committee FROM events e JOIN users u ON e.created_by=u.id WHERE e.status='live' ORDER BY e.date DESC"
    ).fetchall()
    upcoming = conn.execute(
        "SELECT e.*, u.name as committee FROM events e JOIN users u ON e.created_by=u.id WHERE e.status='upcoming' ORDER BY e.date ASC"
    ).fetchall()
    conn.close()
    return render_template('home.html', live=live, upcoming=upcoming)

@app.route('/event/<int:event_id>')
def event_detail(event_id):
    conn = get_db()
    event = conn.execute(
        "SELECT e.*, u.name as committee FROM events e JOIN users u ON e.created_by=u.id WHERE e.id=?", (event_id,)
    ).fetchone()
    if not event:
        conn.close()
        return redirect(url_for('home'))
    updates = conn.execute(
        "SELECT * FROM event_updates WHERE event_id=? ORDER BY id ASC", (event_id,)
    ).fetchall()
    conn.close()
    return render_template('event_detail.html', event=event, updates=updates)

@app.route('/api/updates/<int:event_id>')
def get_updates(event_id):
    after = request.args.get('after', 0, type=int)
    conn = get_db()
    updates = conn.execute(
        "SELECT * FROM event_updates WHERE event_id=? AND id>? ORDER BY id ASC", (event_id, after)
    ).fetchall()
    event = conn.execute("SELECT status FROM events WHERE id=?", (event_id,)).fetchone()
    conn.close()
    return jsonify({
        'updates': [{'id': u['id'], 'message': u['message'], 'timestamp': u['timestamp']} for u in updates],
        'status': event['status'] if event else 'unknown'
    })

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        email = request.form['email']
        pw = hash_pw(request.form['password'])
        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE email=? AND password=?", (email, pw)).fetchone()
        conn.close()
        if user:
            session['user_id'] = user['id']
            session['name'] = user['name']
            session['role'] = user['role']
            if user['role'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('committee_dashboard'))
        error = 'Invalid credentials. Please try again.'
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

@app.route('/student/register', methods=['GET', 'POST'])
def student_register():
    error = None
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        roll_no = request.form.get('roll_no', '').strip()
        department = request.form.get('department', '').strip()
        joined_on = datetime.now().strftime('%Y-%m-%d')
        if not name or not email or not password:
            error = 'Please fill in all required fields.'
        else:
            conn = get_db()
            try:
                conn.execute(
                    "INSERT INTO students (name, email, password, roll_no, department, joined_on) VALUES (?,?,?,?,?,?)",
                    (name, email, hash_pw(password), roll_no, department, joined_on)
                )
                conn.commit()
                conn.close()
                return redirect(url_for('student_login'))
            except sqlite3.IntegrityError:
                error = 'This email is already registered. Please login instead.'
                conn.close()
    return render_template('student_register.html', error=error)

@app.route('/student/login', methods=['GET', 'POST'])
def student_login():
    error = None
    if request.method == 'POST':
        email = request.form['email']
        pw = hash_pw(request.form['password'])
        conn = get_db()
        student = conn.execute("SELECT * FROM students WHERE email=? AND password=?", (email, pw)).fetchone()
        conn.close()
        if student:
            session['student_id'] = student['id']
            session['student_name'] = student['name']
            session['role'] = 'student'
            return redirect(url_for('student_dashboard'))
        error = 'Invalid email or password. Please try again.'
    return render_template('student_login.html', error=error)

@app.route('/student/logout')
def student_logout():
    session.clear()
    return redirect(url_for('home'))

@app.route('/student/dashboard')
def student_dashboard():
    if 'student_id' not in session:
        return redirect(url_for('student_login'))
    conn = get_db()
    live = conn.execute(
        "SELECT e.*, u.name as committee FROM events e JOIN users u ON e.created_by=u.id WHERE e.status='live' ORDER BY e.date DESC"
    ).fetchall()
    upcoming = conn.execute(
        "SELECT e.*, u.name as committee FROM events e JOIN users u ON e.created_by=u.id WHERE e.status='upcoming' ORDER BY e.date ASC"
    ).fetchall()
    completed = conn.execute(
        "SELECT e.*, u.name as committee FROM events e JOIN users u ON e.created_by=u.id WHERE e.status='completed' ORDER BY e.date DESC"
    ).fetchall()
    conn.close()
    return render_template('student_dashboard.html', live=live, upcoming=upcoming, completed=completed)

@app.route('/committee')
def committee_dashboard():
    if 'user_id' not in session or session.get('role') not in ('committee', 'admin'):
        return redirect(url_for('login'))
    conn = get_db()
    events = conn.execute(
        "SELECT * FROM events WHERE created_by=? ORDER BY date DESC", (session['user_id'],)
    ).fetchall()
    conn.close()
    return render_template('committee_dashboard.html', events=events)

@app.route('/committee/create', methods=['GET', 'POST'])
def create_event():
    if 'user_id' not in session or session.get('role') not in ('committee', 'admin'):
        return redirect(url_for('login'))
    if request.method == 'POST':
        conn = get_db()
        conn.execute(
            "INSERT INTO events (title, description, venue, date, time, status, created_by) VALUES (?,?,?,?,?,?,?)",
            (request.form['title'], request.form['description'], request.form['venue'],
             request.form['date'], request.form['time'], 'upcoming', session['user_id'])
        )
        conn.commit()
        conn.close()
        return redirect(url_for('committee_dashboard'))
    return render_template('create_event.html')

@app.route('/committee/edit/<int:event_id>', methods=['GET', 'POST'])
def edit_event(event_id):
    if 'user_id' not in session or session.get('role') not in ('committee', 'admin'):
        return redirect(url_for('login'))
    conn = get_db()
    if session.get('role') == 'admin':
    event = conn.execute("SELECT * FROM events WHERE id=?", (event_id,)).fetchone()
else:
    event = conn.execute("SELECT * FROM events WHERE id=? AND created_by=?", (event_id, session['user_id'])).fetchone()
    if not event:
        conn.close()
        return redirect(url_for('committee_dashboard'))
    if request.method == 'POST':
        conn.execute(
            "UPDATE events SET title=?, description=?, venue=?, date=?, time=?, status=? WHERE id=?",
            (request.form['title'], request.form['description'], request.form['venue'],
             request.form['date'], request.form['time'], request.form['status'], event_id)
        )
        conn.commit()
        conn.close()
        return redirect(url_for('committee_dashboard'))
    conn.close()
    return render_template('edit_event.html', event=event)

@app.route('/committee/update/<int:event_id>', methods=['POST'])
def post_update(event_id):
    if 'user_id' not in session or session.get('role') not in ('committee', 'admin'):
        return redirect(url_for('login'))
    message = request.form.get('message', '').strip()
    if message:
        ts = datetime.now().strftime('%H:%M')
        conn = get_db()
        conn.execute("INSERT INTO event_updates (event_id, message, timestamp) VALUES (?,?,?)",
                     (event_id, message, ts))
        conn.commit()
        conn.close()
    return redirect(url_for('edit_event', event_id=event_id))

@app.route('/admin')
def admin_dashboard():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    conn = get_db()
    events = conn.execute(
        "SELECT e.*, u.name as committee FROM events e JOIN users u ON e.created_by=u.id ORDER BY e.date DESC"
    ).fetchall()
    users = conn.execute("SELECT * FROM users ORDER BY role").fetchall()
    students = conn.execute("SELECT * FROM students ORDER BY joined_on DESC").fetchall()
    conn.close()
    return render_template('admin_dashboard.html', events=events, users=users, students=students)

@app.route('/admin/delete/<int:event_id>', methods=['POST'])
def delete_event(event_id):
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    conn = get_db()
    conn.execute("DELETE FROM event_updates WHERE event_id=?", (event_id,))
    conn.execute("DELETE FROM events WHERE id=?", (event_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/add_user', methods=['POST'])
def add_user():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    conn = get_db()
    try:
        conn.execute("INSERT INTO users (name, email, password, role) VALUES (?,?,?,?)",
                     (request.form['name'], request.form['email'],
                      hash_pw(request.form['password']), request.form['role']))
        conn.commit()
    except:
        pass
    conn.close()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete_user/<int:user_id>', methods=['POST'])
def delete_user(user_id):
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    conn = get_db()
    conn.execute("DELETE FROM users WHERE id=? AND role != 'admin'", (user_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete_student/<int:student_id>', methods=['POST'])
def delete_student(student_id):
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    conn = get_db()
    conn.execute("DELETE FROM students WHERE id=?", (student_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_dashboard'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True)