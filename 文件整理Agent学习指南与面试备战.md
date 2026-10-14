# 文件整理 Agent —— 学习指南 & 面试备战

> 这份资料专门给「跟着跑完了，但不懂原理」的你写的。
> 配套代码：`项目/file-agent/file_agent.py`（已真实跑通，含一次 bug 修复）。
> 读这份资料时，请**开着 `file_agent.py` 对照行号看**，效果最好。

---

## 一、30 秒全局认知

**这个项目干嘛的？**
你给一句自然语言指令（如「把 inbox 里的图片归到 inbox/图片，文档归到 inbox/文档」），Agent **自己决定**调用哪些工具、按什么顺序，把文件整理好，最后汇报结果。

**它和 RAG 项目（第一个）有什么本质区别？**

| | 第一个项目（RAG 知识库） | 第二个项目（文件整理 Agent） |
|---|---|---|
| 核心能力 | **检索知识、问答** | **调用工具、执行动作** |
| 大模型角色 | 根据资料「说答案」 | 当「调度员」，决定调哪个工具 |
| 有没有真正改动外部世界 | 没有（只读） | **有**（真的移动了你的文件） |
| 关键词 | RAG / Embedding / 向量库 | Agent / Function Calling / 工具闭环 |

一句话：**RAG 让 AI「能回答」，Agent 让 AI「能干活」。** 这俩正是当前 AI 应用工程师的两大基本功。

**最小管线图：**
```
你的指令 ──▶ [大模型] 选工具 ──▶ 调工具(列目录/读文件/移动) ──▶ 看结果
                                  ▲                              │
                                  └──── 把结果回传，再决定下一步 ◀┘
                                  （循环，直到任务完成 ──▶ 汇报）
```

---

## 二、逐环节拆解（对照 file_agent.py 行号）

> 每个环节按：**对应代码 → 它是什么 → 为什么这样设计 → 你要补的知识** 来讲。

### 环节 1：导入与加载密钥（行 17–26）
```python
import os, json, shutil, argparse
from dotenv import load_dotenv()           # 行 26
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage
```
- **是什么**：`shutil` 是 Python 自带的"文件操作"库（移动/复制文件靠它）；`dotenv` 用来从 `.env` 读密钥。
- **为什么**：密钥不能写死在代码里（会泄露、会上传到 GitHub）。`.env` 文件本地保存，`load_dotenv()` 把它读进环境变量。
- **你要补的**：① Python 标准库 `os`/`shutil` 基本用法；②「密钥不入代码」是工程常识。

### 环节 2：工具声明 TOOLS（行 28–72）—— 最关键的一块
```python
TOOLS = [
  {"type":"function","function":{
     "name":"list_dir",
     "description":"列出某个目录下的文件（返回文件名列表）",
     "parameters":{"type":"object","properties":{"path":{"type":"string"}},"required":["path"]}
  }},
  ...  # read_head / move_file 类似
]
```
- **是什么**：这是给大模型看的「岗位说明书」。每个工具写清三件事：
  - `name`：工具叫什么
  - `description`：**这行最重要**——告诉模型「这个工具能干嘛、什么时候该用」。模型就是靠读这行来决定要不要调它。
  - `parameters`：参数长什么样（类型、是否必填）。
- **为什么这样设计**：大模型本身**不能直接操作你的电脑**。我们得把"能力"翻译成它能理解的 JSON 格式告诉它，它才"知道"有这些工具可用。
- **你要补的**：这就是 **Function Calling / Tool Use** 的核心概念——把外部能力用 schema 描述出来交给 LLM。

### 环节 3：工具的真实实现 DISPATCH（行 74–96）
```python
DISPATCH = {
    "list_dir":  lambda path: json.dumps(os.listdir(path), ensure_ascii=False),
    "read_head": lambda path, lines=5: _read_head(path, lines),
    "move_file": lambda src, dst: _move_file(src, dst),
}
def _move_file(src, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)   # 目标目录不存在就自动建
    shutil.move(src, dst)
    return f"已移动: {src} -> {dst}"
```
- **是什么**：工具背后**真正干活的 Python 函数**。`DISPATCH` 是个"名字→函数"的映射表。
- **关键分工**：
  - **大模型只做"决定"**：它返回 `{"name":"move_file","args":{"src":"inbox/photo.png","dst":"inbox/图片"}}`。
  - **真正执行的是本地代码**：我们用 `DISPATCH[name](**args)` 调用对应函数，文件才真的被移动。
- **为什么这样设计**：安全 + 可控。模型永远碰不到你的文件系统，它只能"请求"，由你的代码"执行"。
- **你要补的**：① `lambda` 匿名函数；② `dict` 映射表；③ 异常处理 `try/except`（工具出错时返回错误信息而不是崩溃）。

### 环节 4：初始化大模型并"绑定"工具（行 99–105）
```python
def run(instruction, max_steps=10):
    llm = ChatOpenAI(
        model="deepseek-chat",
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        base_url="https://api.deepseek.com/v1",
        temperature=0,
    ).bind_tools(TOOLS)          # ← 关键：把 TOOLS 挂到模型上
```
- **是什么**：`.bind_tools(TOOLS)` 把前面定义的工具清单"绑"给模型，之后模型就能在回答里输出"我要调某某工具"。
- **`temperature=0`**：让模型输出**最确定、最稳定**，不要随机发挥（整理文件这种事要可预期）。
- **为什么用 `ChatOpenAI` 类访问 DeepSeek**：DeepSeek 的 API 完全兼容 OpenAI 格式，所以借用这套成熟的 SDK 即可，不用另学新库。

### 环节 5：构造消息（行 107–113）
```python
messages = [
    SystemMessage("你是一个文件整理助手。根据指令逐步调用工具完成任务；"
                  "全部完成后用一句话汇报，不要再调用工具。"),
    HumanMessage(instruction),
]
```
- **SystemMessage（系统提示）**：给模型的"总规矩"。这里规定了**两件事**：① 要逐步调工具；② 完成后必须汇报、别再调。
- **为什么要有系统提示**：约束模型行为，防止它偷懒不干活或干完活还瞎调。

### 环节 6：Agent 主循环（行 115–131）—— 整个项目的灵魂
```python
for step in range(max_steps):
    resp = llm.invoke(messages)        # 让模型看当前对话，决定下一步
    if not resp.tool_calls:            # 它不调工具了 = 认为任务完成
        print("Agent:", resp.content)
        return
    messages.append(resp)              # 把模型的"决定"存回对话历史
    for tc in resp.tool_calls:         # 它要调的每个工具都执行一遍
        name = tc["name"]; args = tc["args"]
        result = DISPATCH[name](**args)         # 真实执行
        messages.append(ToolMessage(content=str(result), tool_call_id=tc["id"]))  # 把结果回传
```
这是 **Agent 循环 = 感知 → 决策 → 行动 → 反馈**：
1. **感知/决策**：`llm.invoke(messages)` —— 模型读完历史，决定下一步调什么工具。
2. **行动**：`DISPATCH[name](**args)` —— 代码真正执行工具。
3. **反馈**：把工具结果包成 `ToolMessage` 塞回 `messages`。
4. 下一轮循环，模型带着"刚得到的结果"重新决策，直到它觉得干完了（`not resp.tool_calls`）就 `return` 汇报。

- **为什么必须把工具结果回传（`ToolMessage`）**：模型本身**没有记忆**每次调用的结果，它只能看到你塞进 `messages` 的内容。不把结果回传，模型就"失忆"，会重复调或乱调。
- ⚠️ **真实踩坑（你这个项目里发生过）**：最初代码把 `messages.append(resp)` 写在了内层 `for tc` 循环里。当模型**一次返回多个工具调用**时，`resp` 被重复追加，导致"带 tool_calls 的助手消息后面没跟工具结果"，API 直接报错 `An assistant message with 'tool_calls' must be followed by tool messages`。**修复方法**：把 `messages.append(resp)` 提到循环外、只加一次。这一行就是你简历上"我排查并修复了一个 Agent 循环 bug"的素材。

### 环节 7：收尾与主入口（行 134–138）
```python
parser = argparse.ArgumentParser()
parser.add_argument("instruction", ...)
args = parser.parse_args()
run(args.instruction)
```
- 用 `argparse` 让你能在命令行传一句指令进来，不用改代码。

---

## 三、核心名词速查表

| 名词 | 大白话 |
|------|--------|
| **AI Agent（智能体）** | 能自己"感知→决策→行动→反馈"、完成目标的程序，不用人一步步指挥 |
| **Function Calling / Tool Use（工具调用）** | 大模型输出"我要调某某函数、参数是这些"，由你的代码去执行 |
| **Tool Schema（工具描述）** | 给模型看的"说明书"，写清工具名、能干嘛、参数 |
| **Agent 循环** | 模型决定→执行工具→看结果→再决定……反复直到完成 |
| **bind_tools** | 把工具清单挂到模型上，模型才会输出工具调用 |
| **ToolMessage** | 工具执行完的结果，必须回传给模型形成闭环 |
| **max_steps** | 循环上限（本项目 10），防止模型死循环停不下来 |
| **temperature=0** | 输出最稳定、不随机，适合要可预期结果的任务 |
| **SystemMessage** | 给模型的"总规矩/人设" |

---

## 四、面试会问什么（重点，附口语稿）

### A. HR / 通用类（4 题）

**Q1：你为什么做这个项目？**
> 口语稿：我想往 AI Agent 方向走，但之前没基础。RAG 让我懂了"AI 能回答"，而这个项目让我懂了"AI 能干活"——它自己决定调哪个工具去整理文件。两个项目合起来正好是 Agent 应用的两大基础，所以选了它。

**Q2：做的过程中最大的困难是什么？**
> 口语稿：项目第一次跑的时候报错 `tool_calls must be followed by tool messages`。我定位到是 Agent 循环里"把模型决定回传对话"那行被写进了内层循环，模型一次返回多个工具调用时消息就乱了。我把那行提到外层只加一次，就跑通了。这让我真正理解了 Agent 循环里"消息闭环"的重要性。

**Q3：你从中学到了什么？**
> 口语稿：① 大模型不会自己动电脑，得用 Function Calling 把能力"翻译"成它能懂的格式；② 模型没有记忆，工具结果必须回传它才记得；③ 调外部能力一定要做异常处理和步数上限。

**Q4：这个项目的亮点和不足？**
> 口语稿：亮点是**真能干活**（不是玩具），而且覆盖了标准 Agent 闭环。不足是它只有 3 个工具、命令行交互、没有多轮规划；后续可以加"先列计划再执行"和更多工具。

### B. 技术类（11 题）

**Q1：什么是 AI Agent？和单纯调 LLM 有什么区别？**
> 答：单纯调 LLM 是"一问一答"。Agent 是让 LLM 当"大脑"，通过循环调用工具去**改变外部世界、完成多步任务**。区别在：有没有"行动"和"反馈"的闭环。

**Q2：什么是 Function Calling / Tool Use？为什么需要它？**
> 答：把外部能力（如读文件、查数据库、发消息）用 JSON schema 描述给模型，模型输出"要调哪个函数、参数是什么"，由本地代码执行。需要它的原因：LLM 本身碰不到真实系统，只能"请求"，工具让它能真正做事。

**Q3：工具的 description 有什么用？**
> 答：模型靠读 `description` 来判断"什么时候该用这个工具"。描述写得好不好，直接决定模型选得对不对。这是写 Agent 最容易忽略但最关键的一点。

**Q4：Agent 循环是怎么运作的？**
> 答：四步——① 模型读对话历史，决定调哪个工具；② 代码执行工具；③ 把结果回传成 ToolMessage；④ 带着新结果再决策。重复直到模型不再调工具，就汇报完成。

**Q5：为什么要有 max_steps？不收敛怎么办？**
> 答：防死循环（模型一直调工具停不下来）。不收敛时：检查系统提示是否明确要求"完成后汇报"、减少工具数量、或加"规划"步骤让模型先想清楚再动。

**Q6：ToolMessage 是干嘛的？为什么必须把结果回传？**
> 答：它是工具执行结果的载体。模型本身无状态，只有把结果塞回 messages，它下一轮才"看得到"刚才发生了什么，否则会失忆、重复调或乱调。

**Q7：temperature=0 在这里有什么意义？**
> 答：文件整理要可预期、可复现，不能让模型随机发挥，所以设为 0 取最确定的输出。

**Q8：为什么能用 ChatOpenAI 类访问 DeepSeek？**
> 答：DeepSeek 的 API 兼容 OpenAI 协议，所以直接复用 OpenAI 的 SDK 即可，不用额外学新库。

**Q9：模型是怎么"决定"调哪个工具的？**
> 答：靠我们给的 TOOLS 声明里的 `name` + `description` + `parameters`。模型读这些"说明书"，结合当前对话，推理出该调谁、参数填什么。

**Q10：这个项目有什么局限？怎么改进？**
> 答：局限——工具少、命令行、无多轮规划、无确认机制（会直接移文件）。改进：① 加 `rename_file`/`summarize` 工具；② 先让模型列计划再执行（Plan-and-Execute）；③ 危险操作加"确认"；④ 做成一键整理下载文件夹的小工具。

**Q11：RAG 和 Agent 的区别？什么时候用哪个？**
> 答：RAG 是"检索知识来回答"，Agent 是"调工具来执行动作"。要"基于资料问答"用 RAG；要"让 AI 自动完成操作类任务"（整理文件、发邮件、查数据）用 Agent。两者也常结合：Agent 先调 RAG 工具查资料，再决定怎么干。

---

## 五、可以实测的"真实指标"（简历用，必须真测）

RAG 项目测的是"召回率"，这个 Agent 项目测的是**任务成功率**：

1. 准备 **10–15 条**不同的整理指令（放不同文件、不同规则），例如：
   - 「把图片移到 inbox/图片」
   - 「把 .md 文件移到 inbox/笔记」
   - 「把文件名含 report 的移到 inbox/报告」
2. 对每条指令跑一次，人工核对**文件是否被分到正确目录**。
3. 算分：
   ```
   任务成功率 = 整理正确的条数 ÷ 总条数
   ```
4. 简历诚实写法示例：
   > "基于 12 条自建指令测试，文件整理任务成功率达 92%。"

⚠️ 数字必须来自你真跑的结果，别编。哪怕只有 70% 也是真实能力。

---

## 六、4 周学习路线 & 行动清单

**第 1 周：吃透两个项目**
- [ ] 对照本资料，把 `file_agent.py` **逐行用自己的话讲一遍**（卡住哪行就问我）
- [ ] 背熟上面 11 个技术问答，能张口就答
- [ ] 改 `description` 试一次：故意写错，看模型选工具是不是就乱了（理解它的重要性）

**第 2 周：动手改**
- [ ] 加一个工具 `rename_file`（按内容智能重命名），体会"扩展 Agent 能力"
- [ ] 试 `temperature` 改成 0.7，看输出是不是变随机了
- [ ] 故意触发"多次工具调用"，再确认那个 bug 修复后是否稳定

**第 3 周：测指标 + 写简历**
- [ ] 跑 12 条指令测"任务成功率"，把真实数字填进简历
- [ ] 把两个项目的"进行中"改成"已落地"，附真实指标
- [ ] 在 GitHub 上建仓，把两个项目开源（面试官最爱看）

**第 4 周：进阶（可选，简历加分）**
- [ ] 给 Agent 加"先规划再执行"（Plan-and-Execute）
- [ ] 把 RAG 和 Agent 结合：Agent 先调 RAG 工具查资料，再决定怎么干
- [ ] 做一个有界面（Web/命令行交互）的小工具

---

> **诚实底线（务必记住）**：简历上项目可以讲"已跑通"，但**任何指标数字必须来自你真测的结果**。面试官一追问细节就露馅，造假=面试自杀。你这两个项目是真的跑通的，底气足足的，照实讲就好。
