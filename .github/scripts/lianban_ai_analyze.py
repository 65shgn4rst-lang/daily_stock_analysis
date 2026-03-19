#!/usr/bin/env python3
"""连板打板 AI 分析 —— 读取数据 → 调用 Gemini → 保存报告"""

import os
import sys
import glob
import datetime
import akshare as ak

from google import genai
from google.genai import types

# ===== 分析提示词 =====
PROMPT = """你是一位严谨的A股连板打板策略分析师。

【铁律 - 违反任何一条视为失败】
1. 所有结论必须有数据支撑，严禁与数据矛盾
2. 判断市场情绪时，必须首先看大盘指数涨跌和个股涨跌比，如果大盘下跌且下跌家数远超上涨家数，绝对不能判断为"修复向上"或"回暖"
3. 报告必须包含"首板精选"部分
4. 每只股票必须给出明确的买入条件和放弃条件
5. 不得使用模糊乐观的措辞美化弱势行情

请根据以下今日市场数据，生成一份**连板打板策略报告**。

---
{market_data}
---

【关键约束】
- 如果数据中大盘指数下跌、下跌家数占比超过60%，情绪定位只能是"退潮""冰点""弱修复"之一，不得定位为"修复向上""回暖""上升"
- 涨停数量多不代表市场好，必须结合大盘涨跌、个股涨跌比综合判断
- 首板精选：从当日首板涨停股中筛选2~3只次日最值得关注的，要求有明确题材逻辑或辨识度

【市场数据】


【输出格式 - 严格按此结构】

# 🔥 连板打板策略报告 

## 一、市场情绪总览

### 1. 大盘环境
- **指数表现**：如实描述三大指数涨跌幅
- **个股涨跌**：上涨 X 家 / 下跌 X 家（比值 X:X）
- **市场强弱**：强势 / 偏强 / 中性 / 偏弱 / 弱势（必须与上述数据一致）

### 2. 连板生态数据
| 指标 | 数值 | 解读 |
|------|------|------|
| 涨停家数 | | |
| 跌停家数 | | |
| 炸板数/炸板率 | | |
| 最高连板 | | |
| 涨跌停比 | | |
| 昨日连板今日晋级率 | | |

### 3. 情绪周期定位
- **当前阶段**：冰点 / 退潮 / 弱修复 / 修复 / 回暖 / 上升 / 高潮 / 过热（选一个）
- **核心依据**：列出至少3条数据支撑
- **与昨日对比**：转暖 / 持平 / 转冷（说明理由）
- **明日情绪预判**：

## 二、主线题材研判

按强弱排序，每个题材包含：
- **驱动逻辑**
- **持续性判断**
- **梯队结构**：龙头 → 二梯队 → 跟风/首板

## 三、连板股深度分析（2板及以上，按板数从高到低）

对每只股票：
### X. 股票名称（代码）- N板（题材）
- **身份定位**：
- **封板质量**：封单额、换手率、封板时间、炸板次数、成交额
- **辨识度**：高/中/低，原因
- **明日策略**：
  - 竞价预判：
  - ✅ 买入条件：（具体、可执行）
  - ❌ 放弃条件：（具体、可执行）
  - 💰 价位参考：

## 四、首板精选（2~3只）

从当日首板涨停股中精选次日最值得关注的：

### X. 股票名称（代码）- 首板（题材）
- **涨停逻辑**：为什么涨停
- **题材地位**：是否主线、是否有辨识度
- **封板质量**：封单额、换手率、封板时间
- **技术位置**：高位追涨 / 低位启动 / 突破形态
- **明日策略**：
  - ✅ 买入条件：
  - ❌ 放弃条件：

## 五、明日操作总结

- **仓位建议**：X成（必须与市场强弱判断一致，弱势不得建议高仓位）
- **主攻方向**：
- **防守要点**：
- **风险提示**：

---
*⚠️ AI辅助分析，仅供参考，不构成投资建议。*
"""
def get_supplementary_data():
    """获取AI分析所需的补充数据：指数、涨跌家数、首板"""
    sections = []
    today = datetime.now().strftime("%Y%m%d")

    # ===== 1. 三大指数 =====
    sections.append("=" * 50)
    sections.append("【大盘指数表现】")
    sections.append("=" * 50)
    try:
        df = ak.stock_zh_index_spot_em()
        for name in ["上证指数", "深证成指", "创业板指"]:
            row = df[df["名称"] == name]
            if not row.empty:
                r = row.iloc[0]
                price = r.get("最新价", "N/A")
                chg = r.get("涨跌幅", 0)
                chg_val = r.get("涨跌额", 0)
                sections.append(f"  {name}: {price}  涨跌额:{chg_val:+.2f}  涨跌幅:{chg:+.2f}%")
        print("[OK] 指数数据获取成功")
    except Exception as e:
        sections.append(f"  获取失败: {e}")
        print(f"[WARN] 指数数据获取失败: {e}")

    # ===== 2. 全市场涨跌家数 =====
    sections.append("")
    sections.append("=" * 50)
    sections.append("【全市场个股涨跌统计】")
    sections.append("=" * 50)
    try:
        df = ak.stock_zh_a_spot_em()
        total = len(df)
        up = int((df["涨跌幅"] > 0).sum())
        down = int((df["涨跌幅"] < 0).sum())
        flat = int((df["涨跌幅"] == 0).sum())
        up_gt5 = int((df["涨跌幅"] > 5).sum())
        down_gt5 = int((df["涨跌幅"] < -5).sum())
        sections.append(f"  总股票数: {total}")
        sections.append(f"  上涨: {up}家 ({up/total*100:.1f}%)")
        sections.append(f"  下跌: {down}家 ({down/total*100:.1f}%)")
        sections.append(f"  平盘: {flat}家")
        sections.append(f"  涨跌比: {up}:{down}")
        sections.append(f"  涨幅>5%: {up_gt5}家")
        sections.append(f"  跌幅>5%: {down_gt5}家")
        if down > up:
            sections.append(f"  ⚠️ 下跌家数远超上涨家数，市场整体偏弱")
        print(f"[OK] 涨跌家数: 涨{up} 跌{down}")
    except Exception as e:
        sections.append(f"  获取失败: {e}")
        print(f"[WARN] 涨跌数据获取失败: {e}")

    # ===== 3. 首板涨停股 =====
    sections.append("")
    sections.append("=" * 50)
    sections.append("【今日首板涨停股】")
    sections.append("=" * 50)
    try:
        df_zt = ak.stock_zt_pool_em(date=today)
        print(f"[DEBUG] 涨停池列名: {list(df_zt.columns)}")
        
        # 筛选首板（连板数==1）
        if "连板数" in df_zt.columns:
            first_board = df_zt[df_zt["连板数"] == 1].copy()
        else:
            # 如果没有连板数列，全部当首板处理
            first_board = df_zt.copy()

        sections.append(f"  首板涨停共 {len(first_board)} 只")
        sections.append("")

        for _, r in first_board.iterrows():
            name = r.get("名称", "")
            code = r.get("代码", "")
            reason = r.get("涨停原因", "无")
            seal = r.get("封单额", 0)
            seal_str = f"{seal/1e8:.2f}亿" if seal else "N/A"
            turnover = r.get("换手率", 0)
            first_time = r.get("首次封板时间", "N/A")
            last_time = r.get("最终封板时间", "N/A")
            zb_count = r.get("炸板次数", 0)
            amount = r.get("成交额", 0)
            amount_str = f"{amount/1e8:.2f}亿" if amount else "N/A"

            sections.append(
                f"  {name}({code}) | 原因:{reason} | "
                f"封单:{seal_str} | 换手:{turnover:.1f}% | "
                f"首封:{first_time} | 末封:{last_time} | "
                f"炸板:{zb_count}次 | 成交:{amount_str}"
            )
        print(f"[OK] 首板涨停: {len(first_board)}只")
    except Exception as e:
        sections.append(f"  获取失败: {e}")
        print(f"[WARN] 首板数据获取失败: {e}")

    return "\n".join(sections)


def find_latest_data():
    """找到 data/ 目录下最新的数据文件"""
    files = glob.glob("data/lianban_data_*.md")
    if not files:
        return None
    files.sort(reverse=True)
    return files[0]


def call_gemini(market_data):
    """调用 Gemini API"""
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        print("❌ 未设置 GEMINI_API_KEY")
        sys.exit(1)

    model_name = os.environ.get("GEMINI_MODEL") or "gemini-2.5-flash"

    print(f"🤖 调用 {model_name} 分析中...")

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=model_name,
        contents=PROMPT.format(market_data=market_data),
        config=types.GenerateContentConfig(
            temperature=0.3,
            max_output_tokens=8000,
        ),
    )
    return response.text


def main():
    print("=" * 50)
    print("🎯 连板打板 AI 分析系统")
    print("=" * 50)

    # 1. 查找数据文件
    data_path = find_latest_data()
    if not data_path:
        print("❌ 未找到数据文件（data/lianban_data_*.md）")
        sys.exit(1)

    print(f"📄 数据文件: {data_path}")

    with open(data_path, "r", encoding="utf-8") as f:
        market_data = f.read()
    print(f"📄 数据长度: {len(market_data)} 字符")

    # 2. AI 分析
    report = call_gemini(market_data)
    print(f"📝 报告长度: {len(report)} 字符")

    # 3. 保存报告
    # 从文件名提取日期，如 lianban_data_20260319.md → 20260319
    date_str = os.path.basename(data_path).replace("lianban_data_", "").replace(".md", "")
    os.makedirs("reports", exist_ok=True)
    report_path = f"reports/lianban_report_{date_str}.md"

    full_report = f"# 🎯 连板打板策略报告 ({date_str})\n\n{report}"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(full_report)

    print(f"💾 报告已保存: {report_path}")
    print("\n" + "=" * 50)
    print(full_report[:500] + "\n... (截取前500字)")


if __name__ == "__main__":
    main()
