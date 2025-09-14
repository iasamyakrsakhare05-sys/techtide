# techtide
🔒 Secure Data Wiping Tool

A command-line tool to securely erase files, folders, or entire drives with multiple wiping algorithms. It also generates a certificate of erasure in both .log and .pdf formats for audit and compliance purposes.

✨ Features

🔐 Password Protection – Setup & verify password before wiping.

🗑️ File, Folder, or Drive Wiping:

DoD 5220.22-M (3-pass)

Simple Random Overwrite (1-pass)

Gutmann Method (35-pass)

📂 Sensitive Content Scan before wiping.

⚡ Chunked Overwriting – Handles large files efficiently.

📜 Certificates of Erasure:

.log file (plain text)

.pdf file (formatted)

💻 Cross-Platform Support (Windows, Linux, macOS).

Drive label listing is Windows-only.

🛠️ Requirements

Python 3.8+

Dependencies:

pip install psutil tqdm reportlab rich InquirerPy


(Optional, Windows only)

pip install pywin32

🚀 Usage

Run the script:

python f.py

Main Menu Options:

Wipe a specific file – Securely erase one file.

Wipe all data from a drive – Select a removable/fixed drive.

Wipe all data from a folder – Permanently wipe entire folder.

Exit – Quit the program.

📑 Certificates

A .log file is generated automatically after wiping.

You will be asked if you want to generate a PDF certificate.

Example:

Certificate of Erasure
Generated at: 2025-09-14T10:25:00

Device ID: DESKTOP-1234
User Name: JohnDoe
System Info: Windows-10-10.0.19045-SP0
Processor: Intel64 Family 6 Model 158 Stepping 10 GenuineIntel

C:\path\to\file.txt - Pass 1: <hash>
C:\path\to\file.txt - Pass 2: <hash>
C:\path\to\file.txt - Deleted: 2025-09-14T10:25:05

⚠️ Warning

This tool permanently erases data. Once wiped, files cannot be recovered.
Use carefully and double-check paths/drives before confirming.

📜 License

MIT License – Free to use, modify, and distribute.
