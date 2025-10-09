from pathlib import Path
import sys


sys.path.append(str(Path(__file__).resolve().parents[1]))

import crazyflie.core.base_utils as base
from crazyflie.bitcraze.crazyflie import CrazyFlie
from crazyflie.bitcraze.ai_deck import AI_Deck
import crazyflie.bitcraze.swarm as swarm_module

cf = base.BaseClass()
cf.logging(enable=True, file=True, name="test", level=base.LogLevel.debug)
cf.print("Hello, World!", level=base.LogLevel.message)
cf.print("This is a warning message.", level=base.LogLevel.warning)

cf_real = CrazyFlie("radio://0/100/2M/E7E7E7E701")
#cf_real.connect()
print(cf_real.get_path())