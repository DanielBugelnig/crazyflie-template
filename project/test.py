from pathlib import Path
import sys, time

sys.path.append(str(Path(__file__).resolve().parents[1]))

import crazyflie.core.base_utils as base
from crazyflie.bitcraze.crazyflie import CrazyFlie
from crazyflie.bitcraze.ai_deck import AI_Deck
import crazyflie.bitcraze.swarm as swarm_module



cf = CrazyFlie()
cf.logging(enable=True, file=True, level=base.LogLevel.debug)


cf.scan()
cf.test_mode(True)   # set test mode
cf.connect(start_flying=False)
cf.checking_decks()
while True:
    time.sleep(1)