#!/usr/bin/env python3
"""采集A股涨停/连板/炸板/跌停数据，保存为 Markdown"""

import os
import datetime
import akshare as ak
import pandas as pd


def get_trade_date():
    """获取交易日期（北京时间，周末自动回退到周五）"""
    env_date = os.environ.get("TRADE_DATE", "")
    if env_date:
        return env_date

    bj = datetime.timezone(datetime.timedelta(hours=8))
    now = datetime.datetime.now(bj)
    wd = now.weekday()
    if wd == 5:
        now -= datetime.timedelta(days=1)
    elif wd == 6:
        now -= datetime.timedelta(days=2)
    return now.strftime("%Y%m%d")


def safe_collect(name, func, date_str):
    """安全采集，失败返回空 DataFrame"""
    try:
        df = func(date=date_str)
        if df is not None and not df.empty:
            print(f"  ✅ {name}: {len(df)} 条")
            return df
        else:
            print(f"  ⚠️ {name}: 无数据")
    except Exception as e:
        print(f"  ❌ {name} 失败: {e}")
    return pd.DataFrame()


def df_to_md(df):
    """DataFrame 转 Markdown 表格"""
    if df.empty:
        return "（无数据）\n"
    try:
        return df.to_markdown(index=False) + "\n"
    except Exception:
        return df.to_string(index=False) + "\n"


def calc_stats(zt_df, zb_df, dt_df):
    """计算市场情绪统计"""
    zt = len(zt_df)
    zb = len(zb_df)
    dt = len(dt_df)
    zb_rate = round(zb / (zt + zb) * 100, 1) if (zt + zb) > 0 else 0

    lines = [
        f"- 涨停数量: {zt}",
        f"- 炸板数量: {zb}",
        f"- 炸板率: {zb_rate}%",
        f"- 跌停数量: {dt}",
        f"- 涨跌停比: {zt}:{dt}",
    ]

    # 连板梯队
    if not zt_df.empty:
        lb_col = next((c for c in zt_df.columns if "连板" in str(c)), None)
        name_col = next((c for c in zt_df.columns if "名称" in str(c)), None)
        if lb_col and name_col:
            zt_df[lb_col] = pd.to_numeric(zt_df[lb_col], errors="coerce").fillna(1).astype(int)
            max_lb = zt_df[lb_col].max()
            lines.append(f"- 最高连板: {max_lb} 板")
            for n in range(int(max_lb), 1, -1):
                names = zt_df.loc[zt_df[lb_col] == n, name_col].tolist()
                if names:
                    lines.append(f"- {n}板({len(names)}只): {', '.join(names)}")

    return "\n".join(lines)


def main():
    date_str = get_trade_date()
    print(f"📅 交易日期: {date_str}")
    print(f"📊 开始采集数据...\n")

    # ===== 采集 =====
    print("1️⃣ 涨停股池")
    zt_df = safe_collect("涨停池", ak.stock_zt_pool_em, date_str)

    print("2️⃣ 炸板股池")
    zb_df = safe_collect("炸板池", ak.stock_zt_pool_zbgc_em, date_str)

    print("3️⃣ 跌停股池")
    dt_df = safe_collect("跌停池", ak.stock_zt_pool_dtgc_em, date_str)

    # ===== 生成 Markdown =====
    stats = calc_stats(zt_df, zb_df, dt_df)

    md = f"""# A股连板数据 {date_str}

## 一、市场情绪概览

{stats}

## 二、涨停股池

{df_to_md(zt_df)}

## 三、炸板股池

{df_to_md(zb_df)}

## 四、跌停股池

{df_to_md(dt_df)}
"""

    # ===== 保存 =====
    os.makedirs("data", exist_ok=True)
    filepath = f"data/lianban_data_{date_str}.md"
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(md)

    print(f"\n💾 已保存: {filepath} ({len(md)} 字符)")

    if zt_df.empty and zb_df.empty and dt_df.empty:
        print("⚠️ 所有数据为空，可能不是交易日")


if __name__ == "__main__":
    main()
