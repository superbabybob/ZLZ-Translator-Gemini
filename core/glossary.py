"""การจัดการคลังศัพท์ (Glossary) และการสรุปย่อแบบกระชับ (Compact Glossary) เพื่อลด Input Tokens

ระบบจะตรวจจับการเปลี่ยนแปลงของ glossary.md ผ่าน SHA256 อัตโนมัติ
เมื่อมีการแก้ไข จะสร้างและบันทึกไฟล์สรุปย่อไว้ที่ data/glossary_compact.txt
โดยไม่แก้ไขหรือแตะต้องไฟล์ glossary.md ต้นฉบับ
"""
from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path

log = logging.getLogger("glossary")

# ข้อความหรือประโยคคำแนะนำในไฟล์ตัวอย่างที่ไม่จำเป็นต้องส่งไปให้ AI
_BOILERPLATE_PATTERNS = [
    r"this file is automatically attached",
    r"feel free to customize",
    r"lines starting with `#`",
    r"lines starting with #",
    r"the more detailed your context",
]


def compact_glossary_text(raw_text: str) -> str:
    """แปลงเนื้อหา glossary.md ให้กระชับ สั้น และประหยัด token ที่สุด

    - ลบคำแนะนำเบื้องต้นและคอมเมนต์ตกแต่ง
    - รวบคำศัพท์ที่ไม่ต้องแปล (Keep Untranslated) ให้เป็นบรรทัดเดียว
    - รวบชื่อเฉพาะ (Proper Nouns) และกฎน้ำเสียง (Guidelines) ให้เหลือเฉพาะสาระสำคัญ
    - ลบบรรทัดว่างซ้ำซ้อน
    """
    if not raw_text or not raw_text.strip():
        return ""

    lines = raw_text.splitlines()
    sections: list[tuple[str, list[str]]] = []
    current_sec = "General"
    current_lines: list[str] = []

    for line in lines:
        s = line.strip()
        if not s:
            continue

        # ตรวจสอบว่าเป็นคำแนะนำ boilerplate หรือไม่
        s_lower = s.lower()
        if any(re.search(pat, s_lower) for pat in _BOILERPLATE_PATTERNS):
            continue

        # ตรวจสอบหัวข้อหลัก # (ข้ามหัวข้อใหญ่สุด เช่น # Glossary and Project Context)
        if s.startswith("# ") and not s.startswith("## "):
            continue

        # ตรวจสอบหัวข้อย่อย ## หรือ ###
        if s.startswith("## ") or s.startswith("### "):
            if current_lines:
                sections.append((current_sec, current_lines))
                current_lines = []
            current_sec = s.lstrip("#").strip()
            continue

        current_lines.append(s)

    if current_lines:
        sections.append((current_sec, current_lines))

    result_blocks: list[str] = []

    for sec_name, sec_items in sections:
        sec_lower = sec_name.lower()

        # 1. หมวดคำศัพท์ที่ห้ามแปล (Terms to Keep Untranslated)
        if any(k in sec_lower for k in ["keep untranslated", "untranslated", "keep in english", "technical terms"]):
            raw_joined = " ".join(sec_items)
            terms = [t.strip().rstrip(",") for t in re.split(r"[,\n]+", raw_joined) if t.strip()]
            seen = set()
            unique_terms: list[str] = []
            for t in terms:
                if t and t.lower() not in seen:
                    seen.add(t.lower())
                    unique_terms.append(t)
            if unique_terms:
                result_blocks.append(f"Keep English: {', '.join(unique_terms)}")

        # 2. หมวดชื่อเฉพาะ / สินค้า (Proper Nouns & Product Names)
        elif any(k in sec_lower for k in ["proper noun", "product name", "project name"]):
            nouns = []
            for item in sec_items:
                clean = item.lstrip("-*• ").strip()
                if clean:
                    nouns.append(clean)
            if nouns:
                result_blocks.append("Proper Nouns:\n" + "\n".join(f"- {n}" for n in nouns))

        # 3. หมวดบริบทส่วนตัว / ข้อมูลเบื้องต้น (About Me / Context)
        elif any(k in sec_lower for k in ["about me", "context", "profile", "role"]):
            ctx = []
            for item in sec_items:
                clean = item.lstrip("-*• ").strip()
                if clean:
                    ctx.append(clean)
            if ctx:
                result_blocks.append("Context: " + "; ".join(ctx))

        # 4. หมวดข้อตกลงภาษา / น้ำเสียง (Tone & Guidelines)
        elif any(k in sec_lower for k in ["tone", "guideline", "rule", "instruction"]):
            rules = []
            for item in sec_items:
                clean = item.lstrip("-*• ").strip()
                if clean:
                    rules.append(clean)
            if rules:
                result_blocks.append("Guidelines:\n" + "\n".join(f"- {r}" for r in rules))

        # 5. หมวดอื่นๆ ที่ผู้ใช้สร้างเอง
        else:
            other_lines = []
            for item in sec_items:
                clean = item.lstrip("-*• ").strip()
                if clean:
                    other_lines.append(clean)
            if other_lines:
                result_blocks.append(f"{sec_name}:\n" + "\n".join(f"- {o}" for o in other_lines))

    return "\n\n".join(result_blocks).strip()


def get_compact_glossary(root: Path, raw_glossary: str | None = None) -> str:
    """คืนค่า Compact Glossary ที่ถูกสรุปย่อแล้ว โดยตรวจสอบการเปลี่ยนแปลงของ glossary.md อัตโนมัติ

    - หาก glossary.md มีการแก้ไข จะคำนวณสรุปย่อใหม่และบันทึกลง data/glossary_compact.txt
    - หากไม่มีการแก้ไข จะอ่านจากแคช data/glossary_compact.txt ทันที
    - ไม่มีการแก้ไขไฟล์ glossary.md ต้นฉบับใดๆ ทั้งสิ้น
    """
    glossary_path = root / "glossary.md"
    data_dir = root / "data"
    data_dir.mkdir(exist_ok=True)

    cache_file = data_dir / "glossary_compact.txt"
    hash_file = data_dir / "glossary.sha256"

    # หาเนื้อหาดิบของ glossary.md
    if raw_glossary is None:
        if glossary_path.exists():
            try:
                raw_glossary = glossary_path.read_text(encoding="utf-8")
            except Exception as e:
                log.warning("อ่าน glossary.md ไม่สำเร็จ: %s", e)
                raw_glossary = ""
        else:
            raw_glossary = ""

    current_hash = hashlib.sha256(raw_glossary.encode("utf-8")).hexdigest()

    # ตรวจสอบว่ามีแคชเดิมและ hash ตรงกันหรือไม่
    if cache_file.exists() and hash_file.exists():
        try:
            cached_hash = hash_file.read_text(encoding="utf-8").strip()
            if cached_hash == current_hash:
                return cache_file.read_text(encoding="utf-8")
        except Exception:
            pass

    # หาก hash เปลี่ยน หรือยังไม่มีแคช ให้สรุปใหม่แล้วบันทึก
    log.info("Glossary.md มีการเปลี่ยนแปลง: กำลังสรุป Compact Glossary ใหม่...")
    compact_text = compact_glossary_text(raw_glossary)

    try:
        cache_file.write_text(compact_text, encoding="utf-8")
        hash_file.write_text(current_hash, encoding="utf-8")
        log.info("บันทึก Compact Glossary (%d ตัวอักษร) ลงที่ %s เรียบร้อย", len(compact_text), cache_file)
    except Exception as e:
        log.warning("บันทึก glossary_compact.txt ไม่สำเร็จ: %s", e)

    return compact_text
