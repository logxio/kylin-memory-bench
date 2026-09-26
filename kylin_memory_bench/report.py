"""Plain text and dependency-free SVG summaries."""

import html
import math

from .model import ABILITIES


LABELS = {
    "retention": "长期保持", "recall": "记忆调用", "update": "动态更新",
    "discrimination": "相近区分", "boundary": "边界识别", "task_reuse": "任务复用",
}


def text_report(result):
    lines = ["Long-term memory benchmark", "Evidence class: " + result["evidence_class"],
             "Dataset SHA-256: " + result["dataset_fingerprint"], ""]
    for agent in result["agents"]:
        lines.append(agent["name"] + " [" + agent["evidence_class"] + "]")
        lines.append("Overall: " + str(agent["scores"]["overall"]))
        for ability, value in agent["scores"]["dimensions"].items():
            lines.append("  " + LABELS[ability] + ": " + ("no cases" if value is None else str(value)))
        for case in agent["scores"]["cases"]:
            lines.append("  " + case["id"] + " " + str(case["score"]))
            for check in case["checks"]:
                lines.append("    " + check["status"].upper() + " " + check["id"] + ": " + check["reason"])
        lines.append("")
    return "\n".join(lines)


def radar_svg(result):
    cx, cy, radius = 320, 260, 155
    def point(index, value):
        angle = math.radians(-90 + 60 * index)
        return (cx + radius * value / 100 * math.cos(angle),
                cy + radius * value / 100 * math.sin(angle))
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="760" height="560" viewBox="0 0 760 560">',
             '<rect width="100%" height="100%" fill="white"/>',
             '<style>text{font:14px sans-serif;fill:#222}.grid{fill:none;stroke:#ddd}.axis{stroke:#ccc}.series{fill-opacity:.13;stroke-width:2}</style>',
             '<text x="30" y="35" font-size="19">Long-term memory evidence</text>']
    for value in (25, 50, 75, 100):
        coords = " ".join("%.1f,%.1f" % point(i, value) for i in range(6))
        parts.append('<polygon class="grid" points="' + coords + '"/>')
    for i, ability in enumerate(ABILITIES):
        x, y = point(i, 100)
        lx, ly = point(i, 121)
        parts.append('<line class="axis" x1="%d" y1="%d" x2="%.1f" y2="%.1f"/>' % (cx, cy, x, y))
        parts.append('<text x="%.1f" y="%.1f" text-anchor="middle">%s</text>' % (lx, ly + 5, LABELS[ability]))
    colors = ("#2165a3", "#ce5a30", "#388563", "#7a56a6")
    for index, agent in enumerate(result["agents"]):
        color = colors[index % len(colors)]
        values = agent["scores"]["dimensions"]
        coords = " ".join("%.1f,%.1f" % point(i, values[a] or 0) for i, a in enumerate(ABILITIES))
        parts.append('<polygon class="series" fill="' + color + '" stroke="' + color + '" points="' + coords + '"/>')
        parts.append('<text x="565" y="%d" fill="%s">%s (%s)</text>' %
                     (100 + index * 28, color, html.escape(agent["name"]), html.escape(agent["evidence_class"])))
    parts.append('</svg>')
    return "\n".join(parts) + "\n"
