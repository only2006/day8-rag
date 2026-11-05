"""Day 18 · 端到端评测集：评回答，不只是评检索。

数据结构说明：
    id           唯一编号，失败时好定位
    q            问题（必须同义改写，不能照抄原文）
    category     类别，用于分组统计
    expect_refusal  这条是否应该拒答
    must_include 关键词组：[[同义词A1, A2], [同义词B1, B2]]
                 → 每组至少命中一个才算「答到要点」
                 → 用词组是为了避免「答案对了但用词不同」的假阴性
    must_not     不该出现的词（防串味，比如问周报却答了水杯）

注意：不要为了刷分反复改测试集。
      测试集调一次可以，调到 100% 就是过拟合，面试官一问细节就露馅。
"""

CASES: list[dict] = [
    # ---------- 事实型（直接问，答案在文档里明确写着）----------
    {
        "id": "F01",
        "q": "登录功能改了什么",
        "category": "事实型",
        "expect_refusal": False,
        "must_include": [["登录"], ["重构", "改造", "优化"]],
        "must_not": ["年假"],
    },
    {
        "id": "F02",
        "q": "接口响应时间优化了多少",
        "category": "事实型",
        "expect_refusal": False,
        "must_include": [["320"], ["110"]],
        "must_not": [],
    },
    {
        "id": "F03",
        "q": "支付出问题找谁解决",
        "category": "事实型",
        "expect_refusal": False,
        "must_include": [["厂商", "供应商", "第三方"]],
        "must_not": [],
    },
    {
        "id": "F04",
        "q": "谁负责前端",
        "category": "表格数字",
        "expect_refusal": False,
        "must_include": [["小明"]],
        "must_not": [],
    },
    {
        "id": "F05",
        "q": "小刚在做什么任务",
        "category": "表格数字",
        "expect_refusal": False,
        "must_include": [["测试"]],
        "must_not": [],
    },

    # ---------- 同义改写（换个说法问，考语义检索）----------
    {
        "id": "S01",
        "q": "钱付不出去卡住了怎么办",
        "category": "同义改写",
        "expect_refusal": False,
        "must_include": [["支付"], ["超时", "厂商", "排查"]],
        "must_not": [],
    },
    {
        "id": "S02",
        "q": "这个杯子第一次用之前要注意什么",
        "category": "同义改写",
        "expect_refusal": False,
        "must_include": [["充电", "charge", "充满"]],
        "must_not": [],
    },

    # ---------- 产品参数（跨文档，容易串味）----------
    {
        "id": "P01",
        "q": "容量最大的那款是多少毫升",
        "category": "产品参数",
        "expect_refusal": False,
        "must_include": [["600"]],
        "must_not": [],
    },
    {
        "id": "P02",
        "q": "哪个型号防水级别最高",
        "category": "产品参数",
        "expect_refusal": False,
        "must_include": [["IPX8"]],
        "must_not": [],
    },
    {
        "id": "P03",
        "q": "CW-200 的电池续航多久",
        "category": "产品参数",
        "expect_refusal": False,
        "must_include": [["14"]],
        "must_not": [],
    },

    # ---------- 长文档（智能家居手册）----------
    {
        "id": "L01",
        "q": "中控怎么恢复出厂设置",
        "category": "长文档",
        "expect_refusal": False,
        "must_include": [["恢复出厂"]],
        "must_not": [],
    },
    {
        "id": "L02",
        "q": "设备离线了怎么排查",
        "category": "长文档",
        "expect_refusal": False,
        "must_include": [["离线", "网络", "日志"]],
        "must_not": [],
    },

    # ---------- 应拒答（文档里确实没有）----------
    {
        "id": "R01",
        "q": "公司的年假政策是什么",
        "category": "应拒答",
        "expect_refusal": True,
        "must_include": [],
        "must_not": ["5 天", "10 天", "带薪"],
    },
    {
        "id": "R02",
        "q": "Python 的 GIL 是什么",
        "category": "应拒答",
        "expect_refusal": True,
        "must_include": [],
        "must_not": ["全局解释器锁"],
    },
    {
        "id": "R03",
        "q": "2024 年诺贝尔文学奖得主是谁",
        "category": "应拒答",
        "expect_refusal": True,
        "must_include": [],
        "must_not": ["韩江"],
    },

    # ============ 后补 15 条（2026-11-05）============
    # 来源：weekly.docx / report.pdf / 智能家居中控手册.txt /
    #       智能摄像头使用FAQ.txt / 智能门锁安装与排障手册.txt
    # 写法：不照抄原文用词，用「不懂文档的人会怎么问」的口语化说法；
    #       must_include 用同义词组，且每组至少一个词在语料里真实出现过。

    # ---------- 事实型 +3 ----------
    {
        "id": "F06",
        "q": "后端那部分收尾了吗",
        "category": "事实型",
        "expect_refusal": False,
        "must_include": [["小红"], ["已完成", "完成"]],
        "must_not": [],
    },
    {
        "id": "F07",
        "q": "录像用的存储卡最大能插多大的",
        "category": "事实型",
        "expect_refusal": False,
        "must_include": [["256"]],
        "must_not": [],
    },
    {
        "id": "F08",
        "q": "门锁换一次电池大概能用多久",
        "category": "事实型",
        "expect_refusal": False,
        "must_include": [["八个月", "8 个月", "8个月"]],
        "must_not": [],
    },

    # ---------- 同义改写 +4 ----------
    {
        "id": "S03",
        "q": "天一黑画面就变黑白，是坏掉了吗",
        "category": "同义改写",
        "expect_refusal": False,
        "must_include": [["红外", "夜视"], ["黑白"]],
        "must_not": [],
    },
    {
        "id": "S04",
        "q": "主机能塞进家里那个弱电箱吗",
        "category": "同义改写",
        "expect_refusal": False,
        "must_include": [["金属", "弱电箱"], ["屏蔽", "下降"]],
        "must_not": [],
    },
    {
        "id": "S05",
        "q": "路由器开了双频合一，锁一直连不上怎么办",
        "category": "同义改写",
        "expect_refusal": False,
        "must_include": [["2.4GHz", "2.4G"], ["5GHz", "拆分", "关闭"]],
        "must_not": [],
    },
    {
        "id": "S06",
        "q": "以后把设备转给别人，得留着什么东西当凭证",
        "category": "同义改写",
        "expect_refusal": False,
        "must_include": [["备份密钥", "密钥"]],
        "must_not": [],
    },

    # ---------- 产品参数 +2 ----------
    {
        "id": "P04",
        "q": "最入门那款杯子能装多少",
        "category": "产品参数",
        "expect_refusal": False,
        "must_include": [["400"]],
        "must_not": [],
    },
    {
        "id": "P05",
        "q": "顶配那款充一次电能撑几天",
        "category": "产品参数",
        "expect_refusal": False,
        "must_include": [["30"]],
        "must_not": [],
    },

    # ---------- 长文档 +3 ----------
    {
        "id": "L03",
        "q": "按一下复位键会不会把设好的场景全删了",
        "category": "长文档",
        "expect_refusal": False,
        "must_include": [["复位"], ["网络配置", "场景"]],
        "must_not": [],
    },
    {
        "id": "L04",
        "q": "第一次进后台，密码最少要设多少位",
        "category": "长文档",
        "expect_refusal": False,
        "must_include": [["十二", "12"]],
        "must_not": [],
    },
    {
        "id": "L05",
        "q": "子设备离网关最远能放多远",
        "category": "长文档",
        "expect_refusal": False,
        "must_include": [["十米", "10 米", "10米"]],
        "must_not": [],
    },

    # ---------- 应拒答 +3 ----------
    {
        "id": "R04",
        "q": "公司年终奖按几个月发",
        "category": "应拒答",
        "expect_refusal": True,
        "must_include": [],
        "must_not": ["13薪", "14薪", "双倍"],
    },
    {
        "id": "R05",
        "q": "广州明天会不会下雨",
        "category": "应拒答",
        "expect_refusal": True,
        "must_include": [],
        "must_not": ["降雨概率", "气温", "多云转晴"],
    },
    {
        "id": "R06",
        "q": "公司的公积金缴存比例是多少",
        "category": "应拒答",
        "expect_refusal": True,
        "must_include": [],
        "must_not": ["缴存比例", "12%", "提取"],
    },
]