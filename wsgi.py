import sys
import os

# 添加项目路径到 sys.path
path = '/home/你的用户名/mysite'
if path not in sys.path:
    sys.path.insert(0, path)

# 设置环境变量（如果需要在部署时使用）
os.environ['DATABASE_URL'] = 'sqlite:///' + os.path.join(path, 'exam.db')

# 导入 Flask app
from app import app as application
