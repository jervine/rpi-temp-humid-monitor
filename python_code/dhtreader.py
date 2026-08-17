"""DHT sensor reader with the same API as the legacy dhtreader.so extension."""

import logging
import os
import time

DHT11 = 11
DHT22 = 22

_DHT_GOOD = 0
_DHT_BAD_CHECKSUM = 1
_DHT_BAD_DATA = 2
_DHT_TIMEOUT = 3
_STATUS_NAMES = {
    _DHT_GOOD: 'good',
    _DHT_BAD_CHECKSUM: 'bad checksum',
    _DHT_BAD_DATA: 'bad data',
    _DHT_TIMEOUT: 'timeout',
}

_chip = None
_sensors = {}
_adafruit_devices = {}
_backend = None
_one_wire_warned = False


def init():
    """Initialize the DHT reader backend."""
    return None


def close():
    """Release cached DHT devices and their GPIO lines."""
    global _chip, _backend, _one_wire_warned

    for sensor in _sensors.values():
        try:
            sensor.cancel()
        except Exception:
            pass
    _sensors.clear()

    if _chip is not None:
        try:
            import lgpio
            lgpio.gpiochip_close(_chip)
        except Exception:
            pass
        _chip = None

    for device in _adafruit_devices.values():
        try:
            device.exit()
        except Exception:
            pass
    _adafruit_devices.clear()
    _backend = None
    _one_wire_warned = False


def read(dev_type, pin):
    """
    Read temperature (C) and humidity (%).

    Returns (temperature, humidity) on success, or (None, None) on failure.
    """
    pin = int(pin)
    _warn_if_one_wire_conflict(pin)
    backend = _select_backend()
    if backend == 'lgpio':
        return _read_lgpio(dev_type, pin)
    return _read_adafruit(dev_type, pin)


def _select_backend():
    global _backend
    if _backend:
        return _backend

    if _open_gpiochip() is not None:
        _backend = 'lgpio'
        logging.info('DHT backend: lgpio')
        return _backend

    _backend = 'adafruit'
    logging.info('DHT backend: adafruit bitbang')
    return _backend


def _warn_if_one_wire_conflict(pin):
    global _one_wire_warned
    if _one_wire_warned or pin != 4:
        return
    if os.path.isdir('/sys/bus/w1/devices'):
        logging.warning(
            '1-Wire appears enabled; GPIO 4 is the default 1-Wire pin '
            'and will conflict with a DHT data wire on physical pin 7'
        )
        _one_wire_warned = True


def _open_gpiochip():
    global _chip
    if _chip is not None:
        return _chip

    try:
        import lgpio
    except ImportError:
        logging.debug('lgpio is not installed')
        return None

    last_err = None
    preferred = None
    fallback = None
    for chip_id in range(8):
        try:
            handle = lgpio.gpiochip_open(chip_id)
        except Exception as err:
            last_err = err
            continue

        label = _chip_label(lgpio, handle)
        logging.debug('Found gpiochip %s (%s)', chip_id, label)
        text = label.lower()
        if any(token in text for token in ('rp1', 'bcm', 'pinctrl', 'raspberry')):
            if fallback is not None:
                try:
                    lgpio.gpiochip_close(fallback)
                except Exception:
                    pass
            preferred = handle
            break
        if fallback is None:
            fallback = handle
        else:
            try:
                lgpio.gpiochip_close(handle)
            except Exception:
                pass

    _chip = preferred or fallback
    if _chip is None:
        logging.debug('Unable to open a gpiochip: %s', last_err)
    return _chip


def _chip_label(lgpio, handle):
    try:
        info = lgpio.gpiochip_info(handle)
    except Exception:
        return ''
    if isinstance(info, (tuple, list)):
        parts = [str(part) for part in info[:3]]
        return ' '.join(parts)
    name = getattr(info, 'name', '') or ''
    label = getattr(info, 'label', '') or ''
    return f'{name} {label}'.strip()


def _read_lgpio(dev_type, pin):
    try:
        sensor = _get_lgpio_sensor(dev_type, pin)
        _timestamp, _gpio, status, temperature, humidity = sensor.read()
    except Exception as err:
        logging.warning('lgpio DHT read failed: %s', err)
        return None, None

    if status != _DHT_GOOD:
        logging.warning(
            'DHT read failed (%s) on BCM GPIO %d',
            _STATUS_NAMES.get(status, status), pin,
        )
        return None, None

    return float(temperature), float(humidity)


def _get_lgpio_sensor(dev_type, pin):
    key = (dev_type, pin)
    if key not in _sensors:
        _sensors[key] = _LgpioDHT(_chip, pin, dev_type)
    return _sensors[key]


def _read_adafruit(dev_type, pin):
    device = _get_adafruit_device(dev_type, pin)
    try:
        temperature = device.temperature
        humidity = device.humidity
    except RuntimeError as err:
        logging.warning('DHT read failed: %s', err)
        return None, None

    if temperature is None or humidity is None:
        logging.warning('DHT returned no temperature/humidity values')
        return None, None

    return float(temperature), float(humidity)


def _get_adafruit_device(dev_type, pin):
    import adafruit_dht
    import board

    key = (dev_type, pin)
    if key not in _adafruit_devices:
        pin_name = f'D{pin}'
        if not hasattr(board, pin_name):
            raise ValueError(f'Unknown BCM GPIO name {pin_name}')
        gpio = getattr(board, pin_name)
        # PulseIn/libgpiod_pulsein hangs on Raspberry Pi OS after
        # "Unable to set line N to input". Bitbang is the Adafruit fallback.
        if dev_type == DHT11:
            _adafruit_devices[key] = adafruit_dht.DHT11(gpio, use_pulseio=False)
        else:
            _adafruit_devices[key] = adafruit_dht.DHT22(gpio, use_pulseio=False)
    return _adafruit_devices[key]


class _LgpioDHT:
    """
    DHT11/DHT22 reader using lgpio edge callbacks.

    Timing is based on Joan's public-domain DHT.py:
    http://abyz.me.uk/lg/py_lgpio.html
    """

    def __init__(self, chip, gpio, dev_type):
        import lgpio as sbc

        self._sbc = sbc
        self._chip = chip
        self._gpio = gpio
        self._dhtxx = dev_type != DHT11
        self._new_data = False
        self._bits = 0
        self._code = 0
        self._last_edge_tick = 0
        self._timestamp = time.time()
        self._status = _DHT_TIMEOUT
        self._temperature = 0.0
        self._humidity = 0.0
        sbc.gpio_set_watchdog_micros(chip, gpio, 1000)
        self._cb = sbc.callback(chip, gpio, sbc.RISING_EDGE, self._rising_edge)

    def _datum(self):
        return (
            self._timestamp, self._gpio, self._status,
            self._temperature, self._humidity,
        )

    def _validate_dht11(self, b1, b2, b3, b4):
        temperature = b2
        humidity = b4
        valid = b1 == 0 and b3 == 0 and temperature <= 60 and 9 <= humidity <= 90
        return valid, temperature, humidity

    def _validate_dhtxx(self, b1, b2, b3, b4):
        divisor = -10.0 if b2 & 128 else 10.0
        temperature = float(((b2 & 127) << 8) + b1) / divisor
        humidity = float((b4 << 8) + b3) / 10.0
        valid = humidity <= 110.0 and -50.0 <= temperature <= 135.0
        return valid, temperature, humidity

    def _decode(self):
        checksum = self._code & 0xff
        b1 = (self._code >> 8) & 0xff
        b2 = (self._code >> 16) & 0xff
        b3 = (self._code >> 24) & 0xff
        b4 = (self._code >> 32) & 0xff

        if ((b1 + b2 + b3 + b4) & 0xFF) != checksum:
            self._status = _DHT_BAD_CHECKSUM
            self._new_data = True
            return

        if self._dhtxx:
            valid, temperature, humidity = self._validate_dhtxx(b1, b2, b3, b4)
        else:
            valid, temperature, humidity = self._validate_dht11(b1, b2, b3, b4)

        if valid:
            self._timestamp = time.time()
            self._temperature = temperature
            self._humidity = humidity
            self._status = _DHT_GOOD
        else:
            self._status = _DHT_BAD_DATA
        self._new_data = True

    def _rising_edge(self, chip, gpio, level, tick):
        if level != self._sbc.TIMEOUT:
            edge_len = tick - self._last_edge_tick
            self._last_edge_tick = tick
            if edge_len > 2e8:
                self._bits = 0
                self._code = 0
            else:
                self._code <<= 1
                if edge_len > 1e5:
                    self._code |= 1
                self._bits += 1
        elif self._bits >= 30:
            self._decode()

    def _trigger(self):
        sbc = self._sbc
        sbc.gpio_claim_output(self._chip, self._gpio, 0)
        time.sleep(0.001 if self._dhtxx else 0.015)
        self._bits = 0
        self._code = 0
        sbc.gpio_claim_alert(self._chip, self._gpio, sbc.RISING_EDGE)

    def cancel(self):
        if self._cb is not None:
            self._cb.cancel()
            self._cb = None

    def read(self):
        self._new_data = False
        self._status = _DHT_TIMEOUT
        self._trigger()
        for _ in range(20):
            time.sleep(0.05)
            if self._new_data:
                break
        return self._datum()
