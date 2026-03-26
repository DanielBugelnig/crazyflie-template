import sys, time
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))
import os, multiprocessing
from time import sleep


from crazyflie.bitcraze.ai_deck import AI_Deck
from crazyflie.bitcraze.swarm import CrazySwarm, SwarmError
from crazyflie.core.shared_data import StateManager, Flag
from crazyflie.core.base_utils import LogLevel

def recorder(client:tuple[str, str], directory:str, flag:Flag):
    image_recorder = AI_Deck(client[1], client[0])
    image_recorder.logging(enable=True, file=True, level=LogLevel.debug)
    image_recorder.set_display(True)
    image_recorder.set_directory(directory)
    image_recorder.connect()
    try:
        while not flag.get_exit():
            # ask for an image
            image_recorder.save_image()
            sleep(0.1)
    except KeyboardInterrupt:
        pass
    image_recorder.disconnect()
    return

def main():
    try:
        manager = StateManager()
        exit_flag:Flag = manager.Flag()
        exit_flag.set_ready()
        swarm = CrazySwarm()
        swarm.logging(enable=True, file=False, level=LogLevel.message)
        directory = swarm.create_directory(swarm.get_path() + os.sep + "datasets")
        clients = swarm._scan_ai()
    except SwarmError:
        return
    decks:list[multiprocessing.Process] = []
    for client in clients:
        deck = multiprocessing.Process(target=recorder, name=client[0], kwargs={"client": client, "directory": directory, "flag": exit_flag}, daemon=False)
        decks.append(deck)
    for deck in decks:
        deck.start()
    try:
        while True:
            sleep(0.5)
    except KeyboardInterrupt:
        exit_flag.set_exit()
    for deck in decks:
        deck.join()
    return

if __name__ == "__main__":
    main()
