"""Build the cost-model spreadsheet (Section 6.1): one tab per component of AI spend,
formulas throughout, and Atlas's decomposed month (Table 6.0) as the worked example.
Regenerated each release so that prices stay current:

    python finops/cost-model/build_cost_model.py --out finops/cost-model/cost-model.xlsx

Blue cells are inputs; black cells are formulas. Replace the inputs with your own top
three workloads; the Summary tab gives the month and the unit cost per outcome.
"""
from __future__ import annotations

import argparse
import pathlib

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

INPUT = Font(color="0000CC")
BOLD = Font(bold=True)
HEAD = PatternFill("solid", fgColor="DDE4EE")

# Each tab: (title, intro, header, rows). A row is a list of cells; strings starting
# with "=" are formulas, where {r} is replaced by the row number.
TABS = [
    ("Inference", "On-demand tokens by alias. USD per 1M tokens, symbolic, October 2026.",
     ["Alias", "Model", "Input tokens (M)", "Output tokens (M)", "Input $/1M", "Output $/1M",
      "Input cost", "Output cost", "Total"],
     [["standard", "us.anthropic.claude-sonnet-4-6", 12000, 3800, 3.30, 16.50],
      ["premium", "us.anthropic.claude-opus-4-6-v1", 800, 300, 5.50, 27.50],
      ["fast", "us.amazon.nova-micro-v1:0", 40000, 12000, 0.035, 0.14]],
     ["=C{r}*E{r}", "=D{r}*F{r}", "=G{r}+H{r}"]),
    ("Provisioned", "Reserved capacity (floors). Paid per model-unit hour whether tokens flow or not.",
     ["Floor", "Model units", "$/MU-hour", "Hours", "Utilization", "Cost", "Idle cost"],
     [["support-chatbot floor", 2, 31.50, 730, 0.63]],
     ["=B{r}*C{r}*D{r}", "=F{r}*(1-E{r})"]),
    ("Embeddings", "Generation at ingest and — the sneaky one — regeneration on reindex.",
     ["Activity", "Tokens (M)", "$/1M", "Cost"],
     [["Ingest", 30000, 0.10], ["Reindex (embedding model upgrade)", 60000, 0.10]],
     ["=B{r}*C{r}"]),
    ("Vector", "Vector infrastructure: capacity-shaped money behind a per-request mental model.",
     ["Store", "Units", "$/unit-hour", "Hours", "Cost"],
     [["OpenSearch Serverless (OCU, average)", 80, 0.24, 730], ["Aurora PostgreSQL (pgvector)", 1, 9.589, 730]],
     ["=B{r}*C{r}*D{r}"]),
    ("GPU", "Self-hosted model plane (Section 3.2's utilization math as a monthly report).",
     ["Fleet", "Instances", "$/hour", "Hours", "Storage and other", "Utilization", "Cost"],
     [["pilot g5.48xlarge", 1, 16.288, 730, 2110, 0.31]],
     ["=B{r}*C{r}*D{r}+E{r}"]),
    ("FineTuning", "Training runs plus the dedicated serving a custom model usually requires.",
     ["Item", "Quantity", "Unit cost", "Cost"],
     [["Customization job", 1, 2000], ["Dedicated serving (month)", 1, 5000]],
     ["=B{r}*C{r}"]),
    ("Satellites", "Logs, traces, evaluations (judges burn tokens too) and guardrail text units.",
     ["Item", "Quantity", "Unit cost", "Cost"],
     [["Prompt/response logging (GB-month)", 5000, 0.50], ["Trace retention (GB-month)", 7000, 0.50],
      ["Evaluation judge tokens (M)", 760, 3.30], ["Guardrail text units (thousands)", 3333, 0.75]],
     ["=B{r}*C{r}"]),
]


def build(out: pathlib.Path) -> pathlib.Path:
    wb = Workbook()
    summary = wb.active
    summary.title = "Summary"
    totals = []
    for title, intro, header, rows, formulas in TABS:
        ws = wb.create_sheet(title)
        ws["A1"] = intro
        ws["A1"].font = Font(italic=True)
        for c, h in enumerate(header, start=1):
            cell = ws.cell(row=3, column=c, value=h)
            cell.font, cell.fill = BOLD, HEAD
            ws.column_dimensions[get_column_letter(c)].width = max(14, len(h) + 4)
        ws.column_dimensions["A"].width = 38
        first = 4
        for i, row in enumerate(rows):
            r = first + i
            for c, v in enumerate(row, start=1):
                cell = ws.cell(row=r, column=c, value=v)
                if c > 1 and isinstance(v, (int, float)):
                    cell.font = INPUT
            for j, f in enumerate(formulas):
                ws.cell(row=r, column=len(row) + 1 + j, value=f.format(r=r))
        last = first + len(rows) - 1
        cost_col = get_column_letter(len(rows[0]) + len(formulas) - (1 if title == "Provisioned" else 0))
        if title == "Inference":
            cost_col = "I"
        total_row = last + 2
        ws.cell(row=total_row, column=1, value="Total").font = BOLD
        ws[f"{cost_col}{total_row}"] = f"=SUM({cost_col}{first}:{cost_col}{last})"
        ws[f"{cost_col}{total_row}"].font = BOLD
        totals.append((title, f"='{title}'!{cost_col}{total_row}"))

    summary["A1"] = "AI cost model — one month (Atlas worked example, symbolic, October 2026)"
    summary["A1"].font = Font(bold=True, size=13)
    for c, h in enumerate(["Component", "Cost (USD)", "Share"], start=1):
        cell = summary.cell(row=3, column=c, value=h)
        cell.font, cell.fill = BOLD, HEAD
    for i, (title, ref) in enumerate(totals):
        r = 4 + i
        summary.cell(row=r, column=1, value=title)
        summary.cell(row=r, column=2, value=ref)
        summary.cell(row=r, column=3, value=f"=B{r}/$B${4 + len(totals)}")
    tr = 4 + len(totals)
    summary.cell(row=tr, column=1, value="Total").font = BOLD
    summary.cell(row=tr, column=2, value=f"=SUM(B4:B{tr - 1})").font = BOLD
    summary.cell(row=tr + 2, column=1, value="Outcomes this month (e.g. resolved conversations)")
    summary.cell(row=tr + 2, column=2, value=850000).font = INPUT
    summary.cell(row=tr + 3, column=1, value="Cost per outcome").font = BOLD
    summary.cell(row=tr + 3, column=2, value=f"=B{tr}/B{tr + 2}").font = BOLD
    summary.cell(row=tr + 4, column=1, value="Output share of inference cost")
    summary.cell(row=tr + 4, column=2, value="=SUM(Inference!H4:H6)/Inference!I8")
    summary.column_dimensions["A"].width = 52
    summary.column_dimensions["B"].width = 16
    for r in range(4, tr + 5):
        summary.cell(row=r, column=2).number_format = "#,##0.00"
        summary.cell(row=r, column=3).number_format = "0.0%"
    summary.cell(row=tr + 4, column=2).number_format = "0.0%"
    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(pathlib.Path(__file__).with_name("cost-model.xlsx")))
    print(build(pathlib.Path(ap.parse_args().out)))
