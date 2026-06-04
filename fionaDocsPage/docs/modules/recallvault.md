# RecallVault

RecallVault is Fiona's persistent "remembrance" store. It allows the system (and future agents) to save, search, and manage small snippets of information categorized for different contexts.

## Purpose

- **Long-term Memory**: Store facts, configuration snippets, or notes that persist across sessions.
- **Categorization**: Group information into categories such as `general`, `project`, `network`, etc.
- **Agent Integration**: Provides the primary memory interface for future AI reasoning tasks.

## Commands

### Save a remembrance
```bash
fiona recall remember "phi-host" "192.168.1.10" --category network
```

### Search remembrances
```bash
fiona recall search "phi"
```

### Forget an entry
```bash
fiona recall forget "phi-host"
```

### List categories
```bash
fiona recall categories
```

### Clear the vault
```bash
fiona recall clear
```

## TUI Integration

The **Recall** page in the `fiona cli` TUI displays the 10 most recent snippets from the vault and updates in real-time.

## Storage

Data is stored as a JSON array of objects in:
`~/.config/fiona/recallvault.json`
