#!/bin/bash

# 更新系統
apt-get update
apt-get upgrade -y

# 安裝基本工具
apt-get install -y curl wget unzip vim htop git

# 安裝 Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
usermod -aG docker ubuntu

# 安裝 Docker Compose
curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# 安裝 Python 和 pip
apt-get install -y python3 python3-pip python3-venv

# 安裝 Node.js (可選)
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
apt-get install -y nodejs

# 建立應用目錄
mkdir -p /opt/app
chown ubuntu:ubuntu /opt/app

# 設定防火牆 (如果需要)
ufw allow ssh
ufw allow http
ufw allow https

# 記錄啟動完成
echo "VM startup script completed at $(date)" >> /var/log/startup-script.log