import os
import sys
import subprocess

def build_exe():
    """Build the Windows executable using PyInstaller."""
    print("🚀 Starting build process...")
    
    # Ensure pyinstaller is installed
    try:
        import PyInstaller
    except ImportError:
        print("📦 Installing PyInstaller...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

    # Get customtkinter path for assets
    import customtkinter
    customtkinter_path = os.path.dirname(customtkinter.__file__)

    # Define the command
    cmd = [
        "pyinstaller",
        "--noconfirm",
        "--onefile",
        "--windowed",
        "--name", "Simply-YouTube-Downloader",
        "--add-data", f"download.py{os.pathsep}.",
        "--add-data", f"{customtkinter_path}{os.pathsep}customtkinter/",
        "gui.py"
    ]

    print(f"🔨 Running command: {' '.join(cmd)}")
    
    try:
        subprocess.check_call(cmd)
        print("\n✅ Build successful!")
        print(f"📁 Your executable is located in the 'dist' folder.")
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Build failed: {e}")

if __name__ == "__main__":
    if sys.platform != "win32":
        print("⚠️  Warning: This script is intended to be run on Windows to create a .exe file.")
        confirm = input("Do you want to continue anyway? (y/n): ")
        if confirm.lower() != 'y':
            sys.exit(0)
    
    build_exe()
