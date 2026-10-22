"""Step 1: download the real UCI Online Retail dataset (541,909 rows) and validate it."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from retailpulse.data import download

if __name__ == "__main__":
    download(ROOT / "data" / "raw" / "online_retail.csv")
