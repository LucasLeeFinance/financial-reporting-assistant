
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
        historical.index = historical.index.strftime("%Y-%m-%d")
        historical["Revenue"] /= 1e9
        historical["Net Income"] /= 1e9

        financial_summary = historical.round(2).to_string()

        prompt = f"""
        You are writing a financial research report for an
        audience of finance professionals.

        Company ticker: {active_ticker}

        Annual financial data from a third-party data provider:
        {financial_summary}

        IMPORTANT DATA RULES:
        - Treat the figures as provider-supplied data that
          has not yet been verified against company filings.
        - Do not label any period as projected or forecasted
          unless it is explicitly identified as such.
        - Do not assume a period is audited or final.
        - Do not invent causes, business events, or segment data.
        - Clearly distinguish calculations, observations,
          and possible explanations.
        - Do not claim to have reviewed filings or other
          documents that were not provided.

        Write a financial analysis of approximately 700-900
        words, but prioritize substance over length.

        STRUCTURE:

        1. Executive Summary
           Summarize the two or three most meaningful findings.

        2. Revenue Performance
           Examine growth rates, changes in growth,
           and absolute revenue movements.

        3. Profitability Analysis
           Examine net income, net profit margins,
           and how earnings changed relative to revenue.

        4. Financial Strengths and Concerns
           Identify specific trends supported by the figures.
           Explain why they matter to an analyst.

        5. Questions for Further Investigation
           Identify missing financial or operational
           information needed to explain the trends.

        6. Analyst Conclusion
           Provide a balanced assessment without
           making an investment recommendation.

        WRITING STYLE:
        - Write naturally, like a thoughtful financial analyst.
        - Use clear paragraphs and concise headings.
        - Explain the significance of financial changes.
        - Avoid repeating numbers without adding interpretation.
        - Avoid promotional language and corporate buzzwords.
        - Do not use phrases such as "robust performance",
          "substantial upward inflection", "dynamic landscape",
          or "testament to".
        - Do not add filler to reach the word target.
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
                        temperature=0.3,
                        max_output_tokens=1600
                    )
                )

                st.session_state.report = (
                    response.text or "No report was returned."
                )

            except Exception as e:
                st.error(f"AI report unavailable: {e}")

    if "report" in st.session_state:
        st.markdown(st.session_state.report)
