#!/usr/bin/env python3
"""连板打板 AI 分析"""

import os
import sys
import json
import datetime
import google.generativeai as genai

LIANBAN_PROMPT = """你是一位专业的A股短线连板打板交易员，精通情绪周期理论和龙头战法。

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
- **明日策略**：
  - 竞价预判（高开/平开/低开的概率）
  - 什么情况下可以打板/追涨/低吸
  - 什么情况下必须放弃
  - 具体价位参考（强弱分界线）

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

def load_market_data():
    """加载连板数据"""
    data_path = os.environ.get('LIANBAN_DATA_PATH', '')
    
    if not data_path:
        # 查找最新的数据文件
        data_dir = 'data'
        if os.path.exists(data_dir):
            files = [f for f in os.listdir(data_dir) if f.startswith('lianban_data_') and f.endswith('.md')]
            if files:
                files.sort(reverse=True)
                data_path = os.path.join(data_dir, files[0])
    
    if not data_path or not os.path.exists(data_path):
        print("❌ 未找到连板数据文件")
        sys.exit(1)
    
    with open(data_path, 'r', encoding='utf-8') as f:
        return f.read()

def analyze_with_gemini(market_data):
    """使用 Gemini 分析"""
    api_key = os.environ.get('GEMINI_API_KEY', '')
    if not api_key:
        print("❌ 未设置 GEMINI_API_KEY")
        sys.exit(1)
    
    model_name = os.environ.get('GEMINI_MODEL', 'gemini-2.5-flash')
    
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name)
    
    prompt = LIANBAN_PROMPT.format(market_data=market_data)
    
    print(f"🤖 使用 {model_name} 分析中...")
    
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
    
    # 企业微信 Markdown 限制 4096 字节
    if len(content.encode('utf-8')) > 4000:
        # 分段发送
        parts = split_content(content, 3800)
        for i, part in enumerate(parts):
            payload = {
                "msgtype": "markdown",
                "markdown": {"content": part}
            }
            try:
                requests.post(webhook_url, json=payload, timeout=10)
                print(f"✅ 企业微信第 {i+1} 段发送成功")
            except Exception as e:
                print(f"❌ 企业微信发送失败: {e}")
    else:
        payload = {
            "msgtype": "markdown",
            "markdown": {"content": content}
        }
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
    
    # Telegram 限制 4096 字符，分段发送
    parts = split_content(content, 4000)
    for i, part in enumerate(parts):
        payload = {
            "chat_id": chat_id,
            "text": part,
            "parse_mode": "Markdown",
        }
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

def main():
    print("=" * 50)
    print("🎯 连板打板 AI 分析系统")
    print("=" * 50)
    
    # 加载数据
    market_data = load_market_data()
    print(f"📄 数据加载完成，长度: {len(market_data)} 字符")
    
    # AI 分析
    report = analyze_with_gemini(market_data)
    print(f"📝 分析报告生成完成，长度: {len(report)} 字符")
    
    # 保存报告
    os.makedirs('reports', exist_ok=True)
    date_str = os.environ.get('TRADE_DATE', datetime.datetime.now().strftime('%Y%m%d'))
    report_path = f'reports/lianban_report_{date_str}.md'
    
    full_report = f"# 🎯 连板打板策略报告 ({date_str})\n\n{report}"
    
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(full_report)
    print(f"💾 报告已保存: {report_path}")
    
    # 发送通知
    send_wechat(full_report)
    send_telegram(full_report)
    
    # 输出到控制台
    print("\n" + "=" * 50)
    print(full_report)

if __name__ == '__main__':
    main()
