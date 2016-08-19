from __future__ import division

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
from datetime import datetime

AUTH = {'X-Starfighter-Authorization': '0c758ac77e1595c23756812113e730df324730e4'}
USERNAME = 'joewofford'
PS = 'givepeyton#18'
PATH_TO_CHROMEDRIVER = '/Users/joewofford/anaconda/chromedriver'
DELTA = .97
TRADE_WINDOW = 5
MAX_QUOTE_AGE = 1
SPREAD_SPLIT = 1.02

class Account(object):

    def __init__(self):
        self.target_price = 0
        return

    def block_buy(self, qty=100000, max_buy=1000, owned=0):
        self.qty = qty
        self.max_buy = max_buy
        self.owned = owned

        b_chrome = self._login()
        self._initiate_market(b_chrome)
        self._parse_trade_info(b_chrome)
        self._get_venue()

        q = Queue.Queue()
        tickertape = Thread(target=self._launch_tickertape, args=(q,))
        tickertape.start()
        #testing to see if the ticker has launched yet, if not then wait
        while q.empty():
            time.sleep(1)

        self._extract_target_price(b_chrome)

        self._iterative_buying(q)

        print 'We have now bought {} shares of {} on account {}.'.format(self.owned, self.ticker, self.account)

        return

#Example quote from tickertape:
#{"ok":true,"quote":{"symbol":"YLVO","venue":"WDBTEX","bid":5470,"ask":5497,"bidSize":5,"askSize":11446,"bidDepth":41023,"askDepth":34338,"last":5470,"lastSize":348,"lastTrade":"2016-08-18T20:56:09.856793761Z","quoteTime":"2016-08-18T20:56:09.856854129Z"}}
    def _iterative_buying(self, q):
        print 'Starting iterative buying...'
        while self.qty > self.owned:
            if not q.empty():
                quote = json.loads(q.get())
                if all(x in quote['quote'] for x in ['bid', 'ask', 'quoteTime']):
                    q_time = datetime.strptime(quote['quote']['quoteTime'].split('.')[0],'%Y-%m-%dT%H:%M:%S')
                    #Checking the age of the quote to check it'll be somewhat accurate
                    if (datetime.utcnow() - q_time).total_seconds() < MAX_QUOTE_AGE:
                        ask = quote['quote']['ask']

                        #Checking if the 'current' ask price is lower than our target price
                        if ask < (self.target_price*100):
                            print 'Price good.'
                            bid = quote['quote']['bid']
                            buy_size = min(random.randint(1, self.max_buy), (self.qty - self.owned))

                            #Determining what our bid price should be
                            buy_bid = int(str(bid + (ask - bid) * SPREAD_SPLIT).split('.')[0])

                            print 'Ordering {} shares of {} at a bid of {}, out of {} left to buy.'.format(str(buy_size), self.ticker, str(buy_bid/100), str(self.qty-self.owned))

                            buy = self._single_buy(buy_size, 'limit', buy_bid)

                            while buy.status_code != requests.codes.ok:
                                buy = self._single_buy(buy_size, 'limit', buy_bid)

                            t_sent = time.time()
                            print 'Trade sent.'
                            t_id = buy.json()['id']
                            bought = self._sum_fills(self._trade_status(t_id))

                            #Checking if the full order was filled, and monitoring the status for the duraction of TRADE_WINDOW, then close and add the number of shares purchased to the class attribute
                            while bought < buy_size:
                                if time.time() - t_sent > TRADE_WINDOW:
                                    self._cancel_buy(t_id)
                                    print 'Trade cancelled.'
                                    bought = self._sum_fills(self._trade_status(t_id))
                                    break
                                time.sleep(.05)
                                bought = self._sum_fills(self._trade_status(t_id))

                            self.owned = self.owned + bought
                            print 'We just bought {} shares out of an intial request of {}, giving us a total of {} currently owned.'.format(str(bought), str(buy_size), str(self.owned))

            time.sleep(.2)
        return

    def _get_tickers(self, venue):
        call = requests.get('https://api.stockfighter.io/ob/api/venues/{}/stocks'.format(venue), headers=AUTH)
        return [d['symbol'] for d in call.json()['symbols']]

    def _get_venue(self):
        print 'Getting venue now.'
        call = requests.get('https://api.stockfighter.io/ob/api/venues', headers=AUTH)
        venues = [d['venue'] for d in call.json()['venues']]

        for venue in venues:
            if self.ticker in self._get_tickers(venue):
                self.venue = venue
                return

    def _single_buy(self, qty, order_type, price=0):
        order = {
        'account': self.account,
        'venue': self.venue,
        'stock': self.ticker,
        'qty': qty,
        'direction': 'buy',
        'price': price,
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

    def _launch_tickertape(self, q):
        url="wss://api.stockfighter.io/ob/api/ws/{}/venues/{}/tickertape/stocks/{}".format(self.account, self.venue, self.ticker)
        print 'Launching tickertape now.'
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
        b_chrome.find_element_by_name('session[username]').send_keys(USERNAME)
        b_chrome.find_element_by_name('session[password]').send_keys(PS)
        b_chrome.find_element_by_xpath('//*[@id="loginform"]/button').click()
        time.sleep(10)
        return b_chrome

    def _initiate_market(self, b_chrome):
        b_chrome.find_element_by_xpath('//*[@id="app"]/div/div/div/div/div[1]/div[2]/ul/li[1]/b/a').click()
        time.sleep(3)
        b_chrome.find_element_by_xpath('//*[@id="wrapping"]/nav/div/ul/li[2]').click()
        time.sleep(1)
        b_chrome.find_element_by_xpath('//*[@id="wrapping"]/nav/div/ul/li[2]/ul/li[1]/a/span[1]/b').click()
        time.sleep(10)
        return

    def _parse_trade_info(self, b_chrome):
        self.account = b_chrome.find_element_by_xpath('/html/body/div[3]/div/div[2]/div/div/div[2]/span/p[2]/strong[2]').text.split()[1]
        self.ticker = b_chrome.find_element_by_xpath('/html/body/div[3]/div/div[2]/div/div/div[2]/span/p[2]/em').text
        time.sleep(2)
        b_chrome.find_element_by_xpath('/html/body/div[3]/div/div[2]/div/div/div[3]/button').click()
        return

    def _parse_target_price(self, b_chrome):
        temp = b_chrome.find_elements_by_xpath('//*[@id="wrapping"]/div/div[1]/div/div[1]/p')
        if len(temp) == 0:
            return False
        else:
            self.target_price = float(temp[0].text.split('$')[-1][:-1])
            return True

    def _sum_fills(self, trade):
        return sum([x['qty'] for x in trade.json()['fills']])

    def _extract_target_price(self, b_chrome):
        print 'Starting to try to extract target price...'
        #Make small buys to get the target price to pop up, and checking if its there yet, parse and store as attribute, then
        while self.target_price == 0:
            buy = self._single_buy(5, 'market')
            while buy.status_code != requests.codes.ok:
                buy = self._single_buy(5, 'market')
            t_sent = time.time()
            t_id = buy.json()['id']
            bought = self._sum_fills(self._trade_status(t_id))
            print 'Bought = {}'.format(str(bought))

            #Checking if the full order was filled, and monitoring status if not until the trade has been open for TRADE_WINDOW, then close and add the number of shares purchased to the class attribute
            while bought < 5:
                if time.time() - t_sent > TRADE_WINDOW:
                    self._cancel_buy(t_id)
                    print 'Trade cancelled.'
                    bought = self._sum_fills(self._trade_status(t_id))
                    break
                time.sleep(.1)
                bought = self._sum_fills(self._trade_status(t_id))
                print 'Bought = {}'.format(str(bought))

            self.owned = self.owned + bought
            print 'We just bought {} shares out of an intial request of {}, giving us a total of {} currently owned.'.format(str(bought), '5', str(self.owned))

            #Now pause for a bit and check if the trade desk has revealed the target price, then iterate before trading again to prod it along.
            time.sleep(1)
            for x in xrange(3):
                if self._parse_target_price(b_chrome):
                    print 'Target price = {}, ending extraction function.'.format(str(self.target_price))
                    return
                else:
                    time.sleep(10)


if __name__ == '__main__':
    acc = Account()
    acc.block_buy()
