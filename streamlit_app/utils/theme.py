"""
Bluestock brand theme — colors, Plotly template, and shared CSS.

No official Bluestock logo/palette file was found in the project repo, so
this uses a fintech-appropriate deep-blue + cyan palette consistent with the
"Bluestock" name. Drop a real logo at `assets/bluestock_logo.png` and it will
automatically appear in the sidebar (see `render_sidebar_brand()` below).
"""

from __future__ import annotations

from pathlib import Path

import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

# ---------------------------------------------------------------------------
# Palette
# ---------------------------------------------------------------------------
PRIMARY = "#0B3D91"       # deep blue — headers, primary bars
SECONDARY = "#00B4D8"     # cyan — accents, secondary series
ACCENT = "#FFB703"        # gold — highlights, callouts
POSITIVE = "#2E7D32"      # green — positive returns
NEGATIVE = "#C62828"      # red — negative returns / at-risk
BG = "#F5F8FC"
CARD_BG = "#FFFFFF"
TEXT_DARK = "#0B1F3A"
MUTED = "#6B7A99"

CATEGORICAL_SEQUENCE = [
    "#0B3D91", "#00B4D8", "#FFB703", "#2E7D32", "#8E44AD",
    "#C62828", "#F77F00", "#457B9D", "#6A994E", "#9B5DE5",
]

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
LOGO_PATH = ASSETS_DIR / "bluestock_logo.png"


def register_plotly_template() -> None:
    """Register a 'bluestock' Plotly template and make it the default."""
    template = go.layout.Template()
    template.layout = go.Layout(
        colorway=CATEGORICAL_SEQUENCE,
        font=dict(family="Segoe UI, Arial, sans-serif", color=TEXT_DARK, size=13),
        title=dict(font=dict(size=18, color=PRIMARY)),
        paper_bgcolor=CARD_BG,
        plot_bgcolor=CARD_BG,
        xaxis=dict(gridcolor="#E7ECF4", zerolinecolor="#E7ECF4"),
        yaxis=dict(gridcolor="#E7ECF4", zerolinecolor="#E7ECF4"),
        legend=dict(bgcolor="rgba(0,0,0,0)"),
        hoverlabel=dict(bgcolor=PRIMARY, font_color="white", font_size=12),
        margin=dict(l=10, r=10, t=50, b=10),
    )
    pio.templates["bluestock"] = template
    pio.templates.default = "bluestock"


def inject_global_css() -> None:
    st.markdown(
        f"""
        <style>
        .stApp {{
            background-color: {BG};
        }}
        [data-testid="stSidebar"] {{
            background-color: {PRIMARY};
        }}
        [data-testid="stSidebar"] * {{
            color: #FFFFFF !important;
        }}
        .kpi-card {{
            background-color: {CARD_BG};
            border-radius: 14px;
            padding: 18px 20px;
            border: 1px solid #E7ECF4;
            border-top: 4px solid {PRIMARY};
            box-shadow: 0 2px 6px rgba(11,61,145,0.06);
        }}
        .kpi-label {{
            color: {MUTED};
            font-size: 0.82rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            margin-bottom: 4px;
        }}
        .kpi-value {{
            color: {TEXT_DARK};
            font-size: 1.85rem;
            font-weight: 700;
            line-height: 1.1;
        }}
        .kpi-sub {{
            color: {SECONDARY};
            font-size: 0.8rem;
            font-weight: 600;
            margin-top: 4px;
        }}
        h1, h2, h3 {{
            color: {PRIMARY};
        }}
        .bluestock-page-title {{
            display: flex;
            align-items: center;
            gap: 10px;
            border-bottom: 3px solid {SECONDARY};
            padding-bottom: 8px;
            margin-bottom: 18px;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar_brand() -> None:
    with st.sidebar:
        if LOGO_PATH.exists():
            st.image(str(LOGO_PATH), use_container_width=True)
        else:
            st.markdown(
                f"""
                <div style="text-align:center; padding: 6px 0 14px 0;">
                    <span style="font-size:1.6rem; font-weight:800; color:white;">
                        🔷 Bluestock
                    </span><br>
                    <span style="font-size:0.85rem; color:#CFE0FF;">Mutual Fund Analytics</span>
                </div>
                """,
                unsafe_allow_html=True,
            )
        st.caption("Streamlit dashboard — Power BI alternative")
        st.divider()


def kpi_card(label: str, value: str, sub: str | None = None) -> str:
    sub_html = f'<div class="kpi-sub">{sub}</div>' if sub else ""
    return f"""
    <div class="kpi-card">
        <div class="kpi-label">{label}</div>
        <div class="kpi-value">{value}</div>
        {sub_html}
    </div>
    """


def page_title(icon: str, title: str) -> None:
    st.markdown(
        f'<div class="bluestock-page-title"><h1>{icon} {title}</h1></div>',
        unsafe_allow_html=True,
    )
