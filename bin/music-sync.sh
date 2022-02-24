#!/usr/bin/env bash

#set -u
set -e

MEDIADIR="${1}"

function show_help() {
	echo
	echo "Usage: $(basename ${0}) MEDIADIR"
	echo
	echo "	MEDIADIR: the directory name under /run/media/USER where the USB device is automatically mounted as for udev rules."
	echo
}

function main() {
	if test -z $MEDIADIR; then
		echo "Error: MEDIADIR not specified"
		show_help
		exit 1
	fi
	rsync -avz --exclude '*.flac/*' --exclude 'temp/*' $HOME/Music/ /run/media/$(whoami)/$MEDIADIR
}

main "${@}"
