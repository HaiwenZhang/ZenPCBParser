<a id="top"></a>
# 文档风格指南 / Documentation Style Guide

[English](#en)

<a id="zh"></a>
## 中文

本文档定义本项目的文档写作风格。后续 Agent 在新增或编辑项目文档前，应先阅读本文档。

## 适用范围

适用于：

- 项目架构文档。
- 版本号、changelog 和 policy 文档。
- 格式总结和转换说明。
- 需要长期保留在仓库中的 case 分析文档。
- Agent-facing instructions。

不应把以下内容写入长期文档：

- 临时 debug log。
- 一次性命令输出全文。
- 大段 raw parser output。
- 生成的测试输出目录。
- 未整理的 scratch analysis。
- 真实本地路径、私有客户/项目 case 名称或可识别样本名。

## 语言

- 跟随所在文件已有风格。
- `docs/CHANGELOG.md` 是双语文档，必须同时更新中文区和英文区。
- 面向用户或项目维护者的 policy / architecture 文档默认中英双语，中文在前。
- 纯 Agent 入口文档可以英文-only，例如 `AGENTS.md`。
- 技术标识保持固定写法：`AuroraDB`、`ODB++`、`SemanticBoard`、`AAF`、`AEDB`、`Larc`、`Parc`、`PartPad`、`FootPrintSymbol`、`PinList`。

## 结构

长期技术文档优先采用以下顺序：

1. 目的。
2. 适用范围。
3. 核心规则或核心概念。
4. 文件位置。
5. 工作流或决策指南。
6. 验证方式或示例。
7. 已知限制。

架构文档优先采用以下顺序：

1. 高层流程。
2. 责任边界。
3. 数据模型或转换模型。
4. 运行路径。
5. 扩展点。
6. 版本管理和验证。

Case notes 优先采用以下顺序：

1. 输入样本。
2. 问题现象。
3. 根因。
4. 修复。
5. 输出目录。
6. 关键计数和不变量。

## Changelog 条目

每条 `docs/CHANGELOG.md` 记录应说明：

- 改了什么。
- 影响哪条路径，例如 `ODB++ -> Semantic -> AuroraDB`。
- JSON schema 是否变化。
- 预期输出差异。
- 如果修复由具体 case 驱动，应记录重要验证结果。

Changelog 应短，但不能省略行为影响。

## 路径和引用

- 仓库文档中优先使用项目相对路径，例如 `targets/auroradb/exporter.py`。
- 不要在长期文档中写入真实本地绝对路径、私有 case 名称或可识别样本名。
- 需要说明样本或输出位置时，使用脱敏占位，例如 `<CASE_ROOT>/sample.tgz`、`<OUTPUT_ROOT>/case_output` 或 `private ODB++ sample`。
- 路径、命令、字段名和版本常量使用 code formatting。
- 不要在文档中粘贴大段生成 JSON、log 或完整文件 dump。

## 验证描述

记录验证时，优先使用简洁且可复现的信息：

- 使用的命令或工作流。
- 脱敏后的输入样本标识。
- 输出目录。
- 关键计数，例如 component count、part count、footprint count、arc count。
- 不变量，例如 `partpad_pin_issues == 0`。

示例：

```text
Sample: <CASE_ROOT>/sample.tgz
Output: <OUTPUT_ROOT>/case_output
Components: source=1572, semantic=1572, AuroraDB=1572
Invariant: partpad_pin_issues=0
```

## 写作风格

- 先准确，再追求完整。
- 使用短 section 和扁平 bullet list。
- 避免深层嵌套 bullet。
- 避免宣传式语言。
- 避免在长期文档中写入 `currently debugging` 这类临时表达。
- 术语在不同文件中保持一致。
- 实现说明应绑定到文件路径、函数名或数据字段。

## 生成物

- 不要把测试输出、临时日志、coverage output 或 parser output 放进项目根目录或 docs 目录。
- Case 输出应放在测试样本同级目录，或清晰命名的外部输出目录；写入文档时使用脱敏路径。
- 除非生成物本身需要提交，否则文档只记录路径和摘要。

## Agent 注意事项

Agent 应以最小、可长期维护的形式更新文档。只对当前调试会话有帮助的信息，应写在最终回复中，而不是写入仓库文档。

<a id="en"></a>
## English

[中文](#zh) | [Back to top](#top)

This guide defines the documentation style expected in this repository. Agents should read it before adding or editing project documentation.

## Scope

Use this guide for:

- Project architecture documents.
- Versioning, changelog, and policy documents.
- Format summaries and conversion notes.
- Case-analysis documents that are intended to remain in the repository.
- Agent-facing instructions.

Do not use long-lived docs for:

- Temporary debug logs.
- One-off command transcripts.
- Large raw parser outputs.
- Generated test output directories.
- Unreviewed scratch analysis.
- Real local paths, private customer/project case names, or identifiable sample names.

## Language

- Follow the surrounding file style.
- `docs/CHANGELOG.md` is bilingual and must be updated in both Chinese and English sections.
- User-facing policy or architecture docs should be bilingual by default, with Chinese first.
- Pure Agent entrypoint docs may be English-only, for example `AGENTS.md`.
- Keep technical identifiers unchanged: `AuroraDB`, `ODB++`, `SemanticBoard`, `AAF`, `AEDB`, `Larc`, `Parc`, `PartPad`, `FootPrintSymbol`, `PinList`.

## Structure

Prefer this order for durable technical docs:

1. Purpose.
2. Scope.
3. Core rules or concepts.
4. File locations.
5. Workflow or decision guide.
6. Verification or examples.
7. Known limitations.

For architecture docs, prefer:

1. High-level flow.
2. Ownership boundaries.
3. Data model or conversion model.
4. Runtime path.
5. Extension points.
6. Versioning and validation.

For case notes, prefer:

1. Input sample.
2. Symptom.
3. Root cause.
4. Fix.
5. Output directory.
6. Key counts and invariants.

## Changelog Entries

Every `docs/CHANGELOG.md` entry should state:

- What changed.
- Which path is affected, for example `ODB++ -> Semantic -> AuroraDB`.
- Whether JSON schemas changed.
- Expected output differences.
- Important verification results when a specific case drove the change.

Keep changelog entries short, but do not omit behavior impact.

## Paths And References

- Use project-relative paths in repository docs, for example `targets/auroradb/exporter.py`.
- Do not write real local absolute paths, private case names, or identifiable sample names in long-lived docs.
- When a sample or output location is needed, use sanitized placeholders such as `<CASE_ROOT>/sample.tgz`, `<OUTPUT_ROOT>/case_output`, or `private ODB++ sample`.
- Use code formatting for paths, commands, field names, and version constants.
- Do not include large generated JSON, logs, or full file dumps in docs.

## Verification Text

When recording verification, prefer concise, reproducible facts:

- Command or workflow used.
- Sanitized input sample identifier.
- Output directory.
- Key counts, for example component count, part count, footprint count, arc count.
- Invariants, for example `partpad_pin_issues == 0`.

Example:

```text
Sample: <CASE_ROOT>/sample.tgz
Output: <OUTPUT_ROOT>/case_output
Components: source=1572, semantic=1572, AuroraDB=1572
Invariant: partpad_pin_issues=0
```

## Style

- Be precise before being exhaustive.
- Prefer short sections and flat bullet lists.
- Avoid deep nested bullets.
- Avoid promotional language.
- Avoid temporary wording such as "currently debugging" in durable docs.
- Use stable terminology consistently across files.
- Keep implementation notes tied to file paths, functions, or data fields.

## Generated Artifacts

- Do not place test outputs, temporary logs, coverage output, or generated parser output in the project root or docs directory.
- Put case outputs next to the test case or under a clearly named external output directory; use sanitized paths when documenting them.
- Only document generated artifacts by path and summary unless the artifact itself is intentionally committed.

## Agent Notes

Agents should update docs in the smallest durable form that helps future work. If a detail is only useful for the current debugging session, keep it in the final response instead of adding it to repository docs.
