import os
import json
import base64
from pathlib import Path
from typing import Optional

import requests


BASE_URL = "https://api.einvoice.fpt.com.vn/search-icr"

# TODO: sửa 2 giá trị này theo request của bạn
STAX = "xxx"
SERIAL = "xxx"

# Cách an toàn: để credentials qua biến môi trường
# Windows (PowerShell):
#   setx FPT_EINV_USER "your_user"
#   setx FPT_EINV_PASS "your_pass"
# macOS/Linux:
#   export FPT_EINV_USER="your_user"
#   export FPT_EINV_PASS="your_pass"
USERNAME = "xxx"
PASSWORD = "xxx"

SEC_FILE = Path(__file__).with_name("sec.txt")
OUT_DIR = Path(__file__).with_name("pdf")


def ensure_creds():
    if not USERNAME or not PASSWORD:
        raise SystemExit(
            "Thiếu credentials. Hãy set FPT_EINV_USER và FPT_EINV_PASS trong biến môi trường "
            "hoặc điền trực tiếp USERNAME/PASSWORD trong code."
        )


def read_secs(path: Path) -> list[str]:
    if not path.exists():
        raise SystemExit(f"Không thấy file: {path}")
    secs: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s and not s.startswith("#"):
            secs.append(s)
    if not secs:
        raise SystemExit("sec.txt rỗng (hoặc toàn comment).")
    return secs


def extract_pdf_bytes(resp: requests.Response) -> Optional[bytes]:
    # 1) Nếu trả thẳng PDF
    ct = (resp.headers.get("Content-Type") or "").lower()
    content = resp.content or b""

    if "application/pdf" in ct or content.startswith(b"%PDF"):
        return content

    # 2) Nếu trả JSON có base64
    try:
        data = resp.json()
    except Exception:
        return None

    # data có thể là list[{"pdf": "..."}] hoặc {"pdf": "..."}
    pdf_field = None
    if isinstance(data, list) and data and isinstance(data[0], dict):
        pdf_field = data[0].get("pdf")
    elif isinstance(data, dict):
        pdf_field = data.get("pdf")

    if not pdf_field or not isinstance(pdf_field, str):
        return None

    b64 = pdf_field.replace("data:application/pdf;base64,", "").strip()
    try:
        return base64.b64decode(b64, validate=True)
    except Exception:
        # một số server không chuẩn base64 validate
        return base64.b64decode(b64)


def download_one(sec: str) -> Path:
    params = {
        "stax": STAX,
        "serial": SERIAL,
        "sec": sec,
        "type": "pdf",
    }

    r = requests.get(
        BASE_URL,
        params=params,
        auth=(USERNAME, PASSWORD),  # Basic Auth
        timeout=60,
    )

    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:500]}")

    pdf_bytes = extract_pdf_bytes(r)
    if not pdf_bytes:
        # In ra 1 đoạn để debug
        snippet = r.text[:500] if r.text else str(r.content[:200])
        raise RuntimeError(f"Không parse được PDF từ response. Snippet: {snippet}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"{sec}.pdf"
    out_path.write_bytes(pdf_bytes)
    return out_path


def main():
    ensure_creds()
    secs = read_secs(SEC_FILE)

    ok = 0
    fail = 0

    for sec in secs:
        try:
            p = download_one(sec)
            print(f"[OK] {sec} -> {p}")
            ok += 1
        except Exception as e:
            print(f"[FAIL] {sec}: {e}")
            fail += 1

    print(f"\nDone. OK={ok}, FAIL={fail}")


if __name__ == "__main__":
    main()
