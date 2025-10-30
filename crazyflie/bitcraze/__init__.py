"""
    collect the control scripts for Crazyflie, and different decks

    Daniel Bugelnig (daniel.bugelnig@aau.at),
    2025.10.10
"""

from .crazyflie import CrazyFlieError
from .ai_deck import AIDeckError
from .swarm import SwarmError
from .trajectory import TrajectoryError

from .crazyflie import CrazyFlie as crazyflie
from .ai_deck import AI_Deck as ai_deck
from .swarm import CrazySwarm as swarm
from .trajectory import Trajectory as trajectory

BitcrazeError = (CrazyFlieError, AIDeckError, SwarmError, TrajectoryError)
