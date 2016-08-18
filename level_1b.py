import requests
import random
import time
import websocket
import json
import Queue
import re
from threading import Thread
from bs4 import BeautifulSoup
from selenium import webdriver

AUTH = {'X-Starfighter-Authorization': '72d41755aa7d45c4010a5e182e4f0ba543670fb1'}

class Account(object):

    def __init__(self, account):
        self.account = account


    def block_buy(ticker, qty, max_qty=1000, owned=0):
        self.ticker = ticker
        self.qty = qty
        self.owned = owned
        self.max_qty = max_qty
        self.order_type = '????????????????????????????????????????????????'



    def _get_tickers(self, venue):
        call = requests.get('https://api.stockfighter.io/ob/api/venues/{}/stocks'.format(venue), headers=AUTH)
        return [d['symbol'] for d in call.json()['symbols']]


    def _get_venue(self):
        call = requests.get('https://api.stockfighter.io/ob/api/venues', headers=AUTH)
        venues = [d['venue'] for d in call.json()['venues']]

        for venue in venues:
            if self.ticker in get_tickers(venue):
                self.venue = venue
                return True
        return False


    def _single_buy(self, qty):
        order = {
        'account': self.account,
        'venue': self.venue,
        'stock': self.ticker,
        'qty': qty,
        'direction': 'buy',
        'orderType': self.order_type
        }

        call = requests.post('https://api.stockfighter.io/ob/api/venues/{}/stocks/{}/orders'.format(self.venue, self.ticker), headers=AUTH, json=order)

        return call


    def _trade_status(self, t_id):
        call = requests.get('https://api.stockfighter.io/ob/api/venues/{}/stocks/{}/orders/{}'.format(self.venue, self.ticker, t_id), headers=AUTH)
        return call


    def _cancel_buy(self, t_id):
        call = requests.post('https://api.stockfighter.io/ob/api/venues/{}/stocks/{}/orders/{}/cancel'.format(self.venue, self.ticker, t_id), headers=AUTH)
        return call


    def _launch_tickertape(q):
        driver = webdriver.Firefox()
        url="wss://api.stockfighter.io/ob/api/ws/{}/venues/{}/tickertape/stocks/{}".format(self.account, self.venue, self.ticker)
        while 1:
            try:
                tick = ws.recv()
                with q.mutex:
                    q.queue.clear()
                q.put(tick)
            except:
                ws = websocket.create_connection(url)
        return


    def _get_target_price(self):



def _parse_target_price():

    url="https://www.stockfighter.io/ui/play/blotter#chock_a_block"
    r = requests.get(url)
    soup = BeautifulSoup(r.text, 'html.parser')
    price_string = re.compile()
    soup.search(string="Update from the back office: you've purchased 1678 shares at an average cost of $87.69. The client's target price is $82.10.")

    price_string = soup.find_all(re.compile('The client\'s target price is \$(\d*\.\d*)\."'))
