/**
 * SAFE 자료 검토 JS — 단일/사업통합 업로드·프로필·진행상태 폴링
 */

let selectedType = null;
let uploadedFile = null;
/** @type {Record<string, {file_path: string, file_nm: string, file_size: number}>} */
const caseFiles = {};

const STEP_LABELS = {
    upload: '파일 수신',
    ocr: 'OCR 처리',
    parse: '항목 파싱',
    compare: '체크리스트 비교',
    save: '결과 저장',
};

const LIMITS = window.SAFE_UPLOAD_LIMITS || {
    maxFileMb: 100,
    maxZipMb: 500,
    maxZipFiles: 400,
};

const INSPECTION_DATA_TYPE = '0';

function buildUploadHints() {
    const f = LIMITS.maxFileMb;
    const z = LIMITS.maxZipMb;
    const n = LIMITS.maxZipFiles;
    return {
        '1': `PDF · HWP (최대 ${f}MB)`,
        '2': `PDF · HWP · Excel (최대 ${f}MB)`,
        '3': `PDF · JPG · PNG (최대 ${f}MB) 또는 ZIP 묶음 (최대 ${z}MB, ZIP 내 PDF·이미지 최대 ${n}개)`,
        '4': `PDF · HWP · Excel (최대 ${f}MB)`,
    };
}

let UPLOAD_HINTS = buildUploadHints();

function isInspectionChecklistSelected() {
    const sel = document.getElementById('checklist-id');
    const opt = sel.options[sel.selectedIndex];
    if (!opt || !opt.value || opt.value === '-1') return false;
    return opt.dataset.type === INSPECTION_DATA_TYPE;
}

function isCaseMode() {
    return isInspectionChecklistSelected();
}

function updateModePanels() {
    const caseMode = isCaseMode();
    const casePanel = document.getElementById('case-mode-panel');
    const singlePanel = document.getElementById('single-mode-panel');
    const docsManual = document.getElementById('profile-docs-manual');
    const docsAuto = document.getElementById('profile-docs-auto');

    if (casePanel) casePanel.classList.toggle('d-none', !caseMode);
    if (singlePanel) singlePanel.classList.toggle('d-none', caseMode);
    if (docsManual) docsManual.classList.toggle('d-none', caseMode);
    if (docsAuto) docsAuto.classList.toggle('d-none', !caseMode);

    updateProfilePanelVisibility();
    updateStartButton();
}

function updateProfilePanelVisibility() {
    const panel = document.getElementById('profile-panel');
    if (!panel) return;
    panel.classList.toggle('d-none', !isInspectionChecklistSelected());
}

function setProfileEnabledUI(enabled) {
    const panel = document.getElementById('profile-panel');
    const body = document.getElementById('profile-body');
    if (!panel || !body) return;
    panel.classList.toggle('disabled-overlay', !enabled);
}

function selectType(type, el) {
    selectedType = type;
    document.querySelectorAll('.type-card').forEach(c => c.classList.remove('selected'));
    el.classList.add('selected');
    filterChecklists(type);
    hintDocAvailability(type);
    updateStartButton();
    const hint = document.getElementById('upload-hint');
    if (hint) hint.textContent = UPLOAD_HINTS[type] || UPLOAD_HINTS['1'];
}

/** 업로드 자료유형에 맞춰 4종 제출 체크 힌트 (단일 모드) */
function hintDocAvailability(dataType) {
    const map = {
        '1': { '1': true, '2': false, '3': false, '4': false },
        '2': { '1': false, '2': true, '3': false, '4': false },
        '3': { '1': false, '2': false, '3': true, '4': false },
        '4': { '1': false, '2': false, '3': false, '4': true },
    };
    const hints = map[dataType];
    if (!hints) return;
    document.querySelectorAll('.profile-doc').forEach(cb => {
        const doc = cb.dataset.doc;
        if (hints[doc] !== undefined) cb.checked = hints[doc];
    });
}

function syncProfileDocsFromCaseFiles() {
    document.querySelectorAll('.profile-doc').forEach(cb => {
        cb.checked = !!caseFiles[cb.dataset.doc];
    });
}

function filterChecklists(type) {
    const sel = document.getElementById('checklist-id');
    let hasVisible = false;
    Array.from(sel.options).forEach(opt => {
        if (opt.value === '-1' || opt.value === '') {
            opt.hidden = false;
            return;
        }
        const match = opt.dataset.type === type || opt.dataset.type === INSPECTION_DATA_TYPE;
        opt.hidden = !match;
        if (match) hasVisible = true;
    });
    if (hasVisible) {
        const sameType = Array.from(sel.options).find(
            o => !o.hidden && o.value && o.value !== '-1' && o.dataset.type === type
        );
        const first = sameType || Array.from(sel.options).find(
            o => !o.hidden && o.value && o.value !== '-1'
        );
        if (first) sel.value = first.value;
    } else {
        sel.value = '-1';
    }
    updateModePanels();
}

function clearSeomoks() {
    document.querySelectorAll('.profile-seomok').forEach(cb => { cb.checked = false; });
}

function selectAllSeomoks() {
    document.querySelectorAll('.profile-seomok').forEach(cb => { cb.checked = true; });
}

function buildCaseProfilePayload() {
    if (!isInspectionChecklistSelected()) return null;

    const enabled = document.getElementById('profile-enabled').checked;
    const executed = [];
    document.querySelectorAll('.profile-seomok:checked').forEach(cb => {
        executed.push(cb.value);
    });

    const fromCase = isCaseMode() && Object.keys(caseFiles).length > 0;
    return {
        enabled,
        has_plan: fromCase ? !!caseFiles['1'] : document.getElementById('doc-1').checked,
        has_execution: fromCase ? !!caseFiles['2'] : document.getElementById('doc-2').checked,
        has_proof: fromCase ? !!caseFiles['3'] : document.getElementById('doc-3').checked,
        has_settlement: fromCase ? !!caseFiles['4'] : document.getElementById('doc-4').checked,
        executed_seomoks: executed,
        operating_grant_only: document.getElementById('operating-grant-only').checked,
    };
}

function updateStartButton() {
    const btn = document.getElementById('btn-start');
    if (isCaseMode()) {
        btn.disabled = Object.keys(caseFiles).length === 0;
    } else {
        btn.disabled = !(selectedType && uploadedFile);
    }
}

function updateCaseSlotUI(docType) {
    const info = document.querySelector(`.case-file-info[data-doc="${docType}"]`);
    const clearBtn = document.querySelector(`.case-clear[data-doc="${docType}"]`);
    const slot = document.querySelector(`.case-slot[data-doc="${docType}"]`);
    const data = caseFiles[docType];
    if (data) {
        info.textContent = `${data.file_nm} (${(data.file_size / 1024 / 1024).toFixed(1)} MB)`;
        info.classList.remove('d-none');
        clearBtn.classList.remove('d-none');
        slot.classList.add('has-file');
    } else {
        info.classList.add('d-none');
        info.textContent = '';
        clearBtn.classList.add('d-none');
        slot.classList.remove('has-file');
    }
}

function clearCaseFile(docType) {
    delete caseFiles[docType];
    const input = document.querySelector(`.case-file-input[data-doc="${docType}"]`);
    if (input) input.value = '';
    updateCaseSlotUI(docType);
    syncProfileDocsFromCaseFiles();
    updateStartButton();
}

async function handleCaseFile(docType, file) {
    showLoading(true);
    try {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('data_type', docType);
        const res = await fetch('/review/api/upload', { method: 'POST', body: formData });
        const data = await res.json();
        if (!data.success) throw new Error(data.message);
        caseFiles[docType] = {
            file_path: data.file_path,
            file_nm: data.file_nm,
            file_size: data.file_size,
        };
        updateCaseSlotUI(docType);
        syncProfileDocsFromCaseFiles();
        updateStartButton();
        showToast(`${docType === '1' ? '①' : docType === '2' ? '②' : docType === '3' ? '③' : '④'} 업로드 완료`);
    } catch (err) {
        showToast(err.message, 'error');
    } finally {
        showLoading(false);
    }
}

function bindCaseSlots() {
    document.querySelectorAll('.case-drop').forEach(zone => {
        const docType = zone.dataset.doc;
        const input = document.querySelector(`.case-file-input[data-doc="${docType}"]`);
        zone.addEventListener('click', () => input && input.click());
        zone.addEventListener('dragover', e => {
            e.preventDefault();
            zone.classList.add('dragover');
        });
        zone.addEventListener('dragleave', () => zone.classList.remove('dragover'));
        zone.addEventListener('drop', e => {
            e.preventDefault();
            zone.classList.remove('dragover');
            if (e.dataTransfer.files.length) handleCaseFile(docType, e.dataTransfer.files[0]);
        });
    });
    document.querySelectorAll('.case-file-input').forEach(input => {
        input.addEventListener('change', e => {
            if (e.target.files.length) handleCaseFile(input.dataset.doc, e.target.files[0]);
        });
    });
    document.querySelectorAll('.case-clear').forEach(btn => {
        btn.addEventListener('click', e => {
            e.stopPropagation();
            clearCaseFile(btn.dataset.doc);
        });
    });
}

const dropZone = document.getElementById('drop-zone');
const fileInput = document.getElementById('file-input');

if (dropZone && fileInput) {
    dropZone.addEventListener('click', () => fileInput.click());
    dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('dragover'); });
    dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
    dropZone.addEventListener('drop', e => {
        e.preventDefault();
        dropZone.classList.remove('dragover');
        if (e.dataTransfer.files.length) handleFile(e.dataTransfer.files[0]);
    });
    fileInput.addEventListener('change', e => {
        if (e.target.files.length) handleFile(e.target.files[0]);
    });
}

document.getElementById('checklist-id').addEventListener('change', () => {
    updateModePanels();
});

const profileEnabledEl = document.getElementById('profile-enabled');
if (profileEnabledEl) {
    profileEnabledEl.addEventListener('change', () => {
        setProfileEnabledUI(profileEnabledEl.checked);
    });
}

bindCaseSlots();

// 초기: 일제점검 체크리스트가 있으면 기본 선택 → 사업 통합 모드
(function initDefaultChecklist() {
    const sel = document.getElementById('checklist-id');
    const inspection = Array.from(sel.options).find(
        o => o.dataset.type === INSPECTION_DATA_TYPE && o.value && o.value !== '-1'
    );
    if (inspection) {
        sel.value = inspection.value;
    }
    updateModePanels();
})();

async function handleFile(file) {
    if (!selectedType) {
        showToast('먼저 자료유형을 선택하세요.', 'warn');
        return;
    }
    showLoading(true);
    try {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('data_type', selectedType);
        const res = await fetch('/review/api/upload', { method: 'POST', body: formData });
        const data = await res.json();
        if (!data.success) throw new Error(data.message);
        uploadedFile = data;
        const info = document.getElementById('file-info');
        info.classList.remove('d-none');
        let infoText = `업로드 완료: ${data.file_nm} (${(data.file_size / 1024 / 1024).toFixed(1)} MB)`;
        if (data.is_zip_bundle) {
            const n = data.bundle_file_count != null ? data.bundle_file_count : '?';
            infoText += ` — ZIP 묶음 (처리 대상 ${n}개)`;
        }
        info.textContent = infoText;
        hintDocAvailability(selectedType);
        updateStartButton();
        showToast('파일 업로드 완료');
    } catch (err) {
        showToast(err.message, 'error');
    } finally {
        showLoading(false);
    }
}

function getChecklistIdValue() {
    const raw = document.getElementById('checklist-id').value;
    if (raw === '-1') return -1;
    if (!raw) return null;
    return parseInt(raw, 10);
}

async function startReview() {
    document.getElementById('step-upload').classList.add('d-none');
    document.getElementById('step-progress').classList.remove('d-none');
    document.getElementById('all-results').classList.add('d-none');

    let body;
    if (isCaseMode()) {
        const files = Object.entries(caseFiles).map(([data_type, f]) => ({
            data_type,
            file_path: f.file_path,
            file_nm: f.file_nm,
        }));
        if (!files.length) {
            showToast('사업 자료를 1개 이상 업로드하세요.', 'warn');
            document.getElementById('step-upload').classList.remove('d-none');
            document.getElementById('step-progress').classList.add('d-none');
            return;
        }
        body = {
            task_id: '',
            data_type: INSPECTION_DATA_TYPE,
            file_path: files[0].file_path,
            business_nm: document.getElementById('business-nm').value,
            checklist_id: getChecklistIdValue(),
            reviewer: document.getElementById('reviewer').value || '담당자',
            case_profile: buildCaseProfilePayload(),
            case_files: files,
        };
    } else {
        if (!uploadedFile || !selectedType) return;
        body = {
            task_id: '',
            data_type: selectedType,
            file_path: uploadedFile.file_path,
            business_nm: document.getElementById('business-nm').value,
            checklist_id: getChecklistIdValue(),
            reviewer: document.getElementById('reviewer').value || '담당자',
            case_profile: buildCaseProfilePayload(),
        };
    }

    try {
        const res = await apiFetch('/review/api/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });
        pollStatus(res.task_id);
    } catch (err) {
        showToast('검토 시작 실패: ' + err.message, 'error');
        document.getElementById('step-upload').classList.remove('d-none');
        document.getElementById('step-progress').classList.add('d-none');
    }
}

function updateProgressUI(data) {
    const bar = document.getElementById('progress-bar');
    const pct = data.progress || 0;
    bar.style.width = pct + '%';
    bar.textContent = pct + '%';
    document.getElementById('progress-message').textContent = data.message || '';

    const stepsEl = document.getElementById('progress-steps');
    if (!data.steps) return;
    let html = '';
    for (const [key, status] of Object.entries(data.steps)) {
        const icon = status === 'done' ? '✅' : status === 'processing' ? '⏳' : '⏸';
        html += `<div class="progress-step"><span class="step-icon">${icon}</span>
            ${STEP_LABELS[key] || key} <span class="text-muted ms-2">로컬</span></div>`;
    }
    stepsEl.innerHTML = html;
}

function showAllResults(data) {
    const box = document.getElementById('all-results');
    if (!data.review_ids || data.review_ids.length <= 1) return;

    let html = '<div class="alert alert-success"><strong>전체 점검 완료</strong> — 결과 링크:</div><div class="d-flex flex-wrap gap-2">';
    data.review_ids.forEach((id, i) => {
        html += `<a class="btn btn-sm btn-outline-primary" href="/review/${id}/result" target="_blank">결과 ${i + 1} (ID ${id})</a>`;
    });
    html += '</div>';
    box.innerHTML = html;
    box.classList.remove('d-none');
}

function pollStatus(taskId) {
    const interval = setInterval(async () => {
        try {
            const res = await fetch(`/review/api/status/${taskId}`);
            const data = await res.json();
            updateProgressUI(data);

            if (data.status === 'done') {
                clearInterval(interval);
                showToast(data.message || '검토 완료!');

                if (data.all_mode && data.review_ids && data.review_ids.length > 1) {
                    showAllResults(data);
                    setTimeout(() => {
                        window.location.href = `/review/${data.review_id}/result`;
                    }, 2500);
                } else {
                    window.location.href = `/review/${data.review_id}/result`;
                }
            }
            if (data.status === 'error') {
                clearInterval(interval);
                showToast(data.error_msg || '검토 중 오류 발생', 'error');
            }
        } catch (err) {
            clearInterval(interval);
            showToast('상태 확인 실패', 'error');
        }
    }, 2000);
}
