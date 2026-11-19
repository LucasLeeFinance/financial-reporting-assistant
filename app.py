
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

ticker = st.text_input(
    "Enter Stock Ticker",
    value="AAPL"
).strip().upper()

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
        summary = df.copy()
        summary.index = summary.index.strftime("%Y-%m-%d")

        money_cols = [
            "Revenue", "Gross Profit", "Operating Income",
            "Net Income", "Cash", "Total Assets",
            "Total Liabilities", "Equity", "Current Assets",
            "Current Liabilities", "Total Debt",
            "Operating Cash Flow", "Capital Expenditures",
            "Free Cash Flow"
        ]

        summary[money_cols] = summary[money_cols] / 1e9
        financial_summary = summary.round(2).to_string()

        prompt = f"""
        Write a professional financial analyst report for
        {active_ticker} using the following annual data.

        Financial figures are in USD billions unless
        identified as ratios or percentages.

        {financial_summary}

        Write approximately 700-900 words, prioritizing
        accuracy and meaningful analysis over length.

        Include:
        1. Executive Summary
        2. Revenue and Profitability
        3. Balance Sheet and Financial Position
        4. Cash Flow and Earnings Quality
        5. Financial Strengths and Risks
        6. Analyst Conclusion

        Requirements:
        - Reference specific years and financial figures.
        - Interpret changes rather than merely list numbers.
        - Compare earnings with operating cash flow.
        - Discuss liquidity and leverage when data permits.
        - Explain what margins and ratios indicate.
        - Do not invent causes for financial changes.
        - Distinguish facts from possible explanations.
        - Do not label periods as projected without evidence.
        - Do not claim figures were verified against filings.
        - Do not make stock recommendations.
        - Avoid buzzwords, filler, and repetitive language.
        - Write naturally, clearly, and professionally.
        """

        with st.spinner("Generating financial analyst report..."):
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
                        temperature=0.3,
                        max_output_tokens=1800
                    )
                )

                st.session_state.report = (
                    response.text or "No report was returned."
                )

            except Exception as e:
                st.error(f"AI report unavailable: {e}")

    if "report" in st.session_state:
        st.markdown(st.session_state.report)
