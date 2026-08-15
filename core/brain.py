from __future__
import os,re
from datetime import datetime
from pathlib import Path
from core.local_reasoner import LocalReasoner

class GojeBrain:
    def __init__(self,memory,commands,mt5,filesystem,web,voice,events=None,local_reasoner=None):
        self.memory=memory; self.commands=commands; self.mt5=mt5; self.filesystem=filesystem
        self.web=web; self.voice=voice; self.events=events
        self.local=local_reasoner or LocalReasoner({},None)

    def _emit(self,event,payload=None):
        if self.events:
            try:self.events.emit(event,payload or {})
            except Exception:pass

    def _finish(self,sid,text):
        self.memory.add_message(sid,"assistant",text); self._emit("assistant.response",{"text":text}); return text

    def _symbol(self,text):
        t=text.lower().replace("/","")
        aliases={"gold":"XAUUSD","xau":"XAUUSD","xauusd":"XAUUSD","silver":"XAGUSD","xag":"XAGUSD","xagusd":"XAGUSD","bitcoin":"BTCUSD","btc":"BTCUSD","btcusd":"BTCUSD","ethereum":"ETHUSD","eth":"ETHUSD","ethusd":"ETHUSD","oil":"USOIL","crude":"USOIL","usoil":"USOIL","eurusd":"EURUSD","gbpusd":"GBPUSD","usdjpy":"USDJPY"}
        for k,v in aliases.items():
            if k in t:return v
        return "XAUUSD"

    def _ensure_mt5(self):
        return self.mt5.initialize() if not self.mt5.connected else {"ok":True}

    def _reasoning_messages(self,sid,user_text):
        mem=self.memory.search(user_text,limit=12)
        memtxt="\n".join(f"- {m['category']}: {m['title']} — {m['content']}" for m in mem)
        recent=self.memory.recent_messages(sid,20)
        hist="\n".join(f"{m['role']}: {m['content']}" for m in recent)
        system=f"""
You are Goje, a female personal desktop AI partner.
Be concise, practical, friendly and collaborative.
Work with the user as two people solving a task together.
Ask one focused question when needed.
Use memory when relevant and obey the current request over old memory.
Never claim an action happened unless the host tool confirmed it.
Do not dump capability lists. Greetings should be answered naturally.

Memory:\n{memtxt}\n\nRecent conversation:\n{hist}
"""
        return [{"role":"system","content":system},{"role":"user","content":user_text}]

    def _local_command(self,sid,text):
        t=text.lower().strip()
        if t in {"hi","hello","hey","hii","hiya"}:
            return self._finish(sid,"Hi, I am Goje. How can I help you?")
        if t in {"thanks","thank you"}: return self._finish(sid,"You're welcome.")
        if t.startswith("remember "):
            c=text[9:].strip(); self.memory.add_memory("instruction",c[:100],c,tags="explicit",importance=9)
            return self._finish(sid,"Done. I’ll remember that.")
        if t in {"show memory","my memory","list memory"}:
            rows=self.memory.list_memories()[:30]
            return self._finish(sid,"Your memory is empty." if not rows else "\n".join(f"{r['id']}. {r['title']} — {r['content']}" for r in rows))
        if any(x in t for x in ("what time","current time")):
            return self._finish(sid,datetime.now().strftime("It is %I:%M %p."))
        if t.startswith("open ") and any(x in t for x in ("pictures","picture","documents","downloads","desktop")):
            folder={"pictures":"Pictures","picture":"Pictures","documents":"Documents","downloads":"Downloads","desktop":"Desktop"}
            for k,v in folder.items():
                if k in t:
                    p=Path.home()/v
                    try:self.filesystem.open_path(str(p)); return self._finish(sid,f"Opened {v} folder.")
                    except Exception as e:return self._finish(sid,f"I couldn't open {v}: {e}")
        if any(x in t for x in ("find file","find folder","find picture","find photos","locate file")):
            q=re.sub(r"^(please\s+)?(find|locate)\s+(the\s+)?(file|folder|picture|photos?)\s*","",text,flags=re.I).strip() or "picture"
            rows=self.filesystem.search(q)
            if not rows:return self._finish(sid,f"I couldn't find '{q}'.")
            return self._finish(sid,"I found:\n"+"\n".join(f"• {r['name']}\n  {r['path']}" for r in rows[:12]))
        if t.startswith(("search online ","search the web ","web search ","internet search ")):
            q=re.sub(r"^(search online|search the web|web search|internet search)\s*","",text,flags=re.I).strip()
            if not q:return self._finish(sid,"What should I search for?")
            try:
                rows=self.web.search(q)
                return self._finish(sid,"Search results:\n"+"\n".join(f"{i+1}. {r['title']}\n{r['url']}" for i,r in enumerate(rows[:8])))
            except Exception as e:return self._finish(sid,f"Web search failed: {e}")
        if any(x in t for x in ("gold price","gold quote","price of gold")):
            try:
                init=self._ensure_mt5()
                if not init.get("ok"): return self._finish(sid,"MT5 is not connected.")
                q=self.mt5.symbol_tick("XAUUSD")
                return self._finish(sid,f"XAUUSD Bid: {q.get('bid')}\nAsk: {q.get('ask')}\nSpread: {q.get('ask')-q.get('bid')}") if q else self._finish(sid,"I couldn't read XAUUSD from MT5.")
            except Exception as e:return self._finish(sid,f"I couldn't read gold price: {e}")
        if any(x in t for x in ("open trades","open positions","my trades")):
            try:
                self._ensure_mt5(); rows=self.mt5.positions()
                return self._finish(sid,"No open positions.") if not rows else self._finish(sid,"\n".join(f"• {p.get('symbol')} | {p.get('volume')} | P/L {p.get('profit')}" for p in rows))
            except Exception as e:return self._finish(sid,f"I couldn't read positions: {e}")
        return None

    def answer(self,sid,user_text):
        self.memory.add_message(sid,"user",user_text)
        local=self._local_command(sid,user_text)
        if local:return local
        messages=self._reasoning_messages(sid,user_text)
        try:
            if self.local.health().get("ok") and self.local.has_model():
                r=self.local.chat(messages)
                if r.get("content"):return self._finish(sid,r["content"])
        except Exception as e:self._emit("assistant.local_error",{"error":str(e)})
        key=os.getenv("OPENAI_API_KEY","").strip(); model=os.getenv("OPENAI_MODEL","").strip()
        if key and model:
            try:
                from openai import OpenAI
                r=OpenAI(api_key=key).responses.create(model=model,instructions=messages[0]["content"],input=user_text)
                return self._finish(sid,r.output_text.strip())
            except Exception as e:self._emit("assistant.cloud_error",{"error":str(e)})
        return self._finish(sid,"My local reasoning brain is not installed yet. Run INSTALL_LOCAL_BRAIN.bat once, then ask me again.")
