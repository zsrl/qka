/**
 * QKA Quantitative Workstation — Frontend Application Logic
 * High-efficiency interactions, Command Palette (⌘K), Toast notifications, and Stock Pool Engine
 */

let marketChart = null;
let backtestChart = null;
let drawdownChart = null;
let simulateChart = null;
let presetStrategies = [];

// Stock Pool State
let currentPoolLevel = "all";
let currentPoolCategory = "";
let currentPoolKeyword = "";
let poolSearchDebounce = null;
let editingStockSymbol = null;
let cachedPoolStocks = [];
let allPoolStocksMaster = [];

document.addEventListener("DOMContentLoaded", () => {
    initTabs();
    initSystemStatus();
    initPresets();
    initSettings();
    initEventListeners();
    initStockPool();
    initCommandPalette();
    initGlobalShortcuts();
});

// ================= Non-Blocking Toast Notification =================
window.showToast = function(message, type = "info", duration = 3200) {
    const container = document.getElementById("toast-container");
    if (!container) return;

    const item = document.createElement("div");
    item.className = `toast-item ${type}`;

    const iconMap = {
        success: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>`,
        error: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#f43f5e" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>`,
        info: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#38bdf8" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>`
    };

    item.innerHTML = `
        <span style="display:flex; align-items:center; flex-shrink:0;">${iconMap[type] || iconMap.info}</span>
        <span style="line-height:1.4;">${escapeHtml(message)}</span>
    `;

    container.appendChild(item);

    setTimeout(() => {
        item.style.opacity = "0";
        item.style.transform = "translateX(16px)";
        item.style.transition = "all 0.2s ease";
        setTimeout(() => item.remove(), 200);
    }, duration);
};

// ================= Router & Tab Navigation =================
const ROUTE_MAP = {
    "/": "tab-overview",
    "/overview": "tab-overview",
    "/pool": "tab-pool",
    "/stock-pool": "tab-pool",
    "/strategy": "tab-strategy",
    "/market": "tab-market",
    "/simulate": "tab-simulate",
    "/ai": "tab-ai",
    "/settings": "tab-settings"
};

const TAB_TO_ROUTE = {
    "tab-overview": "/overview",
    "tab-pool": "/pool",
    "tab-strategy": "/strategy",
    "tab-market": "/market",
    "tab-simulate": "/simulate",
    "tab-ai": "/ai",
    "tab-settings": "/settings"
};

const TAB_META = {
    "tab-overview": { title: "总览大屏", sub: "QKA 核心运行状态与核心盯盘焦点", docTitle: "总览大屏 - QKA 控制台" },
    "tab-pool": { title: "股票池管理", sub: "选赛道 · 做减法 · 精选股 — 三级池化与盯盘风控", docTitle: "股票池管理 - QKA 控制台" },
    "tab-strategy": { title: "策略开发与回测", sub: "在线编写、A股拟真撮合与 13 项量化绩效体检", docTitle: "策略开发与回测 - QKA 控制台" },
    "tab-market": { title: "行情与指标探索", sub: "全市场股票 / ETF / 转债 K 线、均线系统与量价分析", docTitle: "行情与指标探索 - QKA 控制台" },
    "tab-simulate": { title: "模拟标的生成器", sub: "基于奥恩斯坦-乌伦贝克随机过程现场合成行情", docTitle: "模拟标的生成器 - QKA 控制台" },
    "tab-ai": { title: "AI 策略工坊", sub: "AI Agent 技能标准化规范与量化 Prompt 模板", docTitle: "AI 策略工坊 - QKA 控制台" },
    "tab-settings": { title: "系统与参数设置", sub: "全局数据源、佣金费率模型与本地磁盘缓存管理", docTitle: "系统与参数设置 - QKA 控制台" }
};

function resolveTabFromUrl() {
    const pathname = window.location.pathname.replace(/\/+$/, '') || "/";
    return ROUTE_MAP[pathname] || "tab-overview";
}

window.switchTab = function(targetId, updateHistory = true) {
    const navItems = document.querySelectorAll(".nav-item[data-tab]");
    const contents = document.querySelectorAll(".tab-content");
    const titleEl = document.getElementById("page-title");
    const subEl = document.getElementById("page-subtitle");

    navItems.forEach(i => {
        if (i.getAttribute("data-tab") === targetId) {
            i.classList.add("active");
        } else {
            i.classList.remove("active");
        }
    });

    contents.forEach(c => {
        if (c.id === targetId) {
            c.classList.add("active");
        } else {
            c.classList.remove("active");
        }
    });

    if (TAB_META[targetId]) {
        if (titleEl) titleEl.textContent = TAB_META[targetId].title;
        if (subEl) subEl.textContent = TAB_META[targetId].sub;
        document.title = TAB_META[targetId].docTitle;
    }

    if (updateHistory) {
        const route = TAB_TO_ROUTE[targetId] || "/";
        if (window.location.pathname !== route) {
            window.history.pushState({ tab: targetId }, "", route);
        }
    }

    setTimeout(() => {
        if (marketChart) marketChart.resize();
        if (backtestChart) backtestChart.resize();
        if (drawdownChart) drawdownChart.resize();
        if (simulateChart) simulateChart.resize();
    }, 80);
};

function initTabs() {
    const navItems = document.querySelectorAll(".nav-item[data-tab]");

    navItems.forEach(item => {
        item.addEventListener("click", () => {
            const targetId = item.getAttribute("data-tab");
            switchTab(targetId, true);
        });
    });

    window.addEventListener("popstate", (e) => {
        const tab = (e.state && e.state.tab) || resolveTabFromUrl();
        switchTab(tab, false);
    });

    const initialTab = resolveTabFromUrl();
    switchTab(initialTab, false);
}

// ================= Global Keyboard Shortcuts & Command Palette (⌘K) =================
function initGlobalShortcuts() {
    const tabOrder = [
        "tab-overview",
        "tab-pool",
        "tab-strategy",
        "tab-market",
        "tab-simulate",
        "tab-ai",
        "tab-settings"
    ];

    document.addEventListener("keydown", (e) => {
        const tag = (e.target && e.target.tagName) ? e.target.tagName.toLowerCase() : "";
        const isInput = tag === "input" || tag === "textarea" || tag === "select" || (e.target && e.target.isContentEditable);

        // ⌘K or Ctrl+K -> Toggle Command Palette
        if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
            e.preventDefault();
            toggleCommandPalette();
            return;
        }

        // Escape -> Close any open modal
        if (e.key === "Escape") {
            document.querySelectorAll(".modal-overlay.active").forEach(m => m.classList.remove("active"));
            return;
        }

        // ⌘Enter / Ctrl+Enter -> Run backtest if in strategy tab
        if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
            const activeTab = document.querySelector(".tab-content.active");
            if (activeTab && activeTab.id === "tab-strategy") {
                e.preventDefault();
                runBacktest();
            }
            return;
        }

        // Number keys 1-7 when not typing in an input
        if (!isInput && !e.metaKey && !e.ctrlKey && !e.altKey) {
            const num = parseInt(e.key, 10);
            if (num >= 1 && num <= 7) {
                const targetTab = tabOrder[num - 1];
                if (targetTab) {
                    e.preventDefault();
                    switchTab(targetTab, true);
                }
            }
        }
    });
}

function initCommandPalette() {
    const btnOpen = document.getElementById("btn-open-cmd");
    const modalCmd = document.getElementById("modal-cmd");
    const inputEl = document.getElementById("cmd-palette-input");

    if (btnOpen) {
        btnOpen.addEventListener("click", () => toggleCommandPalette(true));
    }
    if (modalCmd) {
        modalCmd.addEventListener("click", (e) => {
            if (e.target === modalCmd) modalCmd.classList.remove("active");
        });
    }
    if (inputEl) {
        inputEl.addEventListener("input", () => renderCommandPaletteResults(inputEl.value.trim()));
        inputEl.addEventListener("keydown", (e) => {
            if (e.key === "Enter") {
                const firstItem = document.querySelector("#cmd-palette-results .cmd-item");
                if (firstItem) firstItem.click();
            }
        });
    }
}

function toggleCommandPalette(forceOpen) {
    const modalCmd = document.getElementById("modal-cmd");
    const inputEl = document.getElementById("cmd-palette-input");
    if (!modalCmd) return;

    const shouldOpen = forceOpen !== undefined ? forceOpen : !modalCmd.classList.contains("active");
    if (shouldOpen) {
        modalCmd.classList.add("active");
        if (inputEl) {
            inputEl.value = "";
            renderCommandPaletteResults("");
            setTimeout(() => inputEl.focus(), 30);
        }
    } else {
        modalCmd.classList.remove("active");
    }
}

function renderCommandPaletteResults(query) {
    const container = document.getElementById("cmd-palette-results");
    if (!container) return;

    const q = query.toLowerCase();
    const commands = [
        { title: "进入 股票池管理 (选赛道·做减法·精选股)", tag: "导航 2", action: () => switchTab("tab-pool") },
        { title: "添加新股票至股票池", tag: "股票池", action: () => { switchTab("tab-pool"); document.getElementById("btn-open-add-stock").click(); } },
        { title: "券商研报 / 微博笔记批量智能导入", tag: "股票池", action: () => { switchTab("tab-pool"); document.getElementById("btn-open-import").click(); } },
        { title: "载入交易股票池标的并启动策略回测", tag: "回测联动", action: () => handleExportTradingPoolToBacktest() },
        { title: "进入 策略开发与回测", tag: "导航 3", action: () => switchTab("tab-strategy") },
        { title: "进入 行情与指标探索 (K线复盘)", tag: "导航 4", action: () => switchTab("tab-market") },
        { title: "进入 模拟标的生成器", tag: "导航 5", action: () => switchTab("tab-simulate") },
        { title: "进入 系统与参数设置", tag: "导航 7", action: () => switchTab("tab-settings") }
    ];

    const stockItems = (allPoolStocksMaster.length ? allPoolStocksMaster : cachedPoolStocks).map(s => ({
        title: `${s.name} (${s.symbol}) — ${(s.categories || []).join("/")} · 跳转K线看盘`,
        tag: s.pool_level === "trading" ? "交易池" : (s.pool_level === "selected" ? "精选池" : "基础池"),
        action: () => inspectStockInMarket(s.symbol, s.name)
    }));

    const allItems = [...stockItems, ...commands].filter(item =>
        !q || item.title.toLowerCase().includes(q) || item.tag.toLowerCase().includes(q)
    );

    if (allItems.length === 0) {
        container.innerHTML = `<div style="padding: 16px; text-align: center; color: var(--text-dim); font-size: 0.8rem;">无匹配指令或标的，按 Enter 可直接查询行情</div>`;
        return;
    }

    container.innerHTML = allItems.slice(0, 10).map((item, idx) => `
        <div class="cmd-item ${idx === 0 ? 'selected' : ''}" data-cmd-idx="${idx}">
            <div class="cmd-item-left">
                <span>${escapeHtml(item.title)}</span>
            </div>
            <span class="cmd-item-tag">${escapeHtml(item.tag)}</span>
        </div>
    `).join("");

    container.querySelectorAll(".cmd-item").forEach((el, idx) => {
        el.addEventListener("click", () => {
            toggleCommandPalette(false);
            allItems[idx].action();
        });
    });
}

// ================= System & Status =================
async function initSystemStatus() {
    try {
        const res = await fetch("/api/status");
        const json = await res.json();
        if (json.success && json.data) {
            const d = json.data;
            document.getElementById("stat-qka-version").textContent = d.qka_version;
            document.getElementById("stat-python-version").textContent = d.python_version;
            document.getElementById("stat-cache-size").textContent = `${d.cache_size_mb} MB`;
            document.getElementById("stat-cache-files").textContent = `${d.cache_files_count} 个文件`;
            document.getElementById("stat-cache-path").textContent = d.cache_dir;

            const f2 = document.getElementById("stat-cache-files-2");
            const s2 = document.getElementById("stat-cache-size-2");
            if (f2) f2.textContent = d.cache_files_count;
            if (s2) s2.textContent = `${d.cache_size_mb} MB`;

            const modeBadge = document.getElementById("stat-core-mode");
            if (d.has_qka_core) {
                modeBadge.textContent = "原生引擎就绪";
            } else {
                modeBadge.textContent = "仿真引擎就绪";
            }
        }
    } catch (e) {
        console.error("加载系统状态失败:", e);
    }
}

// ================= Global Settings & Config =================
async function initSettings() {
    try {
        const res = await fetch("/api/config");
        const json = await res.json();
        if (json.success && json.data) {
            populateSettingsForm(json.data);
            const pathEl = document.getElementById("cfg-file-path");
            if (pathEl && json.config_path) {
                pathEl.textContent = json.config_path;
            }
        }
    } catch (e) {
        console.error("加载全局配置失败:", e);
    }
}

function populateSettingsForm(cfg) {
    if (!cfg) return;
    const data = cfg.data || {};
    const broker = cfg.broker || {};
    const backtest = cfg.backtest || {};

    if (data.source && document.getElementById("cfg-data-source")) {
        document.getElementById("cfg-data-source").value = data.source;
    }
    if (data.adjust && document.getElementById("cfg-data-adjust")) {
        document.getElementById("cfg-data-adjust").value = data.adjust;
    }
    if (data.period && document.getElementById("cfg-data-period")) {
        document.getElementById("cfg-data-period").value = data.period;
    }
    if (data.warmup !== undefined && document.getElementById("cfg-data-warmup")) {
        document.getElementById("cfg-data-warmup").value = data.warmup;
    }
    if (data.tickflow_api_key !== undefined && document.getElementById("cfg-tickflow-key")) {
        document.getElementById("cfg-tickflow-key").value = data.tickflow_api_key;
    }
    if (data.tdx_root !== undefined && document.getElementById("cfg-tdx-root")) {
        document.getElementById("cfg-tdx-root").value = data.tdx_root;
    }
    if (data.datadir !== undefined && document.getElementById("cfg-data-datadir")) {
        document.getElementById("cfg-data-datadir").value = data.datadir;
    }
    const factorCacheEl = document.getElementById("cfg-factor-cache");
    if (factorCacheEl) factorCacheEl.checked = !!data.factor_cache;
    const fillSuspendedEl = document.getElementById("cfg-fill-suspended");
    if (fillSuspendedEl) fillSuspendedEl.checked = !!data.fill_suspended;

    if (broker.commission_rate !== undefined && document.getElementById("cfg-broker-commission")) {
        document.getElementById("cfg-broker-commission").value = broker.commission_rate;
    }
    if (broker.min_commission !== undefined && document.getElementById("cfg-broker-min-commission")) {
        document.getElementById("cfg-broker-min-commission").value = broker.min_commission;
    }
    if (broker.stamp_duty_rate !== undefined && document.getElementById("cfg-broker-stamp-duty")) {
        document.getElementById("cfg-broker-stamp-duty").value = broker.stamp_duty_rate;
    }
    if (broker.slippage !== undefined && document.getElementById("cfg-broker-slippage")) {
        document.getElementById("cfg-broker-slippage").value = broker.slippage;
    }
    if (broker.initial_cash !== undefined && document.getElementById("cfg-broker-cash")) {
        document.getElementById("cfg-broker-cash").value = broker.initial_cash;
    }

    if (backtest.benchmark && document.getElementById("cfg-backtest-benchmark")) {
        document.getElementById("cfg-backtest-benchmark").value = backtest.benchmark;
    }
    if (backtest.risk_free_rate !== undefined && document.getElementById("cfg-backtest-rf")) {
        document.getElementById("cfg-backtest-rf").value = backtest.risk_free_rate;
    }
    if (backtest.periods_per_year !== undefined && document.getElementById("cfg-backtest-periods")) {
        document.getElementById("cfg-backtest-periods").value = backtest.periods_per_year;
    }
}

function collectSettingsFromForm() {
    return {
        data: {
            source: document.getElementById("cfg-data-source").value,
            adjust: document.getElementById("cfg-data-adjust").value,
            period: document.getElementById("cfg-data-period").value,
            warmup: parseInt(document.getElementById("cfg-data-warmup").value) || 20,
            tickflow_api_key: document.getElementById("cfg-tickflow-key").value.trim(),
            tdx_root: document.getElementById("cfg-tdx-root").value.trim(),
            datadir: document.getElementById("cfg-data-datadir").value.trim(),
            factor_cache: document.getElementById("cfg-factor-cache").checked,
            fill_suspended: document.getElementById("cfg-fill-suspended").checked
        },
        broker: {
            commission_rate: parseFloat(document.getElementById("cfg-broker-commission").value) || 0.00025,
            min_commission: parseFloat(document.getElementById("cfg-broker-min-commission").value) || 5.0,
            stamp_duty_rate: parseFloat(document.getElementById("cfg-broker-stamp-duty").value) || 0.0005,
            slippage: parseFloat(document.getElementById("cfg-broker-slippage").value) || 0.001,
            initial_cash: parseFloat(document.getElementById("cfg-broker-cash").value) || 200000.0
        },
        backtest: {
            benchmark: document.getElementById("cfg-backtest-benchmark").value.trim() || "000300.SH",
            risk_free_rate: parseFloat(document.getElementById("cfg-backtest-rf").value) || 0.03,
            periods_per_year: parseInt(document.getElementById("cfg-backtest-periods").value) || 252
        },
        server: {
            port: 15002,
            host: "0.0.0.0",
            auto_open_browser: true
        }
    };
}

// ================= Preset Strategies =================
async function initPresets() {
    try {
        const res = await fetch("/api/presets");
        const json = await res.json();
        if (json.success && json.data) {
            presetStrategies = json.data;
            const select = document.getElementById("preset-select");
            select.innerHTML = '<option value="">-- 选择预置经典策略 --</option>';

            presetStrategies.forEach(s => {
                const opt = document.createElement("option");
                opt.value = s.id;
                opt.textContent = `${s.name} (${s.symbols.join(", ")})`;
                select.appendChild(opt);
            });

            if (presetStrategies.length > 0) {
                loadPreset(presetStrategies[0].id);
                select.value = presetStrategies[0].id;
            }
        }
    } catch (e) {
        console.error("加载预置策略失败:", e);
    }
}

function loadPreset(strategyId) {
    const strat = presetStrategies.find(s => s.id === strategyId);
    if (!strat) return;

    document.getElementById("strategy-code").value = strat.code.trim();
    document.getElementById("bt-symbols").value = strat.symbols.join(", ");
    document.getElementById("bt-cash").value = strat.cash || 200000;
    document.getElementById("bt-benchmark").value = strat.benchmark || "000300.SH";
    document.getElementById("bt-warmup").value = strat.warmup || 20;

    const descEl = document.getElementById("preset-description");
    if (descEl) descEl.textContent = strat.description;
}

// ================= Event Listeners =================
function initEventListeners() {
    const presetSelect = document.getElementById("preset-select");
    presetSelect.addEventListener("change", (e) => {
        if (e.target.value) {
            loadPreset(e.target.value);
            showToast("已切换策略模板", "info");
        }
    });

    document.getElementById("btn-fetch-market").addEventListener("click", () => {
        fetchMarketData();
    });

    document.getElementById("btn-run-backtest").addEventListener("click", () => {
        runBacktest();
    });

    document.getElementById("btn-run-simulate").addEventListener("click", () => {
        runSimulate();
    });

    const btnClearCache = document.getElementById("btn-clear-cache");
    if (btnClearCache) {
        btnClearCache.addEventListener("click", async () => {
            if (!confirm("确定要清空本地所有已缓存的行情数据吗？")) return;
            try {
                const res = await fetch("/api/cache/clear", { method: "POST" });
                const json = await res.json();
                if (json.success) {
                    showToast(`成功清理了 ${json.cleared_files} 个缓存文件`, "success");
                    initSystemStatus();
                }
            } catch (e) {
                showToast("清理失败: " + e.message, "error");
            }
        });
    }

    const btnSaveConfig = document.getElementById("btn-save-config");
    if (btnSaveConfig) {
        btnSaveConfig.addEventListener("click", async () => {
            const cfg = collectSettingsFromForm();
            btnSaveConfig.textContent = "保存中...";
            btnSaveConfig.disabled = true;
            try {
                const res = await fetch("/api/config", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(cfg)
                });
                const json = await res.json();
                if (json.success) {
                    showToast(json.msg || "全局配置已保存生效", "success");
                    initSystemStatus();
                } else {
                    showToast("保存失败: " + (json.error || "未知原因"), "error");
                }
            } catch (e) {
                showToast("保存失败: " + e.message, "error");
            } finally {
                btnSaveConfig.textContent = "保存全局配置";
                btnSaveConfig.disabled = false;
            }
        });
    }

    const btnResetConfig = document.getElementById("btn-reset-config");
    if (btnResetConfig) {
        btnResetConfig.addEventListener("click", async () => {
            if (!confirm("确定要将所有配置项恢复为出厂默认值吗？")) return;
            try {
                const res = await fetch("/api/config/reset", { method: "POST" });
                const json = await res.json();
                if (json.success) {
                    populateSettingsForm(json.data);
                    showToast("已恢复出厂默认配置", "info");
                }
            } catch (e) {
                showToast("重置失败: " + e.message, "error");
            }
        });
    }

    const btnTestTf = document.getElementById("btn-test-tickflow");
    if (btnTestTf) {
        btnTestTf.addEventListener("click", async () => {
            const key = document.getElementById("cfg-tickflow-key").value.trim();
            const msgEl = document.getElementById("tickflow-test-msg");
            msgEl.style.display = "block";
            msgEl.style.color = "var(--text-dim)";
            msgEl.textContent = "正在探测 TickFlow 接口连通性...";

            try {
                const res = await fetch("/api/config/test_tickflow", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ api_key: key })
                });
                const json = await res.json();
                if (json.success) {
                    msgEl.style.color = "var(--color-emerald)";
                    msgEl.textContent = `✓ ${json.msg} [${json.mode}]`;
                } else {
                    msgEl.style.color = "var(--color-up)";
                    msgEl.textContent = `✕ ${json.error}`;
                }
            } catch (e) {
                msgEl.style.color = "var(--color-up)";
                msgEl.textContent = `✕ 网络异常: ${e.message}`;
            }
        });
    }

    const btnDetectTdx = document.getElementById("btn-detect-tdx");
    if (btnDetectTdx) {
        btnDetectTdx.addEventListener("click", async () => {
            const msgEl = document.getElementById("tdx-detect-msg");
            msgEl.textContent = "正在扫描系统注册表与环境变量...";
            try {
                const res = await fetch("/api/config/detect_tdx");
                const json = await res.json();
                if (json.success && json.data && json.data.root) {
                    document.getElementById("cfg-tdx-root").value = json.data.root;
                    msgEl.style.color = "var(--color-emerald)";
                    msgEl.textContent = `✓ 识别成功 [来源: ${json.data.source}]: ${json.data.root}`;
                } else {
                    msgEl.style.color = "var(--color-warning)";
                    msgEl.textContent = "未检测到通达信 TQ 版安装目录，请手动填写。";
                }
            } catch (e) {
                msgEl.textContent = `✕ 探测出错: ${e.message}`;
            }
        });
    }

    document.querySelectorAll(".preset-benchmark-pill").forEach(pill => {
        pill.addEventListener("click", () => {
            const code = pill.getAttribute("data-code");
            if (code) {
                document.getElementById("cfg-backtest-benchmark").value = code;
                showToast(`基准已设为 ${code}`, "info");
            }
        });
    });

    fetchMarketData();
    runSimulate();

    window.addEventListener("resize", () => {
        if (marketChart) marketChart.resize();
        if (backtestChart) backtestChart.resize();
        if (drawdownChart) drawdownChart.resize();
        if (simulateChart) simulateChart.resize();
    });
}

// ================= 1. Market Data Fetch & Chart (A-Share Red=Up, Green=Down) =================
window.inspectStockInMarket = function(symbol, name) {
    const input = document.getElementById("market-symbol");
    if (input) input.value = symbol;
    switchTab("tab-market", true);
    fetchMarketData();
    showToast(`正在加载 ${name ? name + ' (' + symbol + ')' : symbol} 日K线行情`, "info");
};

async function fetchMarketData() {
    const symbol = document.getElementById("market-symbol").value.trim() || "300308.SZ";
    const source = document.getElementById("market-source").value;
    const adjust = document.getElementById("market-adjust").value;
    const startDate = document.getElementById("market-start").value || "2023-01-01";
    const endDate = document.getElementById("market-end").value || "2024-12-31";

    const btn = document.getElementById("btn-fetch-market");
    btn.textContent = "加载中...";
    btn.disabled = true;

    try {
        const query = new URLSearchParams({
            symbol, source, adjust, start_date: startDate, end_date: endDate
        });
        const res = await fetch(`/api/market?${query.toString()}`);
        const json = await res.json();

        if (json.success && json.data) {
            renderMarketChart(json.data);
            renderMarketTable(json.data);
        } else {
            showToast("获取行情失败: " + (json.error || "未知原因"), "error");
        }
    } catch (e) {
        showToast("网络请求失败: " + e.message, "error");
    } finally {
        btn.textContent = "查询行情";
        btn.disabled = false;
    }
}

function renderMarketChart(data) {
    const chartDom = document.getElementById("market-chart");
    if (!chartDom) return;

    if (!marketChart) {
        marketChart = echarts.init(chartDom, "dark");
    }

    const option = {
        backgroundColor: "transparent",
        tooltip: {
            trigger: "axis",
            axisPointer: { type: "cross" },
            borderWidth: 1,
            borderColor: "rgba(255,255,255,0.12)",
            backgroundColor: "rgba(12, 14, 20, 0.92)"
        },
        legend: {
            data: ["日K线", "MA5", "MA20", "成交量"],
            top: 6,
            textStyle: { color: "#94a3b8", fontSize: 12 }
        },
        grid: [
            { left: "4%", right: "2.5%", top: 42, height: "62%" },
            { left: "4%", right: "2.5%", top: "73%", height: "18%" }
        ],
        xAxis: [
            {
                type: "category",
                data: data.dates,
                scale: true,
                boundaryGap: false,
                axisLine: { lineStyle: { color: "rgba(255,255,255,0.12)" } },
                splitLine: { show: false }
            },
            {
                type: "category",
                gridIndex: 1,
                data: data.dates,
                axisLabel: { show: false },
                axisLine: { lineStyle: { color: "rgba(255,255,255,0.12)" } }
            }
        ],
        yAxis: [
            {
                scale: true,
                splitLine: { lineStyle: { color: "rgba(255, 255, 255, 0.04)" } },
                axisLabel: { color: "#94a3b8" }
            },
            {
                gridIndex: 1,
                scale: true,
                splitNumber: 2,
                axisLabel: { color: "#64748b" },
                splitLine: { show: false }
            }
        ],
        dataZoom: [
            { type: "inside", xAxisIndex: [0, 1], start: 50, end: 100 },
            { show: true, xAxisIndex: [0, 1], type: "slider", bottom: 4, height: 18, borderColor: "rgba(255,255,255,0.08)" }
        ],
        series: [
            {
                name: "日K线",
                type: "candlestick",
                data: data.kline,
                itemStyle: {
                    color: "#f43f5e",        // A股红涨
                    color0: "#10b981",       // A股绿跌
                    borderColor: "#f43f5e",
                    borderColor0: "#10b981"
                }
            },
            {
                name: "MA5",
                type: "line",
                data: data.sma5,
                smooth: true,
                showSymbol: false,
                lineStyle: { width: 1.5, color: "#38bdf8" }
            },
            {
                name: "MA20",
                type: "line",
                data: data.sma20,
                smooth: true,
                showSymbol: false,
                lineStyle: { width: 1.5, color: "#f59e0b" }
            },
            {
                name: "成交量",
                type: "bar",
                xAxisIndex: 1,
                yAxisIndex: 1,
                data: data.volumes,
                itemStyle: {
                    color: (params) => {
                        const i = params.dataIndex;
                        const k = data.kline[i];
                        return (k && k[1] >= k[0]) ? "rgba(244, 63, 94, 0.65)" : "rgba(16, 185, 129, 0.65)";
                    }
                }
            }
        ]
    };

    marketChart.setOption(option, true);
}

function renderMarketTable(data) {
    const tbody = document.getElementById("market-table-body");
    if (!tbody) return;
    tbody.innerHTML = "";

    const len = data.dates.length;
    const startIdx = Math.max(0, len - 10);

    for (let i = len - 1; i >= startIdx; i--) {
        const tr = document.createElement("tr");
        const k = data.kline[i];
        const v = data.volumes[i];
        const d = data.dates[i];
        const s5 = data.sma5[i] || "-";
        const s20 = data.sma20[i] || "-";

        tr.innerHTML = `
            <td style="font-family: var(--font-mono);">${d}</td>
            <td class="num-col">${k[0]}</td>
            <td class="num-col">${k[3]}</td>
            <td class="num-col">${k[2]}</td>
            <td class="num-col" style="font-weight: 600; color: ${k[1] >= k[0] ? 'var(--color-up)' : 'var(--color-down)'}">${k[1]}</td>
            <td class="num-col">${v.toLocaleString()}</td>
            <td class="num-col">${s5}</td>
            <td class="num-col">${s20}</td>
        `;
        tbody.appendChild(tr);
    }
}

// ================= 2. Strategy Backtest Execution =================
async function runBacktest() {
    const code = document.getElementById("strategy-code").value;
    const symbols = document.getElementById("bt-symbols").value.trim() || "000001.SZ";
    const cash = parseFloat(document.getElementById("bt-cash").value) || 200000;
    const benchmark = document.getElementById("bt-benchmark").value.trim() || "000300.SH";
    const startDate = document.getElementById("bt-start").value || "2023-01-01";
    const endDate = document.getElementById("bt-end").value || "2024-12-31";
    const warmup = parseInt(document.getElementById("bt-warmup").value) || 20;

    const btn = document.getElementById("btn-run-backtest");
    const originalText = btn.innerHTML;
    btn.innerHTML = "正在执行回测撮合...";
    btn.disabled = true;

    try {
        const payload = {
            code,
            symbols,
            cash,
            start_date: startDate,
            end_date: endDate,
            benchmark,
            warmup
        };

        const res = await fetch("/api/backtest", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        const json = await res.json();

        if (json.success) {
            updateMetricsView(json.metrics);
            renderBacktestCharts(json);
            renderTradeHistoryTable(json.trade_history);
            showToast(`策略回测完成：总收益率 ${json.metrics.total_return_pct}%`, "success");
        } else {
            showToast("回测执行失败: " + (json.error || "未知错误"), "error");
        }
    } catch (e) {
        showToast("回测请求异常: " + e.message, "error");
    } finally {
        btn.innerHTML = originalText;
        btn.disabled = false;
    }
}

function updateMetricsView(m) {
    if (!m) return;

    const setVal = (id, val, isPct = false, colored = false) => {
        const el = document.getElementById(id);
        if (!el) return;
        const num = parseFloat(val);
        el.textContent = isPct ? `${num > 0 ? '+' : ''}${num.toFixed(2)}%` : (isNaN(num) ? val : num.toFixed(2));
        if (colored) {
            el.className = `metric-value ${num >= 0 ? 'up' : 'down'}`;
        }
    };

    setVal("kpi-total-return", m.total_return_pct, true, true);
    setVal("kpi-annual-return", m.annual_return_pct, true, true);
    setVal("kpi-sharpe", m.sharpe_ratio, false, true);
    setVal("kpi-max-dd", m.max_drawdown_pct, true, false);
    setVal("kpi-calmar", m.calmar_ratio, false, false);
    setVal("kpi-win-rate", m.win_rate_pct, true, false);
    setVal("kpi-pl-ratio", m.profit_loss_ratio, false, false);
    setVal("kpi-trades", m.total_trades, false, false);
}

function renderBacktestCharts(data) {
    const chartDom = document.getElementById("backtest-equity-chart");
    const ddDom = document.getElementById("backtest-dd-chart");
    if (!chartDom || !ddDom) return;

    if (!backtestChart) backtestChart = echarts.init(chartDom, "dark");
    if (!drawdownChart) drawdownChart = echarts.init(ddDom, "dark");

    const equityOpt = {
        backgroundColor: "transparent",
        tooltip: { trigger: "axis", axisPointer: { type: "cross" } },
        legend: { data: ["策略净值", "基准对比"], top: 2, textStyle: { color: "#94a3b8", fontSize: 11 } },
        grid: { left: "5%", right: "3%", top: 34, bottom: 26 },
        xAxis: { type: "category", data: data.dates, axisLine: { lineStyle: { color: "rgba(255,255,255,0.12)" } } },
        yAxis: { scale: true, splitLine: { lineStyle: { color: "rgba(255, 255, 255, 0.04)" } } },
        series: [
            {
                name: "策略净值",
                type: "line",
                data: data.equity,
                smooth: true,
                showSymbol: false,
                lineStyle: { width: 2, color: "#3b82f6" },
                areaStyle: {
                    color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                        { offset: 0, color: "rgba(59, 130, 246, 0.3)" },
                        { offset: 1, color: "rgba(59, 130, 246, 0.01)" }
                    ])
                }
            },
            {
                name: "基准对比",
                type: "line",
                data: data.benchmark_equity,
                smooth: true,
                showSymbol: false,
                lineStyle: { width: 1.5, color: "#64748b", type: "dashed" }
            }
        ]
    };
    backtestChart.setOption(equityOpt, true);

    const ddOpt = {
        backgroundColor: "transparent",
        tooltip: {
            trigger: "axis",
            formatter: (params) => `${params[0].name}<br/>回撤: ${params[0].value}%`
        },
        grid: { left: "5%", right: "3%", top: 18, bottom: 26 },
        xAxis: { type: "category", data: data.dates, axisLine: { lineStyle: { color: "rgba(255,255,255,0.12)" } } },
        yAxis: {
            type: "value",
            max: 0,
            splitLine: { lineStyle: { color: "rgba(255, 255, 255, 0.04)" } },
            axisLabel: { formatter: "{value}%" }
        },
        series: [
            {
                name: "回撤比例",
                type: "line",
                data: data.drawdown,
                smooth: true,
                showSymbol: false,
                lineStyle: { width: 1.5, color: "#10b981" },
                areaStyle: { color: "rgba(16, 185, 129, 0.2)" }
            }
        ]
    };
    drawdownChart.setOption(ddOpt, true);
}

function renderTradeHistoryTable(trades) {
    const tbody = document.getElementById("trade-history-body");
    if (!tbody) return;
    tbody.innerHTML = "";

    if (!trades || trades.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" style="text-align: center; color: var(--text-dim); padding: 20px;">回测周期内无交易生成</td></tr>';
        return;
    }

    trades.slice(-20).reverse().forEach(t => {
        const tr = document.createElement("tr");
        const isBuy = t.action === "buy";
        tr.innerHTML = `
            <td style="font-family: var(--font-mono);">${t.timestamp}</td>
            <td><span class="badge-level ${isBuy ? 'badge-trading' : 'badge-basic'}">${isBuy ? '买入' : '卖出'}</span></td>
            <td style="font-family: var(--font-mono); font-weight: 600;">${t.symbol}</td>
            <td class="num-col">${t.price}</td>
            <td class="num-col">${t.exec_price || t.price}</td>
            <td class="num-col">${t.size}</td>
            <td class="num-col">¥${t.commission || 5.0}</td>
        `;
        tbody.appendChild(tr);
    });
}

// ================= 3. Simulate Playground =================
async function runSimulate() {
    const symbol = document.getElementById("sim-symbol").value.trim() || "SIM.A";
    const drift = parseFloat(document.getElementById("sim-drift").value) || 0.0005;
    const reversion = parseFloat(document.getElementById("sim-reversion").value) || 0.05;
    const vol = parseFloat(document.getElementById("sim-vol").value) || 0.015;
    const days = parseInt(document.getElementById("sim-days").value) || 250;
    const price = parseFloat(document.getElementById("sim-price").value) || 100.0;

    try {
        const res = await fetch("/api/simulate", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                symbol, drift, reversion, vol, days, start_price: price
            })
        });
        const json = await res.json();
        if (json.success && json.data) {
            renderSimulateChart(json.data);
        }
    } catch (e) {
        console.error("生成模拟行情失败:", e);
    }
}

function renderSimulateChart(data) {
    const chartDom = document.getElementById("simulate-chart");
    if (!chartDom) return;

    if (!simulateChart) simulateChart = echarts.init(chartDom, "dark");

    const option = {
        backgroundColor: "transparent",
        tooltip: { trigger: "axis", axisPointer: { type: "cross" } },
        grid: { left: "4%", right: "2.5%", top: 26, bottom: 28 },
        xAxis: { type: "category", data: data.dates, axisLine: { lineStyle: { color: "rgba(255,255,255,0.12)" } } },
        yAxis: { scale: true, splitLine: { lineStyle: { color: "rgba(255, 255, 255, 0.04)" } } },
        dataZoom: [{ type: "inside" }, { type: "slider", bottom: 2, height: 16 }],
        series: [
            {
                name: "模拟标的走势",
                type: "candlestick",
                data: data.kline,
                itemStyle: {
                    color: "#f43f5e",
                    color0: "#10b981",
                    borderColor: "#f43f5e",
                    borderColor0: "#10b981"
                }
            },
            {
                name: "MA20",
                type: "line",
                data: data.sma20,
                smooth: true,
                showSymbol: false,
                lineStyle: { width: 1.5, color: "#38bdf8" }
            }
        ]
    };
    simulateChart.setOption(option, true);
}

// ================= 4. 股票池管理 (Stock Pool Management) =================
function escapeHtml(text) {
    if (!text) return "";
    return String(text)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

window.selectPoolLevelTab = function(level) {
    currentPoolLevel = level || "all";

    // Sync pool-level-tabs buttons
    document.querySelectorAll("#pool-level-tabs .pool-tab-btn").forEach(btn => {
        btn.classList.toggle("active", btn.getAttribute("data-level") === currentPoolLevel);
    });

    // Sync top KPI cards highlight
    document.querySelectorAll("[data-kpi-level]").forEach(box => {
        box.classList.toggle("active-filter", box.getAttribute("data-kpi-level") === currentPoolLevel);
    });

    fetchPoolStocks();
};

window.selectPoolCategory = function(cat) {
    currentPoolCategory = cat || "";
    const catSelect = document.getElementById("pool-category-select");
    if (catSelect) catSelect.value = currentPoolCategory;

    document.querySelectorAll("#sector-quick-pills .sector-pill").forEach(pill => {
        pill.classList.toggle("active", pill.getAttribute("data-cat") === currentPoolCategory);
    });

    fetchPoolStocks();
};

function initStockPool() {
    // 1. 股票池层级 Tab 切换
    document.querySelectorAll("#pool-level-tabs .pool-tab-btn").forEach(btn => {
        btn.addEventListener("click", () => {
            selectPoolLevelTab(btn.getAttribute("data-level") || "all");
        });
    });

    // 2. 赛道下拉框筛选
    const catSelect = document.getElementById("pool-category-select");
    if (catSelect) {
        catSelect.addEventListener("change", (e) => {
            selectPoolCategory(e.target.value.trim());
        });
    }

    // 3. 赛道快捷药丸点击
    document.querySelectorAll("#sector-quick-pills .sector-pill").forEach(pill => {
        pill.addEventListener("click", () => {
            selectPoolCategory(pill.getAttribute("data-cat") || "");
        });
    });

    // 4. 关键字搜索 (防抖)
    const searchInput = document.getElementById("pool-search-input");
    if (searchInput) {
        searchInput.addEventListener("input", (e) => {
            clearTimeout(poolSearchDebounce);
            poolSearchDebounce = setTimeout(() => {
                currentPoolKeyword = e.target.value.trim();
                fetchPoolStocks();
            }, 200);
        });
    }

    // 5. 刷新按钮
    const btnRefresh = document.getElementById("btn-pool-refresh");
    if (btnRefresh) {
        btnRefresh.addEventListener("click", () => {
            fetchPoolStats();
            fetchPoolStocks();
            showToast("股票池数据已刷新", "info");
        });
    }

    // 6. 标的弹窗打开/关闭/保存
    const btnOpenAdd = document.getElementById("btn-open-add-stock");
    const modalStock = document.getElementById("modal-stock");
    const btnCloseStock = document.getElementById("btn-close-stock-modal");
    const btnCancelStock = document.getElementById("btn-cancel-stock-modal");
    const btnSaveStock = document.getElementById("btn-save-stock");

    if (btnOpenAdd && modalStock) {
        btnOpenAdd.addEventListener("click", () => {
            editingStockSymbol = null;
            document.getElementById("modal-stock-title").textContent = "添加股票至股票池";
            document.getElementById("stock-symbol").value = "";
            document.getElementById("stock-symbol").removeAttribute("readonly");
            document.getElementById("stock-name").value = "";
            document.getElementById("stock-level").value = currentPoolLevel === "all" ? "basic" : currentPoolLevel;
            document.getElementById("stock-categories").value = currentPoolCategory ? `科技, ${currentPoolCategory}` : "科技, 光通信";
            document.getElementById("stock-price").value = "";
            document.getElementById("stock-change-pct").value = "";
            document.getElementById("stock-change-3d").value = "";
            document.getElementById("stock-reason").value = "";
            document.getElementById("stock-reports").value = "";
            document.getElementById("stock-risk-notes").value = "";
            modalStock.classList.add("active");
            setTimeout(() => document.getElementById("stock-symbol").focus(), 40);
        });
    }

    if (btnCloseStock) btnCloseStock.addEventListener("click", () => modalStock.classList.remove("active"));
    if (btnCancelStock) btnCancelStock.addEventListener("click", () => modalStock.classList.remove("active"));

    if (modalStock) {
        modalStock.addEventListener("click", (e) => {
            if (e.target === modalStock) modalStock.classList.remove("active");
        });
    }

    if (btnSaveStock) {
        btnSaveStock.addEventListener("click", handleSaveStock);
    }

    // 7. 研报与笔记导入弹窗 + 实时萃取预览
    const btnOpenImport = document.getElementById("btn-open-import");
    const modalImport = document.getElementById("modal-import");
    const btnCloseImport = document.getElementById("btn-close-import-modal");
    const btnCancelImport = document.getElementById("btn-cancel-import-modal");
    const btnSubmitImport = document.getElementById("btn-submit-import");
    const importTextEl = document.getElementById("import-text");

    if (btnOpenImport && modalImport) {
        btnOpenImport.addEventListener("click", () => {
            if (importTextEl) importTextEl.value = "";
            updateImportLivePreview("");
            modalImport.classList.add("active");
            setTimeout(() => importTextEl && importTextEl.focus(), 40);
        });
    }

    if (importTextEl) {
        importTextEl.addEventListener("input", (e) => {
            updateImportLivePreview(e.target.value);
        });
    }

    if (btnCloseImport) btnCloseImport.addEventListener("click", () => modalImport.classList.remove("active"));
    if (btnCancelImport) btnCancelImport.addEventListener("click", () => modalImport.classList.remove("active"));

    if (modalImport) {
        modalImport.addEventListener("click", (e) => {
            if (e.target === modalImport) modalImport.classList.remove("active");
        });
    }

    if (btnSubmitImport) {
        btnSubmitImport.addEventListener("click", handleSubmitImport);
    }

    // 8. 载入交易池至回测
    const btnExportBacktest = document.getElementById("btn-export-to-backtest");
    if (btnExportBacktest) {
        btnExportBacktest.addEventListener("click", handleExportTradingPoolToBacktest);
    }

    fetchPoolStats();
    fetchPoolStocks();
}

function updateImportLivePreview(text) {
    const previewEl = document.getElementById("import-live-preview");
    if (!previewEl) return;

    if (!text || !text.trim()) {
        previewEl.innerHTML = `<span>等待输入文本以实时预览识别到的股票代码...</span>`;
        return;
    }

    const regex = /([036][0-9]{5}(?:\.[Ss][ZzHh])?)/g;
    const matches = [...new Set(text.match(regex) || [])];

    if (matches.length === 0) {
        previewEl.innerHTML = `<span style="color: var(--color-warning);">尚未在文本中检测到 6 位 A 股代码（例如 300308 或 601138.SH）</span>`;
        return;
    }

    previewEl.innerHTML = `<span style="color: var(--color-emerald); font-weight: 600;">已识别 ${matches.length} 只标的：</span>` +
        matches.map(c => `<span class="badge-level badge-basic" style="font-family: var(--font-mono);">${escapeHtml(c.toUpperCase())}</span>`).join("");
}

async function fetchPoolStats() {
    try {
        const resp = await fetch("/api/pool/stats");
        const json = await resp.json();
        if (json.success && json.data) {
            const d = json.data;
            const counts = d.level_counts || {};

            const elTrading = document.getElementById("stat-pool-trading");
            const elSelected = document.getElementById("stat-pool-selected");
            const elBasic = document.getElementById("stat-pool-basic");
            const elTotal = document.getElementById("stat-pool-total");
            const elUpdated = document.getElementById("stat-pool-updated");
            const navBadge = document.getElementById("nav-pool-badge");
            const ovTradingCount = document.getElementById("overview-trading-count");

            if (elTrading) elTrading.textContent = `${counts.trading || 0} 只`;
            if (elSelected) elSelected.textContent = `${counts.selected || 0} 只`;
            if (elBasic) elBasic.textContent = `${counts.basic || 0} 只`;
            if (elTotal) elTotal.textContent = `${d.total_stocks || 0} 只`;
            if (elUpdated) elUpdated.textContent = `更新于 ${d.last_updated || "今日"}`;
            if (navBadge) navBadge.textContent = counts.trading || 0;
            if (ovTradingCount) ovTradingCount.textContent = `${counts.trading || 0} 只`;

            // 渲染盯盘与风控提醒
            const tpBanner = document.getElementById("pool-alerts-tp");
            const tpList = document.getElementById("pool-alerts-tp-list");
            const dipBanner = document.getElementById("pool-alerts-dip");
            const dipList = document.getElementById("pool-alerts-dip-list");

            if (d.take_profit_alerts && d.take_profit_alerts.length > 0) {
                if (tpBanner) tpBanner.style.display = "flex";
                if (tpList) {
                    tpList.innerHTML = d.take_profit_alerts.map(a =>
                        `<div style="margin-top: 3px;">
                            <strong style="cursor:pointer; text-decoration:underline;" onclick="inspectStockInMarket('${escapeHtml(a.symbol)}', '${escapeHtml(a.name)}')">${escapeHtml(a.name)} (${escapeHtml(a.symbol)})</strong>
                            <span class="badge-trend-up">日 +${a.change_pct}% / 3日 +${a.change_3d}%</span> —
                            <span style="color: var(--text-secondary);">${escapeHtml(a.reason)}</span>
                        </div>`
                    ).join("");
                }
            } else {
                if (tpBanner) tpBanner.style.display = "none";
            }

            if (d.dip_buying_alerts && d.dip_buying_alerts.length > 0) {
                if (dipBanner) dipBanner.style.display = "flex";
                if (dipList) {
                    dipList.innerHTML = d.dip_buying_alerts.map(a =>
                        `<div style="margin-top: 3px;">
                            <strong style="cursor:pointer; text-decoration:underline;" onclick="inspectStockInMarket('${escapeHtml(a.symbol)}', '${escapeHtml(a.name)}')">${escapeHtml(a.name)} (${escapeHtml(a.symbol)})</strong>
                            <span class="badge-trend-down">3日 ${a.change_3d}%</span> —
                            <span style="color: var(--text-secondary);">${escapeHtml(a.reason)}</span>
                        </div>`
                    ).join("");
                }
            } else {
                if (dipBanner) dipBanner.style.display = "none";
            }
        }
    } catch (e) {
        console.error("加载股票池统计失败:", e);
    }
}

async function fetchPoolStocks() {
    const tbody = document.getElementById("pool-table-body");
    if (!tbody) return;

    try {
        let url = `/api/pool/stocks?level=${encodeURIComponent(currentPoolLevel)}`;
        if (currentPoolCategory) url += `&category=${encodeURIComponent(currentPoolCategory)}`;
        if (currentPoolKeyword) url += `&keyword=${encodeURIComponent(currentPoolKeyword)}`;

        const resp = await fetch(url);
        const json = await resp.json();

        if (json.success && json.data) {
            cachedPoolStocks = json.data;
            if (currentPoolLevel === "all" && !currentPoolCategory && !currentPoolKeyword) {
                allPoolStocksMaster = json.data;
                renderOverviewTradingTable(allPoolStocksMaster);
            } else if (allPoolStocksMaster.length === 0) {
                fetch("/api/pool/stocks").then(r => r.json()).then(j => {
                    if (j.success && j.data) {
                        allPoolStocksMaster = j.data;
                        renderOverviewTradingTable(allPoolStocksMaster);
                    }
                });
            }
            renderPoolTable(cachedPoolStocks);
        } else {
            tbody.innerHTML = `<tr><td colspan="11" style="text-align: center; color: var(--color-up); padding: 30px;">加载失败: ${escapeHtml(json.error || "网络异常")}</td></tr>`;
        }
    } catch (e) {
        tbody.innerHTML = `<tr><td colspan="11" style="text-align: center; color: var(--color-up); padding: 30px;">请求异常: ${escapeHtml(e.message)}</td></tr>`;
    }
}

function renderOverviewTradingTable(stocks) {
    const tbody = document.getElementById("overview-trading-tbody");
    if (!tbody) return;

    const tradingList = (stocks || []).filter(s => s.pool_level === "trading");
    if (tradingList.length === 0) {
        tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--text-dim); padding: 20px;">暂无交易池标的</td></tr>`;
        return;
    }

    tbody.innerHTML = tradingList.slice(0, 6).map(s => {
        const chgPct = parseFloat(s.change_pct) || 0;
        const chg3d = parseFloat(s.change_3d) || 0;
        const chgPctColor = chgPct > 0 ? "var(--color-up)" : (chgPct < 0 ? "var(--color-down)" : "var(--text-muted)");
        const chg3dColor = chg3d > 0 ? "var(--color-up)" : (chg3d < 0 ? "var(--color-down)" : "var(--text-muted)");
        const cats = (s.categories || []).slice(-1).map(c => `<span class="tag-category" onclick="switchTab('tab-pool'); selectPoolCategory('${escapeHtml(c)}')">${escapeHtml(c)}</span>`).join("");

        return `
            <tr>
                <td>
                    <div class="stock-title-cell">
                        <span class="stock-name-link" onclick="inspectStockInMarket('${escapeHtml(s.symbol)}', '${escapeHtml(s.name)}')">${escapeHtml(s.name)}</span>
                        <span class="stock-code-sub">${escapeHtml(s.symbol)}</span>
                    </div>
                </td>
                <td>${cats}</td>
                <td class="num-col" style="font-weight: 600;">${s.price ? '¥' + Number(s.price).toFixed(2) : '-'}</td>
                <td class="num-col" style="font-weight: 600; color: ${chgPctColor};">${chgPct > 0 ? '+' : ''}${chgPct.toFixed(2)}%</td>
                <td class="num-col" style="font-weight: 600; color: ${chg3dColor};">${chg3d > 0 ? '+' : ''}${chg3d.toFixed(2)}%</td>
                <td style="text-align: right;">
                    <button class="btn-icon" onclick="inspectStockInMarket('${escapeHtml(s.symbol)}', '${escapeHtml(s.name)}')" title="打开K线复盘">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/></svg>
                    </button>
                </td>
            </tr>
        `;
    }).join("");
}

function renderPoolTable(stocks) {
    const tbody = document.getElementById("pool-table-body");
    if (!tbody) return;

    if (!stocks || stocks.length === 0) {
        tbody.innerHTML = `<tr><td colspan="11" style="text-align: center; padding: 40px; color: var(--text-dim);">当前筛选条件下暂无标的，可点击上方「添加标的」或「研报/笔记导入」。</td></tr>`;
        return;
    }

    tbody.innerHTML = stocks.map(s => {
        const categoriesHtml = (s.categories || []).map(c =>
            `<span class="tag-category" onclick="selectPoolCategory('${escapeHtml(c)}')" title="点击筛选该赛道">${escapeHtml(c)}</span>`
        ).join("");

        const chgPct = parseFloat(s.change_pct) || 0;
        const chg3d = parseFloat(s.change_3d) || 0;

        const chgPctColor = chgPct > 0 ? "var(--color-up)" : (chgPct < 0 ? "var(--color-down)" : "var(--text-muted)");
        const chg3dColor = chg3d > 0 ? "var(--color-up)" : (chg3d < 0 ? "var(--color-down)" : "var(--text-muted)");

        const priceDisplay = s.price ? `¥${Number(s.price).toFixed(2)}` : "-";
        const reportsText = (s.reports || []).join("；");

        return `
            <tr>
                <td>
                    <div class="stock-title-cell">
                        <span class="stock-name-link clamp-1" onclick="inspectStockInMarket('${escapeHtml(s.symbol)}', '${escapeHtml(s.name)}')" title="点击查看 ${escapeHtml(s.name)} 日K线行情">
                            ${escapeHtml(s.name)}
                        </span>
                        <span class="stock-code-sub">${escapeHtml(s.symbol)}</span>
                    </div>
                </td>
                <td>
                    <div style="display: flex; flex-direction: column; gap: 3px;">
                        <div class="pool-cascade-tags" title="层级包含：交易 ⊆ 精选 ⊆ 基础">
                            ${s.in_trading ? '<span class="badge-tag-pill badge-tag-trading">⚡交易</span>' : ''}
                            ${s.in_selected ? '<span class="badge-tag-pill badge-tag-selected">⭐精选</span>' : ''}
                            <span class="badge-tag-pill badge-tag-basic">📚基础</span>
                        </div>
                        <div class="level-Seg" title="流转标的所属层级 (交易 ⊆ 精选 ⊆ 基础)">
                            <button type="button" class="level-seg-btn ${s.pool_level === 'basic' ? 'active-basic' : ''}" onclick="handleQuickMoveLevel('${escapeHtml(s.symbol)}', 'basic')">仅基础</button>
                            <button type="button" class="level-seg-btn ${s.pool_level === 'selected' ? 'active-selected' : ''}" onclick="handleQuickMoveLevel('${escapeHtml(s.symbol)}', 'selected')">进精选</button>
                            <button type="button" class="level-seg-btn ${s.pool_level === 'trading' ? 'active-trading' : ''}" onclick="handleQuickMoveLevel('${escapeHtml(s.symbol)}', 'trading')">进交易</button>
                        </div>
                    </div>
                </td>
                <td>
                    <div class="clamp-2" style="max-width: 140px;">
                        ${categoriesHtml || '<span style="color: var(--text-dim);">-</span>'}
                    </div>
                </td>
                <td class="num-col" style="font-weight: 600; color: var(--text-main);">${priceDisplay}</td>
                <td class="num-col" style="font-weight: 600; color: ${chgPctColor};">
                    ${chgPct > 0 ? "+" : ""}${chgPct.toFixed(2)}%
                </td>
                <td class="num-col" style="font-weight: 600; color: ${chg3dColor};">
                    ${chg3d > 0 ? "+" : ""}${chg3d.toFixed(2)}%
                </td>
                <td style="max-width: 260px;">
                    <div class="clamp-2" style="font-size: 0.78rem; color: var(--text-secondary);" title="${escapeHtml(s.reason || '')}">
                        ${escapeHtml(s.reason || '-')}
                    </div>
                </td>
                <td style="max-width: 190px;">
                    <div class="clamp-2" style="font-size: 0.75rem; color: var(--text-muted);" title="${escapeHtml(reportsText)}">
                        ${reportsText ? escapeHtml(reportsText) : '-'}
                    </div>
                </td>
                <td style="max-width: 170px;">
                    <div class="clamp-2" style="font-size: 0.75rem; color: ${s.risk_notes ? '#fbbf24' : 'var(--text-dim)'};" title="${escapeHtml(s.risk_notes || '')}">
                        ${s.risk_notes ? escapeHtml(s.risk_notes) : '无明显瑕疵'}
                    </div>
                </td>
                <td style="font-size: 0.74rem; font-family: var(--font-mono); color: var(--text-dim); white-space: nowrap;">${escapeHtml(s.updated_at || '-')}</td>
                <td style="text-align: right; white-space: nowrap;">
                    <button class="btn-icon" onclick="inspectStockInMarket('${escapeHtml(s.symbol)}', '${escapeHtml(s.name)}')" title="K线看盘">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/></svg>
                    </button>
                    <button class="btn-icon" onclick="handleEditStock('${escapeHtml(s.symbol)}')" title="编辑标的">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
                    </button>
                    <button class="btn-icon danger" onclick="handleDeleteStock('${escapeHtml(s.symbol)}', '${escapeHtml(s.name)}')" title="移出股票池">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
                    </button>
                </td>
            </tr>
        `;
    }).join("");
}

window.handleQuickMoveLevel = async function(symbol, targetLevel) {
    const levelNames = { basic: "基础股票池", selected: "精选股票池", trading: "交易股票池" };
    try {
        const resp = await fetch("/api/pool/stocks/move", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ symbol, target_level: targetLevel })
        });
        const json = await resp.json();
        if (json.success) {
            showToast(`${symbol} 已移入${levelNames[targetLevel] || targetLevel}`, "success");
            allPoolStocksMaster = [];
            fetchPoolStats();
            fetchPoolStocks();
        } else {
            showToast("调整层级失败: " + (json.error || "未知原因"), "error");
        }
    } catch (e) {
        showToast("操作异常: " + e.message, "error");
    }
};

window.handleEditStock = function(symbol) {
    const stock = cachedPoolStocks.find(s => s.symbol === symbol) || allPoolStocksMaster.find(s => s.symbol === symbol);
    if (!stock) return;

    editingStockSymbol = stock.symbol;
    document.getElementById("modal-stock-title").textContent = `编辑标的 — ${stock.name} (${stock.symbol})`;
    document.getElementById("stock-symbol").value = stock.symbol;
    document.getElementById("stock-symbol").setAttribute("readonly", "true");
    document.getElementById("stock-name").value = stock.name || "";
    document.getElementById("stock-level").value = stock.pool_level || "basic";
    document.getElementById("stock-categories").value = (stock.categories || []).join(", ");
    document.getElementById("stock-price").value = stock.price !== undefined ? stock.price : "";
    document.getElementById("stock-change-pct").value = stock.change_pct !== undefined ? stock.change_pct : "";
    document.getElementById("stock-change-3d").value = stock.change_3d !== undefined ? stock.change_3d : "";
    document.getElementById("stock-reason").value = stock.reason || "";
    document.getElementById("stock-reports").value = (stock.reports || []).join("\n");
    document.getElementById("stock-risk-notes").value = stock.risk_notes || "";

    const modalStock = document.getElementById("modal-stock");
    if (modalStock) modalStock.classList.add("active");
};

window.handleDeleteStock = async function(symbol, name) {
    if (!confirm(`确定将标的「${name || symbol}」从股票池中移除吗？`)) return;

    try {
        const resp = await fetch(`/api/pool/stocks/${encodeURIComponent(symbol)}`, {
            method: "DELETE"
        });
        const json = await resp.json();
        if (json.success) {
            showToast(`已移除标的 ${name || symbol}`, "info");
            allPoolStocksMaster = [];
            fetchPoolStats();
            fetchPoolStocks();
        } else {
            showToast("删除失败: " + (json.error || "未知原因"), "error");
        }
    } catch (e) {
        showToast("删除请求异常: " + e.message, "error");
    }
};

async function handleSaveStock() {
    const symbol = document.getElementById("stock-symbol").value.trim().toUpperCase();
    const name = document.getElementById("stock-name").value.trim();
    const level = document.getElementById("stock-level").value;
    const catInput = document.getElementById("stock-categories").value.trim();
    const price = document.getElementById("stock-price").value;
    const changePct = document.getElementById("stock-change-pct").value;
    const change3d = document.getElementById("stock-change-3d").value;
    const reason = document.getElementById("stock-reason").value.trim();
    const reportsText = document.getElementById("stock-reports").value.trim();
    const riskNotes = document.getElementById("stock-risk-notes").value.trim();

    if (!symbol || !name) {
        showToast("请填写标的代码与股票名称", "error");
        return;
    }

    const categories = catInput ? catInput.split(/[,，、 ]+/).filter(Boolean) : ["科技"];
    const reports = reportsText ? reportsText.split(/[\n;；]+/).map(s => s.trim()).filter(Boolean) : [];

    const payload = {
        symbol,
        name,
        pool_level: level,
        categories,
        reason,
        reports,
        risk_notes: riskNotes
    };

    if (price !== "") payload.price = parseFloat(price);
    if (changePct !== "") payload.change_pct = parseFloat(changePct);
    if (change3d !== "") payload.change_3d = parseFloat(change3d);

    try {
        const resp = await fetch("/api/pool/stocks", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        const json = await resp.json();
        if (json.success) {
            const modalStock = document.getElementById("modal-stock");
            if (modalStock) modalStock.classList.remove("active");
            showToast(`已保存标的 ${name} (${symbol})`, "success");
            allPoolStocksMaster = [];
            fetchPoolStats();
            fetchPoolStocks();
        } else {
            showToast("保存失败: " + (json.error || "未知错误"), "error");
        }
    } catch (e) {
        showToast("保存请求异常: " + e.message, "error");
    }
}

async function handleSubmitImport() {
    const text = document.getElementById("import-text").value.trim();
    const level = document.getElementById("import-level").value;
    const category = document.getElementById("import-category").value;

    if (!text) {
        showToast("请粘贴要解析的研报或微博功课文本", "error");
        return;
    }

    const btn = document.getElementById("btn-submit-import");
    const originalText = btn.textContent;
    btn.disabled = true;
    btn.textContent = "正在萃取入池...";

    try {
        const resp = await fetch("/api/pool/import", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ text, level, category })
        });
        const json = await resp.json();

        if (json.success) {
            const count = json.total || json.imported_count || 0;
            const names = (json.stocks || []).map(s => `${s.name}(${s.symbol})`).join("、");
            showToast(`成功萃取并更新 ${count} 只标的：${names || ''}`, "success", 4500);

            const modalImport = document.getElementById("modal-import");
            if (modalImport) modalImport.classList.remove("active");
            allPoolStocksMaster = [];
            fetchPoolStats();
            fetchPoolStocks();
        } else {
            showToast("导入失败: " + (json.error || "未能识别出股票代码"), "error");
        }
    } catch (e) {
        showToast("导入解析异常: " + e.message, "error");
    } finally {
        btn.disabled = false;
        btn.textContent = originalText;
    }
}

window.handleExportTradingPoolToBacktest = async function() {
    try {
        const resp = await fetch("/api/pool/stocks?level=trading");
        const json = await resp.json();

        let symbols = [];
        if (json.success && json.data && json.data.length > 0) {
            symbols = json.data.map(s => s.symbol);
        } else {
            const respSel = await fetch("/api/pool/stocks?level=selected");
            const jsonSel = await respSel.json();
            if (jsonSel.success && jsonSel.data && jsonSel.data.length > 0) {
                symbols = jsonSel.data.map(s => s.symbol);
            }
        }

        if (symbols.length === 0) {
            showToast("当前交易股票池尚无标的，请先将标的移入交易池", "error");
            return;
        }

        const symbolStr = symbols.join(", ");
        const inputBtSymbols = document.getElementById("bt-symbols");
        if (inputBtSymbols) {
            inputBtSymbols.value = symbolStr;
        }

        switchTab("tab-strategy", true);
        showToast(`已将交易池 ${symbols.length} 只核心标的载入策略回测`, "success");
    } catch (e) {
        showToast("载入回测标的异常: " + e.message, "error");
    }
};
