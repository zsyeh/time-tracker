# /root/time_server/gunicorn.conf.py
import multiprocessing

# 网络绑定
bind = "0.0.0.0:30000"

# 进程与线程管理
workers = 3
worker_class = "sync"

# 日志路由配置
accesslog = "/var/log/gunicorn_access.log"
errorlog = "/var/log/gunicorn_error.log"
loglevel = "info"
