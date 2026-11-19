
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
    "Financial data from Yahoo Finance via yfinance. "
    "Verify important figures against company filings. "
    "For educational and research purposes only."
)


@st.cache_data(ttl=3600)
def get_financial_data(ticker):
    financials = yf.Ticker(ticker).income_stmt

    if financials.empty:
        raise ValueError("No financial statements found.")

    required = ["Total Revenue", "Net Income"]

    for item in required:
        if item not in financials.index:
            raise ValueError(f"Missing financial item: {item}")

    df = pd.DataFrame({
        "Revenue": financials.loc["Total Revenue"],
        "Net Income": financials.loc["Net Income"]
    })

    df.index = pd.to_datetime(df.index)
    df = df.sort_index()
    df = df.dropna(subset=["Revenue", "Net Income"])

    if len(df) < 2:
        raise ValueError("At least two years of data are required.")

    df["Profit Margin"] = df["Net Income"] / df["Revenue"] * 100
    df["Revenue Growth"] = df["Revenue"].pct_change() * 100

    return df


ticker = st.text_input("Stock Ticker", value="AAPL").strip().upper()

if st.button("Analyze Company", type="primary"):
    st.session_state.pop("report", None)
    st.session_state.pop("df", None)
    st.session_state.pop("analyzed_ticker", None)

    with st.spinner("Loading financial data..."):
        try:
            st.session_state.df = get_financial_data(ticker)
            st.session_state.analyzed_ticker = ticker
        except Exception as e:
            st.error(f"Unable to analyze company: {e}")

if "df" in st.session_state:
    df = st.session_state.df
    active_ticker = st.session_state.analyzed_ticker

    latest = df.iloc[-1]
    previous = df.iloc[-2]
    latest_year = df.index[-1].year

    st.subheader(f"{active_ticker} — Fiscal {latest_year}")

    col1, col2, col3 = st.columns(3)

    col1.metric("Revenue", f"${latest['Revenue']/1e9:,.2f}B")
    col2.metric("Revenue Growth", f"{latest['Revenue Growth']:.2f}%")
    col3.metric("Net Profit Margin", f"{latest['Profit Margin']:.2f}%")

    display_df = df.copy()
    display_df.index = display_df.index.year
    display_df.index.name = "Fiscal Year"
    display_df["Revenue"] /= 1e9
    display_df["Net Income"] /= 1e9

    st.subheader("Financial Performance")
    st.dataframe(display_df.round(2), use_container_width=True)

    st.subheader("Financial Trends")

    left, right = st.columns(2)

    with left:
        st.write("Annual Revenue (USD billions)")
        st.line_chart(df["Revenue"] / 1e9)

    with right:
        st.write("Net Profit Margin (%)")
        st.line_chart(df["Profit Margin"])

    st.subheader("Financial Analyst Report")

    if st.button("Generate AI Report"):
        historical = df.copy()
        historical.index = historical.index.year
        historical["Revenue"] /= 1e9
        historical["Net Income"] /= 1e9

        financial_summary = historical.round(2).to_string()

        prompt = f"""
        Prepare an independent financial analyst report
        for {active_ticker}.

        Historical annual financial data:
        {financial_summary}

        Include:
        1. Executive Summary
        2. Revenue Trends
        3. Profitability Analysis
        4. Financial Strengths and Concerns
        5. Areas for Further Investigation
        6. Analyst Conclusion

        Reference specific figures and fiscal years.
        Identify acceleration or deceleration in growth.
        Compare revenue growth with profitability changes.

        Write naturally and professionally.
        Avoid generic praise, buzzwords, and repetitive language.
        Do not invent explanations for financial changes.
        Distinguish evidence from hypotheses.
        Do not make stock recommendations.
        """

        with st.spinner("Generating report (up to 60 seconds)..."):
            try:
                client = genai.Client(
                    api_key=st.secrets["GEMINI_API_KEY"],
                    http_options=types.HttpOptions(
                        timeout=60000
                    )
                )

                response = client.models.generate_content(
                    
model="gemini-3.5-flash-lite",

                    contents=prompt
                )

                st.session_state.report = (
                    response.text or "No report was returned."
                )

            except Exception as e:
                st.error(f"AI report unavailable: {e}")

    if "report" in st.session_state:
        st.markdown(st.session_state.report)
