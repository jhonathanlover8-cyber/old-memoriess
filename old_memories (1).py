#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OLD MEMORIES  -  Etapa final (v2.0)
Tema: Ciudadania digital (alfabetizacion digital, pensamiento critico y habilidades tecnicas)

Novedades v2.0:
  - Personajes rediseñados (el ayudante ahora es un demonio y Ella una entidad fantasmal).
  - 7 pisos: ahora hay un GIMNASIO (piso 6) y un COLISEO (piso 7).
  - Si el ayudante te pierde de vista, se teletransporta a otro piso.
  - Casilleros para esconderse + minijuego de pulso (mantén ESPACIO para respirar).
  - Mas NPC con quienes hablar (y que a veces te regalan objetos).
  - Cuenta regresiva de 5 min: la entidad abandona su puesto y te caza 1 min (y el ayudante se retira).
    Contra ella solo sirve lanzarle un objeto para que pierda tu rastro.

Requisitos:  pip install pygame
Ejecutar:    python old_memories.py

Todos los graficos se dibujan por codigo (vectorial suavizado), no necesitas archivos externos.
"""
import math
import random
import sys
from array import array
from collections import deque

import pygame

# ----------------------------------------------------------------------------
# CONSTANTES
# ----------------------------------------------------------------------------
W, H = 1280, 720
FPS = 60
WORLD_W, WORLD_H = 2400, 900
CELL = 30
FLOORS = 7
FLOOR_COLORS = [(79, 195, 247), (129, 199, 132), (255, 183, 77), (186, 104, 200), (229, 115, 115),
                (190, 230, 80), (230, 190, 110)]
FLOOR_NAMES = ["", "", "", "", "", "GIMNASIO", "COLISEO"]
GYM_ROOMS = ["SALA DE PESAS", "CANCHA", "ZONA DE YOGA", "SPINNING"]
COL_ROOMS = ["ARENA NORTE", "ARMERÍA", "PALCO IMPERIAL", "CALABOZOS"]
DIFFS = ["Fácil", "Normal", "Difícil"]
COUNTDOWN = 300.0   # 5 minutos
HUNT_TIME = 60.0    # 1 minuto

CORR = pygame.Rect(120, 360, 2160, 180)
ROOMS = [pygame.Rect(300, 60, 560, 280), pygame.Rect(1300, 60, 560, 280),
         pygame.Rect(600, 560, 560, 280), pygame.Rect(1600, 560, 560, 280)]
DOORS = [pygame.Rect(r.centerx - 50, 336, 100, 28) if r.y < CORR.y
         else pygame.Rect(r.centerx - 50, 536, 100, 28) for r in ROOMS]
WALK = [CORR] + ROOMS + DOORS
PAD = (1200, 450)
ENTITY_POS = (230, 452)
FIRE_POS = (2250, 450)
STOVE_RECT = pygame.Rect(1900, 364, 170, 56)


def make_lockers():
    out = []
    for x in range(CORR.x + 10, CORR.right - 40, 92):
        if any(d.x - 4 < x + 38 and x < d.right + 4 for d in DOORS):
            continue
        if any(abs(x + 19 - (r.centerx + 150)) < 100 for r in ROOMS[:2]):
            continue
        out.append(pygame.Rect(x, 336, 38, 24))
    return out


LOCKERS = make_lockers()

SUBJECTS = ["Informática", "Sociales", "Matemáticas", "Lengua", "Ciencias", "Arte", "Inglés", "Física"]
INGREDIENTS = ["Plátano", "Yuca", "Papa", "Mazorca", "Pollo", "Cilantro"]
DISTRACT = ["Desinfectante", "Desodorante", "Gas pimienta", "Sándwich"]
DIST_INFO = {
    "Desinfectante": ("Lo rocías en los ojos: queda aturdido 4 s.", 230, 4.0),
    "Desodorante": ("Nube asfixiante: queda aturdido 3 s.", 210, 3.0),
    "Gas pimienta": ("¡Directo a la cara! Aturdido 7 s.", 250, 7.0),
    "Sándwich": ("Lanzas el sándwich: se distrae comiendo 6 s.", 450, 6.0),
}

# ----------------------------------------------------------------------------
# UTILIDADES
# ----------------------------------------------------------------------------
_fonts = {}


def F(size, bold=False):
    k = (size, bold)
    if k not in _fonts:
        _fonts[k] = pygame.font.SysFont("segoeui,helveticaneue,ubuntu,dejavusans,arial", size, bold=bold)
    return _fonts[k]


def lerp(a, b, t):
    return a + (b - a) * t


def lerpc(c1, c2, t):
    return tuple(int(lerp(c1[i], c2[i], t)) for i in range(3))


def clamp(v, a, b):
    return max(a, min(b, v))


def shade(c, k):
    return tuple(int(clamp(v * k, 0, 255)) for v in c[:3])


def text(s, t, size, color, pos, anchor="topleft", bold=False, shadow=True, alpha=255):
    f = F(size, bold)
    if shadow:
        sh = f.render(t, True, (0, 0, 0))
        sh.set_alpha(int(alpha * 0.6))
        s.blit(sh, sh.get_rect(**{anchor: (pos[0] + 2, pos[1] + 2)}))
    img = f.render(t, True, color)
    if alpha < 255:
        img.set_alpha(alpha)
    r = img.get_rect(**{anchor: pos})
    s.blit(img, r)
    return r


def wrap(t, size, width, bold=False):
    f = F(size, bold)
    lines, cur = [], ""
    for w in t.split(" "):
        test = (cur + " " + w).strip()
        if f.size(test)[0] <= width:
            cur = test
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    return lines


def para(s, t, size, color, x, y, width, lh=None, bold=False, shadow=False, center=False):
    lh = lh or int(size * 1.4)
    for ln in wrap(t, size, width, bold):
        if center:
            text(s, ln, size, color, (x + width // 2, y), "midtop", bold, shadow)
        else:
            text(s, ln, size, color, (x, y), "topleft", bold, shadow)
        y += lh
    return y


def para_reveal(s, t, n, size, color, x, y, width, lh, center=False):
    f = F(size)
    rem = n
    for ln in wrap(t, size, width):
        if rem <= 0:
            break
        seg = ln[:rem]
        rem -= len(ln) + 1
        xx = x + (width - f.size(ln)[0]) // 2 if center else x
        text(s, seg, size, color, (xx, y), "topleft", False, False)
        y += lh


def vgrad(w, h, c1, c2):
    s = pygame.Surface((w, h))
    for y in range(h):
        pygame.draw.line(s, lerpc(c1, c2, y / max(1, h - 1)), (0, y), (w, y))
    return s


def rrect(s, color, rect, r=10, bw=0, bc=None, alpha=None):
    rect = pygame.Rect(rect)
    if alpha is not None:
        t = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(t, (*color, alpha), t.get_rect(), border_radius=r)
        if bw:
            pygame.draw.rect(t, (*(bc or color), min(255, alpha + 60)), t.get_rect(), bw, border_radius=r)
        s.blit(t, rect.topleft)
    else:
        pygame.draw.rect(s, color, rect, border_radius=r)
        if bw:
            pygame.draw.rect(s, bc or (0, 0, 0), rect, bw, border_radius=r)


def glow_circle(radius, color, peak=255, power=1.6):
    t = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
    for r in range(radius, 0, -2):
        a = int(peak * (1 - r / radius) ** power)
        pygame.draw.circle(t, (*color, a), (radius, radius), r)
    return t


def glow_add(radius, color, peak=1.0, power=1.6):
    t = pygame.Surface((radius * 2, radius * 2))
    for r in range(radius, 0, -2):
        k = peak * (1 - r / radius) ** power
        pygame.draw.circle(t, tuple(int(c * k) for c in color), (radius, radius), r)
    return t


def scaled_glow(g, k):
    c = g.copy()
    v = int(255 * clamp(k, 0, 1))
    c.fill((v, v, v), special_flags=pygame.BLEND_RGB_MULT)
    return c


_glow_cache = {}


def glow_text(t, size, color, glow_color):
    k = (t, size, color, glow_color)
    if k in _glow_cache:
        return _glow_cache[k]
    f = F(size, True)
    base = f.render(t, True, color)
    gl = f.render(t, True, glow_color)
    w, h = base.get_size()
    pad = 50
    out = pygame.Surface((w + pad * 2, h + pad * 2), pygame.SRCALPHA)
    small = pygame.transform.smoothscale(gl, (max(1, w // 6), max(1, h // 6)))
    big = pygame.transform.smoothscale(small, (w + 40, h + 40))
    for _ in range(3):
        out.blit(big, (pad - 20, pad - 20))
    out.blit(base, (pad, pad))
    _glow_cache[k] = out
    return out


def ecg_y(ph):
    def g(c, w, a):
        return a * math.exp(-((ph - c) / w) ** 2)
    return g(0.2, 0.05, 0.15) + g(0.40, 0.012, -0.2) + g(0.44, 0.012, 1.0) + g(0.48, 0.015, -0.35) + g(0.68, 0.05, 0.3)


# ----------------------------------------------------------------------------
# SONIDO (sintetizado, sin archivos)
# ----------------------------------------------------------------------------
def make_tone(freqs, dur, vol=0.3, decay=5.0, slide=0.0):
    n = int(44100 * dur)
    buf = array("h")
    for i in range(n):
        t = i / 44100
        env = math.exp(-decay * t / dur)
        v = sum(math.sin(2 * math.pi * (f + slide * t) * t) for f in freqs) / len(freqs)
        buf.append(int(32767 * vol * env * v))
    return pygame.mixer.Sound(buffer=buf.tobytes())


class Sfx:
    def __init__(self):
        self.on = True
        self.s = {}
        try:
            self.s["click"] = make_tone([700], 0.05, 0.25, 6)
            self.s["ok"] = make_tone([523, 659, 784], 0.35, 0.3, 4)
            self.s["err"] = make_tone([140, 150], 0.25, 0.4, 3)
            self.s["alert"] = make_tone([220, 233], 0.6, 0.35, 2)
            self.s["tele"] = make_tone([300], 0.7, 0.3, 3, slide=500)
            self.s["item"] = make_tone([880, 1175], 0.2, 0.3, 5)
            self.s["scare"] = make_tone([90, 95, 180], 1.0, 0.5, 2)
            self.s["beat"] = make_tone([55, 80], 0.14, 0.6, 6)
        except Exception:
            self.on = False

    def play(self, n):
        if self.on and n in self.s:
            try:
                self.s[n].play()
            except Exception:
                pass


# ----------------------------------------------------------------------------
# PERSONAJES (vectorial suavizado, supersampling x4)
# ----------------------------------------------------------------------------
PEOPLE = {
    "hero": dict(skin=(247, 200, 150), hair=(120, 66, 28), hair2=(86, 46, 18), eye=(96, 62, 34),
                 shirt=(250, 250, 252), shirt2=(212, 216, 230), pants=(58, 60, 82), shoe=(150, 150, 164),
                 style="pony", detail="tie", accent=(206, 28, 40)),
    "sofia": dict(skin=(248, 222, 188), hair=(240, 186, 98), hair2=(200, 142, 66), eye=(70, 130, 190),
                  shirt=(60, 64, 84), shirt2=(38, 40, 58), pants=(240, 226, 214), shoe=(60, 60, 84),
                  style="long", detail="bow", accent=(250, 228, 60), skirt=(150, 34, 44)),
    "mateo": dict(skin=(222, 170, 124), hair=(34, 26, 30), hair2=(20, 16, 20), eye=(60, 40, 28),
                  shirt=(70, 130, 200), shirt2=(50, 98, 160), pants=(48, 52, 68), shoe=(230, 230, 235),
                  style="spiky", detail="tie", accent=(250, 200, 60)),
    "profe": dict(skin=(240, 198, 160), hair=(176, 176, 184), hair2=(130, 130, 138), eye=(70, 70, 70),
                  shirt=(232, 226, 210), shirt2=(200, 194, 176), pants=(60, 56, 52), shoe=(40, 34, 30),
                  style="profe", detail="vest", accent=(120, 76, 48)),
    "valentina": dict(skin=(236, 186, 150), hair=(150, 90, 200), hair2=(110, 60, 160), eye=(120, 60, 160),
                      shirt=(255, 255, 255), shirt2=(222, 214, 240), pants=(236, 210, 200), shoe=(70, 70, 110),
                      style="bun", detail="bow", accent=(255, 120, 170), skirt=(90, 60, 140)),
    "andres": dict(skin=(206, 150, 110), hair=(60, 50, 46), hair2=(40, 32, 30), eye=(50, 36, 28),
                   shirt=(60, 150, 150), shirt2=(40, 110, 112), pants=(50, 70, 100), shoe=(50, 40, 30),
                   style="cap", detail="work", accent=(230, 120, 40)),
    "camila": dict(skin=(250, 210, 170), hair=(200, 60, 50), hair2=(150, 36, 30), eye=(60, 150, 100),
                   shirt=(255, 230, 120), shirt2=(230, 196, 80), pants=(60, 64, 100), shoe=(250, 250, 250),
                   style="pony", detail="hoodie", accent=(255, 255, 255)),
    "lucas": dict(skin=(232, 190, 150), hair=(90, 60, 36), hair2=(60, 40, 22), eye=(70, 100, 60),
                  shirt=(110, 180, 100), shirt2=(80, 140, 72), pants=(70, 76, 100), shoe=(240, 240, 240),
                  style="short", detail="hoodie", accent=(255, 255, 255)),
}

NPC_DEFS = [("Sofía", "sofia", (240, 200, 120)), ("Mateo", "mateo", (130, 200, 255)),
            ("Profe Ramírez", "profe", (210, 210, 170)), ("Valentina", "valentina", (220, 150, 255)),
            ("Don Andrés", "andres", (120, 220, 200)), ("Camila", "camila", (255, 150, 140)),
            ("Lucas", "lucas", (150, 230, 130))]


def _tools(sf, S, O):
    def U(*v):
        return [int(x * S) for x in v]

    def rr(x, y, ww, hh, c, r=2.0, bw=0.8):
        rect = pygame.Rect(*U(x, y, ww, hh))
        pygame.draw.rect(sf, c, rect, border_radius=int(r * S))
        if bw:
            pygame.draw.rect(sf, O, rect, max(1, int(bw * S)), border_radius=int(r * S))

    def el(x, y, ww, hh, c, bw=0.8):
        rect = pygame.Rect(*U(x, y, ww, hh))
        pygame.draw.ellipse(sf, c, rect)
        if bw:
            pygame.draw.ellipse(sf, O, rect, max(1, int(bw * S)))

    def pg(pts, c, bw=0.6):
        q = [(int(a * S), int(b * S)) for a, b in pts]
        pygame.draw.polygon(sf, c, q)
        if bw:
            pygame.draw.polygon(sf, O, q, max(1, int(bw * S)))

    def ln(a, b, c, wd=0.8):
        pygame.draw.line(sf, c, (int(a[0] * S), int(a[1] * S)), (int(b[0] * S), int(b[1] * S)), max(1, int(wd * S)))

    return U, rr, el, pg, ln


def person_surface(kind, phase, out=(56, 89)):
    S = 4
    w, h = 48, 76
    p = PEOPLE[kind]
    sf = pygame.Surface((w * S, h * S), pygame.SRCALPHA)
    O = (30, 20, 38)
    U, rr, el, pg, ln = _tools(sf, S, O)
    bob = [0, -1, 0, -1][phase]
    sw = [0, 3, 0, -3][phase]
    st = p["style"]
    sk, skd = p["skin"], shade(p["skin"], 0.86)
    pygame.draw.ellipse(sf, (0, 0, 0, 90), pygame.Rect(*U(9, 68, 30, 7)))
    # pelo trasero
    if st == "long":
        rr(6, 11 + bob, 36, 42, p["hair2"], 14)
    elif st == "pony":
        el(0, 20 + bob, 12, 28, p["hair2"])
        rr(10, 10 + bob, 28, 20, p["hair2"], 8)
    elif st in ("bun", "short", "spiky", "profe"):
        rr(10, 10 + bob, 28, 18, p["hair2"], 8)
    # piernas
    lift_l, lift_r = max(0, -sw), max(0, sw)
    rr(17, 55 + bob, 6, 12 - lift_l, p["pants"], 2)
    rr(26, 55 + bob, 6, 12 - lift_r, p["pants"], 2)
    el(15.5, 65 - lift_l, 9, 5, p["shoe"], 0.7)
    el(24.5, 65 - lift_r, 9, 5, p["shoe"], 0.7)
    # torso
    rr(14, 35 + bob, 20, 22, p["shirt"], 5)
    pg([(27, 36 + bob), (33, 38 + bob), (33, 54 + bob), (27, 56 + bob)], p["shirt2"], 0)
    rr(14, 50 + bob, 20, 7, p["shirt2"], 4, 0)
    if p.get("skirt"):
        rr(13, 51 + bob, 22, 10, p["skirt"], 3)
        pg([(28, 52 + bob), (35, 52 + bob), (35, 60 + bob), (29, 60 + bob)], shade(p["skirt"], 0.8), 0)
    d = p["detail"]
    if d == "tie":
        pg([(18, 35 + bob), (24, 41 + bob), (30, 35 + bob)], (255, 255, 255), 0.5)
        pg([(22.5, 38 + bob), (25.5, 38 + bob), (26.2, 49 + bob), (24, 51 + bob), (21.8, 49 + bob)], p["accent"], 0.6)
        if kind == "hero":
            rr(28, 52 + bob, 5, 5, (130, 134, 150), 1.5, 0)
    elif d == "vest":
        rr(15, 37 + bob, 18, 19, p["accent"], 5)
        pg([(18, 35 + bob), (24, 41 + bob), (30, 35 + bob)], (255, 255, 255), 0.5)
        pg([(23, 39 + bob), (25, 39 + bob), (25.5, 46 + bob), (24, 47 + bob), (22.5, 46 + bob)], (150, 30, 40), 0.5)
    elif d == "hoodie":
        el(15, 33 + bob, 18, 8, p["shirt2"], 0.6)
        rr(18, 49 + bob, 12, 6, p["shirt2"], 2, 0.5)
        ln((21, 38 + bob), (21, 45 + bob), (255, 255, 255), 0.6)
        ln((27, 38 + bob), (27, 45 + bob), (255, 255, 255), 0.6)
    elif d == "work":
        rr(17, 41 + bob, 7, 7, p["shirt2"], 1.5, 0.5)
        rr(14, 52 + bob, 20, 3, (60, 44, 30), 1, 0)
        el(26, 41 + bob, 4, 3, p["accent"], 0.4)
        pg([(18, 35 + bob), (24, 39 + bob), (30, 35 + bob)], p["shirt2"], 0.5)
    elif d == "bow":
        pg([(18, 35 + bob), (24, 40 + bob), (30, 35 + bob)], (255, 255, 255), 0.5)
        pg([(24, 40 + bob), (18, 37 + bob), (18, 43 + bob)], p["accent"], 0.5)
        pg([(24, 40 + bob), (30, 37 + bob), (30, 43 + bob)], p["accent"], 0.5)
        el(22.6, 38.6 + bob, 2.8, 2.8, shade(p["accent"], 0.8), 0.4)
    # brazos
    al, ar = int(sw * 0.4), -int(sw * 0.4)
    sl = p["shirt"]
    rr(9, 37 + bob + al, 6, 14, sl, 3)
    rr(33, 37 + bob + ar, 6, 14, sl, 3)
    el(9, 49 + bob + al, 6, 6, sk, 0.7)
    el(33, 49 + bob + ar, 6, 6, sk, 0.7)
    # cuello y cabeza
    rr(21, 32 + bob, 6, 6, skd, 1, 0)
    el(8.6, 21 + bob, 3.6, 5.6, sk, 0.6)
    el(35.8, 21 + bob, 3.6, 5.6, sk, 0.6)
    el(10, 10 + bob, 28, 27, sk, 1.0)
    pygame.draw.ellipse(sf, (*skd, 90), pygame.Rect(*U(26, 14 + bob, 12, 20)))
    # cara
    ey = 23 + bob
    for ex in (15.8, 28.0):
        el(ex, ey - 1.8, 5.2, 6.6, (255, 255, 255), 0.5)
        el(ex + 0.7, ey - 1.0, 3.8, 5.4, p["eye"], 0)
        el(ex + 1.3, ey + 0.1, 2.3, 3.2, (20, 14, 24), 0)
        el(ex + 1.0, ey - 0.6, 1.5, 1.7, (255, 255, 255), 0)
        ln((ex - 0.2, ey - 1.5), (ex + 5.4, ey - 1.5), O, 0.9)
        ln((ex, ey - 4.3), (ex + 5, ey - 4.6), p["hair2"], 0.8)
    pygame.draw.ellipse(sf, (255, 130, 150, 130), pygame.Rect(*U(11.5, 28 + bob, 5.5, 3.4)))
    pygame.draw.ellipse(sf, (255, 130, 150, 130), pygame.Rect(*U(31, 28 + bob, 5.5, 3.4)))
    ln((24, 27 + bob), (24.4, 28.4 + bob), skd, 0.6)
    pygame.draw.arc(sf, O, pygame.Rect(*U(20.5, 28.4 + bob, 7, 4.5)), math.pi * 1.1, math.pi * 1.9, max(1, int(0.8 * S)))
    # pelo frontal
    hc, hl = p["hair"], shade(p["hair"], 1.35)
    if st == "pony":
        pygame.draw.ellipse(sf, hc, pygame.Rect(*U(9, 5.5 + bob, 30, 17)))
        pg([(10, 14 + bob), (38, 14 + bob), (38, 19 + bob), (31, 16 + bob), (24, 21 + bob), (17, 16 + bob), (10, 20 + bob)], hc, 0.5)
        pygame.draw.ellipse(sf, O, pygame.Rect(*U(9, 5.5 + bob, 30, 17)), max(1, int(0.8 * S)))
        el(6.5, 21 + bob, 3, 3, p["accent"] if kind == "camila" else (206, 28, 40), 0.5)
    elif st == "short":
        pygame.draw.ellipse(sf, hc, pygame.Rect(*U(9, 5 + bob, 30, 16)))
        pg([(10, 12 + bob), (38, 12 + bob), (38, 18 + bob), (33, 15 + bob), (24, 19 + bob), (15, 15 + bob), (10, 18 + bob)], hc, 0.5)
        pygame.draw.ellipse(sf, O, pygame.Rect(*U(9, 5 + bob, 30, 16)), max(1, int(0.8 * S)))
    elif st == "long":
        pygame.draw.ellipse(sf, hc, pygame.Rect(*U(8, 5 + bob, 32, 18)))
        pg([(9, 13 + bob), (39, 13 + bob), (39, 19 + bob), (33, 17 + bob), (26, 14 + bob), (19, 19 + bob), (9, 23 + bob)], hc, 0.5)
        pg([(8, 14 + bob), (13, 16 + bob), (11, 38 + bob), (7, 40 + bob)], hc, 0.5)
        pg([(35, 16 + bob), (40, 14 + bob), (41, 40 + bob), (37, 38 + bob)], hc, 0.5)
        pygame.draw.ellipse(sf, O, pygame.Rect(*U(8, 5 + bob, 32, 18)), max(1, int(0.8 * S)))
    elif st == "spiky":
        pg([(9, 17 + bob), (8, 8 + bob), (14, 10 + bob), (16, 2 + bob), (21, 9 + bob), (26, 1 + bob), (30, 9 + bob),
            (36, 5 + bob), (38, 14 + bob), (38, 18 + bob), (31, 13 + bob), (24, 17 + bob), (17, 13 + bob), (10, 19 + bob)], hc, 0.6)
    elif st == "bun":
        el(18, 0.5 + bob, 12, 10, hc, 0.7)
        pygame.draw.ellipse(sf, hc, pygame.Rect(*U(9, 5.5 + bob, 30, 17)))
        pg([(10, 13 + bob), (38, 13 + bob), (38, 19 + bob), (31, 16 + bob), (24, 20 + bob), (17, 16 + bob), (10, 20 + bob)], hc, 0.5)
        pygame.draw.ellipse(sf, O, pygame.Rect(*U(9, 5.5 + bob, 30, 17)), max(1, int(0.8 * S)))
        el(20, 5 + bob, 8, 3, p["accent"], 0.4)
    elif st == "cap":
        pg([(9, 17 + bob), (11, 20 + bob), (10, 25 + bob), (8, 21 + bob)], hc, 0.4)
        pg([(39, 17 + bob), (37, 20 + bob), (38, 25 + bob), (40, 21 + bob)], hc, 0.4)
        pygame.draw.ellipse(sf, p["accent"], pygame.Rect(*U(9, 4 + bob, 30, 17)))
        pygame.draw.ellipse(sf, O, pygame.Rect(*U(9, 4 + bob, 30, 17)), max(1, int(0.8 * S)))
        rr(8, 15 + bob, 32, 4, shade(p["accent"], 0.75), 2, 0.6)
        pg([(8, 17 + bob), (2, 20 + bob), (10, 21 + bob)], shade(p["accent"], 0.75), 0.5)
    elif st == "profe":
        pygame.draw.ellipse(sf, hc, pygame.Rect(*U(9, 6 + bob, 30, 13)))
        pg([(9, 12 + bob), (13, 10 + bob), (16, 14 + bob), (12, 20 + bob), (9, 19 + bob)], hc, 0.4)
        pg([(39, 12 + bob), (35, 10 + bob), (32, 14 + bob), (36, 20 + bob), (39, 19 + bob)], hc, 0.4)
        pygame.draw.ellipse(sf, O, pygame.Rect(*U(9, 6 + bob, 30, 13)), max(1, int(0.8 * S)))
        for gx in (14.8, 27.4):
            pygame.draw.ellipse(sf, O, pygame.Rect(*U(gx, 20.3 + bob, 7.5, 6.8)), max(1, int(0.8 * S)))
        ln((22.3, 23 + bob), (27.4, 23 + bob), O, 0.7)
        rr(20, 30 + bob, 8, 2, p["hair2"], 1, 0)
    pygame.draw.ellipse(sf, (*hl, 160), pygame.Rect(*U(15, 7.5 + bob, 9, 3.2))) if st not in ("profe", "cap", "spiky") else None
    return pygame.transform.smoothscale(sf, out)


def demon_surface(phase, out=(64, 102)):
    """El ayudante: demonio encapuchado con cuernos, ojos rojos y garras."""
    S = 4
    w, h = 56, 89
    sf = pygame.Surface((w * S, h * S), pygame.SRCALPHA)
    O = (12, 6, 18)
    U, rr, el, pg, ln = _tools(sf, S, O)
    bob = [0, -1.2, 0, -1.2][phase]
    sway = [0, 2, 0, -2][phase]
    bone = (226, 214, 190)
    for k in range(5):
        pygame.draw.ellipse(sf, (150, 20, 70, 24), pygame.Rect(*U(3 - k * 1.5, 12 + bob - k * 1.5, 50 + k * 3, 72 + k * 3)))
    pygame.draw.ellipse(sf, (0, 0, 0, 120), pygame.Rect(*U(7, 80, 42, 7)))
    for fx in (13, 21, 31, 39):
        pg([(fx, 79), (fx + 3.2, 79), (fx + 1.6, 85.5)], bone, 0.5)
    hem = [(51 + sway - i * 5.7, 74 + (6 if i % 2 else 0)) for i in range(9)]
    cloak = [(14, 36 + bob), (42, 36 + bob), (53 + sway * 0.5, 58)] + hem + [(3 + sway * 0.5, 58)]
    pg(cloak, (32, 20, 48), 0.8)
    pg([(21, 38 + bob), (35, 38 + bob), (40, 72), (16, 72)], (56, 36, 80), 0)
    for i in range(4):
        x = 20 + i * 5
        ln((x, 52 + bob), (x - 1.5 + sway * 0.3, 70), (24, 14, 36), 0.7)
    pg([(26, 38 + bob), (30, 38 + bob), (31.2, 50 + bob), (28, 55 + bob), (24.8, 50 + bob)], (160, 20, 34), 0.6)
    al, ar = sway * 0.7, -sway * 0.7
    for sgn in (0, 1):
        sh = al if sgn == 0 else ar
        X = (lambda x: x) if sgn == 0 else (lambda x: 56 - x)
        pg([(X(11), 38 + bob), (X(17), 38 + bob), (X(11), 62 + bob + sh), (X(6.5), 60 + bob + sh)], (28, 18, 42), 0.7)
        el(X(8.5) - (0 if sgn == 0 else 7), 59 + bob + sh, 7, 6, (190, 180, 196), 0.6)
        for k in range(3):
            cx = X(5.5 + k * 2.6) - (0 if sgn == 0 else 3)
            pg([(cx, 63 + bob + sh), (cx + 2.2, 63 + bob + sh), (cx + 1, 73 + bob + sh)], bone, 0.4)
    # cabeza
    el(13, 9 + bob, 30, 30, (26, 14, 38), 0.9)
    el(18, 16 + bob, 20, 21, (206, 196, 214), 0.8)
    pygame.draw.ellipse(sf, (36, 10, 44, 130), pygame.Rect(*U(18, 16 + bob, 20, 9)))
    for hx in (0, 1):
        X = (lambda x: x) if hx == 0 else (lambda x: 56 - x)
        pg([(X(17), 17 + bob), (X(14), 9 + bob), (X(9), 4 + bob), (X(11), 1.5 + bob), (X(19), 5 + bob), (X(22), 12 + bob)], bone, 0.7)
    ey = 26 + bob
    pygame.draw.circle(sf, (255, 40, 50, 60), (int(23 * S), int(ey * S)), int(7 * S))
    pygame.draw.circle(sf, (255, 40, 50, 60), (int(33 * S), int(ey * S)), int(7 * S))
    for hx in (0, 1):
        X = (lambda x: x) if hx == 0 else (lambda x: 56 - x)
        pg([(X(19.5), ey - 2.2), (X(26.5), ey + 0.8), (X(25.5), ey + 2.6), (X(19), ey + 0.4)], (255, 56, 56), 0.4)
        el(X(23.6) - (0 if hx == 0 else 2.6), ey - 0.4, 2.6, 1.8, (255, 236, 110), 0)
        ln((X(18.5), ey - 4.8), (X(27), ey - 1.2), O, 1.0)
    ln((27, 30 + bob), (26.4, 32 + bob), (90, 70, 100), 0.6)
    ln((29, 30 + bob), (29.6, 32 + bob), (90, 70, 100), 0.6)
    rr(20.5, 33 + bob, 15, 4, (10, 4, 14), 2, 0)
    for i in range(5):
        x = 21.4 + i * 2.7
        pg([(x, 33 + bob), (x + 2.2, 33 + bob), (x + 1.1, 36 + bob)], (255, 255, 255), 0)
    return pygame.transform.smoothscale(sf, out)


def ghost_surface(phase, out=(70, 111)):
    """Ella: entidad fantasmal de largo cabello negro y ojos rojos."""
    S = 4
    w, h = 56, 89
    sf = pygame.Surface((w * S, h * S), pygame.SRCALPHA)
    O = (10, 6, 14)
    U, rr, el, pg, ln = _tools(sf, S, O)
    bob = [0, -1.5, 0, -1.5][phase]
    wv = [0, 1.5, 0, -1.5][phase]
    hair, pale = (14, 10, 20), (232, 224, 232)
    for k in range(5):
        pygame.draw.ellipse(sf, (210, 20, 40, 22), pygame.Rect(*U(2 - k * 2, 8 - k * 2 + bob, 52 + k * 4, 78 + k * 4)))
    pg([(16, 14 + bob), (40, 14 + bob), (49 + wv, 40), (51 + wv * 1.5, 66), (45 + wv, 83), (39, 70), (35 + wv, 85),
        (29, 72), (23 - wv, 87), (17, 72), (9 - wv, 81), (6 - wv * 1.5, 60), (8, 38)], hair, 0.8)
    dress = [(17, 38 + bob), (39, 38 + bob), (46 + wv, 62), (42 + wv, 70), (38, 64), (34, 75), (29, 66), (24, 77),
             (19, 66), (14 - wv, 72), (10 - wv, 62)]
    pg(dress, (226, 222, 234), 0.8)
    pg([(30, 40 + bob), (39, 38 + bob), (46 + wv, 62), (42 + wv, 70), (36, 66)], (190, 184, 206), 0)
    for (x, y, ww, hh) in ((20, 50, 4, 10), (30, 56, 3.2, 8), (25, 62, 2.6, 7)):
        el(x, y, ww, hh, (140, 10, 22), 0)
    pg([(20, 40 + bob), (28, 46 + bob), (36, 40 + bob), (28, 38 + bob)], (150, 16, 30), 0.5)
    for sgn in (0, 1):
        X = (lambda x: x) if sgn == 0 else (lambda x: 56 - x)
        pg([(X(15), 40 + bob), (X(19.5), 40 + bob), (X(15.5), 64 + bob + wv * (1 if sgn == 0 else -1)), (X(12), 63 + bob + wv)], (222, 212, 222), 0.6)
        for k in range(3):
            x0 = X(12.4 + k * 1.2)
            ln((x0, 63 + bob), (x0 - 0.4, 70 + bob), (200, 190, 200), 0.7)
    el(15, 10 + bob, 26, 28, pale, 0.8)
    el(19.5, 22 + bob, 8, 9, (22, 8, 22), 0)
    el(28.5, 22 + bob, 8, 9, (22, 8, 22), 0)
    pygame.draw.circle(sf, (255, 30, 50, 70), (int(24 * S), int((26 + bob) * S)), int(6 * S))
    pygame.draw.circle(sf, (255, 30, 50, 70), (int(33 * S), int((26 + bob) * S)), int(6 * S))
    el(21.8, 24 + bob, 3.4, 4.8, (255, 40, 54), 0)
    el(30.8, 24 + bob, 3.4, 4.8, (255, 40, 54), 0)
    el(22.8, 25.4 + bob, 1.2, 1.8, (255, 214, 214), 0)
    el(31.8, 25.4 + bob, 1.2, 1.8, (255, 214, 214), 0)
    ln((23.2, 30 + bob), (22.6, 40 + bob), (170, 10, 22), 1.0)
    ln((32.4, 30 + bob), (33.0, 41 + bob), (170, 10, 22), 1.0)
    pygame.draw.arc(sf, (40, 6, 18), pygame.Rect(*U(22, 30.5 + bob, 12, 7)), math.pi * 1.05, math.pi * 1.95, max(1, int(1.1 * S)))
    pg([(13, 25 + bob), (15, 8 + bob), (28, 5 + bob), (41, 8 + bob), (43, 25 + bob), (40, 42 + bob), (39, 26 + bob),
        (31, 13 + bob), (25, 13 + bob), (17, 26 + bob), (16, 44 + bob)], hair, 0.6)
    pg([(13, 30 + bob), (17, 36 + bob), (12, 53 + bob + wv), (8, 51 + bob)], hair, 0.5)
    pg([(43, 30 + bob), (39, 36 + bob), (44, 53 + bob - wv), (48, 51 + bob)], hair, 0.5)
    return pygame.transform.smoothscale(sf, out)


def make_icon(name, size=40):
    S = 4
    n = 40
    sf = pygame.Surface((n * S, n * S), pygame.SRCALPHA)
    O = (34, 24, 30)

    def U(*v):
        return [int(x * S) for x in v]

    def rr(x, y, w, h, c, r=2, bw=1.0):
        rect = pygame.Rect(*U(x, y, w, h))
        pygame.draw.rect(sf, c, rect, border_radius=int(r * S))
        if bw:
            pygame.draw.rect(sf, O, rect, int(bw * S), border_radius=int(r * S))

    def el(x, y, w, h, c, bw=1.0):
        rect = pygame.Rect(*U(x, y, w, h))
        pygame.draw.ellipse(sf, c, rect)
        if bw:
            pygame.draw.ellipse(sf, O, rect, int(bw * S))

    def pg(pts, c, bw=1.0):
        q = [(int(a * S), int(b * S)) for a, b in pts]
        pygame.draw.polygon(sf, c, q)
        if bw:
            pygame.draw.polygon(sf, O, q, int(bw * S))

    if name == "Plátano":
        pg([(8, 28), (14, 34), (26, 32), (34, 24), (35, 11), (31, 10), (29, 22), (22, 28), (10, 24)], (250, 218, 60))
        rr(31, 7, 5, 5, (110, 80, 40), 1, 0.8)
    elif name == "Yuca":
        pg([(5, 30), (11, 35), (35, 12), (33, 6), (25, 8)], (176, 126, 76))
        el(29, 5, 7, 8, (246, 236, 214), 0.8)
    elif name == "Papa":
        el(5, 10, 30, 23, (206, 164, 102))
        for a, b in ((12, 17), (22, 14), (26, 23), (15, 26)):
            el(a, b, 2.5, 2.5, (140, 100, 60), 0)
    elif name == "Mazorca":
        el(13, 4, 14, 32, (250, 214, 70))
        for k in range(6, 34, 5):
            pygame.draw.line(sf, (200, 150, 30), (int(14 * S), int(k * S)), (int(26 * S), int(k * S)), 2)
        pg([(14, 36), (6, 22), (13, 20)], (92, 170, 80), 0.8)
        pg([(26, 36), (34, 22), (27, 20)], (72, 150, 70), 0.8)
    elif name == "Pollo":
        el(7, 7, 24, 22, (218, 140, 66))
        pg([(24, 24), (30, 30), (34, 36), (30, 36), (26, 32)], (245, 240, 228), 0.8)
        el(31, 33, 6, 5, (245, 240, 228), 0.8)
        el(12, 11, 7, 5, (240, 180, 110), 0)
    elif name == "Cilantro":
        pygame.draw.line(sf, (60, 120, 60), (20 * S, 36 * S), (20 * S, 18 * S), 5)
        for a, b, r in ((12, 8, 9), (22, 5, 9), (27, 14, 8), (8, 18, 8), (17, 15, 8)):
            el(a, b, r, r, (96, 190, 90), 0.8)
    elif name == "Sándwich":
        pg([(4, 32), (36, 32), (20, 6)], (238, 198, 128))
        pg([(8, 28), (32, 28), (22, 12), (18, 12)], (110, 190, 90), 0.5)
        pg([(10, 25), (30, 25), (26, 19), (14, 19)], (236, 110, 100), 0.5)
        pg([(4, 32), (36, 32), (34, 36), (6, 36)], (214, 168, 98))
    elif name == "Desinfectante":
        rr(11, 14, 18, 22, (74, 150, 232), 4)
        rr(15, 20, 10, 8, (255, 255, 255), 2, 0.6)
        rr(15, 6, 10, 8, (238, 240, 246), 2)
        pg([(25, 7), (36, 9), (36, 12), (25, 12)], (230, 232, 240), 0.8)
    elif name == "Desodorante":
        rr(12, 12, 16, 25, (196, 200, 210), 4)
        rr(12, 4, 16, 10, (66, 104, 206), 3)
        rr(15, 21, 10, 7, (90, 160, 240), 2, 0.6)
    elif name == "Gas pimienta":
        rr(13, 10, 14, 27, (214, 52, 52), 4)
        rr(15, 3, 10, 8, (30, 30, 36), 2)
        pg([(20, 18), (24, 26), (16, 26)], (255, 255, 255), 0.6)
    elif name.startswith("Llave"):
        pg([(5, 15), (21, 5), (35, 15), (31, 33), (13, 35)], (238, 190, 60))
        el(11, 14, 8, 8, (50, 40, 20), 0.8)
        pg([(21, 5), (35, 15), (28, 17), (18, 12)], (255, 226, 130), 0.6)
    elif name == "Sancocho":
        el(2, 28, 36, 10, (160, 164, 180))
        el(5, 14, 30, 22, (248, 246, 232))
        el(8, 10, 24, 12, (56, 140, 100))
        for a, b in ((12, 12), (18, 10), (24, 13), (15, 16), (22, 17)):
            el(a, b, 4, 3, (160, 220, 100), 0)
    out = pygame.transform.smoothscale(sf, (size, size))
    if name.startswith("Llave"):
        num = name[-1]
        t = F(int(size * 0.42), True).render(num, True, (50, 36, 10))
        out.blit(t, t.get_rect(center=(size // 2 + 2, int(size * 0.62))))
    return out


# ----------------------------------------------------------------------------
# MAPA
# ----------------------------------------------------------------------------
def in_walk(x, y):
    for r in WALK:
        if r.collidepoint(x, y):
            return True
    return False


def rel_rect(room, down, rx, ry, rw, rh):
    y = room.bottom - ry - rh if down else room.y + ry
    return pygame.Rect(room.x + rx, y, rw, rh)


def theme_of(fi):
    return "gym" if fi == 5 else "col" if fi == 6 else "school"


def build_layout(fi):
    obs, desks, terms = [], [], []
    for r in ROOMS:
        down = r.y > CORR.y
        td = rel_rect(r, down, 400, 14, 110, 52)
        terms.append(td)
        obs.append(td)
        for rx in (30, 130, 350, 450):
            for ry in (110, 185):
                d = rel_rect(r, down, rx, ry, 80, 44)
                desks.append(d)
                obs.append(d)
    plants = [pygame.Rect(1000, 368, 34, 34), pygame.Rect(1420, 490, 34, 34), pygame.Rect(150, 488, 34, 34)]
    bench = pygame.Rect(1640, 495, 130, 36)
    obs += plants + [bench]
    if fi == 0:
        obs.append(STOVE_RECT)
        obs.append(pygame.Rect(ENTITY_POS[0] - 26, ENTITY_POS[1] - 20, 52, 24))
    return dict(obs=obs, desks=desks, terms=terms, plants=plants, bench=bench)


def shadow_rect(s, rect, off=6, alpha=70):
    t = pygame.Surface((rect.w + 16, rect.h + 16), pygame.SRCALPHA)
    pygame.draw.rect(t, (0, 0, 0, alpha), (8, 8, rect.w, rect.h), border_radius=8)
    s.blit(t, (rect.x - 8 + off // 2, rect.y - 8 + off))


def draw_gym_item(s, d, i, k, rnd):
    if i % 2 == 0:
        c = rnd.choice([(230, 90, 120), (90, 170, 230), (120, 200, 120), (240, 180, 70)])
        rrect(s, c, d.inflate(-10, -8), 10, 2, shade(c, 0.6))
        pygame.draw.line(s, shade(c, 1.2), (d.x + 12, d.centery), (d.right - 12, d.centery), 2)
    else:
        rrect(s, (70, 74, 90), pygame.Rect(d.x + 6, d.y + 12, d.w - 12, 20), 6, 2, (30, 32, 44))
        pygame.draw.line(s, (200, 204, 214), (d.x + 2, d.y + 8), (d.right - 2, d.y + 8), 4)
        for ex in (d.x + 6, d.right - 6):
            pygame.draw.circle(s, (40, 42, 54), (ex, d.y + 8), 8)
            pygame.draw.circle(s, (180, 60, 60), (ex, d.y + 8), 4)


def draw_col_item(s, d, i, k):
    if i % 2 == 0:
        c = (196, 186, 166)
        pygame.draw.rect(s, shade(c, 0.7), (d.centerx - 20, d.y + 2, 40, d.h - 2), border_radius=6)
        pygame.draw.rect(s, c, (d.centerx - 17, d.y, 34, d.h - 4), border_radius=6)
        for k2 in range(3):
            pygame.draw.line(s, shade(c, 0.8), (d.centerx - 8 + k2 * 8, d.y + 4), (d.centerx - 8 + k2 * 8, d.bottom - 8), 2)
        pygame.draw.rect(s, shade(c, 1.1), (d.centerx - 22, d.y - 2, 44, 8), border_radius=3)
    else:
        rrect(s, (120, 80, 48), d.inflate(-6, -4), 4, 2, (66, 42, 24))
        for k2 in range(4):
            x = d.x + 14 + k2 * 16
            pygame.draw.line(s, (200, 204, 214), (x, d.y + 6), (x, d.bottom - 6), 3)
            pygame.draw.polygon(s, (230, 234, 244), [(x - 3, d.y + 7), (x + 3, d.y + 7), (x, d.y)])


def render_floor(fi):
    col = FLOOR_COLORS[fi]
    th = theme_of(fi)
    lay = build_layout(fi)
    rnd = random.Random(fi * 31 + 5)
    s = pygame.Surface((WORLD_W, WORLD_H))
    s.fill((38, 40, 62) if th != "col" else (52, 40, 34))
    gc = (42, 44, 68) if th != "col" else (60, 46, 38)
    for x in range(0, WORLD_W, 48):
        pygame.draw.line(s, gc, (x, 0), (x, WORLD_H))
    wo, wi = ((102, 108, 150), (64, 68, 102)) if th != "col" else ((176, 138, 80), (116, 84, 50))
    for r in [CORR] + ROOMS:
        pygame.draw.rect(s, wo, r.inflate(16, 16), border_radius=6)
        pygame.draw.rect(s, wi, r.inflate(10, 10), 3, border_radius=4)
    # pasillo
    c1, c2, lc = {"school": ((232, 228, 212), (208, 202, 186), (196, 190, 174)),
                  "gym": ((104, 136, 184), (74, 100, 154), (118, 148, 198)),
                  "col": ((218, 194, 154), (190, 164, 124), (168, 142, 106))}[th]
    s.blit(vgrad(CORR.w, CORR.h, c1, c2), CORR.topleft)
    for x in range(CORR.x, CORR.right, 60):
        pygame.draw.line(s, lc, (x, CORR.y), (x, CORR.bottom))
    for y in range(CORR.y, CORR.bottom, 60):
        pygame.draw.line(s, lc, (CORR.x, y), (CORR.right, y))
    for _ in range(700):
        px, py = rnd.randint(CORR.x, CORR.right - 3), rnd.randint(CORR.y, CORR.bottom - 3)
        pygame.draw.rect(s, shade(c2, 0.9), (px, py, 2, 2))
    st = pygame.Surface((CORR.w, 4), pygame.SRCALPHA)
    st.fill((*col, 120))
    s.blit(st, (CORR.x, CORR.centery - 2))
    # aulas
    for i, r in enumerate(ROOMS):
        rc, rl = {"school": (((186, 138, 90), (160, 112, 70)), (146, 100, 62)),
                  "gym": (((228, 184, 120), (202, 156, 96)), (186, 140, 84)),
                  "col": (((230, 204, 150), (206, 178, 122)), (192, 164, 108))}[th]
        s.blit(vgrad(r.w, r.h, rc[0], rc[1]), r.topleft)
        for y in range(r.y, r.bottom, 24):
            pygame.draw.line(s, rl, (r.x, y), (r.right, y))
        for _ in range(60):
            px, py = rnd.randint(r.x, r.right - 20), rnd.randint(r.y, r.bottom - 3)
            pygame.draw.line(s, shade(rl, 1.03), (px, py), (px + rnd.randint(6, 18), py))
        if th == "gym":
            wl = (250, 250, 250)
            pygame.draw.rect(s, wl, r.inflate(-50, -50), 3)
            pygame.draw.line(s, wl, (r.centerx, r.y + 25), (r.centerx, r.bottom - 25), 3)
            pygame.draw.circle(s, wl, r.center, 40, 3)
        elif th == "col":
            pygame.draw.circle(s, (180, 150, 98), r.center, 120, 4)
            pygame.draw.circle(s, (180, 150, 98), r.center, 64, 3)
        rug = pygame.Rect(r.centerx - 120, r.centery - 40, 240, 80)
        t = pygame.Surface(rug.size, pygame.SRCALPHA)
        pygame.draw.rect(t, (*col, 38), t.get_rect(), border_radius=18)
        s.blit(t, rug.topleft)
    for d in DOORS:
        pygame.draw.rect(s, (200, 170, 130), d)
        pygame.draw.line(s, (120, 90, 60), (d.x, d.y), (d.x, d.bottom), 3)
        pygame.draw.line(s, (120, 90, 60), (d.right - 1, d.y), (d.right - 1, d.bottom), 3)
    # sombras interiores
    for r in [CORR] + ROOMS:
        t = pygame.Surface((r.w, 16), pygame.SRCALPHA)
        for k in range(16):
            pygame.draw.line(t, (0, 0, 0, int(80 * (1 - k / 16) ** 2)), (0, k), (r.w, k))
        s.blit(t, r.topleft)
    for d in DOORS:
        pygame.draw.rect(s, (200, 170, 130), d)
    # mobiliario
    for i, r in enumerate(ROOMS):
        down = r.y > CORR.y
        board = rel_rect(r, down, 30, 10, 270, 30)
        if th == "school":
            rrect(s, (30, 70, 56), board, 4)
            rrect(s, (50, 96, 78), board.inflate(-8, -8), 3)
            pygame.draw.rect(s, (130, 90, 56), board, 3, border_radius=4)
            for k in range(3):
                pygame.draw.line(s, (220, 230, 220), (board.x + 20 + k * 70, board.centery - 3 + k * 2),
                                 (board.x + 60 + k * 70, board.centery - 3 + k * 2), 2)
        elif th == "gym":
            rrect(s, (60, 70, 90), board, 4)
            s.blit(vgrad(board.w - 8, board.h - 8, (196, 230, 250), (130, 180, 220)), (board.x + 4, board.y + 4))
            for k in range(4):
                pygame.draw.line(s, (255, 255, 255), (board.x + 30 + k * 62, board.y + 6), (board.x + 14 + k * 62, board.bottom - 6), 3)
        else:
            rrect(s, (140, 24, 32), board, 4)
            pygame.draw.rect(s, (226, 184, 70), board, 3, border_radius=4)
            pygame.draw.circle(s, (226, 184, 70), board.center, 9, 3)
            for k in (-1, 1):
                pygame.draw.line(s, (226, 184, 70), (board.centerx + k * 30, board.y + 7), (board.centerx + k * 90, board.y + 7), 2)
        td = lay["terms"][i]
        shadow_rect(s, td)
        s.blit(vgrad(td.w, td.h, (236, 236, 244), (200, 204, 220)), td.topleft)
        pygame.draw.rect(s, (60, 64, 90), td, 2, border_radius=6)
        mon = pygame.Rect(td.centerx - 28, td.y + (4 if not down else td.h - 36), 56, 32)
        rrect(s, (24, 26, 40), mon, 5)
        s.blit(vgrad(mon.w - 8, mon.h - 8, (110, 220, 240), (50, 120, 200)), (mon.x + 4, mon.y + 4))
        for k, d in enumerate(lay["desks"][i * 8:(i + 1) * 8]):
            shadow_rect(s, d, 5, 60)
            if th == "gym":
                draw_gym_item(s, d, k, i, rnd)
                continue
            if th == "col":
                draw_col_item(s, d, k, i)
                continue
            s.blit(vgrad(d.w, d.h, (214, 176, 126), (190, 150, 100)), d.topleft)
            pygame.draw.rect(s, (110, 76, 46), d, 2, border_radius=6)
            pygame.draw.rect(s, (222, 232, 242), (d.x + 18, d.y + 8, 30, 20), border_radius=3)
            cy = d.bottom + 12 if not down else d.y - 12
            pygame.draw.circle(s, (70, 90, 150), (d.centerx, cy), 11)
            pygame.draw.circle(s, (40, 50, 100), (d.centerx, cy), 11, 2)
        band_y = 350 if not down else 550
        if th == "school":
            subj = SUBJECTS[(fi * 4 + i) % 8]
            label = f"AULA {fi + 1}0{i + 1} · {subj}"
        elif th == "gym":
            label = f"{fi + 1}0{i + 1} · {GYM_ROOMS[i]}"
        else:
            label = f"{fi + 1}0{i + 1} · {COL_ROOMS[i]}"
        text(s, label, 14, (226, 230, 255), (r.centerx + 150, band_y), "center", True, False)
    # decoracion del pasillo
    for p in lay["plants"]:
        shadow_rect(s, p, 4, 70)
        if th == "col":
            pygame.draw.rect(s, (160, 150, 130), (p.x + 2, p.y + 26, 30, 10), border_radius=3)
            pygame.draw.rect(s, (206, 196, 176), (p.x + 6, p.y - 8, 22, 38), border_radius=4)
            pygame.draw.rect(s, (226, 216, 196), (p.x + 2, p.y - 10, 30, 8), border_radius=3)
            for k in range(3):
                pygame.draw.line(s, (170, 160, 140), (p.x + 11 + k * 6, p.y), (p.x + 11 + k * 6, p.y + 26), 2)
            continue
        pygame.draw.ellipse(s, (150, 90, 60), (p.x + 4, p.y + 14, 26, 20))
        for a in range(7):
            ang = a * 0.9
            pygame.draw.ellipse(s, (60 + a * 8, 150 + a * 6, 70), (p.centerx - 5 + math.cos(ang) * 8, p.y - 4 + math.sin(ang) * 6, 11, 22))
    b = lay["bench"]
    shadow_rect(s, b, 5, 70)
    rrect(s, (126, 90, 62) if th != "col" else (170, 160, 140), b, 8, 2, (70, 48, 30))
    for k in range(1, 5):
        pygame.draw.line(s, (96, 66, 44), (b.x + k * 26, b.y + 3), (b.x + k * 26, b.bottom - 3), 2)
    # casilleros (se puede uno esconder en ellos)
    for j, lk in enumerate(LOCKERS):
        if th == "school":
            body, door = (86, 100, 146), (110, 126, 176)
        elif th == "gym":
            body, door = ((190, 80, 50), (240, 120, 80)) if j % 2 else ((40, 110, 180), (80, 160, 230))
        else:
            body, door = (120, 100, 76), (160, 136, 100)
        pygame.draw.rect(s, (0, 0, 0), lk.move(2, 2), border_radius=3)
        pygame.draw.rect(s, body, lk, border_radius=3)
        pygame.draw.rect(s, door, lk.inflate(-6, -6), border_radius=2)
        for k in range(3):
            pygame.draw.line(s, shade(body, 0.6), (lk.x + 10, lk.y + 6 + k * 4), (lk.right - 10, lk.y + 6 + k * 4), 1)
        pygame.draw.circle(s, (240, 220, 120), (lk.right - 8, lk.centery + 3), 2)
        pygame.draw.rect(s, shade(body, 0.55), lk, 2, border_radius=3)
    # elementos del piso 1
    if fi == 0:
        sr = STOVE_RECT
        shadow_rect(s, sr, 6, 80)
        s.blit(vgrad(sr.w, sr.h, (200, 204, 214), (150, 154, 168)), sr.topleft)
        pygame.draw.rect(s, (60, 64, 80), sr, 2, border_radius=6)
        for k in range(4):
            cx = sr.x + 28 + k * 38
            pygame.draw.circle(s, (40, 40, 50), (cx, sr.y + 28), 15)
            pygame.draw.circle(s, (230, 90, 40), (cx, sr.y + 28), 9, 3)
        text(s, "COCINA", 13, (60, 64, 80), (sr.centerx, sr.y + 8), "center", True, False)
        # salida principal
        dr = pygame.Rect(96, 400, 26, 100)
        rrect(s, (70, 170, 110), dr, 4, 3, (30, 80, 56))
        pygame.draw.line(s, (30, 80, 56), (dr.centerx, dr.y), (dr.centerx, dr.bottom), 2)
        rrect(s, (30, 140, 90), (118, 372, 90, 22), 6)
        text(s, "SALIDA", 15, (255, 255, 255), (163, 383), "center", True, False)
        # salida de incendios
        fr = pygame.Rect(2280, 400, 26, 100)
        rrect(s, (190, 50, 50), fr, 4, 3, (90, 20, 20))
        pygame.draw.line(s, (90, 20, 20), (fr.centerx, fr.y), (fr.centerx, fr.bottom), 2)
        rrect(s, (190, 40, 40), (2118, 372, 156, 22), 6)
        text(s, "SALIDA DE INCENDIOS", 12, (255, 255, 255), (2196, 383), "center", True, False)
    else:
        rrect(s, (90, 100, 150), (2280, 400, 26, 100), 4, 2, (50, 56, 90))
        text(s, "VENTANA SELLADA", 11, (200, 205, 235), (2220, 383), "center", False, False)
        rrect(s, (90, 100, 150), (96, 400, 26, 100), 4, 2, (50, 56, 90))
    if th != "school":
        text(s, FLOOR_NAMES[fi], 22, (255, 255, 255), (CORR.centerx, CORR.bottom - 14), "center", True, False, 150)
    return s


# ----------------------------------------------------------------------------
# PUZZLES
# ----------------------------------------------------------------------------
WIN = pygame.Rect(140, 70, 1000, 580)


def draw_window(s, title, accent=(90, 160, 255)):
    dim = pygame.Surface((W, H), pygame.SRCALPHA)
    dim.fill((0, 0, 12, 175))
    s.blit(dim, (0, 0))
    rrect(s, (0, 0, 0), WIN.move(6, 10), 16, alpha=90)
    rrect(s, (24, 26, 42), WIN, 16)
    pygame.draw.rect(s, (38, 42, 66), (WIN.x, WIN.y, WIN.w, 44), border_top_left_radius=16, border_top_right_radius=16)
    for i, c in enumerate(((255, 95, 86), (255, 189, 46), (39, 201, 63))):
        pygame.draw.circle(s, c, (WIN.x + 26 + i * 24, WIN.y + 22), 7)
    text(s, title, 20, (224, 228, 248), (WIN.centerx, WIN.y + 22), "center", True)
    pygame.draw.rect(s, accent, (WIN.x, WIN.y + 44, WIN.w, 3))
    pygame.draw.rect(s, (70, 76, 112), WIN, 2, border_radius=16)
    return pygame.Rect(WIN.x + 24, WIN.y + 62, WIN.w - 48, WIN.h - 100)


class Puzzle:
    name = ""
    desc = ""
    lesson = ""
    accent = (90, 160, 255)

    def __init__(self, game):
        self.g = game
        self.done = False
        self.msg = ""
        self.msg_good = False
        self.msg_t = 0
        self.errors = 0
        self.fin_t = 0

    def say(self, t, good=False):
        self.msg, self.msg_good, self.msg_t = t, good, 4.0

    def fail(self, t):
        self.errors += 1
        self.g.errors += 1
        self.g.sfx.play("err")
        self.say(t, False)

    def win(self):
        self.done = True
        self.fin_t = 1.1
        self.g.sfx.play("ok")

    def update(self, dt):
        if self.msg_t > 0:
            self.msg_t -= dt

    def frame(self, s):
        c = draw_window(s, self.name, self.accent)
        para(s, self.desc, 18, (180, 188, 220), c.x, c.y, c.w, shadow=False)
        return c

    def footer(self, s):
        if self.msg_t > 0 and self.msg:
            col = (120, 230, 150) if self.msg_good else (255, 130, 130)
            text(s, self.msg, 19, col, (WIN.centerx, WIN.bottom - 24), "center", True)
        else:
            text(s, "ESC: salir del terminal", 15, (110, 118, 150), (WIN.centerx, WIN.bottom - 24), "center", False, False)
        if self.done:
            ov = pygame.Surface(WIN.size, pygame.SRCALPHA)
            pygame.draw.rect(ov, (20, 80, 50, 190), ov.get_rect(), border_radius=16)
            s.blit(ov, WIN.topleft)
            text(s, "¡ACCESO CONCEDIDO!", 46, (170, 255, 200), WIN.center, "center", True)

    def event(self, e):
        pass

    def draw(self, s):
        pass


def button(s, rect, label, hover=False, size=20, base=(60, 110, 220)):
    col = lerpc(base, (255, 255, 255), 0.18 if hover else 0)
    rrect(s, (0, 0, 0), pygame.Rect(rect).move(0, 4), 10, alpha=80)
    rrect(s, col, rect, 10, 2, lerpc(col, (255, 255, 255), 0.4))
    text(s, label, size, (255, 255, 255), pygame.Rect(rect).center, "center", True)


FILES = [("tarea_historia.docx", "doc"), ("informe_final.pdf", "doc"), ("presentacion.pptx", "doc"),
         ("selfie_pasillo.png", "img"), ("foto_grupo.jpg", "img"), ("meme_gracioso.gif", "img"),
         ("cancion_favorita.mp3", "aud"), ("nota_de_voz.wav", "aud"), ("podcast_tech.ogg", "aud")]
KIND_COL = {"doc": (80, 140, 240), "img": (90, 200, 130), "aud": (250, 170, 70)}


class FileSort(Puzzle):
    name = "Explorador de archivos"
    desc = "Ordena cada archivo en su carpeta correcta: haz clic en un archivo y luego en la carpeta."
    lesson = "Organizar tus archivos por tipo te ahorra tiempo y evita perder información importante."
    accent = (90, 160, 255)

    def __init__(self, g):
        super().__init__(g)
        self.files = [{"n": n, "k": k} for n, k in random.sample(FILES, 6)]
        self.sel = None
        self.counts = {"doc": 0, "img": 0, "aud": 0}
        self.flash = {}

    def frects(self):
        c = pygame.Rect(WIN.x + 24, WIN.y + 62, WIN.w - 48, WIN.h - 100)
        out = []
        for i, f in enumerate(self.files):
            out.append(pygame.Rect(c.x + (i % 3) * 310, c.y + 70 + (i // 3) * 84, 290, 64))
        return out

    def folders(self):
        c = pygame.Rect(WIN.x + 24, WIN.y + 62, WIN.w - 48, WIN.h - 100)
        return [(pygame.Rect(c.x + i * 310, c.y + 260, 290, 150), n, k)
                for i, (n, k) in enumerate((("Documentos", "doc"), ("Imágenes", "img"), ("Audio", "aud")))]

    def event(self, e):
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 and not self.done:
            for i, r in enumerate(self.frects()):
                if r.collidepoint(e.pos):
                    self.sel = i
                    self.g.sfx.play("click")
                    return
            for r, n, k in self.folders():
                if r.collidepoint(e.pos) and self.sel is not None:
                    f = self.files[self.sel]
                    if f["k"] == k:
                        self.counts[k] += 1
                        self.files.pop(self.sel)
                        self.say("¡Bien! Archivo guardado.", True)
                        self.g.sfx.play("item")
                        self.flash[k] = (0.4, (90, 220, 140))
                        if not self.files:
                            self.win()
                    else:
                        self.fail(f"“{f['n']}” no va en {n}. Fíjate en la extensión.")
                        self.flash[k] = (0.4, (240, 80, 80))
                    self.sel = None
                    return

    def update(self, dt):
        super().update(dt)
        for k in list(self.flash):
            t, c = self.flash[k]
            if t - dt <= 0:
                del self.flash[k]
            else:
                self.flash[k] = (t - dt, c)

    def draw(self, s):
        c = self.frame(s)
        mp = pygame.mouse.get_pos()
        for i, (r, f) in enumerate(zip(self.frects(), self.files)):
            sel = self.sel == i
            rrect(s, (0, 0, 0), r.move(0, 4), 12, alpha=70)
            rrect(s, (44, 50, 78) if not sel else (60, 72, 120), r, 12, 2, (120, 190, 255) if sel else (70, 78, 120))
            icon = pygame.Rect(r.x + 10, r.y + 10, 44, 44)
            rrect(s, KIND_COL[f["k"]], icon, 8)
            text(s, f["n"].split(".")[-1].upper(), 15, (255, 255, 255), icon.center, "center", True)
            text(s, f["n"], 17, (230, 234, 250), (r.x + 64, r.centery), "midleft", False, False)
        for r, n, k in self.folders():
            hover = r.collidepoint(mp) and self.sel is not None
            fl = self.flash.get(k)
            body = (70, 82, 128) if not hover else (90, 106, 160)
            if fl:
                body = fl[1]
            tab = pygame.Rect(r.x, r.y - 14, 100, 24)
            rrect(s, KIND_COL[k], tab, 8)
            rrect(s, body, r, 14, 3, KIND_COL[k])
            text(s, n, 24, (255, 255, 255), (r.centerx, r.centery - 10), "center", True)
            text(s, f"{self.counts[k]} archivos", 16, (200, 208, 240), (r.centerx, r.centery + 24), "center", False, False)
        self.footer(s)


SEARCH_SCENES = [
    ("Averigua la fecha OFICIAL de la feria de ciencias del colegio. Escribe palabras clave y elige la fuente más confiable.",
     [("Feria de ciencias CANCELADA (me lo reenviaron en una cadena)", "chisme-red.net/cadena", "Reenvía esto a 10 contactos o tendrás mala suerte.", "feria ciencias cancelada fecha", False, "Es una cadena sin fuente. ¡No la creas ni la reenvíes!"),
      ("Calendario académico oficial: Feria de Ciencias, 14 de noviembre", "colegio.edu.co/calendario", "Publicado por la coordinación académica del colegio.", "feria ciencias fecha calendario oficial colegio", True, ""),
      ("¡Gana dinero fácil con la feria de ciencias!", "clic-premios.biz", "Haz clic aquí para ganar un premio increíble.", "feria ciencias dinero fecha premios", False, "Es publicidad engañosa (clickbait)."),
      ("Foro: creo que la feria era en diciembre", "foro-estudiantes.net", "Una opinión sin ninguna fuente.", "feria ciencias diciembre foro fecha", False, "Es una opinión, no una fuente oficial.")]),
    ("Encuentra el horario OFICIAL de la biblioteca del colegio. Busca con palabras clave y verifica la fuente.",
     [("Biblioteca abre 24 horas, dice mi primo", "memes-y-mas.com/post", "Mi primo me contó que nunca cierra.", "biblioteca horario abre", False, "Es un rumor de segunda mano."),
      ("Horario de atención de la biblioteca: lunes a viernes, 7:00 a 17:00", "colegio.edu.co/biblioteca", "Información publicada por el colegio.", "biblioteca horario atencion colegio oficial", True, ""),
      ("DESCARGA GRATIS tu carné de biblioteca", "descargas-ya.xyz", "Instala este programa para ver el horario.", "biblioteca horario carne descarga", False, "Pide instalar un programa: es una señal de peligro (malware)."),
      ("Opinión: la biblioteca debería abrir los sábados", "blog-opinion.org", "Un estudiante da su punto de vista.", "biblioteca sabados opinion horario", False, "Es una opinión, no el horario oficial.")]),
    ("¿Hay clases el próximo lunes festivo? Consulta con palabras clave y elige la fuente que realmente puede saberlo.",
     [("Lunes sin clases, ¡es seguro! (captura de pantalla borrosa)", "imagenes-virales.com", "Captura sin fecha ni firma.", "lunes clases festivo captura", False, "Una captura sin origen se puede editar fácilmente."),
      ("Circular oficial: el lunes festivo no habrá actividades académicas", "colegio.edu.co/circulares", "Firmada por la rectoría.", "lunes festivo clases circular oficial rectoria", True, ""),
      ("Urgente: tu cuenta del colegio será bloqueada", "colegio-verifica.top", "Ingresa tu contraseña para verificar el festivo.", "lunes festivo cuenta contraseña clases", False, "Es phishing: pide tu contraseña. Nunca la entregues."),
      ("Chat de grupo: dicen que sí hay clase", "grupo-chat.app", "Mensajes sin confirmar.", "lunes clases festivo grupo chat", False, "Los chats de grupo no son una fuente confirmada.")]),
]


class SearchPuzzle(Puzzle):
    name = "Buscador"
    lesson = "Verifica siempre la fuente: dominios oficiales (.edu.co), datos claros y nada de pedir contraseñas."
    accent = (255, 190, 80)

    def __init__(self, g):
        super().__init__(g)
        self.sc = random.choice(SEARCH_SCENES)
        self.desc = self.sc[0]
        self.q = ""
        self.t = 0

    def matches(self):
        words = [w for w in self.q.lower().replace(",", " ").split() if len(w) > 2]
        if not words:
            return []
        out = []
        for r in self.sc[1]:
            tags = [x.strip(".,:¡!¿?()“”") for x in (r[3].split() + r[0].lower().split())]
            if any(any(tag.startswith(w) or (len(tag) > 3 and w.startswith(tag)) for tag in tags) for w in words):
                out.append(r)
        return out

    def rects(self, n):
        c = pygame.Rect(WIN.x + 24, WIN.y + 62, WIN.w - 48, WIN.h - 100)
        return [pygame.Rect(c.x, c.y + 130 + i * 84, c.w, 74) for i in range(n)]

    def event(self, e):
        if self.done:
            return
        if e.type == pygame.KEYDOWN:
            if e.key == pygame.K_BACKSPACE:
                self.q = self.q[:-1]
            elif e.unicode and e.unicode.isprintable() and len(self.q) < 40:
                self.q += e.unicode
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            res = self.matches()
            for r, res_i in zip(self.rects(len(res)), res):
                if r.collidepoint(e.pos):
                    if res_i[4]:
                        self.say("¡Correcto! Fuente oficial y verificable.", True)
                        self.win()
                    else:
                        self.fail(res_i[5])

    def update(self, dt):
        super().update(dt)
        self.t += dt

    def draw(self, s):
        c = self.frame(s)
        bar = pygame.Rect(c.x, c.y + 62, c.w, 48)
        rrect(s, (240, 242, 250), bar, 24, 2, (150, 160, 200))
        pygame.draw.circle(s, (90, 100, 150), (bar.x + 28, bar.centery - 2), 9, 3)
        pygame.draw.line(s, (90, 100, 150), (bar.x + 34, bar.centery + 4), (bar.x + 42, bar.centery + 12), 3)
        shown = self.q + ("|" if int(self.t * 2) % 2 == 0 else "")
        if not self.q:
            text(s, "Escribe palabras clave (ej: feria, horario, fecha)…", 19, (150, 156, 180), (bar.x + 56, bar.centery), "midleft", False, False)
        text(s, shown, 21, (30, 34, 60), (bar.x + 56, bar.centery), "midleft", False, False)
        res = self.matches()
        for r, it in zip(self.rects(len(res)), res):
            hov = r.collidepoint(pygame.mouse.get_pos())
            rrect(s, (44, 50, 80) if not hov else (60, 70, 110), r, 12, 2, (80, 90, 140))
            text(s, it[0], 19, (140, 190, 255), (r.x + 16, r.y + 10), "topleft", True, False)
            text(s, it[1], 15, (110, 220, 140), (r.x + 16, r.y + 34), "topleft", False, False)
            text(s, it[2], 15, (180, 186, 210), (r.x + 16, r.y + 52), "topleft", False, False)
        if self.q and not res:
            text(s, "Sin resultados. Prueba otras palabras clave.", 19, (200, 200, 220), (c.centerx, c.y + 180), "center", False, False)
        self.footer(s)


class SpreadSheet(Puzzle):
    name = "Hoja de cálculo"
    desc = "Completa las celdas marcadas. Total = Cantidad × Precio. La celda del total general es la SUMA de la columna D."
    lesson = "Las fórmulas (como multiplicar y SUMA) te ayudan a calcular rápido y sin errores."
    accent = (110, 220, 150)

    def __init__(self, g):
        super().__init__(g)
        names = random.sample(INGREDIENTS, 4)
        self.rows = []
        for n in names:
            q, p = random.randint(2, 6), random.randint(2, 9)
            self.rows.append([n, q, p, q * p])
        self.total = sum(r[3] for r in self.rows)
        self.edit = [(2, 3), (3, 3), (4, 3)]
        self.vals = {k: "" for k in self.edit}
        self.cur = 0
        self.t = 0

    def cell_rect(self, r, c):
        base = pygame.Rect(WIN.x + 90, WIN.y + 150, 0, 0)
        xs = [0, 280, 440, 600]
        ws = [280, 160, 160, 180]
        return pygame.Rect(base.x + xs[c], base.y + r * 52, ws[c], 52)

    def check(self):
        ok = True
        for (r, c), v in self.vals.items():
            correct = self.rows[r][3] if r < 4 else self.total
            if v == "" or int(v) != correct:
                ok = False
        if ok:
            self.say("¡Todo correcto!", True)
            self.win()
        else:
            self.fail("Algún valor no coincide. Revisa las multiplicaciones y la suma.")

    def event(self, e):
        if self.done:
            return
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            for i, (r, c) in enumerate(self.edit):
                if self.cell_rect(r + 1, c).collidepoint(e.pos):
                    self.cur = i
                    self.g.sfx.play("click")
            if self.vbtn().collidepoint(e.pos):
                self.check()
        elif e.type == pygame.KEYDOWN:
            k = self.edit[self.cur]
            if e.key == pygame.K_BACKSPACE:
                self.vals[k] = self.vals[k][:-1]
            elif e.key in (pygame.K_TAB, pygame.K_DOWN):
                self.cur = (self.cur + 1) % len(self.edit)
            elif e.key == pygame.K_UP:
                self.cur = (self.cur - 1) % len(self.edit)
            elif e.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                if self.cur < len(self.edit) - 1:
                    self.cur += 1
                else:
                    self.check()
            elif e.unicode.isdigit() and len(self.vals[k]) < 4:
                self.vals[k] += e.unicode

    def vbtn(self):
        return pygame.Rect(WIN.centerx - 90, WIN.bottom - 92, 180, 46)

    def update(self, dt):
        super().update(dt)
        self.t += dt

    def draw(self, s):
        self.frame(s)
        k = self.edit[self.cur]
        formula = f"D{k[0] + 1} = B{k[0] + 1} * C{k[0] + 1}" if k[0] < 4 else "D6 = SUMA(D2:D5)"
        fx = pygame.Rect(WIN.x + 90, WIN.y + 112, 780, 30)
        rrect(s, (36, 40, 60), fx, 6, 1, (70, 76, 110))
        text(s, "fx", 16, (110, 220, 150), (fx.x + 12, fx.centery), "midleft", True, False)
        text(s, formula + "   (el total general suma D2 hasta D5)" if k[0] == 4 else formula, 16, (220, 224, 246), (fx.x + 50, fx.centery), "midleft", False, False)
        headers = ["A · Ingrediente", "B · Cantidad", "C · Precio", "D · Total"]
        for c in range(4):
            r = self.cell_rect(0, c)
            rrect(s, (50, 70, 62), r, 0, 1, (80, 110, 100))
            text(s, headers[c], 17, (200, 255, 220), r.center, "center", True, False)
        for ri in range(5):
            for c in range(4):
                r = self.cell_rect(ri + 1, c)
                is_edit = (ri, c) in self.vals
                is_cur = is_edit and self.edit[self.cur] == (ri, c)
                bg = (30, 34, 50) if not is_edit else (44, 54, 80)
                rrect(s, bg, r, 0, 1, (70, 76, 110))
                if is_cur:
                    pygame.draw.rect(s, (110, 230, 160), r, 3)
                if ri < 4:
                    label = ["", str(self.rows[ri][1]), str(self.rows[ri][2]), str(self.rows[ri][3])][c] if c else self.rows[ri][0]
                else:
                    label = "TOTAL" if c == 0 else ""
                if is_edit:
                    label = self.vals[(ri, c)] + ("|" if is_cur and int(self.t * 2) % 2 == 0 else "")
                col = (255, 230, 150) if is_edit else (224, 228, 246)
                text(s, label, 20, col, r.center if c else (r.x + 14, r.centery), "center" if c else "midleft", ri == 4, False)
        button(s, self.vbtn(), "VERIFICAR", self.vbtn().collidepoint(pygame.mouse.get_pos()), 20, (40, 150, 100))
        self.footer(s)


BANNED = ["1234", "password", "contraseña", "qwerty", "abcd", "admin", "oldmemories", "colegio", "0000"]


class PasswordPuzzle(Puzzle):
    name = "Contraseña segura"
    desc = "Crea una contraseña que cumpla TODOS los requisitos. Piensa en una frase larga que solo tú entiendas."
    lesson = "Una contraseña larga, única y sin datos personales protege tus cuentas. ¡No la compartas!"
    accent = (200, 130, 255)

    def __init__(self, g):
        super().__init__(g)
        self.pw = ""
        self.show = True
        self.t = 0

    def rules(self):
        p = self.pw
        low = p.lower()
        rep = any(p[i] == p[i + 1] == p[i + 2] for i in range(len(p) - 2))
        return [("Al menos 12 caracteres", len(p) >= 12),
                ("Una letra mayúscula", any(ch.isupper() for ch in p)),
                ("Una letra minúscula", any(ch.islower() for ch in p)),
                ("Un número", any(ch.isdigit() for ch in p)),
                ("Un símbolo (!, #, $, %, &, *, _, -)", any((not ch.isalnum()) and ch != " " for ch in p)),
                ("Sin secuencias típicas (1234, password, qwerty…)", len(p) > 0 and not any(b in low for b in BANNED)),
                ("Sin 3 caracteres iguales seguidos", len(p) > 0 and not rep)]

    def eye(self):
        return pygame.Rect(WIN.right - 90, WIN.y + 130, 44, 44)

    def event(self, e):
        if self.done:
            return
        if e.type == pygame.KEYDOWN:
            if e.key == pygame.K_BACKSPACE:
                self.pw = self.pw[:-1]
            elif e.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                if all(ok for _, ok in self.rules()):
                    self.say("¡Contraseña aceptada!", True)
                    self.win()
                else:
                    self.fail("Aún faltan requisitos por cumplir.")
            elif e.unicode and e.unicode.isprintable() and len(self.pw) < 32:
                self.pw += e.unicode
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 and self.eye().collidepoint(e.pos):
            self.show = not self.show

    def update(self, dt):
        super().update(dt)
        self.t += dt

    def draw(self, s):
        c = self.frame(s)
        box = pygame.Rect(c.x, c.y + 66, c.w - 80, 44)
        rrect(s, (16, 18, 30), box, 10, 2, (130, 100, 200))
        shown = self.pw if self.show else "•" * len(self.pw)
        text(s, shown + ("|" if int(self.t * 2) % 2 == 0 else ""), 24, (240, 240, 255), (box.x + 14, box.centery), "midleft", False, False)
        e = self.eye()
        rrect(s, (50, 54, 84), e, 10)
        pygame.draw.ellipse(s, (220, 224, 250), (e.x + 8, e.y + 13, 28, 18), 2)
        if self.show:
            pygame.draw.circle(s, (220, 224, 250), e.center, 5)
        rules = self.rules()
        okn = sum(1 for _, ok in rules if ok)
        sb = pygame.Rect(c.x, c.y + 130, c.w - 120, 16)
        rrect(s, (30, 32, 50), sb, 8)
        fill = pygame.Rect(sb.x, sb.y, int(sb.w * okn / len(rules)), sb.h)
        col = lerpc((240, 80, 80), (90, 230, 140), okn / len(rules))
        if fill.w > 0:
            rrect(s, col, fill, 8)
        text(s, ["Muy débil", "Muy débil", "Débil", "Débil", "Media", "Buena", "Fuerte", "¡Excelente!"][okn], 16, col, (sb.right + 12, sb.centery), "midleft", True, False)
        for i, (lbl, ok) in enumerate(rules):
            y = c.y + 170 + i * 36
            pygame.draw.circle(s, (90, 230, 140) if ok else (90, 94, 124), (c.x + 16, y + 12), 11)
            if ok:
                pygame.draw.lines(s, (10, 40, 20), False, [(c.x + 10, y + 12), (c.x + 15, y + 17), (c.x + 23, y + 7)], 3)
            text(s, lbl, 19, (224, 228, 246) if ok else (150, 156, 186), (c.x + 40, y + 12), "midleft", False, False)
        text(s, "Pulsa ENTER para confirmar", 16, (170, 176, 210), (c.right - 20, c.bottom - 6), "bottomright", False, False)
        self.footer(s)


FACTS_T = ["Un correo que se hace pasar por tu banco para robarte datos se llama phishing.",
           "Una imagen puede estar editada; conviene buscar su origen con una búsqueda inversa.",
           "Colombia tiene 32 departamentos y un Distrito Capital (Bogotá).",
           "El agua hierve a 100 °C al nivel del mar.",
           "Un candado en el navegador cifra la conexión, pero no garantiza que el sitio sea honesto.",
           "La Tierra tarda cerca de 365 días en dar una vuelta al Sol."]
FACTS_F = ["Si una noticia tiene muchos “me gusta”, entonces es verdadera.",
           "Es seguro compartir tu contraseña con tu mejor amigo.",
           "La capital de Colombia es Medellín.",
           "Los mensajes en cadena que piden reenviar a 10 contactos siempre son ciertos.",
           "El Sol gira alrededor de la Tierra.",
           "Un correo urgente que pide tu clave bancaria siempre es legítimo."]


class FactCheck(Puzzle):
    name = "Verificador de datos"
    desc = "Hay 3 afirmaciones FALSAS o engañosas. Márcalas con un clic y pulsa VERIFICAR."
    lesson = "Pensamiento crítico: los “me gusta” y las cadenas no prueban que algo sea verdad."
    accent = (255, 120, 120)

    def __init__(self, g):
        super().__init__(g)
        items = [(t, True) for t in random.sample(FACTS_T, 3)] + [(t, False) for t in random.sample(FACTS_F, 3)]
        random.shuffle(items)
        self.items = items
        self.marked = set()

    def rects(self):
        c = pygame.Rect(WIN.x + 24, WIN.y + 62, WIN.w - 48, WIN.h - 100)
        return [pygame.Rect(c.x, c.y + 50 + i * 62, c.w, 54) for i in range(6)]

    def vbtn(self):
        return pygame.Rect(WIN.centerx - 90, WIN.bottom - 80, 180, 44)

    def event(self, e):
        if self.done:
            return
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            for i, r in enumerate(self.rects()):
                if r.collidepoint(e.pos):
                    self.marked ^= {i}
                    self.g.sfx.play("click")
            if self.vbtn().collidepoint(e.pos):
                truth = {i for i, (_, t) in enumerate(self.items) if not t}
                if self.marked == truth:
                    self.say("¡Excelente criterio!", True)
                    self.win()
                else:
                    wrong = len(self.marked ^ truth)
                    self.fail(f"Hay {wrong} afirmación(es) mal clasificada(s). Piensa de nuevo.")

    def draw(self, s):
        self.frame(s)
        mp = pygame.mouse.get_pos()
        for i, (r, it) in enumerate(zip(self.rects(), self.items)):
            mk = i in self.marked
            bg = (110, 40, 52) if mk else ((50, 56, 90) if r.collidepoint(mp) else (38, 42, 68))
            rrect(s, bg, r, 12, 2, (240, 110, 110) if mk else (70, 78, 120))
            pygame.draw.rect(s, (240, 110, 110) if mk else (90, 96, 130), (r.x + 14, r.y + 15, 24, 24), 3, border_radius=6)
            if mk:
                pygame.draw.lines(s, (255, 150, 150), False, [(r.x + 19, r.y + 27), (r.x + 25, r.y + 33), (r.x + 34, r.y + 20)], 4)
            text(s, it[0], 18, (230, 234, 250), (r.x + 54, r.centery), "midleft", False, False)
        button(s, self.vbtn(), "VERIFICAR", self.vbtn().collidepoint(mp), 20, (200, 70, 80))
        self.footer(s)


POSTS_BAD = ["Miren cómo se viste la rara del salón, jajaja #risas",
             "Dicen que a ella nadie la quiere, ¡reenvíen el chisme!",
             "Subí su foto sin permiso, ¡se va a hacer viral jajaja!",
             "Creé un grupo para burlarnos de ella, ¡únanse!",
             "Nadie le habla, qué bueno que se quede sola."]
POSTS_OK = ["Hoy salimos temprano, ¡buen día a todos!",
            "¿Alguien me ayuda con la tarea de matemáticas?",
            "Qué bonito atardecer hoy desde mi ventana.",
            "Feliz cumpleaños a mi mejor amigo.",
            "Les recomiendo este libro, está genial."]


class DeletePosts(Puzzle):
    name = "Red social · Mis publicaciones antiguas"
    desc = "Borra las publicaciones hirientes que hiciste en el pasado. Conserva las demás."
    lesson = "Lo que publicas deja una huella digital. Borrar ayuda, pero lo mejor es no hacer daño en línea."
    accent = (255, 150, 90)

    def __init__(self, g):
        super().__init__(g)
        bad = [(t, True) for t in random.sample(POSTS_BAD, 4)]
        ok = [(t, False) for t in random.sample(POSTS_OK, 3)]
        self.posts = bad + ok
        random.shuffle(self.posts)
        self.left_bad = 4

    def rects(self):
        c = pygame.Rect(WIN.x + 24, WIN.y + 62, WIN.w - 48, WIN.h - 100)
        return [pygame.Rect(c.x, c.y + 44 + i * 58, c.w, 52) for i in range(len(self.posts))]

    def event(self, e):
        if self.done:
            return
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            for i, r in enumerate(self.rects()):
                b = pygame.Rect(r.right - 120, r.y + 9, 108, 34)
                if b.collidepoint(e.pos):
                    t, bad = self.posts[i]
                    if bad:
                        self.posts.pop(i)
                        self.left_bad -= 1
                        self.g.sfx.play("item")
                        self.say("Publicación eliminada. Pero la huella digital puede quedar…", True)
                        if self.left_bad == 0:
                            self.win()
                    else:
                        self.fail("Esa publicación no es hiriente. Bórrala solo si hace daño.")
                    return

    def draw(self, s):
        self.frame(s)
        mp = pygame.mouse.get_pos()
        for r, (t, bad) in zip(self.rects(), self.posts):
            rrect(s, (38, 42, 68), r, 12, 2, (70, 78, 120))
            pygame.draw.circle(s, (120, 130, 200), (r.x + 30, r.centery), 18)
            pygame.draw.circle(s, (230, 235, 255), (r.x + 30, r.centery - 5), 6)
            pygame.draw.ellipse(s, (230, 235, 255), (r.x + 20, r.centery + 2, 20, 14))
            text(s, "Tú · hace 3 años", 13, (150, 158, 190), (r.x + 62, r.y + 6), "topleft", False, False)
            text(s, t, 17, (230, 234, 250), (r.x + 62, r.y + 25), "topleft", False, False)
            b = pygame.Rect(r.right - 120, r.y + 9, 108, 34)
            button(s, b, "Eliminar", b.collidepoint(mp), 17, (190, 60, 70))
        text(s, f"Hirientes por borrar: {self.left_bad}", 16, (255, 190, 130), (WIN.right - 36, WIN.y + 64), "topright", True, False)
        self.footer(s)


PUZZLES = [FileSort, SearchPuzzle, SpreadSheet, PasswordPuzzle, FactCheck, DeletePosts]


# ----------------------------------------------------------------------------
# ACTORES
# ----------------------------------------------------------------------------
class Actor:
    def __init__(self, x, y):
        self.x, self.y = x, y
        self.face = "r"
        self.anim = 0.0
        self.moving = False


class Chaser(Actor):
    def __init__(self, x, y, floor):
        super().__init__(x, y)
        self.floor = floor
        self.state = "patrol"
        self.path = []
        self.timer = 0.0
        self.replan = 0.0
        self.last_seen = None
        self.lost = 0.0
        self.follow = None
        self.alerted = False


# ----------------------------------------------------------------------------
# JUEGO
# ----------------------------------------------------------------------------
STORY = [
    "Hace años, en estos mismos pasillos, hiciste daño. Burlas, chismes, fotos subidas sin permiso… todo quedó guardado en la red.",
    "Anoche despertaste atada a un pupitre. El colegio está vacío y a oscuras. Alguien no ha olvidado nada.",
    "Ella vigila la salida principal. Su ayudante, un demonio nacido de tus recuerdos, recorre los siete pisos buscándote, y si te atrapa te llevará ante ella.",
    "Hay dos salidas: la de incendios, cerrada con una llave rota en 6 fragmentos, o la principal, si le preparas su plato favorito, un sancocho, como muestra de perdón. Cada ingrediente está junto a un fragmento. Tú eliges.",
    "Tienes 5 minutos. Cuando el reloj llegue a cero, ella abandonará su puesto y te cazará durante 1 minuto, y su ayudante se retirará para que solo ella te persiga. Contra ella no sirven los escondites: solo un objeto puede hacerle perder tu rastro.",
    "Si el ayudante te pierde de vista, se teletransportará a otro piso. Y si te escondes en un casillero (E), controla tu pulso con ESPACIO para que no te escuche.",
]
INTRO_SPRITES = ["hero", "chaser", "entity", "sofia", "entity", "chaser"]
NPC_TIPS = [
    "¿Sabías que la huella digital no desaparece? Aunque borres algo, alguien pudo guardarlo.",
    "Si un mensaje te pide tu contraseña con urgencia, es phishing. Nunca la compartas.",
    "Antes de compartir una noticia, revisa la fuente, la fecha y si otros medios la confirman.",
    "Una contraseña larga y única vale más que una corta con símbolos raros.",
    "Pedir perdón de verdad es más difícil que borrar un mensaje…",
    "Una foto puede estar editada. Busca su origen antes de creerla o compartirla.",
    "Antes de subir la foto de alguien, pídele permiso. Su imagen también es suya.",
    "El ciberacoso hiere igual que el acoso en persona. Si lo ves, no lo reenvíes: repórtalo.",
    "Activa la verificación en dos pasos: aunque roben tu clave, no podrán entrar tan fácil.",
    "Un candado en el navegador no significa que el sitio sea confiable. Revisa la dirección.",
]
ENDINGS = {
    "redemption": ("REDENCIÓN", (120, 230, 170),
                   ["Le entregaste el sancocho temblando. Ella lo probó en silencio.",
                    "—No borra lo que pasó —dijo—, pero es la primera vez que alguien me pide perdón de verdad.",
                    "La puerta principal se abrió. Aprendiste que ser responsable en línea (y fuera de ella) importa más que cualquier contraseña."]),
    "escape": ("ESCAPE", (255, 190, 100),
               ["Armaste la llave y huiste por la salida de incendios. Estás a salvo… por ahora.",
                "Pero la huella digital sigue ahí: lo que publicaste no desaparece solo porque tú corras.",
                "Quizá la próxima vez elijas reparar el daño en lugar de escapar de él."]),
}


class Game:
    def __init__(self):
        pygame.mixer.pre_init(44100, -16, 1, 512)
        pygame.init()
        pygame.display.set_caption("OLD MEMORIES")
        try:
            self.screen = pygame.display.set_mode((W, H), pygame.SCALED | pygame.RESIZABLE)
        except Exception:
            self.screen = pygame.display.set_mode((W, H))
        self.clock = pygame.time.Clock()
        self.loading("Cargando recuerdos…")
        self.sfx = Sfx()
        self.diff = 1
        self.fullscreen = False
        self.sprites = {}
        for k in PEOPLE:
            self.sprites[k] = [person_surface(k, i, (56, 89)) for i in range(4)]
        self.sprites["chaser"] = [demon_surface(i, (64, 102)) for i in range(4)]
        self.sprites["entity"] = [ghost_surface(i, (70, 111)) for i in range(4)]
        self.icons = {}
        for n in INGREDIENTS + DISTRACT + ["Sancocho"] + [f"Llave{i}" for i in range(1, 7)]:
            self.icons[n] = make_icon(n, 40)
        self.big_icons = {n: make_icon(n, 64) for n in INGREDIENTS + ["Sancocho"]}
        self.floors = [render_floor(i).convert() for i in range(FLOORS)]
        self.layouts = [build_layout(i) for i in range(FLOORS)]
        self.obstacles = [l["obs"] for l in self.layouts]
        self.grids = [self.build_grid(i) for i in range(FLOORS)]
        self.light_big = glow_circle(320, (0, 0, 0), 238, 1.3)
        self.light_small = glow_circle(285, (0, 0, 0), 238, 1.3)
        self.light_mid = glow_circle(120, (0, 0, 0), 190, 1.2)
        self.light_pad = glow_circle(170, (0, 0, 0), 200, 1.2)
        self.red_glow = glow_add(190, (255, 40, 50), 0.75, 1.6)
        self.pad_glow = glow_add(150, (90, 200, 255), 0.55, 1.5)
        self.term_glow = glow_add(70, (90, 180, 255), 0.5, 1.4)
        self.vignette = self.make_vignette((200, 20, 30))
        self.menu_glow = pygame.transform.smoothscale(self.red_glow, (700, 700))
        self.dark = pygame.Surface((W, H), pygame.SRCALPHA)
        self.menu_bg = self.floors[0].subsurface(pygame.Rect(260, 180, 1280, 720)).copy()
        ov = pygame.Surface((W, H), pygame.SRCALPHA)
        ov.fill((8, 6, 22, 205))
        self.menu_bg.blit(ov, (0, 0))
        self.particles = [[random.uniform(0, W), random.uniform(0, H), random.uniform(6, 22), random.uniform(10, 40), random.random() * 6] for _ in range(36)]
        self.state = "menu"
        self.prev_state = "menu"
        self.sel = 0
        self.btns = []
        self.t = 0.0
        self.toasts = []
        self.slide = 0
        self.slide_t = 0.0
        self.shake = 0.0
        self.new_run()

    # -------------------------------------------------------------- utilidades
    def loading(self, msg):
        self.screen.fill((8, 6, 20))
        text(self.screen, msg, 32, (220, 224, 255), (W // 2, H // 2), "center", True)
        pygame.display.flip()

    def make_vignette(self, col):
        v = pygame.Surface((W, H), pygame.SRCALPHA)
        for i in range(60):
            a = int(150 * (1 - i / 60) ** 2)
            pygame.draw.rect(v, (*col, a), (i * 4, i * 2, W - i * 8, H - i * 4), 8, border_radius=40)
        return v

    def build_grid(self, fi):
        g = set()
        for cx in range(WORLD_W // CELL):
            for cy in range(WORLD_H // CELL):
                if self.can_stand(fi, cx * CELL + CELL // 2, cy * CELL + CELL // 2, obs=self.obstacles[fi]):
                    g.add((cx, cy))
        return g

    def can_stand(self, fi, x, y, w=24, h=16, obs=None):
        r = pygame.Rect(int(x - w / 2), int(y - h), w, h)
        for px, py in ((r.left, r.top), (r.right - 1, r.top), (r.left, r.bottom - 1), (r.right - 1, r.bottom - 1)):
            if not in_walk(px, py):
                return False
        return r.collidelist(obs if obs is not None else self.obstacles[fi]) == -1

    def toast(self, t, secs=4.0, col=(235, 238, 255)):
        self.toasts.append({"t": t, "s": secs, "c": col, "age": 0.0})
        if len(self.toasts) > 4:
            self.toasts.pop(0)

    def nearest_cell(self, fi, x, y):
        g = self.grids[fi]
        c = (int(x // CELL), int(y // CELL))
        if c in g:
            return c
        best, bd = None, 1e9
        for dx in range(-4, 5):
            for dy in range(-4, 5):
                n = (c[0] + dx, c[1] + dy)
                if n in g and dx * dx + dy * dy < bd:
                    best, bd = n, dx * dx + dy * dy
        return best

    def find_path(self, fi, start, goal):
        g = self.grids[fi]
        if start is None or goal is None or start == goal:
            return []
        prev = {start: None}
        dq = deque([start])
        while dq:
            c = dq.popleft()
            if c == goal:
                break
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
                n = (c[0] + dx, c[1] + dy)
                if n in g and n not in prev:
                    if dx and dy and ((c[0] + dx, c[1]) not in g or (c[0], c[1] + dy) not in g):
                        continue
                    prev[n] = c
                    dq.append(n)
        if goal not in prev:
            return []
        out = []
        c = goal
        while c != start:
            out.append(c)
            c = prev[c]
        out.reverse()
        return out

    def los(self, x1, y1, x2, y2):
        d = math.hypot(x2 - x1, y2 - y1)
        n = int(d // 16) + 1
        for i in range(n + 1):
            t = i / n
            if not in_walk(lerp(x1, x2, t), lerp(y1, y2, t) - 8):
                return False
        return True

    # -------------------------------------------------------------- nueva partida
    def new_run(self):
        self.floor = 0
        self.p = Actor(1400, 450)
        self.p.stamina = 100.0
        self.p.tired = False
        nroom = FLOORS * 4
        types = [PUZZLES[i % 6] for i in range(nroom)]
        random.shuffle(types)
        pair = random.sample(range(nroom), 6)
        ing_order = INGREDIENTS[:]
        random.shuffle(ing_order)
        self.rooms = []
        for fi in range(FLOORS):
            for i in range(4):
                idx = fi * 4 + i
                reward = ("item", random.choice(DISTRACT))
                if idx in pair:
                    k = pair.index(idx)
                    reward = ("pair", k + 1, ing_order[k])
                self.rooms.append(dict(floor=fi, i=i, rect=ROOMS[i], label=f"{fi + 1}0{i + 1}", ptype=types[idx], solved=False, reward=reward))
        self.frags = set()
        self.ings = set()
        self.items = {n: 0 for n in DISTRACT}
        self.items["Desinfectante"] = 1
        self.sel_item = 0
        self.sancocho = False
        self.solved = 0
        self.errors = 0
        self.play_time = 0.0
        self.npcs = []
        spots = [400, 550, 700, 1000, 1350, 1500, 1750, 2000, 2150]
        for fi in range(FLOORS):
            while True:
                xs = random.sample(spots, 2)
                if abs(xs[0] - xs[1]) > 250:
                    break
            lst = []
            for j, x in enumerate(xs):
                nm, kind, colr = NPC_DEFS[(fi + j * 3) % len(NPC_DEFS)]
                lst.append(dict(x=x, y=450 + random.randint(-30, 30), name=nm, kind=kind, col=colr,
                                talked=0, gift=(j == 1 or random.random() < 0.3)))
            self.npcs.append(lst)
        cf = random.randint(2, 5)
        self.chaser = Chaser(2100, 450, cf)
        self.chaser.timer = 0
        e = Actor(*ENTITY_POS)
        e.floor = 0
        e.state = "rest"
        e.path = []
        e.timer = 0.0
        e.replan = 0.0
        e.follow = None
        e.cool = 0.0
        self.ent = e
        self.countdown = COUNTDOWN
        self.ent_awake = False
        self.ent_done = False
        self.hunt_left = 0.0
        self.hide = None
        self.fx = []
        self.hold = 0.0
        self.shake = 0.0
        self.toasts = []
        self.dialog = None
        self.tele_t = 0.0
        self.tele_target = 0
        self.dt_warn = 0.0
        self.caught_reason = ""
        self.ending = None
        self.siren = 0.0
        self.pending_follow = 0.0
        self.nearest = None
        self.entity_near = 0.0
        self.hunt_t = 35.0
        self.puz = None
        self.puz_room = None

    def follow_delay(self):
        return [11.0, 9.0, 7.0][self.diff]

    def chase_speed(self):
        return [150, 175, 200][self.diff]

    # -------------------------------------------------------------- menus
    def menu_items(self):
        st = self.state
        if st == "menu":
            return [("JUGAR", self.start_game), ("CONTROLES", lambda: self.goto("controls")),
                    ("OPCIONES", lambda: self.goto("options")), ("CRÉDITOS", lambda: self.goto("credits")),
                    ("SALIR", self.quit)]
        if st == "options":
            return [(f"Dificultad: {DIFFS[self.diff]}", self.cycle_diff),
                    (f"Sonido: {'Activado' if self.sfx.on else 'Desactivado'}", self.toggle_sound),
                    ("Pantalla completa (F11)", self.toggle_fs), ("VOLVER", lambda: self.goto("menu"))]
        if st in ("controls", "credits"):
            return [("VOLVER", lambda: self.goto("menu"))]
        if st == "pause":
            return [("CONTINUAR", lambda: self.goto("play")), ("MENÚ PRINCIPAL", lambda: self.goto("menu")), ("SALIR", self.quit)]
        if st == "over":
            return [("REINTENTAR", self.start_game), ("MENÚ PRINCIPAL", lambda: self.goto("menu"))]
        if st == "end":
            return [("JUGAR DE NUEVO", self.start_game), ("MENÚ PRINCIPAL", lambda: self.goto("menu"))]
        return []

    def goto(self, st):
        self.state = st
        self.sel = 0
        self.sfx.play("click")

    def quit(self):
        pygame.quit()
        sys.exit()

    def cycle_diff(self):
        self.diff = (self.diff + 1) % 3
        self.sfx.play("click")

    def toggle_sound(self):
        self.sfx.on = not self.sfx.on

    def toggle_fs(self):
        try:
            pygame.display.toggle_fullscreen()
        except Exception:
            pass

    def start_game(self):
        self.new_run()
        self.state = "intro"
        self.slide = 0
        self.slide_t = 0.0
        self.sfx.play("click")

    # -------------------------------------------------------------- eventos
    def handle(self, e):
        if e.type == pygame.QUIT:
            self.quit()
        if e.type == pygame.KEYDOWN and e.key == pygame.K_F11:
            self.toggle_fs()
        st = self.state
        if st in ("menu", "options", "controls", "credits", "pause", "over", "end"):
            self.handle_menu(e)
        elif st == "intro":
            if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                self.state = "play"
            elif (e.type == pygame.KEYDOWN and e.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_e)) or \
                    (e.type == pygame.MOUSEBUTTONDOWN and e.button == 1):
                full = len(STORY[self.slide])
                if self.slide_t * 38 < full:
                    self.slide_t = 999
                else:
                    self.slide += 1
                    self.slide_t = 0
                    if self.slide >= len(STORY):
                        self.state = "play"
                        self.toast("Encuentra 6 fragmentos de llave y 6 ingredientes. ¡Tienes 5 minutos antes de que ella despierte!", 7)
        elif st == "play":
            self.handle_play(e)
        elif st == "hide":
            if e.type == pygame.KEYDOWN and e.key == pygame.K_e:
                self.stop_hide()
        elif st == "puzzle":
            if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                self.state = "play"
                self.puz = None
            elif self.puz:
                self.puz.event(e)
        elif st == "tele_select":
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    self.state = "play"
                elif pygame.K_1 <= e.key <= pygame.K_7:
                    self.start_tele(e.key - pygame.K_1)
            elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                for i, r in enumerate(self.tele_rects()):
                    if r.collidepoint(e.pos):
                        self.start_tele(i)
        elif st == "dialog":
            if (e.type == pygame.KEYDOWN and e.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_e, pygame.K_ESCAPE)) or \
                    (e.type == pygame.MOUSEBUTTONDOWN and e.button == 1):
                d = self.dialog
                if d["t"] * 40 < len(d["lines"][d["i"]]):
                    d["t"] = 999
                else:
                    d["i"] += 1
                    d["t"] = 0
                    if d["i"] >= len(d["lines"]):
                        self.state = "play"
                        if d.get("after"):
                            d["after"]()

    def handle_menu(self, e):
        items = self.menu_items()
        if e.type == pygame.KEYDOWN:
            if e.key in (pygame.K_DOWN, pygame.K_s):
                self.sel = (self.sel + 1) % len(items)
                self.sfx.play("click")
            elif e.key in (pygame.K_UP, pygame.K_w):
                self.sel = (self.sel - 1) % len(items)
                self.sfx.play("click")
            elif e.key in (pygame.K_RETURN, pygame.K_SPACE):
                items[self.sel][1]()
            elif e.key == pygame.K_ESCAPE:
                if self.state == "pause":
                    self.state = "play"
                elif self.state in ("options", "controls", "credits"):
                    self.goto("menu")
        elif e.type == pygame.MOUSEMOTION:
            for i, r in enumerate(self.btns):
                if r.collidepoint(e.pos) and i != self.sel:
                    self.sel = i
                    self.sfx.play("click")
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            for i, r in enumerate(self.btns):
                if r.collidepoint(e.pos) and i < len(items):
                    self.sel = i
                    items[i][1]()
                    break

    def handle_play(self, e):
        if e.type != pygame.KEYDOWN:
            return
        if e.key == pygame.K_ESCAPE:
            self.goto("pause")
        elif e.key == pygame.K_TAB:
            have = [n for n in DISTRACT if self.items[n] > 0]
            if have:
                cur = DISTRACT[self.sel_item]
                i = have.index(cur) if cur in have else -1
                self.sel_item = DISTRACT.index(have[(i + 1) % len(have)])
                self.sfx.play("click")
        elif e.key == pygame.K_q:
            self.use_item()
        elif e.key == pygame.K_e and self.nearest:
            self.interact(self.nearest)

    # -------------------------------------------------------------- acciones
    def use_item(self):
        name = DISTRACT[self.sel_item]
        if self.items[name] <= 0:
            have = [n for n in DISTRACT if self.items[n] > 0]
            if not have:
                self.toast("No tienes objetos para distraer.", 2.5, (255, 180, 150))
                return
            name = have[0]
            self.sel_item = DISTRACT.index(name)
        info = DIST_INFO[name]
        c, e, p = self.chaser, self.ent, self.p
        cands = []
        if c.floor == self.floor:
            cands.append((math.hypot(c.x - p.x, c.y - p.y), c, "chaser"))
        if self.ent_awake and e.floor == self.floor and e.state in ("hunt", "chase", "stun", "eat"):
            cands.append((math.hypot(e.x - p.x, e.y - p.y), e, "entity"))
        cands = [x for x in cands if x[0] <= info[1]]
        if not cands:
            self.toast("No hay nadie al alcance. Guarda el objeto.", 2.5, (255, 200, 150))
            return
        cands.sort(key=lambda x: x[0])
        _, tgt, who = cands[0]
        self.items[name] -= 1
        tgt.path = []
        tgt.state = "eat" if name == "Sándwich" else "stun"
        tgt.timer = info[2]
        if who == "chaser":
            c.lost = 0
            self.toast(info[0], 3.0, (150, 255, 190))
        else:
            e.cool = 3.5
            self.toast(info[0] + " Ella perderá tu rastro.", 3.5, (150, 255, 190))
        self.sfx.play("item")

    def interact(self, n):
        k = n["kind"]
        if k == "terminal":
            room = n["room"]
            if room["solved"]:
                self.toast("Este terminal ya está desbloqueado.", 2.5)
                return
            self.puz = room["ptype"](self)
            self.puz_room = room
            self.state = "puzzle"
            self.sfx.play("click")
        elif k == "tele":
            self.state = "tele_select"
            self.sfx.play("click")
        elif k == "locker":
            e = self.ent
            if self.ent_awake and e.floor == self.floor and e.state == "chase":
                self.toast("¡Ella ya te vio! Esconderte no sirve. Lánzale un objeto para que pierda tu rastro.", 3.5, (255, 140, 140))
                return
            self.start_hide(n["lk"])
        elif k == "npc":
            npc = n["npc"]
            lines = [random.choice(NPC_TIPS)]
            opts = []
            hint = [r for r in self.rooms if r["reward"][0] == "pair" and not r["solved"]]
            if hint:
                r = random.choice(hint)
                opts.append(f"Escuché ruidos en el aula {r['label']}… creo que hay algo importante ahí.")
            else:
                opts.append("Ya encontraste todo lo que escondían las aulas. Elige tu salida con sabiduría.")
            opts.append("Si el ayudante te pierde de vista, se teletransporta a otro piso. Los casilleros te ayudan a esconderte, pero controla tu pulso.")
            if self.ent_awake:
                opts.append("¡Ella está cazando! Si te ve, solo un objeto le hará perder tu rastro.")
            elif not self.ent_done:
                m, s2 = divmod(int(max(0, self.countdown)), 60)
                opts.append(f"Dicen que ella despierta en {m}:{s2:02d}… no te confíes.")
            opts.append("Hay un gimnasio y un coliseo en los pisos de arriba. Allí también hay terminales.")
            lines.append(random.choice(opts))
            if npc["talked"] == 0 and npc["gift"]:
                g = random.choice(DISTRACT)
                self.items[g] += 1
                lines.append(f"Toma, te regalo esto: {g}. Te servirá para distraer al ayudante.")
                self.sfx.play("item")
            self.dialog = dict(name=npc["name"], kind=npc["kind"], col=npc["col"], lines=lines, i=0, t=0.0)
            npc["talked"] += 1
            self.state = "dialog"
        elif k == "entity":
            if self.sancocho:
                lines = ["…", "Tú. Después de todo lo que pasó… ¿cocinaste para mí?", "Mmm… es sancocho. Mi favorito."]
                self.dialog = dict(name="Ella", kind="entity", col=(255, 120, 130), lines=lines, i=0, t=0.0, after=lambda: self.finish("redemption"))
                self.state = "dialog"
            else:
                self.toast("Ella te observa sin parpadear. Necesitas un sancocho. No te acerques así.", 3.5, (255, 140, 140))
        elif k == "stove":
            self.toast("Mantén E para cocinar cuando tengas los 6 ingredientes.", 3)

    def finish(self, which):
        self.ending = which
        self.state = "end"
        self.sel = 0
        self.sfx.play("ok")

    def caught(self, reason):
        self.caught_reason = reason
        self.state = "over"
        self.hide = None
        self.sel = 0
        self.shake = 0.5
        self.sfx.play("scare")

    def room_solved(self, room):
        room["solved"] = True
        self.solved += 1
        r = room["reward"]
        if r[0] == "pair":
            self.frags.add(r[1])
            self.ings.add(r[2])
            self.toast(f"¡Fragmento de llave #{r[1]} y un ingrediente: {r[2]}!", 5.5, (255, 226, 130))
        else:
            self.items[r[1]] += 1
            self.toast(f"Encontraste: {r[1]}. Úsalo (Q) para distraer al ayudante.", 5, (170, 255, 200))
        self.sfx.play("item")
        self.toast(self.puz.lesson, 6.5, (190, 210, 255))

    def tele_rects(self):
        return [pygame.Rect(W // 2 - 420 + i * 120, H // 2 - 20, 108, 110) for i in range(FLOORS)]

    def start_tele(self, to):
        if to == self.floor:
            self.toast("Ya estás en ese piso.", 2)
            return
        self.tele_target = to
        self.tele_t = 0.0
        self.state = "tele_fx"
        self.sfx.play("tele")

    # -------------------------------------------------------------- casilleros / pulso
    def start_hide(self, lk):
        p, c = self.p, self.chaser
        pos = (lk.centerx, CORR.y + 24)
        p.x, p.y = pos[0], pos[1] + 2
        pulse = 15.0
        if c.floor == self.floor and c.state == "chase":
            c.state = "search"
            c.timer = 11.0
            c.path = []
            pulse = 40.0
        self.hide = dict(lk=lk, pos=pos, pulse=pulse, air=100.0, gasp=False, phase=0.0, threat=0.0, t=0.0)
        self.state = "hide"
        self.sfx.play("click")
        self.toast("Estás escondida. Mantén ESPACIO para respirar hondo y bajar el pulso. E: salir.", 5, (190, 210, 255))

    def stop_hide(self):
        self.state = "play"
        self.hide = None
        self.p.moving = False
        self.sfx.play("click")

    def update_hide(self, dt):
        h = self.hide
        if not h:
            return
        keys = pygame.key.get_pressed()
        c, e = self.chaser, self.ent
        lk = h["pos"]
        threat = 0.0
        if c.floor == self.floor and c.state in ("search", "chase"):
            d = math.hypot(c.x - lk[0], c.y - lk[1])
            threat = max(threat, clamp(1 - (d - 60) / 520, 0, 1))
            if c.state == "search" and d < 90:
                threat = max(threat, 0.7)
        if self.ent_awake and e.floor == self.floor and e.state in ("hunt", "chase"):
            d = math.hypot(e.x - lk[0], e.y - lk[1])
            threat = max(threat, clamp(1 - (d - 60) / 500, 0, 1) * 0.9)
            if d < 80:
                threat = 1.0
        h["threat"] = threat
        rate = 4 + 34 * threat
        breathe = keys[pygame.K_SPACE] and h["air"] > 0 and not h["gasp"]
        if breathe:
            h["pulse"] -= 36 * dt
            h["air"] -= 26 * dt
            if h["air"] <= 0:
                h["air"] = 0
                h["gasp"] = True
        else:
            h["air"] = min(100, h["air"] + 14 * dt)
            if h["gasp"] and h["air"] > 30:
                h["gasp"] = False
        h["pulse"] += rate * dt
        if h["gasp"]:
            h["pulse"] += 10 * dt
        h["pulse"] = clamp(h["pulse"], 0, 100)
        bps = (60 + h["pulse"] * 1.2) / 60
        old = int(h["phase"])
        h["phase"] += bps * dt
        if int(h["phase"]) > old:
            self.sfx.play("beat")
        h["t"] += dt
        if h["pulse"] >= 100 and threat > 0.05:
            self.caught("pulse")

    # -------------------------------------------------------------- actualizacion
    def update(self, dt):
        self.t += dt
        for p in self.particles:
            p[1] -= p[3] * dt
            p[0] += math.sin(self.t + p[4]) * 8 * dt
            if p[1] < -30:
                p[1] = H + 20
                p[0] = random.uniform(0, W)
        for t in self.toasts:
            t["age"] += dt
        self.toasts = [t for t in self.toasts if t["age"] < t["s"]]
        for f in self.fx:
            f["age"] += dt
        self.fx = [f for f in self.fx if f["age"] < 0.9]
        if self.shake > 0:
            self.shake -= dt
        st = self.state
        if st == "intro":
            self.slide_t += dt
        elif st == "dialog":
            self.dialog["t"] += dt
            self.world_update(dt * 0.0)
        elif st == "tele_fx":
            self.tele_t += dt
            if self.tele_t > 0.45 and self.floor != self.tele_target:
                self.floor = self.tele_target
                self.p.x, self.p.y = PAD[0], PAD[1] + 56
                c = self.chaser
                if c.floor != self.floor and not self.ent_awake:
                    c.follow = self.follow_delay()
                    self.toast("Escuchas pasos lejanos… alguien viene por el teletransportador.", 4, (255, 170, 150))
                if self.ent_awake and self.ent.floor != self.floor:
                    self.ent.follow = 4.0
                if FLOOR_NAMES[self.floor]:
                    self.toast(f"Has llegado al {FLOOR_NAMES[self.floor]}.", 3, FLOOR_COLORS[self.floor])
            if self.tele_t > 0.9:
                self.state = "play"
        elif st == "puzzle":
            self.puz.update(dt)
            self.world_update(dt, 0.45, True)
            if self.puz.done:
                self.puz.fin_t -= dt
                if self.puz.fin_t <= 0:
                    self.room_solved(self.puz_room)
                    self.state = "play"
        elif st == "hide":
            self.update_hide(dt)
            if self.state == "hide":
                self.world_update(dt, 1.0, True)
        elif st == "play":
            self.world_update(dt)

    def world_update(self, dt, chaser_speed_mul=1.0, frozen_player=False):
        if self.state in ("play", "puzzle", "hide"):
            self.play_time += dt
        p = self.p
        keys = pygame.key.get_pressed()
        if not frozen_player and self.state == "play":
            dx = (keys[pygame.K_d] or keys[pygame.K_RIGHT]) - (keys[pygame.K_a] or keys[pygame.K_LEFT])
            dy = (keys[pygame.K_s] or keys[pygame.K_DOWN]) - (keys[pygame.K_w] or keys[pygame.K_UP])
            sprint = (keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]) and not p.tired
            p.moving = bool(dx or dy)
            if dx and dy:
                dx *= 0.7071
                dy *= 0.7071
            speed = 270 if (sprint and p.moving) else 190
            if sprint and p.moving:
                p.stamina -= 32 * dt
                if p.stamina <= 0:
                    p.stamina, p.tired = 0, True
            else:
                p.stamina = min(100, p.stamina + 20 * dt)
                if p.tired and p.stamina > 30:
                    p.tired = False
            nx = p.x + dx * speed * dt
            if self.can_stand(self.floor, nx, p.y):
                p.x = nx
            ny = p.y + dy * speed * dt
            if self.can_stand(self.floor, p.x, ny):
                p.y = ny
            if dx:
                p.face = "r" if dx > 0 else "l"
            if p.moving:
                p.anim += dt * (11 if speed > 200 else 8)
        else:
            p.moving = False
        # interaccion cercana
        self.nearest = None
        if self.state == "play":
            self.find_nearest()
            self.update_hold(dt, keys)
        self.update_chaser(dt * chaser_speed_mul)
        self.update_entity(dt, chaser_speed_mul)

    def find_nearest(self):
        p, fi = self.p, self.floor
        cands = []
        for r in self.rooms:
            if r["floor"] == fi:
                td = self.layouts[fi]["terms"][r["i"]]
                if td.inflate(90, 90).collidepoint(p.x, p.y):
                    cands.append((math.hypot(td.centerx - p.x, td.centery - p.y), dict(kind="terminal", room=r, pos=td.center,
                                                                                            label="E: Usar terminal" if not r["solved"] else "Terminal desbloqueado")))
        if math.hypot(p.x - PAD[0], p.y - PAD[1]) < 85:
            cands.append((10, dict(kind="tele", pos=PAD, label="E: Usar teletransportador")))
        for npc in self.npcs[fi]:
            if math.hypot(p.x - npc["x"], p.y - npc["y"]) < 80:
                cands.append((20, dict(kind="npc", npc=npc, pos=(npc["x"], npc["y"] - 70), label=f"E: Hablar con {npc['name']}")))
        if p.y < 440:
            for lk in LOCKERS:
                if abs(p.x - lk.centerx) < 34:
                    cands.append((8, dict(kind="locker", lk=lk, pos=(lk.centerx, lk.y - 4), label="E: Esconderte en el casillero")))
        e = self.ent
        if e.floor == fi and math.hypot(p.x - e.x, p.y - e.y) < 170:
            if self.sancocho:
                cands.append((5, dict(kind="entity", pos=(e.x, e.y - 100), label="E: Ofrecer el sancocho")))
            elif e.state == "rest":
                cands.append((5, dict(kind="entity", pos=(e.x, e.y - 100), label="E: Observar a la entidad")))
        if fi == 0:
            if STOVE_RECT.inflate(80, 80).collidepoint(p.x, p.y):
                lab = f"Mantén E: Cocinar sancocho ({len(self.ings)}/6)" if not self.sancocho else "Ya tienes el sancocho"
                cands.append((15, dict(kind="stove", pos=(STOVE_RECT.centerx, STOVE_RECT.y - 6), label=lab)))
            if math.hypot(p.x - FIRE_POS[0], p.y - FIRE_POS[1]) < 90:
                cands.append((12, dict(kind="fire", pos=(FIRE_POS[0], FIRE_POS[1] - 70), label=f"Mantén E: Abrir con la llave ({len(self.frags)}/6)")))
        if cands:
            cands.sort(key=lambda c: c[0])
            self.nearest = cands[0][1]

    def update_hold(self, dt, keys):
        n = self.nearest
        if n and n["kind"] in ("stove", "fire") and keys[pygame.K_e]:
            if n["kind"] == "stove":
                if self.sancocho:
                    return
                if len(self.ings) < 6:
                    if self.hold == 0:
                        self.toast(f"Te faltan ingredientes ({len(self.ings)}/6).", 3, (255, 190, 150))
                    self.hold = 0.001
                    return
                self.hold += dt / 2.5
                if self.hold >= 1:
                    self.hold = 0
                    self.sancocho = True
                    self.toast("¡Sancocho listo! Llévaselo a ella, a la salida principal.", 6, (170, 255, 200))
                    self.sfx.play("ok")
            else:
                if len(self.frags) < 6:
                    if self.hold == 0:
                        self.toast(f"La llave está incompleta ({len(self.frags)}/6 fragmentos).", 3, (255, 190, 150))
                    self.hold = 0.001
                    return
                self.hold += dt / 1.8
                if self.hold >= 1:
                    self.hold = 0
                    self.finish("escape")
        else:
            self.hold = 0

    # -------------------------------------------------------------- la entidad
    def wake_entity(self):
        e = self.ent
        self.ent_awake = True
        self.hunt_left = HUNT_TIME
        e.state = "hunt"
        e.path = []
        e.cool = 1.0
        e.follow = None
        e.replan = 0.0
        self.shake = 0.6
        c = self.chaser
        c.floor = -1
        c.state = "patrol"
        c.path = []
        c.follow = None
        c.last_seen = None
        self.sfx.play("scare")
        self.toast("¡SE ACABÓ EL TIEMPO! La entidad abandonó su lugar y te cazará durante 1 minuto. El ayudante se retira: solo ella te persigue.", 7, (255, 120, 130))
        self.toast("Si te ve, solo un objeto (Q) hará que pierda tu rastro. ¡Los casilleros no sirven!", 7, (255, 190, 150))

    def sleep_entity(self):
        e = self.ent
        self.ent_awake = False
        self.ent_done = True
        e.state = "return"
        e.path = []
        e.follow = None
        if e.floor != 0:
            e.floor = 0
            e.x, e.y = PAD
        if self.floor != 0:
            e.x, e.y = ENTITY_POS
            e.state = "rest"
        c = self.chaser
        c.floor = random.choice([f for f in range(FLOORS) if f != self.floor])
        cell = random.choice(list(self.grids[c.floor]))
        c.x, c.y = cell[0] * CELL + CELL / 2, cell[1] * CELL + CELL / 2
        c.state = "patrol"
        c.path = []
        c.follow = None
        self.hunt_t = 25.0
        self.toast("La entidad se cansó de cazar y regresa a su puesto…", 5, (190, 210, 255))

    def hunt_goal(self):
        g = list(self.grids[self.floor])
        p = self.p
        near = [c for c in g if abs(c[0] * CELL - p.x) < 420 and abs(c[1] * CELL - p.y) < 300]
        return random.choice(near or g)

    def update_entity(self, dt, mul=1.0):
        e, p = self.ent, self.p
        st = self.state
        self.entity_near = 0
        if st not in ("play", "puzzle", "hide", "dialog"):
            return
        if not self.ent_awake and not self.ent_done:
            self.countdown -= dt
            if self.countdown <= 0:
                self.countdown = 0
                self.wake_entity()
        elif self.ent_awake:
            self.hunt_left -= dt
            if self.hunt_left <= 0:
                self.sleep_entity()
        mdt = dt * mul
        same = e.floor == self.floor
        if self.ent_awake and not same:
            if e.follow is None:
                e.follow = 5.0
            e.follow -= dt
            if e.follow <= 0:
                e.follow = None
                e.floor = self.floor
                e.x, e.y = PAD
                e.state = "hunt"
                e.path = []
                e.cool = 2.0
                self.sfx.play("alert")
                self.toast("¡La entidad apareció en el teletransportador!", 3.5, (255, 130, 130))
                same = True
            else:
                return
        if not same:
            return
        e.moving = False
        e.cool = max(0.0, e.cool - dt)
        e.replan -= dt
        d = math.hypot(e.x - p.x, e.y - p.y)
        if e.state == "rest":
            if self.floor == 0 and not self.sancocho:
                self.entity_near = clamp(1 - (d - 120) / 240, 0, 1)
                if d < 115 and st == "play":
                    self.caught("entity")
            return
        seen = d < 430 and st in ("play", "puzzle") and self.los(e.x, e.y, p.x, p.y)
        if e.state in ("stun", "eat"):
            e.timer -= dt
            if e.timer <= 0:
                e.state = "hunt"
                e.path = []
                e.cool = 3.0
            return
        sp = [170, 195, 220][self.diff]
        if e.state == "return":
            tgt = ENTITY_POS
            if math.hypot(e.x - tgt[0], e.y - tgt[1]) < 70:
                e.x, e.y = ENTITY_POS
                e.state = "rest"
                e.path = []
                self.toast("La entidad volvió a su lugar. Ya no te cazará.", 4, (190, 210, 255))
            else:
                if e.replan <= 0 or not e.path:
                    e.replan = 1.0
                    e.path = self.find_path(0, self.nearest_cell(0, e.x, e.y), self.nearest_cell(0, tgt[0], tgt[1]))
                self.step(e, 140, mdt)
        elif e.state == "hunt":
            if seen and e.cool <= 0:
                e.state = "chase"
                e.path = []
                self.sfx.play("alert")
                self.toast("¡La entidad te vio! Solo un objeto puede hacerla perder tu rastro.", 4, (255, 130, 130))
            else:
                if e.replan <= 0 or not e.path:
                    e.replan = 3.0
                    e.path = self.find_path(self.floor, self.nearest_cell(self.floor, e.x, e.y),
                                            self.nearest_cell(self.floor, *[v * CELL + CELL / 2 for v in self.hunt_goal()]))
                self.step(e, sp * 0.7, mdt)
                if d < 40 and st == "play" and not self.sancocho:
                    self.caught("entity")
            self.entity_near = clamp(1 - (d - 150) / 300, 0, 1) * 0.7
        elif e.state == "chase":
            if d < 90 and seen:
                dx, dy = p.x - e.x, p.y - e.y
                m = math.hypot(dx, dy) or 1
                sp2 = sp * mdt
                nx, ny = e.x + dx / m * sp2, e.y + dy / m * sp2
                if self.can_stand(self.floor, nx, e.y):
                    e.x = nx
                if self.can_stand(self.floor, e.x, ny):
                    e.y = ny
                e.face = "r" if dx > 0 else "l"
                e.moving = True
            else:
                if e.replan <= 0 or not e.path:
                    e.replan = 0.3
                    e.path = self.find_path(self.floor, self.nearest_cell(self.floor, e.x, e.y), self.nearest_cell(self.floor, p.x, p.y))
                self.step(e, sp, mdt)
            if d < 42 and st in ("play", "puzzle") and not self.sancocho:
                self.caught("entity")
            self.entity_near = clamp(1 - (d - 150) / 300, 0, 1) * 0.85
        if e.moving:
            e.anim += dt * 9

    # -------------------------------------------------------------- el ayudante
    def chaser_vanish(self):
        c = self.chaser
        self.fx.append(dict(x=c.x, y=c.y, floor=c.floor, age=0.0))
        opts = [f for f in range(FLOORS) if f != c.floor]
        c.floor = random.choice(opts)
        cell = random.choice(list(self.grids[c.floor]))
        c.x, c.y = cell[0] * CELL + CELL / 2, cell[1] * CELL + CELL / 2
        c.state = "patrol"
        c.path = []
        c.follow = None
        c.lost = 0
        c.last_seen = None
        self.hunt_t = random.uniform(28, 42)
        self.sfx.play("tele")

    def chaser_search(self, dt):
        c = self.chaser
        h = self.hide
        tgt = h["pos"]
        c.timer -= dt
        dd = math.hypot(c.x - tgt[0], c.y - tgt[1])
        if dd > 60:
            if c.replan <= 0 or not c.path:
                c.replan = 0.5
                c.path = self.find_path(self.floor, self.nearest_cell(self.floor, c.x, c.y), self.nearest_cell(self.floor, tgt[0], tgt[1]))
            self.step(c, self.chase_speed() * 0.85, dt)
        else:
            c.face = "r" if h["lk"].centerx > c.x else "l"
        if c.timer <= 0:
            self.chaser_vanish()
            self.toast("El ayudante se rindió y se desvaneció. Puedes salir con E.", 4, (170, 255, 200))

    def update_chaser(self, dt):
        c, p = self.chaser, self.p
        if self.ent_awake:
            c.follow = None
            return
        hidden = self.state == "hide"
        # seguir al jugador por el teletransportador
        if c.follow is not None:
            c.follow -= dt
            if c.follow <= 0 and c.floor != self.floor:
                c.follow = None
                c.floor = self.floor
                c.x, c.y = PAD[0], PAD[1]
                if hidden:
                    c.state = "search"
                    c.timer = 11.0
                else:
                    c.state = "chase"
                c.last_seen = (p.x, p.y)
                c.lost = 0
                c.path = []
                self.sfx.play("alert")
                self.toast("¡El ayudante apareció en el teletransportador!", 3.5, (255, 130, 130))
            elif c.floor == self.floor:
                c.follow = None
        if c.floor != self.floor:
            if c.follow is None:
                self.hunt_t -= dt
                if self.hunt_t <= 0:
                    self.hunt_t = 40.0
                    c.follow = self.follow_delay()
            return
        c.moving = False
        c.replan -= dt
        d = math.hypot(c.x - p.x, c.y - p.y)
        seen = d < 380 and not hidden and self.state != "dialog" and self.los(c.x, c.y, p.x, p.y)
        if c.state in ("stun", "eat"):
            c.timer -= dt
            if c.timer <= 0:
                c.state = "patrol"
                c.path = []
            return
        if c.state == "search":
            if not hidden:
                c.state = "chase"
                c.last_seen = (p.x, p.y)
                c.lost = 0
                c.path = []
            else:
                self.chaser_search(dt)
                if c.moving:
                    c.anim += dt * 9
                return
        if c.state == "patrol":
            if seen:
                c.state = "chase"
                c.lost = 0
                self.sfx.play("alert")
            elif self.p.moving and d < 240 and self.state == "play" and keys_sprint():
                c.state = "chase"
                c.last_seen = (p.x, p.y)
        if c.state == "chase":
            if seen:
                c.last_seen = (p.x, p.y)
                c.lost = 0
            else:
                c.lost += dt
                if c.lost > 4.0 or c.last_seen is None:
                    self.chaser_vanish()
                    self.toast("El ayudante perdió tu rastro y se teletransportó a otro piso.", 4, (170, 255, 200))
                    return
            tgt = c.last_seen or (p.x, p.y)
            if seen and d < 90:
                dx, dy = p.x - c.x, p.y - c.y
                m = math.hypot(dx, dy) or 1
                sp = self.chase_speed() * dt
                nx, ny = c.x + dx / m * sp, c.y + dy / m * sp
                if self.can_stand(self.floor, nx, c.y):
                    c.x = nx
                if self.can_stand(self.floor, c.x, ny):
                    c.y = ny
                c.face = "r" if dx > 0 else "l"
                c.moving = True
            else:
                if c.replan <= 0 or not c.path:
                    c.replan = 0.35
                    c.path = self.find_path(self.floor, self.nearest_cell(self.floor, c.x, c.y), self.nearest_cell(self.floor, tgt[0], tgt[1]))
                self.step(c, self.chase_speed(), dt)
            if d < 34 and self.state in ("play", "puzzle"):
                self.caught("chaser")
        elif c.state == "patrol":
            if not c.path:
                g = list(self.grids[self.floor])
                goal = random.choice(g)
                c.path = self.find_path(self.floor, self.nearest_cell(self.floor, c.x, c.y), goal)
            self.step(c, 105, dt)
        if c.moving:
            c.anim += dt * 9

    def step(self, c, speed, dt):
        if not c.path:
            return
        tx, ty = c.path[0]
        tx = tx * CELL + CELL / 2
        ty = ty * CELL + CELL / 2
        dx, dy = tx - c.x, ty - c.y
        d = math.hypot(dx, dy)
        mv = speed * dt
        if d <= mv:
            c.x, c.y = tx, ty
            c.path.pop(0)
        else:
            c.x += dx / d * mv
            c.y += dy / d * mv
        if abs(dx) > 0.5:
            c.face = "r" if dx > 0 else "l"
        c.moving = True

    # -------------------------------------------------------------- dibujo
    def draw(self):
        s = self.screen
        st = self.state
        if st in ("menu", "options", "controls", "credits"):
            self.draw_menu_screen(s)
        elif st == "intro":
            self.draw_intro(s)
        elif st in ("play", "puzzle", "tele_select", "tele_fx", "dialog", "pause", "over", "end", "hide"):
            self.draw_world(s)
            if st == "hide":
                self.draw_hide_view(s)
            self.draw_hud(s)
            if st == "hide":
                self.draw_hide_ui(s)
            elif st == "puzzle":
                self.puz.draw(s)
            elif st == "tele_select":
                self.draw_tele_select(s)
            elif st == "tele_fx":
                a = int(255 * (1 - abs(self.tele_t - 0.45) / 0.45)) if self.tele_t < 0.9 else 0
                fl = pygame.Surface((W, H))
                fl.fill((200, 235, 255))
                fl.set_alpha(clamp(a, 0, 255))
                s.blit(fl, (0, 0))
            elif st == "dialog":
                self.draw_dialog(s)
            elif st == "pause":
                self.draw_overlay_menu(s, "PAUSA", (200, 210, 255))
            elif st == "over":
                self.draw_over(s)
            elif st == "end":
                self.draw_end(s)
        self.draw_toasts(s)

    def draw_world(self, s):
        fi = self.floor
        p = self.p
        e = self.ent
        sh = 0
        if self.shake > 0:
            sh = random.randint(-6, 6)
        if self.entity_near > 0.4:
            sh += random.randint(-2, 2) * self.entity_near
        cx = int(clamp(p.x - W / 2 + sh, 0, WORLD_W - W))
        cy = int(clamp(p.y - H / 2 - 40 + sh, 0, WORLD_H - H))
        s.fill((10, 8, 20))
        s.blit(self.floors[fi], (0, 0), pygame.Rect(cx, cy, W, H))
        # almohadilla teletransportador
        px, py = PAD[0] - cx, PAD[1] - cy
        for k in range(3):
            r = 46 - k * 10 + math.sin(self.t * 3 + k) * 2
            pygame.draw.circle(s, lerpc((60, 120, 200), (170, 230, 255), k / 2), (px, py), int(r), 3)
        pygame.draw.circle(s, (20, 40, 80), (px, py), 26)
        for k in range(6):
            a = self.t * 2 + k * math.pi / 3
            pygame.draw.circle(s, (160, 230, 255), (int(px + math.cos(a) * 34), int(py + math.sin(a) * 34 * 0.8)), 3)
        s.blit(self.pad_glow, (px - 150, py - 150), special_flags=pygame.BLEND_RGB_ADD)
        # terminales
        for r in self.rooms:
            if r["floor"] == fi:
                td = self.layouts[fi]["terms"][r["i"]]
                gx, gy = td.centerx - cx, td.centery - cy
                col = (90, 240, 150) if r["solved"] else (90, 180, 255)
                pygame.draw.circle(s, col, (gx, gy + (18 if td.y < CORR.y else -18)), 4)
                if not r["solved"]:
                    s.blit(self.term_glow, (gx - 70, gy - 70), special_flags=pygame.BLEND_RGB_ADD)
        # casillero ocupado
        if self.state == "hide" and self.hide:
            lk = self.hide["lk"]
            lx, ly = lk.centerx - cx, lk.y + 9 - cy
            pygame.draw.rect(s, (255, 220, 120), (lk.x - cx - 1, lk.y - cy - 1, lk.w + 2, lk.h + 2), 2, border_radius=3)
            for ddx in (-5, 5):
                pygame.draw.circle(s, (255, 255, 255), (lx + ddx, ly), 3)
                pygame.draw.circle(s, (20, 20, 30), (lx + ddx, ly + 1), 1)
        # humo de teletransporte del ayudante
        for f in self.fx:
            if f["floor"] == fi:
                k = f["age"] / 0.9
                r = int(20 + 60 * k)
                a = int(200 * (1 - k))
                t = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
                pygame.draw.circle(t, (150, 40, 200, a), (r, r), r)
                pygame.draw.circle(t, (255, 60, 90, a), (r, r), r, 3)
                s.blit(t, (int(f["x"] - cx - r), int(f["y"] - cy - r - 40)))
        # sprites ordenados por y
        draw = []
        if self.state != "hide":
            draw.append((p.y, "p", 0))
        for i, npc in enumerate(self.npcs[fi]):
            draw.append((npc["y"], "n", i))
        if self.chaser.floor == fi:
            draw.append((self.chaser.y, "c", 0))
        if e.floor == fi:
            draw.append((e.y, "e", 0))
        draw.sort()
        for _, k, i in draw:
            if k == "p":
                self.blit_actor(s, "hero", p, cx, cy)
            elif k == "n":
                npc = self.npcs[fi][i]
                a = Actor(npc["x"], npc["y"])
                a.anim = self.t * 1.2
                a.face = "l" if npc["x"] > p.x else "r"
                self.blit_actor(s, npc["kind"], a, cx, cy, idle=True)
            elif k == "c":
                c = self.chaser
                g = scaled_glow(self.red_glow, 0.28 + 0.1 * math.sin(self.t * 4))
                s.blit(g, (int(c.x - cx - 190), int(c.y - cy - 250)), special_flags=pygame.BLEND_RGB_ADD)
                self.blit_actor(s, "chaser", c, cx, cy)
                hx, hy = int(c.x - cx), int(c.y - cy - 112)
                if c.state == "chase":
                    text(s, "!", 34, (255, 60, 60), (hx, hy), "center", True)
                elif c.state == "search":
                    text(s, "?", 34, (255, 170, 70), (hx, hy), "center", True)
                elif c.state == "stun":
                    for q in range(3):
                        a = self.t * 5 + q * 2.1
                        pygame.draw.circle(s, (255, 230, 90), (int(hx + math.cos(a) * 18), int(hy + 10 + math.sin(a) * 6)), 5)
                elif c.state == "eat":
                    text(s, "ñam ñam", 15, (255, 220, 150), (hx, hy + 6), "center", True)
            elif k == "e":
                self.draw_entity(s, cx, cy)
        # etiqueta de interaccion
        if self.nearest and self.state == "play":
            n = self.nearest
            pos = (int(n["pos"][0] - cx), int(n["pos"][1] - cy) - 34)
            t = F(18, True).render(n["label"], True, (255, 255, 255))
            box = t.get_rect(center=pos).inflate(26, 14)
            rrect(s, (10, 12, 30), box, 14, 2, (130, 180, 255), alpha=215)
            s.blit(t, t.get_rect(center=pos))
            if self.hold > 0:
                bar = pygame.Rect(box.x, box.bottom + 4, box.w, 8)
                rrect(s, (30, 34, 56), bar, 4)
                rrect(s, (120, 230, 160), (bar.x, bar.y, int(bar.w * min(1, self.hold)), 8), 4)
        # oscuridad
        self.dark.fill((6, 5, 18, 208))
        big = self.light_big if int(self.t * 9) % 53 else self.light_small
        self.dark.blit(big, (int(p.x - cx) - big.get_width() // 2, int(p.y - cy - 40) - big.get_height() // 2), special_flags=pygame.BLEND_RGBA_SUB)
        self.dark.blit(self.light_pad, (px - 170, py - 170), special_flags=pygame.BLEND_RGBA_SUB)
        for r in self.rooms:
            if r["floor"] == fi:
                td = self.layouts[fi]["terms"][r["i"]]
                self.dark.blit(self.light_mid, (td.centerx - cx - 120, td.centery - cy - 120), special_flags=pygame.BLEND_RGBA_SUB)
        if e.floor == fi:
            self.dark.blit(self.light_mid, (int(e.x - cx - 120), int(e.y - cy - 120)), special_flags=pygame.BLEND_RGBA_SUB)
        if fi == 0:
            self.dark.blit(self.light_mid, (FIRE_POS[0] - cx - 120, FIRE_POS[1] - cy - 120), special_flags=pygame.BLEND_RGBA_SUB)
        s.blit(self.dark, (0, 0))
        # persecucion / peligro
        if self.chaser.floor == fi and self.chaser.state == "chase":
            self.vignette.set_alpha(int(150 + 90 * math.sin(self.t * 8)))
            s.blit(self.vignette, (0, 0))
        if self.entity_near > 0:
            self.vignette.set_alpha(int(255 * self.entity_near))
            s.blit(self.vignette, (0, 0))
        elif self.ent_awake:
            self.vignette.set_alpha(int(50 + 30 * math.sin(self.t * 3)))
            s.blit(self.vignette, (0, 0))

    def blit_actor(self, s, kind, a, cx, cy, idle=False):
        ph = int(a.anim) % 4 if (a.moving or idle) else 0
        spr = self.sprites[kind][ph]
        if a.face == "l":
            spr = pygame.transform.flip(spr, True, False)
        s.blit(spr, (int(a.x - cx - spr.get_width() / 2), int(a.y - cy - spr.get_height() + 6)))

    def draw_entity(self, s, cx, cy):
        e = self.ent
        x, y = int(e.x - cx), int(e.y - cy)
        awake = e.state in ("hunt", "chase", "stun", "eat")
        g = scaled_glow(self.red_glow, (0.85 if awake else 0.75) + 0.25 * math.sin(self.t * 2))
        s.blit(g, (x - 190, y - 240), special_flags=pygame.BLEND_RGB_ADD)
        spr = self.sprites["entity"][int(self.t * 3) % 4]
        if e.face == "l":
            spr = pygame.transform.flip(spr, True, False)
        off = math.sin(self.t * 1.7) * 3
        s.blit(spr, (x - spr.get_width() // 2, int(y - spr.get_height() + 8 + off)))
        hy = y - 126
        if e.state == "chase":
            text(s, "!", 40, (255, 60, 60), (x, hy), "center", True)
        elif e.state == "stun":
            for q in range(3):
                a = self.t * 5 + q * 2.1
                pygame.draw.circle(s, (255, 230, 90), (int(x + math.cos(a) * 20), int(hy + 12 + math.sin(a) * 6)), 5)
        elif e.state == "eat":
            text(s, "ñam ñam", 15, (255, 220, 150), (x, hy + 6), "center", True)
        elif e.state == "hunt" and e.cool <= 0:
            text(s, "?", 34, (255, 170, 70), (x, hy), "center", True)
        if self.sancocho and e.state == "rest":
            ic = self.big_icons["Sancocho"]
            s.blit(ic, (x - 32, y - 150))

    def draw_hud(self, s):
        if self.state in ("over", "end"):
            return
        fi = self.floor
        col = FLOOR_COLORS[fi]
        rrect(s, (8, 10, 26), (14, 14, 300, 126), 16, 2, col, alpha=200)
        title = f"PISO {fi + 1}" + (f" · {FLOOR_NAMES[fi]}" if FLOOR_NAMES[fi] else "")
        text(s, title, 26 if not FLOOR_NAMES[fi] else 19, col, (30, 20), "topleft", True)
        text(s, f"Aulas: {self.solved}/{FLOORS * 4}", 15, (200, 206, 235), (300, 24), "topright", False, False)
        for i in range(1, 7):
            ic = self.icons[f"Llave{i}"].copy()
            if i not in self.frags:
                ic.fill((60, 60, 70, 255), special_flags=pygame.BLEND_RGBA_MULT)
                ic.set_alpha(110)
            s.blit(ic, (24 + (i - 1) * 46, 56))
        for i, n in enumerate(INGREDIENTS):
            ic = self.icons[n].copy()
            if n not in self.ings:
                ic.fill((50, 50, 60, 255), special_flags=pygame.BLEND_RGBA_MULT)
                ic.set_alpha(110)
            s.blit(ic, (24 + i * 46, 98 - 4))
        if self.sancocho:
            s.blit(self.icons["Sancocho"], (22, 146))
        # cuenta regresiva de la entidad
        if self.ent_awake or not self.ent_done:
            if self.ent_awake:
                m, sec = divmod(int(max(0, self.hunt_left)), 60)
                label = f"¡LA ENTIDAD CAZA!  {m}:{sec:02d}"
                ccol = lerpc((255, 80, 90), (255, 190, 190), 0.5 + 0.5 * math.sin(self.t * 6))
            else:
                m, sec = divmod(int(max(0, self.countdown)), 60)
                label = f"ELLA DESPIERTA EN  {m}:{sec:02d}"
                ccol = lerpc((235, 238, 255), (255, 80, 90), clamp(1 - self.countdown / 60, 0, 1))
            box = pygame.Rect(0, 12, 400, 40)
            box.midtop = (W // 2, 12)
            rrect(s, (8, 10, 26), box, 14, 2, ccol, alpha=210)
            text(s, label, 22, ccol, box.center, "center", True, False)
        # estamina
        sb = pygame.Rect(18, H - 34, 220, 14)
        rrect(s, (10, 12, 26), sb.inflate(6, 6), 10, alpha=190)
        fill = int(sb.w * self.p.stamina / 100)
        if fill > 0:
            rrect(s, (255, 120, 90) if self.p.tired else (110, 220, 150), (sb.x, sb.y, fill, sb.h), 7)
        text(s, "ENERGÍA (Shift)", 12, (200, 206, 235), (sb.x, sb.y - 16), "topleft", False, False)
        # objetos
        for i, n in enumerate(DISTRACT):
            r = pygame.Rect(W // 2 - 190 + i * 98, H - 84, 90, 70)
            sel = i == self.sel_item
            rrect(s, (10, 12, 30), r, 14, 3 if sel else 1, (255, 220, 120) if sel else (80, 90, 140), alpha=200)
            ic = self.icons[n]
            if self.items[n] <= 0:
                ic = ic.copy()
                ic.set_alpha(70)
            s.blit(ic, (r.centerx - 20, r.y + 6))
            text(s, f"x{self.items[n]}", 15, (255, 255, 255), (r.right - 8, r.bottom - 6), "bottomright", True, False)
            text(s, n, 11, (200, 206, 235), (r.centerx, r.bottom - 6), "midbottom", False, False)
        text(s, "TAB: elegir · Q: usar", 12, (170, 176, 210), (W // 2 + 4, H - 94), "midbottom", False, False)
        # minimapa
        sc = 0.085
        mw, mh = int(WORLD_W * sc), int(WORLD_H * sc)
        mm = pygame.Rect(W - mw - 24, 14, mw + 12, mh + 12)
        rrect(s, (8, 10, 26), mm, 12, 2, col, alpha=200)
        for r in WALK:
            pygame.draw.rect(s, (90, 100, 150), (mm.x + 6 + r.x * sc, mm.y + 6 + r.y * sc, max(2, r.w * sc), max(2, r.h * sc)))
        pygame.draw.circle(s, (120, 200, 255), (int(mm.x + 6 + PAD[0] * sc), int(mm.y + 6 + PAD[1] * sc)), 3, 1)
        pygame.draw.circle(s, (255, 255, 255), (int(mm.x + 6 + self.p.x * sc), int(mm.y + 6 + self.p.y * sc)), 4)
        c = self.chaser
        if c.floor == fi and math.hypot(c.x - self.p.x, c.y - self.p.y) < 650:
            pygame.draw.circle(s, (255, 70, 70), (int(mm.x + 6 + c.x * sc), int(mm.y + 6 + c.y * sc)), 4)
        e = self.ent
        if self.ent_awake and e.floor == fi and math.hypot(e.x - self.p.x, e.y - self.p.y) < 800:
            pygame.draw.circle(s, (200, 60, 255), (int(mm.x + 6 + e.x * sc), int(mm.y + 6 + e.y * sc)), 6, 2)
        text(s, "El ayudante se retiró" if c.floor < 0 else "El ayudante está en tu piso" if c.floor == fi else f"El ayudante está en el piso {c.floor + 1}", 13,
             (255, 150, 150) if c.floor == fi else (170, 176, 210), (mm.centerx, mm.bottom + 4), "midtop", False, False)

    # ---- escondite y pulso
    def draw_hide_view(self, s):
        m = pygame.Surface((W, H), pygame.SRCALPHA)
        m.fill((0, 0, 0, 238))
        for i in range(4):
            pygame.draw.rect(m, (0, 0, 0, 0), (W // 2 - 300, 200 + i * 34, 600, 14))
        s.blit(m, (0, 0))
        pygame.draw.rect(s, (70, 80, 110), (W // 2 - 330, 170, 660, 170), 6, border_radius=10)

    def draw_hide_ui(self, s):
        h = self.hide
        if not h:
            return
        pl = pygame.Rect(W // 2 - 320, 420, 640, 170)
        th = h["threat"]
        if h["gasp"]:
            msg, mc = "¡Te quedaste sin aire! Espera a recuperarlo…", (255, 120, 120)
        elif th > 0.6:
            msg, mc = "¡Está justo afuera del casillero!", (255, 110, 110)
        elif th > 0.2:
            msg, mc = "Escuchas pasos cerca…", (255, 190, 110)
        else:
            msg, mc = "Silencio… respira tranquila.", (170, 180, 215)
        text(s, msg, 22, mc, (W // 2, 372), "center", True)
        rrect(s, (8, 10, 26), pl, 16, 2, (255, 110, 130), alpha=225)
        pulse = h["pulse"]
        zc = (90, 230, 140) if pulse < 55 else ((255, 190, 90) if pulse < 80 else (255, 80, 90))
        text(s, "CONTROLA TU PULSO", 16, (230, 236, 255), (pl.x + 16, pl.y + 10), "topleft", True, False)
        ar = pygame.Rect(pl.x + 16, pl.y + 38, 380, 96)
        pygame.draw.rect(s, (14, 16, 30), ar, border_radius=8)
        pygame.draw.line(s, (40, 50, 80), (ar.x, ar.centery), (ar.right, ar.centery), 1)
        bps = (60 + pulse * 1.2) / 60
        n = 190
        pts = []
        for i in range(n):
            ph = (h["phase"] - (n - 1 - i) * 2 / 200 * bps) % 1.0
            pts.append((ar.x + 2 + i * 2, ar.centery + 6 - ecg_y(ph) * ar.h * 0.45))
        pygame.draw.lines(s, zc, False, pts, 3)
        bx = pl.x + 420
        text(s, f"PULSO  {int(60 + pulse * 1.2)} bpm", 15, zc, (bx, pl.y + 34), "topleft", True, False)
        b1 = pygame.Rect(bx, pl.y + 56, 204, 16)
        rrect(s, (30, 32, 50), b1, 8)
        pygame.draw.rect(s, (60, 120, 80), (b1.x, b1.y, int(b1.w * 0.55), b1.h), border_top_left_radius=8, border_bottom_left_radius=8)
        pygame.draw.rect(s, (130, 100, 50), (b1.x + int(b1.w * 0.55), b1.y, int(b1.w * 0.25), b1.h))
        pygame.draw.rect(s, (130, 50, 56), (b1.x + int(b1.w * 0.80), b1.y, b1.w - int(b1.w * 0.80), b1.h), border_top_right_radius=8, border_bottom_right_radius=8)
        mx = b1.x + int(b1.w * pulse / 100)
        pygame.draw.rect(s, zc, (mx - 3, b1.y - 4, 6, b1.h + 8), border_radius=3)
        text(s, "AIRE", 15, (150, 200, 255) if not h["gasp"] else (255, 120, 120), (bx, pl.y + 84), "topleft", True, False)
        b2 = pygame.Rect(bx, pl.y + 106, 204, 14)
        rrect(s, (30, 32, 50), b2, 7)
        if h["air"] > 1:
            rrect(s, (90, 170, 255) if not h["gasp"] else (255, 110, 110), (b2.x, b2.y, int(b2.w * h["air"] / 100), b2.h), 7)
        text(s, "Mantén ESPACIO: respirar hondo (gasta aire) · E: salir", 14, (170, 178, 212), (pl.centerx, pl.bottom - 14), "center", False, False)

    def draw_toasts(self, s):
        y = 160 if self.state in ("play", "puzzle", "dialog", "hide") else 20
        for t in self.toasts:
            a = int(255 * clamp(min(t["age"] * 4, (t["s"] - t["age"]) * 3), 0, 1))
            lines = wrap(t["t"], 18, 640, True)
            h = len(lines) * 24 + 16
            box = pygame.Rect(0, 0, 680, h)
            box.midtop = (W // 2, y)
            rrect(s, (10, 12, 30), box, 14, 2, t["c"], alpha=int(a * 0.85))
            yy = box.y + 8
            for ln in lines:
                text(s, ln, 18, t["c"], (box.centerx, yy), "midtop", True, False, a)
                yy += 24
            y += h + 8

    def draw_dialog(self, s):
        d = self.dialog
        box = pygame.Rect(120, H - 220, W - 240, 170)
        rrect(s, (8, 10, 28), box, 18, 3, d["col"], alpha=235)
        spr = self.sprites[d["kind"]][0]
        s.blit(pygame.transform.smoothscale(spr, (spr.get_width() * 2, spr.get_height() * 2)), (box.x + 10, box.y - 90))
        text(s, d["name"], 24, d["col"], (box.x + 190, box.y + 14), "topleft", True)
        n = int(d["t"] * 40)
        para_reveal(s, d["lines"][d["i"]], n, 21, (236, 240, 255), box.x + 190, box.y + 56, box.w - 220, 30)
        text(s, "ENTER / clic para continuar", 14, (150, 158, 195), (box.right - 18, box.bottom - 12), "bottomright", False, False)

    def draw_tele_select(self, s):
        dim = pygame.Surface((W, H), pygame.SRCALPHA)
        dim.fill((0, 6, 20, 190))
        s.blit(dim, (0, 0))
        text(s, "TELETRANSPORTADOR", 44, (170, 225, 255), (W // 2, H // 2 - 150), "center", True)
        text(s, "Elige un piso (1-7). El ayudante puede seguirte…", 20, (190, 200, 235), (W // 2, H // 2 - 100), "center", False, False)
        mp = pygame.mouse.get_pos()
        for i, r in enumerate(self.tele_rects()):
            col = FLOOR_COLORS[i]
            cur = i == self.floor
            hov = r.collidepoint(mp) and not cur
            rrect(s, lerpc((20, 24, 46), col, 0.35 if hov else 0.12), r, 16, 3, col)
            text(s, str(i + 1), 52, col if not cur else (120, 124, 150), (r.centerx, r.y + 44), "center", True)
            lab = "AQUÍ" if cur else (FLOOR_NAMES[i] or "PISO")
            text(s, lab, 15, (230, 235, 255), (r.centerx, r.bottom - 22), "center", True)
        text(s, "ESC: cancelar", 16, (150, 158, 195), (W // 2, H // 2 + 140), "center", False, False)

    # ---- menus
    def draw_menu_bg(self, s):
        s.blit(self.menu_bg, (0, 0))
        for x, y, r, v, ph in self.particles:
            a = int(50 + 40 * math.sin(self.t * 2 + ph))
            t = pygame.Surface((int(r * 2), int(r * 2.6)), pygame.SRCALPHA)
            pygame.draw.rect(t, (230, 235, 255, a), t.get_rect(), border_radius=3)
            pygame.draw.rect(t, (40, 40, 70, a), (3, 3, t.get_width() - 6, t.get_height() - 12), border_radius=2)
            s.blit(pygame.transform.rotate(t, math.sin(self.t + ph) * 20), (x, y))
        gs = scaled_glow(self.menu_glow, 0.7 + 0.3 * math.sin(self.t * 1.5))
        s.blit(gs, (850, 20), special_flags=pygame.BLEND_RGB_ADD)
        ent = pygame.transform.smoothscale(self.sprites["entity"][int(self.t * 3) % 4], (350, 555))
        s.blit(ent, (960, 120 + math.sin(self.t * 1.3) * 6))
        hero = pygame.transform.smoothscale(self.sprites["hero"][0], (230, 366))
        s.blit(hero, (760, 310 + math.sin(self.t * 2) * 4))
        ch = pygame.transform.smoothscale(self.sprites["chaser"][int(self.t * 2) % 4], (170, 270))
        s.blit(pygame.transform.flip(ch, True, False), (640, 440))
        vg = pygame.Surface((W, H), pygame.SRCALPHA)
        for i in range(0, 380, 4):
            pygame.draw.rect(vg, (4, 3, 12, int(210 * (1 - i / 380) ** 1.6)), (0, i * 0, 720 - i * 1.9, H))
        s.blit(vg, (0, 0))

    def draw_buttons(self, s, x, y, w=420, hgt=58, gap=14):
        items = self.menu_items()
        self.btns = []
        mp = pygame.mouse.get_pos()
        for i, (lbl, _) in enumerate(items):
            r = pygame.Rect(x, y + i * (hgt + gap), w, hgt)
            self.btns.append(r)
            sel = i == self.sel
            off = 12 if sel else 0
            rr = r.move(off, 0)
            rrect(s, (0, 0, 0), rr.move(0, 5), 14, alpha=100)
            rrect(s, (70, 30, 50) if sel else (24, 26, 50), rr, 14, 2, (255, 120, 140) if sel else (80, 90, 150), alpha=225)
            if sel:
                pygame.draw.polygon(s, (255, 120, 140), [(rr.x + 16, rr.centery - 8), (rr.x + 30, rr.centery), (rr.x + 16, rr.centery + 8)])
            text(s, lbl, 26, (255, 255, 255) if sel else (200, 206, 235), (rr.x + 48, rr.centery), "midleft", True)

    def draw_menu_screen(self, s):
        self.draw_menu_bg(s)
        st = self.state
        if st == "menu":
            t = glow_text("OLD", 120, (245, 240, 255), (255, 60, 90))
            s.blit(t, (60, 20))
            t2 = glow_text("MEMORIES", 96, (245, 240, 255), (255, 60, 90))
            s.blit(t2, (60, 140))
            text(s, "Etapa final  ·  Ciudadanía digital", 24, (255, 150, 170), (118, 272), "topleft", True)
            self.draw_buttons(s, 110, 340, 400, 56, 12)
            text(s, "Creado en Pygame · v2.0", 14, (130, 136, 175), (20, H - 28), "topleft", False, False)
        else:
            title = {"options": "OPCIONES", "controls": "CONTROLES", "credits": "CRÉDITOS"}[st]
            text(s, title, 60, (255, 255, 255), (100, 50), "topleft", True)
            pygame.draw.line(s, (255, 90, 120), (104, 124), (380, 124), 4)
            if st == "options":
                self.draw_buttons(s, 100, 170, 480, 60, 16)
                text(s, "La dificultad cambia la velocidad del ayudante y de la entidad, y su tiempo de reacción.", 16, (170, 176, 210), (104, 440), "topleft", False, False)
            elif st == "controls":
                rows = [("W A S D / Flechas", "Mover al personaje"), ("Shift", "Correr (gasta energía)"), ("E", "Interactuar: terminales, teletransportador, hablar"),
                        ("Mantener E", "Cocinar el sancocho / abrir la salida de incendios"), ("Q  ·  TAB", "Usar objeto de distracción  ·  cambiar objeto"),
                        ("E en un casillero", "Esconderte (y E de nuevo para salir)"), ("ESPACIO (escondida)", "Respirar hondo para bajar el pulso"),
                        ("Mouse", "Resolver los puzzles de los terminales"), ("ESC", "Pausa / salir del terminal"), ("F11", "Pantalla completa")]
                rrect(s, (10, 12, 30), (100, 150, 800, 470), 18, 2, (90, 100, 160), alpha=210)
                for i, (a, b) in enumerate(rows):
                    text(s, a, 20, (255, 170, 190), (130, 175 + i * 42), "topleft", True, False)
                    text(s, b, 18, (225, 230, 250), (400, 177 + i * 42), "topleft", False, False)
                self.draw_buttons(s, 100, 640, 260, 56, 0)
            else:
                rrect(s, (10, 12, 30), (100, 150, 720, 380), 18, 2, (90, 100, 160), alpha=210)
                lines = [("OLD MEMORIES", 30, (255, 150, 170)), ("Juego educativo sobre ciudadanía digital", 18, (220, 226, 250)),
                         ("", 10, (0, 0, 0)), ("Competencias clave:", 20, (255, 210, 150)),
                         ("• Alfabetización digital", 18, (225, 230, 250)), ("• Pensamiento crítico para verificar información", 18, (225, 230, 250)),
                         ("• Habilidades técnicas para usar herramientas tecnológicas", 18, (225, 230, 250)),
                         ("", 10, (0, 0, 0)), ("Hecho con Python y Pygame · Gráficos dibujados por código", 16, (150, 158, 195))]
                y = 175
                for t, sz, c in lines:
                    if t:
                        text(s, t, sz, c, (130, y), "topleft", sz >= 20, False)
                    y += sz + 14
                self.draw_buttons(s, 100, 580, 260, 56, 0)

    def draw_intro(self, s):
        s.fill((6, 4, 14))
        for x, y, r, v, ph in self.particles:
            pygame.draw.circle(s, (60, 40, 80), (int(x), int(y)), int(r / 4))
        t = STORY[self.slide]
        n = int(self.slide_t * 38)
        text(s, f"{self.slide + 1} / {len(STORY)}", 18, (130, 136, 175), (W // 2, 120), "center", False, False)
        para_reveal(s, t, n, 30, (235, 238, 255), 180, 220, W - 360, 44, True)
        spr = self.sprites[INTRO_SPRITES[self.slide]][0]
        s.blit(pygame.transform.smoothscale(spr, (spr.get_width() * 2, spr.get_height() * 2)), (W // 2 - spr.get_width(), 470))
        text(s, "ENTER / clic: continuar   ·   ESC: saltar", 16, (130, 136, 175), (W // 2, H - 24), "center", False, False)

    def draw_overlay_menu(self, s, title, col):
        dim = pygame.Surface((W, H), pygame.SRCALPHA)
        dim.fill((2, 2, 12, 200))
        s.blit(dim, (0, 0))
        text(s, title, 72, col, (W // 2, 150), "center", True)
        self.draw_buttons(s, W // 2 - 210, 240, 420, 58, 14)
        text(s, "Aulas resueltas: %d/%d · Fragmentos: %d/6 · Ingredientes: %d/6" % (self.solved, FLOORS * 4, len(self.frags), len(self.ings)), 18,
             (190, 198, 230), (W // 2, 540), "center", False, False)

    def draw_over(self, s):
        dim = pygame.Surface((W, H), pygame.SRCALPHA)
        dim.fill((40, 0, 8, 215))
        s.blit(dim, (0, 0))
        text(s, "TE ATRAPARON", 80, (255, 70, 90), (W // 2, 130), "center", True)
        msgs = {"chaser": "El ayudante te arrastró hasta ella. No hubo segunda oportunidad…",
                "pulse": "Tu corazón latía tan fuerte que el ayudante te escuchó tras la puerta del casillero.",
                "entity": "La entidad te alcanzó. Sus ojos nunca olvidan."}
        msg = msgs.get(self.caught_reason, msgs["entity"])
        text(s, msg, 22, (255, 200, 205), (W // 2, 215), "center", False, False)
        self.draw_buttons(s, W // 2 - 210, 290, 420, 58, 14)

    def draw_end(self, s):
        name, col, lines = ENDINGS[self.ending]
        dim = pygame.Surface((W, H), pygame.SRCALPHA)
        dim.fill((4, 6, 18, 235))
        s.blit(dim, (0, 0))
        text(s, "FINAL", 22, (160, 168, 205), (W // 2, 60), "center", False, False)
        text(s, name, 84, col, (W // 2, 120), "center", True)
        y = 210
        for ln in lines:
            y = para(s, ln, 22, (232, 236, 252), 220, y, W - 440, 30, False, False, True) + 10
        m, sec = divmod(int(self.play_time), 60)
        text(s, f"Tiempo: {m}:{sec:02d}   ·   Aulas resueltas: {self.solved}/{FLOORS * 4}   ·   Errores: {self.errors}   ·   Dificultad: {DIFFS[self.diff]}",
             17, (180, 188, 225), (W // 2, 480), "center", False, False)
        self.draw_buttons(s, W // 2 - 210, 520, 420, 56, 12)

    # -------------------------------------------------------------- bucle
    def run(self):
        while True:
            dt = min(self.clock.tick(FPS) / 1000.0, 0.05)
            for e in pygame.event.get():
                self.handle(e)
            self.update(dt)
            self.draw()
            pygame.display.flip()


def keys_sprint():
    k = pygame.key.get_pressed()
    return bool(k[pygame.K_LSHIFT] or k[pygame.K_RSHIFT])


def main():
    Game().run()


if __name__ == "__main__":
    main()
