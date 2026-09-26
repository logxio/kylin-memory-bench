#!/usr/bin/env python3
"""Generate the short Chinese project brief with ReportLab."""

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
    label(c, "kylin-memory-bench · 开源长期记忆评测", LEFT, 30, 8)
    label(c, str(number) + " / 2", RIGHT - 26, 30, 8)


def first_page(c):
    label(c, "OPENKYLIN / 2026", LEFT, HEIGHT - 53, 9)
    label(c, "kylin-memory-bench", LEFT, HEIGHT - 95, 24, colors.HexColor("#111111"))
    y = para(c, "让长期记忆的判断落到可复查的回复、记忆记录与实际文件。", LEFT,
             HEIGHT - 112, RIGHT - LEFT, 12, 20)
    rule(c, y - 22)
    y -= 48
    label(c, "问题", LEFT, y, 13, colors.HexColor("#111111"))
    y = para(c, "只问智能体“还记得吗”，不足以发现它把旧值继续用于任务、混淆相似实体，或把临时信息错误地写进长期记忆。评测必须跨会话，并对真实行动留证。", LEFT, y - 17, RIGHT - LEFT)
    y -= 31
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
        yy = y - row * 48
        label(c, name, x, yy, 11, colors.HexColor("#111111"))
        label(c, detail, x, yy - 18, 9)
    y -= 3 * 48 + 12
    rule(c, y)
    y -= 32
    label(c, "运行链", LEFT, y, 13, colors.HexColor("#111111"))
    y = para(c, "任务 JSON → 两款智能体适配器 → 原始回复 / 帧 / 文件 → 确定性检查项 → 六维分数、逐项原因和 SVG 雷达图。缺证据不得分；口头称已写文件，仍须核对文件内容。", LEFT, y - 16, RIGHT - LEFT)
    y -= 25
    label(c, "本机读数", LEFT, y, 13, colors.HexColor("#111111"))
    y = para(c, "两个<b>虚构替身</b>走完整 CLI：参考替身六维 100，故意出错的替身总分 19.45。更新旧值、禁存验证码和错误分隔符均被扣分。这只验证流水线，<b>不是 KylinBot 或 OpenClaw 的成绩</b>。", LEFT, y - 16, RIGHT - LEFT)
    footer(c, 1)
    c.showPage()


def second_page(c):
    label(c, "HOW IT IS SCORED", LEFT, HEIGHT - 53, 9)
    label(c, "从证据到可解释分数", LEFT, HEIGHT - 91, 19, colors.HexColor("#111111"))
    y = para(c, "四类检查：回复 JSON 字段、产物 JSON 字段、禁用值是否出现在回复，以及禁用值是否出现在可观察的记忆文件。每项报告 pass / fail / missing 与来源。六维各自归一，再取均值。", LEFT, HEIGHT - 110, RIGHT - LEFT)
    y -= 26
    label(c, "任务书评分项", LEFT, y, 12, colors.HexColor("#111111"))
    y -= 24
    rows = [
        ("任务定义与通用性", "15%", "六项跨会话任务与统一接口"),
        ("数据设计质量", "25%", "虚构样本、旧值与禁用值、行动核验"),
        ("自动评分能力", "25%", "原始证据、结构化判断与原因"),
        ("稳定性与可复现性", "15%", "指纹、隔离输出、运行 ID、合同测试"),
        ("指标完整性", "10%", "六维分、总分、JSON、雷达图"),
        ("创新与工程落地", "10%", "回复 + 记忆 + 文件联合裁决"),
    ]
    for name, weight, detail in rows:
        rule(c, y + 10)
        label(c, name, LEFT, y - 7, 10, colors.HexColor("#111111"))
        label(c, weight, LEFT + 150, y - 7, 10, colors.HexColor("#111111"))
        label(c, detail, LEFT + 205, y - 7, 9)
        y -= 37
    rule(c, y + 10)
    y -= 26
    label(c, "真实运行入口", LEFT, y, 12, colors.HexColor("#111111"))
    y = para(c, "KylinBot 通过 Gateway 的 kylinbot.v1 WebSocket 对话；OpenClaw 通过带固定 session key 的 agent CLI。run-live.sh 从同一数据集批量运行两个配置，产出完整结果和雷达图。deb 构建脚本随仓提供。", LEFT, y - 17, RIGHT - LEFT)
    y -= 23
    label(c, "当前边界与下一发", LEFT, y, 12, colors.HexColor("#111111"))
    y = para(c, "公开代码与替身样例已具备。仍须在 openKylin 云桌面安装两款真实智能体、核实记忆目录和包依赖、跑完整批次，并录 3–5 分钟真实桌面演示。六维目前各一条任务，后续扩充多样本与独立重复运行。", LEFT, y - 17, RIGHT - LEFT)
    y -= 18
    para(c, "代码、任务、评分器与方案：<link href='https://github.com/logxio/kylin-memory-bench'>github.com/logxio/kylin-memory-bench</link>", LEFT, y, RIGHT - LEFT, 9, 14)
    footer(c, 2)
    c.showPage()


def main():
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("docs/intro.pdf")
    output.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(output), pagesize=A4, pageCompression=1)
    c.setTitle("kylin-memory-bench 项目介绍")
    c.setAuthor("Yan Su")
    c.setCreator("kylin-memory-bench")
    first_page(c)
    second_page(c)
    c.save()
    print(output)


if __name__ == "__main__":
    main()
