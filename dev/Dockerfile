FROM python:3.8.2-slim

RUN sed -i 's:^path-exclude /usr/share/groff/\*::' /etc/dpkg/dpkg.cfg.d/docker \
 && apt-get update \
 && apt-get install -y git wget curl nmap zsh groff vim entr sudo jq parallel \
 && sed -i 's/^%sudo.*/%sudo ALL=(ALL) NOPASSWD: ALL/' /etc/sudoers \
 && pip install --upgrade pip \
 && pip install awscli \
 && curl https://s3.amazonaws.com/session-manager-downloads/plugin/latest/ubuntu_64bit/session-manager-plugin.deb -o /tmp/session-manager-plugin.deb \
 && dpkg -i /tmp/session-manager-plugin.deb \
 && rm /tmp/session-manager-plugin.deb \
 && sh -c "$(curl -fsSL https://raw.github.com/ohmyzsh/ohmyzsh/master/tools/install.sh)" \
 && curl -Lo /cw.deb https://github.com/lucagrulla/cw/releases/download/v4.0.6/cw_amd64.deb \
 && dpkg -i /cw.deb \
 && rm -f /cw.deb

COPY requirements.txt /build/

RUN pip install -Ur /build/requirements.txt --no-cache-dir

COPY scripts/docker_zshrc.sh /home/user/.zshrc
COPY scripts/docker_profile.sh /etc/profile.d/docker_dev.sh
COPY scripts/docker_launch.sh /launch.sh
