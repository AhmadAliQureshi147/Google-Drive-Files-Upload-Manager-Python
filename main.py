import authlib
from flask import Flask, redirect, url_for, session, request, render_template, send_from_directory
from authlib.integrations.flask_client import OAuth
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials
import os
import tempfile
import shutil
import openpyxl
import glob

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'your_secret_key_here')

# Set the Google OAuth client ID and client secret
app.config['GOOGLE_CLIENT_ID'] = os.environ.get('GOOGLE_CLIENT_ID', '661420034472-jlbodm792faa0h864t62j734tn9pgnht.apps.googleusercontent.com')
app.config['GOOGLE_CLIENT_SECRET'] = os.environ.get('GOOGLE_CLIENT_SECRET', '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')

oauth = OAuth(app)
google = oauth.register(
    name='google',
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_id='661420034472-jlbodm792faa0h864t62j734tn9pgnht.apps.googleusercontent.com',
    client_secret='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',
    client_kwargs={'scope': 'openid email profile https://www.googleapis.com/auth/drive.file'}
)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login')
def login():
    redirect_uri = url_for('authorize', _external=True)
    return google.authorize_redirect(redirect_uri)

@app.route('/authorize')
def authorize():
    try:
        token = google.authorize_access_token()
        session['user_credentials'] = token
        return redirect(url_for('upload'))
    except authlib.integrations.base_client.errors.MismatchingStateError:
        return 'State mismatch error. Please try logging in again.', 400

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if 'user_credentials' not in session:
        return redirect(url_for('login'))

    upload_success = False  # Initialize the variable

    if request.method == 'POST':
        uploaded_files = request.files.getlist('files')
        if not uploaded_files:
            return 'No files uploaded', 400

        temp_dir = tempfile.mkdtemp()

        # Save the uploaded files temporarily
        uploaded_file_names = []
        for file in uploaded_files:
            file_path = os.path.join(temp_dir, file.filename)
            file.save(file_path)
            uploaded_file_names.append(file.filename.lower())  # Convert filename to lower case

        # Check for specific files
        required_files = ["quiz1.docx", "quiz2.docx", "assign1.docx", "assign2.docx", "mid.docx", "final.docx"]
        files_existence = {file_name: file_name in uploaded_file_names for file_name in required_files}

        # Create an Excel workbook
        workbook = openpyxl.Workbook()
        sheet = workbook.active
        sheet.title = "File Check Report"
        sheet.append(["File Name", "Exists"])

        for file_name, exists in files_existence.items():
            sheet.append([file_name, '✓' if exists else '✗'])

        # Convert the Excel data to a list of dictionaries for easy rendering in HTML
        table_data = []
        for row in sheet.iter_rows(min_row=2, values_only=True):  # Skip the header row
            table_data.append({"File Name": row[0], "Exists": row[1]})
        session['table_data'] = table_data

        # Save the workbook
        excel_file_path = os.path.join(temp_dir, 'file_check_report.xlsx')
        workbook.save(excel_file_path)

        # Upload files and Excel sheet to Google Drive
        token_info = session['user_credentials']
        credentials = Credentials(
            token=token_info['access_token'],
            refresh_token=token_info.get('refresh_token'),
            token_uri='https://oauth2.googleapis.com/token',
            client_id=app.config['GOOGLE_CLIENT_ID'],
            client_secret=app.config['GOOGLE_CLIENT_SECRET']
        )
        service = build('drive', 'v3', credentials=credentials)

        # Uploading each file and the Excel report
        for file_path in [os.path.join(temp_dir, file.filename) for file in uploaded_files] + [excel_file_path]:
            file_metadata = {'name': os.path.basename(file_path)}
            media = MediaFileUpload(file_path, mimetype='*/*')
            service.files().create(body=file_metadata, media_body=media, fields='id').execute()

        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)

        upload_success = True  # Set to True on successful upload

    return render_template('upload.html', upload_success=upload_success)




@app.route('/show-table')
def show_table():
    # Retrieve table data from the session
    table_data = session.get('table_data', [])

    # Check if there is any table data to display
    if not table_data:
        # If not, you can redirect to the upload page or show a message
        # Ensure this template exists or handle this situation as you prefer
        return render_template('no_data.html')
        # Or simply return a message
        # return "No table data available. Please upload files first."

    # If table data is present, render it on the table.html page
    return render_template('table.html', table_data=table_data)


if __name__ == '__main__':
    app.run(debug=True)
