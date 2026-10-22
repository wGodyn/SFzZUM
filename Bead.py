"""
Symulacja wielu koralików na okrągłym drucie – Position-Based Dynamics (PBD)
z obsługą kolizji koralik–koralik.

Program jest rozszerzeniem przykładu z jednym koralikiem (Lab05_1.html,
seria "Ten Minute Physics" Matthiasa Müllera). Tutaj koralików jest wiele,
mają różne promienie i masy, i zderzają się ze sobą.

Jak działa jeden "mały krok" symulacji (dokładnie taka kolejność jak w oryginale):

    1. start_step()   – grawitacja zmienia prędkość, koralik robi krok "na ślepo"
                        (zapamiętujemy też poprzednie położenie),
    2. keep_on_wire() – poprawiamy położenie, żeby koralik wrócił na drut,
    3. end_step()     – prędkość liczymy z faktycznego przesunięcia,
    4. kolizje        – sprawdzamy każdą parę koralików; jeśli się nakładają,
                        rozsuwamy je i wymieniamy prędkości (zderzenie sprężyste).

Uruchomienie:
    python -m pip install matplotlib
    python symulacja_wielu_koralikow.py
"""

import math
import random

import matplotlib.pyplot as plt
from matplotlib.patches import Circle
from matplotlib.widgets import Button


# =============================================================================
# 1. PARAMETRY SYMULACJI (tu można swobodnie eksperymentować)
# =============================================================================

# Grawitacja: skierowana pionowo w dół, 10 m/s^2 (tak jak w Lab05_1.html).
GRAVITY_X = 0.0
GRAVITY_Y = -10.0

# Czas symulowany w jednej klatce animacji: 1/60 sekundy.
DT = 1.0 / 60.0

# Na ile małych kroków dzielimy jedną klatkę.
# W oryginale (JavaScript) było 1000. W Pythonie obliczenia są wolniejsze,
# więc domyślnie jest 500 (wyniki są praktycznie takie same). Im więcej kroków,
# tym dokładniejsza symulacja, ale tym wolniej działa program.
# Jeśli animacja chodzi zbyt wolno, zmniejsz tę liczbę (np. do 200).
NUM_SUBSTEPS = 200

# Świat ma rozmiar 2 x 2 (jednostki "metrów"). Drut to okrąg w jego środku.
WORLD_SIZE = 2.0
WIRE_CENTER_X = WORLD_SIZE / 2.0
WIRE_CENTER_Y = WORLD_SIZE / 2.0
WIRE_RADIUS = WORLD_SIZE * 0.4          # = 0.8, tak jak w oryginale

# Koraliki.
NUM_BEADS = 5
FIRST_BEAD_RADIUS = 0.1                 # pierwszy koralik ma zawsze 0.1 (jak w oryginale)
MIN_BEAD_RADIUS = 0.05                  # pozostałe: losowy promień od 0.05 ...
MAX_BEAD_RADIUS = 0.15                  # ... do 0.15

# Współczynnik odbicia przy zderzeniu:
#   1.0 = zderzenie idealnie sprężyste (nie tracimy energii),
#   0.0 = zderzenie całkowicie niesprężyste (koraliki "sklejają się" w prędkości).
RESTITUTION = 1.0

# Co ile milisekund odświeżać animację.
TIMER_INTERVAL_MS = 16

# Kolory koralików na rysunku.
BEAD_COLORS = ["tab:red", "tab:green", "tab:blue", "tab:orange", "tab:purple",
               "tab:cyan", "tab:pink", "tab:olive"]


# =============================================================================
# 2. KLASA KORALIKA
# =============================================================================

class Bead:
    """Jeden koralik: położenie, poprzednie położenie, prędkość, promień i masa."""

    def __init__(self, radius, mass, x, y):
        self.radius = radius
        self.mass = mass

        # Położenie środka koralika.
        self.x = x
        self.y = y

        # Położenie sprzed ostatniego kroku (potrzebne do obliczenia prędkości w PBD).
        self.prev_x = x
        self.prev_y = y

        # Prędkość. Na początku koralik spoczywa.
        self.vx = 0.0
        self.vy = 0.0

    def start_step(self, h):
        """Krok A i B z notatek: grawitacja -> nowa prędkość -> przewidywane położenie."""
        # Zmiana prędkości = przyspieszenie * czas.
        self.vx += GRAVITY_X * h
        self.vy += GRAVITY_Y * h

        # Zapamiętujemy, gdzie koralik był przed krokiem.
        self.prev_x = self.x
        self.prev_y = self.y

        # Przesuwamy koralik według nowej prędkości.
        # Po tym kroku koralik może już NIE leżeć na drucie.
        self.x += self.vx * h
        self.y += self.vy * h

    def keep_on_wire(self):
        """Krok C z notatek: rzutowanie położenia z powrotem na okrąg (więź geometryczna)."""
        # Wektor od środka okręgu do koralika.
        dx = self.x - WIRE_CENTER_X
        dy = self.y - WIRE_CENTER_Y

        # Jego długość = odległość koralika od środka.
        distance = math.sqrt(dx * dx + dy * dy)

        # Szczególny przypadek: koralik dokładnie w środku okręgu.
        # Nie da się wtedy wyznaczyć kierunku, więc pomijamy korektę.
        if distance == 0.0:
            return

        # Wektor jednostkowy (długość 1) wskazujący od środka na koralik.
        dir_x = dx / distance
        dir_y = dy / distance

        # Poprawka: ile brakuje do promienia drutu.
        # (W JavaScript nazywa się to "lambda", ale w Pythonie "lambda"
        # jest słowem zastrzeżonym, więc używamy nazwy "correction".)
        #   distance > WIRE_RADIUS  ->  correction < 0  ->  przesuwamy do środka
        #   distance < WIRE_RADIUS  ->  correction > 0  ->  przesuwamy na zewnątrz
        correction = WIRE_RADIUS - distance

        self.x += dir_x * correction
        self.y += dir_y * correction

    def end_step(self, h):
        """Krok D z notatek: prędkość = (nowe położenie - poprzednie położenie) / czas."""
        self.vx = (self.x - self.prev_x) / h
        self.vy = (self.y - self.prev_y) / h


# =============================================================================
# 3. KOLIZJA DWÓCH KORALIKÓW
# =============================================================================

def handle_bead_bead_collision(bead1, bead2):
    """Jeśli koraliki się nakładają: rozsuń je i zmień ich prędkości."""

    # Wektor od koralika 1 do koralika 2 i odległość między ich środkami.
    dx = bead2.x - bead1.x
    dy = bead2.y - bead1.y
    distance = math.sqrt(dx * dx + dy * dy)

    # Brak kolizji, gdy koraliki są od siebie dalej niż suma ich promieni.
    # (distance == 0 pomijamy, bo nie da się wtedy wyznaczyć kierunku zderzenia.)
    radii_sum = bead1.radius + bead2.radius
    if distance == 0.0 or distance > radii_sum:
        return

    # Wektor jednostkowy "normalny": kierunek od koralika 1 do koralika 2.
    normal_x = dx / distance
    normal_y = dy / distance

    # --- Część 1: rozsunięcie (korekta położeń, jak w PBD) ---
    # O tyle koraliki wchodzą w siebie. Każdy z nich odsuwamy o połowę.
    overlap = radii_sum - distance
    shift = overlap / 2.0

    bead1.x -= normal_x * shift
    bead1.y -= normal_y * shift
    bead2.x += normal_x * shift
    bead2.y += normal_y * shift

    # --- Część 2: zmiana prędkości (zderzenie 1D wzdłuż normalnej) ---
    # Rzutujemy prędkości na kierunek zderzenia (iloczyn skalarny).
    v1 = bead1.vx * normal_x + bead1.vy * normal_y
    v2 = bead2.vx * normal_x + bead2.vy * normal_y

    m1 = bead1.mass
    m2 = bead2.mass

    # Wzory na prędkości po zderzeniu (zasada zachowania pędu + współczynnik odbicia).
    # Dla RESTITUTION = 1 i równych mas koraliki po prostu wymieniają się prędkościami.
    new_v1 = (m1 * v1 + m2 * v2 - m2 * (v1 - v2) * RESTITUTION) / (m1 + m2)
    new_v2 = (m1 * v1 + m2 * v2 - m1 * (v2 - v1) * RESTITUTION) / (m1 + m2)

    # Zmieniamy tylko składową prędkości wzdłuż normalnej;
    # składowa prostopadła do niej zostaje bez zmian.
    bead1.vx += normal_x * (new_v1 - v1)
    bead1.vy += normal_y * (new_v1 - v1)
    bead2.vx += normal_x * (new_v2 - v2)
    bead2.vy += normal_y * (new_v2 - v2)


# =============================================================================
# 4. SCENA: tworzenie koralików, krok symulacji, energia
# =============================================================================

# Lista wszystkich koralików. Wypełnia ją funkcja create_beads().
beads = []

# Stan programu.
is_running = False        # czy animacja chodzi (Run) czy jest zatrzymana (Pauza)
simulation_time = 0.0     # ile sekund symulacji już upłynęło
start_energy = 0.0        # energia całkowita na początku (do porównania)


def create_beads():
    """Tworzy NUM_BEADS koralików rozmieszczonych na drucie, wszystkie w spoczynku."""
    new_beads = []

    angle = 0.0   # pierwszy koralik na prawo od środka (kąt 0)

    for i in range(NUM_BEADS):
        # Promień koralika.
        if i == 0:
            radius = FIRST_BEAD_RADIUS
        else:
            radius = MIN_BEAD_RADIUS + random.random() * (MAX_BEAD_RADIUS - MIN_BEAD_RADIUS)

        # Masa proporcjonalna do pola koła (większy koralik = cięższy).
        mass = math.pi * radius * radius

        # Położenie na okręgu o promieniu WIRE_RADIUS dla danego kąta.
        x = WIRE_CENTER_X + WIRE_RADIUS * math.cos(angle)
        y = WIRE_CENTER_Y + WIRE_RADIUS * math.sin(angle)

        new_beads.append(Bead(radius, mass, x, y))

        # Następny koralik stawiamy dalej na okręgu: kąty rozłożone co pi/NUM_BEADS,
        # czyli koraliki zajmują górną połowę okręgu. Dzięki temu na starcie
        # na pewno się nie nakładają.
        angle += math.pi / NUM_BEADS

    return new_beads


def simulate_frame():
    """Liczy jedną klatkę animacji (DT sekund), podzieloną na wiele małych kroków."""
    global simulation_time

    # Długość jednego małego kroku.
    h = DT / NUM_SUBSTEPS

    for _ in range(NUM_SUBSTEPS):

        # 1. Każdy koralik robi krok pod wpływem grawitacji.
        for bead in beads:
            bead.start_step(h)

        # 2. Każdy koralik wraca na drut.
        for bead in beads:
            bead.keep_on_wire()

        # 3. Z faktycznych przesunięć liczymy prędkości.
        for bead in beads:
            bead.end_step(h)

        # 4. Kolizje: każda para koralików dokładnie raz (j < i).
        for i in range(len(beads)):
            for j in range(i):
                handle_bead_bead_collision(beads[i], beads[j])

    simulation_time += DT


def total_energy():
    """Energia całkowita układu = energia kinetyczna + energia potencjalna.

    Wysokość liczymy od środka drutu. Bez tarcia i przy RESTITUTION = 1
    energia powinna być (w przybliżeniu) stała - to dobry test symulacji.
    """
    gravity = -GRAVITY_Y   # wartość dodatnia, 10
    energy = 0.0

    for bead in beads:
        speed_squared = bead.vx * bead.vx + bead.vy * bead.vy
        kinetic = 0.5 * bead.mass * speed_squared
        potential = bead.mass * gravity * (bead.y - WIRE_CENTER_Y)
        energy += kinetic + potential

    return energy


# =============================================================================
# 5. OKNO, RYSOWANIE I PRZYCISKI
# =============================================================================

fig, ax = plt.subplots(figsize=(8, 8.5))
fig.subplots_adjust(bottom=0.14)   # miejsce na przyciski pod wykresem

ax.set_xlim(0.0, WORLD_SIZE)
ax.set_ylim(0.0, WORLD_SIZE)
ax.set_aspect("equal")             # koło ma wyglądać jak koło
ax.set_xticks([])
ax.set_yticks([])
ax.set_title("Wiele koralików na drucie – PBD i kolizje")

# Drut: okrąg bez wypełnienia.
wire_patch = Circle((WIRE_CENTER_X, WIRE_CENTER_Y), WIRE_RADIUS,
                    fill=False, edgecolor="black", linewidth=2)
ax.add_patch(wire_patch)

# Koraliki: po jednym kółku na koralik. Położenie i promień ustawia update_drawing().
bead_patches = []
for i in range(NUM_BEADS):
    color = BEAD_COLORS[i % len(BEAD_COLORS)]
    patch = Circle((0.0, 0.0), 0.1, facecolor=color, edgecolor="black")
    ax.add_patch(patch)
    bead_patches.append(patch)

# Napis z informacjami w lewym górnym rogu.
info_text = ax.text(0.02, 0.98, "", transform=ax.transAxes,
                    verticalalignment="top", family="monospace", fontsize=10)

# Przyciski (położenie: [lewo, dół, szerokość, wysokość] w ułamkach okna).
button_restart = Button(fig.add_axes([0.15, 0.03, 0.20, 0.06]), "Restart")
button_run = Button(fig.add_axes([0.40, 0.03, 0.20, 0.06]), "Run")
button_step = Button(fig.add_axes([0.65, 0.03, 0.20, 0.06]), "Step")


def update_drawing():
    """Przenosi aktualne położenia koralików na rysunek."""
    for bead, patch in zip(beads, bead_patches):
        patch.center = (bead.x, bead.y)
        patch.set_radius(bead.radius)

    if is_running:
        state = "URUCHOMIONA"
    else:
        state = "PAUZA"

    info_text.set_text(
        "Stan:                " + state + "\n"
        "Czas symulacji:      " + format(simulation_time, ".2f") + " s\n"
        "Energia początkowa:  " + format(start_energy, ".4f") + "\n"
        "Energia teraz:       " + format(total_energy(), ".4f")
    )


# =============================================================================
# 6. OBSŁUGA PRZYCISKÓW I CZASOMIERZA
# =============================================================================

def restart_scene(event=None):
    """Restart: nowe koraliki w pozycjach początkowych, zerowe prędkości, pauza."""
    global beads, is_running, simulation_time, start_energy

    is_running = False
    simulation_time = 0.0
    beads = create_beads()
    start_energy = total_energy()

    button_run.label.set_text("Run")
    update_drawing()
    fig.canvas.draw_idle()


def toggle_run(event=None):
    """Run / Pauza: przełącza ciągłe liczenie klatek."""
    global is_running

    is_running = not is_running

    if is_running:
        button_run.label.set_text("Pauza")
    else:
        button_run.label.set_text("Run")

    update_drawing()
    fig.canvas.draw_idle()


def do_one_step(event=None):
    """Step: liczy dokładnie jedną klatkę (1/60 s) i zatrzymuje animację."""
    global is_running

    is_running = False
    button_run.label.set_text("Run")

    simulate_frame()
    update_drawing()
    fig.canvas.draw_idle()


def on_timer():
    """Wywoływana co kilka milisekund: jeśli jest Run, policz klatkę i narysuj."""
    if not is_running:
        return

    simulate_frame()
    update_drawing()
    fig.canvas.draw_idle()


button_restart.on_clicked(restart_scene)
button_run.on_clicked(toggle_run)
button_step.on_clicked(do_one_step)


# =============================================================================
# 7. START PROGRAMU
# =============================================================================

if __name__ == "__main__":
    restart_scene()

    # Czasomierz musi być zapisany w zmiennej, inaczej Python go "posprząta".
    timer = fig.canvas.new_timer(interval=TIMER_INTERVAL_MS)
    timer.add_callback(on_timer)
    timer.start()

    plt.show()