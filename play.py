import pyxel
import json

MUSIC_FILE = "sample"


class App:
    def __init__(self):
        pyxel.init(160, 120, title="Pyxel Tracker Player")
        with open(f"./musics/{MUSIC_FILE}.json", "rt") as fin:
            self.music = json.loads(fin.read())
        pyxel.run(self.update, self.draw)

    def update(self):
        if pyxel.btnp(pyxel.KEY_SPACE):
            if pyxel.play_pos(0) is None:
                for ch, sound in enumerate(self.music):
                    pyxel.sound(ch).set(*sound)
                    pyxel.play(ch, ch, loop=True)
            else:
                pyxel.stop()
        if pyxel.btnp(pyxel.KEY_ESCAPE):
            pyxel.quit()

    def draw(self):
        pyxel.cls(0)
        pyxel.text(20, 54, "Press [SPACE] to play / stop.", 7)
        pyxel.text(20, 60, "Press [ESC] to exit.", 7)


App()
