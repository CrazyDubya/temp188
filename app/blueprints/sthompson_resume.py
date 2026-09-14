"""
SThompson Resume Blueprint
Single PDF upload that persists and displays once uploaded
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, send_from_directory
from werkzeug.utils import secure_filename
import os

sthompson_resume_bp = Blueprint('sthompson_resume', __name__)

# Configuration
UPLOAD_FOLDER = '/var/temp188.com/static/sthompson_uploads'
ALLOWED_EXTENSIONS = {'pdf'}
RESUME_FILENAME = 'sthompson_resume.pdf'

# Ensure upload directory exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    """Check if file has allowed extension"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def resume_exists():
    """Check if resume has already been uploaded"""
    return os.path.exists(os.path.join(UPLOAD_FOLDER, RESUME_FILENAME))

@sthompson_resume_bp.route('/SThompson-resume', methods=['GET', 'POST'])
def sthompson_resume():
    """Main route for SThompson resume page"""

    if request.method == 'POST':
        # Only allow upload if no resume exists yet
        if resume_exists():
            flash('Resume has already been uploaded', 'warning')
            return redirect(url_for('sthompson_resume.sthompson_resume'))

        # Check if file was uploaded
        if 'resume' not in request.files:
            flash('No file selected', 'error')
            return redirect(request.url)

        file = request.files['resume']

        # Check if filename is empty
        if file.filename == '':
            flash('No file selected', 'error')
            return redirect(request.url)

        # Validate and save file
        if file and allowed_file(file.filename):
            # Save with fixed filename
            filepath = os.path.join(UPLOAD_FOLDER, RESUME_FILENAME)
            file.save(filepath)
            flash('Resume uploaded successfully!', 'success')
            return redirect(url_for('sthompson_resume.sthompson_resume'))
        else:
            flash('Only PDF files are allowed', 'error')
            return redirect(request.url)

    # GET request - show upload form or display PDF
    has_resume = resume_exists()
    return render_template('sthompson_resume/index.html', has_resume=has_resume)

@sthompson_resume_bp.route('/SThompson-resume/view')
def view_resume():
    """Route to serve the PDF file"""
    if not resume_exists():
        flash('No resume has been uploaded yet', 'error')
        return redirect(url_for('sthompson_resume.sthompson_resume'))

    return send_from_directory(UPLOAD_FOLDER, RESUME_FILENAME)
