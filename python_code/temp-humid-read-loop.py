#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import time

import dhtreader
import updateMysql
import thmonitor_common as common

oldtemp = 'NULL'
oldhumid = 'NULL'


def sensor_read(cfg, dev_type, dhtpin):
    """Read sensor, validate, and store a single measurement."""
    global oldtemp, oldhumid

    start = time.time()
    limits = {
        'maxtemp': cfg['maxtemp'],
        'mintemp': cfg['mintemp'],
        'tempdiff': cfg['tempdiff'],
        'maxhumid': cfg['maxhumid'],
        'minhumid': cfg['minhumid'],
        'humiddiff': cfg['humiddiff'],
    }

    for num in range(cfg['retries']):
        try:
            t, h = dhtreader.read(dev_type, dhtpin)
        except Exception:
            if num + 1 < cfg['retries']:
                logging.warning(
                    'Exception during sensor read; retry %d/%d',
                    num + 1, cfg['retries'],
                )
                time.sleep(cfg['timeout'])
            else:
                logging.error(
                    'Sensor read failed after %d attempts; skipping this cycle.',
                    cfg['retries'],
                )
            continue

        if not t or not h:
            logging.warning('Sensor returned empty reading; retrying.')
            if num + 1 < cfg['retries']:
                time.sleep(cfg['timeout'])
            continue

        logging.debug('Temperature and humidity read as %s and %s', t, h)
        if common.reading_is_plausible(t, h, oldtemp, oldhumid, limits):
            updateMysql.main(
                t, h,
                cfg['host'], cfg['db'], cfg['username'], cfg['password'],
                logging, cfg['sql_retries'], cfg['sql_timeout'],
            )
            oldtemp = t
            oldhumid = h
            break

        if num + 1 < cfg['retries']:
            time.sleep(cfg['timeout'])

    duration = time.time() - start
    logging.debug('Sensor read cycle took %.2f seconds', duration)
    return duration


def run_loop(cfg, dev_type, dhtpin):
    """Run sensor reads on a fixed interval, accounting for read duration."""
    interval = cfg['interval']
    logging.debug('Reading sensor every %d seconds', interval)

    while True:
        start = time.time()
        sensor_read(cfg, dev_type, dhtpin)
        elapsed = time.time() - start
        sleep_for = max(0, interval - elapsed)
        logging.debug('Sleeping %.2f seconds until next reading', sleep_for)
        time.sleep(sleep_for)


def main():
    cfg = common.load_config()
    common.setup_logging(cfg['logfile'], cfg['loglevel'])

    dhtreader.init()
    dev_type = common.resolve_dht_type(cfg['hwtype'])
    dhtpin = common.validate_pin(cfg['pin'])

    logging.info(
        'Multiple (infinite loop) temperature and humidity reading '
        '[version: 2.0, Python 3]'
    )
    run_loop(cfg, dev_type, dhtpin)


if __name__ == '__main__':
    main()
