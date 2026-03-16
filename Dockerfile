FROM archlinux:latest

RUN pacman -Syu --noconfirm \
    base-devel \
    glibc \
    wget curl \
    zip unzip tar \
    sudo \
    git \
    openssl \
    python3 python-uv python-pwntools python-requests \
    gdb \
    ruby \
    nodejs npm \
    checksec \
    docker \
    vim \
    openbsd-netcat \
    openssh

RUN gem install one_gadget seccomp-tools --no-user-install

# setup locale
COPY ./sandbox/locale.gen   /etc/locale.gen
COPY ./sandbox/locale.conf  /etc/locale.conf
RUN chmod 644 /etc/locale.gen
RUN chmod 644 /etc/locale.conf
RUN locale-gen

# setup sudo
COPY ./sandbox/sudoers /etc/sudoers
RUN chmod 440 /etc/sudoers

# create user "agent"
RUN useradd -m agent
RUN usermod -aG wheel agent
RUN usermod -aG docker agent

USER agent
WORKDIR /home/agent

# install yay
RUN cd ~ && \
    git clone https://aur.archlinux.org/yay.git && \
    cd yay && \
    makepkg -si --noconfirm

# install mcp and requests (from yay)
RUN yay -Syy --noconfirm --mflags "--nocheck" python-mcp

# install docker compose
RUN DOCKER_CONFIG=${DOCKER_CONFIG:-$HOME/.docker} && \
    mkdir -p $DOCKER_CONFIG/cli-plugins && \
    curl -SL https://github.com/docker/compose/releases/download/v5.0.1/docker-compose-linux-x86_64 -o $DOCKER_CONFIG/cli-plugins/docker-compose && \
    chmod +x $DOCKER_CONFIG/cli-plugins/docker-compose

# install pwndbg
RUN cd ~ && git clone https://github.com/pwndbg/pwndbg.git && cd ~/pwndbg && yes | ./setup.sh 

# install opencode
RUN cd ~ && curl -fsSL https://opencode.ai/install | bash

# install codex
RUN sudo npm install -g @openai/codex