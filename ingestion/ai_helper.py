import os
import warnings
from abc import ABC, abstractmethod
from typing import Dict, Optional, Type

# Attempt to import local AI libraries
LOCAL_AI_AVAILABLE = True  # Assuming available, validated on first use



# Suppress library warnings
warnings.filterwarnings("ignore")


class MediaHandler(ABC):
    """Base strategy for handling different media types."""
    
    @abstractmethod
    def process(self, file_path: str) -> str:
        """Process the file and return a textual description."""
        pass


class ImageHandler(MediaHandler):
    """Handles image captioning using BLIP."""
    _processor = None
    _model = None

    @classmethod
    def load_model(cls):
        """Lazy load the vision model."""
        global LOCAL_AI_AVAILABLE
        if cls._model is None and LOCAL_AI_AVAILABLE:
            print("Loading Image Captioning Model (BLIP)...")
            try:
                from transformers import BlipProcessor, BlipForConditionalGeneration
                cls._processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
                cls._model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base")
            except Exception as e:
                print(f"Failed to load image model: {e}")
                LOCAL_AI_AVAILABLE = False

    def process(self, file_path: str) -> str:
        if not LOCAL_AI_AVAILABLE:
            return "[Error: Local AI libraries missing]"
        
        self.load_model()
        if not self._model:
            return "[Error: Image model failed to load]"

        try:
            from PIL import Image
            raw_image = Image.open(file_path).convert('RGB')
            inputs = self._processor(raw_image, return_tensors="pt")
            out = self._model.generate(**inputs)
            description = self._processor.decode(out[0], skip_special_tokens=True)
            return description
        except Exception as e:
            return f"[Error processing image: {e}]"


class AudioHandler(MediaHandler):
    """Handles audio transcription using Whisper."""
    _model = None

    @classmethod
    def load_model(cls):
        """Lazy load the audio model."""
        global LOCAL_AI_AVAILABLE
        if cls._model is None and LOCAL_AI_AVAILABLE:
            print("Loading Audio Model (Whisper)...")
            try:
                import whisper
                cls._model = whisper.load_model("base")
            except Exception as e:
                print(f"Failed to load audio model: {e}")
                LOCAL_AI_AVAILABLE = False

    def process(self, file_path: str) -> str:
        if not LOCAL_AI_AVAILABLE:
            return "[Error: Local AI libraries missing]"

        self.load_model()
        if not self._model:
            return "[Error: Audio model failed to load]"

        try:
            result = self._model.transcribe(file_path)
            return f"(Audio Transcript): {result['text'].strip()}"
        except Exception as e:
            return f"[Error processing audio: {e}]"


class VideoHandler(AudioHandler):
    """Handles video by transcribing its audio track."""
    
    def process(self, file_path: str) -> str:
        # Whisper automatically extracts audio from video files via ffmpeg
        transcript = super().process(file_path)
        return transcript.replace("(Audio Transcript)", "(Video Transcript)")


class TextHandler(MediaHandler):
    """Handles plain text files by reading a preview."""
    
    def process(self, file_path: str) -> str:
        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read(500) # Read first 500 chars
                if len(content) == 500:
                    content += "..."
                return f"(Text Content): {content}"
        except Exception as e:
            return f"[Error reading text file: {e}]"


class LocalAIResolver:
    """
    Main resolver class that dispatches processing to the correct handler
    based on media type.
    """
    def __init__(self):
        self.handlers: Dict[str, MediaHandler] = {
            "image": ImageHandler(),
            "video": VideoHandler(),
            "audio": AudioHandler(),
            "text": TextHandler()
        }

    def resolve(self, file_path: str, mime_type: str = "") -> str:
        """
        Public API to describe a media file.
        """
        if not os.path.exists(file_path):
            return f"[Error: File not found] {os.path.basename(file_path)}"

        # Determine the correct handler key
        handler_key = "text" # default fallback
        if mime_type.startswith("image/"):
            handler_key = "image"
        elif mime_type.startswith("video/"):
            handler_key = "video"
        elif mime_type.startswith("audio/"):
            handler_key = "audio"
        elif mime_type.startswith("text/"):
            handler_key = "text"

        handler = self.handlers.get(handler_key)
        
        if handler:
            return handler.process(file_path)
        
        return f"Media file without handler: {os.path.basename(file_path)} ({mime_type})"


# Singleton instance
_resolver = LocalAIResolver()

def generate_media_description(file_path: str, mime_type: str = "image/jpeg") -> str:
    """
    Legacy wrapper function to maintain compatibility with existing code.
    Delegates to the AIResolver class.
    """
    return _resolver.resolve(file_path, mime_type)