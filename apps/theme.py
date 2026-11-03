"""Shared colors and Plotly styling for the chess4f dashboard.

Keeps every chart visually consistent: one palette, white template, transparent
backgrounds, subtle gridlines and clean hover labels.
"""

COLORS = dict(
    primary="#3155d9",
    white="#247ba0",
    draw="#aab2bd",
    black="#ed9135",
    accent="#f59e0b",
    grid="rgba(148,163,184,0.18)",
)

# Keyed by the Vietnamese labels the data frames actually use.
WDL = {"Trắng thắng": COLORS["white"], "Hòa": COLORS["draw"], "Đen thắng": COLORS["black"]}
WDL_SHORT = {"Thắng": COLORS["white"], "Hòa": COLORS["draw"], "Thua": COLORS["black"]}


def style(fig, height=520, **layout):
    """Apply the shared theme and return the figure for chaining."""
    settings = dict(
        height=height,
        margin=dict(t=24, b=24, l=8, r=8),
        font=dict(size=13, color="#0f172a"),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        hoverlabel=dict(bgcolor="white", bordercolor="#cbd5e1", font=dict(color="#0f172a")),
        legend_title_text="",
    )
    settings.update(layout)
    fig.update_layout(**settings)
    fig.update_xaxes(showgrid=True, gridcolor=COLORS["grid"], zeroline=False)
    fig.update_yaxes(showgrid=True, gridcolor=COLORS["grid"], zeroline=False)
    return fig


def thousands(value):
    return f"{value:,.0f}"
