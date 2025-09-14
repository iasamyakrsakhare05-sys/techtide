import os
import hashlib
import random
import datetime
import platform
import getpass
import psutil
from tqdm import tqdm
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from rich.console import Console
from rich.prompt import Prompt
from InquirerPy import inquirer
console = Console()


# Optional imports for Windows-specific features
try:
    import win32api
    import win32file
except ImportError:
    win32api = None
    win32file = None

# Constants
LOG_FILE = "certificate_of_erasure.log"
PDF_FILE = "certificate_of_erasure.pdf"
ENV_PASSWORD_KEY = "ERASE_TOOL_PASSWORD_HASH"
CHUNK_SIZE = 64 * 1024 * 1024  # 64 MB chunks to avoid huge memory usage

# System Info
device_id = platform.node()
user_name = getpass.getuser()
system_info = platform.platform()
processor_info = platform.processor()

def hash_password(password: str) -> str:
# Securely hash a password using PBKDF2.
    salt = b'static_salt'  # For demo; replace with a generated salt in prod
    return hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000).hex()

def scan_file_for_sensitive_content(file_path):
# Scan for sensitive keywords in a file's content.
    import re
    SENSITIVE_KEYWORDS = ['password', 'confidential', 'ssn', 'credit card', 'secret', 'private', 'classified']
    flagged_keywords = []
    try:
        with open(file_path, 'r', errors='ignore') as f:
            content = f.read().lower()
            for keyword in SENSITIVE_KEYWORDS:
                if re.search(r'\b' + re.escape(keyword) + r'\b', content):  # Corrected regex boundary
                    flagged_keywords.append(keyword)
    except Exception as e:
        flagged_keywords.append(f"Error reading file: {str(e)}")
    return flagged_keywords

def select_file_via_dialog():
# Open file dialog to select a file.
    import tkinter as tk
    from tkinter import filedialog
    root = tk.Tk()
    root.withdraw()
    return filedialog.askopenfilename(title="Select a file to wipe")

def setup_password():
# Prompt user to set a password and store its hash.
    if os.environ.get(ENV_PASSWORD_KEY) is None:
        print("\n🔐 First-time setup: Please create a secure password.")
        while True:
            pwd1 = getpass.getpass("Enter new password: ")
            pwd2 = getpass.getpass("Confirm password: ")
            if pwd1 == pwd2 and pwd1.strip():
                os.environ[ENV_PASSWORD_KEY] = hash_password(pwd1)
                print("✅ Password hash set for this session.")
                break
            else:
                print("❌ Passwords do not match or are empty. Try again.")

def verify_password():
# Verify entered password against stored hash.
    print("\n🔐 Password Required to Proceed")
    entered = getpass.getpass("Enter password: ")
    stored_hash = os.environ.get(ENV_PASSWORD_KEY)
    if stored_hash is None:
        print("❌ Password not set. Please restart the program.")
        return False
    return hash_password(entered) == stored_hash

def is_file_locked(file_path):
# Check if file is currently open or locked.
    for proc in psutil.process_iter(['open_files']):
        try:
            if proc.info['open_files']:
                for f in proc.info['open_files']:
                    if f.path == file_path:
                        return True
        except Exception:
            continue
    return False

def overwrite_file_in_chunks(file_path, pattern=None):
# Overwrite file content in chunks to avoid memory overload.
    size = os.path.getsize(file_path)
    with open(file_path, 'r+b') as f:
        remaining = size
        while remaining > 0:
            chunk_size = min(CHUNK_SIZE, remaining)
            data = os.urandom(chunk_size) if pattern is None else pattern * chunk_size
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
            remaining -= chunk_size

# Wiping methods
def wipe_file_dod(file_path):
# DoD 5220.22-M 3-pass wipe: zeros, ones, random.
    log_entries = []
    try:
        for pass_num, pattern in enumerate([b'\x00', b'\xFF', None], start=1):
            overwrite_file_in_chunks(file_path, pattern)
            log_entries.append((file_path, f"Pass {pass_num}", hashlib.sha256(pattern or os.urandom(1)).hexdigest()))
        os.remove(file_path)
        log_entries.append((file_path, "Deleted", datetime.datetime.now().isoformat()))
    except Exception as e:
        log_entries.append((file_path, "Error", str(e)))
    return log_entries

def wipe_file_random(file_path):
# Simple random overwrite (1-pass).
    log_entries = []
    try:
        overwrite_file_in_chunks(file_path)
        log_entries.append((file_path, "Random Pass", hashlib.sha256(os.urandom(1)).hexdigest()))
        os.remove(file_path)
        log_entries.append((file_path, "Deleted", datetime.datetime.now().isoformat()))
    except Exception as e:
        log_entries.append((file_path, "Error", str(e)))
    return log_entries

def wipe_file_gutmann(file_path):
# Simplified Gutmann method: 35 random passes.
    log_entries = []
    try:
        for pass_num in range(1, 36):
            overwrite_file_in_chunks(file_path)
            log_entries.append((file_path, f"Gutmann Pass {pass_num}", hashlib.sha256(os.urandom(1)).hexdigest()))
        os.remove(file_path)
        log_entries.append((file_path, "Deleted", datetime.datetime.now().isoformat()))
    except Exception as e:
        log_entries.append((file_path, "Error", str(e)))
    return log_entries

def list_drives_with_labels():
# List available drives with volume labels (Windows only).
    if not win32api or not win32file:
        print("Drive listing with labels is not supported on this OS.")
        return []
    drives = []
    drive_bits = win32api.GetLogicalDrives()
    for i in range(26):
        if drive_bits & (1 << i):
            drive = f"{chr(65 + i)}:\\"
            try:
                drive_type = win32file.GetDriveType(drive)
                if drive_type in (win32file.DRIVE_REMOVABLE, win32file.DRIVE_FIXED):
                    label = win32api.GetVolumeInformation(drive)[0]
                    drives.append((drive, label))
            except Exception:
                continue
    return drives

def wipe_path(target_path, wipe_func):
# Wipe all files in a folder or drive using the selected wipe function.
    log_entries = []
    for root, _, files in os.walk(target_path):
        for name in files:
            file_path = os.path.join(root, name)
            if is_file_locked(file_path):
                log_entries.append((file_path, "Locked", "File is currently open or in use."))
                continue
            log_entries.extend(wipe_func(file_path))
    return log_entries

def write_log_certificate(log_entries):
# Write log certificate to a text file.
    with open(LOG_FILE, 'w') as f:
        f.write("Certificate of Erasure\n")
        f.write(f"Generated at: {datetime.datetime.now().isoformat()}\n\n")
        f.write(f"Device ID: {device_id}\n")
        f.write(f"User Name: {user_name}\n")
        f.write(f"System Info: {system_info}\n")
        f.write(f"Processor: {processor_info}\n\n")
        for entry in log_entries:
            f.write(f"{entry[0]} - {entry[1]}: {entry[2]}\n")

def write_pdf_certificate(log_entries):
# Write log certificate to a PDF file.
    c = canvas.Canvas(PDF_FILE, pagesize=letter)
    width, height = letter
    y = height - 50
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y, "Certificate of Erasure")
    y -= 20
    c.setFont("Helvetica", 12)
    c.drawString(50, y, f"Generated at: {datetime.datetime.now().isoformat()}")
    y -= 20
    c.drawString(50, y, f"Device ID: {device_id}")
    y -= 15
    c.drawString(50, y, f"User Name: {user_name}")
    y -= 15
    c.drawString(50, y, f"System Info: {system_info}")
    y -= 15
    c.drawString(50, y, f"Processor: {processor_info}")
    y -= 30
    for entry in log_entries:
        line = f"{entry[0]} - {entry[1]}: {entry[2]}"
        c.drawString(50, y, line)
        y -= 15
        if y < 50:
            c.showPage()
            y = height - 50
    c.save()

def confirm_action(message):
# Prompt user for confirmation.
    print(f"\n⚠️ {message}")
    confirm = input("Type 'yes' to confirm: ")
    return confirm.lower() == 'yes'

def ask_certificate():
# Ask user if they want a PDF certificate.
    return input("\nDo you want to generate a PDF certificate of erasure? (yes/no): ").strip().lower() == 'yes'

def select_wipe_algorithm():
# Prompt user to select a wipe algorithm.
    print("\nSelect Wipe Algorithm:")
    print("1. DoD 5220.22-M (3-pass)")
    print("2. Simple Random Overwrite (1-pass)")
    print("3. Gutmann (35-pass)")
    choice = input("Enter your choice (1/2/3): ")
    return {'1': wipe_file_dod, '2': wipe_file_random, '3': wipe_file_gutmann}.get(choice, wipe_file_dod)


def main():
    console.print("[bold cyan]\n🔒 Welcome to Secure Data Wiping Tool 🔒[/bold cyan]")
    setup_password()
    if not verify_password():
        return

    main_choice = inquirer.select(
        message="Main Menu:",
        choices=[
            "Wipe a specific file",
            "Wipe all data from a drive",
            "Wipe all data from a folder",
            "Exit"
        ]
    ).execute()

    if main_choice == "Exit":
        console.print("[yellow]Exiting. Goodbye![/yellow]")
        return

    alg_choice = inquirer.select(
        message="Select Wipe Algorithm:",
        choices=[
            "DoD 5220.22-M (3-pass)",
            "Simple Random Overwrite (1-pass)",
            "Gutmann (35-pass)"
        ]
    ).execute()

    alg_map = {
        "DoD 5220.22-M (3-pass)": wipe_file_dod,
        "Simple Random Overwrite (1-pass)": wipe_file_random,
        "Gutmann (35-pass)": wipe_file_gutmann
    }
    wipe_func = alg_map.get(alg_choice, wipe_file_dod)
    log_entries = []

    if main_choice == "Wipe a specific file":
        file_path = select_file_via_dialog()
        if not file_path or not os.path.isfile(file_path):
            console.print("[red]Invalid file path.[/red]")
            return
        if confirm_action(f"Are you sure you want to permanently wipe the file: {file_path}?"):
            if is_file_locked(file_path):
                console.print("[red]❌ File is currently open or locked. Cannot wipe.[/red]")
                return
            flagged = scan_file_for_sensitive_content(file_path)
            if flagged:
                console.print(f"[bold yellow]⚠️ Sensitive content detected in {file_path}: {', '.join(flagged)}[/bold yellow]")
                if Prompt.ask("Do you still want to wipe this file?", choices=["yes", "no"]) != 'yes':
                    console.print("[cyan]Operation cancelled.[/cyan]")
                    return
            log_entries = wipe_func(file_path)

    elif main_choice == "Wipe all data from a drive":
        drives = list_drives_with_labels()
        if not drives:
            console.print("[red]No removable or fixed drives found.[/red]")
            return
        drive_selection = inquirer.select(
            message="Select drive to wipe:",
            choices=[f"{d[0]} - {d[1]}" for d in drives]
        ).execute()
        drive_index = [f"{d[0]} - {d[1]}" for d in drives].index(drive_selection)
        target_drive = drives[drive_index][0]
        if confirm_action(f"Are you sure you want to permanently wipe all data from drive: {target_drive}?"):
            if confirm_action("Type 'yes' again to confirm final wipe:"):
                log_entries = wipe_path(target_drive, wipe_func)

    elif main_choice == "Wipe all data from a folder":
        folder_path = Prompt.ask("Enter the full path of the folder to wipe")
        if not os.path.isdir(folder_path):
            console.print("[red]Invalid folder path.[/red]")
            return
        if confirm_action(f"Are you sure you want to permanently wipe all data from folder: {folder_path}?"):
            log_entries = wipe_path(folder_path, wipe_func)

    write_log_certificate(log_entries)
    console.print(f"[green]\n✅ Log certificate generated: {os.path.abspath(LOG_FILE)}[/green]")

    if ask_certificate():
        write_pdf_certificate(log_entries)
        console.print(f"[green]✅ PDF certificate generated: {os.path.abspath(PDF_FILE)}[/green]")


if __name__ == "__main__":
    main()