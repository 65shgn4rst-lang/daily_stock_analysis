#!/usr/bin/env python3
"""获取当日涨停股票列表"""
import akshare as ak
import datetime
import os
import sys

def get_zt_stocks(max_count=10):
    today = datetime.datetime.now().strftime("%Y%m%d")
    try:
        df = ak.stock_zt_pool_em(date=today)
        if df is not None and not df.empty:
            # 按封单额排序，优先分析资金最强的
            if '封单额' in df.columns:
                df = df.sort_values('封单额', ascending=False)
            codes = df['代码'].tolist()[:max_count]
            return ",".join(codes)
    except Exception as e:
        print(f"获取涨停股失败: {e}", file=sys.stderr)
        # 尝试用昨天的日期
        yesterday = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%Y%m%d")
        try:
            df = ak.stock_zt_pool_em(date=yesterday)
            if df is not None and not df.empty:
                if '封单额' in df.columns:
                    df = df.sort_values('封单额', ascending=False)
                codes = df['代码'].tolist()[:max_count]
                return ",".join(codes)
        except:
            pass
    return ""

if __name__ == "__main__":
    max_count = int(os.environ.get("ZT_MAX_COUNT", "10"))
    result = get_zt_stocks(max_count)
    if result:
        print(result)
        print(f"共获取 {len(result.split(','))} 只涨停股", file=sys.stderr)
    else:
        print("未获取到涨停股数据", file=sys.stderr)
        sys.exit(1)
