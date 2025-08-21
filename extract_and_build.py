#!/usr/bin/env python3
import os
import json
import re
import argparse
import requests
from lxml import html

WIKI_URL_DEFAULT = "https://en.wikipedia.org/wiki/List_of_FIFA_World_Cup_finals"
RANGE_DEFAULT = "Sheet1!A:D"  # quote in shell when passing on CLI

# ---- XPaths (Step-Library aligned) ----
TABLE_XPATH = (
    "//table[contains(@class,'wikitable')]"
    "[.//caption[contains(.,'List of FIFA World Cup finals')]]"
)
# First 10 data rows (skip header):
ROWS_1_TO_10_XPATH = f"({TABLE_XPATH}/tbody/tr)[position()>1 and position()<=11]"

# Row-relative XPaths (corrected indices)
YEAR_REL_XPATH      = "./*[self::th or self::td][1]"
WINNER_REL_XPATH    = "./td[1]"
SCORE_REL_XPATH     = "./td[2]"
RUNNERSUP_REL_XPATH = "./td[3]"

def clean_text(txt: str) -> str:
    """Remove [1]-style refs, NBSP, collapse spaces, trim."""
    if txt is None:
        return ""
    txt = re.sub(r"\[\s*[^]]+\]", "", txt)
    txt = txt.replace("\u00A0", " ")
    txt = re.sub(r"\s+", " ", txt)
    return txt.strip()

def join_and_clean(nodes) -> str:
    return clean_text("".join(nodes)) if nodes else ""

def scrape_first10(url: str):
    """Return values array: header + 10 rows."""
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    doc = html.fromstring(resp.content)

    rows = doc.xpath(ROWS_1_TO_10_XPATH)
    if not rows:
        raise RuntimeError("Could not locate finals table rows with XPath. Page structure may have changed.")

    values = [["year", "winner", "score", "runners_up"]]
    for tr in rows:
        year      = join_and_clean(tr.xpath(YEAR_REL_XPATH + "//text()"))
        winner    = join_and_clean(tr.xpath(WINNER_REL_XPATH + "//text()"))
        score     = join_and_clean(tr.xpath(SCORE_REL_XPATH + "//text()"))
        runnersup = join_and_clean(tr.xpath(RUNNERSUP_REL_XPATH + "//text()"))

        # optional sanity hint
        if not re.search(r"\d+\s*[–-]\s*\d+", score):
            print(f"Warn: score looks odd for year {year!r}: {score!r}")

        values.append([year, winner, score, runnersup])
    return values

def main():
    ap = argparse.ArgumentParser(description="Extract first 10 FIFA finals rows and build JSON for Postman append.")
    ap.add_argument("--url", default=WIKI_URL_DEFAULT, help="Wikipedia URL")
    ap.add_argument("--range", default=os.getenv("SHEET_RANGE", RANGE_DEFAULT), help="Target range, e.g. 'Sheet1!A:D'")
    ap.add_argument("--values-out", default=os.path.join("data", "values.json"), help="Path to write values.json")
    ap.add_argument("--body-out", default=os.path.join("data", "append_body.json"), help="Path to write append_body.json")
    args = ap.parse_args()

    # 1) Scrape
    values = scrape_first10(args.url)

    # 2) Write files for Postman
    os.makedirs("data", exist_ok=True)
    with open(args.values_out, "w", encoding="utf-8") as f:
        json.dump(values, f, ensure_ascii=False, indent=2)
    with open(args.body_out, "w", encoding="utf-8") as f:
        json.dump({"range": args.range, "majorDimension": "ROWS", "values": values}, f, ensure_ascii=False, indent=2)

    # 3) Print clear Postman instructions
    print("\n✅ Generated:")
    print(f"  • {args.values_out}")
    print(f"  • {args.body_out}")
    print("\nNext Step in Postman (Append to Google Sheets):")
    print("1) Method: POST")
    print("2) URL: https://sheets.googleapis.com/v4/spreadsheets/{SPREADSHEET_ID}/values/{RANGE}:append?valueInputOption=USER_ENTERED&insertDataOption=INSERT_ROWS")
    print("   - Replace {SPREADSHEET_ID} with your sheet ID")
    print("   - Replace {RANGE} with the range you used (e.g., Sheet1!A:D)")
    print("3) Headers:")
    print("   Authorization: Bearer <YOUR_OAUTH2_ACCESS_TOKEN>")
    print("   Content-Type: application/json")
    print("4) Body → raw → JSON: paste the entire contents of append_body.json")

if __name__ == "__main__":
    main()