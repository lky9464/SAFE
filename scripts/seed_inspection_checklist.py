"""
일제점검 체크리스트 JSON 생성 및 DB 시드

사용:
  python scripts/seed_inspection_checklist.py          # JSON 생성 + DB 저장
  python scripts/seed_inspection_checklist.py --json-only
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

import checklist_db  # noqa: E402
import inspection_checklist  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("seed_inspection")


def seed(*, json_only: bool = False) -> int:
    json_path = inspection_checklist.save_checklist_json()
    logger.info("JSON 저장: %s (%d항목)", json_path, len(inspection_checklist.build_checklist_dict()["items"]))

    if json_only:
        return 0

    checklist_id = checklist_db.save_checklist(
        str(json_path),
        created_by="seed_inspection",
        source_file="일제점검_체크리스트_PDF",
    )
    logger.info("DB 저장 완료 — checklist_id=%d, data_type=%s", checklist_id, inspection_checklist.INSPECTION_DATA_TYPE)
    return checklist_id


def main() -> int:
    parser = argparse.ArgumentParser(description="일제점검 47항목 체크리스트 시드")
    parser.add_argument("--json-only", action="store_true", help="JSON만 생성 (DB 미접속)")
    args = parser.parse_args()
    try:
        seed(json_only=args.json_only)
        return 0
    except Exception as exc:
        logger.error("시드 실패: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
