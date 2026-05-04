# Security

## Purpose

Aurora Translator processes local design files. Treat source files, generated
JSON, logs, and output directories as potentially sensitive.

## Rules

- Do not upload private board data, generated JSON, logs, or parser dumps to
  external services.
- Do not record real local absolute paths or private case names in long-lived
  docs.
- Validate archive entry sizes and paths before extraction or parsing.
- Avoid writing outside the requested output directory.
- Do not run destructive cleanup commands unless the user requested them or
  explicitly approved them.
- Prefer dependency changes that are necessary, pinned by the project tooling,
  and documented in the relevant plan or changelog.

## Secrets

- Do not commit tokens, credentials, license keys, or machine-specific config.
- If a command prints sensitive environment data, summarize only the safe
  outcome in the final response.

## External References

External docs may be summarized into `docs/references/` when they are useful for
agents, but keep them concise and cite the source or project context.
