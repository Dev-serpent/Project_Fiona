# Execution Rules

Rules for safely executing actions once planned and selected.

## Before Execution

### Verify Directory
- If creating directories, verify the parent exists first with `ls`.
- Use absolute paths for all file operations.

### Quote Paths
- Always quote file paths containing spaces with double quotes.
- Example: `mkdir "/path/with spaces/dir"`, not `mkdir /path/with spaces/dir`.

### Prefer Inspection First
- Before destructive operations: inspect with `ls`, `git status`, or `read`.
- Before `rm`: verify the path is correct and nothing valuable is there.
- Before `git reset` or `git rebase`: inspect `git log --oneline -10`.

## During Execution

### Chain Dependent Operations Sequentially
- Use `&&` when commands depend on each other:
  ```
  git add file.py && git commit -m "Fix bug"
  ```
- Use `;` only when order doesn't matter.
- Do NOT use `cd` + command patterns — use `workdir` parameter.

### Parallel Independent Operations
- When operations are independent, dispatch them in parallel.
- Multiple `read`, `grep`, `glob`, `edit`, or independent `bash` calls can
  run concurrently.

### Limit Scope
- Change the smallest possible amount of code.
- Preserve existing functionality.
- Avoid unnecessary rewrites.
- Do not refactor unrelated code.

## After Execution

### Verify
- Check `git diff --stat` to confirm only intended files changed.
- Run relevant tests.
- Verify the change doesn't break existing behavior.

### Record
- Note what changed and why in the session summary.
- If tests were added/modified, report the test count.

## Approval System Integration

For actions requiring human approval:
1. Submit a plan via the approval system (`FionaCore/approval.py`).
2. Wait for approval (or timeout).
3. On approval, execute the planned actions.
4. On denial, report and ask for revised instructions.
5. On timeout, ask whether to continue waiting or abort.

Use `fiona approval` CLI subcommand or the `ApprovalManager` API for
programmatic approval flow.
