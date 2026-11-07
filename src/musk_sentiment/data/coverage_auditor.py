import os
import re
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timezone

def generate_coverage_report(posts_df: pd.DataFrame, market_df: pd.DataFrame):
    
    print("--- POST DATASET COVERAGE ---")
    print(f"Total Cleaned Original Posts: {len(posts_df)}")
    print(f"Post Date Range: {posts_df['timestamp_utc'].min()} to {posts_df['timestamp_utc'].max()}")
    print(f"Missing Text Entries: {posts_df['clean_text'].isnull().sum()}")
    
    print("\n--- MARKET DATASET COVERAGE ---")
    for ticker in market_df['ticker'].unique():
        sub = market_df[market_df['ticker'] == ticker]
        print(f"Ticker: {ticker:10s} | Rows: {len(sub)} | Start: {sub['timestamp_utc'].min().date()} | End: {sub['timestamp_utc'].max().date()} | Missing Closes: {sub['Close'].isnull().sum()}")