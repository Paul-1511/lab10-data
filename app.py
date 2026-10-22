"""
Observatorio de Turismo Sostenible - Guatemala  |  Laboratorio 10 (AVANCE)
Tablero interactivo con Streamlit + Plotly.

Ejecutar:   streamlit run app.py
Datos:      coloque la base Excel en  data/base_migracion.xlsx
            (o súbala desde la barra lateral). Columnas esperadas:
            Año, Mes, Vía, Frontera, País, Tipo de viajero, Viajero
Si no hay archivo, la app arranca en MODO DEMO con datos sintéticos
(claramente rotulados) para poder probar la interfaz.
"""
import os
import unicodedata

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# ----------------------------------------------------------------------
# Paleta (significado fijo en toda la app)
#   Azul     = serie total / información general
#   Turquesa = vía aérea
#   Ámbar    = vía terrestre
#   Coral    = ACENTO: selección, pandemia, estimaciones
# ----------------------------------------------------------------------
C_TOTAL, C_AIR, C_LAND, C_ACCENT = "#1F3A5F", "#238A7E", "#A67C00", "#E4572E"
C_TEXT, C_MUTED, C_BG, C_GRID = "#1B1F23", "#5C6670", "#F7F8FA", "#E3E6EA"
VIA_COLORS = {"Aérea": C_AIR, "Terrestre": C_LAND, "Marítima": "#8A97A6"}

MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
MES_MAP = {"enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6, "julio": 7,
           "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12}
EVENTOS = {  # contexto (no causal): hitos que el usuario puede consultar
    "2020-03-01": "Inicio de restricciones por COVID-19",
}

st.set_page_config(page_title="Observatorio de Turismo - Guatemala", page_icon="🧭", layout="wide")

st.markdown(f"""
<style>
html, body, [class*="css"] {{ font-family: 'Inter', 'Segoe UI', sans-serif; color:{C_TEXT}; }}
.stApp {{ background:{C_BG}; }}
h1 {{ color:{C_TOTAL}; font-size:2rem !important; margin-bottom:0; }}
.sub {{ color:{C_MUTED}; font-size:1.05rem; margin-bottom:1rem; }}
.kpi {{ background:white; border-left:6px solid {C_TOTAL}; border-radius:8px; padding:14px 18px;
        box-shadow:0 1px 3px rgba(0,0,0,.08); }}
.kpi .v {{ font-size:2rem; font-weight:700; color:{C_TOTAL}; line-height:1.1; }}
.kpi .l {{ font-size:.95rem; color:{C_MUTED}; }}
.hint {{ background:#EAF1F8; border-radius:8px; padding:8px 12px; font-size:.95rem; color:{C_TOTAL}; }}
.tag-obs {{ color:{C_TOTAL}; font-weight:600; }} .tag-est {{ color:{C_ACCENT}; font-weight:600; }}
</style>""", unsafe_allow_html=True)


# ----------------------------------------------------------------------
# Datos
# ----------------------------------------------------------------------
def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().strip().lower()
    return s.replace(" ", "_")


def _parse_month(x):
    try:
        return int(x)
    except (ValueError, TypeError):
        return MES_MAP.get(_norm(x).replace("_", ""), np.nan)


@st.cache_data(show_spinner="Cargando datos...")
def load_data(file) -> pd.DataFrame:
    df = pd.read_excel(file)
    df.columns = [_norm(c) for c in df.columns]
    df = df.rename(columns={"ano": "anio", "via": "via", "tipo_de_viajero": "tipo", "viajero": "viajeros"})
    df["mes"] = df["mes"].map(_parse_month)
    df["viajeros"] = pd.to_numeric(df["viajeros"], errors="coerce").fillna(0)
    df["via"] = df["via"].astype(str).str.strip().str.capitalize().replace({"Aereo": "Aérea", "Aerea": "Aérea"})
    df["fecha"] = pd.to_datetime(dict(year=df["anio"], month=df["mes"], day=1))
    return df[["fecha", "anio", "mes", "via", "frontera", "pais", "tipo", "viajeros"]]


@st.cache_data
def demo_data() -> pd.DataFrame:
    """Datos SINTÉTICOS solo para probar la interfaz. No usar para conclusiones."""
    rng = np.random.default_rng(7)
    rows = []
    paises = ["El Salvador", "Guatemala", "Estados Unidos de América", "Honduras", "México", "Nicaragua", "Costa Rica", "Canadá", "España", "Colombia"]
    peso = np.array([5, 4, 4, 2, 1.2, .8, .6, .5, .4, .3])
    for f in pd.date_range("2009-01-01", "2026-06-01", freq="MS"):
        t = (f.year - 2009) + f.month / 12
        season = 1 + .25 * np.cos((f.month - 12) / 12 * 2 * np.pi) + (.2 if f.month in (4, 7, 12) else 0)
        covid = .12 if (f.year == 2020 and f.month >= 4) else (.5 if f.year == 2021 else 1)
        for via, share in (("Aérea", .36), ("Terrestre", .62), ("Marítima", .02)):
            for p, w in zip(paises, peso):
                tipo = rng.choice(["Turista", "Excursionista"], p=[.72, .28])
                v = 9000 * (1 + .06 * t) * season * covid * share * w * rng.normal(1, .06)
                rows.append((f, f.year, f.month, via, "—", p, tipo, max(v, 0)))
    return pd.DataFrame(rows, columns=["fecha", "anio", "mes", "via", "frontera", "pais", "tipo", "viajeros"])


st.sidebar.header("Datos")
upload = st.sidebar.file_uploader("Base de migración (.xlsx)", type="xlsx")
path = "data/base_migracion.xlsx"
if upload is not None:
    df, demo = load_data(upload), False
elif os.path.exists(path):
    df, demo = load_data(path), False
else:
    df, demo = demo_data(), True

# ----------------------------------------------------------------------
# Controles globales (nivel de detalle)
# ----------------------------------------------------------------------
st.sidebar.header("Filtros")
y0, y1 = int(df["anio"].min()), int(df["anio"].max())
rango = st.sidebar.slider("Años a analizar", y0, y1, (y0, y1))
vias = st.sidebar.multiselect("Vía de ingreso", sorted(df["via"].unique()), default=sorted(df["via"].unique()))
tipos = st.sidebar.multiselect("Tipo de viajero", sorted(df["tipo"].unique()), default=sorted(df["tipo"].unique()))
gran = st.sidebar.radio("Nivel de detalle temporal", ["Mensual", "Trimestral", "Anual"], horizontal=True,
                        help="Anual resume el panorama; mensual permite ver la estacionalidad.")
topn = st.sidebar.slider("Cantidad de países a mostrar", 5, 20, 10)
st.sidebar.caption("Los filtros aplican a todas las gráficas.")

f = df[df["anio"].between(*rango) & df["via"].isin(vias) & df["tipo"].isin(tipos)]

st.title("Observatorio de Turismo Sostenible: ¿cómo llegan los viajeros a Guatemala?")
st.markdown('<div class="sub">Explore 17 años de ingresos internacionales (INGUAT/IGM). '
            'Seleccione un periodo en la gráfica principal para ver qué mercados y vías lo explican.</div>',
            unsafe_allow_html=True)
if demo:
    st.warning("MODO DEMO: datos sintéticos para probar la interfaz. Cargue la base real para ver cifras oficiales.")
if f.empty:
    st.info("No hay datos para la combinación de filtros elegida. Amplíe el rango de años o seleccione más vías.")
    st.stop()

# ----------------------------------------------------------------------
# Selección enlazada (se lee ANTES de dibujar para que el resto reaccione)
# ----------------------------------------------------------------------
sel_ts = st.session_state["ts"].selection if "ts" in st.session_state and hasattr(st.session_state["ts"], "selection") else {}
ini, fin = f["fecha"].min(), f["fecha"].max()
periodo_sel = False
if sel_ts and sel_ts.get("box"):
    xr = sel_ts["box"][0]["x"]
    ini, fin = pd.to_datetime(min(xr)), pd.to_datetime(max(xr))
    periodo_sel = True
sel_pais = None
sel_bar = st.session_state["paises"].selection if "paises" in st.session_state and hasattr(st.session_state["paises"], "selection") else {}
if sel_bar and sel_bar.get("points"):
    sel_pais = sel_bar["points"][0].get("y")

fp = f[(f["fecha"] >= ini) & (f["fecha"] <= fin)]
if fp.empty:
    fp = f
    periodo_sel = False


def agrupar(d: pd.DataFrame, by_via=False) -> pd.DataFrame:
    rule = {"Mensual": "MS", "Trimestral": "QS", "Anual": "YS"}[gran]
    d = d.set_index("fecha")
    if by_via:
        return d.groupby("via")["viajeros"].resample(rule).sum().reset_index()
    return d["viajeros"].resample(rule).sum().reset_index()


# ----------------------------------------------------------------------
# KPIs (elementos complementarios)
# ----------------------------------------------------------------------
tot = fp["viajeros"].sum()
mejor_mes = fp.groupby("mes")["viajeros"].sum().idxmax()
via_top = fp.groupby("via")["viajeros"].sum().idxmax()
pais_top = fp.groupby("pais")["viajeros"].sum().idxmax()
k = st.columns(4)
for col, val, lab in zip(k, [f"{tot:,.0f}", MESES[int(mejor_mes) - 1], via_top, pais_top],
                         ["Viajeros en el periodo", "Mes de mayor afluencia", "Vía principal", "Principal país de origen"]):
    col.markdown(f'<div class="kpi"><div class="v">{val}</div><div class="l">{lab}</div></div>', unsafe_allow_html=True)
st.write("")

if periodo_sel:
    st.markdown(f'<div class="hint">Periodo seleccionado: <b>{ini:%b %Y} – {fin:%b %Y}</b>. '
                'Las gráficas de mercados y vías muestran solo este periodo. '
                'Haga doble clic en la gráfica principal para restablecer.</div>', unsafe_allow_html=True)
else:
    st.markdown('<div class="hint">Consejo: arrastre sobre la gráfica principal para seleccionar un periodo '
                'y ver cómo cambian los mercados y las vías.</div>', unsafe_allow_html=True)

# ----------------------------------------------------------------------
# VIZ 1  Línea de tiempo (selección de periodo -> enlaza a Viz 2 y 3)
# ----------------------------------------------------------------------
st.subheader("1. Evolución de los ingresos de viajeros")
st.caption("Hallazgo observado: cada punto es la suma de viajeros del periodo. "
           "Arrastre para seleccionar un rango de fechas.")
serie = agrupar(f, by_via=True)
fig = go.Figure()
for via, g in serie.groupby("via"):
    fig.add_trace(go.Scatter(x=g["fecha"], y=g["viajeros"], name=via, mode="lines",
                             line=dict(color=VIA_COLORS.get(via, C_MUTED), width=2.5),
                             hovertemplate="%{x|%b %Y}<br>%{y:,.0f} viajeros<extra>" + via + "</extra>"))
if sel_pais:
    sp = agrupar(f[f["pais"] == sel_pais])
    fig.add_trace(go.Scatter(x=sp["fecha"], y=sp["viajeros"], name=sel_pais, mode="lines",
                             line=dict(color=C_ACCENT, width=3, dash="dot"),
                             hovertemplate="%{x|%b %Y}<br>%{y:,.0f}<extra>" + sel_pais + "</extra>"))
for d, txt in EVENTOS.items():
    dt = pd.to_datetime(d)
    if f["fecha"].min() <= dt <= f["fecha"].max():
        fig.add_vline(x=dt, line_dash="dash", line_color=C_ACCENT, opacity=.7)
        fig.add_annotation(x=dt, y=1, yref="paper", text=txt, showarrow=False, xanchor="left",
                           font=dict(color=C_ACCENT, size=12))
if periodo_sel:
    fig.add_vrect(x0=ini, x1=fin, fillcolor=C_ACCENT, opacity=.08, line_width=0)
fig.update_layout(dragmode="select", selectdirection="h", height=380, margin=dict(l=10, r=10, t=30, b=10),
                  plot_bgcolor="white", paper_bgcolor="rgba(0,0,0,0)", font=dict(size=14, color=C_TEXT),
                  legend=dict(orientation="h", y=-0.15), hovermode="x unified",
                  yaxis=dict(title="Viajeros", gridcolor=C_GRID, tickformat=","), xaxis=dict(gridcolor=C_GRID))
st.plotly_chart(fig, key="ts", on_select="rerun", selection_mode="box", width="stretch")
if sel_pais:
    st.caption(f"Línea punteada coral: {sel_pais} (seleccionado en la gráfica de mercados).")

# ----------------------------------------------------------------------
# VIZ 2 y 3  Mercados (selección de país -> enlaza a Viz 1)  +  composición por vía
# ----------------------------------------------------------------------
c1, c2 = st.columns([3, 2])
with c1:
    st.subheader("2. Principales países de origen")
    st.caption("Hallazgo observado en el periodo seleccionado. Haga clic en una barra para resaltarla en la gráfica 1.")
    top = fp.groupby("pais")["viajeros"].sum().nlargest(topn).sort_values()
    colors = [C_ACCENT if p == sel_pais else C_TOTAL for p in top.index]
    fb = go.Figure(go.Bar(x=top.values, y=top.index, orientation="h", marker_color=colors,
                          hovertemplate="%{y}<br>%{x:,.0f} viajeros<extra></extra>"))
    fb.update_layout(height=max(320, 32 * len(top) + 80), margin=dict(l=10, r=10, t=10, b=10),
                     plot_bgcolor="white", paper_bgcolor="rgba(0,0,0,0)", font=dict(size=14, color=C_TEXT),
                     xaxis=dict(title="Viajeros", gridcolor=C_GRID, tickformat=","), clickmode="event+select")
    st.plotly_chart(fb, key="paises", on_select="rerun", selection_mode="points", width="stretch")
with c2:
    st.subheader("3. ¿Por qué vía ingresan?")
    st.caption("Participación por vía en el periodo seleccionado (hallazgo observado).")
    comp = fp.groupby("via")["viajeros"].sum()
    fd = go.Figure(go.Bar(x=comp.index, y=comp.values / comp.sum() * 100,
                          marker_color=[VIA_COLORS.get(v, C_MUTED) for v in comp.index],
                          text=[f"{v / comp.sum() * 100:.1f}%" for v in comp.values], textposition="outside",
                          hovertemplate="%{x}<br>%{customdata:,.0f} viajeros<extra></extra>", customdata=comp.values))
    fd.update_layout(height=max(320, 32 * len(top) + 80), margin=dict(l=10, r=10, t=10, b=10), plot_bgcolor="white",
                     paper_bgcolor="rgba(0,0,0,0)", font=dict(size=14, color=C_TEXT), showlegend=False,
                     yaxis=dict(title="% del total", gridcolor=C_GRID, range=[0, 110]))
    st.plotly_chart(fd, width="stretch")

# ----------------------------------------------------------------------
# VIZ 4  Estacionalidad (mapa de calor año x mes)
# ----------------------------------------------------------------------
st.subheader("4. ¿En qué meses llegan más viajeros?")
st.caption("Hallazgo observado: tonos más oscuros = más viajeros. "
           "2020–2021 se ve atípico; no se atribuye causa más allá de la coincidencia temporal.")
pv = f.pivot_table(index="anio", columns="mes", values="viajeros", aggfunc="sum").reindex(columns=range(1, 13))
fh = go.Figure(go.Heatmap(z=pv.values, x=MESES, y=pv.index.astype(str), colorscale=[[0, "#EAF1F8"], [1, C_TOTAL]],
                          colorbar=dict(title="Viajeros", tickformat=","),
                          hovertemplate="%{y} - %{x}<br>%{z:,.0f} viajeros<extra></extra>"))
fh.update_layout(height=470, margin=dict(l=10, r=10, t=10, b=10), plot_bgcolor="white", paper_bgcolor="rgba(0,0,0,0)",
                 font=dict(size=14, color=C_TEXT), yaxis=dict(autorange="reversed", dtick=1))
st.plotly_chart(fh, width="stretch")

st.caption("Fuente: Base de Migración 2009–2026, INGUAT/IGM. Uso académico (UVG, CC3066). "
           "Avance: las gráficas 5–8 (modelos de pronóstico del Laboratorio 1) se incorporan en la entrega final.")
