"""LLM backend abstraction for cashew.

Extraction, think cycles, and dream cycles all need to call a language model.
The rest of the codebase talks to a callable `model_fn(prompt) -> str` with an
attached `.usage` dict — this module produces those callables from a backend.

Adding a new backend: subclass `LLMBackend`, implement `_generate`, register it
in `build_backend`. Default is `ClaudeCodeBackend` (headless `claude -p` under
the user's Max plan — no API keys, no gateways, no extra-usage billing).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from abc import ABC, abstractmethod
from typing import Callable, Optional


class LLMBackend(ABC):
    """Callable LLM. Subclasses implement `_generate`; the base handles usage
    accounting and exposes the conventional `model_fn(prompt) -> str` shape."""

    model: str

    def __init__(self, model: str):
        self.model = model
        self.usage = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "calls": 0,
            "model": model,
        }

    @abstractmethod
    def _generate(self, prompt: str) -> tuple[str, int, int]:
        """Return (response_text, prompt_tokens, completion_tokens)."""

    def __call__(self, prompt: str) -> str:
        text, p_tok, c_tok = self._generate(prompt)
        if p_tok <= 0:
            p_tok = len(prompt) // 4
        if c_tok <= 0:
            c_tok = len(text) // 4
        self.usage["prompt_tokens"] += p_tok
        self.usage["completion_tokens"] += c_tok
        self.usage["total_tokens"] += p_tok + c_tok
        self.usage["calls"] += 1
        return text


class ClaudeCodeBackend(LLMBackend):
    """Shell out to headless `claude -p`. Runs under the Claude Code subscription.

    Sessions are scoped to CASHEW_CLAUDE_SESSIONS_DIR (default:
    ~/.cashew/claude-sessions/) to keep inference sessions out of the user's
    project directories and prevent them from being mined on the next run.
    """

    _DEFAULT_SESSIONS_DIR = os.path.join(os.path.expanduser("~"), ".cashew", "claude-sessions")

    def __init__(self, model: Optional[str] = None):
        super().__init__(model or os.environ.get("CASHEW_CLAUDE_MODEL", "claude-haiku-4-5-20251001"))
        self._bin = shutil.which("claude")
        if not self._bin:
            raise RuntimeError("`claude` CLI not found on PATH")
        self._cwd = os.environ.get("CASHEW_CLAUDE_SESSIONS_DIR", self._DEFAULT_SESSIONS_DIR)
        os.makedirs(self._cwd, exist_ok=True)

    def _generate(self, prompt: str) -> tuple[str, int, int]:
        proc = subprocess.run(
            [self._bin, "-p",
             "--model", self.model,
             "--output-format", "json",
             "--permission-mode", "bypassPermissions"],
            input=prompt,
            capture_output=True, text=True, timeout=300,
            cwd=self._cwd,
        )
        if proc.returncode != 0:
            detail = proc.stderr[:500] or proc.stdout[:500]
            raise RuntimeError(f"claude -p failed (rc={proc.returncode}): {detail}")
        try:
            envelope = json.loads(proc.stdout)
        except json.JSONDecodeError:
            last = [line for line in proc.stdout.splitlines() if line.strip()][-1]
            envelope = json.loads(last)
        text = envelope.get("result") or envelope.get("text") or ""
        usage = envelope.get("usage", {}) or {}
        return text, int(usage.get("input_tokens", 0) or 0), int(usage.get("output_tokens", 0) or 0)


class AnthropicBackend(LLMBackend):
    """Direct Anthropic API. Requires ANTHROPIC_API_KEY. No Claude Code sessions."""

    def __init__(self, model: Optional[str] = None):
        super().__init__(model or os.environ.get("CASHEW_CLAUDE_MODEL", "claude-haiku-4-5-20251001"))
        try:
            import anthropic as _anthropic
            self._client = _anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        except ImportError:
            raise RuntimeError("anthropic package not installed — run: pip install anthropic")
        except KeyError:
            raise RuntimeError("ANTHROPIC_API_KEY env var not set")

    def _generate(self, prompt: str) -> tuple[str, int, int]:
        import anthropic as _anthropic
        msg = self._client.messages.create(
            model=self.model,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        text = msg.content[0].text if msg.content else ""
        return text, msg.usage.input_tokens, msg.usage.output_tokens


def build_backend(name: Optional[str] = None, model: Optional[str] = None) -> Optional[Callable[[str], str]]:
    """Build a backend by name. Returns a callable with `.usage` attached,
    or None if the backend is unavailable (e.g. `claude` CLI missing).

    Name defaults to `$CASHEW_LLM_BACKEND` or `anthropic`.
    Model overrides the backend's default when provided.
    """
    name = (name or os.environ.get("CASHEW_LLM_BACKEND") or "claude_code").lower()
    try:
        if name == "claude_code":
            return ClaudeCodeBackend(model=model)
        if name == "anthropic":
            return AnthropicBackend(model=model)
    except RuntimeError as e:
        print(f"Warning: {name} backend unavailable: {e}")
        return None
    print(f"Warning: Unknown LLM backend: {name!r}")
    return None
