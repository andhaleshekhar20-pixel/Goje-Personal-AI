from __future__ import annotations

import datetime
import json
import os
import shutil
import tempfile
import urllib.request
import zipfile
from pathlib import Path

REPO = "andhaleshekhar20-pixel/Goje-Personal-AI"
BRANCH = "main"

class UpdateManager:
    PRESERVE = {"plugins", "data", "config", "ai_inbox", "backups", "memory", ".env", ".venv"}

    def __init__(self, base: Path, logger):
        self.base = Path(base)
        self.logger = logger
        self.backups = self.base / "backups"
        self.backups.mkdir(exist_ok=True)
        self.version_file = self.base / "version.json"
        self.token_file = self.base / "config" / "github_token.txt"

    def current_version(self):
        try:
            return json.loads(self.version_file.read_text(encoding="utf-8")).get("version", "0.0.0")
        except Exception:
            return "0.0.0"

    def get_token(self):
        token = os.getenv("GOJE_GITHUB_TOKEN", "").strip()
        if token:
            return token
        if self.token_file.exists():
            return self.token_file.read_text(encoding="utf-8").strip()
        return ""

    def _request(self, url):
        headers = {
            "User-Agent": "Goje-Personal-AI-Updater",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2026-03-10"
        }
        token = self.get_token()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=20)

    def check(self):
        url = f"https://api.github.com/repos/{REPO}/contents/version.json?ref={BRANCH}"
        try:
            with self._request(url) as r:
                payload = json.loads(r.read().decode("utf-8"))
            import base64
            remote = json.loads(base64.b64decode(payload["content"]).decode("utf-8"))
            current = self.current_version()
            remote_version = remote.get("version", "0.0.0")
            return {
                "ok": True,
                "current": current,
                "remote": remote_version,
                "notes": remote.get("notes", ""),
                "update_available": self._version_tuple(remote_version) > self._version_tuple(current)
            }
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    @staticmethod
    def _version_tuple(v):
        nums=[]
        for part in str(v).lstrip("v").split("."):
            n=""
            for c in part:
                if c.isdigit(): n+=c
                else: break
            nums.append(int(n or 0))
        return tuple((nums+[0,0,0])[:3])

    def backup_app(self):
        stamp=datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        dst=self.backups/f"backup_{stamp}"
        dst.mkdir(parents=True)
        for item in self.base.iterdir():
            if item.name in self.PRESERVE or item.name == "backups": continue
            target=dst/item.name
            if item.is_dir(): shutil.copytree(item,target)
            else: shutil.copy2(item,target)
        self.logger.write("update_backup", {"path":str(dst)})
        return dst

    def download_source(self):
        tmp=Path(tempfile.mkdtemp(prefix="goje_update_"))
        archive=tmp/"goje-source.zip"
        url=f"https://api.github.com/repos/{REPO}/zipball/{BRANCH}"
        with self._request(url) as r: archive.write_bytes(r.read())
        extract=tmp/"extract"; extract.mkdir()
        with zipfile.ZipFile(archive,"r") as z: z.extractall(extract)
        roots=[p for p in extract.iterdir() if p.is_dir()]
        if len(roots)!=1: raise RuntimeError("Unexpected GitHub update package structure.")
        return roots[0],tmp

    def stage_update(self):
        result=self.check()
        if not result.get("ok"): raise RuntimeError(result.get("error","Could not check GitHub."))
        if not result.get("update_available"):
            return {"ok":True,"updated":False,**result}
        source,tmp=self.download_source()
        stage=self.base/"updates"/f"v{result['remote']}"
        if stage.exists(): shutil.rmtree(stage,ignore_errors=True)
        stage.parent.mkdir(exist_ok=True)
        shutil.copytree(source,stage)
        shutil.rmtree(tmp,ignore_errors=True)
        return {"ok":True,"updated":True,"version":result["remote"],"stage":str(stage)}

    def apply_staged(self, stage):
        stage=Path(stage)
        if not stage.exists(): raise FileNotFoundError(str(stage))
        backup=self.backup_app()
        for item in stage.iterdir():
            if item.name in self.PRESERVE or item.name == "backups": continue
            self._merge_copy(item,self.base/item.name)
        self.logger.write("update_installed", {"stage":str(stage),"backup":str(backup)})
        return {"ok":True,"backup":str(backup)}

    def _merge_copy(self, source, target):
        source=Path(source); target=Path(target)
        if source.is_dir():
            target.mkdir(parents=True,exist_ok=True)
            for child in source.iterdir(): self._merge_copy(child,target/child.name)
        else:
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(source,target)

    def install_from_github(self):
        return self.stage_update()
