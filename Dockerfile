FROM docker.io/kalilinux/kali-rolling:latest

LABEL org.label-schema.name='Sn1per - Kali Linux' \
    org.label-schema.description='Automated pentest framework for offensive security experts' \
    org.label-schema.usage='https://github.com/marcarna90/Sn1per' \
    org.label-schema.url='https://github.com/marcarna90/Sn1per' \
    org.label-schema.vendor='https://sn1persecurity.com' \
    org.label-schema.schema-version='1.0' \
    org.label-schema.docker.cmd.devel='docker run --rm -ti xer0dayz/sniper' \
    MAINTAINER="@xer0dayz"

RUN echo "deb http://http.kali.org/kali kali-rolling main contrib non-free" > /etc/apt/sources.list && \
    echo "deb-src http://http.kali.org/kali kali-rolling main contrib non-free" >> /etc/apt/sources.list
ENV DEBIAN_FRONTEND=noninteractive

RUN set -x \
        && apt -yqq update \
        && apt -yqq full-upgrade \
        && apt clean
RUN apt install --yes metasploit-framework

RUN sed -i 's/systemctl status ${PG_SERVICE}/service ${PG_SERVICE} status/g' /usr/bin/msfdb && \
    service postgresql start && \
    msfdb reinit

WORKDIR /usr/src/app

# Build from this fork (Sn1per engine + Jarvis reporting/ASM layer) rather than
# upstream 1N3/Sn1per, so the image ships Jarvis. Override at build time with
#   docker build --build-arg REPO_BRANCH=main ...
ARG REPO_URL=https://github.com/marcarna90/Sn1per.git
ARG REPO_BRANCH=claude/great-ptolemy-dp0gxj

RUN apt --yes install git bash rsync python3
RUN git clone --branch "$REPO_BRANCH" --single-branch "$REPO_URL" Sn1per \
    && cd Sn1per \
    && bash install.sh
# NOTE: 'sniper -u force' is intentionally omitted — it would pull the default
# branch over the install dir and could drop the Jarvis layer.

CMD ["sniper"]