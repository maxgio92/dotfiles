#!/usr/bin/env bash

# Usage: install-ospackage.sh NAME
# This is pretty rough.
PACKAGE="${1}"
DISTRO="$(awk '/^ID=/' /etc/*-release | awk -F'=' '{ print tolower($2) }')"

case "${DISTRO}" in
	nixos)
		nix-env -iA "nixos.${PACKAGE}"
		;;
	debian)
		sudo apt-get update && \
			sudo apt-get install \
				--no-install-recommends -y \
			$PACKAGE
		;;
	ubuntu)
		sudo apt-get update && \
			sudo apt-get install \
				--no-install-recommends -y \
			$PACKAGE
		;;
	arch)
		sudo pacman -S $PACKAGE
		;;
	wolfi)
		sudo apk add $PACKAGE
		;;
esac

