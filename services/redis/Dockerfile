# Redis service for short-term memory cache
# Requires password as per documentation

FROM redis:7.2-alpine

# Create a directory for our script
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Use our custom entrypoint to handle REDIS_PASSWORD
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]

# Expose the default Redis port
EXPOSE 6379

# Default command: start redis server
# The entrypoint will either start with or without requirepass based on env var
CMD ["redis-server"]