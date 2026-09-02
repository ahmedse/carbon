# Moodle image for the air-gapped QBank stack.
# Build via scripts/build-image.sh (it extracts + sha256-verifies the tarball first).
ARG PHP_BASE=moodlehq/moodle-php-apache:8.3
FROM ${PHP_BASE}

ARG MOODLE_VERSION=5.2

RUN set -eux; \
    a2enmod ssl rewrite headers; \
    apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# Moodle source (extracted to build/moodle-code/ by build-image.sh)
COPY build/moodle-code/ /var/www/html/

# Apache vhosts: 80 -> 301 to https; 443 terminates TLS with mounted cert
COPY apache/000-default.conf /etc/apache2/sites-available/000-default.conf
COPY apache/moodle-ssl.conf   /etc/apache2/sites-available/moodle-ssl.conf
RUN a2ensite moodle-ssl

RUN chown -R www-data:www-data /var/www/html

HEALTHCHECK --interval=30s --timeout=5s --retries=3 --start-period=30s \
    CMD curl -fsk https://localhost/login/index.php -o /dev/null || exit 1

EXPOSE 80 443
