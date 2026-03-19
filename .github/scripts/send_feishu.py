import os
import json
import time
import requests
import glob


def split_message(text, max_len=4000):
    """按章节智能分割长消息"""
    sections = []
    current = ""

    for line in text.split("\n"):
        if line.startswith("## ") and len(current) > 500:
            sections.append(current.strip())
            current = ""
        current += line + "\n"

        if len(current) >= max_len:
            sections.append(current.strip())
            current = ""

    if current.strip():
        sections.append(current.strip())

    return sections


def send_card(webhook, title, content):
    """发送一张飞书卡片"""
    payload = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": title
                },
                "template": "blue"
            },
            "elements": [
                {
                    "tag": "markdown",
                    "content": content
                }
            ]
        }
    }

    resp = requests.post(
        webhook,
        headers={"Content-Type": "application/json"},
        data=json.dumps(payload)
    )

    success = resp.status_code == 200 and resp.json().get("code") == 0
    return success, resp.text


def send_feishu():
    webhook = os.environ.get("FEISHU_WEBHOOK")
    if not webhook:
        print("❌ 未设置 FEISHU_WEBHOOK")
        return

    # 查找最新的分析报告
    report_files = sorted(glob.glob("reports/*.md"), reverse=True)
    if not report_files:
        send_card(webhook, "⚠️ 提醒", "今日未生成分析报告")
        return

    with open(report_files[0], "r", encoding="utf-8") as f:
        content = f.read()

    print(f"报告总长度: {len(content)} 字符")

    # 短报告直接发
    if len(content) <= 4000:
        ok, resp = send_card(webhook, "📊 每日连板股分析报告", content)
        print("✅ 飞书推送成功" if ok else f"❌ 推送失败: {resp}")
        return

    # 长报告分段发
    parts = split_message(content, max_len=3800)
    total = len(parts)
    print(f"报告过长，分 {total} 段发送")

    for i, part in enumerate(parts):
        title = f"📊 连板分析报告 ({i+1}/{total})"
        ok, resp = send_card(webhook, title, part)

        if ok:
            print(f"✅ 第{i+1}/{total}段发送成功")
        else:
            print(f"❌ 第{i+1}段失败: {resp}")

        if i < total - 1:
            time.sleep(1)

    print("🎉 报告全部发送完毕")


if __name__ == "__main__":
    send_feishu()
