"""Step 1, read-only: connect and print where the arm is. Never moves it.

    python scripts/01_hello.py --ip 192.168.1.xxx
"""
from lite6 import connect, describe_error, log, parser

args = parser(__doc__).parse_args()
arm = connect("01_hello", args.ip)
log(f"joint angles (deg): {[round(a, 1) for a in arm.angles[:6]]}")
log(f"tool position (x, y, z mm; roll, pitch, yaw deg): {[round(v, 1) for v in arm.position]}")
log(f"joint temperatures (C): {arm.temperatures[:6]}")
log(f"error: {describe_error(arm.error_code)}  (none = good; otherwise run 02_enable.py)")
