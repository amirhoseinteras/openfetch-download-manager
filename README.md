# OpenFetch — Free and Open-Source Windows Software

Independent Windows HTTP/HTTPS download manager with progress indicators, resumable transfers, and parallel downloads when supported.

[![Automated tests](https://github.com/amirhoseinteras/openfetch-download-manager/actions/workflows/tests.yml/badge.svg)](https://github.com/amirhoseinteras/openfetch-download-manager/actions/workflows/tests.yml)
[Download for Windows](https://github.com/amirhoseinteras/openfetch-download-manager/releases/latest) · [Source code](https://github.com/amirhoseinteras/openfetch-download-manager) · [Report a problem](https://github.com/amirhoseinteras/openfetch-download-manager/issues)

**Version:** 0.4 · **Platform:** Windows · **License:** MIT

## Features
- Download files over HTTP or HTTPS using a desktop interface.
- Monitor progress; resume downloads when a remote server supports range requests.
- Use parallel transfer mode where the server supports it.

## Download and install

| Version | Direct download | How to use |
| --- | --- | --- |
| Installer | [OpenFetch-Setup.exe](https://github.com/amirhoseinteras/openfetch-download-manager/releases/latest/download/OpenFetch-Setup.exe) | Launch setup; installs shortcuts and an uninstaller for the current user |
| Portable | [OpenFetch-Portable.zip](https://github.com/amirhoseinteras/openfetch-download-manager/releases/latest/download/OpenFetch-Portable.zip) | Unzip first; launch OpenFetch.exe; no installation required |
| Checksum | [SHA256SUMS.txt](https://github.com/amirhoseinteras/openfetch-download-manager/releases/latest/download/SHA256SUMS.txt) | Verify downloads using SHA-256 |

### Verify your download

~~~powershell
Get-FileHash .\OpenFetch-Setup.exe -Algorithm SHA256
~~~
Compare the calculated hash with the entry for the same filename in SHA256SUMS.txt.

**Security note:** The Windows EXE files are unsigned. Windows SmartScreen may warn you. Verify files and source code; do not disable security protections just to install an unfamiliar program.

## Requirements and limitations

- Resuming and parallel transfer depend on the remote server; they cannot be guaranteed for every URL.
- Independent software, not associated with or endorsed by Internet Download Manager (IDM).
- Use only with content and files you are legally permitted to download or handle.

## Run and test from source

- Windows with Python 3.10+ and Tkinter.
- Clone this repository and open a terminal inside it.
~~~powershell
python -m pip install -r requirements.txt
python openfetch.py
python -m unittest discover -s tests -v
~~~

For a Windows executable, install PyInstaller and run the included build script. Installer packaging sources are under packaging/.

## Open-source development

- [License](LICENSE) · [Security guidance](SECURITY.md) · [Third-party notices](https://github.com/amirhoseinteras/openfetch-download-manager/blob/main/THIRD_PARTY.md)
- [Contributing](CONTRIBUTING.md) · [Version history](CHANGELOG.md) · [Issues](https://github.com/amirhoseinteras/openfetch-download-manager/issues)
- The published source is intended to be readable by developers, search engines and AI assistants. Check the code for definitive technical behavior.

## فارسی — راهنمای کوتاه

**OpenFetch** یک نرم‌افزار رایگان و متن‌باز برای ویندوز است. برای نصب، فایل Setup و برای اجرای بدون نصب، فایل Portable ZIP را از بخش Releases دریافت کنید.
برای اطمینان از سالم بودن فایل دانلودشده، مقدار SHA-256 را با فایل SHA256SUMS.txt همان نسخه مقایسه کنید.

---
**Official repository:** https://github.com/amirhoseinteras/openfetch-download-manager · **Downloads:** https://github.com/amirhoseinteras/openfetch-download-manager/releases