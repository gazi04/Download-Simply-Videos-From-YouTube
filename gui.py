import customtkinter as ctk
import os
import threading
import sys
from pathlib import Path
from tkinter import messagebox
from download import download_youtube_content, parse_multiple_urls

# Appearance Settings
ctk.set_appearance_mode("System")  # Modes: "System" (standard), "Dark", "Light"
ctk.set_default_color_theme("blue")  # Themes: "blue" (standard), "green", "dark-blue"

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Window configuration
        self.title("Simply YouTube Downloader")
        self.geometry("700x650")

        # Grid configuration (2 columns, several rows)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1) # URL Box
        self.grid_rowconfigure(7, weight=1) # Log Box

        # Header
        self.label = ctk.CTkLabel(self, text="Simply YouTube Downloader", font=ctk.CTkFont(size=24, weight="bold"))
        self.label.grid(row=0, column=0, padx=20, pady=(20, 10))

        # URL Input Label
        self.url_label = ctk.CTkLabel(self, text="Enter YouTube URL(s) (one per line or comma-separated):")
        self.url_label.grid(row=1, column=0, padx=20, pady=(10, 0), sticky="w")

        # URL Textbox
        self.url_textbox = ctk.CTkTextbox(self, height=150)
        self.url_textbox.grid(row=2, column=0, padx=20, pady=10, sticky="nsew")

        # Format Selection Frame
        self.format_frame = ctk.CTkFrame(self)
        self.format_frame.grid(row=3, column=0, padx=20, pady=10, sticky="ew")
        self.format_frame.grid_columnconfigure((0, 1), weight=1)

        self.format_var = ctk.StringVar(value="MP4")
        self.radio_mp4 = ctk.CTkRadioButton(self.format_frame, text="MP4 Video", variable=self.format_var, value="MP4")
        self.radio_mp4.grid(row=0, column=0, padx=20, pady=10)
        self.radio_mp3 = ctk.CTkRadioButton(self.format_frame, text="MP3 Audio", variable=self.format_var, value="MP3")
        self.radio_mp3.grid(row=0, column=1, padx=20, pady=10)

        # Buttons Frame
        self.button_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.button_frame.grid(row=4, column=0, padx=20, pady=10, sticky="ew")
        self.button_frame.grid_columnconfigure((0, 1, 2), weight=1)

        self.download_button = ctk.CTkButton(self.button_frame, text="Download", command=self.start_download, fg_color="#28a745", hover_color="#218838")
        self.download_button.grid(row=0, column=0, padx=10, pady=10, sticky="ew")

        self.open_folder_button = ctk.CTkButton(self.button_frame, text="Open Downloads", command=self.open_downloads)
        self.open_folder_button.grid(row=0, column=1, padx=10, pady=10, sticky="ew")

        self.exit_button = ctk.CTkButton(self.button_frame, text="Exit", command=self.quit, fg_color="#dc3545", hover_color="#c82333")
        self.exit_button.grid(row=0, column=2, padx=10, pady=10, sticky="ew")

        # Status Log Label
        self.log_label = ctk.CTkLabel(self, text="Status Log:")
        self.log_label.grid(row=6, column=0, padx=20, pady=(10, 0), sticky="w")

        # Log Textbox
        self.log_textbox = ctk.CTkTextbox(self, height=200, state="disabled", font=("Consolas", 12))
        self.log_textbox.grid(row=7, column=0, padx=20, pady=(0, 20), sticky="nsew")

        self.download_in_progress = False

    def get_download_path(self):
        """Returns the default download path in the user's Music folder."""
        music_path = Path.home() / "Music" / "Simply-Videos-Downloads"
        music_path.mkdir(parents=True, exist_ok=True)
        return str(music_path)

    def open_downloads(self):
        """Opens the download folder in the system file explorer."""
        path = self.get_download_path()
        if sys.platform == 'win32':
            os.startfile(path)
        elif sys.platform == 'darwin':
            os.system(f'open "{path}"')
        else:
            os.system(f'xdg-open "{path}"')

    def log(self, message):
        """Updates the log textbox with a new message."""
        self.log_textbox.configure(state="normal")
        self.log_textbox.insert("end", f"{message}\n")
        self.log_textbox.see("end")
        self.log_textbox.configure(state="disabled")

    def start_download(self):
        if self.download_in_progress:
            messagebox.showwarning("Warning", "A download is already in progress!")
            return

        raw_input = self.url_textbox.get("1.0", "end-1c").strip()
        if not raw_input:
            messagebox.showerror("Error", "Please enter at least one YouTube URL.")
            return

        urls = parse_multiple_urls(raw_input)
        if not urls:
            messagebox.showerror("Error", "No valid YouTube URLs found.")
            return

        format_choice = self.format_var.get()
        audio_only = (format_choice == "MP3")

        self.log("-" * 50)
        self.log(f"🚀 Starting download to: {self.get_download_path()}")
        self.download_button.configure(state="disabled", text="Downloading...")
        self.download_in_progress = True

        # Run download in a separate thread
        thread = threading.Thread(target=self.run_download, args=(urls, audio_only), daemon=True)
        thread.start()

    def run_download(self, urls, audio_only):
        try:
            download_youtube_content(
                urls=urls,
                output_path=self.get_download_path(),
                audio_only=audio_only,
                logger=self.log
            )
            self.after(0, self.finish_download, "✅ Download process finished!")
        except Exception as e:
            self.after(0, self.log, f"❌ Fatal Error: {str(e)}")
            self.after(0, self.finish_download, "❌ Download failed.")

    def finish_download(self, status_message):
        self.log(status_message)
        self.download_button.configure(state="normal", text="Download")
        self.download_in_progress = False
        messagebox.showinfo("Finished", status_message)

def main():
    app = App()
    app.mainloop()

if __name__ == "__main__":
    main()
