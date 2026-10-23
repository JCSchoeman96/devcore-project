#!/usr/bin/env bash
set -euo pipefail
set +x
umask 077

die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

usage() {
  cat <<'USAGE'
Usage:
  install.sh --source FILE --version X.Y.Z --sha256 HEX

Install or update the verified DevCore executable at ~/.local/bin/devcore-project.
The supplied version and SHA-256 must match the executable and release checksum.
USAGE
}

version=""
source_file=""
expected_sha256=""
while (($#)); do
  case "$1" in
    --source)
      (($# >= 2)) || die "--source requires a file path"
      source_file="$2"
      shift 2
      ;;
    --version)
      (($# >= 2)) || die "--version requires X.Y.Z"
      version="$2"
      shift 2
      ;;
    --sha256)
      (($# >= 2)) || die "--sha256 requires a checksum"
      expected_sha256="$2"
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      usage >&2
      die "unknown argument: $1"
      ;;
  esac
done

[[ "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || die "version must use X.Y.Z SemVer"
[[ "$expected_sha256" =~ ^[a-f0-9]{64}$ ]] || die "SHA-256 must contain 64 lowercase hexadecimal characters"
[[ -n "$source_file" && -f "$source_file" && ! -L "$source_file" ]] || die "source must be a regular, non-symlink file"
[[ -n "${HOME:-}" && -d "$HOME" ]] || die "HOME must name an existing user directory"
[[ "${EUID:-0}" -ne 0 ]] || die "run this installer as the target user, without root"

command -v sha256sum >/dev/null 2>&1 || die "required command not found: sha256sum"
command -v install >/dev/null 2>&1 || die "required command not found: install"

home_real="$(cd -- "$HOME" && pwd -P)" || die "cannot resolve HOME"
local_dir="$HOME/.local"
[[ ! -L "$local_dir" ]] || die "refusing a symlink at ~/.local"
mkdir -p -- "$local_dir"
install_dir="$local_dir/bin"
[[ ! -L "$install_dir" ]] || die "refusing a symlink at ~/.local/bin"
mkdir -p -- "$install_dir"
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

actual_sha256="$(sha256sum -- "$source_file" | awk '{print $1}')"
[[ "$actual_sha256" == "$expected_sha256" ]] || die "source checksum does not match the supplied release checksum"

source_version="$(awk -F'"' '/^VERSION="/ { print $2; found=1; exit } END { if (!found) exit 1 }' "$source_file")" || \
  die "source does not declare a VERSION"
[[ "$source_version" == "$version" ]] || die "source version does not match the supplied version"
IFS= read -r first_line < "$source_file" || die "source is empty"
[[ "$first_line" == '#!/usr/bin/env bash' ]] || die "source is not a Bash executable"
bash -n -- "$source_file" || die "source has invalid Bash syntax"

temp_file=""
backup_temp=""
cleanup() {
  [[ -z "$temp_file" || ! -e "$temp_file" ]] || rm -f -- "$temp_file"
  [[ -z "$backup_temp" || ! -e "$backup_temp" ]] || rm -f -- "$backup_temp"
}
trap cleanup EXIT

temp_file="$(mktemp "$install_dir_real/.devcore-project.new.XXXXXX")" || die "cannot stage verified executable"
install -m 0700 -- "$source_file" "$temp_file" || die "cannot set staged executable permissions"
staged_sha256="$(sha256sum -- "$temp_file" | awk '{print $1}')"
[[ "$staged_sha256" == "$expected_sha256" ]] || die "staged executable checksum changed"

backup_path=""
if [[ -e "$target" ]]; then
  backup_temp="$(mktemp "$install_dir_real/.devcore-project.backup.XXXXXX")" || die "cannot stage previous executable"
  install -m 0700 -- "$target" "$backup_temp" || die "cannot back up previous executable"
  backup_stamp="$(date -u +%Y%m%dT%H%M%S.%NZ)" || die "cannot create a UTC backup timestamp"
  [[ "$backup_stamp" =~ ^[0-9]{8}T[0-9]{6}\.[0-9]{9}Z$ ]] || die "date did not provide a nanosecond UTC timestamp"

  backup_sequence=0
  backup_prefix="devcore-project.previous.$backup_stamp."
  shopt -s nullglob
  matching_backups=("$install_dir_real/$backup_prefix"*)
  shopt -u nullglob
  for candidate in "${matching_backups[@]}"; do
    candidate_name="${candidate##*/}"
    [[ "$candidate_name" == "$backup_prefix"* ]] || continue
    candidate_suffix="${candidate_name#"$backup_prefix"}"
    if [[ "$candidate_suffix" =~ ^([0-9]{9})\.[0-9]+$ ]]; then
      candidate_sequence=$((10#${BASH_REMATCH[1]}))
      if ((candidate_sequence >= backup_sequence)); then
        backup_sequence=$((candidate_sequence + 1))
      fi
    fi
  done
  ((backup_sequence <= 999999999)) || die "backup sequence is exhausted for this timestamp"
  printf -v backup_sequence_text '%09d' "$backup_sequence"
  backup_path="$install_dir_real/$backup_prefix$backup_sequence_text.$$"
  [[ ! -e "$backup_path" && ! -L "$backup_path" ]] || die "backup path already exists"
  mv -- "$backup_temp" "$backup_path" || die "cannot save previous executable"
  backup_temp=""
fi

mv -f -- "$temp_file" "$target" || die "cannot atomically install verified executable"
temp_file=""
printf 'Installed devcore-project %s at %s\n' "$version" "$target"
if [[ -n "$backup_path" ]]; then
  printf 'Previous executable saved at %s\n' "$backup_path"
fi
