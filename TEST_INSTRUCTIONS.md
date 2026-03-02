# Heimdall SSH+FTP Deployment Test Instructions

This guide walks you through testing Heimdall's multi-provider LLM support and drift detection with a live VM.

## Prerequisites

1. **Valid API Key**: Either OpenRouter or Anthropic
   - OpenRouter: Get key from https://openrouter.ai/keys
   - Anthropic: Get key from https://console.anthropic.com/

2. **Docker**: Ensure Docker daemon is running

## Setup VM

```bash
# Create fresh Ubuntu 24.04 container
docker run -d --name heimdall-vm --hostname heimdall-test ubuntu:24.04 sleep infinity

# Install prerequisites
docker exec heimdall-vm apt-get update -qq
docker exec heimdall-vm apt-get install -y -qq python3-pip python3-venv git curl

# Copy Heimdall to VM
docker cp . heimdall-vm:/root/heimdall

# Install Heimdall
docker exec heimdall-vm python3 -m venv /opt/heimdall-venv
docker exec -w /root/heimdall heimdall-vm /opt/heimdall-venv/bin/pip install -q -e .
```

## Configure Heimdall

```bash
# Copy sample config
docker cp config-sample.yaml heimdall-vm:/root/heimdall/config.yaml

# Edit config.yaml in the VM and set your provider
# Option 1: OpenRouter (recommended for cost)
# Option 2: Anthropic (more reliable, higher cost)
```

## Test Workflow

### 1. Baseline Discovery

```bash
# Run discovery to establish baseline
docker exec -w /root/heimdall heimdall-vm bash -c \
  "export OPENROUTER_API_KEY='your-key-here' && \
   /opt/heimdall-venv/bin/heimdall --config config.yaml init"

# Check generated profile
docker exec heimdall-vm cat /root/heimdall/profiles/current.json
```

### 2. Apply SSH+FTP Recipe

```bash
# Dry-run first (see what would be done)
docker exec -w /root/heimdall heimdall-vm bash -c \
  "export OPENROUTER_API_KEY='your-key-here' && \
   /opt/heimdall-venv/bin/heimdall --config config.yaml apply recipes/ssh-ftp.md --check"

# Apply for real
docker exec -w /root/heimdall heimdall-vm bash -c \
  "export OPENROUTER_API_KEY='your-key-here' && \
   /opt/heimdall-venv/bin/heimdall --config config.yaml apply recipes/ssh-ftp.md"
```

### 3. Verify Services

```bash
# Check SSH installed
docker exec heimdall-vm dpkg -l | grep openssh-server

# Check vsftpd installed
docker exec heimdall-vm dpkg -l | grep vsftpd

# Check services status
docker exec heimdall-vm systemctl status ssh 2>/dev/null || echo "systemd not available in container"
```

### 4. Introduce Drift (Install NFS)

```bash
# Install NFS server (not in recipe)
docker exec heimdall-vm apt-get install -y -qq nfs-kernel-server
```

### 5. Detect Drift

```bash
# Run guard to check for drift
docker exec -w /root/heimdall heimdall-vm bash -c \
  "export OPENROUTER_API_KEY='your-key-here' && \
   /opt/heimdall-venv/bin/heimdall --config config.yaml guard recipes/ssh-ftp.md"

# Check drift report
docker exec heimdall-vm cat /root/heimdall/profiles/drift-report.json

# View formatted status
docker exec -w /root/heimdall heimdall-vm bash -c \
  "export OPENROUTER_API_KEY='your-key-here' && \
   /opt/heimdall-venv/bin/heimdall --config config.yaml status"
```

## Expected Results

1. **After init**: `profiles/current.json` contains baseline machine state
2. **After apply**: SSH and vsftpd are installed and configured per recipe
3. **After NFS install**: System diverges from recipe specification
4. **After guard**: `profiles/drift-report.json` shows NFS as unexpected package/service

## Cleanup

```bash
# Stop and remove VM
docker rm -f heimdall-vm
```

## Troubleshooting

- **401 Unauthorized**: Check API key is valid and matches provider
- **Tool calling errors**: Ensure model supports function calling (e.g., gpt-4o-mini, not base gpt-3.5)
- **Missing systemd**: Container may not have systemd; some service checks will fail gracefully
- **Permission errors**: OpenRouter client enforces allowlist; check `config.yaml` for allowed commands

## Notes on Provider Choice

- **OpenRouter**: Cheapest option, good for testing. Use `gpt-4o-mini` or tool-capable Llama models.
- **Anthropic**: More expensive but more reliable for complex tool orchestration. Use `sonnet` model.

The abstraction layer allows seamless switching between providers by changing `llm_provider` in config.
