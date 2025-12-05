ARG BUILD_FROM
FROM $BUILD_FROM

# Install ADB and Python dependencies
RUN apk add --no-cache \
    python3 \
    py3-pip \
    android-tools \
    bash \
    jq \
    openssl

# Create app directory
WORKDIR /app

# Copy application files
COPY stremio_mcp.py /app/
COPY requirements.txt /app/
COPY icon.png /app/

# Install Python dependencies
RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt

# Copy run script
COPY run.sh /run.sh
RUN chmod a+x /run.sh

# Create ADB keys directory
RUN mkdir -p /root/.android

# Expose SSE port
EXPOSE 9821

CMD [ "/run.sh" ]

LABEL \
    io.hass.version="1.2.7" \
    io.hass.type="addon" \
    io.hass.arch="amd64|aarch64|armv7"
