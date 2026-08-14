#!/usr/bin/env python
# -*- coding:utf-8 -*-

import logging
import time
import dhtreader
import updateMysql
import readMysql
import thmonitor_common as common


def sensor_read(cfg, dev_type, dhtpin):
    """Perform a single sensor read using the last DB values for validation."""
    oldtemp, oldhumid = readMysql.main(
        cfg['host'], cfg['db'], cfg['username'], cfg['password'],
        logging, cfg['sql_retries'], cfg['sql_timeout'],
    )
    logging.debug(
        'Previous temperature %s and humidity %s loaded from database.',
        oldtemp, oldhumid,
    )

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
                    'Sensor read failed after %d attempts; giving up.',
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
            return 0

        if num + 1 < cfg['retries']:
            time.sleep(cfg['timeout'])

    return 1


def main():
    cfg = common.load_config()
    common.setup_logging(cfg['logfile'], cfg['loglevel'])

    dhtreader.init()
    dev_type = common.resolve_dht_type(cfg['hwtype'])
    dhtpin = common.validate_pin(cfg['pin'])

    logging.info(
        'Single run temperature and humidity reading '
        '[version: 1.1, Jonathan Ervine, 2015-06-17]'
    )
    return sensor_read(cfg, dev_type, dhtpin)


if __name__ == '__main__':
    raise SystemExit(main())
