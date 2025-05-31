"""
Unified temp188.com Application
A multi-project platform with single sign-on
"""

from flask import Flask, render_template, redirect, url_for, session, request, flash
from flask_login import LoginManager, login_required, current_user
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta
import os
import secrets

# Import blueprints
from blueprints.auth import auth_bp
from blueprints.wordcloud import wordcloud_bp
from blueprints.dashboard import dashboard_bp
from blueprints.eternalvoice import eternalvoice_bp
from blueprints.wikipedia import wikipedia_bp
from blueprints.resume_marketplace import resume_bp
from blueprints.video_chat import video_chat_bp

app = Flask(__name__)

# Configuration
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', secrets.token_hex(32))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////var/temp188.com/instance/temp188.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = '/var/temp188.com/static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)  # 30-day session persistence

# Set OpenRouter API key for Wikipedia analysis
if not os.environ.get('OPENROUTER_API_KEY'):
    os.environ['OPENROUTER_API_KEY'] = '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'

# Ensure upload directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('/var/temp188.com/instance', exist_ok=True)

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'

@login_manager.user_loader
def load_user(user_id):
    from models import User
    return User.query.get(int(user_id))

# Register blueprints
app.register_blueprint(auth_bp, url_prefix='/auth')
app.register_blueprint(wordcloud_bp, url_prefix='/wordcloud')
app.register_blueprint(dashboard_bp, url_prefix='/dashboard')
app.register_blueprint(eternalvoice_bp, url_prefix='/eternalvoice')
app.register_blueprint(wikipedia_bp, url_prefix='/wikipedia')
app.register_blueprint(resume_bp, url_prefix='/resume')
app.register_blueprint(video_chat_bp, url_prefix='/video')

@app.route('/')
def index():
    """New multi-project homepage"""
    projects = [
        {
            'id': 'wordcloud',
            'name': 'WordCloud Studio',
            'description': 'Create beautiful word clouds with multiple styles and customization options',
            'icon': 'fa-cloud',
            'color': 'indigo',
            'url': '/wordcloud',
            'features': ['Quick Generator', 'Custom Shapes', 'Advanced Studio']
        },
        {
            'id': 'eternalvoice',
            'name': 'EternalVoice',
            'description': 'Preserve your AI conversations for future generations',
            'icon': 'fa-infinity',
            'color': 'blue',
            'url': '/eternalvoice',
            'features': ['Digital Legacy', 'Offline Storage', 'Family Heritage'],
            'new': True
        },
        {
            'id': 'wikipedia',
            'name': 'Wikipedia AI Analyzer',
            'description': 'Analyze Wikipedia articles for bias, sourcing quality, and factual accuracy',
            'icon': 'fa-brain',
            'color': 'teal',
            'url': '/wikipedia',
            'features': ['Bias Detection', 'Source Quality', 'Citation Analysis', 'AI-Powered'],
            'new': True
        },
        {
            'id': 'resume-marketplace',
            'name': 'Resume Marketplace',
            'description': 'Paywall-based platform where job seekers monetize resumes/videos and employers pay for access',
            'icon': 'fa-briefcase',
            'color': 'purple',
            'url': '/resume',
            'features': ['Magic Link Auth', 'Resume Paywall ($1)', 'Video Submissions ($5)', 'Live Interviews', 'Stripe Integration'],
            'new': True
        },
        # Future projects can be added here
        {
            'id': 'coming-soon-1',
            'name': 'Text Analytics',
            'description': 'Analyze sentiment, extract keywords, and summarize text',
            'icon': 'fa-chart-line',
            'color': 'green',
            'url': '#',
            'features': ['Coming Soon'],
            'disabled': True
        },
        {
            'id': 'coming-soon-2',
            'name': 'Creative Tools',
            'description': 'Generate story prompts, character names, and plot outlines',
            'icon': 'fa-pen-fancy',
            'color': 'purple',
            'url': '#',
            'features': ['Coming Soon'],
            'disabled': True
        }
    ]
    
    return render_template('home_unified.html', projects=projects)

@app.route('/about')
def about():
    """About page for the platform"""
    return render_template('about.html')

@app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def server_error(e):
    return render_template('500.html'), 500

# Context processor to make current_user available in all templates
@app.context_processor
def inject_user():
    return dict(current_user=current_user)

if __name__ == '__main__':
    # Create database tables if they don't exist
    from models import db, init_db
    db.init_app(app)
    with app.app_context():
        init_db()
    
    # Check if running under supervisor
    if os.environ.get('SUPERVISOR_ENABLED'):
        app.run(debug=False, port=5000, host='0.0.0.0')
    else:
        app.run(debug=True, port=5000, host='0.0.0.0')