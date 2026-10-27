import time
import json
import socket
import pytest
from src.communication.host_server import TCPServerThread, command_queue

TEST_HOST = "127.0.0.1"
TEST_PORT = 19920

@pytest.fixture(scope="module")
def tcp_server():
    server_thread = TCPServerThread(host=TEST_HOST, port=TEST_PORT)
    server_thread.start()
    time.sleep(0.3)  # 等待服务器启动完成
    yield server_thread
    server_thread.stop()
    time.sleep(0.2)

def _send_and_recv_lines(payload: dict, timeout: float = 2.0) -> list:
    """模拟上位机 ArmPlugin 发送单条指令并收集所有按行响应"""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    s.connect((TEST_HOST, TEST_PORT))
    
    msg_bytes = (json.dumps(payload) + "\n").encode('utf-8')
    s.sendall(msg_bytes)
    
    responses = []
    buffer = ""
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        try:
            chunk = s.recv(1024)
            if not chunk:
                break
            buffer += chunk.decode('utf-8')
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                line = line.strip()
                if line:
                    responses.append(json.loads(line))
        except socket.timeout:
            break
            
    s.close()
    return responses

def test_check_connection(tcp_server):
    """模拟 ArmPlugin.check_connection: 仅建连探测后立即释放"""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(1.0)
    s.connect((TEST_HOST, TEST_PORT))
    s.close()

def test_status_query(tcp_server):
    """测试状态查询指令"""
    res = _send_and_recv_lines({"action": "status"})
    assert len(res) == 1
    assert res[0].get("result") == "success"
    assert res[0].get("data", {}).get("online") is True

def test_goto_two_stage_protocol(tcp_server):
    """测试 goto 指令的两阶段响应: 阶段 1 返回 start，处理完成后返回 success"""
    while not command_queue.empty():
        command_queue.get()
        
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(2.0)
    s.connect((TEST_HOST, TEST_PORT))
    
    # 模拟上位机发送 goto
    s.sendall((json.dumps({"action": "goto", "point": 0}) + "\n").encode('utf-8'))
    
    # 阶段 1: 等待 {"result": "start"}
    raw_start = s.recv(1024).decode('utf-8').strip()
    res_start = json.loads(raw_start)
    assert res_start.get("result") == "start"
    
    # 验证指令已进入主队列并取出
    cmd = command_queue.get(timeout=1.0)
    assert cmd["action"] == "goto"
    assert cmd["point"] == 0
    handler = cmd["handler"]
    
    # 阶段 2: 模拟机械臂主控运动完成，通知 handler 回复 success
    handler.send_success("到位")
    raw_success = s.recv(1024).decode('utf-8').strip()
    res_success = json.loads(raw_success)
    assert res_success.get("result") == "success"
    
    s.close()

def test_pause_two_stage_protocol(tcp_server):
    """测试 pause 指令的两阶段响应"""
    while not command_queue.empty():
        command_queue.get()
        
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(2.0)
    s.connect((TEST_HOST, TEST_PORT))
    
    s.sendall((json.dumps({"action": "pause"}) + "\n").encode('utf-8'))
    
    raw_start = s.recv(1024).decode('utf-8').strip()
    assert json.loads(raw_start).get("result") == "start"
    
    cmd = command_queue.get(timeout=1.0)
    assert cmd["action"] == "pause"
    cmd["handler"].send_success("已暂停")
    
    raw_success = s.recv(1024).decode('utf-8').strip()
    assert json.loads(raw_success).get("result") == "success"
    
    s.close()

def test_goback_two_stage_protocol(tcp_server):
    """测试 goback 指令的两阶段响应"""
    while not command_queue.empty():
        command_queue.get()
        
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(2.0)
    s.connect((TEST_HOST, TEST_PORT))
    
    s.sendall((json.dumps({"action": "goback"}) + "\n").encode('utf-8'))
    
    raw_start = s.recv(1024).decode('utf-8').strip()
    assert json.loads(raw_start).get("result") == "start"
    
    cmd = command_queue.get(timeout=1.0)
    assert cmd["action"] == "goback"
    cmd["handler"].send_success("已复位")
    
    raw_success = s.recv(1024).decode('utf-8').strip()
    assert json.loads(raw_success).get("result") == "success"
    
    s.close()

def test_invalid_action(tcp_server):
    """测试不支持的动作下发返回 fail"""
    res = _send_and_recv_lines({"action": "invalid_action"})
    assert len(res) == 1
    assert res[0].get("result") == "fail"
    assert "不支持" in res[0].get("message", "")

def test_malformed_json(tcp_server):
    """测试非合法 JSON 字符串返回 fail"""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(2.0)
    s.connect((TEST_HOST, TEST_PORT))
    s.sendall(b"not a json line\n")
    raw = s.recv(1024).decode('utf-8').strip()
    res = json.loads(raw)
    assert res.get("result") == "fail"
    s.close()

def test_fail_response_during_execution(tcp_server):
    """测试执行时失败回复 fail: 阶段 1 返回 start，执行失败时阶段 2 返回 fail"""
    while not command_queue.empty():
        command_queue.get()
        
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(2.0)
    s.connect((TEST_HOST, TEST_PORT))
    
    s.sendall((json.dumps({"action": "goto", "point": 2}) + "\n").encode('utf-8'))
    
    # 阶段 1: start
    raw_start = s.recv(1024).decode('utf-8').strip()
    assert json.loads(raw_start).get("result") == "start"
    
    cmd = command_queue.get(timeout=1.0)
    handler = cmd["handler"]
    
    # 模拟执行时失败: 下发 fail
    handler.send_fail("触碰电子围栏")
    
    raw_fail = s.recv(1024).decode('utf-8').strip()
    res_fail = json.loads(raw_fail)
    assert res_fail.get("result") == "fail"
    assert res_fail.get("message") == "触碰电子围栏"
    
    s.close()
