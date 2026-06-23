# Recovery Rules

Rules for handling errors, failures, and unexpected situations.

## General Recovery Strategy

```
Error Occurs
    │
    ▼
┌─────────────────────────────┐
│ 1. CLASSIFY the error       │
│    - Transient or permanent?│
│    - Known or unknown?      │
│    - Is there a clear fix?  │
└─────────────────────────────┘
    │
    ▼
┌─────────────────────────────┐
│ 2. DIAGNOSE root cause      │
│    - Read full error        │
│    - Identify failing layer │
│    - Check logs             │
│    - Verify preconditions   │
└─────────────────────────────┘
    │
    ▼
┌─────────────────────────────┐
│ 3. ATTEMPT recovery         │
│    - Retry (for transient)  │
│    - Fix (for known cause)  │
│    - Rollback (for partial) │
└─────────────────────────────┘
    │
    ▼
┌─────────────────────────────┐
│ 4. ESCALATE if needed       │
│    - Report to user         │
│    - Suggest workaround     │
│    - Document for later     │
└─────────────────────────────┘
```

## Specific Recovery Patterns

### Build/Test Failures
1. Read the full error output — do not truncate or summarize.
2. Check dependency versions and toolchain.
3. Verify environment variables and paths.
4. Inspect compiler/toolchain versions.
5. Do NOT delete build directories unnecessarily.
6. Explain what failed and why before suggesting a fix.

### Git Conflicts or Errors
1. Check `git status` and `git log --oneline -10` first.
2. Never force push or rebase without explicit instruction.
3. If a commit is rejected by hooks, fix the issue and make a new commit
   — do not amend the failed commit.
4. Preserve history unless explicitly asked to rewrite it.

### Service/Process Failures
1. Check `systemctl status` or `journalctl -u <service>` for system services.
2. Check `ps aux` for user processes.
3. Verify configuration files exist and are valid.
4. Check logs with `journalctl --no-pager -n 50`.
5. Prefer restarting over reinstalling.

### Permission Denied
1. Check file ownership: `ls -la`.
2. Check if `sudo` is actually needed (Prefer non-sudo).
3. If `sudo` is required, flag it as a high-risk action requiring approval.
4. Never suggest `chmod 777` as a solution.

### Network Errors
1. Check connectivity with `ping` or `curl`.
2. Verify URLs and endpoints are correct.
3. Check firewall/proxy configuration.
4. Ensure services are running on the expected ports.
5. For Ollama: verify `ollama serve` is running and the model is pulled.

## Rollback Strategy

Any change should be reversible. Before making changes:

1. Ensure the current state is committed or stashed.
2. Document what will change.
3. After the change, verify with tests and `git diff`.
4. If the change fails, `git checkout -- <file>` or `git stash pop` to
   restore the original state.

## When to Ask for Help

Ask the user when:
- The error is unfamiliar and searching doesn't reveal a cause.
- Multiple approaches are possible and you need to decide which.
- The fix requires deleting data or making irreversible changes.
- You need access to external systems, credentials, or permissions.
- Requirements are ambiguous and need clarification.

## When to Give Up Gracefully

If recovery fails after reasonable attempts:
1. Report what was tried and what failed.
2. Explain the probable cause.
3. Suggest alternative approaches.
4. Document the issue for future reference.
5. Do not leave the system in a broken state — roll back if possible.
