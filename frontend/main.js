let GLOBAL_DATA = [];
// 💡 自動偵測環境：如果在本地開發就連 127.0.0.1，如果在雲端就連未來的雲端後端網址
const isLocal = window.location.hostname === "127.0.0.1" || window.location.hostname === "localhost";
const API_BASE_URL = isLocal ? "http://127.0.0.1:8000" : "https://mlb-war-room-l7ps.onrender.com"; 
// (網址我們先這樣寫，等下 Render 部署完會給我們真實網址，再來換掉)
let AI_RECOMMENDED_PLAYERS = []; // 💡 用來記住 AI 推薦了誰
let myRadarChart = null, myScatterChart = null;
// 🛡️ 歷史遺留問題避震器：我們已升級為 Datalist 智能搜尋，舊版下拉選單函數設為空，避免當機報錯！
window.updatePlayerSelects = function() {
    // 舊版功能，現已由 loadPlayerDatalist 取代，靜音處理。
};

// MLB 30支球隊清單
const MLB_TEAMS_LIST = [
    {id: 119, name: "Los Angeles Dodgers"}, {id: 147, name: "New York Yankees"},
    {id: 111, name: "Boston Red Sox"}, {id: 117, name: "Houston Astros"},
    {id: 144, name: "Atlanta Braves"}, {id: 143, name: "Philadelphia Phillies"},
    {id: 121, name: "New York Mets"}, {id: 141, name: "Toronto Blue Jays"},
    {id: 110, name: "Baltimore Orioles"}, {id: 139, name: "Tampa Bay Rays"},
    {id: 136, name: "Seattle Mariners"}, {id: 140, name: "Texas Rangers"},
    {id: 114, name: "Cleveland Guardians"}, {id: 142, name: "Minnesota Twins"},
    {id: 118, name: "Kansas City Royals"}, {id: 116, name: "Detroit Tigers"},
    {id: 145, name: "Chicago White Sox"}, {id: 108, name: "Los Angeles Angels"},
    {id: 133, name: "Athletics"}, {id: 146, name: "Miami Marlins"}, // 💡 這裡改成 Athletics
    {id: 120, name: "Washington Nationals"}, {id: 112, name: "Chicago Cubs"},
    {id: 113, name: "Cincinnati Reds"}, {id: 158, name: "Milwaukee Brewers"},
    {id: 134, name: "Pittsburgh Pirates"}, {id: 138, name: "St. Louis Cardinals"},
    {id: 109, name: "Arizona Diamondbacks"}, {id: 115, name: "Colorado Rockies"},
    {id: 135, name: "San Diego Padres"}, {id: 137, name: "San Francisco Giants"}
].sort((a,b) => a.name.localeCompare(b.name));
// 🎨 MLB 30 支球隊官方主色與副色 (Hex Color Code)
const MLB_TEAM_COLORS = {
    119: { primary: "#005A9C", secondary: "#EF3340" }, // Dodgers (道奇藍 -> 道奇紅)
    147: { primary: "#0C2340", secondary: "#C4CED4" }, // Yankees (洋基藏青 -> 洋基灰)
    111: { primary: "#BD3039", secondary: "#0C2340" }, // Red Sox (襪子紅 -> 藏青)
    117: { primary: "#002D62", secondary: "#EB6E1F" }, // Astros (太空人藍 -> 太空橘)
    144: { primary: "#CE1141", secondary: "#13274F" }, // Braves (勇士紅 -> 勇士藍)
    143: { primary: "#E81828", secondary: "#002D72" }, // Phillies (費城人紅 -> 費城藍)
    121: { primary: "#002D72", secondary: "#FF5910" }, // Mets (大都會藍 -> 大都會橘)
    141: { primary: "#134A8E", secondary: "#1D2D5C" }, // Blue Jays (藍鳥皇家藍 -> 藍鳥深藍)
    110: { primary: "#DF4601", secondary: "#1D1D1D" }, // Orioles (金鶯橘 -> 曜石黑)
    139: { primary: "#092C5C", secondary: "#8FBCE6" }, // Rays (光芒海軍藍 -> 淺天藍)
    136: { primary: "#0C2340", secondary: "#005C5C" }, // Mariners (水手海軍藍 -> 水手綠)
    140: { primary: "#003278", secondary: "#C0111F" }, // Rangers (遊騎兵藍 -> 遊騎兵紅)
    114: { primary: "#0C2340", secondary: "#E31937" }, // Guardians (守護者藍 -> 守護者紅)
    142: { primary: "#002B5C", secondary: "#D31145" }, // Twins (雙城藍 -> 雙城紅)
    118: { primary: "#004687", secondary: "#BD9B60" }, // Royals (皇家藍 -> 帝王金)
    116: { primary: "#0C2340", secondary: "#FA4616" }, // Tigers (老虎藏青 -> 老虎橘)
    145: { primary: "#27251F", secondary: "#5B6770" }, // White Sox (白襪黑 -> 鋼鐵灰)
    108: { primary: "#BA0021", secondary: "#003263" }, // Angels (天使紅 -> 天使藍)
    133: { primary: "#003831", secondary: "#EFB21E" }, // Athletics (運動家綠 -> 運動家金)
    146: { primary: "#00A3E0", secondary: "#EF3340" }, // Marlins (馬林魚邁阿密藍 -> 邁阿密紅)
    120: { primary: "#AB0003", secondary: "#14225A" }, // Nationals (國民紅 -> 國民藍)
    113: { primary: "#C6011F", secondary: "#111111" }, // Reds (紅人紅 -> 深夜黑)
    112: { primary: "#0E3386", secondary: "#CC3433" }, // Cubs (小熊藍 -> 小熊紅)
    158: { primary: "#12284C", secondary: "#FFC52F" }, // Brewers (釀酒人藏青 -> 大麥金)
    138: { primary: "#C41E3A", secondary: "#0C2340" }, // Cardinals (紅雀紅 -> 紅雀藍)
    134: { primary: "#002D62", secondary: "#FDB827" }, // Pirates (海盜黑 -> 海盜金)
    135: { primary: "#002D62", secondary: "#FFC425" }, // Padres (教士棕藍 -> 聖地牙哥金)
    137: { primary: "#FD5A1E", secondary: "#27251F" }, // Giants (巨人橘 -> 舊金山黑)
    109: { primary: "#A71930", secondary: "#E3D4AD" }, // Dbacks (響尾蛇響尾紅 -> 沙漠金)
    115: { primary: "#33006F", secondary: "#1C003E" }  // Rockies (落磯紫 -> 洛磯深紫)
};
// ==========================================
// ⚾ 局數 (IP) 專業分數顯示轉換器
// ==========================================
window.formatInnings = function(ip_val) {
    if (ip_val === null || ip_val === undefined || ip_val === '-') return '-';
    
    let strVal = String(ip_val).trim();
    
    // 1. 如果傳來的是傳統棒球字串 (例如 "5.1" 或 "5.2")
    if (strVal.endsWith('.1')) return strVal.replace('.1', '⅓');
    if (strVal.endsWith('.2')) return strVal.replace('.2', '⅔');
    if (strVal.endsWith('.0')) return strVal.replace('.0', '');

    // 2. 如果傳來的是被後端算過的精確小數 (例如 5.3, 5.7, 5.333...)
    let num = parseFloat(ip_val);
    if (isNaN(num)) return strVal;

    // 💡 神級防呆：把小數乘 3，四捨五入還原成「總出局數」，再重新組裝！
    let totalOuts = Math.round(num * 3);
    let whole = Math.floor(totalOuts / 3);
    let remainder = totalOuts % 3;

    if (remainder === 1) return whole + '⅓';
    if (remainder === 2) return whole + '⅔';
    return whole.toString(); // remainder === 0，例如 "6.0" 會直接變成 "6"
};
// 🎯 手動儲存實際分數 (Real Pts)
window.updateRealPts = async function(name, newPts) {
    try {
        let pts = parseFloat(newPts);
        if (isNaN(pts)) pts = 0.0;
        await fetch("https://mlb-war-room-l7ps.onrender.com/fantasy/update-player", {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name: name, real_pts: pts })
        });
        console.log(`✅ 已儲存 ${name} 實際分數: ${pts}`);
    } catch(e) { console.error("連線失敗"); }
}
function switchTab(tabId) {
    // 1. 移除所有頁面的 active 狀態
    document.querySelectorAll('.page-section').forEach(el => el.classList.remove('active'));
    // 2. 將所有導覽按鈕恢復為未選取的半透明狀態
    document.querySelectorAll('.nav-btn').forEach(btn => btn.className = "nav-btn text-lg font-bold text-[#005A9C] opacity-60 border-b-2 border-transparent pb-1 hover:opacity-100 transition-all");
    
    // 3. 將點擊的目標頁面加上 active 狀態
    document.getElementById(tabId).classList.add('active');
    // 4. 將點擊的導覽按鈕加上底線與全亮狀態
    document.getElementById(`nav-${tabId.split('-')[0]}`).className = "nav-btn text-lg font-bold text-[#005A9C] opacity-100 border-b-2 border-[#005A9C] pb-1 transition-all";
    
    // 🌟 根據切換的分頁自動抓取對應資料
    if (tabId === 'fantasy-page') fetchFantasyData(); // 🏆 改為抓取 Fantasy 夢幻隊
    if (tabId === 'league-page' && typeof GLOBAL_DATA !== 'undefined' && GLOBAL_DATA.length === 0) fetchLeagueData();
    if (tabId === 'team-page') fetchTeamDashboard();
    if (tabId === 'predict-page') fetchDailySchedule();
}
function switchSubView(viewId) {
    // 1. 隱藏所有子分頁
    document.querySelectorAll('.sub-view').forEach(el => {
        el.classList.add('hidden');
        el.classList.remove('active');
    });
    
    // 2. 所有按鈕換回未選中樣式
    document.querySelectorAll('.sub-btn').forEach(btn => {
        btn.className = "sub-btn shrink-0 text-gray-500 hover:bg-gray-100 px-6 py-3 rounded-xl font-bold text-xl md:text-2xl transition-colors";
    });
    
    // 3. 顯示目標分頁
    const targetView = document.getElementById(viewId);
    if (targetView) {
        targetView.classList.remove('hidden');
        targetView.classList.add('active', 'w-full');
    }
    
    // 4. 被點擊的按鈕換上選中樣式
    const activeBtn = document.getElementById(`btn-sub-${viewId}`);
    if (activeBtn) {
        activeBtn.className = "sub-btn shrink-0 bg-[#005A9C] text-white px-6 py-3 rounded-xl font-bold text-xl md:text-2xl shadow-sm";
    }

    // 5. 🔥 直接觸發專屬資料更新 (不再被守位與篩選器的限制綁架！)
    if (viewId === 'view-mvp' && typeof renderMVPView === 'function') {
        renderMVPView(); 
    } else if (viewId === 'view-hot' && typeof fetchRecentStats === 'function') { 
        loadHotData(); 
    } else if (viewId === 'view-milb' && typeof fetchMiLBData === 'function') { 
        fetchMiLBData(); 
    }

    // 6. 圖表分頁自動重繪 (如果已經有資料與輸入目標)
    if (GLOBAL_DATA && GLOBAL_DATA.length > 0) {
        if (viewId === 'view-radar' && typeof drawRadar === 'function') {
            const p1 = document.getElementById('radar-p1');
            if (p1 && p1.value.trim() !== '') drawRadar(true);
        }
        if (viewId === 'view-scatter' && typeof drawScatter === 'function') {
            if (typeof updateMetricSelects === 'function') updateMetricSelects();
            drawScatter();
        }
        if (viewId === 'view-h2h' && typeof renderH2H === 'function') {
            const h1 = document.getElementById('h2h-p1');
            if (h1 && h1.value.trim() !== '') renderH2H(true);
        }
    }
    
    // 7. 更新自動完成清單
    if (typeof loadPlayerDatalist === 'function') {
        loadPlayerDatalist();
    }
}

function updateSortOptions() {
    const pType = document.getElementById('filter-ptype').value;
    const sortSelect = document.getElementById('filter-sort');
    const posSelect = document.getElementById('filter-pos');
    if (pType === "打者") {
        sortSelect.innerHTML = `<option value="綜合分數" selected>綜合分數 (Grade)</option><option value="OPS">OPS</option><option value="HR">HR</option><option value="HardHit%">HardHit%</option>`;
        posSelect.innerHTML = `<option value="ALL">ALL (全部)</option><option value="C">C (捕手)</option><option value="1B">1B (一壘)</option><option value="2B">2B (二壘)</option><option value="3B">3B (三壘)</option><option value="SS">SS (游擊)</option><option value="OF">OF (外野)</option><option value="DH">DH (指定打擊)</option>`;
    } else {
        sortSelect.innerHTML = `<option value="綜合分數" selected>綜合分數 (Grade)</option><option value="ERA">ERA</option><option value="K%">K%</option><option value="xwOBA">xwOBA(被打)</option>`;
        posSelect.innerHTML = `<option value="ALL">ALL (全部)</option><option value="SP">SP (先發)</option><option value="RP">RP (後援)</option>`;
    }
}

// 🌟 網頁載入時初始化球隊清單
window.onload = () => { 
    updateSortOptions(); 
    const ts = document.getElementById('team-selector');
    if(ts) {
        ts.innerHTML = MLB_TEAMS_LIST.map(t => `<option value="${t.id}">${t.name}</option>`).join('');
        ts.value = "119"; // 預設道奇隊
    }
    // 自動設定今日日期
    const dateInput = document.getElementById('schedule-date');
    if(dateInput) {
        const today = new Date();
        // 考量時區，轉成 YYYY-MM-DD
        dateInput.value = today.toLocaleDateString('en-CA'); 
    }
    switchTab('scout-page'); 
};

function getGradeHTML(grade) {
    const colors = {"S": "bg-gradient-to-r from-yellow-500 to-red-500 text-white shadow-[0_0_10px_rgba(255,215,0,0.8)]", "A": "bg-blue-600 text-white", "B": "bg-green-600 text-white", "C": "bg-gray-600 text-gray-200", "D": "bg-gray-800 text-gray-400"};
    return `<span class="px-3 py-1 rounded-full font-black text-sm ${colors[grade] || colors['D']} border border-gray-200 shadow-sm">${grade}</span>`;
}

function getQuantile(arr, q) {
    const sorted = arr.filter(v => typeof v === 'number' && !isNaN(v)).sort((a, b) => a - b);
    if (sorted.length === 0) return 0;
    const pos = (sorted.length - 1) * q;
    const base = Math.floor(pos);
    const rest = pos - base;
    return sorted[base + 1] !== undefined ? sorted[base] + rest * (sorted[base + 1] - sorted[base]) : sorted[base];
}

function getHeatmapStyle(val, arr, colName) {
    if (typeof val !== 'number' || isNaN(val) || val === 0) return '';
    const lower_is_better = ['ERA', 'xERA', 'WHIP', 'FIP', 'BA', 'xBA', 'BB%', 'L', 'BSV', 'E', 'WP', 'Chase%', 'Whiff%', 'GB%', 'xwOBA'];
    const is_reverse = lower_is_better.includes(colName);
    const q20 = getQuantile(arr, 0.2), q50 = getQuantile(arr, 0.5), q80 = getQuantile(arr, 0.8);

    let style = '';
    if (is_reverse) {
        if (val <= q20) style = 'color: #C62828 !important; background-color: #FFEBEE !important; font-weight: 900 !important; border-radius: 4px; padding: 2px 6px;';
        else if (val <= q50) style = 'color: #E65100 !important; background-color: #FFF3E0 !important; font-weight: 900 !important; border-radius: 4px; padding: 2px 6px;';
        else if (val >= q80) style = 'color: #1565C0 !important; background-color: #E3F2FD !important; font-weight: 900 !important; border-radius: 4px; padding: 2px 6px;';
    } else {
        if (val >= q80) style = 'color: #C62828 !important; background-color: #FFEBEE !important; font-weight: 900 !important; border-radius: 4px; padding: 2px 6px;';
        else if (val >= q50) style = 'color: #E65100 !important; background-color: #FFF3E0 !important; font-weight: 900 !important; border-radius: 4px; padding: 2px 6px;';
        else if (val <= q20) style = 'color: #1565C0 !important; background-color: #E3F2FD !important; font-weight: 900 !important; border-radius: 4px; padding: 2px 6px;';
    }
    return style ? `style="${style}"` : '';
}

// ==========================================
// 🌟 全新獨立功能：球隊戰情室 Dashboard
// ==========================================
// 🛡️ 官方大聯盟 SVG 高清隊徽生成器
function getTeamLogoUrl(teamId) {
    if (!teamId || teamId === 0) return 'https://www.mlbstatic.com/team-logos/league-on-dark/1.svg';
    return `https://www.mlbstatic.com/team-logos/${teamId}.svg`;
}

// 🌟 球隊戰情室 Dashboard (大字體 + 官方隊徽 + 擴大版面)
async function fetchTeamDashboard() {
    const teamId = document.getElementById('team-selector').value;
    const yearElem = document.getElementById('filter-year');
    const year = yearElem ? yearElem.value : 2026;
    
    // 🎨 讀取該球隊專屬的主色與副色
    const teamColor = MLB_TEAM_COLORS[teamId] || { primary: "#005A9C", secondary: "#0C2340" };
    
    const panel = document.getElementById('team-dashboard-content');
    panel.classList.remove('hidden');
    panel.innerHTML = `<div class="p-10 text-center text-[#005A9C] text-4xl font-bold animate-pulse">連線至 MLB 官方資料庫，解析球隊全方位戰情...</div>`;

    const getPosBadge = (posStr) => {
        if (!posStr || posStr === '-') return '-';
        const positions = posStr.split(', ');
        return positions.map(pos => {
            let colorClass = "bg-[#005A9C]";
            if (pos.includes('SP')) colorClass = "bg-green-600";
            else if (pos.includes('RP') || pos.includes('CP')) colorClass = "bg-teal-500";
            else if (pos.includes('OF')) colorClass = "bg-indigo-500";
            else if (pos === 'C') colorClass = "bg-orange-500";
            else if (pos === 'DH') colorClass = "bg-purple-600";
            return `<span class="${colorClass} text-white px-3 py-1.5 rounded-lg shadow-sm text-base font-black tracking-wider border border-white/20 inline-block mr-1 my-0.5">${pos}</span>`;
        }).join('');
    };

    try {
        let res = await fetch(`${API_BASE_URL}/team-info/${teamId}?year=${year}`);
        let data = await res.json();
        
        if (data.status === 'success') {
            const std = data.standings || {};
            const hit = data.team_stats?.hitting || {};
            const pit = data.team_stats?.pitching || {};
            const rf = data.recent_form || {};
            const selectedTeamName = MLB_TEAMS_LIST.find(t => t.id == teamId).name;
            const logoUrl = getTeamLogoUrl(teamId);
            
            // 💡 1. 移除 max-w-7xl 限制，改為 w-full 滿版展開
            let html = `<div class="flex flex-col gap-10 w-full">`;
            
            // --- 1. 戰績與團隊數據 ---
            html += `
            <div class="grid grid-cols-1 lg:grid-cols-2 gap-8">
                <div class="p-8 md:p-10 rounded-3xl shadow-2xl text-white relative overflow-hidden flex flex-col justify-between transition-all duration-500" 
                     style="background: linear-gradient(135deg, ${teamColor.primary} 0%, ${teamColor.secondary} 100%);">
                    <img src="${logoUrl}" class="absolute -right-8 -bottom-8 w-64 h-64 opacity-20 pointer-events-none drop-shadow-2xl object-contain">
                    <div>
                        <div class="flex items-center gap-5 border-b border-white/20 pb-5 mb-6">
                            <div class="bg-white p-2 md:p-3 rounded-2xl shadow-xl border-2 border-gray-100 flex items-center justify-center">
                                <img src="${logoUrl}" class="w-20 h-20 md:w-24 md:h-24 object-contain drop-shadow-sm">
                            </div>
                            <div>
                                <h3 class="text-4xl md:text-5xl font-black text-white tracking-wide leading-tight whitespace-nowrap">${selectedTeamName}</h3>
                                <div class="flex items-center gap-3 mt-3">
                                    <span class="text-lg bg-yellow-400 text-gray-900 font-black px-4 py-1.5 rounded-full shadow-md">${year} 賽季</span>
                                    <span class="text-lg bg-white/20 px-4 py-1.5 rounded-full text-yellow-300 font-bold border border-white/20">${std.streak||'-'}</span>
                                </div>
                            </div>
                        </div>
                        <div class="grid grid-cols-2 md:grid-cols-3 gap-8 relative z-10 whitespace-nowrap">
                            <div><span class="text-lg text-white/80 font-bold block mb-1">分區排名</span><div class="text-6xl font-black">${std.divisionRank||'-'}</div></div>
                            <div><span class="text-lg text-white/80 font-bold block mb-1">勝 - 敗</span><div class="text-6xl font-black">${std.wins||0} - ${std.losses||0}</div></div>
                            <div><span class="text-lg text-white/80 font-bold block mb-1">勝率 / 勝差</span><div class="text-4xl font-black text-yellow-300 mt-3">${std.pct||'.000'} / ${std.gb||'-'}</div></div>
                            <div><span class="text-lg text-white/80 font-bold block mb-1">主場戰績</span><div class="text-3xl font-bold">${std.home_record||'-'}</div></div>
                            <div><span class="text-lg text-white/80 font-bold block mb-1">客場戰績</span><div class="text-3xl font-bold">${std.away_record||'-'}</div></div>
                            <div><span class="text-lg text-white/80 font-bold block mb-1">得失分差</span><div class="text-3xl font-bold ${std.run_diff && std.run_diff.includes('+') ? 'text-green-300' : 'text-red-300'}">${std.run_diff||'-'}</div></div>
                        </div>
                    </div>
                </div>
                
                <div class="bg-gray-50 border border-gray-200 p-8 md:p-10 rounded-3xl shadow-md flex flex-col justify-between">
                    <h3 class="text-4xl font-black text-gray-800 mb-6 border-b-2 border-gray-200 pb-4 flex items-center gap-3">⚔️ 團隊投打綜合數據</h3>
                    <div class="grid grid-cols-2 gap-8 my-auto">
                        <div class="bg-white p-6 rounded-2xl border border-gray-200 shadow-sm">
                            <h4 class="text-2xl font-black text-[#005A9C] mb-5 uppercase border-b pb-3">Hitting (打擊)</h4>
                            <div class="grid grid-cols-2 gap-6 text-gray-700 whitespace-nowrap">
                                <div class="flex flex-col"><span class="text-gray-500 text-sm font-bold tracking-wider">AVG</span><span class="font-black text-4xl text-gray-900">${hit.avg||'.000'}</span></div>
                                <div class="flex flex-col"><span class="text-gray-500 text-sm font-bold tracking-wider">OPS</span><span class="font-black text-4xl text-gray-900">${hit.ops||'.000'}</span></div>
                                <div class="flex flex-col"><span class="text-gray-500 text-sm font-bold tracking-wider">HR</span><span class="font-black text-4xl text-gray-900">${hit.hr||0}</span></div>
                                <div class="flex flex-col"><span class="text-gray-500 text-sm font-bold tracking-wider">SB</span><span class="font-black text-4xl text-gray-900">${hit.sb||0}</span></div>
                            </div>
                        </div>
                        <div class="bg-white p-6 rounded-2xl border border-gray-200 shadow-sm">
                            <h4 class="text-2xl font-black text-red-600 mb-5 uppercase border-b pb-3">Pitching (投球)</h4>
                            <div class="grid grid-cols-2 gap-6 text-gray-700 whitespace-nowrap">
                                <div class="flex flex-col"><span class="text-gray-500 text-sm font-bold tracking-wider">ERA</span><span class="font-black text-4xl text-gray-900">${pit.era||'0.00'}</span></div>
                                <div class="flex flex-col"><span class="text-gray-500 text-sm font-bold tracking-wider">WHIP</span><span class="font-black text-4xl text-gray-900">${pit.whip||'0.00'}</span></div>
                                <div class="flex flex-col"><span class="text-gray-500 text-sm font-bold tracking-wider">SO</span><span class="font-black text-4xl text-gray-900">${pit.so||0}</span></div>
                                <div class="flex flex-col"><span class="text-gray-500 text-sm font-bold tracking-wider">SV</span><span class="font-black text-4xl text-gray-900">${pit.sv||0}</span></div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>`;

            // --- 2. 球員名單 & 傷兵名單 ---
            // 💡 2. 加上 overflow-x-auto 與 whitespace-nowrap 保證橫向展開不換行
            html += `
            <div class="grid grid-cols-1 lg:grid-cols-2 gap-8">
                <div class="bg-white border border-gray-200 rounded-3xl shadow-md overflow-hidden flex flex-col h-[600px]">
                    <div class="bg-blue-50 px-8 py-5 border-b border-blue-100 font-black text-[#005A9C] text-2xl flex justify-between items-center whitespace-nowrap">
                        <span>📋 40人現役名單 (Roster)</span>
                        <span class="bg-[#005A9C] text-white text-lg px-4 py-2 rounded-full">${data.roster.length} 人</span>
                    </div>
                    <div class="overflow-x-auto overflow-y-auto flex-1 p-3">
                        <table class="w-full text-left text-xl whitespace-nowrap">
                            <thead class="sticky top-0 bg-white shadow-sm text-gray-500 uppercase text-lg z-10">
                                <tr><th class="p-4">No.</th><th class="p-4">Name</th><th class="p-4 text-center">Pos</th><th class="p-4 text-center">B/T</th></tr>
                            </thead>
                            <tbody>`;
            data.roster.forEach(p => {
                html += `<tr class="border-b border-gray-100 hover:bg-blue-50/50"><td class="p-4 font-bold text-gray-400 text-2xl">${p.number}</td><td class="p-4 font-black text-gray-900 text-2xl">${p.name}</td><td class="p-4 text-center">${getPosBadge(p.pos)}</td><td class="p-4 text-center font-bold text-gray-600 text-xl">${p.bats_throws}</td></tr>`;
            });
            html += `       </tbody></table></div></div>
                
                <div class="bg-white border border-gray-200 rounded-3xl shadow-md overflow-hidden flex flex-col h-[600px]">
                    <div class="bg-red-50 px-8 py-5 border-b border-red-100 font-black text-red-600 text-2xl flex justify-between items-center whitespace-nowrap">
                        <span>🏥 傷病名單 (IL)</span>
                        <span class="bg-red-500 text-white text-lg px-4 py-2 rounded-full">${data.injuries.length} 人</span>
                    </div>
                    <div class="overflow-x-auto overflow-y-auto flex-1 p-3">`;
            if(data.injuries.length > 0) {
                html += `
                        <table class="w-full text-left text-xl whitespace-nowrap">
                            <thead class="sticky top-0 bg-white shadow-sm text-gray-500 uppercase text-lg z-10">
                                <tr><th class="p-4">Name</th><th class="p-4 text-center">Pos</th><th class="p-4 text-right">Status</th></tr>
                            </thead>
                            <tbody>`;
                data.injuries.forEach(p => {
                    html += `<tr class="border-b border-gray-100 hover:bg-red-50/50"><td class="p-4 font-black text-gray-900 text-2xl">${p.name}</td><td class="p-4 text-center">${getPosBadge(p.pos)}</td><td class="p-4 text-right"><span class="bg-red-100 text-red-700 text-base font-black px-4 py-2 rounded-lg border border-red-200">${p.status}</span></td></tr>`;
                });
                html += `   </tbody></table>`;
            } else {
                html += `<div class="flex items-center justify-center h-full text-gray-400 font-bold text-3xl">目前無人傷停！🎉</div>`;
            }
            html += `</div></div></div>`;

            // --- 3. 賽程表 ---
            html += `<div class="grid grid-cols-1 md:grid-cols-2 gap-8">`;
            
            html += `
            <div class="bg-white border border-gray-200 rounded-3xl shadow-md overflow-hidden">
                <div class="bg-gray-100 px-8 py-5 border-b border-gray-200 font-black text-gray-800 text-2xl flex justify-between items-center whitespace-nowrap overflow-x-auto">
                    <span>⬅️ 過去 5 場比賽</span>
                    <span class="text-lg font-bold bg-white border border-gray-300 px-4 py-2 rounded-xl text-gray-600">近 5 場得失分: <span class="text-green-600 font-black">${rf.runs_scored}</span> - <span class="text-red-500 font-black">${rf.runs_allowed}</span></span>
                </div>
                <ul class="divide-y divide-gray-100">`;
            data.past_games.forEach(g => {
                let resColor = g.result.includes('W') ? 'text-green-600' : (g.result.includes('L') ? 'text-red-600' : 'text-gray-500');
                html += `
                <li class="p-6 flex justify-between items-center hover:bg-gray-50 transition-colors whitespace-nowrap overflow-x-auto">
                    <div class="flex flex-col gap-2">
                        <span class="text-base text-gray-500 font-bold uppercase tracking-wider">${g.date}</span>
                        <span class="font-black text-gray-900 text-2xl">${g.venue} vs <span class="text-[#005A9C]">${g.opponent}</span></span>
                    </div>
                    <div class="text-right">
                        <span class="font-black text-5xl ${resColor}">${g.result}</span>
                        <div class="text-xl font-bold text-gray-700 bg-gray-100 px-4 py-1.5 rounded-lg mt-3">${g.score}</div>
                    </div>
                </li>`;
            });
            html += `</ul></div>`;

            html += `
            <div class="bg-white border border-gray-200 rounded-3xl shadow-md overflow-hidden">
                <div class="bg-blue-50 px-8 py-5 border-b border-blue-100 font-black text-[#005A9C] text-2xl whitespace-nowrap overflow-x-auto">➡️ 未來 5 場賽程</div>
                <ul class="divide-y divide-blue-50/50">`;
            data.future_games.forEach(g => {
                html += `
                <li class="p-6 flex justify-between items-center hover:bg-blue-50/30 transition-colors whitespace-nowrap overflow-x-auto">
                    <div class="flex flex-col gap-2">
                        <span class="text-base text-[#005A9C] font-bold uppercase tracking-wider">${g.date}</span>
                        <span class="font-black text-gray-900 text-2xl">${g.venue} vs <span class="text-red-600">${g.opponent}</span></span>
                    </div>
                    <div class="text-right flex flex-col items-end">
                        <span class="text-base text-gray-500 font-bold bg-gray-100 px-4 py-1.5 rounded-lg mb-2">預計先發</span>
                        <span class="text-2xl font-black text-gray-800">${g.opp_pitcher}</span>
                    </div>
                </li>`;
            });
            html += `</ul></div></div></div>`;

            panel.innerHTML = html;
            if (typeof gsap !== 'undefined') gsap.from("#team-dashboard-content", { opacity: 0, y: 20, duration: 0.4 });
        } else {
            panel.innerHTML = `<div class="p-10 text-center text-red-500 font-bold text-4xl">${data.message}</div>`;
        }
    } catch(e) {
        panel.innerHTML = `<div class="p-10 text-center text-red-400 font-bold text-4xl">API 連線錯誤，請確定後端已啟動。</div>`;
    }
}

// 🏆 Fantasy 子分頁切換器
function switchFanTab(tabId) {
    document.querySelectorAll('.fan-view').forEach(el => el.classList.add('hidden'));
    document.querySelectorAll('.fan-tab-btn').forEach(btn => {
        btn.className = "fan-tab-btn text-gray-500 hover:bg-gray-100 px-4 py-2 md:px-5 rounded-xl font-bold text-base md:text-lg transition-colors";
    });
    document.getElementById(`fan-${tabId}`).classList.remove('hidden');
    document.getElementById(`btn-fan-${tabId}`).className = "fan-tab-btn bg-[#005A9C] text-white px-4 py-2 md:px-5 rounded-xl font-bold text-base md:text-lg shadow-sm";

    if (tabId === 'my-team') renderYahooTeam();
    if (tabId === 'fa-market') renderFreeAgents();
    if (tabId === 'trade-analyzer') renderTradeAnalyzerUI();
    if (tabId === 'prospects') renderProspects();
    
    // 🔥 終極修復：把舊的 renderExpertWarning() 換成這個！
    if (tabId === 'projections') loadProjections('打者'); 
    
    // 🌟 新增下面這兩行
    if (tabId === 'rankings') renderFantasyRankings();
    if (tabId === 'settings') renderFantasySettings();
}

// 供主選單切換使用
async function fetchFantasyData() {
    switchFanTab('my-team'); // 預設載入「我的球隊」
}
window.renderYahooTeam = async function() {
    const container = document.getElementById('fan-my-team');
    container.innerHTML = `<div class="text-center text-[#005A9C] text-3xl font-bold animate-pulse py-10">連線至資料庫載入您的專屬陣容...</div>`;
    try {
        let res = await fetch("https://mlb-war-room-l7ps.onrender.com/fantasy/yahoo-team");
        let data = await res.json();
        // 🚨 X光透視鏡開始
        console.log("🎯 抓到的原始資料:", data);
        if (!data.active_roster) {
        alert("後端有回傳，但找不到 active_roster (先發名單)！");
        }
        // 🚨 X光透視鏡結束
        if (data.status === "success") {
            AI_RECOMMENDED_PLAYERS = []; 
            if (data.ai_diagnosis && data.ai_diagnosis.recommendations) {
                data.ai_diagnosis.recommendations.forEach(r => {
                    AI_RECOMMENDED_PLAYERS.push(r.name);
                });
            }
            let l_html = '';
            let globalLeagues = data.all_leagues;
            Object.keys(globalLeagues).forEach(l => {
                l_html += `<option value="${l}" ${l === data.league_name ? 'selected' : ''}>${l}</option>`;
            });
            let t_html = '';
            globalLeagues[data.league_name].forEach(t => {
                t_html += `<option value="${t}" ${t === data.team_name ? 'selected' : ''}>${t}</option>`;
            });

           // 💡 1. 系統自動計算：本週即時總分 (Live) + 手動補分 = 最終本週實際
            let realWeeklyTotal = 0;  
            let projTotal = 0;
            let realDailyTotal = 0;  // 🚨 抓到了！就是之前漏掉這行，導致畫面崩潰！

            data.active_roster.forEach(p => {
                // 系統即時算出的本週分數 + 手動補分
                let liveWeekly = parseFloat(p.weekly_pts || 0);
                let bonusPts = parseFloat(p.real_pts || 0); 
                let totalPts = liveWeekly + bonusPts;
                
                if (!isNaN(totalPts)) {
                    realWeeklyTotal += totalPts;
                }
                projTotal += parseFloat(p.fan_pts || 0);
                
                // 🚨 補回：本日單日得分
                let dailyVal = parseFloat(p.actual_pts || 0);
                if (!isNaN(dailyVal)) {
                    realDailyTotal += dailyVal;
                }
            });

            let html = `
            <div class="flex flex-col xl:flex-row justify-between items-start xl:items-center mb-8 bg-white p-6 rounded-3xl border border-gray-200 shadow-sm gap-6 whitespace-nowrap overflow-x-auto">
                <div class="flex flex-col gap-3 w-full xl:w-auto">
                    <div class="flex items-center gap-3 flex-nowrap">
                        <select id="fan-league-select" onchange="handleContextChange(true)" class="text-[#005A9C] font-black bg-blue-50 px-5 py-3 rounded-xl border border-blue-100 outline-none text-2xl cursor-pointer hover:bg-blue-100 transition-colors shadow-sm">
                            ${l_html}
                        </select>
                        <span class="text-gray-400 font-black text-3xl hidden md:inline">/</span>
                        <select id="fan-team-select" onchange="handleContextChange(false)" class="text-gray-800 font-black bg-gray-50 px-5 py-3 rounded-xl border border-gray-200 outline-none text-2xl cursor-pointer hover:bg-gray-100 transition-colors shadow-sm">
                            ${t_html}
                        </select>
                        <button onclick="createNewLeagueOrTeam()" class="bg-green-500 text-white font-bold px-5 py-3 rounded-xl hover:bg-green-600 transition-colors shadow-sm text-xl">➕ 新增</button>
                    </div>
                </div>
                
                <div class="flex flex-col md:flex-row items-center gap-4 w-full xl:w-auto">
                    <div class="flex items-center gap-2 w-full relative">
                        <input list="player-datalist" type="text" id="add-player-name" placeholder="搜尋並選擇球員..." class="px-5 py-3 rounded-xl border border-gray-300 font-bold text-gray-800 focus:ring-2 focus:ring-[#005A9C] outline-none text-xl w-full md:w-72">
                        <datalist id="player-datalist"></datalist>
                        <button onclick="manualAddPlayer()" class="bg-[#005A9C] text-white px-6 py-3 rounded-xl font-black text-xl shadow-md hover:scale-105 transition-transform">➕ 簽下</button>
                    </div>
                    
                    <div class="text-right w-full md:w-auto border-t md:border-t-0 md:border-l border-gray-200 pt-4 md:pt-0 md:pl-6 flex gap-3">
                        <div class="bg-gray-50 px-4 py-2 rounded-xl border border-gray-200 text-center">
                            <div class="text-sm font-bold text-gray-500 mb-1">本週預期</div>
                            <div class="text-3xl font-black text-gray-800">${projTotal.toFixed(1)}</div>
                        </div>
                        <div class="bg-blue-50 px-4 py-2 rounded-xl border border-blue-200 text-center shadow-inner">
                            <div class="text-sm font-black text-[#005A9C] mb-1">本週實際</div>
                            <div class="text-3xl font-black text-[#005A9C]">${realWeeklyTotal.toFixed(1)}</div>
                        </div>
                        <div class="bg-green-50 px-4 py-2 rounded-xl border border-green-200 text-center shadow-inner">
                            <div class="text-sm font-black text-green-700 mb-1">本日得分 🎯</div>
                            <div class="text-3xl font-black text-green-600">${realDailyTotal.toFixed(1)}</div>
                        </div>
                    </div>
                </div>
            </div>
    
            <div class="flex flex-col gap-10 w-full">
                <div class="bg-white border border-gray-200 rounded-3xl shadow-sm overflow-hidden w-full">
                    <div class="bg-blue-50 px-6 py-4 border-b border-blue-100 font-black text-[#005A9C] flex justify-between items-center text-2xl whitespace-nowrap">
                        <span>🟢 先發陣容 (Active Roster)</span>
                        <span class="text-base bg-[#005A9C] text-white px-4 py-1.5 rounded-full font-bold">${data.active_roster.length} 人</span>
                    </div>
                    <div class="overflow-x-auto">
                        <table class="w-full text-left text-xl whitespace-nowrap">
                            <thead class="bg-gray-50 text-gray-500 font-bold border-b border-gray-200">
                                <tr>
                                    <th class="p-4 w-32 text-center">Slot</th>
                                    <th class="p-4">Player</th>
                                    <th class="p-4 text-center">Opp</th>
                                    <th class="p-4 text-center">Proj Pts</th>
                                    <th class="p-4 text-center text-green-600">Real Pts 🎯</th>
                                    <th class="p-4 text-center w-32">操作</th>
                                </tr>
                            </thead>
                            <tbody class="divide-y divide-gray-100">
                                ${data.active_roster.map(p => {
                                    // 🛡️ 終極防呆：遇到空位子絕對不當機
                                    let nameSafe = p.name ? p.name.replace(/'/g, "\\'") : '';
                                    let slotSafe = p.slot || '';
                                    let posSafe = p.pos || '';
                                    let realPts = parseFloat(p.real_pts || 0);
                                    
                                    return `
                                <tr class="hover:bg-blue-50/50 transition-colors">
                                    <td class="p-4 text-center">
                                        <select onchange="updatePlayerSlot('${nameSafe}', this.value)" class="bg-gray-100 text-gray-800 font-black px-4 py-2 rounded-lg text-lg outline-none focus:ring-2 focus:ring-[#005A9C] cursor-pointer border border-gray-200 hover:bg-gray-200 w-full text-center">
                                            ${['C','1B','2B','3B','SS','OF','UTIL','SP','RP','P','BN','IL'].map(s => `<option value="${s}" ${slotSafe === s ? 'selected' : ''}>${s}</option>`).join('')}
                                        </select>
                                    </td>
                                    <td class="p-4">
                                        <div class="font-black text-gray-900 text-2xl">${p.name || '空缺'} 
                                            <span class="text-sm text-gray-400 font-bold ml-2">${p.team || ''} - <span onclick="updatePlayerPos('${nameSafe}', '${posSafe}')" class="bg-gray-100 text-gray-600 px-2 py-0.5 rounded cursor-pointer hover:bg-blue-100 transition-colors">${posSafe} ✏️</span></span>
                                        </div>
                                    </td>
                                    <td class="p-4 text-center font-bold text-gray-600 text-xl">${p.has_game ? `<span class="text-[#005A9C] font-black">${p.today_game || ''}</span>` : 'OFF'}</td>
                                    <td class="p-4 text-center font-black text-[#005A9C] text-3xl">${parseFloat(p.fan_pts || 0).toFixed(1)}</td>
                                    <td class="p-4 text-center">
                                        <input type="number" step="0.1" value="${realPts.toFixed(1)}" onchange="updateRealPts('${nameSafe}', this.value)" class="w-24 text-center font-black text-green-600 text-3xl bg-gray-50 border-2 border-gray-300 rounded-xl focus:bg-white outline-none py-1 shadow-inner" title="本週實際總分 (每日自動更新 / 可手動微調)">
                                    </td>
                                    <td class="p-4 text-center">
                                        <button onclick="dropPlayer('${nameSafe}')" class="text-red-500 hover:bg-red-50 px-4 py-2 rounded-lg text-lg font-black border border-red-200">釋出 🗑️</button>
                                    </td>
                                </tr>`; }).join('')}
                                ${data.active_roster.length === 0 ? `<tr><td colspan="6" class="text-center py-8 text-gray-400 font-bold text-2xl">尚無球員...</td></tr>` : ''}
                            </tbody>
                        </table>
                    </div>
                </div>
                <div class="bg-white border border-gray-200 rounded-3xl shadow-sm overflow-hidden w-full">
                    <div class="bg-gray-100 px-6 py-4 border-b border-gray-200 font-black text-gray-600 text-2xl">⚪ 板凳與傷兵 (Bench / IL)</div>
                    <div class="overflow-x-auto">
                        <table class="w-full text-left text-xl whitespace-nowrap">
                            <thead class="bg-gray-50 text-gray-400 font-bold border-b border-gray-200">
                                <tr>
                                    <th class="p-4 w-32 text-center">Slot</th>
                                    <th class="p-4">Player</th>
                                    <th class="p-4 text-center">Opp</th>
                                    <th class="p-4 text-center">Proj Pts</th>
                                    <th class="p-4 text-center text-gray-500">Real Pts 🎯</th>
                                    <th class="p-4 text-center w-32">操作</th>
                                </tr>
                            </thead>
                            <tbody class="divide-y divide-gray-100">
                                ${data.inactive_roster.map(p => {
                                    // 🛡️ 終極防呆 (板凳區)
                                    let nameSafe = p.name ? p.name.replace(/'/g, "\\'") : '';
                                    let slotSafe = p.slot || '';
                                    let posSafe = p.pos || '';
                                    let realPts = parseFloat(p.real_pts || 0);
                                    
                                    return `
                                <tr class="hover:bg-gray-50">
                                    <td class="p-4 text-center w-32">
                                        <select onchange="updatePlayerSlot('${nameSafe}', this.value)" class="${slotSafe.includes('IL') ? 'bg-red-100 text-red-700 border-red-200' : 'bg-gray-200 text-gray-700 border-gray-300'} font-black px-4 py-2 rounded-lg text-lg outline-none cursor-pointer border w-full text-center">
                                            ${['C','1B','2B','3B','SS','OF','UTIL','SP','RP','P','BN','IL'].map(s => `<option value="${s}" ${slotSafe === s ? 'selected' : ''}>${s}</option>`).join('')}
                                        </select>
                                    </td>
                                    <td class="p-4">
                                        <div class="font-black text-gray-500 text-2xl">${p.name || '空缺'} 
                                            <span class="text-sm text-gray-400 font-bold ml-2">${p.team || ''} - <span onclick="updatePlayerPos('${nameSafe}', '${posSafe}')" class="bg-gray-100 text-gray-500 px-2 py-0.5 rounded cursor-pointer">${posSafe} ✏️</span></span>
                                        </div>
                                    </td>
                                    <td class="p-4 text-center font-bold text-gray-400 text-xl">${p.has_game ? (p.today_game || '') : 'OFF'}</td>
                                    <td class="p-4 text-center font-black text-gray-400 text-3xl">${parseFloat(p.fan_pts || 0).toFixed(1)}</td>
                                    <td class="p-4 text-center">
                                        <input type="number" step="0.1" value="${realPts.toFixed(1)}" onchange="updateRealPts('${nameSafe}', this.value)" class="w-24 text-center font-black text-gray-500 text-3xl bg-gray-100 border-2 border-gray-200 rounded-xl outline-none py-1 shadow-inner focus:bg-white">
                                    </td>
                                    <td class="p-4 text-center w-32">
                                        <button onclick="dropPlayer('${nameSafe}')" class="text-red-500 hover:bg-red-50 px-4 py-2 rounded-lg text-lg font-black border border-red-200">釋出 🗑️</button>
                                    </td>
                                </tr>`; }).join('')}
                                ${data.inactive_roster.length === 0 ? `<tr><td colspan="6" class="text-center py-8 text-gray-400 font-bold text-2xl">尚無球員...</td></tr>` : ''}
                            </tbody>
                        </table>
                    </div>
                </div>

                <div class="bg-white border-2 border-gray-200 rounded-3xl shadow-lg p-8 flex flex-col gap-6 w-full">
                    <div class="flex flex-col md:flex-row justify-between items-start md:items-center border-b-2 border-gray-100 pb-4 gap-2 whitespace-nowrap overflow-x-auto">
                        <h3 class="text-4xl font-black text-gray-800 flex items-center gap-3">🧠 陣容戰力體檢 (Z-Score)</h3>
                        <span class="text-lg text-gray-500 font-bold">📊 基於團隊各類別累積數據量化評分 (滿分 99)</span>
                    </div>

                    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 my-2">
                        ${Object.entries(data.z_scores).map(([cat, score]) => {
                            let color = score >= 88 ? 'bg-[#CE1141]' : (score >= 80 ? 'bg-[#005A9C]' : 'bg-gray-400');
                            let badgeColor = score >= 88 ? 'text-[#CE1141] bg-red-50 border-red-200' : (score >= 80 ? 'text-[#005A9C] bg-blue-50 border-blue-200' : 'text-gray-600 bg-gray-100 border-gray-200');
                            return `
                            <div class="bg-gray-50 p-5 rounded-2xl border border-gray-200 shadow-sm flex flex-col justify-between gap-3">
                                <div class="flex justify-between items-center">
                                    <span class="text-gray-800 font-black text-2xl">${cat}</span>
                                    <span class="px-4 py-1.5 rounded-xl text-3xl font-black border ${badgeColor}">${score}</span>
                                </div>
                                <div class="w-full bg-gray-200 rounded-full h-5 shadow-inner overflow-hidden">
                                    <div class="${color} h-5 rounded-full transition-all duration-1000 shadow-md" style="width: ${score}%"></div>
                                </div>
                            </div>`;
                        }).join('')}
                    </div>

                    <div class="p-8 bg-gradient-to-r from-gray-900 via-gray-800 to-black rounded-3xl text-white shadow-xl border border-gray-700 flex flex-col gap-6 w-full">
                        <div class="flex flex-col md:flex-row justify-between items-start md:items-center gap-6">
                            <div class="flex-1">
                                <div class="font-black text-yellow-400 text-3xl mb-3 flex items-center gap-2">🤖 AI 總管診斷報告</div>
                                <div class="text-xl leading-relaxed font-bold text-gray-200">${data.ai_diagnosis.advice}</div>
                            </div>
                            <div class="flex flex-row md:flex-col gap-4 min-w-[260px] bg-gray-800/80 p-5 rounded-2xl border border-gray-700 text-xl font-bold whitespace-nowrap overflow-x-auto">
                                <div class="flex items-center gap-2">
                                    <span class="text-green-400 font-black">🟢 最強戰力：</span>
                                    <span class="text-white font-black text-2xl">${data.ai_diagnosis.strongest}</span>
                                </div>
                                <div class="flex items-center gap-2">
                                    <span class="text-red-400 font-black">🔴 最大短板：</span>
                                    <span class="text-white font-black text-2xl">${data.ai_diagnosis.weakest}</span>
                                </div>
                            </div>
                        </div>
                        
                        ${data.ai_diagnosis.recommendations && data.ai_diagnosis.recommendations.length > 0 ? `
                        <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mt-2">
                            ${data.ai_diagnosis.recommendations.map(r => `
                            <div class="bg-gray-800/80 border border-gray-600 p-6 rounded-2xl flex flex-col gap-3 hover:border-yellow-400 hover:shadow-[0_0_15px_rgba(250,204,21,0.3)] transition-all shadow-lg">
                                <div class="flex justify-between items-start whitespace-nowrap overflow-x-auto gap-4">
                                    <div class="text-white font-black text-3xl">${r.name}</div>
                                    <div class="bg-gray-700 text-yellow-300 text-lg font-black px-4 py-1.5 rounded-xl border border-gray-500 shrink-0">${r.team} - ${r.pos}</div>
                                </div>
                                <div class="text-gray-300 font-bold text-xl whitespace-normal leading-relaxed mt-2 border-t border-gray-600 pt-3">${r.reason}</div>
                            </div>
                            `).join('')}
                        </div>
                        ` : ''}
                    </div>
            </div>`;
            container.innerHTML = html;
        }
        loadPlayerDatalist();
    } catch (e) { container.innerHTML = `<div class="text-red-500 text-center font-bold py-10 text-2xl">連線失敗</div>`; }
};

// ➕ 簽下與 ➖ 釋出球員 JS 動作
async function manualAddPlayer() {
    const input = document.getElementById('add-player-name');
    const name = input ? input.value.trim() : '';
    if (!name) { alert("請輸入球員姓名！"); return; }
    await addPlayerToMyTeam(name);
    input.value = '';
}

async function addPlayerToMyTeam(name, team = "FA", pos = "UTIL") {
    try {
        let res = await fetch("https://mlb-war-room-l7ps.onrender.com/fantasy/add-player", {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name: name, team: team, pos: pos })
        });
        let data = await res.json();
        alert(data.message);
        renderYahooTeam(); // 刷新我的球隊
    } catch(e) { alert("連線失敗"); }
}

async function dropPlayer(name) {
    if (!confirm(`確定要釋出 ${name} 嗎？`)) return;
    try {
        let res = await fetch("https://mlb-war-room-l7ps.onrender.com/fantasy/drop-player", {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name: name })
        });
        let data = await res.json();
        alert(data.message);
        renderYahooTeam(); // 刷新我的球隊
    } catch(e) { alert("連線失敗"); }
}

// ==========================================
// 2. 🛒 自由市場 (動態掃描聯盟狀態與手動去除)
// ==========================================
window.renderFreeAgents = async function(pType = "打者", posFilter = "ALL", searchQuery = "") {
    const container = document.getElementById('fan-fa-market');
    if (!container) return;
    
    container.innerHTML = `<div class="text-center text-[#005A9C] text-3xl font-bold animate-pulse py-16">連線至自由市場，掃描頂級大物中...</div>`;
    
    try {
        let res = await fetch(`${API_BASE_URL}/fantasy/free-agents?p_type=${encodeURIComponent(pType)}&pos_filter=${encodeURIComponent(posFilter)}&search_query=${encodeURIComponent(searchQuery)}`);
        let result = await res.json();
        
        if (result.status === "success") {
            const data = result.data || [];
            
            let html = `
            <div class="flex flex-col xl:flex-row justify-between items-start xl:items-center mb-6 bg-white p-6 rounded-3xl border border-gray-200 shadow-sm gap-6">
                
                <div class="flex items-center gap-4 whitespace-nowrap overflow-x-auto">
                    <button onclick="renderFreeAgents('打者', 'ALL', '')" class="px-8 py-3.5 rounded-xl font-black text-2xl transition-all ${pType === '打者' ? 'bg-[#005A9C] text-white shadow-md' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}">⚾ 尋找打者</button>
                    <button onclick="renderFreeAgents('投手', 'ALL', '')" class="px-8 py-3.5 rounded-xl font-black text-2xl transition-all ${pType === '投手' ? 'bg-[#005A9C] text-white shadow-md' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}">🥎 尋找投手</button>
                    
                    <div class="flex items-center gap-2 ml-2 border-l-2 border-gray-200 pl-4">
                        <span class="font-black text-gray-800 text-2xl">🛡️ 守位:</span>
                        <select id="fa-pos-select" onchange="renderFreeAgents('${pType}', this.value, document.getElementById('fa-search-input').value)" class="px-4 py-3 rounded-xl border-2 border-[#005A9C] font-black text-[#005A9C] bg-blue-50 text-xl shadow-sm outline-none cursor-pointer">
                            ${pType === '打者' ? `
                                <option value="ALL" ${posFilter === 'ALL' ? 'selected' : ''}>全部 (ALL)</option>
                                <option value="C" ${posFilter === 'C' ? 'selected' : ''}>捕手 (C)</option>
                                <option value="1B" ${posFilter === '1B' ? 'selected' : ''}>一壘 (1B)</option>
                                <option value="2B" ${posFilter === '2B' ? 'selected' : ''}>二壘 (2B)</option>
                                <option value="3B" ${posFilter === '3B' ? 'selected' : ''}>三壘 (3B)</option>
                                <option value="SS" ${posFilter === 'SS' ? 'selected' : ''}>游擊 (SS)</option>
                                <option value="OF" ${posFilter === 'OF' ? 'selected' : ''}>外野 (OF)</option>
                                <option value="DH" ${posFilter === 'DH' ? 'selected' : ''}>指打 (DH)</option>
                            ` : `
                                <option value="ALL" ${posFilter === 'ALL' ? 'selected' : ''}>全部 (ALL)</option>
                                <option value="SP" ${posFilter === 'SP' ? 'selected' : ''}>先發 (SP)</option>
                                <option value="RP" ${posFilter === 'RP' ? 'selected' : ''}>後援 (RP/CL)</option>
                            `}
                        </select>
                    </div>
                </div>
                
                <div class="flex items-center gap-3 w-full xl:w-auto">
                    <span class="font-black text-gray-800 text-2xl hidden md:inline whitespace-nowrap">🔍 快搜:</span>
                    <input list="player-datalist" type="text" id="fa-search-input" value="${searchQuery}" placeholder="輸入球員姓名..." 
                        onkeydown="if(event.key==='Enter') renderFreeAgents('${pType}', document.getElementById('fa-pos-select').value, this.value)"
                        class="px-5 py-3 rounded-xl border-2 border-gray-300 font-bold text-gray-800 focus:ring-4 focus:ring-blue-300 outline-none text-xl w-full md:w-72 shadow-inner">
                    <button onclick="renderFreeAgents('${pType}', document.getElementById('fa-pos-select').value, document.getElementById('fa-search-input').value)" class="bg-[#005A9C] text-white px-6 py-3 rounded-xl font-black text-xl shadow-md hover:scale-105 transition-transform whitespace-nowrap">搜尋</button>
                </div>
                
            </div>
            
            ${document.getElementById('player-datalist') ? '' : '<datalist id="player-datalist"></datalist>'}

            <div class="bg-white border border-gray-200 rounded-3xl shadow-sm overflow-hidden overflow-x-auto">
                <table class="w-full text-left text-xl whitespace-nowrap">
                    <thead class="bg-gray-50 text-gray-500 font-bold border-b border-gray-200 text-xl">
                        <tr>
                            <th class="p-4">Player</th>
                            <th class="p-4 text-center">Opp</th>
                            <th class="p-4 text-center">環境加成</th>
                            <th class="p-4 text-center">Proj Pts</th>
                            <th class="p-4 text-center text-green-600">Real Pts 🎯</th>
                            <th class="p-4 text-center">聯盟狀態</th>
                            <th class="p-4 text-center">操作</th>
                        </tr>
                    </thead>
                    <tbody class="divide-y divide-gray-100 text-xl">
            `;
            
            if (data.length === 0) {
                // 💡 修改了 colspan 為 7，確保畫面不破版
                html += `<tr><td colspan="7" class="p-8 text-center text-gray-400 font-bold text-2xl">找不到叫「${searchQuery}」的球員或符合條件的大物。</td></tr>`;
            } else {
                data.forEach(p => {
                    const isAiRec = typeof AI_RECOMMENDED_PLAYERS !== 'undefined' && AI_RECOMMENDED_PLAYERS.includes(p.name);
                    const aiBadge = isAiRec ? `<span class="ml-3 bg-yellow-400 text-gray-900 px-3 py-1 rounded-lg text-sm font-black shadow-sm border border-yellow-500 animate-pulse">🤖 AI 強推</span>` : '';

                    // 💡 加入了這行！系統自動判斷並帶入近7日實際分數 (actual_pts)
                    let defaultReal = (p.real_pts !== undefined && p.real_pts !== null && p.real_pts !== '') ? p.real_pts : (p.actual_pts || 0);

                    html += `
                    <tr class="hover:bg-blue-50/50 transition-colors ${isAiRec ? 'bg-yellow-50/30' : ''}">
                        <td class="p-4">
                            <div class="font-black text-gray-900 text-2xl">${p.name} 
                                <span class="text-sm text-gray-400 font-bold ml-2">${p.team} - ${p.pos}</span>
                                ${aiBadge}
                            </div>
                        </td>
                        <td class="p-4 text-center font-bold text-gray-600">${p.opponents.includes('OFF') ? 'OFF' : `<span class="text-[#005A9C]">${p.opponents}</span>`}</td>
                        <td class="p-4 text-center font-bold text-gray-600">${p.platoon_advantage}</td>
                        <td class="p-4 text-center font-black text-[#CE1141] text-3xl">${p.projected_pts}</td>
                        <td class="p-4 text-center">
                            <input type="number" step="0.1" value="${Number(defaultReal).toFixed(1)}" placeholder="0.0" onchange="updateRealPts('${p.name.replace(/'/g, "\\'")}', this.value)" class="w-24 text-center font-black text-green-600 text-3xl bg-gray-50 border-2 border-gray-300 rounded-xl focus:bg-white focus:ring-4 focus:ring-green-300 outline-none py-1 transition-all shadow-inner">
                        </td>
                        <td class="p-4 text-center font-black ${p.is_fa ? 'text-green-500' : 'text-orange-500'}">
                            ${p.league_status}
                        </td>
                        <td class="p-4 text-center">
                            <div class="flex gap-3 justify-center">
                                ${p.is_fa 
                                    ? `<button onclick="quickAddPlayer('${p.name.replace(/'/g, "\\'")}', '${p.team}', '${p.pos}')" class="bg-[#005A9C] text-white px-5 py-2.5 rounded-lg text-lg font-black hover:bg-blue-700 shadow-sm transition-colors whitespace-nowrap">➕ 簽下</button>`
                                    : `<button disabled class="bg-gray-200 text-gray-400 px-5 py-2.5 rounded-lg text-lg font-black cursor-not-allowed whitespace-nowrap">🔒 無法簽下</button>`
                                }
                                <button onclick="ignorePlayerInMarket('${p.name.replace(/'/g, "\\'")}', '${pType}')" class="bg-gray-100 border border-gray-300 text-gray-600 hover:bg-red-50 hover:text-red-600 px-5 py-2.5 rounded-lg text-lg font-black transition-colors whitespace-nowrap" title="點此隱藏">
                                    去除 🗑️
                                </button>
                            </div>
                        </td>
                    </tr>`;
                });
            }
            
            html += `</tbody></table></div>`;
            container.innerHTML = html;
            
            if (typeof loadPlayerDatalist === 'function') {
                loadPlayerDatalist();
            }
        } else {
            container.innerHTML = `<div class="text-red-500 text-center font-bold py-10 text-2xl">${result.message}</div>`;
        }
    } catch(e) {
        container.innerHTML = `<div class="text-red-500 text-center font-bold py-10 text-2xl">連線失敗</div>`;
    }
};

// 🗑️ 去除(隱藏)沒被偵測到的球員 API
window.ignorePlayerInMarket = async function(name, currentType) {
    if(!confirm(`確定要將 【${name}】 從自由市場中永久去除嗎？\n(這通常代表該球員已經在您的真實 Yahoo 聯盟中被其他玩家選走了)`)) return;
    
    try {
        let res = await fetch("https://mlb-war-room-l7ps.onrender.com/fantasy/ignore-player", {
            method: "POST", headers: {"Content-Type": "application/json"},
            body: JSON.stringify({name: name})
        });
        if(res.ok) {
            renderFreeAgents(currentType); // 瞬間重新整理自由市場
        }
    } catch(e) {
        alert("去除失敗，請確認後端是否啟動。");
    }
}

// 3. 🤝 交易評估模擬器
function renderTradeAnalyzerUI() {
    const container = document.getElementById('fan-trade-analyzer');
    if (!container) return;

    container.innerHTML = `
    <div class="max-w-5xl mx-auto bg-white border border-gray-200 rounded-3xl shadow-xl p-8 md:p-12 mt-4 whitespace-nowrap overflow-x-auto">
        <h2 class="text-4xl font-black text-gray-800 mb-3 text-center">🤝 AI 交易評估模擬器</h2>
        <p class="text-gray-500 font-bold mb-10 text-center text-xl">精算這筆交易對您球隊 Z-Score 的化學效應</p>
        
        <div class="grid grid-cols-1 md:grid-cols-2 gap-10 mb-10">
            <div class="bg-red-50 p-8 rounded-3xl border border-red-100 shadow-sm">
                <h3 class="font-black text-red-700 mb-5 text-2xl">📤 送出球員 (Give)</h3>
                <input list="player-datalist" type="text" id="trade-give-input" placeholder="輸入或選擇送出球員..." class="w-full px-5 py-4 rounded-xl border border-red-200 focus:outline-none focus:ring-4 focus:ring-red-300 font-bold text-xl text-gray-700 shadow-inner">
                <p class="text-red-500 font-bold text-sm mt-3">💡 提示：多位球員請用逗號 ( , ) 分隔</p>
            </div>
            <div class="bg-green-50 p-8 rounded-3xl border border-green-100 shadow-sm">
                <h3 class="font-black text-green-700 mb-5 text-2xl">📥 獲得球員 (Receive)</h3>
                <input list="player-datalist" type="text" id="trade-rec-input" placeholder="輸入或選擇獲得球員..." class="w-full px-5 py-4 rounded-xl border border-green-200 focus:outline-none focus:ring-4 focus:ring-green-300 font-bold text-xl text-gray-700 shadow-inner">
                <p class="text-green-600 font-bold text-sm mt-3">💡 提示：多位球員請用逗號 ( , ) 分隔</p>
            </div>
        </div>
        
        ${document.getElementById('player-datalist') ? '' : '<datalist id="player-datalist"></datalist>'}

        <button onclick="executeTradeAnalysis()" class="w-full bg-gradient-to-r from-gray-800 to-black text-white font-black text-3xl py-5 rounded-2xl shadow-lg hover:scale-[1.02] transition-transform">⚖️ 執行深度交易評估</button>
        
        <div id="trade-result-box" class="mt-10 hidden whitespace-normal"></div>
    </div>`;

    // 💡 呼叫現有的函數，將全聯盟球員名單載入到下拉選單中
    if (typeof loadPlayerDatalist === 'function') {
        loadPlayerDatalist();
    }
}

async function executeTradeAnalysis() {
    const giveInput = document.getElementById('trade-give-input').value;
    const recInput = document.getElementById('trade-rec-input').value;
    const resultBox = document.getElementById('trade-result-box');
    
    if (!giveInput || !recInput) {
        alert('請填寫送出與獲得的球員！');
        return;
    }
    
    const givePlayers = giveInput.split(',').map(s => s.trim()).filter(s => s);
    const recPlayers = recInput.split(',').map(s => s.trim()).filter(s => s);
    
    resultBox.classList.remove('hidden');
    resultBox.innerHTML = `<div class="text-[#005A9C] font-black text-3xl animate-pulse text-center py-10">🧠 AI 總管正在分析龐大交易數據庫...</div>`;
    
    try {
        let res = awaitfetch("https://mlb-war-room-l7ps.onrender.com/fantasy/trade-analyzer", {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ give_players: givePlayers, receive_players: recPlayers })
        });
        let data = await res.json();
        
        if (data.status === 'success') {
            let gradeColor = data.grade.includes('A') ? 'text-green-600' : (data.grade.includes('F') || data.grade.includes('C') ? 'text-red-600' : 'text-yellow-600');
            
            resultBox.innerHTML = `
                <div class="bg-gray-50 border-2 border-gray-200 p-10 rounded-3xl mt-6 shadow-sm">
                    <div class="flex justify-between items-center mb-8 border-b-2 border-gray-200 pb-6">
                        <span class="text-4xl font-black text-gray-800">交易評級</span>
                        <span class="${gradeColor} text-7xl font-black drop-shadow-sm">${data.grade}</span>
                    </div>
                    <div class="text-3xl font-bold text-gray-700 mb-10 text-center">${data.verdict}</div>
                    
                    <div class="grid grid-cols-1 md:grid-cols-3 gap-8 mb-8 text-center whitespace-nowrap overflow-x-auto">
                        <div class="bg-white p-6 rounded-2xl border border-gray-200 shadow-sm flex flex-col justify-center gap-3">
                            <div class="text-gray-500 font-bold text-xl">預期積分變化</div>
                            <div class="text-4xl font-black ${data.delta_score > 0 ? 'text-green-600' : 'text-red-600'}">${data.delta_score > 0 ? '+' : ''}${data.delta_score}</div>
                        </div>
                        <div class="bg-white p-6 rounded-2xl border border-gray-200 shadow-sm flex flex-col justify-center gap-3">
                            <div class="text-gray-500 font-bold text-xl">🟢 最大戰力得益</div>
                            <div class="text-2xl font-black text-green-600 whitespace-normal">${data.gain_category}</div>
                        </div>
                        <div class="bg-white p-6 rounded-2xl border border-gray-200 shadow-sm flex flex-col justify-center gap-3">
                            <div class="text-gray-500 font-bold text-xl">🔴 最大戰力犧牲</div>
                            <div class="text-2xl font-black text-red-600 whitespace-normal">${data.loss_category}</div>
                        </div>
                    </div>
                    
                    <div class="bg-blue-50/80 p-6 rounded-2xl border border-blue-200 text-xl font-bold text-gray-700 leading-relaxed text-center">
                        💡 總管分析：${data.ai_advice}
                    </div>
                </div>
            `;
        } else {
            resultBox.innerHTML = `<div class="text-red-500 font-bold text-3xl text-center py-10">${data.message}</div>`;
        }
    } catch (e) {
        resultBox.innerHTML = `<div class="text-red-500 font-bold text-3xl text-center py-10">連線失敗，無法評估交易。</div>`;
    }
}

// 4. 🌟 大物雷達 (Prospects)
async function renderProspects() {
    const container = document.getElementById('fan-prospects');
    container.innerHTML = `<div class="text-center text-[#005A9C] text-3xl font-bold animate-pulse py-10">掃描小聯盟農場中...</div>`;
    try {
        let res = await fetch("https://mlb-war-room-l7ps.onrender.com/fantasy/prospects");
        let data = await res.json();
        if (data.status === "success") {
            let html = `
            <div class="bg-white border border-gray-200 rounded-3xl shadow-sm overflow-hidden mt-4 overflow-x-auto">
                <table class="w-full text-left text-xl whitespace-nowrap">
                    <thead class="bg-gray-50 text-gray-500 font-bold border-b border-gray-200 text-xl">
                        <tr><th class="p-5">Prospect</th><th class="p-5 text-center">FV 評分</th><th class="p-5 text-center">升級預估</th><th class="p-5 text-center">總管建議</th><th class="p-5 text-center">Hit/Pow/Run</th></tr>
                    </thead>
                    <tbody class="divide-y divide-gray-100">
                        ${data.data.map(p => {
                            let fvColor = p.fv >= 60 ? 'bg-gradient-to-r from-yellow-400 to-yellow-600 text-white shadow-md' : (p.fv >= 50 ? 'bg-blue-500 text-white' : 'bg-gray-200 text-gray-700');
                            return `
                        <tr class="hover:bg-blue-50 transition-colors">
                            <td class="p-5">
                                <div class="font-black text-gray-900 text-2xl">${p.name}</div>
                                <div class="text-base text-gray-500 font-bold">${p.team} -${p.pos}</div>
                            </td>
                            <td class="p-5 text-center"><span class="px-5 py-2 rounded-full font-black ${fvColor} text-xl">${p.fv}</span></td>
                            <td class="p-5 text-center font-bold text-gray-700">${p.eta}</td>
                            <td class="p-5 text-center font-black text-gray-800">${p.stash}</td>
                            <td class="p-5 text-center font-bold text-gray-500">${p.hit} / ${p.power} /${p.run}</td>
                        </tr>`}).join('')}
                    </tbody>
                </table>
            </div>`;
            container.innerHTML = html;
        }
    } catch (e) { container.innerHTML = `<div class="text-red-500 text-center font-bold py-10 text-2xl">連線失敗</div>`; }
}

let globalProjData = [];
let globalProjType = '打者';

// 🔮 1. 抓取資料並繪製框架 (按鈕與下拉選單)
async function loadProjections(p_type = '打者') {
    const content = document.getElementById('fan-projections'); 
    content.innerHTML = `<div class="text-center text-2xl font-bold p-10 text-white">🔮 正在啟動未來預測引擎... (掃描全聯盟賽程與進階數據中)</div>`;

    try {
        const targetYear = typeof current_year !== 'undefined' ? current_year : 2026;
        let res = await fetch(`${API_BASE_URL}/fantasy/projections?p_type=${encodeURIComponent(p_type)}&year=${targetYear}`);
        let result = await res.json();

        if (result.status !== "success") {
            content.innerHTML = `<div class="text-red-500 font-bold p-6 bg-white rounded-xl mx-auto w-1/2 text-center text-xl">載入失敗: ${result.message}</div>`;
            return;
        }

        // 把資料存進全域變數，供篩選器使用
        globalProjData = result.data;
        globalProjType = p_type;

        // 🎨 繪製霸氣框架與【下拉篩選選單】
        let html = `
            <div class="w-full bg-white/95 border border-gray-200 p-6 md:p-8 rounded-3xl shadow-xl mb-6">
                
                <div class="flex flex-col xl:flex-row justify-between items-center mb-6 border-b-4 border-[#005A9C] pb-4 gap-4">
                    <h2 class="text-4xl font-black text-gray-800 tracking-wide flex items-center gap-3 whitespace-nowrap">🔮 終極未來預期</h2>
                    
                    <div class="flex flex-wrap justify-center items-center gap-3 w-full xl:w-auto">
                        <select id="filter-sch" onchange="renderProjTable()" class="bg-gray-50 border-2 border-[#005A9C] text-[#005A9C] rounded-xl px-4 py-2.5 font-bold text-lg shadow-sm outline-none cursor-pointer hover:bg-blue-50 transition-colors">
                            <option value="ALL">🗓️ 所有賽程</option>
                            <option value="🔥 極佳">🔥 極佳賽程</option>
                            <option value="❄️ 艱困">❄️ 艱困賽程</option>
                            <option value="⚖️ 中性">⚖️ 中性賽程</option>
                        </select>
                        
                        <select id="filter-ai" onchange="renderProjTable()" class="bg-gray-50 border-2 border-[#005A9C] text-[#005A9C] rounded-xl px-4 py-2.5 font-bold text-lg shadow-sm outline-none cursor-pointer hover:bg-blue-50 transition-colors">
                            <option value="ALL">📈 所有燈號</option>
                            <option value="🚀 逢低買進">🚀 逢低買進</option>
                            <option value="📉 逢高賣出">📉 逢高賣出</option>
                            <option value="⚖️ 實力相符">⚖️ 實力相符</option>
                        </select>
                    
                        <button class="${p_type === '打者' ? 'bg-[#005A9C] text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'} border-2 border-gray-300 px-6 py-2.5 rounded-xl font-bold text-lg shadow-md transition-colors whitespace-nowrap" onclick="loadProjections('打者')">🏏 打者</button>
                        <button class="${p_type === '投手' ? 'bg-[#005A9C] text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'} border-2 border-gray-300 px-6 py-2.5 rounded-xl font-bold text-lg shadow-md transition-colors whitespace-nowrap" onclick="loadProjections('投手')">⚾ 投手</button>
                    </div>
                </div>
                
                <div class="w-full overflow-x-auto">
                    <table class="w-full text-left border-collapse min-w-[1200px] whitespace-nowrap">
                        <thead class="bg-gray-100 text-gray-700 text-xl font-black border-y-4 border-gray-300">
                            <tr>
                                <th class="p-5 rounded-tl-xl">球員</th>
                                <th class="p-5">季末終局推算 (ROS)</th>
                                <th class="p-5">🗓️ 未來 7 天賽程紅利</th>
                                <th class="p-5">📈 AI 操盤燈號</th>
                                <th class="p-5 rounded-tr-xl">📊 運氣與進階數據</th>
                            </tr>
                        </thead>
                        <tbody id="proj-tbody" class="divide-y-2 divide-gray-200 text-gray-800">
                        </tbody>
                    </table>
                </div>
            </div>
        `;

        content.innerHTML = html;
        
        // 初次呼叫繪製表格
        renderProjTable();

    } catch (e) {
        content.innerHTML = `<div class="text-red-500 font-bold p-6 bg-white rounded-xl mx-auto w-1/2 text-center text-xl">連線錯誤: ${e.message}</div>`;
    }
}

// 🔮 2. 負責根據下拉選單即時篩選、繪製表格內容
function renderProjTable() {
    const tbody = document.getElementById('proj-tbody');
    if (!tbody) return;
    
    // 抓取當前兩個下拉選單的值
    const schFilter = document.getElementById('filter-sch').value;
    const aiFilter = document.getElementById('filter-ai').value;
    
    let html = '';
    let count = 0;
    
    globalProjData.forEach(p => {
        // 🔥 核心篩選邏輯：如果不符合選單條件，直接跳過這名球員 (Return)
        if (schFilter !== 'ALL' && !p.sch_grade.includes(schFilter)) return;
        if (aiFilter !== 'ALL' && !p.ai_judgment.includes(aiFilter)) return;
        
        count++; // 記錄符合條件的球員數量
        
        let nameStyle = p.in_my_team ? 'text-[#ff9800] font-black' : 'text-[#005A9C] font-black';
        let teamBadge = p.in_my_team 
            ? `<span class="bg-yellow-100 text-yellow-800 border-2 border-yellow-300 text-base px-3 py-1 rounded-lg shadow-sm">⭐ 我的球隊</span>` 
            : `<span class="text-gray-500 text-lg font-bold">${p.team}</span>`;
        
        let aiColor = p.ai_judgment.includes('買進') ? 'text-green-600' : (p.ai_judgment.includes('賣出') ? 'text-red-600' : 'text-gray-500');
        
        let metricHtml = globalProjType === '打者' 
            ? `BA: <strong class="text-gray-900">${p.ba.toFixed(3)}</strong> <span class="text-gray-400 mx-2">➡️</span> xBA: <strong class="text-[#005A9C]">${p.xba.toFixed(3)}</strong>` 
            : `ERA: <strong class="text-gray-900">${p.era.toFixed(2)}</strong> <span class="text-gray-400 mx-2">➡️</span> FIP: <strong class="text-[#005A9C]">${p.xera.toFixed(2)}</strong>`;

        html += `
            <tr class="hover:bg-blue-50 transition-colors">
                <td class="p-5">
                    <div class="${nameStyle} text-3xl mb-1">${p.name} <span class="bg-gray-200 text-gray-600 text-lg px-3 py-1 rounded-lg ml-2 font-bold">${p.pos}</span></div>
                    <div class="mt-2">${teamBadge}</div>
                </td>
                <td class="p-5">
                    <div class="text-4xl font-black text-[#17a2b8] drop-shadow-sm">${p.proj_end}</div>
                </td>
                <td class="p-5">
                    <div class="text-2xl font-black">${p.sch_grade}</div>
                    <div class="text-base font-bold text-gray-500 mt-2">未來 7 天共 ${p.sch_games} 場<br>(${p.sch_opp})</div>
                </td>
                <td class="p-5">
                    <div class="text-2xl font-black ${aiColor}">${p.ai_judgment}</div>
                </td>
                <td class="p-5">
                    <div class="text-lg font-black text-gray-600 mb-2">📝 ${p.report}</div>
                    <div class="text-xl">${metricHtml}</div>
                </td>
            </tr>
        `;
    });
    
    // 如果篩選後沒有任何球員，顯示防呆提示
    if (count === 0) {
        html = `<tr><td colspan="5" class="p-10 text-center text-2xl font-bold text-gray-400">目前沒有符合您嚴格篩選條件的球員 😅</td></tr>`;
    }
    
    tbody.innerHTML = html;
}

// ==========================================
// 🔄 全能版抓取與渲染 (還原總教練原始架構 + 修復下拉選單)
// ==========================================
window.fetchLeagueData = async function() {
    // 💡 1. 注入乾淨的雙向凍結 CSS 與拉條美化
    if (!document.getElementById("super-table-style")) {
        const style = document.createElement("style");
        style.id = "super-table-style";
        style.innerHTML = `
            .super-table { border-collapse: separate; border-spacing: 0; }
            .super-table th { position: sticky; top: 0; z-index: 30; background-color: #f3f4f6; border-bottom: 3px solid #cbd5e1; }
            .super-table .freeze-col { position: sticky; left: 0; z-index: 20; border-right: 4px solid #cbd5e1; background-clip: padding-box; }
            .super-table th.freeze-col { z-index: 40; background-color: #e2e8f0; }
            
            #league-top-scroll::-webkit-scrollbar, #league-table-scroll::-webkit-scrollbar { height: 16px; width: 16px; }
            #league-top-scroll::-webkit-scrollbar-track, #league-table-scroll::-webkit-scrollbar-track { background: #f1f5f9; }
            #league-top-scroll::-webkit-scrollbar-thumb, #league-table-scroll::-webkit-scrollbar-thumb { background: #94a3b8; border-radius: 10px; border: 3px solid #f1f5f9; }
            #league-top-scroll::-webkit-scrollbar-thumb:hover, #league-table-scroll::-webkit-scrollbar-thumb:hover { background: #64748b; }
        `;
        document.head.appendChild(style);
    }

    // 💡 2. 啟動防打架的雙向捲軸同步
    let isSyncingTop = false;
    let isSyncingTable = false;
    const topScroll = document.getElementById('league-top-scroll');
    const tableScroll = document.getElementById('league-table-scroll');
    
    if (topScroll && tableScroll) {
        topScroll.onscroll = () => { 
            if (!isSyncingTop) {
                isSyncingTable = true;
                tableScroll.scrollLeft = topScroll.scrollLeft; 
            }
            isSyncingTop = false;
        };
        tableScroll.onscroll = () => { 
            if (!isSyncingTable) {
                isSyncingTop = true;
                topScroll.scrollLeft = tableScroll.scrollLeft; 
            }
            isSyncingTable = false;
        };
    }

    const currentPType = document.getElementById('filter-ptype')?.value || '打者';
    const league = document.getElementById('filter-league')?.value || 'MLB';
    const pos = document.getElementById('filter-pos')?.value || 'ALL';
    const year = document.getElementById('filter-year')?.value || 2026;

    const tbody = document.getElementById('league-table-body');
    const thead = document.getElementById('table-head');

    if (tbody) {
        tbody.innerHTML = `<tr><td colspan="35" class="text-center py-12 font-black text-[#005A9C] text-3xl animate-pulse">連線至大數據資料庫，載入 ${year} 賽季全聯盟超凡數據中... ⏳</td></tr>`;
    }

    try {
        // 🔥 關鍵進化：一次發送兩個請求，把「打者」跟「投手」全部抓進來！
        const [resHitter, resPitcher] = await Promise.all([
            fetch(`${API_BASE_URL}/fantasy/rankings?p_type=打者&league=${league}&pos_filter=${pos}&year=${year}`),
            fetch(`${API_BASE_URL}/fantasy/rankings?p_type=投手&league=${league}&pos_filter=${pos}&year=${year}`)
        ]);

        const dataHitter = await resHitter.json();
        const dataPitcher = await resPitcher.json();

        let batters = dataHitter.status === "success" ? dataHitter.data : [];
        let pitchers = dataPitcher.status === "success" ? dataPitcher.data : [];

        // 🌟 1. 將兩者合併為 GLOBAL_DATA，讓下拉選單跟雷達圖找得到任何人！
        GLOBAL_DATA = [...batters, ...pitchers];

        // 🌟 2. 決定排行榜要渲染誰的資料 (避免打者表頭塞進投手資料，反之亦然)
        let tableData = currentPType === '打者' ? batters : pitchers;

        // 🌟 3. 建立超級下拉選單 (這時候裡面兩種人都有了)
        let datalist = document.getElementById('player-datalist');
        if (datalist && GLOBAL_DATA.length > 0) {
            let optionsHtml = '';
            GLOBAL_DATA.forEach(p => {
                const playerName = p.name || p.Name || p.Player || p.player; 
                const teamName = p.team || p.Team || 'FA';
                // 自動判斷是打者還是投手，並加在選單後方讓您好辨識！
                const role = (p.ip !== undefined || p.era !== undefined) ? '🎯投手' : '⚾打者'; 
                if (playerName) {
                    optionsHtml += `<option value="${playerName}">${playerName} (${teamName} | ${role})</option>`;
                }
            });
            datalist.innerHTML = optionsHtml;
        }

        if (tbody && thead) {
            let headHtml = '';
            let bodyHtml = '';

            // 🔥 渲染打者表格
            if (currentPType === '打者') {
                headHtml = `
                    <tr>
                        <th class="p-4 text-center min-w-[70px] bg-gray-200 text-xl">Rnk</th>
                        <th class="p-4 text-left freeze-col min-w-[220px] text-2xl">Player</th>
                        <th class="p-4 text-center text-gray-600 text-xl font-bold">PA</th><th class="p-4 text-center text-gray-600 text-xl font-bold">AB</th>
                        <th class="p-4 text-center text-xl font-bold">R</th><th class="p-4 text-center text-xl font-bold">H</th>
                        <th class="p-4 text-center text-xl font-bold">1B</th><th class="p-4 text-center text-xl font-bold">2B</th><th class="p-4 text-center text-xl font-bold">3B</th>
                        <th class="p-4 text-center text-2xl font-black text-gray-900 bg-yellow-200/80">HR</th>
                        <th class="p-4 text-center text-xl font-bold">RBI</th><th class="p-4 text-center text-xl font-bold text-[#005A9C]">SB</th>
                        <th class="p-4 text-center text-xl font-bold">BB</th><th class="p-4 text-center text-xl font-bold">HBP</th>
                        <th class="p-4 text-center text-2xl font-bold text-red-600">K</th><th class="p-4 text-center text-xl font-bold text-gray-700">E</th>
                        <th class="p-4 text-center text-2xl font-black text-[#005A9C] border-l-2 border-gray-300 bg-blue-100/50">AVG</th>
                        <th class="p-4 text-center text-2xl font-black text-[#CE1141] border-r-2 border-gray-300 bg-red-100/50">OPS</th>
                        <th class="p-4 text-center text-xl font-bold">OBP</th><th class="p-4 text-center text-xl font-bold">wOBA</th><th class="p-4 text-center text-2xl font-bold text-blue-700">wRC+</th>
                        <th class="p-4 text-center text-xl font-bold">xwOBA</th><th class="p-4 text-center text-xl font-bold">xBA</th>
                        <th class="p-4 text-center text-xl font-bold border-l-2 border-gray-300">HardHit%</th><th class="p-4 text-center text-2xl font-bold text-orange-600">Barrel%</th>
                        <th class="p-4 text-center text-xl font-bold">Chase%</th><th class="p-4 text-center text-xl font-bold">Whiff%</th><th class="p-4 text-center text-xl font-bold">GB%</th>
                        <th class="p-4 text-center text-2xl font-black text-yellow-700 border-l-2 border-gray-300">WAR</th>
                    </tr>
                `;
                tableData.forEach((p, i) => {
                    let rankBadge = i === 0 ? '🥇' : (i === 1 ? '🥈' : (i === 2 ? '🥉' : `#${i + 1}`));
                    let rowBg = i % 2 === 0 ? 'bg-white' : 'bg-gray-50';
                    bodyHtml += `
                        <tr class="${rowBg} hover:bg-blue-100/60 transition-colors border-b border-gray-200 whitespace-nowrap">
                            <td class="p-4 text-center font-black text-2xl text-gray-500">${rankBadge}</td>
                            <td class="p-4 freeze-col ${rowBg}">
                                <div class="font-black text-gray-900 text-2xl">${p.name || p.Name}</div>
                                <div class="text-base text-gray-600 font-bold mt-1">${p.team} - ${p.pos}</div>
                            </td>
                            <td class="p-4 text-center font-bold text-gray-600 text-xl">${p.pa}</td><td class="p-4 text-center font-medium text-gray-600 text-xl">${p.ab}</td>
                            <td class="p-4 text-center font-medium text-gray-800 text-xl">${p.r}</td><td class="p-4 text-center font-bold text-gray-900 text-xl">${p.h}</td>
                            <td class="p-4 text-center text-gray-700 text-xl">${p.b1}</td><td class="p-4 text-center font-bold text-gray-800 text-xl">${p.b2}</td><td class="p-4 text-center font-bold text-gray-800 text-xl">${p.b3}</td>
                            <td class="p-4 text-center font-black text-gray-900 text-3xl bg-yellow-50">${p.hr}</td>
                            <td class="p-4 text-center font-bold text-gray-800 text-xl">${p.rbi}</td><td class="p-4 text-center font-black text-[#005A9C] text-2xl">${p.sb}</td>
                            <td class="p-4 text-center font-medium text-gray-700 text-xl">${p.bb}</td><td class="p-4 text-center font-medium text-gray-700 text-xl">${p.hbp}</td>
                            <td class="p-4 text-center font-black text-red-600 text-2xl">${p.k}</td><td class="p-4 text-center text-gray-600 text-xl">${p.e}</td>
                            <td class="p-4 text-center font-black text-[#005A9C] text-2xl bg-blue-50 border-l-2 border-gray-300">${(typeof p.avg === 'number' ? p.avg.toFixed(3) : p.avg)}</td>
                            <td class="p-4 text-center font-black text-[#CE1141] text-2xl bg-red-50 border-r-2 border-gray-300">${(typeof p.ops === 'number' ? p.ops.toFixed(3) : p.ops)}</td>
                            <td class="p-4 text-center font-bold text-gray-800 text-xl">${(typeof p.obp === 'number' ? p.obp.toFixed(3) : p.obp)}</td><td class="p-4 text-center font-bold text-gray-600 text-xl">${p.woba}</td><td class="p-4 text-center font-black text-blue-700 text-2xl">${p.wrc_plus}</td>
                            <td class="p-4 text-center font-bold text-gray-600 text-xl">${p.xwoba}</td><td class="p-4 text-center font-bold text-gray-600 text-xl">${p.xba}</td>
                            <td class="p-4 text-center font-bold text-gray-600 text-xl border-l-2 border-gray-300">${p.hard_hit}</td><td class="p-4 text-center font-black text-orange-600 text-2xl">${p.barrel}</td>
                            <td class="p-4 text-center font-bold text-gray-600 text-xl">${p.chase}</td><td class="p-4 text-center font-bold text-gray-600 text-xl">${p.whiff}</td><td class="p-4 text-center font-bold text-gray-600 text-xl">${p.gb}</td>
                            <td class="p-4 text-center font-black text-yellow-600 text-2xl border-l-2 border-gray-300">${p.war}</td>
                        </tr>
                    `;
                });
            } 
            // 🔥 渲染投手表格
            else {
                headHtml = `
                    <tr>
                        <th class="p-4 text-center min-w-[70px] bg-gray-200 text-xl">Rnk</th>
                        <th class="p-4 text-left freeze-col min-w-[220px] text-2xl">Player</th>
                        <th class="p-4 text-center text-xl font-bold">W</th><th class="p-4 text-center text-xl font-bold">L</th>
                        <th class="p-4 text-center text-xl font-bold">SHO</th><th class="p-4 text-center text-2xl font-black text-gray-900 bg-yellow-200/80">SV</th>
                        <th class="p-4 text-center text-gray-600 text-xl font-bold">OUT</th><th class="p-4 text-center text-2xl font-black text-gray-900">IP</th>
                        <th class="p-4 text-center text-xl font-bold">H</th><th class="p-4 text-center text-xl font-bold">R</th><th class="p-4 text-center text-xl font-bold">ER</th>
                        <th class="p-4 text-center text-xl font-bold text-red-600">HR</th><th class="p-4 text-center text-xl font-bold">BB</th><th class="p-4 text-center text-xl font-bold">HBP</th>
                        <th class="p-4 text-center text-2xl font-black text-red-600 bg-red-100/50">K</th>
                        <th class="p-4 text-center text-xl font-bold text-gray-700">WP</th><th class="p-4 text-center text-xl font-bold text-blue-800">HLD</th>
                        <th class="p-4 text-center text-xl font-bold text-green-700">QS</th><th class="p-4 text-center text-xl font-bold text-orange-700">BSV</th>
                        <th class="p-4 text-center text-gray-600 text-xl font-bold">PC</th>
                        <th class="p-4 text-center text-2xl font-black text-[#005A9C] border-l-2 border-gray-300 bg-blue-100/50">ERA</th>
                        <th class="p-4 text-center text-xl font-bold">xERA</th>
                        <th class="p-4 text-center text-2xl font-black text-[#CE1141] border-r-2 border-gray-300 bg-red-100/50">WHIP</th>
                        <th class="p-4 text-center text-xl font-bold">K%</th><th class="p-4 text-center text-xl font-bold">BB%</th>
                        <th class="p-4 text-center text-2xl font-bold text-blue-700">FIP</th>
                        <th class="p-4 text-center text-xl font-bold">BA</th><th class="p-4 text-center text-xl font-bold">xBA</th><th class="p-4 text-center text-xl font-bold">Diff</th>
                        <th class="p-4 text-center text-xl font-bold border-l-2 border-gray-300">HardHit%</th><th class="p-4 text-center text-xl font-bold">Barrel%</th>
                        <th class="p-4 text-center text-xl font-bold">Whiff%</th><th class="p-4 text-center text-xl font-bold">GB%</th>
                        <th class="p-4 text-center text-2xl font-black text-yellow-700 border-l-2 border-gray-300">WAR</th>
                    </tr>
                `;
                tableData.forEach((p, i) => {
                    let rankBadge = i === 0 ? '🥇' : (i === 1 ? '🥈' : (i === 2 ? '🥉' : `#${i + 1}`));
                    let rowBg = i % 2 === 0 ? 'bg-white' : 'bg-gray-50';
                    bodyHtml += `
                        <tr class="${rowBg} hover:bg-blue-100/60 transition-colors border-b border-gray-200 whitespace-nowrap">
                            <td class="p-4 text-center font-black text-2xl text-gray-500">${rankBadge}</td>
                            <td class="p-4 freeze-col ${rowBg}">
                                <div class="font-black text-gray-900 text-2xl">${p.name || p.Name}</div>
                                <div class="text-base text-gray-600 font-bold mt-1">${p.team} - ${p.pos}</div>
                            </td>
                            <td class="p-4 text-center font-bold text-gray-800 text-xl">${p.w}</td><td class="p-4 text-center font-bold text-gray-800 text-xl">${p.l}</td>
                            <td class="p-4 text-center text-gray-600 text-xl">${p.sho}</td><td class="p-4 text-center font-black text-gray-900 text-3xl bg-yellow-50">${p.sv}</td>
                            <td class="p-4 text-center text-gray-600 text-xl">${p.outs}</td><td class="p-4 text-center font-black text-gray-900 text-2xl">${(typeof p.ip === 'number' ? p.ip.toFixed(1) : p.ip)}</td>
                            <td class="p-4 text-center font-medium text-gray-800 text-xl">${p.h}</td><td class="p-4 text-center font-medium text-gray-800 text-xl">${p.r}</td><td class="p-4 text-center font-bold text-gray-900 text-xl">${p.er}</td>
                            <td class="p-4 text-center font-bold text-red-600 text-xl">${p.hr}</td><td class="p-4 text-center font-medium text-gray-700 text-xl">${p.bb}</td><td class="p-4 text-center font-medium text-gray-700 text-xl">${p.hbp}</td>
                            <td class="p-4 text-center font-black text-red-600 text-3xl bg-red-50">${p.k}</td>
                            <td class="p-4 text-center text-gray-600 text-xl">${p.wp}</td><td class="p-4 text-center font-black text-blue-800 text-2xl">${p.hld}</td>
                            <td class="p-4 text-center font-black text-green-700 text-2xl">${p.qs}</td><td class="p-4 text-center font-black text-orange-700 text-2xl">${p.bsv}</td><td class="p-4 text-center text-gray-600 text-xl">${p.pc}</td>
                            <td class="p-4 text-center font-black text-[#005A9C] text-2xl bg-blue-50 border-l-2 border-gray-300">${(typeof p.era === 'number' ? p.era.toFixed(2) : p.era)}</td>
                            <td class="p-4 text-center font-bold text-gray-600 text-xl">${p.xera}</td>
                            <td class="p-4 text-center font-black text-[#CE1141] text-2xl bg-red-50 border-r-2 border-gray-300">${(typeof p.whip === 'number' ? p.whip.toFixed(2) : p.whip)}</td>
                            <td class="p-4 text-center font-bold text-gray-600 text-xl">${p.k_pct}</td><td class="p-4 text-center font-bold text-gray-600 text-xl">${p.bb_pct}</td><td class="p-4 text-center font-black text-blue-700 text-2xl">${(typeof p.fip === 'number' ? p.fip.toFixed(2) : p.fip)}</td>
                            <td class="p-4 text-center font-bold text-gray-800 text-xl">${(typeof p.ba === 'number' ? p.ba.toFixed(3) : p.ba)}</td><td class="p-4 text-center font-bold text-gray-600 text-xl">${p.xba}</td><td class="p-4 text-center font-bold text-gray-600 text-xl">${p.diff}</td>
                            <td class="p-4 text-center font-bold text-gray-600 text-xl border-l-2 border-gray-300">${p.hard_hit}</td><td class="p-4 text-center font-bold text-gray-600 text-xl">${p.barrel}</td><td class="p-4 text-center font-bold text-gray-600 text-xl">${p.whiff}</td><td class="p-4 text-center font-bold text-gray-600 text-xl">${p.gb}</td>
                            <td class="p-4 text-center font-black text-yellow-600 text-2xl border-l-2 border-gray-300">${p.war}</td>
                        </tr>
                    `;
                });
            }
            
            if (tableData.length === 0) {
                bodyHtml = `<tr><td colspan="35" class="text-center py-12 font-bold text-gray-400 text-2xl">目前沒有符合條件的球員資料</td></tr>`;
            }
            
            thead.innerHTML = headHtml;
            tbody.innerHTML = bodyHtml;

            setTimeout(() => {
                const topContent = document.getElementById('league-top-scroll-content');
                const mainTable = document.getElementById('league-main-table');
                if (topContent && mainTable) {
                    topContent.style.width = mainTable.scrollWidth + 'px';
                }
            }, 150);
        }

        if (document.getElementById('view-scatter')?.classList.contains('active')) {
            if (typeof updateMetricSelects === 'function') updateMetricSelects();
            if (typeof drawScatter === 'function') drawScatter();
        }
        if (document.getElementById('view-radar')?.classList.contains('active') || document.getElementById('view-h2h')?.classList.contains('active')) {
            if (typeof updatePlayerSelects === 'function') updatePlayerSelects();
        }

    } catch (e) {
        console.error(e);
        if (tbody) tbody.innerHTML = `<tr><td colspan="35" class="text-center py-10 text-red-500 font-bold text-2xl">連線失敗，請確認 API 服務已啟動。</td></tr>`;
    }
}

// 💡 「近況」專屬頂部滑條同步函數
function setupHotTopScrollSync() {
    const topScroll = document.getElementById('hot-top-scroll');
    const tableScroll = document.getElementById('hot-table-scroll');
    const mainTable = document.getElementById('hot-main-table');
    const topContent = document.getElementById('hot-top-scroll-content');

    if (!topScroll || !tableScroll || !mainTable || !topContent) return;

    // 1. 設定頂部滑條軌道長度 ＝ 真實表格總寬度
    topContent.style.width = mainTable.scrollWidth + 'px';

    // 2. 雙向捲軸靈魂連動 (帶防打架開關)
    let isSyncingTop = false;
    let isSyncingTable = false;

    topScroll.onscroll = () => {
        if (!isSyncingTop) {
            isSyncingTable = true;
            tableScroll.scrollLeft = topScroll.scrollLeft;
        }
        isSyncingTop = false;
    };

    tableScroll.onscroll = () => {
        if (!isSyncingTable) {
            isSyncingTop = true;
            topScroll.scrollLeft = tableScroll.scrollLeft;
        }
        isSyncingTable = false;
    };
}

async function fetchRecentStats(days = 14) {
    return; // 🚨 加上這一行！讓這個函數一被呼叫就立刻無效退下，什麼事都不做！
    const viewHot = document.getElementById('view-hot');
    if (viewHot && !document.getElementById('hot-pos-filter')) {
        const filterHtml = `
            <div class="flex flex-wrap gap-4 mb-6 bg-gray-50 p-4 rounded-xl border-2 border-gray-200 shadow-sm" id="hot-filters">
                <div class="flex items-center gap-2">
                    <span class="font-bold text-gray-700 text-lg">⚾ 類型:</span>
                    <select id="hot-ptype" onchange="fetchRecentStats(14)" class="px-4 py-2 rounded-lg border-2 border-gray-300 font-black text-[#005A9C] bg-white outline-none text-base shadow-sm">
                        <option value="打者" selected>打者</option>
                        <option value="投手">投手</option>
                    </select>
                </div>
                <div class="flex items-center gap-2">
                    <span class="font-bold text-gray-700 text-lg">🛡️ 位置:</span>
                    <select id="hot-pos-filter" onchange="fetchRecentStats(14)" class="px-4 py-2 rounded-lg border-2 border-gray-300 font-black text-[#005A9C] bg-white outline-none text-base shadow-sm">
                        <option value="ALL">全部 (ALL)</option><option value="C">捕手 (C)</option><option value="1B">一壘 (1B)</option><option value="2B">二壘 (2B)</option><option value="3B">三壘 (3B)</option><option value="SS">游擊 (SS)</option><option value="OF">外野 (OF)</option><option value="DH">指定打擊 (DH)</option><option value="SP">先發 (SP)</option><option value="RP">後援 (RP/CL)</option>
                    </select>
                </div>
                <div class="flex items-center gap-2">
                    <span class="font-bold text-gray-700 text-lg">📊 排序:</span>
                    <select id="hot-sort-metric" onchange="fetchRecentStats(14)" class="px-4 py-2 rounded-lg border-2 border-gray-300 font-black text-[#CE1141] bg-white outline-none text-base shadow-sm">
                        <option value="OPS">OPS</option><option value="AVG">AVG</option><option value="HR">HR</option><option value="RBI">RBI</option>
                    </select>
                </div>
            </div>
        `;
        viewHot.insertAdjacentHTML('afterbegin', filterHtml);
    }

    let thead = document.getElementById('hot-table-head');
    let tbody = document.getElementById('hot-table-body');
    let mainTable = tbody ? tbody.parentElement : null;
    if (thead && thead.tagName.toLowerCase() === 'tr') {
        const actualThead = thead.parentElement;
        actualThead.id = 'hot-table-head-corrected';
        thead.removeAttribute('id');
        thead = actualThead;
    } else if (document.getElementById('hot-table-head-corrected')) {
        thead = document.getElementById('hot-table-head-corrected');
    }

    if (mainTable && !document.getElementById('hot-table-scroll')) {
        const wrapper = mainTable.parentElement;
        const topScroll = document.createElement('div');
        topScroll.id = 'hot-top-scroll';
        topScroll.className = 'top-scroll-container';
        topScroll.innerHTML = '<div id="hot-top-scroll-content" class="top-scroll-content"></div>';
        
        const bottomScroll = document.createElement('div');
        bottomScroll.id = 'hot-table-scroll';
        bottomScroll.className = 'table-scroll-container';
        
        wrapper.insertBefore(topScroll, mainTable);
        wrapper.insertBefore(bottomScroll, mainTable);
        bottomScroll.appendChild(mainTable);
    }

    if (!document.getElementById("super-table-style")) {
        const style = document.createElement("style");
        style.id = "super-table-style";
        style.innerHTML = `
            .top-scroll-container { width: 100% !important; max-width: 92vw !important; overflow-x: auto !important; overflow-y: hidden !important; background-color: #f8fafc; border: 2px solid #e2e8f0; border-bottom: none; border-radius: 12px 12px 0 0; margin: 0 auto !important; display: block !important; }
            .top-scroll-content { height: 1px; }
            .table-scroll-container { width: 100% !important; max-width: 92vw !important; max-height: 75vh !important; overflow: auto !important; border: 2px solid #e2e8f0; border-radius: 0 0 12px 12px; background-color: white; box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1); margin: 0 auto 20px auto !important; display: block !important; }
            .super-table { width: 100% !important; border-collapse: separate !important; border-spacing: 0 !important; text-align: left; }
            .super-table th { position: sticky !important; top: 0 !important; z-index: 30 !important; background-color: #f1f5f9 !important; border-bottom: 3px solid #cbd5e1 !important; color: #1e293b !important; }
            .super-table .freeze-col { position: sticky !important; left: 0 !important; z-index: 20 !important; border-right: 4px solid #cbd5e1 !important; background-clip: padding-box !important; background-color: inherit; }
            .super-table th.freeze-col { z-index: 40 !important; background-color: #e2e8f0 !important; }
            .top-scroll-container::-webkit-scrollbar, .table-scroll-container::-webkit-scrollbar { height: 16px; width: 16px; }
            .top-scroll-container::-webkit-scrollbar-track, .table-scroll-container::-webkit-scrollbar-track { background: #f8fafc; }
            .top-scroll-container::-webkit-scrollbar-thumb, .table-scroll-container::-webkit-scrollbar-thumb { background: #94a3b8; border-radius: 8px; border: 3px solid #f8fafc; }
            .top-scroll-container::-webkit-scrollbar-thumb:hover, .table-scroll-container::-webkit-scrollbar-thumb:hover { background: #64748b; }
        `;
        document.head.appendChild(style);
    }

    const topScroll = document.getElementById('hot-top-scroll');
    const tableScroll = document.getElementById('hot-table-scroll');
    if (mainTable) {
        mainTable.className = "super-table";
        mainTable.style.minWidth = "1800px"; // 擴充寬度以容納新數據
    }

    let isSyncingTop = false;
    let isSyncingTable = false;
    if (topScroll && tableScroll) {
        topScroll.onscroll = () => { 
            if (!isSyncingTop) { isSyncingTable = true; tableScroll.scrollLeft = topScroll.scrollLeft; }
            isSyncingTop = false;
        };
        tableScroll.onscroll = () => { 
            if (!isSyncingTable) { isSyncingTop = true; topScroll.scrollLeft = tableScroll.scrollLeft; }
            isSyncingTable = false;
        };
    }

    const pType = document.getElementById('hot-ptype') ? document.getElementById('hot-ptype').value : '打者';
    const pos = document.getElementById('hot-pos-filter')?.value || 'ALL';
    const minFilter = pType === '打者' ? 10 : 5;
    
    const sortSelect = document.getElementById('hot-sort-metric');
    if (sortSelect) {
        const currentVal = sortSelect.value;
        if (pType === '打者' && !['OPS', 'AVG', 'HR', 'RBI', 'wRC_plus'].includes(currentVal)) {
            sortSelect.innerHTML = `<option value="OPS">OPS</option><option value="AVG">AVG</option><option value="HR">HR</option><option value="RBI">RBI</option><option value="wrc_plus">wRC+</option>`;
            sortSelect.value = 'OPS';
        } else if (pType === '投手' && !['ERA', 'WHIP', 'K', 'SV', 'FIP'].includes(currentVal)) {
            sortSelect.innerHTML = `<option value="ERA">ERA</option><option value="WHIP">WHIP</option><option value="K">K</option><option value="SV">SV</option><option value="FIP">FIP</option>`;
            sortSelect.value = 'ERA';
        }
    }
    const sortMetric = sortSelect?.value || (pType === '打者' ? 'OPS' : 'ERA');

    if (tbody) tbody.innerHTML = `<tr><td colspan="25" class="text-center py-12 font-black text-[#005A9C] text-2xl animate-pulse">連線至大數據中心，載入近 14 天火力戰報... ⏳</td></tr>`;

    try {
        let res = await fetch(`${API_BASE_URL}/fantasy/recent?p_type=${encodeURIComponent(pType)}&pos_filter=${pos}&min_filter=${minFilter}&sort_metric=${sortMetric}`);
        let result = await res.json();

        if (result.status === "success") {
            let data = result.data || [];
            let headHtml = '';
            let bodyHtml = '';

            // 🔥 打者近況 (22 項進階數據 + 強制黑字)
            if (pType === '打者') {
                headHtml = `
                    <tr>
                        <th class="p-3 text-center min-w-[50px] bg-gray-200 text-gray-900 font-black text-base">Rnk</th>
                        <th class="p-3 text-left freeze-col min-w-[200px] text-gray-900 font-black text-lg">Player</th>
                        <th class="p-3 text-center text-gray-800 font-bold text-base">PA</th><th class="p-3 text-center text-gray-800 font-bold text-base">AB</th>
                        <th class="p-3 text-center text-gray-800 font-bold text-base">R</th><th class="p-3 text-center text-gray-800 font-bold text-base">H</th>
                        <th class="p-3 text-center text-gray-700 font-bold text-base">1B</th><th class="p-3 text-center text-gray-700 font-bold text-base">2B</th><th class="p-3 text-center text-gray-700 font-bold text-base">3B</th>
                        <th class="p-3 text-center text-red-700 font-black bg-yellow-100/80 text-lg">HR</th>
                        <th class="p-3 text-center text-gray-900 font-bold text-base">RBI</th><th class="p-3 text-center text-[#005A9C] font-bold text-base">SB</th>
                        <th class="p-3 text-center text-gray-800 font-bold text-base">BB</th><th class="p-3 text-center text-red-600 font-bold text-base">K</th>
                        <th class="p-3 text-center text-gray-800 font-bold text-base">K%</th><th class="p-3 text-center text-gray-800 font-bold text-base">BB%</th>
                        <th class="p-3 text-center text-[#005A9C] font-black border-l-2 border-gray-300 bg-blue-50 text-lg">AVG</th>
                        <th class="p-3 text-center text-gray-900 font-bold text-base bg-gray-50">OBP</th>
                        <th class="p-3 text-center text-gray-900 font-bold text-base bg-gray-50">SLG</th>
                        <th class="p-3 text-center text-[#CE1141] font-black border-x-2 border-gray-300 bg-red-50 text-xl">OPS</th>
                        <th class="p-3 text-center text-gray-900 font-bold text-base">wOBA</th><th class="p-3 text-center text-blue-800 font-black text-lg">wRC+</th>
                    </tr>
                `;
                data.forEach((p, i) => {
                    let rankBadge = i === 0 ? '🥇' : (i === 1 ? '🥈' : (i === 2 ? '🥉' : `#${i + 1}`));
                    let rowBg = i % 2 === 0 ? 'bg-white' : 'bg-gray-50';
                    bodyHtml += `
                        <tr class="${rowBg} hover:bg-blue-100/60 transition-colors border-b border-gray-200 whitespace-nowrap">
                            <td class="p-3 text-center font-black text-lg text-gray-600">${rankBadge}</td>
                            <td class="p-3 freeze-col ${rowBg}">
                                <div class="font-black text-gray-900 text-lg">${p.name}</div>
                                <div class="text-sm text-gray-700 font-bold">${p.team} - <span class="text-[#005A9C]">${p.pos}</span></div>
                            </td>
                            <td class="p-3 text-center font-bold text-gray-900 text-base">${p.pa}</td><td class="p-3 text-center font-medium text-gray-800 text-base">${p.ab}</td>
                            <td class="p-3 text-center font-bold text-gray-900 text-base">${p.r}</td><td class="p-3 text-center font-black text-gray-900 text-base">${p.h}</td>
                            <td class="p-3 text-center text-gray-800 text-base">${p.b1}</td><td class="p-3 text-center font-bold text-gray-800 text-base">${p.b2}</td><td class="p-3 text-center font-bold text-gray-800 text-base">${p.b3}</td>
                            <td class="p-3 text-center font-black text-red-700 text-2xl bg-yellow-50">${p.hr}</td>
                            <td class="p-3 text-center font-bold text-gray-900 text-lg">${p.rbi}</td><td class="p-3 text-center font-black text-[#005A9C] text-lg">${p.sb}</td>
                            <td class="p-3 text-center font-bold text-gray-800 text-base">${p.bb}</td><td class="p-3 text-center font-black text-red-600 text-base">${p.k}</td>
                            <td class="p-3 text-center font-bold text-gray-800 text-base">${p.k_pct}</td><td class="p-3 text-center font-bold text-gray-800 text-base">${p.bb_pct}</td>
                            <td class="p-3 text-center font-black text-[#005A9C] text-xl border-l-2 border-gray-300 bg-blue-50/50">${p.avg.toFixed(3)}</td>
                            <td class="p-3 text-center font-black text-gray-900 text-lg bg-gray-50/50">${p.obp.toFixed(3)}</td>
                            <td class="p-3 text-center font-black text-gray-900 text-lg bg-gray-50/50">${p.slg.toFixed(3)}</td>
                            <td class="p-3 text-center font-black text-[#CE1141] text-2xl border-x-2 border-gray-300 bg-red-50/50">${p.ops.toFixed(3)}</td>
                            <td class="p-3 text-center font-bold text-gray-900 text-base">${p.woba}</td><td class="p-3 text-center font-black text-blue-800 text-xl">${p.wrc_plus}</td>
                        </tr>
                    `;
                });
            } 
            // 🔥 投手近況 (17 項進階數據 + 強制黑字)
            else {
                headHtml = `
                    <tr>
                        <th class="p-3 text-center min-w-[50px] bg-gray-200 text-gray-900 font-black text-base">Rnk</th>
                        <th class="p-3 text-left freeze-col min-w-[200px] text-gray-900 font-black text-lg">Player</th>
                        <th class="p-3 text-center text-gray-800 font-bold text-base">W</th><th class="p-3 text-center text-gray-800 font-bold text-base">L</th>
                        <th class="p-3 text-center text-gray-900 font-black bg-yellow-100/80 text-lg">SV</th>
                        <th class="p-3 text-center text-blue-900 font-bold text-base">HLD</th>
                        <th class="p-3 text-center text-gray-900 font-black text-lg">IP</th>
                        <th class="p-3 text-center text-gray-800 font-bold text-base">H</th><th class="p-3 text-center text-gray-900 font-bold text-base">ER</th>
                        <th class="p-3 text-center text-red-600 font-bold text-base">HR</th><th class="p-3 text-center text-gray-800 font-bold text-base">BB</th>
                        <th class="p-3 text-center text-red-600 font-black text-xl">K</th>
                        <th class="p-3 text-center text-gray-800 font-bold text-base">K%</th><th class="p-3 text-center text-gray-800 font-bold text-base">BB%</th>
                        <th class="p-3 text-center text-[#005A9C] font-black border-l-2 border-gray-300 text-lg">ERA</th>
                        <th class="p-3 text-center text-[#CE1141] font-black border-r-2 border-gray-300 text-lg">WHIP</th>
                        <th class="p-3 text-center text-blue-800 font-black text-lg">FIP</th>
                    </tr>
                `;
                data.forEach((p, i) => {
                    let rankBadge = i === 0 ? '🥇' : (i === 1 ? '🥈' : (i === 2 ? '🥉' : `#${i + 1}`));
                    let rowBg = i % 2 === 0 ? 'bg-white' : 'bg-gray-50';
                    bodyHtml += `
                        <tr class="${rowBg} hover:bg-blue-100/60 transition-colors border-b border-gray-200 whitespace-nowrap">
                            <td class="p-3 text-center font-black text-lg text-gray-600">${rankBadge}</td>
                            <td class="p-3 freeze-col ${rowBg}">
                                <div class="font-black text-gray-900 text-lg">${p.name}</div>
                                <div class="text-sm text-gray-700 font-bold">${p.team} - <span class="text-[#005A9C]">${p.pos}</span></div>
                            </td>
                            <td class="p-3 text-center font-bold text-gray-900 text-base">${p.w}</td><td class="p-3 text-center font-bold text-gray-900 text-base">${p.l}</td>
                            <td class="p-3 text-center font-black text-gray-900 text-2xl bg-yellow-50">${p.sv}</td>
                            <td class="p-3 text-center font-bold text-blue-900 text-base">${p.hld}</td>
                            <td class="p-3 text-center font-black text-gray-900 text-xl">${formatInnings(p.IP)}</td>
                            <td class="p-3 text-center font-medium text-gray-800 text-base">${p.h}</td><td class="p-3 text-center font-bold text-gray-900 text-base">${p.er}</td>
                            <td class="p-3 text-center font-bold text-red-600 text-base">${p.hr}</td><td class="p-3 text-center font-bold text-gray-800 text-base">${p.bb}</td>
                            <td class="p-3 text-center font-black text-red-600 text-2xl">${p.k}</td>
                            <td class="p-3 text-center font-bold text-gray-800 text-base">${p.k_pct}</td><td class="p-3 text-center font-bold text-gray-800 text-base">${p.bb_pct}</td>
                            <td class="p-3 text-center font-black text-[#005A9C] text-xl border-l-2 border-gray-300 bg-blue-50/50">${p.era.toFixed(2)}</td>
                            <td class="p-3 text-center font-black text-[#CE1141] text-xl border-r-2 border-gray-300 bg-red-50/50">${p.whip.toFixed(2)}</td>
                            <td class="p-3 text-center font-black text-blue-800 text-lg">${p.fip.toFixed(2)}</td>
                        </tr>
                    `;
                });
            }
            
            if (data.length === 0) bodyHtml = `<tr><td colspan="25" class="text-center py-12 font-bold text-gray-400 text-xl">目前沒有符合條件的近況資料</td></tr>`;
            
            if(thead) thead.innerHTML = headHtml;
            if(tbody) tbody.innerHTML = bodyHtml;
            
            // 動態更新頂部捲軸真實寬度
            setTimeout(() => {
                const topContent = document.getElementById('hot-top-scroll-content');
                if (topContent && mainTable) topContent.style.width = mainTable.scrollWidth + 'px';
            }, 150);

        } else {
            if (tbody) tbody.innerHTML = `<tr><td colspan="25" class="text-center py-10 text-red-500 font-bold text-xl">${result.message}</td></tr>`;
        }
    } catch (e) {
        if (tbody) tbody.innerHTML = `<tr><td colspan="25" class="text-center py-10 text-red-500 font-bold text-xl">連線失敗，請確認 API 服務已啟動。</td></tr>`;
    }
}

async function fetchMiLBData() {
    const tableBody = document.getElementById('milb-table-body');
    const tableHead = document.getElementById('milb-table-head');
    const year = document.getElementById('filter-year').value;
   // 💡 直接讀取 MiLB 專屬的打者/投手選單
    const pTypeElem = document.getElementById('milb-ptype');
    const pType = pTypeElem ? pTypeElem.value : '打者';
    const selectElem = document.getElementById('milb-level');
    const sportId = selectElem.value; 
    const levelText = selectElem.options[selectElem.selectedIndex].text; 
    const isPitcher = (pType === "投手");

    tableBody.innerHTML = `<tr><td colspan="10" class="p-8 text-center text-green-600 font-bold text-lg animate-pulse">🌱 正在深入 ${levelText} 農場抓取數據...</td></tr>`;

    if (!isPitcher) { tableHead.innerHTML = `<th class="p-3 whitespace-nowrap">Rank</th><th class="p-3 whitespace-nowrap">Player</th><th class="p-3 text-center whitespace-nowrap">Team</th><th class="p-3 text-center whitespace-nowrap">Pos</th><th class="p-3 text-center text-green-700 whitespace-nowrap">FV 評分</th><th class="p-3 text-center whitespace-nowrap">PA</th><th class="p-3 text-center whitespace-nowrap">HR</th><th class="p-3 text-center whitespace-nowrap">SB</th><th class="p-3 text-center whitespace-nowrap">AVG</th><th class="p-3 text-center font-bold whitespace-nowrap">OPS</th>`; } 
    else { tableHead.innerHTML = `<th class="p-3 whitespace-nowrap">Rank</th><th class="p-3 whitespace-nowrap">Player</th><th class="p-3 text-center whitespace-nowrap">Team</th><th class="p-3 text-center whitespace-nowrap">Pos</th><th class="p-3 text-center text-green-700 whitespace-nowrap">FV 評分</th><th class="p-3 text-center whitespace-nowrap">IP</th><th class="p-3 text-center whitespace-nowrap">SO</th><th class="p-3 text-center font-bold whitespace-nowrap">ERA</th><th class="p-3 text-center whitespace-nowrap">WHIP</th>`; }

    try {
        let res = await fetch(`${API_BASE_URL}/milb-stats?year=${year}&sport_id=${sportId}&p_type=${encodeURIComponent(pType)}`);
        let data = await res.json();
        
        if (data.status === "success" && data.data && data.data.length > 0) {
            let html = '';
            data.data.forEach((p, i) => {
                let fvColor = p.FV >= 60 ? 'bg-gradient-to-r from-yellow-400 to-yellow-600 text-white shadow-md' : (p.FV >= 50 ? 'bg-blue-500 text-white' : 'bg-gray-300 text-gray-700');
                let fvTag = `<span class="px-3 py-1 rounded-full font-black text-sm ${fvColor}">${p.FV}</span>`;
                if (!isPitcher) html += `<tr class="border-b border-gray-200 hover:bg-green-50 text-gray-800 whitespace-nowrap"><td class="p-3 font-bold text-gray-400">#${i+1}</td><td class="p-3 font-bold text-gray-900">${p.Name}</td><td class="p-3 text-center font-bold text-[#005A9C]">${p.Team}</td><td class="p-3 text-center text-gray-500">${p.Pos}</td><td class="p-3 text-center">${fvTag}</td><td class="p-3 text-center">${p.PA}</td><td class="p-3 text-center">${p.HR}</td><td class="p-3 text-center">${p.SB}</td><td class="p-3 text-center">${p.AVG.toFixed(3)}</td><td class="p-3 text-center font-black">${p.OPS.toFixed(3)}</td></tr>`;
                else html += `<tr class="border-b border-gray-200 hover:bg-green-50 text-gray-800 whitespace-nowrap"><td class="p-3 font-bold text-gray-400">#${i+1}</td><td class="p-3 font-bold text-gray-900">${p.Name}</td><td class="p-3 text-center font-bold text-[#005A9C]">${p.Team}</td><td class="p-3 text-center text-gray-500">${p.Pos}</td><td class="p-3 text-center">${fvTag}</td><td class="p-3 text-center">${p.IP.toFixed(1)}</td><td class="p-3 text-center">${p.SO}</td><td class="p-3 text-center font-black">${p.ERA.toFixed(2)}</td><td class="p-3 text-center">${p.WHIP.toFixed(2)}</td></tr>`;
            });
            tableBody.innerHTML = html;
        } else { tableBody.innerHTML = `<tr><td colspan="10" class="p-6 text-center text-gray-400">此層級暫無足夠數據</td></tr>`; }
    } catch (e) { tableBody.innerHTML = `<tr><td colspan="10" class="p-6 text-center text-red-400">連線失敗</td></tr>`; }
}

function switchDSTab(tabId) {
    document.querySelectorAll('.ds-tab-content').forEach(el => el.classList.add('hidden'));
    document.querySelectorAll('.ds-tab-btn').forEach(btn => btn.className = "ds-tab-btn px-4 py-2 bg-gray-100 text-gray-600 hover:bg-gray-200 font-bold rounded-lg transition-colors");
    document.getElementById(tabId).classList.remove('hidden');
    document.getElementById(`btn-${tabId}`).className = "ds-tab-btn px-4 py-2 bg-[#005A9C] text-white font-bold rounded-lg shadow-sm";
}

// 🧠 智慧聯想搜尋
setTimeout(() => {
    const searchInput = document.getElementById('deep-search-input');
    const suggestBox = document.getElementById('search-suggestions');
    let suggestTimer;

    if (searchInput && suggestBox) {
        searchInput.addEventListener('input', function(e) {
            clearTimeout(suggestTimer);
            const query = e.target.value.trim();
            if (query.length < 2) { suggestBox.classList.add('hidden'); return; }
            suggestTimer = setTimeout(async () => {
                try {
                    let res = await fetch(`${API_BASE_URL}/suggest-player/${encodeURIComponent(query)}`);
                    let data = await res.json();
                    if (data.status === 'success' && data.suggestions && data.suggestions.length > 0) {
                        suggestBox.innerHTML = data.suggestions.map(name => `<li class="px-5 py-3 hover:bg-[#005A9C] hover:text-white cursor-pointer transition-colors border-b border-gray-50 last:border-b-0" onmousedown="selectSuggestion('${name.replace(/'/g, "\\'")}')">${name}</li>`).join('');
                        suggestBox.classList.remove('hidden');
                    } else { suggestBox.classList.add('hidden'); }
                } catch (err) { console.error(err); }
            }, 300); 
        });
        searchInput.addEventListener('blur', () => suggestBox.classList.add('hidden'));
        searchInput.addEventListener('focus', () => { if(suggestBox.innerHTML !== '') suggestBox.classList.remove('hidden'); });
    }
}, 500);

function selectSuggestion(name) {
    document.getElementById('deep-search-input').value = name;
    document.getElementById('search-suggestions').classList.add('hidden');
    executeDeepSearch(); 
}

async function executeDeepSearch() {
    const name = document.getElementById('deep-search-input').value;
    if(!name) return;
    const yearElem = document.getElementById('filter-year');
    const year = yearElem ? yearElem.value : 2026;
    
    const panel = document.getElementById('deep-search-results');
    panel.classList.remove('hidden');
    switchDSTab('ds-tab-basic');
    
    document.getElementById('ds-name').innerText = "搜尋中...";
    document.getElementById('ds-stats-grid').innerHTML = `<div class="col-span-2 text-center text-[#005A9C] text-xl font-bold animate-pulse py-8">連線至 ${year} MLB 官方資料庫與 Savant...</div>`;
    document.getElementById('ds-pr-bars').innerHTML = '';
    document.getElementById('ds-scout-text').innerText = '分析中...';
    
    try {
        let res = await fetch(`${API_BASE_URL}/deep-search/${name}?year=${year}`);
        let data = await res.json();
        
        if(data.status === "success") {
            const info = data.player_info;
            const h_st = data.hitting_stats || {};
            const p_st = data.pitching_stats || {};
            const h_adv = data.hitting_adv || {};
            const p_adv = data.pitching_adv || {};
            const h_prs = data.hitting_prs || {};
            const p_prs = data.pitching_prs || {};
            
            document.getElementById('ds-name').innerText = info.Name;
            
            let posArray = Array.isArray(info.PrimaryPos) ? info.PrimaryPos : [info.PrimaryPos];
            let posHtml = posArray.map(p => `<span class="bg-[#005A9C] text-white px-4 py-2 rounded-2xl text-3xl md:text-4xl font-black shadow-md border-2 border-white/20">${p}</span>`).join('');
            const posContainer = document.getElementById('ds-pos');
            posContainer.className = "flex flex-wrap gap-3 justify-center md:justify-start";
            posContainer.innerHTML = posHtml;

            document.getElementById('ds-bio').innerText = `賽季: ${data.year} | 年齡: ${info.Age} | 身高: ${info.Height} | 體重: ${info.Weight} | 投打: ${info.Throws}/${info.Bats}`;
            
            let statsHtml = '';
            if (data.has_hitting) {
                if (data.is_two_way) statsHtml += `<div class="col-span-2 font-black text-xl text-[#005A9C] border-b pb-2 mb-3">⚾ 打擊數據 (${data.year})</div>`;
                statsHtml += `<div class="bg-white p-4 rounded-xl border border-gray-200 shadow-sm"><div class="text-sm text-gray-500 font-bold mb-1">HR</div><div class="text-4xl font-black text-gray-800">${h_st.homeRuns||0}</div></div>`;
                statsHtml += `<div class="bg-white p-4 rounded-xl border border-gray-200 shadow-sm"><div class="text-sm text-gray-500 font-bold mb-1">AVG</div><div class="text-4xl font-black text-gray-800">${h_st.avg||'.000'}</div></div>`;
                statsHtml += `<div class="bg-white p-4 rounded-xl border border-gray-200 shadow-sm"><div class="text-sm text-gray-500 font-bold mb-1">OPS</div><div class="text-4xl font-black text-[#005A9C]">${h_st.ops||'.000'}</div></div>`;
                statsHtml += `<div class="bg-white p-4 rounded-xl border border-gray-200 shadow-sm"><div class="text-sm text-gray-500 font-bold mb-1">xwOBA</div><div class="text-4xl font-black text-[#005A9C]">${h_adv.xwOBA||'-'}</div></div>`;
                statsHtml += `<div class="bg-white p-4 rounded-xl border border-gray-200 shadow-sm"><div class="text-sm text-gray-500 font-bold mb-1">EV (mph)</div><div class="text-4xl font-black text-orange-500">${h_adv.EV||'-'}</div></div>`;
                statsHtml += `<div class="bg-white p-4 rounded-xl border border-gray-200 shadow-sm"><div class="text-sm text-gray-500 font-bold mb-1">SB</div><div class="text-4xl font-black text-green-600">${h_st.stolenBases||0}</div></div>`;
            }
            if (data.has_pitching) {
                if (data.is_two_way) statsHtml += `<div class="col-span-2 font-black text-xl text-[#005A9C] border-b pb-2 mb-3 mt-4">🎯 投球數據 (${data.year})</div>`;
                statsHtml += `<div class="bg-white p-4 rounded-xl border border-gray-200 shadow-sm"><div class="text-sm text-gray-500 font-bold mb-1">ERA</div><div class="text-4xl font-black text-[#005A9C]">${p_st.era||'0.00'}</div></div>`;
                statsHtml += `<div class="bg-white p-4 rounded-xl border border-gray-200 shadow-sm"><div class="text-sm text-gray-500 font-bold mb-1">WHIP</div><div class="text-4xl font-black text-gray-800">${p_st.whip||'0.00'}</div></div>`;
                statsHtml += `<div class="bg-white p-4 rounded-xl border border-gray-200 shadow-sm"><div class="text-sm text-gray-500 font-bold mb-1">IP (局數)</div><div class="text-4xl font-black text-gray-800">${p_st.inningsPitched||'0.0'}</div></div>`;
                statsHtml += `<div class="bg-white p-4 rounded-xl border border-gray-200 shadow-sm"><div class="text-sm text-gray-500 font-bold mb-1">SO (三振)</div><div class="text-4xl font-black text-red-600">${p_st.strikeOuts||0}</div></div>`;
                statsHtml += `<div class="bg-white p-4 rounded-xl border border-gray-200 shadow-sm"><div class="text-sm text-gray-500 font-bold mb-1">FIP (獨立防禦率)</div><div class="text-4xl font-black text-yellow-600">${p_adv.FIP||'-'}</div></div>`;
                statsHtml += `<div class="bg-white p-4 rounded-xl border border-gray-200 shadow-sm"><div class="text-sm text-gray-500 font-bold mb-1">xwOBA (被打)</div><div class="text-4xl font-black text-[#005A9C]">${p_adv.xwOBA||'-'}</div></div>`;
                statsHtml += `<div class="bg-white p-4 rounded-xl border border-gray-200 shadow-sm"><div class="text-sm text-gray-500 font-bold mb-1">W - L (勝敗)</div><div class="text-4xl font-black text-gray-800">${p_st.wins||0}-${p_st.losses||0}</div></div>`;
                statsHtml += `<div class="bg-white p-4 rounded-xl border border-gray-200 shadow-sm"><div class="text-sm text-gray-500 font-bold mb-1">SV / HLD</div><div class="text-4xl font-black text-orange-500">${p_st.saves||0} / ${p_st.holds||0}</div></div>`;
            }
            if (!data.has_hitting && !data.has_pitching) statsHtml = `<div class="col-span-2 text-center text-gray-500 py-6 text-xl">${data.year} 年無出賽紀錄</div>`;
            document.getElementById('ds-stats-grid').innerHTML = statsHtml;

            let prHtml = '';
            const renderBarGroup = (prsDict, titlePrefix = '') => {
                let html = '';
                for (const [key, val] of Object.entries(prsDict)) {
                    let barColor = val >= 75 ? 'bg-[#CE1141]' : (val >= 50 ? 'bg-[#005A9C]' : 'bg-gray-400');
                    let displayWidth = Math.max(4, val);
                    html += `<div class="mb-4"><div class="flex justify-between text-base mb-2"><span class="font-bold text-gray-700">${titlePrefix}${key}</span><span class="font-black text-gray-900 text-lg">PR ${val}</span></div><div class="w-full bg-gray-200 rounded-full h-3"><div class="${barColor} h-3 rounded-full shadow-sm transition-all duration-1000 ease-out" style="width: ${displayWidth}%"></div></div></div>`;
                }
                return html;
            };
            if (data.is_two_way) { prHtml += `<div class="font-black text-base text-[#005A9C] mb-3">⚾ 打擊評分 (Batting PR)</div>` + renderBarGroup(h_prs) + `<div class="font-black text-base text-[#005A9C] mb-3 mt-6">🎯 投球評分 (Pitching PR)</div>` + renderBarGroup(p_prs); } 
            else if (data.has_hitting) { prHtml += renderBarGroup(h_prs); } 
            else if (data.has_pitching) { prHtml += renderBarGroup(p_prs); }
            document.getElementById('ds-pr-bars').innerHTML = prHtml;
            document.getElementById('ds-scout-text').innerText = data.scout_report;

            const renderStatBar = (label, valueStr, min, max, reverse = false) => {
                let cleanStr = String(valueStr).replace(/[^0-9.-]+/g, ""); let val = parseFloat(cleanStr); if (isNaN(val)) val = 0;
                let pct = ((val - min) / (max - min)) * 100; pct = Math.max(0, Math.min(100, pct));
                let goodness = reverse ? 100 - pct : pct;
                let barColor = goodness >= 75 ? 'bg-[#CE1141]' : (goodness >= 50 ? 'bg-[#005A9C]' : 'bg-gray-400');
                let displayWidth = Math.max(4, goodness);
                return `<div class="mb-4"><div class="flex justify-between text-base mb-2"><span class="font-bold text-gray-700">${label}</span><span class="font-black text-gray-900 text-lg">${valueStr}</span></div><div class="w-full bg-gray-200 rounded-full h-3"><div class="${barColor} h-3 rounded-full shadow-sm transition-all duration-1000 ease-out" style="width: ${displayWidth}%"></div></div></div>`;
            };

            const plt = data.platoon_stats || {hitting: {vl:{}, vr:{}}, pitching: {vl:{}, vr:{}}};
            let pltHtml = '<div class="grid grid-cols-1 md:grid-cols-2 gap-8">';
            if (data.has_hitting) {
                const vl = plt.hitting.vl, vr = plt.hitting.vr;
                if(data.is_two_way) pltHtml += `<div class="col-span-1 md:col-span-2 font-black text-2xl text-[#005A9C] border-b-2 pb-2 mb-2">⚾ 打擊：左右投對戰</div>`;
                pltHtml += `<div class="bg-gray-50 border border-gray-200 p-6 rounded-2xl shadow-sm hover:shadow-lg transition-shadow"><h3 class="text-2xl font-black text-gray-800 mb-6 border-b-2 border-red-500 pb-3">⚔️ vs 左投 (LHP)</h3>${renderStatBar('AVG', vl.avg || '.000', 0.150, 0.350)}${renderStatBar('OPS', vl.ops || '.000', 0.500, 1.000)}${renderStatBar('HR', vl.homeRuns || '0', 0, 20)}<div class="mt-5 flex justify-between items-center text-base border-t pt-4 border-gray-200"><span class="font-bold text-gray-700">三振 (SO) / 保送 (BB)</span><span class="font-black text-2xl text-gray-900">${vl.strikeOuts||0} <span class="text-gray-400">/</span> ${vl.baseOnBalls||0}</span></div></div>`;
                pltHtml += `<div class="bg-gray-50 border border-gray-200 p-6 rounded-2xl shadow-sm hover:shadow-lg transition-shadow"><h3 class="text-2xl font-black text-gray-800 mb-6 border-b-2 border-[#005A9C] pb-3">⚔️ vs 右投 (RHP)</h3>${renderStatBar('AVG', vr.avg || '.000', 0.150, 0.350)}${renderStatBar('OPS', vr.ops || '.000', 0.500, 1.000)}${renderStatBar('HR', vr.homeRuns || '0', 0, 20)}<div class="mt-5 flex justify-between items-center text-base border-t pt-4 border-gray-200"><span class="font-bold text-gray-700">三振 (SO) / 保送 (BB)</span><span class="font-black text-2xl text-gray-900">${vr.strikeOuts||0} <span class="text-gray-400">/</span> ${vr.baseOnBalls||0}</span></div></div>`;
            }
            if (data.has_pitching) {
                const vl = plt.pitching.vl, vr = plt.pitching.vr;
                if(data.is_two_way) pltHtml += `<div class="col-span-1 md:col-span-2 font-black text-2xl text-[#005A9C] border-b-2 pb-2 mb-2 mt-6">🎯 投球：左右打對戰</div>`;
                pltHtml += `<div class="bg-gray-50 border border-gray-200 p-6 rounded-2xl shadow-sm hover:shadow-lg transition-shadow"><h3 class="text-2xl font-black text-gray-800 mb-6 border-b-2 border-red-500 pb-3">⚔️ vs 左打 (LHB)</h3>${renderStatBar('被打擊率 (AVG)', vl.avg || '.000', 0.150, 0.300, true)}${renderStatBar('被上壘率 (OBP)', vl.obp || '.000', 0.250, 0.400, true)}${renderStatBar('被全壘打', vl.homeRuns || '0', 0, 15, true)}<div class="mt-5 flex justify-between items-center text-base border-t pt-4 border-gray-200"><span class="font-bold text-gray-700">三振 (SO) / 保送 (BB)</span><span class="font-black text-2xl text-gray-900">${vl.strikeOuts||0} <span class="text-gray-400">/</span> ${vl.baseOnBalls||0}</span></div></div>`;
                pltHtml += `<div class="bg-gray-50 border border-gray-200 p-6 rounded-2xl shadow-sm hover:shadow-lg transition-shadow"><h3 class="text-2xl font-black text-gray-800 mb-6 border-b-2 border-[#005A9C] pb-3">⚔️ vs 右打 (RHB)</h3>${renderStatBar('被打擊率 (AVG)', vr.avg || '.000', 0.150, 0.300, true)}${renderStatBar('被上壘率 (OBP)', vr.obp || '.000', 0.250, 0.400, true)}${renderStatBar('被全壘打', vr.homeRuns || '0', 0, 15, true)}<div class="mt-5 flex justify-between items-center text-base border-t pt-4 border-gray-200"><span class="font-bold text-gray-700">三振 (SO) / 保送 (BB)</span><span class="font-black text-2xl text-gray-900">${vr.strikeOuts||0} <span class="text-gray-400">/</span> ${vr.baseOnBalls||0}</span></div></div>`;
            }
            pltHtml += '</div>';
            document.getElementById('ds-tab-platoon').innerHTML = pltHtml;

            const ha = data.ha_stats || {hitting: {home:{}, away:{}}, pitching: {home:{}, away:{}}};
            let haHtml = '<div class="grid grid-cols-1 md:grid-cols-2 gap-8">';
            if (data.has_hitting) {
                const hm = ha.hitting.home, aw = ha.hitting.away;
                if(data.is_two_way) haHtml += `<div class="col-span-1 md:col-span-2 font-black text-2xl text-[#005A9C] border-b-2 pb-2 mb-2">⚾ 打擊：主客場表現</div>`;
                haHtml += `<div class="bg-gray-50 border border-gray-200 p-6 rounded-2xl shadow-sm hover:shadow-lg transition-shadow"><h3 class="text-2xl font-black text-gray-800 mb-6 border-b-2 border-[#005A9C] pb-3">🏠 主場 (Home)</h3>${renderStatBar('AVG', hm.avg || '.000', 0.150, 0.350)}${renderStatBar('OPS', hm.ops || '.000', 0.500, 1.000)}${renderStatBar('HR', hm.homeRuns || '0', 0, 20)}<div class="mt-5 flex justify-between items-center text-base border-t pt-4 border-gray-200"><span class="font-bold text-gray-700">三振 (SO) / 保送 (BB)</span><span class="font-black text-2xl text-gray-900">${hm.strikeOuts||0} <span class="text-gray-400">/</span> ${hm.baseOnBalls||0}</span></div></div>`;
                haHtml += `<div class="bg-gray-50 border border-gray-200 p-6 rounded-2xl shadow-sm hover:shadow-lg transition-shadow"><h3 class="text-2xl font-black text-gray-800 mb-6 border-b-2 border-gray-500 pb-3">✈️ 客場 (Away)</h3>${renderStatBar('AVG', aw.avg || '.000', 0.150, 0.350)}${renderStatBar('OPS', aw.ops || '.000', 0.500, 1.000)}${renderStatBar('HR', aw.homeRuns || '0', 0, 20)}<div class="mt-5 flex justify-between items-center text-base border-t pt-4 border-gray-200"><span class="font-bold text-gray-700">三振 (SO) / 保送 (BB)</span><span class="font-black text-2xl text-gray-900">${aw.strikeOuts||0} <span class="text-gray-400">/</span> ${aw.baseOnBalls||0}</span></div></div>`;
            }
            if (data.has_pitching) {
                const hm = ha.pitching.home, aw = ha.pitching.away;
                if(data.is_two_way) haHtml += `<div class="col-span-1 md:col-span-2 font-black text-2xl text-[#005A9C] border-b-2 pb-2 mb-2 mt-6">🎯 投球：主客場表現</div>`;
                haHtml += `<div class="bg-gray-50 border border-gray-200 p-6 rounded-2xl shadow-sm hover:shadow-lg transition-shadow"><h3 class="text-2xl font-black text-gray-800 mb-6 border-b-2 border-[#005A9C] pb-3">🏠 主場 (Home)</h3>${renderStatBar('被打擊率 (AVG)', hm.avg || '.000', 0.150, 0.300, true)}${renderStatBar('被上壘率 (OBP)', hm.obp || '.000', 0.250, 0.400, true)}${renderStatBar('被全壘打', hm.homeRuns || '0', 0, 15, true)}<div class="mt-5 flex justify-between items-center text-base border-t pt-4 border-gray-200"><span class="font-bold text-gray-700">三振 (SO) / 保送 (BB)</span><span class="font-black text-2xl text-gray-900">${hm.strikeOuts||0} <span class="text-gray-400">/</span> ${hm.baseOnBalls||0}</span></div></div>`;
                haHtml += `<div class="bg-gray-50 border border-gray-200 p-6 rounded-2xl shadow-sm hover:shadow-lg transition-shadow"><h3 class="text-2xl font-black text-gray-800 mb-6 border-b-2 border-gray-500 pb-3">✈️ 客場 (Away)</h3>${renderStatBar('被打擊率 (AVG)', aw.avg || '.000', 0.150, 0.300, true)}${renderStatBar('被上壘率 (OBP)', aw.obp || '.000', 0.250, 0.400, true)}${renderStatBar('被全壘打', aw.homeRuns || '0', 0, 15, true)}<div class="mt-5 flex justify-between items-center text-base border-t pt-4 border-gray-200"><span class="font-bold text-gray-700">三振 (SO) / 保送 (BB)</span><span class="font-black text-2xl text-gray-900">${aw.strikeOuts||0} <span class="text-gray-400">/</span> ${aw.baseOnBalls||0}</span></div></div>`;
            }
            haHtml += '</div>';
            document.getElementById('ds-tab-splits').innerHTML = haHtml;

            const cr = data.career_stats || {hitting: [], pitching: []};
            let crHtml = '<div class="flex flex-col gap-8">';
            if (cr.hitting.length > 0) {
                if(data.is_two_way) crHtml += `<div class="font-black text-2xl text-[#005A9C] border-b-2 pb-2">⚾ 打擊生涯軌跡 (近 7 年)</div>`;
                crHtml += `<div class="overflow-x-auto"><table class="w-full text-left border-collapse bg-white rounded-xl shadow-md overflow-hidden"><thead><tr class="bg-[#005A9C] text-white text-sm uppercase"><th class="p-4 font-bold">Season</th><th class="p-4 font-bold">Team</th><th class="p-4 font-bold">G</th><th class="p-4 font-bold">HR</th><th class="p-4 font-bold">RBI</th><th class="p-4 font-bold">SB</th><th class="p-4 font-bold">AVG</th><th class="p-4 font-black text-yellow-300">OPS</th></tr></thead><tbody class="text-gray-800 text-lg">`;
                cr.hitting.forEach(s => { crHtml += `<tr class="border-b border-gray-100 hover:bg-blue-50 transition-colors"><td class="p-4 font-black text-gray-600">${s.season}</td><td class="p-4 font-bold text-[#005A9C]">${s.team}</td><td class="p-4 font-bold">${s.gamesPlayed||0}</td><td class="p-4 font-black text-gray-900">${s.homeRuns||0}</td><td class="p-4 font-bold text-gray-700">${s.runsBattedIn||0}</td><td class="p-4 font-bold text-gray-700">${s.stolenBases||0}</td><td class="p-4 font-bold text-gray-700">${s.avg||'.000'}</td><td class="p-4 font-black text-[#005A9C]">${s.ops||'.000'}</td></tr>`; });
                crHtml += `</tbody></table></div>`;
            }
            if (cr.pitching.length > 0) {
                if(data.is_two_way) crHtml += `<div class="font-black text-2xl text-[#005A9C] border-b-2 pb-2 mt-4">🎯 投球生涯軌跡 (近 7 年)</div>`;
                crHtml += `<div class="overflow-x-auto"><table class="w-full text-left border-collapse bg-white rounded-xl shadow-md overflow-hidden"><thead><tr class="bg-[#005A9C] text-white text-sm uppercase"><th class="p-4 font-bold">Season</th><th class="p-4 font-bold">Team</th><th class="p-4 font-bold">IP</th><th class="p-4 font-bold">W-L</th><th class="p-4 font-bold">SO</th><th class="p-4 font-bold">WHIP</th><th class="p-4 font-black text-yellow-300">ERA</th></tr></thead><tbody class="text-gray-800 text-lg">`;
                cr.pitching.forEach(s => { crHtml += `<tr class="border-b border-gray-100 hover:bg-blue-50 transition-colors"><td class="p-4 font-black text-gray-600">${s.season}</td><td class="p-4 font-bold text-[#005A9C]">${s.team}</td><td class="p-4 font-bold">${s.inningsPitched||0}</td><td class="p-4 font-black text-gray-900">${s.wins||0}-${s.losses||0}</td><td class="p-4 font-bold text-red-600">${s.strikeOuts||0}</td><td class="p-4 font-bold text-gray-700">${s.whip||'0.00'}</td><td class="p-4 font-black text-[#005A9C]">${s.era||'0.00'}</td></tr>`; });
                crHtml += `</tbody></table></div>`;
            }
            crHtml += '</div>';
            document.getElementById('ds-tab-career').innerHTML = crHtml;

            gsap.from("#deep-search-results", { opacity: 0, y: 20, duration: 0.5 });
        } else {
            document.getElementById('ds-name').innerText = "查無此人";
            document.getElementById('ds-stats-grid').innerHTML = `<div class="col-span-2 text-center text-red-500 text-xl font-bold py-6">${data.message}</div>`;
        }
    } catch(e) {
        document.getElementById('ds-name').innerText = "連線錯誤";
        document.getElementById('ds-stats-grid').innerHTML = `<div class="col-span-2 text-center text-red-500 text-xl font-bold py-6">無法連線至後端伺服器，請確認 api.py 已啟動</div>`;
    }
}

// 📅 抓取與渲染每日賽程 (含隊徽 + 放大佈局)
// 📅 抓取與渲染每日賽程 (字體放大版)
async function fetchDailySchedule() {
    const dateStr = document.getElementById('schedule-date').value;
    const grid = document.getElementById('daily-matches-grid');
    const panel = document.getElementById('prediction-panel');

    panel.classList.add('hidden');
    grid.innerHTML = `<div class="col-span-full text-center text-[#005A9C] text-2xl font-bold animate-pulse py-10">連線至 MLB 獲取 ${dateStr} 賽事列表...</div>`;

    try {
        let res = await fetch(`${API_BASE_URL}/daily-schedule?date_str=${dateStr}`);
        let data = await res.json();

        if (data.status === 'success') {
            if (!data.games || data.games.length === 0) {
                grid.innerHTML = `<div class="col-span-full text-center text-gray-500 text-3xl font-bold py-10">本日無賽事安排 🏖️</div>`;
                return;
            }

            let html = '';
            data.games.forEach(g => {
                let statusColor = g.status === 'Final' ? 'bg-gray-200 text-gray-700' : (g.status === 'Live' ? 'bg-red-500 text-white animate-pulse' : 'bg-[#005A9C] text-white');
                let isPreview = g.status !== 'Final' && g.status !== 'Live';
                
                let awayLogo = getTeamLogoUrl(g.away_team_id);
                let homeLogo = getTeamLogoUrl(g.home_team_id);

                html += `
                <div onclick="showPrediction('${g.home_team}', '${g.away_team}')" class="bg-white border-2 border-gray-200 rounded-3xl shadow-md hover:shadow-2xl hover:border-[#005A9C] transition-all cursor-pointer transform hover:-translate-y-2 overflow-hidden flex flex-col h-full">
                    <div class="${statusColor} px-6 py-3 flex justify-between items-center font-black text-base tracking-widest uppercase">
                        <span>${g.detailed_status || g.status}</span>
                        <span>Game ${g.game_pk.toString().slice(-4)}</span>
                    </div>
                    <div class="p-6 flex flex-col gap-4 flex-grow justify-center">
                        <div class="flex justify-between items-center gap-2">
                            <div class="flex flex-col items-center w-2/5 text-center">
                                <img src="${awayLogo}" class="w-16 h-16 md:w-20 md:h-20 object-contain mb-2 drop-shadow">
                                <span class="text-sm text-gray-400 font-bold uppercase mb-0.5">Away</span>
                                <span class="font-black text-gray-900 text-xl leading-tight h-12 flex items-center justify-center">${g.away_team}</span>
                            </div>
                            
                            <div class="font-black text-3xl text-gray-300 italic w-1/5 text-center">VS</div>
                            
                            <div class="flex flex-col items-center w-2/5 text-center">
                                <img src="${homeLogo}" class="w-16 h-16 md:w-20 md:h-20 object-contain mb-2 drop-shadow">
                                <span class="text-sm text-[#005A9C] font-bold uppercase mb-0.5">Home</span>
                                <span class="font-black text-[#005A9C] text-xl leading-tight h-12 flex items-center justify-center">${g.home_team}</span>
                            </div>
                        </div>
                        
                        <div class="bg-gray-50 rounded-2xl p-3.5 text-center border border-gray-100 shadow-inner my-1">
                            <span class="font-black text-4xl ${g.status === 'Final' ? 'text-gray-800' : 'text-[#CE1141]'}">${g.score}</span>
                        </div>
                        
                        ${isPreview ? `
                        <div class="flex flex-col text-base text-gray-700 font-bold mt-auto border-t border-gray-100 pt-3 gap-2">
                            <div class="flex justify-between items-center"><span class="text-gray-400 font-black text-sm">客發:</span> <span class="text-gray-900 font-black text-lg truncate pl-2">${g.away_pitcher}</span></div>
                            <div class="flex justify-between items-center"><span class="text-[#005A9C] font-black text-sm">主發:</span> <span class="text-[#005A9C] font-black text-lg truncate pl-2">${g.home_pitcher}</span></div>
                        </div>` : ''}
                    </div>
                    <div class="bg-gray-50 text-center py-3 text-sm font-black text-[#005A9C] uppercase tracking-widest border-t border-gray-200">
                        點擊卡片進行 AI 賽事預測 ⚡
                    </div>
                </div>`;
            });
            
            grid.innerHTML = html;
        } else {
            grid.innerHTML = `<div class="col-span-full text-center text-red-500 text-xl font-bold py-10">${data.message}</div>`;
        }
    } catch (e) {
        grid.innerHTML = `<div class="col-span-full text-center text-red-400 text-xl font-bold py-10">連線錯誤，無法獲取賽程。</div>`;
    }
}
// 🔮 顯示預測結果 (強制破甲版：100% 確保顯示球隊專屬 Logo 與大字體)
async function showPrediction(homeTeam, awayTeam) {
    const panel = document.getElementById('prediction-panel');
    const yearElem = document.getElementById('filter-year');
    const year = yearElem ? yearElem.value : 2026;

    panel.classList.remove('hidden');
    panel.innerHTML = `<div class="text-center text-[#005A9C] text-3xl font-black animate-pulse py-16">🔮 AI 賽事預測引擎運算中...<br><span class="text-lg text-gray-500 mt-4 block">正在匯入 ${homeTeam} 主場校正因子與雙方戰力...</span></div>`;
    
    panel.scrollIntoView({ behavior: 'smooth', block: 'center' });

    try {
        let res = await fetch(`${API_BASE_URL}/predict-matchup?home_team=${encodeURIComponent(homeTeam)}&away_team=${encodeURIComponent(awayTeam)}&year=${year}`);
        let data = await res.json();

        if (data.status === 'success') {
            const p = data.prediction;
            const pf = data.park_factor;
            const ms = data.matchup_stats; // 💡 接收後端傳來的主客場戰績
            
            // 🛡️ 強制比對隊徽
            const awayTeamObj = MLB_TEAMS_LIST.find(t => awayTeam.includes(t.name) || t.name.includes(awayTeam));
            const homeTeamObj = MLB_TEAMS_LIST.find(t => homeTeam.includes(t.name) || t.name.includes(homeTeam));
            
            const awayLogo = getTeamLogoUrl(awayTeamObj ? awayTeamObj.id : (data.away_team_id || 0));
            const homeLogo = getTeamLogoUrl(homeTeamObj ? homeTeamObj.id : (data.home_team_id || 0));

            let html = `
            <div class="flex justify-between items-center border-b-2 border-gray-200 pb-4 mb-8">
                <h2 class="text-3xl md:text-4xl font-black text-gray-800 flex items-center gap-3">🔮 AI 賽事對決預測報告</h2>
                <button onclick="document.getElementById('prediction-panel').classList.add('hidden')" class="text-gray-400 hover:text-red-600 font-black text-3xl transition-colors">✖ 關閉</button>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-3 gap-8 mb-10 items-center">
                <div class="flex flex-col items-center bg-gray-50 p-8 rounded-3xl border border-gray-200 shadow-sm relative overflow-hidden">
                    <span class="text-base font-black text-gray-400 uppercase tracking-widest mb-3">Away 客隊</span>
                    <img src="${awayLogo}" class="w-28 h-28 md:w-36 md:h-36 object-contain my-2 drop-shadow-md">
                    <span class="text-3xl font-black text-gray-900 text-center mb-4 h-16 flex items-center">${awayTeam}</span>
                    <div class="text-7xl font-black text-gray-600">${p.exp_away_runs}</div>
                    <span class="text-lg font-bold text-gray-400 mt-2">預期得分</span>
                </div>

                <div class="flex flex-col items-center justify-center">
                    <span class="text-7xl font-black text-gray-300 italic mb-6 drop-shadow-sm">VS</span>
                    <div class="bg-gradient-to-r from-red-500 to-orange-500 text-white p-6 rounded-2xl text-center shadow-xl transform hover:scale-105 transition-transform w-full">
                        <span class="block text-base font-black uppercase tracking-widest mb-1 text-white/90">預測總分 (O/U)</span>
                        <span class="text-5xl font-black">${(p.exp_away_runs + p.exp_home_runs).toFixed(1)}</span>
                    </div>
                </div>

                <div class="flex flex-col items-center bg-blue-50 p-8 rounded-3xl border border-blue-200 shadow-sm relative overflow-hidden">
                    <div class="absolute top-0 right-0 bg-[#005A9C] text-white text-sm font-black px-4 py-1.5 rounded-bl-2xl shadow-sm">主場優勢</div>
                    <span class="text-base font-black text-[#005A9C] uppercase tracking-widest mb-3">Home 主隊</span>
                    <img src="${homeLogo}" class="w-28 h-28 md:w-36 md:h-36 object-contain my-2 drop-shadow-md">
                    <span class="text-3xl font-black text-[#005A9C] text-center mb-4 h-16 flex items-center">${homeTeam}</span>
                    <div class="text-7xl font-black text-[#005A9C] drop-shadow-sm">${p.exp_home_runs}</div>
                    <span class="text-lg font-bold text-[#005A9C] mt-2">預期得分</span>
                </div>
            </div>

            <div class="mb-12 bg-white p-8 border border-gray-200 rounded-3xl shadow-sm">
                <div class="flex justify-between text-2xl font-black mb-4">
                    <span class="text-gray-800 flex items-center gap-3">
                        <img src="${awayLogo}" class="w-10 h-10 inline object-contain"> ${awayTeam} (<span class="text-4xl text-gray-900">${p.away_win_pct}%</span>)
                    </span>
                    <span class="text-[#005A9C] flex items-center gap-3">
                        (<span class="text-4xl text-[#005A9C]">${p.home_win_pct}%</span>) ${homeTeam} <img src="${homeLogo}" class="w-10 h-10 inline object-contain">
                    </span>
                </div>
                <div class="w-full bg-gray-200 rounded-full h-10 flex overflow-hidden shadow-inner relative">
                    <div class="absolute left-1/2 top-0 bottom-0 w-1 bg-white z-10 opacity-60"></div>
                    <div class="bg-gray-400 h-10 flex items-center justify-start px-5 text-white text-base font-black tracking-widest transition-all duration-1000 ease-out" style="width: ${p.away_win_pct}%">AWAY</div>
                    <div class="bg-[#005A9C] h-10 flex items-center justify-end px-5 text-white text-base font-black tracking-widest transition-all duration-1000 ease-out" style="width: ${p.home_win_pct}%">HOME</div>
                </div>
            </div>

            <div class="flex flex-col gap-10">
                
                <div class="bg-gray-50/80 p-8 rounded-3xl border border-gray-200 shadow-sm">
                    <h3 class="text-3xl font-black text-gray-800 mb-6 border-b-2 border-gray-200 pb-4 flex items-center gap-3">📊 雙方主客場戰績與核心數據</h3>
                    
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-8">
                        <div class="bg-white p-6 rounded-2xl border border-gray-200 shadow-sm hover:shadow-md transition-shadow">
                            <div class="flex items-center gap-4 mb-5 border-b border-gray-100 pb-4">
                                <img src="${awayLogo}" class="w-14 h-14 object-contain drop-shadow-sm">
                                <div class="font-black text-2xl text-gray-900">${awayTeam} <span class="text-gray-400 text-lg ml-1 font-bold">AWAY</span></div>
                            </div>
                            <div class="grid grid-cols-2 gap-y-6 gap-x-4">
                                <div class="flex flex-col"><span class="text-gray-500 font-bold text-lg mb-1">本季總戰績</span><span class="text-3xl font-black text-gray-800">${ms.away_overall}</span></div>
                                <div class="flex flex-col"><span class="text-gray-500 font-bold text-lg mb-1">✈️ 客場戰績</span><span class="text-3xl font-black text-[#CE1141]">${ms.away_record}</span></div>
                                <div class="flex flex-col"><span class="text-gray-500 font-bold text-lg mb-1">✈️ 客場 OPS</span><span class="text-3xl font-black text-blue-700">${ms.away_ops.toFixed(3)}</span></div>
                                <div class="flex flex-col"><span class="text-gray-500 font-bold text-lg mb-1">✈️ 客場 ERA</span><span class="text-3xl font-black text-green-600">${ms.away_era.toFixed(2)}</span></div>
                            </div>
                        </div>
                        
                        <div class="bg-white p-6 rounded-2xl border border-blue-200 shadow-sm hover:shadow-md transition-shadow">
                            <div class="flex items-center gap-4 mb-5 border-b border-blue-100 pb-4">
                                <img src="${homeLogo}" class="w-14 h-14 object-contain drop-shadow-sm">
                                <div class="font-black text-2xl text-[#005A9C]">${homeTeam} <span class="text-[#005A9C]/50 text-lg ml-1 font-bold">HOME</span></div>
                            </div>
                            <div class="grid grid-cols-2 gap-y-6 gap-x-4">
                                <div class="flex flex-col"><span class="text-gray-500 font-bold text-lg mb-1">本季總戰績</span><span class="text-3xl font-black text-gray-800">${ms.home_overall}</span></div>
                                <div class="flex flex-col"><span class="text-gray-500 font-bold text-lg mb-1">🏠 主場戰績</span><span class="text-3xl font-black text-[#CE1141]">${ms.home_record}</span></div>
                                <div class="flex flex-col"><span class="text-gray-500 font-bold text-lg mb-1">🏠 主場 OPS</span><span class="text-3xl font-black text-blue-700">${ms.home_ops.toFixed(3)}</span></div>
                                <div class="flex flex-col"><span class="text-gray-500 font-bold text-lg mb-1">🏠 主場 ERA</span><span class="text-3xl font-black text-green-600">${ms.home_era.toFixed(2)}</span></div>
                            </div>
                        </div>
                    </div>

                <div class="bg-gray-50/80 p-8 rounded-3xl border border-gray-200 shadow-sm">
                    <h3 class="text-3xl font-black text-gray-800 mb-6 border-b-2 border-gray-200 pb-4 flex items-center gap-3">🏟️ 球場環境因子 (Park Factors)</h3>
                    
                    <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
                        <div class="bg-white p-5 rounded-2xl border border-gray-100 shadow-sm flex justify-between items-center">
                            <span class="font-bold text-gray-600 text-xl">打擊綜合 (OPS)</span>
                            <span class="font-black text-3xl ${pf.OPS > 1 ? 'text-red-600' : 'text-[#005A9C]'}">${pf.OPS.toFixed(2)}</span>
                        </div>
                        <div class="bg-white p-5 rounded-2xl border border-gray-100 shadow-sm flex justify-between items-center">
                            <span class="font-bold text-gray-600 text-xl">全壘打 (HR)</span>
                            <span class="font-black text-3xl ${pf.HR > 1 ? 'text-red-600' : 'text-[#005A9C]'}">${pf.HR.toFixed(2)}</span>
                        </div>
                        <div class="bg-white p-5 rounded-2xl border border-gray-100 shadow-sm flex justify-between items-center">
                            <span class="font-bold text-gray-600 text-xl">防禦率 (ERA)</span>
                            <span class="font-black text-3xl ${pf.ERA > 1 ? 'text-red-600' : 'text-[#005A9C]'}">${pf.ERA.toFixed(2)}</span>
                        </div>
                    </div>
                    
                    <div class="p-5 bg-yellow-50 border-2 border-yellow-200 rounded-2xl text-yellow-900 font-bold text-xl shadow-sm">
                        💡 ${pf.desc}
                    </div>
                </div>

                <div class="bg-gray-50/80 p-8 rounded-3xl border border-gray-200 shadow-sm">
                    <h3 class="text-3xl font-black text-gray-800 mb-6 border-b-2 border-gray-200 pb-4 flex items-center gap-3">🤖 AI 球探賽前深度觀點</h3>
                    <div class="bg-gradient-to-br from-gray-800 via-gray-900 to-black text-white p-8 rounded-3xl text-xl leading-relaxed font-medium shadow-2xl border border-gray-700">
                        <ul class="list-disc pl-8 space-y-6">
                            ${data.scout_summary.map(s => `<li>${s.replace(/\*\*(.*?)\*\*/g, '<span class="text-yellow-300 font-black">$1</span>')}</li>`).join('')}
                        </ul>
                    </div>
                </div>
            </div>`;

            panel.innerHTML = html;
            gsap.from(panel, { opacity: 0, scale: 0.95, duration: 0.6, ease: 'back.out(1.5)' });
        } else {
            panel.innerHTML = `<div class="text-center text-red-500 font-bold text-2xl py-10">${data.message}</div>`;
        }
    } catch(e) {
        panel.innerHTML = `<div class="text-center text-red-400 font-bold text-2xl py-10">預測伺服器連線失敗。</div>`;
    }
}

const glassCard = document.getElementById('glass-card');
document.addEventListener('mousemove', (e) => { 
    glassCard.classList.add('active'); 
    glassCard.style.transform = `translate3d(${e.clientX}px, ${e.clientY}px, 0) translate(-50%, -50%)`; 
});
// 📊 6. 近況與數據排行 (Rankings)
let currentFanRankTimeframe = '本季';
let currentFanRankPType = '打者';

async function renderFantasyRankings() {
    const container = document.getElementById('fan-rankings');
    if (!document.getElementById('fan-rank-ptype')) {
        let html = `
        <div class="bg-white border border-gray-200 rounded-3xl shadow-sm p-8 mt-4 whitespace-nowrap overflow-x-auto">
            <div class="flex flex-col xl:flex-row justify-between items-start xl:items-center mb-8 gap-6 border-b-2 border-gray-100 pb-6">
                <h2 class="text-4xl font-black text-gray-800">📊 數據積分排行榜</h2>
                
                <div class="flex flex-nowrap gap-4">
                    <select id="fan-rank-league" onchange="updateFanRankings()" class="bg-blue-50 border border-blue-200 text-[#005A9C] text-xl font-black rounded-xl focus:ring-4 focus:ring-blue-300 px-5 py-3 outline-none cursor-pointer">
                        <option value="MLB">MLB 全聯盟</option><option value="AL">AL 美聯</option><option value="NL">NL 國聯</option>
                    </select>
                    <select id="fan-rank-ptype" onchange="handlePTypeChange()" class="bg-gray-50 border border-gray-300 text-gray-800 text-xl font-black rounded-xl focus:ring-4 focus:ring-gray-300 px-5 py-3 outline-none cursor-pointer">
                        <option value="打者">打者 (Hitters)</option><option value="投手">投手 (Pitchers)</option>
                    </select>
                    <select id="fan-rank-pos" onchange="updateFanRankings()" class="bg-gray-50 border border-gray-300 text-gray-800 text-xl font-bold rounded-xl focus:ring-4 focus:ring-gray-300 px-5 py-3 outline-none cursor-pointer">
                        <option value="ALL">所有打者 (ALL)</option><option value="C">捕手 (C)</option><option value="1B">一壘 (1B)</option><option value="2B">二壘 (2B)</option><option value="3B">三壘 (3B)</option><option value="SS">游擊 (SS)</option><option value="OF">外野 (OF)</option><option value="DH">指打 (DH)</option>
                    </select>
                    <select id="fan-rank-time" onchange="updateFanRankings()" class="bg-gray-800 border border-gray-700 text-white text-xl font-bold rounded-xl focus:ring-4 focus:ring-gray-500 px-5 py-3 outline-none cursor-pointer">
                        <option value="本季">本季 (Season)</option><option value="7天">近 7 天</option><option value="14天">近 14 天</option><option value="30天">近 30 天</option>
                    </select>
                </div>
            </div>
            <div id="fan-rank-content" class="text-center text-[#005A9C] text-2xl font-bold py-10">演算自訂計分排行中...</div>
        </div>`;
        container.innerHTML = html;
    }
    updateFanRankings();
}

async function updateFanRankings() {
    const ptype = document.getElementById('fan-rank-ptype').value;
    const time = document.getElementById('fan-rank-time').value;
    const league = document.getElementById('fan-rank-league').value;
    const pos = document.getElementById('fan-rank-pos').value;
    const year = document.getElementById('filter-year') ? document.getElementById('filter-year').value : 2026;
    
    const content = document.getElementById('fan-rank-content');
    content.innerHTML = `<div class="text-center text-[#005A9C] text-3xl font-bold py-10">套用篩選器計算中... ⏳</div>`;
    
    try {
        let res = await fetch(`${API_BASE_URL}/fantasy/rankings?timeframe=${encodeURIComponent(time)}&p_type=${encodeURIComponent(ptype)}&year=${year}&league=${league}&pos_filter=${pos}`);
        let data = await res.json();
        
        if (data.status === 'success') {
            if (data.data.length === 0) {
                content.innerHTML = `<div class="text-gray-500 font-bold text-center py-10 text-2xl">找不到符合條件的球員資料 🏖️</div>`; return;
            }
            let maxPts = Math.max(...data.data.map(p => p.fan_pts));
            let minPts = Math.min(...data.data.map(p => p.fan_pts));
            
            let tableHtml = `<div class="overflow-x-auto table-scroll-container"><table class="w-full text-left text-xl whitespace-nowrap"><thead class="bg-gray-900 text-white font-bold tracking-wider text-2xl"><tr>`;
            
            if (ptype === '打者') {
                let maxHR = Math.max(...data.data.map(p => p.hr));
                let maxSB = Math.max(...data.data.map(p => p.sb));
                let maxOPS = Math.max(...data.data.map(p => p.ops));

                tableHtml += `<th class="p-5 rounded-tl-xl w-20 text-center">Rnk</th><th class="p-5 w-72">Player</th><th class="p-5 text-center text-gray-300">PA</th><th class="p-5 text-center text-blue-300">HR</th><th class="p-5 text-center text-blue-300">RBI</th><th class="p-5 text-center text-blue-300">R</th><th class="p-5 text-center text-blue-300">SB</th><th class="p-5 text-center text-gray-300">AVG</th><th class="p-5 text-center text-blue-200">OPS</th><th class="p-5 text-center text-yellow-400 text-2xl font-black rounded-tr-xl bg-gray-800 border-l border-gray-700 w-40 shadow-inner">Fan Pts 🔥</th></tr></thead><tbody class="divide-y divide-gray-200">`;
                
                data.data.forEach((p, i) => {
                    let rankColor = i < 3 ? 'text-[#CE1141] font-black text-3xl' : 'text-gray-400 font-bold';
                    tableHtml += `<tr class="hover:bg-blue-50/50 transition-colors bg-white">
                        <td class="p-5 text-center ${rankColor}">#${i+1}</td>
                        <td class="p-5 border-r border-gray-100"><div class="font-black text-gray-900 text-2xl">${p.name}</div><div class="text-base text-gray-500 font-bold mt-1">${p.team} <span class="bg-gray-100 text-gray-600 px-2 py-0.5 rounded text-sm ml-1 border border-gray-200">${p.pos}</span></div></td>
                        <td class="p-5 text-center font-medium text-gray-500">${p.pa}</td>
                        <td class="p-5 text-center font-black" style="${getHeatmapColor(p.hr, 0, maxHR)}">${p.hr}</td>
                        <td class="p-5 text-center text-gray-700">${p.rbi}</td>
                        <td class="p-5 text-center text-gray-700">${p.r}</td>
                        <td class="p-5 text-center font-black" style="${getHeatmapColor(p.sb, 0, maxSB)}">${p.sb}</td>
                        <td class="p-5 text-center font-medium text-gray-500">${p.avg.toFixed(3)}</td>
                        <td class="p-5 text-center font-black" style="${getHeatmapColor(p.ops, 0.600, maxOPS)}">${p.ops.toFixed(3)}</td>
                        <td class="p-5 text-center text-4xl font-black border-l border-gray-200 shadow-[inset_4px_0_4px_-4px_rgba(0,0,0,0.05)]" style="${getHeatmapColor(p.fan_pts, minPts, maxPts)}">${p.fan_pts.toFixed(1)}</td>
                    </tr>`;
                });
            } else {
                let maxSO = Math.max(...data.data.map(p => p.so));
                let minERA = Math.min(...data.data.map(p => p.era));
                let maxERA = Math.max(...data.data.map(p => p.era));

                tableHtml += `<th class="p-5 rounded-tl-xl w-20 text-center">Rnk</th><th class="p-5 w-72">Player</th><th class="p-5 text-center text-gray-300">IP</th><th class="p-5 text-center text-blue-300">W-L</th><th class="p-5 text-center text-blue-300">SV/HLD</th><th class="p-5 text-center text-blue-300">SO</th><th class="p-5 text-center text-blue-200">ERA</th><th class="p-5 text-center text-gray-300">WHIP</th><th class="p-5 text-center text-yellow-400 text-2xl font-black rounded-tr-xl bg-gray-800 border-l border-gray-700 w-40 shadow-inner">Fan Pts 🔥</th></tr></thead><tbody class="divide-y divide-gray-200">`;
                
                data.data.forEach((p, i) => {
                    let rankColor = i < 3 ? 'text-[#CE1141] font-black text-3xl' : 'text-gray-400 font-bold';
                    tableHtml += `<tr class="hover:bg-blue-50/50 transition-colors bg-white">
                        <td class="p-5 text-center ${rankColor}">#${i+1}</td>
                        <td class="p-5 border-r border-gray-100"><div class="font-black text-gray-900 text-2xl">${p.name}</div><div class="text-base text-gray-500 font-bold mt-1">${p.team} <span class="bg-gray-100 text-gray-600 px-2 py-0.5 rounded text-sm ml-1 border border-gray-200">${p.pos}</span></div></td>
                        <td class="p-5 text-center font-medium text-gray-500">${formatInnings(p.ip)}</td>
                        <td class="p-5 text-center font-black text-gray-800">${p.w}-${p.l}</td>
                        <td class="p-5 text-center font-black text-orange-600">${p.sv}/${p.hld}</td>
                        <td class="p-5 text-center font-black" style="${getHeatmapColor(p.so, 0, maxSO)}">${p.so}</td>
                        <td class="p-5 text-center font-black" style="${getHeatmapColor(p.era, minERA, maxERA, true)}">${p.era.toFixed(2)}</td>
                        <td class="p-5 text-center font-medium text-gray-500">${p.whip.toFixed(2)}</td>
                        <td class="p-5 text-center text-4xl font-black border-l border-gray-200 shadow-[inset_4px_0_4px_-4px_rgba(0,0,0,0.05)]" style="${getHeatmapColor(p.fan_pts, minPts, maxPts)}">${p.fan_pts.toFixed(1)}</td>
                    </tr>`;
                });
            }
            tableHtml += `</tbody></table></div>`;
            content.innerHTML = tableHtml;
        } else { content.innerHTML = `<div class="text-red-500 font-bold text-center py-10 text-2xl">${data.message}</div>`; }
    } catch(e) { content.innerHTML = `<div class="text-red-500 font-bold py-10 text-center text-2xl">連線失敗，無法取得排行榜資料。</div>`; }
}

// ⚙️ 7. 聯盟設定與全套 27 項計分權重 (Settings)
async function renderFantasySettings() {
    const container = document.getElementById('fan-settings');
    container.innerHTML = `<div class="text-center text-[#005A9C] text-3xl font-bold animate-pulse py-10">讀取資料庫設定中...</div>`;
    
    try {
        let res = await fetch("https://mlb-war-room-l7ps.onrender.com/fantasy/settings");
        let data = await res.json();
        
        if (data.status === 'success') {
            const db = data.data;
            const hw = db.weights.hitter;
            const pw = db.weights.pitcher;
            
            let html = `
            <div class="max-w-6xl mx-auto bg-white border border-gray-200 rounded-3xl shadow-sm p-10 md:p-14 mt-4 whitespace-nowrap overflow-x-auto">
                <h2 class="text-4xl font-black text-gray-800 mb-10 border-b-2 border-gray-100 pb-5">⚙️ 聯盟名稱與 27 項加扣分權重設定</h2>
                
                <div class="grid grid-cols-1 md:grid-cols-2 gap-10 mb-12">
                    <div>
                        <label class="block text-gray-700 font-bold mb-3 text-xl">聯盟名稱 (League Name)</label>
                        <input type="text" id="set-league-name" value="${db.league_name}" class="w-full px-6 py-4 rounded-xl border border-gray-300 focus:ring-4 focus:ring-blue-300 font-black text-gray-900 bg-gray-50 outline-none text-2xl transition-all">
                    </div>
                    <div>
                        <label class="block text-gray-700 font-bold mb-3 text-xl">您的球隊名稱 (Team Name)</label>
                        <input type="text" id="set-team-name" value="${db.team_name}" class="w-full px-6 py-4 rounded-xl border border-gray-300 focus:ring-4 focus:ring-blue-300 font-black text-gray-900 bg-gray-50 outline-none text-2xl transition-all">
                    </div>
                </div>

                <div class="grid grid-cols-1 lg:grid-cols-2 gap-12 mb-12">
                    <div class="bg-blue-50/70 p-8 rounded-3xl border border-blue-100 shadow-sm">
                        <h3 class="text-3xl font-black text-[#005A9C] mb-8 flex items-center gap-2">⚾ 打者 14 項計分 (Hitter)</h3>
                        <div class="grid grid-cols-2 gap-5">
                            ${Object.keys(hw).map(k => `
                            <div class="flex items-center justify-between bg-white px-5 py-3 rounded-2xl border border-blue-100 shadow-sm hover:border-[#005A9C] transition-colors">
                                <span class="font-black text-gray-700 text-xl">${k}</span>
                                <input type="number" step="0.5" id="hw-${k}" value="${hw[k]}" class="w-24 text-center font-black text-2xl text-[#CE1141] bg-gray-50 border border-gray-200 rounded-xl py-2 focus:ring-4 focus:ring-blue-300 outline-none">
                            </div>`).join('')}
                        </div>
                    </div>
                    
                    <div class="bg-red-50/70 p-8 rounded-3xl border border-red-100 shadow-sm">
                        <h3 class="text-3xl font-black text-red-700 mb-8 flex items-center gap-2">🎯 投手 13 項計分 (Pitcher)</h3>
                        <div class="grid grid-cols-2 gap-5">
                            ${Object.keys(pw).map(k => `
                            <div class="flex items-center justify-between bg-white px-5 py-3 rounded-2xl border border-red-100 shadow-sm hover:border-red-500 transition-colors">
                                <span class="font-black text-gray-700 text-xl">${k}</span>
                                <input type="number" step="0.5" id="pw-${k}" value="${pw[k]}" class="w-24 text-center font-black text-2xl text-[#005A9C] bg-gray-50 border border-gray-200 rounded-xl py-2 focus:ring-4 focus:ring-red-300 outline-none">
                            </div>`).join('')}
                        </div>
                    </div>
                </div>
                
                <button onclick="saveFantasySettings()" class="w-full bg-gradient-to-r from-green-500 to-green-700 text-white font-black text-3xl py-6 rounded-2xl shadow-xl hover:scale-[1.02] hover:shadow-2xl transition-all flex justify-center items-center gap-3">
                    💾 儲存設定至 JSON 資料庫
                </button>
                <div id="set-msg" class="text-center font-black text-2xl mt-8 hidden"></div>
            </div>`;
            container.innerHTML = html;
        }
    } catch(e) {
        container.innerHTML = `<div class="text-red-500 text-center font-bold py-10 text-2xl">連線失敗</div>`;
    }
}

async function saveFantasySettings() {
    const msgBox = document.getElementById('set-msg');
    msgBox.classList.add('hidden');
    
    const leagueName = document.getElementById('set-league-name').value;
    const teamName = document.getElementById('set-team-name').value;
    
    const hwKeys = ["R", "H", "1B", "2B", "3B", "HR", "RBI", "SB", "BB", "HBP", "K", "E", "CYC", "SLAM"];
    const pwKeys = ["W", "L", "SHO", "SV", "OUT", "ER", "WP", "HLD", "QS", "BSV", "SO", "BB", "H"];
    
    let weights = { hitter: {}, pitcher: {} };
    hwKeys.forEach(k => {
        const elem = document.getElementById(`hw-${k}`);
        if(elem) weights.hitter[k] = parseFloat(elem.value) || 0;
    });
    pwKeys.forEach(k => {
        const elem = document.getElementById(`pw-${k}`);
        if(elem) weights.pitcher[k] = parseFloat(elem.value) || 0;
    });
    
   try {
        let res = await fetch("https://mlb-war-room-l7ps.onrender.com/fantasy/settings", {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ league_name: leagueName, team_name: teamName, weights: weights })
        });
        let data = await res.json();
        
        if (data.status === "success") {
            msgBox.innerHTML = `<span class="bg-green-100 text-green-700 border border-green-300 px-6 py-3 rounded-xl shadow-sm inline-block">${data.message}</span>`;
            msgBox.classList.remove('hidden');
            setTimeout(() => { msgBox.classList.add('hidden'); }, 4000);
        } else if (data.status === "warning") {
            // 🚨 新增：專門顯示 Firebase 失敗的警告
            msgBox.innerHTML = `<span class="bg-yellow-100 text-yellow-800 border border-yellow-300 px-6 py-3 rounded-xl shadow-sm inline-block">${data.message}</span>`;
            msgBox.classList.remove('hidden');
        } else {
            msgBox.innerHTML = `<span class="text-red-500">${data.message}</span>`;
            msgBox.classList.remove('hidden');
        }
    } catch(e) {
        msgBox.innerHTML = `<span class="text-red-500">❌ 儲存失敗，請確認後端已啟動。</span>`;
        msgBox.classList.remove('hidden');
    }
}
async function loadPlayerDatalist() {
    const datalist = document.getElementById('player-datalist');
    if (!datalist || !GLOBAL_DATA || GLOBAL_DATA.length === 0) return;

    let optionsHtml = '';
    let seen = new Set(); // 🛡️ 防呆機制：避免重複加入同名球員

    // 全員塞入搜尋下拉選單，選誰都能比對！
    GLOBAL_DATA.forEach(p => {
        // 💡 智能兼容大小寫 (後端現在傳過來的是小寫的 name)
        const playerName = p.name || p.Name || p.Player || p.player;
        const teamName = p.team || p.Team || 'FA';
        
        // 💡 自動偵測這筆資料是投手還是打者
        const role = (p.ip !== undefined || p.era !== undefined) ? '🎯投手' : '⚾打者';
        
        if (playerName) {
            // 💡 神級細節：把身份綁在 value 裡面！這樣選大谷翔平時才不會投手打者傻傻分不清楚！
            const optionValue = `${playerName} - ${role}`;
            
            if (!seen.has(optionValue)) {
                seen.add(optionValue);
                // 顯示：大谷翔平 (LAD) / 實際填入：Shohei Ohtani - ⚾打者
                optionsHtml += `<option value="${optionValue}">${playerName} (${teamName})</option>`;
            }
        }
    });
    datalist.innerHTML = optionsHtml;
}

function getHeatmapColor(value, minVal, maxVal, invert = false) {
    if (maxVal === minVal) return ''; // 避免除以零
    let ratio = (value - minVal) / (maxVal - minVal);
    ratio = Math.max(0, Math.min(1, ratio)); // 限制在 0~1
    if (invert) ratio = 1 - ratio; // 若 invert=true (如 ERA, K)，數值越低越紅
    
    // 從白色 (0) 漸變到深紅色 (1)
    const r = 255;
    const g = Math.round(255 * (1 - ratio) + 235 * ratio); // 255 -> 235
    const b = Math.round(255 * (1 - ratio) + 238 * ratio); // 255 -> 238
    
    // 如果 ratio 大於 0.5，給予微紅背景；大於 0.8 給予深紅背景
    if (ratio > 0.8) return `background-color: #FFCDD2; font-weight: 900; color: #B71C1C;`;
    if (ratio > 0.5) return `background-color: #FFEBEE; font-weight: 800; color: #C62828;`;
    if (ratio < 0.2) return `color: #9E9E9E;`; // 太低的分數變灰
    return `font-weight: 600;`;
}

async function updateFanRankings() {
    const ptype = document.getElementById('fan-rank-ptype').value;
    const time = document.getElementById('fan-rank-time').value;
    const league = document.getElementById('fan-rank-league').value;
    const pos = document.getElementById('fan-rank-pos').value;
    const year = document.getElementById('filter-year') ? document.getElementById('filter-year').value : 2026;
    
    const content = document.getElementById('fan-rank-content');
    content.innerHTML = `<div class="text-center text-[#005A9C] text-xl font-bold py-10">套用 ${league} 聯盟 ${pos} 篩選器計算中... ⏳</div>`;
    
    try {
        // 💡 終極防呆：把所有的變數都包上 encodeURIComponent，確保中文與特殊符號完美傳遞！
let res = await fetch(`${API_BASE_URL}/fantasy/rankings?timeframe=${encodeURIComponent(time)}&p_type=${encodeURIComponent(ptype)}&year=${encodeURIComponent(year)}&league=${encodeURIComponent(league)}&pos_filter=${encodeURIComponent(pos)}`);
        let data = await res.json();
        
        if (data.status === 'success') {
            if (data.data.length === 0) {
                content.innerHTML = `<div class="text-gray-500 font-bold text-center py-10 text-xl">找不到符合條件的球員資料 🏖️</div>`;
                return;
            }

            // 1. 找出各項目的最大值與最小值 (為了算熱力圖比例)
            let maxPts = Math.max(...data.data.map(p => p.fan_pts));
            let minPts = Math.min(...data.data.map(p => p.fan_pts));
            
            let tableHtml = `<div class="overflow-x-auto table-scroll-container"><table class="w-full text-left text-sm md:text-base whitespace-nowrap"><thead class="bg-gray-900 text-white font-bold tracking-wider"><tr>`;
            
            if (ptype === '打者') {
                let maxHR = Math.max(...data.data.map(p => p.hr));
                let maxSB = Math.max(...data.data.map(p => p.sb));
                let maxOPS = Math.max(...data.data.map(p => p.ops));

                tableHtml += `<th class="p-4 rounded-tl-xl w-16 text-center">Rnk</th><th class="p-4 w-64">Player</th><th class="p-4 text-center text-gray-300">PA</th><th class="p-4 text-center text-blue-300">HR</th><th class="p-4 text-center text-blue-300">RBI</th><th class="p-4 text-center text-blue-300">R</th><th class="p-4 text-center text-blue-300">SB</th><th class="p-4 text-center text-gray-300">AVG</th><th class="p-4 text-center text-blue-200">OPS</th><th class="p-4 text-center text-yellow-400 text-lg font-black rounded-tr-xl bg-gray-800 border-l border-gray-700 w-32 shadow-inner">Fan Pts 🔥</th></tr></thead><tbody class="divide-y divide-gray-200">`;
                
                data.data.forEach((p, i) => {
                    let rankColor = i < 3 ? 'text-[#CE1141] font-black text-2xl' : 'text-gray-400 font-bold';
                    tableHtml += `<tr class="hover:bg-blue-50/50 transition-colors bg-white">
                        <td class="p-4 text-center ${rankColor}">#${i+1}</td>
                        <td class="p-4 border-r border-gray-100"><div class="font-black text-gray-900 text-lg">${p.name}</div><div class="text-sm text-gray-500 font-bold mt-0.5">${p.team} <span class="bg-gray-100 text-gray-600 px-1.5 py-0.5 rounded text-xs ml-1 border border-gray-200">${p.pos}</span></div></td>
                        <td class="p-4 text-center font-medium text-gray-500">${p.pa}</td>
                        <td class="p-4 text-center" style="${getHeatmapColor(p.hr, 0, maxHR)}">${p.hr}</td>
                        <td class="p-4 text-center text-gray-700">${p.rbi}</td>
                        <td class="p-4 text-center text-gray-700">${p.r}</td>
                        <td class="p-4 text-center" style="${getHeatmapColor(p.sb, 0, maxSB)}">${p.sb}</td>
                        <td class="p-4 text-center font-medium text-gray-500">${p.avg.toFixed(3)}</td>
                        <td class="p-4 text-center" style="${getHeatmapColor(p.ops, 0.600, maxOPS)}">${p.ops.toFixed(3)}</td>
                        <td class="p-4 text-center text-2xl border-l border-gray-200 shadow-[inset_4px_0_4px_-4px_rgba(0,0,0,0.05)]" style="${getHeatmapColor(p.fan_pts, minPts, maxPts)}">${p.fan_pts.toFixed(1)}</td>
                    </tr>`;
                });
            } else {
                // 💡 雙重保險：API 若回傳 k，則 p.so 會失效，這裡改為 p.so || p.k，確保熱力圖正常運作
                let maxSO = Math.max(...data.data.map(p => p.so || p.k || 0));
                let minERA = Math.min(...data.data.map(p => p.era));
                let maxERA = Math.max(...data.data.map(p => p.era));

                tableHtml += `<th class="p-4 rounded-tl-xl w-16 text-center">Rnk</th><th class="p-4 w-64">Player</th><th class="p-4 text-center text-gray-300">IP</th><th class="p-4 text-center text-blue-300">W-L</th><th class="p-4 text-center text-blue-300">SV/HLD</th><th class="p-4 text-center text-blue-300">SO</th><th class="p-4 text-center text-blue-200">ERA</th><th class="p-4 text-center text-gray-300">WHIP</th><th class="p-4 text-center text-yellow-400 text-lg font-black rounded-tr-xl bg-gray-800 border-l border-gray-700 w-32 shadow-inner">Fan Pts 🔥</th></tr></thead><tbody class="divide-y divide-gray-200">`;
                
                data.data.forEach((p, i) => {
                    let rankColor = i < 3 ? 'text-[#CE1141] font-black text-2xl' : 'text-gray-400 font-bold';
                    tableHtml += `<tr class="hover:bg-blue-50/50 transition-colors bg-white">
                        <td class="p-4 text-center ${rankColor}">#${i+1}</td>
                        <td class="p-4 border-r border-gray-100"><div class="font-black text-gray-900 text-lg">${p.name}</div><div class="text-sm text-gray-500 font-bold mt-0.5">${p.team} <span class="bg-gray-100 text-gray-600 px-1.5 py-0.5 rounded text-xs ml-1 border border-gray-200">${p.pos}</span></div></td>
                        <td class="p-4 text-center font-black text-gray-600 text-lg">${formatInnings(p.ip)}</td>
                        <td class="p-4 text-center font-black text-gray-800">${p.w}-${p.l}</td>
                        <td class="p-4 text-center font-black text-orange-600">${p.sv}/${p.hld}</td>
                        <td class="p-4 text-center" style="${getHeatmapColor(p.so || p.k || 0, 0, maxSO)}">${p.so || p.k || 0}</td>
                        <td class="p-4 text-center" style="${getHeatmapColor(p.era, minERA, maxERA, true)}">${p.era.toFixed(2)}</td>
                        <td class="p-4 text-center font-medium text-gray-500">${p.whip.toFixed(2)}</td>
                        <td class="p-4 text-center text-2xl border-l border-gray-200 shadow-[inset_4px_0_4px_-4px_rgba(0,0,0,0.05)]" style="${getHeatmapColor(p.fan_pts, minPts, maxPts)}">${p.fan_pts.toFixed(1)}</td>
                    </tr>`;
                });
            }
            tableHtml += `</tbody></table></div>`;
            content.innerHTML = tableHtml;
        } else { content.innerHTML = `<div class="text-red-500 font-bold text-center py-10">${data.message}</div>`; }
    } catch(e) { content.innerHTML = `<div class="text-red-500 font-bold py-10 text-center">連線失敗，無法取得排行榜資料。</div>`; }
}
// 📊 全新的排行榜篩選引擎 (處理 打者/投手 切換連動守位)
function handlePTypeChange() {
    const ptype = document.getElementById('fan-rank-ptype').value;
    const posSelect = document.getElementById('fan-rank-pos');
    if (ptype === '打者') {
        posSelect.innerHTML = `<option value="ALL">所有打者 (ALL)</option><option value="C">捕手 (C)</option><option value="1B">一壘 (1B)</option><option value="2B">二壘 (2B)</option><option value="3B">三壘 (3B)</option><option value="SS">游擊 (SS)</option><option value="OF">外野 (OF)</option><option value="DH">指打 (DH)</option>`;
    } else {
        posSelect.innerHTML = `<option value="ALL">所有投手 (ALL)</option><option value="SP">先發 (SP)</option><option value="RP">後援 (RP)</option>`;
    }
    updateFanRankings();
}
// 🔄 調整球員先發板凳位置 (Slot)
async function updatePlayerSlot(name, newSlot) {
    try {
        let res = await fetch("https://mlb-war-room-l7ps.onrender.com/fantasy/update-player", {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name: name, slot: newSlot })
        });
        await res.json();
        renderYahooTeam(); // 瞬間重整畫面，球員會自動跳到對應的表格 (先發或板凳)
    } catch(e) { alert("連線失敗，無法更新位置。"); }
}

// ✏️ 自訂球員守備位置 (Pos)
async function updatePlayerPos(name, currentPos) {
    let newPos = prompt(`請為 ${name} 自訂新的守備位置 (例如: SS, 2B, OF)：`, currentPos);
    if (newPos !== null && newPos.trim() !== "") {
        try {
            let res = await fetch("https://mlb-war-room-l7ps.onrender.com/fantasy/update-player", {
                method: "POST", headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ name: name, pos: newPos.trim().toUpperCase() })
            });
            await res.json();
            renderYahooTeam(); // 瞬間重整畫面顯示新守位
        } catch(e) { alert("連線失敗，無法自訂守位。"); }
    }
}
// 🎯 手動修改/更新實際分數 (Real Pts)
window.updateRealPts = async function(name, newPts) {
    try {
        let pts = parseFloat(newPts);
        if (isNaN(pts)) pts = 0.0;
        
        let res = await fetch("https://mlb-war-room-l7ps.onrender.com/fantasy/update-player", {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name: name, real_pts: pts })
        });
        // 💡 為了不打斷總教練連續輸入的節奏，這裡我們只默默儲存，不重新整理畫面！
        console.log(`已成功將 ${name} 的實際分數更新為 ${pts}`);
    } catch(e) {
        alert("連線失敗，無法更新實際分數。");
    }
}
// 🔄 切換聯盟或球隊 (支援動態讀取不同資料)
async function handleContextChange(isLeagueChange) {
    const l = document.getElementById('fan-league-select').value;
    let t = document.getElementById('fan-team-select').value;
    if (isLeagueChange) t = ""; // 若切換聯盟，讓後端自動抓該聯盟的第一支球隊
    
    try {
        awaitfetch("https://mlb-war-room-l7ps.onrender.com/fantasy/switch-context", {
            method: "POST", headers: {"Content-Type":"application/json"},
            body: JSON.stringify({league: l, team: t})
        });
        renderYahooTeam(); // 瞬間重整畫面，讀取新陣容
    } catch(e) { alert("切換失敗"); }
}

// ➕ 新增聯盟或球隊
async function createNewLeagueOrTeam() {
    const action = prompt("請選擇新增項目 (輸入 1 或 2)：\n1. 建立新聯盟 (包含一支新球隊)\n2. 在當前聯盟建立一支新球隊");
    if (action === "1") {
        const lName = prompt("請為您的新聯盟命名：");
        if(lName && lName.trim()) {
            await fetch("https://mlb-war-room-l7ps.onrender.com/fantasy/switch-context", {
                method: "POST", headers: {"Content-Type":"application/json"},
                body: JSON.stringify({league: lName.trim(), team: "我的新球隊"})
            });
            renderYahooTeam();
        }
    } else if (action === "2") {
        const tName = prompt("請為您的新球隊命名：");
        const currentL = document.getElementById('fan-league-select').value;
        if(tName && tName.trim()) {
            await fetch("https://mlb-war-room-l7ps.onrender.com/fantasy/switch-context", {
                method: "POST", headers: {"Content-Type":"application/json"},
                body: JSON.stringify({league: currentL, team: tName.trim()})
            });
            renderYahooTeam();
        }
    }
}
// ⚡ 一鍵簽下 AI 推薦球員
async function quickAddPlayer(name, team, pos) {
    try {
        let res = await fetch("https://mlb-war-room-l7ps.onrender.com/fantasy/add-player", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({ name: name, team: team, pos: pos })
        });
        let data = await res.json();
        if (data.status === "success") {
            alert(`🎉 成功將 ${name} 簽下入隊！`);
            renderYahooTeam(); // 瞬間重新整理陣容
        } else {
            alert(`⚠️ ${data.message}`);
        }
    } catch(e) {
        alert("簽下球員失敗，請確認後端服務正常。");
    }
}
// 👑 渲染 MVP 與 🏆 賽揚獎預測排行榜 (大字體 + 粗黑顯眼 AVG / WHIP 版)
async function renderMVPView() {
    const container = document.getElementById('view-mvp');
    if (!container) return;
    
    const yearElem = document.getElementById('filter-year');
    const year = yearElem ? yearElem.value : 2026;
    
    container.innerHTML = `<div class="text-center text-[#005A9C] text-2xl font-bold animate-pulse py-16">連線至大數據資料庫，運算 ${year} 賽季 MVP 與賽揚獎預測指數... ⏳</div>`;
    
    try {
        let res = await fetch(`${API_BASE_URL}/mvp-cyyoung?year=${year}`);
        let data = await res.json();
        
        if (data.status === "success") {
            const renderMVPTable = (list, title, isAL) => {
                let badgeColor = isAL ? 'bg-red-600' : 'bg-blue-600';
                let html = `
                <div class="bg-white border-2 border-gray-200 rounded-3xl shadow-lg overflow-hidden flex flex-col">
                    <div class="bg-gray-900 text-white px-6 py-5 border-b border-gray-800 font-black text-2xl flex justify-between items-center">
                        <span>👑 ${title}</span>
                        <span class="${badgeColor} text-white text-sm font-black px-4 py-1.5 rounded-full uppercase tracking-wider">${isAL ? 'AL 美聯' : 'NL 國聯'}</span>
                    </div>
                    <div class="overflow-x-auto">
                        <table class="w-full text-left text-lg whitespace-nowrap">
                            <thead class="bg-gray-100 text-gray-700 font-black border-b-2 border-gray-200 text-base">
                                <tr>
                                    <th class="p-4 text-center w-14">Rnk</th>
                                    <th class="p-4">Player</th>
                                    <th class="p-4 text-center">HR</th>
                                    <th class="p-4 text-center">RBI</th>
                                    <th class="p-4 text-center">AVG</th>
                                    <th class="p-4 text-center">OPS</th>
                                    <th class="p-4 text-center text-[#005A9C] font-black">MVP 指數</th>
                                </tr>
                            </thead>
                            <tbody class="divide-y divide-gray-100">`;
                
                list.forEach((p, i) => {
                    let rankBadge = i === 0 ? '🥇' : (i === 1 ? '🥈' : (i === 2 ? '🥉' : `#${i+1}`));
                    let rowBg = i < 3 ? 'bg-yellow-50/50 font-bold' : 'hover:bg-gray-50';
                    html += `
                    <tr class="${rowBg} transition-colors">
                        <td class="p-4 text-center font-black text-xl text-gray-800">${rankBadge}</td>
                        <td class="p-4">
                            <div class="font-black text-gray-900 text-xl">${p.name}</div>
                            <div class="text-sm text-gray-500 font-bold mt-0.5">${p.team} - ${p.pos}</div>
                        </td>
                        <td class="p-4 text-center font-black text-gray-900 text-lg">${p.hr}</td>
                        <td class="p-4 text-center font-black text-gray-800 text-lg">${p.rbi}</td>
                        <td class="p-4 text-center font-black text-gray-900 text-lg bg-gray-50/60 rounded-xl">${p.avg.toFixed(3)}</td>
                        <td class="p-4 text-center font-black text-[#005A9C] text-xl">${p.ops.toFixed(3)}</td>
                        <td class="p-4 text-center font-black text-2xl text-[#CE1141]">${p.mvp_score}</td>
                    </tr>`;
                });
                html += `</tbody></table></div></div>`;
                return html;
            };

            const renderCYTable = (list, title, isAL) => {
                let badgeColor = isAL ? 'bg-red-600' : 'bg-blue-600';
                let html = `
                <div class="bg-white border-2 border-gray-200 rounded-3xl shadow-lg overflow-hidden flex flex-col">
                    <div class="bg-gray-900 text-white px-6 py-5 border-b border-gray-800 font-black text-2xl flex justify-between items-center">
                        <span>🏆 ${title}</span>
                        <span class="${badgeColor} text-white text-sm font-black px-4 py-1.5 rounded-full uppercase tracking-wider">${isAL ? 'AL 美聯' : 'NL 國聯'}</span>
                    </div>
                    <div class="overflow-x-auto">
                        <table class="w-full text-left text-lg whitespace-nowrap">
                            <thead class="bg-gray-100 text-gray-700 font-black border-b-2 border-gray-200 text-base">
                                <tr>
                                    <th class="p-4 text-center w-14">Rnk</th>
                                    <th class="p-4">Player</th>
                                    <th class="p-4 text-center">W-L</th>
                                    <th class="p-4 text-center">SO</th>
                                    <th class="p-4 text-center">ERA</th>
                                    <th class="p-4 text-center">WHIP</th>
                                    <th class="p-4 text-center text-[#005A9C] font-black">賽揚指數</th>
                                </tr>
                            </thead>
                            <tbody class="divide-y divide-gray-100">`;
                
                list.forEach((p, i) => {
                    let rankBadge = i === 0 ? '🥇' : (i === 1 ? '🥈' : (i === 2 ? '🥉' : `#${i+1}`));
                    let rowBg = i < 3 ? 'bg-blue-50/50 font-bold' : 'hover:bg-gray-50';
                    html += `
                    <tr class="${rowBg} transition-colors">
                        <td class="p-4 text-center font-black text-xl text-gray-800">${rankBadge}</td>
                        <td class="p-4">
                            <div class="font-black text-gray-900 text-xl">${p.name}</div>
                            <div class="text-sm text-gray-500 font-bold mt-0.5">${p.team} - ${p.pos}</div>
                        </td>
                        <td class="p-4 text-center font-black text-gray-800 text-lg">${p.w}-${p.l}</td>
                        <td class="p-4 text-center text-red-600 font-black text-lg">${p.so}</td>
                        <td class="p-4 text-center font-black text-[#005A9C] text-xl">${p.era.toFixed(2)}</td>
                        <td class="p-4 text-center font-black text-gray-900 text-lg bg-gray-50/60 rounded-xl">${p.whip.toFixed(2)}</td>
                        <td class="p-4 text-center font-black text-2xl text-[#CE1141]">${p.cy_score}</td>
                    </tr>`;
                });
                html += `</tbody></table></div></div>`;
                return html;
            };

            let html = `
            <div class="flex flex-col gap-12">
                <div>
                    <h2 class="text-3xl font-black text-gray-900 mb-6 flex items-center gap-3 border-b-4 border-gray-200 pb-3">
                        👑 年度 MVP 競逐排行榜
                        <span class="text-base text-gray-500 font-bold"> (綜合 OPS, HR, RBI, SB 大數據權重)</span>
                    </h2>
                    <div class="grid grid-cols-1 lg:grid-cols-2 gap-8">
                        ${renderMVPTable(data.al_mvp, '美聯 MVP (AL MVP)', true)}
                        ${renderMVPTable(data.nl_mvp, '國聯 MVP (NL MVP)', false)}
                    </div>
                </div>

                <div>
                    <h2 class="text-3xl font-black text-gray-900 mb-6 flex items-center gap-3 border-b-4 border-gray-200 pb-3">
                        🏆 年度賽揚獎 (Cy Young) 競逐排行榜
                        <span class="text-base text-gray-500 font-bold"> (綜合 ERA, WHIP, SO, 勝投, IP 賽揚指數)</span>
                    </h2>
                    <div class="grid grid-cols-1 lg:grid-cols-2 gap-8">
                        ${renderCYTable(data.al_cy, '美聯賽揚獎 (AL Cy Young)', true)}
                        ${renderCYTable(data.nl_cy, '國聯賽揚獎 (NL Cy Young)', false)}
                    </div>
                </div>
            </div>`;

            container.innerHTML = html;
        } else {
            container.innerHTML = `<div class="text-red-500 text-center font-bold py-10 text-xl">${data.message}</div>`;
        }
    } catch(e) {
        container.innerHTML = `<div class="text-red-500 text-center font-bold py-10 text-xl">連線失敗，請確認 api.py 服務已啟動。</div>`;
    }
}
// ==========================================
// 📊 動態更新散佈圖 X 軸與 Y 軸選項 (修復智慧掃描污染 Bug)
// ==========================================
window.updateMetricSelects = function() {
    const xSelect = document.getElementById('scatter-x');
    const ySelect = document.getElementById('scatter-y');
    if (!xSelect || !ySelect) return;

    // 💡 1. 抓取散佈圖專屬的投打選單
    const pType = document.getElementById('scatter-ptype')?.value || '打者';
    
    // ⚾ 定義打者與投手的核心數據指標
    const hitterMetrics = {
        "pa": "PA (打席)", "hr": "HR (全壘打)", "rbi": "RBI (打點)", "r": "R (得分)",
        "sb": "SB (盜壘)", "avg": "AVG (打擊率)", "ops": "OPS (整體攻擊指數)", "fan_pts": "Fantasy 預期積分",
        "wrc_plus": "wRC+ (進階攻擊)", "woba": "wOBA", "war": "WAR"
    };

    const pitcherMetrics = {
        "ip": "IP (投球局數)", "w": "W (勝投)", "l": "L (敗投)", "sv": "SV (救援成功)",
        "hld": "HLD (中繼成功)", "k": "K (三振數)", "era": "ERA (防禦率)", "whip": "WHIP (每局被上壘率)", 
        "fan_pts": "Fantasy 預期積分", "fip": "FIP", "war": "WAR"
    };

    // 使用展開運算子複製一份，避免互相污染
    let metrics = (pType === '打者') ? { ...hitterMetrics } : { ...pitcherMetrics };

    // 💡 2. 修正智慧掃描：精準抓取對應身分的第一個人當作樣本！
    if (GLOBAL_DATA && GLOBAL_DATA.length > 0) {
        // 尋找符合目前身分的第一筆資料
        let sample = GLOBAL_DATA.find(p => {
            if (pType === '打者') return p.pa !== undefined || p.ab !== undefined;
            return p.ip !== undefined || p.era !== undefined;
        });

        if (sample) {
            Object.keys(sample).forEach(key => {
                const kLower = key.toLowerCase();
                // 過濾掉文字與不相干的系統欄位
                if (!['id', 'rank', 'name', 'player', 'team', 'pos'].includes(kLower) && typeof sample[key] === 'number') {
                    if (!metrics[kLower]) {
                        metrics[kLower] = key.toUpperCase(); // 自動將其他數值轉大寫加入選單
                    }
                }
            });
        }
    }

    // 💡 3. 建立下拉選單 HTML
    let xHtml = '', yHtml = '';
    const metricKeys = Object.keys(metrics);

    metricKeys.forEach(key => {
        xHtml += `<option value="${key}">${metrics[key]}</option>`;
        yHtml += `<option value="${key}">${metrics[key]}</option>`;
    });

    xSelect.innerHTML = xHtml;
    ySelect.innerHTML = yHtml;

    // 💡 4. 設定切換後的最佳預設值，確保圖表立刻畫得出來
    if (pType === '打者') {
        xSelect.value = metrics['wrc_plus'] ? 'wrc_plus' : metricKeys[0];
        ySelect.value = metrics['ops'] ? 'ops' : metricKeys[1] || metricKeys[0];
    } else {
        xSelect.value = metrics['k'] ? 'k' : metricKeys[0];
        ySelect.value = metrics['era'] ? 'era' : metricKeys[1] || metricKeys[0];
    }
};
// ==========================================
// 📈 動態更新雷達圖的 6 大指標選項 (投打分離)
// ==========================================
window.updateRadarMetricSelects = function() {
    const pType = document.getElementById('radar-ptype')?.value || '打者';
    const isPitcher = (pType === '投手');

    const hitterMetrics = {
        "ops": "OPS", "woba": "wOBA", "wrc_plus": "wRC+", "xwoba": "xwOBA", "hard_hit": "HardHit%", "barrel": "Barrel%",
        "avg": "AVG", "obp": "OBP", "slg": "SLG", "hr": "HR", "rbi": "RBI", "sb": "SB", "war": "WAR", "chase": "Chase%", "whiff": "Whiff%"
    };

    const pitcherMetrics = {
        // 💡 關鍵修復 1：把 xera 綁定回正確的欄位名稱！
        "era": "ERA", "whip": "WHIP", "fip": "FIP", "k_pct": "K%", "bb_pct": "BB%", "xera": "xERA",
        "k": "K", "ip": "IP", "sv": "SV", "hld": "HLD", "war": "WAR", "hard_hit": "HardHit%", "barrel": "Barrel%", "whiff": "Whiff%"
    };

    const metrics = isPitcher ? pitcherMetrics : hitterMetrics;
    const metricKeys = Object.keys(metrics);

    const defaultHitters = ['ops', 'woba', 'wrc_plus', 'xwoba', 'hard_hit', 'barrel'];
    const defaultPitchers = ['era', 'whip', 'fip', 'k_pct', 'bb_pct', 'xera']; // 💡 修正預設值
    const defaults = isPitcher ? defaultPitchers : defaultHitters;

    for (let i = 1; i <= 6; i++) {
        const select = document.getElementById(`radar-metric-${i}`);
        if (select) {
            let html = '';
            metricKeys.forEach(k => {
                html += `<option value="${k}">${metrics[k]}</option>`;
            });
            select.innerHTML = html;
            select.value = defaults[i - 1] || metricKeys[0];
        }
    }
};
// ==========================================
// 🌌 繪製散佈圖 (核彈換布 + 自動去重音高亮版)
// ==========================================
window.drawScatter = function() {
    console.log("🚀 執行 drawScatter (投打分離無敵版)");
    try {
        if (!GLOBAL_DATA || GLOBAL_DATA.length === 0) return;

        // 💡 1. 先確認散佈圖現在要看的是「打者」還是「投手」
        const pType = document.getElementById('scatter-ptype')?.value || '打者';
        const isPitcher = (pType === '投手');

        // 💡 2. 嚴格把關：只把符合身分的球員放進去畫圖！
        let filteredData = GLOBAL_DATA.filter(p => {
            if (isPitcher) {
                return p.ip !== undefined || p.era !== undefined; // 有局數或防禦率就是投手
            } else {
                return p.pa !== undefined || p.ab !== undefined;  // 有打席或打數就是打者
            }
        });

        // 取得 X 軸與 Y 軸的指標
        const xLabel = document.getElementById('scatter-x')?.value;
        const yLabel = document.getElementById('scatter-y')?.value;

        if (!xLabel || !yLabel) {
            alert("請先選擇 X 軸與 Y 軸的指標！");
            return;
        }

        // 取得使用者想要「特別標亮」的球員名字 (並進行字串淨化與去重音)
        const searchInput = document.getElementById('scatter-search-input')?.value.trim();
        let searchParts = [];
        if (searchInput) {
            let searchClean = searchInput.split('-')[0].split('(')[0].normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/[,.']/g, '').trim().toLowerCase();
            searchParts = searchClean.split(/\s+/).filter(x => x);
        }

        const basePoints = [];
        const highlightPoints = [];

        // 💡 3. 使用過濾好的 filteredData 來畫圖，不要用混在一起的 GLOBAL_DATA！
        filteredData.forEach(p => {
            // 找出對應的屬性 (相容大小寫)
            let actualX = Object.keys(p).find(k => k.toLowerCase() === xLabel.toLowerCase()) || xLabel;
            let actualY = Object.keys(p).find(k => k.toLowerCase() === yLabel.toLowerCase()) || yLabel;

            let valX = parseFloat(p[actualX]);
            let valY = parseFloat(p[actualY]);

            // 確保數值有效才畫點
            if (!isNaN(valX) && !isNaN(valY)) {
                const pointData = {
                    x: valX,
                    y: valY,
                    name: p.name || p.Name || p.Player || "Unknown",
                    team: p.Team || p.team || ""
                };

                // 檢查這位球員是不是使用者想要「高亮」的對象
                let isHighlight = false;
                if (searchParts.length > 0) {
                    let pNameStr = String(pointData.name).normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/[,.']/g, '').toLowerCase();
                    if (searchParts.every(part => pNameStr.includes(part))) {
                        isHighlight = true;
                    }
                }

                if (isHighlight) {
                    highlightPoints.push(pointData);
                } else {
                    basePoints.push(pointData);
                }
            }
        });

        if (basePoints.length === 0 && highlightPoints.length === 0) {
            alert("目前選擇的指標沒有有效的數值可以繪製！");
            return;
        }

        // ==========================================
        // 🔥 核彈級解法：直接把舊畫布摧毀，換一張新的！
        // ==========================================
        let oldCanvas = document.getElementById('scatterChart');
        if (!oldCanvas) return;
        
        let canvasParent = oldCanvas.parentElement; 
        oldCanvas.remove(); 
        
        let newCanvas = document.createElement('canvas');
        newCanvas.id = 'scatterChart';
        canvasParent.appendChild(newCanvas);
        
        const ctx = newCanvas;
        // ==========================================

        const datasets = [
            {
                label: `聯盟${pType} (Others)`, // 💡 動態顯示這是打者還是投手
                data: basePoints,
                backgroundColor: 'rgba(0, 90, 156, 0.4)', // 道奇藍 (半透明)
                borderColor: 'rgba(0, 90, 156, 0.6)',
                pointRadius: 6,
                pointHoverRadius: 9,
                showLine: false
            }
        ];

        // 如果有找到高亮球員，讓他變成紅色的巨大星星！
        if (highlightPoints.length > 0) {
            datasets.push({
                label: '⭐ ' + (searchInput.split('-')[0].trim() || '高亮球員'),
                data: highlightPoints,
                backgroundColor: 'rgba(206, 17, 65, 0.9)', // 勇士紅 (實心)
                borderColor: '#CE1141',
                pointRadius: 12,
                pointHoverRadius: 16,
                showLine: false
            });
        }

        window.myScatterChart = new Chart(ctx, {
            type: 'scatter',
            data: { datasets: datasets },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                const raw = context.raw;
                                return `${raw.name} (${raw.team}): [${xLabel}: ${raw.x}, ${yLabel}: ${raw.y}]`;
                            }
                        },
                        titleFont: { size: 16, family: 'Outfit' },
                        bodyFont: { size: 14, font: 'bold', family: 'Outfit' },
                        backgroundColor: 'rgba(0,0,0,0.8)',
                        padding: 12
                    },
                    legend: {
                        labels: { font: { weight: 'bold', size: 16, family: 'Outfit' }, color: '#333' }
                    }
                },
                scales: {
                    x: {
                        title: { display: true, text: xLabel, font: { weight: 'black', size: 18, family: 'Outfit' }, color: '#005A9C' },
                        grid: { color: 'rgba(0, 0, 0, 0.05)' }
                    },
                    y: {
                        title: { display: true, text: yLabel, font: { weight: 'black', size: 18, family: 'Outfit' }, color: '#005A9C' },
                        grid: { color: 'rgba(0, 0, 0, 0.05)' }
                    }
                }
            }
        });

    } catch (e) {
        console.error("繪製散佈圖失敗:", e);
        alert("繪製散佈圖失敗！錯誤訊息: " + e.message);
    }
};
// ==========================================
// 📈 繪製雷達圖 (修復前後端欄位對應 bug)
// ==========================================
window.drawRadar = function(isSilent = false) {
    try {
        const p1Input = document.getElementById('radar-p1')?.value.trim();
        const p2Input = document.getElementById('radar-p2')?.value.trim();
        
        if (!p1Input) return;
        if (!GLOBAL_DATA || GLOBAL_DATA.length === 0) return;

        const cleanName1 = p1Input.split('-')[0].split('(')[0].trim().toLowerCase();
        const cleanName2 = p2Input ? p2Input.split('-')[0].split('(')[0].trim().toLowerCase() : "";

        const pType = document.getElementById('radar-ptype')?.value || '打者';
        const isPitcher = (pType === '投手');

        const pool = GLOBAL_DATA.filter(p => isPitcher ? (p.ip !== undefined || p.era !== undefined) : (p.pa !== undefined || p.ab !== undefined));

        const p1 = pool.find(p => String(p.name || p.Name || p.Player || "").toLowerCase().includes(cleanName1));
        const p2 = p2Input ? pool.find(p => String(p.name || p.Name || p.Player || "").toLowerCase().includes(cleanName2)) : null;

        if (!p1) {
            // 💡 關鍵升級：切換身分導致找不到人時，清空舊的雷達圖與底下表格！
            const tableContainer = document.getElementById('radar-table-container');
            if (tableContainer) tableContainer.innerHTML = '';
            
            let oldCanvas = document.getElementById('radarChart');
            if (oldCanvas) {
                let p = oldCanvas.parentElement;
                oldCanvas.remove();
                let n = document.createElement('canvas');
                n.id = 'radarChart';
                p.appendChild(n);
            }

            if (typeof isSilent !== 'object' && isSilent !== true) {
                alert(`在 ${pType} 名單中找不到球員：[${p1Input}]\n💡 提示：請確認拼字或確認是否切錯投打身分！`);
            }
            return;
        }

        let selectedKeys = [];
        let displayNames = [];
        for (let i = 1; i <= 6; i++) {
            const sel = document.getElementById(`radar-metric-${i}`);
            if (sel && sel.value) {
                selectedKeys.push(sel.value);
                displayNames.push(sel.options[sel.selectedIndex].text);
            }
        }

        if (selectedKeys.length === 0) {
            if (isPitcher) {
                selectedKeys = ['era', 'whip', 'fip', 'k_pct', 'bb_pct', 'xera'];
                displayNames = ['ERA', 'WHIP', 'FIP', 'K%', 'BB%', 'xERA'];
            } else {
                selectedKeys = ['ops', 'woba', 'wrc_plus', 'xwoba', 'hard_hit', 'barrel'];
                displayNames = ['OPS', 'wOBA', 'wRC+', 'xwOBA', 'HardHit%', 'Barrel%'];
            }
        }

        // 💡 關鍵修復 2：把 xera 加進「越低越好」的名單中，PR 才會算對！
        const reverseMetricsKeys = ['era', 'xera', 'whip', 'fip', 'bb_pct', 'bb', 'l'];

        const prData1 = [], prData2 = [], rawData1 = [], rawData2 = [];
        const truePr1 = [], truePr2 = []; 

        selectedKeys.forEach((key) => {
            let allVals = pool.map(p => parseFloat(p[key])).filter(v => !isNaN(v));

            if (allVals.length === 0) {
                prData1.push(50); prData2.push(50); rawData1.push("-"); rawData2.push("-");
                truePr1.push("-"); truePr2.push("-");
                return;
            }

            let maxV = Math.max(...allVals), minV = Math.min(...allVals);
            if (maxV === minV) maxV = minV + 1; 

            // 球員 1
            let val1 = parseFloat(p1[key]);
            if (isNaN(val1)) val1 = reverseMetricsKeys.includes(key) ? maxV : minV; 
            rawData1.push(val1);

            let pr1 = ((val1 - minV) / (maxV - minV)) * 100;
            if (reverseMetricsKeys.includes(key)) pr1 = 100 - pr1; 
            truePr1.push(Math.round(Math.max(0, Math.min(100, pr1)))); 
            prData1.push(Math.max(5, Math.min(100, pr1))); 

            // 球員 2
            if (p2) {
                let val2 = parseFloat(p2[key]);
                if (isNaN(val2)) val2 = reverseMetricsKeys.includes(key) ? maxV : minV;
                rawData2.push(val2);
                
                let pr2 = ((val2 - minV) / (maxV - minV)) * 100;
                if (reverseMetricsKeys.includes(key)) pr2 = 100 - pr2;
                truePr2.push(Math.round(Math.max(0, Math.min(100, pr2)))); 
                prData2.push(Math.max(5, Math.min(100, pr2))); 
            }
        });

        // ==========================================
        // 📊 生成底下的「橫向」數據 PR 值表格 (球員在左，指標在上)
        // ==========================================
        const tableContainer = document.getElementById('radar-table-container');
        if (tableContainer) {
            let p1NameStr = p1.name || p1.Name || p1Input.split('-')[0].trim();
            let p2NameStr = p2 ? (p2.name || p2.Name || p2Input.split('-')[0].trim()) : '';

            // 建立表頭 (6 大指標在上方)
            let tableHtml = `
            <div class="overflow-x-auto bg-white rounded-xl shadow-md border-2 border-gray-100">
                <table class="w-full text-center whitespace-nowrap">
                    <thead class="bg-gray-800 text-white tracking-wider text-xl">
                        <tr>
                            <th class="p-4 text-left sticky left-0 z-10 bg-gray-900 border-r border-gray-700 min-w-[150px]">球員</th>`;
            displayNames.forEach(metricName => {
                tableHtml += `<th class="p-4">${metricName}</th>`;
            });
            tableHtml += `</tr></thead><tbody class="divide-y divide-gray-200 text-lg">`;

            // 球員 1 的橫向數據列
            tableHtml += `<tr class="hover:bg-blue-50 transition-colors">
                <td class="p-4 font-black bg-gray-50 text-[#005A9C] border-r border-gray-200 sticky left-0 z-10 text-left">${p1NameStr}</td>`;
            
            displayNames.forEach((_, i) => {
                let r1 = typeof rawData1[i] === 'number' && rawData1[i] % 1 !== 0 ? rawData1[i].toFixed(3) : rawData1[i];
                let pr1 = truePr1[i];
                let pr1Color = pr1 >= 80 ? 'text-[#CE1141] font-black' : (pr1 <= 20 ? 'text-[#005A9C] font-bold' : 'text-gray-600');
                if (pr1 === "-") pr1Color = "text-gray-400";

                tableHtml += `<td class="p-4">
                    <div class="font-black text-2xl text-gray-800">${r1}</div>
                    <div class="mt-1 text-sm bg-gray-100 px-2 py-0.5 rounded-md inline-block border border-gray-200 ${pr1Color}">PR ${pr1}</div>
                </td>`;
            });
            tableHtml += `</tr>`;

            // 球員 2 的橫向數據列 (如果有)
            if (p2) {
                tableHtml += `<tr class="hover:bg-red-50 transition-colors">
                    <td class="p-4 font-black bg-gray-50 text-[#CE1141] border-r border-gray-200 sticky left-0 z-10 text-left">${p2NameStr}</td>`;
                
                displayNames.forEach((_, i) => {
                    let r2 = typeof rawData2[i] === 'number' && rawData2[i] % 1 !== 0 ? rawData2[i].toFixed(3) : rawData2[i];
                    let pr2 = truePr2[i];
                    let pr2Color = pr2 >= 80 ? 'text-[#CE1141] font-black' : (pr2 <= 20 ? 'text-[#005A9C] font-bold' : 'text-gray-600');
                    if (pr2 === "-") pr2Color = "text-gray-400";

                    tableHtml += `<td class="p-4">
                        <div class="font-black text-2xl text-gray-800">${r2}</div>
                        <div class="mt-1 text-sm bg-gray-100 px-2 py-0.5 rounded-md inline-block border border-gray-200 ${pr2Color}">PR ${pr2}</div>
                    </td>`;
                });
                tableHtml += `</tr>`;
            }

            tableHtml += `</tbody></table></div>`;
            tableContainer.innerHTML = tableHtml;
        }

        // ==========================================
        // 重新繪製 Chart.js
        // ==========================================
        let oldCanvas = document.getElementById('radarChart');
        if (!oldCanvas) return;
        let canvasParent = oldCanvas.parentElement; 
        oldCanvas.remove(); 
        
        let newCanvas = document.createElement('canvas');
        newCanvas.id = 'radarChart';
        canvasParent.appendChild(newCanvas);
        
        window.myRadarChart = new Chart(newCanvas, {
            type: 'radar', 
            data: { 
                labels: displayNames, 
                datasets: [
                    {
                        label: p1.name || p1.Name || p1Input.split('-')[0].trim(),
                        data: prData1,
                        backgroundColor: 'rgba(0, 90, 156, 0.4)', borderColor: 'rgba(0, 90, 156, 1)',
                        pointBackgroundColor: 'rgba(0, 90, 156, 1)', pointBorderColor: '#fff',
                        pointRadius: 6, pointHoverRadius: 10, borderWidth: 4, rawData: rawData1 
                    },
                    ...(p2 ? [{
                        label: p2.name || p2.Name || p2Input.split('-')[0].trim(),
                        data: prData2,
                        backgroundColor: 'rgba(206, 17, 65, 0.4)', borderColor: 'rgba(206, 17, 65, 1)',
                        pointBackgroundColor: 'rgba(206, 17, 65, 1)', pointBorderColor: '#fff',
                        pointRadius: 6, pointHoverRadius: 10, borderWidth: 4, rawData: rawData2
                    }] : [])
                ] 
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                scales: { r: { min: 0, max: 100, ticks: { display: false }, pointLabels: { font: { size: 22, weight: '900', family: 'Outfit' }, color: '#1f2937' } } },
                plugins: { 
                    legend: { display: true, position: 'top', labels: { font: { size: 22, weight: '900', family: 'Outfit' }, color: '#111827', padding: 20, boxWidth: 20, boxHeight: 20 } },
                    tooltip: { titleFont: { size: 20, weight: 'bold' }, bodyFont: { size: 18, weight: 'bold' }, padding: 14, callbacks: { label: function(c) { return `${c.dataset.label}: ${c.dataset.rawData[c.dataIndex]}`; } } } 
                }
            }
        });
    } catch (e) { console.error(e); }
};
// 🔄 全域更新資料庫 (修正：防止更新時誤觸畫圖警告)
async function handleGlobalUpdate() {
    const btn = document.getElementById('btn-update-db');
    if (!btn) {
        if (typeof fetchLeagueData === 'function') fetchLeagueData();
        return;
    }
    
    const originalHTML = btn.innerHTML;
    btn.innerHTML = '⏳ 讀取中...';
    btn.classList.add('opacity-75', 'cursor-wait');
    
    try {
        // 1. 抓取大聯盟 API 最新數據
        if (typeof fetchLeagueData === 'function') {
            await fetchLeagueData();
        }
        
        // 2. 渲染排行榜表格
        if (typeof renderLeagueTable === 'function') {
            renderLeagueTable();
        }
        
        // 3. 更新下拉選單的球員名單 (給雷達與對決用)
        if (typeof loadPlayerDatalist === 'function') {
            loadPlayerDatalist();
        }

        // 🔥 4. 更新散佈圖的 X 軸與 Y 軸選單 (自動偵測投打)
        if (typeof updateMetricSelects === 'function') {
            updateMetricSelects();
        }

        btn.innerHTML = '✅ 更新成功！';
        btn.classList.replace('bg-[#005A9C]', 'bg-green-600');
        
    } catch (e) {
        console.error("更新數據時發生錯誤:", e);
        btn.innerHTML = '❌ 更新失敗';
        btn.classList.replace('bg-[#005A9C]', 'bg-red-600');
    } finally {
        setTimeout(() => {
            btn.innerHTML = originalHTML;
            btn.classList.remove('opacity-75', 'cursor-wait', 'bg-green-600', 'bg-red-600');
            btn.classList.add('bg-[#005A9C]');
        }, 2000);
    }
}
window.updateH2HMetricOptions = function() {
    const container = document.getElementById('h2h-metrics-checkboxes');
    if (!container) return;

    const pType = document.getElementById('h2h-ptype')?.value || '打者';
    const isPitcher = (pType === '投手');

    // ⚾ 打者與 🎯 投手可用於 PK 的數據清單
    const hitterOptions = [
        { key: 'pa', label: 'PA (打席)', checked: true },
        { key: 'hr', label: 'HR (全壘打)', checked: true },
        { key: 'rbi', label: 'RBI (打點)', checked: true },
        { key: 'r', label: 'R (得分)', checked: false },
        { key: 'sb', label: 'SB (盜壘)', checked: true },
        { key: 'avg', label: 'AVG (打擊率)', checked: true },
        { key: 'obp', label: 'OBP (上壘率)', checked: true },
        { key: 'slg', label: 'SLG (長打率)', checked: true },
        { key: 'ops', label: 'OPS (攻擊指數)', checked: true },
        { key: 'woba', label: 'wOBA', checked: true },
        { key: 'wrc_plus', label: 'wRC+', checked: true },
        { key: 'war', label: 'WAR', checked: true },
        { key: 'hard_hit', label: 'HardHit%', checked: false },
        { key: 'barrel', label: 'Barrel%', checked: false },
        { key: 'whiff', label: 'Whiff%', checked: false }
    ];

    const pitcherOptions = [
        { key: 'w', label: 'W (勝投)', checked: true },
        { key: 'l', label: 'L (敗投)', checked: true },
        { key: 'ip', label: 'IP (局數)', checked: true },
        { key: 'k', label: 'K (三振)', checked: true },
        { key: 'bb', label: 'BB (保送)', checked: true },
        { key: 'sv', label: 'SV (救援)', checked: true },
        { key: 'hld', label: 'HLD (中繼)', checked: true },
        { key: 'era', label: 'ERA (防禦率)', checked: true },
        { key: 'whip', label: 'WHIP', checked: true },
        { key: 'fip', label: 'FIP', checked: true },
        { key: 'xera', label: 'xERA', checked: false },
        { key: 'war', label: 'WAR', checked: true },
        { key: 'hard_hit', label: 'HardHit%', checked: false },
        { key: 'barrel', label: 'Barrel%', checked: false }
    ];

    const options = isPitcher ? pitcherOptions : hitterOptions;
    let html = '';

    // 生成勾選框 HTML，一旦勾選立刻呼叫 renderH2H 重新畫圖
    options.forEach(opt => {
        html += `
        <label class="inline-flex items-center gap-2 bg-white px-3.5 py-1.5 rounded-xl border border-gray-300 shadow-sm cursor-pointer hover:bg-blue-50 transition-colors">
            <input type="checkbox" value="${opt.key}" ${opt.checked ? 'checked' : ''} onchange="renderH2H(true)" class="h2h-metric-cb w-4 h-4 text-[#005A9C] rounded border-gray-300 focus:ring-[#005A9C]">
            <span class="font-bold text-gray-800 text-base">${opt.label}</span>
        </label>`;
    });

    container.innerHTML = html;
};

// ==========================================
// ⚖️ 繪製 Head-to-Head (項目在左 + 黑色粗體 + 動態多選)
// ==========================================
window.renderH2H = function(isSilent = false) {
    try {
        const p1Input = document.getElementById('h2h-p1')?.value.trim();
        const p2Input = document.getElementById('h2h-p2')?.value.trim();

        // 防呆：還沒選滿兩個人就切換選單時，直接安靜離開，不跳警告！
        if (!p1Input || !p2Input) return;
        if (!GLOBAL_DATA || GLOBAL_DATA.length === 0) return;

        const cleanName1 = p1Input.split('-')[0].split('(')[0].trim().toLowerCase();
        const cleanName2 = p2Input.split('-')[0].split('(')[0].trim().toLowerCase();

        const pType = document.getElementById('h2h-ptype')?.value || '打者';
        const isPitcher = (pType === '投手');

        // 嚴格篩選同身分的球員池
        const pool = GLOBAL_DATA.filter(p => isPitcher ? (p.ip !== undefined || p.era !== undefined) : (p.pa !== undefined || p.ab !== undefined));

        const p1 = pool.find(p => String(p.name || p.Name || p.Player || "").toLowerCase().includes(cleanName1));
        const p2 = pool.find(p => String(p.name || p.Name || p.Player || "").toLowerCase().includes(cleanName2));

        if (!p1 || !p2) {
            // 💡 關鍵升級：切換身分導致找不到人時，清空舊的對決表格，避免畫面殘留誤導！
            const resultsContainer = document.getElementById('h2h-results');
            if (resultsContainer) resultsContainer.innerHTML = '';

            if (typeof isSilent !== 'object' && isSilent !== true) {
                alert(`在 ${pType} 名單中無法完整比對！\n💡 提示：請確認拼字正確或切換正確的投打身分。`);
            }
            return;
        }

        // 💡 抓取被勾選的指標
        const cbElems = document.querySelectorAll('.h2h-metric-cb:checked');
        let selectedMetrics = [];
        cbElems.forEach(cb => {
            const labelNode = cb.nextElementSibling;
            selectedMetrics.push({
                key: cb.value,
                label: labelNode ? labelNode.innerText : cb.value.toUpperCase()
            });
        });

        // 萬一使用者把指標全部取消勾選，或是選單還沒載入，給予防呆預設值
        if (selectedMetrics.length === 0) {
            selectedMetrics = [{ key: 'war', label: 'WAR' }];
        }

        // 定義哪些數據越低越好 (決定誰變綠色)
        const reverseMetrics = ['era', 'xera', 'whip', 'fip', 'bb', 'l', 'k_pct', 'bb_pct', 'chase'];
        const keyMap = { 'wrc+': 'wrc_plus', 'k/9': 'k9', 'so': 'k' };

        const resultsContainer = document.getElementById('h2h-results');
        if (!resultsContainer) return;

        let p1NameStr = p1.name || p1.Name || cleanName1;
        let p2NameStr = p2.name || p2.Name || cleanName2;

        // 💡 建立新版表頭：指標(左) - 球員1(中) - 球員2(右)
        let html = `
        <div class="overflow-hidden bg-white rounded-2xl shadow-lg border-2 border-gray-100">
            <div class="flex justify-between items-center bg-gray-900 text-white p-5 font-black text-2xl shadow-inner">
                <div class="w-1/3 text-left pl-6 text-gray-400 text-xl uppercase tracking-wider">分析指標</div>
                <div class="w-1/3 text-center text-[#60A5FA] text-2xl truncate px-2">${p1NameStr}</div>
                <div class="w-1/3 text-center text-[#F87171] text-2xl truncate px-2">${p2NameStr}</div>
            </div>
            <div class="divide-y divide-gray-100">`;

        // 遍歷所有勾選的數據指標
        selectedMetrics.forEach(mObj => {
            let mLower = mObj.key.toLowerCase();
            let actualKey1 = keyMap[mLower] || Object.keys(p1).find(k => k.toLowerCase() === mLower) || mObj.key;
            let actualKey2 = keyMap[mLower] || Object.keys(p2).find(k => k.toLowerCase() === mLower) || mObj.key;

            let val1 = parseFloat(p1[actualKey1]);
            let val2 = parseFloat(p2[actualKey2]);
            if (isNaN(val1)) val1 = p1[actualKey1] ?? 0;
            if (isNaN(val2)) val2 = p2[actualKey2] ?? 0;

            // 判斷勝負
            let p1Wins = false, p2Wins = false;
            if (typeof val1 === 'number' && typeof val2 === 'number' && val1 !== val2) {
                if (reverseMetrics.includes(mLower)) {
                    p1Wins = val1 < val2;
                    p2Wins = val2 < val1;
                } else {
                    p1Wins = val1 > val2;
                    p2Wins = val2 > val1;
                }
            }

           // 數據格式化 (小數點位數，遇局數自動轉換為分數)
            let dV1, dV2;
            if (mLower === 'ip') {
                dV1 = formatInnings(val1);
                dV2 = formatInnings(val2);
            } else {
                dV1 = typeof val1 === 'number' && val1 % 1 !== 0 ? val1.toFixed(3) : val1;
                dV2 = typeof val2 === 'number' && val2 % 1 !== 0 ? val2.toFixed(3) : val2;
            }

            // 贏的一方亮霸氣綠色 + 放大，輸的一方維持一般灰黑色
            let p1Style = p1Wins ? 'text-green-600 font-black text-2xl scale-105 drop-shadow-sm' : 'text-gray-700 font-bold text-xl';
            let p2Style = p2Wins ? 'text-green-600 font-black text-2xl scale-105 drop-shadow-sm' : 'text-gray-700 font-bold text-xl';

            html += `
            <div class="flex justify-between items-center p-4 hover:bg-blue-50/50 transition-colors">
                <div class="w-1/3 text-left pl-6 font-black text-gray-900 text-xl md:text-2xl tracking-wide">${mObj.label}</div>
                
                <div class="w-1/3 text-center transition-transform ${p1Style}">${dV1}</div>
                <div class="w-1/3 text-center transition-transform ${p2Style}">${dV2}</div>
            </div>`;
        });

        html += `</div></div>`;
        resultsContainer.innerHTML = html;
    } catch (e) {
        console.error("H2H 渲染失敗:", e);
    }
};

// ==========================================
// 📋 載入球員下拉選單 (修復大小寫欄位 Bug)
// ==========================================
window.loadPlayerDatalist = function() {
    const datalist = document.getElementById('player-datalist');
    // 如果找不到 datalist 標籤或沒有資料，就直接跳出
    if (!datalist || !GLOBAL_DATA || GLOBAL_DATA.length === 0) return;

    let optionsHtml = '';
    
    // 💡 終極防呆：包容後端所有可能的欄位名稱 (name, Name, Player, player)
    GLOBAL_DATA.forEach(p => {
        const playerName = p.name || p.Name || p.Player || p.player;
        const teamName = p.team || p.Team || 'FA';
        
        if (playerName) {
            // value 存純名字 (保證查詢不報錯)，文字顯示加上球隊 (方便教練辨識)
            optionsHtml += `<option value="${playerName}">${playerName} (${teamName})</option>`;
        }
    });
    
    datalist.innerHTML = optionsHtml;
};
document.addEventListener("DOMContentLoaded", () => {
    if (typeof loadHotData === 'function') loadHotData();
    console.log("啟動自動開機引擎...");

    // 1. 網頁一載入，立刻把雷達圖的 6 大選單選項全部填滿！(解決選單空白問題)
    if (typeof updateRadarMetricSelects === 'function') {
        updateRadarMetricSelects();
    }

    // 2. 網頁一載入，立刻把散佈圖的 X/Y 軸選單也填滿！
    if (typeof updateMetricSelects === 'function') {
        updateMetricSelects();
    }

    // 3. 網頁一載入，就「自動」去抓取全聯盟球員資料庫！
    // (這樣您就不用每次都特地跑回排名分頁按「更新資料庫」了)
    if (typeof handleGlobalUpdate === 'function') {
        handleGlobalUpdate();
    } else if (typeof fetchLeagueData === 'function') {
        fetchLeagueData();
    }
    if (typeof updateH2HMetricOptions === 'function') {
        updateH2HMetricOptions();
    }
});

// ==========================================
// 🔥 近況專屬抓取引擎 (從數據排行借鑒的穩定版)
// ==========================================
window.loadHotData = async function() {
    let ptype = document.getElementById('hot-ptype').value;
    const time = document.getElementById('hot-time').value;
    const league = document.getElementById('hot-league').value;
    let pos = document.getElementById('hot-pos').value;
    const year = document.getElementById('filter-year') ? document.getElementById('filter-year').value : new Date().getFullYear();

    // 💡 智慧防呆：自動切換身分，防止打者群組找投手
    if (['SP', 'RP', 'CL'].includes(pos) && ptype === '打者') {
        ptype = '投手';
        document.getElementById('hot-ptype').value = '投手';
    }
    if (['C', '1B', '2B', '3B', 'SS', 'OF', 'DH'].includes(pos) && ptype === '投手') {
        ptype = '打者';
        document.getElementById('hot-ptype').value = '打者';
    }

    const tbody = document.getElementById('hot-table-body');
    const thead = document.getElementById('hot-table-head');
    
    if (tbody) {
        tbody.innerHTML = `<tr><td colspan="35" class="text-center py-12 font-black text-[#CE1141] text-3xl animate-pulse">連線至大數據資料庫，載入 ${time} 近況數據中... ⏳</td></tr>`;
    }

    try {
        // 💡 使用絕對安全的 encodeURIComponent 傳遞參數
        let url = `${API_BASE_URL}/fantasy/rankings?timeframe=${encodeURIComponent(time)}&p_type=${encodeURIComponent(ptype)}&year=${encodeURIComponent(year)}&league=${encodeURIComponent(league)}&pos_filter=${encodeURIComponent(pos)}`;
        let res = await fetch(url);
        let result = await res.json();

        if (result.status === "success") {
            let data = result.data || [];
            
            if (data.length === 0) {
                tbody.innerHTML = `<tr><td colspan="35" class="text-center py-10 text-gray-400 font-bold text-2xl">目前沒有符合 ${pos} 條件的近況資料 🏖️</td></tr>`;
                thead.innerHTML = '';
                return;
            }

            let headHtml = '';
            let bodyHtml = '';
            
            let maxPts = Math.max(...data.map(p => p.fan_pts));
            let minPts = Math.min(...data.map(p => p.fan_pts));

            // ==========================================
            // ⚾ 打者黃金版 (H, HR, RBI, AVG, OPS, wRC+)
            // ==========================================
            if (ptype === '打者') {
                let maxH = Math.max(...data.map(p => p.h || 0));
                let maxHR = Math.max(...data.map(p => p.hr || 0));
                let maxOPS = Math.max(...data.map(p => p.ops || 0));

                headHtml = `<tr>
                    <th class="p-4 rounded-tl-xl w-16 text-center bg-gray-200">Rnk</th>
                    <th class="p-4 w-64 freeze-col text-xl bg-gray-100">Player</th>
                    <th class="p-4 text-center text-blue-600">H (安打)</th>
                    <th class="p-4 text-center text-red-600 font-black">HR</th>
                    <th class="p-4 text-center text-blue-600">RBI</th>
                    <th class="p-4 text-center text-gray-700">AVG</th>
                    <th class="p-4 text-center text-[#005A9C] font-black">OPS</th>
                    <th class="p-4 text-center text-[#CE1141] font-black">wRC+</th>
                    <th class="p-4 text-center text-yellow-600 text-lg font-black bg-gray-800 border-l border-gray-700 w-32 shadow-inner">Fan Pts 🔥</th>
                </tr>`;
                
                data.forEach((p, i) => {
                    let rankBadge = i === 0 ? '🥇' : (i === 1 ? '🥈' : (i === 2 ? '🥉' : `#${i + 1}`));
                    let rowBg = i % 2 === 0 ? 'bg-white' : 'bg-gray-50';
                    bodyHtml += `<tr class="${rowBg} hover:bg-red-50/60 transition-colors border-b border-gray-200 whitespace-nowrap">
                        <td class="p-4 text-center font-black text-2xl text-gray-500">${rankBadge}</td>
                        <td class="p-4 freeze-col ${rowBg}"><div class="font-black text-gray-900 text-xl">${p.name || p.Name}</div><div class="text-sm text-gray-500 font-bold mt-0.5">${p.team} - ${p.pos}</div></td>
                        <td class="p-4 text-center text-xl font-bold" style="${typeof getHeatmapColor === 'function' ? getHeatmapColor(p.h || 0, 0, maxH) : ''}">${p.h || 0}</td>
                        <td class="p-4 text-center text-xl font-black text-red-600" style="${typeof getHeatmapColor === 'function' ? getHeatmapColor(p.hr || 0, 0, maxHR) : ''}">${p.hr || 0}</td>
                        <td class="p-4 text-center text-xl font-bold text-gray-800">${p.rbi || 0}</td>
                        <td class="p-4 text-center font-bold text-gray-600 text-xl">${(typeof p.avg === 'number' ? p.avg.toFixed(3) : (p.avg || '.000'))}</td>
                        <td class="p-4 text-center text-xl font-black text-[#005A9C]" style="${typeof getHeatmapColor === 'function' ? getHeatmapColor(p.ops || 0, 0.600, maxOPS) : ''}">${(typeof p.ops === 'number' ? p.ops.toFixed(3) : (p.ops || '.000'))}</td>
                        <td class="p-4 text-center font-black text-[#CE1141] text-xl">${p.wrc_plus || 0}</td>
                        <td class="p-4 text-center text-2xl font-black shadow-[inset_4px_0_4px_-4px_rgba(0,0,0,0.05)]" style="${typeof getHeatmapColor === 'function' ? getHeatmapColor(p.fan_pts, minPts, maxPts) : ''}">${(p.fan_pts || 0).toFixed(1)}</td>
                    </tr>`;
                });
            } 
            // ==========================================
            // 🎯 投手黃金版 (W, L, IP, BB, K, HLD, ERA, FIP, BA)
            // ==========================================
            else {
                let maxK = Math.max(...data.map(p => p.so || p.k || 0));
                let minERA = Math.min(...data.map(p => p.era || 0));
                let maxERA = Math.max(...data.map(p => p.era || 0));

                headHtml = `<tr>
                    <th class="p-4 rounded-tl-xl w-16 text-center bg-gray-200">Rnk</th>
                    <th class="p-4 w-64 freeze-col text-xl bg-gray-100">Player</th>
                    <th class="p-4 text-center text-gray-700">W</th>
                    <th class="p-4 text-center text-gray-700">L</th>
                    <th class="p-4 text-center text-[#005A9C] font-black">IP (局數)</th>
                    <th class="p-4 text-center text-gray-600">BB</th>
                    <th class="p-4 text-center text-red-600 font-black">K (三振)</th>
                    <th class="p-4 text-center text-orange-600 font-bold">HLD</th>
                    <th class="p-4 text-center text-[#CE1141] font-black">ERA</th>
                    <th class="p-4 text-center text-gray-700 font-black">FIP</th>
                    <th class="p-4 text-center text-gray-700 font-black">BA (被打)</th>
                    <th class="p-4 text-center text-yellow-600 text-lg font-black bg-gray-800 border-l border-gray-700 w-32 shadow-inner">Fan Pts 🔥</th>
                </tr>`;
                
                data.forEach((p, i) => {
                    let rankBadge = i === 0 ? '🥇' : (i === 1 ? '🥈' : (i === 2 ? '🥉' : `#${i + 1}`));
                    let rowBg = i % 2 === 0 ? 'bg-white' : 'bg-gray-50';
                    
                    // 💡 防呆：投手被打擊率後端可能傳 'ba' 或 'avg'
                    let baVal = typeof p.ba === 'number' ? p.ba.toFixed(3) : (typeof p.avg === 'number' ? p.avg.toFixed(3) : (p.ba || '.000'));
                    
                    bodyHtml += `<tr class="${rowBg} hover:bg-red-50/60 transition-colors border-b border-gray-200 whitespace-nowrap">
                        <td class="p-4 text-center font-black text-2xl text-gray-500">${rankBadge}</td>
                        <td class="p-4 freeze-col ${rowBg}"><div class="font-black text-gray-900 text-xl">${p.name || p.Name}</div><div class="text-sm text-gray-500 font-bold mt-0.5">${p.team} - ${p.pos}</div></td>
                        <td class="p-4 text-center font-bold text-gray-800 text-xl">${p.w || 0}</td>
                        <td class="p-4 text-center font-bold text-gray-800 text-xl">${p.l || 0}</td>
                        <td class="p-4 text-center font-black text-[#005A9C] text-xl">${formatInnings(p.ip)}</td>
                        <td class="p-4 text-center font-bold text-gray-600 text-xl">${p.bb || 0}</td>
                        <td class="p-4 text-center text-xl font-black text-red-600" style="${typeof getHeatmapColor === 'function' ? getHeatmapColor(p.so || p.k || 0, 0, maxK) : ''}">${p.so || p.k || 0}</td>
                        <td class="p-4 text-center font-bold text-orange-600 text-xl">${p.hld || 0}</td>
                        <td class="p-4 text-center text-xl font-black text-[#CE1141]" style="${typeof getHeatmapColor === 'function' ? getHeatmapColor(p.era || 0, minERA, maxERA, true) : ''}">${(typeof p.era === 'number' ? p.era.toFixed(2) : (p.era || '0.00'))}</td>
                        <td class="p-4 text-center font-bold text-gray-700 text-xl">${(typeof p.fip === 'number' ? p.fip.toFixed(2) : (p.fip || '0.00'))}</td>
                        <td class="p-4 text-center font-bold text-gray-600 text-xl">${baVal}</td>
                        <td class="p-4 text-center text-2xl font-black shadow-[inset_4px_0_4px_-4px_rgba(0,0,0,0.05)]" style="${typeof getHeatmapColor === 'function' ? getHeatmapColor(p.fan_pts, minPts, maxPts) : ''}">${(p.fan_pts || 0).toFixed(1)}</td>
                    </tr>`;
                });
            }
            
            thead.innerHTML = headHtml;
            tbody.innerHTML = bodyHtml;

            // 💡 表格拉條長度對齊與捲軸連動
            setTimeout(() => {
                const topContent = document.getElementById('hot-top-scroll-content');
                const mainTable = document.getElementById('hot-main-table');
                if (topContent && mainTable) topContent.style.width = mainTable.scrollWidth + 'px';
            }, 150);

            let isSyncingTop = false, isSyncingTable = false;
            const topScroll = document.getElementById('hot-top-scroll'), tableScroll = document.getElementById('hot-table-scroll');
            if (topScroll && tableScroll) {
                topScroll.onscroll = () => { if (!isSyncingTop) { isSyncingTable = true; tableScroll.scrollLeft = topScroll.scrollLeft; } isSyncingTop = false; };
                tableScroll.onscroll = () => { if (!isSyncingTable) { isSyncingTop = true; topScroll.scrollLeft = tableScroll.scrollLeft; } isSyncingTable = false; };
            }

        } else {
            tbody.innerHTML = `<tr><td colspan="35" class="text-center py-10 text-red-500 font-bold text-2xl">${result.message}</td></tr>`;
        
        }
    } catch (e) {
        console.error(e);
        if (tbody) tbody.innerHTML = `<tr><td colspan="35" class="text-center py-10 text-red-500 font-bold text-2xl">連線失敗，請確認 API 服務已啟動。</td></tr>`;
    }
}
window.autoUpdateAllPts = async function() {
    if (!confirm("⚠️ 系統將自動抓取美國本週一至今天的累積數據，並更新球隊分數。\n(注意：系統抓不到的 QS, HLD, BSV，結算後請點擊分數手動補上)")) {
        return;
    }
    
    let btn = document.getElementById("autoUpdateBtn");
    let originalText = btn.innerHTML;
    btn.innerHTML = "⏳ 正在與大聯盟連線抓取數據中，請稍候...";
    btn.disabled = true;

    try {
        let res = await fetch("https://mlb-war-room-l7ps.onrender.com/fantasy/auto-update-real-pts", { 
        method: "POST" 
        });
        
        let data = await res.json();
        alert(data.message);
        renderYahooTeam(); // 重新載入畫面
    } catch (error) {
        console.error("更新失敗:", error);
        alert("連線後端失敗，請稍後再試！");
    } finally {
        btn.innerHTML = originalText;
        btn.disabled = false;
    }
}