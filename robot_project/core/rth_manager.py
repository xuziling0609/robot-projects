"""
RthManager - 边缘网关返航引擎 (RTH One-Shot Static Compiler)
===========================================================

设计背景与架构意图:
-----------------
在机器人自主巡检或执行作业任务过程中，若遭遇平台调度中止、电量过低报警、火警或人工下发返航指令 (action="rth")，
系统需要从当前所在位置安全、可靠地返回初始待命点或指定的返航目标 (rth)。

历史上旧版的 reverse_manager 采用“运行时内存栈逆序弹栈 + 宏组件反向规则”的模式，存在严重缺陷：
1. 宏动作不可逆：开门、升降梯、传感器采样等业务动作无法通过简单的数学逆操作回滚；
2. 状态强耦合：在宏组件内部硬编码反向逻辑，导致业务扩展极难维护；
3. 动态中断风险：动态生成单步任务在任务引擎中流转时容易产生状态竞态与校验拦截。

全新 RthManager 彻底采用 **“一次性静态离线编译 (One-Shot Compiler)”** 架构：
在接收到返航请求的瞬时，根据被中断任务的历史执行进度，一次性编译生成由纯原子步骤构成的扁平化返航任务列表
(List[Dict[str, Any]])，直接注入底层 TaskManager 调度流水线执行。

四大编译流水线 (Four-Stage Compilation Pipeline):
------------------------------------------------
1. 【前置安全清洗 (Pre-RTH Resets)】:
   从 configs/rth_hooks.yaml 中读取预设的安全复位动作（如云台归中、机械臂收回、停止声光告警等），
   无论机器人在何处被中断，返航前均优先执行清洗动作，确保整机处于最高安全姿态。

2. 【走过路径纯 Nav 轨迹提取与逆序 (Nav Extraction & Inversion)】:
   遍历原任务中截止到当前中断步 (current_step_index) 的所有已执行步骤，滤除与导航无关的传感器和外设操作，
   仅提取出已执行的导航目标点 [P0, P1, P2, ... Pn]，进行就地逆序反转 [Pn, ... P1, P0]，形成物理回程骨干拓扑。

3. 【滑动窗口边动作挂载查表 (Edge Action Hook Table)】:
   以步长为 1 对逆序路径滑动取相邻点对 (P_from, P_to)，组装为有向边键值 "P_from_P_to"。
   在 rth_hooks.yaml 的 edge_actions 映射表中进行匹配：
   - 若命中边配置：将预定义的一组原子边动作展开插入（例如：接近门禁 -> 打开卷帘门 -> 穿过门禁到达目标点 -> 关门）；
   - 若未命中边配置：自动降级为标准直接导航动作 (start_nav 到 P_to)。

4. 【任务专属终点闭环策略 (Custom rth Termination)】:
   若下发任务元数据中携带专属返航目标 (rth，包含 point_id，例如专用充电桩 ST_01)：
   - 自动判定回程轨迹的最后一站是否已是该终点；
   - 若不是，则将回程最后一站与 rth["point_id"] 形成最后一段边，同样进行 edge_actions 查表挂载（例如触发进桩动作）；
   - 若整段任务未包含任何 Nav 点（原地被叫停），则直接由当前位置直飞或进桩至 rth["point_id"]。
"""

import os
import copy
from typing import Dict, Any, List, Optional
import yaml

from core.logger_manager import get_logger

logger = get_logger("rth_manager")


class RthManager:
    """
    边缘网关返航引擎 (RTH Compiler)
    负责将中断的任务轨迹与全局边挂载配置编译为完整的原子级返航任务序列。
    """

    def __init__(self, config_path: Optional[str] = None):
        """
        初始化 RTH 编译器。

        :param config_path: 可选的 rth_hooks.yaml 配置文件绝对路径。
                            默认指向工程根目录下的 configs/rth_hooks.yaml。
        """
        if config_path:
            self.config_path = config_path
        else:
            self.config_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "configs",
                "rth_hooks.yaml"
            )

    def _load_config(self) -> Dict[str, Any]:
        """
        加载返航配置 (支持热更新与异常自愈)。

        每次编译返航任务时均按需读取，确保运营人员或平台动态修改 configs/rth_hooks.yaml
        时无需重启边缘服务即可即时生效。同时在文件缺失或 YAML 解析异常时提供空配置兜底，
        确保返航主干流程绝不抛出未捕获异常。

        :return: 包含 pre_rth_resets(List) 与 edge_actions(Dict) 的配置字典
        """
        default_config: Dict[str, Any] = {"pre_rth_resets": [], "edge_actions": {}}
        if not os.path.exists(self.config_path):
            logger.warning("RTH 配置文件不存在: %s，将使用空配置兜底", self.config_path)
            return default_config

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                loaded = yaml.safe_load(f)
                return loaded if isinstance(loaded, dict) else default_config
        except Exception as err:
            logger.error("加载 RTH 配置文件失败: %s，原因: %s，将使用空配置兜底", self.config_path, err, exc_info=True)
            return default_config

    def build(
        self,
        current_queue: List[Dict[str, Any]],
        current_step_index: int,
        task_metadata: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        核心编译函数 (One-Shot Build Pipeline)

        根据被中断的任务执行队列与元数据，编译出一组有序的、完全扁平化的返航原子步骤列表。

        :param current_queue: 原正向任务的完整步骤队列 (List[Dict[str, Any]])
        :param current_step_index: 触发返航时当前正在执行或刚刚完成的步骤索引 (0-based 整数)
        :param task_metadata: 任务元数据字典，支持读取：
                              - "rth": 平台下发任务时指定的专属返航终点对象 (包含 localization 和 point_id)
        :return: 编译完成的返航步骤列表 (List[Dict])，步骤中的 step 编号已从 1 开始规范重编
        """
        config = self._load_config()
        pre_resets: List[Dict[str, Any]] = config.get("pre_rth_resets", [])
        edge_actions: Dict[str, List[Dict[str, Any]]] = config.get("edge_actions", {})

        # =========================================================================
        # 阶段 1: 提取并过滤已走过的 Nav 纯物理轨迹点 (前闭后闭区间截取)
        # =========================================================================
        # 截取范围为 [0, current_step_index]，即历史上所有已经执行过或当前正在被中断执行的步骤
        executed_steps = current_queue[:current_step_index + 1]
        nav_points: List[Any] = []

        for step in executed_steps:
            if step.get("plugin_type") == "NavPlugin" and step.get("action") == "start_nav":
                pt = step.get("params", {}).get("goal_point")
                if pt is not None:
                    nav_points.append(pt)

        # 逆序反转形成回程基础拓扑：例如正向走过 [P1, P2, P3]，逆序后为 [P3, P2, P1]
        nav_points.reverse()

        # =========================================================================
        # 阶段 2: 组装返航步骤队列与全局步骤自增器
        # =========================================================================
        result_steps: List[Dict[str, Any]] = []
        step_counter = 1

        def add_step(raw_step: Dict[str, Any]) -> None:
            """
            深拷贝注入单步指令并分配连续唯一的步号 (1-based)。
            使用 deepcopy 彻底避免修改全局配置模板中的原始字典对象。
            """
            nonlocal step_counter
            step_copy = copy.deepcopy(raw_step)
            step_copy["step"] = step_counter
            result_steps.append(step_copy)
            step_counter += 1

        # -------------------------------------------------------------------------
        # 步骤 2.1: 铺底前置安全清洗阵列 (Pre-RTH Resets)
        # 无论在哪个点位被叫停返航，优先将云台、机械臂等易碰撞机构复位归中
        # -------------------------------------------------------------------------
        for reset_action in pre_resets:
            add_step(reset_action)

        # -------------------------------------------------------------------------
        # 步骤 2.2: 滑动窗口匹配相邻两点间的边动作 (Edge Actions)
        # -------------------------------------------------------------------------
        if not nav_points:
            # 边界场景 1: 原任务在执行到当前步之前从未执行过任何 Nav 动作（例如刚执行了声光或开门即被叫停）
            # 此时 nav_points 为空，仅执行前置清洗，后续由专属 rth 处理直航
            pass
        elif len(nav_points) == 1:
            # 边界场景 2: 任务中仅包含 1 个导航点（说明机器人在该点附近作业）
            # 若未指定专属 rth 或专属终点恰好等于该点，则确保机器人导航回到该点
            rth_info = task_metadata.get("rth") if task_metadata else None
            rth_pt = rth_info.get("point_id") if isinstance(rth_info, dict) else None
            if rth_pt is None or rth_pt == nav_points[0]:
                add_step({
                    "plugin_type": "NavPlugin",
                    "action": "start_nav",
                    "params": {"goal_point": nav_points[0]}
                })
        else:
            # 典型场景 3: 走过多段航迹（如 P3 -> P2 -> P1），采用双指针滑动窗口逐段提取边
            for i in range(len(nav_points) - 1):
                p_from = nav_points[i]
                p_to = nav_points[i + 1]
                edge_key = f"{p_from}_{p_to}"

                if edge_key in edge_actions:
                    # 命中配置化边动作库：将该边配置的复合原子步骤（如开门、过门、闭门等）逐一解包挂载
                    for action_def in edge_actions[edge_key]:
                        add_step(action_def)
                else:
                    # 未配置特殊边动作：降级为基础直接导航，驱动底盘驶向下一目标点
                    add_step({
                        "plugin_type": "NavPlugin",
                        "action": "start_nav",
                        "params": {"goal_point": p_to}
                    })

        # -------------------------------------------------------------------------
        # 步骤 2.3: 任务专属返航终点兜底策略 (Custom rth Finalization)
        # 平台下发任务时往往指定了特定终点（例如任务起点为 P1，但任务元数据要求返航至充电桩 ST_01）
        # -------------------------------------------------------------------------
        rth_info = task_metadata.get("rth") if task_metadata else None
        rth_point = rth_info.get("point_id") if isinstance(rth_info, dict) else None
        if rth_point is not None:
            # last_point 为回程倒推轨迹的最后一个点（即原任务正向执行的最早导航起点）
            last_point = nav_points[-1] if nav_points else None

            if last_point is not None and last_point != rth_point:
                # 若倒推的终点尚未到达指定的 rth_point，需从 last_point 补齐通往 rth_point 的边
                edge_key = f"{last_point}_{rth_point}"
                if edge_key in edge_actions:
                    # 优先命中终点专属边动作（例如进站充电包含：对准触点、降下受电弓、开始充电确认）
                    for action_def in edge_actions[edge_key]:
                        add_step(action_def)
                else:
                    # 未配置特殊进站边动作，直接生成通向 rth_point 的导航指令
                    add_step({
                        "plugin_type": "NavPlugin",
                        "action": "start_nav",
                        "params": {"goal_point": rth_point}
                    })
            elif last_point is None:
                # 若此前没有任何 Nav 点轨迹，直接以 rth_point 为目标发起导航
                add_step({
                    "plugin_type": "NavPlugin",
                    "action": "start_nav",
                    "params": {"goal_point": rth_point}
                })

        logger.info(
            "RTH 返航任务编译完成: 共生成 %d 个原子步骤 (前置清洗: %d, 历史航点: %d, 专属终点: %s)",
            len(result_steps),
            len(pre_resets),
            len(nav_points),
            rth_info.get("point_id") if (task_metadata and isinstance(rth_info, dict)) else "None"
        )
        return result_steps
