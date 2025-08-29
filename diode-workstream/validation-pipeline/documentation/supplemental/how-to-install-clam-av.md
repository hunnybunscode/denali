# For Developers

## How to install ClamAV on RHEL

```
sudo dnf install -y wget
wget https://www.clamav.net/downloads/production/clamav-1.4.2.linux.x86_64.rpm
sudo rpm -ivh clamav-1.4.2.linux.x86_64.rpm

sudo useradd clamav
sudo mkdir -p /var/lib/clamav
sudo mkdir -p /var/log/clamav
sudo mkdir -p /var/run/clamav
sudo chown -R clamav:clamav /var/lib/clamav
sudo chown -R clamav:clamav /var/log/clamav
sudo chown -R clamav:clamav /var/run/clamav

sudo tee /usr/local/etc/freshclam.conf <<EOF
DatabaseDirectory /var/lib/clamav
UpdateLogFile /var/log/clamav/freshclam.log
DatabaseMirror database.clamav.net
DatabaseOwner clamav
Foreground false
Debug false
MaxAttempts 5
PidFile /var/run/clamav/freshclam.pid
EOF

sudo tee /usr/local/etc/clamd.conf <<EOF
LogFile /var/log/clamav/clamd.log
LogFileMaxSize 2M
LogTime yes
LogVerbose yes
DatabaseDirectory /var/lib/clamav
LocalSocket /var/run/clamav/clamd.sock
LocalSocketMode 666
LocalSocketGroup clamav
TemporaryDirectory /var/tmp
User clamav
ExitOnOOM yes
MaxDirectoryRecursion 20
FollowDirectorySymlinks yes
FollowFileSymlinks yes
ReadTimeout 180
MaxThreads 12
MaxConnectionQueueLength 15
StreamMaxLength 25M
Foreground true
EOF

sudo tee /etc/systemd/system/clamd.service <<EOF
[Unit]
Description=Clam AntiVirus Daemon
After=network.target

[Service]
Type=simple
User=clamav
Group=clamav
RuntimeDirectory=clamav
RuntimeDirectoryMode=0755
ExecStart=/usr/local/sbin/clamd --foreground=true -c /usr/local/etc/clamd.conf
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

freshclam --config-file=/usr/local/etc/freshclam.conf

sudo systemctl daemon-reload
sudo systemctl start clamd
sudo systemctl enable clamd

history -c
```
