#!/usr/bin/env python3
"""连板打板数据采集模块"""

import akshare as ak
import json
import datetime
import time
import os
import sys

def get_trade_date():
    """获取最近交易日"""
    today = datetime.datetime.now()
    for i in range(7):
        date = today - datetime.timedelta(days=i)
        date_str = date.strftime('%Y%m%d')
        try:
            df = ak.stock_zt_pool_em(date=date_str)
            if df is not None and not df.empty:
                return date_str
        except:
            continue
    return today.strftime('%Y%m%d')

def collect_zt_pool(date_str):
    """今日涨停池"""
    try:
        df = ak.stock_zt_pool_em(date=date_str)
        if df is None or df.empty:
            return []
        records = []
        for _, row in df.iterrows():
            records.append({
                '代码': str(row.get('代码', '')),
                '名称': str(row.get('名称', '')),
                '涨跌幅': round(float(row.get('涨跌幅', 0)), 2),
                '最新价': float(row.get('最新价', 0)),
                '成交额': round(float(row.get('成交额', 0)) / 1e8, 2),  # 亿
                '流通市值': round(float(row.get('流通市值', 0)) / 1e8, 2),  # 亿
                '换手率': round(float(row.get('换手率', 0)), 2),
                '连板数': int(row.get('连板数', 1)),
                '封板资金': round(float(row.get('封板资金', 0)) / 1e8, 2),  # 亿
                '首次涨停时间': str(row.get('首次封板时间', '')),
                '最后涨停时间': str(row.get('最后封板时间', '')),
                '炸板次数': int(row.get('炸板次数', 0)),
                '所属行业': str(row.get('所属行业', '')),
            })
        return records
    except Exception as e:
        print(f"获取涨停池失败: {e}")
        return []

def collect_yesterday_zt(date_str):
    """昨日涨停今日表现（算晋级率）"""
    try:
        df = ak.stock_zt_pool_previous_em(date=date_str)
        if df is None or df.empty:
            return {'total': 0, 'data': []}
        records = []
        for _, row in df.iterrows():
            records.append({
                '代码': str(row.get('代码', '')),
                '名称': str(row.get('名称', '')),
                '涨跌幅': round(float(row.get('涨跌幅', 0)), 2),
                '开盘价': float(row.get('开盘价', 0)),
                '最新价': float(row.get('最新价', 0)),
            })
        return {'total': len(records), 'data': records}
    except Exception as e:
        print(f"获取昨日涨停失败: {e}")
        return {'total': 0, 'data': []}

def collect_zbgc(date_str):
    """炸板股"""
    try:
        df = ak.stock_zt_pool_zbgc_em(date=date_str)
        if df is None or df.empty:
            return []
        records = []
        for _, row in df.iterrows():
            records.append({
                '代码': str(row.get('代码', '')),
                '名称': str(row.get('名称', '')),
                '涨跌幅': round(float(row.get('涨跌幅', 0)), 2),
                '炸板次数': int(row.get('炸板次数', 0)),
            })
        return records
    except Exception as e:
        print(f"获取炸板股失败: {e}")
        return []

def collect_dtgc(date_str):
    """跌停股"""
    try:
        df = ak.stock_zt_pool_dtgc_em(date=date_str)
        if df is None or df.empty:
            return 0
        return len(df)
    except Exception as e:
        print(f"获取跌停股失败: {e}")
        return 0

def collect_concept_boards():
    """概念板块涨幅排名"""
    try:
        df = ak.stock_board_concept_name_em()
        if df is None or df.empty:
            return []
        df = df.sort_values('涨跌幅', ascending=False)
        top_boards = []
        for _, row in df.head(15).iterrows():
            top_boards.append({
                '板块名称': str(row.get('板块名称', '')),
                '涨跌幅': round(float(row.get('涨跌幅', 0)), 2),
                '总市值': round(float(row.get('总市值', 0)) / 1e8, 0),
                '上涨家数': int(row.get('上涨家数', 0)),
                '下跌家数': int(row.get('下跌家数', 0)),
                '领涨股票': str(row.get('领涨股票', '')),
            })
        return top_boards
    except Exception as e:
        print(f"获取概念板块失败: {e}")
        return []

def analyze_lianban_ladder(zt_pool):
    """分析连板梯队"""
    ladder = {}
    for stock in zt_pool:
        height = stock['连板数']
        if height not in ladder:
            ladder[height] = []
        ladder[height].append(stock)
    
    result = {}
    for height in sorted(ladder.keys(), reverse=True):
        stocks = ladder[height]
        result[f'{height}板'] = [
            {
                '代码': s['代码'],
                '名称': s['名称'],
                '封板资金': s['封板资金'],
                '换手率': s['换手率'],
                '成交额': s['成交额'],
                '首次涨停时间': s['首次涨停时间'],
                '炸板次数': s['炸板次数'],
                '所属行业': s['所属行业'],
            } for s in sorted(stocks, key=lambda x: x['封板资金'], reverse=True)
        ]
    return result

def calc_market_emotion(zt_pool, zbgc_list, dt_count, yesterday_zt):
    """计算市场情绪指标"""
    zt_count = len(zt_pool)
    zb_count = len(zbgc_list)
    
    # 炸板率
    total_touch = zt_count + zb_count
    zb_rate = round(zb_count / total_touch * 100, 1) if total_touch > 0 else 0
    
    # 晋级率（昨日涨停今日继续涨停的比例）
    yesterday_total = yesterday_zt['total']
    if yesterday_total > 0:
        today_zt_codes = {s['代码'] for s in zt_pool}
        yesterday_codes = {s['代码'] for s in yesterday_zt['data']}
        promoted = today_zt_codes & yesterday_codes
        promotion_rate = round(len(promoted) / yesterday_total * 100, 1)
    else:
        promotion_rate = 0
        promoted = set()
    
    # 最高连板
    max_height = max([s['连板数'] for s in zt_pool], default=0)
    
    # 涨停/跌停比
    zt_dt_ratio = round(zt_count / dt_count, 1) if dt_count > 0 else zt_count
    
    # 昨日涨停今日平均涨跌
    if yesterday_zt['data']:
        avg_change = round(
            sum(s['涨跌幅'] for s in yesterday_zt['data']) / len(yesterday_zt['data']), 2
        )
    else:
        avg_change = 0
    
    # 情绪周期判断
    if zt_count >= 80 and zb_rate < 20 and promotion_rate > 50:
        emotion_phase = '加速上升期（高潮前）'
    elif zt_count >= 100 and zb_rate < 15:
        emotion_phase = '高潮期（注意风险）'
    elif zt_count >= 60 and zb_rate < 30 and promotion_rate > 30:
        emotion_phase = '上升期（可积极参与）'
    elif zt_count >= 40 and promotion_rate > 20:
        emotion_phase = '修复期（精选个股）'
    elif zt_count < 30 or zb_rate > 50 or promotion_rate < 15:
        emotion_phase = '退潮期（以防守为主）'
    elif dt_count > zt_count:
        emotion_phase = '冰点期（等待转折信号）'
    else:
        emotion_phase = '震荡期（控制仓位）'
    
    return {
        '涨停数': zt_count,
        '跌停数': dt_count,
        '涨跌停比': zt_dt_ratio,
        '炸板数': zb_count,
        '炸板率': f'{zb_rate}%',
        '昨日涨停数': yesterday_total,
        '晋级率': f'{promotion_rate}%',
        '昨日涨停今日均涨': f'{avg_change}%',
        '最高连板': f'{max_height}板',
        '情绪周期': emotion_phase,
    }

def identify_themes(zt_pool, concept_boards):
    """识别主攻题材方向"""
    # 按行业分组涨停股
    industry_groups = {}
    for stock in zt_pool:
        industry = stock.get('所属行业', '未知')
        if industry not in industry_groups:
            industry_groups[industry] = []
        industry_groups[industry].append(stock)
    
    # 按涨停数量排序
    themes = []
    for industry, stocks in sorted(industry_groups.items(), key=lambda x: len(x[1]), reverse=True):
        if len(stocks) >= 2:  # 至少2个涨停才算题材
            themes.append({
                '题材方向': industry,
                '涨停数量': len(stocks),
                '代表股': [{'名称': s['名称'], '代码': s['代码'], '连板数': s['连板数']} 
                          for s in sorted(stocks, key=lambda x: x['连板数'], reverse=True)[:5]],
                '最高连板': max(s['连板数'] for s in stocks),
            })
    
    return themes[:10]  # 最多10个题材

def build_report_data(date_str):
    """构建完整数据报告"""
    print(f"📊 开始采集 {date_str} 连板数据...")
    
    print("  → 获取涨停池...")
    zt_pool = collect_zt_pool(date_str)
    time.sleep(1)
    
    print("  → 获取昨日涨停表现...")
    yesterday_zt = collect_yesterday_zt(date_str)
    time.sleep(1)
    
    print("  → 获取炸板股...")
    zbgc_list = collect_zbgc(date_str)
    time.sleep(1)
    
    print("  → 获取跌停数...")
    dt_count = collect_dtgc(date_str)
    time.sleep(1)
    
    print("  → 获取概念板块...")
    concept_boards = collect_concept_boards()
    time.sleep(1)
    
    print("  → 分析连板梯队...")
    lianban_ladder = analyze_lianban_ladder(zt_pool)
    
    print("  → 计算市场情绪...")
    market_emotion = calc_market_emotion(zt_pool, zbgc_list, dt_count, yesterday_zt)
    
    print("  → 识别题材方向...")
    themes = identify_themes(zt_pool, concept_boards)
    
    report = {
        '日期': date_str,
        '市场情绪': market_emotion,
        '连板梯队': lianban_ladder,
        '主攻题材': themes,
        '概念板块TOP15': concept_boards,
        '昨日涨停今日表现': {
            '总数': yesterday_zt['total'],
            '明细': yesterday_zt['data'][:20],
        },
        '炸板股': zbgc_list[:10],
        '涨停池原始数据': zt_pool,
    }
    
    return report

def format_as_markdown(report):
    """将数据格式化为 Markdown 供 AI 分析"""
    md = []
    md.append(f"# 连板打板数据报告 ({report['日期']})\n")
    
    # 市场情绪
    emotion = report['市场情绪']
    md.append("## 一、市场情绪总览")
    md.append(f"- 情绪周期判断：**{emotion['情绪周期']}**")
    md.append(f"- 涨停 {emotion['涨停数']} 家 | 跌停 {emotion['跌停数']} 家 | 涨跌停比 {emotion['涨跌停比']}")
    md.append(f"- 炸板 {emotion['炸板数']} 家 | 炸板率 {emotion['炸板率']}")
    md.append(f"- 昨日涨停 {emotion['昨日涨停数']} 家 → 今日晋级率 {emotion['晋级率']}")
    md.append(f"- 昨日涨停今日平均涨跌：{emotion['昨日涨停今日均涨']}")
    md.append(f"- 最高连板：{emotion['最高连板']}")
    md.append("")
    
    # 连板梯队
    md.append("## 二、连板梯队")
    for height, stocks in report['连板梯队'].items():
        md.append(f"\n### {height}（{len(stocks)}只）")
        for s in stocks:
            md.append(
                f"- **{s['名称']}**({s['代码']}) | "
                f"封板资金:{s['封板资金']}亿 | "
                f"换手:{s['换手率']}% | "
                f"成交:{s['成交额']}亿 | "
                f"首封:{s['首次涨停时间']} | "
                f"炸板:{s['炸板次数']}次 | "
                f"行业:{s['所属行业']}"
            )
    md.append("")
    
    # 主攻题材
    md.append("## 三、主攻题材方向")
    for i, theme in enumerate(report['主攻题材'], 1):
        md.append(f"\n### {i}. {theme['题材方向']}（{theme['涨停数量']}只涨停，最高{theme['最高连板']}板）")
        for s in theme['代表股']:
            board_tag = f"[{s['连板数']}板]" if s['连板数'] > 1 else "[首板]"
            md.append(f"  - {board_tag} {s['名称']}({s['代码']})")
    md.append("")
    
    # 概念板块
    md.append("## 四、概念板块涨幅TOP15")
    for b in report['概念板块TOP15']:
        md.append(
            f"- {b['板块名称']} | 涨跌幅:{b['涨跌幅']}% | "
            f"上涨{b['上涨家数']}家/下跌{b['下跌家数']}家 | "
            f"领涨:{b['领涨股票']}"
        )
    md.append("")
    
    # 昨日涨停今日表现
    md.append("## 五、昨日涨停今日表现（晋级情况）")
    yesterday = report['昨日涨停今日表现']
    if yesterday['明细']:
        for s in sorted(yesterday['明细'], key=lambda x: x['涨跌幅'], reverse=True):
            tag = "🟢" if s['涨跌幅'] > 5 else ("🟡" if s['涨跌幅'] > 0 else "🔴")
            md.append(f"- {tag} {s['名称']}({s['代码']}) | 涨跌幅:{s['涨跌幅']}%")
    md.append("")
    
    # 炸板股
    md.append("## 六、炸板股")
    for s in report['炸板股']:
        md.append(f"- {s['名称']}({s['代码']}) | 涨跌幅:{s['涨跌幅']}% | 炸板{s['炸板次数']}次")
    
    return '\n'.join(md)

def main():
    date_str = get_trade_date()
    print(f"交易日期: {date_str}")
    
    report = build_report_data(date_str)
    
    # 保存 JSON
    os.makedirs('data', exist_ok=True)
    json_path = f'data/lianban_data_{date_str}.json'
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"✅ JSON 数据已保存: {json_path}")
    
    # 保存 Markdown
    md_content = format_as_markdown(report)
    md_path = f'data/lianban_data_{date_str}.md'
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(md_content)
    print(f"✅ Markdown 数据已保存: {md_path}")
    
    # 输出到环境变量供后续步骤使用
    github_env = os.environ.get('GITHUB_ENV', '')
    if github_env:
        with open(github_env, 'a') as f:
            f.write(f'LIANBAN_DATA_PATH={md_path}\n')
            f.write(f'TRADE_DATE={date_str}\n')
            
            # 提取连板股代码列表
            all_codes = [s['代码'] for s in report['涨停池原始数据'] 
                        if s['连板数'] >= 2]
            # 加上封板资金最大的首板
            shouban = [s for s in report['涨停池原始数据'] if s['连板数'] == 1]
            shouban.sort(key=lambda x: x['封板资金'], reverse=True)
            all_codes.extend([s['代码'] for s in shouban[:5]])
            
            if all_codes:
                f.write(f'ZT_STOCK_LIST={",".join(all_codes[:15])}\n')
    
    # 打印摘要
    emotion = report['市场情绪']
    print(f"\n{'='*50}")
    print(f"📊 市场情绪: {emotion['情绪周期']}")
    print(f"📈 涨停 {emotion['涨停数']} | 跌停 {emotion['跌停数']} | 炸板率 {emotion['炸板率']}")
    print(f"🔄 晋级率 {emotion['晋级率']} | 最高 {emotion['最高连板']}")
    print(f"{'='*50}")

if __name__ == '__main__':
    main()
