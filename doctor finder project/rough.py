from flask import Flask, render_template, request, redirect, url_for, session, flash
from pymongo import MongoClient
from bson import ObjectId
from werkzeug.utils import secure_filename
import os
from datetime import datetime
from bson.errors import InvalidId
# from mongoengine import ObjectId
# from models import Appoint
from mongoengine import Document, StringField, DateTimeField, ReferenceField, ObjectIdField, EnumField, connect, EmailField, FloatField, IntField

connect(
        db='doctor_finder',  # Database name
        host='mongodb://localhost:27017/doctor_finder',  # MongoDB URI
        alias='default'  # Default alias for this connection
    )


app = Flask(__name__)
app.secret_key = 'your_secret_key'

# MongoDB setup
client = MongoClient('mongodb://localhost:27017')
db = client['doctor_finder']
doctors = db['doctors']
patients = db['patients']
appoint = db['appointments']
contact_msg = db['contact']



class Doctor(Document):
    """
    MongoEngine Document representing a Doctor.
    """
    doctor_name = StringField(required=True, max_length=100)
    specialization = StringField(required=True, max_length=100)
    email = EmailField(required=True, unique=True)  # Email field with unique constraint
    password = StringField(required=True, min_length=8)
    contact_number = StringField(required=True, max_length=15)
    clinic_address = StringField(required=True)
    experience = IntField(required=True, min_value=0)  # Integer field for years of experience
    consultation_fee = FloatField(required=True, min_value=0.0)  # Float for consultation fee
    profile_image = StringField(default="img/default_doctor.png")  # Path to the profile image

    meta = {'collection': 'doctors'}  # Explicitly define collection name if needed

class Appoint(Document):
    patient_id = ObjectIdField(required=True)
    doctor_id = ObjectIdField(required=True)
    patient_name = StringField(required=True)
    doctor_name = StringField(required=True)
    doctor_specialization = StringField()
    appointment_date = DateTimeField()
    appointment_status = StringField(default="pending")

    meta = {'collection': 'appointments'}
    
# Routes
def validate_appointment(appointment_id, doctor_id):
    """
    Helper function to validate if an appointment exists and belongs to the doctor.
    """
    try:
        # Ensure both appointment ID and doctor ID match
        appointment = appoint.find_one({"_id": ObjectId(appointment_id), "doctor_id": ObjectId(doctor_id)})
        return appointment
    except Exception as e:
        print(f"Error during appointment validation: {e}")
        return None


@app.route("/")
def home():
    # Display all available doctors
    all_doctors = doctors.find()
    return render_template("home.html", doctors=all_doctors)

@app.route("/about")
def about():
    return render_template('about.html')

@app.route("/doctor_profile/<doctor_id>")
def doctor_profile(doctor_id):
    try:
        # Attempt to convert doctor_id to ObjectId
        doctor = doctors.find_one({"_id": ObjectId(doctor_id)})
    except Exception as e:
        flash("Invalid doctor ID provided.", "error")
        return redirect(url_for('home'))
    
    if doctor:
        return render_template("doctor_profile.html", doctor=doctor)
    else:
        flash("Doctor not found", "error")
        return redirect(url_for('home'))

@app.route("/patient_home")
def patient_home():
    if 'patient_id' in session:
        patient = patients.find_one({'username': session['patient_username']})
        if patient:
            # Fetch available doctors
            appointments_list = appoint.find({'patient_id': session['patient_id']})
            doctors_list = doctors.find()
            return render_template(
                'patient_home.html',
                appointments=appointments_list,
                doctors=doctors_list,
                profile_image=patient.get('profile_image', 'img/default_patient.png'),
                view_appointment_url=url_for('appointment_detail', patient_id=session['patient_id'])  # Correct usage
            )
    else:
        flash("You need to be logged in to access this page", "error")
        return redirect(url_for('patient_login'))


UPLOAD_FOLDER = 'static/images/'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route("/doctor_register", methods=['GET', 'POST'])
def doctor_register():
    if request.method == 'POST':
        # Fetch form data
        doctor_name = request.form.get('doctor_name')
        specialization = request.form.get('specialization')
        email = request.form.get('email')
        password = request.form.get('password')
        contact_number = request.form.get('contact_number')
        clinic_address = request.form.get('clinic_address')
        experience = request.form.get('experience')
        consultation_fee = request.form.get('consultation_fee')

        # Profile image upload
        image_file = request.files.get('image')  # Use `.get()` to avoid KeyError
        image_filename = 'img/default_doctor.png'  # Default image

        if image_file and allowed_file(image_file.filename):
            filename = secure_filename(image_file.filename)
            upload_folder = os.path.join(app.static_folder, 'img/doctors')
            os.makedirs(upload_folder, exist_ok=True)  # Create directory if not exists
            file_path = os.path.join(upload_folder, filename)
            image_file.save(file_path)
            image_filename = f'img/doctors/{filename}'  # Relative path to static folder

        # Check if email already exists
        if doctors.find_one({'email': email}):
            flash('Email already exists', 'error')
            return render_template('doctor_register.html')

        # Insert doctor details into the database
        doctors.insert_one({
            'doctor_name': doctor_name,
            'specialization': specialization,
            'email': email,
            'password': password,
            'contact_number': contact_number,
            'clinic_address': clinic_address,
            'experience': experience,
            'consultation_fee': consultation_fee,
            'profile_image': image_filename  # Save relative path in MongoDB
        })

        flash("Doctor registered successfully", "success")
        return redirect(url_for('home'))

    return render_template('doctor_register.html')


@app.route("/doctor_home")
@app.route("/doctor_home/<string:doctor_id>")
def doctor_home(doctor_id=None):
    doctor_id = doctor_id or session.get('doctor_id')
    if not doctor_id:
        flash('Please log in to access your dashboard.', 'error')
        return redirect(url_for('doctor_login'))

    doctor = doctors.find_one({"_id": ObjectId(doctor_id)})
    if not doctor:
        flash('Doctor not found.', 'error')
        return redirect(url_for('doctor_login'))

    appointments = list(appoint.find({'doctor_id': doctor_id}))
    return render_template('doctor_home.html', doctor=doctor, appointments=appointments, doctor_id=doctor_id)


@app.route("/doctor_login", methods=['GET', 'POST'])
def doctor_login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        # Find doctor by email
        doctor = doctors.find_one({'email': email})

        if doctor and (doctor['password'], password):
            session['doctor_id'] = str(doctor['_id'])
            session['doctor_name'] = doctor['doctor_name']
            flash('Login successful', 'success')

            # Pass the doctor_id explicitly
            return redirect(url_for('doctor_home', doctor_id=session['doctor_id']))
        
        flash('Invalid email or password', 'error')

    return render_template('doctor_login.html')


@app.route("/patient_register", methods=['GET', 'POST'])
def patient_register():
    if request.method == 'POST':
        # Retrieve form data
        fullname = request.form.get('fullname')
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')

        # Check if the username already exists
        if patients.find_one({'username': username}):
            flash('Username already exists', 'error')
            return render_template('patient_register.html')

        # Save the new patient data to MongoDB
        patients.insert_one({
            'fullname': fullname,
            'username': username,
            'email': email,
            'password': password
        })
        flash("Patient registered successfully", "success")
        return redirect(url_for('patient_login'))

    return render_template('patient_register.html')

@app.route("/patient_login", methods=['GET', 'POST'])
def patient_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        patient = patients.find_one({'username': username, 'password': password})
        if patient:
            session['patient_id'] = str(patient['_id'])
            session['patient_username'] = patient['username']
            return redirect(url_for('patient_home'))
        else:
            flash('Invalid credentials', 'error')

    return render_template('patient_login.html')

@app.route("/book_appointment/<doctor_id>", methods=['POST'])
def book_appointment(doctor_id):
    if 'patient_id' not in session:
        flash("You need to be logged in to book an appointment.", "info")
        return redirect(url_for('patient_login'))

    # Retrieve patient and doctor info
    patient = patients.find_one({'_id': ObjectId(session['patient_id'])})
    doctor = doctors.find_one({'_id': ObjectId(doctor_id)})

    if patient and doctor:
        # Create appointment request
        appointment_data = {
            'patient_id': session['patient_id'],
            'doctor_id': doctor_id,
            'patient_name': patient['username'],
            'doctor_name': doctor['doctor_name'],
            'doctor_specialization': doctor.get('specialization', 'N/A'),
            'appointment_date': datetime.now(),  # Use current datetime for appointment date
            'appointment_status': 'pending'
        }

        # Insert new appointment into the database using Appoint model
        appoint = Appoint(**appointment_data)
        appoint.save()

        flash("Appointment booked successfully!", "success")
        return redirect(url_for('patient_home'))

    flash("Error booking appointment", "error")
    return redirect(url_for('home'))


@app.route("/appointment_detail")
def appointment_detail():
    if 'patient_username' not in session:
        flash("You need to be logged in to view your appointment details", "error")
        return redirect(url_for('patient_login'))
    
    # Fetch the appointments for the logged-in patient using the patient_username
    patient_username = session['patient_username']
    appoints = Appoint.objects(patient_name=patient_username)  # Query based on patient_name (username)
    
    if appoints:
        return render_template('appointment_detail.html', appoints=appoints)
    else:
        flash("No appointments found.", "error")
        return redirect(url_for('patient_home'))  # Redirect to the patient's home page


@app.route("/doctor_dashboard")
def doctor_dashboard():
    if 'doctor_id' not in session:
        flash('Please log in to access the dashboard.', 'error')
        return redirect(url_for('doctor_login'))
    
    doctor_name = session.get('doctor_name', 'Doctor')
    return f"<h1>Welcome to your dashboard, Dr. {doctor_name}!</h1>"


@app.route("/admin_home")
def admin_home():
    if 'admin_id' in session:
        # Fetch data for the admin
        all_doctors = doctors.find()
        all_patients = patients.find()
        return render_template("admin_home.html", doctors=all_doctors, patients=all_patients)
    else:
        flash("Please log in as admin", "error")
        return redirect(url_for('admin_login'))

@app.route("/admin_login", methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        admin = db['admins'].find_one({'username': username, 'password': password})
        if admin:
            session['admin_id'] = str(admin['_id'])
            session['admin_username'] = admin['username']
            return redirect(url_for('admin_home'))
        else:
            flash("Invalid admin credentials", "error")

    return render_template('admin_login.html')

@app.route("/admin_logout")
def admin_logout():
    session.pop('admin_id', None)
    return redirect(url_for('home'))

@app.route('/patient_logout')
def patient_logout():
    # Remove patient session data
    session.pop('patient_id', None)
    session.pop('patient_username', None)
    
    # Redirect to the home page or patient login page
    flash("You have been logged out successfully.", "success")
    return redirect(url_for('home'))  # Or redirect to 'patient_login' if you want



@app.route("/contact", methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        message = request.form.get('message')
        if not name or not email or not message:
            flash("Name, email, and message are required fields.", "error")
            return redirect(url_for('contact'))
        data = {'name': name, 'email': email, 'message': message}
        contact_msg.insert_one(data)
        flash("Data stored successfully!", "success")
        return redirect(url_for('contact'))
    return render_template('contact.html')

@app.route("/doctor_logout")
def doctor_logout():
    session.pop('doctor_id', None)  # Remove doctor session
    session.pop('doctor_name', None)
    flash("You have been logged out", "success")
    return redirect(url_for('home'))

@app.route("/approve_appointment/<string:appointment_id>", methods=["POST"])
def approve_appointment(appointment_id):
    if 'doctor_id' not in session:
        flash("You must be logged in to approve appointments.", "error")
        return redirect(url_for('doctor_login'))

    doctor_id = session['doctor_id']
    appointment = validate_appointment(appointment_id, doctor_id)

    if not appointment:
        flash("Appointment not found or you're not authorized to approve it.", "error")
        return redirect(url_for('appointment_detail2'))

    try:
        result = appoint.update_one(
            {"_id": ObjectId(appointment_id), "doctor_id": ObjectId(doctor_id)},
            {"$set": {"appointment_status": "approved"}}
        )
        if result.matched_count > 0:
            flash("Appointment approved successfully.", "success")
        else:
            flash("Failed to update appointment status.", "error")
    except Exception as e:
        flash(f"An unexpected error occurred: {str(e)}", "error")
        print(f"Error: {e}")

    return redirect(url_for('appointment_detail2'))


@app.route("/reject_appointment/<string:appointment_id>", methods=["POST"])
def reject_appointment(appointment_id):
    if 'doctor_id' not in session:
        flash("You must be logged in to reject appointments.", "error")
        return redirect(url_for('doctor_login'))

    doctor_id = session['doctor_id']
    appointment = validate_appointment(appointment_id, doctor_id)

    if not appointment:
        flash("Appointment not found or you're not authorized to reject it.", "error")
        return redirect(url_for('appointment_detail2'))

    try:
        result = appoint.update_one(
            {"_id": ObjectId(appointment_id), "doctor_id": ObjectId(doctor_id)},
            {"$set": {"appointment_status": "rejected"}}
        )
        if result.matched_count > 0:
            flash("Appointment rejected successfully.", "success")
        else:
            flash("Failed to update appointment status.", "error")
    except Exception as e:
        flash(f"An unexpected error occurred: {str(e)}", "error")
        print(f"Error: {e}")

    return redirect(url_for('appointment_detail2'))


@app.route("/appointment_detail2", methods=["GET"])
def appointment_detail2():
    if 'doctor_id' not in session:
        flash("You need to be logged in to view your appointment details", "error")
        return redirect(url_for('doctor_login'))

    doctor_id = session['doctor_id']

    try:
        # Query appointments for the logged-in doctor
        doctor_appointments = appoint.find({"doctor_id": ObjectId(doctor_id)})
    except Exception as e:
        flash(f"Error fetching appointments: {str(e)}", "error")
        doctor_appointments = []

    return render_template('appointment_detail2.html', appoints=doctor_appointments, doctor_session=session)



if __name__ == "__main__":
    app.run(debug=True)
 