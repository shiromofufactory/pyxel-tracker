class MidiInput:
    def __init__(self):
        self.enabled = False
        self._warned_runtime_error = False
        self.port = None
        self.mido = None

        try:
            import mido

            self.mido = mido
        except Exception as err:
            print(
                "[WARN] MIDI input is disabled: failed to import mido/python-rtmidi "
                f"({err})."
            )
            return

        try:
            names = self.mido.get_input_names()
            if not names:
                print("[WARN] MIDI input is disabled: no MIDI input device found.")
                return
            self.port = self.mido.open_input(names[0])
            self.enabled = True
            print(f"[INFO] MIDI input connected: {names[0]}")
        except Exception as err:
            print(
                "[WARN] MIDI input is disabled: failed to open MIDI input port "
                f"({err})."
            )

    def poll(self):
        if not self.enabled or self.port is None:
            return []

        events = []
        try:
            for msg in self.port.iter_pending():
                if msg.type == "note_on":
                    velocity = getattr(msg, "velocity", 0)
                    if velocity > 0:
                        events.append(("on", msg.note))
                    else:
                        events.append(("off", msg.note))
                elif msg.type == "note_off":
                    events.append(("off", msg.note))
        except Exception as err:
            if not self._warned_runtime_error:
                print(
                    "[WARN] MIDI input has been disabled due to runtime error "
                    f"({err})."
                )
                self._warned_runtime_error = True
            self.enabled = False
            if self.port is not None:
                try:
                    self.port.close()
                except Exception:
                    pass
                self.port = None
            return []
        return events
