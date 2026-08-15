from __future__
import json, urllib.request

class LocalReasoner:
    def __init__(self, settings, logger):
        cfg=settings.get("reasoning",{})
        self.base_url=str(cfg.get("base_url","http://127.0.0.1:11434")).rstrip("/")
        self.model=str(cfg.get("model","goje-brain"))
        self.thinking=bool(cfg.get("thinking",True))
        self.temperature=float(cfg.get("temperature",0.2))
        self.logger=logger

    def _get(self,path,timeout=10):
        req=urllib.request.Request(self.base_url+path,headers={"User-Agent":"Goje-LocalBrain/8.0"})
        with urllib.request.urlopen(req,timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))

    def _post(self,path,payload,timeout=300):
        data=json.dumps(payload).encode("utf-8")
        req=urllib.request.Request(self.base_url+path,data=data,
            headers={"Content-Type":"application/json","User-Agent":"Goje-LocalBrain/8.0"})
        with urllib.request.urlopen(req,timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))

    def health(self):
        try:
            self._get("/",4); return {"ok":True}
        except Exception as exc:
            return {"ok":False,"error":str(exc)}

    def installed_models(self):
        try: return self._get("/api/tags").get("models",[])
        except Exception: return []

    def has_model(self,model=None):
        wanted=model or self.model
        names={m.get("name","") for m in self.installed_models()}
        return wanted in names or (":" not in wanted and wanted+":latest" in names)

    def chat(self,messages,model=None):
        selected=model or self.model
        result=self._post("/api/chat",{
            "model":selected,"messages":messages,"stream":False,
            "think":self.thinking,"options":{"temperature":self.temperature}
        })
        msg=result.get("message",{})
        return {"ok":True,"model":result.get("model",selected),
                "content":str(msg.get("content","")).strip(),
                "thinking":str(msg.get("thinking","")).strip()}
