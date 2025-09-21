# PROMPTERIA
#
# Copyright (C) 2025 Arnau Ruiz Fernandez
#
# MIDI PDF Teleprompter is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# See <https://www.gnu.org/licenses/> for more details.

import rtmidi
import subprocess
import os
import sys
import time
import json
import argparse
from pydbus import SessionBus

NEXT_PAGE = 48 # C3
CHANNEL = 1

parser = argparse.ArgumentParser(description="Reproductor de PDFs controlado por MIDI")
parser.add_argument(
    "-i", "--input",
    default="pdf_files.json",
    help="Ruta al archivo JSON con la lista de PDFs (por defecto: pdf_files.json)"
)
args = parser.parse_args()
JSON_PATH = args.input

class pdfManager():
    dbus = None
    zathura_ps = None
    current_pdf = 1
    current_page = 0
    pdf_files = {}

    def __init__(self, pdf_files, pdf_folder):
        self.pdf_folder = pdf_folder
        self.start_zathura(pdf_files)

    def clear_zathura_sessions(self):
        """Remove previous sessions and configs"""
        home = os.path.expanduser("~")
        sessions_path = os.path.join(home, ".local", "share", "zathura", "sessions")
        history_path = os.path.join(home, ".local", "share", "zathura", "history")

        if os.path.exists(sessions_path):
            for f in os.listdir(sessions_path):
                try:
                    os.remove(os.path.join(sessions_path, f))
                except Exception as e:
                    print(f"Error when removing sessions {f}: {e}")

        if os.path.exists(history_path):
            for f in os.listdir(history_path):
                try:
                    os.remove(os.path.join(history_path, f))
                except Exception as e:
                    print(f"Error when removing history {f}: {e}")

    def start_zathura(self, pdf_files):
        self.clear_zathura_sessions()
        self.pdf_files = pdf_files
        self.zathura_ps = subprocess.Popen(['zathura', f"{self.pdf_folder}/{self.pdf_files[self.current_pdf]}", '--mode=presentation', '--page=1'])
        time.sleep(4)
        dbus = SessionBus()
        service_name = None
        for name in dbus.get("org.freedesktop.DBus").ListNames():
            if name.startswith("org.pwmt.zathura.PID"):
                service_name = name
                break
        self.dbus = dbus.get(service_name, "/org/pwmt/zathura")
        self.current_page = 0
        self.dbus.GotoPage(self.current_page) # --page=1 on zathura does not always works, lets make sure the pdf is at page 0

    def __del__(self):
        pass

    def is_dbus_active(self):
        try:
            self.dbus.Ping()
            return True
        except Exception:
            return False

    def open_pdf(self, new_pdf_idx):
        """Opens the PDF using Zathura in Full Screen mode"""
        file_path = os.path.join(self.pdf_folder, self.pdf_files[new_pdf_idx])
        self.current_pdf = new_pdf_idx
        if not self.is_dbus_active():
            self.start_zathura()

        # Open the new PDF with Zathura
        try:
            self.current_page = 0
            self.dbus.OpenDocument(file_path, "", self.current_page)
        except Exception as e:
            print(f"Error opening dbus: {e}")
            raise

        #Wait to make sure Zathura has started
        time.sleep(0.1)

    def turn_page(self):
        self.current_page += 1
        self.dbus.GotoPage(self.current_page)

class MidiInputHandler(object):
    def __init__(self, port, midi_through, channel, pdf_manager):
        self.port = port
        self._wallclock = time.time()
        self.midi_through = midi_through
        self.pdf_manager = pdf_manager
        self.channel = channel

    def __call__(self, event, data=None):
        message, deltatime = event
        self._wallclock += deltatime
        self.midi_through.send_message(message)
        print("[%s] @%0.6f %r" % (self.port, self._wallclock, message))

        tipo_mensaje = message[0] & 0xF0  # Mask
        canal_mensaje = message[0] & 0x0F  

        if tipo_mensaje == 0xC0 and canal_mensaje == self.channel:  # Program Change message (0xC0 a 0xCF)
           program_number = message[1]  # Second byte contains the Program Number
           print(f"Program Change received: Program {program_number}")
           self.pdf_manager.open_pdf(program_number)

        elif tipo_mensaje == 0x90 and canal_mensaje == self.channel:  # Note Off message (0x90 a 0x9F)
            note_number = message[1]  # Second byte contains the note numnber.
            if note_number == NEXT_PAGE:
                print("INFO: C3 Note (48) received.")
                self.pdf_manager.turn_page()



def list_midi_ports():
    """List all available MIDI devices"""
    midi_in = rtmidi.MidiIn()
    available_ports = midi_in.get_ports()

    if available_ports:
        print("Available MIDI devices:")
        for i, port in enumerate(available_ports):
            print(f"{i + 1}: {port}")
        return available_ports
    else:
        print("No MIDI ports detected")

def main():
    """Main: Find, listen the MIDI device and react when a signal is received"""
    dirname = os.path.dirname(__file__)
    pdf_folder = os.path.join(dirname, "pdf")
    midi_in = rtmidi.MidiIn()
    midi_through = rtmidi.MidiOut()
    available_ports = list_midi_ports()
    port_name = input("Introduce the MIDI port number to use:")
    channel = CHANNEL - 1 # First element is idx=0

    # Open MIDI device
    if available_ports:
        midi_in.open_port(int(port_name) - 1)
        midi_through.open_port(int(port_name) - 1)
        print(f"Listening to port {available_ports[int(port_name) - 1]}")
    else:
        print("No MIDI ports detected")
        return

    with open(JSON_PATH, 'r') as f:
        raw_pdf_files = json.load(f)

    # Convert keys to int
    pdf_files = {int(k): v for k, v in raw_pdf_files.items()}

    # Check PDF
    missing_files = [f"{key}: {path}" for key, subpath in pdf_files.items() if not os.path.exists(os.path.join(pdf_folder, subpath))]
    if missing_files:
        print("ERROR: The following PDF's doesn't exist:")
        for missing in missing_files:
            print(f"  - {missing}")
        sys.exit(1)

    zathura = pdfManager(pdf_files, pdf_folder)

    print("Attaching MIDI input callback handler.")
    midi_in.set_callback(MidiInputHandler(port_name, midi_through, channel, zathura))

    try:
        # Manually open a PDF or wait for MIDI signals.
        while True:
            command = input("Introduce the PDF number or 'exit' to end the session: ")
            if command == 'exit':
                break
            elif command.isdigit() and int(command) in zathura.pdf_files:
                print(zathura.pdf_files.get(int(command)))
                zathura.open_pdf(int(command))
    except KeyboardInterrupt:
        print("The show has ended!")
        zathura.close()


if __name__ == "__main__":
    main()
