"""
Celery tasks for Whisper STT processing
"""

import os
from celery_app import celery_app

# Import the get_whisper_model function
import sys
sys.path.insert(0, '/var/temp188.com')

@celery_app.task(bind=True, name='whisper.transcribe_audio')
def transcribe_audio_task(self, filepath):
    """
    Async Celery task for STT processing
    Returns: dict with transcribed_text, detected_language, char_count
    """
    # Lazy import to avoid circular dependencies
    from blueprints.whisper import get_whisper_model

    try:
        # Update task state to PROGRESS
        self.update_state(state='PROGRESS', meta={'status': 'Loading Whisper model...'})

        # Get model and transcribe
        model = get_whisper_model()
        self.update_state(state='PROGRESS', meta={'status': 'Transcribing audio...'})

        segments, info = model.transcribe(filepath, beam_size=1)
        transcribed_text = " ".join([segment.text for segment in segments]).strip()
        detected_language = info.language

        # Clean up uploaded file
        if os.path.exists(filepath):
            os.remove(filepath)

        return {
            'transcribed_text': transcribed_text,
            'detected_language': detected_language,
            'char_count': len(transcribed_text)
        }
    except Exception as e:
        # Clean up on error
        if os.path.exists(filepath):
            os.remove(filepath)
        raise e
