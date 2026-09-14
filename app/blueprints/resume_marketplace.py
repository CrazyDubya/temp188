"""
Resume Marketplace Blueprint - Paywall-based resume and video platform
Users submit resumes/videos, employers pay to unlock them
"""

from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta
import os
import secrets
import uuid
import json
from models import db
from .resume_models import ResumeProfile, ResumeDocument, VideoSubmission, PaymentTransaction, InterviewBooking, IdentityVerification
from .secure_storage import secure_storage
from .email_service import email_service

resume_bp = Blueprint('resume_marketplace', __name__)

# Configuration
ALLOWED_RESUME_EXTENSIONS = {'pdf', 'doc', 'docx'}
ALLOWED_VIDEO_EXTENSIONS = {'mp4', 'mov', 'avi', 'webm'}
MAX_RESUME_SIZE = 5 * 1024 * 1024  # 5MB
MAX_VIDEO_SIZE = 100 * 1024 * 1024  # 100MB

def allowed_file(filename, allowed_extensions):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions

def generate_magic_link_token():
    """Generate secure token for magic link authentication"""
    return secrets.token_urlsafe(32)

@resume_bp.route('/')
def index():
    """Main marketplace landing page"""
    # Get sample profiles for preview (anonymized)
    sample_profiles = ResumeProfile.query.filter_by(is_public=True).limit(9).all()
    return render_template('resume_marketplace/index.html', profiles=sample_profiles)

@resume_bp.route('/auth/magic-link', methods=['GET', 'POST'])
def magic_link_auth():
    """Magic link authentication for job seekers and employers"""
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        user_type = request.form.get('user_type', 'jobseeker')  # jobseeker or employer
        
        if not email:
            return jsonify({'error': 'Email is required'}), 400
        
        # Generate magic link token
        token = generate_magic_link_token()
        
        # Store token in session temporarily (in production, use Redis)
        session[f'magic_token_{token}'] = {
            'email': email,
            'user_type': user_type,
            'expires': (datetime.utcnow() + timedelta(hours=1)).isoformat()
        }
        
        # Generate magic link
        magic_link = url_for('resume_marketplace.verify_magic_link', token=token, _external=True)
        
        # Send email with magic link
        email_sent = email_service.send_magic_link(email, magic_link, user_type)
        
        if email_sent:
            return jsonify({
                'success': True,
                'message': f'Magic link sent to {email}. Check your inbox and click the link to sign in.'
            })
        else:
            return jsonify({
                'error': 'Failed to send email. Please try again or contact support.'
            }), 500
    
    return render_template('resume_marketplace/auth.html')

@resume_bp.route('/auth/verify/<token>')
def verify_magic_link(token):
    """Verify magic link and create/login user"""
    session_key = f'magic_token_{token}'
    
    if session_key not in session:
        flash('Invalid or expired magic link', 'error')
        return redirect(url_for('resume_marketplace.magic_link_auth'))
    
    token_data = session[session_key]
    
    # Check if token expired
    if datetime.fromisoformat(token_data['expires']) < datetime.utcnow():
        session.pop(session_key, None)
        flash('Magic link has expired', 'error')
        return redirect(url_for('resume_marketplace.magic_link_auth'))
    
    email = token_data['email']
    user_type = token_data['user_type']
    
    # Find or create user
    from models import User
    user = User.query.filter_by(email=email).first()
    
    if not user:
        # Create new user
        username = email.split('@')[0] + '_' + secrets.token_hex(4)
        user = User(
            username=username,
            email=email,
            role=user_type,
            created_at=datetime.utcnow()
        )
        db.session.add(user)
        db.session.commit()
    
    # Create or update resume profile
    profile = ResumeProfile.query.filter_by(user_id=user.id).first()
    if not profile:
        profile = ResumeProfile(
            user_id=user.id,
            user_type=user_type,
            created_at=datetime.utcnow()
        )
        db.session.add(profile)
        db.session.commit()
    
    # Store user in session (simple session management)
    session['user_id'] = user.id
    session['user_email'] = user.email
    session['user_type'] = user_type
    session['logged_in'] = True
    session.permanent = True  # Make session permanent (30 days)
    
    # Clean up magic token
    session.pop(session_key, None)
    
    # Redirect based on user type
    if user_type == 'employer':
        return redirect(url_for('resume_marketplace.employer_dashboard'))
    else:
        return redirect(url_for('resume_marketplace.jobseeker_dashboard'))

@resume_bp.route('/dashboard')
def dashboard():
    """Redirect to appropriate dashboard"""
    if not session.get('logged_in'):
        return redirect(url_for('resume_marketplace.magic_link_auth'))
    
    if session.get('user_type') == 'employer':
        return redirect(url_for('resume_marketplace.employer_dashboard'))
    else:
        return redirect(url_for('resume_marketplace.jobseeker_dashboard'))

@resume_bp.route('/jobseeker/dashboard')
def jobseeker_dashboard():
    """Job seeker dashboard for managing profile and content"""
    if not session.get('logged_in'):
        return redirect(url_for('resume_marketplace.magic_link_auth'))
    
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('resume_marketplace.magic_link_auth'))
    
    # Get user object
    from models import User
    user = User.query.get(user_id)
    if not user:
        session.clear()
        return redirect(url_for('resume_marketplace.magic_link_auth'))
    
    profile = ResumeProfile.query.filter_by(user_id=user_id).first()
    if not profile:
        # Create profile if it doesn't exist
        profile = ResumeProfile(
            user_id=user_id,
            user_type='jobseeker',
            created_at=datetime.utcnow()
        )
        db.session.add(profile)
        db.session.commit()
    
    # Get user's documents and videos
    documents = ResumeDocument.query.filter_by(profile_id=profile.id).all()
    videos = VideoSubmission.query.filter_by(profile_id=profile.id).all()
    
    # Get earnings
    earnings = db.session.query(db.func.sum(PaymentTransaction.amount * 0.5)).filter(
        PaymentTransaction.recipient_profile_id == profile.id,
        PaymentTransaction.status == 'completed'
    ).scalar() or 0
    
    return render_template('resume_marketplace/jobseeker_dashboard.html', 
                         user=user, profile=profile, documents=documents, videos=videos, earnings=earnings)

@resume_bp.route('/employer/dashboard')
@login_required
def employer_dashboard():
    """Employer dashboard for browsing and purchasing access"""
    profile = ResumeProfile.query.filter_by(user_id=current_user.id).first()
    if not profile or profile.user_type != 'employer':
        flash('Access denied', 'error')
        return redirect(url_for('resume_marketplace.index'))
    
    # Get available profiles to browse
    search_query = request.args.get('search', '')
    skill_filter = request.args.get('skills', '')
    
    query = ResumeProfile.query.filter_by(user_type='jobseeker', is_active=True)
    
    if search_query:
        query = query.filter(
            (ResumeProfile.display_name.contains(search_query)) |
            (ResumeProfile.skills.contains(search_query)) |
            (ResumeProfile.bio.contains(search_query))
        )
    
    if skill_filter:
        query = query.filter(ResumeProfile.skills.contains(skill_filter))
    
    profiles = query.limit(20).all()
    
    # Get user's purchase history
    purchases = PaymentTransaction.query.filter_by(
        buyer_profile_id=profile.id,
        status='completed'
    ).order_by(PaymentTransaction.created_at.desc()).limit(10).all()
    
    return render_template('resume_marketplace/employer_dashboard.html', 
                         profiles=profiles, purchases=purchases, search_query=search_query)

@resume_bp.route('/profile/setup', methods=['GET', 'POST'])
@login_required
def profile_setup():
    """Setup or edit user profile"""
    profile = ResumeProfile.query.filter_by(user_id=current_user.id).first()
    
    if request.method == 'POST':
        # Update profile data
        profile.display_name = request.form.get('display_name', '')
        profile.bio = request.form.get('bio', '')
        profile.skills = request.form.get('skills', '')
        profile.education = request.form.get('education', '')
        profile.experience_years = int(request.form.get('experience_years', 0))
        profile.hourly_rate = float(request.form.get('hourly_rate', 0))
        
        # Social media and identity verification
        profile.github_url = request.form.get('github_url', '')
        profile.linkedin_url = request.form.get('linkedin_url', '')
        profile.twitter_url = request.form.get('twitter_url', '')
        profile.portfolio_url = request.form.get('portfolio_url', '')
        
        profile.updated_at = datetime.utcnow()
        
        # Calculate identity score based on provided information
        profile.identity_score = calculate_identity_score(profile)
        
        db.session.commit()
        flash('Profile updated successfully', 'success')
        return redirect(url_for('resume_marketplace.jobseeker_dashboard'))
    
    return render_template('resume_marketplace/profile_setup.html', profile=profile)

def calculate_identity_score(profile):
    """Calculate identity verification score based on provided information"""
    score = 0
    max_score = 100
    
    # Basic info (30 points)
    if profile.display_name and len(profile.display_name) > 2:
        score += 10
    if profile.bio and len(profile.bio) > 50:
        score += 10
    if profile.education:
        score += 10
    
    # Skills and experience (20 points)
    if profile.skills and len(profile.skills.split(',')) >= 3:
        score += 10
    if profile.experience_years > 0:
        score += 10
    
    # Social media presence (50 points - strong identity indicators)
    if profile.github_url:
        score += 15  # GitHub is strong professional indicator
    if profile.linkedin_url:
        score += 15  # LinkedIn is strong professional indicator
    if profile.twitter_url:
        score += 10  # Social presence
    if profile.portfolio_url:
        score += 10  # Professional work showcase
    
    return min(score, max_score)

@resume_bp.route('/upload')
def upload_page():
    """Upload selection page"""
    if not session.get('logged_in'):
        return redirect(url_for('resume_marketplace.magic_link_auth'))
    
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('resume_marketplace.magic_link_auth'))
    
    # Get user object
    from models import User
    user = User.query.get(user_id)
    if not user:
        session.clear()
        return redirect(url_for('resume_marketplace.magic_link_auth'))
    
    profile = ResumeProfile.query.filter_by(user_id=user_id).first()
    if not profile:
        # Create profile if it doesn't exist
        profile = ResumeProfile(
            user_id=user_id,
            user_type='jobseeker',
            created_at=datetime.utcnow()
        )
        db.session.add(profile)
        db.session.commit()
    
    return render_template('resume_marketplace/upload.html', user=user, profile=profile)

@resume_bp.route('/video-upload')
def video_upload_page():
    """Video upload page"""
    if not session.get('logged_in'):
        return redirect(url_for('resume_marketplace.magic_link_auth'))
    
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('resume_marketplace.magic_link_auth'))
    
    # Get user object
    from models import User
    user = User.query.get(user_id)
    if not user:
        session.clear()
        return redirect(url_for('resume_marketplace.magic_link_auth'))
    
    profile = ResumeProfile.query.filter_by(user_id=user_id).first()
    if not profile:
        # Create profile if it doesn't exist
        profile = ResumeProfile(
            user_id=user_id,
            user_type='jobseeker',
            created_at=datetime.utcnow()
        )
        db.session.add(profile)
        db.session.commit()
    
    return render_template('resume_marketplace/video_upload.html', user=user, profile=profile)

@resume_bp.route('/profile')
def profile_page():
    """Profile setup/edit page"""
    if not session.get('logged_in'):
        return redirect(url_for('resume_marketplace.magic_link_auth'))
    
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('resume_marketplace.magic_link_auth'))
    
    # Get user object
    from models import User
    user = User.query.get(user_id)
    if not user:
        session.clear()
        return redirect(url_for('resume_marketplace.magic_link_auth'))
    
    profile = ResumeProfile.query.filter_by(user_id=user_id).first()
    if not profile:
        # Create profile if it doesn't exist
        profile = ResumeProfile(
            user_id=user_id,
            user_type='jobseeker',
            created_at=datetime.utcnow()
        )
        db.session.add(profile)
        db.session.commit()
    
    return render_template('resume_marketplace/profile_setup.html', user=user, profile=profile)

@resume_bp.route('/upload/resume', methods=['POST'])
def upload_resume():
    """Upload resume document"""
    if not session.get('logged_in'):
        return jsonify({'error': 'Authentication required'}), 401
    
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Authentication required'}), 401
    
    profile = ResumeProfile.query.filter_by(user_id=user_id).first()
    
    if not profile or profile.user_type != 'jobseeker':
        return jsonify({'error': 'Access denied'}), 403
    
    if 'resume' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['resume']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not allowed_file(file.filename, ALLOWED_RESUME_EXTENSIONS):
        return jsonify({'error': 'Invalid file type. Please upload PDF, DOC, or DOCX'}), 400
    
    # Read file data
    file_data = file.read()
    file_extension = file.filename.rsplit('.', 1)[1].lower()
    
    # Create document record first to get ID
    document = ResumeDocument(
        profile_id=profile.id,
        filename='',  # Will be updated after encryption
        original_filename=secure_filename(file.filename),
        file_size=len(file_data),
        file_type=file_extension,
        created_at=datetime.utcnow()
    )
    db.session.add(document)
    db.session.flush()  # Get the document ID
    
    # Encrypt and store file securely
    secure_filename_result = secure_storage.encrypt_and_store_file(
        file_data=file_data,
        user_id=user_id,
        file_id=document.id,
        file_type='resume'
    )
    
    # Update document with secure filename
    document.filename = secure_filename_result
    db.session.commit()
    
    return jsonify({'success': True, 'document_id': document.id})

@resume_bp.route('/upload/video', methods=['POST'])
def upload_video():
    """Upload video submission"""
    if not session.get('logged_in'):
        return jsonify({'error': 'Authentication required'}), 401
    
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Authentication required'}), 401
    
    profile = ResumeProfile.query.filter_by(user_id=user_id).first()
    
    if not profile or profile.user_type != 'jobseeker':
        return jsonify({'error': 'Access denied'}), 403
    
    if 'video' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['video']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not allowed_file(file.filename, ALLOWED_VIDEO_EXTENSIONS):
        return jsonify({'error': 'Invalid file type. Please upload MP4, MOV, AVI, or WEBM'}), 400
    
    # Read file data
    file_data = file.read()
    file_extension = file.filename.rsplit('.', 1)[1].lower()
    
    # Create video record first to get ID
    video = VideoSubmission(
        profile_id=profile.id,
        filename='',  # Will be updated after encryption
        original_filename=secure_filename(file.filename),
        file_size=len(file_data),
        duration_seconds=0,  # TODO: Extract video duration
        created_at=datetime.utcnow()
    )
    db.session.add(video)
    db.session.flush()  # Get the video ID
    
    # Encrypt and store file securely
    secure_filename_result = secure_storage.encrypt_and_store_file(
        file_data=file_data,
        user_id=user_id,
        file_id=video.id,
        file_type='video'
    )
    
    # Update video with secure filename
    video.filename = secure_filename_result
    db.session.commit()
    
    return jsonify({'success': True, 'video_id': video.id})

@resume_bp.route('/purchase/resume/<int:profile_id>')
@login_required
def purchase_resume_access(profile_id):
    """Purchase access to a resume for $1"""
    buyer_profile = ResumeProfile.query.filter_by(user_id=current_user.id).first()
    target_profile = ResumeProfile.query.get_or_404(profile_id)
    
    if not buyer_profile or buyer_profile.user_type != 'employer':
        return jsonify({'error': 'Access denied'}), 403
    
    # Check if already purchased
    existing_purchase = PaymentTransaction.query.filter_by(
        buyer_profile_id=buyer_profile.id,
        recipient_profile_id=target_profile.id,
        content_type='resume',
        status='completed'
    ).first()
    
    if existing_purchase:
        return jsonify({'error': 'You already have access to this resume'}), 400
    
    # Create payment transaction (integrate with Stripe in production)
    transaction = PaymentTransaction(
        buyer_profile_id=buyer_profile.id,
        recipient_profile_id=target_profile.id,
        content_type='resume',
        amount=1.00,  # $1 for resume access
        currency='USD',
        status='pending',
        created_at=datetime.utcnow()
    )
    
    # For demo purposes, mark as completed
    # In production, this would be handled by Stripe webhook
    transaction.status = 'completed'
    transaction.stripe_payment_id = f"demo_{uuid.uuid4().hex}"
    
    db.session.add(transaction)
    db.session.commit()
    
    return jsonify({'success': True, 'transaction_id': transaction.id})

@resume_bp.route('/view/profile/<int:profile_id>')
@login_required
def view_profile(profile_id):
    """View a profile with purchased content"""
    viewer_profile = ResumeProfile.query.filter_by(user_id=current_user.id).first()
    target_profile = ResumeProfile.query.get_or_404(profile_id)
    
    # Check access permissions
    has_resume_access = False
    has_video_access = False
    
    if viewer_profile and viewer_profile.user_type == 'employer':
        # Check if employer has purchased access
        resume_purchase = PaymentTransaction.query.filter_by(
            buyer_profile_id=viewer_profile.id,
            recipient_profile_id=target_profile.id,
            content_type='resume',
            status='completed'
        ).first()
        
        video_purchase = PaymentTransaction.query.filter_by(
            buyer_profile_id=viewer_profile.id,
            recipient_profile_id=target_profile.id,
            content_type='video',
            status='completed'
        ).first()
        
        has_resume_access = resume_purchase is not None
        has_video_access = video_purchase is not None
    
    # Get documents and videos
    documents = ResumeDocument.query.filter_by(profile_id=target_profile.id).all()
    videos = VideoSubmission.query.filter_by(profile_id=target_profile.id).all()
    
    return render_template('resume_marketplace/profile_view.html',
                         profile=target_profile,
                         documents=documents,
                         videos=videos,
                         has_resume_access=has_resume_access,
                         has_video_access=has_video_access)

@resume_bp.route('/purchase/video/<int:profile_id>')
@login_required
def purchase_video_access(profile_id):
    """Purchase access to a video for $5"""
    buyer_profile = ResumeProfile.query.filter_by(user_id=current_user.id).first()
    target_profile = ResumeProfile.query.get_or_404(profile_id)
    
    if not buyer_profile or buyer_profile.user_type != 'employer':
        return jsonify({'error': 'Access denied'}), 403
    
    # Check if already purchased
    existing_purchase = PaymentTransaction.query.filter_by(
        buyer_profile_id=buyer_profile.id,
        recipient_profile_id=target_profile.id,
        content_type='video',
        status='completed'
    ).first()
    
    if existing_purchase:
        return jsonify({'error': 'You already have access to this video'}), 400
    
    # Create payment transaction
    transaction = PaymentTransaction(
        buyer_profile_id=buyer_profile.id,
        recipient_profile_id=target_profile.id,
        content_type='video',
        amount=5.00,  # $5 for video access
        currency='USD',
        status='pending',
        created_at=datetime.utcnow()
    )
    
    # For demo purposes, mark as completed
    transaction.status = 'completed'
    transaction.stripe_payment_id = f"demo_{uuid.uuid4().hex}"
    
    db.session.add(transaction)
    db.session.commit()
    
    return jsonify({'success': True, 'transaction_id': transaction.id})

@resume_bp.route('/book/interview/<int:profile_id>', methods=['GET', 'POST'])
@login_required
def book_interview(profile_id):
    """Book live interview with job seeker"""
    employer_profile = ResumeProfile.query.filter_by(user_id=current_user.id).first()
    jobseeker_profile = ResumeProfile.query.get_or_404(profile_id)
    
    if not employer_profile or employer_profile.user_type != 'employer':
        return jsonify({'error': 'Access denied'}), 403
    
    if not jobseeker_profile.is_available_for_interviews:
        return jsonify({'error': 'This user is not available for interviews'}), 400
    
    if request.method == 'POST':
        # Parse booking details
        scheduled_datetime = datetime.fromisoformat(request.form.get('scheduled_datetime'))
        duration_minutes = int(request.form.get('duration_minutes', 30))
        
        # Calculate total amount
        hourly_rate = jobseeker_profile.hourly_rate
        total_amount = (hourly_rate * duration_minutes / 60)
        
        # Create interview booking
        booking = InterviewBooking(
            jobseeker_profile_id=jobseeker_profile.id,
            employer_profile_id=employer_profile.id,
            scheduled_datetime=scheduled_datetime,
            duration_minutes=duration_minutes,
            hourly_rate=hourly_rate,
            total_amount=total_amount,
            video_room_id=f"interview_{uuid.uuid4().hex}",
            created_at=datetime.utcnow()
        )
        
        # Create payment transaction for the interview
        payment = PaymentTransaction(
            buyer_profile_id=employer_profile.id,
            recipient_profile_id=jobseeker_profile.id,
            content_type='interview',
            amount=total_amount,
            currency='USD',
            description=f"Interview booking for {duration_minutes} minutes",
            status='pending',
            created_at=datetime.utcnow()
        )
        
        # For demo, mark as completed
        payment.status = 'completed'
        payment.stripe_payment_id = f"demo_{uuid.uuid4().hex}"
        
        db.session.add(payment)
        db.session.flush()  # Get payment ID
        
        booking.payment_transaction_id = payment.id
        booking.payment_status = 'paid'
        
        db.session.add(booking)
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'booking_id': booking.id,
            'interview_url': url_for('video_chat.join_interview', booking_id=booking.id)
        })
    
    return render_template('resume_marketplace/book_interview.html', 
                         profile=jobseeker_profile)

@resume_bp.route('/stripe/webhook', methods=['POST'])
def stripe_webhook():
    """Handle Stripe webhook events"""
    payload = request.get_data()
    sig_header = request.headers.get('Stripe-Signature')
    
    try:
        # Verify webhook signature (implement with actual Stripe secret)
        # event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
        
        # For now, just parse the JSON
        event = json.loads(payload)
        
        if event['type'] == 'payment_intent.succeeded':
            # Handle successful payment
            payment_intent = event['data']['object']
            
            # Find transaction by Stripe payment ID
            transaction = PaymentTransaction.query.filter_by(
                stripe_payment_id=payment_intent['id']
            ).first()
            
            if transaction:
                transaction.status = 'completed'
                transaction.completed_at = datetime.utcnow()
                db.session.commit()
        
        return jsonify({'status': 'success'})
    
    except Exception as e:
        current_app.logger.error(f"Stripe webhook error: {str(e)}")
        return jsonify({'error': str(e)}), 400

@resume_bp.route('/api/stripe/create-payment-intent', methods=['POST'])
@login_required
def create_payment_intent():
    """Create Stripe payment intent for purchases"""
    data = request.get_json()
    
    buyer_profile = ResumeProfile.query.filter_by(user_id=current_user.id).first()
    if not buyer_profile or buyer_profile.user_type != 'employer':
        return jsonify({'error': 'Access denied'}), 403
    
    content_type = data.get('content_type')  # 'resume', 'video', 'interview'
    profile_id = data.get('profile_id')
    
    # Determine amount based on content type
    amount_map = {
        'resume': 100,  # $1.00 in cents
        'video': 500,   # $5.00 in cents
        'interview': data.get('amount', 0) * 100  # Custom amount for interviews
    }
    
    amount = amount_map.get(content_type, 0)
    
    if amount <= 0:
        return jsonify({'error': 'Invalid amount'}), 400
    
    try:
        # Create Stripe payment intent (uncomment when Stripe is configured)
        # import stripe
        # intent = stripe.PaymentIntent.create(
        #     amount=amount,
        #     currency='usd',
        #     metadata={
        #         'buyer_profile_id': buyer_profile.id,
        #         'recipient_profile_id': profile_id,
        #         'content_type': content_type
        #     }
        # )
        
        # For demo purposes, return mock data
        intent = {
            'id': f"pi_{uuid.uuid4().hex}",
            'client_secret': f"pi_{uuid.uuid4().hex}_secret",
            'amount': amount,
            'currency': 'usd'
        }
        
        return jsonify({
            'client_secret': intent['client_secret'],
            'payment_intent_id': intent['id']
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@resume_bp.route('/terms')
def terms_of_service():
    """Terms of service for the platform"""
    return render_template('resume_marketplace/terms.html')

@resume_bp.route('/api/search')
def api_search():
    """API endpoint for searching profiles"""
    query = request.args.get('q', '')
    skills = request.args.get('skills', '')
    min_score = int(request.args.get('min_score', 0))
    limit = int(request.args.get('limit', 20))
    
    # Build query
    profiles_query = ResumeProfile.query.filter_by(
        user_type='jobseeker',
        is_active=True,
        is_public=True
    ).filter(ResumeProfile.identity_score >= min_score)
    
    if query:
        profiles_query = profiles_query.filter(
            (ResumeProfile.display_name.contains(query)) |
            (ResumeProfile.bio.contains(query)) |
            (ResumeProfile.skills.contains(query))
        )
    
    if skills:
        profiles_query = profiles_query.filter(ResumeProfile.skills.contains(skills))
    
    profiles = profiles_query.limit(limit).all()
    
    return jsonify({
        'profiles': [p.to_dict() for p in profiles],
        'total': len(profiles)
    })

@resume_bp.route('/download/resume/<int:document_id>')
@login_required
def download_resume(document_id):
    """Download resume document (requires purchase)"""
    buyer_profile = ResumeProfile.query.filter_by(user_id=current_user.id).first()
    document = ResumeDocument.query.get_or_404(document_id)
    
    # Check if user has access
    if buyer_profile.user_type == 'jobseeker' and document.profile_id == buyer_profile.id:
        # Owner can always download their own resume
        has_access = True
    elif buyer_profile.user_type == 'employer':
        # Check if employer has purchased access
        purchase = PaymentTransaction.query.filter_by(
            buyer_profile_id=buyer_profile.id,
            recipient_profile_id=document.profile_id,
            content_type='resume',
            status='completed'
        ).first()
        has_access = purchase is not None
    else:
        has_access = False
    
    if not has_access:
        return jsonify({'error': 'Access denied'}), 403
    
    # Increment view count
    document.view_count += 1
    db.session.commit()
    
    # Decrypt and retrieve file
    try:
        decrypted_data = secure_storage.decrypt_and_retrieve_file(
            secure_filename=document.filename,
            user_id=document.profile.user_id,
            file_id=document.id,
            file_type='resume'
        )
        
        # Create a temporary response with the decrypted file
        from flask import Response
        return Response(
            decrypted_data,
            mimetype='application/octet-stream',
            headers={
                'Content-Disposition': f'attachment; filename="{document.original_filename}"',
                'Content-Length': len(decrypted_data)
            }
        )
        
    except Exception as e:
        current_app.logger.error(f"Error retrieving file {document.id}: {str(e)}")
        return jsonify({'error': 'File not available'}), 500

@resume_bp.route('/watch/video/<int:video_id>')
@login_required
def watch_video(video_id):
    """Watch video submission (requires purchase)"""
    buyer_profile = ResumeProfile.query.filter_by(user_id=current_user.id).first()
    video = VideoSubmission.query.get_or_404(video_id)
    
    # Check access similar to resume download
    if buyer_profile.user_type == 'jobseeker' and video.profile_id == buyer_profile.id:
        has_access = True
    elif buyer_profile.user_type == 'employer':
        purchase = PaymentTransaction.query.filter_by(
            buyer_profile_id=buyer_profile.id,
            recipient_profile_id=video.profile_id,
            content_type='video',
            status='completed'
        ).first()
        has_access = purchase is not None
    else:
        has_access = False
    
    if not has_access:
        return jsonify({'error': 'Access denied - purchase required'}), 403
    
    # Increment view count
    video.view_count += 1
    db.session.commit()
    
    return render_template('resume_marketplace/video_player.html', video=video)

@resume_bp.route('/stream/video/<int:video_id>')
@login_required
def stream_video(video_id):
    """Stream encrypted video content"""
    buyer_profile = ResumeProfile.query.filter_by(user_id=current_user.id).first()
    video = VideoSubmission.query.get_or_404(video_id)
    
    # Check access (same logic as watch_video)
    if buyer_profile.user_type == 'jobseeker' and video.profile_id == buyer_profile.id:
        has_access = True
    elif buyer_profile.user_type == 'employer':
        purchase = PaymentTransaction.query.filter_by(
            buyer_profile_id=buyer_profile.id,
            recipient_profile_id=video.profile_id,
            content_type='video',
            status='completed'
        ).first()
        has_access = purchase is not None
    else:
        has_access = False
    
    if not has_access:
        return jsonify({'error': 'Access denied'}), 403
    
    # Decrypt and stream video
    try:
        decrypted_data = secure_storage.decrypt_and_retrieve_file(
            secure_filename=video.filename,
            user_id=video.profile.user_id,
            file_id=video.id,
            file_type='video'
        )
        
        # Determine MIME type based on file extension
        mime_types = {
            'mp4': 'video/mp4',
            'mov': 'video/quicktime',
            'avi': 'video/x-msvideo',
            'webm': 'video/webm'
        }
        
        file_ext = video.original_filename.split('.')[-1].lower()
        mime_type = mime_types.get(file_ext, 'video/mp4')
        
        from flask import Response
        return Response(
            decrypted_data,
            mimetype=mime_type,
            headers={
                'Content-Length': len(decrypted_data),
                'Accept-Ranges': 'bytes',
                'Cache-Control': 'no-cache, no-store, must-revalidate',
                'Pragma': 'no-cache',
                'Expires': '0'
            }
        )
        
    except Exception as e:
        current_app.logger.error(f"Error streaming video {video.id}: {str(e)}")
        return jsonify({'error': 'Video not available'}), 500

@resume_bp.route('/download/video/<int:video_id>')
@login_required
def download_video(video_id):
    """Download encrypted video file"""
    buyer_profile = ResumeProfile.query.filter_by(user_id=current_user.id).first()
    video = VideoSubmission.query.get_or_404(video_id)
    
    # Check access (same logic as watch_video)
    if buyer_profile.user_type == 'jobseeker' and video.profile_id == buyer_profile.id:
        has_access = True
    elif buyer_profile.user_type == 'employer':
        purchase = PaymentTransaction.query.filter_by(
            buyer_profile_id=buyer_profile.id,
            recipient_profile_id=video.profile_id,
            content_type='video',
            status='completed'
        ).first()
        has_access = purchase is not None
    else:
        has_access = False
    
    if not has_access:
        return jsonify({'error': 'Access denied'}), 403
    
    # Decrypt and download video
    try:
        decrypted_data = secure_storage.decrypt_and_retrieve_file(
            secure_filename=video.filename,
            user_id=video.profile.user_id,
            file_id=video.id,
            file_type='video'
        )
        
        from flask import Response
        return Response(
            decrypted_data,
            mimetype='application/octet-stream',
            headers={
                'Content-Disposition': f'attachment; filename="{video.original_filename}"',
                'Content-Length': len(decrypted_data)
            }
        )
        
    except Exception as e:
        current_app.logger.error(f"Error downloading video {video.id}: {str(e)}")
        return jsonify({'error': 'Video not available'}), 500

@resume_bp.route('/track/video/<int:video_id>/event', methods=['POST'])
@login_required
def track_video_event(video_id):
    """Track video viewing events for analytics"""
    data = request.get_json()
    event = data.get('event')
    timestamp = data.get('timestamp')
    
    # Log video events (you could store these in a separate analytics table)
    current_app.logger.info(f"Video {video_id} event: {event} at {timestamp} by user {current_user.id}")
    
    return jsonify({'status': 'recorded'})

@resume_bp.route('/signup/notify', methods=['POST'])
def signup_notify():
    """Collect email addresses for launch notifications"""
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    email = data.get('email', '').strip().lower()
    user_type = data.get('userType', 'jobseeker')
    source = data.get('source', 'unknown')
    
    if not email:
        return jsonify({'error': 'Email is required'}), 400
    
    # Simple email validation
    import re
    if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
        return jsonify({'error': 'Invalid email format'}), 400
    
    # Store in a simple file for now (in production, use database)
    signup_data = {
        'email': email,
        'user_type': user_type,
        'source': source,
        'timestamp': datetime.utcnow().isoformat(),
        'ip_address': request.remote_addr
    }
    
    # Append to file
    signup_file = '/var/temp188.com/instance/launch_signups.jsonl'
    try:
        os.makedirs(os.path.dirname(signup_file), exist_ok=True)
        with open(signup_file, 'a') as f:
            f.write(json.dumps(signup_data) + '\n')
        
        current_app.logger.info(f"Launch signup: {email} ({user_type}) from {source}")
        
        return jsonify({
            'success': True,
            'message': 'You\'re on the list! We\'ll notify you when payment features launch.'
        })
        
    except Exception as e:
        current_app.logger.error(f"Error saving signup: {str(e)}")
        return jsonify({'error': 'Failed to save signup'}), 500

