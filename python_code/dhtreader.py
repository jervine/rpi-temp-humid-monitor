"""DHT sensor reader with the same API as the legacy dhtreader.so extension."""

DHT11 = 11
DHT22 = 22

_devices = {}


def init():
    """Initialize the DHT reader backend (no-op for adafruit_dht)."""
    return None


def _get_device(dev_type, pin):
    import adafruit_dht
    from adafruit_blinka.microcontroller.bcm283x.pin import Pin

    key = (dev_type, pin)
    if key not in _devices:
        gpio = Pin(pin)
        # PulseIn/libgpiod_pulsein is unreliable on Raspberry Pi OS: it prints
        # "Unable to set line N to input" and then hangs. Bitbang reads work.
        if dev_type == DHT11:
            _devices[key] = adafruit_dht.DHT11(gpio, use_pulseio=False)
        else:
            _devices[key] = adafruit_dht.DHT22(gpio, use_pulseio=False)
    return _devices[key]


def read(dev_type, pin):
    """
    Read temperature (C) and humidity (%).

    Returns (temperature, humidity) on success, or (None, None) on failure.
    """
    device = _get_device(dev_type, pin)
    try:
        temperature = device.temperature
        humidity = device.humidity
    except RuntimeError:
        return None, None

    if temperature is None or humidity is None:
        return None, None

    return float(temperature), float(humidity)


def close():
    """Release cached DHT devices and their GPIO lines."""
    for device in _devices.values():
        try:
            device.exit()
        except Exception:
            pass
    _devices.clear()
