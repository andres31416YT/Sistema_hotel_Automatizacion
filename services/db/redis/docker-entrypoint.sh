#!/bin/sh
# Docker entrypoint script for Redis to handle password from environment

set -e

# If REDIS_PASSWORD is set, we need to add requirepass to redis.conf
if [ -n "$REDIS_PASSWORD" ]; then
    # Create a temporary config file
    TEMP_CONF="/tmp/redis.conf"
    cp /usr/local/etc/redis/redis.conf "$TEMP_CONF"
    echo "requirepass $REDIS_PASSWORD" >> "$TEMP_CONF"
    exec redis-server "$TEMP_CONF"
else
    # No password, start normally
    exec redis-server "$@"
fi