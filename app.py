# STUDSIGHT - SCHOOL MANAGEMENT & ANALYTICS SYSTEM
# Flask-based application for managing students, teachers, behaviour tracking,
# and AI-powered analytical summaries of student performance

# IMPORTS - Essential libraries for the application
from flask import Flask, render_template, session, abort, flash, send_from_directory
from flask import redirect, url_for, request, jsonify, send_from_directory
import datetime
from datetime import date, timedelta
# import matplotlib.pyplot as plt  # Commented out - for future data visualization
import numpy as np  # Numerical computing
import pandas as pd  # Data manipulation and analysis
import sqlite3, csv, os, io  # Database, file handling, and streams
from flask_mail import Mail, Message  # Email functionality (currently disabled)
import random  # Random number generation for PINs
from openai import OpenAI  # AI integration for generating student summaries
from dotenv import load_dotenv  # Environment variable management
import os

# Load environment variables from .env file (API keys, secrets, etc.)
load_dotenv()

# Initialize OpenAI client with API key from environment (optional)
openai_api_key = os.getenv('OPENAI_API_KEY')
client = OpenAI(api_key=openai_api_key) if openai_api_key else None


app = Flask(__name__)  # Create Flask application instance
app.secret_key = os.getenv('SECRET_KEY', 'StudsightSecretKey123')  # Session encryption key
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///forum.db'  # Database configuration

# Email configuration (currently disabled - set up for future use)
# app.config['MAIL_SERVER'] = 'smtp.gmail.com'
# app.config['MAIL_PORT'] = 587
# app.config['MAIL_USE_TLS'] = True
# app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME', 'doludavid@gmail.com')
# app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD', 'David12345!')
# app.config['MAIL_DEFAULT_SENDER'] = 'doludavid15@gmail.com'
# mail = Mail(app)




# DATABASE INITIALIZATION
# Create or connect to accounts database
# This database stores user login credentials (email, password, PIN)
connection = sqlite3.connect("accounts.db")
cursor = connection.cursor()
# Create users table if it doesn't exist - stores authentication information
cursor.execute('''CREATE TABLE IF NOT EXISTS users 
               (ID INTEGER PRIMARY KEY AUTOINCREMENT,email TEXT, password TEXT, pin TEXT)''')
               
connection.commit()
connection.close()

# APPLICATION CONSTANTS

# Behaviour tracking type IDs - map integer IDs to behaviour types
# These correspond to entries in the BehaviourTypes database table
HOUSE_POINT = 1  # Positive reinforcement
DETENTION   = 3  # Disciplinary action
WITHDRAWAL  = 4  # Student withdrawal/absence

# CSV HEADER MAPPINGS
# These lists define the expected columns when importing student data from CSV files
# They ensure data is correctly mapped to database fields

EXPECTED_HEADERS = [
    "Firstname","Surname","DOB","Gender","Yeargroup","Mastery","Email",
    "Parentname","Parentnumber","Address","Nationality","CountryofBirth","EnrollmentDate",
    "Conditions","Medication","Allergies","Needs"
]

SYSTEM_FIELDS = ["FirstSubject", "SecondSubject", "ThirdSubject", "FourthSubject",
    "Parentname","Parentnumber","Address","Nationality","CountryOfBirth","EnrollmentDate",
    "Conditions","Medication","Allergies","Needs"
]

# AI PROMPT CONFIGURATION

# SYSTEM_PROMPT defines the AI behavior for generating student summaries
# It instructs GPT-3.5-turbo how to analyze student data
SYSTEM_PROMPT = (
    "You generate a weekly analytical summary of a student based on school data. "
    "Compare THIS WEEK with LAST WEEK using attendance and behaviour records. "
    "Support statements with statistics and percentages. "
    "Identify trends related to behaviour type, attendance, periods (time of day), "
    "and days of the week. "
    "After the summary, provide short, realistic suggestions to improve outcomes. "
    "Suggestions must be directly based on the trends identified. "
    "Keep the tone professional, supportive, and non-judgemental. "
    "Limit the response to a minimum of 7 sentences maximum of 10."
    "Space responses and sentences properly for easy reading."
)





# COMPLEX ALGORITHM: build_weekly_summary_prompt()
# PURPOSE: Generates a detailed data prompt for AI-powered student analysis
# 
# ALGORITHM OVERVIEW:
# 1. Fetches student basic information from database
# 2. Retrieves attendance records for current + previous week
# 3. Retrieves behaviour event records for current + previous week
# 4. Calculates statistics (counts, attendance rates, behaviour trends)
# 5. Identifies time-based patterns (which periods have most incidents)
# 6. Constructs a comprehensive prompt for GPT to analyze
#
# KEY INSIGHTS:
# - Compares week-over-week data to identify trends
# - Uses dictionaries to aggregate data by category
# - Identifies worst-performing periods (when behaviour issues occur most)
#
def build_weekly_summary_prompt(cursor, student_id: int) -> str:
    # -------- Student core information --------
    # Query basic student details needed for context in the summary
    cursor.execute("""
        SELECT StudentID, Firstname, Surname, Gender, Mastery, Yeargroup
        FROM Students
        WHERE StudentID = ?
    """, (student_id,))
    s = cursor.fetchone()
    if not s:
        return "No student found."

    # Format student basic info for the AI prompt
    student_line = (
        f"Student: {s[1]} {s[2]} (ID {s[0]}), "
        f"Year {s[5]}, Gender: {s[3]}, Mastery: {s[4]}."
    )

    # Fetch attendance records from last 14 days, ordered most recent first
    cursor.execute("""
        SELECT Date, Status
        FROM Attendance
        WHERE StudentID = ?
          AND Date >= date('now','-14 days')
        ORDER BY Date DESC
    """, (student_id,))
    att = cursor.fetchall()

    # Split into two weeks (first 7 records = this week, next 7 = last week)
    this_week = att[:7]
    last_week = att[7:14]

    # Helper function: Count attendance status types
    # Normalizes status values (handles different input formats)
    def count_att(records):
        total = len(records)
        # Count each status type using case-insensitive matching
        present = sum(1 for _, st in records if (st or "").lower() in ["present", "p"])
        absent  = sum(1 for _, st in records if (st or "").lower() in ["absent", "a"])
        late    = sum(1 for _, st in records if (st or "").lower() in ["late", "l"])
        return total, present, absent, late

    # Calculate statistics for both weeks
    tw_total, tw_pres, tw_abs, tw_late = count_att(this_week)
    lw_total, lw_pres, lw_abs, lw_late = count_att(last_week)

    # Format attendance summary for AI
    attendance_summary = (
        f"Attendance: This week – Present {tw_pres}/{tw_total}, "
        f"Absent {tw_abs}, Late {tw_late}. "
        f"Last week – Present {lw_pres}/{lw_total}, "
        f"Absent {lw_abs}, Late {lw_late}."
    )

    # Fetch behaviour events from last 14 days with type information
    cursor.execute("""
        SELECT Date, Period, bt.Type
        FROM BehaviourEvents be
        JOIN BehaviourTypes bt ON bt.TypeID = be.TypeID
        WHERE be.StudentID = ?
          AND Date >= date('now','-14 days')
        ORDER BY Date DESC
    """, (student_id,))
    beh = cursor.fetchall()

    # Split into two weeks
    beh_tw = beh[:7]
    beh_lw = beh[7:14]

    # Helper function: Aggregate behaviour data into categories
    # Returns two dictionaries:
    # - counts: {behaviour_type: number_of_occurrences}
    # - periods: {period: number_of_incidents_during_that_period}
    def behaviour_stats(records):
        counts = {}    # Track frequency of each behaviour type
        periods = {}   # Track which periods have most incidents
        for _, period, t in records:
            # Increment behaviour type counter
            counts[t] = counts.get(t, 0) + 1
            # Increment period counter to identify problem times
            periods[period] = periods.get(period, 0) + 1
        return counts, periods

    # Calculate behaviour statistics for both weeks
    tw_counts, tw_periods = behaviour_stats(beh_tw)
    lw_counts, lw_periods = behaviour_stats(beh_lw)

    # Format behaviour summary for AI
    behaviour_summary = (
        f"Behaviour events: This week – {sum(tw_counts.values())} events "
        f"{dict(tw_counts)}. "
        f"Last week – {sum(lw_counts.values())} events {dict(lw_counts)}."
    )

    # Identify which period of day has most behaviour incidents (algorithmic insight)
    period_trend = ""
    if tw_periods:
        # Find the period with maximum incident count
        worst_period = max(tw_periods, key=tw_periods.get)
        period_trend = f"Most behaviour incidents this week occurred during Period {worst_period}."

    # Combine all data into a structured prompt for the AI
    prompt = (
        f"{student_line}\n"
        f"{attendance_summary}\n"
        f"{behaviour_summary}\n"
        f"{period_trend}\n\n"
        "Task:\n"
        "Write a weekly summary comparing THIS WEEK with LAST WEEK.\n"
        "- Use numbers and percentages.\n"
        "- Identify trends in attendance, behaviour type, and time of day.\n"
        "- After the summary, give 2–3 brief suggestions linked directly to the trends.\n"
        "- Keep the entire response to no more than 10 sentences.\n"
        "- Use a professional, supportive tone."
    )

    return prompt

# FUNCTION: weekly_summary_generator()
# PURPOSE: Sends data to OpenAI API and receives AI-generated analysis
# 
# PROCESS:
# 1. Calls GPT-3.5-turbo with the structured prompt
# 2. Uses low temperature (0.4) for consistency (not creative)
# 3. Limits output to 300 tokens to keep response concise
# 4. Returns cleaned text response
#
def weekly_summary_generator(prompt: str) -> str:
    # Make API call to OpenAI with system and user prompts
    response = client.chat.completions.create(
        model="gpt-3.5-turbo", 
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}  # Provide student data
        ],
        temperature=0.4,
        max_tokens=300  # Limit response length
    )
    # Extract and clean the response text
    return response.choices[0].message.content.strip()





# UTILITY FUNCTIONS - Helper functions used throughout the application

def days_in_week(year, week):
    # ISO weeks start on Monday (weekday=1)
    start = date.fromisocalendar(year, week, 1)
    # Generate all 7 days by adding 0-6 days to the start date
    return [(start + timedelta(days=i)).isoformat() for i in range(7)]


def get_period(current_time=None):
    if current_time is None:
        current_time = datetime.datetime.now().time()

    # Define periods with (period_number, start_time, end_time)
    periods = [
        (1, datetime.time(8, 20), datetime.time(9, 0)),
        (2, datetime.time(9, 0), datetime.time(10, 0)),
        (3, datetime.time(10, 0), datetime.time(11, 0)),
        (4, datetime.time(11, 15), datetime.time(12, 15)),
        (5, datetime.time(13, 15), datetime.time(13, 45)),
        (6, datetime.time(13, 45), datetime.time(14, 45)),
        (7, datetime.time(14, 45), datetime.time(15, 45)),
        (8, datetime.time(16, 0), datetime.time(17, 50)),
    ]

    # Loop through periods and return matching period
    for period, start, end in periods:
        if start <= current_time < end:
            return period

    # Return None if outside all periods
    return None


def generate_pin():
    return str(random.randint(10000000, 99999999))


def get_db():
    """
    PURPOSE: Establish and return database connection
    
    FEATURES:
    - Enables foreign key constraints for data integrity
    - Sets row_factory to return rows as dict-like objects (easier to access columns by name)
    - Used in virtually all database operations
    
    OUTPUT: sqlite3.Connection object configured and ready to use
    """
    conn = sqlite3.connect("schooldata.db")
    conn.row_factory = sqlite3.Row  # Access columns by name instead of index
    conn.execute("PRAGMA foreign_keys = ON")  # Enable foreign key constraint checking
    return conn


def count_behaviour(events, type_id):
    total = 0
    for e in events:
        # BehaviourEvents tuple structure: [0]=EventID, [1]=StudentID, [2]=Date, [3]=Period, [4]=TypeID
        if e[4] == type_id:
            total += 1
    return total


def count_attendance(records, status):
    """
    PURPOSE: Count attendance records with a specific status
    
    ALGORITHM: Similar to count_behaviour - linear search
    - Iterates through attendance records
    - Normalizes status to lowercase for case-insensitive matching
    - Counts matches
    
    TIME COMPLEXITY: O(n) where n = number of records
    
    INPUT:
    - records: List of attendance record tuples
    - status: Status value to count (e.g., "present", "p", "absent", "a")
    
    OUTPUT: Integer count of matching records
    """
    total = 0
    for r in records:
        # Your Attendance logic uses index 3 for status
        if r[3] == status:
            total += 1
    return total



# SECTION: AUTHENTICATION ROUTES
# Routes for user registration, login, password management
# Uses PIN-based account recovery for security




# ROUTE: / (Home Page)
# PURPOSE: Displays the home/landing page for unauthenticated users
# BEHAVIOR: Clears session to ensure user is logged out
@app.route('/')
def home():
    """Clear any existing session and render home page"""
    session.pop('user', None)  # Remove logged-in user session
    return render_template("home.html")



# ROUTE: /register (User Registration)
# PURPOSE: Allows new teachers to create accounts
# SECURITY: Generates unique PIN for account recovery
# DATABASE: Creates entry in accounts.db (NOT schooldata.db)
@app.route('/register', methods=['GET', 'POST'])
def register():
    session.pop('user', None)  # Ensure user not already logged in
    
    # Generate PIN only once per session
    if 'registration_pin' not in session:
        conn = sqlite3.connect('accounts.db')
        cursor = conn.cursor()

        all_pins = cursor.execute("SELECT pin FROM users").fetchall()
        pins = [p[0] for p in all_pins]
        pin = generate_pin()
        while pin in pins:
            pin = generate_pin()
        
        session['registration_pin'] = pin
        conn.close()
    else:
        pin = session['registration_pin']


    if request.method == 'POST':
        email = request.form.get('email').lower().strip()
        pin = session.get('registration_pin')  # Use the PIN from session
        
        conn = sqlite3.connect('accounts.db')
        cursor = conn.cursor()
        
        
        conn = sqlite3.connect('schooldata.db')
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM Teachers WHERE email=?", (email,))
        user = cursor.fetchone()


        if user:
            conn.close()
            conn2 = sqlite3.connect('accounts.db')
            cursor = conn2.cursor()
            cursor.execute("SELECT * FROM users WHERE email=?", (email,))
            user2 = cursor.fetchone()
            conn2.close()



            if user2:
                flash('Account already exists. Please login.')
                return redirect(url_for('login'))
            else:
                password = request.form.get('password', '').strip()
                confirm_password = request.form.get('confirm_password', '').strip()
                
                # Validate password
                if not password:
                    flash('Password cannot be empty.')
                    return redirect(url_for('register'))
                elif len(password) < 8:
                    flash('Password must be at least 8 characters.')
                    return redirect(url_for('register'))
                elif password != confirm_password:
                    flash('Passwords do not match. Please try again.')
                    return redirect(url_for('register'))
                
                conn2 = sqlite3.connect('accounts.db')
                cursor = conn2.cursor()
                
                cursor.execute("INSERT INTO users (email, password, pin) VALUES (?, ?, ?)", (email, password, pin))
                conn2.commit()
                conn2.close()
                flash('Registration successful! Please login.')
                return redirect(url_for('login'))
        else:
            return redirect(url_for('register'))
    return render_template("register.html", pin = pin)





# ROUTE: /login (User Authentication)
# PURPOSE: Validates teacher credentials against accounts.db
# SECURITY NOTES:
# - Checks email exists in schooldata.db (Teachers table)
# - Validates password matches accounts.db
# - Sets session['user'] on success

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Authenticate user credentials and establish session"""
    session.pop('user', None)  # Clear any previous session
    if request.method == 'POST':
        email = request.form.get('email', '').lower().strip()
        password = request.form.get('password', '').strip()

        conn = sqlite3.connect('schooldata.db')
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM Teachers WHERE Email=?", (email,))
        user = cursor.fetchone()
        conn.close()

        conn2 = sqlite3.connect('accounts.db')
        cursor = conn2.cursor()

        cursor.execute("SELECT * FROM users WHERE email=?", (email,))
        user2 = cursor.fetchone()
        conn2.close()

        if user:
            connection = sqlite3.connect("accounts.db")
            cursor = connection.cursor()
            cursor.execute("SELECT * FROM users WHERE email=? AND password=?", (email, password))
            account = cursor.fetchone()
            

            if account:
                session['user'] = email
                return redirect(url_for('dashboard'))
            elif user2: 
                flash('Incorrect password. Try again.')
            else:
                flash('No account found with that email. Please register.')
                return redirect(url_for('register'))
        
        else:
            flash('Invalid email. Try again.')

    return render_template("login.html")




# ROUTE: /forgot_password (Account Recovery)
# PURPOSE: Initiates password reset process using email + PIN
# SECURITY: PIN is generated at registration and stored in accounts.db
# PROCESS: Email + PIN verification -> Redirect to /reset_password

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    """Verify email and PIN, then allow password reset"""
    connection = sqlite3.connect("accounts.db")
    cursor = connection.cursor()
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        pin = request.form.get('pin', '').strip()
        
        # Validate inputs
        if not email or not pin:
            flash('Email and PIN are required.')
            connection.close()
            return render_template("forgot_password.html")
        else:
            cursor.execute("SELECT * FROM users WHERE email=?", (email,))
            user_check = cursor.fetchone()
            
            if user_check:
                # User exists, now check PIN
                stored_pin = str(user_check[3]).strip() if user_check[3] else ""
                if stored_pin == pin.strip():
                    connection.close()
                    session['reset_email'] = email
                    return redirect(url_for('reset_password'))
                else:
                    flash('Invalid PIN. Please try again.')
                    connection.close()
                    return render_template("forgot_password.html")
            else:
                flash('Invalid email. Please try again.')
                connection.close()
                return render_template("forgot_password.html")
    connection.close()
    return render_template("forgot_password.html")


# ROUTE: /reset_password (Password Reset Completion)
# PURPOSE: Allows verified user to set new password
# PREREQUISITE: Must come from /forgot_password with session['reset_email']



@app.route('/reset_password', methods=['GET', 'POST'])
def reset_password():
    """Update password in accounts.db after verification"""
    # Check if user came from forgot_password verification
    if 'reset_email' not in session:
        flash('Please verify your email and PIN first.')
        return redirect(url_for('forgot_password'))
    
    connection = sqlite3.connect("accounts.db")
    cursor = connection.cursor()
    if request.method == 'POST':
        new_password = request.form.get('new_password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()
        
        # Validate password
        if not new_password:
            flash('Password cannot be empty.')
        elif len(new_password) < 6:
            flash('Password must be at least 6 characters.')
        elif new_password == confirm_password:
            cursor.execute("UPDATE users SET password=? WHERE email=?", (new_password, session.get('reset_email')))
            connection.commit()
            connection.close()
            session.pop('reset_email', None)  # Clear reset session
            flash('Password reset successful! Please login.')
            return redirect(url_for('login'))
        else:
            flash('Passwords do not match. Please try again.')
    connection.close()
    return render_template("reset_password.html")




# ROUTE: /logout (Session Termination)
# PURPOSE: Clears user session and redirects to home
@app.route('/logout')
def logout():
    """Clear session and redirect to home page"""
    session.pop('user', None)  # Remove user from session
    return redirect(url_for('home'))




# ROUTE: /dashboard (Teacher Dashboard)
# PURPOSE: Main hub for logged-in teachers showing navigation
# ACCESS: Requires active session (checked with 'user' in session)
# DISPLAYS: Teacher name, role, email for navigation

@app.route('/dashboard')
def dashboard():
    """Display personalized dashboard with teacher information"""
    connection = sqlite3.connect("schooldata.db")
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM Teachers WHERE Email=?", (session['user'],))
    teacher = cursor.fetchall()
    if 'user' in session:
        for t in teacher:
            id = t[0]
            firstname = t[1]
            surname = t[2]
            gender = t[3]
            email = t[4]
            role = t[5]

        return render_template("dashboard.html", user=session['user'], firstname=firstname, surname=surname, gender=gender, email=email, role=role, id=id)
    else:
        flash('You must be logged in to view the dashboard.')
        return redirect(url_for('login'))


# ROUTE: /profile/<teacher_id> (View Teacher Profile)
# PURPOSE: Display teacher information and qualifications
# DISPLAYS: Name, email, subject, DOB, qualifications, contact info
@app.route('/profile/<int:teacher_id>')
def profile(teacher_id):
    connection = sqlite3.connect("schooldata.db")
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM Teachers WHERE TeacherID=?", (teacher_id,))
    teacher = cursor.fetchall()
    cursor.execute("SELECT * FROM Teachers WHERE email=?", (session['user'],))
    user_account = cursor.fetchone()
    userid = user_account[0]
    user_email = user_account[4]
    if 'user' in session:
        for t in teacher:
            teacherid = t[0]
            firstname = t[1]
            surname = t[2]
            gender = t[3]
            email = t[4]
            subjectid = t[6]
        cursor.execute("SELECT * FROM Subjects WHERE SubjectID=?", (subjectid,))
        subjects = cursor.fetchall()
        for s in subjects:
            subjectname = s[1]
        cursor.execute("SELECT * FROM Teacher_info WHERE TeacherID=?", (int(teacherid),))
        details = cursor.fetchall()
        for info in details:
            personal_email = info[2]
            dob = info[3]
            qualifications = info[4]
        return render_template("profile.html", firstname=firstname, 
                               surname=surname, gender=gender, 
                               email=email, subjectname=subjectname, 
                               personal_email=personal_email, dob=dob, 
                               qualifications=qualifications, teacherid=id, user_email=user_email, id=userid)
    else:
        return redirect(url_for('login'))   



# ROUTE: /manage_account (Account Settings)
# PURPOSE: Allow teacher to update password
# SECURITY: Requires PIN verification before password change
@app.route('/manage_account/<int:id>', methods=['GET', 'POST'])
def manage_account(id):
    if 'user' in session:
        connection = sqlite3.connect("schooldata.db")
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM Teachers WHERE Email=?", (session['user'],))
        teacher = cursor.fetchone()
        id = teacher[0]
        email = teacher[4]
        connection.close()
        connection = sqlite3.connect("accounts.db")
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM users WHERE email=?", (email,))
        user = cursor.fetchone()
        set_pin = user[3]
        password = user[2]

        if request.method == 'POST':
            new_email = request.form.get('email').lower()
            current_password = request.form.get('current_password')
            pin = request.form.get('pin')
            new_password = request.form.get('password')
            confirm_new_password = request.form.get('confirm_password')

            if str(pin) == str(set_pin) and new_password == confirm_new_password and new_email == email and current_password == password:
                cursor.execute("UPDATE users SET password=? WHERE email=?", (new_password, email))
                connection.commit()
                flash('Account updated successfully!')
                return redirect(url_for('login'))

        return render_template("manage_account.html", id=id, email=email)
    else:
        return redirect(url_for('login'))



# ROUTE: /class (Current Class/Lesson)
# PURPOSE: Display students in teacher's current lesson period
# LOGIC:
# - Periods 1 & 5: Show mastery group students
# - Periods 2-4, 6-8: Show subject class students
# DYNAMIC: Auto-detects current period using get_period()


@app.route('/class')
def current_class():
    if 'user' in session:
        try:
            connection = sqlite3.connect("schooldata.db")
            cursor = connection.cursor()
            
            # Get teacher information
            cursor.execute("SELECT * FROM Teachers WHERE Email=?", (session['user'],))
            teacher = cursor.fetchone()
            if not teacher:
                return redirect(url_for('login'))
            
            teacher_id = teacher[0]
            firstname = teacher[1]
            surname = teacher[2]
            teacher_name = firstname + " " + surname
            masteryid = teacher[7]
            subjectid = teacher[6]
            
            # Get current period
            period_num = get_period()
            if period_num is None:
                flash('Outside school hours', 'warning')
                return redirect(url_for('dashboard'))
            
            # Get current date and day of week
            today = datetime.date.today()
            day_of_week = today.weekday()  # 0=Monday, 6=Sunday
            # Convert to 1-5 range for Timetable (1=Monday, 5=Friday)
            # If outside school week (Saturday=5, Sunday=6), return to dashboard
            if day_of_week > 4:  # Saturday or Sunday
                flash('School is closed on weekends', 'warning')
                return redirect(url_for('dashboard'))
            day_of_week = day_of_week + 1  # Convert 0-4 to 1-5
            
            # Determine if mastery or subject based on period
            is_mastery_period = (period_num == 1 or period_num == 5)
            
            if is_mastery_period:
                # Mastery periods - get students from mastery group
                period_column = "Period1" if period_num == 1 else "Period5"
                cursor.execute(f"""
                    SELECT s.StudentID, s.Firstname, s.Surname, s.Email, s.Yeargroup
                    FROM Students s
                    JOIN Timetable t ON s.StudentID = t.StudentID
                    WHERE t.{period_column} = ? AND t.Day = ?
                    ORDER BY s.Surname, s.Firstname
                """, (masteryid, day_of_week))
                students_in_class = cursor.fetchall()
                
                cursor.execute("SELECT Masteryname FROM Mastery WHERE MasteryID=?", (masteryid,))
                mastery = cursor.fetchone()
                class_name = mastery[0] if mastery else "Unknown Mastery"
                class_type = "mastery"
            else:
                # Subject periods - get students from subject
                period_column = f"Period{period_num}"
                cursor.execute(f"""
                    SELECT s.StudentID, s.Firstname, s.Surname, s.Email, s.Yeargroup
                    FROM Students s
                    JOIN Timetable t ON s.StudentID = t.StudentID
                    WHERE t.{period_column} = ? AND t.Day = ?
                    ORDER BY s.Surname, s.Firstname
                """, (subjectid, day_of_week))
                students_in_class = cursor.fetchall()
                
                # Get subject name
                cursor.execute("SELECT Subjectname FROM Subjects WHERE SubjectID=?", (subjectid,))
                subject = cursor.fetchone()
                class_name = subject[0] if subject else "Unknown Subject"
                class_type = "subject"
            
            # Get attendance records for today's students in this period
            student_ids = [s[0] for s in students_in_class]
            attendance_records = {}
            
            if student_ids:
                placeholders = ','.join('?' * len(student_ids))
                cursor.execute(f"""
                    SELECT StudentID, Status
                    FROM PeriodAttendance
                    WHERE StudentID IN ({placeholders}) AND Date = ? AND Period = ?
                """, student_ids + [today, period_num])
                for record in cursor.fetchall():
                    attendance_records[record[0]] = record[1]
            
            # Format students data with attendance info
            students_data = []
            for student in students_in_class:
                students_data.append({
                    'id': student[0],
                    'firstname': student[1],
                    'surname': student[2],
                    'email': student[3],
                    'yeargroup': student[4],
                    'attendance_status': attendance_records.get(student[0], 'Not Marked')
                })
            
            connection.close()
            
            # Add success flash message
            flash(f'Loaded {class_type.capitalize()} class: {class_name} (Period {period_num})', 'success')
            
            return render_template("class.html", students=students_data, class_name=class_name, 
                                   class_type=class_type, teacher_name=teacher_name, teacher_id=teacher_id,
                                   period=period_num, today=today.isoformat(), id=teacher_id,
                                   firstname=firstname, surname=surname, email=session['user'])

        except Exception as e:
            flash(f'Error loading class: {str(e)}', 'error')
            return redirect(url_for('dashboard')) 

    else:
        return redirect(url_for('login'))


# ROUTE: /log_attendance (Save Attendance for Student)
# PURPOSE: Save attendance record for a student in a specific period
# METHOD: POST (JSON)
# INPUT: student_id, status (Present/Absent/Late), period, date
# DATABASE: Inserts/Updates PeriodAttendance table

@app.route('/log_attendance', methods=['POST'])
def log_attendance():
    if 'user' not in session:
        return redirect(url_for('login'))
    try:
        data = request.get_json()
        student_id = data.get('student_id')
        status = data.get('status')
        period = data.get('period')
        date = data.get('date')
        
        if not all([student_id, status, period, date]):
            return jsonify({'error': 'Missing required fields'}), 400
        
        # Validate status
        if status not in ['Present', 'Absent', 'Late']:
            return jsonify({'error': 'Invalid status'}), 400
        
        connection = sqlite3.connect("schooldata.db")
        cursor = connection.cursor()
        
        # Get teacher info
        cursor.execute("SELECT TeacherID FROM Teachers WHERE Email=?", (session['user'],))
        teacher = cursor.fetchone()
        if not teacher:
            connection.close()
            return jsonify({'error': 'Teacher not found'}), 404
        
        teacher_id = teacher[0]
        
        # Check if record exists
        cursor.execute("""
            SELECT PeriodAttendanceID FROM PeriodAttendance 
            WHERE StudentID=? AND Date=? AND Period=?
        """, (student_id, date, period))
        
        existing = cursor.fetchone()
        
        if existing:
            # Update existing record
            cursor.execute("""
                UPDATE PeriodAttendance 
                SET Status=?
                WHERE StudentID=? AND Date=? AND Period=?
            """, (status, student_id, date, period))
        else:
            # Insert new record
            cursor.execute("""
                INSERT INTO PeriodAttendance (StudentID, Date, Period, TeacherID, Status)
                VALUES (?, ?, ?, ?, ?)
            """, (student_id, date, period, teacher_id, status))
        
        connection.commit()
        connection.close()
        
        return jsonify({'success': True, 'message': f'Attendance marked as {status}'}), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500




# ROUTE: /teachers (Teacher List & Search)
# PURPOSE: Display all teachers with search/filter functionality
# FEATURES: Search by name, email; view teacher info and subjects
# PERMISSIONS: All logged-in teachers can view

@app.route('/teachers')
def teachers():
    connection = sqlite3.connect("schooldata.db")
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM Teachers WHERE Email=?", (session['user'],))
    teacher = cursor.fetchall()
    if 'user' in session:
        for t in teacher:
            id = t[0]
            role = t[5]
        
        # Get search query from GET parameter
        query = request.args.get('query', '').strip()
        
        if query:
            # Search by ID, first name, surname, email, year, or mastery
            search_param = f"%{query}%"
            cursor.execute("""SELECT * FROM Teachers WHERE 
                            Firstname LIKE ? OR Surname LIKE ? 
                            OR Email LIKE ? """, 
                            (search_param, search_param, search_param))
        else:
            cursor.execute("SELECT * FROM Teachers")

        teachers = cursor.fetchall()
        subjects = cursor.execute("SELECT * FROM Subjects").fetchall()
        masterys = cursor.execute("SELECT * FROM Mastery").fetchall()
        extra_info = cursor.execute("SELECT * FROM Teacher_info").fetchall()

        return render_template("teachers.html", teachers=teachers, info=extra_info, 
                               query=query, role=role, id=id, subjects=subjects, 
                               masterys=masterys)
    else:
        return redirect(url_for('login'))
    




# ROUTE: /add_teacher (Create New Teacher)
# PURPOSE: Form for adding new teacher account
# PERMISSIONS: Admin only (role='A')
# FEATURES: Assign subject and mastery group, store contact info
# DATABASE: Creates entries in Teachers and Teacher_info tables

@app.route('/add_teacher', methods=['GET', 'POST'])
def add_teacher():
    if 'user' in session:
        connection = sqlite3.connect("schooldata.db")
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM Teachers WHERE Email=?", (session['user'],))
        teacher = cursor.fetchone()
        id = teacher[0]
        teachers = cursor.execute("SELECT Email FROM Teachers").fetchall()
        

        if request.method == 'POST':
            firstname = request.form.get('firstname').title()
            surname = request.form.get('surname').title()
            gender = request.form.get('gender')
            email = request.form.get('email')
            subjectid = request.form.get('subject')
            if subjectid == 1:
                role = "A"
            else:
                role = "T"
            masteryid = request.form.get('mastery')
            phonenumber = request.form.get('phonenumber')
            personal_email = request.form.get('personal_email')
            personal_email = str(personal_email).lower()
            dob = request.form.get('dob')
            qualifications = request.form.get('qualifications')
            emergency_contact = request.form.get('emergency_contact')
            address = request.form.get('address')
            employment_start = request.form.get('employment_start')
            connection = sqlite3.connect("schooldata.db")
            cursor = connection.cursor()
            cursor.execute("SELECT * FROM Teachers WHERE Email=?", (email,))
            existing_teacher = cursor.fetchone()
            if existing_teacher:
                flash('A teacher with that email already exists.')
            else:
                cursor.execute("INSERT INTO Teachers (Firstname, Surname, Gender, Email, SubjectID, Role, MasteryID) VALUES (?, ?, ?, ?, ?, ?, ?)", (firstname, surname, gender, email, subjectid, role, masteryid))
                connection.commit()
                cursor.execute("SELECT TeacherID FROM Teachers WHERE Firstname=? AND Surname=? AND Email=?", (firstname, surname, email))
                teacher = cursor.fetchone()
                teacher_id = teacher[0] 
                cursor.execute("INSERT INTO Teacher_info (TeacherID, phonenumber, personal_email, DOB, qualifications, Emergency_contact, Address, employment_start) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (teacher_id, phonenumber, personal_email, dob, qualifications, emergency_contact, address, employment_start))
                connection.commit()
                flash('Teacher added successfully!')
        return render_template("add_teacher.html", id=id, teachers=teachers)
    else:
        return redirect(url_for('login'))


# ROUTE: /delete_teacher (Delete Teacher - Admin Only)
# PURPOSE: Display list of teachers for deletion selection
# PERMISSIONS: Admin teachers only (role='A')
# SEARCH: Can filter teachers by name, email
# SAFETY: Cannot delete other admin teachers

@app.route('/delete_teacher', methods=['GET', 'POST'])
def delete_teacher():
    if "user" not in session:
        return redirect(url_for("login"))

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM Teachers WHERE Email=?", (session["user"],))
    teacher = cur.fetchone()
    teacherid = teacher[0]
    if not teacher or teacher[5] != "A":
        conn.close()
        return redirect(url_for("teachers"))  # only admin can delete

    query = request.args.get("query", "").strip()

    if query:
        search_param = f"%{query}%"
        cur.execute("""SELECT * FROM Teachers WHERE
                       (Firstname LIKE ? OR Surname LIKE ?
                       OR Email LIKE ?)""",
                    (search_param, search_param, search_param))
    else:
        cur.execute("SELECT * FROM Teachers")

    all_teachers = cur.fetchall()
    # Filter out admins from the list
    teachers = [t for t in all_teachers if t[5] != "A"]
    extra_info = cur.execute("SELECT * FROM Teacher_info").fetchall()
    conn.close()

    return render_template("delete_teachers.html", teachers=teachers, info=extra_info, query=query, id=teacherid)


# ROUTE: /teachers/delete/confirm (Teacher Deletion Confirmation)
# PURPOSE: Show confirmation page with selected teachers before delete
# SAFETY: Requires explicit confirmation before final deletion
# PROTECTIONS: Cannot delete admin teachers

@app.route("/teachers/delete/confirm", methods=["POST"])
def confirm_delete_teacher():
    if "user" not in session:
        return redirect(url_for("login"))

    connection = sqlite3.connect("schooldata.db")
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM Teachers WHERE Email=?", (session['user'],))
    teacher = cursor.fetchone()
    teacherid = teacher[0]
    connection.close()

    selected_ids = request.form.getlist("delete_ids")  # list of checked teacher IDs (strings)

    if not selected_ids:
        flash("No teachers selected.", "error")
        return redirect(url_for("delete_teacher"))

    # fetch details for confirmation page
    conn = get_db()
    cur = conn.cursor()

    placeholders = ",".join("?" for _ in selected_ids)
    cur.execute(f"SELECT * FROM Teachers WHERE TeacherID IN ({placeholders})", selected_ids)
    selected_teachers = cur.fetchall()

    # Check if any selected teacher is an admin
    has_admin = any(teacher[5] == "A" for teacher in selected_teachers)
    if has_admin:
        flash("Cannot delete admin teachers.", "error")
        conn.close()
        return redirect(url_for("delete_teacher"))

    conn.close()

    return render_template("confirm_delete_teachers.html",
                           selected_teachers=selected_teachers,
                           selected_ids=selected_ids, id=teacherid)


# ROUTE: /teachers/delete/final (Execute Teacher Deletion)
# PURPOSE: Permanently remove selected teachers from database
# CASCADE: Deletes from Teacher_info before Teachers table
# PROTECTIONS: Verifies no admin teachers being deleted

@app.route("/teachers/delete/final", methods=["POST"])
def final_delete_teacher():
    if "user" not in session:
        return redirect(url_for("login"))

    selected_ids = request.form.getlist("selected_ids")
    if not selected_ids:
        flash("Nothing to delete.", "error")
        return redirect(url_for("delete_teacher"))
    conn = get_db()
    cur = conn.cursor()

    # Verify no admins are being deleted
    placeholders = ",".join("?" for _ in selected_ids)
    cur.execute(f"SELECT * FROM Teachers WHERE TeacherID IN ({placeholders})", selected_ids)
    teachers_to_delete = cur.fetchall()
    
    if any(teacher[5] == "A" for teacher in teachers_to_delete):
        flash("Cannot delete admin teachers.", "error")
        conn.close()
        return redirect(url_for("delete_teacher"))

    try:
        # delete from child tables first (prevents FK errors if not using CASCADE)
        cur.execute(f"DELETE FROM Teacher_info WHERE TeacherID IN ({placeholders})", selected_ids)
        
        # finally delete from Teachers
        cur.execute(f"DELETE FROM Teachers WHERE TeacherID IN ({placeholders})", selected_ids)
        conn.commit()
    except Exception as e:
        conn.rollback()
        flash(f"Delete failed: {e}", "error")
    conn.close()
    return redirect(url_for("delete_teacher"))









# ROUTE: /message_page (Message Board Hub)
# PURPOSE: Navigation page showing available message boards
# DISPLAY:
# - Admin: All boards (general, subject-specific)
# - Teachers: Only their subject board

@app.route('/message_page')
def message_page():
    if 'user' in session:
        connection = sqlite3.connect("schooldata.db")
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM Teachers WHERE Email=?", (session['user'],))
        teacher = cursor.fetchall()
        if 'user' in session:
            for t in teacher:
                id = t[0]   
                subject = t[6]
                role = t[5]
            
            
            if role == 'T':
                return render_template("teacher_message_page.html", subject=subject, id=id)
            else:
                return render_template("message_page.html", id=id)
        else:
            return redirect(url_for('login'))





# ROUTE: /messages (General Message Board)
# PURPOSE: Display all general discussion posts
# FEATURES: Reverse chronological order (newest first)
# PERMISSIONS: All logged-in users

@app.route("/messages", methods =['GET', 'POST'])
def messages():
    if 'user' in session:
        connection = sqlite3.connect("schooldata.db")
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM Teachers WHERE Email=?", (session['user'],))
        teacher = cursor.fetchone()
        id = teacher[0]
        cursor.execute("SELECT * FROM Posts")
        posts = cursor.fetchall()
        cursor.execute("SELECT * FROM Teachers")
        teachers = cursor.fetchall()
        posts = posts[::-1]
        return  render_template("messages.html", posts=posts, teachers=teachers, id=id)
    else:
        return redirect(url_for('login'))
    

# ROUTE: /maths_messages (Maths Department Message Board)
# PURPOSE: Subject-specific discussion board for Maths teachers
# PERMISSION: Maths teachers and admins
@app.route("/maths_messages", methods = ['GET', 'POST'])
def maths_messages():
    if 'user' in session:
        connection = sqlite3.connect("schooldata.db")
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM Teachers WHERE Email=?", (session['user'],))
        teacher = cursor.fetchone()
        id = teacher[0]
        cursor.execute("SELECT * FROM M_Posts")
        posts = cursor.fetchall()
        cursor.execute("SELECT * FROM Teachers")
        teachers = cursor.fetchall()
        posts = posts[::-1]
        return  render_template("maths_messages.html", posts=posts, teachers=teachers, id=id)
    else:
        return redirect(url_for('login'))
    

# ROUTE: /english_messages (English Department Message Board)
# PURPOSE: Subject-specific discussion board for English teachers
# PERMISSION: English teachers and admins
@app.route("/english_messages", methods = ['GET', 'POST'])
def english_messages():
    if 'user' in session:
        connection = sqlite3.connect("schooldata.db")
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM Teachers WHERE Email=?", (session['user'],))
        teacher = cursor.fetchone()
        id = teacher[0]
        cursor.execute("SELECT * FROM E_Posts")
        posts = cursor.fetchall()
        cursor.execute("SELECT * FROM Teachers")
        teachers = cursor.fetchall()
        posts = posts[::-1]
        return  render_template("english_messages.html", posts=posts, teachers=teachers, id=id)
    else:
        return redirect(url_for('login'))
    
# ROUTE: /science_messages (Science Department Message Board)
# PURPOSE: Subject-specific discussion board for Science teachers
# PERMISSION: Science teachers and admins
@app.route("/science_messages", methods = ['GET', 'POST'])
def science_messages():
    if 'user' in session:
        connection = sqlite3.connect("schooldata.db")
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM Teachers WHERE Email=?", (session['user'],))
        teacher = cursor.fetchone()
        id = teacher[0]
        cursor.execute("SELECT * FROM S_Posts")
        posts = cursor.fetchall()
        cursor.execute("SELECT * FROM Teachers")
        teachers = cursor.fetchall()
        posts = posts[::-1]
        return  render_template("science_messages.html", posts=posts, teachers=teachers, id=id)
    else:
        return redirect(url_for('login'))

# ROUTE: /computing_messages (Computing Department Message Board)
# PURPOSE: Subject-specific discussion board for Computing teachers
# PERMISSION: Computing teachers and admins
@app.route("/computing_messages", methods = ['GET', 'POST'])
def computing_messages():
    if 'user' in session:
        connection = sqlite3.connect("schooldata.db")
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM Teachers WHERE Email=?", (session['user'],))
        teacher = cursor.fetchone()
        id = teacher[0]
        cursor.execute("SELECT * FROM C_Posts")
        posts = cursor.fetchall()
        cursor.execute("SELECT * FROM Teachers")
        teachers = cursor.fetchall()
        posts = posts[::-1]
        return  render_template("computing_messages.html", posts=posts, teachers=teachers, id=id)
    else:
        return redirect(url_for('login'))



# ROUTE: /history_messages (History Department Message Board)
# PURPOSE: Subject-specific discussion board for History teachers
# PERMISSION: History teachers and admins
@app.route("/history_messages", methods = ['GET', 'POST'])
def history_messages():
    if 'user' in session:
        connection = sqlite3.connect("schooldata.db")
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM Teachers WHERE Email=?", (session['user'],))
        teacher = cursor.fetchone()
        id = teacher[0]
        cursor.execute("SELECT * FROM H_Posts")
        posts = cursor.fetchall()
        cursor.execute("SELECT * FROM Teachers")
        teachers = cursor.fetchall()
        posts = posts[::-1]
        return  render_template("history_messages.html", posts=posts, teachers=teachers, id=id)
    else:
        return redirect(url_for('login'))












# ROUTE: /view_post/<board>/<int:post_id> (Display Message Board Post)
# PURPOSE: Show full post content with details
@app.route('/view_post/<board>/<int:post_id>')
def view_post(board, post_id):
    if 'user' in session:
        connection = sqlite3.connect("schooldata.db")
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM Teachers WHERE Email=?", (session['user'],))
        teacher = cursor.fetchone()
        id = teacher[0]
        
        # Map board to table and primary key
        table_map = {'general': 'Posts','computing': 'C_Posts',
            'maths': 'M_Posts','english': 'E_Posts','science': 'S_Posts',
            'history': 'H_Posts'
        }
        
        id_column_map = {'Posts': 'PostID','C_Posts': 'CPostID','M_Posts': 'MPostID',
                         'E_Posts': 'EPostID','S_Posts': 'SPostID','H_Posts': 'HPostID'
        }
        
        table = table_map.get(board)
        id_column = id_column_map.get(table)
        
        if not table:
            return redirect(url_for('messages'))
        
        cursor.execute(f"SELECT * FROM {table} WHERE {id_column}=?", (post_id,))
        post = cursor.fetchone()
        connection.close()
        
        if post:
            return render_template("view_post.html", post=post, id=id, board=board)
        else:
            return redirect(url_for('messages'))
    else:
        return redirect(url_for('login'))
    




# ROUTE: /get_attachment/<board>/<post_id> (Retrieve Post Attachment Blob)
# PURPOSE: Fetch and serve the binary blob attachment from database
# BOARDS: general, computing, maths, english, science, history
@app.route('/get_attachment/<board>/<int:post_id>')
def get_attachment(board, post_id):
    if 'user' in session:
        connection = sqlite3.connect("schooldata.db")
        cursor = connection.cursor()
        
        # Select from the appropriate table based on board
        table_map = {'general': 'Posts','computing': 'C_Posts','maths': 'M_Posts',
            'english': 'E_Posts','science': 'S_Posts','history': 'H_Posts'
        }
        
        table = table_map.get(board)
        if not table:
            abort(404)
        
        # Get the primary key column name for the table
        id_column_map = {'Posts': 'PostID','C_Posts': 'CPostID',
            'M_Posts': 'MPostID','E_Posts': 'EPostID',
            'S_Posts': 'SPostID','H_Posts': 'HPostID'
        }
        
        id_column = id_column_map.get(table)
        
        cursor.execute(f"SELECT Attachments FROM {table} WHERE {id_column}=?", (post_id,))
        result = cursor.fetchone()
        connection.close()
        
        if result and result[0]:
            from flask import send_file
            blob_data = result[0]
            # Return the blob as an image file
            return send_file(
                io.BytesIO(blob_data),
                mimetype='image/png',  # or image/jpeg, etc
                as_attachment=False
            )
        else:
            abort(404)
    else:
        return redirect(url_for('login'))


# ROUTE: /new_post/<board> (Create Message Board Post)
# PURPOSE: Teachers create discussion posts on various boards
# BOARDS: general, computing, maths, english, science, history
# FEATURES: File upload support for attachments
# DATABASE: Inserts into Posts or subject-specific table (C_Posts, M_Posts, etc)
@app.route('/new_post/<board>', methods=['GET', 'POST'])
def new_post(board):
    if 'user' in session:
        connection = sqlite3.connect("schooldata.db")
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM Teachers WHERE Email=?", (session['user'],))
        teacher = cursor.fetchone()
        teacherid = teacher[0]

        if request.method == 'POST':
            # Get form data
            title = request.form.get('title')
            content = request.form.get('content')
            date = str(datetime.date.today())
            time = datetime.datetime.now().strftime("%H:%M")
            attachments = None
            
            if 'attachments' in request.files:
                file = request.files['attachments']
                if file and file.filename != '':
                    # Read file as binary blob
                    attachments = file.read()

            # Reconnect to insert post
            connection = sqlite3.connect("schooldata.db")
            cursor = connection.cursor()

            # Insert into correct board table
            if board == 'general':
                cursor.execute("""
                    INSERT INTO Posts (Title, Content, Date, Time, Attachments, TeacherID)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (title, content, date, time, attachments, teacherid))
                connection.commit()
                connection.close()
                flash("Post created successfully!", "success")
                return redirect(url_for('messages'))

            elif board == 'computing':
                cursor.execute("""
                    INSERT INTO C_Posts (Title, Content, Date, Time, Attachments, TeacherID)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (title, content, date, time, attachments, teacherid))
                connection.commit()
                connection.close()
                flash("Post created successfully!", "success")
                return redirect(url_for('computing_messages'))

            elif board == 'maths':
                cursor.execute("""
                    INSERT INTO M_Posts (Title, Content, Date, Time, Attachments, TeacherID)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (title, content, date, time, attachments, teacherid))
                connection.commit()
                connection.close()
                flash("Post created successfully!", "success")
                return redirect(url_for('maths_messages',))
            elif board == 'english':
                cursor.execute("""
                    INSERT INTO E_Posts (Title, Content, Date, Time, Attachments, TeacherID)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (title, content, date, time, attachments, teacherid))
                connection.commit()
                connection.close()
                flash("Post created successfully!", "success")
                return redirect(url_for('english_messages'))

            elif board == 'science':
                cursor.execute("""
                    INSERT INTO S_Posts (Title, Content, Date, Time, Attachments, TeacherID)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (title, content, date, time, attachments, teacherid))
                connection.commit()
                connection.close()
                flash("Post created successfully!", "success")
                return redirect(url_for('science_messages'))
            elif board == 'history':
                cursor.execute("""
                    INSERT INTO H_Posts (Title, Content, Date, Time, Attachments, TeacherID)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (title, content, date, time, attachments, teacherid))
                connection.commit()
                connection.close()
                flash("Post created successfully!", "success")
                return redirect(url_for('history_messages'))

        return render_template("new_post.html", board=board, id=teacherid)
    else:
        return redirect(url_for('login'))




# ROUTE: /delete_post/<board> (Remove Message Board Post)
# PURPOSE: Teachers delete their own posts
# PERMISSIONS: Only author can delete their posts
# DATABASE: Deletes from Posts or subject-specific tables

@app.route('/delete_post/<board>', methods=['GET', 'POST'])
def delete_post(board):
    if 'user' in session:
        connection = sqlite3.connect("schooldata.db")
        cursor = connection.cursor()
        teacher = cursor.execute("SELECT * FROM Teachers WHERE Email=?", (session['user'],)).fetchone()
        teacherid = teacher[0]
        role = teacher[5]  # Get teacher role ('A' for admin, 'T' for teacher)

        # Get posts for the selected board - admins see all posts, regular teachers see only their own
        if board == 'general':
            if role == 'A':
                myposts = cursor.execute("SELECT * FROM Posts").fetchall()
            else:
                myposts = cursor.execute("SELECT * FROM Posts WHERE TeacherID=?", (teacherid,)).fetchall()
        elif board == 'computing':
            if role == 'A':
                myposts = cursor.execute("SELECT * FROM C_Posts").fetchall()
            else:
                myposts = cursor.execute("SELECT * FROM C_Posts WHERE TeacherID=?", (teacherid,)).fetchall()
        elif board == 'maths':
            if role == 'A':
                myposts = cursor.execute("SELECT * FROM M_Posts").fetchall()
            else:
                myposts = cursor.execute("SELECT * FROM M_Posts WHERE TeacherID=?", (teacherid,)).fetchall()
        elif board == 'english':
            if role == 'A':
                myposts = cursor.execute("SELECT * FROM E_Posts").fetchall()
            else:
                myposts = cursor.execute("SELECT * FROM E_Posts WHERE TeacherID=?", (teacherid,)).fetchall()
        elif board == 'science':
            if role == 'A':
                myposts = cursor.execute("SELECT * FROM S_Posts").fetchall()
            else:
                myposts = cursor.execute("SELECT * FROM S_Posts WHERE TeacherID=?", (teacherid,)).fetchall()
        elif board == 'history':
            if role == 'A':
                myposts = cursor.execute("SELECT * FROM H_Posts").fetchall()
            else:
                myposts = cursor.execute("SELECT * FROM H_Posts WHERE TeacherID=?", (teacherid,)).fetchall()
        else:
            myposts = []
        
        myposts = myposts[::-1]

        if request.method == 'POST':
            postid = request.form.get('post_id')
            
            if board == 'general':
                cursor.execute("DELETE FROM Posts WHERE PostID=?", (postid,))
                connection.commit()
                return redirect(url_for('messages'))
            elif board == 'computing':
                cursor.execute("DELETE FROM C_Posts WHERE CPostID=?", (postid,))
                connection.commit()
                return redirect(url_for('computing_messages'))
            elif board == 'maths':
                cursor.execute("DELETE FROM M_Posts WHERE MPostID=?", (postid,))
                connection.commit()
                return redirect(url_for('maths_messages'))
            elif board == 'english':
                cursor.execute("DELETE FROM E_Posts WHERE EPostID=?", (postid,))
                connection.commit()
                return redirect(url_for('english_messages'))
            elif board == 'science':
                cursor.execute("DELETE FROM S_Posts WHERE SPostID=?", (postid,))
                connection.commit()
                return redirect(url_for('science_messages'))
            elif board == 'history':
                cursor.execute("DELETE FROM H_Posts WHERE HPostID=?", (postid,))
                connection.commit()
                return redirect(url_for('history_messages'))
            
        return render_template("delete_post.html", myposts=myposts, id=teacherid, board=board, role=role, teachers=cursor.execute("SELECT * FROM Teachers").fetchall())
            
    else:
        return redirect(url_for('login'))
       





@app.route('/students') # Students route
def students():
    connection = sqlite3.connect("schooldata.db")
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM Teachers WHERE Email=?", (session['user'],))
    teacher = cursor.fetchall()
    if 'user' in session:
        for t in teacher:
            id = t[0]
            role = t[5]
        
        # Get search query from GET parameter
        query = request.args.get('query', '').strip()
        
        if query:
            # Search by ID, first name, surname, email, year, or mastery
            search_param = f"%{query}%"
            cursor.execute("""SELECT * FROM Students WHERE 
                            Firstname LIKE ? OR Surname LIKE ? 
                            OR Email LIKE ? OR YearGroup LIKE ? OR Mastery LIKE ?""", 
                            (search_param, search_param, search_param, search_param, search_param))
        else:
            cursor.execute("SELECT * FROM Students")

        students = cursor.fetchall()
        extra_info = cursor.execute("SELECT * FROM Student_info").fetchall()

        return render_template("students.html", students=students, info=extra_info, query=query, role=role, id=id)
    else:
        return redirect(url_for('login'))
    




# ROUTE: /add_student (Create New Student)
# PURPOSE: Form for manually adding individual student
# VALIDATION: DOB must match year group age requirements
# DATABASE: Creates records in Students, Student_Info, Medical_Info, Timetable

@app.route('/add_student', methods=['GET', 'POST'])
def add_student():
    if 'user' in session:
        connection = sqlite3.connect("schooldata.db")
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM Teachers WHERE Email=?", (session['user'],))
        teacher = cursor.fetchone()
        teacherid = teacher[0]
        cursor.execute("SELECT SubjectID, Subjectname FROM Subjects WHERE Subjectname != 'Admin' ORDER BY Subjectname")
        subjects = cursor.fetchall()

        if request.method == 'POST':
            firstname = request.form.get('firstname').title()
            surname = request.form.get('surname').title()
            gender = request.form.get('gender')
            yeargroup = request.form.get('yeargroup')
            dob = request.form.get('dob')
            mastery = request.form.get('mastery').upper()
            email = request.form.get('email').lower()
            first_subject = request.form.get('first_subject')
            second_subject = request.form.get('second_subject')
            third_subject = request.form.get('third_subject')
            fourth_subject = request.form.get('fourth_subject')

            parentname = request.form.get('parentname').title()
            parentnumber = request.form.get('parentnumber')

            address = request.form.get('address')
            nationality = request.form.get('nationality').title()
            countryofbirth = request.form.get('countryofbirth').title()
            enrollmentdate = request.form.get('enrollmentdate')

            conditions = request.form.get('conditions').title()
            medication = request.form.get('medications').title()
            allergies = request.form.get('allergies').title()
            needs = request.form.get('needs').title()

            try:
                dob_date = datetime.strptime(dob, '%Y-%m-%d').date()
                today = datetime.now().date()
                age = today.year - dob_date.year - ((today.month, today.day) < (dob_date.month, dob_date.day))
                
                yeargroup_int = int(yeargroup)
                valid_ages = {12: (16, 17, 18), 13: (17, 18, 19)}
                min_age, max_age = valid_ages[yeargroup_int]
                
                if age < min_age or age > max_age:
                    flash(f'For Year {yeargroup}, students should be {min_age}-{max_age} years old. The selected date of birth makes the student {age} years old.', 'error')
                    return render_template("add_student.html", id=teacherid, subjects=subjects)
            except:
                flash('Invalid date of birth format', 'error')
                connection = sqlite3.connect("schooldata.db")
                cursor = connection.cursor()
                cursor.execute("SELECT SubjectID, Subjectname FROM Subjects WHERE Subjectname != 'Admin' ORDER BY Subjectname")
                subjects = cursor.fetchall()
                connection.close()
                return render_template("add_student.html", id=teacherid, subjects=subjects, firstname=teacher[1], surname=teacher[2], email=session['user'], role='T')

            connection = sqlite3.connect("schooldata.db")
            cursor = connection.cursor()
            cursor.execute("INSERT INTO Students (Firstname, Surname, DOB, Gender, Mastery, Yeargroup, Email, Subject1, Subject2, Subject3, Subject4) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                            (firstname, surname, dob, gender, mastery, yeargroup, email, first_subject, second_subject, third_subject, fourth_subject))
            connection.commit()
            cursor.execute("SELECT StudentID FROM Students WHERE Firstname=? AND Surname=? AND DOB=?", (firstname, surname, dob))
            student = cursor.fetchone()
            student_id = student[0]
            cursor.execute("INSERT INTO Student_Info (StudentID, Parentname, Parentnumber, Address, Nationality, countryofbirth, Enrollmentdate) VALUES (?, ?, ?, ?, ?, ?, ?)", 
                           (student_id, parentname, parentnumber, address, nationality, countryofbirth, enrollmentdate))
            connection.commit()
            cursor.execute("INSERT INTO Medical_Info (StudentID, Conditions, Medication, Allergies, Needs) VALUES (?, ?, ?, ?, ?)", 
                           (student_id, conditions, medication, allergies, needs))
            connection.commit()
            cursor.execute("INSERT INTO Timetable (StudentID, DAY) VALUES (?, ?)", (student_id, "1"))
            cursor.execute("INSERT INTO Timetable (StudentID, DAY) VALUES (?, ?)", (student_id, "2"))
            cursor.execute("INSERT INTO Timetable (StudentID, DAY) VALUES (?, ?)", (student_id, "3"))
            cursor.execute("INSERT INTO Timetable (StudentID, DAY) VALUES (?, ?)", (student_id, "4"))
            cursor.execute("INSERT INTO Timetable (StudentID, DAY) VALUES (?, ?)", (student_id, "5"))
            connection.commit()
            connection.close()
            flash(f'Student {firstname} {surname} (Year {yeargroup}) added successfully', 'success')
            return redirect(url_for('students'))
        
        connection.close()
        return render_template("add_student.html", id=teacherid, subjects=subjects, firstname=teacher[1], surname=teacher[2], email=session['user'], role='T')
    else:
        return redirect(url_for('login'))



# ROUTE: /view_student (Student Profile)
# PURPOSE: Display comprehensive student information and details
# DISPLAYS: Personal info, contact info, medical info, detentions
# ACTIONS: From here can edit, view assessments, log behaviour
@app.route('/view_student/<int:student_id>')
def view_student(student_id):
    if 'user' in session:
        connection = sqlite3.connect("schooldata.db")
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM Teachers WHERE Email=?", (session['user'],))
        teacher = cursor.fetchone()
        teacherid = teacher[0]
        role = teacher[5]
        current_date = datetime.datetime.now().date()
        period = get_period()
        

        cursor.execute("SELECT * FROM Students WHERE StudentID=?", (student_id,))
        student = cursor.fetchone()
        cursor.execute("SELECT * FROM Student_info WHERE StudentID=?", (student_id,))
        info = cursor.fetchall()
        cursor.execute("SELECT * FROM Medical_info WHERE StudentID=?", (student_id,))
        medical = cursor.fetchone()
        cursor.execute("SELECT * FROM Timetable WHERE StudentID=?", (student_id,))
        timetable = cursor.fetchall()

        student_subject_ids = [student[8], student[9], student[10], student[11]]
        subject_names = []
        if student_subject_ids:
            placeholders = ','.join('?' * len(student_subject_ids))
            cursor.execute(f"SELECT Subjectname FROM Subjects WHERE SubjectID IN ({placeholders}) ORDER BY SubjectID", student_subject_ids)
            subject_names = [row[0] for row in cursor.fetchall()]

        timetable_display = []
        for row in timetable:
            row_list = list(row)
            # Row format: [StudentID, Day, Period1, Period2, Period3, Period4, Period5, Period6, Period7, Period8]
            # Period1 and Period5 are mastery (text), Period2-4 and Period6-8 are SubjectIDs (integers)
            for period_idx in [3, 4, 5, 7, 8, 9]:  # Indices for Period2-4 and Period6-8
                period_val = row_list[period_idx]
                if period_val and period_val != "FREE":
                    try:
                        # Try to get subject name for this ID
                        cursor.execute("SELECT Subjectname FROM Subjects WHERE SubjectID=?", (period_val,))
                        subject_result = cursor.fetchone()
                        if subject_result:
                            row_list[period_idx] = subject_result[0]
                    except:
                        pass
            timetable_display.append(row_list)

        if period and period >= 5:
            cursor.execute("SELECT * FROM BehaviourEvents WHERE StudentID=? AND Date=? AND TypeID=?", (student_id, current_date, 3))
            detentions = cursor.fetchall()
            total_detentions = 0
            for i in detentions:
                if i[3] >= 5:
                    total_detentions += 1     
        else:
            cursor.execute("SELECT * FROM BehaviourEvents WHERE StudentID=? AND Date=? AND TypeID=?", (student_id, current_date, 2))
            detentions = cursor.fetchall()
            total_detentions = 0
            for i in detentions:
                if i[3] < 5:
                    total_detentions += 1

        connection.close()

        if student:
            return render_template("view_student.html", student=student, info=info, medical=medical, role=role, 
                                   timetable=timetable_display, detentions=total_detentions, id=teacherid, subject_names=subject_names, 
                                   firstname=teacher[1], surname=teacher[2], email=session['user'])
        
        else:
            return redirect(url_for('students'))
    else:
        return redirect(url_for('login'))













# ROUTE: /flag_student (Flag Student for Help)
# PURPOSE: Send a flag message to the subject-specific message board
# METHOD: POST (AJAX)
# PARAMETERS:
# - student_id: Student ID to flag

@app.route('/flag_student/<int:student_id>', methods=['POST'])
def flag_student(student_id):
    if 'user' not in session:
        return redirect(url_for('login'))
    
    try:
        connection = sqlite3.connect("schooldata.db")
        cursor = connection.cursor()
        
        # Get student name and verify student exists
        cursor.execute("SELECT Firstname, Surname FROM Students WHERE StudentID=?", (student_id,))
        student = cursor.fetchone()
        if not student:
            connection.close()
            return jsonify({'success': False, 'error': 'Student not found'}), 404
        
        student_name = f"{student[0]} {student[1]}"
        
        # Get teacher info (ID and SubjectID) to identify which subject board to post to
        cursor.execute("SELECT TeacherID, SubjectID FROM Teachers WHERE Email=?", (session['user'],))
        teacher = cursor.fetchone()
        if not teacher:
            connection.close()
            return jsonify({'success': False, 'error': 'Teacher not found'}), 404
        
        teacher_id = teacher[0]
        subject_id = teacher[1]  # Subject the teacher teaches
        
        # Get subject name for logging purposes
        cursor.execute("SELECT Subjectname FROM Subjects WHERE SubjectID=?", (subject_id,))
        subject_result = cursor.fetchone()
        subject_name = subject_result[0] if subject_result else "Unknown"
        
        # Create message text
        message_text = f"{student_name} flagged for help in {subject_name}"
        message_title = f"⚠️ {subject_name} - Student Flag"
        
        # Determine which subject-specific table to insert into based on SubjectID
        subject_table_map = {
            1: 'M_Posts',      # Mathematics
            2: 'E_Posts',      # English
            3: 'S_Posts',      # Science
            4: 'C_Posts',      # Computing
            5: 'H_Posts'       # History
        }
        
        # Get the correct table name for this subject
        table_name = subject_table_map.get(subject_id)
        
        if not table_name:
            connection.close()
            return jsonify({'success': False, 'error': 'Invalid subject assigned to teacher'}), 400
        
        # Get current date and time
        today = datetime.date.today()
        now = datetime.datetime.now().time()
        
        # Insert flag message into the appropriate subject-specific message board table
        cursor.execute(f"""
            INSERT INTO {table_name} (Title, Content, Date, Time, TeacherID)
            VALUES (?, ?, ?, ?, ?)
        """, (message_title, message_text, today, str(now), teacher_id))
        
        connection.commit()
        connection.close()
        
        return jsonify({'success': True, 'message': f'{student_name} has been flagged for help in {subject_name}'}), 200
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500





# ROUTE: /edit_student (Modify Student Information)
# PURPOSE: Update student personal, contact, medical, and subject data
# VALIDATION: Validates DOB against year group age requirements
# DATABASE: Updates Students, Student_Info, Medical_Info tables

@app.route('/edit_student/<int:student_id>', methods=['GET', 'POST'])
def edit_student(student_id):
    if 'user' in session:
        connection = sqlite3.connect("schooldata.db")
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM Teachers WHERE Email=?", (session['user'],))
        teacher = cursor.fetchone()
        teacherid = teacher[0]
        cursor.execute("SELECT * FROM Students WHERE StudentID=?", (student_id,))
        student = cursor.fetchone()
        cursor.execute("SELECT * FROM Student_info WHERE StudentID=?", (student_id,))
        info = cursor.fetchone()
        cursor.execute("SELECT * FROM Medical_info WHERE StudentID=?", (student_id,))
        medical = cursor.fetchone()
        cursor.execute("SELECT * FROM Timetable WHERE StudentID=?", (student_id,))
        timetable = cursor.fetchall()
        
        # Get all subjects for dropdown (excluding Admin)
        cursor.execute("SELECT SubjectID, Subjectname FROM Subjects WHERE Subjectname != 'Admin' ORDER BY Subjectname")
        subjects = cursor.fetchall()

        subject1 = student[8]
        subject2 = student[9]
        subject3 = student[10]
        subject4 = student[11]
        
        firstname = teacher[1]
        surname = teacher[2]

        if request.method == 'POST':
            firstname = request.form.get('firstname').title()
            surname = request.form.get('surname').title()
            dob = request.form.get('dob')
            gender = request.form.get('gender')
            mastery = request.form.get('mastery').upper()
            yeargroup = request.form.get('yeargroup')
            email = request.form.get('email').lower()
            parentname = request.form.get('parentname').title()
            parentnumber = request.form.get('parentnumber')
            address = request.form.get('address')
            nationality = request.form.get('nationality').title()
            countryofbirth = request.form.get('countryofbirth').title()
            enrollmentdate = request.form.get('enrollmentdate')
            first_subject = request.form.get('first_subject')
            second_subject = request.form.get('second_subject')
            third_subject = request.form.get('third_subject')
            fourth_subject = request.form.get('fourth_subject')

            conditions = request.form.get('conditions')
            medication = request.form.get('medication')
            allergies = request.form.get('allergies')
            needs = request.form.get('needs')

            # Validate date of birth against year group
            from datetime import datetime
            try:
                dob_date = datetime.strptime(dob, '%Y-%m-%d').date()
                today = datetime.now().date()
                age = today.year - dob_date.year - ((today.month, today.day) < (dob_date.month, dob_date.day))
                
                yeargroup_int = int(yeargroup)
                valid_ages = {12: (16, 17), 13: (17, 18)}
                min_age, max_age = valid_ages[yeargroup_int]
                
                if age < min_age or age > max_age:
                    flash(f'For Year {yeargroup}, students should be {min_age}-{max_age} years old. The selected date of birth makes the student {age} years old.', 'error')
                    return render_template("edit_student.html", student=student, info=info, medical=medical, timetable=timetable, id=teacherid)
            except:
                flash('Invalid date of birth format', 'error')
                return render_template("edit_student.html", student=student, info=info, medical=medical, timetable=timetable, id=teacherid)

            if conditions:
                conditions = conditions.title()     
            else:
                conditions = ""
                
            if medication:
                medication = medication.title()
            else:
                medication = ""

            if allergies:
                allergies = allergies.title()
            else:
                allergies = ""


            cursor.execute("UPDATE Students SET Firstname=?, Surname=?, DOB=?, Gender=?, Mastery=?, Yeargroup=?, Email=?, Subject1=?, Subject2=?, Subject3=?, Subject4=? WHERE StudentID=?",
                           (firstname, surname, dob, gender, mastery, yeargroup, email, first_subject, second_subject, third_subject, fourth_subject, student_id))
            
            cursor.execute("UPDATE Student_Info SET Parentname=?, Parentnumber=?, Address=?, Nationality=?, CountryofBirth=?, EnrollmentDate=? WHERE StudentID=?",
                           (parentname, parentnumber, address, nationality, countryofbirth, enrollmentdate, student_id))
            
            cursor.execute("UPDATE Medical_Info SET Conditions=?, Medication=?, Allergies=?, Needs=? WHERE StudentID=?",
                           (conditions, medication, allergies, needs, student_id))

            connection.commit()
            connection.close()
            flash(f'Student {firstname} {surname} (Year {yeargroup}) updated successfully', 'success')
            return redirect(url_for('view_student', student_id=student_id))

        return render_template("edit_student.html", student=student, info=info, medical=medical, timetable=timetable, id=teacherid, subjects=subjects, firstname=firstname, surname=surname, email=session['user'], role='T')
    else:
        return redirect(url_for('login'))




@app.route("/timetable/<int:student_id>", methods=["GET", "POST"])
def edit_timetable(student_id):
    if "user" in session:
        
        connection = sqlite3.connect("schooldata.db")
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM Teachers WHERE Email=?", (session['user'],))
        teacher = cursor.fetchone()
        teacherid = teacher[0]
        
        cursor.execute("SELECT * FROM Students WHERE StudentID=?", (student_id,))
        student = cursor.fetchone()
        mastery = student[5]
        student_id = student_id
        student_subjects = [student[8], student[9], student[10], student[11]]

        # Get all subjects for period selection
        cursor.execute("SELECT SubjectID, Subjectname FROM Subjects WHERE Subjectname != 'Admin' ORDER BY Subjectname")
        all_subjects = cursor.fetchall()
        
        # Build periods list with format: [(name/id, display_name), ...]
        periods = [(mastery, mastery)]  # Mastery stores mastery name
        for subject_id in student_subjects:
            if subject_id:
                cursor.execute("SELECT Subjectname FROM Subjects WHERE SubjectID=?", (subject_id,))
                result = cursor.fetchone()
                if result:
                    periods.append((subject_id, result[0]))  # Store (SubjectID, SubjectName)
        periods.append(("FREE", "FREE"))
            



        cursor.execute("SELECT * FROM Timetable WHERE StudentID=?", (student_id,))
        timetable = cursor.fetchall()


        if request.method == "POST":
            for day in range(1, 6):
                period1 = mastery
                period2 = request.form.get(f"day{day}_period2")
                period3 = request.form.get(f"day{day}_period3")
                period4 = request.form.get(f"day{day}_period4")
                period5 = mastery
                period6 = request.form.get(f"day{day}_period6")
                period7 = request.form.get(f"day{day}_period7")
                period8 = request.form.get(f"day{day}_period8")
                
                # Convert period values: if it's a number string (SubjectID), use it; if it's text, handle it
                # Period 2, 3, 4, 6, 7, 8 should be SubjectID (integer)
                # First, check if the value is FREE or a mastery name
                periods_to_save = []
                for period_val in [period1, period2, period3, period4, period5, period6, period7, period8]:
                    if period_val == "FREE" or period_val == mastery:
                        periods_to_save.append(period_val)
                    else:
                        # It's a SubjectID (should be integer or integer string)
                        try:
                            periods_to_save.append(int(period_val))
                        except (ValueError, TypeError):
                            periods_to_save.append(period_val)

                cursor.execute("""
                    UPDATE Timetable
                    SET Period1=?, Period2=?, Period3=?, Period4=?, Period5=?, Period6=?, Period7=?, Period8=?
                    WHERE StudentID=? AND DAY=?
                """, (periods_to_save[0], periods_to_save[1], periods_to_save[2], periods_to_save[3], 
                      periods_to_save[4], periods_to_save[5], periods_to_save[6], periods_to_save[7], 
                      student_id, day))

            connection.commit()
            connection.close()
            return redirect(url_for('view_student', student_id=student_id))
        
        connection.close()
        return render_template("edit_timetable.html", student=student, timetable=timetable, 
                               periods=periods, id=teacherid, student_id=student_id, mastery=mastery, 
                               all_subjects=all_subjects, firstname=teacher[1], surname=teacher[2], 
                               email=session['user'], role='T')
    else:
        return redirect(url_for('login'))




# ROUTE: /import_students (Bulk Import Students via CSV)
# PURPOSE: Upload CSV file with multiple student records
# VALIDATION: Headers must exactly match EXPECTED_HEADERS
# PROCESS:
# 1. Read CSV file (UTF-8 with BOM support)
# 2. Validate header format
# 3. If headers match: directly import to database
# 4. If headers don't match: redirect to /map_headers for manual mapping
# DATABASE: Creates Students, Student_Info, Medical_Info, Timetable records
# ERROR HANDLING: Skips rows with wrong column count, continues on errors
@app.route('/import_students', methods=['GET', 'POST'])
def import_students():
    """ 
    PROCESS:
    1. User uploads CSV file with student data
    2. System validates headers match expected format
    3. For each row:
       - Normalize and clean data (capitalization, trimming, validation)
       - Create student record in Students table
       - Create associated records in Student_Info and Medical_Info tables
       - Initialize timetable entries for 5 school days
    4. Count successes/skips
    5. Display results to user
    
    DATA VALIDATION:
    - Headers must exactly match EXPECTED_HEADERS
    - Each row must have correct number of columns
    - Handles encoding issues (UTF-8 BOM)
    - Normalizes text: title case, trimming whitespace, lowercase emails
    
    DATABASE STRUCTURE (Created records):
    - Students: Main student record
    - Student_Info: Contact/demographic information
    - Medical_Info: Health conditions and allergies
    - Timetable: Initial 5-day schedule entries
    
    ERROR HANDLING:
    - Skips rows with wrong column count
    - Continues on individual row errors (doesn't abort all)
    - Provides summary of imported vs skipped
    
    TIME COMPLEXITY: O(n * m) where n = rows, m = tables being inserted to
    SPACE COMPLEXITY: O(n) for storing all rows in memory
    """
    if 'user' not in session:
        return redirect(url_for('login'))
    
    connection = sqlite3.connect("schooldata.db")
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM Teachers WHERE Email=?", (session['user'],))
    teacher = cursor.fetchone()
    teacherid = teacher[0]
    connection.close()

    if request.method == 'POST':
        file = request.files.get('csv_file')

        if not file or file.filename == "":
            return redirect(request.url)

        try:
            # Read CSV file with UTF-8 encoding (handle BOM for Windows Excel exports)
            stream = io.StringIO(file.stream.read().decode("utf-8-sig"))
            reader = csv.reader(stream)
            headers = next(reader)
            headers = [h.strip() for h in headers]
            # Remove BOM character that sometimes appears in first header
            headers[0] = headers[0].replace('\ufeff', '')
            rows = list(reader)
            
            if len(rows) == 0:
                return redirect(request.url)
            
            # VALIDATION: Check if headers match expected format exactly
            if headers == EXPECTED_HEADERS:
                conn = sqlite3.connect("schooldata.db")
                cursor = conn.cursor()

                imported = 0
                skipped = 0

                # ALGORITHM: Process each student row
                for i, row in enumerate(rows, start=2):
                    # Skip rows with wrong number of columns
                    if len(row) != len(EXPECTED_HEADERS):
                        skipped += 1
                        continue

                    # Unpack row data into individual variables
                    (
                        firstname, surname, dob, gender, yeargroup, mastery, email,
                        parentname, parentnumber, address,  nationality, cob, enrolldate,
                        conditions, medication, allergies, needs
                    ) = row

                    # DATA NORMALIZATION: Clean and standardize all fields
                    # Title case: converts "john smith" to "John Smith"
                    # Strip: removes leading/trailing whitespace
                    # Upper/Lower: standardizes case
                    firstname = firstname.title().strip()
                    surname = surname.title().strip()
                    dob = dob.strip()
                    gender = gender.strip()[0].upper()  # Just first letter (M/F/O)
                    mastery = mastery.upper().strip()  # Mastery levels typically uppercase
                    yeargroup = yeargroup.strip()
                    email = email.lower().strip()  # Emails always lowercase
                    parentname = parentname.title().strip()
                    parentnumber = parentnumber.strip()
                    address = address.strip()   
                    nationality = nationality.title().strip()
                    cob = cob.title().strip()
                    enrolldate = enrolldate.strip()
                    conditions = conditions.title().strip()
                    medication = medication.title().strip()
                    allergies = allergies.title().strip()
                    needs = needs.title().strip()


                    # INSERT INTO STUDENTS TABLE - Main student record
                    cursor.execute("""
                        INSERT INTO Students 
                        (Firstname, Surname, DOB, Gender, Mastery, Yeargroup, Email)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (firstname, surname, dob, gender, mastery, yeargroup, email))

                    # Get ID of newly created student (auto-increment primary key)
                    student_id = cursor.lastrowid
                    
                    # INSERT INTO STUDENT_INFO - Contact & demographic information
                    cursor.execute("""
                        INSERT INTO Student_Info
                        (StudentID, Parentname, Parentnumber, Address, Nationality, countryofbirth, Enrollmentdate)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (student_id, parentname, parentnumber, address, nationality, cob, enrolldate))
                    
                    # INSERT INTO MEDICAL_INFO - Health & medical data
                    cursor.execute("""
                        INSERT INTO Medical_Info
                        (StudentID, Conditions, Medication, Allergies, Needs)
                        VALUES (?, ?, ?, ?, ?)
                    """, (student_id, conditions, medication, allergies, needs))
                    
                    imported += 1
                    
                    # INITIALIZE TIMETABLE - Create 5 empty timetable rows (Mon-Fri)
                    # These will be populated later when teachers schedule lessons
                    cursor.execute("INSERT INTO Timetable (StudentID, DAY) VALUES (?, ?)", (student_id, "1"))
                    cursor.execute("INSERT INTO Timetable (StudentID, DAY) VALUES (?, ?)", (student_id, "2"))
                    cursor.execute("INSERT INTO Timetable (StudentID, DAY) VALUES (?, ?)", (student_id, "3"))
                    cursor.execute("INSERT INTO Timetable (StudentID, DAY) VALUES (?, ?)", (student_id, "4"))
                    cursor.execute("INSERT INTO Timetable (StudentID, DAY) VALUES (?, ?)", (student_id, "5"))

                # COMMIT ALL CHANGES - Either all rows import or transaction rolls back
                conn.commit()
                conn.close()

                if imported > 0:    
                    flash(f'Successfully imported {imported} students.', 'success')
                if skipped > 0:
                    flash(f'Skipped {skipped} rows due to errors.', 'error')

                return redirect(url_for('import_students'))
            
            else:
                session['uploaded_headers'] = headers
                session['uploaded_rows'] = rows
                return redirect(url_for('map_headers'))
            
        except Exception as e: 
            flash('An error occurred while processing the file.', 'error')
            return redirect(url_for('import_students'))
    return render_template('import_students.html', id=teacherid)



# ROUTE: /download_student_template (Get CSV Template)
# PURPOSE: Download template CSV file for bulk import
# FILE: static/student_import_template.csv with correct headers
@app.route('/download_student_template')
def download_student_template():
    if 'user' not in session:
        return redirect(url_for('login'))

    return send_from_directory(
        directory="static",
        path="student_import_template.csv",
        as_attachment=True
    )




# ROUTE: /map_headers (CSV Header Mapping)
# PURPOSE: When CSV headers don't match template, user maps them manually
# PROCESS:
# 1. User selects which system field each CSV column represents
# 2. Mapping stored in session
# 3. Redirect to /confirm_mapped_import to process
@app.route('/map_headers', methods=['GET', 'POST'])
def map_headers():
    if 'user' not in session:
        return redirect(url_for('login'))

    connection = sqlite3.connect("schooldata.db")
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM Teachers WHERE Email=?", (session['user'],))  
    teacher = cursor.fetchone()
    teacherid = teacher[0]
    connection.close()

    uploaded_headers = session.get('uploaded_headers')

    if not uploaded_headers:
        return redirect(url_for('import_students'))

    if request.method == 'POST':
        mapping = {}
        for h in uploaded_headers:
            selected = request.form.get(h)
            if selected:
                mapping[h] = selected

        session['header_mapping'] = mapping
        return redirect(url_for('confirm_mapped_import'))

    return render_template(
        "map_headers.html", id=teacherid,
        uploaded_headers=uploaded_headers,
        system_fields=SYSTEM_FIELDS
    )



# ROUTE: /confirm_mapped_import (Process Manually Mapped CSV)
# PURPOSE: Import students using headers mapped by user
# PROCESS: Applies user's column mappings and imports data
# DATABASE: Creates Students, Student_Info, Medical_Info, Timetable records
@app.route('/confirm_mapped_import')
def confirm_mapped_import():
    if 'user' in session:
        rows = session.get('uploaded_rows')
        mapping = session.get('header_mapping')

        if not rows or not mapping:
            return redirect(url_for('import_students'))

        conn = sqlite3.connect("schooldata.db")
        cursor = conn.cursor()
        
        imported = 0
        skipped = 0

        for row_num, row in enumerate(rows, start=2):
            row_data = dict(zip(session['uploaded_headers'], row))

            data = {field: "" for field in SYSTEM_FIELDS}
            for csv_col, system_col in mapping.items():
                data[system_col] = row_data.get(csv_col, "")

            # Convert subject fields to integers or None
            try:
                first_subj = int(data["FirstSubject"]) if data["FirstSubject"].strip() else None
            except (ValueError, AttributeError):
                first_subj = None
            
            try:
                second_subj = int(data["SecondSubject"]) if data["SecondSubject"].strip() else None
            except (ValueError, AttributeError):
                second_subj = None
            
            try:
                third_subj = int(data["ThirdSubject"]) if data["ThirdSubject"].strip() else None
            except (ValueError, AttributeError):
                third_subj = None
            
            try:
                fourth_subj = int(data["FourthSubject"]) if data["FourthSubject"].strip() else None
            except (ValueError, AttributeError):
                fourth_subj = None

            cursor.execute("""
                INSERT INTO Students
                (Firstname, Surname, DOB, Gender, Mastery, Yeargroup, Email, FirstSubject, SecondSubject, ThirdSubject, FourthSubject)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data["Firstname"], data["Surname"], data["DOB"],
                data["Gender"], data["Mastery"], data["Yeargroup"], data["Email"],
                first_subj, second_subj, third_subj, fourth_subj
            ))

            student_id = cursor.lastrowid

            cursor.execute("""
                INSERT INTO Student_Info
                (StudentID, Parentname, Parentnumber, Address, Nationality, countryofbirth, Enrollmentdate)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                student_id, data["Parentname"], data["Parentnumber"],
                data["Address"], data["Nationality"],
                data["CountryOfBirth"], data["EnrollmentDate"]
            ))

            cursor.execute("""
                INSERT INTO Medical_Info
                (StudentID, Conditions, Medication, Allergies, Needs)
                VALUES (?, ?, ?, ?, ?)
            """, (
                student_id, data["Conditions"], data["Medication"],
                data["Allergies"], data["Needs"]
            ))
            
            imported += 1

        conn.commit()
        conn.close()

        session.pop('uploaded_headers', None)
        session.pop('uploaded_rows', None)
        session.pop('header_mapping', None)

        return redirect(url_for('import_students'))
    else:
        return redirect(url_for('login'))



# =====================================================================
# ROUTE: /students/delete (Delete Student - Admin Only)
# PURPOSE: Display list of students for deletion selection
# PERMISSIONS: Admin teachers only (role='A')
# SEARCH: Can filter students by name, email, year, mastery
# =====================================================================
@app.route("/students/delete", methods=["GET"])
def delete_students():
    if "user" not in session:
        return redirect(url_for("login"))

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM Teachers WHERE Email=?", (session["user"],))
    teacher = cur.fetchone()
    teacherid = teacher[0]
    if not teacher or teacher[5] != "A":
        conn.close()
        return redirect(url_for("students"))  # only admin can delete

    query = request.args.get("query", "").strip()

    if query:
        search_param = f"%{query}%"
        cur.execute("""SELECT * FROM Students WHERE
                       Firstname LIKE ? OR Surname LIKE ?
                       OR Email LIKE ? OR YearGroup LIKE ? OR Mastery LIKE ?""",
                    (search_param, search_param, search_param, search_param, search_param))
    else:
        cur.execute("SELECT * FROM Students")

    students = cur.fetchall()
    extra_info = cur.execute("SELECT * FROM Student_info").fetchall()
    conn.close()

    return render_template("delete_students.html", students=students, info=extra_info, query=query, id=teacherid)


@app.route("/students/delete/confirm", methods=["POST"])
def confirm_delete_students():
    if "user" not in session:
        return redirect(url_for("login"))

    connection = sqlite3.connect("schooldata.db")
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM Teachers WHERE Email=?", (session['user'],))
    teacher = cursor.fetchone()
    teacherid = teacher[0]
    connection.close()

    selected_ids = request.form.getlist("delete_ids")  # list of checked student IDs (strings)

    if not selected_ids:
        flash("No students selected.", "error")
        return redirect(url_for("delete_students"))

    # fetch details for confirmation page
    conn = get_db()
    cur = conn.cursor()

    placeholders = ",".join("?" for _ in selected_ids)
    cur.execute(f"SELECT * FROM Students WHERE StudentID IN ({placeholders})", selected_ids)
    selected_students = cur.fetchall()

    conn.close()

    return render_template("confirm_delete_students.html",
                           selected_students=selected_students,
                           selected_ids=selected_ids, id=teacherid)


@app.route("/students/delete/final", methods=["POST"])
def final_delete_students():
    if "user" not in session:
        return redirect(url_for("login"))

    selected_ids = request.form.getlist("selected_ids")
    if not selected_ids:
        flash("Nothing to delete.", "error")
        return redirect(url_for("delete_students"))
    conn = get_db()
    cur = conn.cursor()

    try:
        placeholders = ",".join("?" for _ in selected_ids)
 
        # delete from child tables first (prevents FK errors if not using CASCADE)
        cur.execute(f"DELETE FROM Timetable WHERE StudentID IN ({placeholders})", selected_ids)
        cur.execute(f"DELETE FROM Attendance WHERE StudentID IN ({placeholders})", selected_ids)
        cur.execute(f"DELETE FROM Medical_Info WHERE StudentID IN ({placeholders})", selected_ids)
        cur.execute(f"DELETE FROM Student_Info WHERE StudentID IN ({placeholders})", selected_ids)
        cur.execute(f"DELETE FROM BehaviourEvents WHERE StudentID IN ({placeholders})", selected_ids)
        cur.execute(f"DELETE FROM Scores WHERE StudentID IN ({placeholders})", selected_ids)
        cur.execute(f"DELETE FROM Assessments WHERE StudentID IN ({placeholders})", selected_ids)
        cur.execute(f"DELETE FROM Summaries WHERE StudentID IN ({placeholders})", selected_ids)

        # finally delete from Students
        cur.execute(f"DELETE FROM Students WHERE StudentID IN ({placeholders})", selected_ids)
        conn.commit()
    except Exception as e:
        conn.rollback()
        flash(f"Delete failed: {e}", "error")
    conn.close()
    return redirect(url_for("delete_students"))





# ROUTE: /log_behaviour (Record Student Behaviour Event)
# PURPOSE: Teachers log positive/negative behaviour incidents
# BEHAVIOUR TYPES:
# - 1: House Points (positive reinforcement)
# - 3: Detention (disciplinary)
# - 4: Withdrawal (absence)
# FEATURES: Auto-assigns current period, allows multiple entries at once
@app.route('/log_behaviour/<int:student_id>', methods=['GET', 'POST'])
def log_behaviour(student_id):
    if 'user' in session:
        connection = sqlite3.connect("schooldata.db")
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM Teachers WHERE Email=?", (session['user'],))
        teacher = cursor.fetchone()
        teacherid = teacher[0]

        cursor.execute("SELECT * FROM Students WHERE StudentID=?", (student_id,))
        student = cursor.fetchone()

        cursor.execute("SELECT * FROM BehaviourTypes")
        behaviour_types = cursor.fetchall()


        if request.method == 'POST':
            date = str(datetime.date.today())
            period = get_period()
            typeid = request.form.get('typeid')
            amount = request.form.get('amount')
            description = request.form.get('description').title()

            for i in range(int(amount)):
                cursor.execute("""
                    INSERT INTO BehaviourEvents (StudentID, Date, Period, TypeID, Description)
                    VALUES (?, ?, ?, ?, ?)
                """, (student_id, date, period, typeid, description))
            connection.commit()
            connection.close()
            return redirect(url_for('view_student', student_id=student_id))

        return render_template("log_behaviour.html", student_id=student_id, student=student, behaviour_types=behaviour_types, id=teacherid)
    else:
        return redirect(url_for('login'))


# ROUTE: /assessments/<student_id> (View Student Assessments)
# PURPOSE: Display all assessment records for a student
# DISPLAYS: Assessment type, score, subject, date in reverse chronological order
@app.route('/assessments/<int:student_id>', methods=['GET', 'POST'])
def assessments(student_id):
    if 'user' not in session:
        return redirect(url_for('login'))
    
    connection = sqlite3.connect("schooldata.db")
    cursor = connection.cursor()
    
    try:
        # Get logged-in teacher
        cursor.execute("SELECT * FROM Teachers WHERE Email=?", (session['user'],))
        teacher = cursor.fetchone()
        if not teacher:
            return redirect(url_for('login'))
        
        teacher_id = teacher[0]
        
        # Get student
        cursor.execute("SELECT * FROM Students WHERE StudentID=?", (student_id,))
        student = cursor.fetchone()
        if not student:
            return redirect(url_for('students'))
        
        # Get all assessments for this student
        cursor.execute("""
            SELECT AssessmentID, StudentID, SubjectID, Type, Score, Date 
            FROM Assessments 
            WHERE StudentID=? 
            ORDER BY Date DESC
        """, (student_id,))
        assessments_data = cursor.fetchall()
        
        # Get subject names for each assessment
        assessments_list = []
        for assessment in assessments_data:
            assessment_id, sid, subject_id, assessment_type, score, date = assessment
            
            # Get subject name
            cursor.execute("SELECT Subjectname FROM Subjects WHERE SubjectID=?", (subject_id,))
            subject_row = cursor.fetchone()
            subject_name = subject_row[0] if subject_row else "Unknown Subject"
            
            assessments_list.append({
                'id': assessment_id,
                'subject': subject_name,
                'type': assessment_type,
                'score': score,
                'date': date
            })
        
        return render_template(
            "assessments.html", 
            student=student, 
            assessments=assessments_list,
            id=teacher_id
        )
    
    finally:
        connection.close()


# ROUTE: /log_assessment (Record Student Assessment)
# PURPOSE: Log assessment scores and update Scores table
# ASSESSMENT TYPES: midpoint1, midpoint2, endpoint (only 3 types)
# PROCESS:
# 1. Insert into Assessments table
# 2. Update Scores table with assessment ID (Assessment1/2/3 columns)
# DATABASE: Creates entries in Assessments and updates Scores
@app.route('/log_assessment/<int:student_id>', methods=['GET', 'POST'])
def log_assessment(student_id):
    if 'user' not in session:
        return redirect(url_for('login'))
    
    connection = sqlite3.connect("schooldata.db")
    cursor = connection.cursor()
    
    try:
        # Get logged-in teacher
        cursor.execute("SELECT * FROM Teachers WHERE Email=?", (session['user'],))
        teacher = cursor.fetchone()
        if not teacher:
            return redirect(url_for('login'))
        
        teacher_id = teacher[0]
        
        # Get student
        cursor.execute("SELECT * FROM Students WHERE StudentID=?", (student_id,))
        student = cursor.fetchone()
        if not student:
            return redirect(url_for('students'))
        
        # Get only the subjects that the student is taking
        # Students can take 4 subjects (Subject1 through Subject4) stored in the Students table
        subject_ids = [student[8], student[9], student[10], student[11]]
        # Filter out None values - students may not be taking all 4 available subjects
        subject_ids = [sid for sid in subject_ids if sid is not None]
        
        # Query database for subject information for only the subjects this student is taking
        if subject_ids:
            placeholders = ','.join('?' * len(subject_ids))
            cursor.execute(f"SELECT SubjectID, Subjectname FROM Subjects WHERE SubjectID IN ({placeholders}) ORDER BY Subjectname", subject_ids)
        else:
            cursor.execute("SELECT SubjectID, Subjectname FROM Subjects WHERE 1=0")
        subjects = cursor.fetchall()

        if request.method == 'POST':
            subject_id = request.form.get('subject_id')
            assessment_type = request.form.get('type')
            date = request.form.get('date')
            score = request.form.get('score')

            if not all([subject_id, assessment_type, date, score]):
                flash('Please fill in all fields', 'error')
            else:
                # Validate date restrictions
                try:
                    assessment_date = datetime.datetime.strptime(date, '%Y-%m-%d').date()
                    today = datetime.date.today()
                    two_years_ago = today - timedelta(days=365*2)

                    if assessment_date < two_years_ago:
                        flash(f'Assessment date cannot be before {two_years_ago.strftime("%B %d, %Y")}. Please select a date from the past 2 years.', 'error')
                    # Check if date is in the future (after today)
                    elif assessment_date > today:
                        flash('Assessment date cannot be in the future. Please select today or an earlier date.', 'error')
                    else:
                        try:
                            # Check if maximum 3 assessments of this type for this subject already exist
                            cursor.execute("""
                                SELECT COUNT(*) FROM Assessments 
                                WHERE StudentID=? AND SubjectID=? AND Type=?
                            """, (student_id, subject_id, assessment_type))
                            assessment_count = cursor.fetchone()[0]
                            
                            # If already 3 or more assessments of this type exist, reject the new entry
                            if assessment_count >= 3:
                                flash(f'Cannot log more than 3 {assessment_type} assessments for this subject. Current count: {assessment_count}.', 'error')
                            else:
                                # Insert into Assessments table
                                cursor.execute("""
                                    INSERT INTO Assessments (StudentID, SubjectID, Type, Date, Score)
                                    VALUES (?, ?, ?, ?, ?)
                                """, (student_id, subject_id, assessment_type, date, score))
                                connection.commit()
                                
                                # Get the assessment ID that was just created
                                assessment_id = cursor.lastrowid
                                
                                # Map assessment type to the corresponding column in Scores table
                                assessment_column_map = {
                                    'midpoint1': 'Assessment1',
                                    'midpoint2': 'Assessment2',
                                    'endpoint': 'Assessment3'
                                }
                                
                                assessment_column = assessment_column_map.get(assessment_type)
                                
                                if assessment_column:
                                    # Check if a score record exists for this student and subject
                                    cursor.execute("""
                                        SELECT ScoreID FROM Scores 
                                        WHERE StudentID=? AND SubjectID=?
                                    """, (student_id, subject_id))
                                    score_record = cursor.fetchone()
                                    
                                    if score_record:
                                        # Update existing record with the assessment ID
                                        cursor.execute(f"""
                                            UPDATE Scores 
                                            SET {assessment_column}=? 
                                            WHERE StudentID=? AND SubjectID=?
                                        """, (assessment_id, student_id, subject_id))
                                    else:
                                        # Create new score record with this assessment
                                        # Only populate the appropriate assessment column based on type
                                        assessment_data = {
                                            'Assessment1': assessment_id if assessment_column == 'Assessment1' else None,
                                            'Assessment2': assessment_id if assessment_column == 'Assessment2' else None,
                                            'Assessment3': assessment_id if assessment_column == 'Assessment3' else None
                                        }
                                        cursor.execute("""
                                            INSERT INTO Scores (StudentID, SubjectID, Assessment1, Assessment2, Assessment3)
                                            VALUES (?, ?, ?, ?, ?)
                                        """, (student_id, subject_id, assessment_data['Assessment1'], assessment_data['Assessment2'], assessment_data['Assessment3']))
                                    
                                    connection.commit()
                                
                                flash('Assessment logged successfully', 'success')
                                return redirect(url_for('assessments', student_id=student_id))
                        except Exception as e:
                            flash(f'Error logging assessment: {str(e)}', 'error')
                except ValueError:
                    flash('Invalid date format', 'error')

        return render_template(
            "log_assessment.html", 
            student=student, 
            subjects=subjects,
            id=teacher_id
        )
    
    finally:
        connection.close()


# ROUTE: /students/analysis (Student Analysis Selection)
# PURPOSE: List all students for detailed week-by-week analysis
# DISPLAYS: Attendance and behaviour comparison (this week vs last week)
# SEARCH: Filter by name, email, year group, mastery
@app.route('/students/analysis')
def analysis():
    connection = sqlite3.connect("schooldata.db")
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM Teachers WHERE Email=?", (session['user'],))
    teacher = cursor.fetchall()
    for t in teacher:
        id = t[0]
    if 'user' in session:
        # Get search query from GET parameter
        query = request.args.get('query', '').strip()
        
        if query:
            # Search by ID, first name, surname, email, year, or mastery
            search_param = f"%{query}%"
            cursor.execute("""SELECT * FROM Students WHERE 
                            Firstname LIKE ? OR Surname LIKE ? 
                            OR Email LIKE ? OR YearGroup LIKE ? OR Mastery LIKE ?""", 
                            (search_param, search_param, search_param, search_param, search_param))
        else:
            cursor.execute("SELECT * FROM Students")

        students = cursor.fetchall()
        extra_info = cursor.execute("SELECT * FROM Student_info").fetchall()
        return render_template("analysis.html", students=students, info=extra_info, query=query, id=id)
    else:
        return redirect(url_for('login'))










# ROUTE: /analyse/<student_id> (Detailed Student Analysis)
# PURPOSE: Show this week vs last week comparison of:
# - Attendance (present, absent, late)
# - Behaviour (house points, detentions, withdrawals)
# ALGORITHM: Compares ISO week data (Mon-Sun) automatically
# TEMPLATE: Displays metrics and trends for teacher review
@app.route('/analyse/<int:student_id>')
def analyse(student_id):
    # Must be logged in
    if 'user' not in session:
        return redirect(url_for('login'))

    conn = sqlite3.connect("schooldata.db")
    cursor = conn.cursor()

    try:
        # Get logged-in teacher
        cursor.execute("SELECT * FROM Teachers WHERE Email=?", (session['user'],))
        teacher = cursor.fetchone()
        if not teacher:
            return redirect(url_for('login'))

        teacher_id = teacher[0]

        # Work out this week and last week (ISO weeks)
        today = datetime.date.today()
        this_week = today.isocalendar()[1]
        year = today.year

        last_week = this_week - 1
        if last_week == 0:
            year -= 1
            last_week = datetime.date(year, 12, 28).isocalendar()[1]

        # Get date ranges using function
        days_this_week = days_in_week(year, this_week)
        days_last_week = days_in_week(year, last_week)

        # Start and end dates for BETWEEN
        this_start, this_end = days_this_week[0], days_this_week[-1]
        last_start, last_end = days_last_week[0], days_last_week[-1]

        # Get student + info
        cursor.execute("SELECT * FROM Students WHERE StudentID=?", (student_id,))
        student = cursor.fetchone()
        if not student:
            return redirect(url_for('analysis'))

        cursor.execute("SELECT * FROM Student_info WHERE StudentID=?", (student_id,))
        info = cursor.fetchall()

        # Behaviour (this week)
        cursor.execute("""SELECT * FROM BehaviourEvents WHERE StudentID = ? AND Date BETWEEN ? AND ? """,
            (student_id, this_start, this_end))
        
        behaviour_this_week = cursor.fetchall()

        # Behaviour (last week)
        cursor.execute("""SELECT * FROM BehaviourEvents WHERE StudentID = ? AND Date BETWEEN ? AND ? """,
            (student_id, last_start, last_end))


        behaviour_last_week = cursor.fetchall()

        # Count behaviour types
        curr_hp = count_behaviour(behaviour_this_week, HOUSE_POINT)
        prev_hp = count_behaviour(behaviour_last_week, HOUSE_POINT)

        curr_detentions = count_behaviour(behaviour_this_week, DETENTION)
        prev_detentions = count_behaviour(behaviour_last_week, DETENTION)

        curr_wd = count_behaviour(behaviour_this_week, WITHDRAWAL)
        prev_wd = count_behaviour(behaviour_last_week, WITHDRAWAL)

        # Attendance (this week)
        cursor.execute(
            """ SELECT * FROM Attendance WHERE StudentID = ? AND Date BETWEEN ? AND ? """,
            (student_id, this_start, this_end))
        # Attendance (this week)
        cursor.execute(
            """ SELECT * FROM Attendance WHERE StudentID = ? AND Date BETWEEN ? AND ? """,
            (student_id, this_start, this_end))
        
        attendance_this_week = cursor.fetchall()

        # Attendance (last week)
        cursor.execute(""" SELECT * FROM Attendance WHERE StudentID = ? AND Date BETWEEN ? AND ? """,
            (student_id, last_start, last_end))
        
        attendance_last_week = cursor.fetchall()

        # Count attendance statuses
        curr_present = count_attendance(attendance_this_week, "Present")
        curr_absent  = count_attendance(attendance_this_week, "Absent")
        curr_late    = count_attendance(attendance_this_week, "Late")

        prev_present = count_attendance(attendance_last_week, "Present")
        prev_absent  = count_attendance(attendance_last_week, "Absent")
        prev_late    = count_attendance(attendance_last_week, "Late")

        # 6) Render page
        return render_template("analyse.html",student=student,info=info,id=teacher_id, curr_present=curr_present,
            curr_absent=curr_absent,curr_late=curr_late,prev_present=prev_present,prev_absent=prev_absent,
            prev_late=prev_late, curr_detentions=curr_detentions,prev_detentions=prev_detentions,
            curr_hp=curr_hp,prev_hp=prev_hp, curr_wd=curr_wd, prev_wd=prev_wd) 

    finally:
        conn.close()





# ROUTE: /smart_generator (AI Summary Selection)
# PURPOSE: List students available for AI-powered analysis
# FEATURES: Search by name, email, year, mastery
# AI CAPABILITY: Uses OpenAI to generate weekly summaries
@app.route('/smart_generator')
def smart_summary():
    connection = sqlite3.connect("schooldata.db")
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM Teachers WHERE Email=?", (session['user'],))
    teacher = cursor.fetchall()
    for t in teacher:
        id = t[0]
    if 'user' in session:
        # Get search query from GET parameter
        query = request.args.get('query', '').strip()
        
        if query:
            # Search by ID, first name, surname, email, year, or mastery
            search_param = f"%{query}%"
            cursor.execute("""SELECT * FROM Students WHERE 
                            Firstname LIKE ? OR Surname LIKE ? 
                            OR Email LIKE ? OR YearGroup LIKE ? OR Mastery LIKE ?""", 
                            (search_param, search_param, search_param, search_param, search_param))
        else:
            cursor.execute("SELECT * FROM Students")

        students = cursor.fetchall()
        extra_info = cursor.execute("SELECT * FROM Student_info").fetchall()
        return render_template("smart.html", students=students, info=extra_info, query=query, id=id)
    else:
        return redirect(url_for('login'))




# ROUTE: /smart_analysis/<student_id> (AI-Generated Student Summary)
# PURPOSE: Generate AI-powered weekly analysis of student performance
# ALGORITHM:
# 1. Call build_weekly_summary_prompt() to gather data
# 2. Send to OpenAI GPT-3.5-turbo for analysis
# 3. Display generated summary with recommendations
# AI INSIGHTS: Compares this week vs last week, identifies patterns
@app.route('/smart_analysis/<int:student_id>', methods=["GET", "POST"])
def smart(student_id):
    if "user" not in session:
        return redirect(url_for("login"))

    connection = sqlite3.connect("schooldata.db")
    cursor = connection.cursor()

    cursor.execute("SELECT * FROM Teachers WHERE Email=?", (session["user"],))
    teacher = cursor.fetchone()
    if not teacher:
        connection.close()
        return redirect(url_for("login"))
    teacherid = teacher[0]

    cursor.execute("SELECT * FROM Students WHERE StudentID=?", (student_id,))
    student = cursor.fetchone()
    if not student:
        connection.close()
        return redirect(url_for("students"))

    summary = None

    # unique key per student
    session_key = f"summary_generated_{student_id}"

    if request.method == "POST" and not session.get(session_key):
        prompt = build_weekly_summary_prompt(cursor, student_id)
        summary = weekly_summary_generator(prompt)
        session[session_key] = True  # lock button after first click
    elif session.get(session_key):
        # already generated before
        prompt = build_weekly_summary_prompt(cursor, student_id)
        summary = weekly_summary_generator(prompt)

    connection.close()

    return render_template(
        "smart_analysis.html",
        student=student,
        summary=summary,
        summary_generated=session.get(session_key, False),
        id=teacherid,
    )



if __name__ == "__main__": # Run the app
    app.run(debug=True)









