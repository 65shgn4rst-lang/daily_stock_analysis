#!/usr/bin/env python3
"""连板打板 AI 分析 —— 读取数据 → 调用 Gemini → 保存报告"""

import os
import sys
import glob
import datetime

from google import genai
from google.genai import types

# ===== 分析提示词 =====
PROMPT = """你是一位专业的A股短线连板打板交易员，精通情绪周期理论和龙头战法。

请根据以下今日市场数据，生成一份**连板打板策略报告**。

---
{market_data}
---

## 分析要求（严格按以下框架输出）：

### 一、情绪周期定位
- 当前处于情绪周期的哪个阶段？（冰点→修复→上升→加速→高潮→分歧→退潮）
- 判断依据：涨停数量、炸板率、晋级率、连板高度、涨跌停比
- 与昨日对比情绪是转暖还是转冷？
- 明日情绪预判

### 二、主线题材研判
- 今日最强主线题材是什么？（1-3个）
- 每个主线的驱动逻辑是什么？（政策/事件/资金）
- 题材的持续性判断（一日游还是中期主线？）
- 题材内部的梯队结构（龙头→二梯队→跟风）

### 三、龙头股分析（最重要！）
对连板梯队中**每一只2板及以上**的股票，逐一分析：
- **身份定位**：是题材龙头？空间龙头？补涨龙？跟风？
- **封板质量**：封单额大小、换手率高低、炸板次数、封板时间
- **辨识度**：市场是否认可其龙头地位？有无竞争对手？
- **明日策略**：竞价预判、操作条件、放弃条件、价位参考

### 四、首板股精选
从今日首板股中选出**最值得关注的3-5只**：
- 选股标准：题材正确、封板资金大、换手率适中、封板时间早
- 说明每只的看点和风险

### 五、风险提示
- 哪些连板股明日有断板风险？为什么？
- 哪些板块可能退潮？
- 需要回避的方向

### 六、明日操盘计划
- 竞价阶段重点观察什么？
- 开盘后的操作优先级
- 仓位建议（根据情绪周期）
- 止损纪律

## 输出格式要求：
- 使用 Markdown 格式
- 观点明确，不要模棱两可
- 每只股票给出**具体操作建议和价位**
- 语言简洁专业，像给职业短线交易员的每日复盘
"""


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

    model_name = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

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
