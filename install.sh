#!/usr/bin/env bash
# install.sh - install desktop_preset and its Omarchy menu entry
set -uo pipefail

SRC_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
BIN_DIR="${HOME}/.local/bin"
MENU_FILE="${HOME}/.config/omarchy/extensions/omarchy-menu.jsonc"
PRESET_DIR="${HOME}/.config/desktop_preset"
AUTOSTART_FILE="${HOME}/.config/hypr/autostart.lua"

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
for f in desktop_preset desktop-preset-layout desktop-preset-autostart \
         desktop-preset-menu-load desktop-preset-menu-save desktop-preset-menu-clear \
         desktop-preset-menu-autostart-enable desktop-preset-menu-autostart-disable desktop-preset-menu-autostart-list; do
  cp "$SRC_DIR/bin/$f" "$BIN_DIR/$f"
  chmod +x "$BIN_DIR/$f"
done

case ":$PATH:" in
  *":$BIN_DIR:"*) ;;
  *) warn "$BIN_DIR isn't on your PATH — add it in ~/.bashrc (or your shell's rc file)" ;;
esac

info "creating $PRESET_DIR"
mkdir -p "$PRESET_DIR"

info "adding the Preset menu entries"
mkdir -p "$(dirname "$MENU_FILE")"
[[ -f $MENU_FILE ]] || printf '{\n}\n' > "$MENU_FILE"

# Insert only entries missing from $MENU_FILE, one at a time, just before its
# final closing brace — matching how the shipped extensions file is meant to
# be extended by hand. Checking per-entry (not just "any preset entry
# exists") means a re-run after an update picks up newly added entries
# (e.g. Autostart) instead of treating any prior install as fully current.
added=0
while IFS= read -r snippet_line; do
  [[ $snippet_line =~ ^[[:space:]]*\"(trigger\.[A-Za-z0-9_.]+)\" ]] || continue
  key=${BASH_REMATCH[1]}
  grep -q "\"$key\"" "$MENU_FILE" 2>/dev/null && continue
  tmp=$(mktemp)
  awk -v line="$snippet_line" '
    /^}[[:space:]]*$/ && !done { print line; done = 1 }
    { print }
  ' "$MENU_FILE" > "$tmp" && mv "$tmp" "$MENU_FILE"
  added=1
done < "$SRC_DIR/menu-snippet.jsonc"

if (( added )); then
  info "menu entries added to $MENU_FILE"
else
  info "menu entries already present — leaving $MENU_FILE untouched"
fi

if command -v omarchy >/dev/null 2>&1; then
  omarchy menu refresh >/dev/null 2>&1 && info "menu refreshed" || warn "couldn't refresh the menu automatically — open it once to pick up the change"
fi

info "wiring up login autostart"
if [[ -f $AUTOSTART_FILE ]]; then
  if grep -q 'desktop-preset-autostart' "$AUTOSTART_FILE" 2>/dev/null; then
    info "autostart already wired up — leaving $AUTOSTART_FILE untouched"
  else
    printf '\no.launch_on_start("desktop-preset-autostart")\n' >> "$AUTOSTART_FILE"
    info "added to $AUTOSTART_FILE (runs desktop_preset autostart run at login)"
  fi
else
  warn "$AUTOSTART_FILE not found — add \`exec-once = desktop-preset-autostart\` to your hyprland.conf (or the Lua equivalent, o.launch_on_start(\"desktop-preset-autostart\")) yourself to enable login autostart"
fi
info "configure per-workspace autostart with: desktop_preset autostart set <name> -w <N>"
info "or from the desktop: Menu -> Trigger -> Preset -> Autostart"

printf '\n'
info "done — try: desktop_preset --help"
info "or from the desktop: Menu -> Trigger -> Preset"
