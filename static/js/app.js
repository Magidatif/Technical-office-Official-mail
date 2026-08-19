// Application State
let currentTab = 'inbox_unreplied';
let currentPage = 1;
let currentLimit = 25;
let searchQuery = '';
let searchDebounceTimer = null;
let syncPollingTimer = null;
let allEmailsCache = [];

// Initialize on DOM Ready
document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    loadStats();
    loadEmails(1);
    checkSyncStatus();
});

// ==========================================================================
// Theme Management
// ==========================================================================
function initTheme() {
    const savedTheme = localStorage.getItem('eha_mail_theme') || 'light';
    document.documentElement.setAttribute('data-theme', savedTheme);
    updateThemeIcon(savedTheme);
}

function toggleTheme() {
    const current = document.documentElement.getAttribute('data-theme') || 'light';
    const nextTheme = current === 'light' ? 'dark' : 'light';
    document.documentElement.setAttribute('data-theme', nextTheme);
    localStorage.setItem('eha_mail_theme', nextTheme);
    updateThemeIcon(nextTheme);
}

function updateThemeIcon(theme) {
    const btn = document.getElementById('themeToggle');
    if (btn) {
        btn.innerHTML = theme === 'dark'
            ? '<i class="fa-solid fa-sun"></i>'
            : '<i class="fa-solid fa-moon"></i>';
    }
}

// ==========================================================================
// Toast Notification
// ==========================================================================
function showToast(message, icon = 'fa-circle-info') {
    const toast = document.getElementById('toast');
    if (!toast) return;
    toast.innerHTML = `<i class="fa-solid ${icon}"></i> <span>${message}</span>`;
    toast.classList.add('show');
    setTimeout(() => {
        toast.classList.remove('show');
    }, 3500);
}

// ==========================================================================
// API: Stats & KPIs
// ==========================================================================
async function loadStats() {
    try {
        const res = await fetch('/api/stats');
        const data = await res.json();

        const inUn = data.inbox_unreplied_count || 0;
        const sentUn = data.sent_unreplied_count || 0;
        const inRep = data.inbox_replied_count || 0;
        const sentRep = data.sent_replied_count || 0;
        const inTot = data.total_inbox || 0;
        const sentTot = data.total_sent || 0;

        if (document.getElementById('statInboxUnreplied')) document.getElementById('statInboxUnreplied').innerText = inUn.toLocaleString('ar-EG');
        if (document.getElementById('statSentUnreplied')) document.getElementById('statSentUnreplied').innerText = sentUn.toLocaleString('ar-EG');
        if (document.getElementById('statInboxReplied')) document.getElementById('statInboxReplied').innerText = inRep.toLocaleString('ar-EG');
        if (document.getElementById('statSentReplied')) document.getElementById('statSentReplied').innerText = sentRep.toLocaleString('ar-EG');
        if (document.getElementById('statInboxTotal')) document.getElementById('statInboxTotal').innerText = inTot.toLocaleString('ar-EG');
        if (document.getElementById('statSentTotal')) document.getElementById('statSentTotal').innerText = sentTot.toLocaleString('ar-EG');

        const badgeIn = document.getElementById('badgeInboxUnreplied');
        if (badgeIn) {
            badgeIn.innerText = inUn;
            badgeIn.style.display = inUn > 0 ? 'inline-block' : 'none';
        }

        const badgeSent = document.getElementById('badgeSentUnreplied');
        if (badgeSent) {
            badgeSent.innerText = sentUn;
            badgeSent.style.display = sentUn > 0 ? 'inline-block' : 'none';
        }
    } catch (e) {
        console.error("Error loading stats:", e);
    }
}

// ==========================================================================
// API: Email List & Filtering
// ==========================================================================
let startDateFilter = '';
let endDateFilter = '';
let colTimeout = null;

function debounceColFilters() {
    clearTimeout(colTimeout);
    colTimeout = setTimeout(() => {
        loadEmails(1);
    }, 500);
}

async function loadEmails(page = 1) {
    currentPage = page;
    const tbody = document.getElementById('emailsTableBody');
    tbody.innerHTML = `
        <tr>
            <td colspan="7" class="loading-state">
                <div class="spinner"></div>
                <p>جاري تحميل وتحديث البيانات...</p>
            </td>
        </tr>
    `;

    try {
        const exactDate = document.getElementById('colDateFilter') ? document.getElementById('colDateFilter').value : '';
        const partyFilter = document.getElementById('colPartyFilter') ? document.getElementById('colPartyFilter').value : '';
        let url = `/api/emails?tab=${currentTab}&query=${encodeURIComponent(searchQuery)}&start=${encodeURIComponent(startDateFilter)}&end=${encodeURIComponent(endDateFilter)}&exact_date=${encodeURIComponent(exactDate)}&party=${encodeURIComponent(partyFilter)}&page=${page}&limit=${currentLimit}`;
        const res = await fetch(url);
        const data = await res.json();

        let items = data.items || [];
        allEmailsCache = items;
        renderEmailsTable(items, (page - 1) * currentLimit);
        renderPagination({ total: data.total || items.length, total_pages: data.total_pages || 1 });
    } catch (e) {
        tbody.innerHTML = `
            <tr>
                <td colspan="7" class="loading-state" style="color:#ef4444;">
                    <i class="fa-solid fa-triangle-exclamation" style="font-size:2rem; margin-bottom:8px;"></i>
                    <p>تعذر تحميل البيانات. يرجى التأكد من تشغيل السيرفر أو بدء سحب البريد.</p>
                </td>
            </tr>
        `;
    }
}

function handleDateFilter() {
    startDateFilter = document.getElementById('dateFilterStart').value;
    endDateFilter = document.getElementById('dateFilterEnd').value;
    const clearBtn = document.getElementById('clearDateBtn');
    if (clearBtn) {
        clearBtn.style.display = (startDateFilter || endDateFilter) ? 'inline-block' : 'none';
    }
    loadEmails(1);
}

function clearDateFilter() {
    document.getElementById('dateFilterStart').value = '';
    document.getElementById('dateFilterEnd').value = '';
    startDateFilter = '';
    endDateFilter = '';
    document.getElementById('clearDateBtn').style.display = 'none';
    loadEmails(1);
}

function renderEmailsTable(items, startIdx) {
    const tbody = document.getElementById('emailsTableBody');
    if (!items || items.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="7" class="loading-state">
                    <i class="fa-regular fa-folder-open" style="font-size:2.2rem; color:var(--text-muted); margin-bottom:8px;"></i>
                    <p>لا توجد رسائل مطابقة لهذا التبويب أو البحث.</p>
                </td>
            </tr>
        `;
        return;
    }

    let rowsHtml = '';
    items.forEach((item, idx) => {
        const rowNum = startIdx + idx + 1;
        const isSent = item.folder === 'Sent' || !item.datetime_received;
        const statusCode = item.status_code || '';

        let statusBadgeClass = 'unreplied';
        let statusIcon = 'fa-clock';
        let statusText = item.status || 'غير محدد';

        if (statusCode === 'inbox_unreplied') {
            statusBadgeClass = 'unreplied';
            statusIcon = 'fa-triangle-exclamation';
            statusText = 'وارد معلق (لم يُرد عليه)';
        } else if (statusCode === 'sent_unreplied') {
            statusBadgeClass = 'sent-unreplied';
            statusIcon = 'fa-hourglass-start';
            statusText = 'صادر بانتظار ردهم';
        } else if (statusCode === 'inbox_replied') {
            statusBadgeClass = 'replied';
            statusIcon = 'fa-circle-check';
            statusText = 'وارد تم الرد عليه';
        } else if (statusCode === 'sent_replied') {
            statusBadgeClass = 'sent-replied';
            statusIcon = 'fa-reply-all';
            statusText = 'صادر ورد رده';
        }

        const dateFormatted = formatDateTime(item.datetime_received || item.datetime_sent);
        const partyLabel = isSent ? 'إلى:' : 'من:';
        const partyName = isSent
            ? (item.to_recipients_names && item.to_recipients_names.length ? item.to_recipients_names.join(', ') : 'إلى المستلمين')
            : (item.sender_name || item.sender_email || 'غير معروف');
        const partyEmail = isSent
            ? (item.to_recipients_emails ? item.to_recipients_emails.join(', ') : '')
            : (item.sender_email || '');

        const attCount = (item.attachments && item.attachments.length) || (item.attachment_names && item.attachment_names.length) || 0;
        const attBadge = attCount > 0
            ? `<span class="att-count-badge" title="${attCount} ملفات مرفقة"><i class="fa-solid fa-paperclip"></i> ${attCount}</span>`
            : `<span style="color:var(--text-muted); font-size:0.8rem;">-</span>`;

        rowsHtml += `
            <tr>
                <td style="text-align:center; font-weight:700; color:var(--text-muted);">${rowNum}</td>
                <td>
                    <span class="status-pill ${statusBadgeClass}">
                        <i class="fa-solid ${statusIcon}"></i>
                        ${statusText}
                    </span>
                </td>
                <td style="font-size:0.8rem; color:var(--text-secondary); white-space:nowrap;">
                    ${dateFormatted}
                </td>
                <td>
                    <div class="party-info">
                        <span class="party-name" title="${partyName}"><small style="color:var(--text-muted);">${partyLabel}</small> ${partyName}</span>
                        <span class="party-email" title="${partyEmail}">${partyEmail}</span>
                    </div>
                </td>
                <td>
                    <div class="subject-wrap">
                        <a class="email-subj-link" onclick="openEmailModal('${item.id}')">${escapeHtml(item.subject || '(بدون موضوع)')}</a>
                        <div class="email-summary-preview">${escapeHtml(item.summary || 'لا يوجد ملخص')}</div>
                    </div>
                </td>
                <td style="text-align:center;">
                    ${attBadge}
                </td>
                <td>
                    <div class="row-actions">
                        <button class="action-btn-sm" onclick="openEmailModal('${item.id}')" title="عرض التفاصيل والملخص والتكليفات">
                            <i class="fa-regular fa-eye"></i>
                        </button>
                        <button class="action-btn-sm" onclick="quickCompare('${item.id}')" title="مقارنة مع إيميل آخر">
                            <i class="fa-solid fa-code-compare"></i>
                        </button>
                    </div>
                </td>
            </tr>
        `;
    });

    tbody.innerHTML = rowsHtml;
}

function renderPagination(data) {
    const total = data.total || 0;
    const totalPages = data.total_pages || 1;
    const info = document.getElementById('paginationInfo');
    const currentText = document.getElementById('currentPageText');
    const prevBtn = document.getElementById('prevPageBtn');
    const nextPageBtn = document.getElementById('nextPageBtn');

    if (info) info.innerText = `عرض ${(total > 0 ? (currentPage - 1) * currentLimit + 1 : 0)} إلى ${Math.min(currentPage * currentLimit, total)} من إجمالي ${total} إيميل`;
    if (currentText) currentText.innerText = `صفحة ${currentPage} من ${totalPages}`;
    if (prevBtn) prevBtn.disabled = currentPage <= 1;
    if (nextPageBtn) nextPageBtn.disabled = currentPage >= totalPages;
}

function changePage(delta) {
    loadEmails(currentPage + delta);
}

// ==========================================================================
// Tabs & Search Handlers
// ==========================================================================
function switchTab(tab) {
    currentTab = tab;
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.tab === tab);
    });
    loadEmails(1);
}

function filterByTab(tab) {
    switchTab(tab);
    window.scrollTo({ top: 320, behavior: 'smooth' });
}

function handleSearch() {
    const input = document.getElementById('searchInput');
    const clearBtn = document.getElementById('clearSearchBtn');
    searchQuery = input.value.trim();
    if (clearBtn) clearBtn.style.display = searchQuery ? 'block' : 'none';

    clearTimeout(searchDebounceTimer);
    searchDebounceTimer = setTimeout(() => {
        loadEmails(1);
    }, 300);
}

function clearSearch() {
    const input = document.getElementById('searchInput');
    input.value = '';
    searchQuery = '';
    document.getElementById('clearSearchBtn').style.display = 'none';
    loadEmails(1);
}

// ==========================================================================
// Sync & Exchange Operations
// ==========================================================================
function toggleSyncMenu() {
    const menu = document.getElementById('syncMenu');
    menu.classList.toggle('show');
}

// Close sync menu on click outside
document.addEventListener('click', (e) => {
    const wrapper = document.querySelector('.sync-dropdown-wrapper');
    if (wrapper && !wrapper.contains(e.target)) {
        const menu = document.getElementById('syncMenu');
        if (menu) menu.classList.remove('show');
    }
});

function openSyncModal() {
    const menu = document.getElementById('syncMenu');
    if (menu) menu.classList.remove('show');
    const modal = document.getElementById('syncOptionsModal');
    if (modal) modal.style.display = 'flex';
}

function startSyncLastNDays(days) {
    const today = new Date();
    const past = new Date();
    past.setDate(today.getDate() - days);
    
    // Format to YYYY-MM-DD
    const start_date = past.toISOString().split('T')[0];
    const end_date = today.toISOString().split('T')[0];
    
    // Close the dropdown menu if it's open
    const menu = document.getElementById('syncMenu');
    if (menu) menu.classList.remove('show');
    
    // Call startSync with 0 limit to fetch everything within date range
    startSync(0, true, start_date, end_date, true);
}

async function executeCustomSync() {
    const startDate = document.getElementById('syncStartDate').value || null;
    const endDate = document.getElementById('syncEndDate').value || null;
    const limit = document.getElementById('syncLimitSelect').value;
    const mergeExisting = document.getElementById('syncMergeCheck').checked;
    const downloadFiles = document.getElementById('syncDownloadFilesCheck').checked;

    closeModal('syncOptionsModal');
    await startSync(limit, downloadFiles, startDate, endDate, mergeExisting);
}

async function startSync(limit = 50, download_files = true, start_date = null, end_date = null, merge_existing = true) {
    const menu = document.getElementById('syncMenu');
    if (menu) menu.classList.remove('show');

    try {
        const payload = {
            limit: (limit === '0' || limit === 0 || limit === 'all') ? 0 : parseInt(limit),
            download_files: download_files,
            start_date: start_date,
            end_date: end_date,
            merge_existing: merge_existing
        };

        const res = await fetch('/api/sync', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await res.json();

        if (res.ok) {
            let label = payload.limit === 0 ? 'كافة الرسائل' : `أحدث ${payload.limit} إيميل`;
            if (start_date || end_date) {
                label += ` للفترة (${start_date || 'البداية'} إلى ${end_date || 'اليوم'})`;
            }
            showToast(`تم بدء سحب ${label}...`, 'fa-arrows-rotate');
            pollSyncProgress();
        } else {
            showToast(data.message || 'المزامنة قيد التشغيل بالفعل', 'fa-triangle-exclamation');
        }
    } catch (e) {
        showToast('تعذر بدء المزامنة. تأكد من الاتصال بالشبكة.', 'fa-triangle-exclamation');
    }
}

function pollSyncProgress() {
    const banner = document.getElementById('syncProgressBanner');
    const syncIcon = document.getElementById('syncIcon');
    if (banner) banner.style.display = 'block';
    if (syncIcon) syncIcon.classList.add('fa-spin');

    clearInterval(syncPollingTimer);
    syncPollingTimer = setInterval(async () => {
        try {
            const res = await fetch('/api/sync-status');
            const data = await res.json();

            const stepText = document.getElementById('syncStepText');
            const bar = document.getElementById('syncProgressBar');
            const percentText = document.getElementById('syncPercentageText');

            if (stepText) stepText.innerText = data.current_step || 'جاري المعالجة...';
            if (bar) bar.style.width = `${data.percentage || 5}%`;
            if (percentText) percentText.innerText = `${data.percentage || 5}%`;

            if (!data.is_running) {
                clearInterval(syncPollingTimer);
                if (syncIcon) syncIcon.classList.remove('fa-spin');

                if (data.success) {
                    showToast('تم اكتمال سحب البريد وتحديث ملف الإكسيل بنجاح!', 'fa-circle-check');
                    loadStats();
                    loadEmails(currentPage);
                    setTimeout(() => {
                        if (banner) banner.style.display = 'none';
                    }, 3000);
                } else if (data.last_error) {
                    showToast(`حدث خطأ: ${data.last_error}`, 'fa-triangle-exclamation');
                }
            }
        } catch (e) {
            console.error("Polling error:", e);
        }
    }, 1200);
}

async function checkSyncStatus() {
    try {
        const res = await fetch('/api/sync-status');
        const data = await res.json();
        if (data.is_running) {
            pollSyncProgress();
        }
    } catch (e) { }
}

// ==========================================================================
// Local Desktop Integrations (Excel, Folders, Files)
// ==========================================================================
async function openExcelDesktop() {
    try {
        showToast('جاري فتح وتحميل ملف الإكسيل...', 'fa-file-excel');
        fetch('/api/open-excel', { method: 'POST' }).catch(() => { });
        window.location.href = '/api/export-excel';
    } catch (e) {
        window.location.href = '/api/export-excel';
    }
}

async function openAttachmentsFolder() {
    try {
        showToast('جاري فتح مجلد المرفقات...', 'fa-folder-open');
        const res = await fetch('/api/open-folder', { method: 'POST' });
        const data = await res.json();
        if (!res.ok) showToast(data.error || 'تعذر فتح المجلد', 'fa-triangle-exclamation');
    } catch (e) {
        showToast('تعذر فتح المجلد', 'fa-triangle-exclamation');
    }
}

async function openLocalFile(filePath) {
    if (!filePath) {
        showToast('المسار المحلي للملف غير متوفر', 'fa-triangle-exclamation');
        return;
    }
    try {
        showToast('جاري فتح الملف...', 'fa-file');
        const res = await fetch('/api/open-file', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ file_path: filePath })
        });
        const data = await res.json();
        if (!res.ok) showToast(data.error || 'تعذر فتح الملف', 'fa-triangle-exclamation');
    } catch (e) {
        showToast('تعذر فتح الملف', 'fa-triangle-exclamation');
    }
}

// ==========================================================================
// Modal: Email Detail View
// ==========================================================================
async function openEmailModal(emailId) {
    try {
        let item = allEmailsCache.find(e => String(e.id) === String(emailId));
        if (!item) {
            const res = await fetch(`/api/email?id=${encodeURIComponent(emailId)}`);
            item = await res.json();
        }
        if (!item || item.error) {
            showToast('تعذر استرجاع تفاصيل الرسالة', 'fa-triangle-exclamation');
            return;
        }

        document.getElementById('modalSubject').innerText = item.subject || '(بدون موضوع)';
        document.getElementById('modalSender').innerText = `${item.sender_name || ''} <${item.sender_email || ''}>`;
        document.getElementById('modalDate').innerText = formatDateTime(item.datetime_received || item.datetime_sent);

        // Status Badge
        const badge = document.getElementById('modalStatusBadge');
        const statusCode = item.status_code || 'unreplied';
        badge.className = `modal-status-badge status-pill ${statusCode}`;
        badge.innerText = item.status || 'بانتظار الرد';

        // Replied Info
        const repliedByRow = document.getElementById('modalRepliedByRow');
        const replyDateRow = document.getElementById('modalReplyDateRow');
        if (item.replied_by || item.reply_datetime) {
            repliedByRow.style.display = 'block';
            replyDateRow.style.display = 'block';
            document.getElementById('modalRepliedBy').innerText = item.replied_by || 'المكتب الفني';
            document.getElementById('modalReplyDate').innerText = formatDateTime(item.reply_datetime);
        } else {
            repliedByRow.style.display = 'none';
            replyDateRow.style.display = 'none';
        }

        // Summary & Actions
        document.getElementById('modalSummary').innerText = item.summary || 'لا يوجد ملخص';
        const actionsDiv = document.getElementById('modalActionsList');
        if (item.actions && item.actions.length > 0) {
            actionsDiv.innerHTML = item.actions.map(act => `<span class="badge" style="background:#0284c7; padding:4px 10px; font-size:0.8rem;"><i class="fa-solid fa-thumbtack"></i> ${escapeHtml(act)}</span>`).join(' ');
            actionsDiv.style.display = 'flex';
        } else {
            actionsDiv.innerHTML = '';
            actionsDiv.style.display = 'none';
        }

        // Attachments
        const attSec = document.getElementById('modalAttachmentsSection');
        const attList = document.getElementById('modalAttachmentsList');
        const attCountEl = document.getElementById('modalAttachmentsCount');
        const attachments = item.attachments || [];

        if (attachments.length > 0) {
            attSec.style.display = 'block';
            attCountEl.innerText = attachments.length;
            attList.innerHTML = attachments.map(att => `
                <div class="attachment-card">
                    <div class="att-meta">
                        <span class="att-name" title="${escapeHtml(att.name)}"><i class="fa-regular fa-file"></i> ${escapeHtml(att.name)}</span>
                        <span class="att-size">${Math.round((att.size_bytes || 0) / 1024)} KB</span>
                    </div>
                    ${att.file_path ? `<button class="btn-open-file" onclick="openLocalFile('${escapeHtml(att.file_path)}')"><i class="fa-solid fa-arrow-up-right-from-square"></i> فتح</button>` : ''}
                </div>
            `).join('');
        } else {
            attSec.style.display = 'none';
        }

        // Body Content
        document.getElementById('modalBody').innerText = item.clean_body || item.body || '(لا يوجد نص)';

        document.getElementById('emailDetailModal').style.display = 'flex';
    } catch (e) {
        showToast('حدث خطأ أثناء فتح الرسالة', 'fa-triangle-exclamation');
    }
}

// ==========================================================================
// Modal: Comparator Tool
// ==========================================================================
function openCompareModal() {
    const modal = document.getElementById('compareModal');
    const selectA = document.getElementById('compareSelectA');
    const selectB = document.getElementById('compareSelectB');

    // Populate selects from cache or currently loaded emails
    if (allEmailsCache.length > 0) {
        const optionsHtml = allEmailsCache.map(e => `
            <option value="${e.id}">${escapeHtml(e.subject || 'بدون موضوع')} (${escapeHtml(e.sender_name || e.sender_email || 'غير معروف')})</option>
        `).join('');

        selectA.innerHTML = optionsHtml;
        selectB.innerHTML = optionsHtml;

        if (allEmailsCache.length > 1) {
            selectB.selectedIndex = 1;
        }
        runComparison();
    }

    modal.style.display = 'flex';
}

function quickCompare(emailId) {
    openCompareModal();
    const selectA = document.getElementById('compareSelectA');
    if (selectA) {
        selectA.value = emailId;
        runComparison();
    }
}

async function runComparison() {
    const idA = document.getElementById('compareSelectA').value;
    const idB = document.getElementById('compareSelectB').value;

    if (!idA || !idB) return;

    try {
        const res = await fetch('/api/compare', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id_a: idA, id_b: idB })
        });
        const data = await res.json();

        if (res.ok) {
            document.getElementById('compareResultContainer').style.display = 'block';
            document.getElementById('simScore').innerText = `${data.similarity_score_pct}%`;

            // Render Email A
            document.getElementById('compSubjA').innerText = data.email_a.subject;
            document.getElementById('compMetaA').innerHTML = `<strong>المرسل:</strong> ${data.email_a.sender} | <strong>التاريخ:</strong> ${formatDateTime(data.email_a.datetime)}`;
            document.getElementById('compSummA').innerText = data.email_a.summary;
            document.getElementById('compAttA').innerHTML = `<strong>المرفقات (${data.email_a.attachments_count}):</strong> ${data.email_a.attachments.join(', ') || 'لا يوجد'}`;
            document.getElementById('compBodyA').innerText = data.email_a.body;

            // Render Email B
            document.getElementById('compSubjB').innerText = data.email_b.subject;
            document.getElementById('compMetaB').innerHTML = `<strong>المرسل:</strong> ${data.email_b.sender} | <strong>التاريخ:</strong> ${formatDateTime(data.email_b.datetime)}`;
            document.getElementById('compSummB').innerText = data.email_b.summary;
            document.getElementById('compAttB').innerHTML = `<strong>المرفقات (${data.email_b.attachments_count}):</strong> ${data.email_b.attachments.join(', ') || 'لا يوجد'}`;
            document.getElementById('compBodyB').innerText = data.email_b.body;
        }
    } catch (e) {
        console.error("Comparison error:", e);
    }
}

// ==========================================================================
// Modal Helpers
// ==========================================================================
function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) modal.style.display = 'none';
}

function closeModalOnBackdrop(event, modalId) {
    if (event.target.id === modalId) {
        closeModal(modalId);
    }
}

// ==========================================================================
// Utilities
// ==========================================================================
function formatDateTime(isoString) {
    if (!isoString) return '';
    try {
        const d = new Date(isoString);
        return d.toLocaleDateString('ar-EG', {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    } catch (e) {
        return isoString;
    }
}

function escapeHtml(text) {
    if (!text) return '';
    return String(text)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}
