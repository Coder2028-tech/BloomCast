import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from data.nldas import NldasProduct, earthdata_session, download_file


def main():
    timestamp = datetime(2023, 7, 1, 12) 
    product = NldasProduct()

    url = product.url(timestamp)
    out_path = Path("data/nldas_test") / product.file_name(timestamp)

    print(f"Attempting download of a single NLDAS file:")
    print(f"  {url}")
    print(f"  -> {out_path}")
    print()

    try:
        session = earthdata_session()
    except ValueError as e:
        print(f"CREDENTIAL ERROR: {e}")
        print("Make sure you ran the two `export EARTHDATA_...` commands in THIS terminal.")
        return

    try:
        result = download_file(url, out_path, session=session, overwrite=True)
    except Exception as e:
        print(f"DOWNLOAD FAILED: {type(e).__name__}: {e}")
        print()
        print("Common causes:")
        print("  - 'HTML page instead of data' -> GES DISC not authorized on this account")
        print("  - 401/403 -> wrong username/password")
        print("  - connection/timeout -> network issue")
        return

    size_kb = result.stat().st_size / 1024
    print(f"SUCCESS - downloaded {size_kb:.1f} KB to {result}")
    print("Auth + GES DISC access confirmed. Safe to build the full pipeline.")

if __name__ == "__main__":
    main()