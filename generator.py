import pyxel as px
import json
from system import sounds

COL_BACK_PRIMARY = 7
COL_BACK_SECONDARY = 12
COL_BTN_BASIC = 5
COL_BTN_SELECTED = 6
COL_BTN_DISABLED = 13
COL_TEXT_BASIC = 1
COL_TEXT_MUTED = 5


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


# タブ
class Tab:
    def __init__(self, idx, x, y, text):
        self.idx = idx
        self.x = x
        self.y = y
        self.w = 64
        self.h = 12
        self.text = text

    def draw(self, app):
        active = self.idx == app.tab
        rect_c = COL_BACK_PRIMARY if active else COL_BACK_SECONDARY
        text_c = COL_TEXT_BASIC if active else COL_TEXT_MUTED
        px.rect(self.x, self.y, self.w, self.h, rect_c)
        text_info = app.get_text(self.text)
        x = int(self.x + self.w / 2 - len(text_info[0]) * text_info[1])
        y = int(self.y + self.h / 2 - 4)
        app.text(x, y, self.text, text_c)


# ボタン
class Button:
    def __init__(self, tab, type, key, x, y, w, text):
        self.tab = tab
        self.type = type
        self.key = key
        self.x = x
        self.y = y
        self.w = w
        self.h = 10 if self.type else 12
        self.text = text
        self.selected = False
        self.disabled = False

    def draw(self, app):
        if app.tab != self.tab:
            return
        text_s = str(self.text)
        if self.type:
            if app.parm[self.type] == self.key:
                rect_c = COL_BTN_SELECTED
            elif self.disabled:
                rect_c = COL_BTN_DISABLED
            else:
                rect_c = COL_BTN_BASIC
            text_c = COL_TEXT_BASIC
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
            "preset": 0,
            "transpose": 0,  # 移調
            "language": 0,
            "melo_lowest_note": 28,  # メロディ最低音
            "melo_jutout_rate": 0.2,  # 音符の半ずらし発生率
            "base_highest_note": 26,  # ベース（ルート）最高音
            "base_quantize": 15,  # ベースクオンタイズ
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
        self.tabs = []
        list_tab = (0, 1, 2)
        for i, elm in enumerate(list_tab):
            self.set_tab(i, i * 64 + 4, 4, elm)
        self.buttons = []
        # プリセットタブ
        list_language = ("Japanese", "English")
        for i, elm in enumerate(self.generator["preset"]):
            self.set_btn(0, "preset", i, 8 + 24 * i, 34, 24, i + 1)
        for i in range(12):
            key = (i + 6) % 12 - 11
            self.set_btn(0, "transpose", key, 8 + 20 * i, 98, 20, i - 5)
        for i, elm in enumerate(list_language):
            self.set_btn(0, "language", i, 8 + 48 * i, 128, 48, elm)
        # コードとリズムタブ
        list_speed = [360, 312, 276, 240, 216, 192, 168, 156]
        list_base_quantize = [12, 13, 14, 15]
        for i, elm in enumerate(list_speed):
            self.set_btn(1, "speed", elm, 8 + 24 * i, 34, 24, int(28800 / elm))
        for i, elm in enumerate(self.generator["chords"]):
            self.set_btn(1, "chord", i, 8 + 24 * i, 64, 24, i + 1)
        for i, elm in enumerate(self.generator["base"]):
            self.set_btn(1, "base", i, 8 + 24 * i, 94, 24, i + 1)
        for i, elm in enumerate(list_base_quantize):
            quantize = str(int(elm * 100 / 16)) + "%"
            self.set_btn(1, "base_quantize", elm, 8 + 24 * i, 124, 24, quantize)
        for i, elm in enumerate(self.generator["drums"]):
            self.set_btn(1, "drums", i, 8 + 24 * i, 154, 24, i + 1)
        self.set_btn(1, "drums", -1, 8 + 24 * 8, 154, 48, "No Drums")
        # メロディータブ
        list_melo_continue_rate = [0.0, 0.2, 0.4, 0.6]
        list_melo_rest_rate = [0.0, 0.1, 0.2, 0.3, 0.4]
        list_melo_length_rate = [
            (0.4, 0.6),
            (0.2, 0.4),
            (0.4, 0.0),
            (0.0, 0.4),
            (0.0, 0.0),
        ]
        list_melo_4_rate = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
        list_melo_8_rate = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
        for i, elm in enumerate(list_tones):
            self.set_btn(2, "melo_tone", i, 8 + 24 * i, 34, 24, i + 1)
        for i, elm in enumerate(list_melo_rest_rate):
            self.set_btn(2, "melo_rest_rate", elm, 8 + 24 * i, 64, 24, elm)
        for i, elm in enumerate(list_melo_continue_rate):
            self.set_btn(2, "melo_continue_rate", elm, 8 + 24 * i, 94, 24, elm)
        for i, elm in enumerate(list_melo_4_rate):
            self.set_btn(2, "melo_4_rate", elm, 8 + 24 * i, 124, 24, elm)
        for i, elm in enumerate(list_melo_8_rate):
            self.set_btn(2, "melo_8_rate", elm, 8 + 24 * i, 154, 24, elm)
        # self.set_btn(2, None, None, 96, 232, 48, "Restart"))
        self.items = []
        self.set_preset(self.parm["preset"])
        self.play()
        self.saved_playkey = [-1, -1]
        self.tab = 0
        px.mouse(True)
        px.run(self.update, self.draw)

    def set_tab(self, *args):
        self.tabs.append(Tab(*args))

    def set_btn(self, *args):
        self.buttons.append(Button(*args))

    def set_disabled(self):
        melo_4_rate = self.parm["melo_4_rate"]
        for button in self.buttons:
            if button.type == "melo_8_rate":
                button.disabled = melo_4_rate + button.key > 1.0
        if self.parm["melo_8_rate"] + melo_4_rate > 1.0:
            self.parm["melo_8_rate"] = 1.0 - melo_4_rate

    def update(self):
        if not px.btnp(px.MOUSE_BUTTON_LEFT):
            return
        mx = px.mouse_x
        my = px.mouse_y
        for tab in self.tabs:
            if (
                mx >= tab.x
                and mx < tab.x + tab.w
                and my >= tab.y
                and my < tab.y + tab.h
            ):
                self.tab = tab.idx
        for button in self.buttons:
            if (
                self.tab == button.tab
                and not button.disabled
                and mx >= button.x
                and mx < button.x + button.w
                and my >= button.y
                and my < button.y + button.h
            ):
                self.select_button(button)

    def select_button(self, button):
        if button.type:
            self.parm[button.type] = button.key
            if button.type == "preset":
                self.set_preset(button.key)
            else:
                make_melody = button.type in [
                    "transpose",
                    "chord",
                    "melo_continue_rate",
                    "melo_rest_rate",
                    "melo_4_rate",
                    "melo_8_rate",
                ]
                self.set_disabled()
                self.generate_music(make_melody)
            self.play()

    def draw(self):
        px.cls(COL_BACK_SECONDARY)
        # px.rectb(0, 0, 256, 208, 12)
        px.rect(4, 16, 248, 192, COL_BACK_PRIMARY)
        if self.tab == 0:
            self.text(8, 24, 3, COL_TEXT_BASIC)
            px.rectb(8, 48, 240, 32, COL_TEXT_MUTED)
            self.text(16, 52, 4, COL_TEXT_MUTED)
            self.text(16, 60, 5, COL_TEXT_MUTED)
            self.text(16, 68, 6, COL_TEXT_MUTED)
            self.text(8, 88, 7, COL_TEXT_BASIC)
            self.text(8, 118, 8, COL_TEXT_BASIC)
        elif self.tab == 1:
            self.text(8, 24, 9, COL_TEXT_BASIC)
            self.text(8, 54, 10, COL_TEXT_BASIC)
            chord_name = self.generator["chords"][self.parm["chord"]]["description"]
            self.text(72, 54, chord_name, COL_TEXT_MUTED)
            self.text(8, 84, 11, COL_TEXT_BASIC)
            self.text(8, 114, 12, COL_TEXT_BASIC)
            self.text(8, 144, 13, COL_TEXT_BASIC)
            px.rectb(8, 168, 240, 24, COL_TEXT_MUTED)
            self.text(16, 172, 14, COL_TEXT_MUTED)
            self.text(16, 180, 15, COL_TEXT_MUTED)
        elif self.tab == 2:
            self.text(8, 24, 16, COL_TEXT_BASIC)
            melo_tone_name = list_tones[self.parm["melo_tone"]][1]
            self.text(40, 24, melo_tone_name, COL_TEXT_MUTED)
            self.text(8, 54, 17, COL_TEXT_BASIC)
            self.text(8, 84, 18, COL_TEXT_BASIC)
            self.text(8, 114, 19, COL_TEXT_BASIC)
            self.text(8, 144, 20, COL_TEXT_BASIC)
            px.rectb(8, 168, 240, 32, COL_TEXT_MUTED)
            self.text(16, 172, 21, COL_TEXT_MUTED)
            self.text(16, 180, 22, COL_TEXT_MUTED)
            self.text(16, 188, 23, COL_TEXT_MUTED)
        for tab in self.tabs:
            tab.draw(self)
        for button in self.buttons:
            button.draw(self)
        self.draw_piano()

    def draw_piano(self):
        sx = 8
        sy = 232
        px.rect(sx, sy, 5 * 42 - 1, 16, 7)
        for x in range(5 * 7 - 1):
            px.line(sx + 5 + x * 6, sy, sx + 5 + x * 6, sy + 15, 0)
        for o in range(5):
            px.rect(sx + 3 + o * 42, sy, 5, 9, 0)
            px.rect(sx + 9 + o * 42, sy, 5, 9, 0)
            px.rect(sx + 21 + o * 42, sy, 5, 9, 0)
            px.rect(sx + 27 + o * 42, sy, 5, 9, 0)
            px.rect(sx + 33 + o * 42, sy, 5, 9, 0)
        pos = px.play_pos(0)[1]
        ticks = self.parm["speed"] / 16
        loc = int(pos // ticks)
        item = self.items[loc]
        self.draw_playkey(0, item[6], 11)
        self.draw_playkey(1, item[10], 10)
        (x1, _) = self.get_piano_xy(self.parm["melo_lowest_note"])
        (x2, _) = self.get_piano_xy(self.parm["melo_lowest_note"] + 16)
        px.rect(x1, 229, x2 - x1 + 3, 2, 11)
        (x1, _) = self.get_piano_xy(self.parm["base_highest_note"] - 24)
        (x2, _) = self.get_piano_xy(self.parm["base_highest_note"])
        px.rect(x1, 229, x2 - x1 + 3, 2, 10)
        for i, elm in enumerate(self.patterns):
            y = i // 3
            x = i % 3
            c = COL_TEXT_BASIC if item[14] == elm["key"] else COL_TEXT_MUTED
            px.text(220 + x * 10, 233 + y * 8, elm["abbr"], c)

    def draw_playkey(self, key, input, c):
        value = input
        if value is None:
            value = self.saved_playkey[key]
        else:
            self.saved_playkey[key] = value
        if value < 0:
            return
        (x, y) = self.get_piano_xy(value)
        px.rect(x, y, 3, 4, c)

    def get_piano_xy(self, value):
        note12 = value % 12
        oct = value // 12
        x = 8 + (1, 4, 7, 10, 13, 19, 22, 25, 28, 31, 34, 37)[note12] + oct * 42
        y = 232 + (2 if note12 in [1, 3, 6, 8, 10] else 10)
        return x, y

    def play(self):
        for ch, sound in enumerate(self.music):
            px.sound(ch).set(*sound)
            px.play(ch, ch, loop=True)

    def set_preset(self, value):
        preset = self.generator["preset"][value]
        for key in preset:
            self.parm[key] = preset[key]
        self.set_disabled()
        self.generate_music()

    def text(self, x, y, value, c):
        if type(value) is int:
            self.bdf.text(x, y, self.get_text(value)[0], c)
        else:
            self.bdf.text(x, y, value, c)

    def get_text(self, value):
        list_text = [
            ("きほん", "Basic"),
            ("コードとリズム", "Chord & Rhythm"),
            ("メロディ", "Melody"),
            ("プリセット", "Preset"),
            (
                "「コードとリズム」「メロディ」の　オススメせっていを",
                "The recommended settings for 'Chord and Rhyth' and",
            ),
            (
                "とうろくしてあります。　はじめてのかたは",
                "'Melody' are registered. If you are a first time user,",
            ),
            ("プリセットをもとに　きょくをつくってみましょう。", "create a song based on the presets."),
            ("トランスポーズ", "Transpose"),
            ("げんご", "Language"),
            ("テンポ", "Tempo"),
            ("コードしんこう", "Chord progression"),
            ("ベース　パターン", "Bass Patterns"),
            ("ベース　クオンタイズ", "Base Quantize"),
            ("ドラム　パターン", "Drums Patterns"),
            ("「No drums」をせんたくすると　ドラムパートのかわりに", "When 'No drums' is selected, "),
            (
                "メロディにリバーブがかかります。",
                "reverb is applied to the melody instead of the drum part.",
            ),
            ("ねいろ", "Tone"),
            ("きゅうふのひんど", "Rests Ratio"),
            ("じぞくおんのひんど", "Sustained Tone Ratio"),
            ("４ぶおんぷのひんど", "Quarter notes Ratio"),
            ("８ぶおんぷのひんど", "Eighth notes Ratio"),
            (
                "おんぷには４ぶおんぷ・８ぶおんぷ・１６ぶおんぷがあり、",
                "There are three types of notes: quarter/eighth/sixteenth",
            ),
            ("１６ぶおんぷのはっせいりつは、", "notes, and the sixteenth notes ratio is "),
            (
                "（１−（４ぶおんぷのひんど＋８ぶおんぷのひんど））です。",
                "( 1 - ( Quarter notes Ratio + Eighth notes Ratio ) )",
            ),
        ]
        lang = self.parm["language"]
        return list_text[value][lang], 4 if lang == 0 else 2

    def generate_music(self, make_melody=True):
        px.stop()
        parm = self.parm
        no_drum = parm["drums"] < 0
        base = self.generator["base"][parm["base"]]
        drums = self.generator["drums"][parm["drums"]]
        chord = self.generator["chords"][parm["chord"]]
        # コードリスト準備
        self.chord_lists = []
        for progression in chord["progression"]:
            chord_list = {
                "loc": progression["loc"],
                "base": 0,
                "notes": [],
                "no_root": False,
            }
            notes = progression["notes"]
            note_chord_cnt = 0
            # ベース音設定
            for idx in range(12):
                if notes[idx] == 2:
                    chord_list["base"] = idx
                if notes[idx] in [1, 2, 3]:
                    note_chord_cnt += 1
            chord_list["no_root"] = note_chord_cnt > 3
            # レンジを決める
            note_highest = None
            idx = 0
            while True:
                note_type = notes[idx % 12]
                note = 12 + idx + parm["transpose"]
                if note >= parm["melo_lowest_note"]:
                    if note_type in [1, 2, 3]:
                        chord_list["notes"].append((note, note_type))
                        if note_highest is None:
                            note_highest = note + 12
                    elif note_type == 9 and note_highest:
                        chord_list["notes"].append((note, note_type))
                if note_highest and note >= note_highest:
                    break
                idx += 1
            self.chord_lists.append(chord_list)
        # メインループ
        items = []
        for loc in range(16 * 4):
            items.append([None for _ in range(19)])
            (chord_idx, _) = self.get_chord(loc)
            chord_list = self.chord_lists[chord_idx]
            item = items[loc]
            tick = loc % 16  # 拍(0-15)
            if loc == 0:  # 最初の行（セットアップ）
                item[0] = parm["speed"]  # テンポ
                item[1] = 48  # 4/4拍子
                item[2] = 3  # 16分音符
                item[3] = list_tones[parm["melo_tone"]][0]  # メロディ音色
                item[4] = 5  # メロディ音量
                item[5] = 14  # メロディ音長
                item[7] = 7  # ベース音色
                item[8] = 7  # ベース音量
                item[9] = parm["base_quantize"]  # ベース音長
                if no_drum:
                    item[11] = item[3]  # リバーブ音色
                    item[12] = 2  # リバーブ音量
                    item[13] = item[5]
                else:
                    item[12] = 5  # ドラム音量
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

        while make_melody:
            prev_chord_idx = -1  # 直前のコード
            self.prev_note = -1  # 直前のメロディー音
            self.first_note = True  # 小説の頭のノート
            self.melody_notes = [-2 for _ in range(16 * 4)]
            for loc in range(16 * 4):
                (chord_idx, next_chord_loc) = self.get_chord(loc)
                if chord_idx > prev_chord_idx:
                    chord_list = self.chord_lists[chord_idx]
                    prev_chord_idx = chord_idx
                    self.first_note = True
                # メロディー音設定
                if self.melody_notes[loc] != -2:
                    continue  # すでに埋まっていたらスキップ
                note_len_seed = px.rndf(0.0, 1.0)
                note_len = 1
                beat = loc % 4
                if (
                    note_len_seed < parm["melo_4_rate"]
                    and loc + 3 < next_chord_loc
                    and (beat in [0, 2])
                    and (beat == 0 or px.rndf(0.0, 1.0) < parm["melo_jutout_rate"])
                ):
                    note_len = 4
                elif (
                    note_len_seed < parm["melo_4_rate"] + parm["melo_8_rate"]
                    and loc + 1 < next_chord_loc
                    and (beat in [0, 2] or px.rndf(0.0, 1.0) < parm["melo_jutout_rate"])
                ):
                    note_len = 2
                cur_idx = None  # 直前のメロディーのインデックスを今のコードリストと照合
                for idx, note in enumerate(chord_list["notes"]):
                    if self.prev_note == note[0]:
                        cur_idx = idx
                        break
                if px.rndf(0.0, 1.0) < parm["melo_rest_rate"]:  # 休符
                    self.put_melody(loc, -1, note_len)
                elif self.prev_note < 0 or cur_idx is None:  # 直前が休符 or コード切り替え
                    idx = self.get_jumping_tone(chord_list, self.first_note)
                    note = chord_list["notes"][idx][0]
                    self.put_melody(loc, note, note_len)
                elif (
                    self.prev_note >= 0
                    and px.rndf(0.0, 1.0) < parm["melo_continue_rate"]
                ):
                    self.put_melody(loc, None, note_len)
                else:
                    next_idx = self.get_jumping_tone(chord_list)
                    diff = abs(next_idx - cur_idx)
                    direction = 1 if next_idx > cur_idx else -1
                    if loc + diff * note_len >= next_chord_loc or diff > 5:
                        # コードが切り替わる/跳躍量が大きい場合、跳躍音を採用
                        note = chord_list["notes"][next_idx][0]
                        self.put_melody(loc, note, note_len)
                    elif diff == 0:
                        self.put_melody(loc, self.prev_note, note_len)
                    else:
                        cur_loc = loc
                        while next_idx != cur_idx:
                            cur_idx += direction
                            note = chord_list["notes"][cur_idx][0]
                            self.put_melody(cur_loc, note, note_len)
                            cur_loc += note_len
            # コード中の重要構成音が入っているかチェック
            cur_chord_idx = -1
            need_notes_list = []
            lack_notes = False
            for loc in range(16 * 4):
                (chord_idx, _) = self.get_chord(loc)
                if chord_idx > cur_chord_idx:
                    if len(need_notes_list) > 0:
                        lack_notes = True
                        break
                    cur_chord_idx = chord_idx
                    chord_list = self.chord_lists[chord_idx]["notes"]
                    need_notes_list = []
                    for chord in chord_list:
                        note = chord[0] % 12
                        if chord[1] == 1 and not note in need_notes_list:
                            need_notes_list.append(note)
                note = self.melody_notes[loc]
                if not note is None and note >= 0 and note % 12 in need_notes_list:
                    need_notes_list.remove(note % 12)
            if not lack_notes:
                break  # 合格

        # メロディーとリバーブパート
        for loc in range(16 * 4):
            item = items[loc]
            item[6] = self.melody_notes[loc]
            if no_drum:
                item[14] = self.melody_notes[(loc + 63) % 64]

        # 完了処理
        self.music = sounds.compile(items, self.tones, self.patterns)
        self.items = items
        with open(f"./musics/generator.json", "wt") as fout:
            fout.write(json.dumps(self.music))

    def get_chord(self, loc):
        chord_lists_cnt = len(self.chord_lists)
        next_chord_loc = 16 * 4
        for rev_idx in range(chord_lists_cnt):
            idx = chord_lists_cnt - rev_idx - 1
            if loc >= self.chord_lists[idx]["loc"]:
                break
            else:
                next_chord_loc = self.chord_lists[idx]["loc"]
        return idx, next_chord_loc

    def get_jumping_tone(self, chord_list, force_no_root=False):
        no_root = force_no_root or chord_list["no_root"]
        notes = chord_list["notes"]
        while True:
            idx = px.rndi(0, len(notes) - 1)
            allowed_types = [1, 3] if no_root else [1, 2, 3]
            if not notes[idx][1] in allowed_types:
                continue
            note = notes[idx][0]
            if self.prev_note >= 0:
                diff = abs(self.prev_note - note)
                if diff > 7 and diff != 12:
                    continue
            return idx

    def put_melody(self, loc, note, note_len=1):
        for idx in range(note_len):
            self.melody_notes[loc + idx] = note if idx == 0 else None
        if note is not None:
            self.prev_note = note
            self.first_note = False


list_tones = [
    (11, "Pulse solid"),
    (8, "Pulse thin"),
    (2, "Pulse soft"),
    (10, "Square solid"),
    (6, "Square thin (Harp)"),
    (4, "Square soft (Flute)"),
]
App()
