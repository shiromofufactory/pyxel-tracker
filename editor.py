import pyxel as px
import json
import os
import copy
import glob

from system import util
from system import sounds


class App:
    # ===============================================
    # Pyxelベース機能
    # ===============================================

    def __init__(self):
        self.outpath = os.path.abspath("./")
        px.init(256, 256, title="Pyxel Tracker", quit_key=px.KEY_NONE)
        self.loading = False
        with open("./help.txt", "rt", encoding="utf-8") as fin:
            self.help_texts = fin.read().split("\n")
        try:
            fin = open("./user/tones.json", "rt", encoding="utf-8")
        except:
            fin = open("./system/tones.json", "rt", encoding="utf-8")
        finally:
            self.tones = json.loads(fin.read())
        try:
            fin = open("./user/patterns.json", "rt", encoding="utf-8")
        except:
            fin = open("./system/patterns.json", "rt", encoding="utf-8")
        finally:
            self.patterns = json.loads(fin.read())
        self.pool = []
        self.redo_items = []
        self.music = []
        self.is_file_load = False
        self.is_file_save = False
        self.is_playing = False
        self.is_help_mode = False
        self.files = []
        self.file_cursol = 0
        self.file_pos = 0
        self.playing_row = 0
        self.playing_start = None
        self.is_tone_edit = False
        self.piano_octave = 2
        self.piano_tone = 0
        self.piano_key = None
        self.cx1 = 0
        self.crow1 = 0
        self.cx2 = 0
        self.crow2 = 0
        self.pos = 0
        self.is_range_mode = False
        self.params_cx = None
        self.params_x = 0
        self.params_y = 0
        self.params_width = 0
        self.params_height = 0
        self.params_cursol = 0
        self.tone_cursol = 0
        self.numstock = 0
        self.confirm_action = None
        self.confirm_txt = None
        self.confirm_cursol = None
        self.buffer = None
        self.flash_pat = False
        self.init_items()
        self.message = "Press [esc] to show help."
        px.run(self.update, self.draw)

    def update(self):
        self.is_cmd = px.btn(px.KEY_GUI) or px.btn(px.KEY_CTRL)
        if self.confirm_action:
            return self.manage_confirm()
        if self.is_help_mode:
            return self.update_help()
        if self.is_file_load or self.is_file_save:
            return self.manage_files()
        if not self.params_cx is None:
            return self.edit_params()
        self.manage_player()
        self.play_piano()
        self.manage_system()
        if self.is_tone_edit:
            self.edit_tone()
        else:
            self.edit_notes()

    def draw(self):
        px.cls(0)
        self.flash_pat = px.frame_count % 30 < 15
        if self.is_help_mode:
            return self.draw_help()
        if self.is_file_load or self.is_file_save:
            return self.draw_files()
        if self.message:
            px.text(20, 216, self.message, 7)
        self.draw_piano()
        if self.is_tone_edit:
            self.draw_tone()
        else:
            self.draw_notes()
            if not self.params_cx is None:
                self.draw_params()
        if self.confirm_txt:
            self.draw_confirm()

    # ===============================================
    # システム機能
    # ===============================================
    def manage_system(self):
        if not self.is_cmd:
            return
        if px.btnp(px.KEY_RETURN):
            self.playing_start = (
                None if self.playing_start == self.crow1 else self.crow1
            )
        if self.is_playing:
            return
        if px.btnp(px.KEY_N):
            self.set_confirm("Are you sure you want to initialize this project?", "new")
        if px.btnp(px.KEY_L):
            self.set_files()
            self.is_file_load = True
        if px.btnp(px.KEY_Z):
            if self.pool:
                self.redo_items.append(self.items)
                self.items = self.pool.pop()
                self.message = "Undoed."
                self.add_crow(0)
            else:
                self.message = "Cannot undo."
        if px.btnp(px.KEY_Y):
            if self.redo_items:
                self.pool.append(self.items)
                self.items = self.redo_items.pop()
                self.message = "Redoed."
                self.add_crow(0)
            else:
                self.message = "Cannot redo."
        if px.btnp(px.KEY_C):
            (x1, x2, y1, y2) = self.get_x12y12()
            buffer = []
            idx = 0
            while True:
                col1 = get_col(x1)
                col2 = get_col(x2 + 1)
                buffer.append(self.items[y1 + idx][col1:col2])
                idx += 1
                if y1 + idx > y2 or y1 + idx >= len(self.items):
                    break
            self.buffer = buffer
            self.is_range_mode = False
            self.message = "Copied."
        if px.btnp(px.KEY_V):
            if self.buffer is None:
                self.message = "No copied data."
                return
            self.push_pool()
            is_col_all = len(self.buffer[0]) > 4
            if is_col_all:
                base_col = 0
            elif self.cx1 == 0:
                self.message = "Cannot Paste."
                return
            else:
                base_col = get_col(self.cx1)
            for y, buffer in enumerate(self.buffer):
                for col, value in enumerate(buffer):
                    self.set_item(self.crow1 + y, base_col + col, value)
            self.add_crow(len(self.buffer))
            self.message = "Pasted."
        if px.btnp(px.KEY_O, 10, 2):
            self.transpose(1)
        if px.btnp(px.KEY_I, 10, 2):
            self.transpose(-1)

    def set_files(self):
        files = glob.glob("./projects/*.json")
        self.files = [file.split("/")[-1] for file in files]
        self.files.sort()

    def push_pool(self):
        self.pool.append(copy.deepcopy(self.items))
        self.redo_items = []
        if len(self.pool) > 30:
            self.pool.pop(0)

    def transpose(self, dist):
        (x1, x2, y1, y2) = self.get_x12y12()
        row = y1
        while True:
            for idx in range(x2 - x1 + 1):
                if x1 + idx > 0:
                    col = get_col(x1 + idx) + 3
                    value = self.items[row][col]
                    if type(value) is int and value >= 0:
                        new_value = util.range(value, dist, 59, 0)
                        self.set_item(row, col, new_value)
            row += 1
            if row > y2 or row >= len(self.items):
                break

    # ===============================================
    # ヘルプ
    # ===============================================

    def update_help(self):
        if px.btnp(px.KEY_ESCAPE) or px.btnp(px.KEY_RETURN):
            self.is_help_mode = False

    def draw_help(self):
        for y, text in enumerate(self.help_texts):
            px.text(2, 2 + y * 8, text, 7)

    # ===============================================
    # ファイルセレクタ
    # ===============================================

    def manage_files(self):
        if self.is_file_save:
            if px.btnp(px.KEY_ESCAPE):
                self.is_file_save = False
            if px.btnp(px.KEY_RETURN):
                if self.project:
                    self.init_play()
                self.is_file_save = False
            tmp_len = len(self.project)
            for key, value in dict_input.items():
                if px.btnp(key, 10, 2) and tmp_len < 15:
                    self.project += value
            if px.btnp(px.KEY_BACKSPACE, 10, 2) and tmp_len > 0:
                self.project = self.project[0 : tmp_len - 1]
        if self.is_file_load:
            if px.btnp(px.KEY_ESCAPE):
                self.is_file_load = False
            if px.btnp(px.KEY_RETURN):
                self.project = (
                    self.files[self.file_cursol]
                    .replace(".json", "")
                    .replace("projects\\", "")
                )
                self.crow1 = 0
                self.pos = 0
                with open(
                    f"./projects/{self.project}.json", "rt", encoding="utf-8"
                ) as fin:
                    self.items = json.loads(fin.read())
                    self.set_locs()
                    self.message = "File loaded."
                self.is_file_load = False
            keep_x = None
            idx = self.file_cursol
            udkey = util.udkey()
            if not udkey is None:
                keep_x = self.file_cursol % 4
                idx += udkey * 4
            rlkey = util.rlkey()
            if not rlkey is None:
                idx += rlkey
            if idx >= len(self.files):
                idx = 0 if keep_x is None else keep_x
            elif idx < 0:
                idx = len(self.files) - 1
                if not keep_x is None:
                    add_x = (4 + keep_x - len(self.files)) % 4
                    idx = len(self.files) - 4 + add_x
            self.file_cursol = idx

    def draw_files(self):
        idx = self.file_pos
        while idx < len(self.files):
            x, y = self.get_files_xy(idx)
            px.text(x + 2, y + 2, self.files[idx].replace(".json", ""), 7)
            idx += 1
        if self.is_file_load:
            px.text(2, 2, "Select project file", 7)
            x, y = self.get_files_xy(self.file_cursol)
            c = 7 if self.flash_pat else 12
            px.rectb(x, y, 63, 8, c)
        if self.is_file_save:
            px.text(2, 2, "Enter project name > " + self.project, 7)
            if len(self.project) < 15 and self.flash_pat:
                px.rect(2 + 21 * 4 + len(self.project) * 4, 2, 4, 5, 7)

    def get_files_xy(self, idx):
        return (idx % 4) * 4 * 16, (idx // 4) * 8 + 16

    # ===============================================
    # プレイヤー
    # ===============================================

    def manage_player(self):
        pressed = px.btnp(px.KEY_RETURN) and not self.is_cmd
        if self.is_playing:
            pos = px.play_pos(0) or px.play_pos(1) or px.play_pos(2) or px.play_pos(3)
            if pos is None:
                self.start_play(True)
            elif pressed:
                self.message = None
                px.stop()
                self.add_crow(self.playing_row - self.crow1)
                self.is_playing = False
            else:
                while self.items_tick[self.playing_row + 1] / 48 <= pos[1]:
                    self.playing_row += 1
        elif pressed:
            self.music = sounds.compile(self.items, self.tones, self.patterns)
            if not self.project:
                self.set_files()
                self.is_file_save = True
                return
            self.init_play()

    def init_play(self):
        with open(
            f"{self.outpath}/projects/{self.project}.json", "wt", encoding="utf-8"
        ) as fout:
            fout.write(json.dumps(self.items))
        with open(
            f"{self.outpath}/musics/{self.project}.json", "wt", encoding="utf-8"
        ) as fout:
            fout.write(json.dumps(self.music))
        with open(f"{self.outpath}/user/tones.json", "wt", encoding="utf-8") as fout:
            fout.write(json.dumps(self.tones))
        self.message = "Saved."
        for ch, sound in enumerate(self.music):
            px.sound(ch).set(*sound)
        self.start_play()
        self.is_playing = True
        self.is_range_mode = False

    def start_play(self, is_loop=False):
        if is_loop:
            row = 0 if self.playing_start is None else self.playing_start
        else:
            row = self.crow1 % len(self.items)
        tick = int(self.items_tick[row] / 48)
        self.playing_row = row
        for ch in range(4):
            px.play(ch, [ch], tick)

    # ===============================================
    # ピアノ
    # ===============================================

    def play_piano(self):
        if self.is_cmd or self.is_range_mode or self.is_playing:
            return
        for key, value in dict_playkey.items():
            if px.btnp(key):
                octave = self.piano_octave + value[1]
                if octave >= 0 and octave <= 4:
                    note = octave * 12 + value[5]
                    self.play_piano_note(key, note, None)
        (key, value) = util.numkey()
        if not key is None:
            for pattern in self.patterns:
                if pattern["key"] == ":" + str(value):
                    self.play_piano_note(key, None, pattern)
        if not self.piano_key is None and px.btnr(self.piano_key):
            px.play(0, [0], tick=480)
            self.piano_key = None
        rest_pressed = px.btnp(px.KEY_R) or px.btnp(px.KEY_MINUS)
        channel = self.cx1 - 1
        if not self.is_tone_edit and channel >= 0 and rest_pressed:
            self.set_note(channel, -1)
        if px.btn(px.KEY_ALT):
            self.piano_octave = util.range(self.piano_octave, util.rlkey(), 4, 0)

    def draw_piano(self):
        project = (
            f"[{self.project.replace('.json', '')}]" if self.project else "(no name)"
        )
        px.text(184, 232, project, 12)
        px.rect(20, 240, 209, 16, 7)
        for x in range(34):
            px.line(25 + x * 6, 240, 25 + x * 6, 255, 0)
        for o in range(5):
            px.rect(23 + o * 42, 240, 5, 9, 0)
            px.rect(29 + o * 42, 240, 5, 9, 0)
            px.rect(41 + o * 42, 240, 5, 9, 0)
            px.rect(47 + o * 42, 240, 5, 9, 0)
            px.rect(53 + o * 42, 240, 5, 9, 0)
        base_x = 21 + self.piano_octave * 42
        for key, value in dict_playkey.items():
            octave = self.piano_octave + value[1]
            if octave >= 0 and octave <= 4:
                x = base_x + value[2]
                y = 240 + value[3]
                if key == self.piano_key:
                    px.rect(x, y, 3, 5, 11)
                else:
                    px.text(x, y, value[4], 11)
        for idx, pattern in enumerate(self.patterns):
            x = 20 + idx * 20
            px.text(x, 232, pattern["abbr"] + pattern["key"], 11)
        c_rs = 13 if self.piano_octave >= 4 else 11
        c_ls = 13 if self.piano_octave <= 0 else 11
        px.text(234, 244, ">>", c_rs)
        px.text(8, 244, "<<", c_ls)

    def play_piano_note(self, key, note, pattern):
        state = {
            "note_cnt": 1,
            "tone": self.piano_tone,
            "volume": 7,
            "quantize": 0.5,
            "duration": 0,
            "note": note,
            "is_rest": False,
            "pattern": pattern,
            "tick": 0,
        }
        result = {}
        sounds.putNotes(960 * 48, state, self.tones, result)
        px.sound(0).set(
            result["note"],
            result["tone"],
            result["volume"],
            result["effect"],
            1,
        )
        px.play(0, [0])
        self.piano_key = key
        channel = self.cx1 - 1
        if not self.is_tone_edit and channel >= 0:
            value = note if not note is None else pattern["key"]
            self.set_note(channel, value)

    # ===============================================
    # 音色
    # ===============================================

    def edit_tone(self):
        if px.btnp(px.KEY_TAB) or px.btnp(px.KEY_ESCAPE):
            self.is_tone_edit = False
        udkey = util.udkey()
        if not udkey is None:
            self.tone_cursol = util.loop(self.tone_cursol, udkey, 7)
            self.numstock = 0
        tone = self.tones[self.piano_tone]
        tone_key = list_parm[self.tone_cursol]
        if px.btnp(px.KEY_BACKSPACE):
            tone[tone_key] = 0
            self.numstock = 0
        rlkey = util.rlkey()
        if not rlkey is None:
            tone = self.tones[self.piano_tone]
            self.numstock = 0
            if self.tone_cursol == 0:
                self.piano_tone = util.loop(self.piano_tone, rlkey, len(self.tones))
            elif self.tone_cursol == 1:
                idx_wave = list_wave.index(tone["wave"])
                idx_wave = util.loop(idx_wave, rlkey, len(list_wave))
                self.update_tone(list_wave[idx_wave])
            else:
                self.update_tone(tone[tone_key] + rlkey)
        if self.tone_cursol > 1:
            (_, value) = util.numkey()
            if not value is None:
                self.update_tone(self.numstock * 10 + value)
                self.numstock = tone[tone_key]
        else:
            tmp_len = len(tone["name"])
            for key, value in dict_input.items():
                if px.btnp(key, 10, 2) and tmp_len < 15:
                    tone["name"] += value
            if px.btnp(px.KEY_BACKSPACE, 10, 2) and tmp_len > 0:
                tone["name"] = tone["name"][0 : tmp_len - 1]

    def draw_tone(self):
        draw_window(16, 16, 224, 152)
        tone = None
        for idx, tmp_tone in enumerate(self.tones):
            y = 24 + idx * 8
            c = 13
            if self.piano_tone == idx:
                tone = tmp_tone
                c = 7
            px.text(24, y, str(idx).ljust(2) + ":" + tmp_tone["name"], c)
        y_base = 24
        x_base = 104
        px.text(x_base, y_base, str(self.piano_tone).ljust(2) + ":" + tone["name"], 7)
        px.text(x_base, y_base + 8, "tone        [PSTN]", 6)
        px.text(x_base, y_base + 16, "attack      ticks", 6)
        px.text(x_base, y_base + 24, "decay       ticks", 6)
        px.text(x_base, y_base + 32, "sustain     %", 6)
        px.text(x_base, y_base + 40, "release     ticks", 6)
        px.text(x_base, y_base + 48, "vibrato     ticks", 6)
        for idx, parm in enumerate(list_parm):
            if not parm is None:
                px.text(x_base + 32, y_base + idx * 8, str(tone[parm]), 7)
        # ADSRグラフ
        attack = tone["attack"]
        decay = tone["decay"]
        sustain = tone["sustain"] / 100
        release = tone["release"]
        vibrato = tone["vibrato"]
        len_sus = max(vibrato + 60 - attack - decay, 60)
        scale = max(attack + decay + len_sus + release, vibrato)
        if vibrato > 0:
            x = vibrato * 112 / scale + x_base
            y = 160 - sustain * 64
            px.line(x, 96, x, 160, 9)
            px.text(x, 162, "vib >>", 9)
        if scale > 60 or sustain > 0:
            draw_adsr(0, attack, 0, 1, scale, 7)
            draw_adsr(attack, decay, 1, sustain, scale, 7)
            draw_adsr(attack + decay, len_sus, sustain, sustain, scale, 11, "sus")
            draw_adsr(attack + decay + len_sus, release, sustain, 0, scale, 3)
        # カーソル
        self.draw_cursol(x_base - 4, 22 + self.tone_cursol * 8, 80)
        # 音色名入力ロケータ
        if self.tone_cursol == 0:
            if len(tone["name"]) < 15 and self.flash_pat:
                px.rect(x_base + (3 + len(tone["name"])) * 4, y_base, 4, 5, 7)

    def update_tone(self, value):
        tone = self.tones[self.piano_tone]
        key = list_parm[self.tone_cursol]
        if key == "attack" or key == "decay" or key == "release" or key == "vibrato":
            tone[key] = max(min(value, 240), 0)
        elif key == "sustain":
            tone[key] = max(min(value, 100), 0)
        else:
            tone[key] = value

    # ===============================================
    # ノート編集
    # ===============================================

    def edit_notes(self):
        if px.btnp(px.KEY_ESCAPE):
            self.is_help_mode = True
        if px.btnp(px.KEY_AT):
            self.open_params()
        if px.btnp(px.KEY_TAB):
            self.numstock = 0
            self.is_tone_edit = True
        if px.btnp(px.KEY_SPACE, 10, 2):
            self.set_note(self.cx1 - 1, None)
        if px.btnp(px.KEY_BACKSPACE, 10, 2):
            if self.cx1 == 0 and self.crow1 == 0:
                return
            col1 = get_col(self.cx1)
            col2 = get_col(self.cx1 + 1) - 1
            is_deleted = False
            while col1 <= col2:
                if self.crow1 >= len(self.items):
                    break
                if not is_deleted and not self.items[self.crow1][col1] is None:
                    is_deleted = True
                    self.push_pool()
                self.set_item(self.crow1, col1, None)
                col1 += 1
            self.auto_delete_rows()
            self.add_crow(-1, True)
        if px.btnp(px.KEY_SHIFT):
            self.is_range_mode = not self.is_range_mode
        ud_key = util.udkey()
        if not ud_key is None:
            if self.is_cmd:
                if ud_key < 0:
                    dist_row = self.get_prev_loc(self.crow1 - 1)
                elif self.crow1 >= len(self.items):
                    dist_row = 0
                else:
                    dist_row = self.get_next_loc(self.crow1) + 1
                self.add_crow(dist_row - self.crow1)
            else:
                self.add_crow(ud_key)
        if not px.btn(px.KEY_ALT):
            self.cx1 = util.loop(self.cx1, util.rlkey(), 5)
        wheel = px.mouse_wheel
        if wheel != 0:
            self.add_crow(-wheel, True)
        if self.is_range_mode:
            self.cx2 = self.cx1 if self.cx1 > 0 else 4
        else:
            self.cx2 = self.cx1
            self.crow2 = self.crow1
        if self.cx1 > 0:
            self.piano_tone = self.piano_tones[self.crow1][self.cx1 - 1]

    def draw_notes(self):
        # 再生インジケータ
        if self.is_playing:
            play_row = self.playing_row - self.pos
            if play_row > 12:
                self.pos += play_row - 12
                play_row = self.playing_row - self.pos
            elif play_row < 0:
                self.pos += play_row
                play_row = self.playing_row - self.pos
            px.rect(0, base_y + (play_row + 1) * 8, 256, 8, 1)
        # 枠
        last_row = min(len(self.items) - self.pos, 25)
        last_y = base_y + (last_row + 1) * 8 - 1
        for x in tpl_vline_p:
            px.line(x, base_y, x, last_y, 5)
        for x in tpl_vline_s:
            px.line(x, base_y, x, last_y, 1)
        # データ
        loc = 0
        tick = 0
        saved_item = copy.deepcopy(item_empty)
        for item_idx in range(len(self.items)):
            item = self.items[item_idx]
            for i, data in enumerate(item):
                if not data is None:
                    saved_item[i] = item[i]
            loc_size = saved_item[1]
            tick += saved_item[2]
            if tick == loc_size:
                tick = 0
            pos = item_idx - self.pos
            if pos >= 0 and pos < 25:
                y = base_y + 9 + 8 * pos
                c = 9
                if loc != self.locs[item_idx]:
                    loc = self.locs[item_idx]
                    c = 10
                s = "<<" if item_idx == self.playing_start else str(loc)
                px.text(tpl_cx[19] * 4 + 1, y, s, c)
                for i, data in enumerate(item):
                    if pos == 0:
                        self.draw_item(y, i, saved_item[i], not data is None)
                    else:
                        self.draw_item(y, i, data, True)
                beat_size = dict_beat[loc_size]
                c = 1
                if tick == 0:
                    c = 10
                elif tick % (loc_size // beat_size) == 0:
                    c = 5
                y = base_y + 7 + pos * 8 + 8
                px.line(0, y, 255, y, c)
        # カーソル
        if not self.is_playing:
            (x1, x2, y1, y2) = self.get_x12y12()
            x, y = self.get_xy(x1, y1)
            w = tpl_cx[get_col(x2 + 1)] * 4 - x - 2
            h = (y2 - y1 + 1) * 8 - 1
            if not self.is_range_mode or px.frame_count % 10 < 8:
                px.rectb(x, y, w, h, 7)
        # 固定ヘッダ
        px.rect(0, base_y, 256, 8, 1)
        px.text(1, base_y + 1, "BPM x/x Tick", 11)
        px.text(53, base_y + 1, "@1 V Qu Nte @2 V Qu Nte @3 V Qu Nte @4 V Qu Nte", 6)
        px.text(245, base_y + 1, "Loc", 10)

    # ===============================================
    # パラメータ編集
    # ===============================================

    def open_params(self):
        x, y = self.get_xy(self.cx1, self.crow1)
        self.params_width = 160 if self.cx1 > 0 else 64
        self.params_height = 30
        self.params_x = x + 2
        if self.params_x + self.params_width >= 254:
            self.params_x = 254 - self.params_width
        self.params_y = y + 10
        if self.params_y + self.params_height >= 254:
            self.params_y = y - 4 - self.params_height
        self.params_saved = repr(self.items)
        self.push_pool()
        self.params_cursol = 1 if self.cx1 > 0 else 2
        self.numstock = 0
        self.params_cx = self.cx1

    def close_params(self):
        self.params_cx = None
        self.auto_add_rows(len(self.items) - 1)
        self.auto_delete_rows()

    def edit_params(self):
        if px.btnp(px.KEY_RETURN) or px.btnp(px.KEY_AT) or px.btnp(px.KEY_ESCAPE):
            if repr(self.items) == self.params_saved:
                self.pool.pop(len(self.pool) - 1)
            self.close_params()
        if px.btnp(px.KEY_TAB):
            self.numstock = 0
            self.close_params()
            self.is_tone_edit = True
        if px.btnp(px.KEY_BACKSPACE):
            self.set_item(self.crow1, self.get_params_col(), None)
            self.auto_delete_rows()
            self.numstock = 0
        udkey = util.udkey()
        if not udkey is None:
            self.params_cursol = util.loop(self.params_cursol, udkey, 3)
            self.numstock = 0
        if self.cx1 == 0:
            self.set_params_base(util.rlkey())
        else:
            self.set_params_channel(util.rlkey(), util.numkey()[1])

    def draw_params(self):
        x = self.params_x
        y = self.params_y
        item = self.get_item(self.crow1)
        draw_window(x, y, self.params_width, self.params_height)
        self.draw_cursol(x + 2, y + 2 + self.params_cursol * 8, self.params_width - 4)
        col = get_col(self.cx1)
        if self.cx1 == 0:
            px.text(x + 4, y + 4, "BPM  =", 6)
            px.text(x + 32, y + 4, get_bpm(item[col]), 6)
            c_beat = 6 if self.is_col_first() else 13
            px.text(x + 4, y + 12, "Beat =", c_beat)
            px.text(x + 32, y + 12, get_beat(item[col + 1]), c_beat)
            px.text(x + 4, y + 20, "Tick =", 6)
            px.text(x + 32, y + 20, get_tick(item[col + 2]), 6)
        else:
            px.text(x + 4, y + 4, "Instrument =    (0-15)", 6)
            if not item[col] is None:
                px.text(x + 56, y + 4, str(item[col]), 6)
                tone = self.tones[item[col]]
                px.text(x + 96, y + 4, tone["name"], 6)
            px.text(x + 4, y + 12, "Volume     =    (1-7)", 6)
            px.text(x + 56, y + 12, str(item[col + 1] or ""), 6)
            px.text(x + 4, y + 20, "Quantize   =    (1-16)", 6)
            px.text(x + 56, y + 20, str(item[col + 2] or ""), 6)

    def set_params_base(self, dist):
        if dist is None:
            return
        item = self.get_item(self.crow1)
        col = self.get_params_col()
        value = item[col]
        if self.params_cursol == 0:
            new_value = util.range(value, -dist * 8, 432, 120)
        elif self.params_cursol == 1:
            if not self.is_col_first():
                return
            old_value = list_beat[0] if value is None else list_beat.index(value)
            new_idx = util.loop(old_value, dist, len(list_beat))
            new_value = list_beat[new_idx]
        else:
            old_value = list_tick[0] if value is None else list_tick.index(value)
            new_idx = util.loop(old_value, dist, len(list_tick))
            new_value = list_tick[new_idx]
        self.set_item(self.crow1, col, new_value)

    def set_params_channel(self, dist, num):
        if dist is None and num is None:
            return
        item = self.get_item(self.crow1)
        col = self.get_params_col()
        value = item[col]
        max_val = (15, 7, 16)[self.params_cursol]
        min_val = (0, 1, 1)[self.params_cursol]
        if not dist is None:
            new_value = util.range(value, dist, max_val, min_val)
            self.numstock = 0
        if not num is None:
            self.numstock = self.numstock * 10 + num
            new_value = min(self.numstock, max_val)
            self.numstock = new_value
        self.set_item(self.crow1, col, new_value)

    def get_params_col(self):
        return get_col(self.cx1) + self.params_cursol

    def is_col_first(self):
        return self.crow1 == 0 or self.locs[self.crow1] > self.locs[self.crow1 - 1]

    # ===============================================
    # confirmウィンドウ
    # ===============================================

    def manage_confirm(self):
        if self.confirm_txt is None:
            if self.confirm_action == "new":
                self.push_pool()
                self.init_items()
                self.message = "Data initialized."
            self.confirm_action = None
        else:
            self.confirm_cursol = util.loop(self.confirm_cursol, util.rlkey(), 2)
            if px.btnp(px.KEY_RETURN):
                if self.confirm_cursol == 1:
                    self.confirm_action = None
                self.confirm_txt = None

    def draw_confirm(self):
        width = len(self.confirm_txt) * 4 + 8
        height = 3 * 8 + 8
        x = 128 - width / 2
        y = 128 - height / 2
        draw_window(x, y, width, height)
        px.text(x + 4, y + 4, self.confirm_txt, 7)
        px.text(128 - 16, y + 20, "yes", 7)
        px.text(128 + 18, y + 20, "no", 7)
        self.draw_cursol(128 - 18 + self.confirm_cursol * 32, y + 19, 16)

    def set_confirm(self, txt, action):
        self.message = None
        self.confirm_cursol = 0
        self.confirm_txt = txt
        self.confirm_action = action

    # ===============================================
    # 汎用
    # ===============================================

    def add_crow(self, dist, no_loop=False):
        if dist is None:
            return
        value = self.crow1
        max_value = len(self.items)
        if no_loop:
            new_value = util.range(value, dist, max_value, 0)
        else:
            new_value = util.loop(value, dist, max_value + 1, 0)
        self.crow1 = new_value
        pos = new_value - self.pos
        if pos < 0:
            self.pos += pos
        if pos >= 24:
            self.pos += pos - 24

    def get_xy(self, cx, cy):
        x = tpl_cx[get_col(cx)] * 4
        y = base_y + 8 + (cy - self.pos) * 8
        return x, y

    def get_x12y12(self):
        if self.cx1 <= self.cx2:
            x1 = self.cx1
            x2 = self.cx2
        else:
            x1 = self.cx2
            x2 = self.cx1
        if self.crow1 <= self.crow2:
            y1 = self.crow1
            y2 = self.crow2
        else:
            y1 = self.crow2
            y2 = self.crow1
        return (x1, x2, y1, y2)

    def get_next_loc(self, row):
        dist_row = row
        self.set_locs()
        loc = self.locs[row]
        while self.locs[dist_row + 1] == loc:
            dist_row += 1
        return dist_row

    def get_prev_loc(self, row):
        dist_row = row
        loc = self.locs[row]
        while dist_row > 0 and self.locs[dist_row - 1] == loc:
            dist_row -= 1
        return dist_row

    def set_locs(self):
        speed = 0
        loc = 1
        tick = 0
        tick_total = 0
        loc_size = 0
        tick_size = 0
        idx = 0
        locs = []
        items_tick = []
        piano_tones = []
        current_tones = [0, 0, 0, 0]
        while True:
            item = self.get_item(idx)
            items_tick.append(tick_total)
            locs.append(loc)
            current_tones = copy.deepcopy(current_tones)
            if not item[0] is None:
                speed = item[0]
            if not item[1] is None:
                loc_size = item[1]
            if not item[2] is None:
                tick_size = item[2]
            for ch in range(4):
                tone = item[3 + ch * 4]
                if not tone is None:
                    current_tones[ch] = tone
            piano_tones.append(current_tones)
            tick += tick_size
            tick_total += speed * tick_size
            if tick >= loc_size:
                tick -= loc_size
                loc += 1
                if len(self.items) <= idx:
                    locs.append(loc)
                    break
            idx += 1
        items_tick.append(tick_total)
        self.piano_tones = piano_tones
        self.items_tick = items_tick
        self.locs = locs

    def init_items(self):
        items = []
        items.append(copy.deepcopy(item_empty))
        items[0][0] = 240
        items[0][1] = 48
        items[0][2] = 6
        self.project = ""
        self.items = items
        self.crow1 = 0
        self.pos = 0
        self.set_item(0, 3, None)
        self.set_locs()

    def get_item(self, row):
        return self.items[row] if row < len(self.items) else copy.deepcopy(item_empty)

    def set_item(self, row, col, data):
        self.message = None
        self.auto_add_rows(row)
        self.items[row][col] = data
        self.set_locs()

    def auto_add_rows(self, row):
        dist_row = self.get_next_loc(row)
        while dist_row > len(self.items) - 1:
            self.items.append(copy.deepcopy(item_empty))

    def auto_delete_rows(self):
        if not self.params_cx is None:
            return
        loop = True
        while loop:
            loc = self.get_prev_loc(len(self.items) - 1)
            next_loc = self.get_next_loc(loc) + 1
            locs = next_loc - loc
            while loc < next_loc:
                for data in self.get_item(loc):
                    if not data is None:
                        loop = False
                        break
                else:
                    loc += 1
                    continue
                loop = False
                break
            else:
                del self.items[-locs:]

    def draw_item(self, y, i, data, is_real):
        if not data is None:
            x = tpl_cx[i] * 4 + 1
            if i == 0:
                txt = get_bpm(data)
            elif i == 1:
                txt = get_beat(data)
            elif i == 2:
                txt = get_tick(data)
            elif i % 4 == 2:
                if type(data) == int:
                    txt = "-" if data < 0 else tpl_note[data % 12] + str(data // 12)
                else:
                    for pattern in self.patterns:
                        if pattern["key"] == data:
                            txt = pattern["abbr"]
            else:
                txt = str(data)
            if i <= 2:
                c = 11 if is_real else 3
            else:
                c = 6 if is_real else 12
            px.text(x, y, txt, c)

    def set_note(self, channel, note):
        if channel >= 0:
            self.push_pool()
            self.set_item(self.crow1, channel * 4 + 6, note)
            if note is None:
                self.auto_delete_rows()
        self.add_crow(1)

    def draw_cursol(self, x, y, width):
        c = 7 if self.flash_pat else 12
        px.rectb(x, y, width, 9, c)


def get_col(x):
    return {0: 0, 1: 3, 2: 7, 3: 11, 4: 15, 5: 19}[x]


def get_bpm(data):
    if data is None:
        return ""
    return str(28800 // data)


def get_beat(data):
    if data is None:
        return ""
    denominator = 48 // (data // dict_beat[data])
    return str(dict_beat[data]) + "/" + str(denominator)


def get_tick(data):
    if data is None:
        return ""
    return "1/" + str(48 // data)


def draw_window(x, y, width, height):
    px.rect(x, y, width, height, 1)
    px.rectb(x, y, width, height, 7)


def draw_adsr(start, length, v1, v2, scale, col, txt=None):
    x1 = start * 120 / scale + 104
    y1 = 160 - v1 * 64
    x2 = (start + length) * 120 / scale + 104
    y2 = 160 - v2 * 64
    px.line(x1, y1, x2, y2, col)
    if txt and v1 > 0:
        px.text((x1 + x2) / 2 - 6, y1 - 6, txt, col)


dict_input = {
    px.KEY_A: "a",
    px.KEY_B: "b",
    px.KEY_C: "c",
    px.KEY_D: "d",
    px.KEY_E: "e",
    px.KEY_F: "f",
    px.KEY_G: "g",
    px.KEY_H: "h",
    px.KEY_I: "i",
    px.KEY_J: "j",
    px.KEY_K: "k",
    px.KEY_L: "l",
    px.KEY_M: "m",
    px.KEY_N: "n",
    px.KEY_O: "o",
    px.KEY_P: "p",
    px.KEY_Q: "q",
    px.KEY_R: "r",
    px.KEY_S: "s",
    px.KEY_T: "t",
    px.KEY_U: "u",
    px.KEY_V: "v",
    px.KEY_W: "w",
    px.KEY_X: "x",
    px.KEY_Y: "y",
    px.KEY_Z: "z",
    px.KEY_0: "0",
    px.KEY_1: "1",
    px.KEY_2: "2",
    px.KEY_3: "3",
    px.KEY_4: "4",
    px.KEY_5: "5",
    px.KEY_6: "6",
    px.KEY_7: "7",
    px.KEY_8: "8",
    px.KEY_9: "9",
    px.KEY_SPACE: " ",
    px.KEY_MINUS: "-",
    px.KEY_UNDERSCORE: "_",
}


dict_playkey = {
    px.KEY_A: ("g#", -1, -15, 2, "A", 8),
    px.KEY_Z: ("a", -1, -12, 10, "Z", 9),
    px.KEY_S: ("a#", -1, -9, 2, "S", 10),
    px.KEY_X: ("b", -1, -6, 10, "X", 11),
    px.KEY_C: ("c", 0, 0, 10, "C", 0),
    px.KEY_F: ("c#", 0, 3, 2, "F", 1),
    px.KEY_V: ("d", 0, 6, 10, "V", 2),
    px.KEY_G: ("d#", 0, 9, 2, "G", 3),
    px.KEY_B: ("e", 0, 12, 10, "B", 4),
    px.KEY_N: ("f", 0, 18, 10, "N", 5),
    px.KEY_J: ("f#", 0, 21, 2, "J", 6),
    px.KEY_M: ("g", 0, 24, 10, "M", 7),
    px.KEY_K: ("g#", 0, 27, 2, "K", 8),
    px.KEY_COMMA: ("a", 0, 30, 10, ",", 9),
    px.KEY_L: ("a#", 0, 33, 2, "L", 10),
    px.KEY_PERIOD: ("b", 0, 36, 10, ".", 11),
    px.KEY_SLASH: ("c", 1, 42, 10, "/", 0),
    px.KEY_COLON: ("c#", 1, 45, 2, ":", 1),
    px.KEY_UNDERSCORE: ("d", 1, 48, 10, "_", 2),
    px.KEY_RIGHTBRACKET: ("d#", 1, 51, 2, "]", 3),
}

list_beat = [6, 12, 18, 24, 30, 36, 42, 48, 60]
dict_beat = {6: 1, 12: 1, 18: 3, 24: 2, 30: 5, 36: 3, 42: 7, 48: 4, 60: 5}
list_tick = [12, 8, 6, 4, 3, 2, 1]
list_wave = ["P", "S", "T", "N"]
list_parm = [None, "wave", "attack", "decay", "sustain", "release", "vibrato"]
base_y = 0
tpl_vline_p = (50, 98, 146, 194, 242)
tpl_vline_s = (14, 30, 62, 70, 82, 110, 118, 130, 158, 166, 178, 206, 214, 226)
tpl_cx = (0, 4, 8, 13, 16, 18, 21, 25, 28, 30, 33, 37, 40, 42, 45, 49, 52, 54, 57, 61)
tpl_note = ("c ", "c#", "d ", "d#", "e ", "f ", "f#", "g ", "g#", "a ", "a#", "b ")
item_empty = [None for _ in range(19)]

App()
