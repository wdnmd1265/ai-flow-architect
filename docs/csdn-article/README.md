# CSDN 文章发布指南

## 文件清单

| 文件 | 用途 | 插入位置 |
|------|------|----------|
| `cover.png` | 封面/头图 | 文章最顶部（CSDN 编辑器里上传为"封面图"） |
| `architecture.svg` | 双脑对抗架构流程图 | "解法：让两个 AI 互相打架" 段落之后 |
| `opponent-brain.svg` | 对手脑 5 视角图 | "核心设计拆解" → "1. 对手脑" 段落之后 |
| `comparison.svg` | 框架对比图 | "与 LangChain / CrewAI 的本质区别" 段落之后 |
| `ai-flow-architect-csdn.md` | 文章正文 | 复制到 CSDN Markdown 编辑器 |

## 发布步骤

### 1. 图片转 PNG（CSDN 对 SVG 支持不稳定）

SVG 文件需要转成 PNG 再上传。最简单的方法：

- 用浏览器打开 SVG 文件（双击即可用浏览器打开）
- 截图保存为 PNG
- 或者使用在线工具如 https://cloudconvert.com/svg-to-png

### 2. 在 CSDN 编辑器中操作

1. 打开 CSDN 创作中心 → 写文章
2. 选择 **Markdown 编辑器**
3. 上传封面图：`cover.png` 作为文章封面
4. 复制 `ai-flow-architect-csdn.md` 全文到编辑器
5. 在对应位置插入图片：
   - 找到 `<!-- 图片位置：上传 cover.png -->` 这行注释，删除注释，插入封面图
   - 找到 `<!-- 图片位置：上传 architecture.png -->`，删除注释，插入架构图
   - 找到 `<!-- 图片位置：上传 opponent-brain.png -->`，删除注释，插入手脑图
   - 找到 `<!-- 图片位置：上传 comparison.png -->`，删除注释，插入对比图
6. 添加标签（建议）：
   - `人工智能`
   - `开源`
   - `Python`
   - `AI工作流`
   - `大模型`
   - `LangChain`
7. 选择分类：`人工智能` 或 `后端`
8. 发布

### 3. 标题建议

当前标题：`「让 GPT 和 Claude 互相挑刺」—— 我写了一个对抗式 AI 工作流引擎`

备选标题（如果 CSDN 标题长度有限制）：
- `让 GPT 和 Claude 互相挑刺：对抗式 AI 工作流引擎`
- `AI 幻觉的解法：双脑对抗工作流引擎开源`
- `pip install ai-flow-architect：一个让 AI 互相监督的框架`

### 4. 发布后的优化

- 发布后分享到微信/QQ 群，让同学朋友帮忙点赞收藏（CSDN 算法对互动量敏感）
- 在文章底部引导读者去 GitHub 点 Star
- 如果文章爆了，可以考虑发系列文章（架构拆解、实战教程、源码分析）

---

*生成时间：2026-05-19*
