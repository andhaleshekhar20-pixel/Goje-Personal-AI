from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
import urllib.request


class LocalReasoner:
    """Ollama local reasoning adapter used by Goje."""

    def __init__(self, settings, logger):
        cfg = (settings or {}).get("reasoning", {})
        self.base_url = str(
            cfg.get("local_base_url", cfg.get("base_url", "http://127.0.0.1:11434"))
        ).rstrip("/")
        self.model = str(
            cfg.get("local_model", cfg.get("model", "qwen3:4b-instruct"))
        )
        self.thinking = False
        self.temperature = float(cfg.get("temperature", 0.2))
        self.logger = logger

    def _get(self, path, timeout=10):
        req = urllib.request.Request(
            self.base_url + path,
            headers={"User-Agent": "Goje-LocalBrain/12.0"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    def _post(self, path, payload, timeout=300):
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.base_url + path,
            data=data,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "Goje-LocalBrain/12.0",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    def _ollama_exe(self):
        found = shutil.which("ollama")
        if found:
            return found
        candidates = [
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Ollama", "ollama.exe"),
            os.path.join(os.environ.get("ProgramFiles", ""), "Ollama", "ollama.exe"),
        ]
        for candidate in candidates:
            if candidate and os.path.exists(candidate):
                return candidate
        return None

    def ensure_service(self, wait_seconds=8):
        if self.health().get("ok"):
            return True
        exe = self._ollama_exe()
        if not exe:
            return False
        try:
            subprocess.Popen(
                [exe, "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except Exception:
            pass
        deadline = time.time() + wait_seconds
        while time.time() < deadline:
            if self.health().get("ok"):
                return True
            time.sleep(0.5)
        return False

    def health(self):
        try:
            self._get("/", 4)
            return {"ok": True}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def installed_models(self):
        try:
            return self._get("/api/tags", 8).get("models", [])
        except Exception:
            return []

    def has_model(self, model=None):
        wanted = model or self.model
        names = {str(m.get("name", "")) for m in self.installed_models()}
        return wanted in names or (":" not in wanted and wanted + ":latest" in names)

    def status(self):
        service = self.health().get("ok", False)
        model = self.has_model()
        return {
            "service": service,
            "model": model,
            "ready": bool(service and model),
            "model_name": self.model,
        }

    def chat(self, messages, model=None):
        if not self.ensure_service():
            return {"ok": False, "error": "Ollama is not running."}

        selected = model or self.model
        if not self.has_model(selected):
            return {
                "ok": False,
                "error": f"Local model {selected} is not installed.",
            }

        result = self._post(
            "/api/chat",
            {
                "model": selected,
                "messages": messages,
                "stream": False,
                "think": False,
                "options": {"temperature": self.temperature},
            },
        )
        message = result.get("message", {})
        return {
            "ok": True,
            "model": result.get("model", selected),
            "content": str(message.get("content", "")).strip(),
            "thinking": "",
        }
