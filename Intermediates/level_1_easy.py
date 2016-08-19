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

class Account(object):

    def __init__(self):
        self.target_price = 0
        return

    def block_buy(self, qty=100000, max_buy=200, owned=0):
        self.qty = qty
        self.max_buy = max_buy
        self.owned = owned

        b_chrome = self._login()
        self._initiate_market(b_chrome)
        self._parse_trade_info(b_chrome)
        self._get_venue()

        self._extract_target_price(b_chrome)

        self._buy_remaining()

        print 'We have now bought {} shares of {} on account {}.'.format(self.owned, self.ticker, self.account)

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

    def _trade_status(self, t_id):
        call = requests.get('https://api.stockfighter.io/ob/api/venues/{}/stocks/{}/orders/{}'.format(self.venue, self.ticker, t_id), headers=AUTH)
        print call.json()
        return call

    def _buy_remaining(self):
        price = int(str(self.target_price * 95).split('.')[0])
        buy = self._single_buy((self.qty - self.owned), 'limit', price)
        print buy.json()
        while buy.status_code != requests.codes.ok:
            buy = self._single_buy((self.qty - self.owned), 'limit', price)
            print buy.json()
        print buy.json().keys()
        while self.owned < self.qty:
            check = self._trade_status(buy.json()['id'])
            print check
            self.owned = self.owned + check.json()['totalFilled']
            time.sleep(2)
        return

    def _extract_target_price(self, b_chrome):
        print 'Starting to try to extract target price...'
        #Make small buys to get the target price to pop up, and checking if its there yet, parse and store as attribute, then
        while self.target_price == 0:
            buy = self._single_buy(10, 'market')
            while buy.status_code != requests.codes.ok:
                buy = self._single_buy(10, 'market')
            t_sent = time.time()
            print 'Trade sent.'
            print buy.json()
            remaining = buy.json()['qty']
            print 'Remaining = {}'.format(str(remaining))

            #Checking if the full order was filled, and monitoring status if not until the trade has been open for TRADE_WINDOW, then close and add the number of shares purchased to the class attribute
            while remaining >0:
                if time.time() - t_sent > TRADE_WINDOW:
                    self._cancel_buy(buy.json()['id'])
                    print 'Trade cancelled.'
                    break
                time.sleep(.1)
                remaining = self._trade_status(buy.json()['id']).json()['qyt']
                print 'Remaining = {}'.format(str(remaining))

            self.owned = self.owned + (10 - remaining)
            print 'We just bought {} shares out of an intial request of {}, giving us a total of {} currently owned.'.format(str(10-remaining), '10', str(self.owned))

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
