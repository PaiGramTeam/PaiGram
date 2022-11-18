from __future__ import annotations

import functools

from metadata.genshin import WEAPON_DATA

__all__ = ["roles", "weapons", "roleToId", "roleToName", "weaponToName", "weaponToId", "not_real_roles"]

# noinspection SpellCheckingInspection
roles = {
    20000000: ["主角", "旅行者", "卑鄙的外乡人", "荣誉骑士", "爷", "风主", "岩主", "雷主", "草主", "履刑者", "抽卡不歪真君"],
    10000002: ["神里绫华", "Ayaka", "ayaka", "Kamisato Ayaka", "神里", "绫华", "神里凌华", "凌华", "白鹭公主", "神里大小姐"],
    10000003: ["琴", "Jean", "jean", "团长", "代理团长", "琴团长", "蒲公英骑士"],
    10000005: ["空", "Aether", "aether", "男主", "男主角", "龙哥", "空哥"],
    10000006: ["丽莎", "Lisa", "lisa", "图书管理员", "图书馆管理员", "蔷薇魔女"],
    10000007: ["荧", "Lumine", "lumine", "女主", "女主角", "莹", "萤", "黄毛阿姨", "荧妹"],
    10000014: ["芭芭拉", "Barbara", "barbara", "巴巴拉", "拉粑粑", "拉巴巴", "内鬼", "加湿器", "闪耀偶像", "偶像"],
    10000015: ["凯亚", "Kaeya", "kaeya", "盖亚", "凯子哥", "凯鸭", "矿工", "矿工头子", "骑兵队长", "凯子", "凝冰渡海真君"],
    10000016: [
        "迪卢克",
        "Diluc",
        "diluc",
        "卢姥爷",
        "姥爷",
        "卢老爷",
        "卢锅巴",
        "正义人",
        "正e人",
        "正E人",
        "卢本伟",
        "暗夜英雄",
        "卢卢伯爵",
        "落魄了",
        "落魄了家人们",
    ],
    10000020: ["雷泽", "Razor", "razor", "狼少年", "狼崽子", "狼崽", "卢皮卡", "小狼", "小狼狗"],
    10000021: ["安柏", "Amber", "amber", "安伯", "兔兔伯爵", "飞行冠军", "侦查骑士", "点火姬", "点火机", "打火机", "打火姬"],
    10000022: [
        "温迪",
        "Venti",
        "venti",
        "温蒂",
        "风神",
        "卖唱的",
        "巴巴托斯",
        "巴巴脱丝",
        "芭芭托斯",
        "芭芭脱丝",
        "干点正事",
        "不干正事",
        "吟游诗人",
        "诶嘿",
        "唉嘿",
        "摸鱼",
    ],
    10000023: ["香菱", "Xiangling", "xiangling", "香玲", "锅巴", "厨师", "万民堂厨师", "香师傅"],
    10000024: ["北斗", "Beidou", "beidou", "大姐头", "大姐", "无冕的龙王", "龙王"],
    10000025: ["行秋", "Xingqiu", "xingqiu", "秋秋人", "秋妹妹", "书呆子", "水神", "飞云商会二少爷"],
    10000026: [
        "魈",
        "Xiao",
        "xiao",
        "杏仁豆腐",
        "打桩机",
        "插秧",
        "三眼五显仙人",
        "三眼五显真人",
        "降魔大圣",
        "护法夜叉",
        "快乐风男",
        "无聊",
        "靖妖傩舞",
        "矮子仙人",
        "三点五尺仙人",
        "跳跳虎",
    ],
    10000027: ["凝光", "Ningguang", "ningguang", "富婆", "天权星"],
    10000029: [
        "可莉",
        "Klee",
        "klee",
        "嘟嘟可",
        "火花骑士",
        "蹦蹦炸弹",
        "炸鱼",
        "放火烧山",
        "放火烧山真君",
        "蒙德最强战力",
        "逃跑的太阳",
        "啦啦啦",
        "哒哒哒",
        "炸弹人",
        "禁闭室",
    ],
    10000030: ["钟离", "Zhongli", "zhongli", "摩拉克斯", "岩王爷", "岩神", "钟师傅", "天动万象", "岩王帝君", "未来可期", "帝君", "拒收病婿"],
    10000031: ["菲谢尔", "Fischl", "fischl", "皇女", "小艾米", "小艾咪", "奥兹", "断罪皇女", "中二病", "中二少女", "中二皇女", "奥兹发射器"],
    10000032: ["班尼特", "Bennett", "bennett", "点赞哥", "点赞", "倒霉少年", "倒霉蛋", "霹雳闪雷真君", "班神", "班爷", "倒霉", "火神", "六星真神"],
    10000033: [
        "达达利亚",
        "Tartaglia",
        "tartaglia",
        "Childe",
        "childe",
        "Ajax",
        "ajax",
        "达达鸭",
        "达达利鸭",
        "公子",
        "玩具销售员",
        "玩具推销员",
        "钱包",
        "鸭鸭",
        "愚人众末席",
    ],
    10000034: ["诺艾尔", "Noelle", "noelle", "女仆", "高达", "岩王帝姬"],
    10000035: ["七七", "Qiqi", "qiqi", "僵尸", "肚饿真君", "度厄真君", "77"],
    10000036: ["重云", "Chongyun", "chongyun", "纯阳之体", "冰棍"],
    10000037: ["甘雨", "Ganyu", "ganyu", "椰羊", "椰奶", "王小美"],
    10000038: [
        "阿贝多",
        "Albedo",
        "albedo",
        "可莉哥哥",
        "升降机",
        "升降台",
        "电梯",
        "白垩之子",
        "贝爷",
        "白垩",
        "阿贝少",
        "花呗多",
        "阿贝夕",
        "abd",
        "阿师傅",
    ],
    10000039: ["迪奥娜", "Diona", "diona", "迪欧娜", "dio", "dio娜", "冰猫", "猫猫", "猫娘", "喵喵", "调酒师"],
    10000041: [
        "莫娜",
        "Mona",
        "mona",
        "穷鬼",
        "穷光蛋",
        "穷",
        "莫纳",
        "占星术士",
        "占星师",
        "讨龙真君",
        "半部讨龙真君",
        "阿斯托洛吉斯·莫娜·梅姬斯图斯",
        "梅姬斯图斯",
        "梅姬斯图斯卿",
    ],
    10000042: [
        "刻晴",
        "Keqing",
        "keqing",
        "刻情",
        "氪晴",
        "刻师傅",
        "刻师父",
        "牛杂",
        "牛杂师傅",
        "斩尽牛杂",
        "免疫",
        "免疫免疫",
        "屁斜剑法",
        "玉衡星",
        "阿晴",
        " 啊晴",
    ],
    10000043: ["砂糖", "Sucrose", "sucrose", "雷莹术士", "雷萤术士", "雷荧术士"],
    10000044: ["辛焱", "Xinyan", "xinyan", "辛炎", "黑妹", "摇滚"],
    10000045: [
        "罗莎莉亚",
        "Rosaria",
        "rosaria",
        "罗莎莉娅",
        "白色史莱姆",
        "白史莱姆",
        "修女",
        "罗莎利亚",
        "罗莎利娅",
        "罗沙莉亚",
        "罗沙莉娅",
        "罗沙利亚",
        "罗沙利娅",
        "萝莎莉亚",
        "萝莎莉娅",
        "萝莎利亚",
        "萝莎利娅",
        "萝沙莉亚",
        "萝沙莉娅",
        "萝沙利亚",
        "萝沙利娅",
    ],
    10000046: [
        "胡桃",
        "HuTao",
        "hutao",
        "Hu Tao",
        "hu tao",
        "Hutao",
        "胡 淘",
        "往生堂堂主",
        "火化",
        "抬棺的",
        "蝴蝶",
        "核桃",
        "堂主",
        "胡堂主",
        "雪霁梅香",
    ],
    10000047: ["枫原万叶", "Kazuha", "kazuha", "Kaedehara Kazuha", "万叶", "叶天帝", "天帝", "叶师傅"],
    10000048: ["烟绯", "Yanfei", "yanfei", "烟老师", "律师", "罗翔"],
    10000049: ["宵宫", "Yoimiya", "yoimiya", "霄宫", "烟花", "肖宫", "肖工", "绷带女孩"],
    10000050: ["托马", "Thoma", "thoma", "家政官", "太郎丸", "地头蛇", "男仆", "拖马"],
    10000051: ["优菈", "Eula", "eula", "优拉", "尤拉", "尤菈", "浪花骑士", "记仇", "劳伦斯"],
    10000052: [
        "雷电将军",
        "Shougun",
        "Raiden Shogun",
        "Raiden",
        "raiden",
        "雷神",
        "将军",
        "雷军",
        "巴尔",
        "阿影",
        "影",
        "巴尔泽布",
        "煮饭婆",
        "奶香一刀",
        "无想一刀",
        "宅女",
    ],
    10000053: ["早柚", "Sayu", "sayu", "小狸猫", "狸 猫", "忍者"],
    10000054: ["珊瑚宫心海", "Kokomi", "kokomi", "Sangonomiya Kokomi", "心海", "军师", "珊瑚宫", "书记", "观赏鱼", "水母", "鱼", "美人鱼"],
    10000055: ["五郎", "Gorou", "gorou", "柴犬", "土狗", "希娜", "希娜小姐"],
    10000056: ["九条裟罗", "Sara", "sara", "Kujou Sara", "九条", "九条沙罗", "裟罗", "沙罗", "天狗"],
    10000057: [
        "荒泷一斗",
        "Itto",
        "itto",
        "Arataki Itto",
        "荒龙一斗",
        "荒泷天下第一斗",
        "一斗",
        "一抖",
        "荒泷",
        "1斗",
        "牛牛",
        "斗子哥",
        "牛子哥",
        "牛子",
        "孩子王",
        "斗虫",
        "巧乐兹",
        "放牛的",
    ],
    10000058: ["八重神子", "Miko", "miko", "Yae Miko", "八重", "神子", "狐狸", "想得美哦", "巫女", "屑狐狸", "骚狐狸", "八重宫司", "婶子", "小八"],
    10000059: ["鹿野院平藏", "Heizou", "heizou", "shikanoin heizou", "heizo", "鹿野苑", "鹿野院", "平藏", "鹿野苑平藏", "鹿野", "小鹿"],
    10000060: ["夜兰", "Yelan", "yelan", "夜阑", "叶 澜", "腋兰", "夜天后"],
    10000062: ["埃洛伊", "Aloy", "aloy"],
    10000063: ["申鹤", "Shenhe", "shenhe", "神鹤", "小姨", "小姨子", "审鹤"],
    10000064: ["云堇", "YunJin", "yunjin", "Yun Jin", "yun jin", "云瑾", "云先生", "云锦", "神女劈观"],
    10000065: ["久岐忍", "Kuki", "kuki", "Kuki Shinobu", "Shinobu", "shinobu", "97忍", "小忍", "久歧忍", "97", "茄忍", "阿忍", "忍姐"],
    10000066: ["神里绫人", "Ayato", "ayato", "Kamisato Ayato", "绫人", "神里凌人", "凌人", "0人", "神人", "零人", "大舅哥"],
    10000067: ["柯莱", "Collei", "collei", "柯来", "科莱", "科来", "小天使", "须弥安柏", "须弥飞行冠军", "见习巡林员", "克莱", "草安伯"],
    10000068: ["多莉", "Dori", "dori", "多利", "多力", "多丽", "奸商"],
    10000069: ["提纳里", "Tighnari", "tighnari", "小提", "提那里", "缇娜里", "提哪里", "驴", "柯莱老师", "柯莱师傅", "巡林官", "提那里"],
    10000070: ["妮露", "Nilou", "nilou", "尼露", "尼禄"],
    10000071: ["赛诺", "Cyno", "cyno", "赛洛"],
    10000072: ["坎蒂丝", "Candace", "candace", "坎迪斯"],
    10000073: ["纳西妲", "Nahida", "nahida", "草王", "草神", "小吉祥草王", "草萝莉", "纳西坦"],
    10000074: ["莱依拉", "Layla", "layla", "拉一拉", "莱伊拉"],
    10000075: ["流浪者", "Wanderer", "散兵", "伞兵", "国崩", "卢本伟", "大炮", "sb"],
}
not_real_roles = [10000075]
weapons = {
    "磐岩结绿": ["绿箭", "绿剑"],
    "斫峰之刃": ["斫峰", "盾剑"],
    "无工之剑": ["蜈蚣", "蜈蚣大剑", "无工大剑", "盾大剑", "无工"],
    "贯虹之槊": ["贯虹", "岩枪", "盾枪", "钟离专武"],
    "赤角石溃杵": ["赤角", "石溃杵", "荒泷一斗专武"],
    "尘世之锁": ["尘世锁", "尘世", "盾书", "锁"],
    "终末嗟叹之诗": ["终末", "终末弓", "叹气弓", "乐团弓", "温迪专武"],
    "松籁响起之时": ["松籁", "乐团大剑", "松剑", "优菈专武"],
    "苍古自由之誓": ["苍古", "乐团剑", "枫原万叶专武"],
    "「渔获」": ["鱼叉", "渔叉", "渔获"],
    "衔珠海皇": ["海皇", "咸鱼剑", "咸鱼大剑"],
    "匣里日月": ["日月"],
    "匣里灭辰": ["灭辰"],
    "匣里龙吟": ["龙吟"],
    "天空之翼": ["天空弓"],
    "天空之刃": ["天空剑"],
    "天空之卷": ["天空书", "厕纸"],
    "天空之脊": ["天空枪", "薄荷枪"],
    "天空之傲": ["天空大剑"],
    "四风原典": ["四风", "可莉专武"],
    "试作斩岩": ["斩岩"],
    "试作星镰": ["星镰"],
    "试作金珀": ["金珀"],
    "试作古华": ["古华"],
    "试作澹月": ["澹月"],
    "千岩长枪": ["千岩枪"],
    "千岩古剑": ["千岩剑", "千岩大剑"],
    "暗巷闪光": ["暗巷剑"],
    "暗巷猎手": ["暗巷弓"],
    "阿莫斯之弓": ["阿莫斯", "ams", "痛苦弓", "甘雨专武"],
    "雾切之回光": ["雾切", "神里绫华专武"],
    "飞雷之弦振": ["飞雷", "飞雷弓", "宵宫专武"],
    "薙草之稻光": ["薙草", "稻光", "薙草稻光", "马尾枪", "马尾", "薙刀", "雷电将军专武"],
    "神乐之真意": ["神乐", "真意", "八重神子专武"],
    "狼的末路": ["狼末"],
    "护摩之杖": ["护摩", "护摩枪", "护膜", "胡桃专武"],
    "和璞鸢": ["鸟枪", "绿枪", "魈专武"],
    "风鹰剑": ["风鹰"],
    "冬极白星": ["冬极", "达达利亚专武"],
    "不灭月华": ["月华", "珊瑚宫心海专武"],
    "波乱月白经津": ["波乱", "月白", "波乱月白", "经津", "波波津", "神里绫人专武"],
    "若水": ["麒麟弓", "夜兰专武"],
    "昭心": ["糟心"],
    "幽夜华尔兹": ["幽夜", "幽夜弓", "华尔兹", "皇女弓"],
    "雪葬的星银": ["雪葬", "星银", "雪葬星银", "雪山大剑"],
    "喜多院十文字": ["喜多院", "十文字"],
    "万国诸海图谱": ["万国", "万国诸海"],
    "天目影打刀": ["天目刀", "天目"],
    "破魔之弓": ["破魔弓"],
    "曚云之月": ["曚云弓"],
    "流月针": ["针"],
    "流浪乐章": ["赌狗书", "赌狗乐章", "赌狗"],
    "桂木斩长正": ["桂木", "斩长正"],
    "腐殖之剑": ["腐殖", "腐殖剑"],
    "风花之颂": ["风花弓"],
    "证誓之明瞳": ["证誓", "明瞳", "证誓明瞳"],
    "嘟嘟可故事集": ["嘟嘟可"],
    "辰砂之纺锤": ["辰砂", "辰砂纺锤", "纺锤", "阿贝多专武"],
    "白辰之环": ["白辰", "白辰环"],
    "决斗之枪": ["决斗枪", "决斗", "月卡枪"],
    "螭骨剑": ["螭骨", "丈育剑", "离骨剑", "月卡大剑"],
    "黑剑": ["月卡剑"],
    "苍翠猎弓": ["绿弓", "月卡弓"],
    "讨龙英杰谭": ["讨龙"],
    "神射手之誓": ["脚气弓", "神射手"],
    "黑缨枪": ["史莱姆枪"],
    "黑岩刺枪": ["黑岩枪"],
    "黑岩战弓": ["黑岩弓"],
    "笼钓瓶一心": ["万叶刀", "一心传名刀"],
    "猎人之径": ["绿弓", "草弓", "提纳里专武"],
    "竭泽": ["鱼弓"],
    "王下近侍": ["须弥锻造弓"],
    "贯月矢": ["须弥锻造长枪"],
    "盈满之实": ["须弥锻造法器"],
    "森林王器": ["须弥锻造大剑"],
    "原木刀": ["须弥锻造单手剑"],
    "圣显之钥": ["圣显之钥", "圣显", "不灭剑华", "妮露专武"],
    "西福斯的月光": ["西福斯", "月光"],
    "赤沙之杖": ["赤沙", "赛诺专武"],
    "风信之锋": ["风信", "风信锋"],
    "玛海菈的水色": ["玛海菈", "水色"],
    "千夜浮梦": ["千夜", "神灯", "茶壶", "夜壶"],
    "流浪的晚星": ["晚星"],
    "息灾": ["申鹤专武"],
}


# noinspection PyPep8Naming
@functools.lru_cache()
def roleToName(shortname: str) -> str:
    """将角色昵称转为正式名"""
    return next((value[0] for value in roles.values() for name in value if name == shortname), shortname)


# noinspection PyPep8Naming
@functools.lru_cache()
def roleToId(name: str) -> int | None:
    """获取角色ID"""
    return next((key for key, value in roles.items() for n in value if n == name), None)


# noinspection PyPep8Naming
@functools.lru_cache()
def weaponToName(shortname: str) -> str:
    """将武器昵称转为正式名"""
    return next((key for key, value in weapons.items() if shortname == key or shortname in value), shortname)


# noinspection PyPep8Naming
@functools.lru_cache()
def weaponToId(name: str) -> int | None:
    """获取武器ID"""
    return next((int(key) for key, value in WEAPON_DATA.items() if weaponToName(name) in value["name"]), None)
