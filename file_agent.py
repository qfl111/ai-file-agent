"""
智能文件整理 Agent —— 最小可跑版本（展示 Function Calling / 工具调用闭环）
==========================================================================
能干嘛：你给一句自然语言指令，Agent 自己决定调用哪些工具去完成文件整理。
        例如：「把 ./inbox 里图片移到 inbox/图片，文档移到 inbox/文档/」

这就是一个最朴素的 AI Agent：
    感知（list_dir / read_head）→ 决策（大模型选工具）→ 行动（move_file）→ 反馈（看结果再决定下一步）

跑起来（4 步）：
  1) pip install -r requirements.txt
  2) 复制 .env.example 为 .env，填入 DEEPSEEK_API_KEY
  3) 在 ./inbox 放一些混合文件（图片/文档/txt 等）
  4) python file_agent.py "把 inbox 里的图片归到 inbox/图片，文档归到 inbox/文档"
"""

import os
import json
import shutil
import argparse

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage

load_dotenv()

# 把工具「声明」给大模型：名字、干什么、参数长什么样
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": "列出某个目录下的文件（返回文件名列表）",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string", "description": "目录路径，如 ./inbox"}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_head",
            "description": "读取文本文件的前几行，用来判断文件内容/类型",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "lines": {"type": "integer", "default": 5},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "move_file",
            "description": "把文件从 src 移动到 dst（目标目录不存在会自动创建）",
            "parameters": {
                "type": "object",
                "properties": {
                    "src": {"type": "string"},
                    "dst": {"type": "string"},
                },
                "required": ["src", "dst"],
            },
        },
    },
]

# 工具的真实实现：大模型只「决定」调哪个，真正干活的是这些函数
DISPATCH = {
    "list_dir": lambda path: json.dumps(os.listdir(path), ensure_ascii=False),
    "read_head": lambda path, lines=5: _read_head(path, lines),
    "move_file": lambda src, dst: _move_file(src, dst),
}


def _read_head(path, lines=5):
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            return "".join([next(f) for _ in range(lines)])
    except Exception as e:
        return f"错误: {e}"


def _move_file(src, dst):
    try:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.move(src, dst)
        return f"已移动: {src} -> {dst}"
    except Exception as e:
        return f"错误: {e}"


def run(instruction: str, max_steps: int = 10):
    llm = ChatOpenAI(
        model="deepseek-chat",
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        base_url="https://api.deepseek.com/v1",
        temperature=0,
    ).bind_tools(TOOLS)

    messages = [
        SystemMessage(
            "你是一个文件整理助手。根据用户的自然语言指令，逐步调用工具完成任务；"
            "全部完成后，用一句话向用户汇报结果，不要再调用工具。"
        ),
        HumanMessage(instruction),
    ]

    for step in range(max_steps):
        resp = llm.invoke(messages)
        if not resp.tool_calls:
            # 没有工具调用 = 已经给出最终答复
            print("Agent:", resp.content)
            return
        # 把「模型的决定」整体回传一次，再附上每个工具的返回结果，形成闭环
        messages.append(resp)
        for tc in resp.tool_calls:
            name = tc["name"]
            args = tc["args"]
            print(f"[第{step+1}步] 调用工具 {name}({args})")
            result = DISPATCH[name](**args)
            print(f"        结果: {result}")
            messages.append(ToolMessage(content=str(result), tool_call_id=tc["id"]))

    print("⚠️ 已到达最大步数，任务可能未完成。")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="智能文件整理 Agent")
    parser.add_argument("instruction", help="自然语言整理指令，如『把 inbox 里的图片归到 inbox/图片』")
    args = parser.parse_args()
    run(args.instruction)
