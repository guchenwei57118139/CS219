"""Small Agents SDK helpers for the NRF workflow."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, List, Optional

try:
    from dotenv import load_dotenv
    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False

from agents import Agent, ModelSettings, OpenAIProvider, RunConfig, Runner

DEFAULT_MODEL = os.environ.get("LLM_MODEL", "gpt-4o")


def load_environment() -> None:
    """Load environment variables from the repo .env if present."""
    if not DOTENV_AVAILABLE:
        return

    try:
        project_root = Path(__file__).resolve().parents[2]
        env_file = project_root / ".env"
        if env_file.exists():
            load_dotenv(env_file, override=False)
        else:
            load_dotenv(override=False)
    except (PermissionError, OSError, Exception):
        pass


def build_run_config(*, workflow_name: str, model: Optional[str] = None) -> RunConfig:
    """Build an OpenAI-backed run configuration."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Set OPENAI_API_KEY in environment")

    return RunConfig(
        model_provider=OpenAIProvider(api_key=api_key),
        model_settings=ModelSettings(temperature=0.1),
        workflow_name=workflow_name,
    )


def run_text_agent(
    *,
    agent_name: str,
    instructions: str,
    prompt: str,
    workflow_name: str,
    model: Optional[str] = None,
) -> str:
    """Run a single-shot text agent and return its output."""
    load_environment()
    active_model = model or DEFAULT_MODEL
    agent = Agent(
        name=agent_name,
        instructions=instructions,
        model=active_model,
        output_type=str,
        model_settings=ModelSettings(temperature=0.1),
    )
    result = Runner.run_sync(
        agent,
        prompt,
        run_config=build_run_config(workflow_name=workflow_name, model=active_model),
    )
    return result.final_output_as(str)

