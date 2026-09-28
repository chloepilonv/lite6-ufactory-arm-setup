"""Step 2: clear errors and switch the motors on. Does not move the arm.

Run this whenever a script stops with an error (a ControllerError "Cxx" in the log).

    python scripts/02_enable.py
"""
from lite6 import connect, enable, log, parser

args = parser(__doc__).parse_args()
arm = connect("02_enable", args.ip)
enable(arm)
log(f"result: state={arm.state}, error={arm.error_code}  (want state 0 or 2 and error 0)")
