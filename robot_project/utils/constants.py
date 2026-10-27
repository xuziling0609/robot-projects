import os

# 动态推导出当前工作区的绝对路径（即 robot_project 根目录）
# utils 目录在根目录下，所以上一级即为 PROJECT_ROOT
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
