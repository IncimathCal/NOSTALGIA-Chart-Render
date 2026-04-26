# NOSTALGIA Chart Render

谱面渲染器，将 NOSTALGIA 游戏内的 chart XML 转换为静态 PNG 平面图。

## 项目结构

```
ChartRender/
├── NOSTALGIAChartRender/      # Python 库
│   ├── __init__.py             # 对外暴露 parse_chart, Renderer, set_assets_dir
│   ├── element.py              # 数据模型：Chart, Note, Timing
│   ├── parser.py               # XML 解析器
│   ├── render.py               # 渲染器核心（最大文件，含所有绘制逻辑）
│   ├── rhythm.py               # 节奏分析（推断分音类型）
│   ├── texture_loader.py       # 纹理加载与缓存
│   ├── theme.py                # 颜色/字体/尺寸配置
│   └── 谱面格式解析.md          # XML 格式完整文档
├── assets/
│   ├── notes/                  # note 纹理（按游戏内搜索优先级合并）
│   └── covers/                 # 歌曲封面
├── output/                     # 默认输出目录
└── render_chart.py             # 命令行入口脚本
```

## 依赖

- Python 3.10+
- `Pillow`（图像处理）
- `numpy`（Trill 渐变层计算）

```bash
pip install Pillow numpy
```

## 快速开始

修改 `render_chart.py` 开头的路径配置：

```python
CONTENTS_DIR = r"F:\NOSTALGIA\contents"
ASSETS_DIR   = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
OUTPUT_DIR   = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
```

运行：

```bash
python render_chart.py m_l0061_felys 3        # Real
python render_chart.py m_t0052_summerdiary 2  # Expert
```

难度编号：`0=Normal, 1=Hard, 2=Expert, 3=Real`

## 核心架构

### 坐标系统

采用**下落式**坐标：
- 时间向下流动（y 轴向下为时间增加方向）
- `y = canvas_height - reserved_bottom - time_ms / resize`
- `resize=4` 表示 1 毫秒 = 0.25 像素

### 渲染管线（单段模式）

```python
_draw_track_background()          # 黑白键背景
_draw_beat_lines()                # 拍子线
_draw_key_separators()            # 琴键分隔线
_draw_variable_speed_layer()      # 变速区域半透明覆盖
_draw_glissando_chain_connections()  # Glissando 链平行四边形连接
_draw_notes()                     # 所有音符
_draw_judge_line()                # 判定线
_post_process_segment()           # 分段裁剪平铺
_draw_segment_annotations()       # BPM/分音注释
_add_header()                     # 顶部信息栏
_draw_combo_milestones()          # 每 100 物件标记
_draw_footer()                    # 底部生成器信息
```

### 分段渲染

当谱面时长 > 25 秒时，自动按小节切分为多段，每段约 20 秒，横向拼接。

切分逻辑在 `_calculate_segments()` 中，基于 BPM 计算小节边界。

### Note 类型与纹理映射

| note_type | 渲染方式 | 头尾纹理 | 中间条 |
|-----------|---------|---------|--------|
| 0 / 8 | 单点纹理 | — | — |
| 2 / 10 | 长押 sustained | 头部 white/white_forte，尾部 long_end | 纯色矩形（50% 透明）|
| 4 / 12 | Glissando 链 | glissando 纹理 | 平行四边形连接（背景层）|
| 64 | Trill | 头部 trill_piano，尾部 long_end | 交替渐变层（numpy 生成，80% 透明）|

### 纹理加载优先级

素材按以下优先级合并到 `assets/notes/`：

1. `data_op2/texture/notes_00/`（最高优先级）
2. `data_op2/texture/notes_01/`
3. `data/texture/notes/`（跳过空文件）
4. `tools/output_assets/notes/`（补充素材）

### 颜色与手映射

- `hand=0`：右手 → 红色纹理（`_r` 后缀）
- `hand=1`：左手 → 蓝色纹理（`_l` 后缀）
- `hand=2`：隐藏音符 → **不渲染**

## 关键文件说明

### render.py

- `Coordinate`：坐标转换类，支持单段和分段两种模式
- `Renderer._render()`：主入口，根据分段数选择单段或多段渲染
- `Renderer._draw_notes()`：遍历所有 note，过滤 `hand=2`
- `Renderer._draw_sustained()`：绘制长押/Trill 的头尾和中间条
- `Renderer._draw_trill_layers()`：Trill 渐变层，用 numpy 生成交替图案
- `Renderer._draw_glissando_chain_connections()`：Glissando 链平行四边形
- `Renderer._post_process_segment()`：分段裁剪与横向拼接

### texture_loader.py

- `TextureLoader`：单例模式，缓存原始纹理和缩放后的纹理
- `set_assets_dir(path)`：配置素材根目录
- `_find_texture()`：在 `assets/notes/` 下查找纹理

### parser.py

- `parse_chart(xml_path)` → `Chart` 对象
- 解析 `header`、`event_data`（仅 type=0 BPM）、`note_data`
- `KNOWN_TYPES = {0, 2, 4, 8, 10, 12, 64}`

### element.py

- `Chart.get_glissando_chains()`：通过 `param1`/`param2` 链表解析 Glissando 链
- `Note.is_glissando_head()` / `is_glissando_tail()`：链头/链尾判断

## 扩展与修改指南

### 修改主题颜色/尺寸

编辑 `theme.py` 中的 `Theme` dataclass：

```python
@dataclass
class Theme:
    track_width: int = 900      # 轨道宽度
    resize: int = 4             # 时间缩放比例（越小谱面越长）
    note_height: int = 16       # 音符高度
    # ... 颜色配置
```

### 添加新的 note 类型支持

1. 在 `parser.py` 的 `KNOWN_TYPES` 中添加新类型
2. 在 `render.py` 的 `_draw_note()` 中添加分支逻辑
3. 在 `texture_loader.py` 的 `_base_name()` 中映射纹理名
4. 在 `theme.py` 的 `note_colors` 中添加 fallback 颜色

### 修改分段策略

编辑 `render.py` 的 `_calculate_segments()`：
- `TARGET = 20000`：目标每段时长（毫秒）
- `MIN_SEG = 10000`：最短段时长
- `OVERLAP = 50`：段间重叠（毫秒）

### 修改 Real 难度等级显示

在 `render.py` 的 `_draw_header_content()` 中：

```python
if diff == "Real" and display_level.isdigit():
    display_level = str(int(display_level) - 10)
```

## 已知问题与 TODO

1. **效率**：长谱面（>120 秒）渲染时间约 3~5 秒，瓶颈在 Pillow 的逐 note `alpha_composite` 上。如需进一步优化可考虑：
   - 预缩放纹理缓存
   - 分段并行渲染
   - 用 OpenCV 替代 Pillow 做批量合成

2. **Trill 宽度**：当前 1.3x 乘数使 Trill 略宽于实机，需调整 `note_rect()` 中的宽度计算

3. **event_data type 1~8**：事件类型含义未完全解码

4. **velocity_zone_data**：未在渲染中使用

5. **note_type=8 (Normal-sfx)**：与 type=0 外观相同，但可能应有不同视觉效果

6. **key_kind / param3**：所有谱面恒为 0，用途未知

## 外部工具依赖

本项目为纯 Python 渲染器，**不依赖** vgmstream/ffmpeg，仅解析 XML 并生成静态图像。

如需配套音频导出工具（从 XWB 提取伴奏+钢琴），参考 `tools/export.py` 计划（未实现）。
