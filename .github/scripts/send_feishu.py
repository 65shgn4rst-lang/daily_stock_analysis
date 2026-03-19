#!/usr/bin/env python3
"""推送分析报告到飞书 Webhook"""

import os
import sys
import glob
import requests


def find_latest_report():
    """查找最新报告"""
    files = glob.glob("reports/lianban_report_*.md")
    if not files:
        return None
    files.sort(reverse=True)
    return files[0]


def split_text(text, max_len=3800):
    """按行拆分长文本，每段不超过 max_len 字节"""
    parts = []
    current = []
    current_len = 0

    for line in text.split("\n"):
        line_bytes = len(line.encode("utf-8")) + 1
        if current_len + line_bytes > max_len and current:
            parts.append("\n".join(current))
            current = [line]
            current_len = line_bytes
        else:
            current.append(line)
            current_len += line_bytes

    if current:
        parts.append("\n".join(current))
    return parts


def send_feishu(webhook_url, content):
    """发送到飞书，自动拆分长消息"""
    parts = split_text(content)
    total = len(parts)

    for i, part in enumerate(parts):
        title = "连板打板策略报告" + (f"（第{i+1}/{total}段）" if total > 1 else "")
        payload = {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {"tag": "plain_text", "content": title},
                    "template": "red",
                },
                "elements": [
                    {
                        "tag": "div",
                        "text": {"tag": "lark_md", "content": part},
                    }
                ],
            },
        }

        try:
            resp = requests.post(webhook_url, json=payload, timeout=15)
            result = resp.json()
            if result.get("code") == 0:
                print(f"  ✅ 第 {i+1}/{total} 段发送成功")
            else:
                print(f"  ❌ 飞书返回错误: {result}")
        except Exception as e:
            print(f"  ❌ 发送失败: {e}")


def main():
    webhook_url = os.environ.get("FEISHU_WEBHOOK", "")
    if not webhook_url:
        print("⚠️ 未设置 FEISHU_WEBHOOK，跳过推送")
        return

    report_path = find_latest_report()
    if not report_path:
        print("⚠️ 未找到报告文件，跳过推送")
        return

    with open(report_path, "r", encoding="utf-8") as f:
        content = f.read()

    print(f"📤 推送: {report_path} ({len(content)} 字符)")
    send_feishu(webhook_url, content)


if __name__ == "__main__":
    main()
