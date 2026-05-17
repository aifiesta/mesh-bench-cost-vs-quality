"""Render the blog's data tables as standalone PNGs.

Same dark theme as the charts. Each PNG is sized for X-thread embeds
(roughly 1600 x 900, 16:9). Footer carries the mesh_api icon + wordmark.
"""
import csv
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
import matplotlib.patches as patches
from matplotlib.patches import FancyBboxPatch, Rectangle

OUT_DIR = Path(__file__).parent
LOGO_PATH = Path("/Users/raushan/Documents/Career/AiFiesta/MeshAPI/marketing/Branding/mesh_api_logo_v2/mesh_api_logo_icon.png")

# Palette matches make_charts.py
BG = "#0E1126"
PANEL = "#171A32"
PANEL_2 = "#1E2240"
BORDER = "#22253E"
TEXT = "#E6E8F2"
MUTED = "#9CA3B8"
VIOLET = "#A78BFA"
VIOLET_DEEP = "#7C5CF5"
ORANGE = "#FB923C"
GREEN = "#34D399"
RED = "#F87171"
TAN = "#F0B36A"

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "text.color": TEXT,
    "axes.facecolor": BG,
    "figure.facecolor": BG,
    "savefig.facecolor": BG,
})


def add_title(fig, title, subtitle=None):
    fig.text(0.05, 0.95, title, color=TEXT, fontsize=18, fontweight="bold",
             ha="left", va="top")
    if subtitle:
        fig.text(0.05, 0.90, subtitle, color=MUTED, fontsize=11, ha="left", va="top")


def add_footer(fig, text="Mesh API benchmark  ·  pilot n=5 per task  ·  github.com/aifiesta/mesh-bench-cost-vs-quality"):
    foot_y = 0.012
    foot_h = 0.05
    foot_ax = fig.add_axes([0.0, foot_y, 1.0, foot_h], frameon=False)
    foot_ax.set_xlim(0, 1); foot_ax.set_ylim(0, 1)
    foot_ax.set_xticks([]); foot_ax.set_yticks([])
    for s in foot_ax.spines.values(): s.set_visible(False)
    foot_ax.patch.set_alpha(0)
    placed = False
    if LOGO_PATH.exists():
        try:
            img = mpimg.imread(str(LOGO_PATH))
            ih, iw = img.shape[0], img.shape[1]
            fig_w_in, fig_h_in = fig.get_size_inches()
            ax_w_in = fig_w_in
            ax_h_in = fig_h_in * foot_h
            icon_h_in = 0.7 * ax_h_in
            icon_w_in = icon_h_in * iw / ih
            icon_w = icon_w_in / ax_w_in
            wordmark_w = 0.060
            sep_w = 0.010
            caption_w = 0.62
            gap = 0.008
            total = icon_w + gap + wordmark_w + sep_w + caption_w
            x = (1 - total) / 2
            foot_ax.imshow(img, extent=(x, x + icon_w, 0.15, 0.85),
                           aspect="auto", interpolation="lanczos", zorder=2)
            cx = x + icon_w + gap
            foot_ax.text(cx, 0.5, "mesh_api", color=TEXT, fontsize=11,
                         fontweight="bold", ha="left", va="center")
            cx += wordmark_w
            foot_ax.text(cx, 0.5, "·", color=MUTED, fontsize=11, ha="left", va="center")
            cx += sep_w
            foot_ax.text(cx, 0.5, text, color=MUTED, fontsize=9, ha="left", va="center")
            placed = True
        except Exception:
            pass
    if not placed:
        foot_ax.text(0.5, 0.5, f"mesh_api  ·  {text}", color=MUTED,
                     fontsize=9, ha="center", va="center")


def draw_table(fig, ax, headers, rows, col_aligns=None, col_widths=None,
               highlight_rows=None, color_cells=None):
    """Render a table on ax. Coordinates in axes-fraction (0..1).

    headers: list of column header strings
    rows: list of row tuples (one tuple per row, len = len(headers))
    col_aligns: list of 'left' | 'right' | 'center' per col
    col_widths: list of fractional widths per col (must sum to 1.0)
    highlight_rows: set of row indices to highlight as 'winner'
    color_cells: dict mapping (row_idx, col_idx) -> color string for that cell text
    """
    n_cols = len(headers)
    n_rows = len(rows)
    if col_aligns is None:
        col_aligns = ["left"] + ["right"] * (n_cols - 1)
    if col_widths is None:
        col_widths = [1.0 / n_cols] * n_cols
    if highlight_rows is None:
        highlight_rows = set()
    if color_cells is None:
        color_cells = {}

    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    # Vertical layout
    header_h = 0.10
    row_h = (1.0 - header_h) / n_rows
    y_header_top = 1.0
    y_header_bot = y_header_top - header_h

    # Header background
    ax.add_patch(Rectangle((0, y_header_bot), 1.0, header_h,
                           linewidth=0, facecolor=PANEL_2, zorder=1))
    # Bottom border under header
    ax.plot([0, 1.0], [y_header_bot, y_header_bot], color=BORDER, linewidth=1, zorder=2)

    # Cumulative x positions for columns
    x_cuts = [0.0]
    acc = 0.0
    for w in col_widths:
        acc += w
        x_cuts.append(acc)

    pad = 0.014
    for ci, h in enumerate(headers):
        align = col_aligns[ci]
        if align == "left":
            tx = x_cuts[ci] + pad; ha = "left"
        elif align == "right":
            tx = x_cuts[ci + 1] - pad; ha = "right"
        else:
            tx = (x_cuts[ci] + x_cuts[ci + 1]) / 2; ha = "center"
        ax.text(tx, y_header_bot + header_h / 2, h.upper(), color=MUTED,
                fontsize=10, fontweight="bold", ha=ha, va="center",
                family="DejaVu Sans", zorder=3)

    # Rows
    for ri, row in enumerate(rows):
        y_top = y_header_bot - ri * row_h
        y_bot = y_top - row_h
        is_winner = ri in highlight_rows
        # Row bg (alternating very faint stripe + winner accent)
        if is_winner:
            ax.add_patch(Rectangle((0, y_bot), 1.0, row_h,
                                   linewidth=0, facecolor="#15291E", zorder=1))
            # Left accent stripe
            ax.add_patch(Rectangle((0, y_bot), 0.005, row_h,
                                   linewidth=0, facecolor=GREEN, zorder=2))
        else:
            bg = PANEL if ri % 2 == 0 else BG
            ax.add_patch(Rectangle((0, y_bot), 1.0, row_h,
                                   linewidth=0, facecolor=bg, zorder=1))
        # Row separator
        ax.plot([0, 1.0], [y_bot, y_bot], color=BORDER, linewidth=0.5, zorder=2)

        for ci, val in enumerate(row):
            align = col_aligns[ci]
            if align == "left":
                tx = x_cuts[ci] + pad; ha = "left"
            elif align == "right":
                tx = x_cuts[ci + 1] - pad; ha = "right"
            else:
                tx = (x_cuts[ci] + x_cuts[ci + 1]) / 2; ha = "center"
            cell_color = color_cells.get((ri, ci))
            color = cell_color or (GREEN if is_winner and ci == 0 else TEXT)
            weight = "bold" if (is_winner and ci == 0) or cell_color else "normal"
            ax.text(tx, y_top - row_h / 2, str(val), color=color,
                    fontsize=12, fontweight=weight, ha=ha, va="center",
                    family="DejaVu Sans" if ci == 0 else "DejaVu Sans Mono",
                    zorder=3)


# ---------------------------------------------------------------------------
# Load data once
# ---------------------------------------------------------------------------
with open(OUT_DIR / "pilot_results.csv") as f:
    agg_rows = list(csv.DictReader(f))

def agg(task, model):
    for r in agg_rows:
        if r["task"] == task and r["model"] == model:
            return r
    raise KeyError(task, model)


# ===========================================================================
# Table 1: Price card
# ===========================================================================
def table_1_pricing():
    fig = plt.figure(figsize=(12, 6.8))
    add_title(fig, "Models and list prices",
              "Per 1M tokens. Mesh API applies a 15% discount on Claude Opus 4.7 (in parens).")
    ax = fig.add_axes([0.05, 0.10, 0.90, 0.78])
    headers = ["Model", "Provider", "Tier", "List $/M in", "List $/M out"]
    rows = [
        ("GPT-5.5",          "OpenAI",     "Frontier", "$5.00",  "$30.00"),
        ("Claude Opus 4.7",  "Anthropic",  "Frontier", "$5.00 ($4.25)",  "$25.00 ($21.25)"),
        ("DeepSeek V4 Pro",  "DeepSeek",   "Mid",      "$1.39",  "$2.78"),
        ("Gemini 2.5 Pro",   "Google",     "Mid",      "$1.25",  "$10.00"),
        ("GPT-4o-mini",      "OpenAI",     "Workhorse","$0.15",  "$0.60"),
    ]
    draw_table(fig, ax, headers, rows,
               col_aligns=["left", "left", "left", "right", "right"],
               col_widths=[0.26, 0.18, 0.16, 0.20, 0.20])
    add_footer(fig)
    fig.savefig(OUT_DIR / "table_1_pricing.png", dpi=144, bbox_inches="tight", facecolor=BG)
    plt.close(fig)


# ===========================================================================
# Table 2: Headline result
# ===========================================================================
def table_2_headline():
    fig = plt.figure(figsize=(13, 7.2))
    add_title(fig, "Pilot results, n=5 per task",
              "GPT-4o-mini wins both axes. Four of five models tied at 100% on the code test.")
    ax = fig.add_axes([0.04, 0.10, 0.92, 0.78])
    headers = ["Model", "Code pass", "Code $/correct", "Support quality (1-5)", "Support $/qual-pt"]
    models = ["GPT-4o-mini", "DeepSeek V4 Pro", "Claude Opus 4.7", "GPT-5.5", "Gemini 2.5 Pro"]
    rows = []
    color_cells = {}
    for i, m in enumerate(models):
        a = agg("task_a", m); b = agg("task_b_support", m)
        n_correct = int(a["n_correct"])
        pass_str = f"{n_correct}/5"
        pc = f"${float(a['cost_per_correct_usd']):.4f}" if a['cost_per_correct_usd'] else "n/a"
        q = float(b["quality_score"])
        v = float(b["quality_variance"])
        qstr = f"{q:.2f} ± {v:.2f}"
        pq = f"${float(b['cost_per_quality_usd']):.5f}"
        rows.append((m, pass_str, pc, qstr, pq))
        # Mark the per-axis bests
        if m == "GPT-4o-mini":
            color_cells[(i, 2)] = GREEN  # Best $/correct
            color_cells[(i, 4)] = GREEN  # Best $/qpt
        if m == "Claude Opus 4.7":
            color_cells[(i, 3)] = TAN    # Best quality
        if m == "Gemini 2.5 Pro":
            color_cells[(i, 1)] = RED    # Worst pass rate
            color_cells[(i, 2)] = RED
    draw_table(fig, ax, headers, rows,
               col_aligns=["left", "center", "right", "center", "right"],
               col_widths=[0.24, 0.13, 0.18, 0.22, 0.23],
               highlight_rows={0},
               color_cells=color_cells)
    add_footer(fig)
    fig.savefig(OUT_DIR / "table_2_headline.png", dpi=144, bbox_inches="tight", facecolor=BG)
    plt.close(fig)


# ===========================================================================
# Table 3: Tokenizer tax (input-side, measured)
# ===========================================================================
def table_3_tokenizer():
    fig = plt.figure(figsize=(12, 6.8))
    add_title(fig, "The tokenizer tax (measured on this run's prompts)",
              "Same 10 English prompts to every model. Input-token counts as reported by each provider's usage field.")
    ax = fig.add_axes([0.05, 0.10, 0.90, 0.78])
    headers = ["Model", "Input tokens for 10 prompts", "Delta vs OpenAI baseline"]
    rows = [
        ("GPT-4o-mini (OpenAI)",  "1,544", "baseline"),
        ("GPT-5.5 (OpenAI)",      "1,534", "-0.6%"),
        ("DeepSeek V4 Pro",        "1,582", "+2.5%"),
        ("Gemini 2.5 Pro",         "1,637", "+6.0%"),
        ("Claude Opus 4.7",        "2,468", "+59.8%"),
    ]
    color_cells = {(4, 1): ORANGE, (4, 2): ORANGE}
    draw_table(fig, ax, headers, rows,
               col_aligns=["left", "right", "right"],
               col_widths=[0.36, 0.32, 0.32],
               highlight_rows=set(),  # don't mark a winner; outlier is the story
               color_cells=color_cells)
    add_footer(fig)
    fig.savefig(OUT_DIR / "table_3_tokenizer.png", dpi=144, bbox_inches="tight", facecolor=BG)
    plt.close(fig)


# ===========================================================================
# Table 4: Cost ratios
# ===========================================================================
def table_4_cost_ratios():
    fig = plt.figure(figsize=(12, 6.8))
    add_title(fig, "Cost ratio per correct code answer",
              "All five models on the same 5 problems. GPT-4o-mini is the baseline.")
    ax = fig.add_axes([0.05, 0.10, 0.90, 0.78])
    headers = ["Model", "$/correct", "Multiple vs GPT-4o-mini"]
    models_sorted = ["GPT-4o-mini", "DeepSeek V4 Pro", "Claude Opus 4.7", "GPT-5.5", "Gemini 2.5 Pro"]
    base_pc = float(agg("task_a", "GPT-4o-mini")["cost_per_correct_usd"])
    rows = []
    color_cells = {}
    for i, m in enumerate(models_sorted):
        a = agg("task_a", m)
        pc = float(a["cost_per_correct_usd"])
        ratio = pc / base_pc
        if i == 0:
            ratio_str = "1x (baseline)"
        else:
            ratio_str = f"{ratio:,.0f}x"
        rows.append((m, f"${pc:.5f}", ratio_str))
        if m == "Gemini 2.5 Pro":
            color_cells[(i, 2)] = RED
        elif m == "GPT-5.5":
            color_cells[(i, 2)] = ORANGE
    draw_table(fig, ax, headers, rows,
               col_aligns=["left", "right", "right"],
               col_widths=[0.40, 0.28, 0.32],
               highlight_rows={0},
               color_cells=color_cells)
    add_footer(fig)
    fig.savefig(OUT_DIR / "table_4_cost_ratios.png", dpi=144, bbox_inches="tight", facecolor=BG)
    plt.close(fig)


# ===========================================================================
# Table 5: Latency
# ===========================================================================
def table_5_latency():
    fig = plt.figure(figsize=(12, 6.8))
    add_title(fig, "Average latency per call",
              "Wall-clock from request to response, averaged across the pilot's 5 items per task.")
    ax = fig.add_axes([0.05, 0.10, 0.90, 0.78])
    headers = ["Model", "Task A (code)", "Task B (support)"]
    models_order = ["GPT-4o-mini", "Claude Opus 4.7", "GPT-5.5", "Gemini 2.5 Pro", "DeepSeek V4 Pro"]
    rows = []
    color_cells = {}
    for i, m in enumerate(models_order):
        a = agg("task_a", m); b = agg("task_b_support", m)
        la = float(a["avg_latency_ms"]) / 1000
        lb = float(b["avg_latency_ms"]) / 1000
        rows.append((m, f"{la:.1f} s", f"{lb:.1f} s"))
        if la > 20:
            color_cells[(i, 1)] = RED
        if lb > 15:
            color_cells[(i, 2)] = RED
    draw_table(fig, ax, headers, rows,
               col_aligns=["left", "right", "right"],
               col_widths=[0.46, 0.27, 0.27],
               highlight_rows={0},
               color_cells=color_cells)
    add_footer(fig)
    fig.savefig(OUT_DIR / "table_5_latency.png", dpi=144, bbox_inches="tight", facecolor=BG)
    plt.close(fig)


# ===========================================================================
# Run
# ===========================================================================
table_1_pricing()
table_2_headline()
table_3_tokenizer()
table_4_cost_ratios()
table_5_latency()

print("Wrote:")
for name in ["table_1_pricing.png", "table_2_headline.png", "table_3_tokenizer.png",
             "table_4_cost_ratios.png", "table_5_latency.png"]:
    p = OUT_DIR / name
    print(f"  {name}  {p.stat().st_size // 1024} KB")
