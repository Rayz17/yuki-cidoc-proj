#!/bin/bash

# Git 同步到 GitHub 脚本
# 使用方法: ./sync_to_github.sh "提交信息"

# 检查是否提供了提交信息
if [ -z "$1" ]; then
    echo "❌ 错误: 请提供提交信息"
    echo "使用方法: ./sync_to_github.sh \"你的提交信息\""
    exit 1
fi

COMMIT_MSG="$1"

echo "📋 步骤 1: 查看当前状态..."
git status

echo ""
echo "📦 步骤 2: 添加所有更改..."
git add .

echo ""
echo "💾 步骤 3: 提交更改..."
git commit -m "$COMMIT_MSG"

echo ""
echo "🚀 步骤 4: 推送到 GitHub..."
git push origin main

echo ""
echo "✅ 完成！所有更改已同步到 GitHub"

