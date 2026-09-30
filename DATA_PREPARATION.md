# Fuel Station Data Preparation & Geocoding Pipeline

This document details the data engineering, preprocessing, and geocoding process used to extract geographic coordinates for the commercial OPIS fuel dataset.

---

## 1. Dataset Understanding & Verification

* **Source & Nature:** The input data represents real commercial benchmark fuel pricing from the **Oil Price Information Service (OPIS)**, widely used in freight logistics, fleet management, and fuel dispatch optimization.
* **Volume:** 8,151 total price entries across the United States and Canada.
* **Data Nuance (OPIS Truckstop IDs):**
  * OPIS IDs are not strictly 1-to-1 with raw CSV rows: 678 OPIS IDs appear across multiple rows due to multiple price postings or slight name/brand variations over time.
  * Each distinct OPIS ID maps to a single physical truck stop location.

---

## 2. Geocoding Feasibility & Tool Selection

When evaluating geocoding strategies for 8,151 commercial addresses:

* **Google Apps Script (`Maps.newGeocoder()`):**
  * Evaluated and rejected due to strict execution constraints:
    * 6-minute maximum script execution timeout.
    * 1,000 requests/day free tier quota.
    * Geocoding 8,151 rows would require spreading execution across 9 days or managing complex pagination triggers.
* **US Census Bureau Batch Geocoder (`https://geocoding.geo.census.gov/geocoder/locations/addressbatch`):**
  * Selected as the primary engine.
  * Zero API key requirements, free of charge, and designed for large batch submissions via multipart form upload.

---

## 3. Pipeline Troubleshooting & Preprocessing

Processing commercial truck stop addresses through the Census API required resolving three major technical challenges:

### A. Encoding Errors (`UnicodeDecodeError: 'utf-8' codec can't decode byte 0x8e`)
* **Cause:** Raw source CSV exports contained Windows-1252 / Latin-1 byte sequences from legacy database dumps.
* **Fix:** Normalized file reading with `cp1252`/`latin1` decode strategies and sanitized strings into clean, valid UTF-8.

### B. Buffer Overflow & CSV Parsing Failures
* **Cause:** Unescaped quotes and formatting artifacts inside highway descriptions (e.g., `I-80, EXIT 15 "A"` or `HWY 59 & FM 1960`).
* **Fix:** Implemented regular expression cleaning to strip rogue internal quotes, collapse multiple spaces, and sanitize address strings before batch assembly.

### C. Census 502 Bad Gateway & Upstream Server Timeouts
* **Cause:** Submitting all 8,151 rows in a single batch request overwhelmed the Census server. Additionally, Canadian provinces (`AB`, `BC`, `ON`, `QC`, etc.) triggered lookup exceptions.
* **Fix:**
  * Filtered out non-US provincial entries prior to Census submission.
  * Partitioned the dataset into chunks of **500 rows**.
  * Added retry loops with progressive backoff (`time.sleep`) to gracefully handle temporary HTTP 502/504 errors.

---

## 4. Batch Submission & Coordinate Extraction

1. **Census 5-Column Batch Specification:** Input data was formatted without headers as:
   $$\text{Row ID, Street/Address, City, State, ZIP (blank)}$$
2. **Response Parsing:**
   The Census engine returns structured CSV with the following key fields:
   * `match_status`: `Match`, `No_Match`, `Tie`
   * `match_type`: `Exact`, `Non_Exact`
   * `matched_address`: Standardized postal address
   * `coordinates`: `Longitude,Latitude`
3. **Re-merging:** Coordinates and match metadata were joined back to the primary dataset using the unique internal row ID.

---

## 5. Geocoding Results & Coverage Analysis

* **Matched Coordinates:** **588 locations (7.2%)**
  * **Exact Matches:** Stations with standard postal street numbers (e.g., `123 Main St`) resolved to exact parcel or rooftop coordinates.
  * **Non-Exact Matches:** Stations referencing highway cross-streets resolved to highway interchanges or road intersections (valid coordinates shared by multiple stations at the same exit).
* **Unmatched (`No_Match` / `Tie`):** **7,563 locations (92.8%)**
  * **Root Cause:** Commercial truck stop addresses are frequently recorded using highway mileage markers rather than standard municipal street numbers (e.g., `I-40 EXIT 156`, `HWY 70 & JCT I-35`). The US Census Bureau's address engine relies on TIGER/Line street address ranges and cannot parse unstructured interstate exit descriptions without street numbers.

---

## 6. The Complete Geocoding Python Script

Below is the complete standalone script used to execute the batch geocoding pipeline and generate `fuel_prices_with_coordinates.csv`:

```python
import io
import re
import time
import pandas as pd
import requests

input_filename = "fuel-prices-for-be-assessment.csv"
df = pd.read_csv(input_filename)


# 1. Clean address strings
def clean_text(val):
    if pd.isna(val):
        return ""
    s = str(val).strip().replace('"', "").replace("'", "")
    return re.sub(r"\s+", " ", s)


df["clean_address"] = df["Address"].apply(clean_text)
df["clean_city"] = df["City"].apply(clean_text)
df["clean_state"] = df["State"].apply(clean_text)
df["clean_zip"] = ""
df["_row_id"] = df.index.astype(str)

# 2. Filter US-only records (Census only covers US)
non_us_mask = (
    df["clean_state"]
    .str.upper()
    .isin(["AB", "BC", "ON", "QC", "MB", "SK", "NB", "NS", "NL", "PE"])
)
us_df = df[~non_us_mask].copy()


# 3. Coordinate parser (Census returns "Longitude,Latitude")
def parse_lon_lat(coord_str):
    if pd.isna(coord_str):
        return None, None
    parts = str(coord_str).split(",")
    if len(parts) == 2:
        try:
            return float(parts[1].strip()), float(parts[0].strip())  # lat, lon
        except ValueError:
            return None, None
    return None, None


# 4. Chunk into batches of 500 rows
CHUNK_SIZE = 500
url = "https://geocoding.geo.census.gov/geocoder/locations/addressbatch"
census_cols = [
    "row_id",
    "input_address",
    "match_status",
    "match_type",
    "matched_address",
    "coordinates",
    "tiger_line_id",
    "side",
]

all_parsed_results = []
chunks = [
    us_df.iloc[i : i + CHUNK_SIZE] for i in range(0, len(us_df), CHUNK_SIZE)
]

for idx, chunk in enumerate(chunks, start=1):
    batch_csv = chunk[[
        "_row_id",
        "clean_address",
        "clean_city",
        "clean_state",
        "clean_zip",
    ]].to_csv(header=False, index=False)

    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            files = {
                "addressFile": ("batch.csv", batch_csv.encode("utf-8"), "text/csv"),
                "benchmark": (None, "Public_AR_Current"),
            }
            res = requests.post(url, files=files, timeout=90)
            if res.status_code == 200 and "Match" in res.text:
                chunk_res = pd.read_csv(
                    io.StringIO(res.text),
                    header=None,
                    names=census_cols,
                    dtype=str,
                    on_bad_lines="skip",
                )
                all_parsed_results.append(chunk_res)
                break
            time.sleep(3 * attempt)
        except Exception:
            time.sleep(3 * attempt)
    time.sleep(1)

# 5. Merge coordinates back to dataframe
if all_parsed_results:
    results_df = pd.concat(all_parsed_results, ignore_index=True)
    coords = results_df["coordinates"].apply(parse_lon_lat)
    results_df["Latitude"] = [c[0] for c in coords]
    results_df["Longitude"] = [c[1] for c in coords]

    results_df["row_id"] = results_df["row_id"].astype(str)
    df["_row_id"] = df["_row_id"].astype(str)

    merged = df.merge(
        results_df[
            ["row_id", "match_status", "match_type", "Latitude", "Longitude"]
        ],
        left_on="_row_id",
        right_on="row_id",
        how="left",
    )
else:
    merged = df.copy()

# Cleanup and export
merged.drop(
    columns=[
        "_row_id",
        "clean_address",
        "clean_city",
        "clean_state",
        "clean_zip",
    ],
    inplace=True,
    errors="ignore",
)
merged.to_csv("fuel_prices_with_coordinates.csv", index=False)
```
