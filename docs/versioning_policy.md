<a id="top"></a>
# 版本号与变更日志规则 / Versioning And Changelog Policy

[English](#en)

<a id="zh"></a>
## 中文

本规则是项目中版本号更新和变更日志维护的统一依据。后续 Agent 在修改 parser、exporter、转换逻辑、CLI 行为或生成结果前，应先阅读本文档。

## 适用文件

项目版本号必须在以下位置保持一致：

- `version.py`
- `pyproject.toml`
- `docs/architecture.md`

项目级变更记录维护在：

- `docs/CHANGELOG.md`

格式级 parser / schema 版本维护在：

- `sources/aedb/version.py`
- `sources/auroradb/version.py`
- `sources/odbpp/version.py`
- `semantic/version.py`

## 规则

1. 项目级版本由 `version.py` 和 `pyproject.toml` 共同维护，两者必须一致。
2. 当项目版本变化时，必须同步更新 `docs/architecture.md` 中的 current-version 表。
3. 任何会改变生成文件、转换行为、解析行为、CLI 行为或其他用户可观察输出的修复，都必须更新 `docs/CHANGELOG.md`。
4. 如果 changelog 顶部版本仍是当前阶段的 active / unreleased 版本，相关修复可以追加到该版本条目中。
5. 如果 changelog 顶部版本已封版、已发布或已交付，新的用户可见修复必须 bump project patch version。
6. 如果用户要求本次修复独立版本，即使顶部版本刚更新过，也必须 bump project patch version。
7. 纯文档修改通常不需要更新 parser version 或 schema version；是否 bump project patch version 由项目负责人决定。
8. AEDB、AuroraDB source 或 ODB++ source parser 行为变化时，必须更新对应 `sources/<format>/version.py` 中的 parser version。
9. Semantic 转换行为变化时，必须更新 `semantic/version.py` 中的 `SEMANTIC_PARSER_VERSION`。
10. JSON 字段新增、删除、重命名、字段含义变化或 schema 结构变化时，必须更新对应 JSON schema version。
11. 只影响 AuroraDB 文件输出且不改变 JSON 结构的修改，不更新 JSON schema version。
12. AuroraDB target exporter 当前没有独立 target-exporter version；影响输出的 exporter 修复至少必须记录到 `docs/CHANGELOG.md`，并按当前发布策略决定是否 bump project patch version。
13. `docs/CHANGELOG.md` 必须双语维护：中文区和英文区都要添加等价条目。
14. Changelog 条目应说明行为变化、影响路径、schema 是否变化，以及预期输出差异。
15. 版本更新后至少应做轻量验证。
16. 针对具体 case 的修复，应在最终回复中记录脱敏后的样本标识、脱敏后的输出目录、关键计数或不变量；如果该 case 定义了重要行为，也应把脱敏后的验证摘要写入 changelog。

## 决策指南

用户可见修复按以下方式处理：

- 当前顶部版本仍 active / unreleased：可以追加到当前版本。
- 当前顶部版本已封版、修复需要独立记录，或用户要求独立版本：bump project patch version。

示例：

- ODB++ parser 逻辑修复并改变 source JSON 内容：更新 `ODBPP_PARSER_VERSION`，通常 bump project patch，并更新 `docs/CHANGELOG.md`。
- Semantic adapter 修复导致 AuroraDB 输出变化但不改变 Semantic JSON schema：如果 Semantic 转换行为变化，更新 `SEMANTIC_PARSER_VERSION`；通常 bump project patch；更新 `docs/CHANGELOG.md`；不更新 JSON schema。
- AuroraDB exporter 修复只改变 `.lyr`、`layout.db` 或 `parts.db`：更新 `docs/CHANGELOG.md`；如果当前版本已封版，通常 bump project patch；不更新 JSON schema。
- 纯文档说明修正：更新对应文档；是否 bump project version 由项目负责人决定。

## 验证记录

尽量记录以下一种或多种验证信息：

- 针对修改 helper / mapping 的轻量断言。
- 对编辑过的 Python 模块运行 `python -m compileall`。
- 将 case 转换输出放在测试样本同级或外部清晰命名目录，不放在项目根目录。
- 文档和 changelog 中只记录脱敏后的样本标识和输出目录，不记录真实本地路径或私有 case 名称。
- 对比 source、Semantic、AAF、AuroraDB 的关键对象计数。
- 记录明确不变量，例如 `partpad_pin_issues == 0` 或 source component count 等于 AuroraDB component placement count。

<a id="en"></a>
## English

[中文](#zh) | [Back to top](#top)

This policy is the canonical project rule for version updates and changelog entries. Agents should read it before changing parser, exporter, conversion, CLI behavior, or generated output.

## Required Files

Project version must stay consistent in:

- `version.py`
- `pyproject.toml`
- `docs/architecture.md`

Project-level changes are recorded in:

- `docs/CHANGELOG.md`

Format-level parser and schema versions are maintained in:

- `sources/aedb/version.py`
- `sources/auroradb/version.py`
- `sources/odbpp/version.py`
- `semantic/version.py`

## Rules

1. Project-level version is maintained by `version.py` and `pyproject.toml`; both files must agree.
2. `docs/architecture.md` current-version tables must be updated when the project version changes.
3. Any fix that changes generated files, conversion behavior, parser behavior, CLI behavior, or other user-visible output must update `docs/CHANGELOG.md`.
4. If the top changelog version is an active, unreleased version for the current work stage, related fixes may be appended to that version entry.
5. If the top changelog version is sealed, released, or already handed off, new user-visible fixes must bump the project patch version.
6. If the user asks for an independent version for the current fix, bump the project patch version even if the top version was recently updated.
7. Documentation-only changes normally do not require parser or schema version bumps. Whether to bump the project patch version for documentation-only work is a project-owner decision.
8. AEDB, AuroraDB source, or ODB++ source parser behavior changes must update the corresponding parser version in `sources/<format>/version.py`.
9. Semantic conversion behavior changes must update `SEMANTIC_PARSER_VERSION` in `semantic/version.py`.
10. JSON field additions, removals, renamed fields, changed field meanings, or schema structure changes must update the corresponding JSON schema version.
11. Changes that only affect AuroraDB file output and do not change JSON structure do not update JSON schema versions.
12. AuroraDB target exporter currently has no separate target-exporter version. Output-affecting exporter fixes must at least be recorded in `docs/CHANGELOG.md`; bump the project patch version when required by the active release policy.
13. `docs/CHANGELOG.md` entries must be bilingual: add equivalent entries in both the Chinese and English sections.
14. Changelog entries should state the behavior change, impacted conversion path, whether schemas changed, and expected output differences.
15. Version updates should be verified with at least a lightweight check.
16. Case-driven fixes should record the sanitized sample identifier, sanitized output directory, and key counts or invariants in the final response. If the case materially defines the behavior, include the sanitized verification summary in the changelog entry.

## Decision Guide

Use one of these paths for a user-visible fix:

- Append to the current top version when that version is still active and unreleased.
- Bump the project patch version when the current top version is sealed, when the fix should stand alone, or when the user requests an independent version.

Examples:

- A parser logic fix that changes ODB++ source JSON content: bump `ODBPP_PARSER_VERSION`, usually bump project patch, update `docs/CHANGELOG.md`.
- A Semantic adapter fix that changes generated AuroraDB but not Semantic JSON schema: bump `SEMANTIC_PARSER_VERSION` if semantic conversion behavior changed, usually bump project patch, update `docs/CHANGELOG.md`; do not bump JSON schema.
- An AuroraDB exporter fix that changes `.lyr`, `layout.db`, or `parts.db` only: update `docs/CHANGELOG.md`, usually bump project patch if the active version is sealed; do not bump JSON schema.
- A documentation-only clarification: update the relevant docs; project version bump is optional and should follow project-owner preference.

## Verification Notes

When possible, include one or more of:

- A lightweight unit-style assertion for the changed helper or mapping.
- `python -m compileall` for edited Python modules.
- A case conversion output directory under the test case location, not inside the project root.
- Docs and changelog entries should only record sanitized sample identifiers and output directories, not real local paths or private case names.
- Count checks that compare source, Semantic, AAF, and AuroraDB objects.
- Specific invariants, for example `partpad_pin_issues == 0` or source component count matching AuroraDB component placement count.
