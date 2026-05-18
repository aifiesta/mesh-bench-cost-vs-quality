"""Generate the 4 blog charts as PNGs in a dark-theme, two-tone style."""
import csv
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
import matplotlib.patches as patches
from matplotlib.patches import FancyBboxPatch
from pathlib import Path

OUT_DIR = Path(__file__).parent
# Pre-rendered mesh_api logo (the full lockup, dark-theme version).
# Source: mesh_api_logo_main_dark_theme.svg, rendered at 1600px and tight-cropped.
LOGO_PATH = OUT_DIR / "_assets_mesh_api_logo.png"

# Palette inspired by reference screenshot (dark navy bg, violet + orange bars)
BG = "#0E1126"
PANEL = "#171a32"
TEXT = "#E6E8F2"
SUBTEXT = "#9CA3B8"
GRID = "#22253E"
VIOLET = "#A78BFA"
VIOLET_DEEP = "#7C5CF5"
ORANGE = "#FB923C"
ORANGE_DEEP = "#F97316"
DOT_GRAY = "#3B3F60"

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 11,
    "text.color": TEXT,
    "axes.facecolor": BG,
    "figure.facecolor": BG,
    "savefig.facecolor": BG,
    "axes.edgecolor": GRID,
    "axes.labelcolor": SUBTEXT,
    "xtick.color": TEXT,
    "ytick.color": SUBTEXT,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.spines.left": False,
    "axes.spines.bottom": False,
    "axes.grid": True,
    "grid.color": GRID,
    "grid.alpha": 0.6,
    "grid.linestyle": "-",
})

with open(OUT_DIR / "pilot_results.csv") as f:
    rows = list(csv.DictReader(f))

def get(task, model):
    for r in rows:
        if r["task"] == task and r["model"] == model:
            return r
    raise KeyError(task, model)

MODELS_DEFAULT = ["GPT-4o-mini", "DeepSeek V4 Pro", "Claude Opus 4.7", "GPT-5.5", "Gemini 2.5 Pro"]
PROVIDER = {
    "GPT-4o-mini": "OpenAI",
    "DeepSeek V4 Pro": "DeepSeek",
    "Claude Opus 4.7": "Anthropic",
    "GPT-5.5": "OpenAI",
    "Gemini 2.5 Pro": "Google",
}
PRICE_NOTE = {
    "GPT-4o-mini": "$0.15 / $0.60 per 1M",
    "DeepSeek V4 Pro": "$1.39 / $2.78 per 1M",
    "Claude Opus 4.7": "$4.25 / $21.25 per 1M",
    "GPT-5.5": "$5.00 / $30.00 per 1M",
    "Gemini 2.5 Pro": "$1.25 / $10.00 per 1M",
}


def pill_legend(ax, items, y=1.04):
    """Render rounded pill legend chips at the top of the axes."""
    fig = ax.figure
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    # We position legend manually using ax.transAxes
    pad_x = 0.012
    pill_h = 0.055
    cx = 0.5  # center horizontally
    # Estimate widths from text length
    widths = []
    for label, color in items:
        widths.append(0.012 * len(label) + 0.06)
    total = sum(widths) + 0.025 * (len(items) - 1)
    x = cx - total / 2
    for (label, color), w in zip(items, widths):
        # Pill background
        box = FancyBboxPatch((x, y), w, pill_h,
                             boxstyle="round,pad=0.005,rounding_size=0.025",
                             linewidth=0.5, edgecolor=GRID, facecolor=PANEL,
                             transform=ax.transAxes, clip_on=False, zorder=5)
        ax.add_patch(box)
        # Color dot
        ax.scatter([x + 0.018], [y + pill_h / 2], s=42, color=color,
                   transform=ax.transAxes, clip_on=False, zorder=6,
                   edgecolors="none")
        # Label
        ax.text(x + 0.034, y + pill_h / 2, label, color=TEXT, fontsize=9.5,
                va="center", ha="left", transform=ax.transAxes, zorder=6)
        x += w + 0.025


def model_labels(ax, models, colors, y_below=-0.10, extras=None):
    """Render model name with colored dot, and provider/pricing sub-label.

    extras: optional list of strings (same length as models) shown on a 3rd line.
    """
    n = len(models)
    for i, m in enumerate(models):
        cx = (i + 0.5) / n
        # Colored dot, sits just left of the name
        ax.scatter([cx - 0.090], [y_below], s=40, color=colors[i],
                   transform=ax.transAxes, clip_on=False, zorder=5,
                   edgecolors="none")
        # Model name (kept short, centered around cx)
        ax.text(cx - 0.075, y_below, m, color=TEXT, fontsize=10.5,
                fontweight="bold", va="center", ha="left",
                transform=ax.transAxes, clip_on=False)
        # Provider line
        ax.text(cx, y_below - 0.045, PROVIDER[m], color=SUBTEXT, fontsize=8,
                va="center", ha="center", transform=ax.transAxes, clip_on=False)
        # Price line
        ax.text(cx, y_below - 0.078, f"{PRICE_NOTE[m]} in/out", color=SUBTEXT,
                fontsize=7.5, va="center", ha="center",
                transform=ax.transAxes, clip_on=False)
        if extras:
            ax.text(cx, y_below - 0.115, extras[i], color=TEXT, fontsize=8,
                    fontweight="bold", va="center", ha="center",
                    transform=ax.transAxes, clip_on=False)


def style_axes(ax, ylabel=None, hide_xticks=True):
    ax.tick_params(axis="x", length=0)
    ax.tick_params(axis="y", length=0, labelsize=9)
    if hide_xticks:
        ax.set_xticks([])
    if ylabel:
        ax.set_ylabel(ylabel, color=SUBTEXT, fontsize=9.5)
    for spine in ax.spines.values():
        spine.set_visible(False)


# Color per-model accent (used for "winner" highlights / dots beside names).
# Each accent is distinct from VIOLET so the dot reads against violet bars too.
ACCENT = {
    "GPT-4o-mini":     "#34D399",   # green
    "DeepSeek V4 Pro": "#60A5FA",   # light blue
    "Claude Opus 4.7": "#F0B36A",   # warm tan
    "GPT-5.5":         "#22D3EE",   # cyan (was violet, blended into bars)
    "Gemini 2.5 Pro":  "#F87171",   # red
}


def add_title(fig, title, subtitle=None):
    fig.text(0.06, 0.96, title, color=TEXT, fontsize=15, fontweight="bold", ha="left", va="top")
    if subtitle:
        fig.text(0.06, 0.92, subtitle, color=SUBTEXT, fontsize=10, ha="left", va="top")


def add_footer(fig, text="Mesh API benchmark  ·  pilot n=5 per task"):
    """Bottom-center footer: full mesh_api logo (lockup) + separator + caption.

    The logo already includes the 'mesh_api' wordmark, so we don't draw a
    separate wordmark; we just place the logo image and the caption text
    side by side on the same baseline.
    """
    foot_y = 0.005
    foot_h = 0.110
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
            logo_h_in = 0.95 * ax_h_in
            logo_w_in = logo_h_in * iw / ih
            logo_w = logo_w_in / ax_w_in
            logo_h = 0.95
            sep_w = 0.010
            caption_w = 0.22
            gap = 0.014
            total = logo_w + gap + sep_w + caption_w
            x = (1 - total) / 2
            foot_ax.imshow(img, extent=(x, x + logo_w, (1 - logo_h)/2, (1 + logo_h)/2),
                           aspect="auto", interpolation="lanczos", zorder=2)
            cx = x + logo_w + gap
            foot_ax.text(cx, 0.5, "·", color=SUBTEXT, fontsize=12, ha="left", va="center")
            cx += sep_w
            foot_ax.text(cx, 0.5, text, color=SUBTEXT, fontsize=10, ha="left", va="center")
            placed = True
        except Exception:
            pass
    if not placed:
        foot_ax.text(0.5, 0.5, f"mesh_api  ·  {text}", color=SUBTEXT,
                     fontsize=9, ha="center", va="center")


# =============================================================================
# Chart 1: Real cost per correct (Task A) ($/correct, log scale)
# Single-metric headline chart, but with pass-rate annotation.
# =============================================================================
def chart_1():
    fig, ax = plt.subplots(figsize=(12, 7.4))
    fig.subplots_adjust(top=0.85, bottom=0.30, left=0.08, right=0.95)
    add_title(fig, "Chart 1: Real cost per correct code answer",
              "Five models, five identical algorithmic problems. Lower bar wins. Log scale.")

    models = sorted(MODELS_DEFAULT, key=lambda m: float(get("task_a", m)["cost_per_correct_usd"]))
    costs = [float(get("task_a", m)["cost_per_correct_usd"]) for m in models]
    pass_rates = [100 * float(get("task_a", m)["pass_rate"]) for m in models]
    colors = [ACCENT[m] for m in models]

    x = np.arange(len(models))
    ax.bar(x, costs, width=0.55, color=VIOLET, edgecolor=VIOLET_DEEP,
           linewidth=1.2, zorder=3)
    ax.set_yscale("log")
    ax.set_ylim(0.00005, 0.5)

    # Dollar label above each bar
    for i, c in enumerate(costs):
        ax.text(i, c * 1.5, f"${c:.4f}", color=TEXT, fontsize=12.5,
                fontweight="bold", ha="center", va="bottom", zorder=4)

    style_axes(ax, ylabel="$ per correct (log)", hide_xticks=True)
    ax.set_xlim(-0.6, len(models) - 0.4)
    ax.set_xticks(x)
    ax.set_xticklabels([])
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"${v:.4f}"))

    # Pass rate as a 4th line under model labels.
    extras = [f"{p:.0f}% pass" for p in pass_rates]
    model_labels(ax, models, colors, y_below=-0.10, extras=extras)
    add_footer(fig)
    plt.savefig(OUT_DIR / "chart_1_real_cost.png", dpi=144, bbox_inches="tight", pad_inches=0.5,
                facecolor=BG)
    plt.close()


# =============================================================================
# Chart 2: Task A scoreboard. Two bars per model (pass rate + $/correct).
# =============================================================================
def chart_2():
    fig, ax = plt.subplots(figsize=(12, 7.2))
    fig.subplots_adjust(top=0.83, bottom=0.27, left=0.08, right=0.92)
    add_title(fig, "Chart 2: Task A scoreboard. Pass rate and $/correct.",
              "Five original code problems. Score is % of test cases passed (left). Cost is dollars per correct solution (right, log).")

    models = sorted(MODELS_DEFAULT, key=lambda m: -float(get("task_a", m)["pass_rate"]))
    pass_rates = [100 * float(get("task_a", m)["pass_rate"]) for m in models]
    costs = []
    for m in models:
        r = get("task_a", m)
        n_correct = int(r["n_correct"])
        costs.append(float(r["effective_cost_usd"]) / n_correct if n_correct else None)

    x = np.arange(len(models))
    w = 0.34
    # Left axis (pass rate) violet bars
    ax.bar(x - w / 2, pass_rates, w, color=VIOLET, edgecolor=VIOLET_DEEP,
           linewidth=1.0, zorder=3)
    ax.set_ylim(0, 130)
    style_axes(ax, ylabel="Pass rate, %", hide_xticks=True)

    # Right axis (cost) orange bars, log
    ax2 = ax.twinx()
    ax2.set_yscale("log")
    ax2.set_ylim(0.00005, 0.5)
    ax2.bar(x + w / 2, costs, w, color=ORANGE, edgecolor=ORANGE_DEEP,
            linewidth=1.0, zorder=3)
    ax2.set_ylabel("$ per correct (log)", color=SUBTEXT, fontsize=9.5)
    ax2.tick_params(axis="y", length=0, labelsize=9, colors=SUBTEXT)
    ax2.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"${v:.4f}"))
    ax2.grid(False)
    for spine in ax2.spines.values():
        spine.set_visible(False)

    # Labels above bars
    for i, p in enumerate(pass_rates):
        ax.text(i - w / 2, p + 5, f"{p:.0f}%", color=TEXT, fontsize=11,
                fontweight="bold", ha="center", va="bottom", zorder=4)
    for i, c in enumerate(costs):
        if c is not None:
            ax2.text(i + w / 2, c * 1.5, f"${c:.4f}", color=TEXT, fontsize=11,
                     fontweight="bold", ha="center", va="bottom", zorder=4)

    ax.set_xticks(x)
    ax.set_xticklabels([])
    ax.set_xlim(-0.7, len(models) - 0.3)

    pill_legend(ax, [("Pass rate, %", VIOLET), ("$/correct, log", ORANGE)], y=1.04)
    model_labels(ax, models, [ACCENT[m] for m in models], y_below=-0.10)
    add_footer(fig)
    plt.savefig(OUT_DIR / "chart_2_task_a.png", dpi=144, bbox_inches="tight", pad_inches=0.5,
                facecolor=BG)
    plt.close()


# =============================================================================
# Chart 3: Task B scoreboard. Two bars per model (quality + $/qual-pt).
# =============================================================================
def chart_3():
    fig, ax = plt.subplots(figsize=(12, 7.2))
    fig.subplots_adjust(top=0.83, bottom=0.27, left=0.08, right=0.92)
    add_title(fig, "Chart 3: Task B scoreboard. Quality and $/quality-point.",
              "Five customer-support tickets. Quality is the LLM judge mean (1 to 5, error bars span temp 0.0 and 0.3). Cost is dollars per quality-point.")

    models = sorted(MODELS_DEFAULT, key=lambda m: -float(get("task_b_support", m)["quality_score"]))
    quality = [float(get("task_b_support", m)["quality_score"]) for m in models]
    variance = [float(get("task_b_support", m)["quality_variance"]) for m in models]
    cost_per_q = [float(get("task_b_support", m)["cost_per_quality_usd"]) for m in models]

    x = np.arange(len(models))
    w = 0.34
    ax.bar(x - w / 2, quality, w, yerr=variance, capsize=4,
           color=VIOLET, edgecolor=VIOLET_DEEP, linewidth=1.0, zorder=3,
           error_kw={"ecolor": TEXT, "elinewidth": 1.0, "alpha": 0.8})
    ax.set_ylim(0, 6.5)
    style_axes(ax, ylabel="Quality, 1 to 5", hide_xticks=True)

    ax2 = ax.twinx()
    ax2.set_yscale("log")
    ax2.set_ylim(0.00005, 0.2)
    ax2.bar(x + w / 2, cost_per_q, w, color=ORANGE, edgecolor=ORANGE_DEEP,
            linewidth=1.0, zorder=3)
    ax2.set_ylabel("$ per quality-point (log)", color=SUBTEXT, fontsize=9.5)
    ax2.tick_params(axis="y", length=0, labelsize=9, colors=SUBTEXT)
    ax2.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"${v:.4f}"))
    ax2.grid(False)
    for spine in ax2.spines.values():
        spine.set_visible(False)

    for i, (q, v) in enumerate(zip(quality, variance)):
        ax.text(i - w / 2, q + v + 0.18, f"{q:.2f}", color=TEXT, fontsize=11,
                fontweight="bold", ha="center", va="bottom", zorder=4)
    for i, c in enumerate(cost_per_q):
        ax2.text(i + w / 2, c * 1.5, f"${c:.4f}", color=TEXT, fontsize=11,
                 fontweight="bold", ha="center", va="bottom", zorder=4)

    ax.set_xticks(x)
    ax.set_xticklabels([])
    ax.set_xlim(-0.7, len(models) - 0.3)

    pill_legend(ax, [("Quality, 1 to 5", VIOLET), ("$/qual-pt, log", ORANGE)], y=1.04)
    model_labels(ax, models, [ACCENT[m] for m in models], y_below=-0.10)
    add_footer(fig)
    plt.savefig(OUT_DIR / "chart_3_task_b.png", dpi=144, bbox_inches="tight", pad_inches=0.5,
                facecolor=BG)
    plt.close()


# =============================================================================
# Chart 4: Combined $/quality across both tasks. Horizontal bars, log.
# =============================================================================
def chart_4():
    fig, ax = plt.subplots(figsize=(11, 5.6))
    fig.subplots_adjust(top=0.84, bottom=0.16, left=0.20, right=0.95)
    add_title(fig, "Chart 4: Combined $/quality across both tasks",
              "Task A pass rate scaled to a 0 to 5 quality value, averaged with Task B's judge score. Log scale spans three orders of magnitude.")

    combo = []
    for m in MODELS_DEFAULT:
        a = get("task_a", m); b = get("task_b_support", m)
        pass_q = float(a["pass_rate"]) * 5
        qual_b = float(b["quality_score"])
        eff_total = float(a["effective_cost_usd"]) + float(b["effective_cost_usd"])
        combined_q = (pass_q + qual_b) / 2
        cost_per_q = eff_total / combined_q if combined_q else None
        combo.append((m, combined_q, cost_per_q))
    combo.sort(key=lambda t: t[2] or 0)

    names = [c[0] for c in combo]
    costs = [c[2] for c in combo]
    qs = [c[1] for c in combo]
    colors = [ACCENT[m] for m in names]

    y = np.arange(len(names))
    ax.barh(y, costs, height=0.55, color=VIOLET, edgecolor=VIOLET_DEEP,
            linewidth=1.0, zorder=3)
    ax.set_xscale("log")
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"${v:.4f}"))
    ax.set_xlim(0.0001, 0.5)
    ax.invert_yaxis()
    ax.set_yticks(y)
    ax.set_yticklabels(names, color=TEXT, fontsize=11.5, fontweight="bold")
    ax.tick_params(axis="y", length=0)
    ax.tick_params(axis="x", length=0, labelsize=9)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.grid(axis="x", color=GRID, alpha=0.6)
    ax.grid(axis="y", visible=False)

    # Annotate each bar
    for i, (n, q, c) in enumerate(combo):
        ax.text(c * 1.15, i, f"${c:.5f}    quality {q:.2f} / 5",
                color=TEXT, fontsize=10.5, va="center", ha="left",
                fontweight="bold")
        # Colored dot to the left of the model name
        ax.scatter([0.00012], [i], s=55, color=colors[i], zorder=5, edgecolors="none",
                   clip_on=False)

    ax.set_xlabel("$ per quality-point across both tasks (log scale)",
                  color=SUBTEXT, fontsize=9.5)
    add_footer(fig)
    plt.savefig(OUT_DIR / "chart_4_cross_task.png", dpi=144, bbox_inches="tight", pad_inches=0.5,
                facecolor=BG)
    plt.close()


chart_1()
chart_2()
chart_3()
chart_4()

print("Wrote:")
for f in ["chart_1_real_cost.png", "chart_2_task_a.png", "chart_3_task_b.png", "chart_4_cross_task.png"]:
    p = OUT_DIR / f
    print(f"  {p.name}  {p.stat().st_size // 1024} KB")
