import os
import json
import requests
import glob

def send_feishu():
    webhook = os.environ.get("FEISHU_WEBHOOK")
    if not webhook:
        print("❌ 未设置 FEISHU_WEBHOOK")
        return

    report_files = sorted(glob.glob("reports/*.md"), reverse=True)
    if not report_files:
        send_text(webhook, "⚠️ 今日未生成分析报告")
        return

    with open(report_files[0], "r", encoding="utf-8") as f:
        content = f.read()

    # 飞书卡片 markdown 限制约4000字符，超长则分段发送
    if len(content) <= 4000:
        send_card(webhook, content)
    else:
        chunks = split_content(content, 3800)
        for i, chunk in enumerate(chunks):
            title = f"📊 每日连板分析报告 ({i+1}/{len(chunks)})"
            send_card(webhook, chunk, title)

    print("✅ 飞书推送完成")


def split_content(text, max_len):
    """按章节分割"""
    sections = text.split("\n## ")
    chunks = []
    current = ""
    for sec in sections:
        piece = ("## " + sec) if chunks or current else sec
        if len(current) + len(piece) > max_len:
            if current:
                chunks.append(current)
            current = piece
        else:
            current += "\n" + piece
    if current:
        chunks.append(current)
    return chunks


def send_card(webhook, content, title="📊 每日连板股分析报告"):
    payload = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": title},
                "template": "blue"
            },
            "elements": [
                {"tag": "markdown", "content": content}
            ]
        }
    }
    resp = requests.post(webhook, headers={"Content-Type": "application/json"}, data=json.dumps(payload))
    if resp.status_code == 200 and resp.json().get("code") == 0:
        print(f"✅ 发送成功: {title}")
    else:
        print(f"❌ 发送失败: {resp.text}")


def send_text(webhook, text):
    payload = {"msg_type": "text", "content": {"text": text}}
    requests.post(webhook, headers={"Content-Type": "application/json"}, data=json.dumps(payload))


if __name__ == "__main__":
    send_feishu()
