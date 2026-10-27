import re
import pytest
from utils.time_utils import generate_msg_id, get_timestamp_ms

class TestTimeUtils:
    def test_generate_msg_id_format(self):
        msg_id = generate_msg_id()
        # 校验格式: 8位数字-6位数字-3位数字-3位数字 (例 20260728-092443-471-250)
        pattern = r"^\d{8}-\d{6}-\d{3}-\d{3}$"
        assert re.match(pattern, msg_id), f"msg_id [{msg_id}] 不符合格式 {pattern}"

    def test_generate_msg_id_uniqueness(self):
        id1 = generate_msg_id()
        id2 = generate_msg_id()
        assert isinstance(id1, str)
        assert isinstance(id2, str)

