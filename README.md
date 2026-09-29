# lite6-starter

Small, readable Python scripts for getting started with the **UFACTORY Lite 6** robot arm:
read its state, move it by hand, drive it from the keyboard or a gamepad, and watch live telemetry in [Rerun](https://rerun.io).

Each script is one file, is numbered in the order to try it, and prints what it is doing.
Everything also goes to `logs/lite6.log`, so after an error you can read back what happened.

| Script | What it does | Moves the arm? |
|---|---|---|
| `scripts/01_hello.py` | connect, print joint angles, tool position, temperatures | no |
| `scripts/02_enable.py` | clear errors, switch the motors on | no |
| `scripts/03_freedrive.py` | free-drive: push the arm by hand, Enter to lock | by hand |
| `scripts/04_teleop_keyboard.py` | step or jog the tool / each joint from the keyboard | **yes** |
| `scripts/05_teleop_gamepad.py` | smooth velocity control with an Xbox / PlayStation / USB gamepad | **yes** |
| `scripts/06_telemetry_rerun.py` | live plots of joint angles, currents, temperatures | no |
| `scripts/07_home.py` | go slowly to the home pose (all joints 0°) | **yes** |

## Safety first

- Keep the **emergency stop** button within reach whenever the motors are on.
- Clear the space the arm can reach (about 44 cm around the base) of people, cables and anything fragile.
- Every script that moves the arm asks you to press Enter first, and uses slow speeds by default.
- Teleop scripts switch the motors **off** when they exit. The brakes hold the pose.
- After any error (the log shows a line like `ERROR C24 ...`), run `02_enable.py` before moving again.

## 1. Network

The Lite 6 control box talks over Ethernet. Its IP address is on a label on the control box
(it usually looks like `192.168.1.xxx`).

1. Plug an Ethernet cable from the control box into your computer (or into the same router).
2. Give your computer's Ethernet port a fixed address on the same network, for example `192.168.1.10`
   with subnet mask `255.255.255.0` (macOS: System Settings > Network > Ethernet > Details > TCP/IP > Manually).
3. Check it: `ping 192.168.1.xxx` should answer.

## 2. Install

Python 3.10 or newer.

```bash
git clone https://github.com/<you>/lite6-starter.git
cd lite6-starter
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Then tell the scripts where the arm is. Do this once per terminal:

```bash
export LITE6_IP=192.168.1.xxx
```

Or pass `--ip 192.168.1.xxx` to any script.

## 3. Run the scripts in order

```bash
python scripts/01_hello.py              # does it answer?
python scripts/02_enable.py             # motors on, errors cleared
python scripts/03_freedrive.py          # move it by hand
python scripts/04_teleop_keyboard.py    # add --jog to hold keys instead of tapping
```

Every script has `--help`.

## 4. Gamepad teleop

Check your gamepad first. This mode never connects to the arm:

```bash
python scripts/05_teleop_gamepad.py --test-pad
```

Then drive:

```bash
python scripts/05_teleop_gamepad.py
```

| Control | Action |
|---|---|
| left stick | move the tool forward/back (x) and left/right (y) |
| right stick up/down | move the tool up/down (z) |
| right stick left/right | twist the gripper |
| d-pad | tilt the tool about its tip |
| L1 / R1 | gripper open / close |
| L2 / R2 | slower / faster |
| A (cross) | point the tool straight down |
| Back / Select | clear error and enable |
| Ctrl-C | quit |

Xbox, PlayStation and Switch Pro controllers work over USB or Bluetooth.
Cheap "Generic USB Joystick" pads (USB id `0079:0006`) that SDL does not recognise can be read directly:

```bash
pip install -e ".[hid]"
python scripts/05_teleop_gamepad.py --hid --test-pad
```

The arm stops by itself 0.2 s after the last command. If the script freezes or the cable comes out, the arm stops.

## 5. Telemetry in Rerun

```bash
python scripts/06_telemetry_rerun.py          # opens the Rerun viewer
python scripts/06_telemetry_rerun.py --save   # also records to logs/telemetry-<time>.rrd
```

This script only reads the arm's state, so run it in a second terminal while you teleop.
Watch the joint currents rise when the arm holds itself out horizontally.
Open a saved recording later with `rerun logs/telemetry-<time>.rrd`.

## Code layout

```
lite6/arm.py        connect(), enable(), call(), log(): shared by every script
lite6/gamepad.py    Gamepad(): any gamepad -> sticks in -1..1 and named buttons
scripts/            the numbered scripts above
tests/              pytest tests for the gamepad parsing (no arm needed): pytest
```

To write your own script, copy `scripts/01_hello.py` and add SDK calls.
The full SDK is in [xArm-Python-SDK](https://github.com/xArm-Developer/xArm-Python-SDK). The Lite 6 uses the same API as the xArm.

## Common errors

| Log line | Meaning | Fix |
|---|---|---|
| `Could not reach the arm` | wrong IP, or different network | section 1 |
| `C24 Speed Exceeds Limit` | moved too fast, often near full reach | `02_enable.py`, then move slower / closer to the base |
| `C31 Collision Caused Abnormal Current` | the arm hit something or was pushed | check nothing is in the way, then `02_enable.py` |
| `C37 Abnormal movement in Manual Mode` | pushed too fast in free-drive | move slower, then `02_enable.py` |
| `C1x Servo motor N error` | fault in joint N (the log line below names it) | `02_enable.py`; if it repeats, power-cycle the control box |
| state `stopped / motors off` | motors were switched off | `02_enable.py` |

## Calibration problem: a joint reads the wrong angle

Each joint has a **zero**: the position where the controller reports 0°. If a zero is wrong, the arm moves fine
but every position it reports (and every position you ask for) is off. Vision and pick-and-place will miss.

**How we noticed.** On our arm, joint 3 (the elbow) read about **40.8° too high**:

- `07_home.py` put all joints at 0°, but the forearm was clearly not horizontal (a side photo showed it).
- The tool height from `01_hello.py` said 53 cm; a tape measure said 37 cm.
- UFactory Studio's 3D view of the arm did not match the real arm.

**How we fixed it (re-zeroing joint 3):**

1. Move the arm so joint 3 is at its **true** zero. Here: upper arm vertical (joint 2 = 0°), forearm horizontal.
   We moved it slowly with the SDK to reported angle = 40.8° (the measured error), then checked it with a photo.
2. Switch the motors off (`set_state(4)`, then `motion_enable(False)`). The brakes hold the pose.
3. Open **UFactory Studio**, UFACTORY's own web app, in a browser: `http://<arm-ip>:18333`.
4. Go to **Settings > General > Debugging Tools** and send the command `D13 I3`.
   `D13` means "make the current position this joint's zero"; `I3` means joint 3.
5. Press the **emergency stop**, wait 5 s, release it. This restarts the joints with the new zero.
6. Check: run `01_hello.py`. Joint 3 now read 0.0° in that pose, and the zero stayed after power-offs.

For another joint, replace the number: `D13 I2` for joint 2, and so on.

**Warnings:**

- `D13` changes the controller permanently. Write down every joint angle (`01_hello.py`) before you send it.
- Only re-zero a joint once you have **measured** the error (photo, tape measure, or Studio's 3D view).
- The wrist joints (4, 5, 6) are harder to check by eye. When we re-zeroed joint 5 (`D13 I5`), the readings of
  joints 4 and 6 jumped about 20° after the next restart. Re-check every joint after a restart.
- If a zero does not hold across restarts, stop and contact UFACTORY support.

## License

MIT
