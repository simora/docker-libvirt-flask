FROM python:3.8.5-buster

WORKDIR /usr/src/app

COPY requirements.txt ./

ENV DEBIAN_FRONTEND="noninteractive"

RUN apt-get update
RUN apt-get install -y \
      libvirt-dev \
      libxml2-dev \
      libxslt-dev
RUN pip install --no-cache-dir -r requirements.txt
