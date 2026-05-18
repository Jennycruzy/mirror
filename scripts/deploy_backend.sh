#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "usage: $0 <ssh-key-path> <user@host>"
  exit 1
fi

SSH_KEY="$1"
TARGET="$2"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

rsync -az --delete \
  --filter='P .env' \
  --filter='P .env.kraken-demo.example' \
  --exclude '.venv' \
  --exclude '.pytest_cache' \
  -e "ssh -i ${SSH_KEY} -o StrictHostKeyChecking=no" \
  "${ROOT}/backend/" \
  "${TARGET}:/home/ubuntu/mirror/backend/"
