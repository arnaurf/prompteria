import time
import threading

NEXT_PAGE = 48  # MIDI note for "next page" (C3)
CHANNEL = 1     # Default MIDI channel


def keyboardInputHandler(pdf_manager, action_queue):
    """
    Start a thread to read keyboard commands.
    """
    def input_thread():
        while True:
            cmd = input("Enter PDF number or 'exit': ")
            if cmd == "exit":
                action_queue.put(lambda: exit())
            elif cmd.isdigit():
                n = int(cmd)
                action_queue.put(lambda pm=pdf_manager, num=n: pm.open_pdf(num))

    threading.Thread(target=input_thread, daemon=True).start()


class MidiInputHandler:
    """
    Handle MIDI messages and map them to PDF actions.
    """

    def __init__(self, port, midi_through, pdf_manager, queue):
        """
        Initialize MIDI handler with port, thru device, and PDF manager.
        """
        self.port = port
        self._wallclock = time.time()
        self.midi_through = midi_through
        self.pdf_manager = pdf_manager
        self.channel = CHANNEL
        self.action_queue = queue

    def __call__(self, event, data=None):
        """
        Process incoming MIDI events.
        """
        message, deltatime = event
        self._wallclock += deltatime
        self.midi_through.send_message(message)
        print("[%s] @%0.6f %r" % (self.port, self._wallclock, message))

        tipo_mensaje = message[0] & 0xF0
        canal_mensaje = message[0] & 0x0F  

        # Program Change: open PDF
        if tipo_mensaje == 0xC0 and canal_mensaje == self.channel:
            program_number = message[1]
            print(f"Program Change received: Program {program_number}")
            self.action_queue.put(lambda: self.pdf_manager.open_pdf(program_number))

        # Note On: next page
        elif tipo_mensaje == 0x90 and canal_mensaje == self.channel:
            note_number = message[1]
            if note_number == NEXT_PAGE:
                print("INFO: C3 Note (48) received.")
                self.action_queue.put(lambda: self.pdf_manager.turn_page())
