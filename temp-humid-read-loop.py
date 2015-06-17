#!/usr/bin/env python
# -*- coding:utf-8 -*-

import sys
import dhtreader
import updateMysql
import ConfigParser
import time
from threading import Timer,Thread,Event
import logging
from datetime import timedelta
from datetime import datetime

oldtemp = "NULL"
oldhumid = "NULL"

def exec_every_n_seconds(n,f,*args):
    first_called=datetime.now()
    print args
    f(*args)
    num_calls=1
    drift=timedelta()
    time_period=timedelta(seconds=n)
    while 1:
        time.sleep(n-drift.microseconds/1000000.0)
        current_time = datetime.now()
        f(*args)
        num_calls += 1
        difference = current_time - first_called
        drift = difference - time_period* num_calls
        print "drift=",drift

def sensorRead(hwtype, pin, retries, timeout, maxtemp, mintemp, maxhumid, minhumid):
    global oldtemp
    global oldhumid
    for num in range(retries):
        try:
            t, h = dhtreader.read(dev_type, dhtpin)
        except:
            if ((num + 1) < retries):
                print('Exception detected! We will retry. Loop number: %d', num)
                logging.warning('Exception detected! We will retry. Loop number: %d', num)
                time.sleep(timeout)
            else:
                print('Exception detected - we are out of retries. Skipping the measurement in this cycle.')
                logging.error('Exception detected - we are out of retries. Skipping the measurement in this cycle.')
        else:
            if t and h:
                print(t, h)
                if (oldtemp != "NULL") and ((t - oldtemp < tempdiff) or (oldtemp - t < tempdiff)) and ((h - oldhumid < humiddiff) or (oldhumid - h < humiddif)):
                    print('Current temperature close enough to previous temperature and previous temperature is not NULL, it is:')
                    logging.debug('Current temperature close enough to previous temperature and previous temperature is not NULL, it is: %s', oldtemp)
                    print oldtemp
                    print('Current humidity close enough to previous humidity and previous humidity is not NULL, it is:')
                    logging.debug('Current humidity close enough to previous humidity and previous humidity is not NULL, it is: %s', oldhumid)
                    print oldhumid
                if (t < maxtemp) and (t > mintemp) and (h < maxhumid) and (h > minhumid):
                    print('Temperature is less than {0} and greater than {1}, humidity is less than {2} and greater than {3}'.format(maxtemp,mintemp,maxhumid,minhumid))
                    logging.debug('Temperature is less than {0} and greater than {1}, humidity is less than {2} and greater than {3}'.format(maxtemp,mintemp,maxhumid,minhumid))
                    updateMysql.main(t, h, host, db, username, password)
                    oldtemp=t
                    oldhumid=h
                    break
                else:
                    print('Temperature {0} or humidity {1} is outside of allowable values - error! Check your configuration.'.format(t, h))
                    logging.error('Temperature {0} or humidity {1} is outside of allowable values - error! Check your configuration.'.format(t, h))
            else:
                    print("Failed to read from sensor, maybe try again?")
                    logging.warning('Failed to read from sensor, maybe try again?')
    return 0

DHT11 = 11
DHT22 = 22
AM2302 = 22

config = ConfigParser.ConfigParser()
config.read('temphumid.conf')
hwtype=config.get('hardware', 'DHT')
pin=config.get('hardware', 'PIN')
retries=int(config.get('software', 'retries'))
timeout=int(config.get('software', 'timeout'))
interval=int(config.get('software', 'interval'))
maxtemp=int(config.get('software', 'maxtemp'))
mintemp=int(config.get('software', 'mintemp'))
tempdiff=int(config.get('software', 'tempdiff'))
maxhumid=int(config.get('software', 'maxhumid'))
minhumid=int(config.get('software', 'minhumid'))
humiddiff=int(config.get('software', 'humiddiff'))
logfile=(config.get('software', 'logfile'))
loglevel=(config.get('software', 'loglevel'))
host=(config.get('database', 'host'))
db=(config.get('database', 'db'))
username=(config.get('database', 'username'))
password=(config.get('database', 'password'))


if loglevel == "debug":
    logging.basicConfig(filename = logfile, format='%(asctime)s %(levelname)s:%(message)s', datefmt='%Y-%m-%d %H:%M:%S', level=logging.DEBUG)
elif loglevel == "info":    
    logging.basicConfig(filename = logfile, format='%(asctime)s %(levelname)s:%(message)s', datefmt='%Y-%m-%d %H:%M:%S', level=logging.INFO)
elif loglevel == "warn":
    logging.basicConfig(filename = logfile, format='%(asctime)s %(levelname)s:%(message)s', datefmt='%Y-%m-%d %H:%M:%S', level=logging.WARNING)
elif loglevel == "error":
    logging.basicConfig(filename = logfile, format='%(asctime)s %(levelname)s:%(message)s', datefmt='%Y-%m-%d %H:%M:%S', level=logging.ERROR)
else:
    logging.basicConfig(filename = logfile, format='%(asctime)s %(levelname)s:%(message)s', datefmt='%Y-%m-%d %H:%M:%S', level=logging.CRITICAL)

dhtreader.init()

dev_type = None
if hwtype == "11":
    dev_type = DHT11
    print('Configured to use DHT11 device')
    logging.info('Configured to use DHT11 device')
elif hwtype == "22":
    dev_type = DHT22
    print('Configured to use DHT22 device')
    logging.info('Configured to use DHT22 device')
elif hwtype == "2302":
    dev_type = AM2302
    print('Configured to use AM 2302 device')
    logging.info('Configured to use AM2303 device')
else:
    print('Invalid hardware type, only DHT11, DHT22 and AM 2302 are supported for now.!')
    logging.warn('Invalid hardware type, only DHT11, DHT22 and AM 2302 are supported for now.!')
    sys.exit(3)

dhtpin = int(pin)
if dhtpin <= 0:
    print("Invalid GPIO pin#, correct your configuration file")
    logging.warn("Invalid GPIO pin#, correct your configuration file")
    sys.exit(3)

print("using pin #{0}".format(dhtpin))
logging.info("using pin #{0}".format(dhtpin))

print('About to enter infinte loop ...')
logging.info("About to enter infinite loop")
exec_every_n_seconds(60,sensorRead,hwtype,pin,retries,timeout,maxtemp,mintemp,maxhumid,minhumid)
