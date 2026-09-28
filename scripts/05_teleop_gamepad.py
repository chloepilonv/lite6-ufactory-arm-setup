"""Step 5: drive the arm with a gamepad. MOVES THE ARM (except with --test-pad).

Hold a stick and the tool moves smoothly, faster the further you push. Let go and it stops within 0.2 s.

  left stick      : tool x / y (base frame; up = +x, left = +y)
  right stick     : up / down = tool z;  left / right = twist the gripper (only while the other axes are still)
  d-pad           : tilt the tool about its tip (only while the sticks are still)
  L1 / R1         : gripper open / close
  L2 / R2         : slower / faster (x0.5 / x2)
  A (cross)       : point the tool straight down
  Back / Select   : clear error + enable
  Ctrl-C          : quit (motors off, brakes hold the pose)

    python scripts/05_teleop_gamepad.py --test-pad   # first: check the sticks and buttons, arm not touched
    python scripts/05_teleop_gamepad.py              # Xbox / PlayStation / most gamepads
    python scripts/05_teleop_gamepad.py --hid        # generic USB pad 0079:0006 (needs: pip install -e ".[hid]")
"""
import time

from lite6 import call, confirm, connect, enable, log, parser, show
from lite6.gamepad import Gamepad

MAX_MM_S, MAX_DEG_S = 60.0, 30.0  # full stick at speed x1
TILT_DEG_S = 10.0                  # d-pad tilt at speed x1
HOLD = 0.2                         # s each velocity command lasts: if this script freezes, the arm stops by itself
MAX_REACH_MM = 400.0               # horizontal distance from the base axis. The Lite 6 is fully stretched at ~440 mm,
                                   # and near there a slow tool move needs very fast joints (error C24).

p = parser(__doc__)
p.add_argument("--hid", action="store_true", help="read a generic USB pad (0079:0006) directly")
p.add_argument("--test-pad", action="store_true", help="print the gamepad state; never connects to the arm")
args = p.parse_args()
pad = Gamepad(hid=args.hid)

if args.test_pad:
    print("move sticks, press buttons, Ctrl-C to stop")
    while True:
        s = pad.read()
        if s.pressed:
            print(f"pressed: {sorted(s.pressed)}")
        if any((s.left_x, s.left_y, s.right_x, s.right_y, *s.dpad)):
            print(f"left ({s.left_x:+.2f}, {s.left_y:+.2f})  right ({s.right_x:+.2f}, {s.right_y:+.2f})  dpad {s.dpad}")
        time.sleep(0.1)

arm = connect("05_teleop_gamepad", args.ip)
confirm("Gamepad teleop will move the arm.")


def velocity_mode():
    arm.set_mode(5)  # 5 = cartesian velocity
    arm.set_state(0)
    time.sleep(0.05)


def position_mode():
    arm.vc_set_cartesian_velocity([0] * 6)
    arm.set_mode(0)
    arm.set_state(0)
    time.sleep(0.05)


enable(arm, mode=5)
print(__doc__)
scale, moving, last_log = 1.0, False, 0.0
try:
    while True:
        s = pad.read()
        if "slower" in s.pressed:
            scale = max(0.125, scale / 2)
            log(f"speed x{scale}")
        if "faster" in s.pressed:
            scale = min(2.0, scale * 2)
            log(f"speed x{scale}")
        if "open" in s.pressed or "close" in s.pressed:  # gripper commands need position mode
            position_mode()
            if "open" in s.pressed:
                show(arm, "gripper open", arm.open_lite6_gripper())
            else:
                show(arm, "gripper close", arm.close_lite6_gripper())
            velocity_mode()
        if "point_down" in s.pressed:
            position_mode()
            x, y, z = arm.position[:3]
            show(arm, "point down", arm.set_position(x, y, z, 180, 0, 0, speed=40, wait=True))
            velocity_mode()
        if "clear" in s.pressed:
            enable(arm, mode=5)

        # tool velocity: x, y, z in mm/s, then roll, pitch, yaw in deg/s
        v = [s.left_y * MAX_MM_S * scale, -s.left_x * MAX_MM_S * scale, s.right_y * MAX_MM_S * scale, 0, 0, 0]
        x, y = arm.position[:2]
        reach = (x * x + y * y) ** 0.5
        if reach > MAX_REACH_MM and x * v[0] + y * v[1] > 0:  # moving outward past the limit: drop that part
            outward = (x * v[0] + y * v[1]) / reach
            v[0] -= outward * x / reach
            v[1] -= outward * y / reach
            if time.time() - last_log > 1:
                log(f"reach {reach:.0f} mm > {MAX_REACH_MM:.0f} mm: not going further out")
                last_log = time.time()
        rotating = False
        if s.right_x and not any(v):
            # Twist about the gripper's own axis (tool frame) = joint 6 only. Twisting in the base frame near
            # the wrist singularity (joint 5 ~ 0) spins joints 4 and 6 hard against each other (error C14).
            v[5] = -s.right_x * MAX_DEG_S * scale
            rotating = True
        elif any(s.dpad) and not any(v):
            v[3], v[4] = s.dpad[0] * TILT_DEG_S * scale, s.dpad[1] * TILT_DEG_S * scale
            rotating = True
        if any(v) or moving:  # keep refreshing while moving, then one zero command after letting go
            code = arm.vc_set_cartesian_velocity(v, is_tool_coord=rotating, duration=HOLD)
            moving = any(v)
            if code or arm.error_code or (moving and time.time() - last_log > 0.3):
                show(arm, f"velocity {[round(c) for c in v]}", code)
                last_log = time.time()
        time.sleep(1 / 30)
except KeyboardInterrupt:
    pass
finally:
    arm.vc_set_cartesian_velocity([0] * 6)
    # Motors off: the brakes hold the pose, and holding still with motors on slowly heats the wrist joint.
    call(arm, "motion_enable", False)
