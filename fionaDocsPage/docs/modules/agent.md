# Agent

Agent is Fiona's local LM Studio bridge. It is the first connection point for future reasoning, but it is not a full autonomous agent yet.

## LM Studio Endpoint

Agent talks to LM Studio's local OpenAI-compatible API.

Default endpoint:

```text
http://localhost:1234/v1
```

Start LM Studio's local server from the LM Studio Developer tab, or with:

```bash
lms server start
```

## Commands

Check the server:

```bash
python3 -m fiona.cli agent status
```

Ask a local model:

```bash
python3 -m fiona.cli agent ask --model <model-id> "Summarize Fiona status."
```

Use a custom endpoint:

```bash
python3 -m fiona.cli agent status --base-url http://localhost:1234/v1
```

Customize generation settings:

```bash
python3 -m fiona.cli agent ask \
  --system "You are Fiona's local assistant." \
  --temperature 0.3 \
  --max-tokens 512 \
  --model <model-id> \
  "Prompt text"
```

## Important Boundary

This is inference, not model training. Fine-tuning, GPU resource control, dataset capture, evaluation, and rollback are future systems.
