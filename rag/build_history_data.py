# -*- coding: utf-8 -*-
"""
构建 RAG 历史数据集。

作用：
  1. 读取 data/history_records.json 中已有的历史记录（当前 100 条）。
  2. 用确定性的模板组合，额外生成 400 条（购物 200 + 时间 200），使总量达到 500 条。
  3. 写回 data/history_records.json，字段结构与既有数据保持一致。

为什么需要一个生成脚本：
  演示/测试数据需要可复现、可解释；直接手写大量 JSON 容易出错且无法追溯。
  本脚本使用固定随机种子，重复运行结果一致，并跳过已存在的 id，保证幂等。

运行方式（推荐在项目根目录）：
  python rag/build_history_data.py
"""

import json
import os
import random
from copy import deepcopy

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE_DIR, "..", "data", "history_records.json")

TARGET_TOTAL = 500
SHOPPING_TARGET = 250
TIME_TARGET = 250

# ---------------------------------------------------------------
# 购物商品池：名称 / 品类 / 典型价格
# ---------------------------------------------------------------
SHOPPING_PRODUCTS = [
    ("无线降噪耳机", "电子数码", 899),
    ("机械键盘", "电子数码", 399),
    ("便携蓝牙音箱", "电子数码", 299),
    ("智能手表", "电子数码", 1299),
    ("平板电脑", "电子数码", 2499),
    ("游戏鼠标", "电子数码", 199),
    ("显示器", "电子数码", 999),
    ("运动手环", "电子数码", 159),
    ("降噪台灯", "学习办公", 199),
    ("护眼学习灯", "学习办公", 249),
    ("人体工学椅", "学习办公", 899),
    ("升降桌", "学习办公", 1099),
    ("翻译笔", "学习办公", 399),
    ("学习平板", "学习办公", 1599),
    ("错题打印机", "学习办公", 299),
    ("空气炸锅", "生活家电", 429),
    ("电饭煲", "生活家电", 259),
    ("破壁机", "生活家电", 599),
    ("加湿器", "生活家电", 129),
    ("挂烫机", "生活家电", 199),
    ("扫地机器人", "生活家电", 1899),
    ("电动牙刷", "生活家电", 159),
    ("咖啡机", "生活家电", 699),
    ("羽绒服", "服饰", 599),
    ("运动鞋", "服饰", 459),
    ("休闲背包", "服饰", 229),
    ("围巾", "服饰", 89),
    ("运动外套", "服饰", 329),
    ("瑜伽垫", "运动户外", 99),
    ("哑铃套装", "运动户外", 199),
    ("跑步鞋", "运动户外", 559),
    ("露营帐篷", "运动户外", 699),
    ("山地自行车", "运动户外", 1699),
    ("坚果零食礼盒", "食品", 139),
    ("全麦面包机", "食品", 269),
    ("咖啡豆", "食品", 89),
    ("专业书籍", "图书", 158),
    ("考研真题", "图书", 109),
    ("手账本", "图书", 49),
    ("文具礼盒", "图书", 79),
    ("护肤精华", "美妆个护", 399),
    ("面膜套组", "美妆个护", 159),
    ("电动剃须刀", "美妆个护", 299),
    ("游戏手柄", "游戏", 349),
    ("游戏掌机", "游戏", 1499),
    ("收纳箱", "收纳", 59),
    ("桌面收纳架", "收纳", 89),
    ("行李箱", "出行", 399),
    ("旅行充电宝", "出行", 129),
    ("颈枕", "出行", 79),
]

SHOPPING_MOTIVATIONS = [
    "学习需要安静专注",
    "工作通勤省时省力",
    "想提升生活幸福感",
    "被博主种草想尝鲜",
    "换季或有刚需",
    "想减少重复家务",
    "想培养一个爱好",
    "送礼给家人朋友",
    "看中性价比想囤货",
    "改善睡眠和作息",
]

SHOPPING_USAGE = [
    "每天使用",
    "每周2-3次",
    "每月几次",
    "低频使用",
    "闲置",
    "一次性使用",
]

CATEGORY_PROS = {
    "电子数码": ["提升学习/工作效率", "使用体验流畅", "外观颜值高", "解放双手,节省时间"],
    "学习办公": ["对学习有帮助", "提升专注力", "长期使用价值高", "符合学习场景需求"],
    "生活家电": ["明显提升生活便利", "减轻家务负担", "省时省力", "使用频率高,不亏"],
    "服饰": ["穿着舒适", "匹配日常穿搭", "实用耐穿", "季节刚需"],
    "运动户外": ["促进锻炼习惯", "增强体质", "户外体验好", "陪伴时间较长"],
    "食品": ["满足日常口腹之欲", "适合分享", "囤货性价比高", "解压"],
    "图书": ["知识密度高", "提升认知", "可反复翻阅", "学习工具型书籍"],
    "美妆个护": ["改善状态", "提升自信", "日常消耗品", "使用后反馈不错"],
    "游戏": ["娱乐解压", "与朋友一起玩", "丰富课余生活", "游玩体验好"],
    "收纳": ["空间更整洁", "物品好找", "提升使用效率", "性价比高"],
    "出行": ["旅行/通勤方便", "收纳井井有条", "耐用", "解决出行痛点"],
}

CATEGORY_CONS = {
    "电子数码": ["更新换代快,容易过时", "价格偏高,预算压力", "使用频率不固定", "闲置风险高"],
    "学习办公": ["初期三分钟热度", "替代品较多", "实际用率不确定", "与现有设备重合"],
    "生活家电": ["占空间", "需要清洁维护", "可能吃灰", "功能重复"],
    "服饰": ["容易冲动消费", "尺码/风格不合适", "闲置率偏高", "衣柜已满"],
    "运动户外": ["坚持不下来", "可能三分钟热度", "占地方,积灰", "跟风买后少用"],
    "食品": ["容易多买浪费", "热量/健康顾虑", "临时兴起", "保质期有限"],
    "图书": ["买后很少翻", "同类型太多", "电子版替代", "吃灰"],
    "美妆个护": ["肤质不符", "容易囤积过期", "评价两极分化", "同类产品多"],
    "游戏": ["容易沉迷", "花费时间较长", "新鲜感消退快", "影响学习节奏"],
    "收纳": ["收纳箱变杂物箱", "尺寸不符", "只用几次", "多为心理安慰"],
    "出行": ["使用率低", "闲置时间长", "一年用不了几次", "占储物空间"],
}

TAGS_BY_CATEGORY = {
    "电子数码": ["电子", "数码", "科技"],
    "学习办公": ["学习", "办公", "效率"],
    "生活家电": ["家电", "居家", "省时"],
    "服饰": ["服饰", "穿搭", "日常"],
    "运动户外": ["运动", "户外", "健康"],
    "食品": ["食品", "美食", "囤货"],
    "图书": ["图书", "知识", "学习"],
    "美妆个护": ["美妆", "个护", "护肤"],
    "游戏": ["游戏", "娱乐", "放松"],
    "收纳": ["收纳", "整理", "居家"],
    "出行": ["出行", "旅行", "通勤"],
}

# ---------------------------------------------------------------
# 时间活动池：名称 / 类型 / 典型耗时（小时）
# ---------------------------------------------------------------
TIME_ACTIVITIES = [
    ("社团例会", "社交", 2),
    ("技术分享会", "技能", 3),
    ("志愿服务", "志愿", 4),
    ("篮球友谊赛", "运动", 3),
    ("班级聚餐", "社交", 2),
    ("校园兼职", "工作", 5),
    ("学术讲座", "技能", 2),
    ("技能培训课", "技能", 3),
    ("部门换届", "工作", 3),
    ("音乐节", "文化", 6),
    ("美术馆展览", "文化", 3),
    ("部门团建", "社交", 4),
    ("补课辅导", "工作", 3),
    ("考研自习", "技能", 6),
    ("项目组会", "工作", 2),
    ("志愿者培训", "志愿", 2),
    ("读书会", "文化", 2),
    ("健身房锻炼", "运动", 2),
    ("户外徒步", "运动", 6),
    ("夜跑活动", "运动", 1),
    ("合唱排练", "文化", 2),
    ("辩论赛", "技能", 3),
    ("摄影外拍", "文化", 4),
    ("编程马拉松", "技能", 8),
    ("社团联谊", "社交", 3),
    ("迎新晚会", "文化", 3),
    ("毕业旅行", "休闲", 12),
    ("博物馆讲解", "志愿", 3),
    ("论文答辩准备", "工作", 5),
    ("实习面试", "工作", 3),
    ("竞赛集训", "技能", 5),
    ("周末聚餐", "社交", 2),
    ("线上公开课", "技能", 2),
    ("企业参观", "工作", 3),
    ("志愿服务值班", "志愿", 4),
    ("新年音乐会", "文化", 2),
    ("羽毛球约球", "运动", 2),
    ("城市骑行", "运动", 4),
    ("剧本杀", "休闲", 3),
    ("桌游聚会", "社交", 3),
    ("社团招新", "社交", 4),
    ("PPT 制作分享", "技能", 2),
    ("实验室组会", "工作", 2),
    ("公益募捐", "志愿", 3),
    ("英语角", "技能", 2),
    ("游泳训练", "运动", 2),
    ("动漫展", "文化", 4),
    ("创业路演", "工作", 4),
    ("考研讲座", "技能", 2),
    ("期末复习营", "技能", 6),
]

TIME_BENEFITS = [
    "可以认识新朋友",
    "能提升专业技能",
    "能积累实践经历",
    "能放松心情",
    "能增长见识",
    "能拓展人脉",
    "能获得证书/奖励",
    "能锻炼表达能力",
]

TIME_ACTIVITY_TAGS = {
    "社交": ["社交", "人脉", "聚会"],
    "技能": ["技能", "学习", "提升"],
    "志愿": ["志愿", "公益", "奉献"],
    "运动": ["运动", "健康", "活力"],
    "工作": ["工作", "任务", "责任"],
    "文化": ["文化", "艺术", "体验"],
    "休闲": ["休闲", "放松", "娱乐"],
}

ACTIVITY_PROS = {
    "社交": ["认识新朋友", "增进感情", "获得归属感", "拓展人脉"],
    "技能": ["提升专业能力", "学到新知识", "积累实操经验", "对未来有帮助"],
    "志愿": ["帮助他人,有成就感", "社会责任感提升", "增加社会阅历", "结交志同道合伙伴"],
    "运动": ["增强体质", "释放压力", "养成运动习惯", "精神状态更好"],
    "工作": ["锻炼责任心", "提升组织能力", "积累履历", "对未来就业有帮助"],
    "文化": ["增长见闻", "陶冶情操", "丰富课余生活", "开阔视野"],
    "休闲": ["释放压力", "愉悦心情", "调节状态", "恢复精力"],
}

ACTIVITY_CONS = {
    "社交": ["占用较多时间", "可能打乱学习计划", "社交疲劳", "与课程冲突"],
    "技能": ["需要较多精力", "短期看不到回报", "内容偏难,坚持难", "挤占复习时间"],
    "志愿": ["耗时较长", "可能耽误正事", "体力/精力消耗大", "与课程撞期"],
    "运动": ["需要持续坚持", "容易受伤", "时间成本高", "与学业冲突"],
    "工作": ["增加任务负担", "时间不可控", "可能过度劳累", "与学习冲突"],
    "文化": ["票务/路程成本", "往返耗时", "热情消退快", "与作业撞期"],
    "休闲": ["容易上瘾", "影响正事", "消费较高", "节律被打乱"],
}

# ---------------------------------------------------------------
# 已有记录读取
# ---------------------------------------------------------------
def load_existing():
    if not os.path.exists(DATA_PATH):
        return []
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, list) else []


def existing_count_by_type(records):
    shop = sum(1 for r in records if r.get("case_type") == "shopping")
    time_n = sum(1 for r in records if r.get("case_type") == "time")
    return shop, time_n


# ---------------------------------------------------------------
# 购物记录生成
# ---------------------------------------------------------------
def _build_shopping_record(idx, product, motivation, usage, result, rng):
    name, category, price = product
    record_id = f"h_shop_{idx}"
    title = f"{name} 消费复盘"
    pros_pool = CATEGORY_PROS[category]
    cons_pool = CATEGORY_CONS[category]
    random_pros = rng.sample(pros_pool, k=min(2, len(pros_pool)))
    random_cons = rng.sample(cons_pool, k=min(2, len(cons_pool)))
    tags = list(TAGS_BY_CATEGORY[category])
    tags.append(result)

    if result == "worth":
        verdict = "买得值，成为日常高频用品。"
        final_decision = "buy"
    elif result == "regret":
        verdict = "买后闲置较多，复盘认为是冲动消费。"
        final_decision = "reject"
    else:
        verdict = "不亏也不赚，属于可买可不买的物品。"
        final_decision = "neutral"

    content = (
        f"花费 {price} 元购买了 {name}。出于{motivation}的目的入手，"
        f"{verdict}使用频率约{usage}。"
    )
    context = f"当时为了满足【{category}】的需求，考察了一段时间才决定入手。"

    return {
        "id": record_id,
        "case_id": f"c_shop_{rng.randint(500, 999)}",
        "report_id": f"rep_{rng.randint(1000, 9999)}",
        "title": title,
        "content": content,
        "context": context,
        "price": price,
        "usage_frequency": usage,
        "pros": random_pros,
        "cons": random_cons,
        "final_decision": final_decision,
        "result": result,
        "source": "decision_history",
        "case_type": "shopping",
        "tags": tags,
        "created_at": f"202{ idx % 10 }-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}T00:00:00+08:00",
    }


def generate_shopping(records, target, start_idx, rng):
    result_cycle = ["worth", "regret", "neutral", "worth", "neutral", "regret"]
    i = start_idx
    name_i = 0
    mot_i = 0
    while existing_count_by_type(records)[0] < target and len(SHOPPING_PRODUCTS) > 0:
        product = SHOPPING_PRODUCTS[name_i % len(SHOPPING_PRODUCTS)]
        motivation = SHOPPING_MOTIVATIONS[mot_i % len(SHOPPING_MOTIVATIONS)]
        usage = SHOPPING_USAGE[(name_i + mot_i) % len(SHOPPING_USAGE)]
        result = result_cycle[(name_i + mot_i) % len(result_cycle)]
        record = _build_shopping_record(i, product, motivation, usage, result, rng)
        records.append(record)
        i += 1
        name_i += 1
        mot_i += 1


# ---------------------------------------------------------------
# 时间记录生成
# ---------------------------------------------------------------
def _build_time_record(idx, activity, benefit, result, rng):
    name, act_type, hours = activity
    record_id = f"h_time_{idx}"
    title = f"{name} 精力投入复盘"
    pros_pool = ACTIVITY_PROS[act_type]
    cons_pool = ACTIVITY_CONS[act_type]
    random_pros = rng.sample(pros_pool, k=min(2, len(pros_pool)))
    random_cons = rng.sample(cons_pool, k=min(2, len(cons_pool)))
    tags = list(TIME_ACTIVITY_TAGS[act_type])
    tags.append(result)

    if result == "worth":
        verdict = "整体值得，是一次不错的个人成长投入。"
        final_decision = "do"
    elif result == "regret":
        verdict = "事后复盘发现占用了太多本该做正事的时间，得不偿失。"
        final_decision = "cancel"
    else:
        verdict = "有收获也有消耗，属于值得考虑但不强求的经历。"
        final_decision = "neutral"

    content = (
        f"投入约 {hours} 小时参加了 {name}。目的主要是{benefit}，"
        f"{verdict}"
    )
    context = f"当时在【{act_type}】方面有需求，决定去试试。"

    return {
        "id": record_id,
        "case_id": f"c_time_{rng.randint(500, 999)}",
        "report_id": f"rep_{rng.randint(1000, 9999)}",
        "title": title,
        "content": content,
        "context": context,
        "price": 0,
        "usage_frequency": "一次性投入",
        "pros": random_pros,
        "cons": random_cons,
        "final_decision": final_decision,
        "result": result,
        "source": "decision_history",
        "case_type": "time",
        "tags": tags,
        "created_at": f"202{ idx % 10 }-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}T00:00:00+08:00",
    }


def generate_time(records, target, start_idx, rng):
    result_cycle = ["worth", "neutral", "regret", "worth", "regret", "neutral"]
    i = start_idx
    name_i = 0
    ben_i = 0
    while existing_count_by_type(records)[1] < target and len(TIME_ACTIVITIES) > 0:
        activity = TIME_ACTIVITIES[name_i % len(TIME_ACTIVITIES)]
        benefit = TIME_BENEFITS[ben_i % len(TIME_BENEFITS)]
        result = result_cycle[(name_i + ben_i) % len(result_cycle)]
        record = _build_time_record(i, activity, benefit, result, rng)
        records.append(record)
        i += 1
        name_i += 1
        ben_i += 1


# ---------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------
def main():
    rng = random.Random(42)

    records = load_existing()
    # 去重，避免重复运行导致重复追加
    seen = set()
    unique_records = []
    for r in records:
        rid = r.get("id")
        if rid not in seen:
            seen.add(rid)
            unique_records.append(r)
    records = unique_records

    shop_count, time_count = existing_count_by_type(records)
    print(f"现有记录：总 {len(records)}（购物 {shop_count} / 时间 {time_count}）")

    # 找到下一个空闲 id 起点
    shop_idx = 1050
    time_idx = 2050
    for r in records:
        if r.get("case_type") == "shopping" and r.get("id", "").startswith("h_shop_"):
            try:
                shop_idx = max(shop_idx, int(r["id"].replace("h_shop_", "")) + 1)
            except ValueError:
                pass
        if r.get("case_type") == "time" and r.get("id", "").startswith("h_time_"):
            try:
                time_idx = max(time_idx, int(r["id"].replace("h_time_", "")) + 1)
            except ValueError:
                pass

    generate_shopping(records, SHOPPING_TARGET, shop_idx, rng)
    generate_time(records, TIME_TARGET, time_idx, rng)

    shop_count, time_count = existing_count_by_type(records)
    print(f"生成完成：总 {len(records)}（购物 {shop_count} / 时间 {time_count}）")

    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    print(f"已写入 {DATA_PATH}")


if __name__ == "__main__":
    main()
