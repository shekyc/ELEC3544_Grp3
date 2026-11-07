from datetime import datetime, timezone
import os
import numpy as np
import pandas as pd
import yfinance as yf


def fetch_and_process_market_data(
    tickers: list[str],
    start_date: str,
    end_date: str,
    interval: str = '1d',
    output_dir: str = 'data/raw' ,
) -> pd.DataFrame:
    """Downloads historical OHLCV data for multiple assets using yfinance,

    calculates log returns and USD trading volume, and saves raw CSV files.

    Parameters:
    - tickers: List of Yahoo Finance ticker symbols (e.g., ['TSLA', 'DOGE-USD',
    'SPY'])
    - start_date: 'YYYY-MM-DD'
    - end_date: 'YYYY-MM-DD'
    - interval: '1d' for daily, '1h' for hourly
    - output_dir: Directory where the CSVs will be stored
    """
    os.makedirs(output_dir, exist_ok=True)
    all_series = []

    print(
        f'--- Starting market data fetch ({start_date} to {end_date},'
        f' interval={interval}) ---'
    )

    for ticker in tickers:
        print(f'Fetching data for: {ticker}...')

        # 1. Fetch raw data from Yahoo Finance
        df = yf.download(
            tickers=ticker,
            start=start_date,
            end=end_date,
            interval=interval,
            progress=False,
            auto_adjust=True,  # Adjusts Open/High/Low/Close for stock splits & dividends
        )

        if df.empty:
            print(f'⚠️ Warning: No data returned for {ticker}.')
            continue

        # Flatten MultiIndex columns if returned by yfinance
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        df = df.reset_index()

        # 2. Standardize Timestamp column to UTC
        date_col = 'Datetime' if 'Datetime' in df.columns else 'Date'
        df['timestamp_utc'] = pd.to_datetime(df[date_col], utc=True)

        # 3. Add Ticker Symbol Identifier
        df['ticker'] = ticker

        # 4. Calculate Log Returns and Dollar Trading Volume
        # Log return: ln(P_t / P_{t-1})
        df['log_return'] = np.log(df['Close'] / df['Close'].shift(1))
        df['volume_usd'] = df['Volume'] * df['Close']

        # 5. Select and reorder relevant features
        columns_to_keep = [
            'timestamp_utc',
            'ticker',
            'Open',
            'High',
            'Low',
            'Close',
            'Volume',
            'log_return',
            'volume_usd',
        ]
        df_clean = df[columns_to_keep].copy()

        # Save individual raw CSV in data/raw/
        safe_ticker_name = ticker.replace('^', '').replace('=', '_')
        file_path = os.path.join(
            output_dir, f'market_{safe_ticker_name}_{interval}.csv'
        )
        df_clean.to_csv(file_path, index=False)
        print(f'  Saved {len(df_clean)} rows -> {file_path}')

        all_series.append(df_clean)

    # Combine all assets into a single DataFrame
    combined_df = pd.concat(all_series, ignore_index=True)
    return combined_df

if __name__ == '__main__':
    # Assets agreed upon in your research proposal
    asset_universe = ['TSLA', 'DOGE-USD', 'BTC-USD', 'SPY', 'RIVN']

    # 1. Daily Data Download (Long Horizon: 2021 to Present)
    daily_data = fetch_and_process_market_data(
        tickers=asset_universe,
        start_date='2020-06-05',
        end_date='2025-04-14',
        interval='1d',
        output_dir='data/raw',
    )