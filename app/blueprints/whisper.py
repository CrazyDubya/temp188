"""
Whisper Blueprint - Text-to-Speech, Speech-to-Text, and Translation Service
Features: TTS (gTTS, Edge-TTS), STT (Whisper), Translation, Unified Workflows
"""

from flask import Blueprint, render_template, request, jsonify, send_file
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from gtts import gTTS
import edge_tts
from faster_whisper import WhisperModel
from deep_translator import GoogleTranslator
import asyncio
import os
import hashlib
import time
from datetime import datetime
import json
from werkzeug.utils import secure_filename

# Import Celery for async tasks
try:
    from celery_app import celery_app
    from blueprints.tasks import transcribe_audio_task
    CELERY_AVAILABLE = True
except ImportError:
    CELERY_AVAILABLE = False
    transcribe_audio_task = None

whisper_bp = Blueprint('whisper', __name__, template_folder='../templates')

# Configuration
AUDIO_FOLDER = '/var/temp188.com/static/whisper_audio'
UPLOAD_FOLDER = '/var/temp188.com/static/whisper_uploads'
MAX_TEXT_LENGTH = 3000
MAX_UPLOAD_SIZE = 25 * 1024 * 1024  # 25MB
ALLOWED_AUDIO_EXTENSIONS = {'mp3', 'wav', 'ogg', 'm4a', 'flac', 'webm'}

# Ensure directories exist
os.makedirs(AUDIO_FOLDER, exist_ok=True)
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Initialize rate limiter
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["100 per hour"],
    storage_uri="memory://"
)

# Load Whisper model (lazy loading)
_whisper_model = None

def get_whisper_model():
    """Lazy load Whisper model with faster-whisper (CPU optimized)"""
    global _whisper_model
    if _whisper_model is None:
        # faster-whisper with int8 quantization for 4x speedup on CPU
        _whisper_model = WhisperModel(
            "tiny",
            device="cpu",
            compute_type="int8",  # 8-bit quantization for speed
            cpu_threads=2,  # Match hardware (2-core CPU)
            num_workers=1  # Single worker to avoid CPU overload
        )
    return _whisper_model

# Available voice accents/languages (reads text in that accent, does not translate)
GTTS_LANGUAGES = {
    'en': 'English (US/UK)',
    'en-us': 'English (US)',
    'en-gb': 'English (UK)',
    'en-au': 'English (Australia)',
    'es': 'Spanish',
    'fr': 'French',
    'de': 'German',
    'it': 'Italian',
    'pt': 'Portuguese',
    'ru': 'Russian',
    'ja': 'Japanese',
    'ko': 'Korean',
    'zh-CN': 'Chinese',
    'ar': 'Arabic',
    'hi': 'Hindi'
}

EDGE_VOICES = {
    'en-US-GuyNeural': 'English (US) - Guy (Male)',
    'en-US-JennyNeural': 'English (US) - Jenny (Female)',
    'en-GB-RyanNeural': 'English (UK) - Ryan (Male)',
    'en-GB-SoniaNeural': 'English (UK) - Sonia (Female)',
    'en-AU-WilliamNeural': 'English (Australia) - William (Male)',
    'en-AU-NatashaNeural': 'English (Australia) - Natasha (Female)',
    'es-ES-AlvaroNeural': 'Spanish (Spain) - Alvaro (Male)',
    'es-ES-ElviraNeural': 'Spanish (Spain) - Elvira (Female)',
    'fr-FR-HenriNeural': 'French - Henri (Male)',
    'fr-FR-DeniseNeural': 'French - Denise (Female)',
    'de-DE-ConradNeural': 'German - Conrad (Male)',
    'de-DE-KatjaNeural': 'German - Katja (Female)',
}

# Translation language mapping
TRANSLATION_LANGUAGES = {
    'en': 'English',
    'es': 'Spanish',
    'fr': 'French',
    'de': 'German',
    'it': 'Italian',
    'pt': 'Portuguese',
    'ru': 'Russian',
    'ja': 'Japanese',
    'ko': 'Korean',
    'zh-CN': 'Chinese',
    'ar': 'Arabic',
    'hi': 'Hindi',
    'nl': 'Dutch',
    'pl': 'Polish',
    'tr': 'Turkish'
}

@whisper_bp.route('/')
def index():
    """Whisper TTS landing page"""
    return render_template('whisper/index.html',
                          gtts_languages=GTTS_LANGUAGES,
                          edge_voices=EDGE_VOICES,
                          translation_languages=TRANSLATION_LANGUAGES)

@whisper_bp.route('/api/tts', methods=['POST'])
@limiter.limit("50 per hour")
def text_to_speech():
    """Convert text to speech using gTTS or Edge-TTS"""
    try:
        data = request.get_json()

        if not data or not data.get('text'):
            return jsonify({'error': 'Text is required'}), 400

        text = data.get('text', '').strip()
        engine = data.get('engine', 'gtts')
        voice = data.get('voice', 'en')
        speed = float(data.get('speed', 1.0))

        # Validate text length
        if len(text) > MAX_TEXT_LENGTH:
            return jsonify({'error': f'Text exceeds maximum length of {MAX_TEXT_LENGTH} characters'}), 400

        if len(text) == 0:
            return jsonify({'error': 'Text cannot be empty'}), 400

        # Generate unique filename
        content_hash = hashlib.md5(f"{text}{engine}{voice}{speed}".encode()).hexdigest()[:12]
        timestamp = int(time.time())
        filename = f"tts_{content_hash}_{timestamp}.mp3"
        filepath = os.path.join(AUDIO_FOLDER, filename)

        # Generate speech
        if engine == 'gtts':
            if voice not in GTTS_LANGUAGES:
                voice = 'en'
            tts = gTTS(text=text, lang=voice, slow=(speed < 1.0))
            tts.save(filepath)

        elif engine == 'edge':
            if voice not in EDGE_VOICES:
                voice = 'en-US-GuyNeural'
            asyncio.run(generate_edge_tts(text, voice, speed, filepath))

        else:
            return jsonify({'error': 'Invalid engine specified'}), 400

        # Save metadata
        metadata = {
            'text': text,
            'engine': engine,
            'voice': voice,
            'speed': speed,
            'filename': filename,
            'timestamp': timestamp,
            'char_count': len(text),
            'ip': request.remote_addr
        }

        metadata_file = filepath.replace('.mp3', '.json')
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)

        audio_url = f"/static/whisper_audio/{filename}"

        return jsonify({
            'success': True,
            'audio_url': audio_url,
            'filename': filename,
            'char_count': len(text),
            'duration_estimate': estimate_duration(text)
        })

    except Exception as e:
        return jsonify({'error': f'Server error: {str(e)}'}), 500

@whisper_bp.route('/api/stt', methods=['POST'])
@limiter.limit("20 per hour")
def speech_to_text():
    """Convert speech to text using Whisper"""
    try:
        if 'audio' not in request.files:
            return jsonify({'error': 'No audio file provided'}), 400

        audio_file = request.files['audio']

        if audio_file.filename == '':
            return jsonify({'error': 'No file selected'}), 400

        # Validate file extension
        if not allowed_file(audio_file.filename):
            return jsonify({'error': f'Invalid file type. Allowed: {", ".join(ALLOWED_AUDIO_EXTENSIONS)}'}), 400

        # Save upload
        filename = secure_filename(audio_file.filename)
        timestamp = int(time.time())
        unique_filename = f"upload_{timestamp}_{filename}"
        filepath = os.path.join(UPLOAD_FOLDER, unique_filename)
        audio_file.save(filepath)

        # Transcribe using faster-whisper (optimized for CPU)
        model = get_whisper_model()
        segments, info = model.transcribe(filepath, beam_size=1)  # beam_size=1 for speed

        # Collect all segments into full text
        transcribed_text = " ".join([segment.text for segment in segments]).strip()
        detected_language = info.language

        # Save metadata
        metadata = {
            'original_filename': filename,
            'transcribed_text': transcribed_text,
            'detected_language': detected_language,
            'timestamp': timestamp,
            'ip': request.remote_addr
        }

        metadata_file = filepath.replace(os.path.splitext(filename)[1], '.json')
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)

        # Clean up audio file
        os.remove(filepath)

        return jsonify({
            'success': True,
            'text': transcribed_text,
            'language': detected_language,
            'char_count': len(transcribed_text)
        })

    except Exception as e:
        return jsonify({'error': f'Server error: {str(e)}'}), 500

@whisper_bp.route('/api/stt-async', methods=['POST'])
@limiter.limit("20 per hour")
def speech_to_text_async():
    """
    Async STT endpoint - submits transcription job to Celery queue
    Returns job_id immediately for status polling
    """
    if not CELERY_AVAILABLE:
        return jsonify({'error': 'Async processing not available. Celery not configured.'}), 503

    try:
        if 'audio' not in request.files:
            return jsonify({'error': 'No audio file provided'}), 400

        audio_file = request.files['audio']

        if audio_file.filename == '':
            return jsonify({'error': 'No file selected'}), 400

        # Validate file extension
        if not allowed_file(audio_file.filename):
            return jsonify({'error': f'Invalid file type. Allowed: {", ".join(ALLOWED_AUDIO_EXTENSIONS)}'}), 400

        # Save upload
        filename = secure_filename(audio_file.filename)
        timestamp = int(time.time())
        unique_filename = f"upload_{timestamp}_{filename}"
        filepath = os.path.join(UPLOAD_FOLDER, unique_filename)
        audio_file.save(filepath)

        # Submit to Celery queue
        task = transcribe_audio_task.apply_async(args=[filepath])

        return jsonify({
            'success': True,
            'job_id': task.id,
            'status': 'PENDING',
            'message': 'Transcription job submitted. Poll /api/stt/status/<job_id> for results.'
        })

    except Exception as e:
        return jsonify({'error': f'Server error: {str(e)}'}), 500

@whisper_bp.route('/api/stt/status/<task_id>', methods=['GET'])
def get_stt_status(task_id):
    """
    Get status of async STT job
    Returns: PENDING, PROGRESS, SUCCESS, or FAILURE with results/error
    """
    if not CELERY_AVAILABLE:
        return jsonify({'error': 'Async processing not available'}), 503

    try:
        from celery.result import AsyncResult
        task = AsyncResult(task_id, app=celery_app)

        if task.state == 'PENDING':
            response = {
                'state': task.state,
                'status': 'Job is queued or does not exist',
                'success': False
            }
        elif task.state == 'PROGRESS':
            response = {
                'state': task.state,
                'status': task.info.get('status', 'Processing...'),
                'success': False
            }
        elif task.state == 'SUCCESS':
            response = {
                'state': task.state,
                'success': True,
                'text': task.result['transcribed_text'],
                'language': task.result['detected_language'],
                'char_count': task.result['char_count']
            }
        elif task.state == 'FAILURE':
            response = {
                'state': task.state,
                'success': False,
                'error': str(task.info)
            }
        else:
            response = {
                'state': task.state,
                'status': 'Unknown state',
                'success': False
            }

        return jsonify(response)

    except Exception as e:
        return jsonify({'error': f'Status check error: {str(e)}'}), 500

@whisper_bp.route('/api/translate', methods=['POST'])
@limiter.limit("100 per hour")
def translate_text():
    """Translate text using Google Translator"""
    try:
        data = request.get_json()

        if not data or not data.get('text'):
            return jsonify({'error': 'Text is required'}), 400

        text = data.get('text', '').strip()
        source_lang = data.get('source', 'auto')
        target_lang = data.get('target', 'en')

        if len(text) > MAX_TEXT_LENGTH:
            return jsonify({'error': f'Text exceeds maximum length of {MAX_TEXT_LENGTH} characters'}), 400

        # Translate
        translator = GoogleTranslator(source=source_lang, target=target_lang)
        translated = translator.translate(text)

        return jsonify({
            'success': True,
            'translated_text': translated,
            'source_lang': source_lang,
            'target_lang': target_lang,
            'char_count': len(translated)
        })

    except Exception as e:
        return jsonify({'error': f'Translation error: {str(e)}'}), 500

@whisper_bp.route('/api/workflow', methods=['POST'])
@limiter.limit("10 per hour")
def unified_workflow():
    """
    Unified workflow: STT → Translation → TTS
    Upload audio → transcribe → translate → generate speech
    """
    try:
        # Step 1: Speech to Text
        if 'audio' not in request.files:
            return jsonify({'error': 'No audio file provided'}), 400

        audio_file = request.files['audio']
        target_lang = request.form.get('target_lang', 'en')
        tts_voice = request.form.get('tts_voice', 'en')
        tts_engine = request.form.get('tts_engine', 'gtts')

        # Save and transcribe
        filename = secure_filename(audio_file.filename)
        timestamp = int(time.time())
        filepath = os.path.join(UPLOAD_FOLDER, f"workflow_{timestamp}_{filename}")
        audio_file.save(filepath)

        model = get_whisper_model()
        segments, info = model.transcribe(filepath, beam_size=1)
        original_text = " ".join([segment.text for segment in segments]).strip()
        detected_lang = info.language

        # Step 2: Translation (if needed)
        if target_lang != detected_lang and target_lang != 'auto':
            translator = GoogleTranslator(source=detected_lang, target=target_lang)
            translated_text = translator.translate(original_text)
        else:
            translated_text = original_text

        # Step 3: Text to Speech
        content_hash = hashlib.md5(f"{translated_text}{tts_engine}{tts_voice}".encode()).hexdigest()[:12]
        tts_filename = f"workflow_tts_{content_hash}_{timestamp}.mp3"
        tts_filepath = os.path.join(AUDIO_FOLDER, tts_filename)

        if tts_engine == 'gtts':
            tts = gTTS(text=translated_text, lang=tts_voice)
            tts.save(tts_filepath)
        else:
            asyncio.run(generate_edge_tts(translated_text, tts_voice, 1.0, tts_filepath))

        # Clean up upload
        os.remove(filepath)

        return jsonify({
            'success': True,
            'original_text': original_text,
            'detected_language': detected_lang,
            'translated_text': translated_text,
            'target_language': target_lang,
            'audio_url': f"/static/whisper_audio/{tts_filename}",
            'filename': tts_filename
        })

    except Exception as e:
        return jsonify({'error': f'Workflow error: {str(e)}'}), 500

async def generate_edge_tts(text: str, voice: str, rate: float, output_file: str):
    """Generate TTS using Edge-TTS"""
    rate_str = f"+{int((rate - 1.0) * 100)}%" if rate >= 1.0 else f"{int((rate - 1.0) * 100)}%"
    communicate = edge_tts.Communicate(text, voice, rate=rate_str)
    await communicate.save(output_file)

def estimate_duration(text: str) -> float:
    """Estimate audio duration in seconds"""
    words = len(text.split())
    return round((words / 150) * 60, 1)

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_AUDIO_EXTENSIONS

@whisper_bp.route('/api/voices')
def get_voices():
    """Get available voices for both engines"""
    return jsonify({
        'gtts': GTTS_LANGUAGES,
        'edge': EDGE_VOICES,
        'translation': TRANSLATION_LANGUAGES
    })

@whisper_bp.route('/api/cleanup', methods=['POST'])
def cleanup_old_files():
    """Clean up audio files older than 24 hours"""
    try:
        current_time = time.time()
        deleted_count = 0

        for folder in [AUDIO_FOLDER, UPLOAD_FOLDER]:
            for filename in os.listdir(folder):
                filepath = os.path.join(folder, filename)

                if os.path.isfile(filepath):
                    file_age = current_time - os.path.getmtime(filepath)

                    if file_age > 86400:  # 24 hours
                        os.remove(filepath)
                        deleted_count += 1

        return jsonify({
            'success': True,
            'deleted_count': deleted_count
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@whisper_bp.route('/history')
def history():
    """View recent TTS generations"""
    try:
        audio_files = []

        for filename in os.listdir(AUDIO_FOLDER):
            if filename.endswith('.json'):
                filepath = os.path.join(AUDIO_FOLDER, filename)
                with open(filepath, 'r') as f:
                    metadata = json.load(f)
                    audio_files.append(metadata)

        audio_files.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
        audio_files = audio_files[:50]

        return render_template('whisper/history.html', audio_files=audio_files)

    except Exception as e:
        return render_template('whisper/history.html', audio_files=[], error=str(e))

@whisper_bp.route('/about')
def about():
    """About Whisper TTS/STT"""
    return render_template('whisper/about.html')
