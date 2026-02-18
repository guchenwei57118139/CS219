"""
LLM wrapper for extremal_testing (generate_tests.py, parse.py).
Uses Google GenAI (google.genai) with the same interface pattern as ORAN_bug_LLManalysis/run.py.
Adds retry/polling on transient errors (rate limit, network).
"""
from pathlib import Path
import os
import time
import google.genai as genai
from google.genai.types import GenerateContentConfig


def _get_client():
    """Build GenAI client. Prefer GOOGLE_API_KEY env."""
    api_key="AIzaSyBvGKGE9eDOmbK7fFm5BMMYFA-JkU5duOA"
    #api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    print(api_key)
    print("Using GenAI API key:", api_key[:4] + "..." + api_key[-4:])
    if not api_key:
        raise RuntimeError("Set GOOGLE_API_KEY or GEMINI_API_KEY in environment")
    return genai.Client(api_key=api_key)


def _get_model():
    """Model name; override with LLM_MODEL env."""
    return os.environ.get("LLM_MODEL", "gemini-2.0-flash")


class GPT:
    """
    Wrapper for generate_tests.py / parse.py.
    - Constructor: GPT(system_prompt=...)
    - ask_llm(prompt, use_history=False) -> raw text (str)
    """

    def __init__(
        self,
        system_prompt: str,
        model: str | None = None,
        max_retries: int = 3,
        retry_delay_seconds: float = 2.0,
    ):
        self.system_prompt = system_prompt
        self.model = model or _get_model()
        self._client = _get_client()
        self._history = []
        self.max_retries = max_retries
        self.retry_delay_seconds = retry_delay_seconds

    def ask_llm(self, prompt: str, use_history: bool = False) -> str:
        """
        Send prompt to the model and return raw response text.
        Retries on transient errors (rate limit, network) up to max_retries with delay.
        If use_history=True, appends user/model to history only on success so retries use same state.
        """
        cfg = GenerateContentConfig(
            system_instruction=self.system_prompt,
            temperature=0.1,
        )
        user_part = {"role": "user", "parts": [{"text": prompt}]}
        if use_history:
            contents = self._history + [user_part]
        else:
            contents = [user_part]

        last_error = None
        for attempt in range(self.max_retries):
            try:
                resp = self._client.models.generate_content(
                    model=self.model,
                    config=cfg,
                    contents=contents,
                )
                text = resp.text or ""
                if use_history:
                    self._history.append(user_part)
                    self._history.append({"role": "model", "parts": [{"text": text}]})
                return text
            except Exception as e:
                last_error = e
                if attempt + 1 < self.max_retries:
                    time.sleep(self.retry_delay_seconds)
                    continue
                raise last_error
        raise last_error