# 智能文件整理 Agent

> 给一句自然语言指令，Agent 自己决定怎么整理文件。这是理解 **AI Agent 工具调用闭环（Function Calling）** 的最小可用样板。

例如执行 `python file_agent.py "把 inbox 里的图片归到 inbox/图片，文档归到 inbox/文档"`，Agent 会自动完成「列目录 → 读文件判断类型 → 移动到对应文件夹 → 汇报结果」的全过程，无需写死任何规则。

## 功能特性

- **自然语言驱动**：用一句话描述整理目标，无需正则规则或硬编码分类逻辑
- **工具调用闭环**：`list_dir`（列目录）/ `read_head`（读文件头判断类型）/ `move_file`（移动归档）三个工具由大模型自主选择和组合
- **Agent 循环**：感知 → 决策（选工具、传参数）→ 行动 → 反馈（根据结果继续），最多 10 步自动收敛
- **真实可用**：可改成整理自己的「下载」文件夹，是能每天省时间的效率小工具，不是玩具

## 技术栈

| 层 | 技术 |
|----|------|
| Agent 编排 | Python、DeepSeek Function Calling（OpenAI 兼容接口） |
| 工具定义 | JSON Schema（name + description + parameters） |
| 循环控制 | 自定义 Agent Loop（最大步数保护、ToolMessage 回传闭环） |
| 文件操作 | Python 标准库（pathlib / shutil） |

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置密钥：复制 .env.example 为 .env，填入 DEEPSEEK_API_KEY
cp .env.example .env

# 3. 准备一些待整理文件，放进 ./inbox（图片 / 文档 / txt 混着放）

# 4. 用自然语言下指令
python file_agent.py "把 inbox 里的图片归到 inbox/图片，文档归到 inbox/文档"
```

**运行示例：**

```
[第1步] 调用工具 list_dir({'path': 'inbox'})
        结果: ['photo.png', 'avatar.jpg', 'notes.txt', ...]
[第2步] 调用工具 read_head({'path': 'inbox/notes.txt'})
        结果: 这是一份学习笔记。主题是 AI Agent 的工具调用。
[第3步] 调用工具 move_file({'src': 'inbox/photo.png', 'dst': 'inbox/图片'})
        结果: 已移动
...
Agent: 已完成整理：photo.png、avatar.jpg 移入 inbox/图片，notes.txt 等移入 inbox/文档。
```

## 目录结构

```
file-agent/
├── file_agent.py          # Agent 主循环 + 3 个工具定义与实现
├── inbox/                 # 放待整理文件（演示数据）
├── requirements.txt
├── .env.example           # 密钥模板（复制为 .env 后填入真实 Key）
└── 文件整理Agent学习指南与面试备战.md  # 原理拆解 + 面试问答
```

## 评测指标（真实测出后填入）

- 建议测试方法：设计 12 条不同整理指令（按类型 / 按日期 / 按内容），逐条核对归档结果
- 计算公式：`任务成功率 = 整理正确的文件数 ÷ 总文件数`
- 实测结果：`待填写`（禁止编造）

## 已知边界与改进方向

- 工具集较小（仅 3 个），可扩展 `rename_file`（按内容重命名）、`summarize`（生成摘要）等
- 未做「先规划后执行」（Plan-and-Execute）模式，长任务稳定性有限
- 未做危险操作二次确认（如删除、覆盖），生产环境需加护栏

## 相关文档

- [文件整理Agent学习指南与面试备战.md](./文件整理Agent学习指南与面试备战.md) —— 对应代码行号的原理拆解 + 15 道面试题口语稿

> 安全提示：`.env` 含真实 API Key，已在 `.gitignore` 中排除，请勿提交。
