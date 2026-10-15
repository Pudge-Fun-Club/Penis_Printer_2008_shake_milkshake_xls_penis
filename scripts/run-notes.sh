#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

# Local single-user controller: never expose the auth bypass on a LAN socket.
export PLOTTER_HOST=127.0.0.1
export PLOTTER_PORT="${PLOTTER_PORT:-8010}"
export PLOTTER_DATA_DIR="${PLOTTER_DATA_DIR:-$PWD/data}"
export STATE_STORE=file
export PLOTTER_AUTH_DEV_BYPASS=true
export PRINTER_SERIAL_ENABLED=true
export PRINTER_DEFAULT_BACKEND=serial
export PRINTER_SERIAL_PORT="${PRINTER_SERIAL_PORT:-/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0}"
export PRINTER_SERIAL_BAUD="${PRINTER_SERIAL_BAUD:-115200}"

if [[ ! -x .venv/bin/python ]]; then
  uv sync --frozen
fi
if [[ ! -f plotter/web/static/index.html ]]; then
  (cd frontend && npm ci --no-audit --no-fund && npm run build)
fi

uv run python - <<'PY'
from plotter.core.calibration import Calibration
from plotter.services.settings_store import load_saved, patch_saved

saved = load_saved()
if "printer.serial_enabled" not in saved:
    patch_saved({
        "printer.serial_enabled": True,
        "printer.serial_port": "/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0",
        "printer.serial_baud": 115200,
        "printer.default_backend": "serial",
    })
if not Calibration.path().exists():
    Calibration(
        bed_width=220, bed_height=220, z_max=250,
        plot_width=190, plot_height=190, origin_x=10, origin_y=10,
        pen_down_z=17, pen_up_z=20, pen_calibrated=False,
        draw_feed=1200, travel_feed=2400, z_feed=300,
        merge_tolerance=.05, park_after_plot=False,
    ).save()
PY
printf 'Конспекты: http://127.0.0.1:%s\n' "$PLOTTER_PORT"
exec uv run gcodescribe-web
