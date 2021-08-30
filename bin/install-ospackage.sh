#!/usr/bin/env bash

PACKAGE="${1}"
DISTRO="$(awk '/^ID=/' /etc/*-release | awk -F'=' '{ print tolower($2) }')"

if [ "${DISTRO}" == "nixos" ]; then
  nix-env -iA "nixos.${PACKAGE}"
elif [ "${DISTRO}" == "debian" ]; then
  sudo apt-get update && \
    sudo apt-get install -y "${PACKAGE}"
elif [ "${DISTRO}" == "ubuntu" ]; then
  sudo apt update && \
    sudo apt install -y "${PACKAGE}"
elif [ "${DISTRO}" == "arch" ]; then
  sudo pacman -S "${PACKAGE}"
fi
