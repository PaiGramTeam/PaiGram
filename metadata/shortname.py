from __future__ import annotations

import functools
from typing import List

from metadata.genshin import WEAPON_DATA

__all__ = [
    "roles",
    "weapons",
    "idToName",
    "roleToId",
    "roleToName",
    "weaponToName",
    "weaponToId",
    "elementToName",
    "elementsToColor",
    "not_real_roles",
    "roleToTag",
]

# noinspection SpellCheckingInspection
roles = {
    20000000: [
        "旅行者",
        "主角",
        "卑鄙的外乡人",
        "荣誉骑士",
        "爷",
        "履刑者",
        "人之子",
        "命定之人",
        "荣誉骑士",
        "小可爱",  # 丽莎
        "小家伙",  # 八重神子
        "金发异乡人",
        "大黄金钓鱼手",  # 派蒙
        "黄毛阿姨",
        "黄毛叔叔",
        "大黄倭瓜那菈",
    ],
    10000002: ["神里绫华", "ayaka", "kamisato ayaka", "神里", "绫华", "神里凌华", "凌华", "白鹭公主", "神里大小姐", "冰骗骗花", "龟龟"],
    10000003: ["琴", "jean", "团长", "代理团长", "琴团长", "蒲公英骑士", "蒙德砍王", "骑士团的魂"],
    10000005: ["空", "aether", "男主", "男主角", "龙哥", "空哥", "王子"],
    10000006: ["丽莎", "lisa", "图书管理员", "图书馆管理员", "蔷薇魔女"],
    10000007: ["荧", "lumine", "女主", "女主角", "莹", "萤", "黄毛阿姨", "荧妹", "公主殿下"],
    10000014: ["芭芭拉", "barbara", "巴巴拉", "拉粑粑", "拉巴巴", "内鬼", "加湿器", "闪耀偶像", "偶像", "蒙德辣王"],
    10000015: ["凯亚", "kaeya", "盖亚", "凯子哥", "凯鸭", "矿工", "矿工头子", "骑兵队长", "凯子", "凝冰渡海真君", "花脸猫"],
    10000016: [
        "迪卢克",
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
        "哦哦哦",
        "前夫哥",
        "在此烧鸟真君",
        "E键三连真君",
    ],
    10000020: [
        "雷泽",
        "razor",
        "狼少年",
        "狼崽子",
        "狼崽",
        "卢皮卡",
        "小狼",
        "小狼狼",
        "小狼狗",
        "小赛诺",
        "替身使者",
        "须佐狼乎",
        "蒙德砍王",
        "炸矿之星",
    ],
    10000021: [
        "安柏",
        "amber",
        "安伯",
        "兔兔伯爵",
        "飞行冠军",
        "侦查骑士",
        "侦察骑士",
        "点火姬",
        "点火机",
        "打火机",
        "打火姬",
        "燃炬焚棘真君",
        "初代目提瓦特第一火弓",
    ],
    10000022: [
        "温迪",
        "venti",
        "barbatos",
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
        "最弱最丢人的七神",
        "卖唱的大哥哥",
        "巴巴托斯大人",
        "欸嘿聚怪真君",
        "荻花洲的吹笛人",
        "直升机",
    ],
    10000023: [
        "香菱",
        "xiangling",
        "香玲",
        "锅巴",
        "厨师",
        "万民堂厨师",
        "香师傅",
        "哪吒",
        "锅巴发射器",
        "无敌风火轮真君",
        "舌尖上的璃月",
        "提瓦特枪王",
    ],
    10000024: ["北斗", "beidou", "大姐头", "大姐", "无冕的龙王", "稻妻人形继电石"],
    10000025: ["行秋", "xingqiu", "秋秋人", "秋妹妹", "书呆子", "飞云商会二少爷", "秋秋人", "6星水神", "枕玉老师"],
    10000026: [
        "魈",
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
        "护法夜叉大将",
        "金鹏大将",
        "这里无能真君",
        "抬头不见低头见真君",
        "跳跳虎",
        "随叫随到真君",
        "成天冷着脸的帅气小哥",
    ],
    10000027: ["凝光", "ningguang", "富婆", "天权", "天权星", "寻山见矿真君"],
    10000029: [
        "可莉",
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
        "艾莉丝的女儿",
        "阿贝多的义妹",
        "火化骑士",
        "炸鱼禁闭真君",
        "蒙德小坦克",
        "骑士团团宠",
    ],
    10000030: [
        "钟离",
        "zhongli",
        "morax",
        "摩拉克斯",
        "岩王爷",
        "岩神",
        "钟师傅",
        "天动万象",
        "岩王帝君",
        "未来可期",
        "帝君",
        "契约之神",
        "社会废人",
        "未来可期真君",
        "废人养成器",
        "听书人",
    ],
    10000031: ["菲谢尔", "fischl", "皇女", "小艾米", "小艾咪", "奥兹", "断罪皇女", "中二病", "中二少女", "中二皇女", "奥兹发射器"],
    10000032: ["班尼特", "bennett", "点赞哥", "点赞", "倒霉少年", "倒霉蛋", "霹雳闪雷真君", "班神", "班爷", "倒霉", "火神", "六星真神"],
    10000033: [
        "达达利亚",
        "tartaglia",
        "childe",
        "ajax",
        "达达鸭",
        "达达利鸭",
        "公子",
        "玩具销售员",
        "玩具推销员",
        "钱包",
        "鸭鸭",
        "愚人众末席",
        "至冬国驻璃月港玩具推销员主管",
        "钟离的钱包",
        "近战弓兵",
        "在蒙德认识的冒险家",
        "永别冬都",
        "汤达人",
        "大貉妖处理专家",
    ],
    10000034: ["诺艾尔", "noelle", "女仆", "高达", "岩王帝姬", "山吹", "冰萤术士", "岩王帝姬"],
    10000035: ["七七", "qiqi", "僵尸", "肚饿真君", "度厄真君", "77", "起死回骸童子", "救苦度厄真君", "椰羊创始人", "不卜庐砍王", "不卜庐剑圣"],
    10000036: ["重云", "chongyun", "纯阳之体", "冰棍", "驱邪世家", "大外甥"],
    10000037: ["甘雨", "ganyu", "椰羊", "椰奶", "鸡腿猎人", "咕噜咕噜滚下山真君", "肝雨", "走路上山真君"],
    10000038: [
        "阿贝多",
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
        "小王子",
        "调查小队队长",
        "西风骑士团首席炼金术师",
        "白垩老师",
        "电梯人",
        "蒙德岩神",
        "平平无奇",
        "蒙德NPC",
    ],
    10000039: ["迪奥娜", "diona", "迪欧娜", "dio", "dio娜", "冰猫", "猫猫", "猫娘", "喵喵", "调酒师"],
    10000041: [
        "莫娜",
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
        "astrologist mona megistus",
        "梅姬斯图斯",
        "梅姬斯图斯卿",
        "梅姬",
        "半部讨龙真君",
    ],
    10000042: [
        "刻晴",
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
        "啊晴",
        "得不到的女人",
        "金丝虾球真君",
        "璃月雷神",
        "刻猫猫",
    ],
    10000043: ["砂糖", "sucrose", "雷莹术士", "雷萤术士", "雷荧术士"],
    10000044: ["辛焱", "xinyan", "辛炎", "黑妹", "摇滚"],
    10000045: [
        "罗莎莉亚",
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
        "hutao",
        "hu tao",
        "胡淘",
        "往生堂堂主",
        "火化",
        "抬棺的",
        "蝴蝶",
        "核桃",
        "堂主",
        "胡堂主",
        "雪霁梅香",
        "赤团开时",
        "黑无常",
        "嘘嘘鬼王",
        "琪亚娜",
        "薪炎之律者",
    ],
    10000047: ["枫原万叶", "kazuha", "kaedehara kazuha", "万叶", "叶天帝", "天帝", "人型气象观测台", "浪人武士"],
    10000048: ["烟绯", "yanfei", "烟老师", "律师", "罗翔", "璃月港的知名律法咨询师", "璃月罗翔", "铁人三项真君"],
    10000049: [
        "宵宫",
        "yoimiya",
        "霄宫",
        "烟花",
        "肖宫",
        "肖工",
        "绷带女孩",
        "夏祭的女王",
        "地对鸽导弹",
        "打火姬二代目",
        "长野原加特林",
        "花见坂军火商",
    ],
    10000050: ["托马", "thoma", "家政官", "太郎丸", "地头蛇", "男仆", "男妈妈"],
    10000051: ["优菈", "eula", "优拉", "尤拉", "尤菈", "浪花骑士", "记仇", "喷嚏记仇真君"],
    10000052: [
        "雷电将军",
        "shougun",
        "raiden shogun",
        "raiden",
        "ei",
        "raiden ei",
        "baal",
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
        "大御所大人",
        "鸣神",
        "永恒之神",
        "姐控",
        "不会做饭真君",
        "宅女程序员",
        "奶香一刀真君",
        "雷电芽衣",
        "又哭又闹真君",
        "御建鸣神主尊大御所大人",
    ],
    10000053: ["早柚", "sayu", "小狸猫", "狸猫", "咕噜咕噜赶路真君", "柚岩龙蜥", "善于潜行的矮子", "专业人士"],
    10000054: [
        "珊瑚宫心海",
        "kokomi",
        "sangonomiya kokomi",
        "心海",
        "我心",
        "你心",
        "军师",
        "珊瑚宫",
        "书记",
        "观赏鱼",
        "水母",
        "鱼",
        "现人神巫女",
        "宅家派节能军师",
        "藤原千花",
        "能量管理大师",
        "五星观赏鱼",
        "海天后",
        "深海舌鲆鱼小姐",
    ],
    10000055: ["五郎", "gorou", "柴犬", "土狗", "希娜", "希娜小姐", "海祇岛的小狗大将", "修勾", "五郎大将的朋友", "小狗勾"],
    10000056: [
        "九条裟罗",
        "sara",
        "kujou sara",
        "九条",
        "九条沙罗",
        "裟罗",
        "天狗",
        "条家的养子",
        "雷系班尼特",
        "雷神单推头子",
        "珊瑚宫心海的冤家",
        "荒泷一斗的冤家",
        "外置暴伤",
        "维密天使",
    ],
    10000057: [
        "荒泷一斗",
        "itto",
        "arataki itto",
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
        "岩丘丘萨满",
        "伐伐伐伐伐木工",
        "希娜小姐的榜一大哥",
    ],
    10000058: [
        "八重神子",
        "miko",
        "yae miko",
        "八重",
        "神子",
        "狐狸",
        "想得美哦",
        "巫女",
        "屑狐狸",
        "骚狐狸",
        "八重宫司",
        "婶子",
        "小八",
        "白辰血脉的后裔",
        "兼具智慧和美貌的八重神子大人",
        "稻妻老八",
        "雷丘丘萨满",
        "八重樱",
        "嗑瓜子",
        "小奥兹",
        "玲珑油豆腐小姐",
    ],
    10000059: [
        "鹿野院平藏",
        "heizou",
        "shikanoin heizou",
        "heizo",
        "鹿野苑",
        "鹿野院",
        "平藏",
        "鹿野苑平藏",
        "鹿野",
        "小鹿",
        "天领奉行侦探",
        "鹿野奈奈的表弟",
        "风拳前锋军",
        "拳师",
        "名侦探柯南",
        "捕快展昭",
    ],
    10000060: ["夜兰", "yelan", "夜阑", "叶澜", "腋兰", "夜天后", "自称就职于总务司的神秘人士", "岩上茶室老板", "夜上海", "胸怀大痣"],
    10000061: ["绮良良", "kirara", "稻妻猫猫", "猫猫快递"],
    10000062: ["埃洛伊", "aloy", "异界的救世主"],
    10000063: ["申鹤", "shenhe", "神鹤", "小姨", "阿鹤", "小姨子", "审鹤", "仙家弟子", "驱邪世家旁", "药材杀手"],
    10000064: ["云堇", "yunjin", "yun jin", "云瑾", "云先生", "云锦", "神女劈观", "岩北斗", "五更琉璃"],
    10000065: [
        "久岐忍",
        "kuki",
        "kuki shinobu",
        "shinobu",
        "97忍",
        "小忍",
        "久歧忍",
        "97",
        "茄忍",
        "阿忍",
        "忍姐",
        "鬼之副手",
        "不是忍者的忍者",
        "医疗忍者",
        "考证专家",
    ],
    10000066: [
        "神里绫人",
        "ayato",
        "kamisato ayato",
        "绫人",
        "神里凌人",
        "凌人",
        "0人",
        "神人",
        "零人",
        "大舅哥",
        "神里绫华的兄长",
        "荒泷一斗的虫友",
        "奥托",
        "奥托·阿波卡利斯",
        "奥托主教",
        "藏镜仕男",
        "袖藏奶茶真君",
        "真正的甘雨",
        "可莉的爷爷",
    ],
    10000067: [
        "柯莱",
        "collei",
        "柯来",
        "科莱",
        "科来",
        "小天使",
        "须弥安柏",
        "须弥飞行冠军",
        "见习巡林员",
        "克莱",
        "草安伯",
        "道成林见习巡林员",
        "提纳里的学徒",
        "安柏的挚友",
        "兰那罗奶奶",
    ],
    10000068: ["多莉", "dori", "多利", "多力", "多丽", "奸商", "须弥百货商人", "桑歌玛哈巴依老爷", "艾尔卡萨扎莱宫之主"],
    10000069: [
        "提纳里",
        "tighnari",
        "小提",
        "提那里",
        "缇娜里",
        "提哪里",
        "驴",
        "柯莱老师",
        "柯莱师傅",
        "巡林官",
        "提那里",
        "耳朵很好摸",
        "道成林巡林官",
        "柯莱的师父",
    ],
    10000070: ["妮露", "nilou", "尼露", "祖拜尔剧场之星", "红牛"],
    10000071: ["赛诺", "cyno", "赛洛", "大风纪官", "大风机关", "胡狼头大人", "夹击妹抖", "游戏王", "冷笑话爱好者", "牌佬", "沙漠死神", "胡狼"],
    10000072: ["坎蒂丝", "candace", "坎迪斯", "水北斗", "赤王后裔", "阿如村守护者"],
    10000073: [
        "纳西妲",
        "nahida",
        "buer",
        "草王",
        "草神",
        "小吉祥草王",
        "草萝莉",
        "艹萝莉",
        "羽毛球",
        "布耶尔",
        "纳西坦",
        "摩诃善法大吉祥智慧主",
        "智慧之神",
        "草木之主",
        "草神大人",
    ],
    10000074: ["莱依拉", "layla", "拉一拉", "莱伊拉", "莫娜的同行", "西琳", "黑塔"],
    10000075: [
        "流浪者",
        "wanderer",
        "散兵",
        "伞兵",
        "伞兵一号",
        "雷电国崩",
        "国崩",
        "卢本伟",
        "雷电大炮",
        "雷大炮",
        "大炮",
        "sb",
        "斯卡拉姆齐",
        "倾奇者",
        "黑主",
        "崩崩小圆帽",
        "七叶寂照秘密主",
        "七彩阳光秘密主",
        "正机之神",
        "伪神",
        "阿帽",
    ],
    10000076: ["珐露珊", "faruzan", "法露珊", "珐妹", "初音", "初音未来", "miku", "发露姗", "发姐", "法姐", "百岁珊", "百岁山", "童姥", "知论派名宿"],
    10000077: ["瑶瑶", "yaoyao", "遥遥", "遥遥无期", "香菱师妹", "萝卜", "四星草奶"],
    10000078: ["艾尔海森", "alhaitham", "爱尔海森", "艾尔海参", "艾尔", "海森", "海参", "海神", "埃尔海森", "草刻晴", "书记官", "代理大贤者"],
    10000079: ["迪希雅", "dehya", "狮女", "狮子", "腕豪", "女拳"],
    10000080: ["米卡", "mika", "镜音连", "咪卡", "小米"],
    10000081: ["卡维", "kaveh", "夺少"],
    10000082: ["白术", "baizhuer", "白大夫", "草行秋"],
    10000083: ["琳妮特", "lynette", "登登", "锵锵", "林尼特"],
    10000084: ["林尼", "lyney", "大魔术师", "琳尼"],
    10000085: ["菲米尼", "freminet", "潜水员"],
    10000086: ["莱欧斯利", "wriothesley", "典狱长", "大狼狗", "莱欧斯利公爵", "公爵", "公爵大人"],
    10000087: ["那维莱特", "neuvillette", "水龙", "龙王", "水龙王", "那维", "大审判官"],
    10000088: ["夏洛蒂", "charlotte", "记者", "枫丹记者", "射命丸文", "大新闻", "弄个大新闻"],
    10000089: ["芙宁娜", "furina", "芙宁娜·德·枫丹", "芙芙", "水神", "芙宁娜大人", "芙宁娜女士", "众水的颂诗", "不休独舞", "众水、众方、众民与众律法的女王"],
    10000090: ["夏沃蕾", "chevreuse"],
    10000091: ["娜维娅", "navia", "黄豆姐"],
}
not_real_roles = []
weapons = {
    # 1.x
    "决斗之枪": ["决斗枪", "决斗", "月卡枪"],
    "螭骨剑": ["螭骨", "丈育剑", "离骨剑", "月卡大剑"],
    "黑剑": ["月卡剑"],
    "苍翠猎弓": ["绿弓", "月卡弓"],
    "匣里日月": ["日月"],
    "匣里灭辰": ["灭辰"],
    "匣里龙吟": ["龙吟"],
    "流月针": ["针"],
    "流浪乐章": ["赌狗书", "赌狗乐章", "赌狗"],
    "昭心": ["糟心"],
    "讨龙英杰谭": ["讨龙"],
    "神射手之誓": ["脚气弓", "神射手"],
    "黑缨枪": ["史莱姆枪"],
    "黑岩刺枪": ["黑岩枪"],
    "黑岩战弓": ["黑岩弓"],
    "天空之刃": ["天空剑"],
    "天空之傲": ["天空大剑"],
    "天空之脊": ["天空枪", "薄荷枪", "薄荷"],
    "天空之卷": ["天空书", "厕纸"],
    "天空之翼": ["天空弓"],
    "四风原典": ["四风", "可莉专武"],
    "阿莫斯之弓": ["阿莫斯", "ams", "痛苦弓", "甘雨专武"],
    "狼的末路": ["狼末"],
    "和璞鸢": ["鸟枪", "绿枪", "魈专武"],
    "风鹰剑": ["风鹰"],
    "试作斩岩": ["斩岩"],
    "试作星镰": ["星镰"],
    "试作金珀": ["金珀"],
    "试作古华": ["古华"],
    "试作澹月": ["澹月"],
    "万国诸海图谱": ["万国", "万国诸海"],
    "尘世之锁": ["尘世锁", "尘世", "盾书", "锁"],
    "无工之剑": ["蜈蚣", "蜈蚣大剑", "无工大剑", "盾大剑", "无工"],
    "贯虹之槊": ["贯虹", "岩枪", "盾枪", "钟离专武"],
    "斫峰之刃": ["斫峰", "盾剑"],
    "腐殖之剑": ["腐殖", "腐殖剑"],
    "雪葬的星银": ["雪葬", "星银", "雪葬星银", "雪山大剑"],
    "磐岩结绿": ["绿箭", "绿剑"],
    "护摩之杖": ["护摩", "护摩枪", "护膜", "胡桃专武"],
    "千岩长枪": ["千岩枪"],
    "千岩古剑": ["千岩剑", "千岩大剑"],
    "西风长枪": ["西风枪"],
    "西风猎弓": ["西风弓"],
    "西风秘典": ["西风书"],
    "暗巷闪光": ["暗巷剑", "暗巷小剑", "暗巷"],
    "暗巷猎手": ["暗巷弓"],
    "暗巷的酒与诗": ["暗巷法器", "暗巷书"],
    "风花之颂": ["风花弓"],
    "终末嗟叹之诗": ["终末", "终末弓", "叹气弓", "乐团弓", "温迪专武"],
    "松籁响起之时": ["松籁", "乐团大剑", "松剑", "优菈专武"],
    "苍古自由之誓": ["苍古", "乐团剑", "枫原万叶专武"],
    "幽夜华尔兹": ["幽夜", "幽夜弓", "华尔兹", "皇女弓"],
    "嘟嘟可故事集": ["嘟嘟可"],
    # 2.x
    "天目影打刀": ["天目刀", "天目"],
    "桂木斩长正": ["桂木", "斩长正"],
    "喜多院十文字": ["喜多院", "十文字"],
    "破魔之弓": ["破魔弓", "破魔"],
    "白辰之环": ["白辰", "白辰环"],
    "雾切之回光": ["雾切", "神里绫华专武"],
    "飞雷之弦振": ["飞雷", "飞雷弓", "宵宫专武"],
    "薙草之稻光": ["薙草", "稻光", "薙草稻光", "马尾枪", "马尾", "薙刀", "雷电将军专武"],
    "不灭月华": ["月华", "珊瑚宫心海专武"],
    "「渔获」": ["鱼叉", "渔叉", "渔获"],
    "衔珠海皇": ["海皇", "咸鱼剑", "咸鱼大剑"],
    "冬极白星": ["冬极", "达达利亚专武"],
    "曚云之月": ["曚云弓", "曚云"],
    "恶王丸": ["断浪大剑"],
    "断浪长鳍": ["断浪", "断浪长枪", "断浪枪"],
    "辰砂之纺锤": ["辰砂", "辰砂纺锤", "纺锤", "阿贝多专武"],
    "赤角石溃杵": ["赤角", "石溃杵", "荒泷一斗专武", "巧乐兹"],
    "息灾": ["申鹤专武"],
    "神乐之真意": ["神乐", "真意", "八重神子专武"],
    "证誓之明瞳": ["证誓", "明瞳", "证誓明瞳", "大贝壳"],
    "波乱月白经津": ["波乱", "月白", "波乱月白", "经津", "波波津", "神里绫人专武", "钵钵鸡"],
    "若水": ["麒麟弓", "夜兰专武"],
    "笼钓瓶一心": ["万叶刀", "一心传名刀", "妖刀"],
    # 3.x
    "猎人之径": ["草弓", "提纳里专武"],
    "竭泽": ["鱼弓"],
    "原木刀": ["须弥锻造单手剑"],
    "森林王器": ["须弥锻造大剑", "原木大剑"],
    "贯月矢": ["须弥锻造长枪", "原木枪"],
    "盈满之实": ["须弥锻造法器"],
    "王下近侍": ["须弥锻造弓", "原木弓"],
    "赤沙之杖": ["赤沙", "赛诺专武", "船桨", "洛阳铲"],
    "圣显之钥": ["圣显之钥", "圣显", "不灭剑华", "妮露专武", "板砖"],
    "风信之锋": ["风信", "风信锋"],
    "西福斯的月光": ["西福斯", "月光", "月光小剑", "月光剑"],
    "玛海菈的水色": ["玛海菈", "水色"],
    "流浪的晚星": ["晚星"],
    "千夜浮梦": ["千夜", "神灯", "茶壶", "夜壶"],
    "图莱杜拉的回忆": ["图莱杜拉", "铃铛", "流浪者专武"],
    "东花坊时雨": ["东花坊", "时雨", "伞"],
    "裁叶萃光": ["萃光", "韭菜刀", "裁叶", "菜叶"],
    "饰铁之花": ["饰铁", "铁花"],
    "苇海信标": ["苇海", "信标"],
    "碧落之珑": ["碧落", "白术专武", "不灭绿华"],
    # 4.x
    "狼牙": ["狼牙"],
    "海渊终曲": ["海渊"],
    "灰河渡手": ["灰河"],
    "聊聊棒": ["聊聊棒"],
    "浪影阔剑": ["浪影阔剑"],
    "峡湾长歌": ["峡湾长歌"],
    "公义的酬报": ["公义的酬报"],
    "遗祀玉珑": ["玉珑"],
    "纯水流华": ["纯水流华"],
    "烈阳之嗣": ["烈阳"],
    "静谧之曲": ["静谧之曲"],
    "最初的大魔术": ["魔术弓"],
    "船坞长剑": ["船坞长剑"],
    "便携动力锯": ["动力锯"],
    "勘探钻机": ["勘探钻机"],
    "无垠蔚蓝之歌": ["无垠蔚蓝之歌"],
    "金流监督": ["金流监督"],
    "万世流涌大典": ["万世"],
    "测距规": ["测距规"],
    "水仙十字之剑": ["水仙", "水仙十字剑"],
    "静水流涌之辉": ["静水", "净水流涌之辉", "水神专武", "芙芙专武"],
    "裁断": ["贯石斧"],
    "「究极霸王超级魔剑」": ["霸王剑", "极霸剑", "全海沫村最好的剑"],
}
elements = {
    "pyro": ["火"],
    "hydro": ["水"],
    "anemo": ["风"],
    "cryo": ["冰"],
    "electro": ["雷"],
    "geo": ["岩"],
    "dendro": ["草"],
    "physical": ["物理"],
}
elementsToColor = {
    "anemo": "#65B89A",
    "geo": "#F6A824",
    "electro": "#9F79B5",
    "dendro": "#97C12B",
    "hydro": "#3FB6ED",
    "pyro": "#E76429",
    "cryo": "#8FCDDC",
    "physical": "#15161B",
}


@functools.lru_cache()
def elementToName(elem: str) -> str | None:
    """将元素昵称转为正式名"""
    elem = str.casefold(elem)  # 忽略大小写
    return elements[elem][0] if elem in elements else None


# noinspection PyPep8Naming
@functools.lru_cache()
def roleToName(shortname: str) -> str:
    """将角色昵称转为正式名"""
    shortname = str.casefold(shortname)  # 忽略大小写
    return next((value[0] for value in roles.values() for name in value if name == shortname), shortname)


# noinspection PyPep8Naming
@functools.lru_cache()
def roleToId(name: str) -> int | None:
    """获取角色ID"""
    name = str.casefold(name)
    return next((key for key, value in roles.items() for n in value if n == name), None)


# noinspection PyPep8Naming
@functools.lru_cache()
def idToName(cid: int) -> str | None:
    """从角色ID获取正式名"""
    return roles[cid][0] if cid in roles else None


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


# noinspection PyPep8Naming
@functools.lru_cache()
def roleToTag(role_name: str) -> List[str]:
    """通过角色名获取TAG"""
    role_name = str.casefold(role_name)
    return next((value for value in roles.values() if value[0] == role_name), [role_name])
