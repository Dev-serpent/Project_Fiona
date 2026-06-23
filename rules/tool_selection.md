# Tool Selection Rules

Choosing the right tool or action is critical to safe and effective
orchestration. Follow these rules when selecting what to use.

## Decision Tree

1. **Is this a read-only information need?**
   - Use `grep` for content search.
   - Use `glob` for file pattern search.
   - Use `read` to view file contents.
   - Use `bash` with `ls` for directory listings.
   - Use `webfetch` or `websearch` for external information.
   - Use `task` (explore agent) for comprehensive codebase exploration.

2. **Is this a file modification?**
   - Use `edit` for targeted string replacements — always prefer this over
     rewriting entire files.
   - Use `write` only when creating new files or completely overwriting an
     existing file after reading it first.
   - Never use `bash` with `sed`, `awk`, `echo >`, or `cat <<EOF` for file
     modifications.

3. **Is this a command execution?**
   - Use `bash` for git, npm, pip, systemctl, docker, and other tool commands.
   - Prefer inspection commands first (e.g., `ls` before `rm`, `git status`
     before `git add`).
   - Chain dependent commands with `&&`, not `;`.
   - Use `workdir` parameter instead of `cd` commands.

4. **Is this a complex multi-step task?**
   - Use `task` with the appropriate subagent type.
   - Provide a detailed prompt with clear inputs and expected outputs.
   - Specify whether the agent should write code or only do research.

5. **Is this a security concern?**
   - Use `security-engineer` for security reviews.
   - Use `web-pentester` for web application testing.

## Risk Assessment

| Risk Level | Examples | Action |
|---|---|---|
| Low | Reading files, searching, non-destructive queries | Proceed autonomously |
| Medium | Writing new code, modifying non-critical files | Proceed, but verify |
| High | Deleting files, modifying infrastructure, running with sudo | Get human approval |

## Action Selection Priority

When an action can be achieved through multiple tools:

1. **Read-only tools first** — `read`, `grep`, `glob`, `websearch`.
2. **Precise editing tools** — `edit` with exact string matches.
3. **File creation tools** — `write` for new files (after verifying nothing
   suitable exists).
4. **Bash commands** — only when no specialized tool fits (e.g., git
   operations, build commands, service management).
5. **Task agent** — for multi-step or exploratory work that doesn't fit a
   single tool call.
