#libvirt-flask base Ubuntu image
FROM simora/docker-libvirt-flask:base

WORKDIR /usr/src/app

COPY root/ /
