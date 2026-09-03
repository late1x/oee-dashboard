import json
import os
from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

DATA_FILE = os.path.join(os.path.dirname(__file__), "data.json")

LIST_BMM = ["801", "802", "803"]

DEFAULT_DATA = {
    "meta": {"oee_meta": 87, "oee_margen": 13},
    "registros": [],
}

MESES_ABREV = {
    1: "Ene", 2: "Feb", 3: "Mar", 4: "Abr", 5: "May", 6: "Jun",
    7: "Jul", 8: "Ago", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dic",
}


def formato_fecha_larga(fecha: date) -> str:
    """Ej: 03 Sep 2026 (evita depender del locale del sistema)."""
    return f"{fecha.day:02d} {MESES_ABREV[fecha.month]} {fecha.year}"

# Paleta: un color fijo por sopladora (identidad) + colores de estado
# (cumple / no cumple), reservados y nunca reutilizados como color de serie.
BMM_COLORS = {
    "801": "#2a78d6",  # azul
    "802": "#eb6834",  # naranja
    "803": "#1baf7a",  # aqua
}
COLOR_REFERENCIA = "#a8abb2"  # gris - líneas de meta/margen permitido
COLOR_CUMPLE = "#1a9c4b"      # verde - estado "cumple"
COLOR_NO_CUMPLE = "#e6483f"   # rojo - estado "no cumple"
COLOR_MUTED = "#767a82"       # gris - texto secundario

CHART_TEMPLATE = "plotly_white"
CHART_FONT_SIZE = 14
CHART_HEIGHT = 320
CHART_LAYOUT = dict(
    template=CHART_TEMPLATE,
    height=CHART_HEIGHT,
    margin=dict(t=10, b=10, l=10, r=30),
    font=dict(size=CHART_FONT_SIZE, color="#33363d"),
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    hovermode="closest",
)

# Tarjetas blancas redondeadas con sombra sobre el fondo gris de la página
# (ver .streamlit/config.toml para backgroundColor). Se aplican por prefijo
# de `key=` según la guía de theming (nunca se tocan colores globales aquí).
CARD_CSS = """
<style>
div[class*="st-key-kpi_"], div[class*="st-key-chart_"] {
    background: #ffffff;
    border-radius: 18px;
    border: 1px solid rgba(15, 15, 15, 0.05);
    box-shadow: 0 2px 10px rgba(15, 15, 15, 0.07);
    transition: box-shadow 0.15s ease;
    overflow: hidden;
}
div[class*="st-key-kpi_"]:hover, div[class*="st-key-chart_"]:hover {
    box-shadow: 0 4px 16px rgba(15, 15, 15, 0.11);
}
div[class*="st-key-kpi_"] {
    padding: 1.2rem 1.4rem 1rem 1.4rem;
    min-height: 168px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
}
div[class*="st-key-chart_"] { padding: 1.1rem 1.3rem 0.3rem 1.3rem; }
.kpi-accent {
    height: 4px;
    border-radius: 4px;
    margin-bottom: 0.9rem;
}
.kpi-title {
    font-size: 0.92rem;
    font-weight: 700;
    color: #55585f;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    margin: 0 0 0.35rem 0;
}
.kpi-value {
    font-size: 2.7rem;
    font-weight: 800;
    line-height: 1.05;
    margin: 0;
}
.kpi-subtitle {
    font-size: 0.85rem;
    color: #767a82;
    margin-top: 0.55rem;
}
.kpi-delta {
    font-weight: 700;
    padding: 0.1rem 0.5rem;
    border-radius: 999px;
    margin-left: 0.2rem;
    white-space: nowrap;
}
.chart-title {
    font-size: 1.05rem;
    font-weight: 700;
    color: #33363d;
    margin-bottom: 0.4rem;
}
[data-testid="stHorizontalBlock"] { gap: 1.25rem; }
</style>
"""


def load_data() -> dict:
    if not os.path.exists(DATA_FILE):
        return DEFAULT_DATA.copy()
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    if "registros" not in data:
        registro = {
            "fecha": date.today().isoformat(),
            "bmm": data.get("BMM", LIST_BMM[0]),
            "oee": data.get("OEE DIARIO", 0),
        }
        data = {
            "meta": {
                "oee_meta": data.get("OEE META", 87),
                "oee_margen": data.get("OEE DIFERENCIA", 13),
            },
            "registros": [registro],
        }
    data.setdefault("meta", DEFAULT_DATA["meta"])
    data.setdefault("registros", [])
    return data


def save_data(data: dict) -> None:
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def upsert_registro(data: dict, fecha: str, bmm: str, oee: float) -> None:
    """Agrega el registro o, si ya existe uno para esa fecha+BMM, lo actualiza."""
    for registro in data["registros"]:
        if registro["fecha"] == fecha and registro["bmm"] == bmm:
            registro["oee"] = oee
            return
    data["registros"].append({"fecha": fecha, "bmm": bmm, "oee": oee})


def kpi_card(
    key: str, title: str, value: str, value_color: str, subtitle: str, delta: str, delta_color: str
) -> None:
    delta_html = ""
    if delta:
        delta_html = (
            f'<span class="kpi-delta" style="color:{delta_color}; '
            f'background:{delta_color}1a;">{delta}</span>'
        )
    with st.container(key=key):
        st.markdown(
            f"""
            <div class="kpi-accent" style="background:{value_color};"></div>
            <div class="kpi-title">{title}</div>
            <div class="kpi-value" style="color:{value_color};">{value}</div>
            <div class="kpi-subtitle">{subtitle} {delta_html}</div>
            """,
            unsafe_allow_html=True,
        )


def style_ranking_chart(fig: go.Figure, x_range=(0, 118)) -> None:
    """Barras horizontales de ranking: sin leyenda, con % al final de cada barra."""
    fig.update_layout(showlegend=False, **CHART_LAYOUT)
    fig.update_xaxes(range=list(x_range), ticksuffix="%", tickfont=dict(size=CHART_FONT_SIZE))
    fig.update_yaxes(tickfont=dict(size=CHART_FONT_SIZE))
    fig.update_traces(
        texttemplate="%{x:.1f}%",
        textposition="outside",
        textfont=dict(size=CHART_FONT_SIZE),
    )


def style_grouped_chart(fig: go.Figure, xaxis_title: str) -> None:
    """Barras verticales agrupadas por sopladora, con leyenda compacta arriba."""
    fig.update_layout(
        barmode="group",
        yaxis_title=None,
        xaxis_title=xaxis_title,
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.03, xanchor="left", x=0),
        **CHART_LAYOUT,
    )
    fig.update_xaxes(type="category", tickfont=dict(size=CHART_FONT_SIZE))
    fig.update_yaxes(range=[0, 130], ticksuffix="%", tickfont=dict(size=CHART_FONT_SIZE))
    fig.update_traces(
        texttemplate="%{y:.1f}%",
        textposition="outside",
        textfont=dict(size=CHART_FONT_SIZE - 1),
        selector=dict(type="bar"),
    )


st.set_page_config(page_title="OEE Dashboard - BMM", layout="wide")
st.markdown(CARD_CSS, unsafe_allow_html=True)

data = load_data()
OEE_META = data["meta"]["oee_meta"]
MARGEN_OEE = data["meta"]["oee_margen"]

# ---------------------------------------------------------------------------
# Sidebar: info de meta + registro de OEE
# ---------------------------------------------------------------------------
st.sidebar.title("OEE Dashboard - BMM")

st.sidebar.markdown(
    f"""
    **Meta de OEE:** {OEE_META}%
    **Margen permitido:** {MARGEN_OEE}%
    """
)

st.sidebar.subheader("Registrar OEE")

with st.sidebar.form("form_oee", clear_on_submit=False):
    fecha = st.date_input("Fecha", value=date.today())
    bmm = st.selectbox("BMM", LIST_BMM)
    oee = st.number_input(
        "OEE reportado (%)", min_value=0.0, max_value=100.0, value=80.0, step=0.1
    )

    submitted = st.form_submit_button("Guardar")
    if submitted:
        upsert_registro(data, fecha.isoformat(), bmm, oee)
        save_data(data)
        st.sidebar.success(f"OEE guardado: BMM {bmm} - {formato_fecha_larga(fecha)} - {oee}%")

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
st.title("Dashboard de OEE")

df = pd.DataFrame(data["registros"])

if df.empty:
    st.info("Todavía no hay registros de OEE.")
    st.stop()

df["fecha"] = pd.to_datetime(df["fecha"])
df = df.sort_values(["bmm", "fecha"]).reset_index(drop=True)

# Margen real del día = brecha contra el 100% (ej. OEE 82% -> margen 18%).
# Cumple si ese margen real queda dentro del margen permitido (13%),
# lo que equivale a OEE >= Meta (87%).
df["margen"] = 100 - df["oee"]
df["cumple_margen"] = df["margen"] <= MARGEN_OEE

# Promedio acumulado del margen, por sopladora, en orden cronológico.
df["margen_promedio"] = df.groupby("bmm")["margen"].transform(
    lambda s: s.expanding().mean()
)

ultimo_por_bmm = df.sort_values("fecha").groupby("bmm").tail(1).set_index("bmm")
margen_prom_por_bmm = df.groupby("bmm")["margen_promedio"].last()

# Acumulado del mes en curso (promedio de OEE), global y por sopladora.
mes_actual = pd.Timestamp.today().to_period("M")
df_mes_actual = df[df["fecha"].dt.to_period("M") == mes_actual]
acumulado_mes_global = df_mes_actual["oee"].mean() if not df_mes_actual.empty else None
acumulado_mes_por_bmm = df_mes_actual.groupby("bmm")["oee"].mean()

# ---------------------------------------------------------------------------
# Fila de KPIs: estatus del día + acumulado del mes, global y por sopladora
# ---------------------------------------------------------------------------
kpi_cols = st.columns(4, gap="medium")

with kpi_cols[0]:
    oee_global = ultimo_por_bmm["oee"].mean()
    fecha_global = formato_fecha_larga(ultimo_por_bmm["fecha"].max())
    if acumulado_mes_global is not None:
        delta_mes_global = acumulado_mes_global - OEE_META
        subtitle_global = f"Acumulado mes: {acumulado_mes_global:.1f}%"
        delta_text_global = f"({delta_mes_global:+.1f}%)"
        delta_color_global = COLOR_CUMPLE if delta_mes_global >= 0 else COLOR_NO_CUMPLE
    else:
        subtitle_global = "Acumulado mes: Sin datos"
        delta_text_global = ""
        delta_color_global = COLOR_MUTED
    kpi_card(
        "kpi_global",
        f"OEE Global — {fecha_global}",
        f"{oee_global:.1f}%",
        COLOR_CUMPLE if oee_global >= OEE_META else COLOR_NO_CUMPLE,
        subtitle_global,
        delta_text_global,
        delta_color_global,
    )

for col, bmm_id in zip(kpi_cols[1:], LIST_BMM):
    with col:
        if bmm_id not in ultimo_por_bmm.index:
            kpi_card(f"kpi_{bmm_id}", f"BMM {bmm_id}", "Sin datos", COLOR_MUTED, "", "", COLOR_MUTED)
            continue
        oee_hoy = ultimo_por_bmm.loc[bmm_id, "oee"]
        fecha_bmm = formato_fecha_larga(ultimo_por_bmm.loc[bmm_id, "fecha"])
        acumulado_mes = acumulado_mes_por_bmm.get(bmm_id)
        if acumulado_mes is not None:
            delta_mes = acumulado_mes - OEE_META
            subtitle = f"Acumulado mes: {acumulado_mes:.1f}%"
            delta_text = f"({delta_mes:+.1f}%)"
            delta_color = COLOR_CUMPLE if delta_mes >= 0 else COLOR_NO_CUMPLE
        else:
            subtitle = "Acumulado mes: Sin datos"
            delta_text = ""
            delta_color = COLOR_MUTED
        kpi_card(
            f"kpi_{bmm_id}",
            f"BMM {bmm_id} — {fecha_bmm}",
            f"{oee_hoy:.1f}%",
            COLOR_CUMPLE if oee_hoy >= OEE_META else COLOR_NO_CUMPLE,
            subtitle,
            delta_text,
            delta_color,
        )

st.markdown('<div style="height:1.5rem;"></div>', unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Grid de tarjetas con gráficos
# ---------------------------------------------------------------------------
st.subheader("Comparativo general")

fila1 = st.columns(2, gap="medium")

with fila1[0]:
    with st.container(key="chart_ranking_oee"):
        st.markdown('<div class="chart-title">OEE por sopladora (último registro)</div>', unsafe_allow_html=True)
        ranking_oee = ultimo_por_bmm["oee"].sort_values(ascending=True)
        fig = go.Figure(
            go.Bar(
                x=ranking_oee.values,
                y=[f"BMM {b}" for b in ranking_oee.index],
                orientation="h",
                marker_color=[BMM_COLORS[b] for b in ranking_oee.index],
            )
        )
        fig.add_vline(x=OEE_META, line_dash="dash", line_color=COLOR_REFERENCIA)
        style_ranking_chart(fig)
        st.plotly_chart(fig, use_container_width=True)

with fila1[1]:
    with st.container(key="chart_ranking_margen"):
        st.markdown('<div class="chart-title">Margen promedio por sopladora</div>', unsafe_allow_html=True)
        ranking_margen = margen_prom_por_bmm.sort_values(ascending=False)
        colores_margen = [
            COLOR_CUMPLE if v <= MARGEN_OEE else COLOR_NO_CUMPLE for v in ranking_margen.values
        ]
        fig = go.Figure(
            go.Bar(
                x=ranking_margen.values,
                y=[f"BMM {b}" for b in ranking_margen.index],
                orientation="h",
                marker_color=colores_margen,
            )
        )
        fig.add_vline(x=MARGEN_OEE, line_dash="dash", line_color=COLOR_REFERENCIA)
        style_ranking_chart(fig, x_range=(0, max(30, ranking_margen.max() * 1.25)))
        st.plotly_chart(fig, use_container_width=True)

st.markdown('<div style="height:1.25rem;"></div>', unsafe_allow_html=True)
fila2 = st.columns(2, gap="medium")

with fila2[0]:
    with st.container(key="chart_diario"):
        st.markdown('<div class="chart-title">OEE diario por sopladora</div>', unsafe_allow_html=True)
        fig = go.Figure()
        for bmm_id in LIST_BMM:
            d = df[df["bmm"] == bmm_id]
            if d.empty:
                continue
            fig.add_bar(
                x=d["fecha"].dt.strftime("%d"),
                y=d["oee"],
                name=f"BMM {bmm_id}",
                marker_color=BMM_COLORS[bmm_id],
            )
        fig.add_hline(y=OEE_META, line_dash="dash", line_color=COLOR_REFERENCIA)
        style_grouped_chart(fig, xaxis_title="Día")
        st.plotly_chart(fig, use_container_width=True)

with fila2[1]:
    with st.container(key="chart_mensual"):
        st.markdown('<div class="chart-title">Promedio mensual de OEE por sopladora</div>', unsafe_allow_html=True)
        df_mes = df.copy()
        df_mes["mes"] = df_mes["fecha"].dt.to_period("M").astype(str)
        mensual = df_mes.groupby(["mes", "bmm"], as_index=False)["oee"].mean()

        fig = go.Figure()
        for bmm_id in LIST_BMM:
            d = mensual[mensual["bmm"] == bmm_id]
            if d.empty:
                continue
            fig.add_bar(
                x=d["mes"], y=d["oee"], name=f"BMM {bmm_id}", marker_color=BMM_COLORS[bmm_id]
            )
        fig.add_hline(y=OEE_META, line_dash="dash", line_color=COLOR_REFERENCIA)
        style_grouped_chart(fig, xaxis_title="Mes")
        st.plotly_chart(fig, use_container_width=True)
