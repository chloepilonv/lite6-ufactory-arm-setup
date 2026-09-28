"""Shared connection + logging for every script.

    from lite6 import connect, call, log
    arm = connect("my_script")                 # IP from --ip or the LITE6_IP environment variable
    call(arm, "motion_enable", True)           # runs the SDK call and logs its return code

Every line goes to the terminal and to logs/lite6.log (append-only), so after a fault you can read
back what happened. Controller and joint error codes are translated to their names from the SDK's own
table, e.g. "C24 Joint speed exceeds limit" instead of "error 24".
"""
import argparse
import atexit
import logging
import os
import sys

from xarm.core.config.x_code import ControllerError, ControllerWarn
from xarm.core.utils.log import logger as sdk_logger
from xarm.wrapper import XArmAPI

LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
LOG_FILE = os.path.join(LOG_DIR, "lite6.log")

STATE_NAMES = {0: "ready", 1: "moving", 2: "ready (idle)", 3: "paused", 4: "stopped / motors off", 5: "stopping",
               6: "manual-mode drift"}
MODE_NAMES = {0: "position", 1: "servo", 2: "manual / free-drive", 4: "joint velocity", 5: "cartesian velocity",
              6: "joint online", 7: "cartesian online"}

_log = logging.getLogger("lite6")


def _setup_logging(script):
    if _log.handlers:
        return
    os.makedirs(LOG_DIR, exist_ok=True)
    _log.setLevel(logging.INFO)
    file_handler = logging.FileHandler(LOG_FILE)
    file_handler.setFormatter(logging.Formatter("%(asctime)s | %(message)s", "%Y-%m-%d %H:%M:%S"))
    terminal = logging.StreamHandler(sys.stdout)
    terminal.setFormatter(logging.Formatter("[lite6] %(message)s"))
    _log.addHandler(file_handler)
    _log.addHandler(terminal)
    # the SDK's own messages ("[SDK][ERROR] ...") go to the same file
    sdk_file = logging.FileHandler(LOG_FILE)
    sdk_file.setFormatter(logging.Formatter("%(asctime)s | SDK: %(message)s", "%Y-%m-%d %H:%M:%S"))
    sdk_logger.addHandler(sdk_file)
    _log.info(f"===== {script} started (pid {os.getpid()}) =====")


def log(msg):
    """One line to the terminal and to logs/lite6.log."""
    _log.info(msg)


def describe_error(code):
    return "none" if code == 0 else f"C{code} {ControllerError(code).title['en']}"


def parser(description):
    """An argparse parser that already has --ip. Scripts add their own flags on top."""
    p = argparse.ArgumentParser(description=description, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--ip", default=os.environ.get("LITE6_IP"),
                   help="arm IP address (default: the LITE6_IP environment variable)")
    return p


def open_arm(ip):
    """The bare SDK connection, with a readable message instead of a traceback when it fails."""
    if not ip:
        raise SystemExit("No arm IP. Run with --ip 192.168.1.xxx, or once per terminal: export LITE6_IP=192.168.1.xxx")
    try:
        arm = XArmAPI(ip, is_radian=False)
    except Exception:
        arm = None
    if arm is None or not arm.connected:
        raise SystemExit(f"Could not reach the arm at {ip}. Is the control box on, and is your computer on the "
                         f"same network? (README, section 'Network')")
    return arm


def connect(script, ip):
    """Connect to the arm, log its state, and log every error / state / mode change from then on."""
    arm = open_arm(ip)
    _setup_logging(script)
    log(f"connected to {ip}, firmware {arm.version}, mode={MODE_NAMES.get(arm.mode, arm.mode)}, "
        f"state={STATE_NAMES.get(arm.state, arm.state)}, error={describe_error(arm.error_code)}")

    def on_error_warn(d):
        error, warn = d.get("error_code", 0), d.get("warn_code", 0)
        if error:
            log(f"ERROR {describe_error(error)}")
            code, servos = arm.get_servo_debug_msg(show=False)  # which joint, if it is a joint fault
            if code == 0:
                for s in servos:
                    if s.get("code"):
                        log(f"  joint detail: {s['name']} S{s['code']} {s['title']}")
        else:
            log("error cleared")
        if warn:
            log(f"WARNING W{warn} {ControllerWarn(warn).title['en']}")

    arm.register_error_warn_changed_callback(on_error_warn)
    arm.register_state_changed_callback(lambda d: log(f"state -> {STATE_NAMES.get(d['state'], d['state'])}"))
    arm.register_mode_changed_callback(lambda d: log(f"mode -> {MODE_NAMES.get(d['mode'], d['mode'])}"))

    def disconnect():
        try:
            log(f"disconnecting: state={STATE_NAMES.get(arm.state, arm.state)}, error={describe_error(arm.error_code)}")
            arm.disconnect()
        except Exception:
            pass

    atexit.register(disconnect)
    return arm


def call(arm, name, *args, **kwargs):
    """Run one SDK call, e.g. call(arm, "set_mode", 0), and log it with its return code (0 = ok)."""
    result = getattr(arm, name)(*args, **kwargs)
    code = result[0] if isinstance(result, (list, tuple)) else result
    shown = ", ".join([*map(str, args), *(f"{k}={v}" for k, v in kwargs.items())])
    log(f"{name}({shown}) -> code {code}")
    return result


def enable(arm, mode=0):
    """Clear errors, switch the motors on and pick a motion mode (0 = position). Does not move the arm."""
    call(arm, "clean_error")
    call(arm, "clean_warn")
    call(arm, "motion_enable", True)
    call(arm, "set_mode", mode)
    call(arm, "set_state", 0)


def show(arm, what, code=0):
    """Log a move and where the arm ended up."""
    p = [round(v) for v in arm.position]
    j = [round(a) for a in arm.angles[:6]]
    err = f"  ERROR {describe_error(arm.error_code)}" if arm.error_code else ""
    log(f"{what} -> code {code} | tool xyz {p[:3]} mm, roll/pitch/yaw {p[3:]} deg | joints {j} deg{err}")


def confirm(text):
    """Ask before the arm moves. Anything but Enter cancels."""
    if input(f"{text}\nClear the area around the arm, keep the emergency stop in reach, then press Enter "
             f"(or type n): ").strip():
        raise SystemExit("cancelled, nothing moved")
