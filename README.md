# rpi-temp-humid-monitor
Raspberry Pi temperature humidity monitor

## Python 3 setup

The Python monitoring scripts require Python 3 and use `adafruit-circuitpython-dht`
instead of the legacy Python 2 `dhtreader.so` extension.

### Recommended install (venv + systemd)

From a clone of this repository on the Raspberry Pi:

```bash
cd rpi-temp-humid-monitor
./install.sh            # show help
sudo ./install.sh --install
```

This will:

- install required system packages (`python3-venv`, `default-libmysqlclient-dev`, etc.)
- create a virtual environment at `/usr/local/lib/thmonitor/venv`
- install Python dependencies into that venv (not system-wide)
- install app files to `/usr/local/lib/thmonitor`
- install `/etc/thMonitor.conf` if it does not already exist
- install command wrappers: `thmonitor-single`, `thmonitor-loop`
- enable and start the `thmonitor` systemd service (loop daemon)

Edit `/etc/thMonitor.conf` after install (GPIO pin, MySQL credentials, limits).

Useful commands:

```bash
sudo systemctl status thmonitor
sudo systemctl restart thmonitor
tail -f /var/log/th-python.log
thmonitor-single    # one-off read (uses venv)
thmonitor-smoke --pin 4   # smoke test: read sensor, print values (no MySQL)
```

Smoke test from a repo clone without a full install (uses the same venv/deps as the monitor, not a separate one):

```bash
python3 -m venv python_code/.venv
python_code/.venv/bin/pip install -r python_code/requirements.txt
python_code/.venv/bin/python python_code/smoke-test-sensor.py --pin 4
```

Cron-based single-shot mode instead of the loop daemon:

```bash
sudo ./install.sh --install --cron
```

Install without starting the service:

```bash
sudo ./install.sh --install --no-start
```

Uninstall:

```bash
sudo ./install.sh --uninstall
```

### Manual install (legacy)

If you prefer not to use the installer:

```bash
sudo apt install python3 python3-pip python3-dev python3-venv default-libmysqlclient-dev build-essential
python3 -m venv /usr/local/lib/thmonitor/venv
sudo /usr/local/lib/thmonitor/venv/bin/pip install -r python_code/requirements.txt
sudo cp python_code/temphumid.conf /etc/thMonitor.conf   # edit credentials and GPIO pin
# copy python_code/*.py to your chosen install directory and point systemd/cron at the venv python
```

Do not copy or keep `dhtreader.so`; use `dhtreader.py` instead.

---

This is my implementation of making a Raspberry Pi powered temperature and humidity monitor. The original instructions that I followed were created by wpnsmith at [the instructables website](http://www.instructables.com/id/Raspberry-Pi-Temperature-Humidity-Network-Monitor/)

In this repository are my copies of the th.c code, a thd init script, and two files for creating a Google Chart graph rather than the python based GraphTH.py using matplotlib that wpnsmith used.

The th.c code was modified so that a fourth column in MySQL is used (an auto incrementing id - probably not strictly necessary as the ComputerTime entry is incrementing anyway), as well as having th detect if an incorrect temperature/humidity reading has been made (by checking against the previously recorded value) and silently not adding this to the MySQL database if it is seen to be a big change.

Using a thd init script means that we don't need to modify /etc/rc.local - which is useful for me as this file is used by other projects and can be overwritten at times.

## UPDATED - 10 July 2015
Added a python script, readMysql.py, to read the previous values of temperature and humidity from the MySQL database. This is necessary for the single run python script, as we don't have a previous reading to compare against.

## UPDATED - 24 June 2015
Fixed a typo in a variable name (humiddiff) that could cause the daemon to crash if an erroneous reading was made.

## UPDATED - 23 June 2015
Fixed a bug in the code where the script would crash as I hadn't passed the temperature and humidity difference tolerances allowed to the loop. If an erroneous reading was made, the script would crash.

## UPDATED - 19 June 2015
The updateMysql.py script has been updated to provide a method of retrying failed MySQL updates. Primarily this was added so that when the server is booted up, the daemon version of the code can retry a number of times before giving up, as the MySQL server will not necessarily have finished starting up.

An updated thMonitord init script has been added, and the temp-humid-read-loop and temp-humid-read-single scripts have been altered so that they are currently hardcoded to use a configuration file called /etc/thMonitor.conf

## UPDATED - 18 June 2015
There are now two python scripts (with logging added rather than printing to stdout)

 - temp-humid-read-loop.py - this code should loop and run the temperature/humidity readind every 60 seconds. I have tried to add code to ensure that this loops every 60 seconds regardless of how long the actual reading takes. Due to occasional reading errors, the function to read temperature and humidity can vary in length - dependent upon the timeout and number of retries conifgured. The code should time the length of the sensorRead function and subtract this time from the configured reading interval. Tests have shown this is reasonably accurate but some drift has still been observed.

 - temp-humid-python-single.py - this code is a simplified python script taken from the looping script. The looping logic has been removed, and a single pass is made reading the temperature and humidity readings. Any errors from a reading during this single pass are retried according to the timeout and retries configured though - so a single read should succeed. This script can be put into a cron job to run on a regularly scheduled basis, which might be less prone to drift than the looped version.

 - updateMysql.py - this code has been cleaned up so that it logs to the logfile rather than to stdout by default.

## UPDATED - 17 June 2015
Looking to replace the C code with a python script that takes a configuration file. Added here:

 - temp-humid-read-loop.py - python code to continuously loop and read the temperature and humidity settings

 - updateMysql.py - python code called by the loop script to update the MySQL database

 - temphumid.conf - sample configuration file to be used with the python script

 - dhtreader.py - pure Python DHT reader wrapper using adafruit-circuitpython-dht (replaces dhtreader.so)

###Please note this updated python code was heavily inspired by the work done by Adafruit here:###
[https://github.com/adafruit/Adafruit-Raspberry-Pi-Python-Code/tree/master/Adafruit_DHT_Driver_Python](https://github.com/adafruit/Adafruit-Raspberry-Pi-Python-Code/tree/master/Adafruit_DHT_Driver_Python)

