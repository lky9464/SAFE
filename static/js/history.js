/**
 * SAFE 이력 조회 JS — 필터·페이징·CSV·선택 삭제
 */

let currentPage = 1;
let currentTotal = 0;
let selectionMode = false;
const selectedIds = new Set();

function getFilters() {
    return {
        data_type: document.getElementById('filter-type').value,
        final_result: document.getElementById('filter-result').value,
        date_from: document.getElementById('filter-from').value,
        date_to: document.getElementById('filter-to').value,
        keyword: document.getElementById('filter-keyword').value,
    };
}

function buildQuery(filters, page) {
    const params = new URLSearchParams({ page, page_size: 10 });
    Object.entries(filters).forEach(([k, v]) => { if (v) params.set(k, v); });
    return params.toString();
}

function updateSelectModeUI() {
    const table = document.getElementById('history-table');
    const enterBtn = document.getElementById('btn-enter-select');
    const modeActions = document.getElementById('select-mode-actions');
    const confirmBtn = document.getElementById('btn-confirm-delete');
    const deleteAllBtn = document.getElementById('btn-delete-all');
    const hint = document.getElementById('select-mode-hint');

    if (table) table.classList.toggle('selection-mode', selectionMode);
    if (enterBtn) enterBtn.classList.toggle('d-none', selectionMode);
    if (modeActions) modeActions.classList.toggle('d-none', !selectionMode);
    if (deleteAllBtn) deleteAllBtn.classList.toggle('d-none', selectionMode);

    document.querySelectorAll('.row-check, #check-all').forEach(el => {
        el.disabled = !selectionMode;
        if (!selectionMode) el.indeterminate = false;
    });

    if (confirmBtn) confirmBtn.disabled = selectedIds.size === 0;
    if (hint) {
        hint.textContent = selectedIds.size > 0
            ? `${selectedIds.size}건 선택됨`
            : '삭제할 항목을 선택하세요.';
    }
}

function enterSelectMode() {
    if (currentTotal === 0) {
        showToast('삭제할 검토 이력이 없습니다.', 'warn');
        return;
    }
    selectionMode = true;
    updateSelectModeUI();
    syncSelectAllCheckbox();
}

function cancelSelectMode() {
    selectionMode = false;
    selectedIds.clear();
    document.querySelectorAll('.row-check').forEach(el => { el.checked = false; });
    updateSelectModeUI();
    syncSelectAllCheckbox();
}

function onRowCheck(reviewId, checked) {
    if (!selectionMode) return;
    if (checked) selectedIds.add(reviewId);
    else selectedIds.delete(reviewId);
    updateSelectModeUI();
    syncSelectAllCheckbox();
}

function syncSelectAllCheckbox() {
    const checkAll = document.getElementById('check-all');
    const rowChecks = document.querySelectorAll('.row-check');
    if (!checkAll) return;

    if (!selectionMode || !rowChecks.length) {
        checkAll.checked = false;
        checkAll.indeterminate = false;
        return;
    }

    const checkedCount = Array.from(rowChecks).filter(el => el.checked).length;
    checkAll.checked = checkedCount === rowChecks.length;
    checkAll.indeterminate = checkedCount > 0 && checkedCount < rowChecks.length;
}

function toggleSelectAll(checked) {
    if (!selectionMode) return;
    document.querySelectorAll('.row-check').forEach(el => {
        el.checked = checked;
        const id = Number(el.dataset.reviewId);
        if (checked) selectedIds.add(id);
        else selectedIds.delete(id);
    });
    updateSelectModeUI();
    syncSelectAllCheckbox();
}

async function loadHistory(page = 1) {
    currentPage = page;
    const filters = getFilters();
    showLoading(true);
    try {
        const data = await apiFetch(`/history/api/list?${buildQuery(filters, page)}`);
        currentTotal = data.total;
        renderTable(data.items, data.page, data.page_size);
        renderPagination(data.total, data.page, data.page_size);
        document.getElementById('history-total').textContent = `전체 ${data.total}건`;
        updateSelectModeUI();
        syncSelectAllCheckbox();
    } finally {
        showLoading(false);
    }
}

function renderTable(items, page = currentPage, pageSize = 10) {
    const tbody = document.getElementById('history-body');

    if (!items.length) {
        tbody.innerHTML = '<tr><td colspan="8" class="text-center text-muted">검토 이력이 없습니다.</td></tr>';
        return;
    }

    tbody.innerHTML = items.map((item, index) => {
        const rowNo = (page - 1) * pageSize + index + 1;
        return `
        <tr>
            <td class="select-col text-center">
                <input type="checkbox" class="history-check row-check"
                       data-review-id="${item.review_id}"
                       ${selectedIds.has(item.review_id) ? 'checked' : ''}
                       ${selectionMode ? '' : 'disabled'}
                       onchange="onRowCheck(${item.review_id}, this.checked)"
                       aria-label="검토 ${rowNo}번 선택">
            </td>
            <td>${rowNo}</td>
            <td>${item.data_type_nm}</td>
            <td>${item.business_nm}</td>
            <td>${formatDate(item.review_at)}</td>
            <td>${item.reviewer}</td>
            <td>${resultBadge(item.final_result)}</td>
            <td><a href="/review/${item.review_id}/result" class="btn btn-sm btn-outline-primary">보기</a></td>
        </tr>`;
    }).join('');
}

function renderPagination(total, page, pageSize) {
    const totalPages = Math.ceil(total / pageSize) || 1;
    const nav = document.getElementById('pagination');
    let html = '';
    if (page > 1) html += `<li class="page-item"><a class="page-link" href="#" onclick="loadHistory(${page-1});return false">이전</a></li>`;
    for (let i = Math.max(1, page-2); i <= Math.min(totalPages, page+2); i++) {
        html += `<li class="page-item ${i===page?'active':''}"><a class="page-link" href="#" onclick="loadHistory(${i});return false">${i}</a></li>`;
    }
    if (page < totalPages) html += `<li class="page-item"><a class="page-link" href="#" onclick="loadHistory(${page+1});return false">다음</a></li>`;
    nav.innerHTML = html;
}

function exportCsv() {
    const filters = getFilters();
    const params = new URLSearchParams();
    Object.entries(filters).forEach(([k, v]) => { if (v) params.set(k, v); });
    window.location.href = `/history/api/export?${params.toString()}`;
    showToast('CSV 다운로드를 시작합니다.');
}

async function confirmDeleteSelected() {
    if (!selectionMode) return;
    if (selectedIds.size === 0) {
        showToast('삭제할 항목을 선택하세요.', 'warn');
        return;
    }

    const count = selectedIds.size;
    if (!confirm(`선택한 검토 이력 ${count}건을 삭제하시겠습니까?\n(목록에서 숨김 처리되며 복구는 SQL로만 가능합니다.)`)) {
        return;
    }

    showLoading(true);
    try {
        const res = await apiFetch('/history/api/delete-selected', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ review_ids: Array.from(selectedIds) }),
        });
        if (res.success) {
            selectionMode = false;
            selectedIds.clear();
            showToast(res.message);
            await loadHistory(currentPage);
        } else {
            showToast(res.message, 'error');
        }
    } finally {
        showLoading(false);
    }
}

async function deleteAll() {
    if (currentTotal === 0) {
        showToast('삭제할 검토 이력이 없습니다.', 'warn');
        return;
    }
    const filters = getFilters();
    const hasFilter = Object.values(filters).some(v => v);
    const scope = hasFilter ? '현재 검색 조건에 해당하는' : '전체';
    if (!confirm(`${scope} 검토 이력 ${currentTotal}건을 모두 삭제하시겠습니까?\n(목록에서 숨김 처리되며 복구는 SQL로만 가능합니다.)`)) {
        return;
    }

    showLoading(true);
    try {
        const res = await apiFetch('/history/api/delete-all', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(filters),
        });
        if (res.success) {
            selectionMode = false;
            selectedIds.clear();
            showToast(res.message);
            await loadHistory(1);
        } else {
            showToast(res.message, 'error');
        }
    } finally {
        showLoading(false);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    updateSelectModeUI();
    loadHistory(1);
});
