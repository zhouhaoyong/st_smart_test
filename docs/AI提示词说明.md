# AI 提示词索引

> 汇总系统中所有 AI 功能使用的提示词，便于统一管理。提示词一律以 `.md` 文件维护、禁止硬编码，业务代码只负责读取并传递。文件名列为相对项目根目录的位置。

## 需求补全（单需求）

| 简介 | 文件 |
|---|---|
| 单需求补全多轮追问（输出 JSON） | `backend/docs/prompt/requirement_refinement.md` |
| 追问结束后整理成完整需求正文 | `backend/docs/prompt/requirement_compose.md` |
| 需求自查维度预置关键词清单 | `backend/docs/prompt/requirement_keywords.md` |
| 核对最终正文与用户输入一致性 | `backend/docs/prompt/requirement_result_comparison.md` |

## 需求合并（多需求）

| 简介 | 文件 |
|---|---|
| 多份需求合并多轮追问（输出 JSON） | `backend/docs/prompt/requirement_merge_refinement.md` |
| 合并追问结束后整理成合并正文 | `backend/docs/prompt/requirement_merge_compose.md` |
| 无追问的一次性需求合并 | `backend/docs/prompt/test_workbench_requirement_merge.md` |

## 测试用例生成

| 简介 | 文件 |
|---|---|
| 用例生成前预检追问（输出 JSON） | `backend/docs/prompt/test_workbench_test_case_preflight.md` |
| 依据需求与确认事实生成用例（输出 JSON） | `backend/docs/prompt/test_workbench_test_case_generation.md` |

## API 测试与平台模型能力

| 功能 | 提示词文件 |
|---|---|
| API 测试用例生成 | `backend/docs/prompt/api_generate_testcases.md` |
| AI 模型能力检测 | `backend/docs/prompt/model_capability_probe.md` |
