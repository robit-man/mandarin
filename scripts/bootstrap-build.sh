#!/bin/sh
set -eu
# Build-time preparation only. End users receive these tools inside the package.
packages=$(python3 -c 'import json; print(" ".join(json.load(open("packaging/runtime-packages.json"))["packages"]))')
sudo apt-get update
sudo apt-get install -y --no-install-recommends build-essential libseccomp-dev libreofficekit-dev libglib2.0-bin xvfb xauth xdotool dbus-x11 $packages
make all
