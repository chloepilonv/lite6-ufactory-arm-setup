"""Step 7: move slowly to the home pose (all joints at 0 deg), then switch the motors off. MOVES THE ARM.

Home is UFACTORY's own zero pose. Use it to start each session from the same place.

    python scripts/07_home.py
"""
from lite6 import call, confirm, connect, enable, parser, show

p = parser(__doc__)
p.add_argument("--speed", type=float, default=15, help="joint speed in deg/s (default 15, slow)")
args = p.parse_args()
arm = connect("07_home", args.ip)
confirm(f"The arm will move to home (all joints 0 deg) at {args.speed} deg/s. Check nothing is in its path.")
enable(arm)
try:
    show(arm, "home", arm.move_gohome(speed=args.speed, wait=True))
finally:
    call(arm, "motion_enable", False)  # brakes hold the pose
