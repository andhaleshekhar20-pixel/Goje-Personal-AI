from __future__ import annotations

"""Goje V9 hybrid-brain bootstrap.

Loaded automatically by Python before desktop_app.py. It keeps the V8 core/tools
intact while upgrading GojeBrain.answer to route between the verified local
qwen3:4b-instruct model and the configured OpenAI cloud model.
"""

import os
from pathlib import Path


def _mode_path():
    return Path(__file__).resolve().parent / "config" / "reasoning_mode.txt"


def _load_mode():
    try:
        value = _mode_path().read_text(encoding="utf-8").strip().lower()
        return value if value in {"auto", "local", "openai", "hybrid"} else "auto"
    except Exception:
        return "auto"


def _save_mode(value):
    p = _mode_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(value, encoding="utf-8")


def _score(text):
    t = text.lower()
    score = 0
    for phrase in ("analyze", "compare", "research", "deep", "detailed", "strategy", "explain", "evaluate", "backtest", "optimize", "develop", "design", "build", "step by step", "complex"):
        if phrase in t:
            score += 1
    for phrase in ("latest", "today", "current news", "recent", "news", "market outlook", "internet"):
        if phrase in t:
            score += 2
    if any(x in t for x in ("gold", "xauusd", "btc", "silver", "trading", "trade")):
        score += 1
    if any(x in t for x in ("hi", "hello", "find file", "open file", "what time", "remember", "gold price", "show positions", "account status")):
        score = min(score, 1)
    return score


def _system_prompt(brain, session_id, user_text):
    try:
        memories = brain.memory.search(user_text, limit=12)
    except Exception:
        memories = []
    try:
        recent = brain.memory.recent_messages(session_id, 16)
    except Exception:
        recent = []
    memory_text = "\n".join(f"- {m.get('title','')}: {m.get('content','')}" for m in memories)
    recent_text = "\n".join(f"{m.get('role')}: {m.get('content')}" for m in recent)
    return f"""
You are Goje, the user's female personal desktop AI partner.
Be natural, concise, practical and collaborative.
Do not dump capability lists.
Do not reveal internal reasoning or chain-of-thought.
Only provide the useful final answer.
Current user instructions override old memory.
Never claim a computer, trading or file action succeeded unless the host tool confirmed it.

Relevant memory:
{memory_text}

Recent conversation:
{recent_text}
"""


def _cloud(system_text, user_text):
    key = os.getenv("OPENAI_API_KEY", "").strip()
    model = os.getenv("OPENAI_MODEL", "").strip()
    if not key or not model:
        return None
    try:
        from openai import OpenAI
        client = OpenAI(api_key=key)
        response = client.responses.create(model=model, instructions=system_text, input=user_text)
        return response.output_text.strip()
    except Exception:
        return None


def _local(brain, system_text, user_text):
    try:
        brain.local.model = "qwen3:4b-instruct"
        if not brain.local.health().get("ok"):
            return None
        if not brain.local.has_model("qwen3:4b-instruct"):
            return None
        result = brain.local.chat(
            [{"role": "system", "content": system_text}, {"role": "user", "content": user_text}],
            model="qwen3:4b-instruct",
        )
        text = result.get("content", "").strip()
        return text or None
    except Exception:
        return None


def _patch_class():
    try:
        from core.brain import GojeBrain
    except Exception:
        return
    if getattr(GojeBrain, "_goje_v9_patched", False):
        return

    original = GojeBrain.answer

    def answer(self, session_id, user_text):
        text = user_text.strip()
        low = text.lower()
        if low in {"/brain auto", "/brain local", "/brain openai", "/brain hybrid"}:
            mode = low.split()[-1]
            _save_mode(mode)
            return self._finish(session_id, f"Brain mode set to {mode.upper()}.")

        # Preserve Goje's existing direct tool intents for things like MT5/file operations.
        try:
            direct = self.local_intent(session_id, user_text)
            if direct:
                return direct
        except Exception:
            pass

        try:
            self.memory.add_message(session_id, "user", user_text)
        except Exception:
            pass

        mode = _load_mode()
        if mode == "auto":
            route = "hybrid" if _score(user_text) >= 2 else "local"
        else:
            route = mode

        system_text = _system_prompt(self, session_id, user_text)

        if route == "local":
            result = _local(self, system_text, user_text)
            if result:
                return self._finish(session_id, result)
        elif route == "openai":
            result = _cloud(system_text, user_text)
            if result:
                return self._finish(session_id, result)
        else:
            local_result = _local(self, system_text, user_text)
            if local_result:
                system_text += "\n\nPreliminary local analysis:\n" + local_result
            cloud_result = _cloud(system_text, user_text)
            if cloud_result:
                return self._finish(session_id, cloud_result)
            if local_result:
                return self._finish(session_id, local_result)

        return original(self, session_id, user_text)

    GojeBrain.answer = answer
    GojeBrain._goje_v9_patched = True


_patch_class()
