import logging
import requests
import time
import typing
import collections

from urllib.parse import urlencode

import hmac
import hashlib

import websocket
import json

import threading

from models import *

from strategies import TechnicalStrategy, BreakoutStrategy

# binance futures base url: "https://fapi.binance.com"
# binance futures testnet base url: "https://testnet.binancefuture.com"
# order book endpoint: "/fapi/v1/ticker/bookTicker"
# candlesticks endpoint: "/fapi/v1/klines"

# binance futures testnet public key: "70d8395d11e64d006cc2bd312c000cb29ea1171782cbd671ed3ef495420e7968"
# binance futures testnet secret key: "29d80625088433f47d0fbb7d7dc543715f9748ed0f30c8b403f1b3dff42aa7b4"

logger = logging.getLogger()


class BinanceClient:
    # constructor
    def __init__(self, public_key: str, secret_key: str, testnet: bool, futures: bool):

        self.futures = futures

        if self.futures:
            self.platform = "binance_futures"

            if testnet:
                self._base_url = "https://testnet.binancefuture.com"
                self._wss_url = "wss://stream.binancefuture.com/ws"
            else:
                self._base_url = "https://fapi.binance.com"
                self._wss_url = "wss://fstream.binance.com/ws"

        else:
            self.platform = "binance_spot"

            if testnet:
                self._base_url = "https://testnet.binance.vision"
                self._wss_url = "wss://testnet.binance.vision/ws"
            else:
                self._base_url = "https://api.binance.com"
                self._wss_url = "wss://stream.binance.com:9443/ws"

        self._public_key = public_key
        self._secret_key = secret_key

        self._headers = {'X-MBX-APIKEY': self._public_key}

        self.contracts = self.get_contracts()
        self.balances = self.get_balances()

        self.prices = dict()
        self.strategies: typing.Dict[int, typing.Union[TechnicalStrategy, BreakoutStrategy]] = dict()

        self.logs = []

        self._ws_id = 1
        self.ws: websocket.WebSocketApp
        self.reconnect = True
        self.ws_connected = False
        self.ws_subscriptions = {"bookTicker": [], "aggTrade": []}

        t = threading.Thread(target=self._start_ws)
        t.start()

        logger.info("Binance Futures Client successfully initialized")

    # Add a log to the list so that it can be picked by the update_ui() method of the root component
    def _add_log(self, msg: str):

        logger.info("%s", msg)
        self.logs.append({"log": msg, "displayed": False})

    def _generate_signature(self, data: typing.Dict) -> str:

        # Generate a signature with the HMAC-256 algorithm
        return hmac.new(self._secret_key.encode(), urlencode(data).encode(), hashlib.sha256).hexdigest()

    # Wrapper that normalizes the requests to the REST API and error handling
    def _make_request(self, method: str, endpoint: str, data: typing.Dict):

        if method == "GET":
            try:
                response = requests.get(self._base_url + endpoint, params=data, headers=self._headers)

            # Takes into account any possible error, most likely network error
            except Exception as e:
                logger.error("Connection error while making %s request to %s: %s", method, endpoint, e)
                return None

        elif method == "POST":
            try:
                response = requests.post(self._base_url + endpoint, params=data, headers=self._headers)
            except Exception as e:
                logger.error("Connection error while making %s request to %s: %s", method, endpoint, e)
                return None

        elif method == "DELETE":
            try:
                response = requests.delete(self._base_url + endpoint, params=data, headers=self._headers)
            except Exception as e:
                logger.error("Connection error while making %s request to %s: %s", method, endpoint, e)
                return None

        else:
            raise ValueError()

        if response.status_code == 200:
            return response.json()
        else:
            logger.error("Error while making %s request to %s: %s (error code: %s)",
                         method, endpoint, response.json(), response.status_code)
            return None

    # Get a list of symbols/contracts on the exchange to be displayed in the OptionsMenus of the interface
    def get_contracts(self) -> typing.Dict[str, Contract]:

        if self.futures:
            exchange_info = self._make_request("GET", "/fapi/v1/exchangeInfo", dict())
        else:
            exchange_info = self._make_request("GET", "/api/v3/exchangeInfo", dict())

        contracts = dict()

        if exchange_info is not None:
            for contract_data in exchange_info['symbols']:
                contracts[contract_data['symbol']] = Contract(contract_data, self.platform)

        # Sort keys of the dictionary alphabetically
        return collections.OrderedDict(sorted(contracts.items()))

    # Get a list of the most recent candlesticks for a given symbol/contract and intreval.
    def get_historical_candles(self, contract: Contract, interval: str) -> typing.List[Candle]:

        data = dict()
        data['symbol'] = contract.symbol
        data['interval'] = interval
        data['limit'] = 1000

        if self.futures:
            raw_candles = self._make_request("GET", "/fapi/v1/klines", data)
        else:
            raw_candles = self._make_request("GET", "/api/v3/klines", data)

        candles = []

        if raw_candles is not None:
            for c in raw_candles:
                candles.append(Candle(c, interval, self.platform))

        return candles

    # Get a snapshot of the current bid and ask price for a symbol/contract,
    # to be sure there is something to display on the Watchlist.
    def get_bid_ask(self, contract: Contract) -> typing.Dict[str, float]:

        data = dict()
        data['symbol'] = contract.symbol

        if self.futures:
            ob_data = self._make_request("GET", "/fapi/v1/ticker/bookTicker", data)
        else:
            ob_data = self._make_request("GET", "/api/v3/ticker/bookTicker", data)

        if ob_data is not None:
            # Add the symbol to the dictionary if needed
            if contract.symbol not in self.prices:
                self.prices[contract.symbol] = {'bid': float(ob_data['bidPrice']), 'ask': float(ob_data['askPrice'])}
            else:
                self.prices[contract.symbol]['bid'] = float(ob_data['bidPrice'])
                self.prices[contract.symbol]['ask'] = float(ob_data['askPrice'])

            return self.prices[contract.symbol]

    # Get the current balance of the account, the data is different between Spot and Futures
    def get_balances(self) -> typing.Dict[str, Balance]:

        data = dict()
        data['timestamp'] = int(time.time() * 1000)
        data['signature'] = self._generate_signature(data)

        balances = dict()

        if self.futures:
            account_data = self._make_request("GET", "/fapi/v2/account", data)
        else:
            account_data = self._make_request("GET", "/api/v3/account", data)

        if account_data is not None:

            if self.futures:
                for a in account_data['assets']:
                    balances[a['asset']] = Balance(a, self.platform)

            else:
                for a in account_data['balances']:
                    balances[a['asset']] = Balance(a, self.platform)

        return balances

    # Place an order based on the order_type. the price and tif arguments are not required.
    def place_order(self, contract: Contract, order_type: str, quantity: float, side: str, price=None,
                    tif=None) -> OrderStatus:

        data = dict()
        data['symbol'] = contract.symbol
        data['side'] = side.upper()
        data['quantity'] = round(int(quantity / contract.lot_size) * contract.lot_size, 8)
        data['type'] = order_type.upper()

        if price is not None:
            data['price'] = round(round(price / contract.tick_size) * contract.tick_size, 8)
            data['price'] = '%.*f' % (contract.price_decimals, data['price'])

        if tif is not None:
            data['timeInForce'] = tif

        data['timestamp'] = int(time.time() * 1000)
        data['signature'] = self._generate_signature(data)

        if self.futures:
            order_status = self._make_request("POST", "/fapi/v1/order", data)
        else:
            order_status = self._make_request("POST", "/api/v3/order", data)

        if order_status is not None:

            if not self.futures:
                if order_status['status'] == 'FILLED':
                    order_status['avgPrice'] = self._get_execution_price(contract, order_status['orderId'])

                else:
                    order_status['avgPrice'] = 0

            order_status = OrderStatus(order_status, self.platform)

        return order_status

    def cancel_order(self, contract: Contract, order_id: int) -> OrderStatus:

        data = dict()
        data['orderId'] = order_id
        data['symbol'] = contract.symbol
        data['timestamp'] = int(time.time() * 1000)
        data['signature'] = self._generate_signature(data)

        if self.futures:
            order_status = self._make_request("DELETE", "/fapi/v1/order", data)
        else:
            order_status = self._make_request("DELETE", "/api/v3/order", data)

        if order_status is not None:

            if not self.futures:
                # Get the average execution price based on the recent trades
                order_status['avgPrice'] = self._get_execution_price(contract, order_id)

            order_status = OrderStatus(order_status, self.platform)

        return order_status

    # For Binance Spot only, find the equivalent of the 'avgPrice' key on the futures side.
    # The average price is the weighted sum of each trade price related to the order_id
    def _get_execution_price(self, contract: Contract, order_id: int) -> float:

        data = dict()
        data['timestamp'] = int(time.time() * 1000)
        data['symbol'] = contract.symbol
        data['signature'] = self._generate_signature(data)

        trades = self._make_request("GET", "/api/v3/myTrades", data)

        avg_price = 0

        if trades is not None:
            executed_qty = 0

            for t in trades:
                if t['orderId'] == order_id:
                    executed_qty += float(t['qty'])

            for t in trades:
                if t['orderId'] == order_id:
                    fill_pct = float(t['qty']) / executed_qty
                    # Weighted sum
                    avg_price += (float(t['price']) * fill_pct)

        return round(round(avg_price / contract.tick_size) * contract.tick_size, 8)

    def get_order_status(self, contract: Contract, order_id: int) -> OrderStatus:

        data = dict()
        data['timestamp'] = int(time.time() * 1000)
        data['symbol'] = contract.symbol
        data['orderId'] = order_id
        data['signature'] = self._generate_signature(data)

        if self.futures:
            order_status = self._make_request("GET", "/fapi/v1/order", data)
        else:
            order_status = self._make_request("GET", "/api/v3/order", data)

        if order_status is not None:

            if not self.futures:
                if order_status['status'] == 'FILLED':
                    # Get the average execution price based on the recent trades
                    order_status['avgPrice'] = self._get_execution_price(contract, order_id)

                else:
                    order_status['avgPrice'] = 0

            order_status = OrderStatus(order_status, self.platform)

        return order_status

    # Infinite loop (thus has to run in a Thread) that reopens the websocket connection in case it drops
    def _start_ws(self):

        self.ws = websocket.WebSocketApp(self._wss_url, on_open=self._on_open, on_close=self._on_close,
                                         on_error=self._on_error, on_message=self._on_message)
        while True:
            try:
                # Reconnect unless the interface is closed by the user
                if self.reconnect:
                    # Blocking method that ends only if the websocket connection drops
                    self.ws.run_forever()
                else:
                    break

            except Exception as e:
                logger.error("Binance error in run_forever() method: %s", e)
            time.sleep(2)

    def _on_open(self, ws):

        logger.info("Binance connection opened")

        self.ws_connected = True

        # The aggTrade channel is subscribed to in the _switch_strategy() method of strategy_component.py

        for channel in ["bookTicker", "aggTrade"]:
            for symbol in self.ws_subscriptions[channel]:
                self.subscribe_channel([self.contracts[symbol]], channel, reconnection=True)

        if "BTCUSDT" not in self.ws_subscriptions['bookTicker']:
            self.subscribe_channel([self.contracts['BTCUSDT']], "bookTicker")

    # Triggered when the connection drops
    def _on_close(self, ws):

        logger.warning("Binance Websocket connection closed")

        self.ws_connected = False

    # Triggered in case of error
    def _on_error(self, ws, msg: str):

        logger.error("Binance Websocket connection error: %s", msg)

    # The websocket updates of the channels the program subscribed to will go thorugh this callback method
    def _on_message(self, ws, msg: str):

        data = json.loads(msg)

        if "u" in data and "A" in data:
            # For Binance Spot, to make the data structure uniform with Binance Futures
            data['e'] = "bookTicker"

        if "e" in data:
            if data['e'] == "bookTicker":
                symbol = data['s']

                # check if the symbol is in the prices dictionary
                if symbol not in self.prices:
                    self.prices[symbol] = {'bid': float(data['b']), 'ask': float(data['a'])}

                else:
                    self.prices[symbol]['bid'] = float(data['b'])
                    self.prices[symbol]['ask'] = float(data['a'])

                # PNL Calculation
                try:
                    for b_index, strat in self.strategies.items():

                        if strat.contract.symbol == symbol:

                            for trade in strat.trades:

                                if trade.status == 'open' and trade.entry_price is not None:

                                    if trade.side == 'long':
                                        trade.pnl = (self.prices[symbol]['bid'] - trade.entry_price) * trade.quantity

                                    elif trade.side == 'short':
                                        trade.pnl = (trade.entry_price - self.prices[symbol]['ask']) * trade.quantity

                # Handles the case the dictionary is modified while loop through it
                except RuntimeError as e:
                    logger.error("Error while looping through the Binance strategies: %s", e)

            if data['e'] == "aggTrade":
                symbol = data['s']

                for key, strat in self.strategies.items():

                    if strat.contract.symbol == symbol:
                        # Updated candlesticks
                        res = strat.parse_trades(float(data['p']), float(data['q']), data['T'])

                        strat.check_trade(res)

    # Subscribe to updates on a specific topic for all the symbols.
    # If your list is bigger than 300 symbols, the subscription will fail.
    def subscribe_channel(self, contracts: typing.List[Contract], channel: str, reconnection=False):

        if len(contracts) > 200:
            logger.warning("Subscribing to more than 200 symbols will most likely fail."
                           "Consider subscribing only when adding a symbol to your Watchlist or when starting a"
                           "strategy for a symbol.")

        data = dict()
        data['method'] = "SUBSCRIBE"
        data['params'] = []

        if len(contracts) == 0:
            data['params'].append(channel)

        else:
            for contract in contracts:
                if contract.symbol not in self.ws_subscriptions[channel] or reconnection:
                    data['params'].append(contract.symbol.lower() + "@" + channel)

                    if contract.symbol not in self.ws_subscriptions[channel]:
                        self.ws_subscriptions[channel].append(contract.symbol)

        if len(data['params']) == 0:
            return

        data['id'] = self._ws_id

        # print(data, type(data))
        # print(json.dumps(data), type(json.dumps(data)))

        try:
            # Converts the JSON object (dictionary) to a JSON string
            self.ws.send(json.dumps(data))
            logger.info("Binance: subscribing to: %s", ','.join(data['params']))

        except Exception as e:
            logger.error("Websocket error while subscribing to @bookTicker and @aggTrade: %s", e)

        self._ws_id += 1

    # Compute the trade size for the strategy module based on the percentage of the balance to use that was defined
    # in the strategy component.
    def get_trade_size(self, contract: Contract, price: float, balance_pct: float):

        logger.info("Getting Binance trade size...")

        balance = self.get_balances()

        if balance is not None:
            if contract.quote_asset in balance:
                if self.futures:
                    balance = balance[contract.quote_asset].wallet_balance

                else:
                    balance = balance[contract.quote_asset].free
            else:
                return None
        else:
            return None

        trade_size = (balance * balance_pct / 100) / price
        # Remove extra decimals
        trade_size = round(round(trade_size / contract.lot_size) * contract.lot_size, 8)

        logger.info("Binance current %s balance = %s, trade size = %s", contract.quote_asset, balance, trade_size)

        return trade_size
