import math, time
import rerun as rr

rr.init("rerun_example_my_data", spawn=True)

for step in range(64):
    rr.set_time("step", sequence=step)
    rr.log("scalar", rr.Scalars(math.sin(step / 10.0)))
    time.sleep(0.01)