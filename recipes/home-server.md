---
name: Home Server
description: SSH hardening, Seafile cloud storage, Jellyfin media streaming
tags: [home, server, media, cloud]
os_families: [debian, redhat]
---

# Home Server Recipe

## System Update

Ensure the system is fully up to date. Run the package manager update and upgrade commands.

## SSH Hardening

Configure SSH for security:

- Disable root login (`PermitRootLogin no` in `/etc/ssh/sshd_config`)
- Disable password authentication (`PasswordAuthentication no`)
- Set `MaxAuthTries 3`
- Allow only key-based authentication (`PubkeyAuthentication yes`)
- Restart the SSH service after changes

## Firewall

Set up the firewall to allow only necessary traffic:

- Allow SSH (port 22)
- Allow HTTP (port 80) and HTTPS (port 443)
- Allow Seafile (port 8082 for file server, port 8000 for web UI)
- Allow Jellyfin (port 8096 for web UI, port 8920 for HTTPS)
- Deny all other incoming traffic by default
- Enable the firewall

## Seafile

Install and configure Seafile cloud storage:

- Install required dependencies: `python3`, `python3-pip`, `python3-setuptools`, `python3-pil`, `libmysqlclient-dev`
- Download and extract the latest Seafile server package to `/opt/seafile`
- Run the setup script with default SQLite configuration
- Create a systemd service unit for Seafile at `/etc/systemd/system/seafile.service`
- Enable and start the Seafile service

## Jellyfin

Install and configure Jellyfin media server:

- Add the Jellyfin repository and GPG key
- Install the `jellyfin` package
- Enable and start the Jellyfin service
- Ensure the media directory `/srv/media` exists with appropriate permissions

## Verification

After applying all sections, verify:

- [ ] SSH is running and hardened (check config values)
- [ ] Firewall is active with correct rules
- [ ] Seafile service is running on ports 8000 and 8082
- [ ] Jellyfin service is running on port 8096
- [ ] All services are enabled for boot
