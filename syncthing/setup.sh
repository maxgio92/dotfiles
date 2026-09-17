#!/usr/bin/env bash
set -euo pipefail
umask 077

source_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null && pwd)
source "$source_dir/devices.env"
source "$source_dir/settings.env"
case "${1:-}" in
  laptop) peer_name=workstation; peer_id=$WORKSTATION_ID; declared_id=$LAPTOP_ID ;;
  workstation) peer_name=laptop; peer_id=$LAPTOP_ID; declared_id=$WORKSTATION_ID ;;
  *) echo 'Usage: setup.sh laptop|workstation' >&2; exit 1 ;;
esac

config_home=${XDG_CONFIG_HOME:-$HOME/.config}
data_home=${XDG_DATA_HOME:-$HOME/.local/share}
state_home=${XDG_STATE_HOME:-$HOME/.local/state}
for path in "$config_home" "$data_home" "$state_home"; do
  [[ $path = /* ]] || { echo 'XDG paths must be absolute.' >&2; exit 1; }
done
share=$data_home/$peer_name
run=(bash "$source_dir/run.sh")

mkdir -p "$config_home/syncthing" "$state_home/syncthing" "$share"
cp "$source_dir/stignore" "$share/.stignore"
if [[ ! -f $config_home/syncthing/config.xml ]]; then
  "${run[@]}" generate --no-port-probing
fi
device_id=$("${run[@]}" device-id)
if [[ -n $declared_id && $declared_id != "$device_id" ]]; then
  echo "Declared local ID differs from this machine: $device_id" >&2
  exit 1
fi
if [[ -n $peer_id && $peer_id = "$device_id" ]]; then
  echo 'Peer ID must belong to the other machine.' >&2
  exit 1
fi

mkdir -p "$HOME/.local/bin" "$config_home/systemd/user"
launcher=$(mktemp "$HOME/.local/bin/.dotfiles-syncthing.XXXXXX")
{
  printf '#!/usr/bin/env bash\n'
  printf 'export XDG_CONFIG_HOME=%q XDG_DATA_HOME=%q XDG_STATE_HOME=%q\n' "$config_home" "$data_home" "$state_home"
  printf 'exec bash %q "$@"\n' "$source_dir/run.sh"
} >"$launcher"
chmod 700 "$launcher"
mv -f "$launcher" "$HOME/.local/bin/dotfiles-syncthing"
ln -sfn "$source_dir/syncthing.service" "$config_home/systemd/user/syncthing.service"
systemctl --user daemon-reload
systemctl --user enable --now syncthing.service
cli=("${run[@]}" cli)
ready=false
for ((attempt=0; attempt<30; attempt++)); do
  if "${cli[@]}" show system >/dev/null 2>&1; then ready=true; break; fi
  sleep 1
done
$ready || { echo 'Syncthing API did not become ready. Check journalctl --user -u syncthing.' >&2; exit 1; }

folders=$("${cli[@]}" config folders list)
if ! grep -Fxq "$FOLDER_ID" <<<"$folders"; then
  "${cli[@]}" config folders add --id "$FOLDER_ID" --path "$share" --type "$FOLDER_TYPE"
fi
folder=("${cli[@]}" config folders "$FOLDER_ID")
"${folder[@]}" path set "$share"
"${folder[@]}" label set "$FOLDER_LABEL"
"${folder[@]}" type set "$FOLDER_TYPE"
"${folder[@]}" fswatcher-enabled set true
"${folder[@]}" fswatcher-delays set "$WATCH_DELAY_SECONDS"
"${folder[@]}" rescan-intervals set "$RESCAN_SECONDS"
"${folder[@]}" versioning type set simple
"${folder[@]}" versioning params set keep "$VERSION_KEEP"

if [[ -n $peer_id ]]; then
  devices=$("${cli[@]}" config devices list)
  if ! grep -Fxq "$peer_id" <<<"$devices"; then
    "${cli[@]}" config devices add --device-id "$peer_id" --name "$peer_name"
  fi
  folder_devices=$("${folder[@]}" devices list)
  if ! grep -Fxq "$peer_id" <<<"$folder_devices"; then
    "${folder[@]}" devices add --device-id "$peer_id"
  fi
else
  echo "Pairing pending: set both IDs in $source_dir/devices.env and rerun on both machines."
fi
folder_devices=$("${folder[@]}" devices list)
while IFS= read -r id; do
  if [[ -n $id && $id != "$device_id" && $id != "$peer_id" ]]; then
    "${folder[@]}" devices "$id" delete
  fi
done <<<"$folder_devices"
printf 'Device ID: %s\nFolder: %s\n' "$device_id" "$share"
