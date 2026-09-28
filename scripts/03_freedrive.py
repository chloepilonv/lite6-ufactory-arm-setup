"""Step 3: free-drive (manual) mode. The motors hold the arm against gravity and you push it by hand.

Press Enter to lock it where it is. Good for feeling the joints and their limits.

    python scripts/03_freedrive.py
"""
from lite6 import call, confirm, connect, log, parser

args = parser(__doc__).parse_args()
arm = connect("03_freedrive", args.ip)
confirm("The motors will hold the arm up but let you push it by hand.")
call(arm, "clean_error")
call(arm, "motion_enable", True)
# mode 2 = manual. detection_param=1 turns off the "abnormal movement" check (C37) that trips when you push.
call(arm, "set_mode", 2, detection_param=1)
call(arm, "set_state", 0)
log("FREE-DRIVE ON. Hold the wrist and move slowly. Press Enter to lock.")
input()
call(arm, "set_mode", 0)
call(arm, "set_state", 0)
log(f"locked at joint angles (deg): {[round(a, 1) for a in arm.angles[:6]]}")
