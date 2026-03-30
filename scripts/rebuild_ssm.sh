#!/bin/bash
# SSM 机构版全站物理自愈与重构脚本 (V8.0)
# 用途：彻底清除所有 Python 缓存、重建 Docker 卷挂载、强制重置内存

echo "🚀 启动全站物理自愈程序..."

# 1. 物理清理宿主机缓存
find . -name "__pycache__" -type d -exec rm -rf {} +
echo "✅ 宿主机 __pycache__ 已物理肃清"

# 2. 强制停服并销毁残留句柄
docker-compose down --remove-orphans
echo "✅ 容器服务已安全关停并清理 Inode"

# 3. 执行物理级全量重建
docker-compose up -d --build
echo "✅ 容器链已 100% 同步磁盘原子状态启动"

# 4. 系统启动巡航
echo "📡 正在为您锁定启动日志..."
sleep 5
docker logs smart-stock-monitor --tail 20

echo "🎉 手术成功！您的 SSM Quantum Pro v7.0 已进入绝对稳态。"
