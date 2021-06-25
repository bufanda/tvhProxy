FROM        python:3-alpine as base

ENV         HE_HTTP_VERBOSE=0

RUN         apk update &&\
                apk add --no-cache git build-base libffi-dev

ARG         TARGETARCH
ARG         TARGETPLATFORM
ARG         BUILDPLATFORM
ARG         ARCH=${TARGETPLATFORM}

FROM base as base-arm64

ADD         https://github.com/just-containers/s6-overlay/releases/download/v1.19.1.1/s6-overlay-armhf.tar.gz /tmp/s6-overlay.tar.gz

FROM base as base-arm

ADD         https://github.com/just-containers/s6-overlay/releases/download/v1.19.1.1/s6-overlay-armhf.tar.gz /tmp/s6-overlay.tar.gz

FROM base as base-amd64

ADD         https://github.com/just-containers/s6-overlay/releases/download/v1.19.1.1/s6-overlay-amd64.tar.gz /tmp/s6-overlay.tar.gz

# hadolint ignore: DL3006
FROM base-$TARGETARCH

SHELL ["/bin/ash", "-eo", "pipefail", "-c"]
RUN         gunzip -c /tmp/s6-overlay.tar.gz | tar -xf - -C /

COPY         requirements.txt /opt/tvhProxy/requirements.txt

RUN         pip install --no-cache-dir -r  /opt/tvhProxy/requirements.txt

COPY         services.d /etc/services.d
COPY         templates /opt/tvhProxy/templates
COPY         *.py /opt/tvhProxy/
RUN         ls -al /opt/tvhProxy

EXPOSE      80 5004 65001/tcp 65001/udp

ENTRYPOINT  ["/init"]
