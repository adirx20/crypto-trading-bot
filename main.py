import logging
import json

from connectors.binance import BinanceClient
from connectors.bitmex import BitmexClient

from interface.root_component import Root

# Create and configure the logger object
logger = logging.getLogger()
# Overall minimum logging level
logger.setLevel(logging.INFO)

# Configure the logging messages displayed in the terminal
stream_handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s %(levelname)s :: %(message)s')
stream_handler.setFormatter(formatter)
# Minimum logging level for the StreamHandler
stream_handler.setLevel(logging.INFO)

# Configure the logging messages written to a file
file_handler = logging.FileHandler("info.log")
file_handler.setFormatter(formatter)
# Minimum logging level for the FileHandlera
file_handler.setLevel(logging.DEBUG)

logger.addHandler(stream_handler)
logger.addHandler(file_handler)

# Read API keys from keys.json
with open("keys.json") as f:
    keys = json.load(f)

binance_keys = keys["binance"]
bitmex_keys = keys["bitmex"]

# Execute the following code only when executing main.py (not when importing it)
if __name__ == "__main__":

    binance = BinanceClient(binance_keys['api_key'], binance_keys['secret_key'], True, True)

    bitmex = BitmexClient(bitmex_keys['api_key'], bitmex_keys['secret_key'], True)

    root = Root(binance, bitmex)
    root.mainloop()
