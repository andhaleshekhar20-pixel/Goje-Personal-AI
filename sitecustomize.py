from __future__ import annotations
"""Goje V10 runtime repair layer.

Loaded automatically by Python before desktop_app.py. V10 keeps the existing
application intact while fixing the local brain and a few common desktop tasks.
"""

import re


def _mode_path():
    from pathlib import Path
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
    if any(x in t for x in ("hi", "hello", "what time", "remember", "gold price", "show positions", "account status")):
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


def _local(brain, system_text, user_text):
    try:
        # The user already installed this verified non-thinking local model.
        brain.local.model = "qwen3:4b-instruct"
        brain.local.thinking = False
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


def _cloud(system_text, user_text):
    key = __import__('os').getenv("OPENAI_API_KEY", "").strip()
    model = __import__('os').getenv("OPENAI_MODEL", "").strip()
    if not key or not model:
        return None
    try:
        from openai import OpenAI
        client = OpenAI(api_key=key)
        response = client.responses.create(model=model, instructions=system_text, input=user_text)
        return response.output_text.strip()
    except Exception:
        return None


def _patch_class():
    try:
        from core.brain import GojeBrain
    except Exception:
        return
    if getattr(GojeBrain, "_goje_v10_patched", False):
        return

    original = GojeBrain.answer

    def answer(self, session_id, user_text):
        text = user_text.strip()
        low = text.lower()
        if low in {"/brain auto", "/brain local", "/brain openai", "/brain hybrid"}:
            mode = low.split()[-1]
            _save_mode(mode)
            return self._finish(session_id, f"Brain mode set to {mode.upper()}.")

        # Common desktop file tasks should work without an LLM.
        triggers = (
            "find movie", "find movies", "find video", "find videos",
            "find picture", "find pictures", "find photo", "find photos",
            "find file", "find files", "find pdf", "find document",
            "find documents", "locate file", "locate movie", "locate video"
        )
        if any(x in low for x in triggers):
            if any(x in low for x in ("movie", "movies", "video", "videos")):
                query = "mp4"
            elif any(x in low for x in ("picture", "pictures", "photo", "photos")):
                query = "jpg"
            elif "pdf" in low:
                query = "pdf"
            else:
                query = re.sub(r"^(find|find the|find my|locate|locate the)\s+", "", low).strip()
            try:
                rows = self.filesystem.search(query)
                if rows:
                    return self._finish(
                        session_id,
                        "I found these:\n\n" + "\n".join(
                            f"• {r.get('name')} ({'folder' if r.get('is_dir') else 'file'})\n  {r.get('path')}"
                            for r in rows[:15]
                        )
                    )
                return self._finish(session_id, f"I couldn't find anything matching '{query}'.")
            except Exception as exc:
                return self._finish(session_id, f"I couldn't search your files: {exc}")

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
        route = ("hybrid" if _score(user_text) >= 2 else "local") if mode == "auto" else mode
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
    GojeBrain._goje_v10_patched = True

_patch_class()
