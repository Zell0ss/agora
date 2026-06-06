#!/bin/bash
# Wrapper para que systemd encuentre npm aunque node esté bajo nvm
export NVM_DIR="/home/ubuntu/.nvm"
# shellcheck disable=SC1091
[ -s "$NVM_DIR/nvm.sh" ] && source "$NVM_DIR/nvm.sh"
exec npm run dev
