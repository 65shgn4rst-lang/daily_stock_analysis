import akshare as ak
import json
import os
from datetime import datetime

def collect_data():
    today = datetime.now().strftime("%Y%m%d")
    result = {
        "date": today,
        "overview": {},
        "lianban": {},    # 2板及以上
        "shouban": [],    # 首板
    }

    # ========== 涨停板数据 ==========
    try:
        df = ak.stock_zt_pool_em(date=today)
        total_zt = len(df)
        result["overview"]["涨停数量"] = total_zt

        # 炸板数据
        try:
            df_zb = ak.stock_zt_pool_zbgc_em(date=today)
            zb_count = len(df_zb)
        except:
            zb_count = 0
        result["overview"]["炸板数量"] = zb_count
        result["overview"]["炸板率"] = f"{round(zb_count/(total_zt+zb_count)*100, 1)}%" if (total_zt+zb_count) > 0 else "0%"

        # ===== 关键修复：用连板天数字段正确分类 =====
        if "连板数" in df.columns:
            board_col = "连板数"
        elif "连续涨停天数" in df.columns:
            board_col = "连续涨停天数"
        else:
            board_col = None

        max_board = 0
        if board_col:
            for _, row in df.iterrows():
                board_num = int(row[board_col])
                name = row["名称"]
                code = row["代码"]

                stock_info = {
                    "代码": code,
                    "名称": name,
                    "连板数": board_num,
                    "封板资金": round(row.get("封板资金", 0) / 1e8, 2),
                    "换手率": round(row.get("换手率", 0), 2),
                    "成交额": round(row.get("成交额", 0) / 1e8, 2),
                    "首次封板时间": str(row.get("首次封板时间", "")),
                    "炸板次数": int(row.get("炸板次数", 0)),
                    "涨停原因": str(row.get("涨停原因", "")),
                }

                if board_num >= 2:
                    key = f"{board_num}板"
                    if key not in result["lianban"]:
                        result["lianban"][key] = []
                    result["lianban"][key].append(stock_info)
                else:
                    result["shouban"].append(stock_info)

                max_board = max(max_board, board_num)

        result["overview"]["最高连板"] = max_board
        result["overview"]["连板晋级率"] = calc_promotion_rate(result["lianban"])

        # 昨日涨停股今日表现
        try:
            df_next = ak.stock_zt_pool_previous_em(date=today)
            if len(df_next) > 0:
                avg_change = round(df_next["涨跌幅"].mean(), 2)
                result["overview"]["昨日涨停今日均涨"] = f"{avg_change}%"
            else:
                result["overview"]["昨日涨停今日均涨"] = "无数据"
        except:
            result["overview"]["昨日涨停今日均涨"] = "获取失败"

        # 首板按封板资金排序，取前10
        result["shouban"] = sorted(result["shouban"], key=lambda x: x["封板资金"], reverse=True)[:10]

    except Exception as e:
        print(f"❌ 数据采集出错: {e}")
        return None

    # 保存
    os.makedirs("data", exist_ok=True)
    filepath = f"data/lianban_{today}.json"
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"✅ 数据已保存: {filepath}")
    return result


def calc_promotion_rate(lianban):
    """计算连板晋级率"""
    rates = {}
    sorted_keys = sorted(lianban.keys(), key=lambda x: int(x.replace("板", "")))
    for i in range(len(sorted_keys) - 1):
        curr = sorted_keys[i]
        next_key = sorted_keys[i + 1]
        curr_count = len(lianban[curr])
        next_count = len(lianban[next_key])
        if curr_count > 0:
            rates[f"{curr}→{next_key}"] = f"{round(next_count/curr_count*100, 1)}%"
    return rates


if __name__ == "__main__":
    collect_data()
