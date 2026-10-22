"""
Symulacja wielu koralików na okrągłym drucie – Position-Based Dynamics (PBD)
z obsługą kolizji koralik–koralik.

Jak działa jeden "mały krok" symulacji:
    1. start_step() – grawitacja zmienia prędkość, koralik robi krok "na ślepo" (zapamiętujemy też poprzednie położenie),
    2. keep_on_wire() – poprawiamy położenie, żeby koralik wrócił na drut,
    3. end_step() – prędkość liczymy z faktycznego przesunięcia,
    4. kolizje – sprawdzamy każdą parę koralików; jeśli się nakładają, rozsuwamy je i wymieniamy prędkości (zderzenie sprężyste).

Czas w symulacji płynie tak samo szybko jak czas rzeczywisty: w każdej klatce
mierzymy, ile naprawdę upłynęło sekund, i o tyle przesuwamy symulację.

Do rysowania używamy "blittingu": tło okna rysujemy raz, a w każdej klatce
odświeżamy tylko koraliki i napis. Dzięki temu animacja jest płynniejsza.
"""

import math
import random
import time

import matplotlib.pyplot as plt
from matplotlib.patches import Circle
from matplotlib.widgets import Button

# --- parametry ---

# grawitacja skierowana w dół
GRAVITY_X = 0.0
GRAVITY_Y = -10.0

# czas symulowany po kliknięciu Step (1/60 s)
STEP_BUTTON_TIME = 1.0 / 60.0

# tempo symulacji względem czasu rzeczywistego (0.8 = 1.25 raza wolniej)
TIME_SCALE = 0.825

# maksymalny czas jednej klatki (chroni przed skokiem po zawieszeniu okna)
MAX_FRAME_TIME = 0.05

# liczba małych kroków w jednej klatce (w oryginale 1000, mniej = szybciej)
NUM_SUBSTEPS = 500

# świat 2 x 2, drut to okrąg na środku
WORLD_SIZE = 2.0
WIRE_CENTER_X = WORLD_SIZE / 2.0
WIRE_CENTER_Y = WORLD_SIZE / 2.0
WIRE_RADIUS = WORLD_SIZE * 0.4

# pierwszy koralik ma stały promień, reszta losowy z zakresu min-max
NUM_BEADS = 5
FIRST_BEAD_RADIUS = 0.1
MIN_BEAD_RADIUS = 0.05
MAX_BEAD_RADIUS = 0.15

# 1.0 = zderzenia sprężyste, 0.0 = całkowicie niesprężyste
RESTITUTION = 1.0

# co ile ms uruchamiać czasomierz
TIMER_INTERVAL_MS = 1

# odcienie niebieskiego, sąsiednie różnią się jasnością
BEAD_COLORS = [
    "#08306b",
    "#9ecae1",
    "#2171b5",
    "#deebf7",
    "#6baed6",
    "#08519c",
    "#c6dbef",
    "#4292c6",
]


# --- koralik ---

class Bead:
    def __init__(self, radius, mass, x, y):
        self.radius = radius
        self.mass = mass
        self.x = x
        self.y = y
        self.prev_x = x
        self.prev_y = y
        self.vx = 0.0
        self.vy = 0.0

    def start_step(self, h):
        # grawitacja zmienia prędkość
        self.vx += GRAVITY_X * h
        self.vy += GRAVITY_Y * h

        # zapamiętujemy położenie i robimy krok
        self.prev_x = self.x
        self.prev_y = self.y
        self.x += self.vx * h
        self.y += self.vy * h

    def keep_on_wire(self):
        # wektor od środka okręgu do koralika
        dx = self.x - WIRE_CENTER_X
        dy = self.y - WIRE_CENTER_Y
        distance = math.sqrt(dx * dx + dy * dy)

        # w samym środku nie ma kierunku, więc nic nie robimy
        if distance == 0.0:
            return

        dir_x = dx / distance
        dir_y = dy / distance

        # ile brakuje do promienia drutu (w JS to "lambda")
        correction = WIRE_RADIUS - distance

        self.x += dir_x * correction
        self.y += dir_y * correction

    def end_step(self, h):
        # prędkość z faktycznego przesunięcia
        self.vx = (self.x - self.prev_x) / h
        self.vy = (self.y - self.prev_y) / h


# --- kolizje ---

def handle_bead_bead_collision(bead1, bead2):
    dx = bead2.x - bead1.x
    dy = bead2.y - bead1.y
    distance = math.sqrt(dx * dx + dy * dy)

    # brak kolizji, gdy koraliki są dalej niż suma promieni
    radii_sum = bead1.radius + bead2.radius
    if distance == 0.0 or distance > radii_sum:
        return

    # kierunek od koralika 1 do 2
    normal_x = dx / distance
    normal_y = dy / distance

    # rozsuwamy koraliki, każdy o połowę nakładania
    overlap = radii_sum - distance
    shift = overlap / 2.0

    bead1.x -= normal_x * shift
    bead1.y -= normal_y * shift
    bead2.x += normal_x * shift
    bead2.y += normal_y * shift

    # prędkości wzdłuż kierunku zderzenia
    v1 = bead1.vx * normal_x + bead1.vy * normal_y
    v2 = bead2.vx * normal_x + bead2.vy * normal_y

    m1 = bead1.mass
    m2 = bead2.mass

    # prędkości po zderzeniu (pęd + współczynnik odbicia)
    new_v1 = (m1 * v1 + m2 * v2 - m2 * (v1 - v2) * RESTITUTION) / (m1 + m2)
    new_v2 = (m1 * v1 + m2 * v2 - m1 * (v2 - v1) * RESTITUTION) / (m1 + m2)

    bead1.vx += normal_x * (new_v1 - v1)
    bead1.vy += normal_y * (new_v1 - v1)
    bead2.vx += normal_x * (new_v2 - v2)
    bead2.vy += normal_y * (new_v2 - v2)


# --- scena ---

beads = []
is_running = False
simulation_time = 0.0
last_time = time.perf_counter()


def create_beads():
    new_beads = []
    angle = 0.0

    for i in range(NUM_BEADS):
        if i == 0:
            radius = FIRST_BEAD_RADIUS
        else:
            radius = MIN_BEAD_RADIUS + random.random() * (MAX_BEAD_RADIUS - MIN_BEAD_RADIUS)

        # masa proporcjonalna do pola koła
        mass = math.pi * radius * radius

        x = WIRE_CENTER_X + WIRE_RADIUS * math.cos(angle)
        y = WIRE_CENTER_Y + WIRE_RADIUS * math.sin(angle)

        new_beads.append(Bead(radius, mass, x, y))

        # koraliki na górnej połowie okręgu, nie nakładają się
        angle += math.pi / NUM_BEADS

    return new_beads


def simulate_frame(frame_time):
    global simulation_time

    h = frame_time / NUM_SUBSTEPS

    for _ in range(NUM_SUBSTEPS):
        for bead in beads:
            bead.start_step(h)

        for bead in beads:
            bead.keep_on_wire()

        for bead in beads:
            bead.end_step(h)

        # każda para koralików raz
        for i in range(len(beads)):
            for j in range(i):
                handle_bead_bead_collision(beads[i], beads[j])

    simulation_time += frame_time


# --- okno i rysowanie ---

fig, ax = plt.subplots(figsize=(8, 8.5))
fig.subplots_adjust(bottom=0.14)

ax.set_xlim(0.0, WORLD_SIZE)
ax.set_ylim(0.0, WORLD_SIZE)
ax.set_aspect("equal")
ax.set_xticks([])
ax.set_yticks([])
ax.set_title("Many beads on a wire - PBD and collisions")

wire_patch = Circle((WIRE_CENTER_X, WIRE_CENTER_Y), WIRE_RADIUS,
                    fill=False, edgecolor="black", linewidth=2)
ax.add_patch(wire_patch)

bead_patches = []
for i in range(NUM_BEADS):
    color = BEAD_COLORS[i % len(BEAD_COLORS)]
    patch = Circle((0.0, 0.0), 0.1, facecolor=color, edgecolor="black", linewidth=1)
    ax.add_patch(patch)
    bead_patches.append(patch)

info_text = ax.text(0.02, 0.98, "", transform=ax.transAxes,
                    verticalalignment="top", family="monospace", fontsize=10)

button_restart = Button(fig.add_axes([0.15, 0.03, 0.20, 0.06]), "Restart")
button_run = Button(fig.add_axes([0.40, 0.03, 0.20, 0.06]), "Run")
button_step = Button(fig.add_axes([0.65, 0.03, 0.20, 0.06]), "Step")

# Blitting: koraliki i napis rysujemy osobno na zapamiętanym tle.
animated_artists = bead_patches + [info_text]

for artist in animated_artists:
    artist.set_animated(True)

background = None


def draw_animated_artists():
    for artist in animated_artists:
        fig.draw_artist(artist)


def on_full_draw(event):
    # po każdym pełnym przerysowaniu okna zapamiętujemy nowe tło
    global background
    background = fig.canvas.copy_from_bbox(ax.bbox)
    draw_animated_artists()


fig.canvas.mpl_connect("draw_event", on_full_draw)


def fast_redraw():
    if background is None:
        fig.canvas.draw_idle()
        return

    fig.canvas.restore_region(background)
    draw_animated_artists()
    fig.canvas.blit(ax.bbox)


def update_drawing():
    for bead, patch in zip(beads, bead_patches):
        patch.center = (bead.x, bead.y)
        patch.set_radius(bead.radius)

    if is_running:
        state = "RUNNING"
    else:
        state = "PAUSED"

    info_text.set_text(
        "State:            " + state + "\n"
        "Simulation time:  " + format(simulation_time, ".2f") + " s"
    )


# --- przyciski i czasomierz ---

def restart_scene(event=None):
    global beads, is_running, simulation_time

    is_running = False
    simulation_time = 0.0
    beads = create_beads()

    button_run.label.set_text("Run")
    update_drawing()
    fig.canvas.draw_idle()


def toggle_run(event=None):
    global is_running, last_time

    is_running = not is_running

    if is_running:
        button_run.label.set_text("Pause")
        # liczymy czas od zera, żeby nie było skoku po pauzie
        last_time = time.perf_counter()
    else:
        button_run.label.set_text("Run")

    update_drawing()
    fig.canvas.draw_idle()


def do_one_step(event=None):
    global is_running

    is_running = False
    button_run.label.set_text("Run")

    simulate_frame(STEP_BUTTON_TIME)
    update_drawing()
    fig.canvas.draw_idle()


def on_timer():
    global last_time

    # ile sekund naprawdę minęło od poprzedniej klatki
    now = time.perf_counter()
    real_time_passed = now - last_time
    last_time = now

    if not is_running:
        return

    if real_time_passed > MAX_FRAME_TIME:
        real_time_passed = MAX_FRAME_TIME

    simulate_frame(real_time_passed * TIME_SCALE)
    update_drawing()
    fast_redraw()


button_restart.on_clicked(restart_scene)
button_run.on_clicked(toggle_run)
button_step.on_clicked(do_one_step)


if __name__ == "__main__":
    restart_scene()

    # timer musi być w zmiennej, inaczej zostanie usunięty z pamięci
    timer = fig.canvas.new_timer(interval=TIMER_INTERVAL_MS)
    timer.add_callback(on_timer)
    timer.start()

    plt.show()