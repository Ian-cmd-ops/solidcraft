#!/usr/bin/env bash
# Wrapper: see tools/post_kit.py for the kit format.
# Usage: tools/post_kit.sh <kit-dir> [--dry-run]
exec python3 "$(cd "$(dirname "$0")" && pwd)/post_kit.py" "$@"
