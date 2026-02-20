# Git Push 网络问题解决方案

## 问题描述
推送时出现：`Failed to connect to github.com port 443`

## 解决方案

### 方案 1：切换到 SSH 方式（推荐）

如果你已经在 GitHub 添加了 SSH 公钥，可以切换到 SSH：

```bash
# 1. 查看当前远程地址
git remote -v

# 2. 切换到 SSH 地址
git remote set-url origin git@github.com:Rayz17/yuki-cidoc-proj.git

# 3. 验证
git remote -v

# 4. 测试连接
ssh -T git@github.com

# 5. 重新推送
git push origin main
```

### 方案 2：配置 HTTP 代理（如果你使用代理）

如果你使用代理（如 Clash、V2Ray 等），需要配置 Git 代理：

```bash
# 设置 HTTP 代理（替换为你的代理地址和端口）
git config --global http.proxy http://127.0.0.1:7890
git config --global https.proxy http://127.0.0.1:7890

# 或者只对 GitHub 设置代理
git config --global http.https://github.com.proxy http://127.0.0.1:7890

# 推送
git push origin main

# 如果不需要代理了，可以取消
git config --global --unset http.proxy
git config --global --unset https.proxy
```

### 方案 3：使用 GitHub CLI（如果已安装）

```bash
# 如果安装了 gh CLI
gh auth login
git push origin main
```

### 方案 4：稍后重试

可能是 GitHub 服务临时问题，可以：
1. 等待几分钟后重试
2. 检查 https://www.githubstatus.com/ 查看 GitHub 服务状态

### 方案 5：分批推送（如果文件很大）

如果文件很大，可以分批推送：

```bash
# 先推送小文件
git push origin main --dry-run  # 预览

# 如果还是失败，可以尝试强制推送（谨慎使用）
git push origin main --force-with-lease
```

## 当前状态

✅ 提交已成功完成（commit hash: 7d2b0ef）
- 23 个文件已提交
- 57,818 行新增
- 163 行删除

❌ 推送到 GitHub 失败（网络连接问题）

## 建议

**优先尝试方案 1（SSH）**，因为：
- SSH 连接更稳定
- 不受 HTTPS 端口限制
- 不需要频繁输入密码（如果配置了 SSH 密钥）





