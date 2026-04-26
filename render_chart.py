#!/usr/bin/env python3
"""
NOSTALGIA 谱面平面图生成脚本

使用方法：
    python render_chart.py <basename> <difficulty_number>

示例：
    python render_chart.py m_l0061_felys 3
    python render_chart.py m_t0052_summerdiary 2

难度编号：
    0 = Normal, 1 = Hard, 2 = Expert, 3 = Real
"""

import os
import sys
import xml.etree.ElementTree as ET

# ======================================================================
# 路径配置（请根据实际情况修改）
# ======================================================================

# NOSTALGIA 游戏 contents 文件夹路径
CONTENTS_DIR = r"F:\NOSTALGIA\contents"

# 素材文件夹路径（内含 notes/ 和 covers/ 子目录）
ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")

# 输出文件夹路径
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")

# ======================================================================

from NOSTALGIAChartRender import parse_chart, Renderer, set_assets_dir


DIFFICULTY_MAP = {
    0: ("00normal", "Normal"),
    1: ("01hard", "Hard"),
    2: ("02extreme", "Expert"),
    3: ("03real", "Real"),
}

MUSIC_DIRS = [
    os.path.join(CONTENTS_DIR, "data_op3", "sound", "music"),
    os.path.join(CONTENTS_DIR, "data_op2", "sound", "music"),
    os.path.join(CONTENTS_DIR, "data", "sound", "music"),
]

MUSIC_LIST_PATHS = [
    os.path.join(CONTENTS_DIR, "data_op3", "sound", "music_list.xml"),
    os.path.join(CONTENTS_DIR, "data_op2", "sound", "music_list.xml"),
    os.path.join(CONTENTS_DIR, "data", "sound", "music_list.xml"),
]

COVER_DIR = os.path.join(ASSETS_DIR, "covers")


def find_chart_xml(basename: str, diff_code: str) -> str | None:
    """根据 basename 和难度代码查找谱面 XML 文件路径"""
    for md in MUSIC_DIRS:
        folder = os.path.join(md, basename)
        if not os.path.isdir(folder):
            continue
        candidates = [
            os.path.join(folder, f"{basename}_{diff_code}.xml"),
            os.path.join(folder, f"{basename}_april_{diff_code}.xml"),
            os.path.join(folder, f"{basename}_pre_{diff_code}.xml"),
        ]
        for cand in candidates:
            if os.path.exists(cand):
                return cand
    return None


def extract_song_info(basename: str, diff_name: str, diff_code: str) -> dict:
    """从 music_list.xml 提取歌曲信息"""
    info = {
        "title": basename,
        "artist": "",
        "level": "",
        "cover": "",
    }

    # 查找封面
    for ext in [".jpg", ".png"]:
        c = os.path.join(COVER_DIR, f"{basename}{ext}")
        if os.path.exists(c):
            info["cover"] = c
            break

    level_tag_map = {
        "00normal": "level_normal",
        "01hard": "level_hard",
        "02extreme": "level_extreme",
        "03real": "level_real",
    }
    level_tag = level_tag_map.get(diff_code, "")

    for ml_path in MUSIC_LIST_PATHS:
        if not os.path.exists(ml_path):
            continue
        try:
            with open(ml_path, "rb") as f:
                text = f.read().decode("cp932", errors="replace")
            text = text.replace("encoding='Shift_JIS'", "encoding='UTF-8'")
            root = ET.fromstring(text.encode("utf-8"))

            for spec in root.findall("music_spec"):
                be = spec.find("basename")
                if be is None or not be.text:
                    continue
                if be.text.strip().lower() != basename.lower():
                    continue

                te = spec.find("title")
                ae = spec.find("artist")
                if te is not None and te.text:
                    info["title"] = te.text.strip()
                if ae is not None and ae.text:
                    info["artist"] = ae.text.strip()

                if level_tag:
                    lev = spec.find(level_tag)
                    if lev is not None and lev.text:
                        val = lev.text.strip()
                        if val and val != "0":
                            info["level"] = val

                return info
        except Exception as e:
            print(f"[WARN] 读取 {ml_path} 失败: {e}")

    return info


def render_chart(basename: str, diff_num: int):
    """渲染指定曲目和难度的谱面平面图"""
    if diff_num not in DIFFICULTY_MAP:
        print(f"[ERROR] 无效的难度编号: {diff_num}。有效范围: 0-3")
        sys.exit(1)

    diff_code, diff_name = DIFFICULTY_MAP[diff_num]

    xml_path = find_chart_xml(basename, diff_code)
    if xml_path is None:
        print(f"[ERROR] 找不到谱面文件: {basename} / {diff_name}")
        sys.exit(1)

    print(f"[INFO] 解析谱面: {xml_path}")
    try:
        chart = parse_chart(xml_path)
    except Exception as e:
        print(f"[ERROR] 解析失败: {e}")
        sys.exit(1)

    print(f"[INFO] {chart}")

    info = extract_song_info(basename, diff_name, diff_code)
    print(f"[INFO] 歌曲: {info['title']} / 艺术家: {info['artist']} / 难度: {diff_name} {info['level']}")

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Real 难度显示时减 10
    display_level = info["level"]
    if diff_name == "Real" and display_level.isdigit():
        display_level = str(int(display_level) - 10)

    renderer = Renderer(
        chart=chart,
        song_title=info["title"],
        artist=info["artist"],
        difficulty=diff_name,
        cover_path=info["cover"] if info["cover"] else None,
        level=display_level,
    )

    out_name = f"{basename}_{diff_code}_chart.png"
    output_path = os.path.join(OUTPUT_DIR, out_name)
    renderer.save(output_path)
    print(f"[INFO] 已保存: {output_path}")


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        print(f"用法: python {sys.argv[0]} <basename> <difficulty_number>")
        sys.exit(1)

    basename = sys.argv[1]
    try:
        diff_num = int(sys.argv[2])
    except ValueError:
        print("[ERROR] 难度编号必须是整数 (0-3)")
        sys.exit(1)

    # 设置素材目录
    set_assets_dir(ASSETS_DIR)

    render_chart(basename, diff_num)


if __name__ == "__main__":
    main()
