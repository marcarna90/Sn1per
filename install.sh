#!/bin/bash
# + -- --=[ Sn1per + Jarvis installer (Linux + macOS)
# + -- --=[ Deploys the framework and registers the 'sniper' and 'jarvis'
# + -- --=[ commands. Linux: run as root (apt). macOS: Homebrew, no root needed.
#
# This installer deploys THIS repository (the Sn1per engine scripts + the
# Jarvis reporting/orchestration/ASM layer) and installs the core OS packages
# it relies on. Jarvis itself needs nothing beyond python3.
#
# Platform notes:
#   * Linux  -> /usr/share/sniper + /usr/bin, dependencies via apt (root).
#   * macOS  -> /usr/local/... (SIP forbids writing /usr/bin, /usr/share),
#               dependencies via Homebrew run as the normal user (brew refuses
#               root). The bash scanning engine is Linux-oriented; on macOS the
#               Jarvis layer (report/asm/export) is the fully supported part,
#               and Docker is recommended for the full scanning engine.
#
# Test hatch (no root, no system changes):
#   SNIPER_INSTALL_TEST=1 SNIPER_INSTALL_DIR=/tmp/s BIN_DIR=/tmp/s/bin ./install.sh --no-deps
#   (SNIPER_PLATFORM=macos|linux forces the platform branch for testing.)

set -u

# --- colours --------------------------------------------------------------
OKBLUE='\033[94m'; OKRED='\033[91m'; OKGREEN='\033[92m'; OKORANGE='\033[93m'; RESET='\e[0m'

info()  { echo -e "$OKBLUE[*]$RESET $*"; }
good()  { echo -e "$OKGREEN[+]$RESET $*"; }
warn()  { echo -e "$OKORANGE[!]$RESET $*"; }
err()   { echo -e "$OKRED[x]$RESET $*" >&2; }

logo() {
  echo -e "$OKRED                ____               $RESET"
  echo -e "$OKRED    _________  /  _/___  ___  _____$RESET"
  echo -e "$OKRED   / ___/ __ \\ / // __ \\/ _ \\/ ___/$RESET"
  echo -e "$OKRED  (__  ) / / // // /_/ /  __/ /    $RESET"
  echo -e "$OKRED /____/_/ /_/___/ .___/\\___/_/     $RESET"
  echo -e "$OKRED               /_/   + Jarvis      $RESET"
  echo -e "$OKORANGE + -- --=[ Sn1per + Jarvis installer$RESET"
  echo ""
}

# --- options --------------------------------------------------------------
INSTALL_DEPS=1
for arg in "$@"; do
  case "$arg" in
    --no-deps) INSTALL_DEPS=0 ;;
    -h|--help)
      logo
      echo "Usage: ./install.sh [--no-deps]"
      echo "  --no-deps   Skip OS package installation (deploy files + commands only)"
      exit 0 ;;
    *) warn "Unknown option: $arg (ignored)" ;;
  esac
done

logo

# --- platform detection ---------------------------------------------------
PLATFORM="${SNIPER_PLATFORM:-}"
if [[ -z "$PLATFORM" ]]; then
  case "$(uname -s)" in
    Darwin) PLATFORM="macos" ;;
    Linux)  PLATFORM="linux" ;;
    *)      PLATFORM="other" ;;
  esac
fi
info "Platform: $PLATFORM"

# The user who invoked us (used to run brew without root on macOS).
RUN_USER="${SUDO_USER:-$(id -un 2>/dev/null || echo "$USER")}"

first_writable_dir() {
  # Echo the first candidate whose parent is writable (dir may not exist yet).
  for d in "$@"; do
    parent="$(dirname "$d")"
    if [[ -w "$d" ]] 2>/dev/null || { [[ -d "$parent" ]] && [[ -w "$parent" ]]; }; then
      echo "$d"; return 0
    fi
  done
  echo "$1"  # fall back to the first candidate
}

# --- paths (overridable via env) -----------------------------------------
if [[ "$PLATFORM" == "macos" ]]; then
  DEFAULT_INSTALL_DIR="/usr/local/share/sniper"
  DEFAULT_BIN_DIR="$(first_writable_dir /usr/local/bin /opt/homebrew/bin "$HOME/.local/bin")"
else
  DEFAULT_INSTALL_DIR="/usr/share/sniper"
  DEFAULT_BIN_DIR="/usr/bin"
fi
INSTALL_DIR="${SNIPER_INSTALL_DIR:-$DEFAULT_INSTALL_DIR}"
BIN_DIR="${BIN_DIR:-$DEFAULT_BIN_DIR}"
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# --- privilege check ------------------------------------------------------
# Linux needs root (apt + /usr/bin). macOS does not: brew refuses root and we
# target /usr/local, which sudo-free setups commonly own. We only warn if the
# chosen directories are not writable.
if [[ "${SNIPER_INSTALL_TEST:-0}" != "1" ]]; then
  if [[ "$PLATFORM" == "linux" && $EUID -ne 0 ]]; then
    err "On Linux this installer must be run as root:  sudo bash install.sh"
    exit 1
  fi
  if [[ "$PLATFORM" == "macos" && $EUID -eq 0 ]]; then
    warn "Running as root on macOS: Homebrew will be invoked as '$RUN_USER'."
  fi
fi

# --- 1. core OS dependencies ---------------------------------------------
install_deps_linux() {
  local pkgs=(nmap git curl wget jq dos2unix python3 python3-pip whois dnsutils)
  if ! command -v apt >/dev/null 2>&1; then
    warn "apt not found. Install these manually: ${pkgs[*]}"; return
  fi
  info "Installing core dependencies via apt..."
  apt-get -yqq update || warn "apt update failed; continuing"
  for pkg in "${pkgs[@]}"; do
    if apt-get -yqq install "$pkg" >/dev/null 2>&1; then good "installed $pkg"
    else warn "could not install $pkg (install it manually if a module needs it)"; fi
  done
}

brew_do() {  # run brew as the non-root user (brew refuses to run as root)
  if [[ $EUID -eq 0 ]]; then sudo -u "$RUN_USER" brew "$@"; else brew "$@"; fi
}

install_deps_macos() {
  # curl, whois and dig ship with macOS; install the rest via Homebrew.
  local pkgs=(nmap git wget jq dos2unix python3)
  if ! command -v brew >/dev/null 2>&1; then
    warn "Homebrew not found. Install it from https://brew.sh then re-run,"
    warn "or install these manually: ${pkgs[*]}"
    return
  fi
  info "Installing core dependencies via Homebrew (as $RUN_USER)..."
  for pkg in "${pkgs[@]}"; do
    if brew_do list "$pkg" >/dev/null 2>&1; then good "$pkg already present"
    elif brew_do install "$pkg" >/dev/null 2>&1; then good "installed $pkg"
    else warn "could not install $pkg (install it manually if a module needs it)"; fi
  done
}

if [[ "$INSTALL_DEPS" == "1" ]]; then
  case "$PLATFORM" in
    linux) install_deps_linux ;;
    macos) install_deps_macos ;;
    *)     warn "Unknown platform; skipping dependency install." ;;
  esac
else
  info "Skipping OS package installation (--no-deps)."
fi

# --- 2. deploy framework files to INSTALL_DIR -----------------------------
if [[ "$SRC_DIR" == "$INSTALL_DIR" ]]; then
  info "Source already at $INSTALL_DIR; skipping copy."
else
  info "Deploying framework to $INSTALL_DIR ..."
  mkdir -p "$INSTALL_DIR" || { err "Cannot create $INSTALL_DIR (try sudo, or set SNIPER_INSTALL_DIR)"; exit 1; }
  if command -v rsync >/dev/null 2>&1; then
    rsync -a --delete --exclude '.git' "$SRC_DIR"/ "$INSTALL_DIR"/
  else
    cp -a "$SRC_DIR"/. "$INSTALL_DIR"/
    rm -rf "$INSTALL_DIR/.git"
  fi
  good "files deployed"
fi

# --- 3. permissions + command symlinks ------------------------------------
chmod +x "$INSTALL_DIR/sniper" "$INSTALL_DIR/jarvis-cli" "$INSTALL_DIR/uninstall.sh" 2>/dev/null
mkdir -p "$BIN_DIR" 2>/dev/null
if ln -sf "$INSTALL_DIR/jarvis-cli" "$BIN_DIR/jarvis" 2>/dev/null; then
  good "registered command: $BIN_DIR/jarvis"
else
  warn "could not create $BIN_DIR/jarvis — run '$INSTALL_DIR/jarvis-cli' directly"
fi
# The scanning engine is Linux-oriented; only register 'sniper' on Linux.
if [[ "$PLATFORM" == "linux" ]]; then
  ln -sf "$INSTALL_DIR/sniper" "$BIN_DIR/sniper" && good "registered command: $BIN_DIR/sniper"
else
  info "macOS: 'sniper' engine is Linux-oriented; not registering it (use Docker for scanning)."
fi
case ":$PATH:" in
  *":$BIN_DIR:"*) : ;;
  *) warn "$BIN_DIR is not on your PATH. Add it, e.g.:  export PATH=\"$BIN_DIR:\$PATH\"" ;;
esac

# --- 4. default user config -----------------------------------------------
if [[ "${SNIPER_INSTALL_TEST:-0}" != "1" ]]; then
  CONF_HOME="$(eval echo "~$RUN_USER" 2>/dev/null || echo "$HOME")"
  if [[ -n "$CONF_HOME" && ! -f "$CONF_HOME/.sniper.conf" && -f "$INSTALL_DIR/sniper.conf" ]]; then
    cp "$INSTALL_DIR/sniper.conf" "$CONF_HOME/.sniper.conf" 2>/dev/null \
      && good "created $CONF_HOME/.sniper.conf from template"
  fi
fi

# --- 5. optional: Go-based scanners (best-effort, Linux) ------------------
if [[ "$INSTALL_DEPS" == "1" && "$PLATFORM" == "linux" ]] && command -v go >/dev/null 2>&1; then
  info "Go detected; attempting optional scanners (best-effort)..."
  GO_TOOLS=(
    "github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest"
    "github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest"
    "github.com/projectdiscovery/httpx/cmd/httpx@latest"
  )
  for mod in "${GO_TOOLS[@]}"; do
    name="${mod%%@*}"; name="${name##*/}"
    if go install "$mod" >/dev/null 2>&1; then good "go install $name"
    else warn "optional: failed to install $name (skip)"; fi
  done
fi

# --- 6. sanity checks -----------------------------------------------------
echo ""
if command -v python3 >/dev/null 2>&1; then
  good "python3: $(python3 --version 2>&1)"
else
  err "python3 not found — Jarvis will not run until it is installed."
fi

# --- 7. next steps --------------------------------------------------------
echo ""
good "Installation complete."
echo ""
info  "Jarvis (reporting / ASM / export — no extra deps):"
echo  "    jarvis report -w $INSTALL_DIR/loot/workspace/<WORKSPACE>"
echo  "    jarvis asm    -w $INSTALL_DIR/loot/workspace/<WORKSPACE> --client \"<CLIENT>\""
echo  "    jarvis export -w $INSTALL_DIR/loot/workspace/<WORKSPACE> --serve"
if [[ "$PLATFORM" == "linux" ]]; then
  echo ""
  info  "Sn1per engine:"
  echo  "    sniper -t <TARGET>"
  echo ""
  warn  "For the complete third-party toolchain (metasploit, nuclei, ...), Kali ships most tools."
else
  echo ""
  warn  "macOS: the bash scanning engine is Linux-oriented and is NOT registered here."
  warn  "Run the full engine via Docker (see README), or use Jarvis on loot copied from a scan box."
fi
warn  "Only test targets you are explicitly authorised to assess."
