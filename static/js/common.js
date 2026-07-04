/**
 * SAFE 공통 JS — 토스트, 로딩, 보안배지, 결과 뱃지
 */

function showToast(message, type = 'success') {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const bgClass = type === 'error' ? 'text-bg-danger'
        : type === 'warn' ? 'text-bg-warning'
        : 'text-bg-success';

    const id = 'toast-' + Date.now();
    const html = `
        <div id="${id}" class="toast align-items-center ${bgClass} border-0" role="alert">
            <div class="d-flex">
                <div class="toast-body">${message}</div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto"
                        data-bs-dismiss="toast"></button>
            </div>
        </div>`;
    container.insertAdjacentHTML('beforeend', html);
    const el = document.getElementById(id);
    const toast = new bootstrap.Toast(el, { delay: 4000 });
    toast.show();
    el.addEventListener('hidden.bs.toast', () => el.remove());
}

function showLoading(show = true, message = '') {
    const overlay = document.getElementById('loading-overlay');
    const msgEl = document.getElementById('loading-overlay-message');
    const barEl = document.getElementById('loading-overlay-progress');
    if (overlay) overlay.classList.toggle('show', show);
    if (msgEl) msgEl.textContent = message || '처리 중...';
    if (barEl) barEl.classList.toggle('d-none', !show || !message);
}

function resultBadge(code) {
    const map = {
        P: '<span class="badge badge-pass">적합</span>',
        W: '<span class="badge badge-warn">주의</span>',
        F: '<span class="badge badge-fail">부적합</span>',
    };
    return map[code] || `<span class="badge bg-secondary">${code}</span>`;
}

function riskBadge(level) {
    const map = {
        H: '<span class="badge badge-fail">H</span>',
        M: '<span class="badge badge-warn">M</span>',
        L: '<span class="badge bg-secondary">L</span>',
    };
    return map[level] || level;
}

async function apiFetch(url, options = {}) {
    try {
        const res = await fetch(url, options);
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
            throw new Error(data.detail || data.message || `요청 실패 (${res.status})`);
        }
        return data;
    } catch (err) {
        showToast(err.message, 'error');
        throw err;
    }
}

/**
 * Gemini 추가분석 요청
 * 내부자료 미포함 — 항목명·분류만 전송
 */
async function requestAnalysis(category, itemContent, judgeResult, dataType) {
    const modalEl = document.getElementById('analysisModal');
    if (!modalEl) {
        showToast('분석 모달을 찾을 수 없습니다.', 'error');
        return;
    }

    const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
    const loading = document.getElementById('analysis-loading');
    const result = document.getElementById('analysis-result');
    const title = document.getElementById('analysis-item-title');
    const content = document.getElementById('analysis-content');

    if (loading) loading.classList.remove('d-none');
    if (result) result.classList.add('d-none');
    if (title) title.textContent = `[${category}] ${itemContent}`;
    if (content) content.textContent = '';
    modal.show();

    try {
        const data = await apiFetch('/api/analysis/ask', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                category,
                item_content: itemContent,
                judge_result: judgeResult,
                data_type: dataType,
            }),
        });

        if (loading) loading.classList.add('d-none');
        if (result) result.classList.remove('d-none');
        if (content) {
            content.textContent = data.success
                ? data.analysis
                : '분석 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.';
        }
    } catch (err) {
        if (loading) loading.classList.add('d-none');
        if (result) result.classList.remove('d-none');
        if (content) content.textContent = `오류: ${err.message}`;
    }
}

function formatDate(dt) {
    if (!dt) return '-';
    const d = new Date(dt);
    if (isNaN(d)) return dt;
    return d.toLocaleDateString('ko-KR');
}

function formatDateTime(dt) {
    if (!dt) return '-';
    const d = new Date(dt);
    if (isNaN(d)) return dt;
    return d.toLocaleString('ko-KR');
}

function setActiveNav(page) {
    document.querySelectorAll('.nav-link[data-page]').forEach(el => {
        el.classList.toggle('active', el.dataset.page === page);
    });
}
