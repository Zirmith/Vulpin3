from flask import Flask, jsonify, request, send_from_directory, redirect, session
from flask_cors import CORS
import os
import sqlite3
import random
import string
from werkzeug.utils import secure_filename
from PIL import Image
import base64
from io import BytesIO

app = Flask(__name__, static_folder='public')
app.secret_key = 'super_secret_key'  # Replace with a strong secret key for production
CORS(app)

# Ensure the uploads directory exists
os.makedirs('public/uploads', exist_ok=True)

# SQLite database setup
def create_db():
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL,
        email TEXT NOT NULL UNIQUE,
        password TEXT NOT NULL,
        profile_picture TEXT,
        verification_code TEXT,
        verified BOOLEAN DEFAULT 0
    );
    ''')
    
    conn.commit()
    conn.close()

create_db()

# Helper function to generate a verification code
def generate_verification_code():
    return ''.join(random.choices(string.digits, k=6))

# Function to check if the user is verified
def check_verified():
    if 'logged_in' in session and session['logged_in']:
        user_id = session.get('user_id')
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute("SELECT verified FROM users WHERE id = ?", (user_id,))
        user = cursor.fetchone()
        conn.close()
        if user and user[0] == 0:  # User is not verified
            return False
    return True


# Define the 404 error handler
@app.errorhandler(404)
def page_not_found(e):
    return send_from_directory(app.static_folder, '404.html'), 404


# Redirect to /login if user is not logged in
@app.route('/')
def root_redirect():
    if 'logged_in' not in session or not session['logged_in']:
        return redirect('/login')  # Redirect to login page if not logged in

    if not check_verified():  # If logged in but not verified
        return redirect('/verify')  # Redirect to verification page

    return redirect('/dashboard')  # Redirect to the dashboard if logged in and verified


# Serve the Login Page
@app.route('/login', methods=['GET', 'POST'])
def login_page():
    if request.method == 'POST':
        if request.is_json:  # Check if the incoming request is JSON
            data = request.get_json()  # Parse JSON data
            
            username = data['email']  # Match keys sent from client
            password = data['password']
        else:
            return jsonify({"error": "Invalid request format. JSON required."}), 400  # Return error for non-JSON

        # Database connection and user validation
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = ? AND password = ?", (username, password))  # Use 'email' here
        user = cursor.fetchone()
        conn.close()


        if user:
            session['logged_in'] = True
            session['user_id'] = user[0]
            if not check_verified():
                return jsonify({"redirect": "/verify"})  # Send JSON response for verification
            return jsonify({"redirect": "/"})  # Send JSON response for successful login
        else:
            return jsonify({"error": "Invalid credentials"}), 401  # Return error response

    # Handle GET request, serve the login page
    return send_from_directory(app.static_folder, 'index.html')



# Serve the Forgot Password Page
@app.route('/forgotpassword', methods=['GET'])
def forgot_password_page():
    return send_from_directory(app.static_folder, 'fp.html')

# Serve the Dashboard Page
@app.route('/dashboard', methods=['GET'])
def dashboard_page():
    if not check_verified():
        return redirect('/verify')  # Redirect to verification page if not verified
    return send_from_directory(app.static_folder, 'dashboard.html')

# Serve the My Profile Page
@app.route('/my-profile', methods=['GET'])
def myprofile_page():
    if not check_verified():
        return redirect('/verify')  # Redirect to verification page if not verified
    return send_from_directory(app.static_folder, 'profileE.html')

# Serve the Verification Page
@app.route('/verify', methods=['GET'])
def verify_page():
    return send_from_directory(app.static_folder, 'verify.html')

# Handle Verification Logic
@app.route('/verifyc', methods=['POST'])
def verify_account():
    print(request.form['code'])
    verification_code = request.form['code']  # Get code from form data

    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    # Get account based on the verification code
    cursor.execute("SELECT * FROM users WHERE verification_code = ?", (verification_code,))
   
    user = cursor.fetchone()
    print(user)

    if user:  # Check if the user exists
        cursor.execute("UPDATE users SET verified = 1 WHERE verification_code = ?", (verification_code,))
        conn.commit()
        conn.close()
        return jsonify({"message": "Account successfully verified"}), 200
    else:
        conn.close()
        return jsonify({"error": "Invalid verification code"}), 400


# User Registration Route
@app.route('/register', methods=['POST'])
def register():
    # Handling form data for text fields
    username = request.form.get('username')
    email = request.form.get('email')
    password = request.form.get('password')

    # Handling file upload
    profile_picture = request.files.get('profile_picture')

    print(f"Username: {username}, Email: {email}, Password: {password}")

    if not username or not email or not password:
        return jsonify({"error": "Missing required fields"}), 400

    # Save profile picture if provided
    profile_picture_filename = None
    if profile_picture:
        profile_picture_filename = secure_filename(profile_picture.filename)
        os.makedirs('public/uploads', exist_ok=True)
        profile_picture.save(os.path.join('public/uploads', profile_picture_filename))

    # Generate verification code
    verification_code = generate_verification_code()

    # Connect to the database and check for existing user
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
    existing_user = cursor.fetchone()

    if existing_user:
        conn.close()
        return jsonify({"error": "Email is already registered"}), 400

    # Insert new user into the database
    cursor.execute('''
    INSERT INTO users (username, email, password, profile_picture, verification_code)
    VALUES (?, ?, ?, ?, ?)
    ''', (username, email, password, profile_picture_filename, verification_code))

    conn.commit()
    conn.close()

    return jsonify({"message": f"Registration successful. Verification code is: {verification_code}"}), 200

# Logout route
@app.route('/logout', methods=['GET'])
def logout():
    session.clear()
    return redirect('/login')

# Get logged-in user details
@app.route('/getuser', methods=['GET'])
def get_user():
    if 'logged_in' not in session or not session['logged_in']:
        return jsonify({"error": "User not logged in"}), 401
    
    user_id = session['user_id']
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()

    if user:
        user_info = {
            "username": user[1],
            "email": user[2],
            "password": user[3],
            "profile_picture": user[4],
            "verified": user[6]
        }
        return jsonify(user_info), 200
    else:
        return jsonify({"error": "User not found"}), 404
    

@app.route('/updateProfilePicture', methods=['POST'])
def update_profile_picture():
    # Check if the user is logged in
    if 'logged_in' not in session or not session['logged_in']:
        return jsonify({"error": "User not logged in"}), 401
    
    # Get the base64-encoded image from the request
    data = request.get_json()
    profile_picture_data = data.get('profile_picture')

    if not profile_picture_data:
        return jsonify({"error": "No image data provided"}), 400

    # Remove the base64 header part (data:image/png;base64,)
    header, encoded_image = profile_picture_data.split(",", 1)

    # Update the user's profile picture in the database with the base64 string
    user_id = session['user_id']
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET profile_picture = ? WHERE id = ?", (encoded_image, user_id))
    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": "Profile picture updated successfully"}), 200

# Serve frontend files (catch-all for static files)
@app.route('/<path:path>')
def serve_frontend(path):
    if path and os.path.exists(os.path.join(app.static_folder, path)):
        return send_from_directory(app.static_folder, path)
    return send_from_directory(app.static_folder, 'index.html')

if __name__ == '__main__':
    app.run(debug=True, port=5000)
