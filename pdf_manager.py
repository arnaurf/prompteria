import subprocess
import time
import os
from pydbus import SessionBus


class pdfManager:
    """
    Manage PDF playback in Zathura via D-Bus.
    """

    dbus = None
    zathura_ps = None
    current_pdf = 1
    current_page = 1
    pdf_files = {}

    def __init__(self, pdf_files, pdf_folder):
        """
        Start Zathura with the given PDF list and folder.
        """
        self.pdf_folder = pdf_folder
        self.start_zathura(pdf_files)

    def clear_zathura_sessions(self):
        """
        Delete Zathura session and history files.
        """
        home = os.path.expanduser("~")
        sessions_path = os.path.join(home, ".local", "share", "zathura", "sessions")
        history_path = os.path.join(home, ".local", "share", "zathura", "history")

        if os.path.exists(sessions_path):
            for f in os.listdir(sessions_path):
                try:
                    os.remove(os.path.join(sessions_path, f))
                except Exception as e:
                    print(f"Error removing session {f}: {e}")

        try:
            os.remove(history_path)
        except Exception as e:
            print(f"Error removing history: {e}")

    def start_zathura(self, pdf_files):
        """
        Launch Zathura in presentation mode with the first PDF.
        """
        self.clear_zathura_sessions()
        self.pdf_files = pdf_files

        self.zathura_ps = subprocess.Popen([
            'zathura',
            f"{self.pdf_folder}/{self.pdf_files[self.current_pdf]}",
            '--mode=presentation',
            '--page=1'
        ])
        time.sleep(4)

        dbus = SessionBus()
        service_name = None
        for name in dbus.get("org.freedesktop.DBus").ListNames():
            if name.startswith("org.pwmt.zathura.PID"):
                service_name = name
                break

        self.dbus = dbus.get(service_name, "/org/pwmt/zathura")
        self.current_page = 1
        self.dbus.GotoPage(self.current_page)  # Ensure page=0

    def __del__(self):
        """Cleanup placeholder."""
        pass

    def is_dbus_active(self):
        """
        Check if Zathura D-Bus is reachable.
        """
        try:
            self.dbus.Ping()
            return True
        except Exception:
            return False

    def open_pdf(self, new_pdf_idx):
        """
        Open a new PDF by index.
        """
        file_path = os.path.join(self.pdf_folder, self.pdf_files[new_pdf_idx])
        self.current_pdf = new_pdf_idx

        if not self.is_dbus_active():
            self.start_zathura()

        try:
            self.current_page = 0
            self.dbus.OpenDocument(file_path, "", self.current_page)
        except Exception as e:
            print(f"Error opening PDF: {e}")
            raise

        time.sleep(0.1)

    def close(self):
        """
        Stop the Zathura process.
        """
        try:
            if self.zathura_ps:
                self.zathura_ps.terminate()
                self.zathura_ps.wait()
        except Exception as e:
            print(f"Error closing Zathura: {e}")

    def turn_page(self):
        """
        Go to the next page.
        """
        
        if self.dbus:
            try:
                self.current_page = self.dbus.pagenumber + 1
                self.dbus.GotoPage(self.current_page)
            except Exception as e:
                print(f"Error turning page: {e}")
