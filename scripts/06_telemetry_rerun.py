"""Step 6, read-only: live plots of every joint's angle, current and temperature in Rerun. Never moves the arm.

Safe to run next to teleop or UFactory Studio: it only reads the report the controller broadcasts.
Try it in a second terminal while 05_teleop_gamepad.py runs, and watch the currents change as you move.

    python scripts/06_telemetry_rerun.py            # opens the Rerun viewer, Ctrl-C to stop
    python scripts/06_telemetry_rerun.py --save     # also saves everything to logs/telemetry-<time>.rrd
                                                    # (reopen later with: rerun logs/telemetry-<time>.rrd)
"""
import os
import sys
import time

import rerun as rr
import rerun.blueprint as rrb

from lite6 import LOG_DIR, open_arm, parser

p = parser(__doc__)
p.add_argument("--save", action="store_true", help="also save to logs/telemetry-<time>.rrd")
p.add_argument("--hz", type=float, default=10, help="samples per second (default 10)")
args = p.parse_args()
arm = open_arm(args.ip)  # before opening the viewer, so a wrong IP fails fast
os.environ["PATH"] = os.path.dirname(sys.executable) + os.pathsep + os.environ["PATH"]  # find the viewer app

rr.init("lite6_telemetry", spawn=True)  # spawn=True opens the Rerun viewer window
layout = rrb.Vertical(
    rrb.Horizontal(rrb.TimeSeriesView(name="joint angle (deg)", origin="/angle_deg"),
                   rrb.TimeSeriesView(name="joint current (A)", origin="/current_A")),
    rrb.Horizontal(rrb.TimeSeriesView(name="joint temperature (C)", origin="/temperature_C"),
                   rrb.TimeSeriesView(name="tool position (mm)", origin="/tool_mm")),
    rrb.TimeSeriesView(name="state / error code", origin="/arm"),
)
if args.save:
    os.makedirs(LOG_DIR, exist_ok=True)
    path = os.path.join(LOG_DIR, time.strftime("telemetry-%Y%m%d-%H%M%S.rrd"))
    rr.set_sinks(rr.GrpcSink(), rr.FileSink(path), default_blueprint=layout)  # live window + file
    print(f"saving to {path}")
else:
    rr.send_blueprint(layout)

time.sleep(1.0)  # before the first report every value reads 0
print(f"streaming {args.ip} to Rerun, Ctrl-C to stop")
try:
    while True:
        rr.set_time("time", timestamp=time.time())
        rr.log("arm/state", rr.Scalars(arm.state))
        rr.log("arm/error_code", rr.Scalars(arm.error_code))
        for j, (a, c, t) in enumerate(zip(arm.angles[:6], arm.currents[:6], arm.temperatures[:6]), 1):
            rr.log(f"angle_deg/joint{j}", rr.Scalars(a))
            rr.log(f"current_A/joint{j}", rr.Scalars(c))
            rr.log(f"temperature_C/joint{j}", rr.Scalars(t))
        for name, value in zip("xyz", arm.position[:3]):
            rr.log(f"tool_mm/{name}", rr.Scalars(value))
        time.sleep(1 / args.hz)
except KeyboardInterrupt:
    pass
finally:
    arm.disconnect()
