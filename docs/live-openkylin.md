# 在 openKylin 3.0 上跑两款真实智能体

这份操作顺序从已安装的 openKylin 3.0 桌面开始：接好 KylinBot 和 OpenClaw，安装本项目的 `.deb`，用一个案例确认两条链路，再跑六维各两例并录下桌面结果。运行会留下逐项原因、原始回复和雷达图。请在云端桌面完成操作，不要把本仓的替身分数当成真实成绩。

命令以当前登录的普通用户执行；只有安装系统包时用 `sudo`。准备一台可联网的 openKylin 3.0 x86_64 桌面、`git`、`curl` 和 Python 3.10+，从公开仓库取代码。每次运行选一个新输出目录，结果不会覆盖旧证据。

```bash
git clone https://github.com/logxio/kylin-memory-bench.git
cd kylin-memory-bench
cat /etc/os-release
uname -m
python3 --version
./run-fixture.sh
```

确认 `VERSION_ID` 为 3.0、架构与镜像一致、Python 至少 3.10。替身输出标为 `synthetic/fixture`，只检验运行流水线。同一台 openKylin 3.0 x86_64 VM 已安装 KylinBot 0.7.5、OpenClaw 2026.9.6 和本项目的 `.deb`，完成下文的双智能体真实六维全批与[本轮桌面演示](../examples/live-openkylin-20260927-v022-demo.mp4)；[4 分 47 秒旧视频](../examples/live-openkylin-20260926-demo.mp4)只对应历史六例。[openKylin 3.0 发布说明](https://www.openkylin.top/news/4098-cn.html)

## 两款智能体先用同一模型

给两款智能体选同一模型，并记下模型名与推理设置。2026-09-26 的双智能体全批共用阿里云百炼 `qwen-plus`，OpenClaw 走其 OpenAI 兼容端点；下面以这次真实配置为例。也可使用 [openKylin Token 中心](https://www.openkylin.top/news/4131-cn.html)提供的模型，但需把两边都改为同一模型，并另记服务与接口地址。

不要把明文 Key 写进仓库、JSON 配置、`.env`、shell 启动文件或命令行参数。下面 OpenClaw 配置只保存环境变量引用；在将要运行 Gateway 的终端隐式输入 Key，进程退出即失效：

```bash
read -r -s -p 'Model API key: ' KMB_MODEL_API_KEY
printf '\n'
export KMB_MODEL_API_KEY
```

这条 `read` 不会把输入写进 shell 历史，也不会回显。不要用 `echo`、`set -x` 或带 Key 的录屏。KylinBot 的模型 Secret 通过它自身的 masked input 输入，由系统 keyring 保存；不要把明文 Key 放进命令参数或配置文件。

## KylinBot：确认本机 Gateway 可用

openKylin 3.0 发布说明把 KylinBot 列为原生智能体。进入桌面后先打开 KylinBot，完成它的首次模型设置，再在终端检查本机包和 Gateway：

```bash
dpkg-query -W -f='${Package} ${Version} ${Status}\n' kylin-bot
```

openKylin 3.0 预装的包版本为 0.7.5。Gateway 默认关闭本地 TCP 监听，先打开它，再启动 Gateway 并检查端口：

```bash
kylin-bot config set gateway.listen-tcp true
kylin-bot gateway start
curl -sS -o /dev/null -w 'HTTP %{http_code}\n' http://127.0.0.1:42617/api/status
```

本机未配对的请求已返回 HTTP 401，说明 42617 端口有响应；它不等于模型调用成功。连接被拒绝时检查 Gateway 是否仍在运行，不要改成本项目里的假地址。

本项目的配置默认连 `ws://127.0.0.1:42617/ws/chat`，以 `kylinbot.v1` 子协议发 `connect` 和 `message`，从 `done.full_response` 取最终回复。适配器在本机没有 `KYLINBOT_WS_TOKEN` 时，通过 `POST /admin/paircode/new` 和 `POST /pair` 自动配对，令牌只留在当前 Python 进程内。不要运行上游会把令牌缓存为 `.ws_token` 的 `get_ws_token.py`；也不要在录屏中展示配对码或令牌。远端 Gateway 不属于这条本机流程。[KylinBot 官方测试分支](https://gitee.com/openkylin/kylin-botshell/tree/develop-for-skill-autotest)

下文的真实全批包含 KylinBot 的回复、文件和逐项评分；它的记忆观察范围需结合 SQLite 限制解读。

## OpenClaw：Gateway 和专用 agent

OpenClaw 的官方 `install-cli.sh` 把 Node 与 CLI 装进当前用户目录，无需 root。它在 openKylin 3.0 上装成 Node 24.21.0 与 OpenClaw 2026.9.6，CLI 位于 `~/.openclaw/bin/openclaw`。跳过向导后，在每个运行 OpenClaw 或本项目适配器的终端加入它的 `bin` 目录。[安装器说明](https://docs.openclaw.ai/install/installer)

```bash
curl -fsSL --proto '=https' --tlsv1.2 https://openclaw.ai/install-cli.sh | bash -s -- --no-onboard
export PATH="$HOME/.openclaw/bin:$PATH"
openclaw --version
openclaw setup --baseline
openclaw config set gateway.mode local
```

本次使用的百炼 OpenAI 兼容端点以 `/v1` 作为 OpenClaw 的 `baseUrl`；Key 字段只保存环境变量引用。此处的自定义 provider 名是本机配置名。[OpenClaw 自定义 provider](https://docs.openclaw.ai/gateway/config-tools/custom-providers)、[环境 SecretRef](https://docs.openclaw.ai/gateway/secrets/secretref-contract)

```bash
openclaw config set models.providers.dashscope '{"baseUrl":"https://dashscope.aliyuncs.com/compatible-mode/v1","api":"openai-completions","apiKey":{"source":"env","provider":"default","id":"KMB_MODEL_API_KEY"},"models":[{"id":"qwen-plus","name":"qwen-plus"}]}' --strict-json --merge
openclaw models set dashscope/qwen-plus
openclaw agents add kmb-test --workspace "$HOME/.openclaw/workspace-kmb-test" --model dashscope/qwen-plus --non-interactive
openclaw config validate
openclaw agents list
```

`kmb-test` 必须出现在列表里，工作区是新的测试专用目录，不能指向日常 `main` agent。适配器会调用 `openclaw agent --agent kmb-test --session-key ... --message-file ... --json --timeout ...`；`--session-key` 会让同一案例的不同会话共用这个 agent 的长期记忆，而各批次有独立运行 ID。`agent exec` 的默认临时状态不用于这项跨会话测试。[OpenClaw agent CLI](https://docs.openclaw.ai/cli/agent)、[独立 agent 命令](https://docs.openclaw.ai/cli/agents)、[记忆文件](https://docs.openclaw.ai/concepts/memory)

在**已输入并导出 `KMB_MODEL_API_KEY` 的同一个终端**前台启动 Gateway，保留该终端运行；另开一个终端做后续命令：

```bash
openclaw gateway run
```

第二个终端检查：

```bash
export PATH="$HOME/.openclaw/bin:$PATH"
openclaw gateway status
```

前台运行使 Gateway 继承当前进程环境；`gateway install` 创建的后台服务不会自动继承这个临时 Key。下文的真实全批已由 OpenClaw 适配器跑完六项并逐项评分。[Gateway 前台命令](https://docs.openclaw.ai/cli/gateway/running)、[环境变量来源](https://docs.openclaw.ai/help/environment)

## 安装并检验 `.deb`

从 [v0.2.2 Release](https://github.com/logxio/kylin-memory-bench/releases/tag/v0.2.2) 下载当前 12 例发行包。包声明依赖 `python3 (>= 3.10)` 和 `python3-websocket`，安装 CLI、任务数据、配置和运行脚本；公开报告、PDF 与视频留在仓库 `examples/` 和 `docs/`，不打进安装包。v0.2.2 已在 openKylin 3.0 经 `apt install` 安装，已安装入口与指定用户目录的替身命令通过检查。历史 v0.2.0、v0.2.1 包也有现场安装记录。想从当前 checkout 自行打包时，先执行 `./packaging/build-deb.sh`，再把下方包路径改成 `dist/kylin-memory-bench_0.2.2_all.deb`。

```bash
curl -fL -o kylin-memory-bench_0.2.2_all.deb https://github.com/logxio/kylin-memory-bench/releases/download/v0.2.2/kylin-memory-bench_0.2.2_all.deb
dpkg-deb --info kylin-memory-bench_0.2.2_all.deb
dpkg-deb --contents kylin-memory-bench_0.2.2_all.deb
sudo apt install ./kylin-memory-bench_0.2.2_all.deb
dpkg-query -W -f='${Package} ${Version} ${Status}\n' kylin-memory-bench
command -v kylin-memory-bench
kylin-memory-bench --help
```

v0.2.2 的包 SHA-256 为 `72dcb72b32efbc8d620b4a81a3716b8154637619099eeba4920fc185458e234e`；现场核验下载文件后再安装。安装后的数据和配置在 `/usr/share/kylin-memory-bench/`，运行输出请写入普通用户目录，不要写到包目录。例如 `./run-fixture.sh "$HOME/kmb-results/fixture-check"` 可验证已安装的替身流水线。

## 先跑一个案例，再跑 12 例

第二个终端设置 OpenClaw 的专用工作区、KylinBot 的可读记忆库与运行输出目录。openKylin 3.0 预装的 KylinBot 0.7.5 将记忆写在下方 SQLite 路径；本项目只读打开它，按每个案例前后变化取证。若其他版本路径不同，先核实数据库位置，不要指向不相关文件。缺证据不会算通过。

```bash
export PATH="$HOME/.openclaw/bin:$PATH"
export KMB_OPENCLAW_WORKSPACE="$HOME/.openclaw/workspace-kmb-test"
export KMB_KYLINBOT_MEMORY_DB="$HOME/.kylinbot/workspace/memory/brain.db"
test -r "$KMB_KYLINBOT_MEMORY_DB"
mkdir -p "$HOME/kmb-results"
cd /usr/share/kylin-memory-bench
kylin-memory-bench --dataset data/tasks.json --agent configs/kylinbot.example.json --agent configs/openclaw.example.json --case retention-01 --output "$HOME/kmb-results/smoke-$(date +%Y%m%d-%H%M%S)" --max-seconds 600
```

若其他 KylinBot 版本确实把记忆写到可读 Markdown 文件，也可设置 `KMB_KYLINBOT_MEMORY_ROOT` 观察该目录。最小案例应在新输出目录产生 `result.json`、`report.txt`、`radar.svg`。先读 `report.txt`，再看 `result.json` 的两款 `kind`、`evidence_class`、逐步 `source`、`errors` 与实际回复。只有 `live:...` 的真实适配器证据才算连通；出现错误、空回复或缺文件，就按原始错误修好后换新输出目录重跑。`live/observed` 标签只说明用了真实适配器，**不单独证明两款智能体完成了任务**。

最小案例两条链路都接通后，从已安装包运行一键全批。当前包会给每款智能体跑同一组 12 个案例、28 个步骤，并在同一输出目录生成六维报告和雷达图；默认总时限 1800 秒。示例配置的逐回合总时限为 130 秒，成功或错误均保留实耗时；原因见[评测方法](method.md#重复运行统计)。保留本次原始目录，不把它和 `out/fixture-*` 混在一起。

```bash
/usr/share/kylin-memory-bench/run-live.sh "$HOME/kmb-results/full-$(date +%Y%m%d-%H%M%S)"
```

打开本次 `report.txt`、`radar.svg`，逐项检查 `result.json` 中 KylinBot 与 OpenClaw 的错误、回复、文件和记忆来源。尤其检查临时验证码那项：没有可读取的记忆证据时，`not-persisted` 必须是 `missing`。记录 VM 的 OS 版本、两款智能体版本、实际模型与温度、运行时间、包版本和输出目录。

要重复运行，先让两款智能体回到同一个可核验的干净状态，包括长期记忆、专用工作区和会话记录；单靠新输出目录或运行 ID 不够。保留每次的原始 `result.json`，用[重复摘要命令](method.md#重复运行统计)计算逐维均值、样本标准差、步骤完成率与超时。无法验证状态一致时，应把重复批次注明为可能受前批记忆影响，不能当作独立波动。

## 2026-09-27 v0.2.2 十二例真机复跑

同一台 openKylin 3.0 x86_64 VM，Python 3.12.2、KylinBot 0.7.5、OpenClaw 2026.9.6、安装包 v0.2.2，两款共用 `qwen-plus`。KylinBot 温度为 0.0，OpenClaw 温度未显式固定。每批前停止网关，从同一基线恢复两款专用记忆、会话和工作区并核验清零；保留 OpenClaw 的工作区根目录及 `USER.md`、`DREAMS.md` 启动文件。三批使用数据指纹 `55cf5b121b039ef5f4ff31285900b9ea7f60ca898d0337339c63aea584766c71`，KylinBot 配置指纹 `cec62be58aed3a1d8c659410de5374b437b6309da797456b4f3906688f304329`，OpenClaw `d89b48a7f071f22e080e6daec73efd8dd7123f79b4840cc1142df02147288528`，评分器 `kmb.scoring.v0.2.1-json-fence`。包版本变更的是超时控制，评分规则仍是 v0.2.1 口径。

| 批次与 run ID | KylinBot 总分、完成、超时 | OpenClaw 总分、完成、超时 | 全批耗时 |
|---|---:|---:|---:|
| 1 · `b72c1361f53e` | 40.28；28/28；0 | 34.72；28/28；0 | 910.375 秒 |
| 2 · `0c2f2492a6fb` | 36.11；28/28；0 | 34.72；28/28；0 | 1096.795 秒 |
| 3 · `9365dedf1939` | 31.95；28/28；0 | 47.22；28/28；0 | 1234.037 秒 |

| 能力 | KylinBot 均值 / 样本标准差 | OpenClaw 均值 / 样本标准差 |
|---|---:|---:|
| 长期保持 | 50.00 / 0.00 | 0.00 / 0.00 |
| 记忆调用 | 33.33 / 28.87 | 0.00 / 0.00 |
| 动态更新 | 41.67 / 14.43 | 83.33 / 14.43 |
| 相近区分 | 0.00 / 0.00 | 16.67 / 28.87 |
| 边界识别 | 58.34 / 0.00 | 100.00 / 0.00 |
| 任务复用 | 33.33 / 0.00 | 33.33 / 0.00 |
| 总分 | 36.11 / 4.17 | 38.89 / 7.22 |

两款共完成 168/168 步，均为零 `TimeoutError`。第二批 OpenClaw 有 77.217 秒和 92.121 秒的成功回合，第三批 KylinBot 最长成功回合 101.938 秒，说明旧 60 秒客户端截止会截断这类正常完成的调用；旧超时请求的上游最终状态没有保存，不能倒推其本来必会成功。查看[独立重复摘要与逐步完成率](../examples/live-openkylin-20260927-v022-repeat-summary.json)、[每批去敏报告与雷达图](../examples/live-openkylin-20260927-v022-full-1-report.txt)、[第二批](../examples/live-openkylin-20260927-v022-full-2-report.txt)、[第三批](../examples/live-openkylin-20260927-v022-full-3-report.txt)、[均值雷达图](../examples/live-openkylin-20260927-v022-mean-radar.svg)和[逐项判定、原始 SHA-256、每批隔离收据](../examples/live-openkylin-20260927-v022-provenance.json)。完整原始结果私下留存；[字段级去敏评分输入](../examples/live-openkylin-20260927-v022-full-replay.json)可按 README 的命令离线重算三批全部 150 项检查，原有第 1 批 `boundary-01` 的[单例样本](../examples/live-openkylin-20260927-v022-boundary-01-replay.json)继续保留。初次隔离预检曾令 OpenClaw 工作区失效，12 例首步全部报错；[失败记录](../examples/live-openkylin-20260927-v022-preflight-failure.json)单列，不并入这三批。OpenClaw 的全局状态库仍保留运行记录，不能把此流程解释为三次全新系统安装。同机、每维两例、三批的样本不支持稳定领先或显著性结论。

## 2026-09-26 v0.2.0 十二例真实运行与 v0.2.1 离线重评分

同一台 openKylin 3.0 x86_64 VM，Python 3.12.2、KylinBot 0.7.5、OpenClaw 2026.9.6、本项目 `.deb` 0.2.0。两款智能体均用 `qwen-plus`，模型温度采用服务默认值、没有显式固定。每批前停止两个 Gateway，将测试身份的长期记忆、会话和工作区恢复到同一干净基线，并现场核验 KylinBot SQLite 记忆与会话数均为零、OpenClaw 测试工作区没有 `MEMORY.md`；再重启 Gateway。每批完整运行同一数据指纹 `55cf5b121b039ef5f4ff31285900b9ea7f60ca898d0337339c63aea584766c71` 的 12 例、每款 28 步。每款智能体的配置指纹在三批内相同；详见[运行来源与原始文件 SHA-256](../examples/live-openkylin-20260926-v020-provenance.json)。

| 批次与运行 ID | 耗时 | KylinBot 总分、完成、超时 | OpenClaw 总分、完成、超时 |
|---|---:|---:|---:|
| 1 · `92ae7d35ea9f` | 1085.812 秒 | 31.95；21/28；3 | 31.94；26/28；2 |
| 2 · `abe90652770c` | 826.011 秒 | 40.28；28/28；0 | 34.72；28/28；0 |
| 3 · `5ad3c72309be` | 1019.448 秒 | 30.56；28/28；0 | 34.72；28/28；0 |

| 维度 | KylinBot 均值 / 样本标准差 | OpenClaw 均值 / 样本标准差 |
|---|---:|---:|
| 长期保持 | 50.00 / 0.00 | 0.00 / 0.00 |
| 记忆调用 | 33.33 / 28.87 | 0.00 / 0.00 |
| 动态更新 | 25.00 / 25.00 | 75.00 / 0.00 |
| 相近区分 | 0.00 / 0.00 | 0.00 / 0.00 |
| 边界识别 | 58.34 / 0.00 | 100.00 / 0.00 |
| 任务复用 | 38.89 / 9.62 | 27.77 / 9.62 |
| 总分 | 34.26 / 5.26 | 33.79 / 1.61 |

上表是 v0.2.0 原始严格解析口径，三份原始 `result.json` 和旧报告保持原样；[旧版固定提交](https://github.com/logxio/kylin-memory-bench/tree/bb8fdda83db52919bff7be352f69856008dd291a/examples)可核。v0.2.1 用同一三批保存的原始证据离线重评分，未在 openKylin 3.0 重新运行或安装新版包。首批 OpenClaw `discrimination-02/probe` 的整段唯一 `json` 围栏现在可解析，`east-boxes` 与 `west-boxes` 两项从 `fail` 变为 `pass`，该案例从 0 变 100；其他 148 项状态不变。旧版首批 OpenClaw 总分 31.94 变为 40.28，三批均值 / 样本标准差从 33.79 / 1.61 变为 36.57 / 3.21；KylinBot 三批分数仍为 31.95、40.28、30.56，均值 / 样本标准差 34.26 / 5.26。OpenClaw 的相近区分维度变为 16.67 / 28.87，其他维度仍如上表。完成率和超时不受评分解析影响，仍为 KylinBot 77/84、3 次和 OpenClaw 82/84、2 次。详见[新逐项去敏审计及原始 SHA-256](../examples/live-openkylin-20260926-v021-offline-audit.json)和[新重复摘要](../examples/live-openkylin-20260926-v021-offline-repeat-summary.json)。

第一批的 5 次超时分别发生于 KylinBot 的 `discrimination-01/teach`、`update-01/old`、`update-02/correction`，以及 OpenClaw 的 `discrimination-01/probe`、`task-reuse-02/execute`。错误后的未执行步骤也计入未完成；三批分别累计为 KylinBot 77/84、OpenClaw 82/84。各步骤完成率、错误数与独立批次分数见[重复摘要](../examples/live-openkylin-20260926-v020-repeat-summary.json)；[第一批](../examples/live-openkylin-20260926-v020-full-1-report.txt)、[第二批](../examples/live-openkylin-20260926-v020-full-2-report.txt)、[第三批](../examples/live-openkylin-20260926-v020-full-3-report.txt)报告列出每项 `PASS`、`FAIL` 或 `MISSING` 及原因。公开文件去除了原始回复、文件和记忆内容；原始 `result.json` 私下保留，并以 SHA-256 对照。三批同机的小样本不构成稳定排名，零标准差也只说明这三批数值相同。

## 2026-09-26 历史六例真实全批读数

同一台 openKylin 3.0 VM 上，KylinBot 0.7.5 与 OpenClaw 2026.9.6 共用 `qwen-plus`，每款完成 14 个 live turns，均为 0 adapter errors。运行 ID 为 `e328e3f61ac1`，耗时 424.494 秒；[逐项报告](../examples/live-openkylin-20260926-report.txt)和[六维雷达图](../examples/live-openkylin-20260926-radar.svg)均标为 `live/observed`。报告中的姓名来自虚构测试样本。

| 能力 | KylinBot | OpenClaw |
|---|---:|---:|
| 长期保持 | 0 | 0 |
| 记忆调用 | 0 | 0 |
| 动态更新 | 50 | 50 |
| 相近区分 | 0 | 0 |
| 边界识别 | 66.67 | 100 |
| 任务复用 | 33.33 | 33.33 |
| 总分 | 25.00/100 | 30.55/100 |

每维只有一例。KylinBot 实际将记忆存于 SQLite，首批文件观察器把 `boundary-01` 的 `not-persisted` 标为 `MISSING`。同机换用逐案例 SQLite 只读观察器后，第二批 `9ad36e2594c4` 耗时 492.003 秒，KylinBot 得 33.33、OpenClaw 得 30.55；KylinBot 的禁存项有新增数据库记录，明确判为 `FAIL`。但 KylinBot 在 `update-01/probe` 超时，只有 13/14 步，OpenClaw 14/14 步无错误。看[第二批报告](../examples/live-openkylin-20260926-sqlite-report.txt)、[雷达图](../examples/live-openkylin-20260926-sqlite-radar.svg)和[来源及错误摘要](../examples/live-openkylin-20260926-sqlite-summary.json)。两批同题结果不支持稳定排名；官方评委分数尚无。原始 `result.json` 含未经去敏的回复与文件内容，不在公开样例中。

## 录 3–5 分钟真实桌面，并检查结果

全批完成后再录屏。桌面先展示 openKylin 版本与两款智能体身份，然后现场重跑一个 `retention-01` 小案例，展示它的 `report.txt`；接着打开**之前真实全批**的 `report.txt`、`radar.svg` 和一条逐项证据。口播或字幕明确区分“现场小案例”和“先前同 VM 全批结果”，显示两次输出目录名或运行 ID。若全批刚好可在录屏时跑完，也可直接录完整过程；不可把剪辑、替身或预置结果说成连续实跑。

可从桌面录屏应用开始；上游 KylinBot 技能还提供 `kylin-screencap full` 打开全桌面录屏，但命令在这台 3.0 VM 上**需先用 `command -v kylin-screencap` 确认**。[KylinBot 录屏技能源码](https://gitee.com/openkylin/kylin-botshell/blob/main/skills/system-control/kylin-screen-recording/SKILL.md)

结束录屏后，先在 VM 本地回看首、中、末段，确认桌面、命令、两款真实回复、六维图和时长都可辨认。`result.json` 含原始 prompt、回复、文件与可能的记忆内容；`report.txt`、SVG、终端错误和视频也可能暴露 Key、配对令牌、用户目录、云地址或账户信息。公开前检查这四类成品和录屏画面，必要时只发布去敏副本，原始目录保留作复核。不要公开 Key、`~/.openclaw` 配置、Gateway 鉴权信息或私人数据。

完成录屏和取证后，可验证卸载；卸载本项目包不会删除用户目录里的结果：

```bash
sudo apt remove kylin-memory-bench
dpkg-query -W -f='${db:Status-Status}\n' kylin-memory-bench
command -v kylin-memory-bench
```

卸载后状态不应为 `installed`，`command -v` 应找不到已安装入口。记录实际输出。
