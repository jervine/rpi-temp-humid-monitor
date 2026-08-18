#!/bin/bash
#
# Install rpi-temp-humid-monitor as a system app with a Python venv.
#
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_CODE="${REPO_ROOT}/python_code"
SERVICE_TEMPLATE="${REPO_ROOT}/systemd/thmonitor.service.in"

INSTALL_ROOT="${INSTALL_ROOT:-/usr/local/lib/thmonitor}"
CONFIG_FILE="${CONFIG_FILE:-/etc/thMonitor.conf}"
LOG_FILE="${LOG_FILE:-/var/log/th-python.log}"
BIN_SINGLE="${BIN_SINGLE:-/usr/local/bin/thmonitor-single}"
BIN_LOOP="${BIN_LOOP:-/usr/local/bin/thmonitor-loop}"
BIN_SMOKE="${BIN_SMOKE:-/usr/local/bin/thmonitor-smoke}"
SYSTEMD_UNIT="${SYSTEMD_UNIT:-/etc/systemd/system/thmonitor.service}"
CRON_FILE="${CRON_FILE:-/etc/cron.d/thmonitor}"
LEGACY_DIR="/usr/local/bin/thMonitor"

RUN_MODE="systemd"
DO_START=1
DO_INSTALL=0
DO_UNINSTALL=0

APT_PACKAGES=(
    python3
    python3-venv
    python3-dev
    python3-pip
    python3-setuptools
    swig
    unzip
    wget
    default-libmysqlclient-dev
    build-essential
)

PYTHON_MODULES=(
    dhtreader.py
    readMysql.py
    smoke-test-sensor.py
    temp-humid-read-loop.py
    temp-humid-read-single.py
    thmonitor_common.py
    updateMysql.py
)

usage() {
    local cmd
    cmd="$(basename "$0")"
    cat <<EOF
Install rpi-temp-humid-monitor as a system app with a Python venv.

Usage:
  sudo ./$cmd --install [options]
  sudo ./$cmd --uninstall
  ./$cmd --help

Actions:
  --install       Install the monitor (venv, app files, wrappers, systemd by default)
  --uninstall     Remove installed app files, wrappers, and services
  -h, --help      Show this help

Install options:
  --cron          Use a cron job for single-shot reads instead of the systemd loop
  --no-start      Install files and unit, but do not enable or start the service

Environment overrides:
  INSTALL_ROOT    Install directory (default: ${INSTALL_ROOT})
  CONFIG_FILE     Config file path (default: ${CONFIG_FILE})
  LOG_FILE        Log file path (default: ${LOG_FILE})

Examples:
  sudo ./$cmd --install
  sudo ./$cmd --install --cron
  sudo ./$cmd --install --no-start
  sudo ./$cmd --uninstall
EOF
}

log() {
    printf '==> %s\n' "$*"
}

die() {
    printf 'ERROR: %s\n' "$*" >&2
    exit 1
}

need_root() {
    if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
        die "Run this script as root (e.g. sudo $0)"
    fi
}

parse_args() {
    if [[ $# -eq 0 ]]; then
        usage
        exit 0
    fi

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --install)
                DO_INSTALL=1
                shift
                ;;
            --cron)
                RUN_MODE="cron"
                shift
                ;;
            --no-start)
                DO_START=0
                shift
                ;;
            --uninstall)
                DO_UNINSTALL=1
                shift
                ;;
            -h|--help)
                usage
                exit 0
                ;;
            *)
                die "Unknown option: $1 (try --help)"
                ;;
        esac
    done

    if [[ "$DO_INSTALL" -eq 1 && "$DO_UNINSTALL" -eq 1 ]]; then
        die "Choose either --install or --uninstall"
    fi

    if [[ "$DO_UNINSTALL" -eq 1 ]]; then
        if [[ "$RUN_MODE" == "cron" || "$DO_START" -eq 0 ]]; then
            die "--cron and --no-start apply only with --install"
        fi
        return
    fi

    if [[ "$DO_INSTALL" -ne 1 ]]; then
        die "Specify --install or --uninstall (try --help)"
    fi
}

install_apt_deps() {
    local missing=()
    local pkg

    for pkg in "${APT_PACKAGES[@]}"; do
        if ! dpkg -s "$pkg" >/dev/null 2>&1; then
            missing+=("$pkg")
        fi
    done

    if ((${#missing[@]} == 0)); then
        log "System packages already installed"
        return
    fi

    log "Installing system packages: ${missing[*]}"
    apt-get update
    DEBIAN_FRONTEND=noninteractive apt-get install -y "${missing[@]}"
}

install_optional_lgpio_packages() {
    local pkg
    local available=()

    for pkg in python3-lgpio liblgpio1 liblgpio-dev; do
        if apt-cache show "$pkg" >/dev/null 2>&1; then
            available+=("$pkg")
        fi
    done

    if ((${#available[@]} == 0)); then
        log "No apt lgpio packages in this distro (normal on Bookworm)"
        return
    fi

    log "Installing apt lgpio packages: ${available[*]}"
    DEBIAN_FRONTEND=noninteractive apt-get install -y "${available[@]}"
}

liblgpio_present() {
    ldconfig -p 2>/dev/null | grep -q 'liblgpio\.so\.1'
}

install_liblgpio_from_source() {
    local builddir

    if liblgpio_present; then
        log "liblgpio.so.1 already present"
        return
    fi

    log "Building liblgpio from source (https://github.com/joan2937/lg)"
    builddir="$(mktemp -d)"
    (
        cd "$builddir"
        wget -q -O lg.zip https://github.com/joan2937/lg/archive/master.zip
        unzip -q lg.zip
        cd lg-master
        make
        make install
    )
    rm -rf "$builddir"
    ldconfig

    if ! liblgpio_present; then
        die "liblgpio.so.1 is still missing after building joan2937/lg"
    fi
}

remove_legacy_install() {
    if [[ -d "$LEGACY_DIR" ]]; then
        log "Removing legacy install directory ${LEGACY_DIR}"
        rm -rf "$LEGACY_DIR"
    fi

    if [[ -f /etc/init.d/thMonitor ]]; then
        if command -v invoke-rc.d >/dev/null 2>&1; then
            invoke-rc.d thMonitor stop >/dev/null 2>&1 || true
        fi
        if command -v update-rc.d >/dev/null 2>&1; then
            update-rc.d thMonitor remove >/dev/null 2>&1 || true
        fi
        rm -f /etc/init.d/thMonitor
    fi

    find "$INSTALL_ROOT" "$LEGACY_DIR" -name 'dhtreader.so' -delete 2>/dev/null || true
}

install_app_files() {
    local module

    log "Installing application to ${INSTALL_ROOT}"
    install -d -m 755 "$INSTALL_ROOT"

    for module in "${PYTHON_MODULES[@]}"; do
        install -m 644 "${PYTHON_CODE}/${module}" "${INSTALL_ROOT}/${module}"
    done

    install -m 644 "${PYTHON_CODE}/requirements.txt" "${INSTALL_ROOT}/requirements.txt"
    rm -f "${INSTALL_ROOT}/dhtreader.so"
}

create_venv() {
    local venv_python="${INSTALL_ROOT}/venv/bin/python"
    local venv_pip="${INSTALL_ROOT}/venv/bin/pip"
    local pyvenv_cfg="${INSTALL_ROOT}/venv/pyvenv.cfg"

    log "Creating Python virtual environment"
    if [[ ! -x "$venv_python" ]]; then
        python3 -m venv "${INSTALL_ROOT}/venv"
    fi

    # apt python3-lgpio lives in system dist-packages; the venv must see it
    # if pip cannot build Joan's lgpio module.
    if [[ -f "$pyvenv_cfg" ]]; then
        sed -i 's/^include-system-site-packages = .*/include-system-site-packages = true/' "$pyvenv_cfg"
    fi

    # Also expose apt dist-packages via a .pth so lgpio imports even if the
    # venv was originally created without system site packages.
    local pyver
    pyver="$("$venv_python" -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
    local site_packages="${INSTALL_ROOT}/venv/lib/python${pyver}/site-packages"
    if [[ -d "$site_packages" ]]; then
        printf '%s\n' '/usr/lib/python3/dist-packages' >"${site_packages}/system-dist-packages.pth"
    fi

    log "Installing Python dependencies into venv"
    "$venv_pip" install --upgrade pip
    "$venv_pip" install -r "${PYTHON_CODE}/requirements.txt"

    if ! "$venv_python" -c 'import lgpio' >/dev/null 2>&1; then
        log "lgpio not importable yet; retrying pip install"
        "$venv_pip" install lgpio || true
    fi
    if "$venv_python" -c 'import lgpio' >/dev/null 2>&1; then
        log "lgpio is available"
    else
        log "WARNING: lgpio is not importable; DHT reads will fall back to Adafruit bitbang"
    fi
}

install_config() {
    install -d -m 755 "$(dirname "$LOG_FILE")"
    touch "$LOG_FILE"
    chmod 644 "$LOG_FILE"

    if [[ -f "$CONFIG_FILE" ]]; then
        log "Keeping existing config ${CONFIG_FILE}"
        return
    fi

    log "Installing sample config ${CONFIG_FILE}"
    install -m 640 "${PYTHON_CODE}/temphumid.conf" "$CONFIG_FILE"
}

install_bin_wrappers() {
    local venv_python="${INSTALL_ROOT}/venv/bin/python"

    log "Installing command wrappers"
    cat >"$BIN_SINGLE" <<EOF
#!/bin/sh
exec "${venv_python}" "${INSTALL_ROOT}/temp-humid-read-single.py" "\$@"
EOF
    cat >"$BIN_LOOP" <<EOF
#!/bin/sh
exec "${venv_python}" "${INSTALL_ROOT}/temp-humid-read-loop.py" "\$@"
EOF
    cat >"$BIN_SMOKE" <<EOF
#!/bin/sh
exec "${venv_python}" "${INSTALL_ROOT}/smoke-test-sensor.py" "\$@"
EOF
    chmod 755 "$BIN_SINGLE" "$BIN_LOOP" "$BIN_SMOKE"
}

install_systemd_service() {
    local venv_python="${INSTALL_ROOT}/venv/bin/python"

    if [[ ! -f "$SERVICE_TEMPLATE" ]]; then
        die "Missing systemd template: ${SERVICE_TEMPLATE}"
    fi

    log "Installing systemd unit ${SYSTEMD_UNIT}"
    sed \
        -e "s|@INSTALL_ROOT@|${INSTALL_ROOT}|g" \
        -e "s|@VENV_PYTHON@|${venv_python}|g" \
        "$SERVICE_TEMPLATE" >"$SYSTEMD_UNIT"
    chmod 644 "$SYSTEMD_UNIT"

    if command -v systemctl >/dev/null 2>&1; then
        systemctl daemon-reload
    else
        log "systemctl not found; systemd unit installed but not loaded"
    fi
}

install_cron_job() {
    log "Installing cron job ${CRON_FILE}"
    cat >"$CRON_FILE" <<EOF
# rpi-temp-humid-monitor: run a single sensor read every minute
* * * * * root ${BIN_SINGLE} >/dev/null 2>&1
EOF
    chmod 644 "$CRON_FILE"
}

disable_systemd_service() {
    if command -v systemctl >/dev/null 2>&1 && [[ -f "$SYSTEMD_UNIT" ]]; then
        systemctl disable --now thmonitor.service >/dev/null 2>&1 || true
    fi
}

enable_systemd_service() {
    if [[ "$DO_START" -ne 1 ]]; then
        log "Skipping service start (--no-start)"
        return
    fi

    if ! command -v systemctl >/dev/null 2>&1; then
        log "systemctl not available; start the loop manually with ${BIN_LOOP}"
        return
    fi

    log "Enabling and starting thmonitor.service"
    systemctl enable thmonitor.service
    systemctl restart thmonitor.service
    systemctl --no-pager --full status thmonitor.service || true
}

remove_cron_job() {
    rm -f "$CRON_FILE"
}

do_install() {
    need_root
    [[ -d "$PYTHON_CODE" ]] || die "Missing python_code directory: ${PYTHON_CODE}"

    install_apt_deps
    install_optional_lgpio_packages
    install_liblgpio_from_source
    remove_legacy_install
    install_app_files
    create_venv
    install_config
    install_bin_wrappers

    case "$RUN_MODE" in
        systemd)
            remove_cron_job
            install_systemd_service
            enable_systemd_service
            ;;
        cron)
            disable_systemd_service
            install_cron_job
            ;;
        *)
            die "Unknown run mode: ${RUN_MODE}"
            ;;
    esac

    cat <<EOF

Installation complete.

  App directory : ${INSTALL_ROOT}
  Virtual env   : ${INSTALL_ROOT}/venv
  Config file   : ${CONFIG_FILE}
  Log file      : ${LOG_FILE}
  Run once      : ${BIN_SINGLE}
  Run loop      : ${BIN_LOOP}
  Smoke test    : ${BIN_SMOKE}

Next steps:
  1. Edit ${CONFIG_FILE} (GPIO pin, MySQL credentials, limits).
  2. If the DHT data wire is on GPIO 4 (physical pin 7), disable 1-Wire
     (raspi-config → Interface Options → 1-Wire) and reboot.
  3. Ensure the configured table (default: bedRoomTempHumid) exists in your MySQL database.
EOF

    if [[ "$RUN_MODE" == "systemd" ]]; then
        cat <<EOF
  4. Check service status: systemctl status thmonitor
  5. Follow logs: tail -f ${LOG_FILE}
EOF
    else
        cat <<EOF
  4. Cron runs ${BIN_SINGLE} every minute.
  5. Follow logs: tail -f ${LOG_FILE}
EOF
    fi
}

do_uninstall() {
    need_root

    log "Uninstalling thmonitor"
    disable_systemd_service
    remove_cron_job
    rm -f "$SYSTEMD_UNIT" "$BIN_SINGLE" "$BIN_LOOP" "$BIN_SMOKE"
    rm -rf "$INSTALL_ROOT"
    remove_legacy_install

    if command -v systemctl >/dev/null 2>&1; then
        systemctl daemon-reload
    fi

    cat <<EOF

Uninstall complete.

Removed:
  ${INSTALL_ROOT}
  ${SYSTEMD_UNIT}
  ${BIN_SINGLE}
  ${BIN_LOOP}
  ${BIN_SMOKE}
  ${CRON_FILE}

Kept (not removed):
  ${CONFIG_FILE}
  ${LOG_FILE}

EOF
}

parse_args "$@"

if [[ "$DO_UNINSTALL" -eq 1 ]]; then
    do_uninstall
elif [[ "$DO_INSTALL" -eq 1 ]]; then
    do_install
else
    usage
    exit 0
fi
