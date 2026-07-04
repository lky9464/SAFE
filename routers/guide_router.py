"""업무 단계별 체크리스트·감사사례 가이드 라우터"""



from fastapi import APIRouter, Request



import work_guide

from web_common import DATA_TYPE_LABELS, templates



router = APIRouter()





def _resolve_guide(guide_id: str | None) -> str:

    gid = guide_id or "work"

    if gid not in work_guide.GUIDE_REGISTRY:

        return "work"

    return gid





@router.get("/guide")

async def guide_page(

    request: Request,

    guide: str | None = None,

    section: str | None = None,

):

    """업무가이드·감사사례 조회 화면"""

    guide_id = _resolve_guide(guide)

    sections = work_guide.parse_guide_sections(guide_id)

    meta = work_guide.get_guide_meta(guide_id)

    initial = section or (sections[0]["id"] if sections else None)

    initial_html = ""

    initial_title = ""

    if initial:

        detail = work_guide.get_section(guide_id, initial)

        if detail:

            initial_html = detail["body_html"]

            initial_title = detail["title"]



    return templates.TemplateResponse(

        request,

        "guide.html",

        {

            "active_page": "guide",

            "guide_id": guide_id,

            "guides": work_guide.list_guides(),

            "meta": meta,

            "toc": work_guide.get_toc(guide_id),

            "data_types": DATA_TYPE_LABELS,

            "initial_section": initial,

            "initial_title": initial_title,

            "initial_html": initial_html,

        },

    )





@router.get("/api/guide/list")

async def api_guide_list():

    """가이드 문서 목록"""

    return {"guides": work_guide.list_guides()}





@router.get("/api/guide/toc")

async def api_guide_toc(guide: str | None = None):

    """목차 JSON"""

    guide_id = _resolve_guide(guide)

    return {

        "guide_id": guide_id,

        "meta": work_guide.get_guide_meta(guide_id),

        "sections": work_guide.get_toc(guide_id),

    }





@router.get("/api/guide/section/{section_id}")

async def api_guide_section(section_id: str, guide: str | None = None):

    """섹션 본문 JSON"""

    guide_id = _resolve_guide(guide)

    detail = work_guide.get_section(guide_id, section_id)

    if not detail:

        return {"error": "섹션을 찾을 수 없습니다."}

    return {

        "guide_id": guide_id,

        "id": detail["id"],

        "title": detail["title"],

        "number": detail["number"],

        "data_types": detail["data_types"],

        "data_type_labels": detail["data_type_labels"],

        "body_html": detail["body_html"],

    }





@router.get("/api/guide/full")

async def api_guide_full(guide: str | None = None):

    """전체 HTML"""

    guide_id = _resolve_guide(guide)

    return {"guide_id": guide_id, "html": work_guide.get_full_guide_html(guide_id)}


