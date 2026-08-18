#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Smoke test: read the DHT sensor once and print temperature and humidity."""

import argparse
import configparser
import logging
import os
import sys
import time

import dhtreader
import thmonitor_common as common

_LOCAL_CONFIG = os.path.join(os.path.dirname(__file__), 'temphumid.conf')
_CONFIG_CANDIDATES = (common.DEFAULT_CONFIG, _LOCAL_CONFIG)


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            'Read the DHT sensor once and print temperature and humidity. '
            'Use --pin to override the GPIO pin from config.'
        ),
    )
    parser.add_argument(
        '--pin',
        type=int,
        metavar='GPIO',
        help='BCM GPIO pin for the DHT data wire (overrides config)',
    )
    parser.add_argument(
        '--type',
        dest='hwtype',
        choices=['11', '22', '2302'],
        help='Sensor type: 11 (DHT11), 22 (DHT22), or 2302 (AM2302)',
    )
    parser.add_argument(
        '--config', '-c',
        help='Config file for pin/type defaults (overrides search order)',
    )
    parser.add_argument(
        '--retries',
        type=int,
        default=3,
        help='Number of read attempts before failing (default: 3)',
    )
    parser.add_argument(
        '--timeout',
        type=float,
        default=2.0,
        help='Seconds to wait between retries (default: 2.0)',
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Show DHT backend log messages on stderr',
    )
    return parser.parse_args()


def load_hardware_defaults(config_path=None):
    """Return (pin, hwtype) from the first readable config file."""
    paths = [config_path] if config_path else list(_CONFIG_CANDIDATES)
    config = configparser.ConfigParser()
    for path in paths:
        if path and config.read(path):
            return (
                config.getint('hardware', 'PIN'),
                config.get('hardware', 'DHT'),
                path,
            )
    return None, None, None


def resolve_pin_and_type(args):
    """Resolve BCM GPIO pin and hardware type from CLI args and/or config."""
    pin = args.pin
    hwtype = args.hwtype
    config_used = args.config

    if pin is None or hwtype is None:
        cfg_pin, cfg_type, cfg_path = load_hardware_defaults(args.config)
        if pin is None:
            pin = cfg_pin
        if hwtype is None:
            hwtype = cfg_type
        if config_used is None:
            config_used = cfg_path

    if pin is None:
        print(
            'ERROR: no GPIO pin specified; use --pin or provide a config file '
            f'(checked: {", ".join(_CONFIG_CANDIDATES)})',
            file=sys.stderr,
        )
        sys.exit(1)

    if hwtype is None:
        hwtype = '22'

    return pin, hwtype, config_used


def read_sensor(dev_type, pin, retries, timeout):
    """Read the sensor, retrying on failure. Returns (temp, humidity) or None."""
    for attempt in range(1, retries + 1):
        try:
            temperature, humidity = dhtreader.read(dev_type, pin)
        except Exception as err:
            if attempt < retries:
                print(
                    f'Read failed (attempt {attempt}/{retries}): {err}',
                    file=sys.stderr,
                )
                time.sleep(timeout)
                continue
            print(f'ERROR: sensor read failed: {err}', file=sys.stderr)
            return None

        if temperature is not None and humidity is not None:
            return temperature, humidity

        if attempt < retries:
            print(
                f'Empty reading (attempt {attempt}/{retries}); retrying...',
                file=sys.stderr,
            )
            time.sleep(timeout)

    print(f'ERROR: no valid reading after {retries} attempts', file=sys.stderr)
    return None


def main():
    args = parse_args()

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format='%(levelname)s: %(message)s',
        stream=sys.stderr,
    )

    pin, hwtype, config_used = resolve_pin_and_type(args)
    if pin <= 0:
        print(f'ERROR: invalid GPIO pin: {pin}', file=sys.stderr)
        return 1

    dev_type = common.resolve_dht_type(hwtype)

    dhtreader.init()
    try:
        result = read_sensor(dev_type, pin, args.retries, args.timeout)
        if result is None:
            return 1

        temperature, humidity = result
        print(f'Temperature: {temperature:.1f} C')
        print(f'Humidity: {humidity:.1f} %')
        print(f'GPIO pin: {pin} (BCM)')
        if config_used:
            print(f'Config: {config_used}')
        return 0
    finally:
        dhtreader.close()


if __name__ == '__main__':
    raise SystemExit(main())
