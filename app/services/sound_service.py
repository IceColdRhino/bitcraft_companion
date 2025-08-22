"""
Sound service for BitCraft Companion.

Manages sound playback for notification customization using pygame.
Handles loading, caching, and playing sound files from the sounds directory.
"""

import logging
import os
import threading
from typing import Dict, List, Optional
import pygame


class SoundService:
    """
    Service for managing notification sound playback.
    
    Features:
    - Load and cache sound files from sounds directory
    - Play sounds asynchronously to avoid UI blocking
    - Support for multiple audio formats (wav, mp3, ogg)
    - Graceful error handling for missing/corrupt files
    """
    
    def __init__(self):
        """Initialize the sound service and pygame mixer."""
        self._sounds_cache: Dict[str, pygame.mixer.Sound] = {}
        self._sounds_directory = None
        self._mixer_initialized = False
        
        self._init_mixer()
        self._load_sounds_directory()
        
        if not (self._mixer_initialized and self._sounds_directory):
            logging.warning("SoundService initialized with limited functionality")
    
    def _init_mixer(self):
        """Initialize pygame mixer with appropriate settings."""
        try:
            pygame.mixer.pre_init(frequency=22050, size=-16, channels=2, buffer=512)
            pygame.mixer.init()
            self._mixer_initialized = True
        except pygame.error as e:
            logging.error(f"Failed to initialize pygame mixer: {e}")
            self._mixer_initialized = False
        except Exception as e:
            logging.error(f"Unexpected error initializing pygame mixer: {e}")
            self._mixer_initialized = False
    
    def _load_sounds_directory(self):
        """Find and set the sounds directory path."""
        try:
            current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            sounds_dir = os.path.join(current_dir, "ui", "sounds")
            
            if os.path.exists(sounds_dir) and os.path.isdir(sounds_dir):
                self._sounds_directory = sounds_dir
            else:
                logging.warning(f"Sounds directory not found at: {sounds_dir}")
        except Exception as e:
            logging.error(f"Error finding sounds directory: {e}")
    
    def get_available_sounds(self) -> List[str]:
        """
        Get list of available sound files.
        
        Returns:
            List of sound filenames (without path)
        """
        if not self._sounds_directory:
            return []
        
        try:
            sound_files = []
            supported_extensions = {'.wav', '.mp3', '.ogg'}
            
            for filename in os.listdir(self._sounds_directory):
                if any(filename.lower().endswith(ext) for ext in supported_extensions):
                    sound_files.append(filename)
            
            sound_files.sort()  # Sort alphabetically
            return sound_files
            
        except Exception as e:
            logging.error(f"Error listing sound files: {e}")
            return []
    
    def get_sound_display_name(self, filename: str) -> str:
        """
        Get a friendly display name for a sound file.
        
        Args:
            filename: Sound filename
            
        Returns:
            Friendly display name
        """
        if not filename:
            return "None (Silent)"
        
        name = os.path.splitext(filename)[0]
        name = name.replace('_', ' ').replace('-', ' ')
        name = name.title()
        name_mappings = {
            'Jobs Done': 'Jobs Done',
            'Mystic Chimes': 'Mystic Chimes',
            'Piano': 'Piano',
            'Notification': 'Notification',
            'Confirmation': 'Confirmation'
        }
        
        return name_mappings.get(name, name)
    
    def _load_sound(self, filename: str) -> Optional[pygame.mixer.Sound]:
        """
        Load a sound file and cache it.
        
        Args:
            filename: Sound filename
            
        Returns:
            pygame Sound object or None if failed
        """
        if not self._mixer_initialized or not self._sounds_directory:
            return None
        
        if filename in self._sounds_cache:
            return self._sounds_cache[filename]
        
        try:
            sound_path = os.path.join(self._sounds_directory, filename)
            if not os.path.exists(sound_path):
                logging.warning(f"Sound file not found: {sound_path}")
                return None
            
            sound = pygame.mixer.Sound(sound_path)
            self._sounds_cache[filename] = sound
            return sound
            
        except pygame.error as e:
            logging.error(f"Pygame error loading sound '{filename}': {e}")
            return None
        except Exception as e:
            logging.error(f"Error loading sound '{filename}': {e}")
            return None
    
    def play_sound(self, filename: str, blocking: bool = False):
        """
        Play a sound file.
        
        Args:
            filename: Sound filename to play
            blocking: If True, wait for sound to finish playing
        """
        if not filename or filename == "none":
            return
        
        if not self._mixer_initialized:
            return
        
        def _play_sound_thread():
            """Thread function to play sound without blocking UI."""
            try:
                sound = self._load_sound(filename)
                if sound:
                    sound.play()
                else:
                    logging.warning(f"Failed to play sound: {filename}")
            except Exception as e:
                logging.error(f"Error playing sound '{filename}': {e}")
        
        if blocking:
            _play_sound_thread()
        else:
            sound_thread = threading.Thread(target=_play_sound_thread, daemon=True)
            sound_thread.start()
    
    def test_sound(self, filename: str):
        """
        Test play a sound file (same as play_sound but explicit for testing).
        
        Args:
            filename: Sound filename to test
        """
        self.play_sound(filename, blocking=False)
    
    def stop_all_sounds(self):
        """Stop all currently playing sounds."""
        if self._mixer_initialized:
            try:
                pygame.mixer.stop()
            except Exception as e:
                logging.error(f"Error stopping sounds: {e}")
    
    def cleanup(self):
        """Clean up resources."""
        try:
            if self._mixer_initialized:
                pygame.mixer.quit()
                self._mixer_initialized = False
                
            self._sounds_cache.clear()
            
        except Exception as e:
            logging.error(f"Error during sound service cleanup: {e}")