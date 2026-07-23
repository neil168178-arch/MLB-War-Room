# data_fetcher.py
import streamlit as st
import pandas as pd
import requests
import aiohttp
import asyncio
from datetime import datetime, timedelta, timezone
from pybaseball import (
    statcast_batter_expected_stats, statcast_pitcher_expected_stats,
    statcast_batter_exitvelo_barrels, statcast_pitcher_exitvelo_barrels,
    statcast_batter, statcast_pitcher
)
from backend.config import *
from backend.utils import clean_name, safe_float, translate_injury

# --- 🚀 非同步資料撈取工具 (Async Helpers) ---
async def fetch_json_async(url, session):
    try:
        async with session.get(url, timeout=10) as response:
            return await response.json()
    except:
        return {}

# ---------------------------------------------

@st.cache_data(ttl=1800)
def fetch_daily_schedule(date_str):
    url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={date_str}&hydrate=probablePitcher"
    try:
        res = requests.get(url, timeout=10).json()
        if not res.get('dates'): return []
        schedule = []
        for g in res['dates'][0].get('games', []):
            away_team = g['teams']['away']['team']['name']
            home_team = g['teams']['home']['team']['name']
            away_p = g['teams']['away'].get('probablePitcher', {})
            home_p = g['teams']['home'].get('probablePitcher', {})
            schedule.append({
                'matchup': f"{away_team} @ {home_team}",
                'away_team': away_team, 'home_team': home_team,
                'away_pitcher': away_p.get('fullName', 'TBD'), 'away_pitcher_id': away_p.get('id', None),
                'home_pitcher': home_p.get('fullName', 'TBD'), 'home_pitcher_id': home_p.get('id', None)
            })
        return schedule
    except: return []

@st.cache_data(ttl=3600)
def fetch_bvp_data(pitcher_id, batter_ids):
    valid_b_ids = [str(int(b)) for b in batter_ids if pd.notna(b)]
    if not pitcher_id or not valid_b_ids: return pd.DataFrame()
    url = f"https://statsapi.mlb.com/api/v1/stats?stats=batterVsPitcher&pitcherId={int(pitcher_id)}&batterId={','.join(valid_b_ids)}"
    try:
        splits = requests.get(url, timeout=10).json().get('stats', [{}])[0].get('splits', [])
        data = []
        for s in splits:
            stat = s.get('stat', {})
            data.append({
                '打者 (Batter)': s.get('batter', {}).get('fullName', 'Unknown'),
                '打數 (AB)': stat.get('atBats', 0), '安打 (H)': stat.get('hits', 0),
                '全壘打 (HR)': stat.get('homeRuns', 0), '三振 (K)': stat.get('strikeOuts', 0),
                '保送 (BB)': stat.get('baseOnBalls', 0),
                'AVG': safe_float(stat.get('avg', 0.0)), 'OPS': safe_float(stat.get('ops', 0.0))
            })
        return pd.DataFrame(data).sort_values(by='OPS', ascending=False) if data else pd.DataFrame()
    except: return pd.DataFrame()

@st.cache_data(ttl=3600*24)
def fetch_historical_positions():
    async def fetch_all_years():
        pos_counts = {}
        async with aiohttp.ClientSession() as session:
            tasks = []
            for y in range(2016, 2027):
                url = f"https://statsapi.mlb.com/api/v1/stats?stats=season&group=fielding&season={y}&playerPool=ALL&limit=10000"
                tasks.append(fetch_json_async(url, session))
            results = await asyncio.gather(*tasks)
            for res in results:
                if 'stats' in res and len(res['stats']) > 0:
                    for s in res['stats'][0].get('splits', []):
                        raw_name = s.get('player', {}).get('fullName', '')
                        if not raw_name: continue
                        name_key = clean_name(raw_name)
                        pos = s.get('position', {}).get('abbreviation', 'Unknown')
                        if pos in ['P', 'PH', 'PR', 'Unknown', 'DH', 'TWP']: continue
                        games = s.get('stat', {}).get('gamesPlayed', 0)
                        if name_key not in pos_counts: pos_counts[name_key] = {}
                        pos_counts[name_key][pos] = pos_counts[name_key].get(pos, 0) + games
        return pos_counts

    try: loop = asyncio.get_event_loop()
    except RuntimeError: loop = asyncio.new_event_loop(); asyncio.set_event_loop(loop)
    pos_counts = loop.run_until_complete(fetch_all_years())
    return {nk: [p for p, g in pos.items() if g >= 30] for nk, pos in pos_counts.items() if [p for p, g in pos.items() if g >= 30]}

@st.cache_data(ttl=3600)
def process_combined_data(p_type, year, min_filter):
    group = 'pitching' if p_type == '投手' else 'hitting'
    url = f"https://statsapi.mlb.com/api/v1/stats?stats=season&group={group}&season={year}&sportId=1&playerPool=ALL&limit=2000&hydrate=person"
    try:
        res = requests.get(url, timeout=15).json()
        splits = res.get('stats', [{}])[0].get('splits', [])
        if not splits: return pd.DataFrame()
        mlb_df = pd.DataFrame([s.get('stat', {}) for s in splits])
        mlb_df['Player'] = [s.get('player', {}).get('fullName', 'Unknown') for s in splits]
        mlb_df['Player_ID'] = [s.get('player', {}).get('id', None) for s in splits]
        mlb_df['Position_raw'] = [s.get('player', {}).get('primaryPosition', {}).get('abbreviation', 'Unknown') for s in splits]
        mlb_df['Team'] = [s.get('team', {}).get('name', 'Unknown') for s in splits]
    except: return pd.DataFrame()
    
    try:
        api = statcast_pitcher_expected_stats if p_type == "投手" else statcast_batter_expected_stats
        savant_df = api(year, minPA=1).reset_index()
        if not savant_df.empty:
            savant_df['Player'] = savant_df['last_name, first_name'].apply(lambda x: f"{x.split(', ')[1].strip()} {x.split(', ')[0].strip()}" if ',' in str(x) else x)
    except: savant_df = pd.DataFrame()
        
    try:
        ev_api = statcast_pitcher_exitvelo_barrels if p_type == "投手" else statcast_batter_exitvelo_barrels
        ev_df = ev_api(year, minBBE=1).reset_index()
        if not ev_df.empty:
            ev_df['Player'] = ev_df['last_name, first_name'].apply(lambda x: f"{x.split(', ')[1].strip()} {x.split(', ')[0].strip()}" if ',' in str(x) else x)
            ev_df = ev_df[['Player', 'brl_percent', 'ev95percent']]
    except: ev_df = pd.DataFrame()
    
    if mlb_df.empty: return pd.DataFrame()
    
    df = mlb_df.copy()
    if not savant_df.empty:
        overlap1 = set(df.columns).intersection(set(savant_df.columns)) - {'Player'}
        savant_df = savant_df.drop(columns=list(overlap1))
        df = pd.merge(df, savant_df, on='Player', how='left')
        
    if not ev_df.empty:
        overlap2 = set(df.columns).intersection(set(ev_df.columns)) - {'Player'}
        ev_df = ev_df.drop(columns=list(overlap2))
        df = pd.merge(df, ev_df, on='Player', how='left')
        
    df = df.fillna(0)
    for col in df.columns:
        if col not in ['Player', 'Player_ID', 'Position_raw', 'Team']: df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    total_outs = df.get('groundOuts', 0) + df.get('airOuts', 0)
    df['GB%'] = ((df.get('groundOuts', 0) / total_outs.replace(0, 1)) * 100).fillna(0)
    hist_pos = fetch_historical_positions()
    
    if p_type == "打者":
        if 'plateAppearances' in df.columns: df = df[df['plateAppearances'] >= min_filter].copy()
        def get_batter_pos(row):
            pos_raw = row.get('Position_raw', 'DH')
            if pos_raw == 'TWP': return 'SP, DH'
            pos = hist_pos.get(clean_name(row['Player']), [pos_raw])
            if pos_raw == 'DH' and 'DH' not in pos: pos.append('DH')
            pos = [p for p in pos if p != 'P']
            if not pos: pos = [pos_raw]
            return ", ".join(list(dict.fromkeys(pos)))
            
        df['Position'] = df.apply(get_batter_pos, axis=1)
        df['1B'] = df['hits'] - df.get('doubles', 0) - df.get('triples', 0) - df['homeRuns']
        df['2B'] = df.get('doubles', 0)
        df['3B'] = df.get('triples', 0)
        df['HBP'] = df.get('hitByPitch', 0)
        df['CYC'] = "-"
        df['SLAM'] = "-"
        
        try:
            f_url = f"https://statsapi.mlb.com/api/v1/stats?stats=season&group=fielding&season={year}&sportId=1&limit=2000"
            f_res = requests.get(f_url, timeout=10).json()
            f_splits = f_res.get('stats', [{}])[0].get('splits', [])
            f_data = [{'Player_ID': s.get('player', {}).get('id'), 'E': s.get('stat', {}).get('errors', 0)} for s in f_splits]
            if f_data:
                f_df = pd.DataFrame(f_data).groupby('Player_ID', as_index=False).sum()
                df = pd.merge(df, f_df, on='Player_ID', how='left')
        except: pass
        if 'E' not in df.columns: df['E'] = 0
        
        df.rename(columns={'plateAppearances': 'PA', 'atBats': 'AB', 'runs': 'R', 'hits': 'H', 'rbi': 'RBI', 'avg': 'AVG', 'ops': 'OPS', 'obp': 'OBP', 'homeRuns': 'HR', 'stolenBases': 'SB', 'baseOnBalls': 'BB', 'strikeOuts': 'K', 'est_ba': 'xBA', 'xba': 'xBA', 'est_woba': 'xwOBA', 'xwoba': 'xwOBA', 'woba': 'wOBA', 'brl_percent': 'Barrel%', 'ev95percent': 'HardHit%'}, inplace=True)
        for col in ['PA', 'AB', 'R', 'H', 'RBI', 'K', 'BB', 'SB', 'HR', 'wOBA', 'xwOBA', 'wRC+', 'OPS']:
            if col not in df.columns: df[col] = 0.0
            
        pa_safe = df['PA'].replace(0, 1)
        df['K%'] = (df['K'] / pa_safe) * 100
        df['Whiff%'] = df['K%'] * 1.15
        df['wRC+'] = (df['wOBA'] / 0.320) * 100
        df['Chase%'] = 28.5 - (df['xwOBA'] * 10)
        df['WAR'] = (((df['wRC+'] - 100) * df['PA'] / 8000) + (df['SB'] * 0.04) + (df['PA'] * 0.002)).round(2)
        df['Fantasy_Score'] = (df['R']*3 + df['H']*2 + df['1B']*3 + df['2B']*6 + df['3B']*10 + df['HR']*15 + df['RBI']*2 + df['SB']*5 + df['BB']*2 + df['HBP']*3 + df['K']*-2 + df['E']*-3)
        keep = ['Player', 'Player_ID', 'Team', 'Position', 'PA', 'AB', 'R', 'H', '1B', '2B', '3B', 'HR', 'RBI', 'SB', 'BB', 'HBP', 'K', 'E', 'CYC', 'SLAM', 'AVG', 'OPS', 'OBP', 'wOBA', 'wRC+', 'xwOBA', 'xBA', 'HardHit%', 'Barrel%', 'Chase%', 'Whiff%', 'GB%', 'WAR', 'Fantasy_Score']
    else:
        def get_pitcher_pos(r):
            base_pos = 'SP' if r.get('gamesStarted', 0) > (r.get('gamesPlayed', 0) / 2) else ('CL' if r.get('saves', 0) >= 5 else 'RP')
            if r.get('Position_raw') == 'TWP': return f"{base_pos}, DH"
            return base_pos
            
        df['Position'] = df.apply(get_pitcher_pos, axis=1)
        if 'inningsPitched' in df.columns: df['IP_calc'] = df['inningsPitched'].astype(str).str.replace('.1', '.333').str.replace('.2', '.667').astype(float)
        else: df['IP_calc'] = 0.0
        df = df[df['IP_calc'] >= min_filter].copy()
        
        def calc_outs(ip_val):
            try:
                ip_str = str(ip_val)
                if '.' in ip_str: return int(ip_str.split('.')[0])*3 + int(ip_str.split('.')[1])
                return int(float(ip_val))*3
            except: return 0
            
        df['W'], df['L'], df['SHO'], df['SV'] = df.get('wins', 0), df.get('losses', 0), df.get('shutouts', 0), df.get('saves', 0)
        df['OUT'] = df.get('outs', df.get('outsPitched', df['inningsPitched'].apply(calc_outs) if 'inningsPitched' in df.columns else 0))
        df['HBP'], df['WP'], df['HLD'], df['QS'], df['BSV'] = df.get('hitBatsmen', 0), df.get('wildPitches', 0), df.get('holds', 0), df.get('qualityStarts', 0), df.get('blownSaves', 0)
        
        df.rename(columns={'inningsPitched': 'IP', 'hits': 'H', 'runs': 'R', 'earnedRuns': 'ER', 'baseOnBalls': 'BB', 'strikeOuts': 'K', 'numberOfPitches': 'PC', 'homeRuns': 'HR', 'era': 'ERA', 'est_era': 'xERA', 'xera': 'xERA', 'whip': 'WHIP', 'avg': 'BA', 'est_ba': 'xBA', 'xba': 'xBA', 'est_woba': 'xwOBA', 'xwoba': 'xwOBA', 'battersFaced': 'PA_calc', 'brl_percent': 'Barrel%', 'ev95percent': 'HardHit%'}, inplace=True)
        for col in ['K', 'PA_calc', 'BB', 'HR', 'xBA', 'BA', 'FIP', 'ERA', 'xERA', 'WHIP', 'IP_calc', 'H', 'R', 'ER', 'PC']:
            if col not in df.columns: df[col] = 0.0
            
        pa_safe, ip_safe = df['PA_calc'].replace(0, 1), df['IP_calc'].replace(0, 1)
        df['K%'] = (df['K'] / pa_safe) * 100
        df['Whiff%'] = df['K%'] * 1.15
        df['BB%'] = (df['BB'] / pa_safe) * 100
        df['FIP'] = ((13 * df['HR']) + (3 * df['BB']) - (2 * df['K'])) / ip_safe + 3.20
        df['Diff'] = df['xBA'] - df['BA']
        df['WAR'] = ((((4.20 - df['FIP']) * df['IP_calc'] / 9) / 10) + (df['IP_calc'] * 0.008)).round(2)
        df['Fantasy_Score'] = (df['W']*20 + df['L']*-10 + df['SHO']*15 + df['SV']*8 + df['OUT']*1 + df['H']*-1 + df['ER']*-3 + df['HR']*-5 + df['BB']*-1 + df['HBP']*-2 + df['K']*4 + df['WP']*-3 + df['HLD']*3 + df['QS']*10 + df['BSV']*-10)
        keep = ['Player', 'Player_ID', 'Team', 'Position', 'W', 'L', 'SHO', 'SV', 'OUT', 'IP', 'H', 'R', 'ER', 'HR', 'BB', 'HBP', 'K', 'WP', 'HLD', 'QS', 'BSV', 'PC', 'ERA', 'xERA', 'WHIP', 'K%', 'BB%', 'FIP', 'BA', 'xBA', 'Diff', 'HardHit%', 'Barrel%', 'Whiff%', 'GB%', 'WAR', 'Fantasy_Score']

    for c in keep:
        if c not in df.columns: df[c] = 0.0
    return df[keep].round(3)

@st.cache_data(ttl=3600*24)
def fetch_all_teams_stats(year):
    url_hit, url_pit = f"https://statsapi.mlb.com/api/v1/teams/stats?season={year}&group=hitting&stats=season&sportIds=1", f"https://statsapi.mlb.com/api/v1/teams/stats?season={year}&group=pitching&stats=season&sportIds=1"
    try:
        res_hit, res_pit = requests.get(url_hit, timeout=10).json(), requests.get(url_pit, timeout=10).json()
        hit_data, pit_data = [], []
        for s in res_hit.get('stats', [{}])[0].get('splits', []):
            st = s['stat']
            hit_data.append({'Team': s['team']['name'], 'H_AVG': float(st.get('avg', 0)), 'H_OPS': float(st.get('ops', 0)), 'H_HR': int(st.get('homeRuns', 0)), 'H_R': int(st.get('runs', 0))})
        for s in res_pit.get('stats', [{}])[0].get('splits', []):
            st = s['stat']
            pit_data.append({'Team': s['team']['name'], 'P_ERA': float(st.get('era', 0)), 'P_WHIP': float(st.get('whip', 0)), 'P_K': int(st.get('strikeOuts', 0)), 'P_BB': int(st.get('baseOnBalls', 0))})
        
        df_hit, df_pit = pd.DataFrame(hit_data), pd.DataFrame(pit_data)
        if df_hit.empty or df_pit.empty: return pd.DataFrame()
        
        df_hit['H_AVG_Rank'], df_hit['H_OPS_Rank'], df_hit['H_HR_Rank'], df_hit['H_R_Rank'] = df_hit['H_AVG'].rank(ascending=False, method='min'), df_hit['H_OPS'].rank(ascending=False, method='min'), df_hit['H_HR'].rank(ascending=False, method='min'), df_hit['H_R'].rank(ascending=False, method='min')
        df_pit['P_ERA_Rank'], df_pit['P_WHIP_Rank'], df_pit['P_K_Rank'], df_pit['P_BB_Rank'] = df_pit['P_ERA'].rank(ascending=True, method='min'), df_pit['P_WHIP'].rank(ascending=True, method='min'), df_pit['P_K'].rank(ascending=False, method='min'), df_pit['P_BB'].rank(ascending=True, method='min')
        return pd.merge(df_hit, df_pit, on='Team')
    except: return pd.DataFrame()


@st.cache_data(ttl=3600*12)
def fetch_team_injury_list(team_id):
    tw_now = datetime.now(timezone(timedelta(hours=8)))
    year = tw_now.year
    
    team_ids_to_check = [team_id]
    try:
        res_teams = requests.get("https://statsapi.mlb.com/api/v1/teams?sportIds=1,11,12,13,14", timeout=10).json()
        for t in res_teams.get('teams', []):
            if t.get('parentOrgId') == team_id and t.get('id') != team_id:
                team_ids_to_check.append(t.get('id'))
    except: pass
        
    il_players = {}
    
    for t_id in team_ids_to_check:
        urls = [
            f"https://statsapi.mlb.com/api/v1/teams/{t_id}/roster/40Man?hydrate=person(injuries)",
            f"https://statsapi.mlb.com/api/v1/teams/{t_id}/roster/fullSeason?season={year}&hydrate=person(injuries)"
        ]
        
        for url in urls:
            try:
                res = requests.get(url, timeout=10).json()
                for p in res.get('roster', []):
                    status_desc = p.get('status', {}).get('description', 'Unknown')
                    
                    if any(x in status_desc.lower() for x in ['il', 'out', 'day-to-day', '7-day', '10-day', '15-day', '60-day', 'injured']):
                        pid = p['person']['id']
                        name = p['person']['fullName']
                        pos = p['position']['abbreviation']
                        
                        injuries = p['person'].get('injuries', [])
                        note = p.get('note', '')
                        
                        raw_detail = ""
                        if injuries:
                            latest_injury = injuries[0]
                            raw_detail = latest_injury.get('injuryDescription', latest_injury.get('injuryType', ''))
                        
                        if not raw_detail and note:
                            raw_detail = note
                            
                        if not raw_detail:
                            raw_detail = status_desc
                            
                        injury_detail = translate_injury(raw_detail)
                        level = "大聯盟 (MLB)" if t_id == team_id else "小聯盟 (MiLB)"
                        
                        if pid in il_players and il_players[pid]['傷勢部位/原因 (Injury)'] != "未公開詳細傷勢" and (injury_detail == "未公開詳細傷勢" or "未公開詳細傷勢" in injury_detail):
                            continue
                            
                        il_players[pid] = {
                            '球員 (Player)': name,
                            '所屬層級 (Level)': level,
                            '守位 (Pos)': pos,
                            '名單狀態 (Status)': status_desc,
                            '傷勢部位/原因 (Injury)': injury_detail,
                            '_is_mlb': 0 if t_id == team_id else 1
                        }
            except Exception as e:
                continue
                
    df = pd.DataFrame(list(il_players.values()))
    if not df.empty:
        df = df.sort_values(by=['_is_mlb', '名單狀態 (Status)']).drop(columns=['_is_mlb']).reset_index(drop=True)
    return df


@st.cache_data(ttl=3600*12)
def fetch_team_roster(team_id, year):
    url = f"https://statsapi.mlb.com/api/v1/teams/{team_id}/roster/Active?hydrate=person(stats(type=season,season={year}))"
    try:
        res = requests.get(url, timeout=15).json()
        roster = []
        for p in res.get('roster', []):
            primary_pos = p['position']['abbreviation']
            stats = p['person'].get('stats', [])
            pos_list = []
            if primary_pos in ['P', 'TWP']:
                p_stat = None
                for s in stats:
                    if s.get('group', {}).get('displayName') == 'pitching' and s.get('type', {}).get('displayName') == 'season' and s.get('splits'): p_stat = s['splits'][0].get('stat', {})
                if p_stat:
                    gs, gp, sv = p_stat.get('gamesStarted', 0), p_stat.get('gamesPlayed', 0), p_stat.get('saves', 0)
                    if gp > 0: pos_list.append('SP' if gs > gp / 2 else 'CL' if sv >= 3 else 'RP')
                else: pos_list.append('SP')
            for s in stats:
                if s.get('group', {}).get('displayName') == 'fielding' and s.get('type', {}).get('displayName') == 'season':
                    for split in s.get('splits', []):
                        f_pos = split.get('position', {}).get('abbreviation', '')
                        if f_pos and f_pos not in ['P', 'Unknown', 'PR', 'PH', 'DH', 'TWP']: pos_list.append(f_pos)
            if primary_pos == 'TWP' and 'DH' not in pos_list: pos_list.append('DH')
            if primary_pos == 'DH' and 'DH' not in pos_list: pos_list.append('DH')
            if not pos_list and primary_pos not in ['P', 'TWP']: pos_list.append(primary_pos)
            roster.append({'背號': p.get('jerseyNumber', '-'), '球員姓名 (Player)': p['person']['fullName'], '本季守備位置/角色 (Positions)': ", ".join(list(dict.fromkeys(pos_list)))})
        df = pd.DataFrame(roster)
        if not df.empty:
            df['num_sort'] = pd.to_numeric(df['背號'], errors='coerce').fillna(999)
            df = df.sort_values('num_sort').drop(columns=['num_sort']).reset_index(drop=True)
        return df
    except: return pd.DataFrame()

@st.cache_data(ttl=3600*6)
def fetch_team_recent_matchups(team_id, target_date_str):
    target_date = datetime.strptime(target_date_str, "%Y-%m-%d")
    start_date = (target_date - timedelta(days=20)).strftime("%Y-%m-%d")
    url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&teamId={team_id}&startDate={start_date}&endDate={target_date_str}"
    try:
        res = requests.get(url, timeout=10).json()
        games = []
        for date_data in res.get('dates', []):
            for game in date_data.get('games', []):
                if game.get('status', {}).get('statusCode') == 'F':
                    home_t, away_t = game['teams']['home']['team']['name'], game['teams']['away']['team']['name']
                    home_s, away_s = game['teams']['home'].get('score', 0), game['teams']['away'].get('score', 0)
                    is_home = (game['teams']['home']['team']['id'] == team_id)
                    games.append({'日期 (Date)': game['officialDate'], '對手 (Opponent)': away_t if is_home else home_t, '主/客 (H/A)': '🏠 主場' if is_home else '✈️ 客場', '勝負 (Result)': ('W' if home_s > away_s else 'L') if is_home else ('W' if away_s > home_s else 'L'), '比分 (Score)': f"{home_s} - {away_s}" if is_home else f"{away_s} - {home_s}"})
        return pd.DataFrame(games[-5:]).iloc[::-1].reset_index(drop=True)
    except: return pd.DataFrame()

@st.cache_data(ttl=3600*24)
def fetch_player_handedness(player_id):
    try:
        url = f"https://statsapi.mlb.com/api/v1/people/{int(player_id)}"
        person = requests.get(url, timeout=5).json().get('people', [{}])[0]
        return f"Bats/Throws: {person.get('batSide', {}).get('code', '-')}/{person.get('pitchHand', {}).get('code', '-')}"
    except: return "Bats/Throws: -/-"

@st.cache_data(ttl=3600*24)
def fetch_player_career(player_id, p_type):
    group = 'hitting' if p_type == '打者' else 'pitching'
    url = f"https://statsapi.mlb.com/api/v1/people/{int(player_id)}/stats?stats=yearByYear&group={group}"
    try:
        splits = requests.get(url, timeout=10).json().get('stats', [{}])[0].get('splits', [])
        data = []
        for s in splits:
            year, team, stat = s.get('season', ''), s.get('team', {}).get('name', 'Total'), s.get('stat', {})
            if p_type == '打者': data.append({'Season': year, 'Team': team, 'AVG': safe_float(stat.get('avg', 0)), 'OBP': safe_float(stat.get('obp', 0)), 'SLG': safe_float(stat.get('slg', 0)), 'OPS': safe_float(stat.get('ops', 0)), 'HR': int(stat.get('homeRuns', 0)), 'SB': int(stat.get('stolenBases', 0)), 'PA': int(stat.get('plateAppearances', 0)), 'H': int(stat.get('hits', 0))})
            else: data.append({'Season': year, 'Team': team, 'ERA': safe_float(stat.get('era', 0)), 'WHIP': safe_float(stat.get('whip', 0)), 'K': int(stat.get('strikeOuts', 0)), 'BB': int(stat.get('baseOnBalls', 0)), 'IP': float(str(stat.get('inningsPitched', '0')).replace('.1', '.333').replace('.2', '.667')), 'W': int(stat.get('wins', 0)), 'L': int(stat.get('losses', 0)), 'SV': int(stat.get('saves', 0))})
        df = pd.DataFrame(data)
        if not df.empty: df = df.drop_duplicates(subset=['Season'], keep='last')
        return df
    except: return pd.DataFrame()

@st.cache_data(ttl=3600)
def fetch_player_gamelog(player_id, p_type, year):
    group = 'hitting' if p_type == '打者' else 'pitching'
    url = f"https://statsapi.mlb.com/api/v1/people/{int(player_id)}/stats?stats=gameLog&group={group}&season={year}"
    try:
        splits = requests.get(url, timeout=10).json().get('stats', [{}])[0].get('splits', [])
        data = []
        for s in splits:
            stat, date = s.get('stat', {}), s.get('date', '')
            opp, venue_str = s.get('opponent', {}).get('name', 'Unknown'), "🏠 主場" if s.get('isHome', False) else "✈️ 客場"
            if p_type == '打者':
                H, HR, D, T = int(stat.get('hits', 0)), int(stat.get('homeRuns', 0)), int(stat.get('doubles', 0)), int(stat.get('triples', 0))
                S = H - D - T - HR
                R, RBI, SB, BB = int(stat.get('runs', 0)), int(stat.get('rbi', 0)), int(stat.get('stolenBases', 0)), int(stat.get('baseOnBalls', 0))
                HBP, K, E = int(stat.get('hitByPitch', 0)), int(stat.get('strikeOuts', 0)), int(stat.get('errors', 0))
                CYC, SLAM = 1 if (S >= 1 and D >= 1 and T >= 1 and HR >= 1) else 0, int(stat.get('grandSlams', 0))
                pts = R*3 + H*2 + S*3 + D*6 + T*10 + HR*15 + RBI*2 + SB*5 + BB*2 + HBP*3 + K*-2 + E*-3 + CYC*20 + SLAM*30
                data.append({'Date': date, 'Opponent': opp, '主/客': venue_str, 'AVG (賽季打擊率走勢)': safe_float(stat.get('avg', 0)), 'OBP (賽季上壘率走勢)': safe_float(stat.get('obp', 0)), 'SLG (賽季長打率走勢)': safe_float(stat.get('slg', 0)), 'OPS (賽季OPS走勢)': safe_float(stat.get('ops', 0)), 'AB': int(stat.get('atBats', 0)), 'R': R, 'H': H, 'RBI': RBI, 'HR': HR, 'SB': SB, 'BB': BB, 'K': K, 'Fantasy_Pts': pts})
            else:
                ip_str = str(stat.get('inningsPitched', '0'))
                ip_calc = float(ip_str.replace('.1', '.333').replace('.2', '.667'))
                OUT = int(ip_str.split('.')[0])*3 + int(ip_str.split('.')[1]) if '.' in ip_str else int(float(ip_str))*3
                W, L, SHO, SV = int(stat.get('wins', 0)), int(stat.get('losses', 0)), int(stat.get('shutouts', 0)), int(stat.get('saves', 0))
                H, ER, HR, BB = int(stat.get('hits', 0)), int(stat.get('earnedRuns', 0)), int(stat.get('homeRuns', 0)), int(stat.get('baseOnBalls', 0))
                HBP, K, WP = int(stat.get('hitBatsmen', 0)), int(stat.get('strikeOuts', 0)), int(stat.get('wildPitches', 0))
                HLD, BSV, QS = int(stat.get('holds', 0)), int(stat.get('blownSaves', 0)), 1 if (OUT >= 18 and ER <= 3) else 0
                pts = W*20 + L*-10 + SHO*15 + SV*8 + OUT*1 + H*-1 + ER*-3 + HR*-5 + BB*-1 + HBP*-2 + K*4 + WP*-3 + HLD*3 + QS*10 + BSV*-10
                data.append({'Date': date, 'Opponent': opp, '主/客': venue_str, 'ERA (賽季防禦率走勢)': safe_float(stat.get('era', 0)), 'WHIP (賽季WHIP走勢)': safe_float(stat.get('whip', 0)), 'IP': safe_float(stat.get('inningsPitched', 0)), 'IP_calc': ip_calc, 'H': H, 'R': int(stat.get('runs', 0)), 'ER': ER, 'BB': BB, 'K': K, 'PC': int(stat.get('numberOfPitches', 0)), 'HR': HR, 'Fantasy_Pts': pts})
        return pd.DataFrame(data).iloc[::-1].reset_index(drop=True) if data else pd.DataFrame()
    except: return pd.DataFrame()

@st.cache_data(ttl=3600*6)
def fetch_bullpen_usage(team_name, target_date_str):
    team_id = MLB_TEAM_IDS.get(team_name)
    if not team_id: return 0
    target_date = datetime.strptime(target_date_str, "%Y-%m-%d")
    start_date = (target_date - timedelta(days=2)).strftime("%Y-%m-%d")
    end_date = (target_date - timedelta(days=1)).strftime("%Y-%m-%d")
    
    async def fetch_all_bp():
        total_bp_pitches = 0
        async with aiohttp.ClientSession() as session:
            schedule_url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&teamId={team_id}&startDate={start_date}&endDate={end_date}"
            res = await fetch_json_async(schedule_url, session)
            
            tasks = []
            for date_data in res.get('dates', []):
                for game in date_data.get('games', []):
                    game_pk = game['gamePk']
                    tasks.append(fetch_json_async(f"https://statsapi.mlb.com/api/v1/game/{game_pk}/boxscore", session))
            
            box_results = await asyncio.gather(*tasks)
            for box_res in box_results:
                if not box_res or 'teams' not in box_res: continue
                team_side = None
                if box_res['teams']['home']['team']['id'] == team_id: team_side = 'home'
                elif box_res['teams']['away']['team']['id'] == team_id: team_side = 'away'
                if not team_side: continue
                
                pitchers = box_res['teams'][team_side].get('pitchers', [])
                if len(pitchers) > 1:
                    for pid in pitchers[1:]: 
                        total_bp_pitches += box_res['teams'][team_side]['players'].get(f"ID{pid}", {}).get('stats', {}).get('pitching', {}).get('numberOfPitches', 0)
        return total_bp_pitches

    try: loop = asyncio.get_event_loop()
    except RuntimeError: loop = asyncio.new_event_loop(); asyncio.set_event_loop(loop)
    return loop.run_until_complete(fetch_all_bp())

@st.cache_data(ttl=3600*6)
def fetch_team_recent_form(team_id, target_date_str):
    if not team_id: return []
    target_date = datetime.strptime(target_date_str, "%Y-%m-%d")
    try:
        res = requests.get(f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&teamId={team_id}&startDate={(target_date - timedelta(days=15)).strftime('%Y-%m-%d')}&endDate={(target_date - timedelta(days=1)).strftime('%Y-%m-%d')}", timeout=5).json()
        games = []
        for date_data in res.get('dates', []):
            for game in date_data.get('games', []):
                if game.get('status', {}).get('statusCode') == 'F':
                    is_home = game['teams']['home']['team']['id'] == team_id
                    games.append('W' if (game['teams']['home'].get('score', 0) > game['teams']['away'].get('score', 0) if is_home else game['teams']['away'].get('score', 0) > game['teams']['home'].get('score', 0)) else 'L')
        return games[-5:] 
    except: return []

@st.cache_data(ttl=3600*3)
def fetch_recent_form_ranking(p_type):
    tw_now = datetime.now(timezone(timedelta(hours=8)))
    end_dt = datetime(tw_now.year - 1, 9, 30) if tw_now.month < 4 else (datetime(tw_now.year, 9, 30) if tw_now.month >= 10 else tw_now)
    try:
        res = requests.get(f"https://statsapi.mlb.com/api/v1/stats?stats=byDateRange&group={'hitting' if p_type == '打者' else 'pitching'}&startDate={(end_dt - timedelta(days=14)).strftime('%Y-%m-%d')}&endDate={end_dt.strftime('%Y-%m-%d')}&sportId=1&gameType=R&playerPool=ALL&limit=2000&hydrate=person", timeout=25).json()
        data = []
        for s in res.get('stats', [{}])[0].get('splits', []):
            stat, p_name, t_name = s.get('stat', {}), s.get('player', {}).get('fullName', 'Unknown'), s.get('team', {}).get('name', 'Unknown')
            if p_type == '打者': data.append({'Player': p_name, 'Team': t_name, 'Position': s.get('player', {}).get('primaryPosition', {}).get('abbreviation', 'Unknown'), 'PA': stat.get('plateAppearances', 0), 'AVG': safe_float(stat.get('avg', 0)), 'OBP': safe_float(stat.get('obp', 0)), 'SLG': safe_float(stat.get('slg', 0)), 'OPS': safe_float(stat.get('ops', 0)), 'HR': stat.get('homeRuns', 0), 'RBI': stat.get('rbi', 0)})
            else:
                ip_str = str(stat.get('inningsPitched', '0'))
                data.append({'Player': p_name, 'Team': t_name, 'Position': 'SP' if (stat.get('gamesPlayed', 0) > 0 and stat.get('gamesStarted', 0) > stat.get('gamesPlayed', 0) / 2) else ('CL' if stat.get('saves', 0) >= 1 else 'RP'), 'IP': safe_float(stat.get('inningsPitched', 0)), 'IP_calc': float(ip_str.replace('.1', '.333').replace('.2', '.667')) if ip_str else 0.0, 'ERA': safe_float(stat.get('era', 0)), 'WHIP': safe_float(stat.get('whip', 0)), 'K': stat.get('strikeOuts', 0), 'BB': stat.get('baseOnBalls', 0), 'SV': stat.get('saves', 0)})
        return pd.DataFrame(data)
    except: return pd.DataFrame()

@st.cache_data(ttl=3600*12)
def fetch_player_home_away_splits(player_id, p_type, year):
    try:
        splits = requests.get(f"https://statsapi.mlb.com/api/v1/people/{int(player_id)}/stats?stats=homeAndAway&group={'hitting' if p_type == '打者' else 'pitching'}&season={year}", timeout=10).json().get('stats', [{}])[0].get('splits', [])
        data = []
        for idx, s in enumerate(splits):
            venue_str = "🏠 主場 (Home)" if s.get('isHome') is True else ("✈️ 客場 (Away)" if s.get('isHome') is False else ("🏠 主場 (Home)" if idx == 0 else "✈️ 客場 (Away)"))
            stat = s.get('stat', {})
            if p_type == '打者': data.append({'場地 (Split)': venue_str, 'PA': stat.get('plateAppearances', 0), 'AVG': safe_float(stat.get('avg', 0)), 'OBP': safe_float(stat.get('obp', 0)), 'SLG': safe_float(stat.get('slg', 0)), 'OPS': safe_float(stat.get('ops', 0)), 'HR': int(stat.get('homeRuns', 0)), 'K': int(stat.get('strikeOuts', 0)), 'BB': int(stat.get('baseOnBalls', 0))})
            else: data.append({'場地 (Split)': venue_str, 'IP': safe_float(stat.get('inningsPitched', 0)), 'ERA': safe_float(stat.get('era', 0)), 'WHIP': safe_float(stat.get('whip', 0)), 'K': int(stat.get('strikeOuts', 0)), 'BB': int(stat.get('baseOnBalls', 0)), 'HR': int(stat.get('homeRuns', 0)), 'BAA': safe_float(stat.get('avg', 0))})
        return pd.DataFrame(data).sort_values(by='場地 (Split)', ascending=False).reset_index(drop=True)
    except: return pd.DataFrame()

@st.cache_data(ttl=3600*12)
def fetch_savant_platoon_splits(player_id, p_type, year):
    try:
        df = statcast_batter(f"{year}-03-01", f"{year}-11-30", player_id) if p_type == '打者' else statcast_pitcher(f"{year}-03-01", f"{year}-11-30", player_id)
        if df is None or df.empty: return pd.DataFrame()
        split_col, split_map = ('p_throws', {'L': 'vs 左投 (vs LHP)', 'R': 'vs 右投 (vs RHP)'}) if p_type == '打者' else ('stand', {'L': 'vs 左打 (vs LHB)', 'R': 'vs 右打 (vs RHB)'})
        pa_df, splits_data = df[df['events'].notna() & (df['events'] != '')].copy(), []
        for hand in ['L', 'R']:
            hand_df, hand_pa = df[df[split_col] == hand], pa_df[pa_df[split_col] == hand]
            pa_count = len(hand_pa)
            if pa_count == 0: continue
            events = hand_pa['events']
            ab_count = events.isin(['single', 'double', 'triple', 'home_run', 'strikeout', 'strikeout_double_play', 'field_out', 'force_out', 'grounded_into_dp', 'double_play', 'field_error', 'fielders_choice', 'fielders_choice_out', 'other_out', 'batter_interference']).sum()
            hits = events.isin(['single', 'double', 'triple', 'home_run']).sum()
            bb_count, hbp_count, sf_count, k_count, hr_count = events.isin(['walk', 'intent_walk']).sum(), events.isin(['hit_by_pitch']).sum(), events.isin(['sac_fly', 'sac_fly_double_play']).sum(), events.isin(['strikeout', 'strikeout_double_play']).sum(), events.isin(['home_run']).sum()
            bbe_df = hand_df[hand_df['type'] == 'X'].dropna(subset=['launch_speed'])
            bbe_count = len(bbe_df)
            splits_data.append({
                '對戰慣用手 (Split)': split_map[hand], 'PA': pa_count,
                'AVG': safe_float(hits / ab_count if ab_count > 0 else 0),
                'OBP': safe_float((hits + bb_count + hbp_count) / (ab_count + bb_count + hbp_count + sf_count) if (ab_count + bb_count + hbp_count + sf_count) > 0 else 0),
                'SLG': safe_float(((events == 'single').sum() + (events == 'double').sum() * 2 + (events == 'triple').sum() * 3 + hr_count * 4) / ab_count if ab_count > 0 else 0),
                'OPS': safe_float((hits / ab_count if ab_count > 0 else 0) + ((events == 'single').sum() + (events == 'double').sum() * 2 + (events == 'triple').sum() * 3 + hr_count * 4) / ab_count if ab_count > 0 else 0),
                'K%': safe_float((k_count / pa_count) * 100), 'BB%': safe_float((bb_count / pa_count) * 100),
                'HardHit%': safe_float((len(bbe_df[bbe_df['launch_speed'] >= 95.0]) / bbe_count) * 100 if bbe_count > 0 else 0),
                'Barrel%': safe_float((len(bbe_df[bbe_df['launch_speed_angle'] == 6.0]) / bbe_count) * 100 if bbe_count > 0 else 0),
                'Whiff%': safe_float((len(hand_df[hand_df['description'].isin(['swinging_strike', 'swinging_strike_blocked', 'missed_bunt'])]) / len(hand_df[hand_df['description'].isin(['swinging_strike', 'swinging_strike_blocked', 'foul_tip', 'hit_into_play', 'foul', 'foul_bunt', 'missed_bunt'])])) * 100 if len(hand_df[hand_df['description'].isin(['swinging_strike', 'swinging_strike_blocked', 'foul_tip', 'hit_into_play', 'foul', 'foul_bunt', 'missed_bunt'])]) > 0 else 0),
                'Avg EV': safe_float(bbe_df['launch_speed'].mean() if bbe_count > 0 else 0)
            })
        return pd.DataFrame(splits_data)
    except: return pd.DataFrame()

@st.cache_data(ttl=3600*24*7)
def fetch_milb_mapping():
    mapping = {}
    try:
        for t in requests.get("https://statsapi.mlb.com/api/v1/teams?sportIds=11,12,13,14", timeout=15).json().get('teams', []):
            if t.get('name') and t.get('parentOrgName'): mapping[t.get('name')] = t.get('parentOrgName')
    except: pass
    return mapping

@st.cache_data(ttl=3600*24)
def fetch_milb_stats(year, sid, p_type):
    try:
        splits = requests.get(f"https://statsapi.mlb.com/api/v1/stats?stats=season&group={'hitting' if p_type == '打者' else 'pitching'}&season={year}&playerPool=ALL&sportId={sid}&limit=5000", timeout=15).json().get('stats', [{}])[0].get('splits', [])
        mapping, data = fetch_milb_mapping(), []
        for s in splits:
            stat, p_name = s.get('stat', {}), s.get('player', {}).get('fullName', 'Unknown')
            mlb_team = mapping.get(s.get('team', {}).get('name', 'Unknown'), s.get('team', {}).get('name', 'Unknown')) 
            if p_type == '打者':
                if stat.get('plateAppearances', 0) >= 50: data.append({'球員 (Player)': p_name, '大聯盟母隊 (MLB Team)': mlb_team, 'PA': stat.get('plateAppearances', 0), 'H': stat.get('hits', 0), 'HR': stat.get('homeRuns', 0), 'SB': stat.get('stolenBases', 0), 'AVG': float(stat.get('avg', 0) or 0), 'OBP': float(stat.get('obp', 0) or 0), 'SLG': float(stat.get('slg', 0) or 0), 'OPS': float(stat.get('ops', 0) or 0)})
            else:
                ip_str = str(stat.get('inningsPitched', '0'))
                if float(ip_str.replace('.1', '.333').replace('.2', '.667')) if ip_str else 0.0 >= 20.0: data.append({'球員 (Player)': p_name, '大聯盟母隊 (MLB Team)': mlb_team, 'IP': safe_float(stat.get('inningsPitched', 0)), 'W': stat.get('wins', 0), 'L': stat.get('losses', 0), 'ERA': float(stat.get('era', 0) or 0), 'WHIP': float(stat.get('whip', 0) or 0), 'K': stat.get('strikeOuts', 0), 'BB': stat.get('baseOnBalls', 0)})
        return pd.DataFrame(data)
    except: return pd.DataFrame()

@st.cache_data(ttl=3600*2)
def fetch_weekly_fantasy_ranking(p_type):
    group = 'hitting' if p_type == '打者' else 'pitching'
    tw_now = datetime.now(timezone(timedelta(hours=8)))
    
    if tw_now.month < 4: end_dt = datetime(tw_now.year - 1, 9, 30)
    elif tw_now.month > 10: end_dt = datetime(tw_now.year, 10, 1)
    else: end_dt = tw_now
    start_dt = end_dt - timedelta(days=7)
    
    url = f"https://statsapi.mlb.com/api/v1/stats?stats=byDateRange&group={group}&startDate={start_dt.strftime('%Y-%m-%d')}&endDate={end_dt.strftime('%Y-%m-%d')}&playerPool=ALL&sportId=1&gameType=R&limit=2000&hydrate=person"
    
    try:
        res = requests.get(url, timeout=25).json()
        splits = res.get('stats', [{}])[0].get('splits', [])
        if not splits: return pd.DataFrame()
        
        data = []
        for s in splits:
            stat = s.get('stat', {})
            name = s.get('player', {}).get('fullName', 'Unknown')
            team = s.get('team', {}).get('name', 'Unknown')
            pos_raw = s.get('player', {}).get('primaryPosition', {}).get('abbreviation', 'Unknown')
            
            G = int(stat.get('gamesPlayed', 0))
            if G == 0: continue
            
            if p_type == '打者':
                H, HR, D, T = int(stat.get('hits', 0)), int(stat.get('homeRuns', 0)), int(stat.get('doubles', 0)), int(stat.get('triples', 0))
                S = H - D - T - HR
                R, RBI, SB, BB = int(stat.get('runs', 0)), int(stat.get('rbi', 0)), int(stat.get('stolenBases', 0)), int(stat.get('baseOnBalls', 0))
                HBP, K, E = int(stat.get('hitByPitch', 0)), int(stat.get('strikeOuts', 0)), 0 
                
                SLAM = int(stat.get('grandSlams', 0))
                pts = R*3 + H*2 + S*3 + D*6 + T*10 + HR*15 + RBI*2 + SB*5 + BB*2 + HBP*3 + K*-2 + E*-3 + SLAM*30
                
                data.append({'Player': name, 'Team': team, 'Position': pos_raw, 'G (出賽)': G, 'Fan_Pts': pts, 'SLAM (滿貫砲)': SLAM, 'Avg_Pts': round(pts / G, 1)})
            else:
                ip_str = str(stat.get('inningsPitched', '0'))
                OUT = int(ip_str.split('.')[0])*3 + int(ip_str.split('.')[1]) if '.' in ip_str else int(float(ip_str))*3
                W, L, SHO, SV = int(stat.get('wins', 0)), int(stat.get('losses', 0)), int(stat.get('shutouts', 0)), int(stat.get('saves', 0))
                H, ER, HR, BB = int(stat.get('hits', 0)), int(stat.get('earnedRuns', 0)), int(stat.get('homeRuns', 0)), int(stat.get('baseOnBalls', 0))
                HBP, K, WP = int(stat.get('hitBatsmen', 0)), int(stat.get('strikeOuts', 0)), int(stat.get('wildPitches', 0))
                HLD, BSV = int(stat.get('holds', 0)), int(stat.get('blownSaves', 0))
                
                QS = int(stat.get('qualityStarts', 0))
                pts = W*20 + L*-10 + SHO*15 + SV*8 + OUT*1 + H*-1 + ER*-3 + HR*-5 + BB*-1 + HBP*-2 + K*4 + WP*-3 + HLD*3 + QS*10 + BSV*-10
                
                data.append({'Player': name, 'Team': team, 'Position': pos_raw, 'G (出賽)': G, 'Fan_Pts': pts, 'QS (優質先發)': QS, 'Avg_Pts': round(pts / G, 1)})
                
        df = pd.DataFrame(data)
        if not df.empty: df = df.sort_values('Fan_Pts', ascending=False).reset_index(drop=True)
        return df
    except: return pd.DataFrame()

# 🚀 【全新 API】抓取近一週球隊打線 OPS 與牛棚 ERA
@st.cache_data(ttl=3600*6)
def fetch_team_weekly_ops_and_bp_era(team_id, target_date_str):
    target_date = datetime.strptime(target_date_str, "%Y-%m-%d")
    start_date = (target_date - timedelta(days=7)).strftime("%Y-%m-%d")
    end_date = target_date_str
    
    recent_ops = 0.700
    try:
        hit_url = f"https://statsapi.mlb.com/api/v1/teams/{team_id}/stats?group=hitting&stats=byDateRange&startDate={start_date}&endDate={end_date}"
        h_res = requests.get(hit_url, timeout=5).json()
        if 'stats' in h_res and h_res['stats']:
            splits = h_res['stats'][0].get('splits', [])
            if splits:
                recent_ops = safe_float(splits[0]['stat'].get('ops', 0.700))
    except: pass

    async def fetch_bp():
        total_er = 0
        total_outs = 0
        async with aiohttp.ClientSession() as session:
            schedule_url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&teamId={team_id}&startDate={start_date}&endDate={end_date}"
            res = await fetch_json_async(schedule_url, session)
            
            tasks = []
            for date_data in res.get('dates', []):
                for game in date_data.get('games', []):
                    if game.get('status', {}).get('statusCode') == 'F':
                        game_pk = game['gamePk']
                        tasks.append(fetch_json_async(f"https://statsapi.mlb.com/api/v1/game/{game_pk}/boxscore", session))
            
            box_results = await asyncio.gather(*tasks)
            for box_res in box_results:
                if not box_res or 'teams' not in box_res: continue
                team_side = 'home' if box_res['teams']['home']['team']['id'] == team_id else 'away'
                pitchers = box_res['teams'][team_side].get('pitchers', [])
                if len(pitchers) > 1: # 扣除先發投手
                    for pid in pitchers[1:]: 
                        p_stat = box_res['teams'][team_side]['players'].get(f"ID{pid}", {}).get('stats', {}).get('pitching', {})
                        total_er += int(p_stat.get('earnedRuns', 0))
                        ip_str = str(p_stat.get('inningsPitched', '0'))
                        if '.' in ip_str:
                            total_outs += int(ip_str.split('.')[0])*3 + int(ip_str.split('.')[1])
                        else:
                            total_outs += int(safe_float(ip_str))*3
        
        if total_outs == 0: return 4.00
        return (total_er / (total_outs / 3)) * 9

    try: loop = asyncio.get_event_loop()
    except RuntimeError: loop = asyncio.new_event_loop(); asyncio.set_event_loop(loop)
    recent_bp_era = loop.run_until_complete(fetch_bp())
    
    return recent_ops, round(recent_bp_era, 2)
