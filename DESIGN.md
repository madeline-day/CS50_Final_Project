# PediaReach — Design Document

## Overview

PediaReach is an AI-powered pediatric virtual appointment system built using Flask, SQLite, and the OpenAI API. While the README covers user-facing instructions, this document provides a technical overview of how the system works behind the scenes, the architectural decisions made, and the reasoning behind key design choices.

The goal was to create a system that feels like a real pediatric intake appointment while remaining simple, secure, scalable, and maintainable. The core challenge was designing a system that feels natural and conversational while still collecting structured medical data that can be reliably extracted and stored.

## System Architecture

PediaReach follows a classic Model–View–Controller (MVC) pattern implemented through Flask:

- **Model**: SQLite database storing users, appointments, and generated medical summaries
- **View**: Jinja2 templates responsible for rendering HTML UI
- **Controller**: Flask routes handle authentication, AI conversations, admin dashboard, and report generation

### High-Level Flow

```
User → Flask Route → AI Conversation Engine → Store Data → Generate Report → Display to User
```

The application follows a three-tier architecture: frontend (HTML/CSS/JavaScript), backend (Flask/Python), and data layer (SQLite). The real innovation here is integrating OpenAI's GPT-4o-mini model to power the conversational interface. Instead of building a rigid form or decision tree, the AI acts as a flexible pediatrician that can adapt to different conversation styles, handle follow-up questions naturally, and provide personalized feedback—all while ensuring we collect the data we need.

## Key Components

### Authentication System

Manages login/signup using Werkzeug for secure password hashing. Passwords are never stored in plain text—they're hashed using `generate_password_hash()` and verified using `check_password_hash()`. The session stores the user's ID and role after successful authentication, which is used throughout the application for access control.

### AI Conversation Engine

The heart of the application is the conversation system powered by OpenAI's API. This was the most challenging part to get right because we need the AI to be conversational and flexible while still following a structured data collection process.

The conversation happens in the `/conversation` route, which handles POST requests containing user messages. Each request builds a message history that includes a system prompt (instructions for the AI) and the conversation history stored in the Flask session. The system prompt is where all the magic happens—it's a detailed set of instructions that tells the AI how to behave.

I structured the system prompt to enforce a specific conversation order: first ask for name/relationship, then "How is your day going?", then height and weight, and only then move into the health assessment topics. This was necessary because early versions of the AI would skip straight to diet questions, which felt unnatural. The prompt explicitly marks these initial steps as "MANDATORY - DO NOT SKIP" to prevent this.

The prompt also includes detailed instructions about asking only 1-2 questions at a time (to avoid overwhelming users), providing examples when asking questions (e.g., "Dairy can include milk, yogurt, cheese, etc."), and giving appropriate feedback. For concerning answers (insufficient sleep, poor diet, smokers in the home), the AI is instructed to provide full, detailed feedback before moving on. For positive answers, it should give brief acknowledgment and keep moving.

The conversation history is stored in the Flask session as a list of message dictionaries with `role` ("user" or "assistant") and `content` (the message text). This allows the AI to maintain context across multiple exchanges. Each time a user sends a message, we append it to the history, call the OpenAI API with the full history, get the response, append that to the history, and save it back to the session.

### Report Generator

After the conversation ends, the `/extract-diet` route (despite its name, it extracts everything) processes the entire conversation history to generate the structured report. This is where we use the AI's ability to understand and summarize text.

The extraction process uses a separate OpenAI API call with a detailed prompt that maps specific questions from the conversation to report sections. For example, questions about fruits/vegetables, dairy, and teeth brushing all map to the "Diet" section. The prompt instructs the AI to extract bullet-point summaries for each category and also extract any recommendations or advice the pediatrician gave.

The extraction prompt uses JSON response format (`response_format={"type": "json_object"}`) to ensure we get structured data back. The AI returns a JSON object with keys like `diet`, `toileting`, `sleep`, etc., each containing a string with bullet points. This makes it easy to parse and store in the database.

Height and weight extraction happens first, because we need these values to calculate growth percentiles. Once we have height, weight, age, and gender, we make another AI call to calculate CDC growth percentiles. The prompt asks for "BMI, BMI Percentile, Height Percentile, and Weight Percentile" using pediatric growth charts, and the AI returns a formatted string like "BMI: 18.5, BMI Percentile: 45th, Height Percentile: 60th, Weight Percentile: 50th".

All of this extracted data is then saved to the `appointments` table in a single UPDATE statement, linking it to the appointment record created at the start of the conversation.

### Admin Dashboard

Filters and displays all patients linked to a specific admin group. The `/people` route filters users to show only patients whose `patient_group` matches the logged-in admin's `admin_group`. This creates a simple group-based access system without needing a separate groups table. When an admin clicks "View Reports" next to a patient, they're taken to `/reports/<user_id>`, which verifies that the admin's group matches the patient's group before displaying the reports.

## Design Decisions

### 1. Why Flask?

Flask was chosen because:

- **Lightweight and ideal for small/medium web apps**: We don't need the full feature set of Django for this project
- **Easy to integrate with SQLite**: Flask's simplicity makes database operations straightforward
- **Clear routing structure**: Each route is a Python function, making the code easy to follow
- **Minimal boilerplate compared to Django**: Faster to get started and easier to understand
- **Perfect fit for CS50 projects**: Gives full control of the application logic without requiring complex frameworks

Flask gives us fine-grained control over routing and session management, which is exactly what we need for this conversational interface.

### 2. Why SQLite3?

SQLite was selected because:

- **Zero configuration**: No separate database server to set up or maintain
- **Automatically creates the database file**: The `init_db()` function handles everything
- **Perfect for local or small-scale use**: Ideal for a CS50 project that might be deployed locally
- **Works smoothly with Flask**: The `sqlite3` module is built into Python
- **Persistent storage without requiring a server setup**: The database file lives alongside the application code

Because PediaReach deals with structured appointment data, SQLite provides exactly what is needed. The database schema evolved organically as features were added, but the core structure is straightforward. There are two main tables: `users` and `appointments`, with a one-to-many relationship (one user can have many appointments).

The `users` table stores authentication credentials (username, password_hash), role information (patient vs. admin), and demographic data (name, date_of_birth, gender). The `admin_group` and `patient_group` fields create a linking system: admins have an `admin_group` name, and patients have a `patient_group` name that matches. This allows admins to see only patients in their assigned group without needing a separate junction table.

The `appointments` table stores structured summaries of each health category (diet, toileting, sleep, development, social, concerns) separately. I also added recommendation columns (`diet_recommendations`, `sleep_recommendations`, etc.) to store the AI's advice separately from the patient's answers. This separation makes it easy to display them distinctly in the reports.

One design decision I made early on was to handle database migrations gracefully. Since SQLite doesn't support dropping columns easily, I used `ALTER TABLE ... ADD COLUMN` statements wrapped in try-except blocks. This allows the database to evolve without breaking existing installations. The `init_db()` function runs on every startup and safely adds any missing columns.

### 3. Why GPT-4o-mini?

GPT-4o-mini was ideal due to:

- **High conversational quality**: The model can maintain natural, flowing conversations that feel like talking to a real pediatrician
- **Low latency**: Fast response times keep the conversation feeling real-time
- **Affordable usage**: Much cheaper than GPT-4 while still providing excellent results
- **Reliable structure in question-answer flows**: When given clear instructions, it follows the conversation structure consistently
- **Capable of tracking pediatric conversation context**: The model understands medical terminology and can provide appropriate feedback

The model is capable of tracking pediatric conversation context and generating responses based on collected data. However, getting it to follow the exact conversation flow required extensive prompt engineering.

### 4. Appointment Structure as a Fixed Question Set

Rather than allowing the AI to freestyle conversations, a structured question flow ensures:

- **All required pediatric domains get proper coverage**: Diet, toileting, sleep, development, social, and concerns are all addressed
- **Reports remain consistent**: Every appointment covers the same topics, making reports comparable
- **Data integrity is maintained**: We know exactly what data we're collecting
- **Easier debugging**: When something goes wrong, we can trace it to a specific question
- **Predictable behavior for admins reviewing reports**: Admins know what to expect in each report

The AI still speaks naturally, but the logic ensures every required question is answered. The system prompt maps specific questions to report sections, so even if the conversation flows naturally, the data extraction process knows where to find each piece of information.

### 5. Growth Percentile Calculations

Percentiles are computed using CDC gender-specific pediatric growth charts via the AI. The design rationale:

- **Provides clinically relevant metrics**: BMI, height, and weight percentiles are standard in pediatric care
- **Enhances the value of appointment reports**: Growth tracking is a core part of pediatric appointments
- **Requires minimal additional computation**: The AI handles unit conversions and calculations
- **Flexible unit handling**: The AI can process height/weight in various formats (cm, inches, kg, pounds)

I chose to use the AI for this calculation rather than implementing CDC charts directly because the AI can handle various unit formats and provide formatted output. For a production medical application, I would probably implement the actual CDC chart calculations for greater precision, but for this project, the AI approach works well.

Because DOB and gender cannot be edited after signup, percentiles remain accurate. These fields are locked to maintain data reliability—if someone could change their date of birth, all their historical growth percentiles would become invalid.

## Data Flow and Report Generation

### Conversation Phase

1. User begins an appointment by clicking the "Appointment" tab
2. The `/appointment` route creates a new appointment record in the database and stores appointment metadata in the Flask session
3. User is redirected to the conversation page
4. AI asks structured questions following the system prompt
5. User responses are stored temporarily in the session's conversation history
6. After all categories are complete, the user clicks "End Appointment"

### Report Phase

1. The `/extract-diet` route is called, which processes the entire conversation history
2. Data is compiled into categories (diet, sleep, social, etc.) using AI extraction
3. Height and weight are extracted first
4. Growth percentiles are calculated using a separate AI call with CDC chart data
5. A formatted summary is saved in the appointments table
6. User and admins can view reports at any time through the `/reports` route

The extraction process uses a separate OpenAI API call with a detailed prompt that maps specific questions from the conversation to report sections. The prompt instructs the AI to extract bullet-point summaries for each category and also extract any recommendations or advice the pediatrician gave.

## Session Management and State

Flask sessions are crucial to this application because we need to maintain conversation state across multiple HTTP requests. When a user clicks "Appointment", the `/appointment` route creates a new appointment record in the database and stores appointment metadata (id, date, time, age, patient name, gender) in `session['appointment_data']`. It also initializes `session['conversation_history']` as an empty list.

The conversation page loads this data from the session and displays it. Each chat message is a POST request that reads the conversation history from the session, appends the new exchange, and saves it back. This stateless HTTP approach works well because Flask sessions are stored server-side (using the secret key) and persist across requests.

One design decision I made was to store the appointment ID in the session rather than passing it as a URL parameter. This keeps the URLs clean and prevents users from accidentally accessing other people's appointments by manipulating URLs. The session also stores the user's role, which is used throughout the application for role-based access control.

## Role-Based Access Control

The application has two user roles: patients and admins. This is implemented simply with a `role` field in the `users` table. The navigation tabs are conditionally rendered in `layout.html` using Jinja2 templates: admins see "main" and "people" tabs, while patients see "main", "appointment", and "reports" tabs.

The `/people` route filters users to show only patients whose `patient_group` matches the logged-in admin's `admin_group`. This creates a simple group-based access system without needing a separate groups table. When an admin clicks "View Reports" next to a patient, they're taken to `/reports/<user_id>`, which verifies that the admin's group matches the patient's group before displaying the reports.

The `/reports` route handles both cases: if no `view_user_id` is provided, it shows the logged-in user's own reports. If a `view_user_id` is provided (and the user is an admin with matching group), it shows that patient's reports. This dual-purpose route keeps the code DRY (Don't Repeat Yourself).

## Security Considerations

- **Passwords are hashed using Werkzeug**: Passwords are never stored in plain text. The `generate_password_hash()` function creates a secure hash that can't be reversed.
- **No sensitive medical data is transmitted publicly**: All data transmission happens over the local Flask server (or would be HTTPS in production).
- **Admin access is role-restricted**: Only users with `role='admin'` can access admin features.
- **Users can only view their own reports**: The `/reports` route checks that the logged-in user matches the requested user, unless the user is an admin viewing a patient in their group.
- **Admins can only view patients in their assigned group**: The group matching system ensures admins can't access patients outside their assigned group.

The session secret key is configurable via environment variable (`FLASK_SECRET_KEY`), though for development it defaults to a fixed value. In production, this should be set to a secure random string.

## Frontend-Backend Interaction

The frontend uses a mix of server-side rendering (Jinja2 templates) and client-side JavaScript for dynamic interactions. The conversation page is a good example: the page structure and initial appointment data are rendered server-side, but the chat interface uses JavaScript to send POST requests to `/conversation` and update the chat display without page refreshes.

The chat messages are sent as JSON (`request.json.get('message')`) and responses come back as JSON (`jsonify({"message": assistant_message})`). This AJAX-style interaction creates a smooth, real-time conversation experience. Error handling is built into the JavaScript to display user-friendly messages if the API call fails (e.g., rate limits, authentication errors).

The reports page uses server-side rendering exclusively, pulling appointment data from the database and displaying it in a structured format. Each report section (Diet, Toileting, Sleep, etc.) is displayed as a card with the patient's answers and the pediatrician's recommendations side-by-side. The growth percentile information is displayed prominently at the top in a full-width section.

## Challenges and How They Were Solved

### 1. Maintaining Conversation State

**Challenge**: AI models are stateless, but appointments require memory across multiple exchanges.

**Solution**: Flask session storage combined with prompt engineering ensures the AI knows what questions have been asked, what data is still needed, and when the appointment is complete. The conversation history is passed to the AI with each request, giving it full context of the conversation so far.

### 2. Handling Age-Specific Questions

**Challenge**: Potty training questions only apply to children under 3 years. We can't ask a 10-year-old about potty training.

**Solution**: Conditional logic in the system prompt ensures age-appropriate questioning. The prompt explicitly states "ONLY ask if age is under 3 years old" for potty training questions, and the AI follows this instruction.

### 3. Ensuring Data Completeness

**Challenge**: The AI might skip a question or respond unpredictably, leaving gaps in the data.

**Solution**: The system prompt is very explicit about which questions must be asked. The prompt maps each question to a report section, and the extraction process checks for completeness. If a category is missing, it's noted in the report. Additionally, the prompt instructs the AI not to skip questions and to ask again if an answer is unclear.

### 4. Integrating Percentile Calculations

**Challenge**: CDC percentiles are non-linear and gender-specific, requiring complex calculations.

**Solution**: Rather than implementing the full CDC chart calculations (which would require extensive lookup tables), I use the AI to calculate percentiles. The AI has knowledge of CDC growth charts and can provide accurate percentile calculations. The prompt asks for "BMI, BMI Percentile, Height Percentile, and Weight Percentile using pediatric growth charts from CDC," and the AI returns formatted results.

### 5. Preventing Profile Changes That Break Medical Accuracy

**Challenge**: DOB and gender affect percentiles. If someone could change these after creating appointments, all historical data would become invalid.

**Solution**: Date of birth and gender fields are locked after initial signup. The edit profile page explicitly prevents editing these fields, maintaining data reliability across all historical appointments.

### 6. AI Not Following Conversation Order

**Challenge**: Early versions of the AI would skip the initial questions (name/relationship, "How is your day going?", height/weight) and jump straight to diet questions.

**Solution**: The system prompt was refined with explicit, numbered steps marked as "MANDATORY - DO NOT SKIP". The prompt now has a clear "STARTING THE CONVERSATION" section that enforces the exact order, and the AI consistently follows it.

### 7. AI Re-asking Questions Unnecessarily

**Challenge**: The AI would sometimes ask for clarification on questions like "Who lives at home?" even when the answer was reasonable.

**Solution**: The prompt now explicitly instructs the AI to "accept any reasonable answer" for certain questions and move on. This prevents the conversation from getting stuck in clarification loops.

## Design Trade-offs

One major design decision was to use the AI for both conversation and data extraction rather than building a structured form. The trade-off is that we get a much more natural, flexible user experience, but we have less control over exactly what data is collected. The extraction process can sometimes miss details if the conversation goes off-track, though the detailed system prompt helps mitigate this.

I chose to store conversation history in the session rather than the database to keep the database schema simpler and avoid storing potentially long conversation transcripts. The trade-off is that if a user's session expires, they lose their conversation progress. However, once the appointment is completed and the data is extracted, it's saved to the database permanently.

Another decision was to calculate growth percentiles using the AI rather than implementing CDC charts directly. This is less precise but more flexible (handles various units, provides formatted output) and was faster to implement. For a production medical application, I would probably implement the actual CDC chart calculations, but for this project, the AI approach works well.

The automatic appointment creation (no user input for date/time) simplifies the user experience but means we can't schedule future appointments. This was an intentional choice to focus on the conversational aspect rather than appointment scheduling features.

Finally, I hardcoded the OpenAI API key directly in the code for simplicity during development. In production, this should definitely be stored as an environment variable or in a secure configuration file, but for a CS50 project, this approach is acceptable.

## Future Improvements

- **Add video appointment features**: Integrate video calling capabilities for face-to-face virtual appointments
- **Integration with real pediatric EHR systems**: Connect to existing electronic health record systems used by healthcare providers
- **More advanced developmental screening**: Implement standardized developmental screening tools (e.g., Ages & Stages Questionnaire)
- **Multi-language support**: Allow the AI to conduct conversations in multiple languages
- **Adding charts for long-term growth tracking**: Visualize growth trends over time with interactive charts
- **Deploying on a full production server with PostgreSQL**: Move from SQLite to PostgreSQL for better scalability and concurrent access
- **Implement actual CDC growth chart calculations**: Replace AI-based percentile calculations with precise CDC chart lookups for medical accuracy
- **Conversation history storage**: Store full conversation transcripts in the database for audit trails and review
- **Scheduled appointments**: Allow users to schedule future appointments rather than only creating them on-demand

## Conclusion

PediaReach demonstrates how modern AI APIs can be integrated into traditional web applications to create novel user experiences. The key was finding the right balance between AI flexibility and structured data collection, which required careful prompt engineering and a robust extraction process. The Flask + SQLite + OpenAI stack proved to be a powerful combination for building this type of application quickly and effectively.

The system successfully bridges the gap between natural conversation and structured medical data collection, creating an experience that feels like talking to a real pediatrician while still generating comprehensive, standardized reports that can be used for medical record-keeping and long-term health tracking.
