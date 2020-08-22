#LinuxServers base Ubuntu image
FROM lsiobase/ubuntu:bionic

WORKDIR /usr/src/app

COPY root/ /

ENV DEBIAN_FRONTEND="noninteractive"

RUN apt-get update && apt-get install -y \
      python3.8 \
      python3.8-dev \
      python3-pip \
      libvirt-dev \
      libxml2-dev \
      libxslt-dev \
      openssh-client && \
      apt-get -y autoremove && \
      update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.8
RUN pip3 install --no-cache-dir -r /app/requirements.txt && \
    rm -rf \
      /root/.cache \
      /tmp/*
