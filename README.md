# OpenFetch (Windows)

A lightweight graphical Windows manager for direct HTTP/HTTPS files, with progress, resume and parallel transfers when servers allow them.

Version 0.4.

## Download / دانلود

Download the latest Setup.exe from GitHub Releases for installation with shortcuts and uninstall; or download Portable ZIP for extraction and direct use of OpenFetch.exe.

## Source installation

Windows and Python 3.10+ with Tkinter required. Install dependencies with: python -m pip install -r requirements.txt

Then run: python openfetch.py

## Notes / نکات

Independent project, not affiliated with commercial Internet Download Manager (IDM).

Use for lawful downloads only. Never share browser cookies or login details.

## Security and license

See SECURITY.md, THIRD_PARTY.md and LICENSE. License: MIT. Contributions and responsible issue reports welcome.

## Reproducible Windows builds

Install Python 3.10+, run 'python -m pip install -r requirements.txt pyinstaller' then 'python build_windows.py'. Outputs are under dist/. The installer provides per-user installation and uninstall; it never requires administrator access.
