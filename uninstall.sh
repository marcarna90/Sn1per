#!/bin/bash
# Uninstall script for Sn1per + Jarvis (Linux + macOS)
# Created by @xer0dayz - https://sn1persecurity.com

# VARS
OKBLUE='\033[94m'
OKRED='\033[91m'
OKGREEN='\033[92m'
OKORANGE='\033[93m'
RESET='\e[0m'

echo -e "$OKRED                ____               $RESET"
echo -e "$OKRED    _________  /  _/___  ___  _____$RESET"
echo -e "$OKRED   / ___/ __ \ / // __ \/ _ \/ ___/$RESET"
echo -e "$OKRED  (__  ) / / // // /_/ /  __/ /    $RESET"
echo -e "$OKRED /____/_/ /_/___/ .___/\___/_/     $RESET"
echo -e "$OKRED               /_/                 $RESET"
echo -e "$RESET"
echo -e "$OKORANGE + -- --=[https://sn1persecurity.com$RESET"
echo ""

# Cover both the Linux (/usr/share, /usr/bin) and macOS (/usr/local) layouts.
INSTALL_DIRS=("/usr/share/sniper" "/usr/local/share/sniper")
BIN_DIRS=("/usr/bin" "/usr/local/bin" "/opt/homebrew/bin" "$HOME/.local/bin")

echo -e "$OKRED[>]$RESET This will remove sniper/jarvis and ALL files under:$RESET"
for d in "${INSTALL_DIRS[@]}"; do echo "    $d"; done
echo -e "$OKRED[>]$RESET Hit Enter to continue, or Ctrl+C to abort.$RESET"
read -r answer

for d in "${INSTALL_DIRS[@]}"; do
  [[ -e "$d" ]] && rm -Rf "$d" && echo -e "$OKBLUE[*]$RESET removed $d"
done
for b in "${BIN_DIRS[@]}"; do
  for cmd in sniper jarvis; do
    if [[ -L "$b/$cmd" || -e "$b/$cmd" ]]; then
      rm -f "$b/$cmd" && echo -e "$OKBLUE[*]$RESET removed $b/$cmd"
    fi
  done
done

echo -e "$OKBLUE[*]$RESET Done!$RESET"
