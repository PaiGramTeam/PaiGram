"""此文件用于储存 honey impact 中的部分基础数据"""
__all__ = [
    'HONEY_ID_MAP', 'HONEY_RESERVED_ID_MAP',
    'HONEY_ROLE_NAME_MAP'
]

# noinspection SpellCheckingInspection
HONEY_ID_MAP = {
    'character': {
        'ayaka_002': ['神里绫华', 5],
        'xiangling_023': ['香菱', 4],
        'xingqiu_025': ['行秋', 4],
        'albedo_038': ['阿贝多', 5],
        'lisa_006': ['丽莎', 4],
        'sucrose_043': ['砂糖', 4],
        'mona_041': ['莫娜', 5],
        'diona_039': ['迪奥娜', 4],
        'venti_022': ['温迪', 5],
        'xinyan_044': ['辛焱', 4],
        'rosaria_045': ['罗莎莉亚', 4],
        'hutao_046': ['胡桃', 5],
        'zhongli_030': ['钟离', 5],
        'ningguang_027': ['凝光', 4],
        'eula_051': ['优菈', 5],
        'shougun_052': ['雷电将军', 5],
        'sayu_053': ['早柚', 4],
        'keqing_042': ['刻晴', 5],
        'ganyu_037': ['甘雨', 5],
        'gorou_055': ['五郎', 4],
        'tartaglia_033': ['达达利亚', 5],
        'beidou_024': ['北斗', 4],
        'itto_057': ['荒泷一斗', 5],
        'ambor_021': ['安柏', 4],
        'diluc_016': ['迪卢克', 5],
        'chongyun_036': ['重云', 4],
        'kaeya_015': ['凯亚', 4],
        'aloy_062': ['埃洛伊', 4],
        'yunjin_064': ['云堇', 4],
        'shinobu_065': ['久岐忍', 4],
        'ayato_066': ['神里绫人', 5],
        'collei_067': ['柯莱', 4],
        'feiyan_048': ['烟绯', 4],
        'razor_020': ['雷泽', 4],
        'barbara_014': ['芭芭拉', 4],
        'dori_068': ['多莉', 4],
        'noel_034': ['诺艾尔', 4],
        'tighnari_069': ['提纳里', 5],
        'kazuha_047': ['枫原万叶', 5],
        'qiqi_035': ['七七', 5],
        'bennett_032': ['班尼特', 4],
        'nilou_070': ['妮露', 5],
        'fischl_031': ['菲谢尔', 4],
        'klee_029': ['可莉', 5],
        'cyno_071': ['赛诺', 5],
        'candace_072': ['坎蒂丝', 4],
        'qin_003': ['琴', 5],
        'xiao_026': ['魈', 5],
        'playergirl_007': ['荧', 5],
        'heizo_059': ['鹿野院平藏', 4],
        'yoimiya_049': ['宵宫', 5],
        'playerboy_005': ['空', 5],
        'sara_056': ['九条裟罗', 4],
        'tohma_050': ['托马', 4],
        'kokomi_054': ['珊瑚宫心海', 5],
        'shenhe_063': ['申鹤', 5],
        'yae_058': ['八重神子', 5],
        'yelan_060': ['夜兰', 5]
    },
    'weapon': {
        'i_n11401': ['西风剑', 4],
        'i_n11305': ['吃虎鱼刀', 3],
        'i_n11101': ['无锋剑', 1],
        'i_n11303': ['旅行剑', 3],
        'i_n11410': ['暗巷闪光', 4],
        'i_n11301': ['冷刃', 3],
        'i_n11416': ['笼钓瓶一心', 4],
        'i_n11407': ['铁蜂刺', 4],
        'i_n11501': ['风鹰剑', 5],
        'i_n11419': ['「一心传」名刀', 4],
        'i_n13409': ['龙脊长枪', 4],
        'i_n13406': ['千岩长枪', 4],
        'i_n11412': ['降临之剑', 4],
        'i_n13505': ['和璞鸢', 5],
        'i_n11504': ['斫峰之刃', 5],
        'i_n11417': ['原木刀', 4],
        'i_n13101': ['新手长枪', 1],
        'i_n11509': ['雾切之回光', 5],
        'i_n11502': ['天空之刃', 5],
        'i_n14304': ['翡玉法球', 3],
        'i_n13401': ['匣里灭辰', 4],
        'i_n11413': ['腐殖之剑', 4],
        'i_n11404': ['宗室长剑', 4],
        'i_n11418': ['西福斯的月光', 4],
        'i_n11415': ['辰砂之纺锤', 4],
        'i_n11503': ['苍古自由之誓', 5],
        'i_n13402': ['试作星镰', 4],
        'i_n11511': ['圣显之钥', 5],
        'i_n11409': ['黑剑', 4],
        'i_n11414': ['天目影打刀', 4],
        'i_n11405': ['匣里龙吟', 4],
        'i_n11510': ['波乱月白经津', 5],
        'i_n13405': ['决斗之枪', 4],
        'i_n13407': ['西风长枪', 4],
        'i_n11408': ['黑岩长剑', 4],
        'i_n14306': ['琥珀玥', 3],
        'i_n11505': ['磐岩结绿', 5],
        'i_n14408': ['黑岩绯玉', 4],
        'i_n14417': ['盈满之实', 4],
        'i_n14416': ['流浪的晚星', 4],
        'i_n12301': ['铁影阔剑', 3],
        'i_n14506': ['不灭月华', 5],
        'i_n14305': ['甲级宝珏', 3],
        'i_n13415': ['「渔获」', 4],
        'i_n14402': ['流浪乐章', 4],
        'i_n12402': ['钟剑', 4],
        'i_n12201': ['佣兵重剑', 2],
        'i_n14403': ['祭礼残章', 4],
        'i_n14405': ['匣里日月', 4],
        'i_n12101': ['训练大剑', 1],
        'i_n14501': ['天空之卷', 5],
        'i_n14413': ['嘟嘟可故事集', 4],
        'i_n14302': ['讨龙英杰谭', 3],
        'i_n14303': ['异世界行记', 3],
        'i_n12303': ['白铁大剑', 3],
        'i_n14409': ['昭心', 4],
        'i_n13502': ['天空之脊', 5],
        'i_n14404': ['宗室秘法录', 4],
        'i_n14401': ['西风秘典', 4],
        'i_n14415': ['证誓之明瞳', 4],
        'i_n13301': ['白缨枪', 3],
        'i_n13404': ['黑岩刺枪', 4],
        'i_n13408': ['宗室猎枪', 4],
        'i_n13201': ['铁尖枪', 2],
        'i_n13511': ['赤沙之杖', 5],
        'i_n13416': ['断浪长鳍', 4],
        'i_n13509': ['薙草之稻光', 5],
        'i_n13403': ['流月针', 4],
        'i_n13417': ['贯月矢', 4],
        'i_n13419': ['风信之锋', 4],
        'i_n13302': ['钺矛', 3],
        'i_n11406': ['试作斩岩', 4],
        'i_n13414': ['喜多院十文字', 4],
        'i_n14201': ['口袋魔导书', 2],
        'i_n13501': ['护摩之杖', 5],
        'i_n13303': ['黑缨枪', 3],
        'i_n14101': ['学徒笔记', 1],
        'i_n12401': ['西风大剑', 4],
        'i_n12304': ['石英大剑', 3],
        'i_n14412': ['忍冬之果', 4],
        'i_n14414': ['白辰之环', 4],
        'i_n14509': ['神乐之真意', 5],
        'i_n14406': ['试作金珀', 4],
        'i_n14502': ['四风原典', 5],
        'i_n12305': ['以理服人', 3],
        'i_n14504': ['尘世之锁', 5],
        'i_n12306': ['飞天大御剑', 3],
        'i_n14301': ['魔导绪论', 3],
        'i_n12302': ['沐浴龙血的剑', 3],
        'i_n14407': ['万国诸海图谱', 4],
        'i_n13504': ['贯虹之槊', 5],
        'i_n12416': ['恶王丸', 4],
        'i_n12409': ['螭骨剑', 4],
        'i_n12404': ['宗室大剑', 4],
        'i_n12405': ['雨裁', 4],
        'i_n12414': ['桂木斩长正', 4],
        'i_n12408': ['黑岩斩刀', 4],
        'i_n12410': ['千岩古剑', 4],
        'i_n12406': ['试作古华', 4],
        'i_n12415': ['玛海菈的水色', 4],
        'i_n12403': ['祭礼大剑', 4],
        'i_n12411': ['雪葬的星银', 4],
        'i_n12412': ['衔珠海皇', 4],
        'i_n12407': ['白影剑', 4],
        'i_n11201': ['银剑', 2],
        'i_n12504': ['无工之剑', 5],
        'i_n15305': ['信使', 3],
        'i_n15411': ['落霞', 4],
        'i_n15413': ['风花之颂', 4],
        'i_n15401': ['西风猎弓', 4],
        'i_n12510': ['赤角石溃杵', 5],
        'i_n15405': ['弓藏', 4],
        'i_n15403': ['祭礼弓', 4],
        'i_n15201': ['历练的猎弓', 2],
        'i_n15404': ['宗室长弓', 4],
        'i_n15302': ['神射手之誓', 3],
        'i_n12501': ['天空之傲', 5],
        'i_n15402': ['绝弦', 4],
        'i_n12417': ['森林王器', 4],
        'i_n11306': ['飞天御剑', 3],
        'i_n15410': ['暗巷猎手', 4],
        'i_n15414': ['破魔之弓', 4],
        'i_n15101': ['猎弓', 1],
        'i_n15415': ['掠食者', 4],
        'i_n15301': ['鸦羽弓', 3],
        'i_n11304': ['暗铁剑', 3],
        'i_n15303': ['反曲弓', 3],
        'i_n15306': ['黑檀弓', 3],
        'i_n15408': ['黑岩战弓', 4],
        'i_n15304': ['弹弓', 3],
        'i_n15409': ['苍翠猎弓', 4],
        'i_n15412': ['幽夜华尔兹', 4],
        'i_n15406': ['试作澹月', 4],
        'i_n15417': ['王下近侍', 4],
        'i_n15501': ['天空之翼', 5],
        'i_n15418': ['竭泽', 4],
        'i_n15507': ['冬极白星', 5],
        'i_n15508': ['若水', 5],
        'i_n15503': ['终末嗟叹之诗', 5],
        'i_n15509': ['飞雷之弦振', 5],
        'i_n15511': ['猎人之径', 5],
        'i_n12502': ['狼的末路', 5],
        'i_n15407': ['钢轮弓', 4],
        'i_n12503': ['松籁响起之时', 5],
        'i_n15416': ['曚云之月', 4],
        'i_n11402': ['笛剑', 4],
        'i_n15502': ['阿莫斯之弓', 5],
        'i_n11302': ['黎明神剑', 3],
        'i_n13507': ['息灾', 5],
        'i_n11403': ['祭礼剑', 4],
        'i_n14410': ['暗巷的酒与诗', 4]
    },
    'material': {
        'i_413': ['「勤劳」的哲学', 4],
        'i_411': ['「勤劳」的教导', 2],
        'i_n104333': ['「巧思」的指引', 3],
        'i_584': ['今昔剧画之鬼人', 5],
        'i_427': ['「天光」的指引', 3],
        'i_453': ['「抗争」的哲学', 4],
        'i_n112063': ['休眠菌核', 3],
        'i_408': ['「浮世」的哲学', 4],
        'i_n104336': ['「笃行」的指引', 3],
        'i_n104337': ['「笃行」的哲学', 4],
        'i_421': ['「自由」的教导', 2],
        'i_n112068': ['混沌容器', 2],
        'i_n104331': ['「诤言」的哲学', 4],
        'i_n104330': ['「诤言」的指引', 3],
        'i_402': ['「诗文」的指引', 3],
        'i_416': ['「风雅」的教导', 2],
        'i_423': ['「自由」的哲学', 4],
        'i_407': ['「浮世」的指引', 3],
        'i_581': ['今昔剧画之恶尉', 2],
        'i_401': ['「诗文」的教导', 2],
        'i_441': ['「繁荣」的教导', 2],
        'i_n104335': ['「笃行」的教导', 2],
        'i_422': ['「自由」的指引', 3],
        'i_432': ['「黄金」的指引', 3],
        'i_n104332': ['「巧思」的教导', 2],
        'i_53': ['历战的箭簇', 3],
        'i_417': ['「风雅」的指引', 3],
        'i_431': ['「黄金」的教导', 2],
        'i_403': ['「诗文」的哲学', 4],
        'i_451': ['「抗争」的教导', 2],
        'i_462': ['东风之爪', 5],
        'i_461': ['东风之翎', 5],
        'i_524': ['凛风奔狼的怀乡', 5],
        'i_433': ['「黄金」的哲学', 4],
        'i_406': ['「浮世」的教导', 2],
        'i_452': ['「抗争」的指引', 3],
        'i_n104334': ['「巧思」的哲学', 4],
        'i_133': ['原素花蜜', 3],
        'i_582': ['今昔剧画之虎啮', 3],
        'i_442': ['「繁荣」的指引', 3],
        'i_483': ['凶将之手眼', 5],
        'i_583': ['今昔剧画之一角', 4],
        'i_418': ['「风雅」的哲学', 4],
        'i_463': ['东风的吐息', 5],
        'i_443': ['「繁荣」的哲学', 4],
        'i_521': ['凛风奔狼的始龀', 2],
        'i_n104329': ['「诤言」的教导', 2],
        'i_464': ['北风之尾', 5],
        'i_61': ['沉重号角', 2],
        'i_523': ['凛风奔狼的断牙', 4],
        'i_485': ['万劫之真意', 5],
        'i_33': ['不祥的面具', 3],
        'i_467': ['吞天之鲸·只角', 5],
        'i_465': ['北风之环', 5],
        'i_21': ['史莱姆凝液', 1],
        'i_513': ['孤云寒林的圣骸', 4],
        'i_185': ['浮游干核', 1],
        'i_511': ['孤云寒林的光砂', 2],
        'i_522': ['凛风奔狼的裂齿', 3],
        'i_514': ['孤云寒林的神体', 5],
        'i_412': ['「勤劳」的指引', 3],
        'i_466': ['北风的魂匣', 5],
        'i_173': ['混沌真眼', 4],
        'i_73': ['地脉的新芽', 4],
        'i_183': ['偏光棱镜', 4],
        'i_n112061': ['孢囊晶尘', 3],
        'i_83': ['混沌炉心', 4],
        'i_142': ['结实的骨片', 3],
        'i_22': ['史莱姆清', 2],
        'i_112': ['士官的徽记', 2],
        'i_23': ['史莱姆原浆', 3],
        'i_163': ['名刀镡', 3],
        'i_n112062': ['失活菌核', 2],
        'i_n112072': ['混浊棱晶', 3],
        'i_428': ['「天光」的哲学', 4],
        'i_552': ['漆黑陨铁的一片', 3],
        'i_172': ['混沌枢纽', 3],
        'i_72': ['地脉的枯叶', 3],
        'i_426': ['「天光」的教导', 2],
        'i_n112070': ['混沌锚栓', 4],
        'i_491': ['智识之冕', 5],
        'i_123': ['攫金鸦印', 3],
        'i_121': ['寻宝鸦印', 1],
        'i_153': ['幽邃刻像', 4],
        'i_41': ['导能绘卷', 1],
        'i_187': ['浮游晶化核', 3],
        'i_32': ['污秽的面具', 2],
        'i_469': ['武炼之魂·孤影', 5],
        'i_553': ['漆黑陨铁的一角', 4],
        'i_151': ['晦暗刻像', 2],
        'i_182': ['水晶棱镜', 3],
        'i_71': ['地脉的旧枝', 2],
        'i_512': ['孤云寒林的辉岩', 3],
        'i_42': ['封魔绘卷', 2],
        'i_132': ['微光花蜜', 2],
        'i_152': ['夤夜刻像', 3],
        'i_186': ['浮游幽核', 2],
        'i_482': ['灰烬之心', 5],
        'i_81': ['混沌装置', 2],
        'i_82': ['混沌回路', 3],
        'i_n114045': ['烈日威权的残响', 2],
        'i_541': ['狮牙斗士的枷锁', 2],
        'i_n114046': ['烈日威权的余光', 3],
        'i_171': ['混沌机关', 2],
        'i_51': ['牢固的箭簇', 1],
        'i_542': ['狮牙斗士的铁链', 3],
        'i_111': ['新兵的徽记', 1],
        'i_n112069': ['混沌模块', 3],
        'i_n114048': ['烈日威权的旧日', 5],
        'i_162': ['影打刀镡', 2],
        'i_481': ['狱火之蝶', 5],
        'i_554': ['漆黑陨铁的一块', 5],
        'i_n112071': ['破缺棱晶', 2],
        'i_143': ['石化的骨片', 4],
        'i_103': ['督察长祭刀', 4],
        'i_31': ['破损的面具', 1],
        'i_43': ['禁咒绘卷', 3],
        'i_n114043': ['绿洲花园的哀思', 4],
        'i_n112067': ['织金红绸', 3],
        'i_n114042': ['绿洲花园的恩惠', 3],
        'i_n114044': ['绿洲花园的真谛', 5],
        'i_n112060': ['荧光孢粉', 2],
        'i_122': ['藏银鸦印', 2],
        'i_n112065': ['褪色红绸', 1],
        'i_141': ['脆弱的骨片', 2],
        'i_n114040': ['谧林涓露的金符', 5],
        'i_n114039': ['谧林涓露的银符', 4],
        'i_562': ['远海夷地的玉枝', 3],
        'i_563': ['远海夷地的琼枝', 4],
        'i_564': ['远海夷地的金枝', 5],
        'i_n114038': ['谧林涓露的铁符', 3],
        'i_n114037': ['谧林涓露的铜符', 2],
        'i_52': ['锐利的箭簇', 2],
        'i_n112066': ['镶边红绸', 2],
        'i_174': ['隐兽指爪', 2],
        'i_176': ['隐兽鬼爪', 4],
        'i_534': ['雾海云间的转还', 5],
        'i_531': ['雾海云间的铅丹', 2],
        'i_503': ['高塔孤王的断片', 4],
        'i_91': ['雾虚花粉', 2],
        'i_92': ['雾虚草囊', 3],
        'i_501': ['高塔孤王的破瓦', 2],
        'i_504': ['高塔孤王的碎梦', 5],
        'i_468': ['魔王之刃·残片', 5],
        'i_544': ['狮牙斗士的理想', 5],
        'i_470': ['龙王之冕', 5],
        'i_572': ['鸣神御灵的欢喜', 3],
        'i_574': ['鸣神御灵的勇武', 5],
        'i_573': ['鸣神御灵的亲爱', 4],
        'i_480': ['熔毁之刻', 5],
        'i_62': ['黑铜号角', 3],
        'i_101': ['猎兵祭刀', 2],
        'i_551': ['漆黑陨铁的一粒', 2],
        'i_484': ['祸神之禊泪', 5],
        'i_n114041': ['绿洲花园的追忆', 2],
        'i_n112059': ['蕈兽孢子', 1],
        'i_561': ['远海夷地的瑚枝', 2],
        'i_n112073': ['辉光棱晶', 4],
        'i_175': ['隐兽利爪', 3],
        'i_532': ['雾海云间的汞丹', 3],
        'i_93': ['雾虚灯芯', 4],
        'i_131': ['骗骗花蜜', 1],
        'i_571': ['鸣神御灵的明惠', 2],
        'i_n114047': ['烈日威权的梦想', 4],
        'i_63': ['黑晶号角', 4],
        'i_543': ['狮牙斗士的镣铐', 4],
        'i_n112064': ['茁壮菌核', 4],
        'i_161': ['破旧的刀镡', 1],
        'i_472': ['鎏金之鳞', 5],
        'i_113': ['尉官的徽记', 3],
        'i_502': ['高塔孤王的残垣', 3],
        'i_181': ['黯淡棱镜', 2],
        'i_102': ['特工祭刀', 3],
        'i_471': ['血玉之枝', 5],
        'i_533': ['雾海云间的金丹', 4]
    }
}

HONEY_RESERVED_ID_MAP = {
    k: {j[0]: [i, j[1]] for i, j in v.items()} for k, v in HONEY_ID_MAP.items()
}
# noinspection SpellCheckingInspection
HONEY_ROLE_NAME_MAP = {
    10000002: ['ayaka_002', '神里绫华', 'ayaka'],
    10000042: ['keqing_042', '刻晴', 'keqing'],
    10000030: ['zhongli_030', '钟离', 'zhongli'],
    10000026: ['xiao_026', '魈', 'xiao'],
    10000020: ['razor_020', '雷泽', 'razor'],
    10000015: ['kaeya_015', '凯亚', 'kaeya'],
    10000037: ['ganyu_037', '甘雨', 'ganyu'],
    10000041: ['mona_041', '莫娜', 'mona'],
    10000038: ['albedo_038', '阿贝多', 'albedo'],
    10000014: ['barbara_014', '芭芭拉', 'barbara'],
    10000027: ['ningguang_027', '凝光', 'ningguang'],
    10000054: ['kokomi_054', '珊瑚宫心海', 'kokomi'],
    10000044: ['xinyan_044', '辛焱', 'xinyan'],
    10000056: ['sara_056', '九条裟罗', 'sara'],
    10000053: ['sayu_053', '早柚', 'sayu'],
    10000043: ['sucrose_043', '砂糖', 'sucrose'],
    10000059: ['heizo_059', '鹿野院平藏', 'heizo'],
    10000060: ['yelan_060', '夜兰', 'yelan'],
    10000064: ['yunjin_064', '云堇', 'yunjin'],
    10000050: ['tohma_050', '托马', 'tohma'],
    10000066: ['ayato_066', '神里绫人', 'ayato'],
    10000067: ['collei_067', '柯莱', 'collei'],
    10000052: ['shougun_052', '雷电将军', 'shougun'],
    10000069: ['tighnari_069', '提纳里', 'tighnari'],
    10000007: ['playergirl_007', '荧', 'playergirl'],
    10000016: ['diluc_016', '迪卢克', 'diluc'],
    10000070: ['nilou_070', '妮露', 'nilou'],
    10000047: ['kazuha_047', '枫原万叶', 'kazuha'],
    10000055: ['gorou_055', '五郎', 'gorou'],
    10000034: ['noel_034', '诺艾尔', 'noel'],
    10000024: ['beidou_024', '北斗', 'beidou'],
    10000032: ['bennett_032', '班尼特', 'bennett'],
    10000062: ['aloy_062', '埃洛伊', 'aloy'],
    10000025: ['xingqiu_025', '行秋', 'xingqiu'],
    10000022: ['venti_022', '温迪', 'venti'],
    10000036: ['chongyun_036', '重云', 'chongyun'],
    10000049: ['yoimiya_049', '宵宫', 'yoimiya'],
    10000029: ['klee_029', '可莉', 'klee'],
    10000006: ['lisa_006', '丽莎', 'lisa'],
    10000033: ['tartaglia_033', '达达利亚', 'tartaglia'],
    10000039: ['diona_039', '迪奥娜', 'diona'],
    10000063: ['shenhe_063', '申鹤', 'shenhe'],
    10000072: ['candace_072', '坎蒂丝', 'candace'],
    10000045: ['rosaria_045', '罗莎莉亚', 'rosaria'],
    10000051: ['eula_051', '优菈', 'eula'],
    10000035: ['qiqi_035', '七七', 'qiqi'],
    10000057: ['itto_057', '荒泷一斗', 'itto'],
    10000005: ['playerboy_005', '空', 'playerboy'],
    10000048: ['feiyan_048', '烟绯', 'feiyan'],
    10000003: ['qin_003', '琴', 'qin'],
    10000023: ['xiangling_023', '香菱', 'xiangling'],
    10000071: ['cyno_071', '赛诺', 'cyno'],
    10000031: ['fischl_031', '菲谢尔', 'fischl'],
    10000046: ['hutao_046', '胡桃', 'hutao'],
    10000021: ['ambor_021', '安柏', 'ambor'],
    10000068: ['dori_068', '多莉', 'dori'],
    10000065: ['shinobu_065', '久岐忍', 'shinobu'],
    10000058: ['yae_058', '八重神子', 'yae']
}


def main():
    from pathlib import Path
    path = Path("Y:/Fork/TGPaimonBot/plugins/genshin/daily/honey.json").resolve()
    import ujson as json

    data = json.load(path.open())
    breakpoint()


if __name__ == '__main__':
    main()
