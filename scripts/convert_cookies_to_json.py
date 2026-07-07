"""
One-time helper: converts your existing screener_cookies.pkl (from the
old Streamlit app) into screener_cookies.json, which is what you'll
paste into Render's Secret Files (they're plaintext-only; a binary
pickle file can't go there directly).

Usage:
    python scripts/convert_cookies_to_json.py /path/to/screener_cookies.pkl

Then open the resulting screener_cookies.json in a text editor, copy
its full contents, and paste them into Render's Secret File named
"screener_cookies.json".
"""
import json
import pickle
import sys
from pathlib import Path


def main():
    if len(sys.argv) != 2:
        print("Usage: python convert_cookies_to_json.py /path/to/screener_cookies.pkl")
        sys.exit(1)

    pkl_path = Path(sys.argv[1])
    if not pkl_path.exists():
        print(f"File not found: {pkl_path}")
        sys.exit(1)

    with open(pkl_path, "rb") as f:
        cookies = pickle.load(f)

    out_path = pkl_path.with_suffix(".json")
    with open(out_path, "w") as f:
        json.dump(cookies, f, indent=2)

    print(f"Wrote {out_path}")
    print("Open that file, copy its full contents, and paste them into")
    print('Render Dashboard -> your service -> Environment -> Secret Files')
    print('-> + Add Secret File -> filename: screener_cookies.json')


if __name__ == "__main__":
    main()
