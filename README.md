# kylin-memory-bench

把智能体的长期记忆变成可复查的任务、运行证据和六维分数。它向同一款智能体连续发送跨会话任务，再核对回复、实际写出的文件和可观察的记忆文件；每个得分都有检查项与证据来源。

**真实全批 `live/observed`（2026-09-26）：**同一台 openKylin 3.0 VM 上，KylinBot 0.7.5 得 25.00/100，OpenClaw 2026.9.6 得 30.55/100。两者共用阿里云百炼 `qwen-plus`，各完成 14 个 live turns，均无适配器错误。查看[逐项报告](examples/live-openkylin-20260926-report.txt)、[六维雷达图](examples/live-openkylin-20260926-radar.svg)和[4 分 47 秒真实桌面录屏](examples/live-openkylin-20260926-demo.mp4)。每维仅一例；KylinBot 实际将记忆存于 SQLite，旧文件观察器把 `boundary-01` 的 `not-persisted` 判为 `MISSING`，这 5.55 分差不能当作稳定的系统排名。

换用逐案例 SQLite 只读观察器重跑后，KylinBot 33.33、OpenClaw 30.55；KylinBot 的禁存项被真实数据库记录判为 `FAIL`，但它在另一个案例遇到一次超时，只完成 13/14 步。查看[第二批报告](examples/live-openkylin-20260926-sqlite-report.txt)、[雷达图](examples/live-openkylin-20260926-sqlite-radar.svg)与[来源及错误摘要](examples/live-openkylin-20260926-sqlite-summary.json)。两批同题的相对顺序已翻转，当前数字不支持稳定排名。

[替身结果](examples/fixture-result.json)与[替身雷达图](examples/fixture-radar.svg)标为 `synthetic/fixture`，只证明流水线能识别故意制造的错误，不是两款真实智能体的成绩。

[两页项目介绍 PDF](docs/intro.pdf)可供快速评审；完整测试方法见[方案文档](docs/method.md)。

## 一条命令看结果

需要 Python 3.10+。从公开仓库取代码后，替身不需要网络或额外依赖：

```bash
git clone https://github.com/logxio/kylin-memory-bench.git
cd kylin-memory-bench
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

双智能体、`.deb` 和桌面录屏的操作顺序见 [openKylin 3.0 实跑指南](docs/live-openkylin.md)。在 openKylin 3.0 上可下载 [v0.1.0 发行包](https://github.com/logxio/kylin-memory-bench/releases/download/v0.1.0/kylin-memory-bench_0.1.0_all.deb) 安装；`apt` 会从系统源解析 `python3-websocket`：

```bash
curl -fL -o kylin-memory-bench_0.1.0_all.deb https://github.com/logxio/kylin-memory-bench/releases/download/v0.1.0/kylin-memory-bench_0.1.0_all.deb
sudo apt install ./kylin-memory-bench_0.1.0_all.deb
```

openKylin 3.0 预装 KylinBot 0.7.5；先执行 `kylin-bot config set gateway.listen-tcp true` 和 `kylin-bot gateway start`。[KylinBot Gateway 自动测试脚本](https://gitee.com/openkylin/kylin-botshell/tree/develop-for-skill-autotest)给出 `kylinbot.v1` WebSocket 协议：在 `ws://127.0.0.1:42617/ws/chat` 连接后发送 `connect`、`message`，并以 `done.full_response` 作为最终回复。适配器可按上游的 `/admin/paircode/new`、`/pair` 接口自动与本机网关配对；远端网关则须把令牌放入环境变量 `KYLINBOT_WS_TOKEN`。适配器使用 Authorization header，不主动把令牌写进结果。`configs/kylinbot.example.json` 可改网关地址和超时。

按 [OpenClaw 官方用户目录安装器](https://docs.openclaw.ai/install/installer)使用 `install-cli.sh --no-onboard` 安装，并将 `~/.openclaw/bin` 加入运行终端的 `PATH`。用[官方 agents 命令](https://docs.openclaw.ai/cli/agents)建立专门的测试身份，例如 `openclaw agents add kmb-test --workspace ~/.openclaw/workspace-kmb-test --non-interactive`；`configs/openclaw.example.json` 的 `agent_id` 默认就是 `kmb-test`。适配器调用 `openclaw agent --agent ... --session-key ... --message-file ... --json`；每个任务的不同会话有不同 key，同一批次自动加唯一运行 ID。[官方记忆说明](https://docs.openclaw.ai/concepts/memory)介绍 `MEMORY.md`、`USER.md` 和 `memory/*.md`。不要用默认临时状态的 `agent exec` 测跨会话记忆。

运行前给两款智能体各自准备**干净、专用的**测试身份与工作区；把 `KMB_OPENCLAW_WORKSPACE` 指向 OpenClaw 的 agent 工作区，把 `KMB_KYLINBOT_MEMORY_DB` 指向 KylinBot 0.7.5 实际的 `~/.kylinbot/workspace/memory/brain.db`。SQLite 观察器只读数据库，并按案例前后变化取证。其他版本若暴露可读的记忆文件，也可用 `KMB_KYLINBOT_MEMORY_ROOT`；路径须先现场核实。两款 agent 应使用可比的模型与设置；把版本、模型和环境写入评测记录。完成配置后在云端 openKylin 运行：

```bash
./run-live.sh
```

CLI 也支持任意配置的批量对比，例如 `python3 -m kylin_memory_bench --dataset data/tasks.json --agent configs/kylinbot.example.json --agent configs/openclaw.example.json --output out/my-run --max-seconds 1800`。`--agent` 可重复，`--case retention-01` 可先跑最小连通测试。真实失败会留下错误记录与 `missing`，绝不会退回替身数据。结果可能包含真实回复和记忆文件；公开前先删去私人信息与令牌。

## 任务书逐项对应

| 评审项 | 权重 | 现在可检查的产物 |
|---|---:|---|
| 任务定义与通用性 | 15% | [六项跨会话任务](data/tasks.json)、统一 agent 接口 |
| 数据设计质量 | 25% | 六项虚构样本、答案与禁用值、回复及文件验证项 |
| 自动评分能力 | 25% | [评分器](kylin_memory_bench/scoring.py)、逐项原因与证据来源；缺证据不给分 |
| 稳定性与可复现性 | 15% | 数据及配置指纹、隔离输出目录、运行 ID、[合同测试](tests/test_scoring.py) |
| 指标完整性 | 10% | 六维与总分、[结构化样例](examples/fixture-result.json)、[雷达图](examples/fixture-radar.svg) |
| 创新与工程落地 | 10% | 回复、记忆和实际文件共同裁决；两个真实适配器、[一键脚本](run-live.sh)、[.deb 构建脚本](packaging/build-deb.sh) |

完整的测试前提、数据生成、结果收集和评分流程见[评测方案](docs/method.md)。真实六维比较已有上方的报告、雷达图与桌面视频；官方评委分数尚无。每批每维只有一条样本，不能据此声称统计显著差异。

## 构建与贡献

当前版本为 v0.1.0。`./packaging/build-deb.sh` 使用 Python 标准库生成 `dist/kylin-memory-bench_0.1.0_all.deb`；openKylin 3.0 上的 `apt install`、系统依赖和已安装入口 `--help` 已通过。介绍 PDF 可用 `python3 scripts/build-intro.py docs/intro.pdf` 重新生成，需另装 `reportlab`。测试命令：`python3 -m unittest discover -s tests`。[公共 CI](https://github.com/logxio/kylin-memory-bench/actions/workflows/ci.yml) 在 Ubuntu 的干净 checkout 中运行单元测试、替身与打包；真实 openKylin 证据见上方两批报告。

接下来的改动围绕已经看到的误差：给六维各加虚构变体并重复运行，量出分数波动；复测 KylinBot 的超时；让不同版本的记忆文件和 SQLite 记录都能逐案例读取；接收外部 openKylin 复跑的去敏证据。每维一例的两批结果只显示当前案例发生了什么，不给稳定排名。源代码按 [MIT](LICENSE) 发布；用 [Issue 模板](https://github.com/logxio/kylin-memory-bench/issues/new/choose)提交可复现问题或案例，用 [贡献指南](CONTRIBUTING.md)准备 PR。
