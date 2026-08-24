#!/usr/bin/env bash
# install.sh - install desktop_preset and its Omarchy menu entry
set -uo pipefail

SRC_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
BIN_DIR="${HOME}/.local/bin"
MENU_FILE="${HOME}/.config/omarchy/extensions/omarchy-menu.jsonc"
PRESET_DIR="${HOME}/.config/desktop_preset"

die()  { printf '\033[31merror:\033[0m %s\n' "$*" >&2; exit 1; }
warn() { printf '\033[33mwarn:\033[0m %s\n' "$*" >&2; }
info() { printf '\033[36m::\033[0m %s\n' "$*"; }

info "checking dependencies"
missing=0
for c in hyprctl jq python3; do
  command -v "$c" >/dev/null 2>&1 || { warn "missing: $c"; missing=1; }
done
command -v omarchy >/dev/null 2>&1 || warn "the 'omarchy' CLI wasn't found — this is built for Omarchy on Hyprland"
(( missing )) && die "install the missing dependencies above, then re-run this script"

if command -v omarchy >/dev/null 2>&1; then
  ov=$(omarchy version 2>/dev/null || echo "unknown")
  info "Omarchy $ov detected (built and tested against 4.0.0)"
fi
if command -v hyprctl >/dev/null 2>&1; then
  hv=$(hyprctl version 2>/dev/null | head -1 || echo "unknown")
  info "$hv"
fi

info "installing scripts to $BIN_DIR"
mkdir -p "$BIN_DIR"
for f in desktop_preset desktop-preset-layout desktop-preset-menu-load desktop-preset-menu-save desktop-preset-menu-clear; do
  cp "$SRC_DIR/bin/$f" "$BIN_DIR/$f"
  chmod +x "$BIN_DIR/$f"
done

case ":$PATH:" in
  *":$BIN_DIR:"*) ;;
  *) warn "$BIN_DIR isn't on your PATH — add it in ~/.bashrc (or your shell's rc file)" ;;
esac

info "creating $PRESET_DIR"
mkdir -p "$PRESET_DIR"

info "adding the Preset menu entry"
mkdir -p "$(dirname "$MENU_FILE")"
[[ -f $MENU_FILE ]] || printf '{\n}\n' > "$MENU_FILE"

if grep -q '"trigger.preset"' "$MENU_FILE" 2>/dev/null; then
  info "menu entry already present — leaving $MENU_FILE untouched"
else
  # Insert just before the file's final closing brace, matching how the
  # shipped extensions file is meant to be extended by hand.
  tmp=$(mktemp)
  awk -v snippet="$SRC_DIR/menu-snippet.jsonc" '
    /^}[[:space:]]*$/ && !done {
      while ((getline line < snippet) > 0) print line
      done = 1
    }
    { print }
  ' "$MENU_FILE" > "$tmp" && mv "$tmp" "$MENU_FILE"
  info "menu entry added to $MENU_FILE"
fi

if command -v omarchy >/dev/null 2>&1; then
  omarchy menu refresh >/dev/null 2>&1 && info "menu refreshed" || warn "couldn't refresh the menu automatically — open it once to pick up the change"
fi

printf '\n'
info "done — try: desktop_preset --help"
info "or from the desktop: Menu -> Trigger -> Preset"
