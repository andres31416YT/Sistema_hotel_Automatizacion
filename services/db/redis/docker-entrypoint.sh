#!/bin/sh
# Docker entrypoint script for Redis to handle password from environment

set -e

CONF="/tmp/redis.conf"

# Always write a config file
echo "" > "$CONF"

# If REDIS_PASSWORD is set, add requirepass
if [ -n "$REDIS_PASSWORD" ]; then
    echo "requirepass $REDIS_PASSWORD" >> "$CONF"
fi

exec redis-server "$CONF"