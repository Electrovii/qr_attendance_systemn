from flask import Flask, request, jsonify, send_file, send_from_directory, render_template
import qrcode
import sqlite3
import io
from datetime import datetime, timezone
import os
import time

app = Flask(__name__)

@app.before_request
def log_request_info():
    print(f"Request Method: {request.method}, URL: {request.url}")

# Serve the favicon.ico from the static folder
@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'favicon.ico')

# Initialize the database
def init_db():
    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS attendance (
                      id INTEGER PRIMARY KEY AUTOINCREMENT,
                      student_id TEXT NOT NULL,
                      student_name TEXT,
                      session_id TEXT NOT NULL,
                      timestamp TEXT NOT NULL)''')
    conn.commit()
    conn.close()

# Generate QR Code for the given session_id
@app.route('/generate_qr/<session_id>', methods=['GET'])
def generate_qr(session_id):
    if not session_id:
        return jsonify({"error": "Session ID is required"}), 400

    # Generate a unique token based on the current time (rounded to 5 minutes)
    current_time = int(time.time())  # Current time in seconds
    rounded_time = current_time - (current_time % 300)  # Round to the nearest 5 minutes
    token = f"{session_id}-{rounded_time}"

    # Generate the QR code with the token
    qr_data = f"{request.host_url}scan/{token}"
    qr = qrcode.make(qr_data)
    img_io = io.BytesIO()
    qr.save(img_io, 'PNG')
    img_io.seek(0)
    return send_file(img_io, mimetype='image/png')

# Mark Attendance for a student
@app.route('/mark_attendance', methods=['POST'])
def mark_attendance():
    data = request.json
    student_id = data.get('student_id')
    session_id = data.get('session_id')

    # Validate input
    if not student_id or not session_id:
        return jsonify({"error": "Missing student_id or session_id"}), 400

    timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')

    try:
        conn = sqlite3.connect('attendance.db')
        cursor = conn.cursor()
        cursor.execute("INSERT INTO attendance (student_id, session_id, timestamp) VALUES (?, ?, ?)",
                       (student_id, session_id, timestamp))
        conn.commit()
    except sqlite3.Error as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

    return jsonify({"message": "Attendance marked successfully"})

# Get Attendance Records
@app.route('/get_attendance', methods=['GET'])
def get_attendance():
    try:
        conn = sqlite3.connect('attendance.db')
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM attendance")
        records = cursor.fetchall()
    except sqlite3.Error as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

    return jsonify(records)

# Scan QR Code (Simulates attendance marking)
@app.route('/scan/<token>', methods=['GET'])
def scan_qr(token):
    if not token:
        return jsonify({"error": "Token is required"}), 400

    # Extract session_id and timestamp from the token
    try:
        session_id, token_time = token.rsplit('-', 1)
        token_time = int(token_time)
    except ValueError:
        return jsonify({"error": "Invalid token format"}), 400

    # Validate the token (allow a 5-minute window)
    current_time = int(time.time())
    if current_time - token_time > 300:
        return jsonify({"error": "QR code has expired"}), 400

    # Render a form for the user to input their details
    return render_template('scan.html', session_id=session_id)

@app.route('/scan/<session_id>')
def scan(session_id):
    return render_template('scan.html', session_id=session_id)

@app.route('/submit_attendance', methods=['POST'])
def submit_attendance():
    student_id = request.form.get('student_id')
    student_name = request.form.get('student_name')  # Not stored yet
    session_id = request.form.get('session_id')

    if not student_id or not session_id:
        return "Missing student ID or session ID", 400

    # Optional: Prevent duplicate attendance for the same session
    try:
        conn = sqlite3.connect('attendance.db')
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM attendance WHERE student_id=? AND session_id=?", (student_id, session_id))
        if cursor.fetchone():
            return "Attendance already marked for this session.", 400
        timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
        cursor.execute("INSERT INTO attendance (student_id, session_id, timestamp) VALUES (?, ?, ?)",
                       (student_id, session_id, timestamp))
        conn.commit()
    except sqlite3.Error as e:
        return f"Database error: {e}", 500
    finally:
        conn.close()

    return "Attendance marked successfully!"

if __name__ == '__main__':
    init_db()  # Initialize the database
    app.run(debug=True)
