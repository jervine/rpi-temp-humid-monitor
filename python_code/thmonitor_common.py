#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Shared configuration, logging, and sensor validation for thMonitor scripts."""

from __future__ import print_function

import sys
import logging
import ConfigParser

DHT11 = 11
DHT22 = 22
AM2302 = 22

DEFAULT_CONFIG = '/etc/thMonitor.conf'


def load_config(path=DEFAULT_CONFIG):
    """Load and return thMonitor configuration as a dict."""
    config = ConfigParser.ConfigParser()
    if not config.read(path):
        print('ERROR: configuration file not found: {0}'.format(path), file=sys.stderr)
        sys.exit(1)

    return {
        'config_path': path,
        'hwtype': config.get('hardware', 'DHT'),
        'pin': config.get('hardware', 'PIN'),
        'retries': config.getint('software', 'retries'),
        'timeout': config.getint('software', 'timeout'),
        'interval': config.getint('software', 'interval'),
        'maxtemp': config.getint('software', 'maxtemp'),
        'mintemp': config.getint('software', 'mintemp'),
        'tempdiff': config.getint('software', 'tempdiff'),
        'maxhumid': config.getint('software', 'maxhumid'),
        'minhumid': config.getint('software', 'minhumid'),
        'humiddiff': config.getint('software', 'humiddiff'),
        'logfile': config.get('software', 'logfile'),
        'loglevel': config.get('software', 'loglevel'),
        'host': config.get('database', 'host'),
        'db': config.get('database', 'db'),
        'username': config.get('database', 'username'),
        'password': config.get('database', 'password'),
        'sql_retries': config.getint('database', 'sql_retries'),
        'sql_timeout': config.getint('database', 'sql_timeout'),
    }


def setup_logging(logfile, loglevel):
    """Configure logging from config file settings."""
    levels = {
        'debug': logging.DEBUG,
        'info': logging.INFO,
        'warn': logging.WARNING,
        'error': logging.ERROR,
        'critical': logging.CRITICAL,
    }
    level = levels.get(loglevel.lower(), logging.CRITICAL)
    logging.basicConfig(
        filename=logfile,
        format='%(asctime)s %(levelname)s:%(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        level=level,
    )


def resolve_dht_type(hwtype):
    """Map config hardware type string to dhtreader device constant."""
    types = {
        '11': (DHT11, 'DHT11'),
        '22': (DHT22, 'DHT22'),
        '2302': (AM2302, 'AM2302'),
    }
    if hwtype not in types:
        logging.warn(
            'Invalid hardware type %r; supported values are 11, 22, and 2302',
            hwtype,
        )
        sys.exit(3)
    dev_type, name = types[hwtype]
    logging.info('Configured to use %s device', name)
    return dev_type


def validate_pin(pin):
    """Return GPIO pin number or exit if invalid."""
    dhtpin = int(pin)
    if dhtpin <= 0:
        logging.warn('Invalid GPIO pin number: %s', pin)
        sys.exit(3)
    logging.info('using pin #%d', dhtpin)
    return dhtpin


def reading_is_plausible(t, h, oldtemp, oldhumid, limits):
    """
    Return True if reading is within configured bounds and not an abrupt jump
    from the previous values.
    """
    if not (limits['mintemp'] < t < limits['maxtemp']):
        logging.error(
            'Temperature %s outside allowable range (%d, %d)',
            t, limits['mintemp'], limits['maxtemp'],
        )
        return False

    if not (limits['minhumid'] < h < limits['maxhumid']):
        logging.error(
            'Humidity %s outside allowable range (%d, %d)',
            h, limits['minhumid'], limits['maxhumid'],
        )
        return False

    if oldtemp != 'NULL' and abs(t - oldtemp) >= limits['tempdiff']:
        logging.warning(
            'Temperature jump too large: current=%s previous=%s (limit=%d)',
            t, oldtemp, limits['tempdiff'],
        )
        return False

    if oldhumid != 'NULL' and abs(h - oldhumid) >= limits['humiddiff']:
        logging.warning(
            'Humidity jump too large: current=%s previous=%s (limit=%d)',
            h, oldhumid, limits['humiddiff'],
        )
        return False

    return True
