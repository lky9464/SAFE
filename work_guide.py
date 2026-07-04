"""

지방보조금 업무 가이드·감사사례 문서 로드·파싱

"""



import re

from pathlib import Path

from typing import Any



import markdown



_BASE_DIR = Path(__file__).resolve().parent



GUIDE_REGISTRY: dict[str, dict[str, Any]] = {

    "work": {

        "title": "지방보조금 업무 단계별 체크리스트",

        "source": "경남·충남 감사사례집, 보조사업 단계별 주요 점검사항 종합",

        "path": _BASE_DIR / "docs" / "지방보조금_업무단계별_체크리스트.md",

        "updated": "2025년 6월",

        "section_data_types": {

            "1": ["1"],

            "2": ["1"],

            "3": ["2", "3"],

            "4": ["3", "4"],

            "5": [],

            "6": [],

            "7": ["3"],

            "8": ["2", "3"],

            "9": [],

        },

    },

    "chungnam": {

        "title": "충청남도 감사 사례 체크리스트",

        "source": "★2025년 충청남도 지방보조금 감사 사례집 (2025. 8.)",

        "path": _BASE_DIR / "docs" / "충청남도_감사사례_체크리스트.md",

        "updated": "2025년 8월",

        "section_data_types": {

            "1": ["1"],

            "2": ["2", "3"],

            "3": ["3", "4"],

            "4": ["4"],

            "5": [],

        },

    },

    "event": {

        "title": "민간행사보조금 특정감사",

        "source": "민간행사보조금 집행실태 특정감사 결과(공개문) — 인천광역시 (2025)",

        "path": _BASE_DIR / "docs" / "민간행사보조금_감사사례_체크리스트.md",

        "updated": "2025년 8월",

        "section_data_types": {

            "1": [],

            "2": ["1"],

            "3": ["2"],

            "4": ["3"],

            "5": ["4"],

            "6": [],

        },

    },

    "gangbuk": {

        "title": "자치행정과 종합감사",

        "source": "2024년 자치행정과 종합감사 결과 보고(공개) — 서울 강북구 (2024. 7.)",

        "path": _BASE_DIR / "docs" / "자치행정과_종합감사_체크리스트.md",

        "updated": "2024년 8월",

        "section_data_types": {

            "1": [],

            "2": ["1"],

            "3": ["2"],

            "4": ["3"],

            "5": ["4"],

            "6": [],

        },

    },

    "sports": {

        "title": "감사사례집 (체육단체)",

        "source": "감사사례집(배포용) — 세종시체육회 회원종목단체 (2025. 5.)",

        "path": _BASE_DIR / "docs" / "감사사례집_체육단체_체크리스트.md",

        "updated": "2025년 5월",

        "section_data_types": {

            "1": [],

            "2": ["1"],

            "3": ["3"],

            "4": ["2"],

            "5": ["4"],

            "6": [],

        },

    },

}



DATA_TYPE_LABELS = {

    "1": "① 사업계획서",

    "2": "② 집행내역서",

    "3": "③ 지출증빙",

    "4": "④ 정산보고서",

}



_SKIP_SECTIONS = {"목차"}





def list_guides() -> list[dict[str, str]]:

    """등록된 가이드 목록"""

    return [

        {

            "id": gid,

            "title": meta["title"],

            "source": meta["source"],

            "updated": meta["updated"],

        }

        for gid, meta in GUIDE_REGISTRY.items()

    ]





def _get_meta(guide_id: str) -> dict[str, Any]:

    if guide_id not in GUIDE_REGISTRY:

        raise KeyError(f"알 수 없는 가이드: {guide_id}")

    meta = GUIDE_REGISTRY[guide_id]

    return {

        "id": guide_id,

        "title": meta["title"],

        "source": meta["source"],

        "path": str(meta["path"]),

        "updated": meta["updated"],

    }





def _section_id(title: str) -> str:

    num_match = re.match(r"^(\d+)\.", title.strip())

    if num_match:

        return f"sec-{num_match.group(1)}"

    slug = re.sub(r"[^\w가-힣]+", "-", title).strip("-").lower()

    return slug or "sec"





def _section_number(title: str) -> str:

    m = re.match(r"^(\d+)\.", title.strip())

    return m.group(1) if m else ""





def _related_data_types(guide_id: str, section_num: str) -> list[str]:

    mapping = GUIDE_REGISTRY[guide_id].get("section_data_types", {})

    return mapping.get(section_num, [])





def load_guide_raw(guide_id: str = "work") -> str:

    path = GUIDE_REGISTRY[guide_id]["path"]

    if not path.is_file():

        raise FileNotFoundError(f"가이드 문서를 찾을 수 없습니다: {path}")

    return path.read_text(encoding="utf-8")





def parse_guide_sections(guide_id: str = "work") -> list[dict[str, Any]]:

    content = load_guide_raw(guide_id)

    parts = re.split(r"\n(?=## )", content)

    sections: list[dict[str, Any]] = []



    for part in parts:

        part = part.strip()

        if not part.startswith("##"):

            continue



        lines = part.split("\n", 1)

        raw_title = lines[0].replace("## ", "").strip()

        title = re.sub(r"\s*\{#[^}]+\}", "", raw_title).strip()

        if title in _SKIP_SECTIONS:

            continue

        body = lines[1] if len(lines) > 1 else ""

        sec_num = _section_number(title)

        data_types = _related_data_types(guide_id, sec_num)



        sections.append({

            "id": _section_id(title),

            "number": sec_num,

            "title": title,

            "body_md": body.strip(),

            "data_types": data_types,

            "data_type_labels": [DATA_TYPE_LABELS.get(dt, dt) for dt in data_types],

        })



    return sections





def render_section_html(body_md: str) -> str:

    if not body_md:

        return ""

    return markdown.markdown(

        body_md,

        extensions=["tables", "nl2br", "sane_lists"],

    )





def get_guide_meta(guide_id: str = "work") -> dict[str, Any]:

    return _get_meta(guide_id)





def get_toc(guide_id: str = "work") -> list[dict[str, Any]]:

    return [

        {

            "id": s["id"],

            "number": s["number"],

            "title": s["title"],

            "data_types": s["data_types"],

            "data_type_labels": s["data_type_labels"],

        }

        for s in parse_guide_sections(guide_id)

    ]





def get_section(guide_id: str, section_id: str) -> dict[str, Any] | None:

    for sec in parse_guide_sections(guide_id):

        if sec["id"] == section_id:

            return {**sec, "body_html": render_section_html(sec["body_md"])}

    return None





def get_full_guide_html(guide_id: str = "work") -> str:

    sections = parse_guide_sections(guide_id)

    chunks = []

    for sec in sections:

        chunks.append(f'<section id="{sec["id"]}" class="guide-section">')

        chunks.append(f'<h2>{sec["title"]}</h2>')

        if sec["data_type_labels"]:

            labels = " · ".join(sec["data_type_labels"])

            chunks.append(f'<p class="guide-related"><strong>SAFE 연관:</strong> {labels}</p>')

        chunks.append(render_section_html(sec["body_md"]))

        chunks.append("</section>")

    return "\n".join(chunks)


