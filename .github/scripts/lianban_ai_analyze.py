import os
import json
import time
import google.generativeai as genai
from datetime import datetime


# ========== AI 提供商定义 ==========

def call_gemini(api_key, prompt):
    """Google Gemini"""
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.0-flash")
    response = model.generate_content(prompt)
    return response.text


def call_deepseek(api_key, prompt):
    """DeepSeek（超便宜，中文好）"""
    from openai import OpenAI
    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=4096
    )
    return response.choices[0].message.content


def call_qwen(api_key, prompt):
    """通义千问（阿里，中文好）"""
    from openai import OpenAI
    client = OpenAI(api_key=api_key, base_url="https://dashscope.aliyuncs.com/compatible-mode/v1")
    response = client.chat.completions.create(
        model="qwen-plus",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=4096
    )
    return response.choices[0].message.content


def call_openai(api_key, prompt):
    """OpenAI"""
    from openai import OpenAI
    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=4096
    )
    return response.choices[0].message.content


# ========== 自动发现可用的 AI ==========

def get_providers():
    providers = []

    # Gemini（支持多个 key 轮换）
    for key_name in ["GEMINI_API_KEY", "GEMINI_API_KEY_2", "GEMINI_API_KEY_3"]:
        api_key = os.environ.get(key_name)
        if api_key:
            providers.append({
                "name": f"Gemini({key_name})",
                "func": call_gemini,
                "api_key": api_key
            })

    # DeepSeek
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if api_key:
        providers.append({
            "name": "DeepSeek",
            "func": call_deepseek,
            "api_key": api_key
        })

    # 通义千问
    api_key = os.environ.get("QWEN_API_KEY")
    if api_key:
        providers.append({
            "name": "通义千问",
            "func": call_qwen,
            "api_key": api_key
        })

    # OpenAI
    api_key = os.environ.get("OPENAI_API_KEY")
    if api_key:
        providers.append({
            "name": "OpenAI",
            "func": call_openai,
            "api_key": api_key
        })

    return providers


def call_ai_with_fallback(prompt):
    """按顺序尝试所有 AI，直到成功"""
    providers = get_providers()

    if not providers:
        print("❌ 未配置任何 AI API Key")
        return None

    print(f"📋 已配置 {len(providers)} 个AI: {', '.join(p['name'] for p in providers)}")

    for i, provider in enumerate(providers):
        print(f"\n🔄 [{i+1}/{len(providers)}] 尝试 {provider['name']}...")
        try:
            result = provider["func"](provider["api_key"], prompt)
            print(f"✅ {provider['name']} 成功!")
            return result
        except Exception as e:
            print(f"⚠️ {provider['name']} 失败: {str(e)[:200]}")
            if i < len(providers) - 1:
                print("⏳ 5秒后尝试下一个...")
                time.sleep(5)

    print("❌ 所有AI提供商均失败")
    return None


# ========== 主逻辑 ==========

def analyze():
    today = datetime.now().strftime("%Y%m%d")
    data_file = f"data/lianban_{today}.json"

    if not os.path.exists(data_file):
        print("❌ 未找到今日数据文件")
        return

    with open(data_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    # ===== 精简数据 =====
    keep_fields = [
        "股票代码", "股票名称", "连板数", "涨停价", "封板资金",
        "换手率", "成交额", "首封时间", "炸板次数", "题材",
        "流通市值", "涨幅"
    ]

    def slim(stock):
        return {k: v for k, v in stock.items() if k in keep_fields}

    lianban = [s for s in data if s.get("连板数", 1) >= 2]
    lianban = [slim(s) for s in lianban]

    shouban = [s for s in data if s.get("连板数", 1) == 1]
    shouban.sort(key=lambda x: float(str(x.get("封板资金", "0")).replace("亿", "") or 0), reverse=True)
    shouban = [slim(s) for s in shouban[:10]]

    slim_data = {
        "连板股": lianban,
        "首板TOP10": shouban,
        "总涨停数": len(data),
        "总连板数": len(lianban),
        "总首板数": len(data) - len(lianban)
    }

    print(f"📊 数据精简: 连板{len(lianban)}只, 首板取前10(共{len(data)-len(lianban)}只)")

    prompt = f"""你是一位专业的A股短线打板交易员，请根据以下数据生成【连板打板策略报告】。

## 数据
{json.dumps(slim_data, ensure_ascii=False, indent=2)}

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

### 【题材名称】⭐⭐⭐（1-5星持续性评级）
- **驱动逻辑：** xxx
- **持续性判断：** xxx
- **梯队结构：** 龙头→二梯队→跟风
- **明日关注：** xxx

---

## 三、👑 龙头股分析

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
1. 数据中 "连板数" 字段就是实际连板天数，直接使用
2. 用 emoji 和加粗让关键信息一目了然
3. 每只股票的策略必须具体可执行
"""

    report = call_ai_with_fallback(prompt)
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
