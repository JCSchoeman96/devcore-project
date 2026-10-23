#!/usr/bin/env bash
set -euo pipefail
set +x
umask 077

die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

if (($#)); then
  die "rollback takes no arguments"
fi
[[ -n "${HOME:-}" && -d "$HOME" ]] || die "HOME must name an existing user directory"
[[ "${EUID:-0}" -ne 0 ]] || die "run rollback as the target user, without root"
command -v install >/dev/null 2>&1 || die "required command not found: install"

home_real="$(cd -- "$HOME" && pwd -P)" || die "cannot resolve HOME"
local_dir="$HOME/.local"
[[ ! -L "$local_dir" ]] || die "refusing a symlink at ~/.local"
install_dir="$local_dir/bin"
[[ ! -L "$install_dir" ]] || die "refusing a symlink at ~/.local/bin"
[[ -d "$install_dir" ]] || die "user-local install directory does not exist"
install_dir_real="$(cd -- "$install_dir" && pwd -P)" || die "cannot resolve user-local install directory"
case "$install_dir_real/" in
  "$home_real/"*) ;;
  *) die "user-local install directory resolves outside HOME" ;;
esac

target="$install_dir_real/devcore-project"
if [[ -L "$target" ]]; then
  die "refusing to replace a symlink at the install target"
fi
if [[ -e "$target" && ! -f "$target" ]]; then
  die "install target exists and is not a regular file"
fi

shopt -s nullglob
backups=("$install_dir_real"/devcore-project.previous.*)
shopt -u nullglob
((${#backups[@]} > 0)) || die "no previous DevCore executable is available"
backup=""
for candidate in "${backups[@]}"; do
  candidate_name="${candidate##*/}"
  [[ "$candidate_name" =~ ^devcore-project\.previous\.[0-9]{8}T[0-9]{6}Z\.[0-9]+$ ]] || continue
  [[ -f "$candidate" && ! -L "$candidate" ]] || continue
  [[ -z "$backup" || "$candidate" > "$backup" ]] && backup="$candidate"
done
[[ -n "$backup" && -f "$backup" && ! -L "$backup" ]] || die "no timestamped previous executable is available"

source_version="$(awk -F'"' '/^VERSION="/ { print $2; found=1; exit } END { if (!found) exit 1 }' "$backup")" || \
  die "previous executable does not declare a VERSION"
IFS= read -r first_line < "$backup" || die "previous executable is empty"
[[ "$first_line" == '#!/usr/bin/env bash' ]] || die "previous file is not a Bash executable"
bash -n -- "$backup" || die "previous executable has invalid Bash syntax"

temp_file=""
current_backup_temp=""
cleanup() {
  [[ -z "$temp_file" || ! -e "$temp_file" ]] || rm -f -- "$temp_file"
  [[ -z "$current_backup_temp" || ! -e "$current_backup_temp" ]] || rm -f -- "$current_backup_temp"
}
trap cleanup EXIT

temp_file="$(mktemp "$install_dir_real/.devcore-project.rollback.XXXXXX")" || die "cannot stage rollback executable"
install -m 0700 -- "$backup" "$temp_file" || die "cannot stage rollback executable"

current_backup_path=""
if [[ -e "$target" ]]; then
  current_backup_temp="$(mktemp "$install_dir_real/.devcore-project.current.XXXXXX")" || die "cannot stage current executable"
  install -m 0700 -- "$target" "$current_backup_temp" || die "cannot preserve current executable"
  current_backup_path="$install_dir_real/devcore-project.rolled-back.$(date -u +%Y%m%dT%H%M%SZ).$$"
  [[ ! -e "$current_backup_path" && ! -L "$current_backup_path" ]] || die "rollback backup path already exists"
  mv -- "$current_backup_temp" "$current_backup_path" || die "cannot preserve current executable"
  current_backup_temp=""
fi

mv -f -- "$temp_file" "$target" || die "cannot atomically restore previous executable"
temp_file=""
printf 'Restored devcore-project %s at %s\n' "$source_version" "$target"
if [[ -n "$current_backup_path" ]]; then
  printf 'Replaced executable saved at %s\n' "$current_backup_path"
fi
