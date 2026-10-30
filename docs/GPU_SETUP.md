# Ollama GPU setup on this Windows machine

GPU access was enabled on 30 October 2026 with the user's approval. The running
Ollama container now has NVIDIA GPU access through Docker Desktop's WSL 2 backend.

## Verified hardware and cause

`nvidia-smi` reports **NVIDIA GeForce RTX 4060 Laptop GPU**, **8,188 MiB VRAM**,
driver **581.80**. The physical GPU therefore has about 8 GB, even if the amount
currently free for applications is lower.

The original Docker container had `HostConfig.DeviceRequests = null`. Ollama
reported `size_vram = 0`, so the original live attempts used CPU inference.
WSL's default version was already 2. The driver and GPU were detectable on Windows.

## Commands used to switch

The existing image ID was reused, the named volume `ollama` was retained, and the
original stopped container was renamed rather than deleted:

```powershell
$ollamaImage = docker inspect --format '{{.Image}}' ollama
docker stop ollama
docker rename ollama ollama-cpu-backup-20261030120239
docker run -d --gpus all --name ollama `
  -p 127.0.0.1:11434:11434 `
  -v ollama:/root/.ollama `
  --restart unless-stopped `
  $ollamaImage
```

This switch interrupted the in-progress CPU test, which remains preserved as an
unverified run. A fresh GPU run was created separately. The models were not
downloaded again. The API is bound to loopback and remains reachable at
`http://localhost:11434` from the host-side Python agent.

Do not repeat the rename/start sequence while the new container is already
running. The commands document the completed switch, not a required startup step.
For normal use, start Docker Desktop; the container's restart policy is
`unless-stopped`. If it was explicitly stopped, run `docker start ollama`.

## Verification

```powershell
docker inspect ollama --format '{{json .HostConfig.DeviceRequests}}'
docker exec ollama ollama run qwen2.5:latest 'Reply with OK only.'
docker exec ollama ollama ps
nvidia-smi --query-gpu=name,memory.total,memory.used,utilization.gpu --format=csv
Invoke-RestMethod 'http://localhost:11434/api/ps'
```

The first warm-up at an 8,192-token context returned `OK` and showed:

```text
NAME              PROCESSOR    CONTEXT
qwen2.5:latest    100% GPU     8192
```

The API reported `size_vram = 4,987,132,312` bytes. NVIDIA reported 4,896 MiB
allocated immediately afterward. GPU utilization can return to zero when no
generation is active; loaded VRAM plus Ollama's PROCESSOR field are useful checks.
The agent's `.env` requests a 16,384-token context. Actual memory use depends on
that context, parallel requests, model quantization, and other GPU applications.

The `.env` endpoint does not change:

```dotenv
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:latest
OLLAMA_NUM_CTX=16384
```

If a future run spills partly onto CPU, close other GPU-heavy workloads or reduce
context cautiously. A smaller context also reduces how much project history the
model can see. GPU acceleration changes execution speed and memory placement; it
does not by itself make the same model follow instructions more reliably.

## Recovery information

The preserved old container is named `ollama-cpu-backup-20261030120239`. Both old
and new configurations reference the same `ollama` model volume. Keep only one
server active on port 11434. No model-volume deletion is needed to switch back.

If Docker cannot expose the GPU on another machine, verify the NVIDIA Windows
driver, enable Docker Desktop's WSL 2 engine, and update WSL with `wsl --update`
if necessary. On this machine GPU passthrough was verified without installing
additional Linux drivers or changing Windows graphics preferences.

## Official references

- [Docker Desktop GPU support on Windows](https://docs.docker.com/desktop/features/gpu/)
- [Ollama Docker GPU command](https://docs.ollama.com/docker)
- [Ollama supported GPUs](https://docs.ollama.com/gpu)
