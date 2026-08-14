"""
BeautyLab - Financial Performance Dashboard
Minimalist Black & White Design
Author: JosyMarquez
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path

# ============================================================================
# PAGE CONFIGURATION
# ============================================================================
st.set_page_config(
    page_title="BeautyLab - Financial Dashboard",
    layout="wide",
    page_icon="📊"
)

# ============================================================================
# CUSTOM CSS - MINIMALIST BLACK & WHITE
# ============================================================================
st.markdown("""
<style>
    /* Main background */
    .main {
        background-color: #ffffff;
    }
    
    /* Metric cards */
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
    .metric-card .sub {
        font-size: 0.75rem;
        color: #888;
        margin-top: 2px;
    }
    
    /* Headers */
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
    .section-title {
        font-size: 1.1rem;
        font-weight: 500;
        color: #1a1a1a;
        border-bottom: 2px solid #e0e0e0;
        padding-bottom: 8px;
        margin-bottom: 16px;
    }
    
    /* Dataframes */
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
    
    /* Sidebar */
    [data-testid="stSidebar"] {
        background-color: #f8f9fa;
        border-right: 1px solid #e0e0e0;
    }
    [data-testid="stSidebar"] h1 {
        color: #1a1a1a;
        font-weight: 300;
    }
    [data-testid="stSidebar"] .stSelectbox label,
    [data-testid="stSidebar"] .stMultiSelect label {
        color: #333;
        font-weight: 400;
        font-size: 0.8rem;
    }
    
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0px;
        border-bottom: 1px solid #e0e0e0;
    }
    .stTabs [data-baseweb="tab"] {
        padding: 10px 20px;
        color: #666;
        font-weight: 400;
        background-color: transparent;
        border: none;
        border-bottom: 2px solid transparent;
        transition: 0.2s;
    }
    .stTabs [data-baseweb="tab"][aria-selected="true"] {
        color: #1a1a1a;
        font-weight: 500;
        border-bottom: 2px solid #1a1a1a;
    }
    
    /* Dividers */
    hr {
        border-color: #e0e0e0;
        margin: 24px 0;
    }
    
    /* Footer */
    .footer {
        font-size: 0.7rem;
        color: #aaa;
        text-align: center;
        padding: 20px 0;
        border-top: 1px solid #e0e0e0;
        margin-top: 30px;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# DATA LOADING ENGINE
# ============================================================================
@st.cache_data
def load_and_calculate():
    """Load CSV files and calculate P&L up to GP Std."""
    
    DATA_DIR = Path("Data")
    
    pricing = pd.read_csv(DATA_DIR / "pricing.csv")
    gtn = pd.read_csv(DATA_DIR / "GTN.csv")
    volume = pd.read_csv(DATA_DIR / "volume.csv")

    # Normalize months
    month_map = {
        "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4,
        "May": 5, "Jun": 6, "Jul": 7, "Aug": 8,
        "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12
    }
    gtn["month_num"] = gtn["month"].map(month_map)

    # Structural GTN
    gtn_structural = (
        gtn[(gtn["month"] == "Annual") & (gtn["category"] == "All")]
        .groupby(["client_code", "client_name"], as_index=False)
        .agg(structural_gtn_pct=("gtn_pct", "sum"))
    )

    # Tactical GTN
    gtn_tactical = (
        gtn[gtn["month"] != "Annual"]
        .groupby(["month_num", "client_code", "client_name", "category"], as_index=False)
        .agg(tactical_gtn_pct=("gtn_pct", "sum"))
    )

    # Merge volume with pricing
    pxq = volume.merge(
        pricing,
        on=["client_code", "client_name", "channel", "sku", "product_name", "category"],
        how="left"
    )

    # Calculate Gross Sales and COGS
    pxq["gross_sales"] = pxq["units_sold"] * pxq["price_to_client_gbp"]
    pxq["cogs"] = pxq["units_sold"] * pxq["cogs_per_unit_gbp"]

    # Merge Structural GTN
    pxq = pxq.merge(
        gtn_structural[["client_code", "structural_gtn_pct"]],
        on="client_code",
        how="left"
    )
    pxq["structural_gtn_pct"] = pxq["structural_gtn_pct"].fillna(0.0)

    # Merge Tactical GTN
    pxq = pxq.merge(
        gtn_tactical[["month_num", "client_code", "category", "tactical_gtn_pct"]],
        left_on=["month", "client_code", "category"],
        right_on=["month_num", "client_code", "category"],
        how="left"
    )
    pxq["tactical_gtn_pct"] = pxq["tactical_gtn_pct"].fillna(0.0)

    # P&L Calculations
    pxq["total_gtn_pct"] = pxq["structural_gtn_pct"] + pxq["tactical_gtn_pct"]
    pxq["returns"] = pxq["gross_sales"] * 0.02
    pxq["bonus"] = pxq["gross_sales"] * 0.015
    pxq["gtn_amount"] = pxq["gross_sales"] * pxq["total_gtn_pct"]
    pxq["nts"] = pxq["gross_sales"] - pxq["returns"] - pxq["bonus"] - pxq["gtn_amount"]
    pxq["gp_std"] = pxq["nts"] - pxq["cogs"]
    pxq["gp_std_pct"] = (pxq["gp_std"] / pxq["nts"] * 100).round(1)

    # Define column order
    column_order = [
        "year", "month", "client_code", "client_name", "channel",
        "sku", "product_name", "category", "units_sold",
        "gross_sales", "returns", "bonus",
        "structural_gtn_pct", "tactical_gtn_pct", "total_gtn_pct", "gtn_amount",
        "nts", "cogs", "gp_std", "gp_std_pct"
    ]

    return pxq[column_order].copy()

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================
def format_currency(val):
    """Format value as currency."""
    return f"£{val:,.0f}" if abs(val) >= 1000 else f"£{val:,.2f}"

def format_pct(val):
    """Format value as percentage."""
    return f"{val:.1f}%"

def create_pl_table(df, label_col, value_col, pct_col=None):
    """Create a formatted P&L table."""
    pl_data = []
    
    # Define P&L structure
    pl_structure = [
        ("Gross Trade Sales (GTS)", "gross_sales", True),
        ("Returns (2%)", "returns", False),
        ("Bonuses (1.5%)", "bonus", False),
        ("GTN (Structural + Tactical)", "gtn_amount", False),
        ("Net Trade Sales (NTS)", "nts", True),
        ("COGS", "cogs", False),
        ("Gross Profit (GP Std)", "gp_std", True)
    ]
    
    for label, col, is_bold in pl_structure:
        val = df[col].sum() if col in df.columns else 0
        pl_data.append({
            "Account": label,
            "Value": val,
            "Bold": is_bold
        })
    
    return pd.DataFrame(pl_data)

def create_metric_card(label, value, sub=None):
    """Create a minimal metric card."""
    html = f"""
    <div class="metric-card">
        <div class="label">{label}</div>
        <div class="value">{value}</div>
        {f'<div class="sub">{sub}</div>' if sub else ''}
    </div>
    """
    return html

# ============================================================================
# LOAD DATA
# ============================================================================
st.markdown('<p class="page-title">BeautyLab</p>', unsafe_allow_html=True)
st.markdown('<p class="page-subtitle">Financial Performance Dashboard</p>', unsafe_allow_html=True)

with st.spinner("Loading data..."):
    df = load_and_calculate()

# ============================================================================
# SIDEBAR FILTERS - MINIMALIST
# ============================================================================
with st.sidebar:
    st.markdown("### Filters")
    st.divider()
    
    # Year
    year_options = sorted(df["year"].unique(), reverse=True)
    selected_year = st.selectbox("Year", year_options)
    
    # Client
    client_options = sorted(df[df["year"] == selected_year]["client_name"].unique())
    selected_clients = st.multiselect(
        "Clients",
        options=client_options,
        default=client_options
    )
    
    # Category
    cat_options = sorted(df[df["year"] == selected_year]["category"].unique())
    selected_cats = st.multiselect(
        "Categories",
        options=cat_options,
        default=cat_options
    )
    
    st.divider()
    st.caption("Data up to GP Std")

# Apply filters
df_filtered = df[
    (df["year"] == selected_year) &
    (df["client_name"].isin(selected_clients)) &
    (df["category"].isin(selected_cats))
]

# ============================================================================
# MAIN TABS
# ============================================================================
tab_pl, tab_gtn, tab_price, tab_cost, tab_gp_drivers = st.tabs([
    "P&L Executive",
    "GTN Analysis",
    "Price Analysis",
    "Cost Efficiency",
    "GP Driver Analysis"
])

# ============================================================================
# TAB 1: P&L EXECUTIVE
# ============================================================================
with tab_pl:
    st.markdown("### P&L Executive Summary")
    
    # Consolidated P&L
    pl_consolidated = create_pl_table(df_filtered)
    
    # Key metrics row
    total_gts = df_filtered["gross_sales"].sum()
    total_nts = df_filtered["nts"].sum()
    total_gp = df_filtered["gp_std"].sum()
    gp_pct = (total_gp / total_nts * 100) if total_nts > 0 else 0
    
    col1, col2, col3, col4 = st.columns(4)
    col1.markdown(create_metric_card("GTS", format_currency(total_gts)), unsafe_allow_html=True)
    col2.markdown(create_metric_card("NTS", format_currency(total_nts)), unsafe_allow_html=True)
    col3.markdown(create_metric_card("GP Std", format_currency(total_gp)), unsafe_allow_html=True)
    col4.markdown(create_metric_card("GP %", format_pct(gp_pct)), unsafe_allow_html=True)
    
    st.divider()
    
    # P&L Table
    st.markdown("#### P&L by Account")
    
    # Format for display
    pl_display = pl_consolidated.copy()
    pl_display["Value"] = pl_display["Value"].apply(lambda x: format_currency(x) if abs(x) >= 1000 else f"£{x:,.2f}")
    
    # Bold styling
    def style_pl(row):
        if row["Bold"]:
            return ["font-weight: 600; background-color: #f8f9fa;"] * len(row)
        return [""] * len(row)
    
    st.dataframe(
        pl_display[["Account", "Value"]].style.apply(style_pl, axis=1),
        use_container_width=True,
        hide_index=True
    )
    
    st.divider()
    
    # P&L by Client
    st.markdown("#### P&L by Client")
    
    df_client = df_filtered.groupby("client_name").agg({
        "units_sold": "sum",
        "gross_sales": "sum",
        "nts": "sum",
        "cogs": "sum",
        "gp_std": "sum"
    }).reset_index()
    
    df_client["gp_pct"] = (df_client["gp_std"] / df_client["nts"] * 100).round(1)
    df_client = df_client.sort_values("gp_std", ascending=False)
    
    st.dataframe(
        df_client.style.format({
            "units_sold": "{:,.0f}",
            "gross_sales": "£{:,.0f}",
            "nts": "£{:,.0f}",
            "cogs": "£{:,.0f}",
            "gp_std": "£{:,.0f}",
            "gp_pct": "{:.1f}%"
        }),
        use_container_width=True,
        hide_index=True
    )
    
    st.divider()
    
    # P&L by Category
    st.markdown("#### P&L by Category")
    
    df_cat = df_filtered.groupby("category").agg({
        "units_sold": "sum",
        "gross_sales": "sum",
        "nts": "sum",
        "cogs": "sum",
        "gp_std": "sum"
    }).reset_index()
    
    df_cat["gp_pct"] = (df_cat["gp_std"] / df_cat["nts"] * 100).round(1)
    df_cat = df_cat.sort_values("gp_std", ascending=False)
    
    st.dataframe(
        df_cat.style.format({
            "units_sold": "{:,.0f}",
            "gross_sales": "£{:,.0f}",
            "nts": "£{:,.0f}",
            "cogs": "£{:,.0f}",
            "gp_std": "£{:,.0f}",
            "gp_pct": "{:.1f}%"
        }),
        use_container_width=True,
        hide_index=True
    )

# ============================================================================
# TAB 2: GTN ANALYSIS
# ============================================================================
with tab_gtn:
    st.markdown("### GTN Analysis")
    
    # P&L hasta NTS por Canal y Categoría
    st.markdown("#### P&L to NTS by Channel & Category")
    
    # By Channel
    df_gtn_channel = df_filtered.groupby("channel").agg({
        "units_sold": "sum",
        "gross_sales": "sum",
        "returns": "sum",
        "bonus": "sum",
        "gtn_amount": "sum",
        "nts": "sum"
    }).reset_index()
    
    # Add percentages
    total_gts_ch = df_gtn_channel["gross_sales"].sum()
    for col in ["returns", "bonus", "gtn_amount", "nts"]:
        df_gtn_channel[f"{col}_pct"] = (df_gtn_channel[col] / total_gts_ch * 100).round(1)
    
    st.dataframe(
        df_gtn_channel.style.format({
            "units_sold": "{:,.0f}",
            "gross_sales": "£{:,.0f}",
            "returns": "£{:,.0f}",
            "bonus": "£{:,.0f}",
            "gtn_amount": "£{:,.0f}",
            "nts": "£{:,.0f}",
            "returns_pct": "{:.1f}%",
            "bonus_pct": "{:.1f}%",
            "gtn_amount_pct": "{:.1f}%",
            "nts_pct": "{:.1f}%"
        }),
        use_container_width=True,
        hide_index=True
    )
    
    st.divider()
    
    # By Category
    st.markdown("#### P&L to NTS by Category")
    
    df_gtn_cat = df_filtered.groupby("category").agg({
        "units_sold": "sum",
        "gross_sales": "sum",
        "returns": "sum",
        "bonus": "sum",
        "gtn_amount": "sum",
        "nts": "sum"
    }).reset_index()
    
    total_gts_cat = df_gtn_cat["gross_sales"].sum()
    for col in ["returns", "bonus", "gtn_amount", "nts"]:
        df_gtn_cat[f"{col}_pct"] = (df_gtn_cat[col] / total_gts_cat * 100).round(1)
    
    st.dataframe(
        df_gtn_cat.style.format({
            "units_sold": "{:,.0f}",
            "gross_sales": "£{:,.0f}",
            "returns": "£{:,.0f}",
            "bonus": "£{:,.0f}",
            "gtn_amount": "£{:,.0f}",
            "nts": "£{:,.0f}",
            "returns_pct": "{:.1f}%",
            "bonus_pct": "{:.1f}%",
            "gtn_amount_pct": "{:.1f}%",
            "nts_pct": "{:.1f}%"
        }),
        use_container_width=True,
        hide_index=True
    )
    
    st.divider()
    
    # GTN Breakdown Summary
    st.markdown("#### GTN Breakdown Summary")
    st.caption("Desglose de Units, GTS, Acuerdos Comerciales, Tácticos y NTS")
    
    df_gtn_summary = df_filtered.groupby("client_name").agg({
        "units_sold": "sum",
        "gross_sales": "sum",
        "gtn_amount": "sum",
        "nts": "sum"
    }).reset_index()
    
    # Add columns for structural and tactical
    df_gtn_summary["structural_gtn"] = df_filtered.groupby("client_name")["structural_gtn_pct"].mean().values
    df_gtn_summary["tactical_gtn"] = df_filtered.groupby("client_name")["tactical_gtn_pct"].mean().values
    df_gtn_summary["gtn_pct"] = (df_gtn_summary["gtn_amount"] / df_gtn_summary["gross_sales"] * 100).round(1)
    
    st.dataframe(
        df_gtn_summary.style.format({
            "units_sold": "{:,.0f}",
            "gross_sales": "£{:,.0f}",
            "gtn_amount": "£{:,.0f}",
            "nts": "£{:,.0f}",
            "structural_gtn": "{:.1%}",
            "tactical_gtn": "{:.1%}",
            "gtn_pct": "{:.1f}%"
        }),
        use_container_width=True,
        hide_index=True
    )
    
    st.divider()
    
    # TIE - Trade Investment Efficiency
    st.markdown("#### TIE - Trade Investment Efficiency")
    st.caption("GTN por Unidad vs NTS por Unidad")
    
    df_tie = df_filtered.groupby("client_name").agg({
        "units_sold": "sum",
        "gtn_amount": "sum",
        "nts": "sum"
    }).reset_index()
    
    df_tie["gtn_per_unit"] = df_tie["gtn_amount"] / df_tie["units_sold"]
    df_tie["nts_per_unit"] = df_tie["nts"] / df_tie["units_sold"]
    df_tie["tie_ratio"] = (df_tie["gtn_per_unit"] / df_tie["nts_per_unit"] * 100).round(1)
    df_tie = df_tie.sort_values("tie_ratio", ascending=True)
    
    st.dataframe(
        df_tie.style.format({
            "units_sold": "{:,.0f}",
            "gtn_amount": "£{:,.0f}",
            "nts": "£{:,.0f}",
            "gtn_per_unit": "£{:.2f}",
            "nts_per_unit": "£{:.2f}",
            "tie_ratio": "{:.1f}%"
        }),
        use_container_width=True,
        hide_index=True
    )
    
    st.caption("💡 **TIE Ratio** = GTN por Unidad / NTS por Unidad. Menor ratio = Mayor eficiencia de inversión comercial.")

# ============================================================================
# TAB 3: PRICE ANALYSIS
# ============================================================================
with tab_price:
    st.markdown("### Price Analysis")
    
    # Price by Client
    st.markdown("#### Average Price by Client")
    
    df_price_client = df_filtered.groupby("client_name").agg({
        "units_sold": "sum",
        "gross_sales": "sum",
        "nts": "sum",
        "cogs": "sum",
        "gp_std": "sum"
    }).reset_index()
    
    df_price_client["avg_price"] = df_price_client["gross_sales"] / df_price_client["units_sold"]
    df_price_client["avg_cogs"] = df_price_client["cogs"] / df_price_client["units_sold"]
    df_price_client["avg_gp"] = df_price_client["gp_std"] / df_price_client["units_sold"]
    df_price_client["gp_pct"] = (df_price_client["gp_std"] / df_price_client["nts"] * 100).round(1)
    
    # Price Premium vs Average
    avg_price = df_price_client["avg_price"].mean()
    df_price_client["price_premium"] = (df_price_client["avg_price"] / avg_price * 100).round(1)
    
    df_price_client = df_price_client.sort_values("avg_price", ascending=False)
    
    st.dataframe(
        df_price_client.style.format({
            "units_sold": "{:,.0f}",
            "gross_sales": "£{:,.0f}",
            "avg_price": "£{:.2f}",
            "avg_cogs": "£{:.2f}",
            "avg_gp": "£{:.2f}",
            "gp_pct": "{:.1f}%",
            "price_premium": "{:.1f}%"
        }),
        use_container_width=True,
        hide_index=True
    )
    
    st.divider()
    
    # Price by SKU
    st.markdown("#### Average Price by SKU")
    
    df_price_sku = df_filtered.groupby(["sku", "product_name", "category"]).agg({
        "units_sold": "sum",
        "gross_sales": "sum",
        "nts": "sum",
        "cogs": "sum",
        "gp_std": "sum"
    }).reset_index()
    
    df_price_sku["avg_price"] = df_price_sku["gross_sales"] / df_price_sku["units_sold"]
    df_price_sku["avg_cogs"] = df_price_sku["cogs"] / df_price_sku["units_sold"]
    df_price_sku["avg_gp"] = df_price_sku["gp_std"] / df_price_sku["units_sold"]
    df_price_sku["gp_pct"] = (df_price_sku["gp_std"] / df_price_sku["nts"] * 100).round(1)
    df_price_sku = df_price_sku.sort_values("avg_price", ascending=False)
    
    st.dataframe(
        df_price_sku.style.format({
            "units_sold": "{:,.0f}",
            "avg_price": "£{:.2f}",
            "avg_cogs": "£{:.2f}",
            "avg_gp": "£{:.2f}",
            "gp_pct": "{:.1f}%"
        }),
        use_container_width=True,
        hide_index=True
    )
    
    st.divider()
    
    # Price Waterfall by Category
    st.markdown("#### Price Waterfall by Category")
    st.caption("Del Precio de Venta al GP por Unidad")
    
    df_price_waterfall = df_filtered.groupby("category").agg({
        "units_sold": "sum",
        "gross_sales": "sum",
        "gtn_amount": "sum",
        "cogs": "sum",
        "gp_std": "sum"
    }).reset_index()
    
    for idx, row in df_price_waterfall.iterrows():
        units = row["units_sold"]
        price = row["gross_sales"] / units if units > 0 else 0
        gtn_unit = row["gtn_amount"] / units if units > 0 else 0
        cogs_unit = row["cogs"] / units if units > 0 else 0
        gp_unit = row["gp_std"] / units if units > 0 else 0
        
        st.markdown(f"**{row['category']}**")
        st.caption(f"Price: £{price:.2f} | GTN: £{gtn_unit:.2f} | COGS: £{cogs_unit:.2f} | GP: £{gp_unit:.2f}")
        
        # Simple horizontal bar
        st.progress(min(gp_unit / price, 1.0) if price > 0 else 0)
    
    st.caption("💡 La barra muestra el GP como % del precio. Mayor barra = Mayor eficiencia.")

# ============================================================================
# TAB 4: COST EFFICIENCY
# ============================================================================
with tab_cost:
    st.markdown("### Cost Efficiency Analysis")
    
    # Key metrics
    total_cogs = df_filtered["cogs"].sum()
    total_units = df_filtered["units_sold"].sum()
    avg_cogs = total_cogs / total_units if total_units > 0 else 0
    total_nts_cost = df_filtered["nts"].sum()
    cogs_pct = (total_cogs / total_nts_cost * 100) if total_nts_cost > 0 else 0
    
    col1, col2, col3, col4 = st.columns(4)
    col1.markdown(create_metric_card("Total COGS", format_currency(total_cogs)), unsafe_allow_html=True)
    col2.markdown(create_metric_card("Avg COGS/Unit", f"£{avg_cogs:.2f}"), unsafe_allow_html=True)
    col3.markdown(create_metric_card("COGS % NTS", format_pct(cogs_pct)), unsafe_allow_html=True)
    col4.markdown(create_metric_card("Total Units", f"{total_units:,.0f}"), unsafe_allow_html=True)
    
    st.divider()
    
    # COGS by SKU (Efficiency Ranking)
    st.markdown("#### COGS Efficiency Ranking by SKU")
    st.caption("Menor COGS por Unidad = Mayor Eficiencia")
    
    df_cost_sku = df_filtered.groupby(["sku", "product_name", "category"]).agg({
        "units_sold": "sum",
        "cogs": "sum",
        "nts": "sum",
        "gp_std": "sum"
    }).reset_index()
    
    df_cost_sku["cogs_per_unit"] = df_cost_sku["cogs"] / df_cost_sku["units_sold"]
    df_cost_sku["gp_per_unit"] = df_cost_sku["gp_std"] / df_cost_sku["units_sold"]
    df_cost_sku["efficiency_score"] = (df_cost_sku["gp_per_unit"] / df_cost_sku["cogs_per_unit"] * 100).round(1)
    df_cost_sku = df_cost_sku.sort_values("cogs_per_unit", ascending=True)
    
    st.dataframe(
        df_cost_sku.style.format({
            "units_sold": "{:,.0f}",
            "cogs": "£{:,.0f}",
            "cogs_per_unit": "£{:.2f}",
            "gp_per_unit": "£{:.2f}",
            "efficiency_score": "{:.1f}%"
        }),
        use_container_width=True,
        hide_index=True
    )
    
    st.caption("💡 **Efficiency Score** = GP por Unidad / COGS por Unidad × 100. Mayor score = Mayor eficiencia.")
    
    st.divider()
    
    # COGS by Client
    st.markdown("#### COGS by Client")
    
    df_cost_client = df_filtered.groupby("client_name").agg({
        "units_sold": "sum",
        "cogs": "sum",
        "nts": "sum",
        "gp_std": "sum"
    }).reset_index()
    
    df_cost_client["cogs_per_unit"] = df_cost_client["cogs"] / df_cost_client["units_sold"]
    df_cost_client["cogs_pct_nts"] = (df_cost_client["cogs"] / df_cost_client["nts"] * 100).round(1)
    df_cost_client = df_cost_client.sort_values("cogs_per_unit", ascending=True)
    
    st.dataframe(
        df_cost_client.style.format({
            "units_sold": "{:,.0f}",
            "cogs": "£{:,.0f}",
            "cogs_per_unit": "£{:.2f}",
            "cogs_pct_nts": "{:.1f}%"
        }),
        use_container_width=True,
        hide_index=True
    )
    
    st.divider()
    
    # Volume vs COGS Scatter
    st.markdown("#### Volume vs COGS per Unit")
    
    fig_cost = px.scatter(
        df_cost_sku,
        x="units_sold",
        y="cogs_per_unit",
        color="category",
        hover_name="product_name",
        text="sku",
        title="",
        labels={
            "units_sold": "Units Sold",
            "cogs_per_unit": "COGS per Unit (£)"
        },
        size="gp_per_unit",
        size_max=40,
        height=400
    )
    
    fig_cost.update_layout(
        plot_bgcolor="white",
        paper_bgcolor="white",
        font=dict(color="#333", size=11),
        xaxis=dict(gridcolor="#e0e0e0", showgrid=True),
        yaxis=dict(gridcolor="#e0e0e0", showgrid=True),
        margin=dict(l=40, r=40, t=20, b=40)
    )
    
    fig_cost.update_traces(textposition="top center")
    st.plotly_chart(fig_cost, use_container_width=True)
    
    st.caption("💡 **Interpretación:** SKUs en la parte inferior = Menor costo por unidad (más eficientes). Tamaño de burbuja = GP por unidad.")

# ============================================================================
# TAB 5: GP DRIVER ANALYSIS
# ============================================================================
with tab_gp_drivers:
    st.markdown("### GP Driver Analysis")
    st.caption("¿El GP es bajo por Volumen, Precio o Costos?")
    
    # Calculate drivers
    total_units = df_filtered["units_sold"].sum()
    avg_price = df_filtered["gross_sales"].sum() / total_units if total_units > 0 else 0
    avg_cogs = df_filtered["cogs"].sum() / total_units if total_units > 0 else 0
    avg_gp = avg_price - avg_cogs
    gp_pct = (avg_gp / avg_price * 100) if avg_price > 0 else 0
    
    # Driver breakdown
    col1, col2, col3, col4 = st.columns(4)
    col1.markdown(create_metric_card("Avg Price/Unit", f"£{avg_price:.2f}"), unsafe_allow_html=True)
    col2.markdown(create_metric_card("Avg COGS/Unit", f"£{avg_cogs:.2f}"), unsafe_allow_html=True)
    col3.markdown(create_metric_card("Avg GP/Unit", f"£{avg_gp:.2f}"), unsafe_allow_html=True)
    col4.markdown(create_metric_card("GP %", format_pct(gp_pct)), unsafe_allow_html=True)
    
    st.divider()
    
    # Driver Analysis by Client
    st.markdown("#### GP Driver Analysis by Client")
    
    df_drivers = df_filtered.groupby("client_name").agg({
        "units_sold": "sum",
        "gross_sales": "sum",
        "cogs": "