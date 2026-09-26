# 在 openKylin 3.0 上跑两款真实智能体

这份操作顺序从已安装的 openKylin 3.0 桌面开始：接好 KylinBot 和 OpenClaw，安装本项目的 `.deb`，用一个案例确认两条链路，再跑六项比较并录下桌面结果。运行会留下逐项原因、原始回复和雷达图。请在云端桌面完成操作，不要把本仓的替身分数当成真实成绩。

命令以当前登录的普通用户执行；只有安装系统包时用 `sudo`。先从本仓公开页面把源码取到 VM，终端进入仓库根目录。以下以 `~/kylin-memory-bench` 为仓库目录，若放在别处，把第一条 `cd` 改成实际位置。每次运行选一个新输出目录，结果不会覆盖旧证据。

```bash
cd ~/kylin-memory-bench
cat /etc/os-release
uname -m
python3 --version
```

确认 `VERSION_ID` 为 3.0、架构与镜像一致、Python 至少 3.10。系统发行说明确认 3.0 支持 KylinBot 与 OpenClaw，**没有替这台 VM 验证**实际包、Gateway、模型调用或 `.deb` 依赖。[openKylin 3.0 发布说明](https://www.openkylin.top/news/4098-cn.html)

## 两款智能体先用同一模型

在桌面的 Token 中心选一个两款智能体都能调用的模型，并记下实际模型名与推理设置。下例采用官方列出的 `qwen3.7-plus` 和 OpenAI 兼容请求地址；它是配置示例，**不是本项目已实测的模型**。两边保持相同模型、温度与测试时段，最后把实际值记入结果说明。Token 中心领取 Key、模型名及接口地址见[openKylin 官方说明](https://www.openkylin.top/news/4131-cn.html)。

不要把明文 Key 写进仓库、JSON 配置、`.env`、shell 启动文件或命令行参数。下面 OpenClaw 配置只保存环境变量引用；在将要运行 Gateway 的终端隐式输入 Key，进程退出即失效：

```bash
read -r -s -p 'Model API key: ' KMB_MODEL_API_KEY
printf '\n'
export KMB_MODEL_API_KEY
```

这条 `read` 不会把输入写进 shell 历史，也不会回显。不要用 `echo`、`set -x` 或带 Key 的录屏。**KylinBot 模型设置仍需在 VM 核对**：从系统预装的 KylinBot 和 Token 中心选择同一模型，先确认能否从当前进程环境或 Token 中心会话取用 Key，且不把 Key 写入文件；若当前版只支持保存 Key 到磁盘，记录版本与限制，不把这一步写成已完成的无秘密落盘配置。Token 中心涉及账号的领取和登录由 VM 操作者本人完成。

## KylinBot：确认本机 Gateway 可用

openKylin 3.0 发布说明把 KylinBot 列为原生智能体。进入桌面后先打开 KylinBot，完成它的首次模型设置，再在终端检查本机包和 Gateway：

```bash
dpkg-query -W -f='${Package} ${Version} ${Status}\n' kylin-bot
curl -sS -o /dev/null -w 'HTTP %{http_code}\n' http://127.0.0.1:42617/api/status
```

`dpkg-query` 的包名来自 KylinBot 官方自动化脚本；是否预装、版本号和 Gateway 启动方式以这台 VM 的输出为准。`/api/status` 返回 200 表示可读；返回 401 只能说明端口应答，不能说明模型已接通。连接被拒绝时先在 KylinBot 桌面界面启动/启用 Gateway，再重查，不要改成本项目里的假地址。

本项目的配置默认连 `ws://127.0.0.1:42617/ws/chat`，以 `kylinbot.v1` 子协议发 `connect` 和 `message`，从 `done.full_response` 取最终回复。适配器在本机没有 `KYLINBOT_WS_TOKEN` 时，通过 `POST /admin/paircode/new` 和 `POST /pair` 自动配对，令牌只留在当前 Python 进程内。不要运行上游会把令牌缓存为 `.ws_token` 的 `get_ws_token.py`；也不要在录屏中展示配对码或令牌。远端 Gateway 不属于这条本机流程。[KylinBot 官方测试分支](https://gitee.com/openkylin/kylin-botshell/tree/develop-for-skill-autotest)

**VM 待验**：这台 3.0 镜像是否预装 `kylin-bot`，实际 Gateway 是否在 42617 启动，本机自动配对、Authorization header 和 `kylinbot.v1` 帧是否与当前版一致，模型与文件工具能否完成案例。上游测试脚本给的是接口合同，不是本 VM 的运行回执。

## OpenClaw：Gateway 和专用 agent

OpenClaw 当前 Linux 安装器会补受支持的 Node 运行时；CLI 要求 Node 24.16+ 或 26.1+。以下用上游安装器跳过会要求输入凭据的向导，之后只写非秘密配置。[安装与 Node 要求](https://docs.openclaw.ai/start/getting-started)、[安装器说明](https://docs.openclaw.ai/install/installer)

```bash
curl -fsSL --proto '=https' --tlsv1.2 https://openclaw.ai/install.sh | bash -s -- --no-onboard
node --version
openclaw --version
openclaw setup --baseline
openclaw config set gateway.mode local
```

把 Token 中心给出的 `/v1/chat/completions` 请求地址按 OpenClaw 的 `baseUrl` 约定写成 `/v1`；Key 字段只是一条环境变量引用。此处的自定义 provider 名是本机配置名，不是第二套模型服务。[OpenClaw 自定义 provider](https://docs.openclaw.ai/gateway/config-tools/custom-providers)、[环境 SecretRef](https://docs.openclaw.ai/gateway/secrets/secretref-contract)

```bash
openclaw config set models.providers.openkylin '{"baseUrl":"https://llm-gateway.openkylin.top/v1","api":"openai-completions","apiKey":{"source":"env","provider":"default","id":"KMB_MODEL_API_KEY"},"models":[{"id":"qwen3.7-plus","name":"qwen3.7-plus"}]}' --strict-json --merge
openclaw models set openkylin/qwen3.7-plus
openclaw agents add kmb-test --workspace "$HOME/.openclaw/workspace-kmb-test" --model openkylin/qwen3.7-plus --non-interactive
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
openclaw gateway status
```

前台运行使 Gateway 继承当前进程环境；`gateway install` 创建的后台服务不会自动继承这个临时 Key。**VM 待验**：安装器和 `setup --baseline` 在 openKylin 3.0 的实际结果、自定义 provider 配置是否被当前 CLI 接受、模型能否真实完成一次回复、`--json` 输出是否仍满足本项目适配器的解析。配置检查通过不能替代模型调用。[Gateway 前台命令](https://docs.openclaw.ai/cli/gateway/running)、[环境变量来源](https://docs.openclaw.ai/help/environment)

## 安装并检验 `.deb`

从源码在 VM 上构建，避免误把本机归档检查当成 openKylin 安装测试。包声明依赖 `python3 (>= 3.10)` 和 `python3-websocket`；若 `apt` 找不到依赖，保留原报错并查该 VM 的包源，不用 `dpkg --force` 跳过依赖。

```bash
cd ~/kylin-memory-bench
./packaging/build-deb.sh
dpkg-deb --info dist/kylin-memory-bench_0.1.0_all.deb
dpkg-deb --contents dist/kylin-memory-bench_0.1.0_all.deb
sudo apt install ./dist/kylin-memory-bench_0.1.0_all.deb
dpkg-query -W -f='${Package} ${Version} ${Status}\n' kylin-memory-bench
command -v kylin-memory-bench
kylin-memory-bench --help
```

`--help` 证明已安装的入口能装载 Python 模块；它不证明两个真实适配器可用。安装后的数据和配置在 `/usr/share/kylin-memory-bench/`，运行输出请写入普通用户目录，不要写到包目录。**VM 待验**：`apt` 依赖解析、实际安装/卸载、已安装入口与系统 Python 是否兼容。

## 先跑一个案例，再跑六项

第二个终端设置可观察的记忆目录；OpenClaw 工作区由上面的专用 agent 创建。KylinBot 的记忆文件根目录只有现场确认确实可读时才设置。留空会让需要持久化文件证据的检查记为 `missing`，不能把缺证据算成通过。

```bash
export KMB_OPENCLAW_WORKSPACE="$HOME/.openclaw/workspace-kmb-test"
mkdir -p "$HOME/kmb-results"
cd /usr/share/kylin-memory-bench
kylin-memory-bench --dataset data/tasks.json --agent configs/kylinbot.example.json --agent configs/openclaw.example.json --case retention-01 --output "$HOME/kmb-results/smoke-$(date +%Y%m%d-%H%M%S)" --max-seconds 600
```

若已经确认 KylinBot 把记忆写到某个可读目录，可在运行前执行 `export KMB_KYLINBOT_MEMORY_ROOT="<实际记忆目录>"`；不要猜路径。最小案例应在新输出目录产生 `result.json`、`report.txt`、`radar.svg`。先读 `report.txt`，再看 `result.json` 的两款 `kind`、`evidence_class`、逐步 `source`、`errors` 与实际回复。只有 `live:...` 的真实适配器证据才算连通；出现错误、空回复或缺文件，就按原始错误修好后换新输出目录重跑。`live/observed` 标签只说明用了真实适配器，**不单独证明两款智能体完成了任务**。

最小案例两条链路都接通后，从已安装包运行一键全批。它会给每款智能体跑同一组六个案例，并在同一输出目录生成六维报告和雷达图；默认总时限 1800 秒。保留本次原始目录，不把它和 `out/fixture-*` 混在一起。

```bash
/usr/share/kylin-memory-bench/run-live.sh "$HOME/kmb-results/full-$(date +%Y%m%d-%H%M%S)"
```

打开本次 `report.txt`、`radar.svg`，逐项检查 `result.json` 中 KylinBot 与 OpenClaw 的错误、回复、文件和记忆来源。尤其检查临时验证码那项：没有可读取的记忆文件时，`not-persisted` 必须是 `missing`。记录 VM 的 OS 版本、两款智能体版本、实际模型与温度、运行时间、包版本和输出目录；不要根据首轮六个案例宣称统计显著差异。

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

卸载后状态不应为 `installed`，`command -v` 应找不到已安装入口。记录实际输出；在 VM 验过前，文档中的安装、模型和 Gateway 命令都只是按本仓代码与上游资料准备的执行路径，不是已产生的真实成绩。
