#!/bin/sh
set -eu
umask 077

if [ ! -w /app/data ]; then
    echo "SoloLMNP: /app/data is not writable. See docs/DEPLOYMENT.md for Linux UID/GID settings." >&2
    exit 1
fi

# A failed migration stops startup; never advertise an outdated schema as ready.
python -m alembic upgrade head
exec "$@"
