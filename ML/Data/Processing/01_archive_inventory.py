
import re
import csv
from datetime import datetime

from paths import REPORTS_DIR, SOURCE_DIR

# ============================================================
# GRIDSENSE
# STAGE 1: CORRECTED ARCHIVE INVENTORY
# ============================================================

# ---------------- PROJECT PATHS ----------------

DATA_ROOT = SOURCE_DIR
REPORT_FOLDER = REPORTS_DIR

REPORT_FOLDER.mkdir(parents=True, exist_ok=True)

OUTPUT_FILE = REPORT_FOLDER / "archive_inventory.csv"

ARCHIVE_EXTENSIONS = {
    ".rar",
    ".zip",
    ".7z"
}

# ---------------- REGULAR EXPRESSIONS ----------------

# Financial year detection
FY_PATTERN = re.compile(
    r"FY[\s_-]*(\d{2})[\s_-]*(\d{2})|"
    r"(20\d{2})[\s_-]*(20\d{2})",
    re.IGNORECASE
)

# Detect actual report week immediately after ABT or ABT-BILL.
# Supports:
# ABT-16
# ABT-BILL-06
# ABT BILL-24
# ABT-BILL 20
# Rev01Abt-05
# Rev01_ABT BILL-23

ABT_WEEK_PATTERN = re.compile(
    r"ABT(?:[\s_-]*BILL)?[\s_-]+(\d{1,2})(?=[\s_.-]|$)",
    re.IGNORECASE
)


# Revised report detection
REVISED_PATTERN = re.compile(
    r"revised|revsd|rvsd|rev[\s_-]?\d",
    re.IGNORECASE
)

# ---------------- HEADER ----------------

print("\n" + "=" * 65)
print("       GRIDSENSE - CORRECTED ARCHIVE INVENTORY")
print("=" * 65)

if not DATA_ROOT.exists():
    raise SystemExit(
        f"\nERROR: Data folder not found:\n{DATA_ROOT}"
    )

print("\nData folder found successfully.")

# ---------------- INVENTORY ----------------

archives = []

for file in DATA_ROOT.rglob("*"):

    if not file.is_file():
        continue

    if file.suffix.lower() not in ARCHIVE_EXTENSIONS:
        continue

    filename = file.name

    # ----------------------------------------
    # FINANCIAL YEAR DETECTION
    # ----------------------------------------

    financial_year = "Unknown"

    for part in file.parts:

        match = FY_PATTERN.search(part)

        if match:

            if match.group(1):

                start = match.group(1)
                end = match.group(2)

                financial_year = (
                    f"20{start}-20{end}"
                )

            else:

                start = match.group(3)
                end = match.group(4)

                financial_year = (
                    f"{start}-{end}"
                )

            break

    # ----------------------------------------
    # ACTUAL WEEK NUMBER DETECTION
    # ----------------------------------------

    week_match = ABT_WEEK_PATTERN.search(filename)

    if week_match:

        week_number = int(week_match.group(1))
        week_status = "IDENTIFIED"

    else:

        week_number = ""
        week_status = "MANUAL_CHECK_REQUIRED"

    # ----------------------------------------
    # REVISED REPORT DETECTION
    # ----------------------------------------

    is_revised = bool(
        REVISED_PATTERN.search(filename)
    )

    # ----------------------------------------
    # FILE INFORMATION
    # ----------------------------------------

    file_size = round(
        file.stat().st_size / (1024 * 1024),
        2
    )

    modified_time = datetime.fromtimestamp(
        file.stat().st_mtime
    ).strftime("%Y-%m-%d %H:%M:%S")

    # ----------------------------------------
    # STORE RECORD
    # ----------------------------------------

    archives.append({

        "filename": filename,

        "financial_year": financial_year,

        "week_number": week_number,

        "week_status": week_status,

        "revised": is_revised,

        "size_mb": file_size,

        "modified_date": modified_time,

        "full_path": str(file)

    })

# ---------------- SORTING ----------------
#
# Sort by financial year and actual ABT week.
# Unknown week numbers are placed at the end.
# Original files are not renamed or moved.

archives.sort(
    key=lambda x: (
        x["financial_year"],
        x["week_number"] if x["week_number"] != "" else 999,
        x["revised"],
        x["filename"].lower()
    )
)

# ---------------- SAVE CSV ----------------

fields = [
    "filename",
    "financial_year",
    "week_number",
    "week_status",
    "revised",
    "size_mb",
    "modified_date",
    "full_path"
]

with open(
    OUTPUT_FILE,
    "w",
    newline="",
    encoding="utf-8-sig"
) as csv_file:

    writer = csv.DictWriter(
        csv_file,
        fieldnames=fields
    )

    writer.writeheader()
    writer.writerows(archives)

# ---------------- SUMMARY ----------------

year_summary = {}

for archive in archives:

    year = archive["financial_year"]

    year_summary[year] = (
        year_summary.get(year, 0) + 1
    )

revised_count = sum(
    1 for archive in archives
    if archive["revised"]
)

unknown_fy_count = sum(
    1 for archive in archives
    if archive["financial_year"] == "Unknown"
)

unidentified_week_count = sum(
    1 for archive in archives
    if archive["week_status"] != "IDENTIFIED"
)

print("\n" + "=" * 65)
print("                 INVENTORY SUMMARY")
print("=" * 65)

print("Total archives          :", len(archives))
print("Revised archives        :", revised_count)
print("Unknown financial years :", unknown_fy_count)
print("Unidentified week numbers:", unidentified_week_count)

print("\nFINANCIAL YEAR BREAKDOWN")
print("-" * 45)

for year, count in sorted(year_summary.items()):

    print(f"{year:<20} : {count}")

print("\nWEEK IDENTIFICATION")
print("-" * 45)

identified_count = (
    len(archives) - unidentified_week_count
)

print("Identified weeks        :", identified_count)
print("Need manual inspection  :", unidentified_week_count)

print("\nREPORT LOCATION")
print("-" * 45)

print(OUTPUT_FILE)

print("\n" + "=" * 65)
print("       STAGE 1 COMPLETED")
print("=" * 65)
