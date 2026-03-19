#!/usr/bin/env python3
"""连板打板 AI 分析（含大盘数据）"""

import os
import sys
import json
import datetime
import google.generativeai as genai

# ========== 新增：akshare 采集大盘 ==========
try:
    import akshare as ak
except ImportError:
    print("⚠️ akshare 未安装，尝试安装...")
    os.system(f"{sys.executable} -m pip install akshare")
    import akshare as ak


LIANBAN_PROMPT = """你是一位专业的A股短线连板打板交易员，精通情绪周期理论和龙头战法。

请根据以下今日市场数据，生成一份**连板打板策略报告**。

---
## 大盘环境数据
{market_overview}
---

## 今日连板股数据
{lianban_data}
---

## 分析要求（严格按以下框架输出）：

### 一、大盘环境评估（新增！）
- 大盘指数表现如何？量能与昨日对比？
- 涨跌比和涨停数反映的市场情绪
- 北向资金流向释放什么信号？
- 当前大盘环境是否适合打板操作？（明确给出：激进/正常/保守/空仓）

### 二、情绪周期定位
- 当前处于情绪周期的哪个阶段？（冰点→修复→上升→加速→高潮→分歧→退潮）
- 判断依据：涨停数量、炸板率、晋级率、连板高度、涨跌停比
- 与昨日对比情绪是转暖还是转冷？
- 明日情绪预判

### 三、主线题材研判
- 今日最强主线题材是什么？（1-3个）
- 每个主线的驱动逻辑是什么？（政策/事件/资金）
- 题材的持续性判断（一日游还是中期主线？）
- 题材内部的梯队结构（龙头→二梯队→跟风）

### 四、龙头股分析（最重要！）
对连板梯队中**每一只2板及以上**的股票，逐一分析：
- **身份定位**：是题材龙头？空间龙头？补涨龙？跟风？
- **封板质量**：封单额大小、换手率高低、炸板次数、封板时间
- **辨识度**：市场是否认可其龙头地位？有无竞争对手？
- **明日策略**：
  - 竞价预判（高开/平开/低开的概率）
  - 什么情况下可以打板/追涨/低吸
  - 什么情况下必须放弃
  - 具体价位参考（强弱分界线）

### 五、首板股精选
从今日首板股中选出**最值得关注的3-5只**：
- 选股标准：题材正确、封板资金大、换手率适中、封板时间早
- 说明每只的看点和风险

### 六、风险提示
- 结合大盘环境，哪些连板股明日有断板风险？
- 哪些板块可能退潮？
- 需要回避的方向

### 七、明日操盘计划
- 竞价阶段重点观察什么？
- 开盘后的操作优先级
- **仓位建议**（结合大盘环境和情绪周期综合给出）
- 止损纪律

## 输出格式要求：
- 使用 Markdown 格式
- 观点明确，不要模棱两可
- 每只股票给出**具体操作建议和价位**
- 语言简洁专业，像给职业短线交易员的每日复盘
"""


# ========== 新增：大盘数据采集 ==========
def get_market_overview():
    """获取大盘整体数据"""
    result = {}

    # ----- 主要指数 -----
    indices = {
        "上证指数": "sh000001",
        "深证成指": "sz399001",
        "创业板指": "sz399006",
        "科创50": "sh000688",
    }

    index_summary = []
    for name, symbol in indices.items():
        try:
            df = ak.stock_zh_index_daily(symbol=symbol)
            if df is None or df.empty:
                continue
            latest = df.iloc[-1]
            prev = df.iloc[-2]
            close = float(latest["close"])
            prev_close = float(prev["close"])
            change_pct = round((close - prev_close) / prev_close * 100, 2)
            volume = round(float(latest["volume"]) / 1e8, 2)

            index_summary.append({
                "名称": name,
                "收盘价": close,
                "涨跌幅": change_pct,
                "成交量(亿手)": volume
            })
        except Exception as e:
            print(f"  ⚠️ 获取{name}失败: {e}")

    result["指数行情"] = index_summary

    # ----- 涨跌家数统计 -----
    try:
        df_all = ak.stock_zh_a_spot_em()
        if df_all is not None and not df_all.empty:
            total = len(df_all)
            up_count = len(df_all[df_all["涨跌幅"] > 0])
            down_count = len(df_all[df_all["涨跌幅"] < 0])
            flat_count = len(df_all[df_all["涨跌幅"] == 0])
            limit_up = len(df_all[df_all["涨跌幅"] >= 9.5])
            limit_down = len(df_all[df_all["涨跌幅"] <= -9.5])
            total_amount = round(df_all["成交额"].sum() / 1e8, 2)
            avg_change = round(df_all["涨跌幅"].mean(), 2)

            result["市场概况"] = {
                "总股票数": total,
                "上涨家数": up_count,
                "下跌家数": down_count,
                "平盘家数": flat_count,
                "涨停家数": limit_up,
                "跌停家数": limit_down,
                "涨跌比": f"{up_count}:{down_count}",
                "全市场成交额(亿)": total_amount,
                "个股平均涨幅": avg_change,
            }
    except Exception as e:
        print(f"  ⚠️ 获取涨跌统计失败: {e}")

    # ----- 北向资金 -----
    try:
        df_north = ak.stock_hsgt_north_net_flow_in_em(symbol="北向")
        if df_north is not None and not df_north.empty:
            latest_north = df_north.iloc[-1]
            net_flow = round(float(latest_north["当日净流入"]) / 1e4, 2)
            result["北向资金"] = {"净流入(亿)": net_flow}
    except Exception as e:
        print(f"  ⚠️ 获取北向资金失败: {e}")

    return result


def format_market_overview(data):
    """将大盘数据格式化为文本"""
    lines = []

    # 指数行情
    if data.get("指数行情"):
        lines.append("### 主要指数")
        for idx in data["指数行情"]:
            emoji = "🟢" if idx["涨跌幅"] >= 0 else "🔴"
            lines.append(
                f"- {emoji} **{idx['名称']}**: "
                f"{idx['收盘价']}  ({idx['涨跌幅']:+.2f}%)  "
                f"成交量 {idx['成交量(亿手)']}亿手"
            )
        lines.append("")

    # 市场概况
    if data.get("市场概况"):
        m = data["市场概况"]
        lines.append("### 市场情绪面板")
        lines.append(f"- 涨跌比: **{m['涨跌比']}**")
        lines.append(f"- 涨停家数: **{m['涨停家数']}** / 跌停家数: **{m['跌停家数']}**")
        lines.append(f"- 全市场成交额: **{m['全市场成交额(亿)']}亿**")
        lines.append(f"- 个股平均涨幅: **{m['个股平均涨幅']:+.2f}%**")
        lines.append("")

    # 北向资金
    if data.get("北向资金"):
        n = data["北向资金"]["净流入(亿)"]
        emoji = "🟢" if n > 0 else "🔴"
        lines.append("### 北向资金")
        lines.append(f"- {emoji} 今日净流入: **{n:+.2f}亿**")
        lines.append("")

    if not lines:
        return "⚠️ 大盘数据获取失败，请结合经验判断市场环境。"

    return "\n".join(lines)


# ========== 原有函数（保持不变）==========
def load_market_data():
    """加载连板数据"""
    data_path = os.environ.get('LIANBAN_DATA_PATH', '')

    if not data_path:
        data_dir = 'data'
        if os.path.exists(data_dir):
            files = [f for f in os.listdir(data_dir)
                     if f.startswith('lianban_data_') and f.endswith('.md')]
            if files:
                files.sort(reverse=True)
                data_path = os.path.join(data_dir, files[0])

    if not data_path or not os.path.exists(data_path):
        print("❌ 未找到连板数据文件")
        sys.exit(1)

    with open(data_path, 'r', encoding='utf-8') as f:
        return f.read()


def analyze_with_gemini(market_overview, lianban_data):
    """使用 Gemini 分析（修改：接收两份数据）"""
    api_key = os.environ.get('GEMINI_API_KEY', '')
    if not api_key:
        print("❌ 未设置 GEMINI_API_KEY")
        sys.exit(1)

    model_name = os.environ.get('GEMINI_MODEL', 'gemini-2.5-flash')

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name)

    prompt = LIANBAN_PROMPT.format(
        market_overview=market_overview,
        lianban_data=lianban_data
    )

    print(f"🤖 使用 {model_name} 分析中...")
    print(f"📊 Prompt 总长度: {len(prompt)} 字符")

    response = model.generate_content(
        prompt,
        generation_config=genai.types.GenerationConfig(
            temperature=0.3,
            max_output_tokens=8000,
        )
    )

    return response.text


def send_wechat(content):
    """发送企业微信通知"""
    import requests
    webhook_url = os.environ.get('WECHAT_WEBHOOK_URL', '')
    if not webhook_url:
        return

    if len(content.encode('utf-8')) > 4000:
        parts = split_content(content, 3800)
        for i, part in enumerate(parts):
            payload = {"msgtype": "markdown", "markdown": {"content": part}}
            try:
                requests.post(webhook_url, json=payload, timeout=10)
                print(f"✅ 企业微信第 {i+1} 段发送成功")
            except Exception as e:
                print(f"❌ 企业微信发送失败: {e}")
    else:
        payload = {"msgtype": "markdown", "markdown": {"content": content}}
        try:
            requests.post(webhook_url, json=payload, timeout=10)
            print("✅ 企业微信发送成功")
        except Exception as e:
            print(f"❌ 企业微信发送失败: {e}")


def send_telegram(content):
    """发送 Telegram 通知"""
    import requests
    bot_token = os.environ.get('TELEGRAM_BOT_TOKEN', '')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID', '')
    if not bot_token or not chat_id:
        return

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    parts = split_content(content, 4000)
    for i, part in enumerate(parts):
        payload = {"chat_id": chat_id, "text": part, "parse_mode": "Markdown"}
        thread_id = os.environ.get('TELEGRAM_MESSAGE_THREAD_ID', '')
        if thread_id:
            payload["message_thread_id"] = int(thread_id)
        try:
            requests.post(url, json=payload, timeout=10)
            print(f"✅ Telegram 第 {i+1} 段发送成功")
        except Exception as e:
            print(f"❌ Telegram 发送失败: {e}")


def split_content(content, max_bytes):
    """按字节长度分割内容"""
    parts = []
    lines = content.split('\n')
    current = []
    current_len = 0

    for line in lines:
        line_len = len(line.encode('utf-8')) + 1
        if current_len + line_len > max_bytes and current:
            parts.append('\n'.join(current))
            current = [line]
            current_len = line_len
        else:
            current.append(line)
            current_len += line_len

    if current:
        parts.append('\n'.join(current))

    return parts


# ========== 主函数（修改）==========
def main():
    print("=" * 50)
    print("🎯 连板打板 AI 分析系统")
    print("=" * 50)

    # ===== 1. 新增：采集大盘数据 =====
    print("\n📈 获取大盘数据...")
    try:
        market_raw = get_market_overview()
        market_overview = format_market_overview(market_raw)
        print(market_overview)
    except Exception as e:
        print(f"⚠️ 大盘数据获取异常: {e}")
        market_overview = "⚠️ 大盘数据获取失败，请结合经验判断。"

    # ===== 2. 加载连板数据 =====
    print("\n🔍 加载连板数据...")
    lianban_data = load_market_data()
    print(f"📄 连板数据加载完成，长度: {len(lianban_data)} 字符")

    # ===== 3. AI 分析（传入两份数据）=====
    report = analyze_with_gemini(market_overview, lianban_data)
    print(f"📝 分析报告生成完成，长度: {len(report)} 字符")

    # ===== 4. 拼接完整报告（大盘数据 + AI分析）=====
    os.makedirs('reports', exist_ok=True)
    date_str = os.environ.get(
        'TRADE_DATE',
        datetime.datetime.now().strftime('%Y%m%d')
    )

    full_report = (
        f"# 🎯 连板打板策略报告 ({date_str})\n\n"
        f"## 📈 大盘概况\n\n"
        f"{market_overview}\n\n"
        f"---\n\n"
        f"{report}"
    )

    report_path = f'reports/lianban_report_{date_str}.md'
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(full_report)
    print(f"💾 报告已保存: {report_path}")

    # ===== 5. 发送通知 =====
    send_wechat(full_report)
    send_telegram(full_report)

    print("\n" + "=" * 50)
    print(full_report)


if __name__ == '__main__':
    main()
