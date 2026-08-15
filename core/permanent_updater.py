from __future__ import annotations
import base64
import json
import os
import shutil
import tempfile
import urllib.request
import zipfile
from pathlib import Path
from datetime import datetime

REPO = "andhaleshekhar20-pixel/Goje-Personal-AI"
BRANCH = "main"
API = "https://api.github.com"

PRESERVE = {"data", "memory", "plugins", "config", "ai_inbox", "backups", "updates", ".env", ".venv"}

class PermanentUpdater:
    def __init__(self, base: Path, logger):
        self.base = Path(base)
        self.logger = logger
        self.backups = self.base / "backups"
        self.backups.mkdir(parents=True, exist_ok=True)

    @property
    def token_path(self):
        return self.base / "config" / "github_token.txt"

    def current_version(self):
        try:
            return json.loads((self.base / "version.json").read_text(encoding="utf-8")).get("version", "0.0.0")
        except Exception:
            return "0.0.0"

    @staticmethod
    def ver(v):
        nums = []
        for part in str(v).lstrip("v").split("."):
            digits = ""
            for c in part:
                if c.isdigit(): digits += c
                else: break
            nums.append(int(digits or 0))
        return tuple((nums + [0, 0, 0])[:3])

    def token(self):
        env = os.getenv("GOJE_GITHUB_TOKEN", "").strip()
        if env: return env
        if self.token_path.exists(): return self.token_path.read_text(encoding="utf-8").strip()
        return ""

    def save_token(self, token):
        self.token_path.parent.mkdir(parents=True, exist_ok=True)
        self.token_path.write_text(token.strip(), encoding="utf-8")

    def has_token(self):
        return bool(self.token())

    def _request_json(self, url):
        headers = {
            "User-Agent": "Goje-Personal-AI-Updater/8.0",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }
        token = self.token()
        if token: headers["Authorization"] = f"Bearer {token}"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))

    def remote_version(self):
        data = self._request_json(f"{API}/repos/{REPO}/contents/releases/latest/version.json?ref={BRANCH}")
        raw = base64.b64decode(data["content"]).decode("utf-8")
        return json.loads(raw)

    def check(self):
        try:
            remote = self.remote_version()
            current = self.current_version()
            rv = remote.get("version", "0.0.0")
            return {"ok": True, "current": current, "remote": rv,
                    "notes": remote.get("notes", ""),
                    "update_available": self.ver(rv) > self.ver(current)}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def _download_file_contents(self, path):
        data = self._request_json(f"{API}/repos/{REPO}/contents/{path}?ref={BRANCH}")
        return base64.b64decode(data["content"])

    def download_source(self):
        tmp = Path(tempfile.mkdtemp(prefix="goje_update_"))
        archive = tmp / "repo.zip"
        try:
            manifest = json.loads(self._download_file_contents("releases/latest/payload_manifest.json").decode("utf-8"))
            chunks = [self._download_file_contents(f"releases/latest/payload/{name}").decode("ascii") for name in manifest.get("parts", [])]
            archive.write_bytes(base64.b64decode("".join(chunks)))
        except Exception:
            # Reliable fallback: download the authenticated main-branch snapshot.
            headers = {
                "User-Agent": "Goje-Personal-AI-Updater/8.0",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28"
            }
            token = self.token()
            if token: headers["Authorization"] = f"Bearer {token}"
            req = urllib.request.Request(f"{API}/repos/{REPO}/zipball/{BRANCH}", headers=headers)
            with urllib.request.urlopen(req, timeout=60) as r:
                archive.write_bytes(r.read())

        extract = tmp / "extract"
        extract.mkdir()
        with zipfile.ZipFile(archive, "r") as z: z.extractall(extract)
        roots = [x for x in extract.iterdir() if x.is_dir()]
        source = roots[0] if len(roots) == 1 else extract
        return source, tmp

    def backup(self):
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dst = self.backups / f"pre_update_{stamp}"
        dst.mkdir(parents=True, exist_ok=True)
        for item in self.base.iterdir():
            if item.name in PRESERVE or item.name == "backups": continue
            target = dst / item.name
            if item.is_dir(): shutil.copytree(item, target)
            else: shutil.copy2(item, target)
        return dst

    def _merge_copy(self, src: Path, dst: Path):
        if src.is_dir():
            dst.mkdir(parents=True, exist_ok=True)
            for child in src.iterdir():
                if child.name == "__pycache__": continue
                self._merge_copy(child, dst / child.name)
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

    def stage(self):
        chk = self.check()
        if not chk.get("ok") or not chk.get("update_available"):
            return {**chk, "updated": False} if chk.get("ok") else chk
        source, tmp = self.download_source()
        stage = self.base / "updates" / f"v{chk['remote']}"
        if stage.exists(): shutil.rmtree(stage, ignore_errors=True)
        stage.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, stage)
        shutil.rmtree(tmp, ignore_errors=True)
        return {**chk, "updated": True, "stage": str(stage)}

    def apply(self, stage):
        stage_path = Path(stage)
        if not stage_path.exists(): raise FileNotFoundError(stage)
        backup = self.backup()
        for item in stage_path.iterdir():
            if item.name in {"data", "memory", "plugins", "config", "ai_inbox", "backups", "updates", ".env", ".venv"}: continue
            self._merge_copy(item, self.base / item.name)
        self.logger.write("update_applied", {"stage": str(stage_path), "backup": str(backup)})
        return {"ok": True, "backup": str(backup)}

    def create_restart_helper(self, python_exe, stage):
        helper = self.base / "apply_goje_update.bat"
        script = self.base / "core" / "apply_update_helper.py"
        helper.write_text(
            "@echo off\r\n"
            "timeout /t 2 /nobreak >nul\r\n"
            f'"{python_exe}" "{script}" "{self.base}" "{stage}"\r\n'
            f'start "" "{python_exe}" "{self.base / "desktop_app.py"}"\r\n'
            'del "%~f0"\r\n',
            encoding="utf-8"
        )
        return helper
