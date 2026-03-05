'''
gunicorn main:app -c run.py
uvicorn main:app --host 0.0.0.0 --port 8000
'''

import socket
if socket.gethostname() == "knpu":
    port = 8004
else:
    port = 8000
    
bind = f"0.0.0.0:{port}"
workers = 1
worker_class = "uvicorn.workers.UvicornWorker"
timeout = 0
loglevel = "warning"
accesslog = None          
keepalive = 86400
