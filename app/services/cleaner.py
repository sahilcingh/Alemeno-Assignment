import uuid
import pandas as pd
from dateutil import parser as date_parser

# order matters: try the two known formats first, fall back to dateutil for edge cases
DATE_FORMATS = ["%d-%m-%Y", "%Y/%m/%d", "%Y-%m-%d"]


def _parse_date(val) -> str | None:
    if not val or pd.isna(val):
        return None
    s = str(val).strip()
    for fmt in DATE_FORMATS:
        try:
            return pd.to_datetime(s, format=fmt).strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            continue
    # dateutil handles anything left over (e.g. "2024-07-15" ISO format)
    # note: 2024/02/29 is invalid (not a leap year) — dateutil raises, we return None
    try:
        return date_parser.parse(s).strftime("%Y-%m-%d")
    except Exception:
        return None


def _parse_amount(val) -> float | None:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    try:
        return float(str(val).replace("$", "").strip())
    except ValueError:
        return None


def clean_csv(filepath: str) -> pd.DataFrame:
    df = pd.read_csv(filepath, dtype=str)
    df.columns = [c.strip().lower() for c in df.columns]

    df.dropna(how="all", inplace=True)

    df["date"] = df["date"].apply(_parse_date)
    df["amount"] = df["amount"].apply(_parse_amount)

    df["status"] = df["status"].str.upper().str.strip()
    df["currency"] = df["currency"].str.upper().str.strip()

    df["category"] = df["category"].fillna("").str.strip()
    df.loc[df["category"] == "", "category"] = "Uncategorised"

    # blank txn_ids get a short generated id so dedup logic works on them
    def _fix_txn_id(x):
        if pd.isna(x) or str(x).strip() == "":
            return f"GEN-{str(uuid.uuid4())[:8]}"
        return str(x).strip()

    df["txn_id"] = df["txn_id"].apply(_fix_txn_id)

    # replace NaN in text fields with empty string so they serialize cleanly
    df["notes"] = df["notes"].where(pd.notna(df["notes"]), None)
    df["merchant"] = df["merchant"].where(pd.notna(df["merchant"]), None)

    df.drop_duplicates(inplace=True)
    df.reset_index(drop=True, inplace=True)

    return df
