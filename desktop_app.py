from __future__ import annotations
import json, os, threading, uuid
from pathlib import Path
import tkinter as tk
from tkinter import messagebox
from dotenv import load_dotenv

from core.sdk import CommandRegistry, EventBus, PermissionManager, PluginContext
from core.audit import AuditLog
from core.mt5_connector import MT5Connector
from core.plugin_manager import PluginManager
from core.memory import MemoryStore
from core.filesystem_service import FileSystemService
from core.web_search import WebSearchService
from core.voice import VoiceService
from core.brain import GojeBrain
from core.local_reasoner import LocalReasoner
from core.permanent_updater import PermanentUpdater

BASE=Path(__file__).resolve().parent
os.chdir(BASE); load_dotenv()
settings=json.loads((BASE/'config/settings.json').read_text(encoding='utf-8')) if (BASE/'config/settings.json').exists() else {}
version=json.loads((BASE/'version.json').read_text(encoding='utf-8')).get('version','12.0.0') if (BASE/'version.json').exists() else '12.0.0'
logger=AuditLog(settings.get('audit_log','data/audit.log'))
permissions=PermissionManager(settings); commands=CommandRegistry(); events=EventBus()
mt5=MT5Connector(permissions); memory=MemoryStore(); filesystem=FileSystemService(permissions,logger); web=WebSearchService(permissions,logger); voice=VoiceService(logger)
local=LocalReasoner(settings,logger); ctx=PluginContext(commands,events,permissions,mt5,logger,settings)
plugins=PluginManager(ctx); updater=PermanentUpdater(BASE,logger)
brain=GojeBrain(memory,commands,mt5,filesystem,web,voice,events,local); session=str(uuid.uuid4())

BG='#050a11'; PANEL='#0a1320'; CYAN='#2de2e6'; BLUE='#4aa3ff'; TEXT='#e8f7ff'; MUTED='#6f8ea7'; GREEN='#55f28b'; RED='#ff3b52'

class Goje(tk.Tk):
    def __init__(self):
        super().__init__(); self.title(f'GOJE // PERSONAL AI V{version}'); self.geometry('1450x850'); self.minsize(1000,650); self.configure(bg=BG)
        self.last_answer=''; self.auto_speak=tk.BooleanVar(value=True); self._build(); self.after(100,self.start); self.protocol('WM_DELETE_WINDOW',self.close)
    def btn(self,p,text,cmd,w=12): return tk.Button(p,text=text,command=cmd,bg=PANEL,fg=TEXT,activebackground='#14334e',activeforeground=CYAN,relief='flat',bd=0,font=('Segoe UI',10,'bold'),cursor='hand2',width=w,padx=7,pady=7)
    def _build(self):
        top=tk.Frame(self,bg='#07111d',height=78); top.pack(fill='x'); top.pack_propagate(False)
        tk.Label(top,text='GOJE',bg='#07111d',fg=GREEN,font=('Segoe UI',22,'bold')).pack(side='left',padx=(22,8),pady=16)
        tk.Label(top,text=f'PERSONAL AI // V{version} // AUTO-UPDATE V12 TEST',bg='#07111d',fg=MUTED,font=('Consolas',9)).pack(side='left',pady=25)
        self.status=tk.StringVar(value='STARTING'); tk.Label(top,textvariable=self.status,bg='#07111d',fg=CYAN,font=('Consolas',9,'bold')).pack(side='right',padx=16)
        self.btn(top,'⟳ UPDATE',self.update,10).pack(side='right',padx=4); self.btn(top,'🧠 LOCAL BRAIN',self.install_brain,14).pack(side='right',padx=4)
        body=tk.Frame(self,bg=BG); body.pack(fill='both',expand=True)
        side=tk.Frame(body,bg='#07111d',width=180); side.pack(side='left',fill='y'); side.pack_propagate(False)
        tk.Label(side,text='MODULES',bg='#07111d',fg=MUTED,font=('Consolas',9,'bold')).pack(anchor='w',padx=15,pady=(18,8))
        for t,c in [('Conversation',lambda:self.entry.focus_set()),('Memory',self.show_memory),('Files',lambda:self.quick('find file ')),('Internet',lambda:self.quick('search online ')),('MT5',lambda:self.quick('gold price')),('Voice',self.test_voice)]: self.btn(side,t,c,17).pack(fill='x',padx=9,pady=3)
        self.info=tk.StringVar(value=''); tk.Label(side,textvariable=self.info,bg='#07111d',fg=GREEN,font=('Consolas',9),justify='left').pack(anchor='w',padx=15,pady=18)
        center=tk.Frame(body,bg=BG); center.pack(side='left',fill='both',expand=True,padx=10)
        h=tk.Frame(center,bg=PANEL); h.pack(fill='x',pady=10); tk.Label(h,text='LIVE CONVERSATION',bg=PANEL,fg=CYAN,font=('Consolas',10,'bold')).pack(side='left',padx=12,pady=10)
        self.activity=tk.StringVar(value='READY'); tk.Label(h,textvariable=self.activity,bg=PANEL,fg=MUTED,font=('Consolas',9)).pack(side='right',padx=12)
        self.chat=tk.Text(center,bg='#03070c',fg=TEXT,insertbackground=CYAN,wrap='word',font=('Segoe UI',11),relief='flat',bd=0,padx=16,pady=14); self.chat.pack(fill='both',expand=True); self.chat.configure(state='disabled')
        self.chat.tag_configure('you',foreground=BLUE,font=('Segoe UI',10,'bold')); self.chat.tag_configure('goje',foreground=CYAN,font=('Segoe UI',10,'bold')); self.chat.tag_configure('txt',foreground=TEXT)
        bar=tk.Frame(center,bg=BG); bar.pack(fill='x',pady=10); self.entry=tk.Entry(bar,bg='#08111c',fg=TEXT,insertbackground=CYAN,relief='flat',font=('Segoe UI',12)); self.entry.pack(side='left',fill='x',expand=True,ipady=10,padx=(0,7)); self.entry.bind('<Return>',lambda e:self.send())
        self.btn(bar,'SEND ›',self.send,8).pack(side='left',padx=2); self.btn(bar,'🎤 TALK',self.listen,8).pack(side='left',padx=2); self.btn(bar,'🔊 REPEAT',self.repeat,9).pack(side='left',padx=2)
        tk.Checkbutton(center,text='AUTO SPEAK ANSWERS',variable=self.auto_speak,bg=BG,fg=MUTED,activebackground=BG,activeforeground=TEXT,selectcolor=PANEL,font=('Consolas',8)).pack(anchor='w',pady=(0,8))
        hud=tk.Frame(body,bg='#07111d',width=230); hud.pack(side='right',fill='y'); hud.pack_propagate(False); tk.Label(hud,text='SYSTEM HUD',bg='#07111d',fg=CYAN,font=('Consolas',10,'bold')).pack(anchor='w',padx=14,pady=(18,10))
        self.brain_s=tk.StringVar(); self.mem_s=tk.StringVar(); self.mt5_s=tk.StringVar(); self.plug_s=tk.StringVar()
        for title,var in [('AI BRAIN',self.brain_s),('MEMORY',self.mem_s),('MT5',self.mt5_s),('PLUGINS',self.plug_s)]:
            f=tk.Frame(hud,bg='#0d1a2a'); f.pack(fill='x',padx=10,pady=4); tk.Label(f,text=title,bg='#0d1a2a',fg=MUTED,font=('Consolas',8,'bold')).pack(anchor='w',padx=8,pady=(5,0)); tk.Label(f,textvariable=var,bg='#0d1a2a',fg=TEXT,font=('Consolas',9)).pack(anchor='w',padx=8,pady=(0,6))
    def start(self):
        try: mt5.initialize(); plugins.scan_and_load()
        except Exception: pass
        self.refresh(); self.say('Hi. I’m Goje. I’m ready to work with you.')
    def refresh(self):
        try: localok=local.health().get('ok') and local.has_model()
        except Exception: localok=False
        self.brain_s.set('LOCAL READY' if localok else 'LOCAL OFFLINE'); self.mem_s.set(f'{len(memory.list_memories())} RECORDS'); self.mt5_s.set('CONNECTED' if mt5.connected else 'OFFLINE'); self.plug_s.set(f'{len(plugins.loaded)} LOADED'); self.info.set(f'VERSION V{version}\nBRAIN {"●" if localok else "○"}\nMT5 {"●" if mt5.connected else "○"}')
    def append(self,who,text): self.chat.configure(state='normal'); self.chat.insert('end',f'\n{who}\n','you' if who=='YOU' else 'goje'); self.chat.insert('end',text+'\n','txt'); self.chat.see('end'); self.chat.configure(state='disabled'); self.last_answer=text if who=='GOJE' else self.last_answer
    def say(self,t): self.append('GOJE',t)
    def send(self):
        t=self.entry.get().strip();
        if not t:return
        self.entry.delete(0,'end'); self.append('YOU',t); self.activity.set('THINKING…'); threading.Thread(target=self._run,args=(t,),daemon=True).start()
    def _run(self,t):
        a=brain.answer(session,t); self.after(0,lambda:self.done(a))
    def done(self,a):
        self.say(a); self.activity.set('READY'); self.refresh();
        if self.auto_speak.get(): threading.Thread(target=lambda:voice.speak_answer(a),daemon=True).start()
    def quick(self,t): self.entry.delete(0,'end'); self.entry.insert(0,t); self.entry.focus_set()
    def listen(self):
        self.activity.set('LISTENING…')
        def w():
            r=voice.listen();
            if r.get('ok'): self.after(0,lambda:self.quick(r['text']) or self.send())
            else: self.after(0,lambda:messagebox.showinfo('Goje Voice',r.get('message','Voice unavailable.')))
            self.after(0,lambda:self.activity.set('READY'))
        threading.Thread(target=w,daemon=True).start()
    def repeat(self):
        if self.last_answer: threading.Thread(target=lambda:voice.speak_answer(self.last_answer),daemon=True).start()
    def test_voice(self): threading.Thread(target=lambda:voice.speak_answer('Hello. I am Goje. Ready to work with you.'),daemon=True).start()
    def show_memory(self):
        rows=memory.list_memories()[:20]; self.say('Your memory is empty.' if not rows else '\n'.join(f'{r["id"]}. {r["title"]} — {r["content"]}' for r in rows))
    def install_brain(self):
        p=BASE/'INSTALL_LOCAL_BRAIN.bat'; os.startfile(str(p)) if p.exists() else messagebox.showerror('Goje','INSTALL_LOCAL_BRAIN.bat not found.')
    def update(self):
        self.activity.set('CHECKING UPDATE…')
        def w():
            try:r=updater.check(); self.after(0,lambda:self.upd_result(r))
            except Exception as e:self.after(0,lambda:messagebox.showerror('Goje Update',str(e)))
        threading.Thread(target=w,daemon=True).start()
    def upd_result(self,r):
        if not r.get('ok'): messagebox.showerror('Goje Update',r.get('error','Update check failed')); self.activity.set('READY'); return
        if not r.get('update_available'): messagebox.showinfo('Goje Update',f'Goje is up to date. Current version: V{r.get("current")}'); self.activity.set('READY'); return
        if messagebox.askyesno('Goje Update',f'V{r["remote"]} is available. Update now?'): threading.Thread(target=self._stage,daemon=True).start()
    def _stage(self):
        try:
            r=updater.stage();
            if not r.get('updated'): return
            helper=updater.create_restart_helper(str(Path(os.sys.executable)),r['stage']); self.after(0,lambda:messagebox.showinfo('Goje Update',f'V{r["remote"]} is ready. Goje will restart.')); self.after(700,lambda:(os.startfile(str(helper)),self.destroy()))
        except Exception as e:self.after(0,lambda:messagebox.showerror('Goje Update',str(e)))
    def close(self):
        try: mt5.shutdown(); memory.close()
        finally: self.destroy()

if __name__=='__main__': Goje().mainloop()
