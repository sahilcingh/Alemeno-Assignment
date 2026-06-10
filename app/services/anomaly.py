import pandas as pd

# these merchants only operate domestically in India,
# so any transaction in USD is almost certainly a data error or fraud
DOMESTIC_ONLY = {"swiggy", "ola", "irctc", "zomato", "bookmyshow", "jio recharge", "hdfc atm"}


def detect_anomalies(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["is_anomaly"] = False
    df["anomaly_reason"] = ""

    # flag statistical outliers: amount > 3x the account's median spend
    medians = df.groupby("account_id")["amount"].median()

    for idx, row in df.iterrows():
        acct_median = medians.get(row["account_id"])
        if acct_median and acct_median > 0 and row["amount"]:
            if float(row["amount"]) > 3 * float(acct_median):
                df.at[idx, "is_anomaly"] = True
                df.at[idx, "anomaly_reason"] = "statistical_outlier"

    # flag USD charges on domestic-only merchants
    for idx, row in df.iterrows():
        if str(row.get("currency", "")).upper() == "USD":
            merchant = str(row.get("merchant", "")).lower().strip()
            if merchant in DOMESTIC_ONLY:
                existing = df.at[idx, "anomaly_reason"]
                df.at[idx, "is_anomaly"] = True
                df.at[idx, "anomaly_reason"] = (
                    f"{existing}; currency_mismatch" if existing else "currency_mismatch"
                )

    return df
