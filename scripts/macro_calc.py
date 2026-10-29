#!/usr/bin/env python3
"""
谭成义（谭师）饮食体系宏量营养素与个人缺口计算器
支持：
1. 默认自动识别当天是星期几，自动匹配 82kg 一周四练（1245）分日档位（周一/四 大消耗日、周二/五 常规训练日、周三/六/日 休息日）
2. 自动扣除个人每日固定基底（玉米+2全蛋+特仑苏+无糖阿萨姆奶茶+2勺酵母蛋白粉）及今日已吃餐食
3. 内置丰富常吃预设（711能量碗、饭团、香蕉、自制咖喱红扁豆炖鸡腿、水煮饺子、拉面/汤面、赛百味、麦当劳双吉等）
4. 将剩余营养素缺口自动折算为日常食材重量（熟米饭、自制咖喱红扁豆炖鸡腿、7-11能量碗、瘦牛肉/鱼虾等）
"""

import argparse
import datetime
import json
import sys

# 谭成义白板官方系数表：(碳水g/kg, 蛋白质g/kg, 脂肪g/kg)
WHITEBOARD_MATRIX = {
    "male": {
        "2-3": (2.2, 1.4, 0.8),
        "4-5": (2.5, 1.6, 0.9),
        "6-7": (3.0, 1.7, 1.0),
        "8-9": (3.5, 1.8, 1.0),
    },
    "female": {
        "2-3": (2.0, 1.4, 1.0),
        "4-5": (2.2, 1.6, 1.1),
        "6-7": (2.5, 1.7, 1.1),
        "8-9": (3.0, 1.8, 1.2),
    },
}

# 用户 82kg 一周四练（1245）分日预设目标（克）
USER_82KG_DAY_TARGETS = {
    "high": {
        "label": "周一/周四（练背/练腿大消耗日 · 2.8~3.0倍碳水档）",
        "c": 235.0,
        "p": 140.0,
        "f": 75.0,
    },
    "moderate": {
        "label": "周二/周五（练胸/上肢补强日 · 2.5倍碳水稳健档）",
        "c": 205.0,
        "p": 135.0,
        "f": 72.0,
    },
    "rest": {
        "label": "周三/周六/周日（彻底休息日 · 2.2倍碳水换口味档）",
        "c": 180.0,
        "p": 130.0,
        "f": 75.0,
    },
}

DAY_TO_MODE = {
    "mon": "high",
    "1": "high",
    "周一": "high",
    "星期一": "high",
    "thu": "high",
    "4": "high",
    "周四": "high",
    "星期四": "high",
    "tue": "moderate",
    "2": "moderate",
    "周二": "moderate",
    "星期二": "moderate",
    "fri": "moderate",
    "5": "moderate",
    "周五": "moderate",
    "星期五": "moderate",
    "wed": "rest",
    "3": "rest",
    "周三": "rest",
    "星期三": "rest",
    "sat": "rest",
    "6": "rest",
    "周六": "rest",
    "星期六": "rest",
    "sun": "rest",
    "7": "rest",
    "周日": "rest",
    "星期日": "rest",
    "星期天": "rest",
}

WEEKDAY_NAMES_ZH = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

# 个人每日固定基底明细
USER_BASE_ITEMS = [
    {"name": "早餐：1根中等玉米 + 2个全蛋", "c": 32.0, "p": 18.0, "f": 11.0},
    {"name": "特仑苏纯牛奶 (1盒 250ml)", "c": 13.3, "p": 9.0, "f": 11.0},
    {"name": "统一阿萨姆无糖奶茶 (1瓶 500ml)", "c": 0.0, "p": 3.0, "f": 6.5},
    {"name": "酵母蛋白粉 (2勺 约50g)", "c": 4.0, "p": 38.0, "f": 2.0},
]

# 常见单品预设库
FOOD_PRESETS = {
    "711_bowl": {
        "name": "7-11 黑椒烤鸡能量碗 (1碗 255g 实测标签)",
        "c": 26.8,
        "p": 17.3,
        "f": 6.4,
    },
    "711_onigiri": {"name": "便利店饭团 (1个)", "c": 35.0, "p": 4.0, "f": 2.0},
    "banana": {"name": "中等香蕉 (1根)", "c": 25.0, "p": 1.5, "f": 0.3},
    "curry_dal": {
        "name": "自制纯咖喱粉红扁豆炖去皮鸡腿 (1标准份: 80g干扁豆+200g去皮鸡腿+150g胡萝卜洋葱丁)",
        "c": 60.0,
        "p": 59.0,
        "f": 13.0,
    },
    "bread_floss": {"name": "桃李鸡蛋香松面包 (1袋 120g 实测标签)", "c": 56.4, "p": 10.6, "f": 18.1},
    "bread_brownie": {"name": "桃李布朗尼蛋糕 (1袋 100g 实测标签)", "c": 57.0, "p": 6.5, "f": 16.3},
    "bread_tiramisu": {"name": "艾尼卡提拉米苏脆皮面包 (1袋 100g 实测标签)", "c": 43.3, "p": 5.5, "f": 13.0},
    "dumplings": {"name": "手工水煮菜肉水饺 (1盘 约15-18个)", "c": 80.0, "p": 26.0, "f": 22.0},
    "noodles_beef": {"name": "苏式汤面/兰州拉面 + 单加牛肉 (1碗 少喝汤)", "c": 78.0, "p": 32.0, "f": 12.0},
    "subway_6inch": {"name": "赛百味 6寸全麦香烤牛肉/照烧鸡三明治 (1个)", "c": 42.0, "p": 24.0, "f": 6.0},
    "mcd_double_cheese": {"name": "麦当劳双层吉士汉堡 (1个)", "c": 33.0, "p": 26.0, "f": 23.0},
    "rice_100g": {"name": "熟米饭 (100g)", "c": 26.0, "p": 2.6, "f": 0.3},
}


def kcal(c: float, p: float, f: float) -> float:
    return 4.0 * c + 4.0 * p + 9.0 * f


def main():
    parser = argparse.ArgumentParser(description="谭成义饮食体系宏量与缺口计算器")
    parser.add_argument("--weight", type=float, default=82.0, help="当前体重 kg (默认: 82.0)")
    parser.add_argument("--sex", choices=["male", "female"], default="male", help="性别系数选择 (默认: male)")
    parser.add_argument("--hours", choices=["2-3", "4-5", "6-7", "8-9"], help="按谭师白板每周运动时长计算")
    parser.add_argument("--day", type=str, help="按82kg专属周日程计算 (默认自动取今天星期几; 可传 周一~周日 或 mon~sun)")
    parser.add_argument("--no-profile", action="store_true", help="不扣除个人每日固定基底（玉米/鸡蛋/特仑苏/无糖阿萨姆/2勺蛋白粉）")
    parser.add_argument("--preset", action="append", default=[], help=f"今日已吃的预设餐品，可多次指定: {', '.join(FOOD_PRESETS.keys())}")
    parser.add_argument("--eaten", type=str, help="手动指定额外已吃的宏量营养素 '碳水,蛋白,脂肪' (如 '80,26,22')")
    parser.add_argument("--json", action="store_true", help="以 JSON 格式输出")
    args = parser.parse_args()

    # 1. 计算目标（若未传 --hours 且体重为默认 82kg，自动按 --day 或当天星期几匹配 82kg 分日目标）
    day_str = args.day
    if not day_str and not args.hours and abs(args.weight - 82.0) < 0.1:
        weekday_idx = datetime.datetime.now().weekday()  # 0=Mon .. 6=Sun
        day_str = WEEKDAY_NAMES_ZH[weekday_idx]

    if day_str and day_str.lower() in DAY_TO_MODE and abs(args.weight - 82.0) < 0.1:
        mode = DAY_TO_MODE[day_str.lower()]
        t = USER_82KG_DAY_TARGETS[mode]
        target_c, target_p, target_f = t["c"], t["p"], t["f"]
        target_label = f"[{day_str}] {t['label']}"
    else:
        hours = args.hours or "4-5"
        c_coef, p_coef, f_coef = WHITEBOARD_MATRIX[args.sex][hours]
        target_c = round(args.weight * c_coef, 1)
        target_p = round(args.weight * p_coef, 1)
        target_f = round(args.weight * f_coef, 1)
        target_label = f"谭成义白板公式 ({args.weight}kg | {args.sex} | 每周运动 {hours}h: 碳水{c_coef}/蛋白{p_coef}/脂肪{f_coef})"

    target_kcal = round(kcal(target_c, target_p, target_f))

    # 2. 统计已摄入
    eaten_items = []
    if not args.no_profile:
        eaten_items.extend(USER_BASE_ITEMS)

    for p_key in args.preset:
        if p_key in FOOD_PRESETS:
            eaten_items.append(FOOD_PRESETS[p_key])
        else:
            print(f"警告: 未知预设 '{p_key}'，可选值: {', '.join(FOOD_PRESETS.keys())}", file=sys.stderr)

    if args.eaten:
        parts = [float(x.strip()) for x in args.eaten.split(",")]
        if len(parts) == 3:
            eaten_items.append({"name": "手动录入已吃餐食", "c": parts[0], "p": parts[1], "f": parts[2]})

    eaten_c = round(sum(i["c"] for i in eaten_items), 1)
    eaten_p = round(sum(i["p"] for i in eaten_items), 1)
    eaten_f = round(sum(i["f"] for i in eaten_items), 1)
    eaten_kcal = round(kcal(eaten_c, eaten_p, eaten_f))

    rem_c = round(target_c - eaten_c, 1)
    rem_p = round(target_p - eaten_p, 1)
    rem_f = round(target_f - eaten_f, 1)
    rem_kcal = round(target_kcal - eaten_kcal)

    # 3. 食材折算建议
    rice_equiv_g = max(0, round(rem_c / 0.26))
    potato_equiv_g = max(0, round(rem_c / 0.22))
    meat_equiv_g = max(0, round(rem_p / 0.22))
    after_curry_rem_c = max(0.0, rem_c - 60.0)
    after_curry_rice_g = round(after_curry_rem_c / 0.26)

    result = {
        "target": {"label": target_label, "c": target_c, "p": target_p, "f": target_f, "kcal": target_kcal},
        "eaten": {"items": eaten_items, "c": eaten_c, "p": eaten_p, "f": eaten_f, "kcal": eaten_kcal},
        "remaining": {"c": rem_c, "p": rem_p, "f": rem_f, "kcal": rem_kcal},
        "conversions": {
            "pure_cooked_rice_g": rice_equiv_g,
            "pure_sweet_potato_g": potato_equiv_g,
            "raw_lean_meat_g": meat_equiv_g,
            "if_eat_1_curry_dal_need_cooked_rice_g": after_curry_rice_g,
        },
    }

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    print(f"=== 🎯 今日营养目标：{target_label} ===")
    print(f"目标总量：碳水 {target_c}g | 蛋白质 {target_p}g | 脂肪 {target_f}g | 热量约 {target_kcal} kcal\n")

    print("=== 🍽️ 已计入饮食基底与餐食 ===")
    if not eaten_items:
        print("  (无)")
    for item in eaten_items:
        print(f"  - {item['name']}: 碳水 {item['c']}g | 蛋白 {item['p']}g | 脂肪 {item['f']}g")
    print(f"已吃小计：碳水 {eaten_c}g | 蛋白质 {eaten_p}g | 脂肪 {eaten_f}g | 热量约 {eaten_kcal} kcal\n")

    print("=== 📊 剩余营养素缺口 ===")
    print(f"还需摄入：碳水 {rem_c:+.1f}g | 蛋白质 {rem_p:+.1f}g | 脂肪 {rem_f:+.1f}g | 剩余热量约 {rem_kcal:+d} kcal\n")

    print("=== ⚖️ 剩余缺口食材折算参考 ===")
    if rem_c > 0 or rem_p > 0:
        print(f"  • 【常规外食/家常折算】：约需 熟米饭 {rice_equiv_g}g (或红薯/土豆 {potato_equiv_g}g) + 生重瘦肉/去皮禽肉/鱼虾 {meat_equiv_g}g")
        print(f"  • 【自制咖喱红扁豆炖鸡腿模式】：若吃 1 标准份炖菜 (含60g碳水+59g蛋白)，还需额外配 熟米饭约 {after_curry_rice_g}g")
    else:
        print("  • 今日碳水与蛋白质目标均已达成！")


if __name__ == "__main__":
    main()
