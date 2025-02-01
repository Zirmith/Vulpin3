from flask import Flask, jsonify, request, send_from_directory, redirect, session
from dotenv import load_dotenv

from flask_cors import CORS
import os
import sqlite3
import random
import string
from werkzeug.utils import secure_filename
from PIL import Image
import base64
from io import BytesIO
import subprocess
# import ngrok python sdk
import ngrok
import time
import uuid

load_dotenv()
NGROK_AUTH_TOKEN = os.getenv('NGROK_AUTH_TOKEN')

ngrok.set_auth_token(NGROK_AUTH_TOKEN)



app = Flask(__name__, static_folder='public')
app.secret_key = 'super_secret_key'  # Replace with a strong secret key for production
CORS(app)



# Ensure the uploads directory exists
os.makedirs('public/uploads', exist_ok=True)

# Global variables to store bots
created_bots = []       # This list holds all created bots
bot_counter = 1         # Simple counter for unique bot IDs



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
@app.route('/bconsole', methods=['GET'])
def console_page():
    return send_from_directory(app.static_folder, 'console.html')


# Serve the Forgot Password Page
@app.route('/forgotpassword', methods=['GET'])
def forgot_password_page():
    return send_from_directory(app.static_folder, 'fp.html')

# Serve the Dashboard Page
@app.route('/dashboard', methods=['GET'])
def dashboard_page():
    if 'logged_in' not in session or not session['logged_in']:
        return redirect('/login')  # Redirect to login page if not logged in
    if not check_verified():
        return redirect('/verify')  # Redirect to verification page if not verified
    return send_from_directory(app.static_folder, 'dashboard.html')

# Serve the My Profile Page
@app.route('/my-profile', methods=['GET'])
def myprofile_page():
    if 'logged_in' not in session or not session['logged_in']:
        return redirect('/login')  # Redirect to login page if not logged in
    if not check_verified():
        return redirect('/verify')  # Redirect to verification page if not verified
    return send_from_directory(app.static_folder, 'profileE.html')


# Serve the Bots Page
@app.route('/bots', methods=['GET'])
def bots_page():
    if 'logged_in' not in session or not session['logged_in']:
        return redirect('/login')  # Redirect to login page if not logged in
    if not check_verified():
        return redirect('/verify')  # Redirect to verification page if not verified
    return send_from_directory(app.static_folder, 'bots.html')

# Serve the Verification Page
@app.route('/verify', methods=['GET'])
def verify_page():
    return send_from_directory(app.static_folder, 'verify.html')

# Handle Verification Logic
@app.route('/verifyc', methods=['POST'])
def verify_account():
    verification_code = request.form['code']  # Get code from form data

    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    # Get account based on the verification code
    cursor.execute("SELECT * FROM users WHERE verification_code = ?", (verification_code,))
    user = cursor.fetchone()

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


# NEW: Endpoint to return all created bots
@app.route('/getbots', methods=['GET'])
def get_bots():
    # Exclude 'process' from the response because Popen is not JSON serializable
    bots_info = [
        {key: bot[key] for key in bot if key != "process"} 
        for bot in created_bots
    ]
    return jsonify({"bots": bots_info}), 200

# Modified: Endpoint to receive bot status updates and update our in-memory bots list
@app.route("/update-bot-status", methods=["POST"])
def update_bot_status():
    data = request.json
    bot_name = data.get("botName", "").strip()  # Ensure it's a string and strip spaces
    current_answer = data.get("current_answer")
    is_correct = data.get("is_correct")

    print(f"Received update for bot: {bot_name}")

    # 🛑 If the answer is "disconnect", remove the bot that sent it
    if str(current_answer).strip().lower() == "disconnect":
        bot_to_remove = None
        for bot in created_bots:
            if bot["name"].strip().lower() == bot_name.lower():  # Case-insensitive match
                bot_to_remove = bot
                break
        
        if bot_to_remove:
            created_bots.remove(bot_to_remove)
            print(f"🚨 Bot {bot_name} disconnected and removed.")
            return jsonify({"status": "success", "message": f"Bot {bot_name} removed due to disconnect"}), 200
        else:
            print(f"❌ No bot found with the name: {bot_name}")
            return jsonify({"status": "error", "message": "Bot not found"}), 404

    # 🛑 If the answer is "quiz end", remove all bots
    if str(current_answer).strip().lower() == "quiz end":
        created_bots.clear()
        print("🚨 Quiz ended! All bots removed.")
        return jsonify({"status": "success", "message": "All bots removed due to quiz end"}), 200

    updated = False
    for bot in created_bots:
        print(f"Checking bot: {bot['name']}")

        if bot["name"].strip().lower() == bot_name.lower():  # Case-insensitive match
            bot["current_answer"] = current_answer
            bot["is_correct"] = is_correct
            bot["last_updated"] = time.time()
            updated = True
            print(f"✅ Bot {bot_name} updated successfully!")
            break

    if not updated:
        print(f"❌ No bot found with the name: {bot_name}")

    return jsonify({
        "status": "success" if updated else "error",
        "message": "Bot status updated" if updated else "Bot not found"
    }), 200 if updated else 404




# Modified: Create Bot endpoint that spawns bots and saves them in our global list
@app.route('/createbot', methods=['POST'])
def create_bot():
    global bot_counter

    data = request.get_json()
    app.logger.info("Received createbot data: %s", data)

    bot_name = data.get('bot_name', '[̶Vulpin3 AI]̶ ̶ˢ̶ᵖ̶ᵉ̶ᶜ̶ᵗ̶ʳ̶ᵃ̶ᵀ̶ʰ̶ᵉ̶ᶠ̶ˡ̶ᵒ̶ᶠ̶')
    pin = data.get('pin')
    amount = int(data.get('amount', 1))
    smart = data.get('smart', False)

    if not pin:
        return jsonify({"error": "Pin is required"}), 400

    node_script = "Vulpin_Handler"

    aggregated_stdout = []
    aggregated_stderr = []

    for i in range(amount):
        new_bot_name = f"{bot_name}" + (f" #{i+1}" if amount > 1 else "")
        args = ["node", node_script, "[Vulpin3]" + new_bot_name, str(pin)]
        if smart:
            args.append("smart")
        app.logger.info("Spawning bot with args: %s", args)

        try:
            process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

            bot_object = {
                "id": str(uuid.uuid4()),  # Generate a unique ID
                "name": "[Vulpin3]" + new_bot_name,
                "current_answer": "N/A",
                "is_correct": None,
                "gamepin": pin,
                "last_updated": time.time(),
                "process": process  # Store the process to manage it later
            }
            created_bots.append(bot_object)
            bot_counter += 1

        except Exception as e:
            app.logger.error("Error spawning bot %s: %s", new_bot_name, str(e))
            return jsonify({"error": "An error occurred", "details": str(e)}), 500

    app.logger.info("New bots created: %s", created_bots)
    return jsonify({"message": "Bots spawned successfully"}), 200




if __name__ == '__main__':
    app.run(debug=True)



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



@app.route('/assets/<path:filename>')
def serve_assets(filename):
    return send_from_directory('public/assets', filename)

# Serve frontend files (catch-all for static files)
@app.route('/<path:path>')
def serve_frontend(path):
    if path and os.path.exists(os.path.join(app.static_folder, path)):
        return send_from_directory(app.static_folder, path)
    return send_from_directory(app.static_folder, 'index.html')

if __name__ == '__main__':
    app.run(debug=True, port=5000)
