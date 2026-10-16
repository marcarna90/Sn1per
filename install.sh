#!/bin/bash
# + -- --=[ Sn1per + Jarvis installer
# + -- --=[ Deploys the framework to /usr/share/sniper and registers the
# + -- --=[ 'sniper' and 'jarvis' commands. Run as root on Kali/Parrot/Debian.
#
# This installer deploys THIS repository (the Sn1per engine scripts + the
# Jarvis reporting/orchestration layer) and installs the core OS packages it
# relies on. The heavier third-party scanners that some Sn1per modes call
# (nuclei, subfinder, httpx, metasploit, ...) are NOT fully provisioned here;
# Kali ships many of them, and a best-effort step below installs the Go-based
# ones when 'go' is available. Jarvis itself needs nothing beyond python3.
#
# Test hatch (no root, no system changes): run with
#   SNIPER_INSTALL_TEST=1 SNIPER_INSTALL_DIR=/tmp/s BIN_DIR=/tmp/s/bin ./install.sh --no-deps

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

# --- paths (overridable for testing) --------------------------------------
INSTALL_DIR="${SNIPER_INSTALL_DIR:-/usr/share/sniper}"
BIN_DIR="${BIN_DIR:-/usr/bin}"
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# --- root check (skipped only in the documented test hatch) ---------------
if [[ "${SNIPER_INSTALL_TEST:-0}" != "1" && $EUID -ne 0 ]]; then
  err "This installer must be run as root (or use the documented test hatch)."
  exit 1
fi

# --- 1. core OS dependencies ---------------------------------------------
CORE_PKGS=(nmap git curl wget jq dos2unix python3 python3-pip whois dnsutils)
if [[ "$INSTALL_DEPS" == "1" ]]; then
  if command -v apt >/dev/null 2>&1; then
    info "Installing core dependencies via apt..."
    apt-get -yqq update || warn "apt update failed; continuing"
    for pkg in "${CORE_PKGS[@]}"; do
      if apt-get -yqq install "$pkg" >/dev/null 2>&1; then
        good "installed $pkg"
      else
        warn "could not install $pkg (install it manually if a module needs it)"
      fi
    done
  else
    warn "apt not found. Install these manually for full functionality:"
    warn "  ${CORE_PKGS[*]}"
  fi
else
  info "Skipping OS package installation (--no-deps)."
fi

# --- 2. deploy framework files to INSTALL_DIR -----------------------------
if [[ "$SRC_DIR" == "$INSTALL_DIR" ]]; then
  info "Source already at $INSTALL_DIR; skipping copy."
else
  info "Deploying framework to $INSTALL_DIR ..."
  mkdir -p "$INSTALL_DIR"
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
mkdir -p "$BIN_DIR"
ln -sf "$INSTALL_DIR/sniper" "$BIN_DIR/sniper"
ln -sf "$INSTALL_DIR/jarvis-cli" "$BIN_DIR/jarvis"
good "registered commands: $BIN_DIR/sniper and $BIN_DIR/jarvis"

# --- 4. default user config -----------------------------------------------
if [[ "${SNIPER_INSTALL_TEST:-0}" != "1" ]]; then
  if [[ ! -f /root/.sniper.conf && -f "$INSTALL_DIR/sniper.conf" ]]; then
    cp "$INSTALL_DIR/sniper.conf" /root/.sniper.conf 2>/dev/null \
      && good "created /root/.sniper.conf from template"
  fi
fi

# --- 5. optional: Go-based scanners (best-effort) -------------------------
if [[ "$INSTALL_DEPS" == "1" ]] && command -v go >/dev/null 2>&1; then
  info "Go detected; attempting optional scanners (best-effort)..."
  GO_TOOLS=(
    "github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest"
    "github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest"
    "github.com/projectdiscovery/httpx/cmd/httpx@latest"
  )
  for mod in "${GO_TOOLS[@]}"; do
    name="${mod%%@*}"; name="${name##*/}"
    if go install "$mod" >/dev/null 2>&1; then
      good "go install $name"
    else
      warn "optional: failed to install $name (skip)"
    fi
  done
else
  [[ "$INSTALL_DEPS" == "1" ]] && info "Go not found; skipping optional Go scanners."
fi

# --- 6. sanity checks -----------------------------------------------------
echo ""
if command -v python3 >/dev/null 2>&1; then
  good "python3: $(python3 --version 2>&1)"
else
  err "python3 not found — Jarvis reporting will not run until it is installed."
fi

# --- 7. next steps --------------------------------------------------------
echo ""
good "Installation complete."
echo ""
info  "Jarvis (reporting/orchestration — no extra deps):"
echo  "    jarvis report -w $INSTALL_DIR/loot/workspace/<WORKSPACE>"
echo  "    jarvis run <campaign.json> --dry-run"
echo ""
info  "Sn1per engine:"
echo  "    sniper -t <TARGET>"
echo ""
warn  "For the complete third-party toolchain (metasploit, nuclei, etc.),"
warn  "Kali Linux ships most tools; see jarvis/README.md and the wiki."
warn  "Only test targets you are explicitly authorised to assess."
