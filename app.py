from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os
from openai import OpenAI
from datetime import date, datetime

app = Flask(__name__)
# Use a fixed secret key from environment variable, or use a default
# This ensures sessions persist across server restarts
# In production, set FLASK_SECRET_KEY environment variable to a secure random string
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production-12345')
# Configure session to be permanent (persist across browser restarts)
app.config['PERMANENT_SESSION_LIFETIME'] = 86400 * 30  # 30 days

# Initialize OpenAI client
# Get API key from environment variable for security
openai_api_key = os.getenv('OPENAI_API_KEY')
if not openai_api_key:
    raise ValueError("OPENAI_API_KEY environment variable is not set")
client = OpenAI(api_key=openai_api_key)

# Database setup
DATABASE = 'users.db'

def get_db():
    """Get database connection"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize the database with users and appointments tables"""
    conn = get_db()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL,
            admin_group TEXT,
            patient_group TEXT,
            name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # Add name column if it doesn't exist (for existing databases)
    try:
        conn.execute('ALTER TABLE users ADD COLUMN name TEXT')
    except sqlite3.OperationalError:
        pass  # Column already exists
    # Add date_of_birth column if it doesn't exist
    try:
        conn.execute('ALTER TABLE users ADD COLUMN date_of_birth TEXT')
    except sqlite3.OperationalError:
        pass  # Column already exists
    # Add gender column if it doesn't exist
    try:
        conn.execute('ALTER TABLE users ADD COLUMN gender TEXT')
    except sqlite3.OperationalError:
        pass  # Column already exists
    # Try to rename sex_assigned_at_birth to gender if it exists
    try:
        conn.execute('ALTER TABLE users RENAME COLUMN sex_assigned_at_birth TO gender')
    except sqlite3.OperationalError:
        pass  # Column doesn't exist or already renamed
    
    # Create appointments table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS appointments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                time TEXT NOT NULL,
                age_years INTEGER NOT NULL,
                height TEXT NOT NULL,
                weight TEXT NOT NULL,
                concerns TEXT,
                diet_info TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        ''')
        # Add diet_info column if it doesn't exist (for existing databases)
        try:
            conn.execute('ALTER TABLE appointments ADD COLUMN diet_info TEXT')
        except sqlite3.OperationalError:
            pass
        # Add new columns for additional sections
        for column in ['toileting_info', 'sleep_info', 'development_behavior_info', 'social_info', 'extracted_concerns']:
            try:
                conn.execute(f'ALTER TABLE appointments ADD COLUMN {column} TEXT')
            except sqlite3.OperationalError:
                pass  # Column already exists
        # Add recommendation columns for each section
        for column in ['diet_recommendations', 'toileting_recommendations', 'sleep_recommendations', 'development_behavior_recommendations', 'social_recommendations', 'concerns_recommendations']:
            try:
                conn.execute(f'ALTER TABLE appointments ADD COLUMN {column} TEXT')
            except sqlite3.OperationalError:
                pass  # Column already exists
        # Add growth_percentile_info column
        try:
            conn.execute('ALTER TABLE appointments ADD COLUMN growth_percentile_info TEXT')
        except sqlite3.OperationalError:
            pass  # Column already exists
    conn.commit()
    conn.close()


@app.route("/")
def cover_page():
    """Redirect to main page"""
    return redirect(url_for('main_page'))

@app.route("/main")
def main_page():
    return render_template("main.html")

@app.route("/people")
def people_page():
    """Display users in admin's group"""
    if 'user_id' not in session:
        flash("Please log in to view this page.", "error")
        return redirect(url_for('login'))
    
    # Check if user is admin
    if session.get('role') != 'admin':
        flash("Access denied. Admin access required.", "error")
        return redirect(url_for('main_page'))
    
    admin_group = session.get('admin_group')
    if not admin_group:
        flash("No admin group assigned. Please contact support.", "error")
        return redirect(url_for('main_page'))
    
    conn = get_db()
    # Get users who are in this admin's group (where patient_group matches admin_group)
    users = conn.execute('''
        SELECT id, username, name, role, date_of_birth, gender, created_at, patient_group
        FROM users
        WHERE patient_group = ?
        ORDER BY created_at DESC
    ''', (admin_group,)).fetchall()
    conn.close()
    
    return render_template("people.html", users=users)


@app.route("/reports")
@app.route("/reports/<int:view_user_id>")
def reports_page(view_user_id=None):
    """Display user's appointment history"""
    if 'user_id' not in session:
        flash("Please log in to view your reports.", "error")
        return redirect(url_for('login'))
    
    current_user_id = session['user_id']
    current_user_role = session.get('role')
    
    # If view_user_id is provided, check if current user is admin viewing another user's reports
    if view_user_id:
        if current_user_role != 'admin':
            flash("Access denied. Admin access required.", "error")
            return redirect(url_for('reports_page'))
        
        # Verify the user being viewed is in the admin's group
        conn = get_db()
        target_user = conn.execute('SELECT patient_group FROM users WHERE id = ?', (view_user_id,)).fetchone()
        admin_group = session.get('admin_group')
        
        if not target_user or target_user['patient_group'] != admin_group:
            conn.close()
            flash("Access denied. User not in your admin group.", "error")
            return redirect(url_for('people_page'))
        
        user_id = view_user_id
        viewing_other_user = True
        conn.close()
    else:
        user_id = current_user_id
        viewing_other_user = False
    
    conn = get_db()
    
    # Retrieve all appointments for this user, ordered by date (newest first)
    appointments = conn.execute('''
        SELECT * FROM appointments 
        WHERE user_id = ? 
        ORDER BY date DESC, time DESC
    ''', (user_id,)).fetchall()
    
    # Get user info for display
    user_info = None
    if viewing_other_user:
        user_info = conn.execute('SELECT name, username FROM users WHERE id = ?', (user_id,)).fetchone()
    conn.close()
    
    return render_template("reports.html", appointments=appointments, viewing_other_user=viewing_other_user, user_info=user_info)

@app.route("/extract-diet", methods=["POST"])
def extract_diet():
    """Extract all information sections from conversation and save to database"""
    if 'appointment_data' not in session:
        return jsonify({"error": "No active appointment"}), 400
    
    appointment_id = session.get('appointment_data', {}).get('id')
    conversation_history = session.get('conversation_history', [])
    
    if not appointment_id or not conversation_history:
        return jsonify({"error": "No conversation data available"}), 400
    
    # Build a prompt to extract all information sections
    conversation_text = "\n".join([
        f"{msg['role']}: {msg['content']}" for msg in conversation_history
    ])
    
    extraction_prompt = f"""Based on the following conversation between a pediatrician and a patient, extract and summarize information for each category. 

FIRST, extract the patient's height and weight from the conversation. Look for when the pediatrician asked about height and weight, and what the patient/parent responded. Extract these as:
- "height": The patient's height with units (e.g., "150 cm", "5 feet 3 inches", "60 inches")
- "weight": The patient's weight with units (e.g., "45 kg", "100 lbs", "100 pounds")

Map the questions to sections as follows:

QUESTIONS 1-3 → Diet section:
- Question 1: How many servings of fruits and vegetables per day?
- Question 2: How much dairy?
- Question 3: Does child brush teeth twice a day?

QUESTIONS 4-5 → Toileting section:
- Question 4: Is child potty trained? Any concerns with peeing or pooping? (ONLY ask if age is under 3 years old)
- Question 5: Is there any constipation?  (ALWAYS ask this)

QUESTIONS 6-7 → Sleep section:
- Question 6: How many hours does child sleep at night?
- Question 7: Any concerns with sleep?

QUESTION 8 → Development/Behavior section:
- Question 8: Gross motor, fine motor, and developmental milestones

QUESTIONS 9-11 → Social section:
- Question 9: Does child go to school? What grade? If no, what do they do instead? (or daycare/home care for <5)
- Question 10: Who lives at home?
- Question 11: Are there smokers in the home?

QUESTION 12 → Concerns section:
- Question 12: Medical concerns today? Any questions?
- Include a summary of: what concerns/questions the patient/parent mentioned, what the pediatrician asked about, and how the pediatrician responded to those concerns/questions
- This should summarize the entire exchange about medical concerns, not just the initial question

For each category, provide bullet points summarizing the patient's answers. If information is missing or unclear, note that in the summary. 

Also extract any recommendations, advice, or guidance given by the pediatrician for each category. If no recommendations were given for a category, use "None" for that category's recommendations.

Format your response as JSON with keys: 
- "height": The patient's height with units (e.g., "150 cm" or "5 feet 3 inches")
- "weight": The patient's weight with units (e.g., "45 kg" or "100 lbs")
- "diet", "toileting", "sleep", "development_behavior", "social", "concerns" (each with patient answers as bullet points)
- "diet_recommendations", "toileting_recommendations", "sleep_recommendations", "development_behavior_recommendations", "social_recommendations", "concerns_recommendations" (each with recommendations/advice given, or "None" if none)

Each value should be a string with bullet points separated by newlines, or "None" for recommendations if none were given.

Conversation:
{conversation_text}

Extract the information in JSON format:"""
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": extraction_prompt}],
            temperature=0.3,
            max_tokens=2000,
            response_format={"type": "json_object"}
        )
        
        extracted_data = response.choices[0].message.content.strip()
        import json
        data = json.loads(extracted_data)
        
        # Get appointment data for growth percentile calculation
        appointment_data = session.get('appointment_data', {})
        patient_age = appointment_data.get('age_years', 0)
        patient_gender = appointment_data.get('gender', '')
        extracted_height = data.get('height', 'N/A')
        extracted_weight = data.get('weight', 'N/A')
        
        # Calculate growth percentiles
        growth_percentile_info = 'N/A'
        if extracted_height != 'N/A' and extracted_weight != 'N/A' and patient_age and patient_gender:
            try:
                growth_prompt = f"with a {extracted_height}, {extracted_weight}, {patient_age} year old {patient_gender} can you tell me the BMI, BMI Percentile, Height Percentile, and Weight Percentile. use pediatric growth charts from CDC. ONLY give me name: answer."
                
                growth_response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": growth_prompt}],
                    temperature=0.3,
                    max_tokens=200
                )
                
                growth_percentile_info = growth_response.choices[0].message.content.strip()
            except Exception as e:
                print(f"Error calculating growth percentiles: {str(e)}")
                growth_percentile_info = 'N/A'
        
        # Save to database
        conn = get_db()
        conn.execute(
            '''UPDATE appointments SET 
                height = ?,
                weight = ?,
                growth_percentile_info = ?,
                diet_info = ?,
                toileting_info = ?,
                sleep_info = ?,
                development_behavior_info = ?,
                social_info = ?,
                extracted_concerns = ?,
                diet_recommendations = ?,
                toileting_recommendations = ?,
                sleep_recommendations = ?,
                development_behavior_recommendations = ?,
                social_recommendations = ?,
                concerns_recommendations = ?
            WHERE id = ?''',
            (
                extracted_height,
                extracted_weight,
                growth_percentile_info,
                data.get('diet', ''),
                data.get('toileting', ''),
                data.get('sleep', ''),
                data.get('development_behavior', ''),
                data.get('social', ''),
                data.get('concerns', ''),
                data.get('diet_recommendations', 'None'),
                data.get('toileting_recommendations', 'None'),
                data.get('sleep_recommendations', 'None'),
                data.get('development_behavior_recommendations', 'None'),
                data.get('social_recommendations', 'None'),
                data.get('concerns_recommendations', 'None'),
                appointment_id
            )
        )
        conn.commit()
        conn.close()
        
        return jsonify({"success": True, "data": data})
    
    except Exception as e:
        print(f"Error extracting info: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route("/account")
def account_page():
    """Display user profile page"""
    if 'user_id' not in session:
        return redirect(url_for('cover_page'))
    
    conn = get_db()
    user = conn.execute(
        'SELECT * FROM users WHERE id = ?', (session['user_id'],)
    ).fetchone()
    
    if not user:
        conn.close()
        session.clear()
        return redirect(url_for('cover_page'))
    
    # Get group members if admin, or group admin if patient
    group_members = []
    group_admin = None
    
    if user['role'] == 'admin' and user['admin_group']:
        # Get all patients in this admin's group
        group_members = conn.execute(
            'SELECT username, name FROM users WHERE patient_group = ? AND role = ?',
            (user['admin_group'], 'patient')
        ).fetchall()
    elif user['role'] == 'patient' and user['patient_group']:
        # Get the admin of this patient's group
        admin = conn.execute(
            'SELECT username, name FROM users WHERE admin_group = ? AND role = ?',
            (user['patient_group'], 'admin')
        ).fetchone()
        if admin:
            group_admin = dict(admin)
    
    conn.close()
    
    return render_template("account.html", 
                         user=user,
                         group_members=group_members,
                         group_admin=group_admin)

@app.route("/edit-profile", methods=["GET", "POST"])
def edit_profile():
    """Edit user profile"""
    if 'user_id' not in session:
        return redirect(url_for('cover_page'))
    
    conn = get_db()
    user = conn.execute(
        'SELECT * FROM users WHERE id = ?', (session['user_id'],)
    ).fetchone()
    
    if not user:
        conn.close()
        session.clear()
        return redirect(url_for('cover_page'))
    
    if request.method == "POST":
        new_username = request.form.get("username", "").strip()
        new_password = request.form.get("password", "").strip()
        new_name = request.form.get("name", "").strip()
        
        # Validate username (always required)
        if not new_username:
            conn.close()
            return render_template("edit_profile.html", user=user, 
                                 error="Username is required.")
        
        # Check if new username already exists (if changed)
        if new_username.lower() != user['username'].lower():
            existing = conn.execute(
                'SELECT * FROM users WHERE LOWER(username) = LOWER(?) AND id != ?',
                (new_username, user['id'])
            ).fetchone()
            if existing:
                conn.close()
                return render_template("edit_profile.html", user=user, 
                                     error="Username already exists. Please choose a different username.")
        
        # Update username (always update to ensure consistency)
        conn.execute(
            'UPDATE users SET username = ? WHERE id = ?',
            (new_username, user['id'])
        )
        session['username'] = new_username
        
        # Update password if provided
        if new_password:
            password_hash = generate_password_hash(new_password)
            conn.execute(
                'UPDATE users SET password_hash = ? WHERE id = ?',
                (password_hash, user['id'])
            )
        
        # Update name (always update, even if empty to allow clearing)
        conn.execute(
            'UPDATE users SET name = ? WHERE id = ?',
            (new_name if new_name else None, user['id'])
        )
        
        # Update name in session
        session['name'] = new_name if new_name else None
        
        # Commit all changes to database
        conn.commit()
        conn.close()
        
        # Redirect back to profile page
        return redirect(url_for('account_page'))
    
    conn.close()
    return render_template("edit_profile.html", user=user)


@app.route("/appointment")
def appointment_page():
    """Create a new appointment and redirect to conversation page"""
    try:
        # Get user ID
        user_id = session.get('user_id')
        if not user_id:
            return redirect(url_for('login'))
        # Get current date and time
        now = datetime.now()
        appointment_date = now.strftime('%Y-%m-%d')
        appointment_time = now.strftime('%H:%M')
        
        # Get user's information
        conn = get_db()
        user = conn.execute('SELECT name, username, date_of_birth, gender FROM users WHERE id = ?', (user_id,)).fetchone()
        conn.close()
        
        if not user:
            flash("User not found. Please log in again.", "error")
            return redirect(url_for('login'))
        
        patient_name = user['name'] or user['username']
        date_of_birth = user['date_of_birth']
        gender = user['gender']
        
        # Calculate age from date of birth
        dob = datetime.strptime(date_of_birth, "%Y-%m-%d").date()
        today = date.today()
        age_years = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
        # Save appointment to database (persists across logins)
        conn = get_db()
        try:
            cursor = conn.execute('''
                INSERT INTO appointments (user_id, date, time, age_years, height, weight)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, appointment_date, appointment_time, age_years, 'N/A', 'N/A'))
            conn.commit()
            appointment_id = cursor.lastrowid
            conn.close()
        except sqlite3.Error as e:
            conn.close()
            flash(f"Error creating appointment: {str(e)}. Please try again.", "error")
            return redirect(url_for('main_page'))
        
        # Store appointment data in session for conversation page
        session['appointment_data'] = {
            'id': appointment_id,
            'date': appointment_date,
            'time': appointment_time,
            'age_years': age_years,
            'height': 'N/A',
            'weight': 'N/A',
            'patient_name': patient_name,
            'gender': gender
        }
        # Initialize conversation history
        session['conversation_history'] = []
        session.modified = True
        
        return redirect(url_for('conversation_page'))
    except Exception as e:
        flash(f"An error occurred: {str(e)}. Please try again.", "error")
        return redirect(url_for('main_page'))

@app.route("/conversation", methods=["GET", "POST"])
def conversation_page():
    """Handle conversation page and chat messages"""
    if 'appointment_data' not in session:
        return redirect(url_for('appointment_page'))
    
    if request.method == "POST":
        # Handle chat message
        user_message = request.json.get('message', '')
        
        if not user_message:
            return jsonify({"error": "No message provided"}), 400
        
        # Get appointment data
        appointment = session.get('appointment_data', {})
        conversation_history = session.get('conversation_history', [])
        
        # Ensure conversation_history is a list
        if not isinstance(conversation_history, list):
            conversation_history = []
            session['conversation_history'] = conversation_history
        
        # Build system prompt for pediatrician
        patient_name = appointment.get('patient_name', 'there')
        age_years = appointment.get('age_years', 0)
        try:
            age_int = int(age_years)
        except (ValueError, TypeError):
            age_int = 0
        
        system_prompt = f"""Act like you are a pediatrician who is meeting someone for an appointment.

The patient information:
- Name: {patient_name}
- Age: {age_years} years
- Height: {appointment.get('height', 'N/A')}
- Weight: {appointment.get('weight', 'N/A')}

IMPORTANT: Have a natural, flowing conversation while ensuring you gather information on all these topics:

CONVERSATION STYLE:
- Be warm, friendly, and conversational - like a real person having a chat
- If the patient asks you questions, answer naturally and genuinely, then continue the conversation
- Depending on if the person you're talking to is the patient or someone else, adjust who you are addressing accordingly.
- Throughout the conversation, address the person by their name when appropriate
- When asking questions, provide helpful examples to clarify what you're asking about

STARTING THE CONVERSATION - YOU MUST FOLLOW THIS EXACT ORDER, DO NOT SKIP ANY STEPS:

STEP 1: Ask for name and relationship
- Ask: "Before we begin, could you tell me your name and your relationship to {patient_name}?" (e.g., parent, guardian, etc.)
- IMPORTANT: If the person says their name is {patient_name} (the same as the patient's name), that means they ARE the patient themselves. In this case, acknowledge that they are the patient and adjust your language accordingly 
- Wait for their response and acknowledge it (e.g., "Nice to meet you, [name]" or "Thank you, [name]")

STEP 2: Ask how they are doing (MANDATORY - DO NOT SKIP THIS - THIS IS THE NEXT QUESTION AFTER NAME/RELATIONSHIP)
- IMMEDIATELY AFTER acknowledging their name/relationship response, you MUST ask: "How is your day going?" (or "How are you feeling today?" if they are the patient)
- DO NOT skip this question and go straight to diet, height, weight, or any other topics
- Wait for their response
- Acknowledge their response naturally (e.g., "That's good to hear" or "I understand" or "I'm sorry to hear that")

STEP 3: Ask for height and weight (MANDATORY - DO NOT SKIP THIS, MUST BE BEFORE ANY OTHER QUESTIONS)
- IMMEDIATELY AFTER acknowledging their response about their day (from Step 2), you MUST ask for height and weight BEFORE asking about diet, toileting, sleep, or any other topics
- DO NOT skip to diet questions or any other topics until you have asked for and received height and weight
- First ask: "What is {patient_name}'s height?" (or "What is your height?" if they are the patient). Ask them to include the unit (cm, inches, feet and inches, etc.). Examples: "Height can be in centimeters (cm), inches (in), or feet and inches (e.g., 5 feet 3 inches)."
- Wait for their response and acknowledge it
- Then ask: "What is {patient_name}'s weight?" (or "What is your weight?" if they are the patient). Ask them to include the unit (kg, pounds, lbs, etc.). Examples: "Weight can be in kilograms (kg) or pounds (lbs)."
- Wait for their response and acknowledge it

STEP 4: Only AFTER completing steps 1, 2, and 3, then you can transition into gathering the other information (diet, toileting, sleep, etc.)

IMPORTANT RULES: 
- Ask ONLY 1-2 questions maximum per message.
- Always provide helpful examples when asking questions to clarify what you mean (e.g., "How much dairy does the child consume? Dairy can include milk, yogurt, cheese, etc.")
- Only ask clarifying follow-up questions if the answer is TRULY unclear, contradictory, or completely unrelated to the question (but still only 1-2 questions at a time)
- Do not skip any questions. If the patient does not answer the question at all (not even a brief answer), ask again/clarify the question.
- FEEDBACK GUIDELINES - GIVE FEEDBACK BEFORE MOVING ON:
  * If the answer indicates a problem or concern, you MUST provide FULL, DETAILED feedback and advice BEFORE moving to the next question. Do not move on until you've given complete guidance. Examples:
    - Not enough fruits/vegetables: Explain recommended daily servings for their age, provide examples, explain benefits
    - Not enough dairy: Explain recommended daily amounts, suggest sources (milk, yogurt, cheese)
    - Constipation: Explain causes, prevention strategies, dietary recommendations (fiber, water), when to seek medical attention
    - Insufficient sleep: Provide age-appropriate sleep recommendations, explain importance, suggest bedtime routines
    - Not enough development: Explain what milestones should be met, suggest activities to support development, when to be concerned
    - Not in school (if school age): Explain importance of school (social development, learning, structure), encourage enrollment
    - Smokers in the home: Explain secondhand smoke risks and consequences, suggest considering quitting
  * Use your medical judgment to provide helpful, evidence-based advice for any concerning answers!
  * If the answer is good/healthy (e.g., adequate sleep, good diet, no concerns), give brief positive feedback (e.g., "That's great!" or "That sounds good!") and then move on to the next question.
- Keep the conversation moving efficiently - once you've given appropriate feedback (brief for good answers, detailed for problems), move on to the next question/topic
- The goal is to gather all the required information so a complete report can be generated, while still maintaining a natural, friendly conversation and providing thorough guidance when there are concerns

TOPICS TO COVER (work these into the conversation naturally, not in a rigid order):

   DIET (Questions 1-3):
   - How many servings of fruits and vegetables does the child eat in a day?
   - How much dairy does the child consume?
   - Does the child brush their teeth twice a day? (Once in the morning and once at night)

   TOILETING (Questions 4-5) - IMPORTANT: DO NOT SKIP THESE QUESTIONS:
   - Question 4: Is the child potty trained? Any concerns with peeing or pooping? (ONLY ask if age is under 3 years old)
   - Question 5: Is there any constipation? (ALWAYS ask this, regardless of age)
   - If constipation is mentioned, provide detailed feedback about causes, prevention, and when to seek medical attention BEFORE moving on

   SLEEP (Questions 6-7):
   - How many hours does the child sleep at night? (Ask about both bedtime and wake time, or total hours)
   - Any concerns with sleep?

   DEVELOPMENT (Question 8):
   - Ask about age-appropriate developmental milestones for {age_years} years old. ASK THESE SEPARATELY (one at a time):
     * First, ask about GROSS MOTOR SKILLS: running, jumping, balance, coordination, climbing, etc.
     * Then, ask about FINE MOTOR SKILLS: writing, drawing, using utensils, buttoning, zipping, etc.
     * Also ask about other developmental milestones appropriate for this age

   SOCIAL (Questions 9-11):
   - Does the child go to school? If yes, what grade? If no, what does the child do instead? (If age < 5, ask about daycare or home care)
     * IMPORTANT: If the child is NOT in school and is of school age, explain the importance of school - social development, learning, structure, routine, etc.
   - Who lives at home? (Examples: parents, siblings, grandparents, other family members, etc.)
   - Are there smokers in the home? (This includes cigarettes, cigars, e-cigarettes, or vaping)

   CONCERNS (Question 12):
   - Do you have any medical concerns today? Any questions for me?
   - When they answer, respond naturally and helpfully as a pediatrician would - provide answers, guidance, and address their concerns
"""
        
    
        # Prepare messages for OpenAI
        messages = [{"role": "system", "content": system_prompt}]
        
        # Add conversation history
        for msg in conversation_history:
            # Ensure each message has the correct format
            if isinstance(msg, dict) and 'role' in msg and 'content' in msg:
                messages.append(msg)
        
        # Add current user message
        messages.append({"role": "user", "content": user_message})
        
        try:
            # Call OpenAI API
            response = client.chat.completions.create(
                model="gpt-4o-mini",  # Using a more accessible model
                messages=messages,
                temperature=0.7,
                max_tokens=500
            )
            
            # Validate response
            if not response or not response.choices or len(response.choices) == 0:
                raise Exception("OpenAI API returned an empty response")
            
            assistant_message = response.choices[0].message.content
            
            if not assistant_message:
                raise Exception("OpenAI API returned a message with no content")
            
            # Update conversation history
            conversation_history.append({"role": "user", "content": user_message})
            conversation_history.append({"role": "assistant", "content": assistant_message})
            session['conversation_history'] = conversation_history
            
            return jsonify({"message": assistant_message})
        
        except Exception as e:
            error_msg = str(e)
            
            # Handle rate limit errors specifically
            if "rate_limit" in error_msg.lower() or "429" in error_msg:
                user_message = "I'm currently experiencing high demand. Please wait about 20 seconds and try again. Thank you for your patience!"
            elif "api key" in error_msg.lower() or "authentication" in error_msg.lower():
                user_message = "There was an authentication issue. Please contact support if this persists."
            else:
                # For other errors, show a generic but helpful message
                user_message = "Sorry, I encountered an error processing your message. Please try again in a moment."
            
            return jsonify({
                "error": error_msg, 
                "message": user_message
            }), 500
    
    # GET request - show conversation page
    appointment = session.get('appointment_data', {})
    return render_template("conversation.html", appointment=appointment)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Handle login GET and POST requests"""
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        
        if not username or not password:
            flash("Please provide both username and password", "error")
            return render_template("login.html")
        
        conn = get_db()
        user = conn.execute(
            'SELECT * FROM users WHERE LOWER(username) = LOWER(?)', (username,)
        ).fetchone()
        conn.close()
        
        if user and check_password_hash(user['password_hash'], password):
            # Login successful - store all user info in session
            session.permanent = True  # Make session persist across browser restarts
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['name'] = user['name']
            session['role'] = user['role']
            session['admin_group'] = user['admin_group']
            session['patient_group'] = user['patient_group']
            return redirect(url_for('main_page'))
        else:
            flash("Invalid username or password", "error")
            return render_template("login.html")
    
    return render_template("login.html")

@app.route("/signup", methods=["GET", "POST"])
def signup():
    """Handle signup GET and POST requests"""
    if request.method == "POST":
        first_name = request.form.get("first_name", "").strip()
        last_name = request.form.get("last_name", "").strip()
        username = request.form.get("username")
        password = request.form.get("password")
        role = request.form.get("role")
        admin_group = request.form.get("admin_group", "").strip()
        patient_group = request.form.get("patient_group", "").strip()
        date_of_birth = request.form.get("date_of_birth", "").strip()
        gender = request.form.get("gender", "").strip()
        
        # Combine first and last name
        full_name = f"{first_name} {last_name}".strip()
        
        # Validation
        if not first_name or not last_name or not username or not password or not role or not date_of_birth or not gender:
            return render_template("signup.html", error="Please fill in all required fields")
        
        # Validate gender
        if gender not in ['male', 'female']:
            return render_template("signup.html", error="Please select a valid gender")
        
        # Validate and calculate age from date of birth
        try:
            dob = datetime.strptime(date_of_birth, "%Y-%m-%d").date()
            today = date.today()
            age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
            if age < 0:
                return render_template("signup.html", error="Date of birth cannot be in the future")
            # Only restrict age for patients (must be 18 and under)
            # Admins can be any age
            if role == "patient" and age > 18:
                return render_template("signup.html", error="This service is only for pediatric appointments (18 years and under). Please contact your healthcare provider for adult services.")
        except ValueError:
            return render_template("signup.html", error="Please enter a valid date of birth")
        
        if role == "admin" and not admin_group:
            return render_template("signup.html", error="Please enter the name of the group you are admining")
        
        # Check if username already exists (case-insensitive check)
        conn = get_db()
        existing_user = conn.execute(
            'SELECT * FROM users WHERE LOWER(username) = LOWER(?)', (username,)
        ).fetchone()
        
        if existing_user:
            conn.close()
            return render_template("signup.html", error="Username already exists. Please choose a different username.")
        
        # Hash password
        password_hash = generate_password_hash(password)
        
        # Insert new user
        try:
            conn.execute(
                '''INSERT INTO users (username, password_hash, role, admin_group, patient_group, name, date_of_birth, gender)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                (username, password_hash, role, admin_group if role == "admin" else None, 
                 patient_group if role == "patient" else None, full_name, date_of_birth, gender)
            )
            conn.commit()
            conn.close()
            
            # Auto-login after signup - store all user info in session
            conn = get_db()
            user = conn.execute(
                'SELECT * FROM users WHERE username = ?', (username,)
            ).fetchone()
            conn.close()
            
            session.permanent = True  # Make session persist across browser restarts
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['name'] = user['name']
            session['role'] = user['role']
            session['admin_group'] = user['admin_group']
            session['patient_group'] = user['patient_group']
            
            return redirect(url_for('main_page'))
        except sqlite3.IntegrityError:
            # Username already exists (caught by database UNIQUE constraint)
            conn.close()
            return render_template("signup.html", error="Username already exists. Please choose a different username.")
        except sqlite3.Error as e:
            conn.close()
            return render_template("signup.html", error="An error occurred. Please try again.")
    
    return render_template("signup.html")

@app.route("/logout")
def logout():
    """Logout user"""
    session.clear()
    return redirect(url_for('cover_page'))


if __name__ == "__main__":
    # Initialize database on startup
    init_db()
    app.run(debug=True, port=5001)

