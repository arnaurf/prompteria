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
import sys
import json
import argparse
import queue
import os
import time
from pdf_manager import pdfManager
from input_handler import keyboardInputHandler, MidiInputHandler

# Parse input params
parser = argparse.ArgumentParser(description="Light midi-controlled Teleprompter using PDFs")
parser.add_argument(
    "-i", "--input",
    default="pdf_files.json",
    help="Path to the setlist file. It must be a json containing multiple PDF's file paths. Default: pdf_files.json"
)
args = parser.parse_args()
JSON_PATH = args.input

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


def setup_midi(pdf_manager, queue):
    """Setup the MIDI device for i/o"""
    midi_in = rtmidi.MidiIn()
    midi_out = rtmidi.MidiOut()
    available_ports = list_midi_ports()
    port_name = input("Select the MIDI device: ")

    if not available_ports:
        print("No MIDI ports detected")
        sys.exit(1)

    midi_in.open_port(int(port_name) - 1)
    midi_out.open_port(int(port_name) - 1)
    print(f"Listening to port {available_ports[int(port_name) - 1]}")

    return midi_in, midi_out


def main():
    dirname = os.path.dirname(__file__)
    pdf_folder = os.path.join(dirname, "pdf")

    # Check PDF files
    with open(JSON_PATH, 'r') as f:
        raw_pdf_files = json.load(f)
    pdf_files = {int(k): v for k, v in raw_pdf_files.items()}

    missing_files = [f"{key}: {path}" for key, subpath in pdf_files.items()
                     if not os.path.exists(os.path.join(pdf_folder, subpath))]
    if missing_files:
        print("ERROR: The following PDFs don't exist:")
        for missing in missing_files:
            print(f"  - {missing}")
        sys.exit(1)

    # Listen keyboard and MIDI device and add tasks to queue
    zathura = pdfManager(pdf_files, pdf_folder)
    action_queue = queue.Queue()
    midi_in, midi_out = setup_midi(zathura, action_queue)
    keyboardInputHandler(zathura, action_queue)

    # MAIN LOOP // Process and perform tasks from queue
    try:
        while True:
            while not action_queue.empty():
                action = action_queue.get()
                action()
            time.sleep(0.01)
    except KeyboardInterrupt:
        print("The show has ended!")
        zathura.close()

if __name__ == "__main__":
    main()
