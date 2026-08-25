#!/usr/bin/env bash
# uninstall.sh - remove desktop_preset's scripts, Omarchy menu entries, and
# login autostart wiring. The reverse of install.sh.
set -uo pipefail

BIN_DIR="${HOME}/.local/bin"
MENU_FILE="${HOME}/.config/omarchy/extensions/omarchy-menu.jsonc"
PRESET_DIR="${HOME}/.config/desktop_preset"
AUTOSTART_FILE="${HOME}/.config/hypr/autostart.lua"

die()  { printf '\033[31merror:\033[0m %s\n' "$*" >&2; exit 1; }
warn() { printf '\033[33mwarn:\033[0m %s\n' "$*" >&2; }
info() { printf '\033[36m::\033[0m %s\n' "$*"; }

PURGE=0
for a in "$@"; do
  case $a in
    --purge) PURGE=1 ;;
    -h|--help)
      cat <<USAGE
usage: ./uninstall.sh [--purge]

Removes desktop_preset's scripts from $BIN_DIR, its Preset menu entries
from $MENU_FILE, and its login autostart wiring from $AUTOSTART_FILE.

  --purge   also delete $PRESET_DIR (your saved presets and autostart
            config) -- left in place by default so a reinstall doesn't
            lose them
USAGE
      exit 0 ;;
    *) die "unknown option: $a (try --help)" ;;
  esac
done

info "removing scripts from $BIN_DIR"
for f in desktop_preset desktop-preset-layout desktop-preset-autostart \
         desktop-preset-menu-load desktop-preset-menu-save desktop-preset-menu-clear \
         desktop-preset-menu-autostart-enable desktop-preset-menu-autostart-disable desktop-preset-menu-autostart-list; do
  if [[ -e "$BIN_DIR/$f" ]]; then
    rm -f "$BIN_DIR/$f"
    info "removed $BIN_DIR/$f"
  fi
done

info "removing Preset menu entries"
if [[ -f $MENU_FILE ]]; then
  tmp=$(mktemp)
  removed=0
  while IFS= read -r line; do
    if [[ $line =~ \"(trigger\.preset[A-Za-z0-9_.]*)\" ]] \
       || [[ $line == *"Desktop Preset:"* ]] \
       || [[ $line == *"omarchy-menu-select"* ]] \
       || [[ $line == *"notification, since these run with no terminal"* ]]; then
      removed=1
      continue
    fi
    printf '%s\n' "$line" >> "$tmp"
  done < "$MENU_FILE"
  if (( removed )); then
    mv "$tmp" "$MENU_FILE"
    info "menu entries removed from $MENU_FILE"
    command -v omarchy >/dev/null 2>&1 && omarchy menu refresh >/dev/null 2>&1 && info "menu refreshed"
  else
    rm -f "$tmp"
    info "no Preset menu entries found in $MENU_FILE"
  fi
else
  info "$MENU_FILE not found — nothing to remove"
fi

info "removing login autostart wiring"
if [[ -f $AUTOSTART_FILE ]] && grep -q 'desktop-preset-autostart' "$AUTOSTART_FILE" 2>/dev/null; then
  tmp=$(mktemp)
  grep -v 'desktop-preset-autostart' "$AUTOSTART_FILE" > "$tmp"
  mv "$tmp" "$AUTOSTART_FILE"
  info "removed from $AUTOSTART_FILE"
else
  info "no autostart wiring found in $AUTOSTART_FILE"
fi

if (( PURGE )); then
  if [[ -d $PRESET_DIR ]]; then
    rm -rf "$PRESET_DIR"
    info "removed $PRESET_DIR (your saved presets and autostart config)"
  fi
else
  [[ -d $PRESET_DIR ]] && info "leaving $PRESET_DIR in place (your saved presets) — remove manually or re-run with --purge"
fi

printf '\n'
info "done"
