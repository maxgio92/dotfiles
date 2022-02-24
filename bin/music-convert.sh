#!/usr/bin/env bash

set -uo pipefail

SRC_CODEC=flac
DEST_CODEC=mp3

DIRSFILE=dirs.txt
FLACSFILE=flacs.txt

function convert_flac_to_mp3() {
	find . -type f -name *.$SRC_CODEC -exec echo {} >> $FLACSFILE \;
	while read flac; do
		if [[ $(dirname "${flac}") != **".$SRC_CODEC"** ]]; then
			track2track "${flac}" -t "${DEST_CODEC}" -o "${flac}.${DEST_CODEC}" 2>/dev/null
		fi
	done <$FLACSFILE
}

function store_flac_albums_dirs() {
	find . -type f -name *.$SRC_CODEC -exec dirname {} >> $DIRSFILE \;
	cat $DIRSFILE | uniq > $DIRSFILE.uniq
}

function reorganize_dirs() {
	while read dir; do
		if [[ "${dir}" != *".$DEST_CODEC"* ]] && [[ "${dir}" != *".$SRC_CODEC"* ]]; then
			mkdir -p "${dir}.$DEST_CODEC"
			find "${dir}" -type f -name *.$SRC_CODEC.$DEST_CODEC -exec mv {} "${dir}.$DEST_CODEC"/ \;
			while read file; do mv "${dir}.$DEST_CODEC/${file}" "${dir}.${DEST_CODEC}/${file//.$SRC_CODEC.$DEST_CODEC/.$DEST_CODEC}"; done <<<$(ls -1 "${dir}.$DEST_CODEC")
			mv "${dir}" "${dir}.$SRC_CODEC"
		fi
	done <$DIRSFILE.uniq
}

function clean_cache() {
	rm -f $DIRSFILE
	rm -f $DIRSFILE.uniq
	rm -f $FLACSFILE
}

function fix_wrong_dirnames() {
	find . -type d -name *.flac.flac > dirs.wrongname.txt
	while read dir; do echo "Renaming $dir to ${dir/.flac}"; mv "${dir}" "${dir/.flac}"; done<dirs.wrongname.txt
	rm -f dirs.wrongname.txt
}

function main() {
	clean_cache
	convert_flac_to_mp3
	store_flac_albums_dirs
	reorganize_dirs
	clean_cache
}

main $@
