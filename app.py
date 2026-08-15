"""
BeautyLab - Financial Performance Dashboard
Minimalist Black & White Design
Author: JosyMarquez
"""

import streamlit as st
import pandas as pd
from pathlib import Path
import os

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
    .main {
        background-color: #ffffff;
    }
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
    hr {
        border-color: #e0e0e0;
        margin: 24px 0;
    }
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
# DATA LOADING ENGINE WITH PRO-RATED STRUCTURAL GTN
# ============================================================================
@st.cache_data
def load_and_calculate():
    """
    Load CSV files and calculate P&L up to GP Std.
    Structural GTN is pro-rated by SKU weight within each client.
    Returns: 1.2% of GTS
    Bonuses: 1.5% of GTS
    """
    
    found_path = None
    for path in ALT_PATHS:
        if (path / "pricing.csv").exists():
            found_path = path
            break
    
    if found_path is None:
        st.error("❌ CSV files not found. Please check the Data folder.")
        st.write("Current directory:", os.getcwd())
        st.write("Files in current directory:", os.listdir(".") if os.path.exists(".") else "Cannot list")
        raise FileNotFoundError("CSV files not found")
    
    pricing = pd.read_csv(found_path / "pricing.csv")
    gtn = pd.read_csv(found_path / "GTN.csv")
    volume = pd.read_csv(found_path / "volume.csv")

    # Normalize months
    month_map = {
        "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4,
        "May": 5, "Jun": 6, "Jul": 7, "Aug": 8,
        "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12
    }
    gtn["month_num"] = gtn["month"].map(month_map)

    # ------------------------------------------------------------------------
    # STEP 1: Merge volume with pricing (PxQ)
    # ------------------------------------------------------------------------
    pxq = volume.merge(
        pricing,
        on=["client_code", "client_name", "channel", "sku", "product_name", "category"],
        how="left"
    )

    # Calculate Gross Sales and COGS
    pxq["gross_sales"] = pxq["units_sold"] * pxq["price_to_client_gbp"]
    pxq["cogs"] = pxq["units_sold"] * pxq["cogs_per_unit_gbp"]

    # ------------------------------------------------------------------------
    # STEP 2: Calculate SKU weight within each client (by month)
    # ------------------------------------------------------------------------
    # Total GTS per client per month
    pxq["gts_client_month_total"] = pxq.groupby(
        ["year", "month", "client_code", "client_name"]
    )["gross_sales"].transform("sum")
    
    # SKU weight (0-1) within the client for that month
    pxq["sku_weight"] = pxq["gross_sales"] / pxq["gts_client_month_total"]
    
    # Handle division by zero (should not happen, but safe)
    pxq["sku_weight"] = pxq["sku_weight"].fillna(0.0)

    # ------------------------------------------------------------------------
    # STEP 3: Structural GTN (Client level from Annual/All rows)
    # ------------------------------------------------------------------------
    gtn_structural = (
        gtn[(gtn["month"] == "Annual") & (gtn["category"] == "All")]
        .groupby(["client_code", "client_name"], as_index=False)
        .agg(structural_gtn_pct=("gtn_pct", "sum"))
    )

    # Merge Structural GTN at client level
    pxq = pxq.merge(
        gtn_structural[["client_code", "structural_gtn_pct"]],
        on="client_code",
        how="left"
    )
    pxq["structural_gtn_pct"] = pxq["structural_gtn_pct"].fillna(0.0)

    # ------------------------------------------------------------------------
    # STEP 4: PRO-RATE Structural GTN by SKU weight
    # ------------------------------------------------------------------------
    # The structural GTN is distributed across SKUs based on their sales weight
    # This keeps the total client GTN constant while allocating it proportionally
    pxq["structural_gtn_pct_pro_rated"] = pxq["structural_gtn_pct"] * pxq["sku_weight"]

    # ------------------------------------------------------------------------
    # STEP 5: Tactical GTN (Category level from monthly rows)
    # ------------------------------------------------------------------------
    gtn_tactical = (
        gtn[gtn["month"] != "Annual"]
        .groupby(["month_num", "client_code", "client_name", "category"], as_index=False)
        .agg(tactical_gtn_pct=("gtn_pct", "sum"))
    )

    # Merge Tactical GTN
    pxq = pxq.merge(
        gtn_tactical[["month_num", "client_code", "category", "tactical_gtn_pct"]],
        left_on=["month", "client_code", "category"],
        right_on=["month_num", "client_code", "category"],
        how="left"
    )
    pxq["tactical_gtn_pct"] = pxq["tactical_gtn_pct"].fillna(0.0)

    # ------------------------------------------------------------------------
    # STEP 6: Total GTN and P&L Calculations
    # ------------------------------------------------------------------------
    # Use pro-rated structural GTN for the financial calculation
    pxq["total_gtn_pct"] = pxq["structural_gtn_pct_pro_rated"] + pxq["tactical_gtn_pct"]
    
    # Returns: 1.2% of GTS (updated from 2%)
    RETURNS_PCT = 0.012
    # Bonuses: 1.5% of GTS (unchanged)
    BONUS_PCT = 0.015
    
    pxq["returns"] = pxq["gross_sales"] * RETURNS_PCT
    pxq["bonus"] = pxq["gross_sales"] * BONUS_PCT
    pxq["gtn_amount"] = pxq["gross_sales"] * pxq["total_gtn_pct"]
    pxq["nts"] = pxq["gross_sales"] - pxq["returns"] - pxq["bonus"] - pxq["gtn_amount"]
    pxq["gp_std"] = pxq["nts"] - pxq["cogs"]
    pxq["gp_std_pct"] = (pxq["gp_std"] / pxq["nts"] * 100).round(1)

    # Ensure no division by zero
    pxq.loc[pxq["nts"] == 0, "gp_std_pct"] = 0.0

    # ------------------------------------------------------------------------
    # STEP 7: Define column order for the final dataset
    # ------------------------------------------------------------------------
    column_order = [
        "year", "month", "client_code", "client_name", "channel",
        "sku", "product_name", "category", "units_sold", "sku_weight",
        "gross_sales", "returns", "bonus",
        "structural_gtn_pct",                    # Original structural GTN (for reference)
        "structural_gtn_pct_pro_rated",          # Pro-rated structural GTN (NEW)
        "tactical_gtn_pct", 
        "total_gtn_pct",                         # Total GTN (with pro-rating)
        "gtn_amount",
        "nts", "cogs", "gp_std", "gp_std_pct"
    ]

    return pxq[column_order].copy()

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================
def format_currency(val):
    if abs(val) >= 1000:
        return f"£{val:,.0f}"
    else:
        return f"£{val:,.2f}"

def format_pct(val):
    return f"{val:.1f}%"

def create_metric_card(label, value):
    html = f"""
    <div class="metric-card">
        <div class="label">{label}</div>
        <div class="value">{value}</div>
    </div>
    """
    return html

def create_pl_table(df):
    pl_data = []
    
    pl_structure = [
        ("Gross Trade Sales (GTS)", "gross_sales"),
        ("Returns (1.2%)", "returns"),
        ("Bonuses (1.5%)", "bonus"),
        ("GTN (Structural + Tactical)", "gtn_amount"),
        ("Net Trade Sales (NTS)", "nts"),
        ("COGS", "cogs"),
        ("Gross Profit (GP Std)", "gp_std")
    ]
    
    for label, col in pl_structure:
        val = df[col].sum() if col in df.columns else 0
        pl_data.append({
            "Account": label,
            "Value": val
        })
    
    return pd.DataFrame(pl_data)

# ============================================================================
# LOAD DATA
# ============================================================================
st.markdown('<p class="page-title">BeautyLab</p>', unsafe_allow_html=True)
st.markdown('<p class="page-subtitle">Financial Performance Dashboard</p>', unsafe_allow_html=True)

with st.spinner("Loading data..."):
    try:
        df = load_and_calculate()
    except Exception as e:
        st.error(f"❌ Error loading data: {str(e)}")
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
tab_pl, tab_gtn, tab_price, tab_cost, tab_gp_drivers, tab_raw = st.tabs([
    "P&L Executive",
    "GTN Analysis",
    "Price Analysis",
    "Cost Efficiency",
    "GP Driver Analysis",
    "Raw Data"
])

# ============================================================================
# TAB 1: P&L EXECUTIVE
# ============================================================================
with tab_pl:
    st.markdown("### P&L Executive Summary")
    
    pl_consolidated = create_pl_table(df_filtered)
    
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
    
    st.markdown("#### P&L by Account")
    
    pl_display = pl_consolidated.copy()
    pl_display["Value"] = pl_display["Value"].apply(lambda x: format_currency(x) if abs(x) >= 1000 else f"£{x:,.2f}")
    
    bold_accounts = [
        "Gross Trade Sales (GTS)",
        "Net Trade Sales (NTS)",
        "Gross Profit (GP Std)"
    ]
    
    def highlight_bold(row):
        if row["Account"] in bold_accounts:
            return ["font-weight: 600; background-color: #f8f9fa;"] * len(row)
        return [""] * len(row)
    
    st.dataframe(
        pl_display[["Account", "Value"]].style.apply(highlight_bold, axis=1),
        use_container_width=True,
        hide_index=True
    )
    
    st.divider()
    
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
    
    st.markdown("#### P&L to NTS by Channel")
    
    df_gtn_channel = df_filtered.groupby("channel").agg({
        "units_sold": "sum",
        "gross_sales": "sum",
        "returns": "sum",
        "bonus": "sum",
        "gtn_amount": "sum",
        "nts": "sum"
    }).reset_index()
    
    total_gts_ch = df_gtn_channel["gross_sales"].sum()
    if total_gts_ch > 0:
        for col in ["returns", "bonus", "gtn_amount", "nts"]:
            df_gtn_channel[f"{col}_pct"] = (df_gtn_channel[col] / total_gts_ch * 100).round(1)
    else:
        for col in ["returns", "bonus", "gtn_amount", "nts"]:
            df_gtn_channel[f"{col}_pct"] = 0.0
    
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
    if total_gts_cat > 0:
        for col in ["returns", "bonus", "gtn_amount", "nts"]:
            df_gtn_cat[f"{col}_pct"] = (df_gtn_cat[col] / total_gts_cat * 100).round(1)
    else:
        for col in ["returns", "bonus", "gtn_amount", "nts"]:
            df_gtn_cat[f"{col}_pct"] = 0.0
    
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
    
    st.markdown("#### GTN Breakdown Summary")
    st.caption("Units, GTS, GTN and NTS")
    
    df_gtn_summary = df_filtered.groupby("client_name").agg({
        "units_sold": "sum",
        "gross_sales": "sum",
        "gtn_amount": "sum",
        "nts": "sum"
    }).reset_index()
    
    df_gtn_summary["gtn_pct"] = (df_gtn_summary["gtn_amount"] / df_gtn_summary["gross_sales"] * 100).round(1)
    
    st.dataframe(
        df_gtn_summary.style.format({
            "units_sold": "{:,.0f}",
            "gross_sales": "£{:,.0f}",
            "gtn_amount": "£{:,.0f}",
            "nts": "£{:,.0f}",
            "gtn_pct": "{:.1f}%"
        }),
        use_container_width=True,
        hide_index=True
    )
    
    st.divider()
    
    st.markdown("#### SKU-Level GTN Breakdown")
    st.caption("Structural GTN is pro-rated by SKU weight within each client")
    
    df_gtn_sku = df_filtered.groupby(["client_name", "sku", "product_name", "category"]).agg({
        "units_sold": "sum",
        "gross_sales": "sum",
        "structural_gtn_pct": "mean",           # Original (for reference)
        "structural_gtn_pct_pro_rated": "mean",  # Pro-rated (NEW)
        "tactical_gtn_pct": "mean",
        "total_gtn_pct": "mean",
        "gtn_amount": "sum",
        "nts": "sum"
    }).reset_index()
    
    # Format percentages
    for col in ["structural_gtn_pct", "structural_gtn_pct_pro_rated", "tactical_gtn_pct", "total_gtn_pct"]:
        df_gtn_sku[col] = (df_gtn_sku[col] * 100).round(1)
    
    st.dataframe(
        df_gtn_sku.style.format({
            "units_sold": "{:,.0f}",
            "gross_sales": "£{:,.0f}",
            "structural_gtn_pct": "{:.1f}%",
            "structural_gtn_pct_pro_rated": "{:.1f}%",
            "tactical_gtn_pct": "{:.1f}%",
            "total_gtn_pct": "{:.1f}%",
            "gtn_amount": "£{:,.0f}",
            "nts": "£{:,.0f}"
        }),
        use_container_width=True,
        hide_index=True
    )
    
    st.caption("💡 Structural GTN Pro-rated = Structural GTN % × SKU Weight (sales proportion within client)")
    
    st.divider()
    
    st.markdown("#### TIE - Trade Investment Efficiency")
    st.caption("GTN per Unit vs NTS per Unit")
    
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
    
    st.caption("💡 TIE Ratio = GTN per Unit / NTS per Unit. Lower ratio = Higher investment efficiency.")

# ============================================================================
# TAB 3: PRICE ANALYSIS
# ============================================================================
with tab_price:
    st.markdown("### Price Analysis")
    
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

# ============================================================================
# TAB 4: COST EFFICIENCY
# ============================================================================
with tab_cost:
    st.markdown("### Cost Efficiency Analysis")
    
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
    
    st.markdown("#### COGS Efficiency Ranking by SKU")
    st.caption("Lower COGS per Unit = Higher Efficiency")
    
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
    
    st.caption("💡 Efficiency Score = GP per Unit / COGS per Unit * 100. Higher score = Higher efficiency.")
    
    st.divider()
    
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

# ============================================================================
# TAB 5: GP DRIVER ANALYSIS
# ============================================================================
with tab_gp_drivers:
    st.markdown("### GP Driver Analysis")
    st.caption("Is GP low due to Volume, Price or Costs?")

    total_units = df_filtered["units_sold"].sum()
    avg_price = df_filtered["gross_sales"].sum() / total_units if total_units > 0 else 0
    avg_cogs = df_filtered["cogs"].sum() / total_units if total_units > 0 else 0
    avg_gp = avg_price - avg_cogs
    gp_pct = (avg_gp / avg_price * 100) if avg_price > 0 else 0

    col1, col2, col3, col4 = st.columns(4)
    col1.markdown(create_metric_card("Avg Price/Unit", f"£{avg_price:.2f}"), unsafe_allow_html=True)
    col2.markdown(create_metric_card("Avg COGS/Unit", f"£{avg_cogs:.2f}"), unsafe_allow_html=True)
    col3.markdown(create_metric_card("Avg GP/Unit", f"£{avg_gp:.2f}"), unsafe_allow_html=True)
    col4.markdown(create_metric_card("GP %", format_pct(gp_pct)), unsafe_allow_html=True)

    st.divider()

    st.markdown("#### GP Driver Analysis by Client")

    df_drivers = df_filtered.groupby("client_name").agg({
        "units_sold": "sum",
        "gross_sales": "sum",
        "cogs": "sum",
        "nts": "sum",          # Added NTS to fix KeyError
        "gp_std": "sum"
    }).reset_index()

    df_drivers["avg_price"] = df_drivers["gross_sales"] / df_drivers["units_sold"]
    df_drivers["avg_cogs"] = df_drivers["cogs"] / df_drivers["units_sold"]
    df_drivers["avg_gp"] = df_drivers["gp_std"] / df_drivers["units_sold"]
    df_drivers["gp_pct"] = (df_drivers["gp_std"] / df_drivers["nts"] * 100).round(1)

    df_drivers["price_impact"] = (df_drivers["avg_price"] / avg_price * 100).round(1)
    df_drivers["cost_impact"] = (df_drivers["avg_cogs"] / avg_cogs * 100).round(1)

    st.dataframe(
        df_drivers.style.format({
            "units_sold": "{:,.0f}",
            "gross_sales": "£{:,.0f}",
            "cogs": "£{:,.0f}",
            "gp_std": "£{:,.0f}",
            "avg_price": "£{:.2f}",
            "avg_cogs": "£{:.2f}",
            "avg_gp": "£{:.2f}",
            "gp_pct": "{:.1f}%",
            "price_impact": "{:.1f}%",
            "cost_impact": "{:.1f}%"
        }),
        use_container_width=True,
        hide_index=True
    )

    st.caption("💡 Price Impact = Client price vs average. Cost Impact = Client COGS vs average.")

    st.divider()

    st.markdown("#### GP Driver Analysis by SKU")

    df_drivers_sku = df_filtered.groupby(["sku", "product_name", "category"]).agg({
        "units_sold": "sum",
        "gross_sales": "sum",
        "cogs": "sum",
        "nts": "sum",          # Added NTS to fix KeyError
        "gp_std": "sum"
    }).reset_index()

    df_drivers_sku["avg_price"] = df_drivers_sku["gross_sales"] / df_drivers_sku["units_sold"]
    df_drivers_sku["avg_cogs"] = df_drivers_sku["cogs"] / df_drivers_sku["units_sold"]
    df_drivers_sku["avg_gp"] = df_drivers_sku["gp_std"] / df_drivers_sku["units_sold"]
    df_drivers_sku["gp_pct"] = (df_drivers_sku["gp_std"] / df_drivers_sku["nts"] * 100).round(1)

    df_drivers_sku["price_impact"] = (df_drivers_sku["avg_price"] / avg_price * 100).round(1)
    df_drivers_sku["cost_impact"] = (df_drivers_sku["avg_cogs"] / avg_cogs * 100).round(1)

    st.dataframe(
        df_drivers_sku.style.format({
            "units_sold": "{:,.0f}",
            "gross_sales": "£{:,.0f}",
            "cogs": "£{:,.0f}",
            "gp_std": "£{:,.0f}",
            "avg_price": "£{:.2f}",
            "avg_cogs": "£{:.2f}",
            "avg_gp": "£{:.2f}",
            "gp_pct": "{:.1f}%",
            "price_impact": "{:.1f}%",
            "cost_impact": "{:.1f}%"
        }),
        use_container_width=True,
        hide_index=True
    )

    st.caption("💡 Price Impact = SKU price vs average. Cost Impact = SKU COGS vs average.")

    st.divider()

    st.markdown("#### GP Driver Summary")

    summary_data = [
        ("Total GP", f"£{df_filtered['gp_std'].sum():,.0f}", f"{gp_pct:.1f}% of Price"),
        ("Total GTS", f"£{df_filtered['gross_sales'].sum():,.0f}", ""),
        ("Total COGS", f"£{df_filtered['cogs'].sum():,.0f}", f"{(df_filtered['cogs'].sum() / df_filtered['gross_sales'].sum() * 100):.1f}% of GTS"),
        ("Volume Impact", f"{total_units:,.0f} units", f"Avg GP: £{avg_gp:.2f}/unit"),
        ("Price Impact", f"£{(total_units * avg_price):,.0f}", f"Avg Price: £{avg_price:.2f}/unit"),
        ("Cost Impact", f"£{(total_units * avg_cogs):,.0f}", f"Avg COGS: £{avg_cogs:.2f}/unit")
    ]

    df_summary = pd.DataFrame(summary_data, columns=["Driver", "Value", "Note"])

    def highlight_driver(row):
        if row["Driver"] in ["Total GP", "Total GTS", "Total COGS"]:
            return ["font-weight: 600; background-color: #f8f9fa;"] * len(row)
        return [""] * len(row)

    st.dataframe(
        df_summary.style.apply(highlight_driver, axis=1),
        use_container_width=True,
        hide_index=True
    )

# ============================================================================
# TAB 6: RAW DATA
# ============================================================================
with tab_raw:
    st.markdown("### Raw Data")
    st.caption("Detailed P&L data at SKU level with pro-rated Structural GTN")
    
    st.dataframe(
        df_filtered.style.format({
            "units_sold": "{:,.0f}",
            "sku_weight": "{:.4f}",
            "gross_sales": "£{:,.0f}",
            "returns": "£{:,.0f}",
            "bonus": "£{:,.0f}",
            "structural_gtn_pct": "{:.2%}",
            "structural_gtn_pct_pro_rated": "{:.2%}",
            "tactical_gtn_pct": "{:.2%}",
            "total_gtn_pct": "{:.2%}",
            "gtn_amount": "£{:,.0f}",
            "nts": "£{:,.0f}",
            "cogs": "£{:,.0f}",
            "gp_std": "£{:,.0f}",
            "gp_std_pct": "{:.1f}%"
        }),
        use_container_width=True,
        height=500
    )
    
    # Download button
    csv = df_filtered.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="📥 Download Raw Data (CSV)",
        data=csv,
        file_name=f"pl_raw_data_{selected_year}.csv",
        mime="text/csv"
    )