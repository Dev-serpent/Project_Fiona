# Getting Started

Fiona can be run directly from a source checkout:

```bash
cd Fiona
python3 -m fiona.cli <command>
```

Examples:

```bash
python3 -m fiona.cli edit
python3 -m fiona.cli list
python3 -m fiona.cli camcoms smoke-test
python3 -m fiona.cli phiconnect
python3 -m fiona.cli dataclient
```

If the console script is installed and on `PATH`, use:

```bash
fiona <command>
```

## Shared GUI

Open the shared Fiona GUI:

```bash
python3 -m fiona.cli edit
```

Panel order:

```text
CamComs -> Vsee -> Bindings -> Raw Json -> Debug -> Host
```

Panel roles:

- `CamComs`: generate identities, export public keys, encrypt/decrypt messages, send encoded envelopes, and run a local smoke test.
- `Vsee`: edit 3D points and edges and render connected wireframe shapes.
- `Bindings`: edit QuikTieper app launchers and shortcut bindings.
- `Raw Json`: edit the QuikTieper config directly.
- `Debug`: restricted project file editor for `tests`, `scripts`, `QuikTieper`, and `CamComs`.
- `Host`: inspect host config, trusted devices, key paths, and audit logs.

## Standalone Apps

```bash
python3 -m fiona.cli vsee
python3 -m fiona.cli phiconnect
python3 -m fiona.cli dataclient
```

## Useful First Checks

```bash
python3 -m fiona.cli list
python3 -m fiona.cli camcoms paths
python3 -m fiona.cli camcoms smoke-test
python3 -m fiona.cli seeondesk status
```
