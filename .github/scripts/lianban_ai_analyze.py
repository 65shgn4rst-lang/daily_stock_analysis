import os
import json
import glob
import google.generativeai as genai
from datetime import datetime

import time

def call_gemini_with_retry(model, prompt, max_retries=3):
    for i in range(max_retries):
        try:
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            error_msg = str(e)
            print(f"⚠️ 第{i+1}次请求失败: {error_msg}")
            if "429" in error_msg or "quota" in error_msg.lower() or "resource" in error_msg.lower():
                wait = 15 * (i + 1)
                print(f"⏳ 等待{wait}秒后重试...")
                time.sleep(wait)
            else:
                raise e
    print("❌ 重试耗尽，尝试缩减内容后再请求")
    return None

def analyze():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("❌ 未设置 GEMINI_API_KEY")
        return

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.0-flash")

    today = datetime.now().strftime("%Y%m%d")
    data_file = f"data/lianban_{today}.json"

    if not os.path.exists(data_file):
        print("❌ 未找到今日数据文件")
        return

    with open(data_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    prompt = f"""你是一位专业的A股短线打板交易员，请根据以下数据生成【连板打板策略报告】。

## 数据
{json.dumps(data, ensure_ascii=False, indent=2)}

## 报告格式要求（严格遵守）

请用以下格式输出，注意用 emoji 和加粗突出重点：

---

# 🎯 连板打板策略报告 ({today})

## 一、📊 情绪周期定位

**🔴 当前阶段：** [退潮期/冰点期/修复期/升温期/高潮期]

**核心数据看板：**
| 指标 | 数值 | 评价 |
|---|---|---|
| 涨停数量 | xx | 🟢高/🟡中/🔴低 |
| 炸板率 | xx% | 🟢低/🟡中/🔴高 |
| 昨日晋级率 | xx% | 🟢高/🟡中/🔴低 |
| 最高连板 | x板 | - |
| 昨涨停今日均涨 | xx% | 🟢正/🔴负 |

**与昨日对比：** 转暖/转冷/持平，一句话说明
**明日情绪预判：** 一句话

---

## 二、🔥 主线题材研判

对每个主线题材，用以下格式：

### 【题材名称】⭐⭐⭐（1-5星持续性评级）
- **驱动逻辑：** xxx
- **持续性判断：** xxx
- **梯队结构：** 龙头→二梯队→跟风
- **明日关注：** xxx

---

## 三、👑 龙头股分析

对每只连板股（从最高板到2板），用以下格式：

### 🏆 [N板] 股票名称(代码) | 题材
> **一句话定位：** xxx

| 维度 | 详情 |
|---|---|
| 封板资金 | xx亿 |
| 换手率 | xx% |
| 成交额 | xx亿 |
| 首封时间 | xx |
| 炸板次数 | x次 |
| 封板质量 | 🟢优/🟡中/🔴差 |

**辨识度：** ⭐⭐⭐⭐ xxx
**明日策略：**
- 🟢 **打板/追涨条件：** xxx
- 🔴 **放弃条件：** xxx
- 📍 **关键价位：** xxx

---

## 四、💡 首板重点关注

从首板中选出最值得关注的3-5只，简要说明：
| 股票 | 题材 | 封板资金 | 亮点 | 明日关注 |
|---|---|---|---|---|

---

## 五、⚡ 明日操作计划

### 最优策略方向
- **首选：** xxx
- **备选：** xxx
- **回避：** xxx

### 仓位建议
根据情绪周期给出建议仓位比例

---

## 重要要求：
1. 必须正确识别每只股票的连板天数，不能搞错
2. 数据中 "连板数" 字段就是实际连板天数，直接使用
3. 用 emoji 和加粗让关键信息一目了然
4. 首板分析必须包含，选封板资金最大、题材最正的
5. 每只股票的策略必须具体可执行，不要空话
"""

    report = call_gemini_with_retry(model, prompt)
    if not report:
        print("❌ AI生成失败")
        return

    os.makedirs("reports", exist_ok=True)
    report_path = f"reports/report_{today}.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"✅ 报告已生成: {report_path}")


if __name__ == "__main__":
    analyze()
