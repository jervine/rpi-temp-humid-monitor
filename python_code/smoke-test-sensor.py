#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Smoke test: read the DHT sensor once and print temperature and humidity.

Uses the same Python dependencies as the monitor (adafruit-circuitpython-dht,
lgpio, etc.). Do not create a separate venv for this script.

After install:
  thmonitor-smoke --pin 4

From a repo clone (one-time venv setup):
  python3 -m venv python_code/.venv
  python_code/.venv/bin/pip install -r python_code/requirements.txt
  python_code/.venv/bin/python python_code/smoke-test-sensor.py --pin 4
"""

import argparse
import configparser
import logging
import os
import shutil
import subprocess
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
        epilog=(
            'Run with the monitor venv (thmonitor-smoke after install, or '
            'python_code/.venv/bin/python after pip install -r requirements.txt). '
            'System python3 will fail if adafruit_dht is not installed.'
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
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
    parser.add_argument(
        '--diagnose',
        action='store_true',
        help='Print GPIO contention checks and exit (no sensor read)',
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


def warn_if_gpio_may_be_busy(pin):
    """Warn when something else is likely holding the configured GPIO line."""
    issues = list(_gpio_contention_checks(pin))
    for message in issues:
        print(f'WARNING: {message}', file=sys.stderr)


def _gpio_contention_checks(pin):
    """Yield human-readable descriptions of likely GPIO conflicts."""
    if shutil.which('systemctl') is not None:
        try:
            active = subprocess.run(
                ['systemctl', 'is-active', '--quiet', 'thmonitor.service'],
                check=False,
            ).returncode == 0
        except OSError:
            active = False
        if active:
            yield (
                'thmonitor.service is running (stop with: sudo systemctl stop thmonitor)'
            )

    cron_file = '/etc/cron.d/thmonitor'
    if os.path.isfile(cron_file):
        yield (
            f'{cron_file} exists and may run thmonitor-single every minute '
            '(disable cron or wait between runs)'
        )

    if pin == 4 and os.path.isdir('/sys/bus/w1/devices'):
        yield (
            '1-Wire is enabled; the kernel owns GPIO 4 (physical pin 7). '
            'Disable 1-Wire in raspi-config or move the sensor to another pin'
        )

    if shutil.which('pgrep') is not None:
        try:
            result = subprocess.run(
                ['pgrep', '-af', r'temp-humid-read|thmonitor'],
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError:
            result = None
        if result and result.stdout.strip():
            for line in result.stdout.strip().splitlines():
                if 'smoke-test-sensor' not in line:
                    yield f'another monitor process may be running: {line.strip()}'


def diagnose_gpio(pin):
    """Print GPIO diagnostics and return the number of issues found."""
    print(f'GPIO diagnostics for BCM pin {pin}:')
    issues = list(_gpio_contention_checks(pin))
    if issues:
        for message in issues:
            print(f'  ! {message}')
    else:
        print('  - no obvious software conflicts (systemd/cron/1-Wire/monitor processes)')

    line_info = dhtreader.describe_gpio_line(pin)
    if line_info:
        print(f'  - {line_info}')
    else:
        print('  - lgpio line info unavailable (lgpio not installed or no gpiochip)')

    print(
        '\nDHT sensors need exclusive access to the data pin for ~1 s per read. '
        'Timeouts on early attempts are normal; GPIO busy usually means the kernel '
        'or another process owns the line.'
    )
    return len(issues)


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

    if args.diagnose:
        dhtreader.init()
        try:
            return 1 if diagnose_gpio(pin) else 0
        finally:
            dhtreader.close()

    warn_if_gpio_may_be_busy(pin)

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
