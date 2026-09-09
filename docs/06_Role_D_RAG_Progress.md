# D 模块：RAG 实现、验收与历史记录

> 当前实现基线：`dev@53d70bc`。本次购物交付；time主流程延期，不再等待C为本轮实现时间编排。以下将静态事实、待验收与历史测量分开，取消无证据的综合完成百分比。

## 1. 职责与实现现状

D负责 `rag/`、历史种子、检索/评测，配合B历史接口、C RAG adapter和A证据展示。

| 内容 | 代码现状 |
|---|---|
| 种子 | data/history_records.json，共500条，购物250、时间250；本轮按JSON分组核对 |
| 检索 | FastAPI + jieba搜索分词 + BM25，按类型过滤、按标题去重 |
| 实时数据 | 尝试拉取当前用户的B历史，按ID合并，实时记录优先 |
| 契约 | 仅返回RagEvidence字段，失败/无命中不编造 |
| C接入 | C通过HTTP调用D，不再使用mock_rag主链路 |
| 工程 | RAG已纳入BAT、screen与Docker Compose配置 |
| 评测 | 检索指标、关键词接地、规则生成侧指标及测试文件已存在 |

“已存在实现”不等于该基线所有评测/部署均已重新通过。时间种子与组件测试保留，不将它们算作已交付的时间产品。

## 2. 数据流与限制

```text
用户反馈 → B histories
                    ↘
静态JSON（首次缓存） → D按用户拉取实时历史 → 按ID合并
  → 按case_type过滤 → jieba/BM25 → 标题去重 → RagEvidence
  → C正反方/法官上下文、report与trace
```

每次检索都会尝试拉取实时历史，当前只请求page=1、page_size=1000，不是无限分页同步；拉取失败时保留静态数据。新反馈只有在保存、读取、过滤成功后才可能成为命中，不保证立即命中。

B当前历史GET过滤is_deleted=0；软删除记录虽然仍在数据库，但不保证经当前HTTP链路继续用于RAG。种子属于演示数据，不可冒充当前用户的真实消费经历。

| 配置 | 默认 | 含义 |
|---|---|---|
| RAG_LIVE_RECORDS | 1 | 非1时不拉取实时历史 |
| BACKEND_HISTORY_URL | http://127.0.0.1:8000/api/history | 后端历史接口 |
| HISTORY_TIMEOUT | 1.0秒 | 以data_loader.py实际赋值为准 |
| C的RAG_SEARCH_URL | http://127.0.0.1:8001/api/rag/search | C到D的地址 |

容器中使用服务名backend/rag，不使用指向自身的localhost。当前没有向量或混合检索。

## 3. 返回与失败语义

`POST /api/rag/search` 接受user_id/case_id/case_type/query/top_k，成功data.results为数组，元素包含id/title/content/score/source/case_type/tags/created_at。

- score是BM25排序分数，不是概率。
- 正常无结果返回[]；C记录rag_search completed。
- 服务断开或非法响应时C adapter抛给编排层记录failed，再fallback=[]。
- RAG不负责最终建议。判决规则、LLM说明、前端展示分别属于C/A，不能用检索成功证明这些层都成功。

## 4. 测试与脚本

| 文件 | 用途 |
|---|---|
| tests/test_rag.py | 检索、契约、类型/用户过滤、种子和标准查询 |
| tests/test_rag_data_loader.py | 实时字段映射、合并、失败回退、开关 |
| tests/test_rag_adapter.py | C-D HTTP/body/返回契约 |
| tests/test_dialogue_quality_metrics.py | 证据上下文、引用和关键词接地计算 |
| tests/test_rag_standard_metrics.py | 检索指标与规则生成侧指标 |
| rag/evaluate_rag.py | 四组历史标准查询与命中 |
| rag/evaluate_rag_standard.py | 检索侧指标；--live额外调用后端评估购物输出 |
| rag/evaluate_dialogue_quality.py | 对话/证据代理指标 |
| rag/e2e_verify.py | 辅助购物HTTP链路；不是完整UI/提醒验收 |

`faithfulness` 实际计算报告词项落在证据中的比例，`answer_relevancy` 是预设要点命中比例；不能宣传为语义正确率或人工评审结果。相关集合依靠标题关键词建立，结果与种子、k值、规则有关。

命令从仓库根目录执行，先按 [测试计划](05_TestPlan.md) 配置隔离环境：

```powershell
uv run --frozen pytest -p no:cacheprovider tests/test_rag.py tests/test_rag_data_loader.py tests/test_rag_adapter.py tests/test_dialogue_quality_metrics.py tests/test_rag_standard_metrics.py
uv run --frozen uvicorn retriever:app --app-dir rag --host 127.0.0.1 --port 8001
```

测试与服务在独立终端运行。离线评测：

```powershell
$env:RAG_LIVE_RECORDS = "0"
uv run --frozen python rag/evaluate_rag.py --out "$env:TEMP/decisionjury-rag-eval.json"
uv run --frozen python rag/evaluate_rag_standard.py --out "$env:TEMP/decisionjury-rag-standard.json"
```

实时脚本需要后端和RAG，先注册脚本使用的测试user_id。`rag/e2e_verify.py` 支持E2E_USER_ID/BACKEND_URL/RAG_URL；其默认e2e_user不会自动注册。脚本会写演示数据，使用隔离实例。B提醒导入已修复，但本轮没有复跑该实时脚本，不把它列为必然成功的命令。

## 5. 本轮待验收与分工

| 事项 | 配合 | 通过条件 |
|---|---|---|
| 购物检索/引用截图 | C/A | 实际命中进入上下文/报告，来源准确 |
| B实时历史更新 | B | 新复盘候选可加载，过滤/删除行为如实展示 |
| 提醒分支联调 | B | Reminder导入已修复，继续核验页面与复盘链路 |
| BM25空/失败 | C | 空为completed，故障为failed，均不伪造证据 |
| 当前评测复现 | D/测试 | 记录commit、种子、k、模式、实际数值 |
| 部署互通 | E | 服务名/端口和数据源可达，健康检查之外有业务验收 |

time端到端、向量/混合检索属于后续选题，不是本轮必须等待的依赖。A已有证据/庭审组件，仍需以真实页面确认显示效果。

## 6. 历史测量（非本次复跑）

以下保留原D交付日志，缺少与当前基线一一对应的运行环境和完整原始产物，不可直接作为新答辩的最新性能数据：

- 早期定向测试记录：29 passed。
- 早期购物联调记录：命中3条，rag_search completed，report.final_decision=delay。
- 历史查询优化记录：四组标准查询由3组expected_hit变为4组；其中两组time只属组件检索。
- 对话代理指标记录：retrieval_hits=3、evidence_in_judge_context=true、report_cites_evidence=true、grounded_keyword_hit=true、token_overlap=16。

原top_k=5检索测量：

| 查询 | Precision | Recall | MRR | NDCG |
|---|---|---|---|---|
| 降噪耳机 | 0.4 | 0.33 | 1.0 | 0.55 |
| 学习用品 | 0.8 | 0.14 | 1.0 | 0.85 |
| 社团活动（历史组件） | 0.6 | 0.25 | 0.5 | 0.53 |
| 技术分享（历史组件） | 0.4 | 0.25 | 1.0 | 0.55 |

原生成侧记录：耳机faithfulness=0.18、answer_relevancy=1.0、延迟约1.06秒；学习用品为0.11/0.5/约0.13秒。真实模型/fallback状态未在这些记录中充分证明，不能称为DeepSeek真实端到端性能。词项重合低也不直接证明判决错误。

## 7. 历史提交与材料

原开发分支为 `feature/rag-500-linkage`，相关能力已存在于本次dev基线；不再写“等待合入”作为当前状态。原记录保留以下提交标识，具体归属和合并历史以Git为准：

```text
6b95b43  8ab0b21  344a29a  3277999  4c35073
1c9b032  beb33cc  157f199  cbde8e8
```

旧文档日期“2020-07”不可靠，本次不替它推定真实验收日期。旧本地产物名为rag_eval_result.json、rag_dialogue_quality_result.json、rag_std_retrieval.json、rag_std_full.json；文件名不证明产物当前存在或结果有效。

新的截图和指标必须注明版本/模式，避免提交数据库、密钥和本地评测输出。正式交付范围以 [MVP](01_MVP.md) 为准。
