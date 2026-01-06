# PediaReach - AI-Powered Pediatric Appointment System

Welcome to PediaReach! This is a web application designed to help parents and guardians conduct virtual pediatric appointments using an AI-powered pediatrician. The system guides users through a comprehensive health assessment, collects important information about diet, sleep, development, and more, and generates detailed reports that can be reviewed later.

## What is PediaReach?

PediaReach is a Flask-based web application that simulates pediatric appointments through conversational AI. Instead of filling out lengthy forms, users have a natural conversation with an AI pediatrician that asks relevant questions based on the patient's age and needs. The system is designed for patients 18 years and under, with special admin accounts available for healthcare providers who can view multiple patients' reports.

## Features

- **User Authentication**: Secure signup and login system with role-based access (patient or admin)
- **AI-Powered Conversations**: Natural, flowing conversations with an AI pediatrician powered by OpenAI's GPT-4o-mini
- **Comprehensive Health Assessment**: Covers diet, toileting, sleep, development/behavior, social factors, and medical concerns
- **Detailed Reports**: Automatically generated appointment summaries with recommendations for each health category
- **Growth Percentiles**: Calculates BMI, BMI percentile, height percentile, and weight percentile using CDC pediatric growth charts
- **Admin Dashboard**: Healthcare providers can view and manage reports for all patients in their assigned group
- **Persistent Data**: All appointment data is saved to a SQLite database and persists across sessions

## Getting Started

### Prerequisites

Before you begin, make sure you have the following installed on your system:

- **Python 3.7 or higher** (check with `python3 --version`)
- **pip** (Python package installer)
- **Flask** (will be installed via requirements)
- **An OpenAI API key** (get one at https://platform.openai.com/)

### Installation

1. **Clone or download this project** to your local machine.

2. **Navigate to the project directory** in your terminal:
   ```bash
   cd "CS50 Final Project"
   ```

3. **Install required Python packages**:
   ```bash
   pip3 install flask werkzeug openai
   ```
   
   Or if you have a requirements.txt file:
   ```bash
   pip3 install -r requirements.txt
   ```

4. **Set up your OpenAI API key** as an environment variable. You have two options:

   **Option A: Set it temporarily (for this terminal session only)**
   ```bash
   export OPENAI_API_KEY="your-api-key-here"
   ```

   **Option B: Set it permanently (recommended)**
   
   On macOS/Linux, add this line to your `~/.zshrc` or `~/.bashrc` file:
   ```bash
   export OPENAI_API_KEY="your-api-key-here"
   ```
   
   Then reload your shell:
   ```bash
   source ~/.zshrc
   ```

   Replace `"your-api-key-here"` with your actual OpenAI API key (it should start with `sk-proj-`).

5. **Set up Flask secret key** (optional, but recommended for production):
   ```bash
   export FLASK_SECRET_KEY="your-secret-key-here"
   ```
   
   If you don't set this, the app will use a default development key. For production, use a secure random string.

### Running the Application

1. **Make sure you're in the project directory**:
   ```bash
   cd "CS50 Final Project"
   ```

2. **Start the Flask development server**:
   ```bash
   python3 -m flask run --debug
   ```
   
   Or if you prefer to specify the host and port explicitly:
   ```bash
   python3 -m flask run --debug --host=127.0.0.1 --port=5000
   ```

3. **Open your web browser** and navigate to:
   ```
   http://127.0.0.1:5000
   ```
   
   You should see the PediaReach homepage!

4. **To stop the server**, press `Ctrl+C` in the terminal where Flask is running.

## How to Use PediaReach

### For Patients (First-Time Users)

1. **Sign Up**: Click "Sign Up" in the top right corner and fill out the registration form:
   - Enter your first name, last name, and choose a username
   - Create a password
   - Select "patient" as your role
   - Enter your date of birth (must be 18 years or younger for patients)
   - Select your gender (male or female)
   - Enter your patient group name (this links you to an admin/healthcare provider)
   - **Important**: Date of birth and gender cannot be changed after signup

2. **Start an Appointment**: 
   - Click the "appointment" tab in the navigation
   - You'll be automatically redirected to a conversation page
   - The AI pediatrician will greet you and ask for your name and relationship to the patient

3. **Have the Conversation**:
   - Answer the pediatrician's questions naturally
   - The conversation will cover:
     - How your day is going
     - Height and weight
     - Diet (fruits, vegetables, dairy, teeth brushing)
     - Toileting (potty training, constipation)
     - Sleep (hours, concerns)
     - Development/Behavior (gross motor, fine motor, milestones)
     - Social (school, who lives at home, smokers)
     - Medical concerns and questions
   - The AI will provide helpful feedback and recommendations as you go

4. **End the Appointment**:
   - Click the "End Appointment" button when finished
   - Confirm that you want to end the appointment
   - You'll be redirected to the reports page

5. **View Your Reports**:
   - Click the "reports" tab to see all your past appointments
   - Each report shows:
     - Appointment date and time
     - Patient age, height, and weight
     - Growth percentile information (BMI, percentiles)
     - Detailed summaries for each health category
     - Recommendations for each section

### For Admins (Healthcare Providers)

1. **Sign Up as Admin**:
   - Follow the same signup process, but select "admin" as your role
   - Enter your admin group name (this should match the patient group names of patients you want to manage)
   - Admins can be any age (not restricted to 18 and under)

2. **View Your Patients**:
   - Click the "people" tab to see all patients in your admin group
   - The table shows patient names, usernames, roles, dates of birth, and join dates

3. **View Patient Reports**:
   - Click "View Reports" next to any patient's name
   - You'll see all of that patient's appointment history and summaries
   - This allows you to track patient progress over time

### General Tips

- **Be Natural**: The AI is designed to have a natural conversation. Feel free to ask questions or provide additional context.
- **Complete the Conversation**: Make sure to answer all the questions so your report is complete. The AI will guide you through everything.
- **Review Your Reports**: Check your reports page regularly to see summaries and recommendations from past appointments.
- **Profile Management**: Click your profile icon (top right) to view and edit your profile information (except date of birth and gender).

## Project Structure

```
CS50 Final Project/
├── app.py                 # Main Flask application file
├── users.db               # SQLite database (created automatically)
├── README.md              # This file!
├── templates/             # HTML templates
│   ├── layout.html        # Base template with navigation
│   ├── main.html          # Homepage
│   ├── login.html         # Login page
│   ├── signup.html        # Signup page
│   ├── conversation.html  # Chat interface for appointments
│   ├── reports.html       # Appointment history and summaries
│   ├── account.html       # User profile page
│   ├── edit_profile.html  # Edit profile page
│   ├── people.html        # Admin view of patients
│   └── cover.html         # Landing page (redirects to main)
└── static/                # Static files (CSS, images, etc.)
    ├── logo.png           # PediaReach logo
    └── main.png           # Homepage banner image
```

## Technologies Used

- **Flask**: Python web framework for handling routes and rendering templates
- **SQLite3**: Lightweight database for storing user accounts and appointment data
- **OpenAI API**: GPT-4o-mini model for AI-powered conversations
- **Werkzeug**: Password hashing and security utilities
- **Jinja2**: Template engine for dynamic HTML generation
- **HTML/CSS/JavaScript**: Frontend for user interface and chat functionality

## Database Schema

The application uses two main tables:

**users**: Stores user account information
- id, username, password_hash, role, admin_group, patient_group, name, date_of_birth, gender, created_at

**appointments**: Stores appointment data and summaries
- id, user_id, date, time, age_years, height, weight, concerns
- diet_info, toileting_info, sleep_info, development_behavior_info, social_info, extracted_concerns
- diet_recommendations, toileting_recommendations, sleep_recommendations, development_behavior_recommendations, social_recommendations, concerns_recommendations
- growth_percentile_info, created_at

The database is automatically initialized when you first run the application.

## Important Notes

- **API Key Security**: Never commit your OpenAI API key to version control. Always use environment variables.
- **Session Persistence**: User sessions persist for 30 days. You'll stay logged in even after closing your browser.
- **Data Privacy**: All data is stored locally in the SQLite database file. Make sure to back up `users.db` if you need to preserve data.
- **Rate Limits**: The free tier of OpenAI API has rate limits (3 requests per minute). If you hit a rate limit, wait about 20 seconds and try again.
- **Age Restrictions**: Patients must be 18 years or younger. Admins can be any age.
- **Group System**: Patients and admins are linked through matching `patient_group` and `admin_group` names. Make sure these match when creating accounts.

## Troubleshooting

**"OpenAI API Error" or "Authentication issue"**
- Make sure your `OPENAI_API_KEY` environment variable is set correctly
- Check that your API key is valid and has credits available
- Try restarting your terminal and Flask server

**"Rate limit" error**
- You've made too many requests too quickly. Wait about 20 seconds and try again.
- Consider upgrading your OpenAI plan if you need higher rate limits

**Database errors**
- If you see database errors, the database file might be corrupted. You can delete `users.db` and restart the app (this will delete all data).
- Make sure you have write permissions in the project directory

**Port already in use**
- Another process might be using port 5000. Try a different port:
  ```bash
  python3 -m flask run --debug --port=5001
  ```

**Can't see appointments or reports**
- Make sure you're logged in with the correct account
- Check that appointments were actually created (click the appointment tab)
- Verify that you clicked "End Appointment" to save the data

## Future Enhancements

Potential improvements for future versions:
- Email notifications for appointment summaries
- Export reports as PDF
- Multiple language support
- Integration with electronic health records (EHR) systems
- Mobile app version
- Video call integration for virtual appointments

## Contact

If you have questions about this project, please email: pediareach@gmail.com

---

**Note for CS50 Staff**: This project was developed as a final project for CS50. All code is original work, with the exception of standard Flask, SQLite, and OpenAI API usage following their official documentation. The application is fully functional and ready for testing. Simply follow the installation and running instructions above to get started!

