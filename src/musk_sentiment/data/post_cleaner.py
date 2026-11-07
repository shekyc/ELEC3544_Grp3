import os
import re
import pandas as pd

def load_musk_tweets_dataset(csv_path: str) -> pd.DataFrame:
    """
    Ingests and cleans the Kaggle 'dadalyndell/elon-musk-tweets-2010-to-2025-march' archive (all_musk_posts.csv).
    Filters out replies and retweets, normalizes timestamps to UTC, strips URLs, and standardizes feature columns.
    """
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Dataset CSV not found at: {csv_path}")

    df = pd.read_csv(csv_path)

    # 1. Fallback mapping for column names (handles dadalyndell & legacy schemas)
    text_col = 'fullText' if 'fullText' in df.columns else ('text' if 'text' in df.columns else df.columns[1])
    date_col = 'createdAt' if 'createdAt' in df.columns else ('date' if 'date' in df.columns else 'created_at')

    # 2. Filter out Retweets using metadata flags
    if 'isRetweet' in df.columns:
        df = df[df['isRetweet'] == False]
    elif 'is_retweet' in df.columns:
        df = df[df['is_retweet'] == False]

    # 3. Filter out Replies using metadata and text patterns
    if 'isReply' in df.columns:
        df = df[df['isReply'] == False]

    df[text_col] = df[text_col].astype(str)
    # Secondary check: strip any remaining posts starting with '@' mentions
    df = df[~df[text_col].str.startswith('@')]

    # 4. Clean text (remove URLs while preserving $TSLA, $DOGE ticker symbols)
    df['clean_text'] = df[text_col].apply(clean_tweet_text)
    df = df[df['clean_text'].str.len() > 0]

    # 5. Normalize timestamps to ISO 8601 UTC
    df['timestamp_utc'] = pd.to_datetime(df[date_col], utc=True)

    # 6. Deduplicate and sort chronologically
    if 'id' in df.columns:
        df = df.drop_duplicates(subset=['id'])
    df = df.drop_duplicates(subset=['clean_text', 'timestamp_utc'])
    df = df.sort_values(by='timestamp_utc').reset_index(drop=True)

    # 7. Standardize column names for downstream NLP and modeling stages
    column_mapping = {
        'id': 'post_id',
        text_col: 'raw_text',
        'likeCount': 'likes',
        'favorites': 'likes',
        'retweetCount': 'retweets',
        'replyCount': 'replies',
        'quoteCount': 'quotes',
        'viewCount': 'views'
    }
    df = df.rename(columns=column_mapping)

    # Output schema for Groupmates 2 and 3
    target_columns = ['timestamp_utc', 'post_id', 'raw_text', 'clean_text', 'likes', 'retweets', 'replies', 'quotes', 'views']
    available_columns = [col for col in target_columns if col in df.columns]

    return df[available_columns]


def clean_tweet_text(text: str) -> str:
    """Removes URLs and normalizes whitespace while preserving stock/crypto ticker symbols ($TSLA, $DOGE)."""
    text = re.sub(r'http\S+|www\.\S+', '', str(text))  # Strip URLs
    text = re.sub(r'\s+', ' ', text).strip()            # Normalize spaces
    return text