# Coze API 超时问题修复

## 问题分析

用户反馈在使用 Coze 进行抽取时，尽管 Coze 后台显示请求成功，但 GUI 日志显示 `Read timed out`，导致任务失败且没有数据。

**根本原因：**
1. **Coze 生成内容过长**：日志显示 Coze 返回了超过 13,000 个 token。生成如此大量的内容需要数分钟（通常 > 6分钟）。
2. **HTTP 连接超时**：之前的代码设置了 300秒（5分钟）的超时时间。当生成时间超过这个限制时，Python 客户端主动断开了连接。
3. **非流式请求阻塞**：使用了 `stream=False`，客户端必须空等直到服务器生成完所有内容。

## 修复方案

已将 `src/automated_extractor.py` 中的 `call_coze_api` 函数修改为 **流式接收 (`stream=True`)** 模式。

### 修改点：

1. **启用流式模式**：
   ```python
   chat_payload = {
       ...,
       'stream': True  # 改为True
   }
   requests.post(..., stream=True)
   ```

2. **实时数据处理**：
   不再等待完整响应，而是逐行读取数据流 (`iter_lines`)。这样即使总生成时间很长，只要服务器在持续发送数据，连接就会保持活跃，**彻底解决超时问题**。

   ```python
   for line in chat_response.iter_lines():
       if decoded_line.startswith('data:'):
           # 解析每一块数据并拼接...
   ```

## 验证结果

通过 `test_coze_stream.py` 测试脚本验证，流式接口工作正常：
```
收到数据行: data:{"event":"message","message":{"role":"assistant","type":"answer","content":"..."}}
  -> 提取内容: ...
最终完整内容: ```json ...
✅ 测试成功！
```

## 后续建议

由于 Coze Agent 输出内容非常多（13k+ token），建议：
1. **检查 Prompt**：确认是否可以让模型输出更精简的内容（只输出 JSON）。
2. **耐心等待**：现在的抽取过程可能会比较慢（因为生成内容多），请耐心等待任务完成，不要因为看起来像卡住而关闭程序。

---

**修复已应用，请重新运行抽取任务！** 🚀

