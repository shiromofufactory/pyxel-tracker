import pyxel as px
import json
import copy

from system import sounds


# 日本語フォント表示
class BDFRenderer:
    BORDER_DIRECTIONS = [
        (-1, -1),
        (0, -1),
        (1, -1),
        (-1, 0),
        (1, 0),
        (-1, 1),
        (0, 1),
        (1, 1),
    ]

    def __init__(self, bdf_filename):
        self.fontboundingbox = [0, 0, 0, 0]
        self.fonts = self._parse_bdf(bdf_filename)
        self.screen_ptr = px.screen.data_ptr()
        self.screen_width = px.width

    def _parse_bdf(self, bdf_filename):
        fonts = {}
        code = None
        bitmap = None
        dwidth = 0
        with open(bdf_filename, "r") as f:
            for line in f:
                if line.startswith("ENCODING"):
                    code = int(line.split()[1])
                elif line.startswith("DWIDTH"):
                    dwidth = int(line.split()[1])
                elif line.startswith("BBX"):
                    bbx_data = list(map(int, line.split()[1:]))
                    font_width, font_height, offset_x, offset_y = (
                        bbx_data[0],
                        bbx_data[1],
                        bbx_data[2],
                        bbx_data[3],
                    )
                elif line.startswith("BITMAP"):
                    bitmap = []
                elif line.startswith("ENDCHAR"):
                    fonts[code] = (
                        dwidth,
                        font_width,
                        font_height,
                        offset_x,
                        offset_y,
                        bitmap,
                    )
                    bitmap = None
                elif line.startswith("FONTBOUNDINGBOX"):
                    # 0:width 1:height 2:offset_x 3:offset_y
                    self.fontboundingbox = list(map(int, line.split()[1:]))
                elif bitmap is not None:
                    hex_string = line.strip()
                    bin_string = bin(int(hex_string, 16))[2:].zfill(len(hex_string) * 4)
                    bitmap.append(int(bin_string[::-1], 2))
        return fonts

    def _draw_font(self, x, y, font, color):
        dwidth, font_width, font_height, offset_x, offset_y, bitmap = font
        screen_ptr = self.screen_ptr
        screen_width = self.screen_width
        x = x + self.fontboundingbox[2] + offset_x
        y = (
            y
            + self.fontboundingbox[1]
            + self.fontboundingbox[3]
            - font_height
            - offset_y
        )
        for j in range(font_height):
            for i in range(font_width):
                if (bitmap[j] >> i) & 1:
                    screen_ptr[(y + j) * screen_width + x + i] = color

    def text(self, x, y, text, color=7, border_color=None, spacing=0):
        for char in text:
            code = ord(char)
            if code not in self.fonts:
                continue
            font = self.fonts[code]
            if border_color is not None:
                for dx, dy in self.BORDER_DIRECTIONS:
                    self._draw_font(
                        x + dx,
                        y + dy,
                        font,
                        border_color,
                    )
            self._draw_font(x, y, font, color)
            x += font[0] + spacing


# ボタン
class Button:
    def __init__(self, type, key, x, y, w, text):
        self.type = type
        self.key = key
        self.x = x
        self.y = y
        self.w = w
        self.h = 10 if self.type else 12
        self.text = text
        self.selected = False

    def draw(self, parm):
        text_s = str(self.text)
        if self.type:
            selected = parm[self.type] == self.key
            rect_c = 6 if selected else 5
            text_c = 0
        else:
            rect_c = 4
            text_c = 9
        px.rect(self.x, self.y, self.w - 1, self.h - 1, rect_c)
        px.text(
            self.x + self.w / 2 - len(text_s) * 2,
            self.y + self.h / 2 - 3,
            text_s,
            text_c,
        )


class App:
    def __init__(self):
        px.init(256, 256, title="Pyxel Sound Generator", quit_key=px.KEY_NONE)
        self.bdf = BDFRenderer("./system/misaki_gothic.bdf")
        self.parm = {
            "speed": 240,  # 28800 /240 = bpm120
            "chord": 0,  # コード
            "transpose": 0,  # 移調
            "arp_tone": 0,  # アルペジオの音色
            "arp_lowest_note": 28,  # アルペジオ最低音
            "arp_continue_rate": 0.4,  # アルペジオ連続音発生率
            "arp_rest_rate": 0.2,  # アルペジオ休符発生率
            "base": 4,  # ベースパターン
            "base_highest_note": 26,  # ベース（ルート）最高音
            "drums": 4,  # ドラムパターン(-1でドラムレス)
        }
        try:
            fin = open("./user/tones.json", "rt")
        except:
            fin = open("./system/tones.json", "rt")
        finally:
            self.tones = json.loads(fin.read())
            fin.close()
        try:
            fin = open("./user/patterns.json", "rt")
        except:
            fin = open("./system/patterns.json", "rt")
        finally:
            self.patterns = json.loads(fin.read())
            fin.close()
        with open("./system/generator.json", "rt") as fin:
            self.generator = json.loads(fin.read())
        self.buttons = []
        for i, elm in enumerate(list_speed):
            self.buttons.append(
                Button("speed", elm, 8 + 24 * i, 18, 24, int(28800 / elm))
            )
        for i, elm in enumerate(self.generator["chords"]):
            self.buttons.append(Button("chord", i, 8 + 24 * i, 48, 24, i + 1))
        for i in range(12):
            key = (i + 6) % 12 - 11
            self.buttons.append(Button("transpose", key, 8 + 20 * i, 78, 20, i - 5))
        for i, elm in enumerate(list_tones):
            self.buttons.append(Button("arp_tone", i, 8 + 24 * i, 108, 24, i + 1))
        for i, elm in enumerate(list_arp_continue_rate):
            self.buttons.append(
                Button("arp_continue_rate", elm, 8 + 24 * i, 138, 24, elm)
            )
        for i, elm in enumerate(self.generator["base"]):
            self.buttons.append(Button("base", i, 8 + 24 * i, 168, 24, i + 1))
        for i, elm in enumerate(self.generator["drums"]):
            self.buttons.append(Button("drums", i, 8 + 24 * i, 198, 24, i + 1))
        self.buttons.append(Button("drums", -1, 8 + 24 * 8, 198, 48, "No Drums"))
        # self.buttons.append(Button(None, None, 96, 232, 48, "Restart"))
        self.items = []
        self.generate_music()
        self.play()
        self.saved_playkey = [-1, -1]
        px.mouse(True)
        px.run(self.update, self.draw)

    def update(self):
        if not px.btn(px.MOUSE_BUTTON_LEFT):
            return
        mx = px.mouse_x
        my = px.mouse_y
        for button in self.buttons:
            if (
                mx >= button.x
                and mx < button.x + button.w
                and my >= button.y
                and my < button.y + button.h
            ):
                if button.type:
                    self.parm[button.type] = button.key
                    self.generate_music()
                self.play()

    def draw(self):
        px.cls(7)
        text_c = 1
        text_c_sub = 5
        self.bdf.text(8, 8, "テンポ", text_c)
        self.bdf.text(8, 38, "コードしんこう", text_c)
        chord_name = self.generator["chords"][self.parm["chord"]]["description"]
        self.bdf.text(72, 38, chord_name, text_c_sub)
        self.bdf.text(8, 68, "トランスポーズ", text_c)
        self.bdf.text(8, 98, "アルペジオ　おんしょく", text_c)
        arp_tone_name = list_tones[self.parm["arp_tone"]][1]
        self.bdf.text(104, 98, arp_tone_name, text_c_sub)
        # self.bdf.text(8, 128, "アルペジオ　ルートおんをふくめない", text_c)
        self.bdf.text(8, 128, "アルペジオ　じぞくおんのわりあい", text_c)
        # self.bdf.text(16, 136, "１にちかいと　ながいおとがふえる", 13)
        self.bdf.text(8, 158, "ベース　パターン", text_c)
        self.bdf.text(8, 188, "ドラム　パターン", text_c)
        # self.bdf.text(16, 192, "「No drums」をせんたくすると、ドラムパートのかわりに", 13)
        # self.bdf.text(16, 200, "アルペジオにリバーブがかかります", 13)
        for button in self.buttons:
            button.draw(self.parm)
        self.draw_piano()

    def draw_piano(self):
        sx = 8
        sy = 232
        px.rectb(sx, sy, 5 * 42 - 1, 16, 0)
        for x in range(5 * 7 - 1):
            px.line(sx + 5 + x * 6, sy, sx + 5 + x * 6, sy + 15, 0)
        for o in range(5):
            px.rect(sx + 3 + o * 42, sy, 5, 9, 0)
            px.rect(sx + 9 + o * 42, sy, 5, 9, 0)
            px.rect(sx + 21 + o * 42, sy, 5, 9, 0)
            px.rect(sx + 27 + o * 42, sy, 5, 9, 0)
            px.rect(sx + 33 + o * 42, sy, 5, 9, 0)
        pos = px.play_pos(0)[1]
        note_len = self.parm["speed"] / 16
        loc = int(pos // note_len)
        item = self.items[loc]
        self.draw_playkey(0, item[6], 11)
        self.draw_playkey(1, item[10], 10)
        for i, elm in enumerate(self.patterns):
            y = i // 3
            x = i % 3
            c = 0 if item[14] == elm["key"] else 13
            px.text(220 + x * 10, 233 + y * 8, elm["abbr"], c)

    def draw_playkey(self, key, input, c):
        value = input
        if value is None:
            value = self.saved_playkey[key]
        else:
            self.saved_playkey[key] = value
        if value < 0:
            return
        sx = 8
        sy = 232
        note12 = value % 12
        oct = value // 12
        x = (1, 4, 7, 10, 13, 19, 22, 25, 28, 31, 34, 37)[note12] + oct * 42
        y = 2 if note12 in [1, 3, 6, 8, 10] else 10
        px.rect(sx + x, sy + y, 3, 4, c)

    def play(self):
        for ch, sound in enumerate(self.music):
            px.sound(ch).set(*sound)
            px.play(ch, ch, loop=True)

    def generate_music(self):
        parm = self.parm
        no_drum = parm["drums"] < 0
        base = self.generator["base"][parm["base"]]
        drums = self.generator["drums"][parm["drums"]]
        chord = self.generator["chords"][parm["chord"]]
        chord_lists = []
        for progression in chord["progression"]:
            chord_list = {"loc": progression["loc"], "base": 0, "notes": []}
            notes = progression["notes"]
            # ベース音設定
            for idx in range(12):
                if notes[idx] == 2:
                    chord_list["base"] = idx
            # レンジを決める
            note_highest = None
            idx = 0
            while True:
                note_type = notes[idx % 12]
                note = 12 + idx + parm["transpose"]
                if note >= parm["arp_lowest_note"]:
                    if note_type in [1, 2]:
                        chord_list["notes"].append((note, note_type))
                        if note_highest is None:
                            note_highest = note + 12
                    elif note_type == 9 and note_highest:
                        chord_list["notes"].append((note, note_type))
                if note_highest and note >= note_highest:
                    break
                idx += 1
            chord_lists.append(chord_list)
            chord_lists_cnt = len(chord_lists)
        items = []
        saved_melody = -1  # 直前のメロディー音
        items = [copy.deepcopy(item_empty) for _ in range(16 * 4)]
        for loc in range(16 * 4):
            item = items[loc]
            next_chord_loc = 16 * 4
            for rev_idx in range(chord_lists_cnt):
                idx = chord_lists_cnt - rev_idx - 1
                if loc >= chord_lists[idx]["loc"]:
                    chord_list = chord_lists[idx]
                    break
                else:
                    next_chord_loc = chord_lists[idx]["loc"]
            tick = loc % 16  # 拍(0-15)
            if loc == 0:  # 最初の行（セットアップ）
                item[0] = parm["speed"]  # テンポ
                item[1] = 48  # 4/4拍子
                item[2] = 3  # 16分音符
                item[3] = list_tones[parm["arp_tone"]][0]  # アルペジオ音色
                item[4] = 5  # アルペジオ音量
                item[5] = 12  # アルペジオ音長
                item[7] = 7  # ベース音色
                item[8] = 7  # ベース音量
                item[9] = 12  # ベース音長
                if no_drum:
                    item[11] = item[3]  # リバーブ音色
                    item[12] = 2  # リバーブ音量
                    item[13] = item[5]
                else:
                    item[12] = 5  # ドラム音量
            # メロディー音設定
            if item[6] is None:  # すでに埋まっていたらスキップ
                cur_idx = None  # 直前のメロディーのインデックスを今のコードリストと照合
                for idx, note in enumerate(chord_list["notes"]):
                    if saved_melody == note[0]:
                        cur_idx = idx
                        break
                if px.rndf(0.0, 1.0) < parm["arp_rest_rate"]:  # 休符
                    item[6] = -1
                elif saved_melody < 0 or cur_idx is None:  # 直前が休符 or コード切り替え
                    idx = self.get_jumping_tone(chord_list)
                    item[6] = chord_list["notes"][idx][0]
                else:  # 直前の音が決まっている
                    if px.rndf(0.0, 1.0) < parm["arp_continue_rate"]:
                        item[6] = None  # 連続音
                    else:
                        next_idx = self.get_jumping_tone(chord_list, False)
                        diff = abs(next_idx - cur_idx)
                        direction = 1 if next_idx > cur_idx else -1
                        if loc + diff >= next_chord_loc or diff > 3:
                            # コードが切り替わる/跳躍量が大きい場合、跳躍音を採用（ルート音除外）
                            idx = self.get_jumping_tone(chord_list)
                            item[6] = chord_list["notes"][idx][0]
                        elif diff == 0:
                            item[6] = saved_melody
                        else:
                            cur_loc = loc
                            while next_idx != cur_idx:
                                cur_idx += direction
                                items[cur_loc][6] = chord_list["notes"][cur_idx][0]
                                cur_loc += 1
            if item[6] is not None:
                saved_melody = item[6]
            # ベース音設定
            base_note = base[tick]
            if not base[tick] is None and base[tick] >= 0:
                highest = parm["base_highest_note"]
                base_root = 12 + parm["transpose"] + chord_list["base"]
                while base_root + 24 > highest:
                    base_root -= 12
                base_note = base_root + base[tick]
            item[10] = base_note
            # ドラム音設定
            if not no_drum:
                pattern = "basic" if loc < 16 * 3 else "final"
                item[14] = drums[pattern][tick] if drums[pattern][tick] else None
        # 連続音の調整とリバーブパート
        for loc in range(16 * 4):
            item = items[loc]
            prev_item = items[(loc + 63) % 64]
            if no_drum:
                item[14] = prev_item[6]
        self.music = sounds.compile(items, self.tones, self.patterns)
        self.items = items
        with open(f"./musics/generator.json", "wt") as fout:
            fout.write(json.dumps(self.music))

    def get_jumping_tone(self, chord_list, no_root=True):
        notes = chord_list["notes"]
        while True:
            idx = px.rndi(0, len(notes) - 1)
            # TODO: テンションコードの考慮
            allowed_types = [1] if no_root else [1, 2]
            if notes[idx][1] in allowed_types:
                return idx


item_empty = [None for _ in range(19)]
list_speed = [360, 312, 276, 240, 216, 192, 168, 156]
list_tones = [
    (11, "Pulse_solid"),
    (8, "Pulse-thin"),
    (2, "Pulse-soft"),
    (10, "Square-solid"),
    (6, "Square-thin (Harp)"),
    (4, "Square-soft (Flute)"),
]
list_arp_continue_rate = [0.0, 0.2, 0.4, 0.6, 0.8]
App()
