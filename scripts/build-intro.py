#!/usr/bin/env python3
"""Generate the short Chinese project brief with ReportLab."""

import json
from pathlib import Path
import sys

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph


pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
FONT = "STSong-Light"
WIDTH, HEIGHT = A4
LEFT = 52
RIGHT = WIDTH - 52


def para(c, text, x, y, width, size=10.5, leading=17, color=colors.HexColor("#222222")):
    style = ParagraphStyle("body", fontName=FONT, fontSize=size, leading=leading,
                           textColor=color, alignment=TA_LEFT, spaceAfter=0)
    paragraph = Paragraph(text, style)
    _, height = paragraph.wrap(width, HEIGHT)
    paragraph.drawOn(c, x, y - height)
    return y - height


def label(c, text, x, y, size=10, color=colors.HexColor("#666666")):
    c.setFillColor(color)
    c.setFont(FONT, size)
    c.drawString(x, y, text)


def rule(c, y):
    c.setStrokeColor(colors.HexColor("#D7D7D7"))
    c.setLineWidth(.6)
    c.line(LEFT, y, RIGHT, y)


def footer(c, number):
    rule(c, 46)
    label(c, "kylin-memory-bench / 开源长期记忆评测", LEFT, 30, 8)
    label(c, str(number) + " / 2", RIGHT - 26, 30, 8)


def first_page(c, summary):
    label(c, "OPENKYLIN / 2026", LEFT, HEIGHT - 53, 9)
    label(c, "记忆状态取证评测", LEFT, HEIGHT - 95, 24, colors.HexColor("#111111"))
    y = para(c, "把跨会话回复、可观察记忆和实际文件逐项核对：智能体没说出口的禁存值，也可能已经进入记忆。缺证据不得分。", LEFT,
             HEIGHT - 112, RIGHT - LEFT, 12, 20)
    rule(c, y - 22)
    y -= 48
    label(c, "问题", LEFT, y, 13, colors.HexColor("#111111"))
    y = para(c, "只问智能体“还记得吗”，不足以发现它把旧值继续用于任务、混淆相似实体，或把临时信息错误地写进长期记忆。评测必须跨会话，并对真实行动留证。", LEFT, y - 17, RIGHT - LEFT)
    y -= 26
    label(c, "六项能力", LEFT, y, 13, colors.HexColor("#111111"))
    y -= 28
    abilities = [
        ("01 长期保持", "隔开干扰后回忆代号"),
        ("02 记忆调用", "召回项目负责人和格式"),
        ("03 动态更新", "更正后弃用旧联系人"),
        ("04 相近区分", "不交换相近任务日期"),
        ("05 边界识别", "临时验证码不持久化"),
        ("06 任务复用", "按旧偏好写出真实文件"),
    ]
    for index, (name, detail) in enumerate(abilities):
        col = index % 2
        row = index // 2
        x = LEFT + col * 252
        yy = y - row * 43
        label(c, name, x, yy, 11, colors.HexColor("#111111"))
        label(c, detail, x, yy - 18, 9)
    y -= 3 * 43 + 8
    rule(c, y)
    y -= 28
    label(c, "运行链", LEFT, y, 13, colors.HexColor("#111111"))
    y = para(c, "任务 JSON → 两款智能体适配器 → 原始回复 / 帧 / 文件 → 确定性检查项 → 六维分数、逐项原因和 SVG 雷达图。缺证据不得分；口头称已写文件，仍须核对文件内容。", LEFT, y - 16, RIGHT - LEFT)
    y -= 22
    label(c, "openKylin 3.0 / 12 例真实重复运行", LEFT, y, 13, colors.HexColor("#111111"))
    y = para(c, "KylinBot 0.7.5 与 OpenClaw 2026.9.6 双实装；v0.2.2 发行包已在 openKylin 3.0 经 apt 安装。下表是两款真实适配器连续三批运行同一数据与配置，每批每款 12 例、28 步；批前恢复并核验干净记忆状态。", LEFT, y - 17, RIGHT - LEFT, 9.5, 15)
    y -= 17
    label(c, "批次 / run ID", LEFT, y, 8.5)
    label(c, "KylinBot: 分数 / 完成 / 超时", LEFT + 151, y, 8.5)
    label(c, "OpenClaw: 分数 / 完成 / 超时", LEFT + 327, y, 8.5)
    y -= 9
    bot, claw = summary["agents"]
    runs = []
    for index, run_id in enumerate(summary["run_ids"]):
        def reading(agent):
            run = agent["runs"][index]
            return f"{run['overall']:.2f} / {run['completed_steps']}/28 / {run['timeout_error_count']}"
        runs.append((f"{index + 1} / {run_id}", reading(bot), reading(claw)))
    for batch, bot_reading, claw_reading in runs:
        rule(c, y)
        label(c, batch, LEFT, y - 17, 8.5, colors.HexColor("#111111"))
        label(c, bot_reading, LEFT + 151, y - 17, 8.5, colors.HexColor("#111111"))
        label(c, claw_reading, LEFT + 327, y - 17, 8.5, colors.HexColor("#111111"))
        y -= 25
    rule(c, y)
    y = para(c, f"三批总分均值 / 样本标准差：<b>KylinBot {bot['overall']['mean']:.2f} / {bot['overall']['sample_stddev']:.2f}</b>，完成 {bot['completed_steps']}/84 步、{bot['timeout_error_count']} 次 TimeoutError；<b>OpenClaw {claw['overall']['mean']:.2f} / {claw['overall']['sample_stddev']:.2f}</b>，完成 {claw['completed_steps']}/84 步、{claw['timeout_error_count']} 次 TimeoutError。均为智能体分数，非评委分。", LEFT, y - 15, RIGHT - LEFT, 9.2, 14)
    y = para(c, "<link href='https://github.com/logxio/kylin-memory-bench/blob/main/examples/live-openkylin-20260927-v022-demo-v3.mp4'>本轮 4 分 06 秒演示</link>先说明记忆状态取证评测与公开禁存案例，再接 openKylin 桌面安装版本、三批结果、雷达图与独立现场小案例；开头卡片不是新跑批。", LEFT, y - 10, RIGHT - LEFT, 9, 14)
    if y < 62:
        raise ValueError(f"First page overlaps footer: y={y:.1f}")
    footer(c, 1)
    c.showPage()


def second_page(c):
    label(c, "HOW IT IS SCORED", LEFT, HEIGHT - 53, 9)
    label(c, "从证据到可解释分数", LEFT, HEIGHT - 91, 19, colors.HexColor("#111111"))
    y = para(c, "四类检查：回复 JSON 字段、产物 JSON 字段、禁用值是否出现在回复或文件，以及禁用值是否进入可观察的记忆文件或 SQLite 记录。每项报告 pass / fail / missing 与来源。六维各自归一，再取均值。", LEFT, HEIGHT - 110, RIGHT - LEFT)
    y -= 23
    label(c, "任务书评分项", LEFT, y, 12, colors.HexColor("#111111"))
    y -= 24
    rows = [
        ("任务定义与通用性", "15%", "六项跨会话任务与统一接口"),
        ("数据设计质量", "25%", "六维各两例、虚构变体、行动核验"),
        ("自动评分能力", "25%", "原始证据、结构化判断与原因"),
        ("稳定性与可复现性", "15%", "三批同指纹复跑、隔离、错误与完成率"),
        ("指标完整性", "10%", "六维分、总分、JSON、雷达图"),
        ("创新与工程落地", "10%", "回复 + 记忆 + 文件联合裁决"),
    ]
    for name, weight, detail in rows:
        rule(c, y + 10)
        label(c, name, LEFT, y - 7, 10, colors.HexColor("#111111"))
        label(c, weight, LEFT + 150, y - 7, 10, colors.HexColor("#111111"))
        label(c, detail, LEFT + 205, y - 7, 9)
        y -= 35
    rule(c, y + 10)
    y -= 20
    label(c, "重复口径与边界", LEFT, y, 12, colors.HexColor("#111111"))
    y = para(c, "n=3 批；每批每维 2 例，两个智能体各 28 步。只汇总同一数据、各智能体相同配置指纹及相同评分器版本的完整运行；逐维和总分报告均值、样本标准差，逐步统计完成率与 TimeoutError。历史六例、旧 v0.2.0 批次和替身结果不混算。", LEFT, y - 17, RIGHT - LEFT, 9.5, 15)
    y = para(c, "v0.2.2 保持 v0.2.1 的 JSON 围栏评分口径，改进客户端超时控制。三批前均恢复并核验干净记忆状态；一次隔离预检失败单独保留，不纳入三批。仍仅同一台 VM、每维两例，OpenClaw 温度未显式固定；不能认定稳定排名或统计显著性。完整原始证据私下保留。", LEFT, y - 9, RIGHT - LEFT, 9.5, 15)
    y -= 19
    label(c, "自己重算禁存案例", LEFT, y, 12, colors.HexColor("#111111"))
    y = para(c, "从<link href='https://github.com/logxio/kylin-memory-bench/blob/main/examples/live-openkylin-20260927-v022-boundary-01-replay.json'>公开去敏样本</link>读取第 1 批两款智能体的真实回复与记忆，用仓内评分器重算 boundary-01 三项状态；仅覆盖这一例。", LEFT, y - 17, RIGHT - LEFT, 9.5, 15)
    label(c, "python3 scripts/replay-boundary-01.py  (Python 3.10+)", LEFT, y - 18, 9, colors.HexColor("#111111"))
    y -= 43
    label(c, "版本与参与", LEFT, y, 12, colors.HexColor("#111111"))
    y = para(c, "<link href='https://github.com/logxio/kylin-memory-bench/releases/tag/v0.2.2'>v0.2.2 Release 与 .deb</link>、<link href='https://github.com/logxio/kylin-memory-bench/actions/workflows/ci.yml'>Ubuntu CI</link>、<link href='https://github.com/logxio/kylin-memory-bench/blob/main/examples/live-openkylin-20260927-v022-repeat-summary.json'>三批摘要</link>与<link href='https://github.com/logxio/kylin-memory-bench/blob/main/examples/live-openkylin-20260927-v022-provenance.json'>逐项判定及原始哈希</link>、<link href='https://github.com/logxio/kylin-memory-bench/blob/main/CONTRIBUTING.md'>贡献指南</link>和 <link href='https://github.com/logxio/kylin-memory-bench/issues/new/choose'>Issue 入口</link>。历史 v0.2.1 离线重算另有固定报告，不写成新版真机重跑。", LEFT, y - 17, RIGHT - LEFT, 9.2, 15)
    if y < 62:
        raise ValueError(f"Second page overlaps footer: y={y:.1f}")
    footer(c, 2)
    c.showPage()


def main():
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("docs/intro.pdf")
    summary = json.loads(Path("examples/live-openkylin-20260927-v022-repeat-summary.json").read_text(encoding="utf-8"))
    if summary["run_count"] != 3 or [agent["name"] for agent in summary["agents"]] != ["KylinBot", "OpenClaw"]:
        raise ValueError("reviewer brief requires three live runs of KylinBot and OpenClaw")
    output.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(output), pagesize=A4, pageCompression=1)
    c.setTitle("记忆状态取证评测｜kylin-memory-bench 项目介绍")
    c.setAuthor("Yan Su")
    c.setCreator("kylin-memory-bench")
    first_page(c, summary)
    second_page(c)
    c.save()
    print(output)


if __name__ == "__main__":
    main()
