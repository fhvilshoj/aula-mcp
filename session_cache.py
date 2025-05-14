"""
Session cache manager for Aula MCP client
"""
import os
import json
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import pickle
import base64

_LOGGER = logging.getLogger(__name__)

class SessionCache:
    """Class for managing Aula session persistence"""
    
    def __init__(self, cache_dir: str = None):
        """Initialize the session cache
        
        Args:
            cache_dir: Directory to store cache files (defaults to ~/.aula)
        """
        self.cache_dir = cache_dir or os.path.expanduser("~/.aula")
        self.cache_file = os.path.join(self.cache_dir, "session_cache.json")
        
        # Ensure cache directory exists
        os.makedirs(self.cache_dir, exist_ok=True)
    
    def save_session(self, session: Dict[str, Any]) -> bool:
        """Save a session to the cache
        
        Args:
            session: The session data dictionary to save
            
        Returns:
            bool: True if successful
        """
        try:
            # Need to serialize complex objects that aren't JSON serializable
            # Convert datetime objects to ISO strings
            if "tokens" in session:
                for widget_id, token_data in session["tokens"].items():
                    if isinstance(token_data, dict) and "timestamp" in token_data and isinstance(token_data["timestamp"], datetime):
                        token_data["timestamp"] = token_data["timestamp"].isoformat()
            
            # Save to file with timestamp
            cache_data = {
                "timestamp": datetime.now().isoformat(),
                "session": session
            }
            
            with open(self.cache_file, 'w') as f:
                json.dump(cache_data, f)
                
            _LOGGER.debug(f"Session saved to {self.cache_file}")
            return True
        except Exception as e:
            _LOGGER.error(f"Failed to save session: {e}")
            return False
    
    def load_session(self, max_age_hours: int = 12) -> Optional[Dict[str, Any]]:
        """Load a session from the cache if available and not expired
        
        Args:
            max_age_hours: Maximum age of the session in hours
            
        Returns:
            Optional[Dict[str, Any]]: Session data or None if not found/expired
        """
        if not os.path.exists(self.cache_file):
            _LOGGER.debug("No session cache file found")
            return None
            
        try:
            with open(self.cache_file, 'r') as f:
                cache_data = json.load(f)
                
            # Check if cache is expired
            cache_time = datetime.fromisoformat(cache_data["timestamp"])
            if datetime.now() - cache_time > timedelta(hours=max_age_hours):
                _LOGGER.debug(f"Session cache expired (older than {max_age_hours} hours)")
                return None
                
            _LOGGER.debug("Loaded session from cache")
            return cache_data["session"]
        except Exception as e:
            _LOGGER.error(f"Failed to load session: {e}")
            return None
    
    def clear_cache(self) -> bool:
        """Clear the session cache
        
        Returns:
            bool: True if successful
        """
        if os.path.exists(self.cache_file):
            try:
                os.remove(self.cache_file)
                _LOGGER.debug("Session cache cleared")
                return True
            except Exception as e:
                _LOGGER.error(f"Failed to clear session cache: {e}")
                
        return False 