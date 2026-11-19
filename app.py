
import streamlit as st
import yfinance as yf
import pandas as pd
from google import genai
from google.genai import types

st.set_page_config(
    page_title="Financial Reporting Assistant",
    page_icon="📊",
    layout="wide"
)

# =====================================
# WEBSITE HEADER AND NAVIGATION
# =====================================

st.markdown("""
<style>
.block-container {
    max-width: 1250px;
    padding-top: 2rem;
    padding-bottom: 3rem;
}

h1, h2, h3 {
    letter-spacing: -0.5px;
}

div[data-testid="stMetric"] {
    background-color: rgba(128, 128, 128, 0.07);
    padding: 18px;
    border-radius: 12px;
    border: 1px solid rgba(128, 128, 128, 0.15);
}

div[data-testid="stDataFrame"] {
    border-radius: 10px;
}
</style>
""", unsafe_allow_html=True)

st.sidebar.title("Financial Reporting Assistant")
st.sidebar.caption("Financial Analysis Platform")

st.sidebar.markdown("### Navigation")
st.sidebar.info(
    "Use the sections below to analyze financial "
    "statements, compare companies, verify SEC data, "
    "and review advanced financial metrics."
)

st.sidebar.divider()
st.sidebar.caption(
    "Data: Yahoo Finance | Verification: SEC EDGAR"
)

st.title("📊 Financial Reporting Assistant")
st.write(
    "Financial statement analysis, performance trends, "
    "and AI-assisted analyst commentary."
)
st.caption(
    "Source: Yahoo Finance via yfinance. "
    "Figures should be verified against company filings."
)


def get_value(statement, names, date):
    for name in names:
        if name in statement.index and date in statement.columns:
            value = statement.loc[name, date]
            if pd.notna(value):
                return float(value)
    return None


def safe_ratio(numerator, denominator, multiplier=1):
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator * multiplier


@st.cache_data(ttl=3600)
def get_financial_data(ticker):
    company = yf.Ticker(ticker)

    income = company.income_stmt
    balance = company.balance_sheet
    cashflow = company.cashflow

    if income.empty:
        raise ValueError("No annual income statement found.")

    dates = sorted(pd.to_datetime(income.columns))

    records = []

    for date in dates:
        revenue = get_value(income, ["Total Revenue"], date)
        gross_profit = get_value(income, ["Gross Profit"], date)
        operating_income = get_value(
            income, ["Operating Income"], date
        )
        net_income = get_value(
            income, ["Net Income", "Net Income Common Stockholders"], date
        )

        cash = get_value(
            balance,
            ["Cash And Cash Equivalents",
             "Cash Cash Equivalents And Short Term Investments"],
            date
        )

        assets = get_value(balance, ["Total Assets"], date)
        liabilities = get_value(
            balance, ["Total Liabilities Net Minority Interest"], date
        )
        equity = get_value(
            balance, ["Stockholders Equity", "Common Stock Equity"], date
        )
        current_assets = get_value(
            balance, ["Current Assets"], date
        )
        current_liabilities = get_value(
            balance, ["Current Liabilities"], date
        )
        debt = get_value(
            balance, ["Total Debt"], date
        )

        operating_cashflow = get_value(
            cashflow, ["Operating Cash Flow"], date
        )
        capex = get_value(
            cashflow, ["Capital Expenditure"], date
        )

        free_cashflow = None
        if operating_cashflow is not None and capex is not None:
            free_cashflow = operating_cashflow + capex

        records.append({
            "Date": date,
            "Revenue": revenue,
            "Gross Profit": gross_profit,
            "Operating Income": operating_income,
            "Net Income": net_income,
            "Cash": cash,
            "Total Assets": assets,
            "Total Liabilities": liabilities,
            "Equity": equity,
            "Current Assets": current_assets,
            "Current Liabilities": current_liabilities,
            "Total Debt": debt,
            "Operating Cash Flow": operating_cashflow,
            "Capital Expenditures": capex,
            "Free Cash Flow": free_cashflow
        })

    df = pd.DataFrame(records).set_index("Date")
    df = df.sort_index()
 # Remove years without the three core financial statements.
    required_columns = [
        "Revenue",
        "Net Income",
        "Total Assets",
        "Operating Cash Flow"
    ]

    df = df.dropna(subset=required_columns)

    if df["Revenue"].notna().sum() < 2:
        raise ValueError("Insufficient annual financial data.")

    df["Revenue Growth (%)"] = df["Revenue"].pct_change() * 100
    df["Gross Margin (%)"] = (
        df["Gross Profit"] / df["Revenue"] * 100
    )
    df["Operating Margin (%)"] = (
        df["Operating Income"] / df["Revenue"] * 100
    )
    df["Net Margin (%)"] = (
        df["Net Income"] / df["Revenue"] * 100
    )
    df["Current Ratio"] = (
        df["Current Assets"] / df["Current Liabilities"]
    )
    df["Debt to Equity"] = df["Total Debt"] / df["Equity"]

    # ROE uses average equity when prior-year equity is available.
    average_equity = (
        df["Equity"] + df["Equity"].shift(1)
    ) / 2
    df["ROE (%)"] = df["Net Income"] / average_equity * 100

    return df


def format_financial_table(df, columns, money=False):
    table = df[columns].copy()

    # Display fiscal years as column headings.
    table.index = table.index.year.astype(str)
    table = table.T
    table.columns.name = "Fiscal Year"

    if money:
        table = table / 1e9

    return table.round(2)

def build_verified_observations(df):
    observations = []

    for i in range(1, len(df)):
        current = df.iloc[i]
        previous = df.iloc[i - 1]
        year = df.index[i].year

        revenue = current["Revenue"]
        prior_revenue = previous["Revenue"]

        if pd.notna(revenue) and pd.notna(prior_revenue):
            if prior_revenue != 0:
                growth = (revenue / prior_revenue - 1) * 100
                observations.append(
                    f"FY{year} revenue growth: {growth:.2f}%."
                )

        operating_cash = current["Operating Cash Flow"]
        net_income = current["Net Income"]

        if pd.notna(operating_cash) and pd.notna(net_income):
            difference = operating_cash - net_income

            if difference >= 0:
                observations.append(
                    f"FY{year} operating cash flow exceeded "
                    f"or equaled net income by "
                    f"${difference / 1e9:.2f} billion."
                )
            else:
                observations.append(
                    f"FY{year} operating cash flow was below "
                    f"net income by "
                    f"${abs(difference) / 1e9:.2f} billion."
                )

        operating_margin = current["Operating Margin (%)"]
        prior_margin = previous["Operating Margin (%)"]

        if pd.notna(operating_margin) and pd.notna(prior_margin):
            change = operating_margin - prior_margin
            observations.append(
                f"FY{year} operating margin changed by "
                f"{change:+.2f} percentage points."
            )

    return "\n".join(observations)


ticker = st.text_input(
    "Enter Stock Ticker",
    value="AAPL"
).strip().upper()


# Official SEC filing resources
st.subheader("Official SEC Filings")

st.write(
    "Financial data comes from Yahoo Finance. "
    "Review official SEC filings to verify the figures."
)


st.link_button(
    "Search Official SEC Filings",
    f"https://www.sec.gov/edgar/search/#/q={ticker}&filter_forms=10-K"


)

st.caption(
    f"Search for {ticker} on the SEC website. "
    "Use Form 10-K for annual financial statements."
)

if st.button("Analyze Company", type="primary"):
    st.session_state.pop("report", None)
    st.session_state.pop("df", None)
    st.session_state.pop("analyzed_ticker", None)

    with st.spinner("Retrieving financial statements..."):
        try:
            df = get_financial_data(ticker)
            st.session_state.df = df
            st.session_state.analyzed_ticker = ticker
        except Exception as e:
            st.error(f"Unable to analyze company: {e}")


if "df" in st.session_state:
    df = st.session_state.df
    active_ticker = st.session_state.analyzed_ticker

    latest = df.iloc[-1]
    latest_year = df.index[-1].year

    st.header(f"{active_ticker} — Fiscal {latest_year}")

    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "Revenue",
        f"${latest['Revenue']/1e9:,.2f}B"
    )
    col2.metric(
        "Revenue Growth",
        f"{latest['Revenue Growth (%)']:.2f}%"
    )
    col3.metric(
        "Operating Margin",
        f"{latest['Operating Margin (%)']:.2f}%"
    )
    col4.metric(
        "Free Cash Flow",
        f"${latest['Free Cash Flow']/1e9:,.2f}B"
        if pd.notna(latest["Free Cash Flow"]) else "N/A"
    )

   
    st.subheader("Financial Statements")

    tab1, tab2, tab3, tab4 = st.tabs([
        "Income Statement",
        "Balance Sheet",
        "Cash Flow",
        "Financial Ratios"
    ])

    with tab1:
        income_cols = [
            "Revenue",
            "Gross Profit",
            "Operating Income",
            "Net Income"
        ]
        st.dataframe(
            format_financial_table(
                df, income_cols, money=True
            ),
            use_container_width=True
        )
        st.caption("USD billions")

    with tab2:
        balance_cols = [
            "Cash",
            "Total Assets",
            "Total Liabilities",
            "Equity",
            "Total Debt"
        ]
        st.dataframe(
            format_financial_table(
                df, balance_cols, money=True
            ),
            use_container_width=True
        )
        st.caption("USD billions")

    with tab3:
        cash_cols = [
            "Operating Cash Flow",
            "Capital Expenditures",
            "Free Cash Flow"
        ]
        st.dataframe(
            format_financial_table(
                df, cash_cols, money=True
            ),
            use_container_width=True
        )
        st.caption("USD billions")

    with tab4:
        ratio_cols = [
            "Revenue Growth (%)",
            "Gross Margin (%)",
            "Operating Margin (%)",
            "Net Margin (%)",
            "Current Ratio",
            "Debt to Equity",
            "ROE (%)"
        ]
        st.dataframe(
            format_financial_table(
                df, ratio_cols
            ),
            use_container_width=True
        )
        st.caption(
            "Percentages are labeled (%). "
            "Current Ratio and Debt to Equity are multiples."
        )

   
    st.subheader("Financial Trends")

    chart_df = df.copy()
    chart_df.index = chart_df.index.year.astype(str)
    chart_df.index.name = "Fiscal Year"

    left, right = st.columns(2)

    with left:
        st.write("Revenue and Operating Income")
        st.bar_chart(
            chart_df[["Revenue", "Operating Income"]] / 1e9,
            x_label="Fiscal Year",
            y_label="USD billions"
        )

    with right:
        st.write("Operating and Net Profit Margins")
        st.line_chart(
            chart_df[
                ["Operating Margin (%)", "Net Margin (%)"]
            ],
            x_label="Fiscal Year",
            y_label="Margin (%)"
        )

    st.write("Operating Cash Flow vs. Net Income")

    st.bar_chart(
        chart_df[
            ["Operating Cash Flow", "Net Income"]
        ] / 1e9,
        x_label="Fiscal Year",
        y_label="USD billions"
    )


    st.subheader("Financial Analyst Report")

   
    if st.button("Generate AI Report"):
        st.session_state.pop("report", None)

        # Prepare a smaller financial dataset for Gemini.
        report_columns = [
            "Revenue",
            "Gross Profit",
            "Operating Income",
            "Net Income",
            "Total Assets",
            "Total Liabilities",
            "Equity",
            "Total Debt",
            "Operating Cash Flow",
            "Free Cash Flow",
            "Revenue Growth (%)",
            "Gross Margin (%)",
            "Operating Margin (%)",
            "Net Margin (%)",
            "Current Ratio",
            "Debt to Equity",
            "ROE (%)"
        ]

        report_data = df[report_columns].copy()
        report_data.index = report_data.index.year
        report_data.index.name = "Fiscal Year"

        money_columns = [
            "Revenue",
            "Gross Profit",
            "Operating Income",
            "Net Income",
            "Total Assets",
            "Total Liabilities",
            "Equity",
            "Total Debt",
            "Operating Cash Flow",
            "Free Cash Flow"
        ]

        report_data[money_columns] /= 1e9

        # Use explicit missing-value labels.
        report_table = report_data.round(2).to_string(
            na_rep="N/A"
        )

        verified_observations = build_verified_observations(df)

        prompt = f"""
        You are preparing a financial analyst research report.

        Company ticker: {active_ticker}

        The financial dataset below contains annual figures.
        Monetary figures are in USD billions.
        Percentage metrics are explicitly labeled (%).
        Ratios without (%) are multiples.

        FINANCIAL DATA:
        {report_table}

        PRECALCULATED OBSERVATIONS:
        {verified_observations}

        IMPORTANT:
        - Use the exact metric names in the dataset.
        - Never confuse gross, operating, and net margins.
        - Never describe a decrease as growth.
        - Never describe increasing debt-to-equity as
          improving leverage.
        - Compare operating cash flow and net income
          separately for each fiscal year.
        - Never claim a trend applies to every year
          when an exception exists.
        - Do not invent business explanations.
        - Do not invent financial figures.
        - Treat the figures as third-party provider data,
          not independently verified SEC filing data.
        - Do not label periods as forecasts without evidence.

        Write approximately 650-850 words.
        Do not add filler to meet the word target.

        REPORT STRUCTURE:
        1. Executive Summary
        2. Revenue and Profitability
        3. Balance Sheet and Liquidity
        4. Cash Flow and Earnings Quality
        5. Financial Strengths and Risks
        6. Analyst Conclusion

        WRITING STYLE:
        - Professional, clear, and natural.
        - Use specific figures only when they add value.
        - Explain why financial changes matter.
        - Avoid exaggerated claims and corporate buzzwords.
        - Avoid repeating the same conclusion.
        - Do not make investment recommendations.

        Before finalizing, check every numerical comparison
        against the supplied dataset and observations.
        """

        with st.spinner("Preparing financial analyst report..."):
            try:
                client = genai.Client(
                    api_key=st.secrets["GEMINI_API_KEY"],
                    http_options=types.HttpOptions(
                        timeout=60000
                    )
                )

                response = client.models.generate_content(
                    model="gemini-3.5-flash-lite",
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.1,
                        max_output_tokens=2000
                    )
                )

                st.session_state.report = (
                    response.text or "No report was returned."
                )

            except Exception as e:
                st.error(f"AI report unavailable: {e}")

    if "report" in st.session_state:
        st.markdown(st.session_state.report)
    
# =====================================
# COMPANY COMPARISON
# =====================================

st.divider()
st.header("Company Comparison")
st.write(
    "Compare two publicly traded companies using "
    "their latest available annual financial statements."
)

left_input, right_input = st.columns(2)

with left_input:
    ticker_1 = st.text_input(
        "First Company",
        value="AAPL",
        key="comparison_ticker_1"
    ).strip().upper()

with right_input:
    ticker_2 = st.text_input(
        "Second Company",
        value="MSFT",
        key="comparison_ticker_2"
    ).strip().upper()


if st.button("Compare Companies"):
    st.session_state.pop("comparison_data", None)

    if not ticker_1 or not ticker_2:
        st.warning("Enter two stock tickers.")

    elif ticker_1 == ticker_2:
        st.warning("Choose two different companies.")

    else:
        with st.spinner("Loading company financial data..."):
            try:
                company_1 = get_financial_data(ticker_1)
                company_2 = get_financial_data(ticker_2)

                st.session_state.comparison_data = {
                    "ticker_1": ticker_1,
                    "ticker_2": ticker_2,
                    "company_1": company_1,
                    "company_2": company_2
                }

            except Exception as e:
                st.error(f"Comparison unavailable: {e}")


if "comparison_data" in st.session_state:
    comparison = st.session_state.comparison_data

    df1 = comparison["company_1"]
    df2 = comparison["company_2"]

    name1 = comparison["ticker_1"]
    name2 = comparison["ticker_2"]

    latest1 = df1.iloc[-1]
    latest2 = df2.iloc[-1]

    date1 = df1.index[-1].strftime("%B %d, %Y")
    date2 = df2.index[-1].strftime("%B %d, %Y")

    st.subheader(f"{name1} vs. {name2}")

    st.caption(
        f"{name1} fiscal year ended {date1}. "
        f"{name2} fiscal year ended {date2}. "
        "Reporting periods may differ."
    )

    metrics = {
        "Revenue (USD billions)": "Revenue",
        "Revenue Growth (%)": "Revenue Growth (%)",
        "Gross Margin (%)": "Gross Margin (%)",
        "Operating Margin (%)": "Operating Margin (%)",
        "Net Margin (%)": "Net Margin (%)",
        "Current Ratio": "Current Ratio",
        "Debt to Equity": "Debt to Equity",
        "ROE (%)": "ROE (%)",
        "Operating Cash Flow (USD billions)": "Operating Cash Flow",
        "Free Cash Flow (USD billions)": "Free Cash Flow"
    }

    rows = []

    for label, column in metrics.items():
        value1 = latest1[column]
        value2 = latest2[column]

        if "USD billions" in label:
            value1 = value1 / 1e9
            value2 = value2 / 1e9

        rows.append({
            "Financial Metric": label,
            name1: value1,
            name2: value2
        })

    comparison_table = pd.DataFrame(rows)
    comparison_table = comparison_table.set_index(
        "Financial Metric"
    )

    st.dataframe(
        comparison_table.round(2),
        use_container_width=True
    )

    st.caption(
        "Figures are sourced from Yahoo Finance via yfinance. "
        "Financial metrics are not adjusted for differences "
        "in fiscal year-end dates or accounting policies."
    )

    st.subheader("Profitability Comparison")

    margin_metrics = [
        "Gross Margin (%)",
        "Operating Margin (%)",
        "Net Margin (%)"
    ]

    margin_chart = pd.DataFrame({
        name1: [
            latest1[metric] for metric in margin_metrics
        ],
        name2: [
            latest2[metric] for metric in margin_metrics
        ]
    }, index=[
        "Gross Margin",
        "Operating Margin",
        "Net Margin"
    ])

    st.bar_chart(
        margin_chart,
        x_label="Profitability Metric",
        y_label="Margin (%)"
    )

    st.subheader("Cash Flow Comparison")

    cash_chart = pd.DataFrame({
        name1: [
            latest1["Operating Cash Flow"] / 1e9,
            latest1["Free Cash Flow"] / 1e9
        ],
        name2: [
            latest2["Operating Cash Flow"] / 1e9,
            latest2["Free Cash Flow"] / 1e9
        ]
    }, index=[
        "Operating Cash Flow",
        "Free Cash Flow"
    ])

    st.bar_chart(
        cash_chart,
        x_label="Cash Flow Metric",
        y_label="USD billions"
    )

    st.subheader("AI Company Comparison")

    if st.button("Generate Comparison Report"):
        st.session_state.pop("comparison_report", None)

        # Prepare the same financial metrics for both companies.
        comparison_input = comparison_table.round(2).to_string()

        prompt = f"""
        Write a concise comparative financial analyst report.

        Company 1: {name1}
        Fiscal year ended: {date1}

        Company 2: {name2}
        Fiscal year ended: {date2}

        Financial comparison:
        {comparison_input}

        IMPORTANT:
        - Monetary figures are in USD billions.
        - Percentage figures and ratios are labeled.
        - The companies have different fiscal year-end dates.
        - Do not assume their reporting periods are identical.
        - Compare profitability, revenue growth, liquidity,
          leverage, and operating cash flow.
        - Explain differences in financial scale.
        - Do not assume higher absolute revenue or cash flow
          automatically means better financial performance.
        - Do not invent reasons for financial differences.
        - Do not confuse operating margin with net margin.
        - Never invent missing figures.
        - Avoid unsupported claims about business quality.
        - Do not make stock recommendations.

        Write approximately 400-600 words.

        Structure:
        1. Executive Comparison
        2. Growth and Profitability
        3. Financial Position
        4. Cash Flow
        5. Analyst Takeaways

        Use clear, natural financial writing.
        Focus on interpretation rather than repeating numbers.
        """

        with st.spinner("Generating company comparison..."):
            try:
                client = genai.Client(
                    api_key=st.secrets["GEMINI_API_KEY"],
                    http_options=types.HttpOptions(
                        timeout=60000
                    )
                )

                response = client.models.generate_content(
                    model="gemini-3.5-flash-lite",
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.1,
                        max_output_tokens=1400
                    )
                )

                st.session_state.comparison_report = (
                    response.text or "No comparison was returned."
                )

            except Exception as e:
                st.error(f"Comparison report unavailable: {e}")

    if "comparison_report" in st.session_state:
        st.markdown(st.session_state.comparison_report)

# =====================================
# SEC FINANCIAL DATA VERIFICATION
# =====================================

import requests

st.divider()
st.header("SEC Financial Data Verification")

st.write(
    "Compare Yahoo Finance annual financial figures "
    "with official SEC XBRL data for matching fiscal periods."
)

SEC_HEADERS = {
    "User-Agent": (
        f"FinancialReportingAssistant "
        f"{st.secrets['SEC_CONTACT_EMAIL']}"
    ),
    "Accept-Encoding": "gzip, deflate",
}


@st.cache_data(ttl=86400)
def get_sec_company_tickers():
    url = "https://www.sec.gov/files/company_tickers.json"

    response = requests.get(
        url, headers=SEC_HEADERS, timeout=20
    )
    response.raise_for_status()

    companies = response.json()

    return {
        company["ticker"].upper(): str(
            company["cik_str"]
        ).zfill(10)
        for company in companies.values()
    }


@st.cache_data(ttl=86400)
def get_sec_company_facts(cik):
    url = (
        "https://data.sec.gov/api/xbrl/companyfacts/"
        f"CIK{cik}.json"
    )

    response = requests.get(
        url, headers=SEC_HEADERS, timeout=25
    )
    response.raise_for_status()

    return response.json()



def get_sec_annual_value(facts, tags, fiscal_end):
    us_gaap = facts.get("facts", {}).get("us-gaap", {})
    target_date = pd.Timestamp(fiscal_end)
    matches = []

    for priority, tag in enumerate(tags):
        entries = (
            us_gaap.get(tag, {})
            .get("units", {})
            .get("USD", [])
        )

        for entry in entries:
            if entry.get("form") != "10-K":
                continue

            if not all(
                key in entry
                for key in ["start", "end", "val"]
            ):
                continue

            try:
                start = pd.Timestamp(entry["start"])
                end = pd.Timestamp(entry["end"])
            except (ValueError, TypeError):
                continue

            # Allow Yahoo Finance and SEC fiscal dates
            # to differ by up to seven days.
            date_difference = abs(
                (end - target_date).days
            )

            duration = (end - start).days

            if date_difference > 7:
                continue

            if not 350 <= duration <= 380:
                continue

            matches.append({
                "priority": priority,
                "date_difference": date_difference,
                "filed": entry.get("filed", ""),
                "value": float(entry["val"]),
                "tag": tag,
                "sec_date": end.strftime("%Y-%m-%d"),
            })

    if not matches:
        return None, None, None

    # Prefer closest date, preferred accounting tag,
    # and most recently filed annual value.
    matches.sort(
        key=lambda x: (
            x["date_difference"],
            x["priority"],
            x["filed"],
        )
    )

    closest_date = matches[0]["date_difference"]
    closest_matches = [
        x for x in matches
        if x["date_difference"] == closest_date
    ]

    best_priority = min(
        x["priority"] for x in closest_matches
    )

    preferred = [
        x for x in closest_matches
        if x["priority"] == best_priority
    ]

    selected = max(
        preferred,
        key=lambda x: x["filed"]
    )

    return (
        selected["value"],
        selected["tag"],
        selected["sec_date"],
    )



if "df" in st.session_state and "analyzed_ticker" in st.session_state:

    verification_ticker = st.session_state.analyzed_ticker
    verification_df = st.session_state.df

    st.write(
        f"Selected company: **{verification_ticker}**"
    )

    if st.button("Verify Financial Data Against SEC"):

        with st.spinner("Retrieving official SEC data..."):

            try:
                ticker_map = get_sec_company_tickers()

                if verification_ticker not in ticker_map:
                    st.warning(
                        "This ticker was not found in the "
                        "SEC company directory."
                    )
                else:
                    cik = ticker_map[verification_ticker]
                    sec_facts = get_sec_company_facts(cik)

                    metric_tags = {
                        "Revenue": [
                            "RevenueFromContractWithCustomerExcludingAssessedTax",
                            "Revenues",
                            "SalesRevenueNet",
                        ],
                        "Net Income": [
                            "NetIncomeLoss",
                        ],
                    }

                    results = []

                    for date, row in verification_df.iterrows():

                        fiscal_end = date.strftime("%Y-%m-%d")

                        for metric, tags in metric_tags.items():

                            yahoo_value = row.get(metric)

                            
                            sec_value, sec_tag, sec_date = (
                                get_sec_annual_value(
                                    sec_facts,
                                    tags,
                                    fiscal_end

                                )
                            )

                            if (
                                sec_value is None
                                or pd.isna(yahoo_value)
                            ):
                                results.append({
                                    "Fiscal Year End": fiscal_end,
                                    "SEC Reporting Date": sec_date,
                                    "Metric": metric,
                                    "Yahoo Finance ($B)": (
                                        yahoo_value / 1e9
                                        if pd.notna(yahoo_value)
                                        else None
                                    ),
                                    "SEC ($B)": (
                                        sec_value / 1e9
                                        if sec_value is not None
                                        else None
                                    ),
                                    "Difference ($B)": None,
                                    "Difference (%)": None,
                                    "Status": "Not verified",
                                })
                                continue

                            difference = (
                                float(yahoo_value) - sec_value
                            )

                            percent_difference = (
                                abs(difference) / abs(sec_value) * 100
                                if sec_value != 0
                                else None
                            )

                            tolerance = max(
                                abs(sec_value) * 0.001,
                                1_000_000
                            )

                            status = (
                                "Numerically matched"
                                if abs(difference) <= tolerance
                                else "Review difference"
                            )

                            results.append({
                                "Fiscal Year End": fiscal_end,
                                "SEC Reporting Date": sec_date,
                                "Metric": metric,
                                "Yahoo Finance ($B)": (
                                    float(yahoo_value) / 1e9
                                ),
                                "SEC ($B)": sec_value / 1e9,
                                "Difference ($B)": difference / 1e9,
                                "Difference (%)": percent_difference,
                                "Status": status,
                            })

                    st.session_state.sec_verification = {
                        "ticker": verification_ticker,
                        "results": pd.DataFrame(results),
                    }

            except requests.exceptions.RequestException as e:
                st.error(
                    "SEC data could not be retrieved. "
                    "The SEC may be temporarily unavailable "
                    "or may have restricted this request."
                )
                st.caption(str(e))

            except Exception as e:
                st.error(f"Verification unavailable: {e}")


    if "sec_verification" in st.session_state:

        saved = st.session_state.sec_verification

        if saved["ticker"] == verification_ticker:

            st.subheader("Verification Results")

            st.dataframe(
                saved["results"].round(3),
                use_container_width=True
            )

            st.caption(
                "Numerically matched means the values agree "
                "within 0.1% or $1 million, whichever is larger. "
                "This is not an audit or a guarantee of accuracy. "
                "Missing figures and accounting-definition "
                "differences require manual review."
            )

            st.link_button(
                "View SEC Company Facts",
                (
                    "https://data.sec.gov/api/xbrl/"
                    "companyfacts/CIK"
                    + get_sec_company_tickers()[
                        verification_ticker
                    ]
                    + ".json"
                )
            )

else:
    st.info(
        "Analyze a company above to enable "
        "SEC financial data verification."
    )

# =====================================
# ADVANCED FINANCIAL ANALYSIS
# =====================================

st.divider()
st.header("Advanced Financial Analysis")

if "df" in st.session_state and "analyzed_ticker" in st.session_state:

    advanced_df = st.session_state.df.copy()
    advanced_ticker = st.session_state.analyzed_ticker

    st.write(
        f"Additional profitability, growth, and cash flow "
        f"analysis for **{advanced_ticker}**."
    )

    # Calculate additional metrics
    advanced_df["FCF Margin (%)"] = (
        advanced_df["Free Cash Flow"]
        / advanced_df["Revenue"] * 100
    )

    advanced_df["Cash Conversion Ratio"] = (
        advanced_df["Operating Cash Flow"]
        / advanced_df["Net Income"]
    )

    advanced_df["CapEx Intensity (%)"] = (
        (
            advanced_df["Operating Cash Flow"]
            - advanced_df["Free Cash Flow"]
        )
        / advanced_df["Revenue"] * 100
    )

    advanced_df["Asset Turnover"] = (
        advanced_df["Revenue"]
        / (
            (
                advanced_df["Total Assets"]
                + advanced_df["Total Assets"].shift(1)
            ) / 2
        )
    )

    latest = advanced_df.iloc[-1]

    st.subheader("Financial Performance Indicators")

    col1, col2, col3, col4 = st.columns(4)

    def show_advanced_metric(column, label, suffix="", decimals=2):
        value = latest[column]
        if pd.notna(value):
            st.metric(label, f"{value:.{decimals}f}{suffix}")
        else:
            st.metric(label, "N/A")

    with col1:
        show_advanced_metric("FCF Margin (%)", "FCF Margin", "%")

    with col2:
        show_advanced_metric(
            "Cash Conversion Ratio",
            "Cash Conversion",
            "x"
        )

    with col3:
        show_advanced_metric(
            "CapEx Intensity (%)",
            "CapEx / Revenue",
            "%"
        )

    with col4:
        show_advanced_metric(
            "Asset Turnover",
            "Asset Turnover",
            "x"
        )

    st.subheader("Advanced Financial Ratio Trends")

    advanced_chart = advanced_df[
        ["FCF Margin (%)", "CapEx Intensity (%)"]
    ].copy()

    advanced_chart.index = (
        advanced_chart.index.year.astype(str)
    )

    st.line_chart(
        advanced_chart,
        x_label="Fiscal Year",
        y_label="Percentage (%)"
    )

    st.subheader("Cash Conversion Trends")

    cash_conversion_chart = advanced_df[
        ["Cash Conversion Ratio"]
    ].copy()

    cash_conversion_chart = cash_conversion_chart.replace(
        [float("inf"), float("-inf")],
        float("nan")
    )

    cash_conversion_chart.index = (
        cash_conversion_chart.index.year.astype(str)
    )

    st.line_chart(
        cash_conversion_chart,
        x_label="Fiscal Year",
        y_label="Operating Cash Flow / Net Income"
    )

    st.subheader("Financial Strengths and Risks")

    observations = []

    if pd.notna(latest["FCF Margin (%)"]):
        observations.append(
            f"Free cash flow margin is "
            f"{latest['FCF Margin (%)']:.2f}%, "
            "showing the proportion of revenue "
            "remaining as free cash flow."
        )

    if pd.notna(latest["Cash Conversion Ratio"]):
        observations.append(
            f"Operating cash flow is "
            f"{latest['Cash Conversion Ratio']:.2f} times "
            "reported net income. Interpret this ratio "
            "carefully when net income is negative or small."
        )

    if pd.notna(latest["CapEx Intensity (%)"]):
        observations.append(
            f"Capital expenditure intensity is "
            f"{latest['CapEx Intensity (%)']:.2f}% "
            "of revenue, based on the cash flow data."
        )

    if pd.notna(latest["Current Ratio"]):
        observations.append(
            f"The current ratio is "
            f"{latest['Current Ratio']:.2f}, "
            "indicating current assets relative "
            "to current liabilities."
        )

    if pd.notna(latest["Debt to Equity"]):
        observations.append(
            f"Debt-to-equity is "
            f"{latest['Debt to Equity']:.2f}, "
            "indicating debt relative to "
            "shareholders' equity."
        )

    for observation in observations:
        st.write("• " + observation)

    st.caption(
        "These indicators are descriptive, not investment "
        "recommendations. Ratio interpretation depends on "
        "industry, accounting policies, and financial context."
    )

else:
    st.info(
        "Analyze a company above to view advanced financial metrics."
    )
