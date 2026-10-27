-- gaussdb.gen_table 定义
CREATE TABLE gen_table (
    table_id          BIGSERIAL PRIMARY KEY,
    table_name        VARCHAR(200) DEFAULT '',
    table_comment     VARCHAR(500) DEFAULT '',
    sub_table_name    VARCHAR(64) DEFAULT NULL,
    sub_table_fk_name VARCHAR(64) DEFAULT NULL,
    class_name        VARCHAR(100) DEFAULT '',
    tpl_category      VARCHAR(200) DEFAULT 'crud',
    tpl_web_type      VARCHAR(30) DEFAULT '',
    package_name      VARCHAR(100) DEFAULT NULL,
    module_name       VARCHAR(30) DEFAULT NULL,
    business_name     VARCHAR(30) DEFAULT NULL,
    function_name     VARCHAR(50) DEFAULT NULL,
    function_author   VARCHAR(50) DEFAULT NULL,
    gen_type          CHAR(1) DEFAULT '0',
    gen_path          VARCHAR(200) DEFAULT '/',
    options           VARCHAR(1000) DEFAULT NULL,
    create_by         VARCHAR(64) DEFAULT '',
    create_time       TIMESTAMP DEFAULT NULL,
    update_by         VARCHAR(64) DEFAULT '',
    update_time       TIMESTAMP DEFAULT NULL,
    remark            VARCHAR(500) DEFAULT NULL
);

COMMENT ON TABLE  gen_table                    IS '代码生成业务表';
COMMENT ON COLUMN gen_table.table_id           IS '编号';
COMMENT ON COLUMN gen_table.table_name         IS '表名称';
COMMENT ON COLUMN gen_table.table_comment      IS '表描述';
COMMENT ON COLUMN gen_table.sub_table_name     IS '关联子表的表名';
COMMENT ON COLUMN gen_table.sub_table_fk_name  IS '子表关联的外键名';
COMMENT ON COLUMN gen_table.class_name         IS '实体类名称';
COMMENT ON COLUMN gen_table.tpl_category       IS '使用的模板（crud单表操作 tree树表操作）';
COMMENT ON COLUMN gen_table.tpl_web_type       IS '前端模板类型（element-ui模版 element-plus模版）';
COMMENT ON COLUMN gen_table.package_name       IS '生成包路径';
COMMENT ON COLUMN gen_table.module_name        IS '生成模块名';
COMMENT ON COLUMN gen_table.business_name      IS '生成业务名';
COMMENT ON COLUMN gen_table.function_name      IS '生成功能名';
COMMENT ON COLUMN gen_table.function_author    IS '生成功能作者';
COMMENT ON COLUMN gen_table.gen_type           IS '生成代码方式（0zip压缩包 1自定义路径）';
COMMENT ON COLUMN gen_table.gen_path           IS '生成路径（不填默认项目路径）';
COMMENT ON COLUMN gen_table.options            IS '其它生成选项';
COMMENT ON COLUMN gen_table.create_by          IS '创建者';
COMMENT ON COLUMN gen_table.create_time        IS '创建时间';
COMMENT ON COLUMN gen_table.update_by          IS '更新者';
COMMENT ON COLUMN gen_table.update_time        IS '更新时间';
COMMENT ON COLUMN gen_table.remark             IS '备注';

-- gaussdb.gen_table_column 定义
CREATE TABLE gen_table_column (
    column_id       BIGSERIAL PRIMARY KEY,
    table_id        BIGINT DEFAULT NULL,
    column_name     VARCHAR(200) DEFAULT NULL,
    column_comment  VARCHAR(500) DEFAULT NULL,
    column_type     VARCHAR(100) DEFAULT NULL,
    java_type       VARCHAR(500) DEFAULT NULL,
    java_field      VARCHAR(200) DEFAULT NULL,
    is_pk           CHAR(1) DEFAULT NULL,
    is_increment    CHAR(1) DEFAULT NULL,
    is_required     CHAR(1) DEFAULT NULL,
    is_insert       CHAR(1) DEFAULT NULL,
    is_edit         CHAR(1) DEFAULT NULL,
    is_list         CHAR(1) DEFAULT NULL,
    is_query        CHAR(1) DEFAULT NULL,
    query_type      VARCHAR(200) DEFAULT 'EQ',
    html_type       VARCHAR(200) DEFAULT NULL,
    dict_type       VARCHAR(200) DEFAULT '',
    sort            INTEGER DEFAULT NULL,
    create_by       VARCHAR(64) DEFAULT '',
    create_time     TIMESTAMP DEFAULT NULL,
    update_by       VARCHAR(64) DEFAULT '',
    update_time     TIMESTAMP DEFAULT NULL
);

COMMENT ON TABLE  gen_table_column                 IS '代码生成业务表字段';
COMMENT ON COLUMN gen_table_column.column_id       IS '编号';
COMMENT ON COLUMN gen_table_column.table_id        IS '归属表编号';
COMMENT ON COLUMN gen_table_column.column_name     IS '列名称';
COMMENT ON COLUMN gen_table_column.column_comment  IS '列描述';
COMMENT ON COLUMN gen_table_column.column_type     IS '列类型';
COMMENT ON COLUMN gen_table_column.java_type       IS 'JAVA类型';
COMMENT ON COLUMN gen_table_column.java_field      IS 'JAVA字段名';
COMMENT ON COLUMN gen_table_column.is_pk           IS '是否主键（1是）';
COMMENT ON COLUMN gen_table_column.is_increment    IS '是否自增（1是）';
COMMENT ON COLUMN gen_table_column.is_required     IS '是否必填（1是）';
COMMENT ON COLUMN gen_table_column.is_insert       IS '是否为插入字段（1是）';
COMMENT ON COLUMN gen_table_column.is_edit         IS '是否编辑字段（1是）';
COMMENT ON COLUMN gen_table_column.is_list         IS '是否列表字段（1是）';
COMMENT ON COLUMN gen_table_column.is_query        IS '是否查询字段（1是）';
COMMENT ON COLUMN gen_table_column.query_type      IS '查询方式（等于、不等于、大于、小于、范围）';
COMMENT ON COLUMN gen_table_column.html_type       IS '显示类型（文本框、文本域、下拉框、复选框、单选框、日期控件）';
COMMENT ON COLUMN gen_table_column.dict_type       IS '字典类型';
COMMENT ON COLUMN gen_table_column.sort            IS '排序';
COMMENT ON COLUMN gen_table_column.create_by       IS '创建者';
COMMENT ON COLUMN gen_table_column.create_time     IS '创建时间';
COMMENT ON COLUMN gen_table_column.update_by       IS '更新者';
COMMENT ON COLUMN gen_table_column.update_time     IS '更新时间';

-- gaussdb.robot_ability_debug 定义
CREATE TABLE robot_ability_debug (
    id            BIGSERIAL PRIMARY KEY,
    robot_id      VARCHAR(55)  DEFAULT NULL,
    msg_id        VARCHAR(255) DEFAULT NULL,
    operation     VARCHAR(255) DEFAULT NULL,
    step_type     VARCHAR(255) DEFAULT NULL,
    action        VARCHAR(255) DEFAULT NULL,
    destination   VARCHAR(255) DEFAULT NULL,
    ability_info  TEXT         DEFAULT NULL,
    result        VARCHAR(255) DEFAULT NULL,
    msg_info      TEXT         DEFAULT NULL,
    data_info     TEXT         DEFAULT NULL,
    "timestamp"   TIMESTAMP    DEFAULT NULL,
    description   VARCHAR(255) DEFAULT NULL,
    ext1          VARCHAR(16)  DEFAULT NULL,
    ext2          VARCHAR(255) DEFAULT NULL,
    ext3          VARCHAR(500) DEFAULT NULL,
    ext4          VARCHAR(255) DEFAULT NULL,
    create_by     VARCHAR(64)  DEFAULT '',
    create_time   TIMESTAMP    DEFAULT NULL,
    update_by     VARCHAR(64)  DEFAULT '',
    update_time   TIMESTAMP    DEFAULT NULL,
    del_flag      CHAR(1)      DEFAULT '0'
);

COMMENT ON TABLE  robot_ability_debug               IS '机器人调试表';
COMMENT ON COLUMN robot_ability_debug.id            IS '主键ID';
COMMENT ON COLUMN robot_ability_debug.robot_id      IS '机器人ID/车辆ID';
COMMENT ON COLUMN robot_ability_debug.msg_id        IS '步骤ID';
COMMENT ON COLUMN robot_ability_debug.operation     IS '操作类型';
COMMENT ON COLUMN robot_ability_debug.step_type     IS '步骤类型';
COMMENT ON COLUMN robot_ability_debug.action        IS '步骤操作';
COMMENT ON COLUMN robot_ability_debug.destination   IS '目的地';
COMMENT ON COLUMN robot_ability_debug.ability_info  IS '下发的调试数据';
COMMENT ON COLUMN robot_ability_debug.result        IS '执行结果：初始(系统赋值)/开始/成功/失败(init/start/success/fail)';
COMMENT ON COLUMN robot_ability_debug.msg_info      IS '结果原因';
COMMENT ON COLUMN robot_ability_debug.data_info     IS '响应回复数据详情';
COMMENT ON COLUMN robot_ability_debug."timestamp"   IS '下发时间';
COMMENT ON COLUMN robot_ability_debug.description   IS '描述';
COMMENT ON COLUMN robot_ability_debug.ext1          IS '备用1';
COMMENT ON COLUMN robot_ability_debug.ext2          IS '备用2';
COMMENT ON COLUMN robot_ability_debug.ext3          IS '备用3';
COMMENT ON COLUMN robot_ability_debug.ext4          IS '备用4';
COMMENT ON COLUMN robot_ability_debug.create_by     IS '创建者';
COMMENT ON COLUMN robot_ability_debug.create_time   IS '创建时间';
COMMENT ON COLUMN robot_ability_debug.update_by     IS '更新者';
COMMENT ON COLUMN robot_ability_debug.update_time   IS '更新时间';
COMMENT ON COLUMN robot_ability_debug.del_flag      IS '删除标志（0存在 2删除）';

-- gaussdb.robot_alarm_config 定义
CREATE TABLE robot_alarm_config (
    id              BIGSERIAL PRIMARY KEY,
    robot_id        VARCHAR(55)  DEFAULT NULL,
    plugin_type     VARCHAR(64)  DEFAULT NULL,
    gas_type        VARCHAR(64)  DEFAULT NULL,
    alarm_level     VARCHAR(64)  DEFAULT NULL,
    config_operator VARCHAR(64)  DEFAULT NULL,
    config_value    VARCHAR(255) DEFAULT NULL,
    message         VARCHAR(500) DEFAULT NULL,
    ext1            VARCHAR(55)  DEFAULT NULL,
    ext2            VARCHAR(55)  DEFAULT NULL,
    ext3            VARCHAR(55)  DEFAULT NULL,
    ext4            VARCHAR(55)  DEFAULT NULL,
    status          INTEGER      DEFAULT 1,
    create_by       VARCHAR(64)  DEFAULT '',
    create_time     TIMESTAMP    DEFAULT NULL,
    update_by       VARCHAR(64)  DEFAULT '',
    update_time     TIMESTAMP    DEFAULT NULL,
    del_flag        CHAR(1)      DEFAULT '0'
);

COMMENT ON TABLE  robot_alarm_config                 IS '告警配置';
COMMENT ON COLUMN robot_alarm_config.id              IS '主键ID';
COMMENT ON COLUMN robot_alarm_config.robot_id        IS '机器人ID';
COMMENT ON COLUMN robot_alarm_config.plugin_type     IS '插件类型';
COMMENT ON COLUMN robot_alarm_config.gas_type        IS '告警类型';
COMMENT ON COLUMN robot_alarm_config.alarm_level     IS '告警级别';
COMMENT ON COLUMN robot_alarm_config.config_operator IS '区间类型';
COMMENT ON COLUMN robot_alarm_config.config_value    IS '告警值';
COMMENT ON COLUMN robot_alarm_config.message         IS '描述';
COMMENT ON COLUMN robot_alarm_config.ext1            IS '备用1';
COMMENT ON COLUMN robot_alarm_config.ext2            IS '备用2';
COMMENT ON COLUMN robot_alarm_config.ext3            IS '备用3';
COMMENT ON COLUMN robot_alarm_config.ext4            IS '备用4';
COMMENT ON COLUMN robot_alarm_config.status          IS '状态：1=启用，0=禁用';
COMMENT ON COLUMN robot_alarm_config.create_by       IS '创建者';
COMMENT ON COLUMN robot_alarm_config.create_time     IS '创建时间';
COMMENT ON COLUMN robot_alarm_config.update_by       IS '更新者';
COMMENT ON COLUMN robot_alarm_config.update_time     IS '更新时间';
COMMENT ON COLUMN robot_alarm_config.del_flag        IS '删除标志：0=未删除，1=已删除';

-- gaussdb.robot_config 定义
CREATE TABLE robot_config (
    id           BIGSERIAL PRIMARY KEY,
    config_name  VARCHAR(255)  NOT NULL,
    config_key   VARCHAR(255)  NOT NULL,
    config_value VARCHAR(1000) NOT NULL,
    create_by    VARCHAR(64)   DEFAULT '',
    create_time  TIMESTAMP     DEFAULT NULL,
    update_by    VARCHAR(64)   DEFAULT '',
    update_time  TIMESTAMP     DEFAULT NULL,
    remark       VARCHAR(500)  DEFAULT NULL,
    CONSTRAINT uk_config_key UNIQUE (config_key)
);

COMMENT ON TABLE  robot_config              IS '机器人相关参数配置表';
COMMENT ON COLUMN robot_config.id           IS '主键ID';
COMMENT ON COLUMN robot_config.config_name  IS '配置项名称';
COMMENT ON COLUMN robot_config.config_key   IS '配置键';
COMMENT ON COLUMN robot_config.config_value IS '配置值';
COMMENT ON COLUMN robot_config.create_by    IS '创建者';
COMMENT ON COLUMN robot_config.create_time  IS '创建时间';
COMMENT ON COLUMN robot_config.update_by    IS '更新者';
COMMENT ON COLUMN robot_config.update_time  IS '更新时间';
COMMENT ON COLUMN robot_config.remark       IS '备注';

-- gaussdb.robot_device 定义
CREATE TABLE robot_device (
    id                  BIGSERIAL PRIMARY KEY,
    robot_id            VARCHAR(255) DEFAULT NULL,
    ability_type        VARCHAR(50)  DEFAULT NULL,
    ability_name        VARCHAR(20)  DEFAULT NULL,
    ability_description TEXT         DEFAULT NULL,
    action_json         TEXT         DEFAULT NULL,
    ext1                TEXT         DEFAULT NULL,
    ext2                TEXT         DEFAULT NULL,
    ext3                VARCHAR(16)  DEFAULT NULL,
    ext4                VARCHAR(16)  DEFAULT NULL,
    remark              VARCHAR(500) DEFAULT NULL,
    create_by           VARCHAR(64)  DEFAULT '',
    create_time         TIMESTAMP    DEFAULT NULL,
    update_by           VARCHAR(64)  DEFAULT '',
    update_time         TIMESTAMP    DEFAULT NULL,
    del_flag            CHAR(1)      DEFAULT '0'
);

COMMENT ON TABLE  robot_device                     IS '机器人设备';
COMMENT ON COLUMN robot_device.id                  IS '主键ID';
COMMENT ON COLUMN robot_device.robot_id            IS '机器人id';
COMMENT ON COLUMN robot_device.ability_type        IS '能力类型  door_control：开门机控制 robot_arm_control：机械臂控制 partial_discharge_control：局放控制 elevator_control：电梯控制 camera_control：摄像机控制 ptz_control：云台控制 robot_dog_navigation：机械狗导航控制';
COMMENT ON COLUMN robot_device.ability_name        IS '能力名称';
COMMENT ON COLUMN robot_device.ability_description IS '能力描述';
COMMENT ON COLUMN robot_device.action_json         IS '动作JSON';
COMMENT ON COLUMN robot_device.ext1                IS '告警配置列表';
COMMENT ON COLUMN robot_device.ext2                IS '告警配置列表';
COMMENT ON COLUMN robot_device.ext3                IS '备用3';
COMMENT ON COLUMN robot_device.ext4                IS '备用4';
COMMENT ON COLUMN robot_device.remark              IS '备注';
COMMENT ON COLUMN robot_device.create_by           IS '创建者';
COMMENT ON COLUMN robot_device.create_time         IS '创建时间';
COMMENT ON COLUMN robot_device.update_by           IS '更新者';
COMMENT ON COLUMN robot_device.update_time         IS '更新时间';
COMMENT ON COLUMN robot_device.del_flag            IS '删除标志（0代表存在 2代表删除）';

-- gaussdb.robot_device_type 定义
CREATE TABLE robot_device_type (
    id          BIGSERIAL PRIMARY KEY,
    parent_id   BIGINT       NOT NULL DEFAULT 0,
    type_level  INTEGER      NOT NULL,
    type_name   VARCHAR(255) NOT NULL,
    type_value  VARCHAR(255) NOT NULL,
    create_by   VARCHAR(64)  DEFAULT '',
    create_time TIMESTAMP    DEFAULT NULL,
    update_by   VARCHAR(64)  DEFAULT '',
    update_time TIMESTAMP    DEFAULT NULL,
    icon_img    VARCHAR(255) DEFAULT NULL,
    ext1        VARCHAR(255) DEFAULT NULL,
    ext2        VARCHAR(255) DEFAULT NULL,
    ext3        VARCHAR(255) DEFAULT NULL,
    ext4        VARCHAR(255) DEFAULT NULL,
    remark      VARCHAR(500) DEFAULT NULL
);

CREATE INDEX uk_parent_id ON robot_device_type (parent_id);

COMMENT ON TABLE  robot_device_type             IS '机器人设备类型表';
COMMENT ON COLUMN robot_device_type.id          IS '主键ID';
COMMENT ON COLUMN robot_device_type.parent_id   IS '上级ID';
COMMENT ON COLUMN robot_device_type.type_level  IS '层级';
COMMENT ON COLUMN robot_device_type.type_name   IS '类型名称';
COMMENT ON COLUMN robot_device_type.type_value  IS '类型值';
COMMENT ON COLUMN robot_device_type.create_by   IS '创建者';
COMMENT ON COLUMN robot_device_type.create_time IS '创建时间';
COMMENT ON COLUMN robot_device_type.update_by   IS '更新者';
COMMENT ON COLUMN robot_device_type.update_time IS '更新时间';
COMMENT ON COLUMN robot_device_type.icon_img    IS '图标';
COMMENT ON COLUMN robot_device_type.ext1        IS '备用1';
COMMENT ON COLUMN robot_device_type.ext2        IS '备用2';
COMMENT ON COLUMN robot_device_type.ext3        IS '备用3';
COMMENT ON COLUMN robot_device_type.ext4        IS '备用4';
COMMENT ON COLUMN robot_device_type.remark      IS '备注';

-- gaussdb.robot_display_config 定义
CREATE TABLE robot_display_config (
    id          BIGSERIAL PRIMARY KEY,
    robot_id    VARCHAR(55)  DEFAULT NULL,
    plugin_type VARCHAR(64)  DEFAULT NULL,
    plugin_name VARCHAR(255) DEFAULT NULL,
    action      VARCHAR(128) DEFAULT NULL,
    name        VARCHAR(255) DEFAULT NULL,
    description VARCHAR(500) DEFAULT NULL,
    params      TEXT         DEFAULT NULL,
    scopes      TEXT         DEFAULT NULL,
    create_by   VARCHAR(64)  DEFAULT '',
    create_time TIMESTAMP    DEFAULT NULL,
    update_by   VARCHAR(64)  DEFAULT '',
    update_time TIMESTAMP    DEFAULT NULL,
    del_flag    CHAR(1)      DEFAULT '0'
);

CREATE INDEX idx_robot_display_config_robot_id ON robot_display_config (robot_id);

COMMENT ON TABLE  robot_display_config              IS '机器人界面配置表';
COMMENT ON COLUMN robot_display_config.id           IS '主键ID';
COMMENT ON COLUMN robot_display_config.robot_id     IS '机器人ID';
COMMENT ON COLUMN robot_display_config.plugin_type  IS '插件类型';
COMMENT ON COLUMN robot_display_config.plugin_name  IS '插件名称';
COMMENT ON COLUMN robot_display_config.action       IS '操作';
COMMENT ON COLUMN robot_display_config.name         IS '名称';
COMMENT ON COLUMN robot_display_config.description  IS '描述';
COMMENT ON COLUMN robot_display_config.params       IS '参数';
COMMENT ON COLUMN robot_display_config.scopes       IS '应用范围';
COMMENT ON COLUMN robot_display_config.create_by    IS '创建者';
COMMENT ON COLUMN robot_display_config.create_time  IS '创建时间';
COMMENT ON COLUMN robot_display_config.update_by    IS '更新者';
COMMENT ON COLUMN robot_display_config.update_time  IS '更新时间';
COMMENT ON COLUMN robot_display_config.del_flag     IS '删除标志：0=未删除，1=已删除';

-- gaussdb.robot_gas_sensor 定义
CREATE TABLE robot_gas_sensor (
    id          BIGSERIAL PRIMARY KEY,
    robot_id    VARCHAR(64)  DEFAULT NULL,
    msg_id      VARCHAR(64)  DEFAULT NULL,
    sensor_no   VARCHAR(11)  DEFAULT NULL,
    gas_name    VARCHAR(64)  DEFAULT NULL,
    gas_value   VARCHAR(10)  DEFAULT NULL,
    gas_unit    VARCHAR(32)  DEFAULT NULL,
    result      VARCHAR(32)  DEFAULT NULL,
    reason      VARCHAR(512) DEFAULT NULL,
    create_time TIMESTAMP    DEFAULT NULL,
    update_time TIMESTAMP    DEFAULT NULL,
    ext1        VARCHAR(16)  DEFAULT NULL,
    ext2        VARCHAR(255) DEFAULT NULL,
    ext3        VARCHAR(500) DEFAULT NULL,
    ext4        VARCHAR(255) DEFAULT NULL,
    create_by   VARCHAR(64)  DEFAULT '',
    update_by   VARCHAR(64)  DEFAULT '',
    del_flag    CHAR(1)      DEFAULT '0'
);

COMMENT ON TABLE  robot_gas_sensor             IS '设备气体传感器数据表';
COMMENT ON COLUMN robot_gas_sensor.id          IS '主键ID';
COMMENT ON COLUMN robot_gas_sensor.robot_id    IS '设备编号';
COMMENT ON COLUMN robot_gas_sensor.msg_id      IS '指令ID/消息ID';
COMMENT ON COLUMN robot_gas_sensor.sensor_no   IS '传感器编号 1/2/3...';
COMMENT ON COLUMN robot_gas_sensor.gas_name    IS '气体名称';
COMMENT ON COLUMN robot_gas_sensor.gas_value   IS '气体浓度值';
COMMENT ON COLUMN robot_gas_sensor.gas_unit    IS '单位';
COMMENT ON COLUMN robot_gas_sensor.result      IS '执行结果 start/success/fail';
COMMENT ON COLUMN robot_gas_sensor.reason      IS '失败原因';
COMMENT ON COLUMN robot_gas_sensor.create_time IS '创建时间';
COMMENT ON COLUMN robot_gas_sensor.update_time IS '更新时间';
COMMENT ON COLUMN robot_gas_sensor.ext1        IS '备用1';
COMMENT ON COLUMN robot_gas_sensor.ext2        IS '备用2';
COMMENT ON COLUMN robot_gas_sensor.ext3        IS '备用3';
COMMENT ON COLUMN robot_gas_sensor.ext4        IS '备用4';
COMMENT ON COLUMN robot_gas_sensor.create_by   IS '创建者';
COMMENT ON COLUMN robot_gas_sensor.update_by   IS '更新者';
COMMENT ON COLUMN robot_gas_sensor.del_flag    IS '删除标志（0存在 2删除）';

-- gaussdb.robot_hidden_danger 定义
CREATE TABLE robot_hidden_danger (
    id                  BIGSERIAL PRIMARY KEY,
    alert_id            VARCHAR(50)  DEFAULT NULL,
    device_id           VARCHAR(50)  DEFAULT NULL,
    device_name         VARCHAR(50)  DEFAULT NULL,
    device_desc         VARCHAR(255) DEFAULT NULL,
    source_id           VARCHAR(50)  DEFAULT NULL,
    source_desc         VARCHAR(255) DEFAULT NULL,
    source_ip           VARCHAR(50)  DEFAULT NULL,
    alg_name            VARCHAR(50)  DEFAULT NULL,
    alg_ch_name         VARCHAR(50)  DEFAULT NULL,
    alg_type            VARCHAR(50)  DEFAULT NULL,
    hazard_level        VARCHAR(50)  DEFAULT NULL,
    image               TEXT         DEFAULT NULL,
    alert_time          TIMESTAMP    DEFAULT NULL,
    status              VARCHAR(10)  DEFAULT NULL,
    handler             VARCHAR(50)  DEFAULT NULL,
    handling_suggestion VARCHAR(500) DEFAULT NULL,
    handling_time       TIMESTAMP    DEFAULT NULL,
    ext1                VARCHAR(255) DEFAULT NULL,
    ext2                VARCHAR(16)  DEFAULT NULL,
    ext3                VARCHAR(16)  DEFAULT NULL,
    ext4                VARCHAR(16)  DEFAULT NULL,
    remark              VARCHAR(500) DEFAULT NULL,
    create_by           VARCHAR(64)  DEFAULT '',
    create_time         TIMESTAMP    DEFAULT NULL,
    update_by           VARCHAR(64)  DEFAULT '',
    update_time         TIMESTAMP    DEFAULT NULL,
    del_flag            CHAR(1)      DEFAULT '0'
);

COMMENT ON TABLE  robot_hidden_danger                     IS '隐患跟进表';
COMMENT ON COLUMN robot_hidden_danger.id                  IS 'id';
COMMENT ON COLUMN robot_hidden_danger.alert_id            IS '告警id';
COMMENT ON COLUMN robot_hidden_danger.device_id           IS '设备id';
COMMENT ON COLUMN robot_hidden_danger.device_name         IS '设备名称';
COMMENT ON COLUMN robot_hidden_danger.device_desc         IS '设备描述';
COMMENT ON COLUMN robot_hidden_danger.source_id           IS '数据源id';
COMMENT ON COLUMN robot_hidden_danger.source_desc         IS '数据源描述';
COMMENT ON COLUMN robot_hidden_danger.source_ip           IS '数据源ip';
COMMENT ON COLUMN robot_hidden_danger.alg_name            IS '算法名称';
COMMENT ON COLUMN robot_hidden_danger.alg_ch_name         IS '算法显示名称';
COMMENT ON COLUMN robot_hidden_danger.alg_type            IS 'general';
COMMENT ON COLUMN robot_hidden_danger.hazard_level        IS '危险等级';
COMMENT ON COLUMN robot_hidden_danger.image               IS 'base64编码的图片数据';
COMMENT ON COLUMN robot_hidden_danger.alert_time          IS '告警时间';
COMMENT ON COLUMN robot_hidden_danger.status              IS '状态';
COMMENT ON COLUMN robot_hidden_danger.handler             IS '处理人';
COMMENT ON COLUMN robot_hidden_danger.handling_suggestion IS '处理意见';
COMMENT ON COLUMN robot_hidden_danger.handling_time       IS '处理时间';
COMMENT ON COLUMN robot_hidden_danger.ext1                IS '备用1';
COMMENT ON COLUMN robot_hidden_danger.ext2                IS '备用2';
COMMENT ON COLUMN robot_hidden_danger.ext3                IS '备用3';
COMMENT ON COLUMN robot_hidden_danger.ext4                IS '备用4';
COMMENT ON COLUMN robot_hidden_danger.remark              IS '备注';
COMMENT ON COLUMN robot_hidden_danger.create_by           IS '创建者';
COMMENT ON COLUMN robot_hidden_danger.create_time         IS '创建时间';
COMMENT ON COLUMN robot_hidden_danger.update_by           IS '更新者';
COMMENT ON COLUMN robot_hidden_danger.update_time         IS '更新时间';
COMMENT ON COLUMN robot_hidden_danger.del_flag            IS '删除标志（0代表存在 2代表删除）';

-- gaussdb.robot_lora_relay 定义
CREATE TABLE robot_lora_relay (
    id                    BIGSERIAL PRIMARY KEY,
    robot_id              VARCHAR(55)   DEFAULT NULL,
    relay_no              VARCHAR(64)   DEFAULT NULL,
    relay_name            VARCHAR(255)  DEFAULT NULL,
    voltage               NUMERIC(10,3) DEFAULT NULL,
    normal_voltage_lower  NUMERIC(10,3) DEFAULT 2.600,
    normal_voltage_upper  NUMERIC(10,3) DEFAULT 3.600,
    report_time           TIMESTAMP     DEFAULT NULL,
    raw_message           TEXT          DEFAULT NULL,
    remark                VARCHAR(500)  DEFAULT NULL,
    create_by             VARCHAR(64)   DEFAULT NULL,
    create_time           TIMESTAMP     DEFAULT NULL,
    update_by             VARCHAR(64)   DEFAULT NULL,
    update_time           TIMESTAMP     DEFAULT NULL,
    CONSTRAINT uk_robot_lora_relay_no UNIQUE (relay_no)
);

COMMENT ON TABLE  robot_lora_relay                      IS 'LoRa中继管理表';
COMMENT ON COLUMN robot_lora_relay.id                   IS '主键ID';
COMMENT ON COLUMN robot_lora_relay.robot_id             IS '机器人ID';
COMMENT ON COLUMN robot_lora_relay.relay_no             IS '中继编号';
COMMENT ON COLUMN robot_lora_relay.relay_name           IS '中继名称';
COMMENT ON COLUMN robot_lora_relay.voltage              IS '电量：电压(V)';
COMMENT ON COLUMN robot_lora_relay.normal_voltage_lower IS '正常电压下限(V)';
COMMENT ON COLUMN robot_lora_relay.normal_voltage_upper IS '正常电压上限(V)';
COMMENT ON COLUMN robot_lora_relay.report_time          IS '上报时间';
COMMENT ON COLUMN robot_lora_relay.raw_message          IS '原始报文';
COMMENT ON COLUMN robot_lora_relay.remark               IS '备注';
COMMENT ON COLUMN robot_lora_relay.create_by            IS '创建者';
COMMENT ON COLUMN robot_lora_relay.create_time          IS '创建时间';
COMMENT ON COLUMN robot_lora_relay.update_by            IS '更新者';
COMMENT ON COLUMN robot_lora_relay.update_time          IS '更新时间';

-- gaussdb.robot_map 定义
CREATE TABLE robot_map (
    id             BIGSERIAL PRIMARY KEY,
    map_name       VARCHAR(255) DEFAULT NULL,
    coding         VARCHAR(50)  DEFAULT NULL,
    map_img_2d     VARCHAR(255) DEFAULT NULL,
    map_2d_las     VARCHAR(255) DEFAULT NULL,
    map_2d_info    TEXT         DEFAULT NULL,
    map_img_3d     VARCHAR(255) DEFAULT NULL,
    map_versions_id BIGINT      DEFAULT NULL,
    status         CHAR(1)      NOT NULL,
    versions       INTEGER      DEFAULT NULL,
    ext1           VARCHAR(255) DEFAULT NULL,
    ext2           VARCHAR(16)  DEFAULT NULL,
    ext3           VARCHAR(16)  DEFAULT NULL,
    ext4           VARCHAR(255) DEFAULT NULL,
    remark         VARCHAR(500) DEFAULT NULL,
    create_by      VARCHAR(64)  DEFAULT '',
    create_time    TIMESTAMP    DEFAULT NULL,
    update_by      VARCHAR(64)  DEFAULT '',
    update_time    TIMESTAMP    DEFAULT NULL,
    del_flag       CHAR(1)      DEFAULT '0'
);

COMMENT ON TABLE  robot_map                 IS '地图表';
COMMENT ON COLUMN robot_map.id              IS '主键ID';
COMMENT ON COLUMN robot_map.map_name        IS '名称';
COMMENT ON COLUMN robot_map.coding          IS '编码';
COMMENT ON COLUMN robot_map.map_img_2d      IS '地图2d';
COMMENT ON COLUMN robot_map.map_2d_las      IS '2d  las 文件';
COMMENT ON COLUMN robot_map.map_2d_info     IS '2d 拓展信息';
COMMENT ON COLUMN robot_map.map_img_3d      IS '地图3d';
COMMENT ON COLUMN robot_map.map_versions_id IS '发布的地图版本id';
COMMENT ON COLUMN robot_map.status          IS '发布表示 0：未发布，1：已发布';
COMMENT ON COLUMN robot_map.versions        IS '版本';
COMMENT ON COLUMN robot_map.ext1            IS '平面图文件';
COMMENT ON COLUMN robot_map.ext2            IS '备用2';
COMMENT ON COLUMN robot_map.ext3            IS '备用3';
COMMENT ON COLUMN robot_map.ext4            IS '备用4';
COMMENT ON COLUMN robot_map.remark          IS '备注';
COMMENT ON COLUMN robot_map.create_by       IS '创建者';
COMMENT ON COLUMN robot_map.create_time     IS '创建时间';
COMMENT ON COLUMN robot_map.update_by       IS '更新者';
COMMENT ON COLUMN robot_map.update_time     IS '更新时间';
COMMENT ON COLUMN robot_map.del_flag        IS '删除标志（0代表存在 2代表删除）';

-- gaussdb.robot_map_versions 定义
CREATE TABLE robot_map_versions (
    id              BIGSERIAL PRIMARY KEY,
    robot_map_id    BIGINT       NOT NULL,
    status          CHAR(1)      NOT NULL,
    versions        INTEGER      DEFAULT NULL,
    map_content_xml TEXT         DEFAULT NULL,
    ext1            VARCHAR(16)  DEFAULT NULL,
    ext2            VARCHAR(16)  DEFAULT NULL,
    ext3            VARCHAR(16)  DEFAULT NULL,
    ext4            VARCHAR(16)  DEFAULT NULL,
    remark          VARCHAR(500) DEFAULT NULL,
    create_by       VARCHAR(64)  DEFAULT '',
    create_time     TIMESTAMP    DEFAULT NULL,
    update_by       VARCHAR(64)  DEFAULT '',
    update_time     TIMESTAMP    DEFAULT NULL,
    del_flag        CHAR(1)      DEFAULT '0'
);

COMMENT ON TABLE  robot_map_versions                 IS '地图版本';
COMMENT ON COLUMN robot_map_versions.id              IS '主键ID';
COMMENT ON COLUMN robot_map_versions.robot_map_id    IS '地图id';
COMMENT ON COLUMN robot_map_versions.status          IS '发布表示 0：未发布，1：已发布';
COMMENT ON COLUMN robot_map_versions.versions        IS '版本';
COMMENT ON COLUMN robot_map_versions.map_content_xml IS '地图的点位数据';
COMMENT ON COLUMN robot_map_versions.ext1            IS '备用1';
COMMENT ON COLUMN robot_map_versions.ext2            IS '备用2';
COMMENT ON COLUMN robot_map_versions.ext3            IS '备用3';
COMMENT ON COLUMN robot_map_versions.ext4            IS '备用4';
COMMENT ON COLUMN robot_map_versions.remark          IS '备注';
COMMENT ON COLUMN robot_map_versions.create_by       IS '创建者';
COMMENT ON COLUMN robot_map_versions.create_time     IS '创建时间';
COMMENT ON COLUMN robot_map_versions.update_by       IS '更新者';
COMMENT ON COLUMN robot_map_versions.update_time     IS '更新时间';
COMMENT ON COLUMN robot_map_versions.del_flag        IS '删除标志（0代表存在 2代表删除）';

-- gaussdb.robot_partial_discharge 定义
CREATE TABLE robot_partial_discharge (
    id          BIGSERIAL PRIMARY KEY,
    robot_id    VARCHAR(64)  DEFAULT NULL,
    msg_id      VARCHAR(64)  DEFAULT NULL,
    result      VARCHAR(32)  DEFAULT NULL,
    reason      VARCHAR(512) DEFAULT NULL,
    max         VARCHAR(10)  DEFAULT NULL,
    avagate     VARCHAR(10)  DEFAULT NULL,
    count       VARCHAR(11)  DEFAULT NULL,
    create_time TIMESTAMP    DEFAULT NULL,
    update_time TIMESTAMP    DEFAULT NULL,
    ext1        VARCHAR(16)  DEFAULT NULL,
    ext2        VARCHAR(255) DEFAULT NULL,
    ext3        VARCHAR(500) DEFAULT NULL,
    ext4        VARCHAR(255) DEFAULT NULL,
    create_by   VARCHAR(64)  DEFAULT '',
    update_by   VARCHAR(64)  DEFAULT '',
    del_flag    CHAR(1)      DEFAULT '0'
);

COMMENT ON TABLE  robot_partial_discharge             IS '设备局放检测数据表';
COMMENT ON COLUMN robot_partial_discharge.id          IS '主键ID';
COMMENT ON COLUMN robot_partial_discharge.robot_id    IS '设备编号';
COMMENT ON COLUMN robot_partial_discharge.msg_id      IS '指令ID/消息ID';
COMMENT ON COLUMN robot_partial_discharge.result      IS '执行结果 start/success/fail';
COMMENT ON COLUMN robot_partial_discharge.reason      IS '失败原因';
COMMENT ON COLUMN robot_partial_discharge.max         IS '放电峰值';
COMMENT ON COLUMN robot_partial_discharge.avagate     IS '放电均值';
COMMENT ON COLUMN robot_partial_discharge.count       IS '放电次数';
COMMENT ON COLUMN robot_partial_discharge.create_time IS '创建时间';
COMMENT ON COLUMN robot_partial_discharge.update_time IS '更新时间';
COMMENT ON COLUMN robot_partial_discharge.ext1        IS '备用1';
COMMENT ON COLUMN robot_partial_discharge.ext2        IS '备用2';
COMMENT ON COLUMN robot_partial_discharge.ext3        IS '备用3';
COMMENT ON COLUMN robot_partial_discharge.ext4        IS '备用4';
COMMENT ON COLUMN robot_partial_discharge.create_by   IS '创建者';
COMMENT ON COLUMN robot_partial_discharge.update_by   IS '更新者';
COMMENT ON COLUMN robot_partial_discharge.del_flag    IS '删除标志（0存在 2删除）';

-- gaussdb.robot_platen_log 定义
CREATE TABLE robot_platen_log (
    id          BIGSERIAL PRIMARY KEY,
    robot_id    VARCHAR(55)  DEFAULT NULL,
    action_type VARCHAR(55)  DEFAULT NULL,
    message     VARCHAR(500) DEFAULT NULL,
    ext1        VARCHAR(225) DEFAULT NULL,
    ext2        VARCHAR(225) DEFAULT NULL,
    ext3        VARCHAR(225) DEFAULT NULL,
    ext4        VARCHAR(225) DEFAULT NULL,
    create_by   VARCHAR(64)  DEFAULT '',
    create_time TIMESTAMP    DEFAULT NULL,
    del_flag    CHAR(1)      DEFAULT '0'
);

COMMENT ON TABLE  robot_platen_log             IS '二次压板日志记录';
COMMENT ON COLUMN robot_platen_log.id          IS '主键ID';
COMMENT ON COLUMN robot_platen_log.robot_id    IS '机器人ID';
COMMENT ON COLUMN robot_platen_log.action_type IS '动作类型action';
COMMENT ON COLUMN robot_platen_log.message     IS '日志描述';
COMMENT ON COLUMN robot_platen_log.ext1        IS '备用1';
COMMENT ON COLUMN robot_platen_log.ext2        IS '备用2';
COMMENT ON COLUMN robot_platen_log.ext3        IS '备用3';
COMMENT ON COLUMN robot_platen_log.ext4        IS '备用4';
COMMENT ON COLUMN robot_platen_log.create_by   IS '创建者';
COMMENT ON COLUMN robot_platen_log.create_time IS '创建时间';
COMMENT ON COLUMN robot_platen_log.del_flag    IS '删除标志：0=未删除，1=已删除';

-- gaussdb.robot_plugin_collect 定义
CREATE TABLE robot_plugin_collect (
    id           BIGSERIAL PRIMARY KEY,
    robot_id     VARCHAR(55)  DEFAULT NULL,
    plugin_type  VARCHAR(64)  DEFAULT NULL,
    c_name       VARCHAR(64)  DEFAULT NULL,
    c_label      VARCHAR(64)  DEFAULT NULL,
    c_value      VARCHAR(64)  DEFAULT NULL,
    c_unit       VARCHAR(10)  DEFAULT NULL,
    c_status     VARCHAR(10)  DEFAULT NULL,
    sensor_id    VARCHAR(10)  DEFAULT NULL,
    channel_code VARCHAR(10)  DEFAULT NULL,
    ext1         VARCHAR(55)  DEFAULT NULL,
    ext2         VARCHAR(55)  DEFAULT NULL,
    ext3         VARCHAR(55)  DEFAULT NULL,
    ext4         VARCHAR(55)  DEFAULT NULL,
    ext5         VARCHAR(55)  DEFAULT NULL,
    create_by    VARCHAR(64)  DEFAULT '',
    create_time  TIMESTAMP    DEFAULT NULL,
    update_by    VARCHAR(64)  DEFAULT '',
    update_time  TIMESTAMP    DEFAULT NULL,
    del_flag     CHAR(1)      DEFAULT '0'
);

COMMENT ON TABLE  robot_plugin_collect              IS '插件采集表';
COMMENT ON COLUMN robot_plugin_collect.id           IS '主键ID';
COMMENT ON COLUMN robot_plugin_collect.robot_id     IS '机器人ID';
COMMENT ON COLUMN robot_plugin_collect.plugin_type  IS '插件类型';
COMMENT ON COLUMN robot_plugin_collect.c_name       IS '指标名称';
COMMENT ON COLUMN robot_plugin_collect.c_label      IS '指标名称';
COMMENT ON COLUMN robot_plugin_collect.c_value      IS '指标值';
COMMENT ON COLUMN robot_plugin_collect.c_unit       IS '计量单位';
COMMENT ON COLUMN robot_plugin_collect.c_status     IS '状态标志';
COMMENT ON COLUMN robot_plugin_collect.sensor_id    IS '硬件模组ID';
COMMENT ON COLUMN robot_plugin_collect.channel_code IS '通道编号';
COMMENT ON COLUMN robot_plugin_collect.ext1         IS '备用1';
COMMENT ON COLUMN robot_plugin_collect.ext2         IS '备用2';
COMMENT ON COLUMN robot_plugin_collect.ext3         IS '备用3';
COMMENT ON COLUMN robot_plugin_collect.ext4         IS '备用4';
COMMENT ON COLUMN robot_plugin_collect.ext5         IS '备用5';
COMMENT ON COLUMN robot_plugin_collect.create_by    IS '创建者';
COMMENT ON COLUMN robot_plugin_collect.create_time  IS '创建时间';
COMMENT ON COLUMN robot_plugin_collect.update_by    IS '更新者';
COMMENT ON COLUMN robot_plugin_collect.update_time  IS '更新时间';
COMMENT ON COLUMN robot_plugin_collect.del_flag     IS '删除标志：0=未删除，1=已删除';

-- gaussdb.robot_point 定义
CREATE TABLE robot_point (
    id           BIGSERIAL PRIMARY KEY,
    robot_map_id BIGINT       DEFAULT NULL,
    ctn_point_no VARCHAR(255) DEFAULT NULL,
    point_list   VARCHAR(500) DEFAULT NULL,
    ext1         VARCHAR(16)  DEFAULT NULL,
    ext2         VARCHAR(16)  DEFAULT NULL,
    ext3         VARCHAR(16)  DEFAULT NULL,
    ext4         VARCHAR(16)  DEFAULT NULL,
    remark       VARCHAR(500) DEFAULT NULL,
    create_by    VARCHAR(64)  DEFAULT '',
    create_time  TIMESTAMP    DEFAULT NULL,
    update_by    VARCHAR(64)  DEFAULT '',
    update_time  TIMESTAMP    DEFAULT NULL,
    del_flag     CHAR(1)      DEFAULT '0'
);

COMMENT ON TABLE  robot_point              IS '点位集合';
COMMENT ON COLUMN robot_point.id           IS '主键ID';
COMMENT ON COLUMN robot_point.robot_map_id IS '点位相关地图ID';
COMMENT ON COLUMN robot_point.ctn_point_no IS '机器人平台对应的箱体位置编号';
COMMENT ON COLUMN robot_point.point_list   IS '点位集合';
COMMENT ON COLUMN robot_point.ext1         IS '备用1';
COMMENT ON COLUMN robot_point.ext2         IS '备用2';
COMMENT ON COLUMN robot_point.ext3         IS '备用3';
COMMENT ON COLUMN robot_point.ext4         IS '备用4';
COMMENT ON COLUMN robot_point.remark       IS '备注';
COMMENT ON COLUMN robot_point.create_by    IS '创建者';
COMMENT ON COLUMN robot_point.create_time  IS '创建时间';
COMMENT ON COLUMN robot_point.update_by    IS '更新者';
COMMENT ON COLUMN robot_point.update_time  IS '更新时间';
COMMENT ON COLUMN robot_point.del_flag     IS '删除标志（0代表存在 2代表删除）';

-- gaussdb.robot_task 定义
CREATE TABLE robot_task (
    id          BIGSERIAL PRIMARY KEY,
    robot_id    VARCHAR(55)  DEFAULT NULL,
    job_id      VARCHAR(255) DEFAULT NULL,
    task_type   VARCHAR(255) DEFAULT NULL,
    task_status VARCHAR(255) DEFAULT NULL,
    status      VARCHAR(10)  DEFAULT NULL,
    ext1        VARCHAR(16)  DEFAULT NULL,
    ext2        VARCHAR(16)  DEFAULT NULL,
    ext3        VARCHAR(16)  DEFAULT NULL,
    ext4        VARCHAR(16)  DEFAULT NULL,
    remark      VARCHAR(500) DEFAULT NULL,
    create_by   VARCHAR(64)  DEFAULT '',
    create_time TIMESTAMP    DEFAULT NULL,
    update_by   VARCHAR(64)  DEFAULT '',
    update_time TIMESTAMP    DEFAULT NULL,
    del_flag    CHAR(1)      DEFAULT '0',
    online_flag CHAR(1)      DEFAULT '0'
);

COMMENT ON TABLE  robot_task              IS '主任务';
COMMENT ON COLUMN robot_task.id           IS '主键ID';
COMMENT ON COLUMN robot_task.robot_id     IS '机器人';
COMMENT ON COLUMN robot_task.job_id       IS '海港EDI-任务id';
COMMENT ON COLUMN robot_task.task_type    IS '任务类型';
COMMENT ON COLUMN robot_task.task_status  IS '任务状态';
COMMENT ON COLUMN robot_task.status       IS '机器人当前执行任务状态 0：机器人空闲状态；1：机器人有任务';
COMMENT ON COLUMN robot_task.ext1         IS '任务来源模板id';
COMMENT ON COLUMN robot_task.ext2         IS '任务来源：1:海港IDE 2:模板';
COMMENT ON COLUMN robot_task.ext3         IS '任务名称';
COMMENT ON COLUMN robot_task.ext4         IS '备用4';
COMMENT ON COLUMN robot_task.remark       IS '备注';
COMMENT ON COLUMN robot_task.create_by    IS '创建者';
COMMENT ON COLUMN robot_task.create_time  IS '创建时间';
COMMENT ON COLUMN robot_task.update_by    IS '更新者';
COMMENT ON COLUMN robot_task.update_time  IS '更新时间';
COMMENT ON COLUMN robot_task.del_flag     IS '删除标志（0代表存在 2代表删除）';
COMMENT ON COLUMN robot_task.online_flag  IS '离线任务：0在线；1离线';

-- gaussdb.robot_task_item 定义
CREATE TABLE robot_task_item (
    id          BIGSERIAL PRIMARY KEY,
    robot_id    VARCHAR(55)  DEFAULT NULL,
    task_id     VARCHAR(255) DEFAULT NULL,
    job_id      VARCHAR(255) DEFAULT NULL,
    operation   VARCHAR(255) DEFAULT NULL,
    step_id     VARCHAR(255) DEFAULT NULL,
    step_type   VARCHAR(255) DEFAULT NULL,
    action      VARCHAR(255) DEFAULT NULL,
    "timestamp" TIMESTAMP(3) DEFAULT NULL,
    destination VARCHAR(255) DEFAULT NULL,
    description VARCHAR(255) DEFAULT NULL,
    position    VARCHAR(255) DEFAULT NULL,
    state       VARCHAR(255) DEFAULT NULL,
    ext1        VARCHAR(16)  DEFAULT NULL,
    ext2        VARCHAR(255) DEFAULT NULL,
    ext3        TEXT         DEFAULT NULL,
    ext4        VARCHAR(255) DEFAULT NULL,
    remark      VARCHAR(500) DEFAULT NULL,
    create_by   VARCHAR(64)  DEFAULT '',
    create_time TIMESTAMP    DEFAULT NULL,
    update_by   VARCHAR(64)  DEFAULT '',
    update_time TIMESTAMP    DEFAULT NULL,
    del_flag    CHAR(1)      DEFAULT '0'
);

COMMENT ON TABLE  robot_task_item               IS '子任务';
COMMENT ON COLUMN robot_task_item.id            IS '主键ID';
COMMENT ON COLUMN robot_task_item.robot_id      IS '车辆';
COMMENT ON COLUMN robot_task_item.task_id       IS '任务id';
COMMENT ON COLUMN robot_task_item.job_id        IS 'pentcs-任务id';
COMMENT ON COLUMN robot_task_item.operation     IS '操作类型';
COMMENT ON COLUMN robot_task_item.step_id       IS '步骤id';
COMMENT ON COLUMN robot_task_item.step_type     IS '步骤类型';
COMMENT ON COLUMN robot_task_item.action        IS '步骤操作';
COMMENT ON COLUMN robot_task_item."timestamp"   IS '任务下发时间';
COMMENT ON COLUMN robot_task_item.destination   IS '目的地';
COMMENT ON COLUMN robot_task_item.description   IS '备注';
COMMENT ON COLUMN robot_task_item.position      IS '场地位置';
COMMENT ON COLUMN robot_task_item.state         IS '任务订单处理状态';
COMMENT ON COLUMN robot_task_item.ext1          IS '备用1';
COMMENT ON COLUMN robot_task_item.ext2          IS '备用2';
COMMENT ON COLUMN robot_task_item.ext3          IS '备用3';
COMMENT ON COLUMN robot_task_item.ext4          IS '备用4';
COMMENT ON COLUMN robot_task_item.remark        IS '备注';
COMMENT ON COLUMN robot_task_item.create_by     IS '创建者';
COMMENT ON COLUMN robot_task_item.create_time   IS '创建时间';
COMMENT ON COLUMN robot_task_item.update_by     IS '更新者';
COMMENT ON COLUMN robot_task_item.update_time   IS '更新时间';
COMMENT ON COLUMN robot_task_item.del_flag      IS '删除标志（0代表存在 2代表删除）';

-- gaussdb.robot_task_status 定义
CREATE TABLE robot_task_status (
    id           BIGSERIAL PRIMARY KEY,
    robot_id     VARCHAR(255) DEFAULT NULL,
    job_id       VARCHAR(255) DEFAULT NULL,
    command_type VARCHAR(255) DEFAULT NULL,
    msg_id       VARCHAR(255) DEFAULT NULL,
    "timestamp"  TIMESTAMP(3) DEFAULT NULL,
    result       VARCHAR(255) DEFAULT NULL,
    msg_info     VARCHAR(255) DEFAULT NULL,
    step_id      VARCHAR(255) DEFAULT NULL,
    data_info    TEXT         DEFAULT NULL,
    remark       VARCHAR(500) DEFAULT NULL,
    create_by    VARCHAR(64)  DEFAULT '',
    create_time  TIMESTAMP    DEFAULT NULL,
    update_by    VARCHAR(64)  DEFAULT '',
    update_time  TIMESTAMP    DEFAULT NULL,
    del_flag     CHAR(1)      DEFAULT '0'
);

COMMENT ON TABLE  robot_task_status               IS '上报查验过程节点状态';
COMMENT ON COLUMN robot_task_status.id            IS '主键ID';
COMMENT ON COLUMN robot_task_status.robot_id      IS '机器人id';
COMMENT ON COLUMN robot_task_status.job_id        IS '任务id';
COMMENT ON COLUMN robot_task_status.command_type  IS '指令类型，原样返回';
COMMENT ON COLUMN robot_task_status.msg_id        IS '指令ID，原样返回';
COMMENT ON COLUMN robot_task_status."timestamp"   IS '更新时间戳';
COMMENT ON COLUMN robot_task_status.result        IS '更新点位成功/失败';
COMMENT ON COLUMN robot_task_status.msg_info      IS '成功/失败原因';
COMMENT ON COLUMN robot_task_status.step_id       IS '步骤';
COMMENT ON COLUMN robot_task_status.data_info     IS '数据详情';
COMMENT ON COLUMN robot_task_status.remark        IS '备注';
COMMENT ON COLUMN robot_task_status.create_by     IS '创建者';
COMMENT ON COLUMN robot_task_status.create_time   IS '创建时间';
COMMENT ON COLUMN robot_task_status.update_by     IS '更新者';
COMMENT ON COLUMN robot_task_status.update_time   IS '更新时间';
COMMENT ON COLUMN robot_task_status.del_flag      IS '删除标志（0代表存在 2代表删除）';

-- gaussdb.robot_task_template 定义
CREATE TABLE robot_task_template (
    id              BIGSERIAL PRIMARY KEY,
    job_name        VARCHAR(64)  NOT NULL DEFAULT '',
    job_group       VARCHAR(64)  DEFAULT 'DEFAULT',
    work_flow_no    VARCHAR(255) DEFAULT NULL,
    cron_expression VARCHAR(255) DEFAULT '',
    info_json       TEXT         DEFAULT NULL,
    status          CHAR(1)      DEFAULT '0',
    return_point    VARCHAR(255) DEFAULT NULL,
    ext1            VARCHAR(16)  DEFAULT NULL,
    ext2            VARCHAR(16)  DEFAULT NULL,
    ext3            VARCHAR(16)  DEFAULT NULL,
    ext4            VARCHAR(16)  DEFAULT NULL,
    remark          VARCHAR(500) DEFAULT NULL,
    create_by       VARCHAR(64)  DEFAULT '',
    create_time     TIMESTAMP    DEFAULT NULL,
    update_by       VARCHAR(64)  DEFAULT '',
    update_time     TIMESTAMP    DEFAULT NULL,
    del_flag        CHAR(1)      DEFAULT '0',
    online_flag     CHAR(1)      DEFAULT '0',
    sync_status     CHAR(1)      DEFAULT '0'
);

COMMENT ON TABLE  robot_task_template                 IS '任务模板';
COMMENT ON COLUMN robot_task_template.id              IS '主键ID';
COMMENT ON COLUMN robot_task_template.job_name        IS '任务名称';
COMMENT ON COLUMN robot_task_template.job_group       IS '任务组名';
COMMENT ON COLUMN robot_task_template.work_flow_no    IS '机器人平台对应的工作流编号';
COMMENT ON COLUMN robot_task_template.cron_expression IS 'cron执行表达式';
COMMENT ON COLUMN robot_task_template.info_json       IS '模板json';
COMMENT ON COLUMN robot_task_template.status          IS '状态（0正常 1暂停）';
COMMENT ON COLUMN robot_task_template.return_point    IS '返航点';
COMMENT ON COLUMN robot_task_template.ext1            IS '备用1';
COMMENT ON COLUMN robot_task_template.ext2            IS '备用2';
COMMENT ON COLUMN robot_task_template.ext3            IS '备用3';
COMMENT ON COLUMN robot_task_template.ext4            IS '备用4';
COMMENT ON COLUMN robot_task_template.remark          IS '备注';
COMMENT ON COLUMN robot_task_template.create_by       IS '创建者';
COMMENT ON COLUMN robot_task_template.create_time     IS '创建时间';
COMMENT ON COLUMN robot_task_template.update_by       IS '更新者';
COMMENT ON COLUMN robot_task_template.update_time     IS '更新时间';
COMMENT ON COLUMN robot_task_template.del_flag        IS '删除标志（0代表存在 2代表删除）';
COMMENT ON COLUMN robot_task_template.online_flag     IS '离线任务：0在线；1离线';
COMMENT ON COLUMN robot_task_template.sync_status     IS '同步状态';

-- gaussdb.robot_transducer 定义
CREATE TABLE robot_transducer (
    id          BIGINT       NOT NULL,
    ext1        VARCHAR(16)  DEFAULT NULL,
    ext2        VARCHAR(16)  DEFAULT NULL,
    ext3        VARCHAR(16)  DEFAULT NULL,
    ext4        VARCHAR(16)  DEFAULT NULL,
    remark      VARCHAR(500) DEFAULT NULL,
    create_by   VARCHAR(64)  DEFAULT '',
    create_time TIMESTAMP    DEFAULT NULL,
    update_by   VARCHAR(64)  DEFAULT '',
    update_time TIMESTAMP    DEFAULT NULL,
    del_flag    CHAR(1)      DEFAULT '0',
    CONSTRAINT robot_transducer_pkey PRIMARY KEY (id)
);

COMMENT ON TABLE  robot_transducer             IS '机器人传感器';
COMMENT ON COLUMN robot_transducer.id          IS '主键ID';
COMMENT ON COLUMN robot_transducer.ext1        IS '备用1';
COMMENT ON COLUMN robot_transducer.ext2        IS '备用2';
COMMENT ON COLUMN robot_transducer.ext3        IS '备用3';
COMMENT ON COLUMN robot_transducer.ext4        IS '备用4';
COMMENT ON COLUMN robot_transducer.remark      IS '备注';
COMMENT ON COLUMN robot_transducer.create_by   IS '创建者';
COMMENT ON COLUMN robot_transducer.create_time IS '创建时间';
COMMENT ON COLUMN robot_transducer.update_by   IS '更新者';
COMMENT ON COLUMN robot_transducer.update_time IS '更新时间';
COMMENT ON COLUMN robot_transducer.del_flag    IS '删除标志（0代表存在 2代表删除）';

-- gaussdb.robot_vehicle 定义
CREATE TABLE robot_vehicle (
    id                     BIGSERIAL PRIMARY KEY,
    map_id                 BIGINT       DEFAULT NULL,
    robot_id               VARCHAR(30)  DEFAULT NULL,
    vehicle_name           VARCHAR(255) DEFAULT NULL,
    vehicle_brand          VARCHAR(255) DEFAULT NULL,
    vehicle_serial_number  VARCHAR(20)  DEFAULT NULL,
    vehicle_type           VARCHAR(10)  DEFAULT NULL,
    vehicle_ip             VARCHAR(255) DEFAULT NULL,
    device_type            VARCHAR(10)  DEFAULT NULL,
    vehicle_capture        VARCHAR(255) DEFAULT NULL,
    vehicle_json           TEXT         DEFAULT NULL,
    voice_topic            VARCHAR(255) DEFAULT NULL,
    blocked_voice_content  VARCHAR(255) DEFAULT NULL,
    status                 VARCHAR(10)  DEFAULT NULL,
    ext1                   VARCHAR(55)  DEFAULT NULL,
    ext2                   VARCHAR(16)  DEFAULT NULL,
    ext3                   VARCHAR(16)  DEFAULT NULL,
    ext4                   VARCHAR(55)  DEFAULT NULL,
    ext5                   VARCHAR(50)  DEFAULT NULL,
    ext6                   VARCHAR(50)  DEFAULT NULL,
    ext7                   VARCHAR(50)  DEFAULT NULL,
    ext8                   VARCHAR(50)  DEFAULT NULL,
    remark                 VARCHAR(500) DEFAULT NULL,
    last_sync_date_time    TIMESTAMP    DEFAULT NULL,
    create_by              VARCHAR(64)  DEFAULT '',
    create_time            TIMESTAMP    DEFAULT NULL,
    update_by              VARCHAR(64)  DEFAULT '',
    update_time            TIMESTAMP    DEFAULT NULL,
    del_flag               CHAR(1)      DEFAULT '0'
);

COMMENT ON TABLE  robot_vehicle                        IS '机器人';
COMMENT ON COLUMN robot_vehicle.id                     IS '主键ID';
COMMENT ON COLUMN robot_vehicle.map_id                 IS '关联地图';
COMMENT ON COLUMN robot_vehicle.robot_id               IS '机器人ID';
COMMENT ON COLUMN robot_vehicle.vehicle_name           IS '名称';
COMMENT ON COLUMN robot_vehicle.vehicle_brand          IS '品牌';
COMMENT ON COLUMN robot_vehicle.vehicle_serial_number  IS '序列号';
COMMENT ON COLUMN robot_vehicle.vehicle_type           IS '型号';
COMMENT ON COLUMN robot_vehicle.vehicle_ip             IS 'ip地址';
COMMENT ON COLUMN robot_vehicle.device_type            IS '设备类型(机器狗/agv）';
COMMENT ON COLUMN robot_vehicle.vehicle_capture        IS '机器人图片地址';
COMMENT ON COLUMN robot_vehicle.vehicle_json           IS '其他属性（json）';
COMMENT ON COLUMN robot_vehicle.voice_topic            IS '语音播报主题';
COMMENT ON COLUMN robot_vehicle.blocked_voice_content  IS '遇到障碍播报的语音';
COMMENT ON COLUMN robot_vehicle.status                 IS '在线状态(0:离线，1:在线)';
COMMENT ON COLUMN robot_vehicle.ext1                   IS '备用1';
COMMENT ON COLUMN robot_vehicle.ext2                   IS '备用2';
COMMENT ON COLUMN robot_vehicle.ext3                   IS '备用3';
COMMENT ON COLUMN robot_vehicle.ext4                   IS '备用4';
COMMENT ON COLUMN robot_vehicle.ext5                   IS '备用5';
COMMENT ON COLUMN robot_vehicle.ext6                   IS '备用6';
COMMENT ON COLUMN robot_vehicle.ext7                   IS '备用7';
COMMENT ON COLUMN robot_vehicle.ext8                   IS '备用8';
COMMENT ON COLUMN robot_vehicle.remark                 IS '备注';
COMMENT ON COLUMN robot_vehicle.last_sync_date_time    IS '上次信息同步时间';
COMMENT ON COLUMN robot_vehicle.create_by              IS '创建者';
COMMENT ON COLUMN robot_vehicle.create_time            IS '创建时间';
COMMENT ON COLUMN robot_vehicle.update_by              IS '更新者';
COMMENT ON COLUMN robot_vehicle.update_time            IS '更新时间';
COMMENT ON COLUMN robot_vehicle.del_flag               IS '删除标志（0代表存在 2代表删除）';

-- gaussdb.robot_vehicle_moving_trail 定义
CREATE TABLE robot_vehicle_moving_trail (
    id           BIGSERIAL PRIMARY KEY,
    robot_id     VARCHAR(255) DEFAULT NULL,
    command_type VARCHAR(255) DEFAULT NULL,
    msg_id       VARCHAR(255) DEFAULT NULL,
    "timestamp"  TIMESTAMP    DEFAULT NULL,
    position_x   VARCHAR(255) DEFAULT NULL,
    position_y   VARCHAR(255) DEFAULT NULL,
    position_z   VARCHAR(255) DEFAULT NULL,
    angle        VARCHAR(255) DEFAULT NULL,
    point_name   VARCHAR(255) DEFAULT NULL,
    velocity_x   VARCHAR(255) DEFAULT NULL,
    velocity_y   VARCHAR(255) DEFAULT NULL,
    velocity_z   VARCHAR(255) DEFAULT NULL,
    proc_state   VARCHAR(255) DEFAULT NULL,
    task_id      VARCHAR(255) DEFAULT NULL,
    energy_level VARCHAR(255) DEFAULT NULL,
    ext1         VARCHAR(255) DEFAULT NULL,
    ext2         VARCHAR(16)  DEFAULT NULL,
    ext3         VARCHAR(16)  DEFAULT NULL,
    ext4         VARCHAR(16)  DEFAULT NULL,
    remark       VARCHAR(500) DEFAULT NULL,
    create_by    VARCHAR(64)  DEFAULT '',
    create_time  TIMESTAMP    DEFAULT NULL,
    update_by    VARCHAR(64)  DEFAULT '',
    update_time  TIMESTAMP    DEFAULT NULL,
    del_flag     CHAR(1)      DEFAULT '0'
);

COMMENT ON TABLE  robot_vehicle_moving_trail               IS '机器人移动轨迹';
COMMENT ON COLUMN robot_vehicle_moving_trail.id            IS '主键ID';
COMMENT ON COLUMN robot_vehicle_moving_trail.robot_id      IS '机器人id';
COMMENT ON COLUMN robot_vehicle_moving_trail.command_type  IS '指令类型，初始位置';
COMMENT ON COLUMN robot_vehicle_moving_trail.msg_id        IS '指令ID';
COMMENT ON COLUMN robot_vehicle_moving_trail."timestamp"   IS '更新时间戳';
COMMENT ON COLUMN robot_vehicle_moving_trail.position_x    IS 'X坐标';
COMMENT ON COLUMN robot_vehicle_moving_trail.position_y    IS 'Y坐标';
COMMENT ON COLUMN robot_vehicle_moving_trail.position_z    IS 'Z坐标';
COMMENT ON COLUMN robot_vehicle_moving_trail.angle         IS '角度';
COMMENT ON COLUMN robot_vehicle_moving_trail.point_name    IS '点位名称';
COMMENT ON COLUMN robot_vehicle_moving_trail.velocity_x    IS 'X方向速度';
COMMENT ON COLUMN robot_vehicle_moving_trail.velocity_y    IS 'Y方向速度';
COMMENT ON COLUMN robot_vehicle_moving_trail.velocity_z    IS 'Z方向速度';
COMMENT ON COLUMN robot_vehicle_moving_trail.proc_state    IS '空闲：IDLE/任务处理中：PROCESSING';
COMMENT ON COLUMN robot_vehicle_moving_trail.task_id       IS '任务处理中返回给出当前taskId,否则为空';
COMMENT ON COLUMN robot_vehicle_moving_trail.energy_level  IS '电量百分比';
COMMENT ON COLUMN robot_vehicle_moving_trail.ext1          IS '备用1';
COMMENT ON COLUMN robot_vehicle_moving_trail.ext2          IS '备用2';
COMMENT ON COLUMN robot_vehicle_moving_trail.ext3          IS '备用3';
COMMENT ON COLUMN robot_vehicle_moving_trail.ext4          IS '备用4';
COMMENT ON COLUMN robot_vehicle_moving_trail.remark        IS '备注';
COMMENT ON COLUMN robot_vehicle_moving_trail.create_by     IS '创建者';
COMMENT ON COLUMN robot_vehicle_moving_trail.create_time   IS '创建时间';
COMMENT ON COLUMN robot_vehicle_moving_trail.update_by     IS '更新者';
COMMENT ON COLUMN robot_vehicle_moving_trail.update_time   IS '更新时间';
COMMENT ON COLUMN robot_vehicle_moving_trail.del_flag      IS '删除标志（0代表存在 2代表删除）';

-- gaussdb.sys_arm_target_cable 定义
CREATE TABLE sys_arm_target_cable (
    id          BIGSERIAL PRIMARY KEY,
    robot_id    VARCHAR(55)  DEFAULT NULL,
    cable_code  VARCHAR(50)  DEFAULT NULL,
    cable_name  VARCHAR(255) DEFAULT NULL,
    description VARCHAR(500) DEFAULT NULL,
    status      SMALLINT     DEFAULT 1,
    remark      VARCHAR(500) DEFAULT NULL,
    create_by   VARCHAR(64)  DEFAULT NULL,
    create_time TIMESTAMP    DEFAULT NULL,
    update_by   VARCHAR(64)  DEFAULT NULL,
    update_time TIMESTAMP    DEFAULT NULL,
    del_flag    CHAR(1)      DEFAULT '0'
);

COMMENT ON TABLE  sys_arm_target_cable             IS '机械臂目标线缆管理表';
COMMENT ON COLUMN sys_arm_target_cable.id          IS '主键ID';
COMMENT ON COLUMN sys_arm_target_cable.robot_id    IS '机器人ID';
COMMENT ON COLUMN sys_arm_target_cable.cable_code  IS '线缆编号';
COMMENT ON COLUMN sys_arm_target_cable.cable_name  IS '线缆名称';
COMMENT ON COLUMN sys_arm_target_cable.description IS '线缆描述';
COMMENT ON COLUMN sys_arm_target_cable.status      IS '状态：1=启用，0=禁用';
COMMENT ON COLUMN sys_arm_target_cable.remark      IS '备注';
COMMENT ON COLUMN sys_arm_target_cable.create_by   IS '创建人';
COMMENT ON COLUMN sys_arm_target_cable.create_time IS '创建时间';
COMMENT ON COLUMN sys_arm_target_cable.update_by   IS '更新人';
COMMENT ON COLUMN sys_arm_target_cable.update_time IS '更新时间';
COMMENT ON COLUMN sys_arm_target_cable.del_flag    IS '删除标志：0=未删除，1=已删除';

-- gaussdb.sys_config 定义
CREATE TABLE sys_config (
    config_id    SERIAL       PRIMARY KEY,
    config_name  VARCHAR(100) DEFAULT '',
    config_key   VARCHAR(100) DEFAULT '',
    config_value VARCHAR(500) DEFAULT '',
    config_type  CHAR(1)      DEFAULT 'N',
    create_by    VARCHAR(64)  DEFAULT '',
    create_time  TIMESTAMP    DEFAULT NULL,
    update_by    VARCHAR(64)  DEFAULT '',
    update_time  TIMESTAMP    DEFAULT NULL,
    remark       VARCHAR(500) DEFAULT NULL
);

COMMENT ON TABLE  sys_config              IS '参数配置表';
COMMENT ON COLUMN sys_config.config_id    IS '参数主键';
COMMENT ON COLUMN sys_config.config_name  IS '参数名称';
COMMENT ON COLUMN sys_config.config_key   IS '参数键名';
COMMENT ON COLUMN sys_config.config_value IS '参数键值';
COMMENT ON COLUMN sys_config.config_type  IS '系统内置（Y是 N否）';
COMMENT ON COLUMN sys_config.create_by    IS '创建者';
COMMENT ON COLUMN sys_config.create_time  IS '创建时间';
COMMENT ON COLUMN sys_config.update_by    IS '更新者';
COMMENT ON COLUMN sys_config.update_time  IS '更新时间';
COMMENT ON COLUMN sys_config.remark       IS '备注';

-- gaussdb.sys_dept 定义
CREATE TABLE sys_dept (
    dept_id     BIGSERIAL    PRIMARY KEY,
    parent_id   BIGINT       DEFAULT 0,
    ancestors   VARCHAR(50)  DEFAULT '',
    dept_name   VARCHAR(30)  DEFAULT '',
    order_num   INTEGER      DEFAULT 0,
    leader      VARCHAR(20)  DEFAULT NULL,
    phone       VARCHAR(11)  DEFAULT NULL,
    email       VARCHAR(50)  DEFAULT NULL,
    status      CHAR(1)      DEFAULT '0',
    del_flag    CHAR(1)      DEFAULT '0',
    create_by   VARCHAR(64)  DEFAULT '',
    create_time TIMESTAMP    DEFAULT NULL,
    update_by   VARCHAR(64)  DEFAULT '',
    update_time TIMESTAMP    DEFAULT NULL
);

COMMENT ON TABLE  sys_dept             IS '部门表';
COMMENT ON COLUMN sys_dept.dept_id     IS '部门id';
COMMENT ON COLUMN sys_dept.parent_id   IS '父部门id';
COMMENT ON COLUMN sys_dept.ancestors   IS '祖级列表';
COMMENT ON COLUMN sys_dept.dept_name   IS '部门名称';
COMMENT ON COLUMN sys_dept.order_num   IS '显示顺序';
COMMENT ON COLUMN sys_dept.leader      IS '负责人';
COMMENT ON COLUMN sys_dept.phone       IS '联系电话';
COMMENT ON COLUMN sys_dept.email       IS '邮箱';
COMMENT ON COLUMN sys_dept.status      IS '部门状态（0正常 1停用）';
COMMENT ON COLUMN sys_dept.del_flag    IS '删除标志（0代表存在 2代表删除）';
COMMENT ON COLUMN sys_dept.create_by   IS '创建者';
COMMENT ON COLUMN sys_dept.create_time IS '创建时间';
COMMENT ON COLUMN sys_dept.update_by   IS '更新者';
COMMENT ON COLUMN sys_dept.update_time IS '更新时间';

-- gaussdb.sys_dict_data 定义
CREATE TABLE sys_dict_data (
    dict_code   BIGSERIAL    PRIMARY KEY,
    dict_sort   INTEGER      DEFAULT 0,
    dict_label  VARCHAR(100) DEFAULT '',
    dict_value  VARCHAR(100) DEFAULT '',
    dict_type   VARCHAR(100) DEFAULT '',
    css_class   VARCHAR(100) DEFAULT NULL,
    list_class  VARCHAR(100) DEFAULT NULL,
    is_default  CHAR(1)      DEFAULT 'N',
    status      CHAR(1)      DEFAULT '0',
    create_by   VARCHAR(64)  DEFAULT '',
    create_time TIMESTAMP    DEFAULT NULL,
    update_by   VARCHAR(64)  DEFAULT '',
    update_time TIMESTAMP    DEFAULT NULL,
    remark      VARCHAR(500) DEFAULT NULL
);

COMMENT ON TABLE  sys_dict_data             IS '字典数据表';
COMMENT ON COLUMN sys_dict_data.dict_code   IS '字典编码';
COMMENT ON COLUMN sys_dict_data.dict_sort   IS '字典排序';
COMMENT ON COLUMN sys_dict_data.dict_label  IS '字典标签';
COMMENT ON COLUMN sys_dict_data.dict_value  IS '字典键值';
COMMENT ON COLUMN sys_dict_data.dict_type   IS '字典类型';
COMMENT ON COLUMN sys_dict_data.css_class   IS '样式属性（其他样式扩展）';
COMMENT ON COLUMN sys_dict_data.list_class  IS '表格回显样式';
COMMENT ON COLUMN sys_dict_data.is_default  IS '是否默认（Y是 N否）';
COMMENT ON COLUMN sys_dict_data.status      IS '状态（0正常 1停用）';
COMMENT ON COLUMN sys_dict_data.create_by   IS '创建者';
COMMENT ON COLUMN sys_dict_data.create_time IS '创建时间';
COMMENT ON COLUMN sys_dict_data.update_by   IS '更新者';
COMMENT ON COLUMN sys_dict_data.update_time IS '更新时间';
COMMENT ON COLUMN sys_dict_data.remark      IS '备注';

-- gaussdb.sys_dict_type 定义
CREATE TABLE sys_dict_type (
    dict_id     BIGSERIAL    PRIMARY KEY,
    dict_name   VARCHAR(100) DEFAULT '',
    dict_type   VARCHAR(100) DEFAULT '',
    status      CHAR(1)      DEFAULT '0',
    create_by   VARCHAR(64)  DEFAULT '',
    create_time TIMESTAMP    DEFAULT NULL,
    update_by   VARCHAR(64)  DEFAULT '',
    update_time TIMESTAMP    DEFAULT NULL,
    remark      VARCHAR(500) DEFAULT NULL,
    CONSTRAINT dict_type UNIQUE (dict_type)
);

COMMENT ON TABLE  sys_dict_type             IS '字典类型表';
COMMENT ON COLUMN sys_dict_type.dict_id     IS '字典主键';
COMMENT ON COLUMN sys_dict_type.dict_name   IS '字典名称';
COMMENT ON COLUMN sys_dict_type.dict_type   IS '字典类型';
COMMENT ON COLUMN sys_dict_type.status      IS '状态（0正常 1停用）';
COMMENT ON COLUMN sys_dict_type.create_by   IS '创建者';
COMMENT ON COLUMN sys_dict_type.create_time IS '创建时间';
COMMENT ON COLUMN sys_dict_type.update_by   IS '更新者';
COMMENT ON COLUMN sys_dict_type.update_time IS '更新时间';
COMMENT ON COLUMN sys_dict_type.remark      IS '备注';

-- gaussdb.sys_door_control 定义
CREATE TABLE sys_door_control (
    id             BIGSERIAL    PRIMARY KEY,
    robot_id       VARCHAR(55)  DEFAULT NULL,
    door_name      VARCHAR(255) DEFAULT NULL,
    ip_address     VARCHAR(255) DEFAULT NULL,
    speed          INTEGER      DEFAULT 80,
    target_percent INTEGER      DEFAULT 0,
    status         SMALLINT     DEFAULT 1,
    remark         VARCHAR(500) DEFAULT NULL,
    create_by      VARCHAR(64)  DEFAULT NULL,
    create_time    TIMESTAMP    DEFAULT NULL,
    update_by      VARCHAR(64)  DEFAULT NULL,
    update_time    TIMESTAMP    DEFAULT NULL,
    del_flag       CHAR(1)      DEFAULT '0'
);

COMMENT ON TABLE  sys_door_control                IS '开门机管理表';
COMMENT ON COLUMN sys_door_control.id             IS '主键ID';
COMMENT ON COLUMN sys_door_control.robot_id       IS '机器人ID';
COMMENT ON COLUMN sys_door_control.door_name      IS '门名称';
COMMENT ON COLUMN sys_door_control.ip_address     IS 'IP地址';
COMMENT ON COLUMN sys_door_control.speed          IS '开门速度(0-100)';
COMMENT ON COLUMN sys_door_control.target_percent IS '开门位置(0-100) 0代表完全关闭，100代表完全打开';
COMMENT ON COLUMN sys_door_control.status         IS '状态：1=启用，0=禁用';
COMMENT ON COLUMN sys_door_control.remark         IS '备注';
COMMENT ON COLUMN sys_door_control.create_by      IS '创建人';
COMMENT ON COLUMN sys_door_control.create_time    IS '创建时间';
COMMENT ON COLUMN sys_door_control.update_by      IS '更新人';
COMMENT ON COLUMN sys_door_control.update_time    IS '更新时间';
COMMENT ON COLUMN sys_door_control.del_flag       IS '删除标志：0=未删除，1=已删除';

-- gaussdb.sys_elevator_control 定义
CREATE TABLE sys_elevator_control (
    id            BIGSERIAL    PRIMARY KEY,
    robot_id      VARCHAR(55)  DEFAULT NULL,
    elevator_name VARCHAR(255) DEFAULT NULL,
    address       VARCHAR(50)  DEFAULT NULL,
    floor         INTEGER      DEFAULT NULL,
    hode_time     INTEGER      DEFAULT 10,
    status        SMALLINT     DEFAULT 1,
    remark        VARCHAR(500) DEFAULT NULL,
    create_by     VARCHAR(64)  DEFAULT '',
    create_time   TIMESTAMP    DEFAULT NULL,
    update_by     VARCHAR(64)  DEFAULT '',
    update_time   TIMESTAMP    DEFAULT NULL,
    del_flag      CHAR(1)      DEFAULT '0'
);

COMMENT ON TABLE  sys_elevator_control               IS '电梯控制管理表';
COMMENT ON COLUMN sys_elevator_control.id            IS '主键ID';
COMMENT ON COLUMN sys_elevator_control.robot_id      IS '机器人ID';
COMMENT ON COLUMN sys_elevator_control.elevator_name IS '电梯名称';
COMMENT ON COLUMN sys_elevator_control.address       IS '电梯IP(01,02)';
COMMENT ON COLUMN sys_elevator_control.floor         IS '目标楼层';
COMMENT ON COLUMN sys_elevator_control.hode_time     IS '延迟关门时间(秒)';
COMMENT ON COLUMN sys_elevator_control.status        IS '状态：1=启用，0=禁用';
COMMENT ON COLUMN sys_elevator_control.remark        IS '备注';
COMMENT ON COLUMN sys_elevator_control.create_by     IS '创建者';
COMMENT ON COLUMN sys_elevator_control.create_time   IS '创建时间';
COMMENT ON COLUMN sys_elevator_control.update_by     IS '更新者';
COMMENT ON COLUMN sys_elevator_control.update_time   IS '更新时间';
COMMENT ON COLUMN sys_elevator_control.del_flag      IS '删除标志：0=未删除，1=已删除';

-- gaussdb.sys_gas_sensor 定义
CREATE TABLE sys_gas_sensor (
    id          BIGSERIAL    PRIMARY KEY,
    robot_id    VARCHAR(55)  DEFAULT NULL,
    sensor_code INTEGER      DEFAULT NULL,
    sensor_name VARCHAR(255) DEFAULT NULL,
    description VARCHAR(500) DEFAULT NULL,
    status      SMALLINT     DEFAULT 1,
    remark      VARCHAR(500) DEFAULT NULL,
    create_by   VARCHAR(64)  DEFAULT NULL,
    create_time TIMESTAMP    DEFAULT NULL,
    update_by   VARCHAR(64)  DEFAULT NULL,
    update_time TIMESTAMP    DEFAULT NULL,
    del_flag    CHAR(1)      DEFAULT '0'
);

COMMENT ON TABLE  sys_gas_sensor             IS '气体传感器管理表';
COMMENT ON COLUMN sys_gas_sensor.id          IS '主键ID';
COMMENT ON COLUMN sys_gas_sensor.robot_id    IS '机器人ID';
COMMENT ON COLUMN sys_gas_sensor.sensor_code IS '传感器编号';
COMMENT ON COLUMN sys_gas_sensor.sensor_name IS '传感器名称';
COMMENT ON COLUMN sys_gas_sensor.description IS '描述';
COMMENT ON COLUMN sys_gas_sensor.status      IS '状态：1=启用，0=禁用';
COMMENT ON COLUMN sys_gas_sensor.remark      IS '备注';
COMMENT ON COLUMN sys_gas_sensor.create_by   IS '创建人';
COMMENT ON COLUMN sys_gas_sensor.create_time IS '创建时间';
COMMENT ON COLUMN sys_gas_sensor.update_by   IS '更新人';
COMMENT ON COLUMN sys_gas_sensor.update_time IS '更新时间';
COMMENT ON COLUMN sys_gas_sensor.del_flag    IS '删除标志：0=未删除，1=已删除';

-- gaussdb.sys_job 定义
CREATE TABLE sys_job (
    job_id          BIGSERIAL    NOT NULL,
    job_name        VARCHAR(64)  NOT NULL DEFAULT '',
    job_group       VARCHAR(64)  NOT NULL DEFAULT 'DEFAULT',
    invoke_target   VARCHAR(500) NOT NULL,
    cron_expression VARCHAR(255) DEFAULT '',
    misfire_policy  VARCHAR(20)  DEFAULT '3',
    concurrent      CHAR(1)      DEFAULT '1',
    status          CHAR(1)      DEFAULT '0',
    create_by       VARCHAR(64)  DEFAULT '',
    create_time     TIMESTAMP    DEFAULT NULL,
    update_by       VARCHAR(64)  DEFAULT '',
    update_time     TIMESTAMP    DEFAULT NULL,
    remark          VARCHAR(500) DEFAULT '',
    online_flag     CHAR(1)      DEFAULT '0',
    CONSTRAINT sys_job_pkey PRIMARY KEY (job_id, job_name, job_group)
);

COMMENT ON TABLE  sys_job                 IS '定时任务调度表';
COMMENT ON COLUMN sys_job.job_id          IS '任务ID';
COMMENT ON COLUMN sys_job.job_name        IS '任务名称';
COMMENT ON COLUMN sys_job.job_group       IS '任务组名';
COMMENT ON COLUMN sys_job.invoke_target   IS '调用目标字符串';
COMMENT ON COLUMN sys_job.cron_expression IS 'cron执行表达式';
COMMENT ON COLUMN sys_job.misfire_policy  IS '计划执行错误策略（1立即执行 2执行一次 3放弃执行）';
COMMENT ON COLUMN sys_job.concurrent      IS '是否并发执行（0允许 1禁止）';
COMMENT ON COLUMN sys_job.status          IS '状态（0正常 1暂停）';
COMMENT ON COLUMN sys_job.create_by       IS '创建者';
COMMENT ON COLUMN sys_job.create_time     IS '创建时间';
COMMENT ON COLUMN sys_job.update_by       IS '更新者';
COMMENT ON COLUMN sys_job.update_time     IS '更新时间';
COMMENT ON COLUMN sys_job.remark          IS '备注信息';
COMMENT ON COLUMN sys_job.online_flag     IS '离线任务：0在线；1离线';

-- gaussdb.sys_job_log 定义
CREATE TABLE sys_job_log (
    job_log_id     BIGSERIAL    PRIMARY KEY,
    job_name       VARCHAR(64)  NOT NULL,
    job_group      VARCHAR(64)  NOT NULL,
    invoke_target  VARCHAR(500) NOT NULL,
    job_message    VARCHAR(500) DEFAULT NULL,
    status         CHAR(1)      DEFAULT '0',
    exception_info VARCHAR(2000) DEFAULT '',
    create_time    TIMESTAMP    DEFAULT NULL
);

COMMENT ON TABLE  sys_job_log                IS '定时任务调度日志表';
COMMENT ON COLUMN sys_job_log.job_log_id     IS '任务日志ID';
COMMENT ON COLUMN sys_job_log.job_name       IS '任务名称';
COMMENT ON COLUMN sys_job_log.job_group      IS '任务组名';
COMMENT ON COLUMN sys_job_log.invoke_target  IS '调用目标字符串';
COMMENT ON COLUMN sys_job_log.job_message    IS '日志信息';
COMMENT ON COLUMN sys_job_log.status         IS '执行状态（0正常 1失败）';
COMMENT ON COLUMN sys_job_log.exception_info IS '异常信息';
COMMENT ON COLUMN sys_job_log.create_time    IS '创建时间';

-- gaussdb.sys_logininfor 定义
CREATE TABLE sys_logininfor (
    info_id       BIGSERIAL    PRIMARY KEY,
    user_name     VARCHAR(50)  DEFAULT '',
    ipaddr        VARCHAR(128) DEFAULT '',
    login_location VARCHAR(255) DEFAULT '',
    browser       VARCHAR(50)  DEFAULT '',
    os            VARCHAR(50)  DEFAULT '',
    status        CHAR(1)      DEFAULT '0',
    msg           VARCHAR(255) DEFAULT '',
    login_time    TIMESTAMP    DEFAULT NULL
);

CREATE INDEX idx_sys_logininfor_s  ON sys_logininfor (status);
CREATE INDEX idx_sys_logininfor_lt ON sys_logininfor (login_time);

COMMENT ON TABLE  sys_logininfor                IS '系统访问记录';
COMMENT ON COLUMN sys_logininfor.info_id        IS '访问ID';
COMMENT ON COLUMN sys_logininfor.user_name      IS '用户账号';
COMMENT ON COLUMN sys_logininfor.ipaddr         IS '登录IP地址';
COMMENT ON COLUMN sys_logininfor.login_location IS '登录地点';
COMMENT ON COLUMN sys_logininfor.browser        IS '浏览器类型';
COMMENT ON COLUMN sys_logininfor.os             IS '操作系统';
COMMENT ON COLUMN sys_logininfor.status         IS '登录状态（0成功 1失败）';
COMMENT ON COLUMN sys_logininfor.msg            IS '提示消息';
COMMENT ON COLUMN sys_logininfor.login_time     IS '访问时间';

-- gaussdb.sys_menu 定义
CREATE TABLE sys_menu (
    menu_id     BIGSERIAL    PRIMARY KEY,
    menu_name   VARCHAR(50)  NOT NULL,
    parent_id   BIGINT       DEFAULT 0,
    order_num   INTEGER      DEFAULT 0,
    path        VARCHAR(200) DEFAULT '',
    component   VARCHAR(255) DEFAULT NULL,
    query       VARCHAR(255) DEFAULT NULL,
    route_name  VARCHAR(50)  DEFAULT '',
    is_frame    INTEGER      DEFAULT 1,
    is_cache    INTEGER      DEFAULT 0,
    menu_type   CHAR(1)      DEFAULT '',
    visible     CHAR(1)      DEFAULT '0',
    status      CHAR(1)      DEFAULT '0',
    perms       VARCHAR(100) DEFAULT NULL,
    icon        VARCHAR(100) DEFAULT '#',
    create_by   VARCHAR(64)  DEFAULT '',
    create_time TIMESTAMP    DEFAULT NULL,
    update_by   VARCHAR(64)  DEFAULT '',
    update_time TIMESTAMP    DEFAULT NULL,
    remark      VARCHAR(500) DEFAULT ''
);

COMMENT ON TABLE  sys_menu             IS '菜单权限表';
COMMENT ON COLUMN sys_menu.menu_id     IS '菜单ID';
COMMENT ON COLUMN sys_menu.menu_name   IS '菜单名称';
COMMENT ON COLUMN sys_menu.parent_id   IS '父菜单ID';
COMMENT ON COLUMN sys_menu.order_num   IS '显示顺序';
COMMENT ON COLUMN sys_menu.path        IS '路由地址';
COMMENT ON COLUMN sys_menu.component   IS '组件路径';
COMMENT ON COLUMN sys_menu.query       IS '路由参数';
COMMENT ON COLUMN sys_menu.route_name  IS '路由名称';
COMMENT ON COLUMN sys_menu.is_frame    IS '是否为外链（0是 1否）';
COMMENT ON COLUMN sys_menu.is_cache    IS '是否缓存（0缓存 1不缓存）';
COMMENT ON COLUMN sys_menu.menu_type   IS '菜单类型（M目录 C菜单 F按钮）';
COMMENT ON COLUMN sys_menu.visible     IS '菜单状态（0显示 1隐藏）';
COMMENT ON COLUMN sys_menu.status      IS '菜单状态（0正常 1停用）';
COMMENT ON COLUMN sys_menu.perms       IS '权限标识';
COMMENT ON COLUMN sys_menu.icon        IS '菜单图标';
COMMENT ON COLUMN sys_menu.create_by   IS '创建者';
COMMENT ON COLUMN sys_menu.create_time IS '创建时间';
COMMENT ON COLUMN sys_menu.update_by   IS '更新者';
COMMENT ON COLUMN sys_menu.update_time IS '更新时间';
COMMENT ON COLUMN sys_menu.remark      IS '备注';

-- gaussdb.sys_notice 定义
CREATE TABLE sys_notice (
    notice_id      SERIAL       PRIMARY KEY,
    notice_title   VARCHAR(255) NOT NULL,
    notice_type    CHAR(1)      NOT NULL,
    notice_content TEXT         DEFAULT NULL,
    status         CHAR(1)      DEFAULT '0',
    create_by      VARCHAR(64)  DEFAULT '',
    create_time    TIMESTAMP    DEFAULT NULL,
    update_by      VARCHAR(64)  DEFAULT '',
    update_time    TIMESTAMP    DEFAULT NULL,
    remark         VARCHAR(255) DEFAULT NULL,
    robot_id       VARCHAR(55)  NOT NULL,
    robot_name     VARCHAR(255) NOT NULL,
    error_code     VARCHAR(255) NOT NULL
);

COMMENT ON TABLE  sys_notice                IS '通知公告表';
COMMENT ON COLUMN sys_notice.notice_id      IS '公告ID';
COMMENT ON COLUMN sys_notice.notice_title   IS '公告标题';
COMMENT ON COLUMN sys_notice.notice_type    IS '公告类型（1通知 2公告）';
COMMENT ON COLUMN sys_notice.notice_content IS '公告内容';
COMMENT ON COLUMN sys_notice.status         IS '公告状态（0正常 1关闭）';
COMMENT ON COLUMN sys_notice.create_by      IS '创建者';
COMMENT ON COLUMN sys_notice.create_time    IS '创建时间';
COMMENT ON COLUMN sys_notice.update_by      IS '更新者';
COMMENT ON COLUMN sys_notice.update_time    IS '更新时间';
COMMENT ON COLUMN sys_notice.remark         IS '备注';
COMMENT ON COLUMN sys_notice.robot_id       IS '机器人ID';
COMMENT ON COLUMN sys_notice.robot_name     IS '机器人名称';
COMMENT ON COLUMN sys_notice.error_code     IS '告警错误码';

-- gaussdb.sys_notice_read 定义
CREATE TABLE sys_notice_read (
    read_id   BIGSERIAL   PRIMARY KEY,
    notice_id INTEGER     NOT NULL,
    user_id   BIGINT      NOT NULL,
    read_time TIMESTAMP   NOT NULL,
    CONSTRAINT uk_user_notice UNIQUE (user_id, notice_id)
);

COMMENT ON TABLE  sys_notice_read           IS '公告已读记录表';
COMMENT ON COLUMN sys_notice_read.read_id   IS '已读主键';
COMMENT ON COLUMN sys_notice_read.notice_id IS '公告id';
COMMENT ON COLUMN sys_notice_read.user_id   IS '用户id';
COMMENT ON COLUMN sys_notice_read.read_time IS '阅读时间';
COMMENT ON CONSTRAINT uk_user_notice ON sys_notice_read IS '同一用户同一公告只记录一次';

-- gaussdb.sys_oper_log 定义
CREATE TABLE sys_oper_log (
    oper_id        BIGSERIAL    PRIMARY KEY,
    title          VARCHAR(50)  DEFAULT '',
    business_type  INTEGER      DEFAULT 0,
    method         VARCHAR(200) DEFAULT '',
    request_method VARCHAR(10)  DEFAULT '',
    operator_type  INTEGER      DEFAULT 0,
    oper_name      VARCHAR(50)  DEFAULT '',
    dept_name      VARCHAR(50)  DEFAULT '',
    oper_url       VARCHAR(255) DEFAULT '',
    oper_ip        VARCHAR(128) DEFAULT '',
    oper_location  VARCHAR(255) DEFAULT '',
    oper_param     TEXT         DEFAULT '',
    json_result    TEXT         DEFAULT '',
    status         INTEGER      DEFAULT 0,
    error_msg      VARCHAR(2000) DEFAULT '',
    oper_time      TIMESTAMP    DEFAULT NULL,
    cost_time      BIGINT       DEFAULT 0
);

CREATE INDEX idx_sys_oper_log_bt ON sys_oper_log (business_type);
CREATE INDEX idx_sys_oper_log_s  ON sys_oper_log (status);
CREATE INDEX idx_sys_oper_log_ot ON sys_oper_log (oper_time);

COMMENT ON TABLE  sys_oper_log                IS '操作日志记录';
COMMENT ON COLUMN sys_oper_log.oper_id        IS '日志主键';
COMMENT ON COLUMN sys_oper_log.title          IS '模块标题';
COMMENT ON COLUMN sys_oper_log.business_type  IS '业务类型（0其它 1新增 2修改 3删除）';
COMMENT ON COLUMN sys_oper_log.method         IS '方法名称';
COMMENT ON COLUMN sys_oper_log.request_method IS '请求方式';
COMMENT ON COLUMN sys_oper_log.operator_type  IS '操作类别（0其它 1后台用户 2手机端用户）';
COMMENT ON COLUMN sys_oper_log.oper_name      IS '操作人员';
COMMENT ON COLUMN sys_oper_log.dept_name      IS '部门名称';
COMMENT ON COLUMN sys_oper_log.oper_url       IS '请求URL';
COMMENT ON COLUMN sys_oper_log.oper_ip        IS '主机地址';
COMMENT ON COLUMN sys_oper_log.oper_location  IS '操作地点';
COMMENT ON COLUMN sys_oper_log.oper_param     IS '请求参数';
COMMENT ON COLUMN sys_oper_log.json_result    IS '返回参数';
COMMENT ON COLUMN sys_oper_log.status         IS '操作状态（0正常 1异常）';
COMMENT ON COLUMN sys_oper_log.error_msg      IS '错误消息';
COMMENT ON COLUMN sys_oper_log.oper_time      IS '操作时间';
COMMENT ON COLUMN sys_oper_log.cost_time      IS '消耗时间';

-- gaussdb.sys_platen_label 定义
CREATE TABLE sys_platen_label (
    id          BIGSERIAL    PRIMARY KEY,
    robot_id    VARCHAR(55)  DEFAULT NULL,
    label_code  VARCHAR(64)  DEFAULT NULL,
    label_name  VARCHAR(255) DEFAULT NULL,
    status      INTEGER      DEFAULT 1,
    remark      VARCHAR(500) DEFAULT NULL,
    create_by   VARCHAR(64)  DEFAULT '',
    create_time TIMESTAMP    DEFAULT NULL,
    update_by   VARCHAR(64)  DEFAULT '',
    update_time TIMESTAMP    DEFAULT NULL,
    del_flag    CHAR(1)      DEFAULT '0'
);

COMMENT ON TABLE  sys_platen_label            IS '压板管理';
COMMENT ON COLUMN sys_platen_label.id         IS '主键ID';
COMMENT ON COLUMN sys_platen_label.robot_id   IS '机器人ID';
COMMENT ON COLUMN sys_platen_label.label_code IS '压板编号';
COMMENT ON COLUMN sys_platen_label.label_name IS '压板名称';
COMMENT ON COLUMN sys_platen_label.status     IS '状态：1=启用，0=禁用';
COMMENT ON COLUMN sys_platen_label.remark     IS '备注';
COMMENT ON COLUMN sys_platen_label.create_by  IS '创建者';
COMMENT ON COLUMN sys_platen_label.create_time IS '创建时间';
COMMENT ON COLUMN sys_platen_label.update_by  IS '更新者';
COMMENT ON COLUMN sys_platen_label.update_time IS '更新时间';
COMMENT ON COLUMN sys_platen_label.del_flag   IS '删除标志：0=未删除，1=已删除';

-- gaussdb.sys_post 定义;
CREATE TABLE sys_post (
    post_id     BIGSERIAL    PRIMARY KEY,
    post_code   VARCHAR(64)  NOT NULL,
    post_name   VARCHAR(50)  NOT NULL,
    post_sort   INTEGER      NOT NULL,
    status      CHAR(1)      NOT NULL,
    create_by   VARCHAR(64)  DEFAULT '',
    create_time TIMESTAMP    DEFAULT NULL,
    update_by   VARCHAR(64)  DEFAULT '',
    update_time TIMESTAMP    DEFAULT NULL,
    remark      VARCHAR(500) DEFAULT NULL
);

COMMENT ON TABLE  sys_post             IS '岗位信息表';
COMMENT ON COLUMN sys_post.post_id     IS '岗位ID';
COMMENT ON COLUMN sys_post.post_code   IS '岗位编码';
COMMENT ON COLUMN sys_post.post_name   IS '岗位名称';
COMMENT ON COLUMN sys_post.post_sort   IS '显示顺序';
COMMENT ON COLUMN sys_post.status      IS '状态（0正常 1停用）';
COMMENT ON COLUMN sys_post.create_by   IS '创建者';
COMMENT ON COLUMN sys_post.create_time IS '创建时间';
COMMENT ON COLUMN sys_post.update_by   IS '更新者';
COMMENT ON COLUMN sys_post.update_time IS '更新时间';
COMMENT ON COLUMN sys_post.remark      IS '备注';

-- gaussdb.sys_preset_point 定义
CREATE TABLE sys_preset_point (
    id          BIGSERIAL    PRIMARY KEY,
    robot_id    VARCHAR(55)  DEFAULT NULL,
    ptz_code    VARCHAR(64)  DEFAULT NULL,
    point_code  VARCHAR(64)  DEFAULT NULL,
    point_name  VARCHAR(255) DEFAULT NULL,
    status      INTEGER      DEFAULT 1,
    remark      VARCHAR(500) DEFAULT NULL,
    create_by   VARCHAR(64)  DEFAULT '',
    create_time TIMESTAMP    DEFAULT NULL,
    update_by   VARCHAR(64)  DEFAULT '',
    update_time TIMESTAMP    DEFAULT NULL,
    del_flag    CHAR(1)      DEFAULT '0'
);

COMMENT ON TABLE  sys_preset_point            IS '云台预置点位管理';
COMMENT ON COLUMN sys_preset_point.id         IS '主键ID';
COMMENT ON COLUMN sys_preset_point.robot_id   IS '机器人ID';
COMMENT ON COLUMN sys_preset_point.ptz_code   IS '云台编号';
COMMENT ON COLUMN sys_preset_point.point_code IS '点位编号';
COMMENT ON COLUMN sys_preset_point.point_name IS '点位名称';
COMMENT ON COLUMN sys_preset_point.status     IS '状态：1=启用，0=禁用';
COMMENT ON COLUMN sys_preset_point.remark     IS '备注';
COMMENT ON COLUMN sys_preset_point.create_by  IS '创建者';
COMMENT ON COLUMN sys_preset_point.create_time IS '创建时间';
COMMENT ON COLUMN sys_preset_point.update_by  IS '更新者';
COMMENT ON COLUMN sys_preset_point.update_time IS '更新时间';
COMMENT ON COLUMN sys_preset_point.del_flag   IS '删除标志：0=未删除，1=已删除';

-- gaussdb.sys_role 定义
CREATE TABLE sys_role (
    role_id             BIGSERIAL    PRIMARY KEY,
    role_name           VARCHAR(30)  NOT NULL,
    role_key            VARCHAR(100) NOT NULL,
    role_sort           INTEGER      NOT NULL,
    data_scope          CHAR(1)      DEFAULT '1',
    menu_check_strictly SMALLINT     DEFAULT 1,
    dept_check_strictly SMALLINT     DEFAULT 1,
    status              CHAR(1)      NOT NULL,
    del_flag            CHAR(1)      DEFAULT '0',
    create_by           VARCHAR(64)  DEFAULT '',
    create_time         TIMESTAMP    DEFAULT NULL,
    update_by           VARCHAR(64)  DEFAULT '',
    update_time         TIMESTAMP    DEFAULT NULL,
    remark              VARCHAR(500) DEFAULT NULL
);

COMMENT ON TABLE  sys_role                       IS '角色信息表';
COMMENT ON COLUMN sys_role.role_id               IS '角色ID';
COMMENT ON COLUMN sys_role.role_name             IS '角色名称';
COMMENT ON COLUMN sys_role.role_key              IS '角色权限字符串';
COMMENT ON COLUMN sys_role.role_sort             IS '显示顺序';
COMMENT ON COLUMN sys_role.data_scope            IS '数据范围（1：全部数据权限 2：自定数据权限 3：本部门数据权限 4：本部门及以下数据权限）';
COMMENT ON COLUMN sys_role.menu_check_strictly   IS '菜单树选择项是否关联显示';
COMMENT ON COLUMN sys_role.dept_check_strictly   IS '部门树选择项是否关联显示';
COMMENT ON COLUMN sys_role.status                IS '角色状态（0正常 1停用）';
COMMENT ON COLUMN sys_role.del_flag              IS '删除标志（0代表存在 2代表删除）';
COMMENT ON COLUMN sys_role.create_by             IS '创建者';
COMMENT ON COLUMN sys_role.create_time           IS '创建时间';
COMMENT ON COLUMN sys_role.update_by             IS '更新者';
COMMENT ON COLUMN sys_role.update_time           IS '更新时间';
COMMENT ON COLUMN sys_role.remark                IS '备注';

-- gaussdb.sys_role_dept 定义
CREATE TABLE sys_role_dept (
    role_id BIGINT NOT NULL,
    dept_id BIGINT NOT NULL,
    CONSTRAINT sys_role_dept_pkey PRIMARY KEY (role_id, dept_id)
);

COMMENT ON TABLE  sys_role_dept         IS '角色和部门关联表';
COMMENT ON COLUMN sys_role_dept.role_id IS '角色ID';
COMMENT ON COLUMN sys_role_dept.dept_id IS '部门ID';

-- gaussdb.sys_role_menu 定义
CREATE TABLE sys_role_menu (
    role_id BIGINT NOT NULL,
    menu_id BIGINT NOT NULL,
    CONSTRAINT sys_role_menu_pkey PRIMARY KEY (role_id, menu_id)
);

COMMENT ON TABLE  sys_role_menu         IS '角色和菜单关联表';
COMMENT ON COLUMN sys_role_menu.role_id IS '角色ID';
COMMENT ON COLUMN sys_role_menu.menu_id IS '菜单ID';

-- gaussdb.sys_station_control 定义
CREATE TABLE sys_station_control (
    id                BIGSERIAL    PRIMARY KEY,
    robot_id          VARCHAR(55)  DEFAULT NULL,
    station_door_name VARCHAR(255) DEFAULT NULL,
    ip_address        VARCHAR(255) DEFAULT NULL,
    speed             INTEGER      DEFAULT 80,
    target_percent    INTEGER      DEFAULT 0,
    status            SMALLINT     DEFAULT 1,
    remark            VARCHAR(500) DEFAULT NULL,
    create_by         VARCHAR(64)  DEFAULT NULL,
    create_time       TIMESTAMP    DEFAULT NULL,
    update_by         VARCHAR(64)  DEFAULT NULL,
    update_time       TIMESTAMP    DEFAULT NULL,
    del_flag          CHAR(1)      DEFAULT '0'
);

COMMENT ON TABLE  sys_station_control                   IS '充电站控制管理表';
COMMENT ON COLUMN sys_station_control.id                IS '主键ID';
COMMENT ON COLUMN sys_station_control.robot_id          IS '机器人ID';
COMMENT ON COLUMN sys_station_control.station_door_name IS '充电站门名称';
COMMENT ON COLUMN sys_station_control.ip_address        IS 'IP地址';
COMMENT ON COLUMN sys_station_control.speed             IS '开门速度(0-100)';
COMMENT ON COLUMN sys_station_control.target_percent    IS '开门位置(0-100) 0代表完全关闭，100代表完全打开';
COMMENT ON COLUMN sys_station_control.status            IS '状态：1=启用，0=禁用';
COMMENT ON COLUMN sys_station_control.remark            IS '备注';
COMMENT ON COLUMN sys_station_control.create_by         IS '创建人';
COMMENT ON COLUMN sys_station_control.create_time       IS '创建时间';
COMMENT ON COLUMN sys_station_control.update_by         IS '更新人';
COMMENT ON COLUMN sys_station_control.update_time       IS '更新时间';
COMMENT ON COLUMN sys_station_control.del_flag          IS '删除标志：0=未删除，1=已删除';

-- gaussdb.sys_user 定义
CREATE TABLE sys_user (
    user_id         BIGSERIAL    PRIMARY KEY,
    dept_id         BIGINT       DEFAULT NULL,
    user_name       VARCHAR(30)  NOT NULL,
    nick_name       VARCHAR(30)  NOT NULL,
    user_type       VARCHAR(2)   DEFAULT '00',
    email           VARCHAR(50)  DEFAULT '',
    phonenumber     VARCHAR(11)  DEFAULT '',
    sex             CHAR(1)      DEFAULT '0',
    avatar          VARCHAR(100) DEFAULT '',
    password        VARCHAR(100) DEFAULT '',
    status          CHAR(1)      DEFAULT '0',
    del_flag        CHAR(1)      DEFAULT '0',
    login_ip        VARCHAR(128) DEFAULT '',
    login_date      TIMESTAMP    DEFAULT NULL,
    pwd_update_date TIMESTAMP    DEFAULT NULL,
    create_by       VARCHAR(64)  DEFAULT '',
    create_time     TIMESTAMP    DEFAULT NULL,
    update_by       VARCHAR(64)  DEFAULT '',
    update_time     TIMESTAMP    DEFAULT NULL,
    remark          VARCHAR(500) DEFAULT NULL
);

COMMENT ON TABLE  sys_user                 IS '用户信息表';
COMMENT ON COLUMN sys_user.user_id         IS '用户ID';
COMMENT ON COLUMN sys_user.dept_id         IS '部门ID';
COMMENT ON COLUMN sys_user.user_name       IS '用户账号';
COMMENT ON COLUMN sys_user.nick_name       IS '用户昵称';
COMMENT ON COLUMN sys_user.user_type       IS '用户类型（00系统用户）';
COMMENT ON COLUMN sys_user.email           IS '用户邮箱';
COMMENT ON COLUMN sys_user.phonenumber     IS '手机号码';
COMMENT ON COLUMN sys_user.sex             IS '用户性别（0男 1女 2未知）';
COMMENT ON COLUMN sys_user.avatar          IS '头像地址';
COMMENT ON COLUMN sys_user.password        IS '密码';
COMMENT ON COLUMN sys_user.status          IS '账号状态（0正常 1停用）';
COMMENT ON COLUMN sys_user.del_flag        IS '删除标志（0代表存在 2代表删除）';
COMMENT ON COLUMN sys_user.login_ip        IS '最后登录IP';
COMMENT ON COLUMN sys_user.login_date      IS '最后登录时间';
COMMENT ON COLUMN sys_user.pwd_update_date IS '密码最后更新时间';
COMMENT ON COLUMN sys_user.create_by       IS '创建者';
COMMENT ON COLUMN sys_user.create_time     IS '创建时间';
COMMENT ON COLUMN sys_user.update_by       IS '更新者';
COMMENT ON COLUMN sys_user.update_time     IS '更新时间';
COMMENT ON COLUMN sys_user.remark          IS '备注';

-- gaussdb.sys_user_post 定义
CREATE TABLE sys_user_post (
    user_id BIGINT NOT NULL,
    post_id BIGINT NOT NULL,
    CONSTRAINT sys_user_post_pkey PRIMARY KEY (user_id, post_id)
);

COMMENT ON TABLE  sys_user_post         IS '用户与岗位关联表';
COMMENT ON COLUMN sys_user_post.user_id IS '用户ID';
COMMENT ON COLUMN sys_user_post.post_id IS '岗位ID';

-- gaussdb.sys_user_role 定义
CREATE TABLE sys_user_role (
    user_id BIGINT NOT NULL,
    role_id BIGINT NOT NULL,
    CONSTRAINT sys_user_role_pkey PRIMARY KEY (user_id, role_id)
);

COMMENT ON TABLE  sys_user_role         IS '用户和角色关联表';
COMMENT ON COLUMN sys_user_role.user_id IS '用户ID';
COMMENT ON COLUMN sys_user_role.role_id IS '角色ID';

-- gaussdb.sys_valve_info 定义
CREATE TABLE sys_valve_info (
    id          BIGSERIAL    PRIMARY KEY,
    robot_id    VARCHAR(55)  DEFAULT NULL,
    valve_code  VARCHAR(64)  DEFAULT NULL,
    valve_name  VARCHAR(255) DEFAULT NULL,
    status      INTEGER      DEFAULT 1,
    remark      VARCHAR(500) DEFAULT NULL,
    create_by   VARCHAR(64)  DEFAULT '',
    create_time TIMESTAMP    DEFAULT NULL,
    update_by   VARCHAR(64)  DEFAULT '',
    update_time TIMESTAMP    DEFAULT NULL,
    del_flag    CHAR(1)      DEFAULT '0'
);

COMMENT ON TABLE  sys_valve_info            IS '阀门管理';
COMMENT ON COLUMN sys_valve_info.id         IS '主键ID';
COMMENT ON COLUMN sys_valve_info.robot_id   IS '机器人ID';
COMMENT ON COLUMN sys_valve_info.valve_code IS '阀门编号';
COMMENT ON COLUMN sys_valve_info.valve_name IS '阀门名称';
COMMENT ON COLUMN sys_valve_info.status     IS '状态：1=启用，0=禁用';
COMMENT ON COLUMN sys_valve_info.remark     IS '备注';
COMMENT ON COLUMN sys_valve_info.create_by  IS '创建者';
COMMENT ON COLUMN sys_valve_info.create_time IS '创建时间';
COMMENT ON COLUMN sys_valve_info.update_by  IS '更新者';
COMMENT ON COLUMN sys_valve_info.update_time IS '更新时间';
COMMENT ON COLUMN sys_valve_info.del_flag   IS '删除标志：0=未删除，1=已删除';

INSERT INTO robot_config (id,config_name,config_key,config_value,create_by,create_time,update_by,update_time,remark) VALUES
	 (1,'AI盒子地址','robot.ai.box.address','192.168.2.101','admin','2026-04-27 17:51:31',NULL,NULL,'AI盒子IP地址'),
	 (2,'AI盒子端口','robot.ai.box.port','9092','admin','2026-04-27 17:51:31',NULL,NULL,'AI盒子服务端口'),
	 (4,'机器人电池低电量保护阈值','robot.battery.power','20','admin','2026-04-27 17:51:31',NULL,NULL,'电池电量低于此值(百分比)时触发保护'),
	 (5,'Lora网关地址','robot.lora.gateway.address','127.0.0.1','admin','2026-04-27 17:51:31',NULL,NULL,'Lora网关IP地址'),
	 (6,'Lora网关端口','robot.lora.gateway.port','8888','admin','2026-04-27 17:51:31',NULL,NULL,'Lora网关MQTT端口'),
	 (8,'超时重试时效','robot.task.item.timeout','5','testRole001','2026-08-12 14:16:42','testRole002','2026-08-14 10:56:07',NULL),
	 (9,'录像管理地址','robot.task.surveillance.address','127.0.0.1','admin','2026-09-15 12:51:05','admin','2026-09-15 12:52:38','录像管理ip地址'),
	 (10,'录像管理端口','robot.task.surveillance.port','8888','admin','2026-09-15 12:53:05','admin','2026-09-15 12:53:15',NULL);
INSERT INTO robot_device_type (id,parent_id,type_level,type_name,type_value,create_by,create_time,update_by,update_time,icon_img,ext1,ext2,ext3,ext4,remark) VALUES
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
INSERT INTO robot_device_type (id,parent_id,type_level,type_name,type_value,create_by,create_time,update_by,update_time,icon_img,ext1,ext2,ext3,ext4,remark) VALUES
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
INSERT INTO robot_device_type (id,parent_id,type_level,type_name,type_value,create_by,create_time,update_by,update_time,icon_img,ext1,ext2,ext3,ext4,remark) VALUES
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
INSERT INTO robot_device_type (id,parent_id,type_level,type_name,type_value,create_by,create_time,update_by,update_time,icon_img,ext1,ext2,ext3,ext4,remark) VALUES
	 (31,10,3,'Zsl1 V026','Zsl1 V026',NULL,'2026-09-04 10:35:25',NULL,NULL,'Zsl1.png',NULL,NULL,NULL,NULL,NULL),
	 (32,10,3,'Zsl1 V027','Zsl1 V027',NULL,'2026-09-04 10:35:34',NULL,NULL,'Zsl1.png',NULL,NULL,NULL,NULL,NULL),
	 (33,10,3,'Zsl1W V027','Zsl1W V027',NULL,'2026-09-04 10:35:43',NULL,NULL,'Zsl1W.png',NULL,NULL,NULL,NULL,NULL),
	 (34,11,3,'D1MAX V003','D1MAX V003',NULL,'2026-09-04 10:35:55',NULL,NULL,'D1MAXV003.png',NULL,NULL,NULL,NULL,NULL),
	 (35,11,3,'D1MAX V008','D1MAX V008',NULL,'2026-09-04 10:36:04',NULL,NULL,'D1MAXV008.png',NULL,NULL,NULL,NULL,NULL);
INSERT INTO sys_config (config_id,config_name,config_key,config_value,config_type,create_by,create_time,update_by,update_time,remark) VALUES
	 (1,'主框架页-默认皮肤样式名称','sys.index.skinName','skin-blue','Y','admin','2025-06-25 03:56:22',NULL,NULL,'蓝色 skin-blue、绿色 skin-green、紫色 skin-purple、红色 skin-red、黄色 skin-yellow'),
	 (2,'用户管理-账号初始密码','sys.user.initPassword','123456','Y','admin','2025-06-25 03:56:22',NULL,NULL,'初始化密码 123456'),
	 (3,'主框架页-侧边栏主题','sys.index.sideTheme','theme-dark','Y','admin','2025-06-25 03:56:22',NULL,NULL,'深色主题theme-dark，浅色主题theme-light'),
	 (4,'账号自助-验证码开关','sys.account.captchaEnabled','true','Y','admin','2025-06-25 03:56:22',NULL,NULL,'是否开启验证码功能（true开启，false关闭）'),
	 (5,'账号自助-是否开启用户注册功能','sys.account.registerUser','false','Y','admin','2025-06-25 03:56:22',NULL,NULL,'是否开启注册用户功能（true开启，false关闭）'),
	 (6,'用户登录-黑名单列表','sys.login.blackIPList',NULL,'Y','admin','2025-06-25 03:56:22',NULL,NULL,'设置登录IP黑名单限制，多个匹配项以;分隔，支持匹配（*通配、网段）'),
	 (7,'用户管理-初始密码修改策略','sys.account.initPasswordModify','1','Y','admin','2025-06-25 03:56:22',NULL,NULL,'0：初始密码修改策略关闭，没有任何提示，1：提醒用户，如果未修改初始密码，则在登录时就会提醒修改密码对话框'),
	 (8,'用户管理-账号密码更新周期','sys.account.passwordValidateDays','0','Y','admin','2025-06-25 03:56:22',NULL,NULL,'密码更新周期（填写数字，数据初始化值为0不限制，若修改必须为大于0小于365的正整数），如果超过这个周期登录系统时，则在登录时就会提醒修改密码对话框');
INSERT INTO sys_dept (dept_id,parent_id,ancestors,dept_name,order_num,leader,phone,email,status,del_flag,create_by,create_time,update_by,update_time) VALUES
	 (1,0,'0','XX科技',0,NULL,NULL,NULL,'0','0','admin','2025-06-25 03:56:13','admin','2026-06-04 18:46:23');
INSERT INTO sys_dict_data (dict_code,dict_sort,dict_label,dict_value,dict_type,css_class,list_class,is_default,status,create_by,create_time,update_by,update_time,remark) VALUES
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
INSERT INTO sys_dict_data (dict_code,dict_sort,dict_label,dict_value,dict_type,css_class,list_class,is_default,status,create_by,create_time,update_by,update_time,remark) VALUES
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
INSERT INTO sys_dict_data (dict_code,dict_sort,dict_label,dict_value,dict_type,css_class,list_class,is_default,status,create_by,create_time,update_by,update_time,remark) VALUES
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
INSERT INTO sys_dict_data (dict_code,dict_sort,dict_label,dict_value,dict_type,css_class,list_class,is_default,status,create_by,create_time,update_by,update_time,remark) VALUES
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
INSERT INTO sys_dict_data (dict_code,dict_sort,dict_label,dict_value,dict_type,css_class,list_class,is_default,status,create_by,create_time,update_by,update_time,remark) VALUES
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
INSERT INTO sys_dict_data (dict_code,dict_sort,dict_label,dict_value,dict_type,css_class,list_class,is_default,status,create_by,create_time,update_by,update_time,remark) VALUES
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
INSERT INTO sys_dict_data (dict_code,dict_sort,dict_label,dict_value,dict_type,css_class,list_class,is_default,status,create_by,create_time,update_by,update_time,remark) VALUES
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
INSERT INTO sys_dict_data (dict_code,dict_sort,dict_label,dict_value,dict_type,css_class,list_class,is_default,status,create_by,create_time,update_by,update_time,remark) VALUES
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
INSERT INTO sys_dict_data (dict_code,dict_sort,dict_label,dict_value,dict_type,css_class,list_class,is_default,status,create_by,create_time,update_by,update_time,remark) VALUES
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
INSERT INTO sys_dict_data (dict_code,dict_sort,dict_label,dict_value,dict_type,css_class,list_class,is_default,status,create_by,create_time,update_by,update_time,remark) VALUES
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
INSERT INTO sys_dict_data (dict_code,dict_sort,dict_label,dict_value,dict_type,css_class,list_class,is_default,status,create_by,create_time,update_by,update_time,remark) VALUES
	 (178,3,'致命','3','sys_notice_type',NULL,'fatal','N','0','admin','2026-09-03 23:10:48','admin','2026-09-07 11:10:01','fatal'),
	 (179,0,'提示','0','sys_notice_type',NULL,'einfo','N','0','admin','2026-09-07 10:54:27','admin','2026-09-08 09:30:50','info'),
	 (180,0,'在线任务','0','sys_job_online',NULL,'success','N','0','admin','2026-09-07 12:39:59','admin','2026-09-07 17:11:12',NULL),
	 (181,1,'离线任务','1','sys_job_online',NULL,'warning','N','0','admin','2026-09-07 12:40:09','admin','2026-09-07 17:11:18',NULL),
	 (183,0,'未同步','0','sys_job_sync_status',NULL,'primary','N','0','admin','2026-09-08 09:32:33',NULL,NULL,NULL),
	 (184,0,'已同步','1','sys_job_sync_status',NULL,'success','N','0','admin','2026-09-08 09:32:44',NULL,NULL,NULL),
	 (185,0,'无需同步','2','sys_job_sync_status',NULL,'info','N','0','admin','2026-09-08 10:34:07',NULL,NULL,NULL),
	 (186,0,'未确认','0','alarm_read_status',NULL,'primary','N','0','admin','2026-09-10 18:26:16',NULL,NULL,'未确认'),
	 (187,0,'已确认','1','alarm_read_status',NULL,'success','N','0','admin','2026-09-10 18:26:33',NULL,NULL,'已确认');
INSERT INTO sys_dict_type (dict_id,dict_name,dict_type,status,create_by,create_time,update_by,update_time,remark) VALUES
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
INSERT INTO sys_dict_type (dict_id,dict_name,dict_type,status,create_by,create_time,update_by,update_time,remark) VALUES
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
INSERT INTO sys_dict_type (dict_id,dict_name,dict_type,status,create_by,create_time,update_by,update_time,remark) VALUES
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
INSERT INTO sys_dict_type (dict_id,dict_name,dict_type,status,create_by,create_time,update_by,update_time,remark) VALUES
	 (120,'离线任务同步状态','sys_job_sync_status','0','admin','2026-09-08 09:32:07',NULL,NULL,'离线任务同步状态'),
	 (121,'告警确认状态','alarm_read_status','0','admin','2026-09-10 18:25:51',NULL,NULL,'0未确认，1已确认');
INSERT INTO sys_menu (menu_id,menu_name,parent_id,order_num,"path",component,"query",route_name,is_frame,is_cache,menu_type,"visible",status,perms,icon,create_by,create_time,update_by,update_time,remark) VALUES
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
INSERT INTO sys_menu (menu_id,menu_name,parent_id,order_num,"path",component,"query",route_name,is_frame,is_cache,menu_type,"visible",status,perms,icon,create_by,create_time,update_by,update_time,remark) VALUES
	 (107,'告警通知',2214,8,'notice','system/notice/index',NULL,NULL,1,0,'C','0','0','system:notice:list','message','admin','2025-06-25 03:56:16','admin','2026-09-11 17:49:16','通知公告菜单'),
	 (108,'日志管理',1,9,'log',NULL,NULL,NULL,1,0,'M','0','0',NULL,'log','admin','2025-06-25 03:56:16',NULL,NULL,'日志管理菜单'),
	 (109,'在线用户',2,1,'online','monitor/online/index',NULL,NULL,1,0,'C','0','0','monitor:online:list','online','admin','2025-06-25 03:56:16',NULL,NULL,'在线用户菜单'),
	 (110,'定时任务',2,2,'job','monitor/job/index',NULL,NULL,1,0,'C','0','0','monitor:job:list','job','admin','2025-06-25 03:56:16',NULL,NULL,'定时任务菜单'),
	 (111,'数据监控',2,3,'druid','monitor/druid/index',NULL,NULL,1,0,'C','0','0','monitor:druid:list','druid','admin','2025-06-25 03:56:16',NULL,NULL,'数据监控菜单'),
	 (112,'服务监控',2,4,'server','monitor/server/index',NULL,NULL,1,0,'C','0','0','monitor:server:list','server','admin','2025-06-25 03:56:16',NULL,NULL,'服务监控菜单'),
	 (113,'缓存监控',2,5,'cache','monitor/cache/index',NULL,NULL,1,0,'C','0','0','monitor:cache:list','redis','admin','2025-06-25 03:56:16',NULL,NULL,'缓存监控菜单'),
	 (114,'缓存列表',2,6,'cacheList','monitor/cache/list',NULL,NULL,1,0,'C','0','0','monitor:cache:list','redis-list','admin','2025-06-25 03:56:16',NULL,NULL,'缓存列表菜单');
INSERT INTO sys_menu (menu_id,menu_name,parent_id,order_num,"path",component,"query",route_name,is_frame,is_cache,menu_type,"visible",status,perms,icon,create_by,create_time,update_by,update_time,remark) VALUES
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
INSERT INTO sys_menu (menu_id,menu_name,parent_id,order_num,"path",component,"query",route_name,is_frame,is_cache,menu_type,"visible",status,perms,icon,create_by,create_time,update_by,update_time,remark) VALUES
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
INSERT INTO sys_menu (menu_id,menu_name,parent_id,order_num,"path",component,"query",route_name,is_frame,is_cache,menu_type,"visible",status,perms,icon,create_by,create_time,update_by,update_time,remark) VALUES
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
INSERT INTO sys_menu (menu_id,menu_name,parent_id,order_num,"path",component,"query",route_name,is_frame,is_cache,menu_type,"visible",status,perms,icon,create_by,create_time,update_by,update_time,remark) VALUES
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
INSERT INTO sys_menu (menu_id,menu_name,parent_id,order_num,"path",component,"query",route_name,is_frame,is_cache,menu_type,"visible",status,perms,icon,create_by,create_time,update_by,update_time,remark) VALUES
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
INSERT INTO sys_menu (menu_id,menu_name,parent_id,order_num,"path",component,"query",route_name,is_frame,is_cache,menu_type,"visible",status,perms,icon,create_by,create_time,update_by,update_time,remark) VALUES
	 (1047,'批量强退',109,2,'#',NULL,NULL,NULL,1,0,'F','0','0','monitor:online:batchLogout','#','admin','2025-06-25 03:56:16',NULL,NULL,NULL),
	 (1048,'单条强退',109,3,'#',NULL,NULL,NULL,1,0,'F','0','0','monitor:online:forceLogout','#','admin','2025-06-25 03:56:16',NULL,NULL,NULL),
	 (1049,'任务查询',110,1,'#',NULL,NULL,NULL,1,0,'F','0','0','monitor:job:query','#','admin','2025-06-25 03:56:16',NULL,NULL,NULL),
	 (1050,'任务新增',110,2,'#',NULL,NULL,NULL,1,0,'F','0','0','monitor:job:add','#','admin','2025-06-25 03:56:16',NULL,NULL,NULL),
	 (1051,'任务修改',110,3,'#',NULL,NULL,NULL,1,0,'F','0','0','monitor:job:edit','#','admin','2025-06-25 03:56:16',NULL,NULL,NULL),
	 (1052,'任务删除',110,4,'#',NULL,NULL,NULL,1,0,'F','0','0','monitor:job:remove','#','admin','2025-06-25 03:56:16',NULL,NULL,NULL),
	 (1053,'状态修改',110,5,'#',NULL,NULL,NULL,1,0,'F','0','0','monitor:job:changeStatus','#','admin','2025-06-25 03:56:16',NULL,NULL,NULL),
	 (1054,'任务导出',110,6,'#',NULL,NULL,NULL,1,0,'F','0','0','monitor:job:export','#','admin','2025-06-25 03:56:16',NULL,NULL,NULL);
INSERT INTO sys_menu (menu_id,menu_name,parent_id,order_num,"path",component,"query",route_name,is_frame,is_cache,menu_type,"visible",status,perms,icon,create_by,create_time,update_by,update_time,remark) VALUES
	 (2008,'地图管理',2085,1,'map','core/map/index',NULL,NULL,1,0,'C','0','0','core:map:list','international','admin','2025-06-26 06:21:48','admin','2025-12-22 17:04:39',NULL),
	 (2027,'机器人管理',2086,2,'vehicle','core/vehicle/index',NULL,NULL,1,0,'C','0','0','core:vehicle:list','example','admin','2025-07-07 04:09:28','admin','2025-12-22 17:11:26',NULL),
	 (2028,'任务管理',0,1,'task',NULL,NULL,NULL,1,0,'M','0','0',NULL,'component','admin','2025-07-30 06:22:09','admin','2026-08-11 12:05:17',NULL),
	 (2030,'任务编排',2028,0,'template/index','task/template/index',NULL,NULL,1,0,'C','0','0','core:template:list','monitor','admin','2025-07-30 06:28:29','admin','2025-09-28 09:34:25',NULL),
	 (2043,'任务记录',2028,1,'run','task/record/index',NULL,NULL,1,0,'C','0','0','core:task:list','component','admin','2025-07-30 10:02:24','admin','2025-07-30 10:18:28',NULL),
	 (2049,'控制面板',2086,0,'vehicle/console','core/vehicle/console',NULL,NULL,1,0,'C','1','0','core:vehicle:ctrl','#','admin','2025-08-06 03:22:49','admin','2025-12-22 17:16:21',NULL);
INSERT INTO sys_menu (menu_id,menu_name,parent_id,order_num,"path",component,"query",route_name,is_frame,is_cache,menu_type,"visible",status,perms,icon,create_by,create_time,update_by,update_time,remark) VALUES
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
INSERT INTO sys_menu (menu_id,menu_name,parent_id,order_num,"path",component,"query",route_name,is_frame,is_cache,menu_type,"visible",status,perms,icon,create_by,create_time,update_by,update_time,remark) VALUES
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
INSERT INTO sys_menu (menu_id,menu_name,parent_id,order_num,"path",component,"query",route_name,is_frame,is_cache,menu_type,"visible",status,perms,icon,create_by,create_time,update_by,update_time,remark) VALUES
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
INSERT INTO sys_menu (menu_id,menu_name,parent_id,order_num,"path",component,"query",route_name,is_frame,is_cache,menu_type,"visible",status,perms,icon,create_by,create_time,update_by,update_time,remark) VALUES
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
INSERT INTO sys_menu (menu_id,menu_name,parent_id,order_num,"path",component,"query",route_name,is_frame,is_cache,menu_type,"visible",status,perms,icon,create_by,create_time,update_by,update_time,remark) VALUES
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
INSERT INTO sys_menu (menu_id,menu_name,parent_id,order_num,"path",component,"query",route_name,is_frame,is_cache,menu_type,"visible",status,perms,icon,create_by,create_time,update_by,update_time,remark) VALUES
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
INSERT INTO sys_menu (menu_id,menu_name,parent_id,order_num,"path",component,"query",route_name,is_frame,is_cache,menu_type,"visible",status,perms,icon,create_by,create_time,update_by,update_time,remark) VALUES
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
INSERT INTO sys_menu (menu_id,menu_name,parent_id,order_num,"path",component,"query",route_name,is_frame,is_cache,menu_type,"visible",status,perms,icon,create_by,create_time,update_by,update_time,remark) VALUES
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
INSERT INTO sys_menu (menu_id,menu_name,parent_id,order_num,"path",component,"query",route_name,is_frame,is_cache,menu_type,"visible",status,perms,icon,create_by,create_time,update_by,update_time,remark) VALUES
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
INSERT INTO sys_menu (menu_id,menu_name,parent_id,order_num,"path",component,"query",route_name,is_frame,is_cache,menu_type,"visible",status,perms,icon,create_by,create_time,update_by,update_time,remark) VALUES
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
INSERT INTO sys_menu (menu_id,menu_name,parent_id,order_num,"path",component,"query",route_name,is_frame,is_cache,menu_type,"visible",status,perms,icon,create_by,create_time,update_by,update_time,remark) VALUES
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
INSERT INTO sys_menu (menu_id,menu_name,parent_id,order_num,"path",component,"query",route_name,is_frame,is_cache,menu_type,"visible",status,perms,icon,create_by,create_time,update_by,update_time,remark) VALUES
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
INSERT INTO sys_menu (menu_id,menu_name,parent_id,order_num,"path",component,"query",route_name,is_frame,is_cache,menu_type,"visible",status,perms,icon,create_by,create_time,update_by,update_time,remark) VALUES
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
INSERT INTO sys_menu (menu_id,menu_name,parent_id,order_num,"path",component,"query",route_name,is_frame,is_cache,menu_type,"visible",status,perms,icon,create_by,create_time,update_by,update_time,remark) VALUES
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
INSERT INTO sys_menu (menu_id,menu_name,parent_id,order_num,"path",component,"query",route_name,is_frame,is_cache,menu_type,"visible",status,perms,icon,create_by,create_time,update_by,update_time,remark) VALUES
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
INSERT INTO sys_menu (menu_id,menu_name,parent_id,order_num,"path",component,"query",route_name,is_frame,is_cache,menu_type,"visible",status,perms,icon,create_by,create_time,update_by,update_time,remark) VALUES
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
INSERT INTO sys_menu (menu_id,menu_name,parent_id,order_num,"path",component,"query",route_name,is_frame,is_cache,menu_type,"visible",status,perms,icon,create_by,create_time,update_by,update_time,remark) VALUES
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
INSERT INTO sys_menu (menu_id,menu_name,parent_id,order_num,"path",component,"query",route_name,is_frame,is_cache,menu_type,"visible",status,perms,icon,create_by,create_time,update_by,update_time,remark) VALUES
	 (2230,'视频下载',2227,3,NULL,NULL,NULL,NULL,1,0,'F','0','0','robot:surveillance:download','#','admin','2026-09-15 12:09:06',NULL,NULL,NULL),
	 (2231,'录像管理',0,5,NULL,NULL,NULL,NULL,1,0,'M','0','0',NULL,'monitor','admin','2026-09-15 12:33:54','admin','2026-09-15 12:34:41',NULL),
	 (2232,'设备自检',2087,10,'statusCheck','core/statusCheck/index',null,null,1,0,'C','0','0','core:vehicle:statusCheck','monitor','admin','2026-09-20 17:51:02',NULL,null,'机器人插件状态检测页面'),
     (2233,'自检',2232,1,NULL,NULL,null,null,1,0,'F','0','0','core:vehicle:statusCheck','#','admin','2026-09-20 17:51:02',NULL,null,'插件状态检测执行按钮'),
     (2234,'商业授权','1','10','license','system/license/index',NULL,NULL,'1','0','C','0','0','system:license:list','lock','admin','2026-09-28 14:50:43','admin','2026-09-28 16:11:15','商业授权管理与更新'),
	 (2235,'授权查询','2234','1',NULL,NULL,NULL,NULL,'1','0','F','0','0','system:license:query','#','admin','2026-09-28 14:50:52',NULL,NULL,'查询商业授权信息与机器码'),
	 (2236,'上传授权','2234','2',NULL,NULL,NULL,NULL,'1','0','F','0','0','system:license:upload','#','admin','2026-09-28 14:50:55',NULL,NULL,'上传更新商业授权证书文件');
INSERT INTO sys_role (role_id,role_name,role_key,role_sort,data_scope,menu_check_strictly,dept_check_strictly,status,del_flag,create_by,create_time,update_by,update_time,remark) VALUES
	 (1,'超级管理员','admin',1,'1',1,1,'0','0','admin','2025-06-25 03:56:15',NULL,NULL,'超级管理员');
INSERT INTO sys_user (user_id,dept_id,user_name,nick_name,user_type,email,phonenumber,sex,avatar,"password",status,del_flag,login_ip,login_date,pwd_update_date,create_by,create_time,update_by,update_time,remark) VALUES
	 (1,100,'admin','管理员','00','773807831@qq.com','13000000000','0',NULL,'$2a$10$7JB720yubVSZvUI0rEqK/.VqGOZTH.ulu33dHOiBE8ByOhJIrdAu2','0','0','127.0.0.1','2026-09-17 12:00:05.028','2025-06-25 03:56:13','admin','2025-06-25 03:56:13',NULL,'2026-09-17 12:00:01.783249','管理员');
INSERT INTO sys_user_role (user_id,role_id) VALUES
	 (1,1);
	 
SELECT setval(pg_get_serial_sequence('postgres.gaussdb.robot_config', 'id'),COALESCE(MAX(id), 1)) FROM postgres.gaussdb.robot_config;


DO $$
DECLARE
    rec RECORD;
BEGIN
    FOR rec IN 
        SELECT 
            s.relname AS seq_name,
            n.nspname AS schema_name,
            t.relname AS table_name,
            a.attname AS column_name
        FROM pg_class s
        JOIN pg_namespace n ON n.oid = s.relnamespace
        JOIN pg_depend d ON d.objid = s.oid AND d.deptype = 'a'
        JOIN pg_class t ON t.oid = d.refobjid
        JOIN pg_attribute a ON a.attrelid = d.refobjid AND a.attnum = d.refobjsubid
        WHERE s.relkind = 'S' AND n.nspname = 'gaussdb'
    LOOP
        EXECUTE format('SELECT setval(%L, COALESCE((SELECT MAX(%I) FROM %I.%I), 1))', 
                       rec.schema_name || '.' || rec.seq_name, 
                       rec.column_name, 
                       rec.schema_name, 
                       rec.table_name);
    END LOOP;
END $$;
