"""
검토 결과 HTML 보고서 생성 모듈
"""

import logging
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any

import checker
import config
import inspection_checklist
import logger as safe_logger

logger = logging.getLogger(__name__)

# 판정 결과 색상
RESULT_COLORS: dict[str, dict[str, str]] = {
    "P": {"bg": "#E8F5E9", "text": "#107C10", "label": "적합"},
    "W": {"bg": "#FFFDE7", "text": "#BA7517", "label": "주의"},
    "F": {"bg": "#FFEBEE", "text": "#C50F1F", "label": "부적합"},
    "A": {"bg": "#F1F3F5", "text": "#495057", "label": "해당없음"},
}

_DOC_LABELS = {
    "1": "① 사업계획서",
    "2": "② 집행내역서",
    "3": "③ 지출증빙",
    "4": "④ 정산보고서",
}

DATA_TYPE_LABELS = safe_logger.DATA_TYPE_LABELS
RESULT_LABELS = safe_logger.RESULT_LABELS


def get_report_data(review_id: int) -> dict[str, Any] | None:
    """보고서용 데이터 조회"""
    data = safe_logger.get_review_detail(review_id)
    if not data:
        return None
    return data


def render_summary_card(result_data: dict[str, Any]) -> str:
    """요약 카드 HTML 생성"""
    pass_cnt = result_data.get("pass_cnt", 0)
    warn_cnt = result_data.get("warn_cnt", 0)
    fail_cnt = result_data.get("fail_cnt", 0)
    na_cnt = result_data.get("na_cnt", 0)
    applicable = result_data.get("applicable_item_cnt", pass_cnt + warn_cnt + fail_cnt)
    total = result_data.get("total_item_cnt", applicable + na_cnt)
    final = result_data.get("final_result", "W")
    final_color = RESULT_COLORS.get(final, RESULT_COLORS["W"])

    return f"""
    <section class="summary">
      <div class="card pass">적합 <strong>{pass_cnt}</strong>항목</div>
      <div class="card warn">주의 <strong>{warn_cnt}</strong>항목</div>
      <div class="card fail">부적합 <strong>{fail_cnt}</strong>항목</div>
      <div class="card na">해당없음 <strong>{na_cnt}</strong>항목</div>
      <div class="card final" style="background:{final_color['bg']};color:{final_color['text']}">
        최종결과: <strong>{escape(RESULT_LABELS.get(final, final))}</strong>
      </div>
    </section>
    <p class="meta">적용 {applicable}건 / 전체 {total}건
      (해당없음 {na_cnt}건은 최종 판정에서 제외)</p>
    """


def render_profile_summary(result_data: dict[str, Any]) -> str:
    """사업 프로필 요약 HTML"""
    snapshot = result_data.get("case_profile")
    if not snapshot:
        return ""

    docs = [_DOC_LABELS[d] for d in snapshot.get("docs", []) if d in _DOC_LABELS]
    labels = inspection_checklist.INSPECTION_SEOMOK_LABELS
    seomoks = [
        f"{code} {labels.get(code, '')}".strip()
        for code in snapshot.get("seomoks", [])
    ]
    docs_text = ", ".join(docs) if docs else "없음"
    seomoks_text = ", ".join(seomoks) if seomoks else "없음"
    og_line = (
        "<p><strong>운영비 교부 사업만 (JC-04 적용)</strong></p>"
        if snapshot.get("operating_grant_only")
        else ""
    )
    return f"""
    <section class="profile-summary">
      <h2>사업 프로필 요약</h2>
      <p>제출 자료: <strong>{escape(docs_text)}</strong></p>
      <p>② 집행 세목: <strong>{escape(seomoks_text)}</strong></p>
      {og_line}
    </section>
    """


def _format_risk_line(item: dict[str, Any]) -> str:
    """위험 항목 표시 — 판정 근거 중복 제거"""
    category = item.get("category", "")
    content = item.get("item_content", "")
    reason = item.get("judge_reason", "")

    if content and reason.startswith(content):
        reason = reason[len(content):].lstrip(" —-|")
    duplicate_prefix = f"{content} — {content}"
    if reason.startswith(duplicate_prefix):
        reason = reason[len(duplicate_prefix):].lstrip(" —-|")

    label = f"[{category}] {content}" if category else content
    return f"{label} — {reason}" if reason else label


def render_risk_highlight(risk_items: list[dict[str, Any]]) -> str:
    """위험 항목 강조 HTML 생성"""
    if not risk_items:
        return ""

    rows = []
    for item in risk_items:
        rows.append(
            f"<li><strong>{escape(_format_risk_line(item))}</strong></li>"
        )

    return f"""
    <section class="risk-highlight">
      <h2>즉시 조치 필요 항목</h2>
      <ul>{''.join(rows)}</ul>
    </section>
    """


def render_detail_table(details: list[dict[str, Any]]) -> str:
    """항목별 결과 테이블 HTML 생성"""
    rows = []
    for detail in details:
        grade = detail.get("judge_result", "W")
        color = RESULT_COLORS.get(grade, RESULT_COLORS["W"])
        sim = detail.get("similarity")
        sim_text = f"{float(sim):.2f}" if sim is not None else "-"
        extracted = checker.humanize_extracted_val(detail)

        rows.append(f"""
        <tr style="background:{color['bg']}">
          <td>{detail.get('item_no', '')}</td>
          <td>{escape(str(detail.get('category', '')))}</td>
          <td>{escape(str(detail.get('item_content', '')))}</td>
          <td>{escape(extracted)}</td>
          <td style="color:{color['text']};font-weight:bold">{escape(color['label'])}</td>
          <td>{sim_text}</td>
          <td>{escape(str(detail.get('judge_reason', '')))}</td>
          <td>{escape(str(detail.get('law_ref', '')))}</td>
        </tr>
        """)

    return f"""
    <section class="detail-table">
      <h2>항목별 검토 결과</h2>
      <table>
        <thead>
          <tr>
            <th>No</th><th>분류</th><th>점검항목</th><th>검토내용</th>
            <th>결과</th><th>유사도</th><th>판정근거</th><th>법령근거</th>
          </tr>
        </thead>
        <tbody>{''.join(rows)}</tbody>
      </table>
    </section>
    """


def _report_styles() -> str:
    """보고서 CSS"""
    return """
    <style>
      body { font-family: '맑은 고딕', sans-serif; margin: 40px; color: #333; }
      h1 { color: #1a3a6b; border-bottom: 2px solid #1a3a6b; padding-bottom: 10px; }
      .summary { display: flex; gap: 16px; margin: 24px 0; flex-wrap: wrap; }
      .card { padding: 16px 24px; border-radius: 8px; font-size: 16px; min-width: 140px; }
      .card.pass { background: #E8F5E9; color: #107C10; }
      .card.warn { background: #FFFDE7; color: #BA7517; }
      .card.fail { background: #FFEBEE; color: #C50F1F; }
      .card.na { background: #F1F3F5; color: #495057; }
      .card.final { border: 2px solid currentColor; }
      .profile-summary { background: #f8fafc; border-left: 4px solid #1a3a6b;
                         padding: 16px; margin: 16px 0; }
      .profile-summary h2 { margin-top: 0; font-size: 1.1rem; }
      .risk-highlight { background: #FFEBEE; border-left: 4px solid #C50F1F;
                        padding: 16px; margin: 24px 0; }
      .risk-highlight h2 { color: #C50F1F; margin-top: 0; }
      table { width: 100%; border-collapse: collapse; margin: 16px 0; font-size: 13px; }
      th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
      th { background: #f5f5f5; }
      footer { margin-top: 40px; color: #888; font-size: 12px;
                border-top: 1px solid #ddd; padding-top: 16px; }
      .meta { color: #666; margin: 8px 0; }
    </style>
    """


def generate_html_report(review_id: int) -> str:
    """
    HTML 보고서 생성 및 저장.

    Returns:
        생성된 HTML 파일 경로
    """
    data = get_report_data(review_id)
    if not data:
        raise ValueError(f"검토 이력을 찾을 수 없습니다: review_id={review_id}")

    config.ensure_directories()
    details = data.get("details", [])
    risk_items = [d for d in details if d.get("judge_result") == "F"]

    review_at = data.get("review_at", datetime.now())
    if isinstance(review_at, datetime):
        review_at_str = review_at.strftime("%Y-%m-%d %H:%M:%S")
    else:
        review_at_str = str(review_at)

    data_type_label = DATA_TYPE_LABELS.get(data.get("data_type", ""), "")
    business_nm = data.get("business_nm", "미상")
    safe_name = "".join(c if c.isalnum() or c in "._-" else "_" for c in business_nm)[:30]
    date_str = datetime.now().strftime("%Y%m%d")
    filename = f"{review_id}_{date_str}_{safe_name}.html"
    output_path = Path(config.REPORTS_DIR) / filename

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>SAFE 검토 결과 보고서 — {escape(business_nm)}</title>
  {_report_styles()}
</head>
<body>
  <div class="report">
    <header>
      <h1>SAFE 검토 결과 보고서</h1>
      <p class="meta">
        사업명: <strong>{escape(business_nm)}</strong> |
        검토일: {escape(review_at_str)} |
        담당자: {escape(str(data.get('reviewer', '')))} |
        자료유형: {escape(data_type_label)}
      </p>
    </header>

    {render_summary_card(data)}
    {render_profile_summary(data)}
    {render_risk_highlight(risk_items)}
    {render_detail_table(details)}

    <footer>
      <p>본 보고서는 SAFE 시스템에 의해 자동 생성됨</p>
      <p>생성일시: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
    </footer>
  </div>
</body>
</html>
"""

    try:
        output_path.write_text(html, encoding="utf-8")
        logger.info("HTML 보고서 생성 완료: %s", output_path)
        return str(output_path)
    except OSError as exc:
        logger.error("HTML 보고서 생성 실패: %s", exc)
        raise RuntimeError(f"HTML 보고서 생성에 실패했습니다: {exc}") from exc
