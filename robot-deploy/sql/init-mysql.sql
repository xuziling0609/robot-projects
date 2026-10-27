-- ==============================================================================
-- 智能机器人综合管理平台 - MySQL 8.0 数据库初始化结构与基础数据
-- 字符集: utf8mb4 / utf8mb4_unicode_ci
-- ==============================================================================

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;
SET SQL_MODE = 'NO_AUTO_VALUE_ON_ZERO';

CREATE DATABASE IF NOT EXISTS `robot` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE `robot`;

-- gen_table 定义
-- Drop table
-- DROP TABLE gen_table;

-- robot.gen_table 定义

create table `gen_table` (
  `table_id` bigint not null auto_increment COMMENT '编号',
`table_name` varchar(200) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '表名称',
`table_comment` varchar(500) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '表描述',
`sub_table_name` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '关联子表的表名',
`sub_table_fk_name` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '子表关联的外键名',
`class_name` varchar(100) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '实体类名称',
`tpl_category` varchar(200) character set utf8mb4 collate utf8mb4_general_ci default 'crud' COMMENT '使用的模板（crud单表操作 tree树表操作）',
`tpl_web_type` varchar(30) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '前端模板类型（element-ui模版 element-plus模版）',
`package_name` varchar(100) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '生成包路径',
`module_name` varchar(30) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '生成模块名',
`business_name` varchar(30) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '生成业务名',
`function_name` varchar(50) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '生成功能名',
`function_author` varchar(50) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '生成功能作者',
`gen_type` char(1) character set utf8mb4 collate utf8mb4_general_ci default '0' COMMENT '生成代码方式（0zip压缩包 1自定义路径）',
`gen_path` varchar(200) character set utf8mb4 collate utf8mb4_general_ci default '/' COMMENT '生成路径（不填默认项目路径）',
`options` varchar(1000) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '其它生成选项',
`create_by` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '创建者',
`create_time` datetime default null COMMENT '创建时间',
`update_by` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '更新者',
`update_time` datetime default null COMMENT '更新时间',
`remark` varchar(500) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '备注',
primary key (`table_id`)
    using BTREE
) engine = InnoDB auto_increment = 1 default CHARSET = utf8mb4 collate = utf8mb4_general_ci ROW_FORMAT = dynamic COMMENT = '代码生成业务表';
-- robot.gen_table_column 定义

create table `gen_table_column` (
  `column_id` bigint not null auto_increment COMMENT '编号',
`table_id` bigint default null COMMENT '归属表编号',
`column_name` varchar(200) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '列名称',
`column_comment` varchar(500) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '列描述',
`column_type` varchar(100) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '列类型',
`java_type` varchar(500) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT 'JAVA类型',
`java_field` varchar(200) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT 'JAVA字段名',
`is_pk` char(1) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '是否主键（1是）',
`is_increment` char(1) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '是否自增（1是）',
`is_required` char(1) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '是否必填（1是）',
`is_insert` char(1) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '是否为插入字段（1是）',
`is_edit` char(1) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '是否编辑字段（1是）',
`is_list` char(1) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '是否列表字段（1是）',
`is_query` char(1) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '是否查询字段（1是）',
`query_type` varchar(200) character set utf8mb4 collate utf8mb4_general_ci default 'EQ' COMMENT '查询方式（等于、不等于、大于、小于、范围）',
`html_type` varchar(200) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '显示类型（文本框、文本域、下拉框、复选框、单选框、日期控件）',
`dict_type` varchar(200) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '字典类型',
`sort` int default null COMMENT '排序',
`create_by` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '创建者',
`create_time` datetime default null COMMENT '创建时间',
`update_by` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '更新者',
`update_time` datetime default null COMMENT '更新时间',
primary key (`column_id`)
    using BTREE
) engine = InnoDB auto_increment = 1 default CHARSET = utf8mb4 collate = utf8mb4_general_ci ROW_FORMAT = dynamic COMMENT = '代码生成业务表字段';
-- robot.robot_ability_debug 定义

create table `robot_ability_debug` (
  `id` bigint not null auto_increment COMMENT '主键ID',
`robot_id` varchar(55) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '机器人ID/车辆ID',
`msg_id` varchar(255) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '步骤ID',
`operation` varchar(255) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '操作类型',
`step_type` varchar(255) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '步骤类型',
`action` varchar(255) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '步骤操作',
`destination` varchar(255) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '目的地',
`ability_info` mediumtext character set utf8mb4 collate utf8mb4_general_ci COMMENT '下发的调试数据',
`result` varchar(255) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '执行结果：初始(系统赋值)/开始/成功/失败(init/start/success/fail)',
`msg_info` mediumtext character set utf8mb4 collate utf8mb4_general_ci COMMENT '结果原因',
`data_info` mediumtext character set utf8mb4 collate utf8mb4_general_ci COMMENT '响应回复数据详情',
`timestamp` datetime default null COMMENT '下发时间',
`description` varchar(255) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '描述',
`ext1` varchar(16) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '备用1',
`ext2` varchar(255) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '备用2',
`ext3` varchar(500) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '备用3',
`ext4` varchar(255) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '备用4',
`create_by` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '创建者',
`create_time` datetime default null COMMENT '创建时间',
`update_by` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '更新者',
`update_time` datetime default null COMMENT '更新时间',
`del_flag` char(1) character set utf8mb4 collate utf8mb4_general_ci default '0' COMMENT '删除标志（0存在 2删除）',
primary key (`id`)
    using BTREE
) engine = InnoDB auto_increment = 1 default CHARSET = utf8mb4 collate = utf8mb4_general_ci ROW_FORMAT = dynamic COMMENT = '机器人调试表';
-- robot.robot_alarm_config 定义

create table `robot_alarm_config` (
  `id` bigint not null auto_increment COMMENT '主键ID',
`robot_id` varchar(55) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '机器人ID',
`plugin_type` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '插件类型',
`gas_type` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '告警类型',
`alarm_level` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '告警级别',
`config_operator` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '区间类型',
`config_value` varchar(255) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '告警值',
`message` varchar(500) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '描述',
`ext1` varchar(55) collate utf8mb4_general_ci default null COMMENT '备用1',
`ext2` varchar(55) collate utf8mb4_general_ci default null COMMENT '备用2',
`ext3` varchar(55) collate utf8mb4_general_ci default null COMMENT '备用3',
`ext4` varchar(55) collate utf8mb4_general_ci default null COMMENT '备用4',
`status` int default '1' COMMENT '状态：1=启用，0=禁用',
`create_by` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '创建者',
`create_time` datetime default null COMMENT '创建时间',
`update_by` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '更新者',
`update_time` datetime default null COMMENT '更新时间',
`del_flag` char(1) character set utf8mb4 collate utf8mb4_general_ci default '0' COMMENT '删除标志：0=未删除，1=已删除',
primary key (`id`)
    using BTREE
) engine = InnoDB auto_increment = 1 default CHARSET = utf8mb4 collate = utf8mb4_general_ci ROW_FORMAT = dynamic COMMENT = '告警配置';
-- robot.robot_config 定义

create table `robot_config` (
  `id` bigint not null auto_increment COMMENT '主键ID',
`config_name` varchar(255) character set utf8mb4 collate utf8mb4_general_ci not null COMMENT '配置项名称',
`config_key` varchar(255) character set utf8mb4 collate utf8mb4_general_ci not null COMMENT '配置键',
`config_value` varchar(1000) character set utf8mb4 collate utf8mb4_general_ci not null COMMENT '配置值',
`create_by` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '创建者',
`create_time` datetime default null COMMENT '创建时间',
`update_by` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '更新者',
`update_time` datetime default null COMMENT '更新时间',
`remark` varchar(500) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '备注',
primary key (`id`)
    using BTREE,
unique key `uk_config_key` (`config_key`)
    using BTREE
) engine = InnoDB auto_increment = 1 default CHARSET = utf8mb4 collate = utf8mb4_general_ci ROW_FORMAT = dynamic COMMENT = '机器人相关参数配置表';
-- robot.robot_device 定义

create table `robot_device` (
  `id` bigint not null auto_increment,
`robot_id` varchar(255) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '机器人id',
`ability_type` varchar(50) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '能力类型  \r\n   door_control：开门机控制\r\nrobot_arm_control：机械臂控制\r\npartial_discharge_control：局放控制\r\nelevator_control：电梯控制\r\ncamera_control：摄像机控制\r\nptz_control：云台控制\r\n   robot_dog_navigation：机械狗导航控制',
`ability_name` varchar(20) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '能力名称',
`ability_description` text character set utf8mb4 collate utf8mb4_general_ci,
`action_json` text character set utf8mb4 collate utf8mb4_general_ci,
`ext1` text collate utf8mb4_general_ci COMMENT '告警配置列表',
`ext2` text collate utf8mb4_general_ci COMMENT '告警配置列表',
`ext3` varchar(16) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '备用3',
`ext4` varchar(16) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '备用4',
`remark` varchar(500) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '备注',
`create_by` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '创建者',
`create_time` datetime default null COMMENT '创建时间',
`update_by` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '更新者',
`update_time` datetime default null COMMENT '更新时间',
`del_flag` char(1) character set utf8mb4 collate utf8mb4_general_ci default '0' COMMENT '删除标志（0代表存在 2代表删除）',
primary key (`id`)
    using BTREE
) engine = InnoDB auto_increment = 1 default CHARSET = utf8mb4 collate = utf8mb4_general_ci ROW_FORMAT = dynamic COMMENT = '机器人设备';
-- robot.robot_device_type 定义

create table `robot_device_type` (
  `id` bigint not null auto_increment COMMENT '主键ID',
`parent_id` bigint not null default '0' COMMENT '上级ID',
`type_level` int not null COMMENT '层级',
`type_name` varchar(255) character set utf8mb4 collate utf8mb4_general_ci not null COMMENT '类型名称',
`type_value` varchar(255) character set utf8mb4 collate utf8mb4_general_ci not null COMMENT '类型值',
`create_by` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '创建者',
`create_time` datetime default null COMMENT '创建时间',
`update_by` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '更新者',
`update_time` datetime default null COMMENT '更新时间',
`icon_img` varchar(255) collate utf8mb4_general_ci default null,
`ext1` varchar(255) collate utf8mb4_general_ci default null,
`ext2` varchar(255) collate utf8mb4_general_ci default null,
`ext3` varchar(255) collate utf8mb4_general_ci default null,
`ext4` varchar(255) collate utf8mb4_general_ci default null,
`remark` varchar(500) collate utf8mb4_general_ci default null,
primary key (`id`)
    using BTREE,
key `uk_parent_id` (`parent_id`)
    using BTREE
) engine = InnoDB auto_increment = 1 default CHARSET = utf8mb4 collate = utf8mb4_general_ci ROW_FORMAT = dynamic COMMENT = '机器人设备类型表';
-- robot.robot_display_config 定义

create table `robot_display_config` (
  `id` bigint not null auto_increment COMMENT '主键ID',
`robot_id` varchar(55) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '机器人ID',
`plugin_type` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '插件类型（上装能力类型 abilityType）',
`plugin_name` varchar(255) collate utf8mb4_general_ci default null COMMENT '插件名称',
`action` varchar(128) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '动作标识',
`name` varchar(255) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '动作名称',
`description` varchar(500) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '动作描述',
`params` text character set utf8mb4 collate utf8mb4_general_ci COMMENT '动作参数（JSON数组字符串）',
`scopes` text character set utf8mb4 collate utf8mb4_general_ci COMMENT '作用域（JSON数组字符串）',
`create_by` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '创建者',
`create_time` datetime default null COMMENT '创建时间',
`update_by` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '更新者',
`update_time` datetime default null COMMENT '更新时间',
`del_flag` char(1) character set utf8mb4 collate utf8mb4_general_ci default '0' COMMENT '删除标志：0=未删除，1=已删除',
primary key (`id`)
    using BTREE,
unique key `uk_robot_plugin_action` (`robot_id`,
`plugin_type`,
`action`)
    using BTREE,
key `idx_robot_id` (`robot_id`)
    using BTREE
) engine = InnoDB auto_increment = 1 default CHARSET = utf8mb4 collate = utf8mb4_general_ci ROW_FORMAT = dynamic COMMENT = '首页展示动作配置';
-- robot.robot_gas_sensor 定义

create table `robot_gas_sensor` (
  `id` bigint not null auto_increment COMMENT '主键ID',
`robot_id` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '设备编号',
`msg_id` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '指令ID/消息ID',
`sensor_no` varchar(11) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '传感器编号 1/2/3...',
`gas_name` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '气体名称',
`gas_value` varchar(10) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '气体浓度值',
`gas_unit` varchar(32) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '单位',
`result` varchar(32) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '执行结果 start/success/fail',
`reason` varchar(512) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '失败原因',
`create_time` datetime default null COMMENT '创建时间',
`update_time` datetime default null COMMENT '更新时间',
`ext1` varchar(16) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '备用1',
`ext2` varchar(255) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '备用2',
`ext3` varchar(500) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '备用3',
`ext4` varchar(255) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '备用4',
`create_by` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '创建者',
`update_by` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '更新者',
`del_flag` char(1) character set utf8mb4 collate utf8mb4_general_ci default '0' COMMENT '删除标志（0存在 2删除）',
primary key (`id`)
    using BTREE
) engine = InnoDB auto_increment = 1 default CHARSET = utf8mb4 collate = utf8mb4_general_ci ROW_FORMAT = dynamic COMMENT = '设备气体传感器数据表';
-- robot.robot_hidden_danger 定义

create table `robot_hidden_danger` (
  `id` int not null auto_increment COMMENT 'id',
`alert_id` varchar(50) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '告警id',
`device_id` varchar(50) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '设备id',
`device_name` varchar(50) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '设备名称',
`device_desc` varchar(255) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '设备描述',
`source_id` varchar(50) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '数据源id',
`source_desc` varchar(255) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '数据源描述',
`source_ip` varchar(50) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '数据源ip',
`alg_name` varchar(50) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '算法名称',
`alg_ch_name` varchar(50) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '算法显示名称',
`alg_type` varchar(50) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT 'general',
`hazard_level` varchar(50) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '危险等级',
`image` mediumtext character set utf8mb4 collate utf8mb4_general_ci COMMENT 'base64编码的图片数据',
`alert_time` datetime default null COMMENT '告警时间',
`status` varchar(10) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '状态',
`handler` varchar(50) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '处理人',
`handling_suggestion` varchar(500) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '处理意见',
`handling_time` datetime default null COMMENT '处理时间',
`ext1` varchar(255) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '备用1',
`ext2` varchar(16) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '备用2',
`ext3` varchar(16) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '备用3',
`ext4` varchar(16) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '备用4',
`remark` varchar(500) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '备注',
`create_by` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '创建者',
`create_time` datetime default null COMMENT '创建时间',
`update_by` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '更新者',
`update_time` datetime default null COMMENT '更新时间',
`del_flag` char(1) character set utf8mb4 collate utf8mb4_general_ci default '0' COMMENT '删除标志（0代表存在 2代表删除）',
primary key (`id`)
    using BTREE
) engine = InnoDB auto_increment = 1 default CHARSET = utf8mb4 collate = utf8mb4_general_ci ROW_FORMAT = dynamic COMMENT = '隐患跟进表';
-- robot.robot_lora_relay 定义

create table `robot_lora_relay` (
  `id` bigint not null auto_increment COMMENT '主键ID',
`robot_id` varchar(55) character set utf8mb4 collate utf8mb4_general_ci default null,
`relay_no` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '中继编号',
`relay_name` varchar(255) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '中继名称',
`voltage` decimal(10, 3) default null COMMENT '电量：电压(V)',
`normal_voltage_lower` decimal(10, 3) default '2.600' COMMENT '正常电压下限(V)',
`normal_voltage_upper` decimal(10, 3) default '3.600' COMMENT '正常电压上限(V)',
`report_time` datetime default null COMMENT '上报时间',
`raw_message` text character set utf8mb4 collate utf8mb4_general_ci COMMENT '原始报文',
`remark` varchar(500) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '备注',
`create_by` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '创建者',
`create_time` datetime default null COMMENT '创建时间',
`update_by` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '更新者',
`update_time` datetime default null COMMENT '更新时间',
primary key (`id`)
    using BTREE,
unique key `uk_robot_lora_relay_no` (`relay_no`)
    using BTREE
) engine = InnoDB auto_increment = 1 default CHARSET = utf8mb4 collate = utf8mb4_general_ci ROW_FORMAT = dynamic COMMENT = 'LoRa中继管理表';
-- robot.robot_map 定义

create table `robot_map` (
  `id` bigint not null auto_increment,
`map_name` varchar(255) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '名称',
`coding` varchar(50) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '编码',
`map_img_2d` varchar(255) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '地图2d',
`map_2d_las` varchar(255) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '2d  las 文件',
`map_2d_info` text character set utf8mb4 collate utf8mb4_general_ci COMMENT '2d 拓展信息',
`map_img_3d` varchar(255) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '地图3d',
`map_versions_id` bigint default null COMMENT '发布的地图版本id',
`status` char(1) character set utf8mb4 collate utf8mb4_general_ci not null COMMENT '发布表示 0：未发布，1：已发布',
`versions` int default null COMMENT '版本',
`ext1` varchar(255) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '平面图文件',
`ext2` varchar(16) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '备用2',
`ext3` varchar(16) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '备用3',
`ext4` varchar(255) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '备用4',
`remark` varchar(500) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '备注',
`create_by` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '创建者',
`create_time` datetime default null COMMENT '创建时间',
`update_by` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '更新者',
`update_time` datetime default null COMMENT '更新时间',
`del_flag` char(1) character set utf8mb4 collate utf8mb4_general_ci default '0' COMMENT '删除标志（0代表存在 2代表删除）',
primary key (`id`)
    using BTREE
) engine = InnoDB auto_increment = 1 default CHARSET = utf8mb4 collate = utf8mb4_general_ci ROW_FORMAT = dynamic COMMENT = '地图表';
-- robot.robot_map_versions 定义

create table `robot_map_versions` (
  `id` bigint not null auto_increment,
`robot_map_id` bigint not null COMMENT '地图id',
`status` char(1) character set utf8mb4 collate utf8mb4_general_ci not null COMMENT '发布表示 0：未发布，1：已发布',
`versions` int default null COMMENT '版本',
`map_content_xml` text character set utf8mb4 collate utf8mb4_general_ci COMMENT '地图的点位数据',
`ext1` varchar(16) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '备用1',
`ext2` varchar(16) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '备用2',
`ext3` varchar(16) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '备用3',
`ext4` varchar(16) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '备用4',
`remark` varchar(500) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '备注',
`create_by` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '创建者',
`create_time` datetime default null COMMENT '创建时间',
`update_by` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '更新者',
`update_time` datetime default null COMMENT '更新时间',
`del_flag` char(1) character set utf8mb4 collate utf8mb4_general_ci default '0' COMMENT '删除标志（0代表存在 2代表删除）',
primary key (`id`)
    using BTREE
) engine = InnoDB auto_increment = 1 default CHARSET = utf8mb4 collate = utf8mb4_general_ci ROW_FORMAT = dynamic COMMENT = '地图版本';
-- robot.robot_partial_discharge 定义

create table `robot_partial_discharge` (
  `id` bigint not null auto_increment COMMENT '主键ID',
`robot_id` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '设备编号',
`msg_id` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '指令ID/消息ID',
`result` varchar(32) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '执行结果 start/success/fail',
`reason` varchar(512) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '失败原因',
`max` varchar(10) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '放电峰值',
`avagate` varchar(10) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '放电均值',
`count` varchar(11) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '放电次数',
`create_time` datetime default null COMMENT '创建时间',
`update_time` datetime default null COMMENT '更新时间',
`ext1` varchar(16) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '备用1',
`ext2` varchar(255) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '备用2',
`ext3` varchar(500) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '备用3',
`ext4` varchar(255) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '备用4',
`create_by` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '创建者',
`update_by` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '更新者',
`del_flag` char(1) character set utf8mb4 collate utf8mb4_general_ci default '0' COMMENT '删除标志（0存在 2删除）',
primary key (`id`)
    using BTREE
) engine = InnoDB auto_increment = 1 default CHARSET = utf8mb4 collate = utf8mb4_general_ci ROW_FORMAT = dynamic COMMENT = '设备局放检测数据表';
-- robot.robot_platen_log 定义

create table `robot_platen_log` (
  `id` bigint not null auto_increment COMMENT '主键ID',
`robot_id` varchar(55) character set utf8mb4 collate utf8mb4_general_ci default null,
`action_type` varchar(55) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '动作类型action',
`message` varchar(500) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '日志描述',
`ext1` varchar(225) collate utf8mb4_general_ci default null,
`ext2` varchar(225) collate utf8mb4_general_ci default null,
`ext3` varchar(225) collate utf8mb4_general_ci default null,
`ext4` varchar(225) collate utf8mb4_general_ci default null,
`create_by` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '创建者',
`create_time` datetime default null COMMENT '创建时间',
`del_flag` char(1) character set utf8mb4 collate utf8mb4_general_ci default '0' COMMENT '删除标志：0=未删除，1=已删除',
primary key (`id`)
    using BTREE
) engine = InnoDB auto_increment = 1 default CHARSET = utf8mb4 collate = utf8mb4_general_ci ROW_FORMAT = dynamic COMMENT = '二次压板日志记录';
-- robot.robot_plugin_collect 定义

create table `robot_plugin_collect` (
  `id` bigint not null auto_increment COMMENT '主键ID',
`robot_id` varchar(55) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '机器人ID',
`plugin_type` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '插件类型',
`c_name` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '指标名称',
`c_label` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '指标名称',
`c_value` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '指标值',
`c_unit` varchar(10) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '计量单位',
`c_status` varchar(10) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '状态标志',
`sensor_id` varchar(10) collate utf8mb4_general_ci default null COMMENT '硬件模组ID',
`channel_code` varchar(10) collate utf8mb4_general_ci default null COMMENT '通道编号',
`ext1` varchar(55) collate utf8mb4_general_ci default null COMMENT '备用1',
`ext2` varchar(55) collate utf8mb4_general_ci default null COMMENT '备用2',
`ext3` varchar(55) collate utf8mb4_general_ci default null COMMENT '备用3',
`ext4` varchar(55) collate utf8mb4_general_ci default null COMMENT '备用4',
`ext5` varchar(55) collate utf8mb4_general_ci default null COMMENT '备用5',
`create_by` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '创建者',
`create_time` datetime default null COMMENT '创建时间',
`update_by` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '更新者',
`update_time` datetime default null COMMENT '更新时间',
`del_flag` char(1) character set utf8mb4 collate utf8mb4_general_ci default '0' COMMENT '删除标志：0=未删除，1=已删除',
primary key (`id`)
    using BTREE
) engine = InnoDB auto_increment = 1 default CHARSET = utf8mb4 collate = utf8mb4_general_ci ROW_FORMAT = dynamic COMMENT = '插件采集表';
-- robot.robot_point 定义

create table `robot_point` (
  `id` bigint not null auto_increment,
`robot_map_id` bigint default null COMMENT '点位相关地图ID',
`ctn_point_no` varchar(255) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '机器人平台对应的箱体位置编号',
`point_list` varchar(500) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '点位集合',
`ext1` varchar(16) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '备用1',
`ext2` varchar(16) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '备用2',
`ext3` varchar(16) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '备用3',
`ext4` varchar(16) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '备用4',
`remark` varchar(500) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '备注',
`create_by` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '创建者',
`create_time` datetime default null COMMENT '创建时间',
`update_by` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '更新者',
`update_time` datetime default null COMMENT '更新时间',
`del_flag` char(1) character set utf8mb4 collate utf8mb4_general_ci default '0' COMMENT '删除标志（0代表存在 2代表删除）',
primary key (`id`)
    using BTREE
) engine = InnoDB default CHARSET = utf8mb4 collate = utf8mb4_general_ci ROW_FORMAT = dynamic COMMENT = '点位集合';
-- robot.robot_task 定义

create table `robot_task` (
  `id` bigint not null auto_increment,
`robot_id` varchar(55) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '机器人',
`job_id` varchar(255) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '海港EDI-任务id',
`task_type` varchar(255) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '任务类型',
`task_status` varchar(255) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '任务状态',
`status` varchar(10) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '机器人当前执行任务状态 0：机器人空闲状态；1：机器人有任务',
`ext1` varchar(16) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '任务来源模板id',
`ext2` varchar(16) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '任务来源：1:海港IDE 2:模板',
`ext3` varchar(16) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '任务名称',
`ext4` varchar(16) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '备用4',
`remark` varchar(500) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '备注',
`create_by` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '创建者',
`create_time` datetime default null COMMENT '创建时间',
`update_by` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '更新者',
`update_time` datetime default null COMMENT '更新时间',
`del_flag` char(1) character set utf8mb4 collate utf8mb4_general_ci default '0' COMMENT '删除标志（0代表存在 2代表删除）',
`online_flag` char(1) collate utf8mb4_general_ci default '0' COMMENT '离线任务：0在线；1离线',
primary key (`id`)
    using BTREE
) engine = InnoDB auto_increment = 1 default CHARSET = utf8mb4 collate = utf8mb4_general_ci ROW_FORMAT = dynamic COMMENT = '主任务';
-- robot.robot_task_item 定义

create table `robot_task_item` (
  `id` bigint not null auto_increment,
`robot_id` varchar(55) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '车辆',
`task_id` varchar(255) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '任务id',
`job_id` varchar(255) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT 'pentcs-任务id',
`operation` varchar(255) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '操作类型',
`step_id` varchar(255) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '步骤id',
`step_type` varchar(255) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '步骤类型',
`action` varchar(255) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '步骤操作',
`timestamp` datetime(3) default null COMMENT '任务下发时间',
`destination` varchar(255) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '目的地',
`description` varchar(255) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '备注',
`position` varchar(255) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '场地位置',
`state` varchar(255) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '任务订单处理状态',
`ext1` varchar(16) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '备用1',
`ext2` varchar(255) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '备用2',
`ext3` mediumtext character set utf8mb4 collate utf8mb4_general_ci COMMENT '备用3',
`ext4` varchar(255) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '备用4',
`remark` varchar(500) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '备注',
`create_by` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '创建者',
`create_time` datetime default null COMMENT '创建时间',
`update_by` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '更新者',
`update_time` datetime default null COMMENT '更新时间',
`del_flag` char(1) character set utf8mb4 collate utf8mb4_general_ci default '0' COMMENT '删除标志（0代表存在 2代表删除）',
primary key (`id`)
    using BTREE
) engine = InnoDB auto_increment = 1 default CHARSET = utf8mb4 collate = utf8mb4_general_ci ROW_FORMAT = dynamic COMMENT = '子任务';
-- robot.robot_task_status 定义

create table `robot_task_status` (
  `id` bigint not null auto_increment,
`robot_id` varchar(255) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '机器人id',
`job_id` varchar(255) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '任务id',
`command_type` varchar(255) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '指令类型，原样返回',
`msg_id` varchar(255) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '指令ID，原样返回',
`timestamp` datetime(3) default null COMMENT '更新时间戳',
`result` varchar(255) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '更新点位成功/失败',
`msg_info` varchar(255) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '成功/失败原因',
`step_id` varchar(255) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '步骤',
`data_info` mediumtext character set utf8mb4 collate utf8mb4_general_ci COMMENT '数据详情',
`remark` varchar(500) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '备注',
`create_by` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '创建者',
`create_time` datetime default null COMMENT '创建时间',
`update_by` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '更新者',
`update_time` datetime default null COMMENT '更新时间',
`del_flag` char(1) character set utf8mb4 collate utf8mb4_general_ci default '0' COMMENT '删除标志（0代表存在 2代表删除）',
primary key (`id`)
    using BTREE
) engine = InnoDB auto_increment = 1 default CHARSET = utf8mb4 collate = utf8mb4_general_ci ROW_FORMAT = dynamic COMMENT = '上报查验过程节点状态';
-- robot.robot_task_template 定义

create table `robot_task_template` (
  `id` bigint not null auto_increment,
`job_name` varchar(64) character set utf8mb4 collate utf8mb4_general_ci not null default '' COMMENT '任务名称',
`job_group` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default 'DEFAULT' COMMENT '任务组名',
`work_flow_no` varchar(255) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '机器人平台对应的工作流编号',
`cron_expression` varchar(255) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT 'cron执行表达式',
`info_json` text character set utf8mb4 collate utf8mb4_general_ci COMMENT '模板json',
`status` char(1) character set utf8mb4 collate utf8mb4_general_ci default '0' COMMENT '状态（0正常 1暂停）',
`return_point` varchar(255) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '返航点',
`ext1` varchar(16) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '备用1',
`ext2` varchar(16) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '备用2',
`ext3` varchar(16) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '备用3',
`ext4` varchar(16) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '备用4',
`remark` varchar(500) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '备注',
`create_by` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '创建者',
`create_time` datetime default null COMMENT '创建时间',
`update_by` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '更新者',
`update_time` datetime default null COMMENT '更新时间',
`del_flag` char(1) character set utf8mb4 collate utf8mb4_general_ci default '0' COMMENT '删除标志（0代表存在 2代表删除）',
`online_flag` char(1) collate utf8mb4_general_ci default '0' COMMENT '离线任务：0在线；1离线',
`sync_status` char(1) collate utf8mb4_general_ci default '0',
primary key (`id`)
    using BTREE
) engine = InnoDB auto_increment = 1 default CHARSET = utf8mb4 collate = utf8mb4_general_ci ROW_FORMAT = dynamic COMMENT = '任务模板';
-- robot.robot_transducer 定义

create table `robot_transducer` (
  `id` bigint not null,
`ext1` varchar(16) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '备用1',
`ext2` varchar(16) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '备用2',
`ext3` varchar(16) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '备用3',
`ext4` varchar(16) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '备用4',
`remark` varchar(500) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '备注',
`create_by` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '创建者',
`create_time` datetime default null COMMENT '创建时间',
`update_by` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '更新者',
`update_time` datetime default null COMMENT '更新时间',
`del_flag` char(1) character set utf8mb4 collate utf8mb4_general_ci default '0' COMMENT '删除标志（0代表存在 2代表删除）',
primary key (`id`)
    using BTREE
) engine = InnoDB default CHARSET = utf8mb4 collate = utf8mb4_general_ci ROW_FORMAT = dynamic COMMENT = '机器人传感器';
-- robot.robot_vehicle 定义

create table `robot_vehicle` (
  `id` bigint not null auto_increment,
`map_id` bigint default null COMMENT '关联地图',
`robot_id` varchar(30) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '机器人ID',
`vehicle_name` varchar(255) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '名称',
`vehicle_brand` varchar(255) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '品牌',
`vehicle_serial_number` varchar(20) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '序列号',
`vehicle_type` varchar(10) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '型号',
`vehicle_ip` varchar(255) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT 'ip地址',
`device_type` varchar(10) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '设备类型(机器狗/agv）',
`vehicle_capture` varchar(255) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '机器人图片地址',
`vehicle_json` text character set utf8mb4 collate utf8mb4_general_ci COMMENT '其他属性（json）',
`voice_topic` varchar(255) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '语音播报主题',
`blocked_voice_content` varchar(255) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '遇到障碍播报的语音',
`status` varchar(10) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '在线状态(0:离线，1:在线)',
`ext1` varchar(55) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '备用1',
`ext2` varchar(16) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '备用2',
`ext3` varchar(16) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '备用3',
`ext4` varchar(55) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '备用4',
`ext5` varchar(50) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '备用5',
`ext6` varchar(50) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '备用6',
`ext7` varchar(50) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '备用7',
`ext8` varchar(50) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '备用8',
`remark` varchar(500) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '备注',
`last_sync_date_time` datetime default null on
update
    CURRENT_TIMESTAMP COMMENT '上次信息同步时间',
    `create_by` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '创建者',
    `create_time` datetime default null COMMENT '创建时间',
    `update_by` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '更新者',
    `update_time` datetime default null COMMENT '更新时间',
    `del_flag` char(1) character set utf8mb4 collate utf8mb4_general_ci default '0' COMMENT '删除标志（0代表存在 2代表删除）',
    primary key (`id`)
        using BTREE
) engine = InnoDB auto_increment = 1 default CHARSET = utf8mb4 collate = utf8mb4_general_ci ROW_FORMAT = dynamic COMMENT = '机器人';
-- robot.robot_vehicle_moving_trail 定义

create table `robot_vehicle_moving_trail` (
  `id` bigint not null auto_increment,
`robot_id` varchar(255) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '机器人id',
`command_type` varchar(255) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '指令类型，初始位置',
`msg_id` varchar(255) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '指令ID',
`timestamp` datetime default null COMMENT '更新时间戳',
`position_x` varchar(255) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT 'X坐标',
`position_y` varchar(255) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT 'Y坐标',
`position_z` varchar(255) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT 'Z坐标',
`angle` varchar(255) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '角度',
`point_name` varchar(255) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '点位名称',
`velocity_x` varchar(255) character set utf8mb4 collate utf8mb4_general_ci default null,
`velocity_y` varchar(255) character set utf8mb4 collate utf8mb4_general_ci default null,
`velocity_z` varchar(255) character set utf8mb4 collate utf8mb4_general_ci default null,
`proc_state` varchar(255) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '空闲：IDLE/任务处理中：PROCESSING',
`task_id` varchar(255) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '任务处理中返回给出当前taskId,否则为空',
`energy_level` varchar(255) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '电量百分比',
`ext1` varchar(255) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '备用1',
`ext2` varchar(16) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '备用2',
`ext3` varchar(16) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '备用3',
`ext4` varchar(16) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '备用4',
`remark` varchar(500) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '备注',
`create_by` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '创建者',
`create_time` datetime default null COMMENT '创建时间',
`update_by` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '更新者',
`update_time` datetime default null COMMENT '更新时间',
`del_flag` char(1) character set utf8mb4 collate utf8mb4_general_ci default '0' COMMENT '删除标志（0代表存在 2代表删除）',
primary key (`id`)
    using BTREE
) engine = InnoDB auto_increment = 1 default CHARSET = utf8mb4 collate = utf8mb4_general_ci ROW_FORMAT = dynamic COMMENT = '机器人移动轨迹';
-- robot.sys_arm_target_cable 定义

create table `sys_arm_target_cable` (
  `id` bigint not null auto_increment COMMENT '主键ID',
`robot_id` varchar(55) character set utf8mb4 collate utf8mb4_general_ci default null,
`cable_code` varchar(50) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '线缆编号',
`cable_name` varchar(255) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '线缆名称',
`description` varchar(500) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '线缆描述',
`status` tinyint default '1' COMMENT '状态：1=启用，0=禁用',
`remark` varchar(500) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '备注',
`create_by` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '创建人',
`create_time` datetime default null COMMENT '创建时间',
`update_by` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '更新人',
`update_time` datetime default null COMMENT '更新时间',
`del_flag` char(1) character set utf8mb4 collate utf8mb4_general_ci default '0' COMMENT '删除标志：0=未删除，1=已删除',
primary key (`id`)
    using BTREE
) engine = InnoDB auto_increment = 1 default CHARSET = utf8mb4 collate = utf8mb4_general_ci ROW_FORMAT = dynamic COMMENT = '机械臂目标线缆管理表';
-- robot.sys_config 定义

create table `sys_config` (
  `config_id` int not null auto_increment COMMENT '参数主键',
`config_name` varchar(100) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '参数名称',
`config_key` varchar(100) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '参数键名',
`config_value` varchar(500) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '参数键值',
`config_type` char(1) character set utf8mb4 collate utf8mb4_general_ci default 'N' COMMENT '系统内置（Y是 N否）',
`create_by` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '创建者',
`create_time` datetime default null COMMENT '创建时间',
`update_by` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '更新者',
`update_time` datetime default null COMMENT '更新时间',
`remark` varchar(500) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '备注',
primary key (`config_id`)
    using BTREE
) engine = InnoDB auto_increment = 1 default CHARSET = utf8mb4 collate = utf8mb4_general_ci ROW_FORMAT = dynamic COMMENT = '参数配置表';
-- robot.sys_dept 定义

create table `sys_dept` (
  `dept_id` bigint not null auto_increment COMMENT '部门id',
`parent_id` bigint default '0' COMMENT '父部门id',
`ancestors` varchar(50) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '祖级列表',
`dept_name` varchar(30) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '部门名称',
`order_num` int default '0' COMMENT '显示顺序',
`leader` varchar(20) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '负责人',
`phone` varchar(11) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '联系电话',
`email` varchar(50) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '邮箱',
`status` char(1) character set utf8mb4 collate utf8mb4_general_ci default '0' COMMENT '部门状态（0正常 1停用）',
`del_flag` char(1) character set utf8mb4 collate utf8mb4_general_ci default '0' COMMENT '删除标志（0代表存在 2代表删除）',
`create_by` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '创建者',
`create_time` datetime default null COMMENT '创建时间',
`update_by` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '更新者',
`update_time` datetime default null COMMENT '更新时间',
primary key (`dept_id`)
    using BTREE
) engine = InnoDB auto_increment = 1 default CHARSET = utf8mb4 collate = utf8mb4_general_ci ROW_FORMAT = dynamic COMMENT = '部门表';
-- robot.sys_dict_data 定义

create table `sys_dict_data` (
  `dict_code` bigint not null auto_increment COMMENT '字典编码',
`dict_sort` int default '0' COMMENT '字典排序',
`dict_label` varchar(100) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '字典标签',
`dict_value` varchar(100) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '字典键值',
`dict_type` varchar(100) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '字典类型',
`css_class` varchar(100) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '样式属性（其他样式扩展）',
`list_class` varchar(100) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '表格回显样式',
`is_default` char(1) character set utf8mb4 collate utf8mb4_general_ci default 'N' COMMENT '是否默认（Y是 N否）',
`status` char(1) character set utf8mb4 collate utf8mb4_general_ci default '0' COMMENT '状态（0正常 1停用）',
`create_by` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '创建者',
`create_time` datetime default null COMMENT '创建时间',
`update_by` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '更新者',
`update_time` datetime default null COMMENT '更新时间',
`remark` varchar(500) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '备注',
primary key (`dict_code`)
    using BTREE
) engine = InnoDB auto_increment = 1 default CHARSET = utf8mb4 collate = utf8mb4_general_ci ROW_FORMAT = dynamic COMMENT = '字典数据表';
-- robot.sys_dict_type 定义

create table `sys_dict_type` (
  `dict_id` bigint not null auto_increment COMMENT '字典主键',
`dict_name` varchar(100) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '字典名称',
`dict_type` varchar(100) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '字典类型',
`status` char(1) character set utf8mb4 collate utf8mb4_general_ci default '0' COMMENT '状态（0正常 1停用）',
`create_by` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '创建者',
`create_time` datetime default null COMMENT '创建时间',
`update_by` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '更新者',
`update_time` datetime default null COMMENT '更新时间',
`remark` varchar(500) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '备注',
primary key (`dict_id`)
    using BTREE,
unique key `dict_type` (`dict_type`)
    using BTREE
) engine = InnoDB auto_increment = 1 default CHARSET = utf8mb4 collate = utf8mb4_general_ci ROW_FORMAT = dynamic COMMENT = '字典类型表';
-- robot.sys_door_control 定义

create table `sys_door_control` (
  `id` bigint not null auto_increment COMMENT '主键ID',
`robot_id` varchar(55) character set utf8mb4 collate utf8mb4_general_ci default null,
`door_name` varchar(255) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '门名称',
`ip_address` varchar(255) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT 'IP地址',
`speed` int default '80' COMMENT '开门速度(0-100)',
`target_percent` int default '0' COMMENT '开门位置(0-100) 0代表完全关闭，100代表完全打开',
`status` tinyint default '1' COMMENT '状态：1=启用，0=禁用',
`remark` varchar(500) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '备注',
`create_by` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '创建人',
`create_time` datetime default null COMMENT '创建时间',
`update_by` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '更新人',
`update_time` datetime default null COMMENT '更新时间',
`del_flag` char(1) character set utf8mb4 collate utf8mb4_general_ci default '0' COMMENT '删除标志：0=未删除，1=已删除',
primary key (`id`)
    using BTREE
) engine = InnoDB auto_increment = 1 default CHARSET = utf8mb4 collate = utf8mb4_general_ci ROW_FORMAT = dynamic COMMENT = '开门机管理表';
-- robot.sys_elevator_control 定义

create table `sys_elevator_control` (
  `id` bigint not null auto_increment COMMENT '主键ID',
`robot_id` varchar(55) character set utf8mb4 collate utf8mb4_general_ci default null,
`elevator_name` varchar(255) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '电梯名称',
`address` varchar(50) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '电梯IP(01,02)',
`floor` int default null COMMENT '目标楼层',
`hode_time` int default '10' COMMENT '延迟关门时间(秒)',
`status` tinyint default '1' COMMENT '状态：1=启用，0=禁用',
`remark` varchar(500) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '备注',
`create_by` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '创建者',
`create_time` datetime default null COMMENT '创建时间',
`update_by` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '更新者',
`update_time` datetime default null COMMENT '更新时间',
`del_flag` char(1) character set utf8mb4 collate utf8mb4_general_ci default '0' COMMENT '删除标志：0=未删除，1=已删除',
primary key (`id`)
    using BTREE
) engine = InnoDB auto_increment = 1 default CHARSET = utf8mb4 collate = utf8mb4_general_ci ROW_FORMAT = dynamic COMMENT = '电梯控制管理表';
-- robot.sys_gas_sensor 定义

create table `sys_gas_sensor` (
  `id` bigint not null auto_increment COMMENT '主键ID',
`robot_id` varchar(55) character set utf8mb4 collate utf8mb4_general_ci default null,
`sensor_code` int default null COMMENT '传感器编号',
`sensor_name` varchar(255) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '传感器名称',
`description` varchar(500) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '描述',
`status` tinyint default '1' COMMENT '状态：1=启用，0=禁用',
`remark` varchar(500) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '备注',
`create_by` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '创建人',
`create_time` datetime default null COMMENT '创建时间',
`update_by` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '更新人',
`update_time` datetime default null COMMENT '更新时间',
`del_flag` char(1) character set utf8mb4 collate utf8mb4_general_ci default '0' COMMENT '删除标志：0=未删除，1=已删除',
primary key (`id`)
    using BTREE
) engine = InnoDB auto_increment = 1 default CHARSET = utf8mb4 collate = utf8mb4_general_ci ROW_FORMAT = dynamic COMMENT = '气体传感器管理表';
-- robot.sys_job 定义

create table `sys_job` (
  `job_id` bigint not null auto_increment COMMENT '任务ID',
`job_name` varchar(64) character set utf8mb4 collate utf8mb4_general_ci not null default '' COMMENT '任务名称',
`job_group` varchar(64) character set utf8mb4 collate utf8mb4_general_ci not null default 'DEFAULT' COMMENT '任务组名',
`invoke_target` varchar(500) character set utf8mb4 collate utf8mb4_general_ci not null COMMENT '调用目标字符串',
`cron_expression` varchar(255) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT 'cron执行表达式',
`misfire_policy` varchar(20) character set utf8mb4 collate utf8mb4_general_ci default '3' COMMENT '计划执行错误策略（1立即执行 2执行一次 3放弃执行）',
`concurrent` char(1) character set utf8mb4 collate utf8mb4_general_ci default '1' COMMENT '是否并发执行（0允许 1禁止）',
`status` char(1) character set utf8mb4 collate utf8mb4_general_ci default '0' COMMENT '状态（0正常 1暂停）',
`create_by` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '创建者',
`create_time` datetime default null COMMENT '创建时间',
`update_by` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '更新者',
`update_time` datetime default null COMMENT '更新时间',
`remark` varchar(500) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '备注信息',
`online_flag` char(1) collate utf8mb4_general_ci default '0' COMMENT '离线任务：0在线；1离线',
primary key (`job_id`,
`job_name`,
`job_group`)
    using BTREE
) engine = InnoDB auto_increment = 1 default CHARSET = utf8mb4 collate = utf8mb4_general_ci ROW_FORMAT = dynamic COMMENT = '定时任务调度表';
-- robot.sys_job_log 定义

create table `sys_job_log` (
  `job_log_id` bigint not null auto_increment COMMENT '任务日志ID',
`job_name` varchar(64) character set utf8mb4 collate utf8mb4_general_ci not null COMMENT '任务名称',
`job_group` varchar(64) character set utf8mb4 collate utf8mb4_general_ci not null COMMENT '任务组名',
`invoke_target` varchar(500) character set utf8mb4 collate utf8mb4_general_ci not null COMMENT '调用目标字符串',
`job_message` varchar(500) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '日志信息',
`status` char(1) character set utf8mb4 collate utf8mb4_general_ci default '0' COMMENT '执行状态（0正常 1失败）',
`exception_info` varchar(2000) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '异常信息',
`create_time` datetime default null COMMENT '创建时间',
primary key (`job_log_id`)
    using BTREE
) engine = InnoDB auto_increment = 1 default CHARSET = utf8mb4 collate = utf8mb4_general_ci ROW_FORMAT = dynamic COMMENT = '定时任务调度日志表';
-- robot.sys_logininfor 定义

create table `sys_logininfor` (
  `info_id` bigint not null auto_increment COMMENT '访问ID',
`user_name` varchar(50) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '用户账号',
`ipaddr` varchar(128) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '登录IP地址',
`login_location` varchar(255) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '登录地点',
`browser` varchar(50) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '浏览器类型',
`os` varchar(50) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '操作系统',
`status` char(1) character set utf8mb4 collate utf8mb4_general_ci default '0' COMMENT '登录状态（0成功 1失败）',
`msg` varchar(255) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '提示消息',
`login_time` datetime default null COMMENT '访问时间',
primary key (`info_id`)
    using BTREE,
key `idx_sys_logininfor_s` (`status`)
    using BTREE,
key `idx_sys_logininfor_lt` (`login_time`)
    using BTREE
) engine = InnoDB auto_increment = 1 default CHARSET = utf8mb4 collate = utf8mb4_general_ci ROW_FORMAT = dynamic COMMENT = '系统访问记录';
-- robot.sys_menu 定义

create table `sys_menu` (
  `menu_id` bigint not null auto_increment COMMENT '菜单ID',
`menu_name` varchar(50) character set utf8mb4 collate utf8mb4_general_ci not null COMMENT '菜单名称',
`parent_id` bigint default '0' COMMENT '父菜单ID',
`order_num` int default '0' COMMENT '显示顺序',
`path` varchar(200) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '路由地址',
`component` varchar(255) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '组件路径',
`query` varchar(255) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '路由参数',
`route_name` varchar(50) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '路由名称',
`is_frame` int default '1' COMMENT '是否为外链（0是 1否）',
`is_cache` int default '0' COMMENT '是否缓存（0缓存 1不缓存）',
`menu_type` char(1) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '菜单类型（M目录 C菜单 F按钮）',
`visible` char(1) character set utf8mb4 collate utf8mb4_general_ci default '0' COMMENT '菜单状态（0显示 1隐藏）',
`status` char(1) character set utf8mb4 collate utf8mb4_general_ci default '0' COMMENT '菜单状态（0正常 1停用）',
`perms` varchar(100) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '权限标识',
`icon` varchar(100) character set utf8mb4 collate utf8mb4_general_ci default '#' COMMENT '菜单图标',
`create_by` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '创建者',
`create_time` datetime default null COMMENT '创建时间',
`update_by` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '更新者',
`update_time` datetime default null COMMENT '更新时间',
`remark` varchar(500) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '备注',
primary key (`menu_id`)
    using BTREE
) engine = InnoDB auto_increment = 1 default CHARSET = utf8mb4 collate = utf8mb4_general_ci ROW_FORMAT = dynamic COMMENT = '菜单权限表';
-- robot.sys_notice 定义

create table `sys_notice` (
  `notice_id` int not null auto_increment COMMENT '公告ID',
`notice_title` varchar(255) collate utf8mb4_general_ci not null,
`notice_type` char(1) character set utf8mb4 collate utf8mb4_general_ci not null COMMENT '公告类型（1通知 2公告）',
`notice_content` longtext character set utf8mb4 collate utf8mb4_general_ci COMMENT '公告内容',
`status` char(1) character set utf8mb4 collate utf8mb4_general_ci default '0' COMMENT '公告状态（0正常 1关闭）',
`create_by` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '创建者',
`create_time` datetime default null COMMENT '创建时间',
`update_by` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '更新者',
`update_time` datetime default null COMMENT '更新时间',
`remark` varchar(255) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '备注',
`robot_id` varchar(55) collate utf8mb4_general_ci not null COMMENT '机器人ID',
`robot_name` varchar(255) collate utf8mb4_general_ci not null COMMENT '机器人名称',
`error_code` varchar(255) collate utf8mb4_general_ci not null COMMENT '告警错误码',
primary key (`notice_id`)
    using BTREE
) engine = InnoDB auto_increment = 1 default CHARSET = utf8mb4 collate = utf8mb4_general_ci ROW_FORMAT = dynamic COMMENT = '通知公告表';
-- robot.sys_notice_read 定义

create table `sys_notice_read` (
  `read_id` bigint not null auto_increment COMMENT '已读主键',
`notice_id` int not null COMMENT '公告id',
`user_id` bigint not null COMMENT '用户id',
`read_time` datetime not null COMMENT '阅读时间',
primary key (`read_id`),
unique key `uk_user_notice` (`user_id`,
`notice_id`) COMMENT '同一用户同一公告只记录一次'
) engine = InnoDB auto_increment = 1 default CHARSET = utf8mb4 collate = utf8mb4_general_ci COMMENT = '公告已读记录表';
-- robot.sys_oper_log 定义

create table `sys_oper_log` (
  `oper_id` bigint not null auto_increment COMMENT '日志主键',
`title` varchar(50) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '模块标题',
`business_type` int default '0' COMMENT '业务类型（0其它 1新增 2修改 3删除）',
`method` varchar(200) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '方法名称',
`request_method` varchar(10) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '请求方式',
`operator_type` int default '0' COMMENT '操作类别（0其它 1后台用户 2手机端用户）',
`oper_name` varchar(50) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '操作人员',
`dept_name` varchar(50) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '部门名称',
`oper_url` varchar(255) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '请求URL',
`oper_ip` varchar(128) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '主机地址',
`oper_location` varchar(255) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '操作地点',
`oper_param` text character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '请求参数',
`json_result` text character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '返回参数',
`status` int default '0' COMMENT '操作状态（0正常 1异常）',
`error_msg` varchar(2000) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '错误消息',
`oper_time` datetime default null COMMENT '操作时间',
`cost_time` bigint default '0' COMMENT '消耗时间',
primary key (`oper_id`)
    using BTREE,
key `idx_sys_oper_log_bt` (`business_type`)
    using BTREE,
key `idx_sys_oper_log_s` (`status`)
    using BTREE,
key `idx_sys_oper_log_ot` (`oper_time`)
    using BTREE
) engine = InnoDB auto_increment = 1 default CHARSET = utf8mb4 collate = utf8mb4_general_ci ROW_FORMAT = dynamic COMMENT = '操作日志记录';
-- robot.sys_platen_label 定义

create table `sys_platen_label` (
  `id` bigint not null auto_increment COMMENT '主键ID',
`robot_id` varchar(55) character set utf8mb4 collate utf8mb4_general_ci default null,
`label_code` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '压板编号',
`label_name` varchar(255) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '压板名称',
`status` int default '1' COMMENT '状态：1=启用，0=禁用',
`remark` varchar(500) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '备注',
`create_by` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '创建者',
`create_time` datetime default null COMMENT '创建时间',
`update_by` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '更新者',
`update_time` datetime default null COMMENT '更新时间',
`del_flag` char(1) character set utf8mb4 collate utf8mb4_general_ci default '0' COMMENT '删除标志：0=未删除，1=已删除',
primary key (`id`)
    using BTREE
) engine = InnoDB auto_increment = 4 default CHARSET = utf8mb4 collate = utf8mb4_general_ci ROW_FORMAT = dynamic COMMENT = '压板管理';
-- robot.sys_post 定义

create table `sys_post` (
  `post_id` bigint not null auto_increment COMMENT '岗位ID',
`post_code` varchar(64) character set utf8mb4 collate utf8mb4_general_ci not null COMMENT '岗位编码',
`post_name` varchar(50) character set utf8mb4 collate utf8mb4_general_ci not null COMMENT '岗位名称',
`post_sort` int not null COMMENT '显示顺序',
`status` char(1) character set utf8mb4 collate utf8mb4_general_ci not null COMMENT '状态（0正常 1停用）',
`create_by` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '创建者',
`create_time` datetime default null COMMENT '创建时间',
`update_by` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '更新者',
`update_time` datetime default null COMMENT '更新时间',
`remark` varchar(500) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '备注',
primary key (`post_id`)
    using BTREE
) engine = InnoDB auto_increment = 1 default CHARSET = utf8mb4 collate = utf8mb4_general_ci ROW_FORMAT = dynamic COMMENT = '岗位信息表';
-- robot.sys_preset_point 定义

create table `sys_preset_point` (
  `id` bigint not null auto_increment COMMENT '主键ID',
`robot_id` varchar(55) character set utf8mb4 collate utf8mb4_general_ci default null,
`ptz_code` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '云台编号',
`point_code` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '点位编号',
`point_name` varchar(255) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '点位名称',
`status` int default '1' COMMENT '状态：1=启用，0=禁用',
`remark` varchar(500) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '备注',
`create_by` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '创建者',
`create_time` datetime default null COMMENT '创建时间',
`update_by` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '更新者',
`update_time` datetime default null COMMENT '更新时间',
`del_flag` char(1) character set utf8mb4 collate utf8mb4_general_ci default '0' COMMENT '删除标志：0=未删除，1=已删除',
primary key (`id`)
    using BTREE
) engine = InnoDB auto_increment = 1 default CHARSET = utf8mb4 collate = utf8mb4_general_ci ROW_FORMAT = dynamic COMMENT = '云台预置点位管理';
-- robot.sys_role 定义

create table `sys_role` (
  `role_id` bigint not null auto_increment COMMENT '角色ID',
`role_name` varchar(30) character set utf8mb4 collate utf8mb4_general_ci not null COMMENT '角色名称',
`role_key` varchar(100) character set utf8mb4 collate utf8mb4_general_ci not null COMMENT '角色权限字符串',
`role_sort` int not null COMMENT '显示顺序',
`data_scope` char(1) character set utf8mb4 collate utf8mb4_general_ci default '1' COMMENT '数据范围（1：全部数据权限 2：自定数据权限 3：本部门数据权限 4：本部门及以下数据权限）',
`menu_check_strictly` tinyint(1) default '1' COMMENT '菜单树选择项是否关联显示',
`dept_check_strictly` tinyint(1) default '1' COMMENT '部门树选择项是否关联显示',
`status` char(1) character set utf8mb4 collate utf8mb4_general_ci not null COMMENT '角色状态（0正常 1停用）',
`del_flag` char(1) character set utf8mb4 collate utf8mb4_general_ci default '0' COMMENT '删除标志（0代表存在 2代表删除）',
`create_by` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '创建者',
`create_time` datetime default null COMMENT '创建时间',
`update_by` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '更新者',
`update_time` datetime default null COMMENT '更新时间',
`remark` varchar(500) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '备注',
primary key (`role_id`)
    using BTREE
) engine = InnoDB auto_increment = 1 default CHARSET = utf8mb4 collate = utf8mb4_general_ci ROW_FORMAT = dynamic COMMENT = '角色信息表';
-- robot.sys_role_dept 定义

create table `sys_role_dept` (
  `role_id` bigint not null COMMENT '角色ID',
`dept_id` bigint not null COMMENT '部门ID',
primary key (`role_id`,
`dept_id`)
    using BTREE
) engine = InnoDB default CHARSET = utf8mb4 collate = utf8mb4_general_ci ROW_FORMAT = dynamic COMMENT = '角色和部门关联表';
-- robot.sys_role_menu 定义

create table `sys_role_menu` (
  `role_id` bigint not null COMMENT '角色ID',
`menu_id` bigint not null COMMENT '菜单ID',
primary key (`role_id`,
`menu_id`)
    using BTREE
) engine = InnoDB default CHARSET = utf8mb4 collate = utf8mb4_general_ci ROW_FORMAT = dynamic COMMENT = '角色和菜单关联表';
-- robot.sys_station_control 定义

create table `sys_station_control` (
  `id` bigint not null auto_increment COMMENT '主键ID',
`robot_id` varchar(55) character set utf8mb4 collate utf8mb4_general_ci default null,
`station_door_name` varchar(255) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '充电站门名称',
`ip_address` varchar(255) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT 'IP地址',
`speed` int default '80' COMMENT '开门速度(0-100)',
`target_percent` int default '0' COMMENT '开门位置(0-100) 0代表完全关闭，100代表完全打开',
`status` tinyint default '1' COMMENT '状态：1=启用，0=禁用',
`remark` varchar(500) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '备注',
`create_by` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '创建人',
`create_time` datetime default null COMMENT '创建时间',
`update_by` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '更新人',
`update_time` datetime default null COMMENT '更新时间',
`del_flag` char(1) character set utf8mb4 collate utf8mb4_general_ci default '0' COMMENT '删除标志：0=未删除，1=已删除',
primary key (`id`)
    using BTREE
) engine = InnoDB auto_increment = 1 default CHARSET = utf8mb4 collate = utf8mb4_general_ci ROW_FORMAT = dynamic COMMENT = '充电站控制管理表';
-- robot.sys_user 定义

create table `sys_user` (
  `user_id` bigint not null auto_increment COMMENT '用户ID',
`dept_id` bigint default null COMMENT '部门ID',
`user_name` varchar(30) character set utf8mb4 collate utf8mb4_general_ci not null COMMENT '用户账号',
`nick_name` varchar(30) character set utf8mb4 collate utf8mb4_general_ci not null COMMENT '用户昵称',
`user_type` varchar(2) character set utf8mb4 collate utf8mb4_general_ci default '00' COMMENT '用户类型（00系统用户）',
`email` varchar(50) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '用户邮箱',
`phonenumber` varchar(11) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '手机号码',
`sex` char(1) character set utf8mb4 collate utf8mb4_general_ci default '0' COMMENT '用户性别（0男 1女 2未知）',
`avatar` varchar(100) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '头像地址',
`password` varchar(100) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '密码',
`status` char(1) character set utf8mb4 collate utf8mb4_general_ci default '0' COMMENT '账号状态（0正常 1停用）',
`del_flag` char(1) character set utf8mb4 collate utf8mb4_general_ci default '0' COMMENT '删除标志（0代表存在 2代表删除）',
`login_ip` varchar(128) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '最后登录IP',
`login_date` datetime default null COMMENT '最后登录时间',
`pwd_update_date` datetime default null COMMENT '密码最后更新时间',
`create_by` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '创建者',
`create_time` datetime default null COMMENT '创建时间',
`update_by` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '更新者',
`update_time` datetime default null COMMENT '更新时间',
`remark` varchar(500) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '备注',
primary key (`user_id`)
    using BTREE
) engine = InnoDB auto_increment = 1 default CHARSET = utf8mb4 collate = utf8mb4_general_ci ROW_FORMAT = dynamic COMMENT = '用户信息表';
-- robot.sys_user_post 定义

create table `sys_user_post` (
  `user_id` bigint not null COMMENT '用户ID',
`post_id` bigint not null COMMENT '岗位ID',
primary key (`user_id`,
`post_id`)
    using BTREE
) engine = InnoDB default CHARSET = utf8mb4 collate = utf8mb4_general_ci ROW_FORMAT = dynamic COMMENT = '用户与岗位关联表';
-- robot.sys_user_role 定义

create table `sys_user_role` (
  `user_id` bigint not null COMMENT '用户ID',
`role_id` bigint not null COMMENT '角色ID',
primary key (`user_id`,
`role_id`)
    using BTREE
) engine = InnoDB default CHARSET = utf8mb4 collate = utf8mb4_general_ci ROW_FORMAT = dynamic COMMENT = '用户和角色关联表';
-- robot.sys_valve_info 定义

create table `sys_valve_info` (
  `id` bigint not null auto_increment COMMENT '主键ID',
`robot_id` varchar(55) character set utf8mb4 collate utf8mb4_general_ci default null,
`valve_code` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '阀门编号',
`valve_name` varchar(255) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '阀门名称',
`status` int default '1' COMMENT '状态：1=启用，0=禁用',
`remark` varchar(500) character set utf8mb4 collate utf8mb4_general_ci default null COMMENT '备注',
`create_by` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '创建者',
`create_time` datetime default null COMMENT '创建时间',
`update_by` varchar(64) character set utf8mb4 collate utf8mb4_general_ci default '' COMMENT '更新者',
`update_time` datetime default null COMMENT '更新时间',
`del_flag` char(1) character set utf8mb4 collate utf8mb4_general_ci default '0' COMMENT '删除标志：0=未删除，1=已删除',
primary key (`id`)
    using BTREE
) engine = InnoDB auto_increment = 1 default CHARSET = utf8mb4 collate = utf8mb4_general_ci ROW_FORMAT = dynamic COMMENT = '阀门管理';

INSERT INTO `robot_config` (id,config_name,config_key,config_value,create_by,create_time,update_by,update_time,remark) VALUES
	 (1,'AI盒子地址','robot.ai.box.address','192.168.2.101','admin','2026-04-27 17:51:31',NULL,NULL,'AI盒子IP地址'),
	 (2,'AI盒子端口','robot.ai.box.port','9092','admin','2026-04-27 17:51:31',NULL,NULL,'AI盒子服务端口'),
	 (4,'机器人电池低电量保护阈值','robot.battery.power','20','admin','2026-04-27 17:51:31',NULL,NULL,'电池电量低于此值(百分比)时触发保护'),
	 (5,'Lora网关地址','robot.lora.gateway.address','127.0.0.1','admin','2026-04-27 17:51:31',NULL,NULL,'Lora网关IP地址'),
	 (6,'Lora网关端口','robot.lora.gateway.port','8888','admin','2026-04-27 17:51:31',NULL,NULL,'Lora网关MQTT端口'),
	 (8,'超时重试时效','robot.task.item.timeout','5','testRole001','2026-08-12 14:16:42','testRole002','2026-08-14 10:56:07',NULL),
	 (9,'录像管理地址','robot.task.surveillance.address','127.0.0.1','admin','2026-09-15 12:51:05','admin','2026-09-15 12:52:38','录像管理ip地址'),
	 (10,'录像管理端口','robot.task.surveillance.port','8888','admin','2026-09-15 12:53:05','admin','2026-09-15 12:53:15',NULL);
INSERT INTO `robot_device_type` (id,parent_id,type_level,type_name,type_value,create_by,create_time,update_by,update_time,icon_img,ext1,ext2,ext3,ext4,remark) VALUES
	 (1,0,1,'宇树科技','宇树科技',NULL,'2026-09-04 10:19:44',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL),
	 (2,0,1,'西工大深研院','西工大深研院',NULL,'2026-09-04 10:20:28',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL),
	 (3,0,1,'云深处','云深处',NULL,'2026-09-04 10:20:42',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL),
	 (4,0,1,'智身','智身',NULL,'2026-09-04 10:20:52',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL),
	 (5,0,1,'智元','智元',NULL,'2026-09-04 10:21:01',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL),
	 (6,1,2,'机器狗','机器狗',NULL,'2026-09-04 10:21:17',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL),
	 (7,1,2,'通用人形','通用人形',NULL,'2026-09-04 10:21:33',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL),
	 (8,2,2,'特种机器人','特种机器人',NULL,'2026-09-04 10:21:50',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL),
	 (9,3,2,'机器狗','机器狗',NULL,'2026-09-04 10:22:07',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL),
	 (10,4,2,'机器狗','机器狗',NULL,'2026-09-04 10:22:29',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL);
INSERT INTO `robot_device_type` (id,parent_id,type_level,type_name,type_value,create_by,create_time,update_by,update_time,icon_img,ext1,ext2,ext3,ext4,remark) VALUES
	 (11,5,2,'机器狗','机器狗',NULL,'2026-09-04 10:22:42',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL),
	 (12,6,3,'G2','G2',NULL,'2026-09-04 10:23:29',NULL,NULL,'G2.png',NULL,NULL,NULL,NULL,NULL),
	 (13,6,3,'G2-W','G2-W',NULL,'2026-09-04 10:23:41',NULL,'2026-09-04 11:21:24','G2-W.png',NULL,NULL,NULL,NULL,NULL),
	 (14,6,3,'As2','As2',NULL,'2026-09-04 10:23:51',NULL,NULL,'As2.png',NULL,NULL,NULL,NULL,NULL),
	 (15,6,3,'As2-W','As2-W',NULL,'2026-09-04 10:24:00',NULL,'2026-09-04 11:21:31','As2-W.png',NULL,NULL,NULL,NULL,NULL),
	 (16,6,3,'B2','B2',NULL,'2026-09-04 10:24:16',NULL,NULL,'B2.png',NULL,NULL,NULL,NULL,NULL),
	 (17,6,3,'B2-W','B2-W',NULL,'2026-09-04 10:31:43',NULL,'2026-09-04 11:21:41','B2-W.png',NULL,NULL,NULL,NULL,NULL),
	 (18,6,3,'A2','A2',NULL,'2026-09-04 10:31:54',NULL,NULL,'A2.png',NULL,NULL,NULL,NULL,NULL),
	 (19,6,3,'A2-W','A2-W',NULL,'2026-09-04 10:32:03',NULL,'2026-09-04 11:21:47','A2-W.png',NULL,NULL,NULL,NULL,NULL),
	 (20,7,3,'H2','H2',NULL,'2026-09-04 10:32:24',NULL,NULL,'H2.png',NULL,NULL,NULL,NULL,NULL);
INSERT INTO `robot_device_type` (id,parent_id,type_level,type_name,type_value,create_by,create_time,update_by,update_time,icon_img,ext1,ext2,ext3,ext4,remark) VALUES
	 (21,7,3,'R1','R1',NULL,'2026-09-04 10:32:35',NULL,NULL,'R1.png',NULL,NULL,NULL,NULL,NULL),
	 (22,7,3,'G1','G1',NULL,'2026-09-04 10:32:44',NULL,NULL,'G1.png',NULL,NULL,NULL,NULL,NULL),
	 (23,7,3,'H1','H1',NULL,'2026-09-04 10:32:55',NULL,NULL,'H1.png',NULL,NULL,NULL,NULL,NULL),
	 (24,8,3,'DL-YB01','DL-YB01',NULL,'2026-09-04 10:33:15',NULL,NULL,'DL-YB01.png',NULL,NULL,NULL,NULL,NULL),
	 (25,8,3,'DL-FM01','DL-FM01',NULL,'2026-09-04 10:33:24',NULL,NULL,'DL-FM01.png',NULL,NULL,NULL,NULL,NULL),
	 (26,8,3,'DL-KG01','DL-KG01',NULL,'2026-09-04 10:33:46',NULL,NULL,'DL-KG01.png',NULL,NULL,NULL,NULL,NULL),
	 (27,9,3,'X30','X30',NULL,'2026-09-04 10:34:19',NULL,NULL,'X30.png',NULL,NULL,NULL,NULL,NULL),
	 (28,9,3,'Lite3','Lite3',NULL,'2026-09-04 10:34:29',NULL,NULL,'Lite3.png',NULL,NULL,NULL,NULL,NULL),
	 (29,9,3,'M20','M20',NULL,'2026-09-04 10:34:54',NULL,NULL,'M20.png',NULL,NULL,NULL,NULL,NULL),
	 (30,10,3,'Zsl1 V020','Zsl1 V020',NULL,'2026-09-04 10:35:15',NULL,NULL,'Zsl1.png',NULL,NULL,NULL,NULL,NULL);
INSERT INTO `robot_device_type` (id,parent_id,type_level,type_name,type_value,create_by,create_time,update_by,update_time,icon_img,ext1,ext2,ext3,ext4,remark) VALUES
	 (31,10,3,'Zsl1 V026','Zsl1 V026',NULL,'2026-09-04 10:35:25',NULL,NULL,'Zsl1.png',NULL,NULL,NULL,NULL,NULL),
	 (32,10,3,'Zsl1 V027','Zsl1 V027',NULL,'2026-09-04 10:35:34',NULL,NULL,'Zsl1.png',NULL,NULL,NULL,NULL,NULL),
	 (33,10,3,'Zsl1W V027','Zsl1W V027',NULL,'2026-09-04 10:35:43',NULL,NULL,'Zsl1W.png',NULL,NULL,NULL,NULL,NULL),
	 (34,11,3,'D1MAX V003','D1MAX V003',NULL,'2026-09-04 10:35:55',NULL,NULL,'D1MAXV003.png',NULL,NULL,NULL,NULL,NULL),
	 (35,11,3,'D1MAX V008','D1MAX V008',NULL,'2026-09-04 10:36:04',NULL,NULL,'D1MAXV008.png',NULL,NULL,NULL,NULL,NULL);
INSERT INTO `sys_config` (config_id,config_name,config_key,config_value,config_type,create_by,create_time,update_by,update_time,remark) VALUES
	 (1,'主框架页-默认皮肤样式名称','sys.index.skinName','skin-blue','Y','admin','2025-06-25 03:56:22',NULL,NULL,'蓝色 skin-blue、绿色 skin-green、紫色 skin-purple、红色 skin-red、黄色 skin-yellow'),
	 (2,'用户管理-账号初始密码','sys.user.initPassword','123456','Y','admin','2025-06-25 03:56:22',NULL,NULL,'初始化密码 123456'),
	 (3,'主框架页-侧边栏主题','sys.index.sideTheme','theme-dark','Y','admin','2025-06-25 03:56:22',NULL,NULL,'深色主题theme-dark，浅色主题theme-light'),
	 (4,'账号自助-验证码开关','sys.account.captchaEnabled','true','Y','admin','2025-06-25 03:56:22',NULL,NULL,'是否开启验证码功能（true开启，false关闭）'),
	 (5,'账号自助-是否开启用户注册功能','sys.account.registerUser','false','Y','admin','2025-06-25 03:56:22',NULL,NULL,'是否开启注册用户功能（true开启，false关闭）'),
	 (6,'用户登录-黑名单列表','sys.login.blackIPList',NULL,'Y','admin','2025-06-25 03:56:22',NULL,NULL,'设置登录IP黑名单限制，多个匹配项以;分隔，支持匹配（*通配、网段）'),
	 (7,'用户管理-初始密码修改策略','sys.account.initPasswordModify','1','Y','admin','2025-06-25 03:56:22',NULL,NULL,'0：初始密码修改策略关闭，没有任何提示，1：提醒用户，如果未修改初始密码，则在登录时就会提醒修改密码对话框'),
	 (8,'用户管理-账号密码更新周期','sys.account.passwordValidateDays','0','Y','admin','2025-06-25 03:56:22',NULL,NULL,'密码更新周期（填写数字，数据初始化值为0不限制，若修改必须为大于0小于365的正整数），如果超过这个周期登录系统时，则在登录时就会提醒修改密码对话框');
INSERT INTO `sys_dept` (dept_id,parent_id,ancestors,dept_name,order_num,leader,phone,email,status,del_flag,create_by,create_time,update_by,update_time) VALUES
	 (1,0,'0','XX科技',0,NULL,NULL,NULL,'0','0','admin','2025-06-25 03:56:13','admin','2026-06-04 18:46:23');
INSERT INTO `sys_dict_data` (dict_code,dict_sort,dict_label,dict_value,dict_type,css_class,list_class,is_default,status,create_by,create_time,update_by,update_time,remark) VALUES
	 (1,1,'男','0','sys_user_sex',NULL,NULL,'Y','0','admin','2025-06-25 03:56:21',NULL,NULL,'性别男'),
	 (2,2,'女','1','sys_user_sex',NULL,NULL,'N','0','admin','2025-06-25 03:56:21',NULL,NULL,'性别女'),
	 (3,3,'未知','2','sys_user_sex',NULL,NULL,'N','0','admin','2025-06-25 03:56:21',NULL,NULL,'性别未知'),
	 (4,1,'显示','0','sys_show_hide',NULL,'primary','Y','0','admin','2025-06-25 03:56:21',NULL,NULL,'显示菜单'),
	 (5,2,'隐藏','1','sys_show_hide',NULL,'danger','N','0','admin','2025-06-25 03:56:21',NULL,NULL,'隐藏菜单'),
	 (6,1,'正常','0','sys_normal_disable',NULL,'primary','Y','0','admin','2025-06-25 03:56:21',NULL,NULL,'正常状态'),
	 (7,2,'停用','1','sys_normal_disable',NULL,'danger','N','0','admin','2025-06-25 03:56:21',NULL,NULL,'停用状态'),
	 (8,1,'正常','0','sys_job_status',NULL,'primary','Y','0','admin','2025-06-25 03:56:21',NULL,NULL,'正常状态'),
	 (9,2,'暂停','1','sys_job_status',NULL,'danger','N','0','admin','2025-06-25 03:56:21',NULL,NULL,'停用状态'),
	 (10,1,'默认','DEFAULT','sys_job_group',NULL,'info','Y','0','admin','2025-06-25 03:56:21','admin','2026-09-08 09:28:12','默认');
INSERT INTO `sys_dict_data` (dict_code,dict_sort,dict_label,dict_value,dict_type,css_class,list_class,is_default,status,create_by,create_time,update_by,update_time,remark) VALUES
	 (11,2,'系统','SYSTEME','sys_job_group',NULL,'primary','N','0','admin','2025-06-25 03:56:21','admin','2026-09-08 09:29:13','系统'),
	 (12,1,'是','Y','sys_yes_no',NULL,'primary','Y','0','admin','2025-06-25 03:56:21',NULL,NULL,'系统默认是'),
	 (13,2,'否','N','sys_yes_no',NULL,'danger','N','0','admin','2025-06-25 03:56:21',NULL,NULL,'系统默认否'),
	 (14,1,'告警','1','sys_notice_type',NULL,'warning','Y','0','admin','2025-06-25 03:56:21','admin','2026-09-07 10:55:37','warning'),
	 (15,2,'严重','2','sys_notice_type',NULL,'error','N','0','admin','2025-06-25 03:56:21','admin','2026-09-07 11:05:37','error'),
	 (16,1,'正常','0','sys_notice_status',NULL,'primary','Y','0','admin','2025-06-25 03:56:21',NULL,NULL,'正常状态'),
	 (17,2,'关闭','1','sys_notice_status',NULL,'danger','N','0','admin','2025-06-25 03:56:21',NULL,NULL,'关闭状态'),
	 (18,99,'其他','0','sys_oper_type',NULL,'info','N','0','admin','2025-06-25 03:56:21',NULL,NULL,'其他操作'),
	 (19,1,'新增','1','sys_oper_type',NULL,'info','N','0','admin','2025-06-25 03:56:21',NULL,NULL,'新增操作'),
	 (20,2,'修改','2','sys_oper_type',NULL,'info','N','0','admin','2025-06-25 03:56:21',NULL,NULL,'修改操作');
INSERT INTO `sys_dict_data` (dict_code,dict_sort,dict_label,dict_value,dict_type,css_class,list_class,is_default,status,create_by,create_time,update_by,update_time,remark) VALUES
	 (21,3,'删除','3','sys_oper_type',NULL,'danger','N','0','admin','2025-06-25 03:56:21',NULL,NULL,'删除操作'),
	 (22,4,'授权','4','sys_oper_type',NULL,'primary','N','0','admin','2025-06-25 03:56:21',NULL,NULL,'授权操作'),
	 (23,5,'导出','5','sys_oper_type',NULL,'warning','N','0','admin','2025-06-25 03:56:21',NULL,NULL,'导出操作'),
	 (24,6,'导入','6','sys_oper_type',NULL,'warning','N','0','admin','2025-06-25 03:56:21',NULL,NULL,'导入操作'),
	 (25,7,'强退','7','sys_oper_type',NULL,'danger','N','0','admin','2025-06-25 03:56:21',NULL,NULL,'强退操作'),
	 (26,8,'生成代码','8','sys_oper_type',NULL,'warning','N','0','admin','2025-06-25 03:56:21',NULL,NULL,'生成操作'),
	 (27,9,'清空数据','9','sys_oper_type',NULL,'danger','N','0','admin','2025-06-25 03:56:21',NULL,NULL,'清空操作'),
	 (28,1,'成功','0','sys_common_status',NULL,'primary','N','0','admin','2025-06-25 03:56:21',NULL,NULL,'正常状态'),
	 (29,2,'失败','1','sys_common_status',NULL,'danger','N','0','admin','2025-06-25 03:56:21',NULL,NULL,'停用状态'),
	 (100,0,'已发布','1','map_status',NULL,'success','N','0','admin','2025-06-27 02:42:08','admin','2025-06-27 02:42:42',NULL);
INSERT INTO `sys_dict_data` (dict_code,dict_sort,dict_label,dict_value,dict_type,css_class,list_class,is_default,status,create_by,create_time,update_by,update_time,remark) VALUES
	 (101,0,'未发布','0','map_status',NULL,'warning','N','0','admin','2025-06-27 02:42:20','admin','2025-06-27 02:42:36',NULL),
	 (102,0,'离线','0','robot_status',NULL,'warning','N','0','admin','2025-07-07 06:32:06','admin','2025-07-07 06:36:54',NULL),
	 (103,0,'在线','1','robot_status',NULL,'success','N','0','admin','2025-07-07 06:32:18','admin','2025-07-07 06:36:59',NULL),
	 (104,0,'机器狗','1','robot_type',NULL,'default','N','0','admin','2025-09-03 08:23:29',NULL,NULL,NULL),
	 (105,1,'agv','2','robot_type',NULL,'default','N','0','admin','2025-09-03 08:23:42',NULL,NULL,NULL),
	 (107,0,'任务模板','2','task_source',NULL,'primary','N','0','admin','2025-09-04 08:27:08',NULL,NULL,NULL),
	 (111,0,'正在处理中','BEING_PROCESSED','task_state',NULL,'primary','N','0','admin','2025-09-04 09:49:19','admin','2025-09-04 09:49:49',NULL),
	 (112,0,'撤销','WITHDRAWN','task_state',NULL,'info','N','0','admin','2025-09-04 09:50:17','admin','2025-09-04 09:50:24',NULL),
	 (113,0,'完成','FINISHED','task_state',NULL,'success','N','0','admin','2025-09-04 09:50:41','admin','2025-09-04 09:50:46',NULL),
	 (114,0,'失败','FAILED','task_state',NULL,'danger','N','0','admin','2025-09-04 09:51:07',NULL,NULL,NULL);
INSERT INTO `sys_dict_data` (dict_code,dict_sort,dict_label,dict_value,dict_type,css_class,list_class,is_default,status,create_by,create_time,update_by,update_time,remark) VALUES
	 (115,0,'故障','UNROUTABLE','task_state',NULL,'warning','N','1','admin','2025-09-04 09:52:19','admin','2026-04-15 17:14:39',NULL),
	 (116,0,'巡检任务','INSPECTION','task_type',NULL,'primary','N','0','admin','2025-09-04 09:54:48',NULL,NULL,NULL),
	 (117,0,'初始','PRISTINE','step_state',NULL,'info','N','0','admin','2025-09-04 10:13:04',NULL,NULL,NULL),
	 (118,0,'执行中','TRAVELLING','step_state',NULL,'primary','N','0','admin','2025-09-04 10:13:56','admin','2025-12-24 18:59:08',NULL),
	 (120,0,'完成','FINISHED','step_state',NULL,'success','N','0','admin','2025-09-04 10:14:48',NULL,NULL,NULL),
	 (121,0,'失败','FAILED','step_state',NULL,'danger','N','0','admin','2025-09-04 10:15:01',NULL,NULL,NULL),
	 (122,0,'开启后摄像头视频流','START_FRONT_VIDEO_STREAM','step_action',NULL,'primary','N','0','admin','2025-09-11 04:40:43',NULL,NULL,NULL),
	 (123,0,'关闭前摄像头视频流','END_FRONT_VIDEO_STREAM','step_action',NULL,'primary','N','0','admin','2025-09-11 04:41:06','admin','2025-09-11 04:41:30',NULL),
	 (124,0,'开启后摄像头视频流','START_BACK_VIDEO_STREAM','step_action',NULL,'primary','N','0','admin','2025-09-11 04:41:48',NULL,NULL,NULL),
	 (125,0,'关闭后摄像头视频流','END_BACK_VIDEO_STREAM','step_action',NULL,'primary','N','0','admin','2025-09-11 04:42:04',NULL,NULL,NULL);
INSERT INTO `sys_dict_data` (dict_code,dict_sort,dict_label,dict_value,dict_type,css_class,list_class,is_default,status,create_by,create_time,update_by,update_time,remark) VALUES
	 (126,0,'使用算法A','ALGORITHM_A','step_action',NULL,'primary','N','0','admin','2025-09-11 04:42:39',NULL,NULL,NULL),
	 (127,0,'机械臂执行A动作','ACTION_A','step_action',NULL,'primary','N','0','admin','2025-09-11 04:42:53',NULL,NULL,NULL),
	 (128,0,'读取传感器数值','READ','step_action',NULL,'primary','N','0','admin','2025-09-11 04:43:09',NULL,NULL,NULL),
	 (129,0,'打开开关','TURN_ON','step_action',NULL,'primary','N','0','admin','2025-09-11 04:43:23',NULL,NULL,NULL),
	 (130,0,'读取开关数值','GET_STATUS','step_action',NULL,'primary','N','0','admin','2025-09-11 04:43:41',NULL,NULL,NULL),
	 (131,0,'移动','auto_move','step_type',NULL,'primary','N','0','admin','2025-09-12 08:01:48','admin','2025-12-22 18:13:37',NULL),
	 (132,3,'相机','CAMERA','step_type',NULL,'primary','N','0','admin','2025-09-12 08:02:32','admin','2025-12-22 18:13:16',NULL),
	 (133,2,'机械臂','MECHANICAL','step_type',NULL,'primary','N','0','admin','2025-09-12 08:03:35','admin','2025-12-22 18:45:03',NULL),
	 (134,4,'传感器','SENSOR','step_type',NULL,'primary','N','0','admin','2025-09-12 08:04:05','admin','2025-12-22 18:13:23',NULL),
	 (135,5,'照明开关','SWITCH','step_type',NULL,'primary','N','0','admin','2025-09-12 08:04:50','admin','2025-12-23 16:42:47',NULL);
INSERT INTO `sys_dict_data` (dict_code,dict_sort,dict_label,dict_value,dict_type,css_class,list_class,is_default,status,create_by,create_time,update_by,update_time,remark) VALUES
	 (136,0,'暂停','PAUSE','task_state',NULL,'warning','N','0','admin','2025-09-16 08:04:52','admin','2026-04-21 18:16:49',NULL),
	 (137,0,'暂停','PAUSE','step_state',NULL,'warning','N','0','admin','2025-09-16 08:05:26',NULL,NULL,NULL),
	 (138,0,'恢复','RESUME','step_state',NULL,'primary','N','0','admin','2025-09-16 08:05:47','admin','2025-09-16 10:14:20',NULL),
	 (139,0,'取消','CANCEL','step_state',NULL,'danger','N','0','admin','2025-09-17 02:29:58',NULL,NULL,NULL),
	 (140,0,'低度','1','danger_severity',NULL,'default','N','0','admin','2025-09-25 04:47:08',NULL,NULL,NULL),
	 (141,1,'中度','2','danger_severity',NULL,'default','N','0','admin','2025-09-25 04:48:23',NULL,NULL,NULL),
	 (142,2,'高度','3','danger_severity',NULL,'default','N','0','admin','2025-09-25 04:48:36',NULL,NULL,NULL),
	 (143,0,'未处理','0','danger_status',NULL,'info','N','0','admin','2025-09-25 10:25:28','admin','2025-12-25 18:33:09',NULL),
	 (145,2,'已处理','2','danger_status',NULL,'success','N','0','admin','2025-09-25 10:25:50','admin','2025-12-25 18:33:21',NULL),
	 (146,0,'执行动作A','ACTION_A','mechanical',NULL,'primary','N','0','admin','2025-09-26 04:27:10',NULL,NULL,NULL);
INSERT INTO `sys_dict_data` (dict_code,dict_sort,dict_label,dict_value,dict_type,css_class,list_class,is_default,status,create_by,create_time,update_by,update_time,remark) VALUES
	 (147,0,'执行动作B','ACTION_B','mechanical',NULL,'primary','N','0','admin','2025-09-26 04:27:20','admin','2025-09-26 04:27:26',NULL),
	 (148,0,'开启前摄','START_FRONT_VIDEO_STREAM','camera',NULL,'primary','N','0','admin','2025-09-26 04:27:46',NULL,NULL,NULL),
	 (149,0,'关闭前摄','END_FRONT_VIDEO_STREAM','camera',NULL,'primary','N','0','admin','2025-09-26 04:27:58','admin','2025-09-26 04:28:03',NULL),
	 (150,0,'开启后摄','START_BACK_VIDEO_STREAM','camera',NULL,'primary','N','0','admin','2025-09-26 04:28:16',NULL,NULL,NULL),
	 (151,0,'关闭后摄','END_BACK_VIDEO_STREAM','camera',NULL,'primary','N','0','admin','2025-09-26 04:28:36',NULL,NULL,NULL),
	 (152,0,'读取数据','READ','sensor',NULL,'primary','N','0','admin','2025-09-26 04:29:57','admin','2025-09-26 04:30:02',NULL),
	 (153,0,'打开照明','TURN_ON','switch_on_off',NULL,'success','N','0','admin','2025-09-26 04:30:51','admin','2025-12-25 11:48:04',NULL),
	 (154,0,'关闭照明','TURN_OFF','switch_on_off',NULL,'warning','N','0','admin','2025-09-26 04:31:21','admin','2025-12-25 11:47:41',NULL),
	 (155,0,'读取照明状态','GET_STATUS','switch_on_off',NULL,'primary','N','1','admin','2025-09-26 04:31:46','admin','2025-12-23 16:44:35',NULL),
	 (156,0,'执行算法A','ALGORITHM_A','camera',NULL,'primary','N','0','admin','2025-09-26 06:42:46',NULL,NULL,NULL);
INSERT INTO `sys_dict_data` (dict_code,dict_sort,dict_label,dict_value,dict_type,css_class,list_class,is_default,status,create_by,create_time,update_by,update_time,remark) VALUES
	 (157,0,'执行算法B','ALGORITHM_B','camera',NULL,'primary','N','0','admin','2025-09-26 06:42:59',NULL,NULL,NULL),
	 (158,0,'执行算法C','ALGORITHM_C','camera',NULL,'primary','N','0','admin','2025-09-26 06:43:12',NULL,NULL,NULL),
	 (159,1,'语音播报','VOICE','step_type',NULL,'primary','N','0','admin','2025-12-22 18:11:43','admin','2025-12-29 15:42:06',NULL),
	 (160,0,'语音播报','BROADCAST','voice',NULL,'primary','N','0','admin','2025-12-22 18:15:26','admin','2025-12-24 16:14:41',NULL),
	 (161,1,'暂停移动','pause','step_type',NULL,'primary','N','0','admin','2025-12-23 14:33:03','admin','2025-12-29 15:41:59',NULL),
	 (162,0,'打开报警','TURN_ON','switch_alert_on_off',NULL,'success','N','0','admin','2025-12-23 15:03:07','admin','2025-12-24 16:15:02',NULL),
	 (163,1,'关闭报警','TURN_OFF','switch_alert_on_off',NULL,'warning','N','0','admin','2025-12-23 15:03:23','admin','2025-12-24 16:15:08',NULL),
	 (164,2,'读取报警状态','GET_STATUS','switch_alert_on_off',NULL,'primary','N','1','admin','2025-12-23 15:03:42','admin','2025-12-24 16:15:15',NULL),
	 (165,1,'报警开关','SWITCH_ALERT','step_type',NULL,'primary','N','0','admin','2025-12-23 16:41:42','admin','2025-12-24 11:24:31',NULL),
	 (166,0,'误报','3','danger_status',NULL,'warning','N','0','admin','2025-12-25 18:55:15',NULL,NULL,NULL);
INSERT INTO `sys_dict_data` (dict_code,dict_sort,dict_label,dict_value,dict_type,css_class,list_class,is_default,status,create_by,create_time,update_by,update_time,remark) VALUES
	 (167,0,'充电','CHARGE','step_type',NULL,'primary','N','0','admin','2025-12-29 15:37:49','admin','2025-12-29 15:41:13',NULL),
	 (168,0,'开始充电','CHARGE','charge',NULL,'success','N','0','admin','2025-12-29 15:39:19','admin','2025-12-29 15:42:29',NULL),
	 (169,1,'退出充电','EXIT_CHARGING','charge',NULL,'primary','N','0','admin','2026-02-27 17:18:22',NULL,NULL,NULL),
	 (170,0,'开始任务','start','step_state',NULL,'primary','N','0','admin','2026-04-22 11:39:04','admin','2026-07-09 08:38:37',NULL),
	 (171,0,'失败','fail','step_state',NULL,'danger','N','0','admin','2026-04-22 11:39:26','admin','2026-07-09 08:39:04',NULL),
	 (172,0,'重试','retry','step_state',NULL,'primary','N','0','admin','2026-04-22 11:39:45',NULL,NULL,NULL),
	 (173,0,'失败','fail','step_state',NULL,'default','N','0','admin','2026-04-22 11:39:56',NULL,NULL,NULL),
	 (174,0,'经典低速','3','robot_gait',NULL,'primary','N','0','admin','2026-04-24 12:21:43','admin','2026-06-01 07:09:07',NULL),
	 (175,1,'经典高速','4','robot_gait',NULL,'primary','N','0','admin','2026-04-24 12:22:09','admin','2026-06-01 07:09:33',NULL),
	 (176,2,'视觉辅助','7','robot_gait',NULL,'primary','N','0','admin','2026-04-24 12:22:23','admin','2026-06-01 07:10:03',NULL);
INSERT INTO `sys_dict_data` (dict_code,dict_sort,dict_label,dict_value,dict_type,css_class,list_class,is_default,status,create_by,create_time,update_by,update_time,remark) VALUES
	 (178,3,'致命','3','sys_notice_type',NULL,'fatal','N','0','admin','2026-09-03 23:10:48','admin','2026-09-07 11:10:01','fatal'),
	 (179,0,'提示','0','sys_notice_type',NULL,'einfo','N','0','admin','2026-09-07 10:54:27','admin','2026-09-08 09:30:50','info'),
	 (180,0,'在线任务','0','sys_job_online',NULL,'success','N','0','admin','2026-09-07 12:39:59','admin','2026-09-07 17:11:12',NULL),
	 (181,1,'离线任务','1','sys_job_online',NULL,'warning','N','0','admin','2026-09-07 12:40:09','admin','2026-09-07 17:11:18',NULL),
	 (183,0,'未同步','0','sys_job_sync_status',NULL,'primary','N','0','admin','2026-09-08 09:32:33',NULL,NULL,NULL),
	 (184,0,'已同步','1','sys_job_sync_status',NULL,'success','N','0','admin','2026-09-08 09:32:44',NULL,NULL,NULL),
	 (185,0,'无需同步','2','sys_job_sync_status',NULL,'info','N','0','admin','2026-09-08 10:34:07',NULL,NULL,NULL),
	 (186,0,'未确认','0','alarm_read_status',NULL,'primary','N','0','admin','2026-09-10 18:26:16',NULL,NULL,'未确认'),
	 (187,0,'已确认','1','alarm_read_status',NULL,'success','N','0','admin','2026-09-10 18:26:33',NULL,NULL,'已确认');
INSERT INTO `sys_dict_type` (dict_id,dict_name,dict_type,status,create_by,create_time,update_by,update_time,remark) VALUES
	 (1,'用户性别','sys_user_sex','0','admin','2025-06-25 03:56:20',NULL,NULL,'用户性别列表'),
	 (2,'菜单状态','sys_show_hide','0','admin','2025-06-25 03:56:20',NULL,NULL,'菜单状态列表'),
	 (3,'系统开关','sys_normal_disable','0','admin','2025-06-25 03:56:20',NULL,NULL,'系统开关列表'),
	 (4,'任务状态','sys_job_status','0','admin','2025-06-25 03:56:20',NULL,NULL,'任务状态列表'),
	 (5,'任务分组','sys_job_group','0','admin','2025-06-25 03:56:20','admin','2026-09-08 09:27:07','任务分组列表'),
	 (6,'系统是否','sys_yes_no','0','admin','2025-06-25 03:56:20',NULL,NULL,'系统是否列表'),
	 (7,'通知类型','sys_notice_type','0','admin','2025-06-25 03:56:20',NULL,NULL,'通知类型列表'),
	 (8,'通知状态','sys_notice_status','0','admin','2025-06-25 03:56:20',NULL,NULL,'通知状态列表'),
	 (9,'操作类型','sys_oper_type','0','admin','2025-06-25 03:56:20',NULL,NULL,'操作类型列表'),
	 (10,'系统状态','sys_common_status','0','admin','2025-06-25 03:56:20',NULL,NULL,'登录状态列表');
INSERT INTO `sys_dict_type` (dict_id,dict_name,dict_type,status,create_by,create_time,update_by,update_time,remark) VALUES
	 (100,'发布状态','map_status','0','admin','2025-06-27 02:41:43','admin','2025-07-01 03:59:31',NULL),
	 (101,'机器人在线状态','robot_status','0','admin','2025-07-07 06:31:48',NULL,NULL,NULL),
	 (102,'机器人类型','robot_type','0','admin','2025-09-03 08:22:52',NULL,NULL,'1:机器狗,2:agv'),
	 (103,'任务来源','task_source','0','admin','2025-09-04 08:25:53',NULL,NULL,NULL),
	 (104,'任务状态','task_state','0','admin','2025-09-04 09:45:51',NULL,NULL,NULL),
	 (105,'任务类型','task_type','0','admin','2025-09-04 09:54:06',NULL,NULL,NULL),
	 (106,'步骤状态','step_state','0','admin','2025-09-04 10:12:31',NULL,NULL,NULL),
	 (107,'步骤操作','step_action','0','admin','2025-09-11 04:40:05',NULL,NULL,NULL),
	 (108,'步骤类型','step_type','0','admin','2025-09-12 08:00:20',NULL,NULL,NULL),
	 (109,'隐患程度','danger_severity','0','admin','2025-09-25 04:46:35','admin','2025-09-25 10:24:11','隐患程度列表');
INSERT INTO `sys_dict_type` (dict_id,dict_name,dict_type,status,create_by,create_time,update_by,update_time,remark) VALUES
	 (110,'隐患处理状态','danger_status','0','admin','2025-09-25 10:24:04',NULL,NULL,NULL),
	 (111,'机械臂','mechanical','0','admin','2025-09-26 04:19:36',NULL,NULL,NULL),
	 (112,'摄像头','camera','0','admin','2025-09-26 04:26:05',NULL,NULL,NULL),
	 (113,'传感器','sensor','0','admin','2025-09-26 04:26:15',NULL,NULL,NULL),
	 (114,'照明控制','switch_on_off','0','admin','2025-09-26 04:26:30','admin','2025-12-23 15:02:01',NULL),
	 (115,'语音播报','voice','0','admin','2025-12-22 18:12:41','admin','2025-12-22 18:52:04',NULL),
	 (116,'报警控制','switch_alert_on_off','0','admin','2025-12-23 15:02:32',NULL,NULL,NULL),
	 (117,'充电','charge','0','admin','2025-12-29 15:38:39',NULL,NULL,NULL),
	 (118,'机器狗步态','robot_gait','0','admin','2026-04-24 12:21:17',NULL,NULL,NULL),
	 (119,'任务类型','sys_job_online','0','admin','2026-09-07 12:39:31','admin','2026-09-07 18:24:52','0:在线任务，1离线任务');
INSERT INTO `sys_dict_type` (dict_id,dict_name,dict_type,status,create_by,create_time,update_by,update_time,remark) VALUES
	 (120,'离线任务同步状态','sys_job_sync_status','0','admin','2026-09-08 09:32:07',NULL,NULL,'离线任务同步状态'),
	 (121,'告警确认状态','alarm_read_status','0','admin','2026-09-10 18:25:51',NULL,NULL,'0未确认，1已确认');
INSERT INTO `sys_menu` (menu_id,menu_name,parent_id,order_num,`path`,component,`query`,route_name,is_frame,is_cache,menu_type,`visible`,status,perms,icon,create_by,create_time,update_by,update_time,remark) VALUES
	 (1,'系统管理',0,6,'system',NULL,NULL,NULL,1,0,'M','0','0',NULL,'system','admin','2025-06-25 03:56:16','admin','2026-09-12 14:30:43','系统管理目录'),
	 (2,'系统监控',0,8,'monitor',NULL,NULL,NULL,1,0,'M','0','0',NULL,'monitor','admin','2025-06-25 03:56:16','admin','2026-09-12 14:30:34','系统监控目录'),
	 (3,'系统工具',0,9,'tool',NULL,NULL,NULL,1,0,'M','0','0',NULL,'tool','admin','2025-06-25 03:56:16','admin','2026-09-12 14:30:10','系统工具目录'),
	 (100,'用户管理',1,1,'user','system/user/index',NULL,NULL,1,0,'C','0','0','system:user:list','user','admin','2025-06-25 03:56:16','admin','2026-06-04 16:45:52','用户管理菜单'),
	 (101,'角色管理',1,2,'role','system/role/index',NULL,NULL,1,0,'C','0','0','system:role:list','peoples','admin','2025-06-25 03:56:16',NULL,NULL,'角色管理菜单'),
	 (102,'菜单管理',1,3,'menu','system/menu/index',NULL,NULL,1,0,'C','0','0','system:menu:list','tree-table','admin','2025-06-25 03:56:16',NULL,NULL,'菜单管理菜单'),
	 (103,'部门管理',1,4,'dept','system/dept/index',NULL,NULL,1,0,'C','0','0','system:dept:list','tree','admin','2025-06-25 03:56:16',NULL,NULL,'部门管理菜单'),
	 (104,'岗位管理',1,5,'post','system/post/index',NULL,NULL,1,0,'C','0','0','system:post:list','post','admin','2025-06-25 03:56:16',NULL,NULL,'岗位管理菜单'),
	 (105,'字典管理',1,6,'dict','system/dict/index',NULL,NULL,1,0,'C','0','0','system:dict:list','dict','admin','2025-06-25 03:56:16',NULL,NULL,'字典管理菜单'),
	 (106,'参数设置',1,7,'config','system/config/index',NULL,NULL,1,0,'C','0','0','system:config:list','edit','admin','2025-06-25 03:56:16',NULL,NULL,'参数设置菜单');
INSERT INTO `sys_menu` (menu_id,menu_name,parent_id,order_num,`path`,component,`query`,route_name,is_frame,is_cache,menu_type,`visible`,status,perms,icon,create_by,create_time,update_by,update_time,remark) VALUES
	 (107,'告警通知',2214,8,'notice','system/notice/index',NULL,NULL,1,0,'C','0','0','system:notice:list','message','admin','2025-06-25 03:56:16','admin','2026-09-11 17:49:16','通知公告菜单'),
	 (108,'日志管理',1,9,'log',NULL,NULL,NULL,1,0,'M','0','0',NULL,'log','admin','2025-06-25 03:56:16',NULL,NULL,'日志管理菜单'),
	 (109,'在线用户',2,1,'online','monitor/online/index',NULL,NULL,1,0,'C','0','0','monitor:online:list','online','admin','2025-06-25 03:56:16',NULL,NULL,'在线用户菜单'),
	 (110,'定时任务',2,2,'job','monitor/job/index',NULL,NULL,1,0,'C','0','0','monitor:job:list','job','admin','2025-06-25 03:56:16',NULL,NULL,'定时任务菜单'),
	 (111,'数据监控',2,3,'druid','monitor/druid/index',NULL,NULL,1,0,'C','0','0','monitor:druid:list','druid','admin','2025-06-25 03:56:16',NULL,NULL,'数据监控菜单'),
	 (112,'服务监控',2,4,'server','monitor/server/index',NULL,NULL,1,0,'C','0','0','monitor:server:list','server','admin','2025-06-25 03:56:16',NULL,NULL,'服务监控菜单'),
	 (113,'缓存监控',2,5,'cache','monitor/cache/index',NULL,NULL,1,0,'C','0','0','monitor:cache:list','redis','admin','2025-06-25 03:56:16',NULL,NULL,'缓存监控菜单'),
	 (114,'缓存列表',2,6,'cacheList','monitor/cache/list',NULL,NULL,1,0,'C','0','0','monitor:cache:list','redis-list','admin','2025-06-25 03:56:16',NULL,NULL,'缓存列表菜单');
INSERT INTO `sys_menu` (menu_id,menu_name,parent_id,order_num,`path`,component,`query`,route_name,is_frame,is_cache,menu_type,`visible`,status,perms,icon,create_by,create_time,update_by,update_time,remark) VALUES
	 (117,'系统接口',3,3,'swagger','tool/swagger/index',NULL,NULL,1,0,'C','0','0','tool:swagger:list','swagger','admin','2025-06-25 03:56:16',NULL,NULL,'系统接口菜单'),
	 (500,'操作日志',108,1,'operlog','monitor/operlog/index',NULL,NULL,1,0,'C','0','0','monitor:operlog:list','form','admin','2025-06-25 03:56:16',NULL,NULL,'操作日志菜单'),
	 (501,'登录日志',108,2,'logininfor','monitor/logininfor/index',NULL,NULL,1,0,'C','0','0','monitor:logininfor:list','logininfor','admin','2025-06-25 03:56:16',NULL,NULL,'登录日志菜单'),
	 (1000,'用户查询',100,1,NULL,NULL,NULL,NULL,1,0,'F','0','0','system:user:query','#','admin','2025-06-25 03:56:16',NULL,NULL,NULL),
	 (1001,'用户新增',100,2,NULL,NULL,NULL,NULL,1,0,'F','0','0','system:user:add','#','admin','2025-06-25 03:56:16',NULL,NULL,NULL),
	 (1002,'用户修改',100,3,NULL,NULL,NULL,NULL,1,0,'F','0','0','system:user:edit','#','admin','2025-06-25 03:56:16',NULL,NULL,NULL),
	 (1003,'用户删除',100,4,NULL,NULL,NULL,NULL,1,0,'F','0','0','system:user:remove','#','admin','2025-06-25 03:56:16',NULL,NULL,NULL),
	 (1004,'用户导出',100,5,NULL,NULL,NULL,NULL,1,0,'F','0','0','system:user:export','#','admin','2025-06-25 03:56:16',NULL,NULL,NULL),
	 (1005,'用户导入',100,6,NULL,NULL,NULL,NULL,1,0,'F','0','0','system:user:import','#','admin','2025-06-25 03:56:16',NULL,NULL,NULL),
	 (1006,'重置密码',100,7,NULL,NULL,NULL,NULL,1,0,'F','0','0','system:user:resetPwd','#','admin','2025-06-25 03:56:16',NULL,NULL,NULL);
INSERT INTO `sys_menu` (menu_id,menu_name,parent_id,order_num,`path`,component,`query`,route_name,is_frame,is_cache,menu_type,`visible`,status,perms,icon,create_by,create_time,update_by,update_time,remark) VALUES
	 (1007,'角色查询',101,1,NULL,NULL,NULL,NULL,1,0,'F','0','0','system:role:query','#','admin','2025-06-25 03:56:16',NULL,NULL,NULL),
	 (1008,'角色新增',101,2,NULL,NULL,NULL,NULL,1,0,'F','0','0','system:role:add','#','admin','2025-06-25 03:56:16',NULL,NULL,NULL),
	 (1009,'角色修改',101,3,NULL,NULL,NULL,NULL,1,0,'F','0','0','system:role:edit','#','admin','2025-06-25 03:56:16',NULL,NULL,NULL),
	 (1010,'角色删除',101,4,NULL,NULL,NULL,NULL,1,0,'F','0','0','system:role:remove','#','admin','2025-06-25 03:56:16',NULL,NULL,NULL),
	 (1011,'角色导出',101,5,NULL,NULL,NULL,NULL,1,0,'F','0','0','system:role:export','#','admin','2025-06-25 03:56:16',NULL,NULL,NULL),
	 (1012,'菜单查询',102,1,NULL,NULL,NULL,NULL,1,0,'F','0','0','system:menu:query','#','admin','2025-06-25 03:56:16',NULL,NULL,NULL),
	 (1013,'菜单新增',102,2,NULL,NULL,NULL,NULL,1,0,'F','0','0','system:menu:add','#','admin','2025-06-25 03:56:16',NULL,NULL,NULL),
	 (1014,'菜单修改',102,3,NULL,NULL,NULL,NULL,1,0,'F','0','0','system:menu:edit','#','admin','2025-06-25 03:56:16',NULL,NULL,NULL),
	 (1015,'菜单删除',102,4,NULL,NULL,NULL,NULL,1,0,'F','0','0','system:menu:remove','#','admin','2025-06-25 03:56:16',NULL,NULL,NULL),
	 (1016,'部门查询',103,1,NULL,NULL,NULL,NULL,1,0,'F','0','0','system:dept:query','#','admin','2025-06-25 03:56:16',NULL,NULL,NULL);
INSERT INTO `sys_menu` (menu_id,menu_name,parent_id,order_num,`path`,component,`query`,route_name,is_frame,is_cache,menu_type,`visible`,status,perms,icon,create_by,create_time,update_by,update_time,remark) VALUES
	 (1017,'部门新增',103,2,NULL,NULL,NULL,NULL,1,0,'F','0','0','system:dept:add','#','admin','2025-06-25 03:56:16',NULL,NULL,NULL),
	 (1018,'部门修改',103,3,NULL,NULL,NULL,NULL,1,0,'F','0','0','system:dept:edit','#','admin','2025-06-25 03:56:16',NULL,NULL,NULL),
	 (1019,'部门删除',103,4,NULL,NULL,NULL,NULL,1,0,'F','0','0','system:dept:remove','#','admin','2025-06-25 03:56:16',NULL,NULL,NULL),
	 (1020,'岗位查询',104,1,NULL,NULL,NULL,NULL,1,0,'F','0','0','system:post:query','#','admin','2025-06-25 03:56:16',NULL,NULL,NULL),
	 (1021,'岗位新增',104,2,NULL,NULL,NULL,NULL,1,0,'F','0','0','system:post:add','#','admin','2025-06-25 03:56:16',NULL,NULL,NULL),
	 (1022,'岗位修改',104,3,NULL,NULL,NULL,NULL,1,0,'F','0','0','system:post:edit','#','admin','2025-06-25 03:56:16',NULL,NULL,NULL),
	 (1023,'岗位删除',104,4,NULL,NULL,NULL,NULL,1,0,'F','0','0','system:post:remove','#','admin','2025-06-25 03:56:16',NULL,NULL,NULL),
	 (1024,'岗位导出',104,5,NULL,NULL,NULL,NULL,1,0,'F','0','0','system:post:export','#','admin','2025-06-25 03:56:16',NULL,NULL,NULL),
	 (1025,'字典查询',105,1,'#',NULL,NULL,NULL,1,0,'F','0','0','system:dict:query','#','admin','2025-06-25 03:56:16',NULL,NULL,NULL),
	 (1026,'字典新增',105,2,'#',NULL,NULL,NULL,1,0,'F','0','0','system:dict:add','#','admin','2025-06-25 03:56:16',NULL,NULL,NULL);
INSERT INTO `sys_menu` (menu_id,menu_name,parent_id,order_num,`path`,component,`query`,route_name,is_frame,is_cache,menu_type,`visible`,status,perms,icon,create_by,create_time,update_by,update_time,remark) VALUES
	 (1027,'字典修改',105,3,'#',NULL,NULL,NULL,1,0,'F','0','0','system:dict:edit','#','admin','2025-06-25 03:56:16',NULL,NULL,NULL),
	 (1028,'字典删除',105,4,'#',NULL,NULL,NULL,1,0,'F','0','0','system:dict:remove','#','admin','2025-06-25 03:56:16',NULL,NULL,NULL),
	 (1029,'字典导出',105,5,'#',NULL,NULL,NULL,1,0,'F','0','0','system:dict:export','#','admin','2025-06-25 03:56:16',NULL,NULL,NULL),
	 (1030,'参数查询',106,1,'#',NULL,NULL,NULL,1,0,'F','0','0','system:config:query','#','admin','2025-06-25 03:56:16',NULL,NULL,NULL),
	 (1031,'参数新增',106,2,'#',NULL,NULL,NULL,1,0,'F','0','0','system:config:add','#','admin','2025-06-25 03:56:16',NULL,NULL,NULL),
	 (1032,'参数修改',106,3,'#',NULL,NULL,NULL,1,0,'F','0','0','system:config:edit','#','admin','2025-06-25 03:56:16',NULL,NULL,NULL),
	 (1033,'参数删除',106,4,'#',NULL,NULL,NULL,1,0,'F','0','0','system:config:remove','#','admin','2025-06-25 03:56:16',NULL,NULL,NULL),
	 (1034,'参数导出',106,5,'#',NULL,NULL,NULL,1,0,'F','0','0','system:config:export','#','admin','2025-06-25 03:56:16',NULL,NULL,NULL),
	 (1035,'告警查询',107,1,'#',NULL,NULL,NULL,1,0,'F','0','0','system:notice:query','#','admin','2025-06-25 03:56:16',NULL,NULL,NULL),
	 (1036,'告警新增',107,2,'#',NULL,NULL,NULL,1,0,'F','0','1','system:notice:add','#','admin','2025-06-25 03:56:16',NULL,NULL,NULL);
INSERT INTO `sys_menu` (menu_id,menu_name,parent_id,order_num,`path`,component,`query`,route_name,is_frame,is_cache,menu_type,`visible`,status,perms,icon,create_by,create_time,update_by,update_time,remark) VALUES
	 (1037,'告警修改',107,3,'#',NULL,NULL,NULL,1,0,'F','0','1','system:notice:edit','#','admin','2025-06-25 03:56:16',NULL,NULL,NULL),
	 (1038,'告警删除',107,4,'#',NULL,NULL,NULL,1,0,'F','0','0','system:notice:remove','#','admin','2025-06-25 03:56:16',NULL,NULL,NULL),
	 (1039,'操作查询',500,1,'#',NULL,NULL,NULL,1,0,'F','0','0','monitor:operlog:query','#','admin','2025-06-25 03:56:16',NULL,NULL,NULL),
	 (1040,'操作删除',500,2,'#',NULL,NULL,NULL,1,0,'F','0','0','monitor:operlog:remove','#','admin','2025-06-25 03:56:16',NULL,NULL,NULL),
	 (1041,'日志导出',500,3,'#',NULL,NULL,NULL,1,0,'F','0','0','monitor:operlog:export','#','admin','2025-06-25 03:56:16',NULL,NULL,NULL),
	 (1042,'登录查询',501,1,'#',NULL,NULL,NULL,1,0,'F','0','0','monitor:logininfor:query','#','admin','2025-06-25 03:56:16',NULL,NULL,NULL),
	 (1043,'登录删除',501,2,'#',NULL,NULL,NULL,1,0,'F','0','0','monitor:logininfor:remove','#','admin','2025-06-25 03:56:16',NULL,NULL,NULL),
	 (1044,'日志导出',501,3,'#',NULL,NULL,NULL,1,0,'F','0','0','monitor:logininfor:export','#','admin','2025-06-25 03:56:16',NULL,NULL,NULL),
	 (1045,'账户解锁',501,4,'#',NULL,NULL,NULL,1,0,'F','0','0','monitor:logininfor:unlock','#','admin','2025-06-25 03:56:16',NULL,NULL,NULL),
	 (1046,'在线查询',109,1,'#',NULL,NULL,NULL,1,0,'F','0','0','monitor:online:query','#','admin','2025-06-25 03:56:16',NULL,NULL,NULL);
INSERT INTO `sys_menu` (menu_id,menu_name,parent_id,order_num,`path`,component,`query`,route_name,is_frame,is_cache,menu_type,`visible`,status,perms,icon,create_by,create_time,update_by,update_time,remark) VALUES
	 (1047,'批量强退',109,2,'#',NULL,NULL,NULL,1,0,'F','0','0','monitor:online:batchLogout','#','admin','2025-06-25 03:56:16',NULL,NULL,NULL),
	 (1048,'单条强退',109,3,'#',NULL,NULL,NULL,1,0,'F','0','0','monitor:online:forceLogout','#','admin','2025-06-25 03:56:16',NULL,NULL,NULL),
	 (1049,'任务查询',110,1,'#',NULL,NULL,NULL,1,0,'F','0','0','monitor:job:query','#','admin','2025-06-25 03:56:16',NULL,NULL,NULL),
	 (1050,'任务新增',110,2,'#',NULL,NULL,NULL,1,0,'F','0','0','monitor:job:add','#','admin','2025-06-25 03:56:16',NULL,NULL,NULL),
	 (1051,'任务修改',110,3,'#',NULL,NULL,NULL,1,0,'F','0','0','monitor:job:edit','#','admin','2025-06-25 03:56:16',NULL,NULL,NULL),
	 (1052,'任务删除',110,4,'#',NULL,NULL,NULL,1,0,'F','0','0','monitor:job:remove','#','admin','2025-06-25 03:56:16',NULL,NULL,NULL),
	 (1053,'状态修改',110,5,'#',NULL,NULL,NULL,1,0,'F','0','0','monitor:job:changeStatus','#','admin','2025-06-25 03:56:16',NULL,NULL,NULL),
	 (1054,'任务导出',110,6,'#',NULL,NULL,NULL,1,0,'F','0','0','monitor:job:export','#','admin','2025-06-25 03:56:16',NULL,NULL,NULL);
INSERT INTO `sys_menu` (menu_id,menu_name,parent_id,order_num,`path`,component,`query`,route_name,is_frame,is_cache,menu_type,`visible`,status,perms,icon,create_by,create_time,update_by,update_time,remark) VALUES
	 (2008,'地图管理',2085,1,'map','core/map/index',NULL,NULL,1,0,'C','0','0','core:map:list','international','admin','2025-06-26 06:21:48','admin','2025-12-22 17:04:39',NULL),
	 (2027,'机器人管理',2086,2,'vehicle','core/vehicle/index',NULL,NULL,1,0,'C','0','0','core:vehicle:list','example','admin','2025-07-07 04:09:28','admin','2025-12-22 17:11:26',NULL),
	 (2028,'任务管理',0,1,'task',NULL,NULL,NULL,1,0,'M','0','0',NULL,'component','admin','2025-07-30 06:22:09','admin','2026-08-11 12:05:17',NULL),
	 (2030,'任务编排',2028,0,'template/index','task/template/index',NULL,NULL,1,0,'C','0','0','core:template:list','monitor','admin','2025-07-30 06:28:29','admin','2025-09-28 09:34:25',NULL),
	 (2043,'任务记录',2028,1,'run','task/record/index',NULL,NULL,1,0,'C','0','0','core:task:list','component','admin','2025-07-30 10:02:24','admin','2025-07-30 10:18:28',NULL),
	 (2049,'控制面板',2086,0,'vehicle/console','core/vehicle/console',NULL,NULL,1,0,'C','1','0','core:vehicle:ctrl','#','admin','2025-08-06 03:22:49','admin','2025-12-22 17:16:21',NULL);
INSERT INTO `sys_menu` (menu_id,menu_name,parent_id,order_num,`path`,component,`query`,route_name,is_frame,is_cache,menu_type,`visible`,status,perms,icon,create_by,create_time,update_by,update_time,remark) VALUES
	 (2052,'隐患跟进',2084,2,'danger','task/danger/index',NULL,NULL,1,0,'C','0','0','core:danger:list','bug','admin','2025-09-24 08:18:42','admin','2025-12-22 17:04:10',NULL),
	 (2053,'新增',2027,0,NULL,NULL,NULL,NULL,1,0,'F','0','0','core:vehicle:add','#','admin','2025-09-28 07:41:34',NULL,NULL,NULL),
	 (2054,'控制台',2027,1,NULL,NULL,NULL,NULL,1,0,'F','0','0','core:vehicle:console','#','admin','2025-09-28 07:42:23',NULL,NULL,NULL),
	 (2055,'实时地图',2027,2,NULL,NULL,NULL,NULL,1,0,'F','0','0','core:vehicle:real','#','admin','2025-09-28 07:42:40',NULL,NULL,NULL),
	 (2056,'任务记录',2027,3,NULL,NULL,NULL,NULL,1,0,'F','0','0','core:vehicle:record','#','admin','2025-09-28 07:43:02',NULL,NULL,NULL),
	 (2057,'任务计划',2027,4,NULL,NULL,NULL,NULL,1,0,'F','0','0','core:vehicle:plan','#','admin','2025-09-28 07:43:18',NULL,NULL,NULL),
	 (2058,'编辑',2027,5,NULL,NULL,NULL,NULL,1,0,'F','0','0','core:vehicle:edit','#','admin','2025-09-28 07:43:37',NULL,NULL,NULL),
	 (2059,'设备管理',2027,6,NULL,NULL,NULL,NULL,1,0,'F','0','0','core:vehicle:manage','#','admin','2025-09-28 07:43:57',NULL,NULL,NULL),
	 (2060,'删除',2027,7,NULL,NULL,NULL,NULL,1,0,'F','0','0','core:vehicle:remove','#','admin','2025-09-28 07:46:31',NULL,NULL,NULL),
	 (2061,'新增',2008,0,NULL,NULL,NULL,NULL,1,0,'F','0','0','core:map:add','#','admin','2025-09-28 07:59:10',NULL,NULL,NULL);
INSERT INTO `sys_menu` (menu_id,menu_name,parent_id,order_num,`path`,component,`query`,route_name,is_frame,is_cache,menu_type,`visible`,status,perms,icon,create_by,create_time,update_by,update_time,remark) VALUES
	 (2062,'信息修改',2008,1,NULL,NULL,NULL,NULL,1,0,'F','0','0','core:map:edit','#','admin','2025-09-28 07:59:29',NULL,NULL,NULL),
	 (2063,'地图编辑',2008,2,NULL,NULL,NULL,NULL,1,0,'F','0','0','core:map:update','#','admin','2025-09-28 07:59:43',NULL,NULL,NULL),
	 (2064,'实时作图',2008,3,NULL,NULL,NULL,NULL,1,0,'F','0','0','core:map:real','#','admin','2025-09-28 07:59:57','admin','2025-09-29 03:53:50',NULL),
	 (2065,'版本管理',2008,4,NULL,NULL,NULL,NULL,1,0,'F','0','0','core:map:version','#','admin','2025-09-28 08:00:14',NULL,NULL,NULL),
	 (2066,'文件管理',2008,5,NULL,NULL,NULL,NULL,1,0,'F','0','0','core:map:file','#','admin','2025-09-28 08:00:29',NULL,NULL,NULL),
	 (2067,'删除',2008,6,NULL,NULL,NULL,NULL,1,0,'F','0','0','core:map:remove','#','admin','2025-09-28 08:00:43',NULL,NULL,NULL),
	 (2071,'新增',2030,0,NULL,NULL,NULL,NULL,1,0,'F','0','0','monitor:job:addTaskTemplate','#','admin','2025-09-28 08:10:48','admin','2026-08-11 11:38:08',NULL),
	 (2072,'修改',2030,1,NULL,NULL,NULL,NULL,1,0,'F','0','0','monitor:job:updateTaskTemplate','#','admin','2025-09-28 08:11:06','admin','2026-08-11 11:38:22',NULL),
	 (2073,'删除',2030,2,NULL,NULL,NULL,NULL,1,0,'F','0','0','core:template:remove','#','admin','2025-09-28 08:11:20','admin','2025-09-29 04:27:53',NULL),
	 (2074,'任务流程',2030,3,NULL,NULL,NULL,NULL,1,0,'F','0','0','core:map:taskRun','#','admin','2025-09-28 08:11:34','admin','2025-09-29 04:49:17',NULL);
INSERT INTO `sys_menu` (menu_id,menu_name,parent_id,order_num,`path`,component,`query`,route_name,is_frame,is_cache,menu_type,`visible`,status,perms,icon,create_by,create_time,update_by,update_time,remark) VALUES
	 (2076,'流程详细',2030,4,NULL,NULL,NULL,NULL,1,0,'F','0','0','core:map:taskShow','#','admin','2025-09-28 08:12:09','admin','2025-09-29 07:51:55',NULL),
	 (2078,'轨迹查看',2043,6,NULL,NULL,NULL,NULL,1,0,'F','0','0','core:task:track','#','admin','2025-09-28 08:19:18',NULL,NULL,NULL),
	 (2079,'详情',2043,7,NULL,NULL,NULL,NULL,1,0,'F','0','0','core:item:list','#','admin','2025-09-28 08:19:35','admin','2025-09-29 07:02:17',NULL),
	 (2080,'巡检报告',2043,8,NULL,NULL,NULL,NULL,1,0,'F','0','0','core:task:record','#','admin','2025-09-28 08:20:00',NULL,NULL,NULL),
	 (2081,'修改',2052,0,NULL,NULL,NULL,NULL,1,0,'F','0','0','core:danger:edit','#','admin','2025-09-28 08:25:14',NULL,NULL,NULL),
	 (2082,'查看报告',2052,1,NULL,NULL,NULL,NULL,1,0,'F','0','0','core:danger:getDanger','#','admin','2025-09-28 08:25:27','admin','2026-08-11 14:32:20',NULL),
	 (2083,'删除',2052,2,NULL,NULL,NULL,NULL,1,0,'F','0','0','core:danger:remove','#','admin','2025-09-28 08:25:44',NULL,NULL,NULL),
	 (2084,'隐患管理',0,4,'task/danger',NULL,NULL,NULL,1,0,'M','0','1',NULL,'bug','admin','2025-12-22 17:00:28','admin','2026-09-15 12:30:51',NULL),
	 (2085,'地图管理',0,3,'core/map',NULL,NULL,NULL,1,0,'M','0','0',NULL,'international','admin','2025-12-22 17:01:55','admin','2026-06-04 15:34:55',NULL),
	 (2086,'机器人管理',0,2,'core',NULL,NULL,NULL,1,0,'M','0','0',NULL,'example','admin','2025-12-22 17:02:40','admin','2026-06-04 15:34:32',NULL);
INSERT INTO `sys_menu` (menu_id,menu_name,parent_id,order_num,`path`,component,`query`,route_name,is_frame,is_cache,menu_type,`visible`,status,perms,icon,create_by,create_time,update_by,update_time,remark) VALUES
	 (2087,'上装能力管理',0,7,'system/upperAbility',NULL,NULL,NULL,1,0,'M','0','0',NULL,'redis','admin','2026-04-24 16:02:39','admin','2026-09-12 14:30:28',NULL),
	 (2088,'上装能力管理',2087,1,'upperAbility','system/upperAbility/index',NULL,NULL,1,0,'C','0','0','system:upperAbility:list','redis','admin','2026-04-24 16:08:37','admin','2026-04-27 11:12:56',NULL),
	 (2089,'机器人参数配置',2086,3,'robotConfig','core/robotConfig/index',NULL,NULL,1,0,'C','0','0','core:config:list','dict','admin','2026-04-28 17:07:14','admin','2026-04-28 17:08:08',NULL),
	 (2090,'能力调试',2087,2,'debugCtrl','core/vehicle/debugCtrl',NULL,NULL,1,0,'C','0','0',NULL,'bug','admin','2026-04-29 14:35:00','admin','2026-06-01 17:26:01',NULL),
	 (2091,'调试记录',2087,3,'debugList','core/debug/index',NULL,NULL,1,0,'C','0','0',NULL,'build','admin','2026-05-07 10:45:36','admin','2026-09-14 16:24:24',NULL),
	 (2092,'声纹管理',2087,4,'http://192.168.123.102',NULL,NULL,NULL,1,0,'C','0','0',NULL,'star','admin','2026-06-01 17:25:36','admin','2026-06-01 17:27:40',NULL),
	 (2095,'暂停任务',2043,1,NULL,NULL,NULL,NULL,1,0,'F','0','0','core:task:pauseCurrentTask','#','admin','2026-08-11 12:26:01',NULL,NULL,NULL),
	 (2096,'恢复任务',2043,2,NULL,NULL,NULL,NULL,1,0,'F','0','0','core:task:resumeCurrentTask','#','admin','2026-08-11 12:26:17',NULL,NULL,NULL),
	 (2097,'取消任务',2043,3,NULL,NULL,NULL,NULL,1,0,'F','0','0','core:task:cancelCurrentTask','#','admin','2026-08-11 12:26:33',NULL,NULL,NULL),
	 (2098,'暂停当前任务',2049,1,NULL,NULL,NULL,NULL,1,0,'F','0','0','core:vehicle:pauseTaskStep','#','admin','2026-08-11 12:40:24',NULL,NULL,NULL);
INSERT INTO `sys_menu` (menu_id,menu_name,parent_id,order_num,`path`,component,`query`,route_name,is_frame,is_cache,menu_type,`visible`,status,perms,icon,create_by,create_time,update_by,update_time,remark) VALUES
	 (2099,'恢复当前任务',2049,2,NULL,NULL,NULL,NULL,1,0,'F','0','0','core:vehicle:resumeTaskStep','#','admin','2026-08-11 12:40:48',NULL,NULL,NULL),
	 (2100,'取消当前任务',2049,3,NULL,NULL,NULL,NULL,1,0,'F','0','0','core:vehicle:cancelTaskStep','#','admin','2026-08-11 12:41:08',NULL,NULL,NULL),
	 (2101,'模式切换',2049,4,NULL,NULL,NULL,NULL,1,0,'F','0','0','core:vehicle:changeMode','#','admin','2026-08-11 12:42:19',NULL,NULL,NULL),
	 (2102,'充放电切换',2049,5,NULL,NULL,NULL,NULL,1,0,'F','0','0','core:vehicle:changeCharge','#','admin','2026-08-11 12:43:04',NULL,NULL,NULL),
	 (2103,'摇杆操作',2049,6,NULL,NULL,NULL,NULL,1,0,'F','0','0','core:vehicle:vehicleMove','#','admin','2026-08-11 12:46:36',NULL,NULL,NULL),
	 (2104,'机器人任务状态',2049,7,NULL,NULL,NULL,NULL,1,0,'F','0','0','core:vehicle:vehicleStatus','#','admin','2026-08-11 12:49:20',NULL,NULL,NULL),
	 (2105,'机器人实时上报数据',2049,8,NULL,NULL,NULL,NULL,1,0,'F','0','0','core:vehicle:getInstantInfo','#','admin','2026-08-11 12:50:39',NULL,NULL,NULL),
	 (2106,'机器人充电状态',2049,9,NULL,NULL,NULL,NULL,1,0,'F','0','0','core:vehicle:getChargeStatus','#','admin','2026-08-11 12:59:33',NULL,NULL,NULL),
	 (2107,'机器人详细信息',2049,10,NULL,NULL,NULL,NULL,1,0,'F','0','0','core:vehicle:getRobot','#','admin','2026-08-11 14:13:51',NULL,NULL,NULL),
	 (2108,'新增机器人配置',2089,0,NULL,NULL,NULL,NULL,1,0,'F','0','0','core:config:add','#','admin','2026-08-11 14:24:51',NULL,NULL,NULL);
INSERT INTO `sys_menu` (menu_id,menu_name,parent_id,order_num,`path`,component,`query`,route_name,is_frame,is_cache,menu_type,`visible`,status,perms,icon,create_by,create_time,update_by,update_time,remark) VALUES
	 (2109,'编辑机器人配置',2089,1,NULL,NULL,NULL,NULL,1,0,'F','0','0','core:config:edit','#','admin','2026-08-11 14:25:26',NULL,NULL,NULL),
	 (2110,'删除机器人配置',2089,2,NULL,NULL,NULL,NULL,1,0,'F','0','0','core:config:remove','#','admin','2026-08-11 14:25:52',NULL,NULL,NULL),
	 (2111,'导出机器人配置',2089,3,NULL,NULL,NULL,NULL,1,0,'F','0','0','core:config:export','#','admin','2026-08-11 14:26:18',NULL,NULL,NULL),
	 (2112,'修改隐患跟进',2052,3,NULL,NULL,NULL,NULL,1,0,'F','0','0','core:danger:edit','#','admin','2026-08-11 14:38:12',NULL,NULL,NULL),
	 (2113,'新增隐患跟进',2052,4,NULL,NULL,NULL,NULL,1,0,'F','0','0','core:danger:add','#','admin','2026-08-11 14:38:53','admin','2026-08-11 14:39:03',NULL),
	 (2114,'获取告警视频',2052,5,NULL,NULL,NULL,NULL,1,0,'F','0','0','core:danger:getAlertVideo','#','admin','2026-08-11 14:40:19',NULL,NULL,NULL),
	 (2115,'机械臂目标线缆列表',2088,1,NULL,NULL,NULL,NULL,1,0,'F','0','0','system:cable:list','#','admin','2026-08-11 14:44:48','admin','2026-08-11 14:51:34',NULL),
	 (2116,'机械臂目标线缆详细信息',2088,2,NULL,NULL,NULL,NULL,1,0,'F','0','0','system:cable:query','#','admin','2026-08-11 14:46:03','admin','2026-08-11 14:51:38',NULL),
	 (2117,'新增机械臂目标线缆',2088,3,NULL,NULL,NULL,NULL,1,0,'F','0','0','system:cable:add','#','admin','2026-08-11 14:46:46','admin','2026-08-11 14:51:43',NULL),
	 (2118,'删除机械臂目标线缆',2088,4,NULL,NULL,NULL,NULL,1,0,'F','0','0','system:cable:remove','#','admin','2026-08-11 14:47:09','admin','2026-08-11 14:51:50',NULL);
INSERT INTO `sys_menu` (menu_id,menu_name,parent_id,order_num,`path`,component,`query`,route_name,is_frame,is_cache,menu_type,`visible`,status,perms,icon,create_by,create_time,update_by,update_time,remark) VALUES
	 (2119,'修改机械臂目标线缆',2088,5,NULL,NULL,NULL,NULL,1,0,'F','0','0','system:cable:edit','#','admin','2026-08-11 14:47:45','admin','2026-08-11 14:51:59',NULL),
	 (2120,'开门机管理列表',2088,6,NULL,NULL,NULL,NULL,1,0,'F','0','0','system:control:list','#','admin','2026-08-11 14:48:51','admin','2026-08-11 14:52:13',NULL),
	 (2121,'开门机管理详细信息',2088,7,NULL,NULL,NULL,NULL,1,0,'F','0','0','system:control:query','#','admin','2026-08-11 14:49:29','admin','2026-08-11 14:52:17',NULL),
	 (2122,'新增开门机管理',2088,8,NULL,NULL,NULL,NULL,1,0,'F','0','0','system:control:add','#','admin','2026-08-11 14:49:50','admin','2026-08-11 14:52:22',NULL),
	 (2123,'修改开门机管理',2088,9,NULL,NULL,NULL,NULL,1,0,'F','0','0','system:control:edit','#','admin','2026-08-11 14:50:12','admin','2026-08-11 14:52:26',NULL),
	 (2124,'删除开门机管理',2088,10,NULL,NULL,NULL,NULL,1,0,'F','0','0','system:control:remove','#','admin','2026-08-11 14:50:46','admin','2026-08-11 14:52:31',NULL),
	 (2125,'查询电梯控制管理列表',2088,11,NULL,NULL,NULL,NULL,1,0,'F','0','0','system:elevator:list','#','admin','2026-08-11 14:53:21',NULL,NULL,NULL),
	 (2126,'获取电梯控制详细信息',2088,12,NULL,NULL,NULL,NULL,1,0,'F','0','0','system:elevator:query','#','admin','2026-08-11 14:54:01',NULL,NULL,NULL),
	 (2127,'新增电梯控制管理',2088,13,NULL,NULL,NULL,NULL,1,0,'F','0','0','system:elevator:add','#','admin','2026-08-11 14:54:24',NULL,NULL,NULL),
	 (2128,'修改电梯控制管理',2088,14,NULL,NULL,NULL,NULL,1,0,'F','0','0','system:elevator:edit','#','admin','2026-08-11 14:54:44',NULL,NULL,NULL);
INSERT INTO `sys_menu` (menu_id,menu_name,parent_id,order_num,`path`,component,`query`,route_name,is_frame,is_cache,menu_type,`visible`,status,perms,icon,create_by,create_time,update_by,update_time,remark) VALUES
	 (2129,'删除电梯控制管理',2088,15,NULL,NULL,NULL,NULL,1,0,'F','0','0','system:elevator:remove','#','admin','2026-08-11 14:55:03',NULL,NULL,NULL),
	 (2130,'查询云台预置点位管理列表',2088,16,NULL,NULL,NULL,NULL,1,0,'F','0','0','system:preset:list','#','admin','2026-08-11 14:56:11',NULL,NULL,NULL),
	 (2131,'获取云台预置点位管理详细信息',2088,17,NULL,NULL,NULL,NULL,1,0,'F','0','0','system:preset:query','#','admin','2026-08-11 14:56:31',NULL,NULL,NULL),
	 (2132,'新增云台预置点位管理',2088,18,NULL,NULL,NULL,NULL,1,0,'F','0','0','system:preset:add','#','admin','2026-08-11 14:56:48',NULL,NULL,NULL),
	 (2133,'修改云台预置点位管理',2088,19,NULL,NULL,NULL,NULL,1,0,'F','0','0','system:preset:edit','#','admin','2026-08-11 14:57:09',NULL,NULL,NULL),
	 (2134,'删除云台预置点位管理',2088,20,NULL,NULL,NULL,NULL,1,0,'F','0','0','system:preset:remove','#','admin','2026-08-11 14:57:24',NULL,NULL,NULL),
	 (2135,'查询气体传感器管理列表',2088,21,NULL,NULL,NULL,NULL,1,0,'F','0','0','system:gasSensor:list','#','admin','2026-08-11 14:58:17',NULL,NULL,NULL),
	 (2136,'获取气体传感器管理详细信息',2088,22,NULL,NULL,NULL,NULL,1,0,'F','0','0','system:gasSensor:query','#','admin','2026-08-11 14:58:35',NULL,NULL,NULL),
	 (2137,'新增气体传感器管理',2088,23,NULL,NULL,NULL,NULL,1,0,'F','0','0','system:gasSensor:add','#','admin','2026-08-11 14:58:51',NULL,NULL,NULL),
	 (2138,'修改气体传感器管理',2088,24,NULL,NULL,NULL,NULL,1,0,'F','0','0','system:gasSensor:edit','#','admin','2026-08-11 14:59:10',NULL,NULL,NULL);
INSERT INTO `sys_menu` (menu_id,menu_name,parent_id,order_num,`path`,component,`query`,route_name,is_frame,is_cache,menu_type,`visible`,status,perms,icon,create_by,create_time,update_by,update_time,remark) VALUES
	 (2139,'删除气体传感器管理',2088,25,NULL,NULL,NULL,NULL,1,0,'F','0','0','system:gasSensor:remove','#','admin','2026-08-11 14:59:24',NULL,NULL,NULL),
	 (2140,'查询LoRa中继列表',2088,26,NULL,NULL,NULL,NULL,1,0,'F','0','0','core:loraRelay:list','#','admin','2026-08-11 15:00:58','admin','2026-08-11 15:17:56',NULL),
	 (2141,'获取LoRa中继详细信息',2088,27,NULL,NULL,NULL,NULL,1,0,'F','0','0','core:loraRelay:query','#','admin','2026-08-11 15:01:28','admin','2026-08-11 15:18:01',NULL),
	 (2142,'新增LoRa中继',2088,28,NULL,NULL,NULL,NULL,1,0,'F','0','0','core:loraRelay:add','#','admin','2026-08-11 15:01:54','admin','2026-08-11 15:18:06',NULL),
	 (2143,'修改LoRa中继',2088,29,NULL,NULL,NULL,NULL,1,0,'F','0','0','core:loraRelay:edit','#','admin','2026-08-11 15:02:20','admin','2026-08-11 15:18:12',NULL),
	 (2144,'删除LoRa中继',2088,30,NULL,NULL,NULL,NULL,1,0,'F','0','0','core:loraRelay:remove','#','admin','2026-08-11 15:02:42','admin','2026-08-11 15:18:18',NULL),
	 (2145,'充电站配置列表',2088,31,NULL,NULL,NULL,NULL,1,0,'F','0','0','system:station:list','#','admin','2026-08-11 15:04:11',NULL,NULL,NULL),
	 (2146,'充电站详情',2088,32,NULL,NULL,NULL,NULL,1,0,'F','0','0','system:station:query','#','admin','2026-08-11 15:04:34',NULL,NULL,NULL),
	 (2147,'新增充电站',2088,33,NULL,NULL,NULL,NULL,1,0,'F','0','0','system:station:add','#','admin','2026-08-11 15:04:54',NULL,NULL,NULL),
	 (2148,'修改充电站',2088,34,NULL,NULL,NULL,NULL,1,0,'F','0','0','system:station:edit','#','admin','2026-08-11 15:05:16',NULL,NULL,NULL);
INSERT INTO `sys_menu` (menu_id,menu_name,parent_id,order_num,`path`,component,`query`,route_name,is_frame,is_cache,menu_type,`visible`,status,perms,icon,create_by,create_time,update_by,update_time,remark) VALUES
	 (2149,'删除充电站',2088,35,NULL,NULL,NULL,NULL,1,0,'F','0','0','system:station:remove','#','admin','2026-08-11 15:05:37',NULL,NULL,NULL),
	 (2150,'绑定地图的机器人列表',2090,1,NULL,NULL,NULL,NULL,1,0,'F','0','0','core:vehicle:listAllBindMap','#','admin','2026-08-11 15:07:04','admin','2026-08-11 15:07:18',NULL),
	 (2151,'根据机器人id获取地图',2090,2,NULL,NULL,NULL,NULL,1,0,'F','0','0','core:vehicle:getMapByRobotId','#','admin','2026-08-11 15:08:20',NULL,NULL,NULL),
	 (2152,'机器人能力列表',2090,3,NULL,NULL,NULL,NULL,1,0,'F','0','0','core:device:listAll','#','admin','2026-08-11 15:09:24','admin','2026-08-11 16:43:16',NULL),
	 (2153,'能力集调试下发',2090,4,NULL,NULL,NULL,NULL,1,0,'F','0','0','core:vehicle:abilityDebug','#','admin','2026-08-11 15:10:35',NULL,NULL,NULL),
	 (2154,'机器人调试详细信息',2090,5,NULL,NULL,NULL,NULL,1,0,'F','0','0','core:debug:getInfoByMsgId','#','admin','2026-08-11 15:11:26','admin','2026-08-11 15:18:46',NULL),
	 (2155,'绑定地图的机器人列表',2091,1,NULL,NULL,NULL,NULL,1,0,'F','0','0','core:vehicle:listAllBindMap','#','admin','2026-08-11 15:15:14','admin','2026-08-11 15:15:39',NULL),
	 (2156,'机器人能力列表',2091,2,NULL,NULL,NULL,NULL,1,0,'F','0','0','core:device:listAll','#','admin','2026-08-11 15:16:32','admin','2026-08-11 16:43:44',NULL),
	 (2157,'机器人调试列表',2091,3,NULL,NULL,NULL,NULL,1,0,'F','0','0','core:debug:list','#','admin','2026-08-11 15:17:08','admin','2026-08-11 15:18:53',NULL),
	 (2158,'查询机器人列表',2030,5,NULL,NULL,NULL,NULL,1,0,'F','0','0','core:vehicle:listAll','#','admin','2026-08-11 16:03:04',NULL,NULL,NULL);
INSERT INTO `sys_menu` (menu_id,menu_name,parent_id,order_num,`path`,component,`query`,route_name,is_frame,is_cache,menu_type,`visible`,status,perms,icon,create_by,create_time,update_by,update_time,remark) VALUES
	 (2159,'执行一次',2030,6,NULL,NULL,NULL,NULL,1,0,'F','0','0','monitor:job:run','#','admin','2026-08-11 16:07:23',NULL,NULL,NULL),
	 (2160,'调度日志',2030,7,NULL,NULL,NULL,NULL,1,0,'F','0','0','core:task:listAll','#','admin','2026-08-11 16:08:23','admin','2026-08-12 10:42:10',NULL),
	 (2161,'任务模板详细信息',2030,8,NULL,NULL,NULL,NULL,1,0,'F','0','0','core:template:query','#','admin','2026-08-11 17:12:29',NULL,NULL,NULL),
	 (2163,'绑定地图的机器人',2030,9,NULL,NULL,NULL,NULL,1,0,'F','0','0','core:vehicle:listAllBindMap','#','admin','2026-08-11 17:19:35',NULL,NULL,NULL),
	 (2164,'机器人id获取地图',2030,10,NULL,NULL,NULL,NULL,1,0,'F','0','0','core:vehicle:getMapByRobotId','#','admin','2026-08-11 17:20:16',NULL,NULL,NULL),
	 (2165,'机器人能力列表',2030,11,NULL,NULL,NULL,NULL,1,0,'F','0','0','core:device:listAll','#','admin','2026-08-11 17:21:50',NULL,NULL,NULL),
	 (2166,'保存任务流程',2030,12,NULL,NULL,NULL,NULL,1,0,'F','0','0','core:template:edit','#','admin','2026-08-11 17:23:29',NULL,NULL,NULL),
	 (2167,'所有地图',2043,9,NULL,NULL,NULL,NULL,1,0,'F','0','0','core:map:all','#','admin','2026-08-11 17:34:03',NULL,NULL,NULL),
	 (2168,'机器人数据',2027,8,NULL,NULL,NULL,NULL,1,0,'F','0','0','core:vehicle:getRobot','#','admin','2026-08-11 17:49:58',NULL,NULL,NULL),
	 (2169,'机器人能力列表',2027,9,NULL,NULL,NULL,NULL,1,0,'F','0','0','core:device:manage','#','admin','2026-08-11 17:52:03',NULL,NULL,NULL);
INSERT INTO `sys_menu` (menu_id,menu_name,parent_id,order_num,`path`,component,`query`,route_name,is_frame,is_cache,menu_type,`visible`,status,perms,icon,create_by,create_time,update_by,update_time,remark) VALUES
	 (2170,'获取地图详情',2027,10,NULL,NULL,NULL,NULL,1,0,'F','0','0','core:map:query','#','admin','2026-08-11 17:54:00',NULL,NULL,NULL),
	 (2171,'获取地图数据',2027,11,NULL,NULL,NULL,NULL,1,0,'F','0','0','core:map:getMapByIdAndVersionId','#','admin','2026-08-11 17:54:59',NULL,NULL,NULL),
	 (2172,'根据地图获取机器人',2027,12,NULL,NULL,NULL,NULL,1,0,'F','0','0','core:vehicle:getVehicleByMapId','#','admin','2026-08-11 17:56:37',NULL,NULL,NULL),
	 (2173,'获取所有机器人位置',2027,13,NULL,NULL,NULL,NULL,1,0,'F','0','0','core:vehicle:getAllRobotPosition','#','admin','2026-08-11 17:58:03',NULL,NULL,NULL),
	 (2174,'一键暂停任务',2027,14,NULL,NULL,NULL,NULL,1,0,'F','0','0','core:vehicle:stopAllRobot','#','admin','2026-08-11 17:59:22','admin','2026-08-11 18:03:48',NULL),
	 (2175,'一键结束任务',2027,15,NULL,NULL,NULL,NULL,1,0,'F','0','0','core:vehicle:cancelAllRobot','#','admin','2026-08-11 18:00:08','admin','2026-08-11 18:02:31',NULL),
	 (2176,'一键恢复任务',2027,16,NULL,NULL,NULL,NULL,1,0,'F','0','0','core:vehicle:resumeAllRobot','#','admin','2026-08-11 18:03:36',NULL,NULL,NULL),
	 (2177,'查询子任务列表',2043,10,NULL,NULL,NULL,NULL,1,0,'F','0','0','core:item:list','#','admin','2026-08-11 18:05:46',NULL,NULL,NULL),
	 (2178,'获取主任务详细信息',2043,11,NULL,NULL,NULL,NULL,1,0,'F','0','0','core:task:query','#','admin','2026-08-11 18:06:29',NULL,NULL,NULL),
	 (2179,'获取重试的时间',2043,12,NULL,NULL,NULL,NULL,1,0,'F','0','0','core:config:configKey','#','admin','2026-08-11 18:07:34','admin','2026-08-11 18:07:58',NULL);
INSERT INTO `sys_menu` (menu_id,menu_name,parent_id,order_num,`path`,component,`query`,route_name,is_frame,is_cache,menu_type,`visible`,status,perms,icon,create_by,create_time,update_by,update_time,remark) VALUES
	 (2180,'重试按钮',2043,13,NULL,NULL,NULL,NULL,1,0,'F','0','0','core:task:retryTask','#','admin','2026-08-11 18:08:25',NULL,NULL,NULL),
	 (2181,'查询配置参数详情',2089,4,NULL,NULL,NULL,NULL,1,0,'F','0','0','core:config:query','#','admin','2026-08-11 18:11:42',NULL,NULL,NULL),
	 (2182,'覆盖原地图',2008,7,NULL,NULL,NULL,NULL,1,0,'F','0','0','core:versions:edit','#','admin','2026-08-11 18:13:30',NULL,NULL,NULL),
	 (2183,'添加新地图',2008,8,NULL,NULL,NULL,NULL,1,0,'F','0','0','core:versions:add','#','admin','2026-08-11 18:14:39',NULL,NULL,NULL),
	 (2184,'地图版本列表',2008,9,NULL,NULL,NULL,NULL,1,0,'F','0','0','core:versions:list','#','admin','2026-08-11 18:16:17',NULL,NULL,NULL),
	 (2185,'发布地图',2008,10,NULL,NULL,NULL,NULL,1,0,'F','0','0','core:versions:pushMapVersions','#','admin','2026-08-11 18:17:26',NULL,NULL,NULL),
	 (2186,'导出机械臂目标线缆管理列表',2088,5,NULL,NULL,NULL,NULL,1,0,'F','0','0','system:cable:export','#','admin','2026-08-11 18:45:32',NULL,NULL,NULL),
	 (2187,'导出开门机管理列表',2088,10,NULL,NULL,NULL,NULL,1,0,'F','0','0','system:control:export','#','admin','2026-08-11 18:46:01',NULL,NULL,NULL),
	 (2188,'导出电梯控制管理列表',2088,15,NULL,NULL,NULL,NULL,1,0,'F','0','0','system:elevator:export','#','admin','2026-08-11 18:46:30',NULL,NULL,NULL),
	 (2189,'导出云台预置点位管理列表',2088,20,NULL,NULL,NULL,NULL,1,0,'F','0','0','system:preset:export','#','admin','2026-08-11 18:47:02',NULL,NULL,NULL);
INSERT INTO `sys_menu` (menu_id,menu_name,parent_id,order_num,`path`,component,`query`,route_name,is_frame,is_cache,menu_type,`visible`,status,perms,icon,create_by,create_time,update_by,update_time,remark) VALUES
	 (2190,'导出气体传感器管理列表',2088,25,NULL,NULL,NULL,NULL,1,0,'F','0','0','system:gasSensor:export','#','admin','2026-08-11 18:47:27',NULL,NULL,NULL),
	 (2191,'导出LoRa中继列表',2088,30,NULL,NULL,NULL,NULL,1,0,'F','0','0','core:loraRelay:export','#','admin','2026-08-11 18:47:56',NULL,NULL,NULL),
	 (2192,'导出充电站',2088,35,NULL,NULL,NULL,NULL,1,0,'F','0','0','system:station:export','#','admin','2026-08-11 18:48:36',NULL,NULL,NULL),
	 (2193,'查看调试详情',2091,4,NULL,NULL,NULL,NULL,1,0,'F','0','0','core:debug:select','#','admin','2026-08-11 18:51:32',NULL,NULL,NULL),
	 (2194,'机器人设备类型',2027,10,'deviceType','core/deviceType/index',NULL,NULL,1,0,'C','0','1','core:deviceType:list','#','admin','2026-09-04 09:40:15',NULL,NULL,'机器人设备类型菜单'),
	 (2195,'机器人设备类型查询',2194,1,'#',NULL,NULL,NULL,1,0,'F','0','0','core:deviceType:query','#','admin','2026-09-04 09:40:15',NULL,NULL,NULL),
	 (2196,'机器人设备类型新增',2194,2,'#',NULL,NULL,NULL,1,0,'F','0','0','core:deviceType:add','#','admin','2026-09-04 09:40:15',NULL,NULL,NULL),
	 (2197,'机器人设备类型修改',2194,3,'#',NULL,NULL,NULL,1,0,'F','0','0','core:deviceType:edit','#','admin','2026-09-04 09:40:15',NULL,NULL,NULL),
	 (2198,'机器人设备类型删除',2194,4,'#',NULL,NULL,NULL,1,0,'F','0','0','core:deviceType:remove','#','admin','2026-09-04 09:40:15',NULL,NULL,NULL),
	 (2199,'机器人设备类型导出',2194,5,'#',NULL,NULL,NULL,1,0,'F','0','0','core:deviceType:export','#','admin','2026-09-04 09:40:16',NULL,NULL,NULL);
INSERT INTO `sys_menu` (menu_id,menu_name,parent_id,order_num,`path`,component,`query`,route_name,is_frame,is_cache,menu_type,`visible`,status,perms,icon,create_by,create_time,update_by,update_time,remark) VALUES
	 (2200,'同步离线任务',2030,13,NULL,NULL,NULL,NULL,1,0,'F','0','0','core:task:syncOfflineTask','#','admin','2026-08-11 17:23:29',NULL,NULL,NULL),
	 (2201,'处理离线任务',2030,14,NULL,NULL,NULL,NULL,1,0,'F','0','0','core:task:handleOfflineTask','#','admin','2026-08-11 17:23:29',NULL,NULL,NULL),
	 (2202,'压板管理',2088,36,'label','system/label/index',NULL,NULL,1,0,'C','0','0','system:label:list','#','admin','2026-09-09 12:56:21',NULL,NULL,'压板管理菜单'),
	 (2203,'压板管理查询',2088,37,'#',NULL,NULL,NULL,1,0,'F','0','0','system:label:query','#','admin','2026-09-09 12:56:21',NULL,NULL,NULL),
	 (2204,'压板管理新增',2088,38,'#',NULL,NULL,NULL,1,0,'F','0','0','system:label:add','#','admin','2026-09-09 12:56:21',NULL,NULL,NULL),
	 (2205,'压板管理修改',2088,39,'#',NULL,NULL,NULL,1,0,'F','0','0','system:label:edit','#','admin','2026-09-09 12:56:21',NULL,NULL,NULL),
	 (2206,'压板管理删除',2088,40,'#',NULL,NULL,NULL,1,0,'F','0','0','system:label:remove','#','admin','2026-09-09 12:56:22',NULL,NULL,NULL),
	 (2207,'压板管理导出',2088,41,'#',NULL,NULL,NULL,1,0,'F','0','0','system:label:export','#','admin','2026-09-09 12:56:22',NULL,NULL,NULL),
	 (2208,'阀门管理',2088,42,'valve','system/valve/index',NULL,NULL,1,0,'C','0','0','system:valve:list','#','admin','2026-09-10 10:25:35',NULL,NULL,'阀门管理菜单'),
	 (2209,'阀门管理查询',2088,43,'#',NULL,NULL,NULL,1,0,'F','0','0','system:valve:query','#','admin','2026-09-10 10:25:35',NULL,NULL,NULL);
INSERT INTO `sys_menu` (menu_id,menu_name,parent_id,order_num,`path`,component,`query`,route_name,is_frame,is_cache,menu_type,`visible`,status,perms,icon,create_by,create_time,update_by,update_time,remark) VALUES
	 (2210,'阀门管理新增',2088,44,'#',NULL,NULL,NULL,1,0,'F','0','0','system:valve:add','#','admin','2026-09-10 10:25:35',NULL,NULL,NULL),
	 (2211,'阀门管理修改',2088,45,'#',NULL,NULL,NULL,1,0,'F','0','0','system:valve:edit','#','admin','2026-09-10 10:25:35',NULL,NULL,NULL),
	 (2212,'阀门管理删除',2088,46,'#',NULL,NULL,NULL,1,0,'F','0','0','system:valve:remove','#','admin','2026-09-10 10:25:35',NULL,NULL,NULL),
	 (2213,'阀门管理导出',2088,47,'#',NULL,NULL,NULL,1,0,'F','0','0','system:valve:export','#','admin','2026-09-10 10:25:36',NULL,NULL,NULL),
	 (2214,'告警管理',0,5,'system/notice/index',NULL,NULL,NULL,1,0,'M','0','0',NULL,'message','admin','2026-09-11 17:48:57','admin','2026-09-12 14:30:51',NULL),
	 (2215,'告警配置',2088,1,'alarmConfig','system/alarmConfig/index',NULL,NULL,1,0,'C','0','0','system:alarmConfig:list','#','admin','2026-09-12 10:13:29',NULL,NULL,'告警配置菜单'),
	 (2216,'告警配置查询',2088,1,'#',NULL,NULL,NULL,1,0,'F','0','0','system:alarmConfig:query','#','admin','2026-09-12 10:13:29',NULL,NULL,NULL),
	 (2217,'告警配置新增',2088,2,'#',NULL,NULL,NULL,1,0,'F','0','0','system:alarmConfig:add','#','admin','2026-09-12 10:13:29',NULL,NULL,NULL),
	 (2218,'告警配置修改',2088,3,'#',NULL,NULL,NULL,1,0,'F','0','0','system:alarmConfig:edit','#','admin','2026-09-12 10:13:29',NULL,NULL,NULL),
	 (2219,'告警配置删除',2088,4,'#',NULL,NULL,NULL,1,0,'F','0','0','system:alarmConfig:remove','#','admin','2026-09-12 10:13:30',NULL,NULL,NULL);
INSERT INTO `sys_menu` (menu_id,menu_name,parent_id,order_num,`path`,component,`query`,route_name,is_frame,is_cache,menu_type,`visible`,status,perms,icon,create_by,create_time,update_by,update_time,remark) VALUES
	 (2220,'告警配置导出',2088,5,'#',NULL,NULL,NULL,1,0,'F','0','0','system:alarmConfig:export','#','admin','2026-09-12 10:13:30',NULL,NULL,NULL),
	 (2221,'数据采集记录',2087,1,'collect','system/collect/index',NULL,NULL,1,0,'C','0','0','system:collect:list','druid','admin','2026-09-14 10:32:03','admin','2026-09-14 12:58:43','数据采集记录菜单'),
	 (2222,'数据采集记录查询',2221,1,'#',NULL,NULL,NULL,1,0,'F','0','0','system:collect:query','#','admin','2026-09-14 10:32:03',NULL,NULL,NULL),
	 (2223,'数据采集记录新增',2221,2,'#',NULL,NULL,NULL,1,0,'F','0','0','system:collect:add','#','admin','2026-09-14 10:32:03',NULL,NULL,NULL),
	 (2224,'数据采集记录修改',2221,3,'#',NULL,NULL,NULL,1,0,'F','0','0','system:collect:edit','#','admin','2026-09-14 10:32:03',NULL,NULL,NULL),
	 (2225,'数据采集记录删除',2221,4,'#',NULL,NULL,NULL,1,0,'F','0','0','system:collect:remove','#','admin','2026-09-14 10:32:03',NULL,NULL,NULL),
	 (2226,'数据采集记录导出',2221,5,'#',NULL,NULL,NULL,1,0,'F','0','0','system:collect:export','#','admin','2026-09-14 10:32:04',NULL,NULL,NULL),
	 (2227,'录像管理',2231,2,'surveillance','robot/surveillance/index',NULL,NULL,1,0,'C','0','0','robot:surveillance:list','monitor','admin','2026-09-15 12:09:06','admin','2026-09-15 12:35:10','机器人巡检监控菜单'),
	 (2228,'巡检查询',2227,1,NULL,NULL,NULL,NULL,1,0,'F','0','0','robot:surveillance:query','#','admin','2026-09-15 12:09:06',NULL,NULL,NULL),
	 (2229,'视频播放',2227,2,NULL,NULL,NULL,NULL,1,0,'F','0','0','robot:surveillance:play','#','admin','2026-09-15 12:09:06',NULL,NULL,NULL);
INSERT INTO `sys_menu` (menu_id,menu_name,parent_id,order_num,`path`,component,`query`,route_name,is_frame,is_cache,menu_type,`visible`,status,perms,icon,create_by,create_time,update_by,update_time,remark) VALUES
	 (2230,'视频下载',2227,3,NULL,NULL,NULL,NULL,1,0,'F','0','0','robot:surveillance:download','#','admin','2026-09-15 12:09:06',NULL,NULL,NULL),
	 (2231,'录像管理',0,5,NULL,NULL,NULL,NULL,1,0,'M','0','0',NULL,'monitor','admin','2026-09-15 12:33:54','admin','2026-09-15 12:34:41',NULL),
	 (2232,'设备自检',2087,10,'statusCheck','core/statusCheck/index',null,null,1,0,'C','0','0','core:vehicle:statusCheck','monitor','admin','2026-09-20 17:51:02',NULL,null,'机器人插件状态检测页面'),
     (2233,'自检',2232,1,NULL,NULL,null,null,1,0,'F','0','0','core:vehicle:statusCheck','#','admin','2026-09-20 17:51:02',NULL,null,'插件状态检测执行按钮'),
	 (2234,'商业授权','1','10','license','system/license/index',NULL,NULL,'1','0','C','0','0','system:license:list','lock','admin','2026-09-28 14:50:43','admin','2026-09-28 16:11:15','商业授权管理与更新'),
	 (2235,'授权查询','2234','1',NULL,NULL,NULL,NULL,'1','0','F','0','0','system:license:query','#','admin','2026-09-28 14:50:52',NULL,NULL,'查询商业授权信息与机器码'),
	 (2236,'上传授权','2234','2',NULL,NULL,NULL,NULL,'1','0','F','0','0','system:license:upload','#','admin','2026-09-28 14:50:55',NULL,NULL,'上传更新商业授权证书文件');
INSERT INTO `sys_role` (role_id,role_name,role_key,role_sort,data_scope,menu_check_strictly,dept_check_strictly,status,del_flag,create_by,create_time,update_by,update_time,remark) VALUES
	 (1,'超级管理员','admin',1,'1',1,1,'0','0','admin','2025-06-25 03:56:15',NULL,NULL,'超级管理员');
INSERT INTO `sys_user` (user_id,dept_id,user_name,nick_name,user_type,email,phonenumber,sex,avatar,`password`,status,del_flag,login_ip,login_date,pwd_update_date,create_by,create_time,update_by,update_time,remark) VALUES
	 (1,1,'admin','管理员','00','773807831@qq.com','13000000000','0',NULL,'$2a$10$7JB720yubVSZvUI0rEqK/.VqGOZTH.ulu33dHOiBE8ByOhJIrdAu2','0','0','127.0.0.1','2026-09-17 12:00:05.028','2025-06-25 03:56:13','admin','2025-06-25 03:56:13',NULL,'2026-09-17 12:00:01.783249','管理员');
INSERT INTO `sys_user_role` (user_id,role_id) VALUES
	 (1,1);

COMMIT;

SET FOREIGN_KEY_CHECKS = 1;
-- 数据库初始化完成
