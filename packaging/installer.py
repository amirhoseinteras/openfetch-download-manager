"""Per-user, offline, self-contained Windows installer for OpenFetch."""
from __future__ import annotations
import os
import sys
import shutil
import subprocess
import tkinter as tk
from pathlib import Path
from tkinter import messagebox

APP_TITLE = "OpenFetch"
APP_VERSION = "0.4"
APP_EXE = "OpenFetch.exe"
ASSETS = ['IDM.ico', 'IDM_header.png']
REG_KEY = 'Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\' + APP_TITLE + "-OpenSource"
ROOT = Path(os.environ.get("LOCALAPPDATA",str(Path.home()))) / "Programs" / APP_TITLE


def payload_root():
    return Path(getattr(sys,"_MEIPASS",Path(__file__).parent)) / "payload"


def payload_ready():
    return (payload_root()/APP_EXE).is_file()


def shortcut(folder:Path, executable:Path):
    folder.mkdir(parents=True,exist_ok=True)
    target=folder/(APP_TITLE+".lnk")
    # Local trusted paths, quoted via PowerShell single quoted string with doubled quote escaping.
    def ps(s):return "'"+str(s).replace("'","''")+"'"
    script="$s=(New-Object -ComObject WScript.Shell).CreateShortcut("+ps(target)+");$s.TargetPath="+ps(executable)+";$s.WorkingDirectory="+ps(executable.parent)+";$s.Save()"
    result=subprocess.run(["powershell.exe","-NoProfile","-NonInteractive","-Command",script],capture_output=True,text=True,timeout=20)
    if result.returncode:raise RuntimeError("Shortcut error: "+result.stderr[-400:])
    return target


def install(folder:Path, register=True):
    if not payload_ready():raise RuntimeError("App payload missing in setup.")
    folder.mkdir(parents=True,exist_ok=True)
    for name in [APP_EXE]+ASSETS:
        source=payload_root()/name
        if not source.is_file():raise FileNotFoundError(source)
        shutil.copy2(source,folder/name)
    if register:
        shutil.copy2(sys.executable,folder/"Uninstall.exe")
        program=Path(os.environ["APPDATA"])/"Microsoft"/"Windows"/"Start Menu"/"Programs"
        shortcut(program,folder/APP_EXE)
        desktop=Path(os.environ.get("USERPROFILE",str(Path.home())))/"Desktop"
        shortcut(desktop,folder/APP_EXE)
        import winreg
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER,REG_KEY) as k:
            for name,value in {
                "DisplayName":APP_TITLE,"DisplayVersion":APP_VERSION,
                "Publisher":"Open-source contributors","InstallLocation":str(folder),
                "DisplayIcon":str(folder/APP_EXE),
                "UninstallString":'"'+str(folder/"Uninstall.exe")+'" --uninstall'
            }.items():winreg.SetValueEx(k,name,0,winreg.REG_SZ,value)
    return folder/APP_EXE


def uninstall(folder:Path,register=True):
    if register:
        program=Path(os.environ["APPDATA"])/"Microsoft"/"Windows"/"Start Menu"/"Programs"
        desktop=Path(os.environ.get("USERPROFILE",str(Path.home())))/"Desktop"
        for lnk in (program/(APP_TITLE+".lnk"),desktop/(APP_TITLE+".lnk")):
            if lnk.exists():lnk.unlink()
        import winreg
        try:winreg.DeleteKey(winreg.HKEY_CURRENT_USER,REG_KEY)
        except FileNotFoundError:pass
    for name in [APP_EXE]+ASSETS:
        item=folder/name
        if item.is_file():item.unlink()
    # Uninstall.exe is currently running. Remove it after exit.
    if register and (folder/"Uninstall.exe").exists():
        s='Start-Sleep -Seconds 2;Remove-Item -LiteralPath '+repr(str(folder/"Uninstall.exe"))+' -Force -ErrorAction SilentlyContinue'
        subprocess.Popen(["powershell.exe","-NoProfile","-WindowStyle","Hidden","-Command",s],
                         creationflags=subprocess.CREATE_NO_WINDOW)
    try:folder.rmdir()
    except OSError:pass


def main():
    args=sys.argv[1:]
    if args==["--inspect"]:
        print("SETUP_OK",APP_TITLE,APP_VERSION,"PAYLOAD",payload_ready())
        return 0 if payload_ready() else 2
    if len(args)==2 and args[0] in ("--install-test","--uninstall-test"):
        folder=Path(args[1]).resolve()
        temp=Path(os.environ.get("TEMP",str(Path.home()))).resolve()
        if not folder.is_relative_to(temp) or folder==temp:
            raise ValueError("Test install path must be a subdirectory of TEMP")
        if args[0]=="--install-test":
            print("TEST_INSTALLED",install(folder,False))
        else:
            uninstall(folder,False);print("TEST_UNINSTALLED",folder)
        return 0
    tk.Tk().withdraw()
    if args==["--uninstall"]:
        if messagebox.askyesno(APP_TITLE,"Uninstall "+APP_TITLE+"?"):
            uninstall(ROOT)
            messagebox.showinfo(APP_TITLE,"Uninstalled.")
        return 0
    if not payload_ready():
        messagebox.showerror(APP_TITLE,"Damaged setup: app payload missing.")
        return 2
    if not messagebox.askyesno(APP_TITLE,"Install "+APP_TITLE+" "+APP_VERSION+" for current user?\nDesktop and Start Menu shortcuts will be created."):
        return 0
    try:
        exe=install(ROOT)
        messagebox.showinfo(APP_TITLE,"Installed successfully to:\n"+str(exe))
        return 0
    except Exception as exc:
        messagebox.showerror(APP_TITLE,"Install failed:\n"+str(exc))
        return 1


if __name__=="__main__":
    raise SystemExit(main())
