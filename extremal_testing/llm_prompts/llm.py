"""
LLM wrapper for extremal_testing supporting both Google GenAI and OpenAI.
Uses the same interface pattern for both providers.
Adds retry/polling on transient errors (rate limit, network).
"""
import os
import time
from pathlib import Path
from typing import List, Dict, Any, Optional, Literal

try:
    from dotenv import load_dotenv
    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False

try:
    import google.genai as genai
    from google.genai.types import GenerateContentConfig
    GOOGLE_GENAI_AVAILABLE = True
except ImportError:
    GOOGLE_GENAI_AVAILABLE = False

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

# =========== Load Environment Variables ===========

def _load_env_file() -> None:
    """Load environment variables from .env file in project root."""
    if not DOTENV_AVAILABLE:
        return
    
    try:
        project_root = Path(__file__).resolve().parents[1]
        env_file = project_root / ".env"
        if env_file.exists():
            load_dotenv(env_file, override=False)
        else:
            load_dotenv(override=False)  # Try default locations
    except (PermissionError, OSError, Exception):
        # Silently fail - environment variables may already be set or .env file not accessible
        pass

_load_env_file()

# =========== Constants ===========

DEFAULT_PROVIDER = os.environ.get("LLM_PROVIDER", "google").lower()
DEFAULT_GOOGLE_MODEL = os.environ.get("LLM_MODEL", "gemini-2.0-flash")
DEFAULT_OPENAI_MODEL = os.environ.get("LLM_MODEL", "gpt-4o")

# =========== Provider Detection and Client Creation ===========

def _get_google_client() -> Any:
    """Build Google GenAI client using API key from environment."""
    api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("Set GOOGLE_API_KEY or GEMINI_API_KEY in environment")
    
    masked_key = api_key[:4] + "..." + api_key[-4:] if len(api_key) > 8 else "****"
    print(f"Using Google GenAI API key: {masked_key}")
    return genai.Client(api_key=api_key)


def _get_openai_client() -> Any:
    """Build OpenAI client using API key from environment."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Set OPENAI_API_KEY in environment")
    
    masked_key = api_key[:4] + "..." + api_key[-4:] if len(api_key) > 8 else "****"
    print(f"Using OpenAI API key: {masked_key}")
    return OpenAI(api_key=api_key)


def _get_provider() -> Literal["google", "openai"]:
    """Determine which LLM provider to use based on environment or default."""
    provider = os.environ.get("LLM_PROVIDER", DEFAULT_PROVIDER).lower()
    
    if provider not in ["google", "openai"]:
        raise ValueError(f"LLM_PROVIDER must be 'google' or 'openai', got: {provider}")
    
    if provider == "google" and not GOOGLE_GENAI_AVAILABLE:
        raise RuntimeError("Google GenAI not available. Install with: pip install google-genai")
    
    if provider == "openai" and not OPENAI_AVAILABLE:
        raise RuntimeError("OpenAI not available. Install with: pip install openai")
    
    return provider


def _get_model_for_provider(provider: Literal["google", "openai"], model: Optional[str] = None) -> str:
    """Get the model name for the specified provider."""
    if model:
        return model
    
    if provider == "google":
        return DEFAULT_GOOGLE_MODEL
    else:
        return DEFAULT_OPENAI_MODEL

# =========== LLM Wrapper Class ===========

class GPT:
    """
    Unified LLM wrapper supporting both Google GenAI and OpenAI.
    - Constructor: GPT(system_prompt=..., provider="google"|"openai", model=...)
    - ask_llm(prompt, use_history=False) -> raw text (str)
    """

    def __init__(
        self,
        system_prompt: str,
        provider: Optional[Literal["google", "openai"]] = None,
        model: Optional[str] = None,
        max_retries: int = 3,
        retry_delay_seconds: float = 2.0,
    ):
        self.system_prompt = system_prompt
        self.provider = provider or _get_provider()
        self.model = _get_model_for_provider(self.provider, model)
        self.max_retries = max_retries
        self.retry_delay_seconds = retry_delay_seconds
        self._history: List[Dict[str, Any]] = []
        
        if self.provider == "google":
            self._client = _get_google_client()
        else:
            self._client = _get_openai_client()

    def ask_llm(self, prompt: str, use_history: bool = False) -> str:
        """
        Send prompt to the model and return raw response text.
        Retries on transient errors (rate limit, network) up to max_retries with delay.
        If use_history=True, appends user/model to history only on success so retries use same state.
        """
        if self.provider == "google":
            return self._ask_google_llm(prompt, use_history)
        else:
            return self._ask_openai_llm(prompt, use_history)

    def _ask_google_llm(self, prompt: str, use_history: bool) -> str:
        """Send prompt to Google GenAI model."""
        config = GenerateContentConfig(
            system_instruction=self.system_prompt,
            temperature=0.1,
        )
        user_message = {"role": "user", "parts": [{"text": prompt}]}
        
        if use_history:
            contents = self._history + [user_message]
        else:
            contents = [user_message]

        last_error = None
        for attempt in range(self.max_retries):
            try:
                response = self._client.models.generate_content(
                    model=self.model,
                    config=config,
                    contents=contents,
                )
                response_text = response.text or ""
                
                if use_history:
                    self._history.append(user_message)
                    self._history.append({"role": "model", "parts": [{"text": response_text}]})
                
                return response_text
            except Exception as error:
                last_error = error
                if attempt + 1 < self.max_retries:
                    time.sleep(self.retry_delay_seconds)
                    continue
                raise last_error
        
        raise last_error

    def _ask_openai_llm(self, prompt: str, use_history: bool) -> str:
        """Send prompt to OpenAI model."""
        messages: List[Dict[str, str]] = [{"role": "system", "content": self.system_prompt}]
        
        if use_history:
            for history_item in self._history:
                if history_item.get("role") == "user":
                    messages.append({"role": "user", "content": history_item.get("content", "")})
                elif history_item.get("role") == "assistant":
                    messages.append({"role": "assistant", "content": history_item.get("content", "")})
        
        messages.append({"role": "user", "content": prompt})

        last_error = None
        use_temperature = True
        
        for attempt in range(self.max_retries):
            try:
                request_params = {
                    "model": self.model,
                    "messages": messages,
                }
                if use_temperature and not self.model.startswith("o1"):
                    request_params["temperature"] = 0.1
                
                response = self._client.chat.completions.create(**request_params)
                response_text = response.choices[0].message.content or ""
                
                if use_history:
                    self._history.append({"role": "user", "content": prompt})
                    self._history.append({"role": "assistant", "content": response_text})
                
                return response_text
            except Exception as error:
                last_error = error
                # If temperature error, retry without temperature
                if "temperature" in str(error).lower() and use_temperature:
                    use_temperature = False
                    continue
                if attempt + 1 < self.max_retries:
                    time.sleep(self.retry_delay_seconds)
                    continue
                raise last_error
        
        raise last_error
