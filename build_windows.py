"""Reproducible app and installer build: python -m pip install -r requirements.txt pyinstaller; python build_windows.py"""
from pathlib import Path
import subprocess,sys,zipfile
ROOT=Path(__file__).resolve().parent
NAME='OpenFetch'
SOURCE='openfetch.py'
ASSETS=['IDM.ico', 'IDM_header.png']
ICON='IDM.ico'
def run(args):
    subprocess.run([sys.executable,"-m","PyInstaller","--noconfirm","--clean","--onefile","--windowed"]+args,check=True,cwd=ROOT)
basic=["--name",NAME]
if ICON:basic+=["--icon",ICON]
run(basic+[SOURCE])
app=ROOT/"dist"/(NAME+".exe")
archive=ROOT/"dist"/(NAME+"-Portable.zip")
with zipfile.ZipFile(archive,"w",zipfile.ZIP_DEFLATED) as out:
    for f in [app]+[ROOT/n for n in ASSETS]+[ROOT/"README.md",ROOT/"LICENSE"]:
        out.write(f,arcname=f.name)
args=["--name",NAME+"-Setup","--add-data",str(app)+";payload"]
for a in ASSETS:args+=["--add-data",str(ROOT/a)+";payload"]
if ICON:args+=["--icon",ICON]
run(args+["packaging/installer.py"])
print("BUILT",app,archive,ROOT/"dist"/(NAME+"-Setup.exe"))
