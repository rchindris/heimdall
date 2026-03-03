---
name: Secure SSH + FTP Baseline
description: Install and configure OpenSSH for admin access and vsftpd for file transfer.
tags: [ssh, ftp, baseline]
os_families: [debian, redhat]
---

# Secure SSH + FTP Baseline

## System Update

Ensure the system is fully updated via the package manager before making any changes.

## OpenSSH Server

- Install `openssh-server`.
- Ensure `/etc/ssh/sshd_config` enforces:
  - `PasswordAuthentication no`
  - `PermitRootLogin prohibit-password`
  - `MaxAuthTries 4`
- Restart and enable the SSH service.

## FTP Service

- Install `vsftpd`.
- Configure `/etc/vsftpd.conf` with:
  - `listen=YES`
  - `listen_ipv6=NO`
  - `anonymous_enable=NO`
  - `local_enable=YES`
  - `write_enable=YES`
  - `chroot_local_user=YES`
- Ensure `/srv/ftp` exists and is owned by `ftp:ftp` with mode `0755`.
- Enable and start the `vsftpd` service.

## Firewall

- Ensure `ufw` (Debian/Ubuntu) or `firewalld` (RHEL/Fedora) is installed.
- For `ufw`:
  - Set default incoming policy to DENY.
  - Allow SSH (22/tcp).
  - Allow FTP (21/tcp).
  - Enable the firewall.
- For `firewalld`:
  - Set default zone to drop.
  - Add permanent rules for SSH (22/tcp) and FTP (21/tcp).
  - Reload firewall.
- Confirm with `ufw status` or `firewall-cmd --list-all` that only ports 21 and 22 are allowed.

## Verification

- Confirm `sshd` is listening on port 22 and `vsftpd` on port 21.
- Ensure both services are enabled at boot.
- Verify firewall allows only SSH (22) and FTP (21).
