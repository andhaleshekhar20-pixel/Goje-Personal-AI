from __future__ import annotations
import argparse,base64,json,os,shutil,subprocess,sys,tempfile,time,urllib.request,zipfile
from datetime import datetime
from pathlib import Path
REPO='andhaleshekhar20-pixel/Goje-Personal-AI'; BRANCH='main'
KEEP={'data','memory','plugins','config','backups','updates','ai_inbox','.env','.venv'}
def log(p,s):
    p.parent.mkdir(parents=True,exist_ok=True); p.open('a',encoding='utf-8').write(f'[{datetime.now().isoformat()}] {s}\n')
def gj(url):
    r=urllib.request.Request(url,headers={'User-Agent':'Goje-Updater/12.0','Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28'})
    with urllib.request.urlopen(r,timeout=60) as x:return json.loads(x.read().decode())
def vk(v):
    a=[]
    for p in str(v).lstrip('v').split('.'):
        d=''.join(c for c in p if c.isdigit()); a.append(int(d or 0))
    return tuple((a+[0,0,0])[:3])
def rv():
    d=gj(f'https://api.github.com/repos/{REPO}/contents/version.json?ref={BRANCH}')
    return json.loads(base64.b64decode(d['content']).decode())
def wait(pid,logp):
    if not pid:return
    end=time.time()+20
    while time.time()<end:
        try:os.kill(pid,0);time.sleep(.4)
        except OSError:return
    subprocess.run(['taskkill','/PID',str(pid),'/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=False)
    end=time.time()+10
    while time.time()<end:
        try:os.kill(pid,0);time.sleep(.3)
        except OSError:return
    raise RuntimeError('Goje process did not exit.')
def download(tmp):
    z=tmp/'repo.zip'; q=urllib.request.Request(f'https://github.com/{REPO}/archive/refs/heads/{BRANCH}.zip',headers={'User-Agent':'Goje-Updater/12.0'})
    with urllib.request.urlopen(q,timeout=180) as r:z.write_bytes(r.read())
    ex=tmp/'extract';ex.mkdir()
    with zipfile.ZipFile(z) as f:f.extractall(ex)
    ds=[p for p in ex.iterdir() if p.is_dir()]; src=ds[0] if len(ds)==1 else ex
    if not (src/'desktop_app.py').exists():
        c=list(src.rglob('desktop_app.py'))
        if not c: raise RuntimeError('desktop_app.py missing from update')
        src=c[0].parent
    if not (src/'version.json').exists():raise RuntimeError('version.json missing from update')
    for p in src.rglob('*.py'):compile(p.read_text(encoding='utf-8'),str(p),'exec')
    return src
def backup(base):
    b=base/'backups'/('pre_update_'+datetime.now().strftime('%Y%m%d_%H%M%S'));b.mkdir(parents=True,exist_ok=True)
    for n in KEEP:
        s=base/n
        if s.exists():
            if s.is_dir():shutil.copytree(s,b/n,dirs_exist_ok=True)
            else:shutil.copy2(s,b/n)
    return b
def copytree(src,dst):
    if src.is_dir():
        dst.mkdir(parents=True,exist_ok=True)
        for c in src.iterdir():
            if c.name not in {'.git','__pycache__'}:copytree(c,dst/c.name)
    else:
        dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--base',required=True);ap.add_argument('--pid',type=int,default=0);a=ap.parse_args();base=Path(a.base).resolve();tmp=Path(tempfile.mkdtemp(prefix='GojeUpdate_'));lp=tmp/'update.log'
    try:
        cur=json.loads((base/'version.json').read_text(encoding='utf-8')).get('version','0.0.0')
        remote=rv();new=str(remote.get('version','0.0.0'));log(lp,f'Current V{cur}; remote V{new}.')
        if vk(new)<=vk(cur):return 0
        src=download(tmp);log(lp,f'Validated V{new}.')
        wait(a.pid,lp);b=backup(base);log(lp,f'Backup {b}.')
        # IMPORTANT: do not rename the installation directory. Windows may lock it
        # because Explorer or a command prompt has it as its working directory.
        for item in src.iterdir():
            if item.name in KEEP or item.name in {'.git','__pycache__'}:continue
            copytree(item,base/item.name)
        installed=json.loads((base/'version.json').read_text(encoding='utf-8')).get('version','0.0.0')
        if installed!=new:raise RuntimeError(f'Version verification failed: expected V{new}, found V{installed}')
        (base/'updates').mkdir(parents=True,exist_ok=True)
        (base/'updates'/'update_status.json').write_text(json.dumps({'status':'success','from':cur,'to':new,'mode':'in_place','backup':str(b),'time':datetime.now().isoformat()},indent=2),encoding='utf-8')
        (base/'updates'/'update.log').write_text(lp.read_text(encoding='utf-8'),encoding='utf-8')
        py=base/'.venv'/'Scripts'/'python.exe';py=py if py.exists() else Path(sys.executable)
        subprocess.Popen([str(py),str(base/'desktop_app.py')],cwd=str(base),creationflags=getattr(subprocess,'CREATE_NEW_CONSOLE',0))
        return 0
    except Exception as e:
        log(lp,f'UPDATE FAILED: {e}');(base/'updates').mkdir(parents=True,exist_ok=True);(base/'updates'/'update_status.json').write_text(json.dumps({'status':'failed','error':str(e),'time':datetime.now().isoformat()},indent=2),encoding='utf-8');(base/'updates'/'update.log').write_text(lp.read_text(encoding='utf-8'),encoding='utf-8');raise
    finally:shutil.rmtree(tmp,ignore_errors=True)
if __name__=='__main__':raise SystemExit(main())
