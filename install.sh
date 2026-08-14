#!/bin/bash
#
# Install rpi-temp-humid-monitor as a system app with a Python venv.
#
# Usage:
#   sudo ./install.sh              # systemd loop daemon (default)
#   sudo ./install.sh --cron       # cron single-shot mode instead
#   sudo ./install.sh --no-start   # install only, do not enable/start
#   sudo ./install.sh --uninstall  # remove installed app files
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
SYSTEMD_UNIT="${SYSTEMD_UNIT:-/etc/systemd/system/thmonitor.service}"
CRON_FILE="${CRON_FILE:-/etc/cron.d/thmonitor}"
LEGACY_DIR="/usr/local/bin/thMonitor"

RUN_MODE="systemd"
DO_START=1
DO_UNINSTALL=0

APT_PACKAGES=(
    python3
    python3-venv
    python3-dev
    python3-pip
    default-libmysqlclient-dev
    build-essential
)

PYTHON_MODULES=(
    dhtreader.py
    readMysql.py
    temp-humid-read-loop.py
    temp-humid-read-single.py
    thmonitor_common.py
    updateMysql.py
)

usage() {
    sed -n '3,10p' "$0" | sed 's/^# \?//'
    echo
    echo "Environment overrides:"
    echo "  INSTALL_ROOT   Install directory (default: ${INSTALL_ROOT})"
    echo "  CONFIG_FILE    Config file path (default: ${CONFIG_FILE})"
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
    while [[ $# -gt 0 ]]; do
        case "$1" in
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

    log "Creating Python virtual environment"
    if [[ ! -x "$venv_python" ]]; then
        python3 -m venv "${INSTALL_ROOT}/venv"
    fi

    log "Installing Python dependencies into venv"
    "$venv_pip" install --upgrade pip
    "$venv_pip" install -r "${PYTHON_CODE}/requirements.txt"
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
    chmod 755 "$BIN_SINGLE" "$BIN_LOOP"
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

Next steps:
  1. Edit ${CONFIG_FILE} (GPIO pin, MySQL credentials, limits).
  2. Ensure the TempHumid table exists in your MySQL database.
EOF

    if [[ "$RUN_MODE" == "systemd" ]]; then
        cat <<EOF
  3. Check service status: systemctl status thmonitor
  4. Follow logs: tail -f ${LOG_FILE}
EOF
    else
        cat <<EOF
  3. Cron runs ${BIN_SINGLE} every minute.
  4. Follow logs: tail -f ${LOG_FILE}
EOF
    fi
}

do_uninstall() {
    need_root

    log "Uninstalling thmonitor"
    disable_systemd_service
    remove_cron_job
    rm -f "$SYSTEMD_UNIT" "$BIN_SINGLE" "$BIN_LOOP"
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
  ${CRON_FILE}

Kept (not removed):
  ${CONFIG_FILE}
  ${LOG_FILE}

EOF
}

parse_args "$@"

if [[ "$DO_UNINSTALL" -eq 1 ]]; then
    do_uninstall
else
    do_install
fi
