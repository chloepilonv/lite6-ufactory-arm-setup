"""Step 4: drive the arm from the keyboard. MOVES THE ARM.

Run in a terminal and press keys (no Enter needed). Each press is one small step.

  w / s : tool x + / -        a / d : tool y + / -        q / e : tool z up / down      (mm, base frame)
  j / l : joint 1 - / +       i / k : joint 2 - / +       u / o : joint 3 + / -
  f / g : joint 4 - / +       n / m : joint 5 - / +       v / b : joint 6 - / +         (deg)
  t / y : gripper open / close    r : point the tool straight down
  [ / ] : smaller / bigger steps  c : clear error + enable  x : quit

    python scripts/04_teleop_keyboard.py
    python scripts/04_teleop_keyboard.py --jog   # hold a key to move smoothly instead of one step per press

With --jog the arm moves at 2 x step per second while a key is held and stops ~0.15 s after you let go.
Set your OS key-repeat delay to short and the repeat rate to fast for a smooth start.
Works on macOS and Linux (it reads raw key presses from the terminal).
"""
import sys
import termios
import time
import tty

from lite6 import call, confirm, connect, enable, parser, show

p = parser(__doc__)
p.add_argument("--jog", action="store_true", help="hold keys to move smoothly (velocity mode)")
args = p.parse_args()

STEP_MM, STEP_DEG = 20.0, 5.0
FIRST_HOLD, REPEAT_HOLD = 0.6, 0.15  # s one velocity command lasts: the first covers the OS key-repeat delay
XYZ_KEYS = {"w": (1, 0, 0), "s": (-1, 0, 0), "a": (0, 1, 0), "d": (0, -1, 0), "q": (0, 0, 1), "e": (0, 0, -1)}
JOINT_KEYS = {"j": (1, -1), "l": (1, 1), "i": (2, -1), "k": (2, 1), "u": (3, 1), "o": (3, -1),
              "f": (4, -1), "g": (4, 1), "n": (5, -1), "m": (5, 1), "v": (6, -1), "b": (6, 1)}

arm = connect("04_teleop_keyboard", args.ip)
confirm("Keyboard teleop will move the arm.")
enable(arm)
print(__doc__)
mode, last_key, last_time, last_log = 0, None, 0.0, 0.0


def use_mode(m):
    """0 = position (steps), 4 = joint velocity, 5 = cartesian velocity (--jog)."""
    global mode
    if mode != m:
        arm.set_mode(m)
        arm.set_state(0)
        time.sleep(0.05)
        mode = m


def jog(key, what, send):
    """One velocity command that expires on its own, so releasing the key stops the arm."""
    global last_key, last_time, last_log
    now = time.time()
    held = key == last_key and now - last_time < FIRST_HOLD + 0.1
    code = send(REPEAT_HOLD if held else FIRST_HOLD)
    last_key, last_time = key, now
    if code or now - last_log > 0.3:  # otherwise ~30 log lines per second
        show(arm, what, code)
        last_log = now


def move_xyz(dx, dy, dz):
    if args.jog:
        use_mode(5)
        v = [dx * 2, dy * 2, dz * 2, 0, 0, 0]
        return jog((dx, dy, dz), f"jog {v[:3]} mm/s", lambda hold: arm.vc_set_cartesian_velocity(v, duration=hold))
    use_mode(0)
    code = arm.set_position(x=dx, y=dy, z=dz, relative=True, speed=50, wait=True)
    show(arm, f"move xyz {dx:+.0f} {dy:+.0f} {dz:+.0f} mm", code)


def move_joint(n, ddeg):
    if args.jog:
        use_mode(4)
        v = [0] * 6
        v[n - 1] = ddeg * 2
        return jog((n, ddeg), f"jog joint {n} {ddeg * 2:+.0f} deg/s",
                   lambda hold: arm.vc_set_joint_velocity(v, is_radian=False, duration=hold))
    use_mode(0)
    code = arm.set_servo_angle(servo_id=n, angle=ddeg, relative=True, speed=20, wait=True)
    show(arm, f"joint {n} {ddeg:+.0f} deg", code)


fd = sys.stdin.fileno()
old_terminal = termios.tcgetattr(fd)
try:
    tty.setcbreak(fd)  # read single key presses without Enter
    while True:
        k = sys.stdin.read(1)
        if k == "x":
            break
        elif k in XYZ_KEYS:
            move_xyz(*(s * STEP_MM for s in XYZ_KEYS[k]))
        elif k in JOINT_KEYS:
            n, sign = JOINT_KEYS[k]
            move_joint(n, sign * STEP_DEG)
        elif k == "t":
            use_mode(0)
            show(arm, "gripper open", arm.open_lite6_gripper())
        elif k == "y":
            use_mode(0)
            show(arm, "gripper close", arm.close_lite6_gripper())
        elif k == "r":
            use_mode(0)
            x, y, z = arm.position[:3]
            show(arm, "point down", arm.set_position(x, y, z, 180, 0, 0, speed=40, wait=True))
        elif k == "[":
            STEP_MM, STEP_DEG = max(2, STEP_MM / 2), max(1, STEP_DEG / 2)
            print(f"step {STEP_MM} mm / {STEP_DEG} deg")
        elif k == "]":
            STEP_MM, STEP_DEG = min(80, STEP_MM * 2), min(20, STEP_DEG * 2)
            print(f"step {STEP_MM} mm / {STEP_DEG} deg")
        elif k == "c":
            enable(arm)
            mode = 0
finally:
    termios.tcsetattr(fd, termios.TCSADRAIN, old_terminal)
    # Motors off: the brakes hold the pose, and holding still with motors on slowly heats the wrist joint.
    call(arm, "motion_enable", False)
