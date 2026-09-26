# kylin-memory-bench

把智能体的长期记忆变成可复查的任务、运行证据和六维分数。它向同一款智能体连续发送跨会话任务，再核对回复、实际写出的文件和可观察的记忆文件；每个得分都有检查项与证据来源。

**当前状态：框架已在本机用虚构替身跑通；KylinBot、OpenClaw 的真实成绩尚未产生。** [样例分数](examples/fixture-result.json)与[雷达图](examples/fixture-radar.svg)明确标为 `synthetic/fixture`，只证明流水线能识别故意制造的错误。真实评测须在 openKylin 上安装两款智能体、配置专用测试身份后运行。

[两页项目介绍 PDF](docs/intro.pdf)可供快速评审；完整测试方法见[方案文档](docs/method.md)。

## 一条命令看结果

需要 Python 3.10+。替身不需要网络或额外依赖：

```bash
./run-fixture.sh
```

脚本打印新建的 `out/fixture-...` 目录，其中 `result.json` 保存原始回复、文件快照、逐项判定和六维分；`report.txt` 给人读原因；`radar.svg` 可直接在浏览器打开。同样的任务与证据产生同样的分数。默认整批任务六项，两个虚构替身各跑一轮。`Synthetic reference` 为 100，`Synthetic faulty` 为 19.45；**它们不是 KylinBot 或 OpenClaw 的表现**。

## 测什么

| 能力 | 跨会话任务 | 可核对的结果 |
|---|---|---|
| 长期保持 | 记下代号，隔开无关任务后再问 | 新会话回答代号 |
| 记忆调用 | 记下负责人和格式后另起会话 | 两个字段均正确 |
| 动态更新 | 联系人更正后再问 | 只用新值，不再复用旧值 |
| 相近区分 | 记住名字相近的两个任务 | 两个日期各归其主 |
| 边界识别 | 临时验证码明确不许长期保存 | 新会话不泄露；可观察的记忆文件不含验证码 |
| 任务复用 | 记下报表习惯后要求执行 | 回复与实际写出的导出配置都正确 |

[任务数据](data/tasks.json)只含虚构姓名、项目和验证码。评分器支持 `reply_equals`、`file_equals`、`forbidden_text`、`memory_forbidden` 四种检查。答错记为 `fail`，缺少可观察证据记为 `missing`，两者都不得分。边界项若没有暴露可读取的记忆记录，`not-persisted` 就是 `missing`，不会凭“没有看到”奖励分数。任务复用同时查回复与文件，防止只凭“我已完成”拿满分。

## 接真实智能体

在 openKylin 上准备 Python 3.10+，并安装网关客户端依赖：

```bash
python3 -m pip install -r requirements.txt
```

按 [KylinBot Gateway 自动测试脚本](https://gitee.com/openkylin/kylin-botshell/tree/develop-for-skill-autotest)配置 KylinBot；它的 `kylinbot.v1` WebSocket 协议在 `ws://127.0.0.1:42617/ws/chat` 连接后发送 `connect`、`message`，并以 `done.full_response` 作为最终回复。适配器可按上游的 `/admin/paircode/new`、`/pair` 接口自动与本机网关配对；远端网关则须把令牌放入环境变量 `KYLINBOT_WS_TOKEN`。适配器使用 Authorization header，不主动把令牌写进结果。`configs/kylinbot.example.json` 可改网关地址和超时。

按 [OpenClaw 官方 agent CLI](https://docs.openclaw.ai/cli/agent)安装并启动 Gateway。用[官方 agents 命令](https://docs.openclaw.ai/cli/agents)建立专门的测试身份，例如 `openclaw agents add kmb-test --workspace ~/.openclaw/workspace-kmb-test --non-interactive`；`configs/openclaw.example.json` 的 `agent_id` 默认就是 `kmb-test`。适配器调用 `openclaw agent --agent ... --session-key ... --message-file ... --json`；每个任务的不同会话有不同 key，同一批次自动加唯一运行 ID。[官方记忆说明](https://docs.openclaw.ai/concepts/memory)介绍 `MEMORY.md`、`USER.md` 和 `memory/*.md`。不要用默认临时状态的 `agent exec` 测跨会话记忆。

运行前给两款智能体各自准备**干净、专用的**测试身份与工作区；把 `KMB_OPENCLAW_WORKSPACE` 指向 OpenClaw 的 agent 工作区，把 `KMB_KYLINBOT_MEMORY_ROOT` 指向 KylinBot 可观察的记忆文件根目录。若后者实际版本不以文件暴露记忆，留空即可，报告会把持久化检查记为缺证据。两款 agent 应使用可比的模型与设置；把版本、模型和环境写入评测记录。完成配置后在云端 openKylin 运行：

```bash
./run-live.sh
```

CLI 也支持任意配置的批量对比，例如 `python3 -m kylin_memory_bench --dataset data/tasks.json --agent configs/kylinbot.example.json --agent configs/openclaw.example.json --output out/my-run --max-seconds 1800`。`--agent` 可重复，`--case retention-01` 可先跑最小连通测试。真实失败会留下错误记录与 `missing`，绝不会退回替身数据。结果可能包含真实回复和记忆文件；公开前先删去私人信息与令牌。

## 任务书逐项对应

| 评审项 | 权重 | 现在可检查的产物 |
|---|---:|---|
| 任务定义与通用性 | 15% | [六项跨会话任务](data/tasks.json)、统一 agent 接口 |
| 数据设计质量 | 25% | 六项虚构样本、答案与禁用值、回复及文件验证项；下一轮需扩充每维多样本 |
| 自动评分能力 | 25% | [评分器](kylin_memory_bench/scoring.py)、逐项原因与证据来源；缺证据不给分 |
| 稳定性与可复现性 | 15% | 数据及配置指纹、隔离输出目录、运行 ID、[合同测试](tests/test_scoring.py) |
| 指标完整性 | 10% | 六维与总分、[结构化样例](examples/fixture-result.json)、[雷达图](examples/fixture-radar.svg) |
| 创新与工程落地 | 10% | 回复、记忆和实际文件共同裁决；两个真实适配器、[一键脚本](run-live.sh)、[.deb 构建脚本](packaging/build-deb.sh) |

完整的测试前提、数据生成、结果收集和评分流程见[评测方案](docs/method.md)。任务书的交付还包括 openKylin 桌面上两款智能体的真实比较与 3–5 分钟完整录屏。当前仓库没有这些证据，也没有官方评委分数。六维各只有一条样本，适合作为首轮连通和评审演示，不足以声称统计显著差异。

## 构建与贡献

`./packaging/build-deb.sh` 使用 Python 标准库在本机生成 `dist/kylin-memory-bench_0.1.0_all.deb`；归档结构已检查，安装与依赖可用性仍需在 openKylin 验证。介绍 PDF 可用 `python3 scripts/build-intro.py docs/intro.pdf` 重新生成，需另装 `reportlab`。测试命令：`python3 -m unittest discover -s tests`。源代码按 [MIT](LICENSE) 发布；问题报告和 PR 说明见 [CONTRIBUTING.md](CONTRIBUTING.md)。
