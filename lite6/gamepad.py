"""Read a USB / Bluetooth gamepad as one simple state, whatever the brand.

    pad = Gamepad()          # Xbox, PlayStation, Switch Pro, most others (through pygame / SDL)
    pad = Gamepad(hid=True)  # cheap "Generic USB Joystick" (USB id 0079:0006) read directly, no SDL
    s = pad.read()           # s.left_x, s.left_y, s.right_x, s.right_y: -1..1, right / up = +
                             # s.dpad: (x, y) in -1, 0, 1      s.pressed: buttons pressed since the last read

Button names in s.pressed: "open", "close" (the shoulder buttons L1 / R1), "slower", "faster" (the triggers
L2 / R2), "point_down" (A / cross / button 1), "clear" (Back / Select / Share).
"""
from dataclasses import dataclass, field

DEADZONE = 0.12  # stick fraction ignored, so a stick that does not centre perfectly does not drift the arm


def shape(v):
    """Deadzone, then square (keeping the sign) so small pushes are very slow and full push is full speed."""
    v = max(-1.0, min(1.0, v))
    return 0.0 if abs(v) < DEADZONE else v * abs(v)


@dataclass
class PadState:
    left_x: float = 0.0
    left_y: float = 0.0
    right_x: float = 0.0
    right_y: float = 0.0
    dpad: tuple = (0, 0)
    pressed: set = field(default_factory=set)


class Gamepad:
    def __init__(self, hid=False):
        self._held = set()
        self._read_raw = self._open_hid() if hid else self._open_sdl()

    def read(self):
        """The newest state. Buttons count as pressed once, on the read where they go down."""
        state, held = self._read_raw()
        state.pressed = held - self._held
        self._held = held
        return state

    # --- Xbox / PlayStation / most pads: SDL's GameController layer knows their button layout ---
    def _open_sdl(self):
        import os
        os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
        import pygame
        from pygame._sdl2 import controller

        pygame.init()
        controller.init()
        if controller.get_count() == 0:
            raise SystemExit("No gamepad found. Plug it in (or pair it), then run again. "
                             "A cheap generic USB pad may need --hid.")
        if not controller.is_controller(0):
            raise SystemExit("SDL does not know this gamepad's layout. Try --hid (USB id 0079:0006 pads), or "
                             "use an Xbox / PlayStation controller.")
        pad = controller.Controller(0)
        print(f"gamepad: {pad.name}")
        axis = lambda a: pad.get_axis(a) / 32767
        buttons = {"open": pygame.CONTROLLER_BUTTON_LEFTSHOULDER, "close": pygame.CONTROLLER_BUTTON_RIGHTSHOULDER,
                   "point_down": pygame.CONTROLLER_BUTTON_A, "clear": pygame.CONTROLLER_BUTTON_BACK}

        def read_raw():
            pygame.event.pump()
            held = {name for name, b in buttons.items() if pad.get_button(b)}
            if axis(pygame.CONTROLLER_AXIS_TRIGGERLEFT) > 0.5:
                held.add("slower")
            if axis(pygame.CONTROLLER_AXIS_TRIGGERRIGHT) > 0.5:
                held.add("faster")
            dpad = (pad.get_button(pygame.CONTROLLER_BUTTON_DPAD_RIGHT) - pad.get_button(pygame.CONTROLLER_BUTTON_DPAD_LEFT),
                    pad.get_button(pygame.CONTROLLER_BUTTON_DPAD_UP) - pad.get_button(pygame.CONTROLLER_BUTTON_DPAD_DOWN))
            state = PadState(left_x=shape(axis(pygame.CONTROLLER_AXIS_LEFTX)),
                             left_y=shape(-axis(pygame.CONTROLLER_AXIS_LEFTY)),  # SDL: down = +
                             right_x=shape(axis(pygame.CONTROLLER_AXIS_RIGHTX)),
                             right_y=shape(-axis(pygame.CONTROLLER_AXIS_RIGHTY)),
                             dpad=dpad)
            return state, held

        return read_raw

    # --- Generic USB Joystick 0079:0006 (common no-name pad): raw 8-byte USB reports via hidapi ---
    def _open_hid(self, vendor=0x79, product=0x6):
        import hid

        pad = hid.device()
        try:
            pad.open(vendor, product)
        except OSError:
            raise SystemExit(f"No USB gamepad with id {vendor:04x}:{product:04x} found. Is it plugged in?")
        pad.set_nonblocking(1)
        print(f"gamepad: {pad.get_product_string()}  (press its ANALOG button so the LED is red)")
        last = [bytes([128, 128, 128, 128, 128, 15, 0, 0])]  # sticks centred, nothing pressed

        def read_raw():
            while r := pad.read(8):  # drain to the newest report
                last[0] = r
            return parse_hid_report(last[0])

        return read_raw


# Generic USB Joystick 0079:0006 report (8 bytes): bytes 0-4 = stick axes (128 = centre), byte 5 = d-pad
# (low 4 bits, 15 = none) + buttons, byte 6 = more buttons, one bit each. Without ANALOG on (LED red),
# its sticks act like the d-pad.
HID_BUTTONS = {"open": (6, 0), "close": (6, 1), "slower": (6, 2), "faster": (6, 3), "clear": (6, 4),
               "point_down": (5, 4)}  # name -> (byte, bit)
HID_DPAD = {0: (0, 1), 2: (1, 0), 4: (0, -1), 6: (-1, 0)}


def parse_hid_report(r):
    """One raw report -> (PadState, set of held button names)."""
    axis = lambda byte: (byte - 128) / 127
    held = {name for name, (byte, bit) in HID_BUTTONS.items() if r[byte] >> bit & 1}
    state = PadState(left_x=shape(axis(r[0])), left_y=shape(-axis(r[1])),
                     right_x=shape(axis(r[3])), right_y=shape(-axis(r[4])),
                     dpad=HID_DPAD.get(r[5] & 0x0F, (0, 0)))
    return state, held
