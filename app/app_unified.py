"""
Unified temp188.com Application
A multi-project platform with single sign-on
"""

# IMPORTANT: Monkey patch MUST be first, before any other imports
from gevent import monkey
monkey.patch_all()

from flask import Flask, render_template, redirect, url_for, session, request, flash
from flask_login import LoginManager, login_required, current_user
from flask_socketio import SocketIO
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta
import os
import secrets
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv('/var/temp188.com/.env')

# Import blueprints
from blueprints.auth import auth_bp
from blueprints.wordcloud import wordcloud_bp
from blueprints.dashboard import dashboard_bp
from blueprints.eternalvoice import eternalvoice_bp
from blueprints.wikipedia import wikipedia_bp
from blueprints.resume_marketplace import resume_bp
from blueprints.video_chat import video_chat_bp
from blueprints.billing import billing_bp
from blueprints.sthompson_resume import sthompson_resume_bp
from blueprints.turing_chat import turing_bp
from blueprints.whisper import whisper_bp

app = Flask(__name__)

# Configuration
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', secrets.token_hex(32))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////var/temp188.com/instance/temp188.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = '/var/temp188.com/static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)  # 30-day session persistence

# Session configuration for subdomain support
app.config['SESSION_COOKIE_DOMAIN'] = '.temp188.com'  # Allow cookies across subdomains
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = True  # HTTPS only

# Stripe Configuration - Load from environment variables only
app.config['STRIPE_PUBLIC_KEY'] = os.environ.get('STRIPE_PUBLIC_KEY', '')
app.config['STRIPE_SECRET_KEY'] = os.environ.get('STRIPE_SECRET_KEY', '')
app.config['STRIPE_WEBHOOK_SECRET'] = os.environ.get('STRIPE_WEBHOOK_SECRET', '')
app.config['STRIPE_PRICE_ID'] = os.environ.get('STRIPE_PRICE_ID', '')
# Set OpenRouter API key for Wikipedia analysis (load from .env file)
# Ensure OPENROUTER_API_KEY is set in /var/temp188.com/.env

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

# Initialize SocketIO
socketio = SocketIO(
    app,
    message_queue='redis://localhost:6379/0',
    cors_allowed_origins="*",
    async_mode='gevent',
    logger=True,
    engineio_logger=False
)

# Register blueprints
app.register_blueprint(auth_bp, url_prefix='/auth')
app.register_blueprint(wordcloud_bp, url_prefix='/wordcloud')
app.register_blueprint(dashboard_bp, url_prefix='/dashboard')
app.register_blueprint(eternalvoice_bp, url_prefix='/eternalvoice')
app.register_blueprint(wikipedia_bp, url_prefix='/wikipedia')
app.register_blueprint(resume_bp, url_prefix='/resume')
app.register_blueprint(video_chat_bp, url_prefix='/video')
app.register_blueprint(billing_bp, url_prefix='/billing')
app.register_blueprint(sthompson_resume_bp)
app.register_blueprint(turing_bp)
app.register_blueprint(whisper_bp, url_prefix='/whisper')

# Initialize rate limiter for whisper blueprint
from blueprints.whisper import limiter as whisper_limiter
whisper_limiter.init_app(app)

# Initialize SocketIO events
from blueprints.turing_chat import init_socketio
init_socketio(socketio)

@app.route('/')
def index():
    """New multi-project homepage - with subdomain routing"""
    # Detect if accessing from turing subdomain - show Turing landing page
    if request.host.startswith('turing.'):
        return redirect('/turing')

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
        {
            'id': 'turing-test',
            'name': 'Turing Test Chat',
            'description': 'Challenge your perception: Chat with someone and guess if they\'re human or AI',
            'icon': 'fa-robot',
            'color': 'red',
            'url': '/turing',
            'features': ['Real-Time Chat', 'Anonymous Play', 'Global Leaderboard', 'Stats Tracking'],
            'new': True
        },
        {
            'id': 'whisper',
            'name': 'Whisper AI Suite',
            'description': 'Complete audio & text processing: speech-to-text, text-to-speech, and translation',
            'icon': 'fa-microphone-lines',
            'color': 'indigo',
            'url': '/whisper',
            'features': ['Text-to-Speech', 'Speech-to-Text (Whisper AI)', 'Translation', 'Unified Workflows', '15+ Languages'],
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

@app.route('/video/test')
def video_test():
    """Test video chat without authentication"""
    room_name = f"test-room-{secrets.token_hex(4)}"
    jitsi_domain = os.environ.get('JITSI_DOMAIN', 'meet.jit.si')
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Video Chat Test - temp188.com</title>
        <script src="https://{jitsi_domain}/external_api.js"></script>
        <style>
            body {{ margin: 0; padding: 0; font-family: Arial, sans-serif; }}
            #meet {{ height: 100vh; }}
            .info {{ 
                position: fixed; top: 10px; left: 10px; 
                background: rgba(0,0,0,0.7); color: white; 
                padding: 15px; border-radius: 5px; z-index: 1000;
            }}
        </style>
    </head>
    <body>
        <div class="info">
            <strong>🎥 Video Chat Test</strong><br>
            Room: {room_name}<br>
            Server: {jitsi_domain}<br>
            Status: <span id="status">Connecting...</span>
        </div>
        <div id="meet"></div>
        
        <script>
            const domain = '{jitsi_domain}';
            const options = {{
                roomName: '{room_name}',
                width: '100%',
                height: '100%',
                parentNode: document.querySelector('#meet'),
                configOverwrite: {{
                    startWithAudioMuted: false,
                    startWithVideoMuted: false,
                }},
                interfaceConfigOverwrite: {{
                    TOOLBAR_BUTTONS: [
                        'microphone', 'camera', 'closedcaptions', 'desktop', 
                        'fullscreen', 'fodeviceselection', 'hangup', 'chat',
                        'settings', 'videoquality', 'filmstrip', 'stats', 
                        'shortcuts', 'tileview'
                    ],
                }}
            }};
            
            const api = new JitsiMeetExternalAPI(domain, options);
            
            api.addEventListener('videoConferenceJoined', () => {{
                document.getElementById('status').textContent = '✅ Connected';
                document.getElementById('status').style.color = '#0f0';
            }});
            
            api.addEventListener('readyToClose', () => {{
                window.location.href = '/';
            }});
        </script>
    </body>
    </html>
    """

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
        socketio.run(app, debug=False, port=5000, host='0.0.0.0')
    else:
        socketio.run(app, debug=True, port=5000, host='0.0.0.0')