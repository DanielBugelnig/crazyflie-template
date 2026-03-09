import subprocess
from pathlib import Path
import sys, time
sys.path.append(str(Path(__file__).resolve().parents[1]))
from crazyflie.core.base_utils import BaseClass

from crazyflie.constants import WIFI_NAME, WIFI_PASSWORD


base = BaseClass()
base.logging(True, False, base.LogLevel.message, name="test")

interface = base.get_wifi_interface()
base.start_hotspot(interface, "ai_deck", "bitcraze")
result = subprocess.run(["nmcli" ,"-f", "802-11-wireless.ssid", "connection", "show" ,"Hotspot"], capture_output=True, text=True)
print(result.stdout)
input()
base.deactivate_hotspot()

