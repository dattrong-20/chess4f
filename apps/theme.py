"""Shared colors and Plotly styling for the chess4f dashboard.

Dark chess.com-like palette: charcoal surfaces, warm text, green accent.
"""

COLORS = dict(
    primary="#81B64C",
    white="#5B9BD5",
    draw="#8A8A84",
    black="#E08A3C",
    accent="#D9A441",
    grid="rgba(232,230,227,0.10)",
)

TEXT = "#E8E6E3"
PANEL = "#262421"
BORDER = "#3D3A37"

# Keyed by the Vietnamese labels the data frames actually use.
WDL = {"Trắng thắng": COLORS["white"], "Hòa": COLORS["draw"], "Đen thắng": COLORS["black"]}
WDL_SHORT = {"Thắng": COLORS["white"], "Hòa": COLORS["draw"], "Thua": COLORS["black"]}


def style(fig, height=520, **layout):
    """Apply the shared theme and return the figure for chaining."""
    settings = dict(
        height=height,
        margin=dict(t=24, b=24, l=8, r=8),
        font=dict(size=13, color=TEXT),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        hoverlabel=dict(bgcolor=PANEL, bordercolor=BORDER, font=dict(color=TEXT)),
        legend_title_text="",
    )
    settings.update(layout)
    fig.update_layout(**settings)
    fig.update_xaxes(showgrid=True, gridcolor=COLORS["grid"], zeroline=False,
                     linecolor=BORDER, tickfont=dict(color=TEXT), title_font=dict(color=TEXT))
    fig.update_yaxes(showgrid=True, gridcolor=COLORS["grid"], zeroline=False,
                     linecolor=BORDER, tickfont=dict(color=TEXT), title_font=dict(color=TEXT))
    return fig


def thousands(value):
    return f"{value:,.0f}"
