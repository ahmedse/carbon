# Archetypes — Host System Packs

An **archetype** is a reusable pack that lets Pulse onboard a host system (or a
self-contained persona) in minutes. Each archetype lives in its own directory
under `archetypes/<name>/` and is rendered into a concrete instance config.

## Directory Structure

```
archetypes/<name>/
├── archetype.yaml            # REQUIRED — metadata (name, display_name, version, description, tags, icon)
├── instance.template.yaml    # REQUIRED — Jinja2 template → instances/<name>/instance.yaml
├── playbook/                 # optional — persona.j2, domain.j2 (system-prompt blocks)
├── domain/                   # optional — connectors.yaml (host integration stubs)
└── skills/                   # optional — reusable skill YAMLs (prompt_template / tool skills)
```

## Required Files

| File | Purpose | Required? |
|------|---------|-----------|
| `archetype.yaml` | `name`, `display_name`, `version`, `description` (also `tags`, `icon`, `requires`) | ✅ yes |
| `instance.template.yaml` | Jinja2 template producing a full `instance.yaml` (persona, tools, cognition, nav) | ✅ yes |
| `playbook/persona.j2` | Identity + tone for the agent | ⬜ recommended |
| `playbook/domain.j2` | Domain rules (metrics, units, forbidden terms) | ⬜ recommended |

`instance.template.yaml` must render to a config containing at minimum:
`name`, `display_name`, `persona`, `domain`, and `tools` (with
`tools.open_entity.entity_types` non-empty — see `tests/test_wave09_archetype_packs.py`).

## How to Create a New Archetype

1. **Pick a name** — kebab-case, e.g. `my-host`.
2. **Create the directory + metadata**:
   ```bash
   mkdir -p archetypes/my-host
   ```
   Write `archetype.yaml`:
   ```yaml
   name: my-host
   display_name: "My Host"
   version: 0.1.0
   description: "What this archetype does."
   tags: [category]
   icon: "database"
   requires:
     pulse_version: ">=0.3.0"
     auth_mode: local
     storage_mode: standalone
   ```
3. **Write `instance.template.yaml`** — a Jinja2 template. Available template
   vars: `instance_name`, `display_name`, `description`, `archetype_name`,
   `archetype_version`, `created_at`, `timezone`, `languages`,
   `persona_tagline`, `persona_audience`. Copy an existing pack (e.g.
   `archetypes/twin-mind/`) as a starting point and adapt the sections.
4. **Add tools config** — `tools.open_entity.entity_types` (entity routing),
   `tools.api_resolver` / `tools.param_resolution` / `tools.slug_resolution`
   (dispatch), `tools.review_rules` (redaction).
5. **Validate the template renders**:
   ```bash
   venv/bin/python -c "
   from core.archetypes import render_instance_config, validate_instance_config_or_raise
   cfg = render_instance_config('my-host', 'test-instance', 'Test Instance')
   validate_instance_config_or_raise(cfg)
   print('OK —', len(cfg.get('tools', {}).get('open_entity', {}).get('entity_types', [])), 'entity types')
   "
   ```
6. **Optional — extract from an existing instance** (creates a pack skeleton):
   ```bash
   venv/bin/python -m cli.main archetype extract <instance-name>
   ```

## How to Test an Archetype

The Wave 9 smoke tests (`tests/test_wave09_archetype_packs.py`) cover: loading,
template rendering (persona/domain/tools present), registry API fields, YAML
validity, and domain-purge checks. Add your archetype name to `ALL_ARCHETYPES`
in that file, then run:

```bash
venv/bin/python -m pytest tests/test_wave09_archetype_packs.py -q
```

You can also verify the rendered instance config via the CLI validator:
```bash
venv/bin/python -m cli.main new --name test-<name> <archetype-name>
```
