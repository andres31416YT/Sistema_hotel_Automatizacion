# Hotel Transactional PostgreSQL DB
# This database stores clients, rooms, reservations, checkins, etc.

# We'll use the official postgres image and run init scripts

# No additional Python packages needed; the image provides the DB.
# We'll just ensure the init scripts are copied.

# Since we are using the official image, we don't need a custom Dockerfile unless we want to add extensions.
# We'll use the official postgres:16-alpine and rely on the init scripts.

# However, to keep the structure similar to other services, we'll create a minimal Dockerfile that uses the official image.

FROM postgres:16-alpine

# Copy init scripts
COPY init/ /docker-entrypoint-initdb.d/

# The official postgres image will automatically run .sql and .sh scripts found in /docker-entrypoint-initdb.d/