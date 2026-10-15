#!/usr/bin/env bash
# Grant persistent access to this Ender-3 Neo's CH340 USB interface.
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  printf 'Запусти: sudo %q\n' "$0" >&2
  exit 1
fi
printer_user="${1:-${SUDO_USER:-}}"
if [[ ! "$printer_user" =~ ^[a-z_][a-z0-9_-]*\$?$ ]] || [[ "$printer_user" == root ]]; then
  printf 'Укажи обычного пользователя: sudo %q azod\n' "$0" >&2
  exit 1
fi
id "$printer_user" >/dev/null
command -v udevadm >/dev/null

install -d -m 0755 /etc/udev/rules.d
printer_rule_temp=$(mktemp /etc/udev/rules.d/.gcodescribe-printer.XXXXXX)
trap 'rm -f "$printer_rule_temp"' EXIT
printf '%s\n' \
  '# GCodeScribe: persistent Ender-3 Neo USB access, independent of ttyUSB number.' \
  "SUBSYSTEM==\"tty\", ATTRS{idVendor}==\"1a86\", ATTRS{idProduct}==\"7523\", ENV{ID_SERIAL}==\"1a86_USB_Serial\", ENV{ID_USB_INTERFACE_NUM}==\"00\", OWNER=\"$printer_user\", MODE=\"0660\"" \
  > "$printer_rule_temp"
install -m 0644 "$printer_rule_temp" /etc/udev/rules.d/99-gcodescribe-printer.rules
udevadm control --reload-rules
udevadm trigger --action=change --subsystem-match=tty \
  --property-match=ID_SERIAL=1a86_USB_Serial \
  --property-match=ID_USB_INTERFACE_NUM=00 --settle
printf 'Постоянный доступ для %s установлен. Приложение подключится автоматически.\n' "$printer_user"
