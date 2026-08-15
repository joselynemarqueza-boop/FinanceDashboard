"""
BeautyLab - P&L Dashboard
Minimalist Design - Focus on P&L Analysis
Author: JosyMarquez
"""

import streamlit as st
import pandas as pd
from pathlib import Path
import os
import plotly.express as px
import plotly.graph_objects as go

# ============================================================================
# PAGE CONFIGURATION
# ============================================================================
st.set_page_config(
    page_title="BeautyLab - P&L Dashboard",
    layout="wide",
    page_icon="📊"
)

# ============================================================================
# CUSTOM CSS
# ============================================================================
st.markdown("""
<style>
    .main { background-color: #ffffff; }
    .metric-card {
        background-color: #f8f9fa;
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        padding: 16px 20px;
        margin: 4px 0;
    }
    .metric-card .label {
        font-size: 0.75rem;
        font-weight: 400;
        color: #666;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .metric-card .value {
        font-size: 1.6rem;
        font-weight: 600;
        color: #1a1a1a;
        margin-top: 2px;
    }
    .page-title {
        font-size: 2rem;
        font-weight: 300;
        color: #1a1a1a;
        letter-spacing: -0.5px;
        margin-bottom: 0.25rem;
    }
    .page-subtitle {
        font-size: 0.9rem;
        color: #888;
        margin-bottom: 2rem;
    }
    .stDataFrame {
        border: 1px solid #e0e0e0;
        border-radius: 4px;
    }
    .stDataFrame thead th {
        background-color: #f5f5f5 !important;
        color: #1a1a1a !important;
        font-weight: 500 !important;
        font-size: 0.75rem !important;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    [data-testid="stSidebar"] {
        background-color: #f8f9fa;
        border-right: 1px solid #e0e0e0;
    }
    hr {
        border-color: #e0e0e0;
        margin: 24px 0;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# CONSTANTS
# ============================================================================
RETURNS_PCT = 0.012
BONUS_PCT = 0.015

COMMERCIAL_DISCOUNT_TYPES = [
    "Base Discount", "PPR", "Channel Discount",
    "Logistics Allowance", "Payment Terms"
]

STRUCTURAL_DISCOUNT_TYPES = ["Annual Rebates", "Listing Fees"]

# ============================================================================
# FILE PATH CONFIGURATION
# ============================================================================
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "Data"

ALT_PATHS = [
    DATA_DIR,
    BASE_DIR,
    Path("."),
    Path("/mount/src/financedashboard/Data"),
    Path("/mount/src/financedashboard"),
]

# ============================================================================
# DATA LOADING ENGINE
# ============================================================================
@st.cache_data
def load_and_calculate():
    """Carga datos y calcula P&L por cliente"""
    
    found_path = None
    for path in ALT_PATHS:
        if (path / "pricing.csv").exists():
            found_path = path
            break
    
    if found_path is None:
        st.error("❌ Archivos CSV no encontrados. Verifica la carpeta Data.")
        raise FileNotFoundError("CSV files not found")
    
    # Cargar datos
    pricing = pd.read_csv(found_path / "pricing.csv")
    gtn = pd.read_csv(found_path / "GTN.csv")
    volume = pd.read_csv(found_path / "volume.csv")
    
    # Limpiar espacios en nombres de columnas
    pricing.columns = pricing.columns.str.strip()
    gtn.columns = gtn.columns.str.strip()
    volume.columns = volume.columns.str.strip()
    
    # DEBUG: Mostrar columnas para verificar
    st.write("Columnas en volume:", list(volume.columns))
    st.write("Columnas en gtn:", list(gtn.columns))
    st.write("Columnas en pricing:", list(pricing.columns))
    
    # ========================================================================
    # 1. Procesar Descuentos Comerciales (van en el precio)
    # ========================================================================
    commercial_discounts = gtn[gtn["account"].isin(COMMERCIAL_DISCOUNT_TYPES)].copy()
    
    # Por categoría - Verificar si la columna existe
    if "category" in commercial_discounts.columns:
        commercial_by_cat = commercial_discounts[
            commercial_discounts["category"] != "All"
        ].groupby(["client_code", "client_name", "category"])["gtn_pct"].sum().reset_index()
        commercial_by_cat.rename(columns={"gtn_pct": "commercial_discount_cat"}, inplace=True)
    else:
        commercial_by_cat = pd.DataFrame(columns=["client_code", "client_name", "category", "commercial_discount_cat"])
    
    # "All" aplica a todas las categorías
    commercial_all = commercial_discounts[
        commercial_discounts["category"] == "All"
    ].groupby(["client_code", "client_name"])["gtn_pct"].sum().reset_index()
    commercial_all.rename(columns={"gtn_pct": "commercial_discount_all"}, inplace=True)
    
    # ========================================================================
    # 2. Procesar GTN Estructural (después del precio)
    # ========================================================================
    structural_gtn = gtn[gtn["account"].isin(STRUCTURAL_DISCOUNT_TYPES)].copy()
    
    if "category" in structural_gtn.columns:
        structural_by_cat = structural_gtn[
            structural_gtn["category"] != "All"
        ].groupby(["client_code", "client_name", "category"])["gtn_pct"].sum().reset_index()
        structural_by_cat.rename(columns={"gtn_pct": "structural_gtn_cat"}, inplace=True)
    else:
        structural_by_cat = pd.DataFrame(columns=["client_code", "client_name", "category", "structural_gtn_cat"])
    
    structural_all = structural_gtn[
        structural_gtn["category"] == "All"
    ].groupby(["client_code", "client_name"])["gtn_pct"].sum().reset_index()
    structural_all.rename(columns={"gtn_pct": "structural_gtn_all"}, inplace=True)
    
    # ========================================================================
    # 3. Procesar GTN Táctico (promociones mensuales)
    # ========================================================================
    tactical_gtn = gtn[
        (gtn["month"] != "Annual") &
        (~gtn["account"].isin(COMMERCIAL_DISCOUNT_TYPES)) &
        (~gtn["account"].isin(STRUCTURAL_DISCOUNT_TYPES))
    ].copy()
    
    month_map = {
        "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4,
        "May": 5, "Jun": 6, "Jul": 7, "Aug": 8,
        "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12
    }
    
    if "category" in tactical_gtn.columns:
        tactical_gtn["month_num"] = tactical_gtn["month"].map(month_map)
        tactical_summary = tactical_gtn.groupby(
            ["month_num", "client_code", "client_name", "category"]
        )["gtn_pct"].sum().reset_index()
        tactical_summary.rename(columns={"gtn_pct": "tactical_gtn_pct"}, inplace=True)
    else:
        tactical_summary = pd.DataFrame(columns=["month_num", "client_code", "client_name", "category", "tactical_gtn_pct"])
    
    # ========================================================================
    # 4. Fusionar todos los datos
    # ========================================================================
    df = volume.merge(pricing, on=["sku"], how="left")
    
    # Verificar que category existe en df
    if "category" not in df.columns:
        st.error("❌ La columna 'category' no existe en volume.csv o pricing.csv")
        st.write("Columnas en volume:", list(volume.columns))
        st.write("Columnas en pricing:", list(pricing.columns))
        raise KeyError("category column not found")
    
    # Merges condicionales
    if not commercial_by_cat.empty:
        df = df.merge(commercial_by_cat, on=["client_code", "client_name", "category"], how="left")
    else:
        df["commercial_discount_cat"] = 0.0
    
    if not commercial_all.empty:
        df = df.merge(commercial_all, on=["client_code", "client_name"], how="left")
    else:
        df["commercial_discount_all"] = 0.0
    
    if not structural_by_cat.empty:
        df = df.merge(structural_by_cat, on=["client_code", "client_name", "category"], how="left")
    else:
        df["structural_gtn_cat"] = 0.0
    
    if not structural_all.empty:
        df = df.merge(structural_all, on=["client_code", "client_name"], how="left")
    else:
        df["structural_gtn_all"] = 0.0
    
    if not tactical_summary.empty:
        df = df.merge(
            tactical_summary,
            left_on=["month", "client_code", "client_name", "category"],
            right_on=["month_num", "client_code", "client_name", "category"],
            how="left"
        )
    else:
        df["tactical_gtn_pct"] = 0.0
    
    # Rellenar nulos
    for col in ["commercial_discount_cat", "commercial_discount_all", 
                "structural_gtn_cat", "structural_gtn_all", "tactical_gtn_pct"]:
        if col in df.columns:
            df[col] = df[col].fillna(0.0)
        else:
            df[col] = 0.0
    
    # ========================================================================
    # 5. Calcular métricas
    # ========================================================================
    df["commercial_discount_pct"] = df["commercial_discount_cat"] + df["commercial_discount_all"]
    df["structural_gtn_pct"] = df["structural_gtn_cat"] + df["structural_gtn_all"]
    df["total_gtn_pct"] = df["structural_gtn_pct"] + df["tactical_gtn_pct"]
    
    # Precio al cliente
    df["price_to_client_gbp"] = df["rrp_gbp"] * (1 - df["commercial_discount_pct"])
    
    # P&L
    df["gross_sales"] = df["units_sold"] * df["price_to_client_gbp"]
    df["returns"] = df["gross_sales"] * RETURNS_PCT
    df["bonus"] = df["gross_sales"] * BONUS_PCT
    df["gtn_amount"] = df["gross_sales"] * df["total_gtn_pct"]
    df["nts"] = df["gross_sales"] - df["returns"] - df["bonus"] - df["gtn_amount"]
    df["cogs"] = df["units_sold"] * df["cogs_per_unit_gbp"]
    df["gp_std"] = df["nts"] - df["cogs"]
    df["gp_std_pct"] = (df["gp_std"] / df["nts"] * 100).round(1)
    df.loc[df["nts"] == 0, "gp_std_pct"] = 0.0
    
    return df

# ============================================================================
# FUNCIONES DE FORMATO
# ============================================================================
def fmt_currency(val):
    if pd.isna(val):
        return "£0"
    return f"£{val:,.2f}" if abs(val) < 1000 else f"£{val:,.0f}"

def fmt_pct(val):
    if pd.isna(val):
        return "0.0%"
    return f"{val:.1f}%"

def create_pl_table(df):
    """Genera la tabla P&L por cliente exactamente como en la vista"""
    
    # Agrupar por cliente
    pl_client = df.groupby(["client_code", "client_name"]).agg({
        "gross_sales": "sum",
        "returns": "sum",
        "bonus": "sum",
        "gtn_amount": "sum",
        "nts": "sum",
        "cogs": "sum",
        "gp_std": "sum"
    }).reset_index()
    
    # Calcular porcentajes
    pl_client["gtn_pct"] = (pl_client["gtn_amount"] / pl_client["gross_sales"] * 100).round(1)
    pl_client["cogs_pct"] = (pl_client["cogs"] / pl_client["nts"] * 100).round(1)
    pl_client["gp_pct"] = (pl_client["gp_std"] / pl_client["nts"] * 100).round(1)
    
    # Calcular Structural y Tactical por separado
    structural_total = df.groupby(["client_code", "client_name"]).apply(
        lambda x: (x["gross_sales"] * x["structural_gtn_pct"]).sum()
    ).reset_index(name="structural_amount")
    
    tactical_total = df.groupby(["client_code", "client_name"]).apply(
        lambda x: (x["gross_sales"] * x["tactical_gtn_pct"]).sum()
    ).reset_index(name="tactical_amount")
    
    pl_client = pl_client.merge(structural_total, on=["client_code", "client_name"], how="left")
    pl_client = pl_client.merge(tactical_total, on=["client_code", "client_name"], how="left")
    pl_client["structural_amount"] = pl_client["structural_amount"].fillna(0)
    pl_client["tactical_amount"] = pl_client["tactical_amount"].fillna(0)
    
    # Ordenar columnas
    column_order = [
        "client_code", "client_name",
        "gross_sales", "returns", "bonus",
        "structural_amount", "tactical_amount",
        "gtn_amount", "gtn_pct",
        "nts", "cogs", "cogs_pct",
        "gp_std", "gp_pct"
    ]
    
    return pl_client[column_order]

# ============================================================================
# LOAD DATA
# ============================================================================
st.markdown('<p class="page-title">BeautyLab</p>', unsafe_allow_html=True)
st.markdown('<p class="page-subtitle">P&L Analysis Dashboard</p>', unsafe_allow_html=True)

with st.spinner("Cargando datos..."):
    try:
        df = load_and_calculate()
    except Exception as e:
        st.error(f"❌ Error cargando datos: {str(e)}")
        st.stop()

# ============================================================================
# SIDEBAR FILTERS
# ============================================================================
with st.sidebar:
    st.markdown("### Filters")
    st.divider()
    
    year_options = sorted(df["year"].unique(), reverse=True)
    selected_year = st.selectbox("Year", year_options)
    
    client_options = sorted(df[df["year"] == selected_year]["client_name"].unique())
    selected_clients = st.multiselect(
        "Clients",
        options=client_options,
        default=client_options
    )
    
    st.divider()
    st.caption(f"Returns: {RETURNS_PCT*100:.1f}% | Bonus: {BONUS_PCT*100:.1f}%")

# ============================================================================
# FILTRAR DATOS
# ============================================================================
df_filtered = df[
    (df["year"] == selected_year) &
    (df["client_name"].isin(selected_clients))
]

# ============================================================================
# MAIN DASHBOARD
# ============================================================================

# --- KPIs ---
total_gts = df_filtered["gross_sales"].sum()
total_nts = df_filtered["nts"].sum()
total_gp = df_filtered["gp_std"].sum()
total_gtn = df_filtered["gtn_amount"].sum()
gp_pct = (total_gp / total_nts * 100) if total_nts > 0 else 0

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("GTS", fmt_currency(total_gts))
col2.metric("NTS", fmt_currency(total_nts))
col3.metric("GP", fmt_currency(total_gp), delta=f"{gp_pct:.1f}%")
col4.metric("GTN", fmt_currency(total_gtn), delta=f"{(total_gtn/total_gts*100):.1f}%")
col5.metric("COGS", fmt_currency(df_filtered["cogs"].sum()), delta=f"{(df_filtered['cogs'].sum()/total_nts*100):.1f}%")

st.divider()

# --- P&L Table ---
st.markdown("### P&L by Client")

pl_table = create_pl_table(df_filtered)

# Formatear para display
display_table = pl_table.copy()
for col in ["gross_sales", "returns", "bonus", "structural_amount", 
            "tactical_amount", "gtn_amount", "nts", "cogs", "gp_std"]:
    display_table[col] = display_table[col].apply(fmt_currency)

for col in ["gtn_pct", "cogs_pct", "gp_pct"]:
    display_table[col] = display_table[col].apply(fmt_pct)

# Renombrar columnas para display
display_table.columns = [
    "Client Code", "Client Name",
    "GTS", "Returns", "Bonus",
    "Structural GTN", "Tactical GTN",
    "Total GTN", "GTN %",
    "NTS", "COGS", "COGS %",
    "GP", "GP %"
]

st.dataframe(
    display_table,
    use_container_width=True,
    hide_index=True
)

# --- Grand Total ---
st.divider()
st.markdown("### Grand Total")

grand_total = pl_table.agg({
    "gross_sales": "sum",
    "returns": "sum",
    "bonus": "sum",
    "structural_amount": "sum",
    "tactical_amount": "sum",
    "gtn_amount": "sum",
    "nts": "sum",
    "cogs": "sum",
    "gp_std": "sum"
}).to_frame().T

grand_total["gtn_pct"] = (grand_total["gtn_amount"] / grand_total["gross_sales"] * 100).round(1)
grand_total["cogs_pct"] = (grand_total["cogs"] / grand_total["nts"] * 100).round(1)
grand_total["gp_pct"] = (grand_total["gp_std"] / grand_total["nts"] * 100).round(1)

display_grand = grand_total.copy()
for col in ["gross_sales", "returns", "bonus", "structural_amount", 
            "tactical_amount", "gtn_amount", "nts", "cogs", "gp_std"]:
    display_grand[col] = display_grand[col].apply(fmt_currency)

display_grand.columns = [
    "GTS", "Returns", "Bonus", "Structural GTN",
    "Tactical GTN", "Total GTN", "NTS", "COGS", "GP",
    "GTN %", "COGS %", "GP %"
]

# Añadir columna de nombre
display_grand.insert(0, "Client Name", "Grand Total")

st.dataframe(
    display_grand,
    use_container_width=True,
    hide_index=True
)

# ============================================================================
# VISUALIZACIONES
# ============================================================================
st.divider()
st.markdown("### Visualizations")

col1, col2 = st.columns(2)

with col1:
    # GP % por Cliente
    fig_gp = px.bar(
        pl_table,
        x="client_name",
        y="gp_pct",
        title="GP % by Client",
        labels={"gp_pct": "GP %", "client_name": ""},
        color="gp_pct",
        color_continuous_scale="Greens",
        text_auto=".1f"
    )
    fig_gp.update_layout(showlegend=False, height=350)
    st.plotly_chart(fig_gp, use_container_width=True)

with col2:
    # GTN % por Cliente
    fig_gtn = px.bar(
        pl_table,
        x="client_name",
        y="gtn_pct",
        title="GTN % by Client",
        labels={"gtn_pct": "GTN %", "client_name": ""},
        color="gtn_pct",
        color_continuous_scale="Oranges",
        text_auto=".1f"
    )
    fig_gtn.update_layout(showlegend=False, height=350)
    st.plotly_chart(fig_gtn, use_container_width=True)

# --- Distribución de GTS y GP ---
st.divider()

col3, col4 = st.columns(2)

with col3:
    # GTS por Cliente
    fig_gts = px.pie(
        pl_table,
        values="gross_sales",
        names="client_name",
        title="GTS Distribution by Client",
        hole=0.4
    )
    fig_gts.update_traces(textposition="inside", textinfo="percent+label")
    fig_gts.update_layout(height=350)
    st.plotly_chart(fig_gts, use_container_width=True)

with col4:
    # GP por Cliente
    fig_gp_pie = px.pie(
        pl_table,
        values="gp_std",
        names="client_name",
        title="GP Distribution by Client",
        hole=0.4
    )
    fig_gp_pie.update_traces(textposition="inside", textinfo="percent+label")
    fig_gp_pie.update_layout(height=350)
    st.plotly_chart(fig_gp_pie, use_container_width=True)

# --- Waterfall: GTS → NTS → GP ---
st.divider()
st.markdown("### P&L Waterfall (Grand Total)")

waterfall_data = [
    {"label": "GTS", "value": grand_total["gross_sales"].iloc[0]},
    {"label": "Returns", "value": -grand_total["returns"].iloc[0]},
    {"label": "Bonus", "value": -grand_total["bonus"].iloc[0]},
    {"label": "GTN", "value": -grand_total["gtn_amount"].iloc[0]},
    {"label": "NTS", "value": grand_total["nts"].iloc[0]},
    {"label": "COGS", "value": -grand_total["cogs"].iloc[0]},
    {"label": "GP", "value": grand_total["gp_std"].iloc[0]}
]

fig_waterfall = go.Figure(go.Waterfall(
    name="P&L",
    orientation="v",
    measure=["relative", "relative", "relative", "relative", "total", "relative", "total"],
    x=[d["label"] for d in waterfall_data],
    y=[d["value"] for d in waterfall_data],
    text=[fmt_currency(d["value"]) for d in waterfall_data],
    textposition="outside",
    connector={"line": {"color": "rgb(63, 63, 63)"}},
    increasing={"marker": {"color": "#2e7d32"}},
    decreasing={"marker": {"color": "#c62828"}},
    totals={"marker": {"color": "#1565c0"}}
))

fig_waterfall.update_layout(
    height=400,
    showlegend=False,
    title="GTS → NTS → GP",
    yaxis_title="£"
)

st.plotly_chart(fig_waterfall, use_container_width=True)

# ============================================================================
# FOOTER
# ============================================================================
st.divider()
st.caption(f"BeautyLab Financial Dashboard | Data up to {selected_year} | Returns: {RETURNS_PCT*100:.1f}% | Bonus: {BONUS_PCT*100:.1f}%")