#libvirt-flask base Ubuntu image
FROM simora/docker-libvirt-flask:base

WORKDIR /usr/src/app

COPY root/ /

ENV DEBIAN_FRONTEND="noninteractive"

RUN pip3 install --no-cache-dir -r /app/requirements.txt && \
    rm -rf \
      /root/.cache \
      /tmp/*
