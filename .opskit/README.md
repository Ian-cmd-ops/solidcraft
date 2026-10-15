# SolidCraft as an OpsKit member

This branch is OpsKit-aware: `.opskit/pack.yml` declares a subagent
(`@solidcraft-dev`), a skill (`solidcraft-workflow`) and four methodology docs.
OpsKit: https://github.com/CascadeSTEAM/opskit (see its `docs/opskit-aware.md`).

Validate after any change, from an OpsKit checkout:

    python3 bin/opskit-aware.py check /path/to/solidcraft-kit
