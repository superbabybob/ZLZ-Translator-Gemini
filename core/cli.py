"""ใช้ทดสอบจาก command line

    python -m core.cli read "Could you send the files by Friday?"
    python -m core.cli reply "เดี๋ยวส่งให้พรุ่งนี้เช้าครับ" --tone formal
    python -m core.cli explain "..."  --provider gemini
    python -m core.cli status
"""
from __future__ import annotations

import argparse
import logging
import sys

from core.config import MODES, TONES, load_config
from core.providers import PROVIDERS, ProviderError
from core.translator import Translator


def _status(translator: Translator) -> int:
    cfg = translator.config
    print(f"โฟลเดอร์โปรเจกต์ : {cfg.root}")
    print(f"ลำดับผู้ให้บริการ : {' -> '.join(cfg.provider_order)}")
    print(f"น้ำเสียงเริ่มต้น  : {cfg.default_tone}")
    print("ผู้ให้บริการ:")
    for name, cls in PROVIDERS.items():
        prov = cls(cfg)
        ready = "พร้อม" if prov.available() else "ยังไม่พร้อม (ขาด GEMINI_API_KEY ใน .env)"
        detail = f"model={prov.model}" if hasattr(prov, "model") else ""
        print(f"  - {name:12s} {ready:15s} {detail}")
    used = translator.usage.today()
    print(f"ใช้งานวันนี้: {used if used else 'ยังไม่มี'}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="translator", description="เครื่องมือแปลสำหรับคุยกับลูกค้า")
    parser.add_argument("mode", choices=[*MODES, "status"])
    parser.add_argument("text", nargs="?", help="ข้อความ (ถ้าไม่ใส่จะอ่านจาก stdin)")
    parser.add_argument("--tone", choices=TONES)
    parser.add_argument("--provider", choices=list(PROVIDERS))
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.WARNING, format="%(levelname)s %(message)s")

    try:
        translator = Translator(load_config())
    except FileNotFoundError as e:
        print(e, file=sys.stderr)
        return 2

    if args.mode == "status":
        return _status(translator)

    text = args.text if args.text is not None else sys.stdin.read()
    try:
        result = translator.run(args.mode, text, tone=args.tone, provider=args.provider)
    except (ProviderError, ValueError) as e:
        print(f"ผิดพลาด: {e}", file=sys.stderr)
        return 1

    print(result.text)
    note = f"[{result.provider} / {result.model} / {result.seconds:.1f}s"
    if result.fallback_used:
        note += " / ใช้ตัวสำรอง"
    print(note + "]", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
