#LinuxServers base Ubuntu image
FROM lsiobase/ubuntu:bionic

WORKDIR /usr/src/app

COPY root/ /

ENV DEBIAN_FRONTEND="noninteractive"

RUN apt-get update && apt-get install -y \
      python3 \
      python3-pip \
      libvirt-dev \
      libxml2-dev \
      libxslt-dev

RUN pip install --no-cache-dir -r /app/requirements.txt
