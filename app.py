
import streamlit as st
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
from google import genai

st.set_page_config(
    page_title="Financial Reporting Assistant",
    page_icon="📊",
    layout="wide"
)

st.title("📊 Financial Reporting Assistant")
st.write(
    "Analyze public companies using financial statements, "
    "Python calculations, charts, and AI."
)

st.caption(
    "Financial data from Yahoo Finance via yfinance. "
    "Verify figures against official company filings. "
    "AI commentary is for educational purposes, not investment advice."
)

ticker = st.text_input("Enter a Stock Ticker", value="AAPL")
analyze = st.button("Analyze Company", type="primary")

if analyze:
    ticker = ticker.strip().upper()

    if not ticker:
        st.error("Please enter a stock ticker.")
        st.stop()

    # Retrieve financial data
    with st.spinner("Retrieving financial statements..."):
        try:
            company = yf.Ticker(ticker)
            financials = company.income_stmt
        except Exception as e:
            st.error(f"Could not retrieve data: {e}")
            st.stop()

    if financials.empty:
        st.error("No financial data was found for this ticker.")
        st.stop()

    for item in ["Total Revenue", "Net Income"]:
        if item not in financials.index:
            st.error(f"Missing required financial data: {item}")
            st.stop()

    # Organize the financial data
    df = pd.DataFrame({
        "Revenue": financials.loc["Total Revenue"],
        "Net Income": financials.loc["Net Income"]
    })

    df.index = pd.to_datetime(df.index)
    df = df.sort_index()
    df = df.dropna(subset=["Revenue", "Net Income"])

    if len(df) < 2:
        st.error("At least two years of financial data are required.")
        st.stop()

    # Calculate financial metrics
    df["Profit Margin"] = (
        df["Net Income"] / df["Revenue"] * 100
    )

    df["Revenue Growth"] = (
        df["Revenue"].pct_change() * 100
    )

    latest = df.iloc[-1]
    previous = df.iloc[-2]
    latest_year = df.index[-1].year

    # Display financial metrics
    st.subheader(f"{ticker} — Fiscal Year {latest_year}")

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Revenue",
        f"${latest['Revenue'] / 1e9:,.2f}B"
    )

    col2.metric(
        "Revenue Growth",
        f"{latest['Revenue Growth']:.2f}%"
    )

    col3.metric(
        "Net Profit Margin",
        f"{latest['Profit Margin']:.2f}%"
    )

    # Display financial table
    st.subheader("Financial Performance")

    display_df = df.copy()
    display_df.index = display_df.index.year
    display_df.index.name = "Fiscal Year"

    display_df["Revenue"] /= 1e9
    display_df["Net Income"] /= 1e9

    display_df = display_df.rename(columns={
        "Revenue": "Revenue ($B)",
        "Net Income": "Net Income ($B)",
        "Profit Margin": "Profit Margin (%)",
        "Revenue Growth": "Revenue Growth (%)"
    })

    st.dataframe(
        display_df.round(2),
        use_container_width=True
    )

    # Create financial charts
    st.subheader("Financial Trends")

    chart1, chart2 = st.columns(2)

    with chart1:
        st.write("Annual Revenue")
        st.line_chart(df["Revenue"] / 1e9)

    with chart2:
        st.write("Net Profit Margin")
        st.line_chart(df["Profit Margin"])

    # Generate AI financial analysis
    st.subheader("AI Financial Analysis")

    prompt = f"""
    You are a financial research assistant.

    Analyze {ticker} using these annual financial metrics:

    Fiscal Year: {latest_year}
    Revenue: ${latest["Revenue"]:,.0f}
    Net Income: ${latest["Net Income"]:,.0f}
    Revenue Growth: {latest["Revenue Growth"]:.2f}%
    Net Profit Margin: {latest["Profit Margin"]:.2f}%
    Previous Profit Margin: {previous["Profit Margin"]:.2f}%

    Write a concise professional report containing:

    1. Executive Summary
    2. Revenue Analysis
    3. Profitability Analysis
    4. Potential Risks
    5. Analyst Conclusion

    Use only the supplied figures.
    Do not invent explanations for financial changes.
    Identify questions requiring further investigation.
    """

    with st.spinner("Generating AI financial report..."):
        try:
            client = genai.Client(
                api_key=st.secrets["GEMINI_API_KEY"]
            )

            response = client.models.generate_content(
                model="gemini-3.8-flash",
                contents=prompt
            )

            st.markdown(
                response.text or "No AI report was returned."
            )

        except Exception as e:
            st.warning(
                "The financial analysis loaded, but the AI report "
                f"could not be generated: {e}"
            )
