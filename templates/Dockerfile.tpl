FROM archlinux:latest

{{PACMAN_BLOCK}}
RUN useradd -m agent && usermod -aG wheel,docker agent
RUN printf '%s\n' 'Defaults env_reset' 'root ALL=(ALL:ALL) ALL' '%wheel ALL=(ALL:ALL) NOPASSWD:ALL' > /etc/sudoers && chmod 440 /etc/sudoers

{{COPY_BLOCK}}
{{ENV_BLOCK}}
{{ROOT_COMMANDS_BLOCK}}

USER agent
{{AGENT_COMMANDS_BLOCK}}
{{YAY_BLOCK}}
{{NPM_BLOCK}}
{{GEM_BLOCK}}
{{PIP_BLOCK}}
WORKDIR /home/agent/challenge
