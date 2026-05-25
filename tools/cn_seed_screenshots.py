#!/usr/bin/env python3
"""
cn_seed_screenshots.py — build the CN tile→hanzi seed map from
gameplay-screenshot ground truth.

The CN font (font_cn.bin) is in a non-standard format we haven't
decoded directly. Instead we use captured gameplay screenshots
(simplified-Chinese fan release) as authoritative text and align them
character-by-character with the tile_codes parsed from D00.DAT.

Each screenshot entry below is the Chinese text exactly as displayed
in-game, paired with its scen/entry index. The character count must
match the entry's cn_tile_count or alignment fails.

Output: data/cn/tile_char_map_seed.json — consumed by
tools/dump_cn_en_pairs.py to decode cn_visible across all scenarios.
"""
import json
import sys
from collections import Counter
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
PAIRS_CN = PROJ / "data" / "translation_pairs_cn"
OUT = PROJ / "data" / "cn" / "tile_char_map_seed.json"

# (scen, entry_idx): "exact CN text shown on screen"
SCREENSHOTS: dict[tuple[int, int], str] = {
    (123, 28): "拉卡斯王国拉卡西亚城门前",
    (123, 29): ("原本富饶繁荣的拉卡斯王国，因为过于相信浮游城上装备着的魔动炮的"
                "威力，所以仅仅只拥有少量的军队。"),
    (123, 30): ("所依靠的浮游城，被利古里亚帝国军的阿鲁迪缪拉元帅所指挥的军队"
                "击落之后，在拥有压倒性兵力的帝国军面前，王都拉卡西亚根本就无法防守。"),
    (123, 31): "随后，没经过几个月，王都拉卡西亚、以及其他国土基本上都被帝国给占领。",
    (123, 32): ("还有，在一得知浮游城和拉卡西亚陷落之后，附近的各国都聚集起来开始了"
                "进攻。副王都被巴拉尔所占，而西边的国土则渐渐地被柯尔西亚国所控制。"),
    (123, 33): "利古里亚帝国之城・谒见之间",
    (123, 51): "现在，拉卡斯王国内，有许多国家的军队在相互争斗着，再也不见了往日的繁荣。",
    (123, 55): ("辛苦逃离了浮游城的一行人，辗转来到边境的领主、同时也是主人公叔叔的"
                "雷蒙德子爵那里，并在暗中制定收复祖国的计划。"),
    (123, 56): ("时间过的很快，在半年过去之后，雷蒙德子爵的身边，渐渐集结了相当"
                "多的兵力。"),
    # scen122 = attract mode (5 of 6 narrations captured; entry 23 still missing).
    # Confirmed by character-position match against partial decode using earlier seed.
    (122, 19): ("那个富饶的国家—拉卡斯位于北面的利古里亚帝国，"
                "和南面的同盟国—巴拉尔王国之间。"),
    (122, 20): ("北边的利古里亚帝国，控制了许多国家。拥有广阔的领土，"
                "但是大部分却被冻土所覆盖，收获的农作物，无法支持其所增加的人口，"
                "民众生活在贫困之中。"),
    (122, 21): ("南边的巴拉尔王国，虽然并不怎么富饶，但却和拉卡斯缔结了同盟，"
                "保持着友好关系。"),
    (122, 22): ("除此之外，还有许多小国和拉卡斯接壤。这些国家，"
                "对于拉卡斯所拥有的富饶资源和极佳的地理位置感到非常嫉恨。"),
    (122, 23): ("但是，拉卡斯凭借位于王都拉卡西亚上空的古代遗产—浮游城和装备在那里的魔动炮，"
                "多次击退了邻国的进攻。"),
    (122, 24): ("避免了战乱的和平之国拉卡斯，作为贸易的要冲而极度繁荣。"
                "并且，凭借优质的土地和丰富的地下资源，成为了大陆上最富饶的国家。 "),
    # scen001 = prologue (Lushiris narration + character-creation quiz + tutorial).
    # 98 screenshots captured 2026-04-30, covering entries 19-27, 29, 31-37, 49-52,
    # 73-80, 89-92, 110-113, 130-167 (with gaps at 162-164 and 166).
    (1, 19): "……立志成为骑士的年轻人，……将要创造历史的年轻人，请快点醒来吧。",
    (1, 20): "我的名字是露希莉丝，凡间的人都称呼我为光之女神。",
    (1, 21): "我所守护的拉卡斯王国，是个长年和平安定，极其繁荣的国家。",
    (1, 22): "但是，这个国家已隐隐出现了不祥的预兆。",
    (1, 23): "不久，它就要结束和平的历史，并开始动乱的时代。",
    (1, 24): "但是，保护人世的并不是我，而是你们的职责。我只能在一旁给予帮助。",
    (1, 25): "如果是真的希望和平的话，那你的信念就能打动人心，并能再次给这个世界带来和平。",
    (1, 26): "为了测试你是否真的能够拯救这个世界，现在，我要向你提几个问题。",
    (1, 27): "首先，请告诉我你的名字。",
    (1, 29): "那么，说明结束，请千万不要忘记雇佣佣兵。那么，期待你今后的表现。",
    (1, 31): "那么，请你回答我的问题。",
    (1, 32): "在战斗之前，我想送你一个礼物。请按下C键。",
    (1, 33): "为了创造一支无敌的部队，你认为最重要的是什么？",
    (1, 34): "统率力",
    (1, 35): "机动力",
    (1, 36): "破坏力",
    (1, 37): "为了成为英雄，你认为必须具备什么？",
    (1, 49): "下面几项里面，你最喜欢什么？",
    (1, 50): "暴风雨前的寂静",
    (1, 51): "带有大海味道的海风",
    (1, 52): "卷起树叶的秋风",
    (1, 73): "你认为神在什么地方？",
    (1, 74): "天上界",
    (1, 75): "神不存在",
    (1, 76): "一切有形的物体中",
    (1, 77): "当世界陷入毁灭的危机时，能拯救我们的，是谁？",
    (1, 78): "伟大的众神",
    (1, 79): "丰富的知识",
    (1, 80): "自己的力量",
    (1, 89): "你毕生所要追求的东西是什么？",
    (1, 90): "权力",
    (1, 91): "财富",
    (1, 92): "知识",
    (1, 110): "对你来说，爱是怎样的一种东西？",
    (1, 111): "相互给予",
    (1, 112): "接受",
    (1, 113): "无限力量的源泉",
    (1, 130): "在战斗开始的时候，你对于自己的能力有什么要求？",
    (1, 131): "丰富的战术知识",
    (1, 132): "冷静的判断力",
    (1, 133): "强大的力量",
    (1, 134): "你理想中的部队是怎么样的？",
    (1, 135): "少数精锐",
    (1, 136): "个人力量弱的大部队",
    (1, 137): "自己一个人就足够了",
    (1, 138): "最后，你是为了什么而战？",
    (1, 139): "为了得到名誉",
    (1, 140): "为了保卫祖国",
    (1, 141): "为了保护所爱的人",
    (1, 142): "如果可以的话，我想说明一下这个世界所特有的战术。",
    (1, 143): "要进行基本流程的说明吗？",
    (1, 144): ("各关卡最先会开始本关的序幕，然后，会转移到出击准备的菜单。"
               "在出击准备的菜单里，能雇佣佣兵，买卖物品，实施装备等等，还能够进行转职。"
               "并且，如果把所有指挥官都配置在地图上，就能选择【出击】开始本关的游戏。"
               "但是，由于关卡的不同，也有一开始就自动决定好配置的情况。"
               "游戏模式分为地图模式和战斗模式两部分。这次这两部分，都加入了新的系统。"
               "然后，只要满足各个关卡的【胜利条件】，就能打通该关卡。"
               "如果达到了【败北条件】，则宣告游戏结束。"
               "【胜利条件】【败北条件】在各关卡前的序幕都会被表示出来，"
               "但也有在关卡的途中变更的情况，请加以注意。"
               "胜利条件在游戏的菜单中，随时都可以确认。"),
    (1, 145): "要对出击准备时的详细部分进行说明吗？",
    (1, 146): ("在出击准备时，能够雇佣佣兵、购买物品。"
               "要雇佣佣兵的指挥官能用【LR键】进行切换。"
               "还有，关于物品和佣兵的说明，可以按【START键】进行了解。"),
    (1, 147): "要对S・S(半即时模拟）战斗进行说明吗？",
    (1, 148): ("在这次的游戏中，是以指挥官为1个部队单位开展行动的，"
               "因此，只能对指挥官下达命令，而不能对每个佣兵下达指示。"
               "另外，即使再给各个指挥官下达命令时，他也不会马上开展行动。"
               "只有在给所有的指挥官下达完行动命令后，"
               "在设定菜单里选择【开始作战】，全部队才会同时开始行动。"),
    (1, 149): "对各个指令也进行说明吗？",
    (1, 150): ("【移动目标】是用来设定部队的移动目标。"
               "如果是在最大移动力的范围力，就能设定最多4次的移动路线。"
               "【治疗】能够用来恢复部队的HP。"
               "只是，选择了这个指令，就不能进行移动或发动主动攻击了。"
               "【魔法】只消费MP来念诵魔法咒语，但不能同时再进行其它的行动。"
               "还有，魔法需要念诵的时间，越是大的魔法它所需发动的时间就越是长。"
               "【道具】能对所拥有的物品进行【装备】和【使用】。"
               "装备、使用因为是在敌・我方的移动回合结束之后再进行的，"
               "所以，在此之前，就必须先待机。"
               "【使用】：专门的物品一般在使用后，就会被消费掉。"
               "还有，有特殊效果的物品在【使用】之后，有时也会坏掉。"
               "【召唤】是一种消费MP来呼唤出魔物的魔法。"
               "呼唤出来的魔物能作为1个部队，自由地进行操作。"),
    (1, 151): ("【技能】是各个指挥官的特殊能力，"
               "分为自动使用的能力和任意使用的能力。"
               "在战斗中能够选择的，就只有任意使用的技能。"
               "效果是各种各样的，有效地使用技能，就是通向胜利的捷径吧。"
               "基本上，选择了一个指令后，就不能同时使用其它指令了。"
               "但是，只有【模式】【阵形】能和其它指令同时使用。"
               "另外，在选择【开始作战】之前，能够随时改变行动命令。"),
    (1, 152): "关于【模式】指令，要进行下说明吗？",
    (1, 153): ("移动模式里有【通常】【高速】【防御】3种。"
               "【通常】是一切都采取平衡的能力进行行动。"
               "【高速】是提升移动力，下降攻击、防御力。"
               "选择【防御】之后，就无法移动，但能提升防御力。"
               "还有，因为佣兵也留在了那里，所以阵形不会改变，"
               "这样就能对敌人张开防御网。"),
    (1, 154): "对【阵形】指令进行建议吗？",
    (1, 155): ("阵形意味着在移动后对展开的佣兵进行配置。"
               "还有，在【防御】的时候，无法改变阵形，"
               "所以，想要改变阵形的时候，就必须得解除一次防御。"
               "【口】是基本的阵形，能对应移动到任何方向。"
               "【I】能够抵挡住从侧面方向来的敌人，并弥补竖方向移动的不足。"
               "【一】能够抵挡住从前后方向来的敌人，并弥补横方向移动的不足。"
               "【＼】【／】能够抵挡住从斜方向来的敌人，并弥补斜方向移动的不足。"
               "本作的战斗是以接触到敌人为重点，"
               "所以，请巧妙地使用阵形，使战斗能有利地进展。"),
    (1, 156): "对战斗模式要进行下说明吗？",
    (1, 157): ("在移动结束后，如果在地图上和敌人接触的话，就进入战斗模式。"
               "本作包括佣兵，全体部队都能够进行战斗。"
               "还有，在地图上的配置会被直接反映到战斗中，"
               "请仔细考虑好【阵形】再采取行动。"
               "另外，在战斗前的画面中，能设定部队的【攻击目标】【护卫目标】等。"
               "在战斗前的画面中，请选择想下达命令的单位。"),
    (1, 158): ("在指示结束之后，选择菜单里的【开始作战】，"
               "或者按下【START键】，战斗就开始了。"
               "如果是无指示的场合，就会变成【自动】。"
               "之后，各单位会遵从在战斗前画面中所进行的指示，来开始战斗。"
               "另外，如果指挥官被打倒的话，那支部队就全灭了。"),
    (1, 159): "对相性进行说明吗？",
    (1, 160): ("每个属性，都有如下所示的战斗相性。"
               "步兵强于枪兵、弱于骑兵。 枪兵强于骑兵、弱于步兵。 "
               "骑兵强于步兵、弱于枪兵。"
               "弓兵强于飞兵。还有，僧侣强于亡灵、魔族、以及史莱姆。"
               "另外，飞兵里面还分为对地飞兵和对空飞兵。"
               "水兵里面有在水上特别有利的，也有只是在水上移动速度加快的。"
               "这些特征，在佣兵斡旋所选择佣兵时，能通过【START键】进行了解。"),
    (1, 161): "对灵活的转职方式进行说明吗？",
    (1, 165): ("保持同一属性的职业进行转职，称为职业提升。"
               "职业提升可以使用物品【众神的祝福】，"
               "或者当一个职业提升到等级15的时候，就会被自动进行。"
               "【例】  士官职业提升到等级15的时候，就能成为士官长。"),
    (1, 167): ("即使留下些佣兵直接打倒敌指挥官，"
               "一起全灭的佣兵的那部分经验值也还是能得到的。"
               "因此，巧妙地打倒指挥官，才是最理想的。"
               "但是，即便只是佣兵，但如果能某种程度的加以消灭，"
               "也还是能得到少量经验值的。"),
    # scen044 = SCENARIO-02 'Laffel's Madness' chapter intro and Jeriol farewell.
    # Captured 2026-04-30 (post-scen001 session).
    # Note: <$F600><$0000> protagonist-name tokens are stripped from cn_tile_codes
    # by dump_cn_en_pairs.py, so adjacent surrounding tiles end up next to each
    # other in the seed (e.g. '，，' in #67). Text below matches the LITERAL
    # tile sequence after the token strip — do not transcribe whatever name
    # the loaded save renders into the screenshot.
    (44, 23): "    SCENARIO-02    『拉斐尔的疯狂』",
    (44, 24): ("由于帝国军元帅阿鲁迪缪拉的策略，浮游城陷落了。"
               "好不容易才成功逃离了浮游城的他们，"
               "向着拉斐尔之都逃去。"),
    (44, 25): ("如果能得到同盟国巴拉尔王国的协助，"
               "那么和帝国放手一搏，也就并非是不可能的事。"
               "但是，就连拉斐尔的街上，也即将染上战火。"),
    (44, 26): "※胜利条件 ・全灭敌人 ・、蕾拉、  提娅丽丝到达地图下端",
    (44, 27): "※败北条件 ・死亡 ・蕾拉死亡",
    (44, 28): "拉斐尔之都・教堂",
    (44, 29): "呼……。完成了。",
    (44, 30): "神官大人，谢谢你了。",
    (44, 31): "神官大人，杰利奥鲁的情况怎么样了？",
    (44, 32): "……我已经尽力了。老实说，他能活到现在，已经是非常不可思议了。",
    (44, 33): "那么……",
    (44, 34): "也许、还能撑几天吧……",
    (44, 35): "不会吧……",
    (44, 36): "不好了！",
    (44, 37): "有敌人！敌人发动了袭击！市民快点前去避难！",
    (44, 38): "什么！这样可不行！",
    (44, 39): "是敌人！？帝国的那些家伙，真快啊……。",
    (44, 40): "不好了！似乎是有军队攻到这拉斐尔了！",
    (44, 41): "不会吧！",
    (44, 42): "快点做好逃离的准备！",
    (44, 43): "是！提娅丽丝也来帮忙吧！",
    (44, 44): "嗯……。你也快点。",
    (44, 45): "…等一下，。",
    (44, 46): "杰利奥鲁！？你没事吧？",
    (44, 47): "是敌人攻过来了吗？",
    (44, 48): "嗯。",
    (44, 49): "快丢下我，逃走吧……。",
    (44, 50): "你在说什么啊，杰利奥鲁！",
    (44, 51): "自己的事情自己最明白，我这伤，已经活不了多久了吧……。",
    (44, 52): "不想成为你们的负担，快丢下我走吧。",
    (44, 53): "以现在拉卡斯的兵力，这里也许也会被攻陷的。在此之前，你们要离开这里。",
    (44, 54): "杰利奥鲁！",
    (44, 55): ("啊……，你一定要成为出色的骑士，"
               "成为这个大陆上最厉害，最光荣的骑士。"),
    (44, 56): "就把这当作对我的报恩吧，并且，总有一天……要替我收复拉斐尔。",
    (44, 57): "……知道了，杰利奥鲁。我一定会成为出色的骑士，再次回到这里的。",
    (44, 58): "我会编组好士兵，回到这里并且，收复你和蕾拉的故乡—拉斐尔。",
    (44, 59): "……蕾拉就拜托你了。",
    (44, 60): "蕾拉小姐！？",
    (44, 61): "…………。你听到了吗？",
    (44, 62): "杰利奥鲁、我……",
    (44, 63): ("拜托了，蕾拉。你也是个将要成为骑士之妻的女孩，"
               "这种觉悟，应该还是有的……。这是我最后的请求。"
               "至少，不要让我为了你而担心，快和一起，离开这里吧！"),
    (44, 64): ("……好。那么，我对你也有个请求。"
               "那就是一定要活下去，等以后再来和我见面……"),
    (44, 65): "嗯……。",
    (44, 66): "……。",
    (44, 67): "呼……。那么，快走吧，，没时间了。",
    (44, 68): "拜托你了，……。 ",
}


# PLOT.DAT chapter-recap blocks. The file is structured as:
#   bytes  0..3:   u32 BE = file size
#   bytes  4..73:  35 × u16 BE block offsets
#   each block:
#     bytes 0..1: 0xFFF8 (start marker)
#     bytes 2..3: u16 BE block index (1..35)
#     bytes 4..7: 0x00000000
#     bytes 8..:  u16 BE tile codes, with separators
#                 0xFFFE (block end), 0xFFFD (paragraph break),
#                 0xFFFC (line break, used inside long blocks).
# Text below uses '\n' for paragraph break; alignment skips separator codes.
PLOT_BLOCKS: dict[int, str] = {
    0: ("SCENARIO-01\n"
        "在主人公被授任骑士的那天，浮游城受到了帝国军元帅阿鲁迪缪拉所率领的飞兵部队的奇袭。\n"
        "防御战失败，提娅丽丝的父亲威廉卿被杀，浮游城也被击沉了。\n"
        "辛苦逃离的主人公，带着受伤的杰利奥鲁以及他的未婚妻—蕾拉，还有提娅丽丝，向拉斐尔之都赶去。"),
}

PLOT_DAT = PROJ / "data" / "cn" / "plot_cn.dat"


def parse_plot_block(data: bytes, block_idx: int) -> list[int] | None:
    """Return the list of visible tile codes for block_idx (separators stripped)."""
    import struct
    file_size = struct.unpack(">I", data[:4])[0]
    offsets = list(struct.unpack(">35H", data[4:74])) + [file_size]
    if block_idx < 0 or block_idx >= 35:
        return None
    start, end = offsets[block_idx], offsets[block_idx + 1]
    body = data[start + 8:end]  # skip 8-byte header
    codes = list(struct.unpack(f">{len(body)//2}H", body[:len(body)//2*2]))
    # strip separator codes (0xFFxx)
    return [c for c in codes if c < 0xff00]


def main() -> int:
    tile_to_chars: dict[int, Counter[str]] = {}
    aligned = 0
    skipped: list[tuple[tuple[int, int], str]] = []

    for (scen, idx), text in SCREENSHOTS.items():
        path = PAIRS_CN / f"scen{scen:03d}.json"
        if not path.exists():
            skipped.append(((scen, idx), "scen JSON missing — run dump_cn_en_pairs first"))
            continue
        data = json.loads(path.read_text())
        entry = next((e for e in data["entries"] if e["index"] == idx), None)
        if entry is None:
            skipped.append(((scen, idx), f"entry {idx} not in scen{scen}"))
            continue
        codes = entry["cn_tile_codes"]
        if len(codes) != len(text):
            skipped.append(((scen, idx),
                           f"length mismatch: {len(codes)} tiles vs {len(text)} chars"))
            continue
        for tc, ch in zip(codes, text):
            tile_to_chars.setdefault(tc, Counter())[ch] += 1
        aligned += 1

    # Align PLOT.DAT blocks
    plot_aligned = 0
    if PLOT_DAT.exists() and PLOT_BLOCKS:
        plot_data = PLOT_DAT.read_bytes()
        for block_idx, text in PLOT_BLOCKS.items():
            codes = parse_plot_block(plot_data, block_idx)
            if codes is None:
                skipped.append((("plot", block_idx), f"block {block_idx} out of range"))
                continue
            text_no_nl = text.replace("\n", "")
            if len(codes) != len(text_no_nl):
                skipped.append((("plot", block_idx),
                               f"length mismatch: {len(codes)} tiles vs {len(text_no_nl)} chars"))
                continue
            for tc, ch in zip(codes, text_no_nl):
                tile_to_chars.setdefault(tc, Counter())[ch] += 1
            plot_aligned += 1

    conflicts = {tc: dict(c) for tc, c in tile_to_chars.items() if len(c) > 1}
    final = {tc: c.most_common(1)[0][0] for tc, c in tile_to_chars.items()}

    # Direct bitmap identifications from data/cn/font_cn_decoded.bin — tiles
    # identified by reading their 1bpp 16x16 ASCII rendering, no screenshot
    # alignment needed. Cross-checked against surrounding decoded context.
    bitmap_path = PROJ / "tools" / "cn_seed_bitmap.json"
    bitmap_added = 0
    bitmap_overrides = []
    if bitmap_path.exists():
        bm = json.loads(bitmap_path.read_text())
        for k, v in bm.get("map", {}).items():
            tid = int(k)
            if tid in final and final[tid] != v:
                bitmap_overrides.append((tid, final[tid], v))
            elif tid not in final:
                bitmap_added += 1
            final[tid] = v

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "source": "tools/cn_seed_screenshots.py",
        "screenshots_used": aligned,
        "tiles_mapped": len(final),
        "conflicts": len(conflicts),
        "map": {str(k): v for k, v in sorted(final.items())},
    }, ensure_ascii=False, indent=2))

    print(f"Aligned {aligned}/{len(SCREENSHOTS)} D00 screenshots, "
          f"{plot_aligned}/{len(PLOT_BLOCKS)} PLOT.DAT blocks; "
          f"+{bitmap_added} from bitmap-identified")
    if bitmap_overrides:
        print(f"Bitmap overrides ({len(bitmap_overrides)}) of screenshot-derived mappings:")
        for tid, old, new in bitmap_overrides[:20]:
            print(f"  tile #{tid}: screenshot={old!r} → bitmap={new!r}")
    if skipped:
        print(f"Skipped {len(skipped)}:")
        for key, why in skipped:
            print(f"  scen{key[0]:03d} #{key[1]}: {why}")
    if conflicts:
        print(f"Conflicts ({len(conflicts)}) — same tile mapped to multiple hanzi:")
        for tc, counts in conflicts.items():
            print(f"  tile {tc}: {counts}")
    print(f"Wrote {OUT} ({len(final)} tile→hanzi entries)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
