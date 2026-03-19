import os
import json
import requests
import glob

def send_feishu():
    webhook = os.environ.get("FEISHU_WEBHOOK")
    if not webhook:
        print("❌ 未设置 FEISHU_WEBHOOK")
        return

    # 查找最新的分析报告
    report_files = sorted(glob.glob("reports/*.md"), reverse=True)
    if not report_files:
        content = "⚠️ 今日未生成分析报告"
    else:
        with open(report_files[0], "r", encoding="utf-8") as f:
            content = f.read()

    # 飞书消息体（富文本）
    # 如果内容太长，截断到 4000 字符
    if len(content) > 4000:
        content = content[:4000] + "\n\n... (内容过长已截断)"

    payload = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": "📊 每日连板股分析报告"
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

    if resp.status_code == 200 and resp.json().get("code") == 0:
        print("✅ 飞书推送成功")
    else:
        print(f"❌ 飞书推送失败: {resp.text}")

if __name__ == "__main__":
    send_feishu()
