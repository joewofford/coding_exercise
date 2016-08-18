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

AUTH = {'X-Starfighter-Authorization': '7f1b969336002cf5f1dbf584276fa81b0f13880f'}
USERNAME = 'joewofford'
PS = '????????????????'
PATH_TO_CHROMEDRIVER = '/Users/joewofford/anaconda/chromedriver'
DELTA = .99

class Account(object):

    def __init__(self):
        return

    def block_buy(qty=100000, max_qty=1000, owned=0):
        self.qty = qty
        self.max_qty = max_qty
        self.owned = owned

        self._login()
        self._initiate_market()
        self._parse_trade_info()
        self._get_venue()

        q = Queue.Queue()
        self._launch_tickertape(q)
        time.sleep(60)

    def

    def _get_tickers(self, venue):
        call = requests.get('https://api.stockfighter.io/ob/api/venues/{}/stocks'.format(venue), headers=AUTH)
        return [d['symbol'] for d in call.json()['symbols']]

    def _get_venue(self):
        call = requests.get('https://api.stockfighter.io/ob/api/venues', headers=AUTH)
        venues = [d['venue'] for d in call.json()['venues']]

        for venue in venues:
            if self.ticker in get_tickers(venue):
                self.venue = venue
                return

    def _single_buy(self, qty, order_type):
        order = {
        'account': self.account,
        'venue': self.venue,
        'stock': self.ticker,
        'qty': qty,
        'direction': 'buy',
        'orderType': order_type
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

    def _login(self):
        url = 'https://www.stockfighter.io'
        b_chrome = webdriver.Chrome(executable_path = PATH_TO_CHROMEDRIVER)
        b_chrome.get(url)
        b_chrome.find_elements_by_name('session[username]')[0].send_keys(USERNAME)
        b_chrom.find_elements_by_name('session[password]')[0].send_keys(PS)
        b_chrom.find_elements_by_xpath('//*[@id="loginform"]/button')[0].click()
        time.sleep(30)
        return

    def _initiate_market(self):
        b_chrom.find_elements_by_xpath('//*[@id="wrapping"]/nav/div/ul/li[2]')[0].click()
        b_chrom.find_elements_by_xpath('//*[@id="wrapping"]/nav/div/ul/li[2]/ul/li[1]/a/span[1]/b')[0].click()
        time.sleep(30)
        return

    def _parse_trade_info(self):
        self.account = b_chrom.find_elements_by_xpath('/html/body/div[3]/div/div[2]/div/div/div[2]/span/p[2]/strong[2]')[0].text.split()[1]
        self.ticker = b_chrom.find_elements_by_xpath('/html/body/div[3]/div/div[2]/div/div/div[2]/span/p[2]/em')[0].text
        time.sleep(5)
        return

    def _parse_target_price(self):
        self.target_price = float(b_chrom.find_element_by_xpath('//*[@id="wrapping"]/div/div[1]/div/div[1]/p').text.split('$')[-1][:-1])
        return

    def _extract_target_price(self):





# def _parse_target_price():
#
#     url="https://www.stockfighter.io/ui/play/blotter#chock_a_block"
#     r = requests.get(url)
#     soup = BeautifulSoup(r.text, 'html.parser')
#     price_string = re.compile()
#     soup.search(string="Update from the back office: you've purchased 1678 shares at an average cost of $87.69. The client's target price is $82.10.")
#
#     price_string = soup.find_all(re.compile('The client\'s target price is \$(\d*\.\d*)\."'))
#
#     WILL NOT WORK USING REQUESTS BECAUSE JAVASCRIPT RENDERING...
