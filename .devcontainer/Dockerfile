# base it on debian:11
FROM debian:11

# add requirements
COPY requirements.txt /tmp/pip-tmp/
RUN apt-get update && \
   apt-get -y install wget gcc && \
   pip3 --disable-pip-version-check --no-cache-dir install -r /tmp/pip-tmp/requirements.txt && \
   rm -rf /tmp/pip-tmp

RUN 	apt install wget && \
   wget -O dpp.deb https://dl.dpp.dev/ && \
   dpkg -i dpp.deb