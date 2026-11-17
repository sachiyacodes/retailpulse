"""RetailPulse dashboard. Run with ``streamlit run src/retailpulse/dashboard.py``."""

from html import escape
import json
import os
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st


ROOT = Path(__file__).resolve().parents[2]
DATA = Path(os.environ.get("RETAILPULSE_DATA_DIR", ROOT / "data" / "processed"))
TEAL = "#138d80"
COLORS = [TEAL, "#8b80d6", "#e4ad58", "#609fc3", "#d77f8f"]
ICONS = {
    "payments": '<rect x="3" y="5" width="18" height="14" rx="3"/><path d="M3 10h18M7 15h4"/>',
    "shopping_bag": '<path d="M5 7h14l1 14H4L5 7Z"/><path d="M9 8V5a3 3 0 0 1 6 0v3"/>',
    "receipt_long": '<path d="M6 3h12v18l-3-2-3 2-3-2-3 2V3Z M9 8h6M9 12h6"/>',
    "group": '<circle cx="9" cy="8" r="3"/><path d="M3 21v-3a6 6 0 0 1 12 0v3M17 5a3 3 0 0 1 0 6M18 15a5 5 0 0 1 3 5"/>',
}


def chart_style(chart):
    return (chart.properties(background="#ffffff").configure_view(strokeWidth=0)
            .configure_axis(labelColor="#829099", titleColor="#687981", labelFontSize=11,
                            titleFontSize=11, titleFontWeight="normal", gridColor="#edf1f2",
                            domain=False, ticks=False, labelPadding=10, titlePadding=16)
            .configure_legend(labelColor="#687981", labelFontSize=11, title=None,
                              symbolType="circle", orient="bottom"))


def section_label(title, description):
    st.markdown(f'<div class="panel-title">{escape(title)}</div>'
                f'<div class="panel-description">{escape(description)}</div>', unsafe_allow_html=True)


def product_table(ranking, currency, limit=None):
    st.dataframe(ranking.head(limit) if limit else ranking, hide_index=True, width="stretch",
                 column_order=["description", "stock_code", "units", "revenue"],
                 column_config={"description": st.column_config.TextColumn("Product", width="large"),
                                "stock_code": "SKU", "units": "Units sold",
                                "revenue": st.column_config.ProgressColumn(
                                    f"Revenue ({currency})", format="%.2f", min_value=0,
                                    max_value=float(ranking.revenue.max()))})


def main():
    st.set_page_config(page_title="RetailPulse | Retail intelligence", page_icon="◈", layout="wide")
    st.markdown(f"<style>{Path(__file__).with_name('dashboard.css').read_text(encoding='utf-8')}</style>",
                unsafe_allow_html=True)
    transactions = DATA / "transactions.csv"
    if not transactions.exists():
        st.title("Welcome to RetailPulse")
        st.info("No processed data yet. Run the pipeline from the repository root, then refresh this page.")
        st.code("python -m retailpulse.pipeline --output data/processed", language="bash")
        st.stop()
    try:
        frame = pd.read_csv(transactions, dtype={"invoice_no": str, "stock_code": str, "customer_id": str})
        frame["invoice_date"] = pd.to_datetime(frame["invoice_date"], errors="raise")
        required = {"invoice_no", "stock_code", "description", "quantity", "unit_price", "customer_id", "country", "revenue"}
        missing = required - set(frame.columns)
        if missing:
            raise ValueError(f"Missing columns: {', '.join(sorted(missing))}")
        if frame.empty:
            st.info("The processed dataset contains no transactions.")
            st.stop()
        manifest = json.loads((DATA / "manifest.json").read_text(encoding="utf-8")) if (DATA / "manifest.json").exists() else {}
    except (ValueError, OSError, KeyError) as exc:
        st.error(f"Cannot load processed data: {exc}")
        st.stop()

    source = str(manifest.get("source", "Source not recorded"))
    currency = str(manifest.get("currency", "GBP"))
    money = "£" if currency == "GBP" else f"{currency} "
    demo = "synthetic" in source.lower()
    minimum, maximum = frame.invoice_date.dt.date.min(), frame.invoice_date.dt.date.max()

    with st.sidebar:
        st.markdown('''<div class="brand"><span class="brand-mark">▥</span>
                    <span>Retail<span class="brand-accent">Pulse</span></span></div>
                    <div class="brand-description">Clarity in every transaction.</div>
                    <div class="sidebar-label">WORKSPACE</div>''', unsafe_allow_html=True)
        view = st.radio("Workspace", ["Overview", "Products", "Customers", "Forecast"], label_visibility="collapsed")
        st.markdown('<div class="sidebar-label filter-label">FILTER YOUR VIEW</div>', unsafe_allow_html=True)
        dates = st.date_input("Invoice date range", value=(minimum, maximum), min_value=minimum,
                              max_value=maximum, format="DD/MM/YYYY")
        countries = sorted(frame.country.dropna().unique())
        selected = st.multiselect("Countries", countries, default=countries)
        st.caption("Filters apply to sales, products and customers. Forecasts always use the full dataset.")
        with st.expander("How metrics work"):
            st.caption("Revenue = quantity × unit price. Orders = distinct invoices. AOV = revenue / orders. Customers exclude missing IDs.")
        st.markdown('<div class="sidebar-note"><span class="status-dot"></span> LOCAL WORKSPACE'
                    '<p>Your data, a clearer perspective.</p></div>', unsafe_allow_html=True)

    st.markdown('<div class="breadcrumb">WORKSPACE <span>/</span> RETAIL ANALYTICS</div>', unsafe_allow_html=True)
    header, status = st.columns([3, 1], vertical_alignment="center")
    with header:
        st.title({"Overview": "Sales overview", "Products": "Product performance",
                  "Customers": "Customer intelligence", "Forecast": "Revenue forecast"}[view])
        st.caption({"Overview": "Revenue, orders and customer activity at a glance.",
                    "Products": "Discover what sells, and where the value comes from.",
                    "Customers": "Understand the people behind the purchases.",
                    "Forecast": "Look ahead, with the evidence in view."}[view])
    with status:
        label = "Synthetic demo" if demo else source
        st.markdown(f'<div class="source-badge"><span class="status-dot"></span>{escape(label)}</div>', unsafe_allow_html=True)

    if len(dates) != 2:
        st.info("Choose both start and end dates.")
        st.stop()
    visible = frame.loc[frame.invoice_date.dt.date.between(dates[0], dates[1]) & frame.country.isin(selected)].copy()
    if visible.empty:
        st.info("No transactions match these filters. Select a country or widen the date range.")
        st.stop()

    toolbar, export = st.columns([3, 1], vertical_alignment="center")
    with toolbar:
        st.markdown(f'<div class="selection-summary"><span class="calendar-mark">▦</span>'
                    f'{dates[0]:%d %b %Y} <span class="range-separator">—</span> {dates[1]:%d %b %Y}'
                    f'<span class="selection-count">{len(selected)} markets · {len(visible):,} sales lines</span></div>', unsafe_allow_html=True)
    with export:
        st.download_button("Export transactions", visible.to_csv(index=False), "retailpulse_transactions.csv",
                           "text/csv", icon=":material/download:", width="stretch")

    revenue = visible.revenue.sum()
    orders = visible.invoice_no.nunique()
    known = visible.dropna(subset=["customer_id"])
    customer_sales = known.groupby("customer_id", as_index=False).agg(
        revenue=("revenue", "sum"), orders=("invoice_no", "nunique"), last_purchase=("invoice_date", "max")
    ).sort_values("revenue", ascending=False)
    repeat = (customer_sales.orders > 1).mean() if len(customer_sales) else 0
    descriptions = frame.sort_values(["stock_code", "invoice_date", "description"], ascending=[True, False, True]).drop_duplicates("stock_code")
    ranking = visible.groupby("stock_code", as_index=False).agg(revenue=("revenue", "sum"), units=("quantity", "sum"))
    ranking = ranking.merge(descriptions[["stock_code", "description"]], on="stock_code", validate="one_to_one")
    ranking["product"] = ranking.stock_code + " · " + ranking.description
    ranking = ranking.sort_values("revenue", ascending=False)
    country_sales = visible.groupby("country", as_index=False).revenue.sum().sort_values("revenue", ascending=False)

    for column, label, value, detail, icon in zip(
        st.columns(4), ["Total revenue", "Total orders", "Average order value", "Known customers"],
        [f"{money}{revenue:,.2f}", f"{orders:,}", f"{money}{revenue / orders:,.2f}", f"{visible.customer_id.nunique():,}"],
        ["Positive merchandise sales", "Distinct purchase invoices", "Revenue per purchase", "Customers with a recorded ID"],
        ["payments", "shopping_bag", "receipt_long", "group"],
    ):
        with column, st.container(border=True, key=f"kpi-{icon}"):
            st.markdown('<div class="metric-icon"><svg width="18" height="18" viewBox="0 0 24 24" '
                        f'fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" '
                        f'stroke-linejoin="round" aria-hidden="true">{ICONS[icon]}</svg></div>', unsafe_allow_html=True)
            st.metric(label, value)
            st.caption(detail)

    if view == "Overview":
        left, right = st.columns([2, 1], gap="medium")
        with left, st.container(border=True, key="panel-revenue"):
            title, granularity = st.columns([1.4, 1], vertical_alignment="center")
            with title:
                section_label("Revenue performance", f"Purchase revenue in {currency}")
            with granularity:
                interval = st.selectbox("Chart interval", ["Weekly", "Daily", "Monthly"], label_visibility="collapsed")
            frequency = {"Daily": "D", "Weekly": "W", "Monthly": "MS"}[interval]
            daily = visible.set_index("invoice_date").revenue.resample(frequency).sum().rename_axis("date").reset_index()
            area = alt.Chart(daily).mark_area(interpolate="monotone", line={"color": TEAL, "strokeWidth": 2.5},
                color=alt.Gradient(gradient="linear", stops=[alt.GradientStop(color="#b2e1d9", offset=0),
                    alt.GradientStop(color="#ffffff", offset=1)], x1=1, x2=1, y1=0, y2=1)).encode(
                x=alt.X("date:T", title=None, axis=alt.Axis(format="%b %d", grid=False, tickCount=6)),
                y=alt.Y("revenue:Q", title=None, axis=alt.Axis(format="~s", tickCount=5)),
                tooltip=[alt.Tooltip("date:T", title="Period ending" if interval == "Weekly" else "Period"),
                         alt.Tooltip("revenue:Q", title=f"Revenue ({currency})", format=",.2f")]).properties(height=235)
            st.altair_chart(chart_style(area), width="stretch")
            st.caption("Weeks end on Sunday. Boundary weeks may be partial." if interval == "Weekly" else "Totals within the selected date range.")
        with right, st.container(border=True, key="panel-markets"):
            section_label("Revenue by market", "Revenue share · top markets listed below")
            donut = alt.Chart(country_sales).mark_arc(innerRadius=57, outerRadius=80, cornerRadius=4,
                stroke="white", strokeWidth=3).encode(
                theta=alt.Theta("revenue:Q"), color=alt.Color("country:N", scale=alt.Scale(domain=country_sales.country.tolist(), range=COLORS),
                    legend=None),
                tooltip=[alt.Tooltip("country:N", title="Market"), alt.Tooltip("revenue:Q", title=f"Revenue ({currency})", format=",.2f")])
            center = alt.Chart(pd.DataFrame({"label": [str(len(country_sales))]})).mark_text(
                fontSize=32, fontWeight=600, color="#203339", dy=-5).encode(text="label:N")
            subtitle = alt.Chart(pd.DataFrame({"label": ["markets"]})).mark_text(fontSize=11, color="#829099", dy=22).encode(text="label:N")
            st.altair_chart(chart_style((donut + center + subtitle).properties(height=190)), width="stretch")
            legend = "".join(
                f'<div class="market-row"><span><i style="background:{COLORS[i % len(COLORS)]}"></i>'
                f'{escape(row.country)}</span><strong>{row.revenue / revenue:.1%}</strong></div>'
                for i, row in enumerate(country_sales.head(5).itertuples())
            )
            st.markdown(legend, unsafe_allow_html=True)

        products, snapshot = st.columns([2, 1], gap="medium")
        with products, st.container(border=True, key="panel-bestsellers"):
            section_label("Your best sellers", "Top products by purchase revenue")
            product_table(ranking, currency, limit=5)
        with snapshot, st.container(border=True, key="panel-snapshot"):
            section_label("At a glance", "The selected period, in perspective")
            for label, value in [("Leading market", country_sales.iloc[0].country),
                                 ("Units sold", f"{int(visible.quantity.sum()):,}"),
                                 ("Active products", f"{visible.stock_code.nunique():,}"),
                                 ("Repeat customer share", f"{repeat:.1%}")]:
                st.markdown(f'<div class="insight-row"><span>{escape(label)}</span><strong>{escape(str(value))}</strong></div>', unsafe_allow_html=True)

    elif view == "Products":
        with st.container(border=True, key="panel-product-chart"):
            section_label("Products driving sales", "Top 10 products · ranked by purchase revenue")
            bars = alt.Chart(ranking.head(10)).mark_bar(color=TEAL, cornerRadiusEnd=5, size=22).encode(
                x=alt.X("revenue:Q", title=f"Revenue ({currency})"),
                y=alt.Y("product:N", sort="-x", title=None, axis=alt.Axis(labelLimit=300)),
                tooltip=["stock_code", "description", alt.Tooltip("revenue:Q", format=",.2f"), "units"]).properties(height=330)
            st.altair_chart(chart_style(bars), width="stretch")
        with st.container(border=True, key="panel-product-table"):
            section_label("Product breakdown", "One row per product, using its latest observed description")
            product_table(ranking, currency)
        st.caption("Cost and stock records are absent. Profit, inventory and replenishment recommendations are not calculated.")

    elif view == "Customers":
        left, right = st.columns([2, 1])
        with left, st.container(border=True, key="panel-customers"):
            section_label("Customers driving value", "Top 10 known customers by purchase revenue")
            bars = alt.Chart(customer_sales.head(10)).mark_bar(color=TEAL, cornerRadiusEnd=5, size=20).encode(
                x=alt.X("revenue:Q", title=f"Revenue ({currency})"), y=alt.Y("customer_id:N", title="Customer", sort="-x"),
                tooltip=["customer_id", "orders", alt.Tooltip("revenue:Q", format=",.2f")]).properties(height=290)
            st.altair_chart(chart_style(bars), width="stretch")
        with right, st.container(border=True, key="panel-repeat"):
            section_label("Repeat purchasing", "Repeat buying in the selected period")
            st.metric("Repeat customer share", f"{repeat:.1%}")
            st.caption("Share of known customers with more than one invoice. This is not retention.")
            st.caption("Anonymous purchases contribute to revenue, but are excluded from customer counts.")
        with st.container(border=True, key="panel-customer-table"):
            section_label("Customer breakdown", "Purchase activity within your current filters")
            st.dataframe(customer_sales, hide_index=True, width="stretch", column_config={
                "customer_id": "Customer ID", "revenue": st.column_config.NumberColumn(f"Revenue ({currency})", format="%.2f"),
                "orders": "Orders", "last_purchase": st.column_config.DatetimeColumn("Last purchase", format="DD MMM YYYY")})

    else:
        st.caption("Forecasts use the full dataset, independent of sidebar filters. Point estimates are not guaranteed future sales.")
        forecast_path, metrics_path = DATA / "forecast.csv", DATA / "forecast_metrics.json"
        if forecast_path.exists() and metrics_path.exists():
            try:
                forecast = pd.read_csv(forecast_path, parse_dates=["date"])
                metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
                with st.container(border=True, key="panel-forecast"):
                    section_label("Revenue outlook", "Daily purchase revenue · observed history and future estimates")
                    history = frame.set_index("invoice_date").revenue.resample("D").sum().tail(42).rename_axis("date").reset_index()
                    history["series"] = "Observed"
                    future = forecast.rename(columns={"prediction": "revenue"}).assign(series="Forecast")
                    series = pd.concat([history, future], ignore_index=True)
                    line = alt.Chart(series).mark_line(strokeWidth=2.5).encode(
                        x=alt.X("date:T", title=None), y=alt.Y("revenue:Q", title=f"Revenue ({currency})"),
                        color=alt.Color("series:N", scale=alt.Scale(domain=["Observed", "Forecast"], range=[TEAL, "#8b80d6"])),
                        strokeDash=alt.StrokeDash("series:N", scale=alt.Scale(domain=["Observed", "Forecast"], range=[[1, 0], [5, 4]])),
                        tooltip=["date:T", "series:N", alt.Tooltip("revenue:Q", format=",.2f")]).properties(height=280)
                    st.altair_chart(chart_style(line), width="stretch")
                if "selected_model" in metrics:
                    st.caption(f"Selected model: {metrics['selected_model'].replace('_', ' ').title()} · selected using development folds only.")
                if "holdout" in metrics:
                    with st.container(border=True, key="panel-validation"):
                        section_label("Holdout validation", f"Untouched holdout · {metrics['holdout_start']} to {metrics['holdout_end']}")
                        comparison = pd.DataFrame(metrics["holdout"]).T.rename_axis("Model").reset_index()
                        st.dataframe(comparison, hide_index=True, width="stretch", column_config={
                            "mae": st.column_config.NumberColumn("MAE (GBP/day)", format="%.2f"),
                            "rmse": st.column_config.NumberColumn("RMSE (GBP/day)", format="%.2f"),
                            "wape": st.column_config.NumberColumn("WAPE (fraction)", format="%.3f")})
                        st.caption("Lower error is better. WAPE of 0.20 means 20%. No calibrated uncertainty intervals are supplied.")
                with st.expander("Validation folds and methodology"):
                    st.json(metrics, expanded=True)
                st.download_button("Download forecast CSV", forecast.to_csv(index=False), "retailpulse_forecast.csv", "text/csv", icon=":material/download:")
            except (ValueError, KeyError, OSError) as exc:
                st.warning(f"Forecast artifacts cannot be displayed: {exc}")
        else:
            st.info("No validated forecast artifacts found. Run the full pipeline to generate them.")

    with st.expander("Explore transaction details"):
        st.dataframe(visible, hide_index=True, width="stretch")
    provenance = "Synthetic demonstration data · fictional retailer" if demo else f"Source: {source} · inspect the pipeline manifest"
    st.markdown(f'<div class="page-footer"><span>RetailPulse <span class="footer-divider">/</span> Retail intelligence</span>'
                f'<span>{escape(provenance)} · {escape(currency)}</span></div>', unsafe_allow_html=True)


if __name__ == "__main__":
    main()
