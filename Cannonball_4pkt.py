"""
Symulacja wielu piłek odbijających się od ścian.
Sterowanie:
    Strzałka w górę - dodaje nową piłkę (maksymalnie MAX_BALLS)
    Strzałka w dół - usuwa ostatnio dodaną piłkę (pierwsza zostaje zawsze)
    Lewy przycisk - podbija piłkę najbliższą miejscu kliknięcia
    Prawy przycisk - podbija wszystkie piłki
"""

import random
import tkinter as tk
from dataclasses import dataclass


MAX_BALLS = 10                  # największa liczba piłek na ekranie

TIME_STEP = 1.0 / 60.0          # długość jednego kroku symulacji
FRAME_DELAY_MS = 16             # co ile milisekund rysujemy nową klatkę

GRAVITY_Y = -10.0               # grawitacja
AIR_RESISTANCE = 0.02           # opór powietrza

FLOOR_BOUNCINESS = 0.75          # sprężystość podłogi (1.0 = idealna, 0.0 = brak odbicia)
WALL_BOUNCINESS = 0.9          # sprężystość ścian

# Tarcie przy odbiciu: prędkość równoległa do przeszkody jest mnożona
# przez tę liczbę. 1.0 = brak tarcia, 0.9 = piłka traci 10% prędkości.
FLOOR_FRICTION_FACTOR = 0.97    # uderzenie w podłogę zmniejsza prędkość poziomą
WALL_FRICTION_FACTOR = 0.98     # uderzenie w ścianę zmniejsza prędkość pionową

ROLLING_DECELERATION = 1.0      # hamowanie piłki leżącej na podłodze

STOP_THRESHOLD = 0.3            # poniżej tej prędkości odbicia piłka przestaje podskakiwać

# Rozmiar i masa piłek
MIN_RADIUS = 0.2                # najmniejszy promień piłki
MAX_RADIUS = 0.8                # największy promień piłki

SMALLEST_BALL_MASS = 1.0        # masa piłki o najmniejszym promieniu
LARGEST_BALL_MASS = 1.5         # masa piłki o największym promieniu

# Podbijanie myszką
# Zmiana prędkości = siła podzielona przez masę piłki.
KICK_UP_STRENGTH = 7.0          # siła podbicia w górę
KICK_SIDE_STRENGTH = 9.0        # siła podbicia w bok

# Największe prędkości, jakie piłka może mieć zaraz po podbiciu.
MAX_VERTICAL_SPEED_AFTER_KICK = 14.0
MAX_HORIZONTAL_SPEED_AFTER_KICK = 15.0

# Prędkość pozioma nowych piłek
MIN_START_SPEED_X = 3.0         # najmniejsza prędkość pozioma nowej piłki
MAX_START_SPEED_X = 8.0         # największa prędkość pozioma nowej piłki

# 10 różnych kolorów. Pierwsza piłka dostaje pierwszy kolor z listy (czerwony).
BALL_COLORS = [
    "#FF0000",   # czerwony
    "#0066FF",   # niebieski
    "#00AA00",   # zielony
    "#FF8800",   # pomarańczowy
    "#AA00AA",   # fioletowy
    "#00BBBB",   # turkusowy
    "#FF66AA",   # różowy
    "#8B4513",   # brązowy
    "#99CC00",   # jasnozielony
    "#444444",   # ciemnoszary
]


# DANE
# =====================================================================

@dataclass
class Vector2:
    """Para liczb: x to ruch poziomo, y to ruch pionowo."""
    x: float
    y: float


@dataclass
class Ball:
    """Jedna piłka ze wszystkimi swoimi właściwościami."""
    radius: float           # promień piłki (w jednostkach świata)
    mass: float             # masa piłki (zależy od promienia)
    color: str              # kolor piłki
    position: Vector2       # miejsce, w którym jest środek piłki
    velocity: Vector2       # prędkość piłki
    canvas_item: int        # numer kółka narysowanego na płótnie
    is_resting: bool = False   # True, gdy piłka leży na podłodze


# FUNKCJE POMOCNICZE
# =====================================================================

def reduce_towards_zero(value, amount):
    """Zmniejsza wartość (bez względu na znak) o 'amount', ale nie poniżej zera.

    Przykłady:
        reduce_towards_zero(5.0, 2.0)   daje  3.0
        reduce_towards_zero(-5.0, 2.0)  daje -3.0
        reduce_towards_zero(1.0, 2.0)   daje  0.0   (nie przechodzimy przez zero)
    """
    if value > 0.0:
        new_value = value - amount
        if new_value < 0.0:
            new_value = 0.0
        return new_value
    else:
        new_value = value + amount
        if new_value > 0.0:
            new_value = 0.0
        return new_value


def calculate_mass(radius):
    """Oblicza masę piłki na podstawie jej promienia.

    Piłka o najmniejszym promieniu ma masę SMALLEST_BALL_MASS,
    piłka o największym promieniu ma masę LARGEST_BALL_MASS,
    a piłki pośrednie mają masę leżącą proporcjonalnie pomiędzy nimi.
    """
    # Liczba od 0.0 (najmniejsza piłka) do 1.0 (największa piłka).
    position_in_range = (radius - MIN_RADIUS) / (MAX_RADIUS - MIN_RADIUS)

    mass_difference = LARGEST_BALL_MASS - SMALLEST_BALL_MASS
    return SMALLEST_BALL_MASS + position_in_range * mass_difference


# GŁÓWNA KLASA PROGRAMU
# =====================================================================

class CannonballSimulation:
    def __init__(self, root):
        self.root = root
        self.root.title("Cannonball")

        # Okna nie da się rozciągać, bo skala jest liczona tylko raz.
        self.root.resizable(False, False)

        # Tekst z podpowiedzią nad płótnem
        self.info_label = tk.Label(root, text="", font=("Arial", 10))
        self.info_label.pack()

        # Rozmiar płótna (obszaru rysowania) w pikselach
        self.canvas_width = max(200, root.winfo_screenwidth() - 20)
        self.canvas_height = max(200, root.winfo_screenheight() - 120)

        # Czarna ramka wokół płótna. Robimy ją osobno,żeby nie zasłaniała brzegów obszaru rysowania.
        self.frame = tk.Frame(root, bg="black", padx=2, pady=2)
        self.frame.pack()

        self.canvas = tk.Canvas(
            self.frame,
            width=self.canvas_width,
            height=self.canvas_height,
            bg="white",
            highlightthickness=0,
        )
        self.canvas.pack()

        # Świat symulacji
        # Krótszy bok okna to 20 jednostek świata.
        # pixels_per_unit mówi, ile pikseli ma jedna jednostka świata.
        self.sim_min_width = 20.0
        shorter_side = min(self.canvas_width, self.canvas_height)
        self.pixels_per_unit = shorter_side / self.sim_min_width

        # Rozmiar świata w jednostkach (a nie w pikselach).
        self.sim_width = self.canvas_width / self.pixels_per_unit
        self.sim_height = self.canvas_height / self.pixels_per_unit

        # Lista piłek
        self.balls = []

        # Pierwsza piłka jest taka sama jak w oryginalnym programie (czerwona).
        first_ball = self.create_ball(
            radius=0.2,
            color=BALL_COLORS[0],
            position=Vector2(0.2, 0.2),
            velocity=Vector2(10.0, 15.0),
        )
        self.balls.append(first_ball)

        # Obsługa klawiszy i myszki (Windows)
        self.root.bind("<Up>", self.on_key_up)
        self.root.bind("<Down>", self.on_key_down)
        self.canvas.bind("<Button-1>", self.on_left_click)    # lewy przycisk
        self.canvas.bind("<Button-3>", self.on_right_click)   # prawy przycisk

        self.update_info_text()

        # Start pętli animacji.
        self.update()


    # Zamiana współrzędnych: świat symulacji <-> piksele
    # -----------------------------------------------------------------

    def to_pixel_x(self, world_x):
        """Zamienia pozycję poziomą ze świata symulacji na piksele."""
        return world_x * self.pixels_per_unit

    def to_pixel_y(self, world_y):
        """Zamienia pozycję pionową ze świata symulacji na piksele.

        W świecie symulacji y rośnie w górę, ale na ekranie rośnie w dół.
        Dlatego odejmujemy od wysokości płótna.
        """
        return self.canvas_height - world_y * self.pixels_per_unit

    def to_world_x(self, pixel_x):
        """Zamienia piksele (np. miejsce kliknięcia) na pozycję poziomą świata."""
        return pixel_x / self.pixels_per_unit

    def to_world_y(self, pixel_y):
        """Zamienia piksele (np. miejsce kliknięcia) na pozycję pionową świata."""
        return (self.canvas_height - pixel_y) / self.pixels_per_unit


    # Tworzenie i usuwanie piłek
    # -----------------------------------------------------------------

    def create_ball(self, radius, color, position, velocity):
        """Tworzy piłkę i rysuje ją na płótnie."""

        mass = calculate_mass(radius)

        # Rysujemy kółko (na razie w punkcie 0, draw() ustawi je w dobrym miejscu).
        canvas_item = self.canvas.create_oval(
            0, 0, 0, 0, fill=color, outline=color
        )

        return Ball(
            radius=radius,
            mass=mass,
            color=color,
            position=position,
            velocity=velocity,
            canvas_item=canvas_item,
        )

    def choose_free_color(self):
        """Losuje kolor, którego nie ma jeszcze żadna piłka na ekranie."""

        # Zbieramy kolory, które są już używane.
        used_colors = []
        for ball in self.balls:
            used_colors.append(ball.color)

        # Zbieramy kolory, które są wolne.
        free_colors = []
        for color in BALL_COLORS:
            if color not in used_colors:
                free_colors.append(color)

        # Gdyby wolnych kolorów zabrakło (np. po zwiększeniu MAX_BALLS powyżej liczby kolorów), bierzemy dowolny kolor z całej listy.
        if len(free_colors) == 0:
            return random.choice(BALL_COLORS)

        return random.choice(free_colors)

    def create_random_ball(self):
        """Tworzy piłkę o losowym rozmiarze, kolorze, miejscu i prędkości."""
        radius = random.uniform(MIN_RADIUS, MAX_RADIUS)
        color = self.choose_free_color()

        # Miejsce startu: gdzieś w górnej części ekranu, nie na samej krawędzi.
        position_x = random.uniform(radius, self.sim_width - radius)
        position_y = random.uniform(self.sim_height * 0.5, self.sim_height - 1.0)

        # Prędkość pozioma: zawsze wyraźnie różna od zera (od 3 do 8), a kierunek (w lewo albo w prawo) losujemy osobno.
        speed_x = random.uniform(MIN_START_SPEED_X, MAX_START_SPEED_X)
        direction_x = random.choice([-1.0, 1.0])
        velocity_x = speed_x * direction_x

        # Prędkość pionowa: trochę w dół albo trochę w górę.
        velocity_y = random.uniform(-5.0, 10.0)

        return self.create_ball(
            radius=radius,
            color=color,
            position=Vector2(position_x, position_y),
            velocity=Vector2(velocity_x, velocity_y),
        )

    def add_ball(self):
        """Dodaje nową piłkę, jeśli nie ma ich jeszcze za dużo."""
        if len(self.balls) < MAX_BALLS:
            new_ball = self.create_random_ball()
            self.balls.append(new_ball)
            self.update_info_text()

    def remove_last_ball(self):
        """Usuwa ostatnio dodaną piłkę. Pierwsza piłka zawsze zostaje."""
        if len(self.balls) > 1:
            last_ball = self.balls.pop()
            self.canvas.delete(last_ball.canvas_item)
            self.update_info_text()

    def update_info_text(self):
        """Odświeża napis nad płótnem."""
        self.info_label.config(
            text=(
                "Strzałka w górę: dodaj piłkę   |   "
                "Strzałka w dół: usuń piłkę   |   "
                "Lewy przycisk: podbij najbliższą   |   "
                "Prawy przycisk: podbij wszystkie   |   "
                f"Piłek: {len(self.balls)} / {MAX_BALLS}"
            )
        )

    # Obsługa klawiszy i myszki
    # -----------------------------------------------------------------

    def on_key_up(self, event):
        """Strzałka w górę: nowa piłka."""
        self.add_ball()

    def on_key_down(self, event):
        """Strzałka w dół: usuń ostatnią piłkę."""
        self.remove_last_ball()

    def on_left_click(self, event):
        """Lewy przycisk myszki: podbij piłkę najbliższą miejscu kliknięcia."""
        click_x = self.to_world_x(event.x)
        click_y = self.to_world_y(event.y)

        nearest_ball = self.find_nearest_ball(click_x, click_y)
        if nearest_ball is not None:
            self.kick_ball(nearest_ball)

    def on_right_click(self, event):
        """Prawy przycisk myszki: podbij wszystkie piłki."""
        for ball in self.balls:
            self.kick_ball(ball)

    def find_nearest_ball(self, world_x, world_y):
        """Zwraca piłkę, której środek jest najbliżej podanego punktu."""
        nearest_ball = None
        smallest_distance_squared = 0.0

        for ball in self.balls:
            difference_x = ball.position.x - world_x
            difference_y = ball.position.y - world_y
            # Porównujemy kwadraty odległości - nie trzeba liczyć pierwiastka.
            distance_squared = difference_x * difference_x + difference_y * difference_y

            if nearest_ball is None or distance_squared < smallest_distance_squared:
                nearest_ball = ball
                smallest_distance_squared = distance_squared

        return nearest_ball

    def get_kick_direction(self, ball):
        """Zwraca kierunek poziomy podbicia: 1.0 to w prawo, -1.0 to w lewo.

        Zasady podbicia piłki:
          - piłka porusza się w prawo -> podbijamy w prawo,
          - piłka porusza się w lewo -> podbijamy w lewo,
          - piłka stoi -> podbijamy w stronę środka okna.
        """
        if ball.velocity.x > 0.0:
            return 1.0

        if ball.velocity.x < 0.0:
            return -1.0

        # Piłka stoi (prędkość pozioma równa zero).
        middle_x = self.sim_width / 2.0
        if ball.position.x < middle_x:
            return 1.0      # piłka jest w lewej połowie, więc w prawo
        return -1.0         # piłka jest w prawej połowie, więc w lewo

    def kick_ball(self, ball):
        """Podbija piłkę w górę i w bok (w stronę, w którą się porusza).

        Lekka piłka dostaje większy impuls niż ciężka.
        """
        # Ile prędkości dodajemy: siła podzielona przez masę.
        speed_change_up = KICK_UP_STRENGTH / ball.mass
        speed_change_sideways = KICK_SIDE_STRENGTH / ball.mass

        direction_x = self.get_kick_direction(ball)

        # Dodajemy prędkości do tych, które piłka już ma.
        ball.velocity.y = ball.velocity.y + speed_change_up
        ball.velocity.x = ball.velocity.x + speed_change_sideways * direction_x

        # Ograniczamy prędkość po podbiciu, żeby piłka nie wyleciała poza ekran.
        if ball.velocity.y > MAX_VERTICAL_SPEED_AFTER_KICK:
            ball.velocity.y = MAX_VERTICAL_SPEED_AFTER_KICK

        if ball.velocity.x > MAX_HORIZONTAL_SPEED_AFTER_KICK:
            ball.velocity.x = MAX_HORIZONTAL_SPEED_AFTER_KICK

        if ball.velocity.x < -MAX_HORIZONTAL_SPEED_AFTER_KICK:
            ball.velocity.x = -MAX_HORIZONTAL_SPEED_AFTER_KICK

        # Podbita piłka przestaje leżeć na podłodze.
        ball.is_resting = False


    # Fizyka
    # -----------------------------------------------------------------

    def simulate_ball(self, ball):
        """Jeden krok symulacji dla jednej piłki."""

        # 1. Grawitacja zmienia prędkość (ale nie dla piłki leżącej na podłodze).
        if not ball.is_resting:
            ball.velocity.y = ball.velocity.y + GRAVITY_Y * TIME_STEP

        # 2. Opór powietrza lekko zmniejsza prędkość. Szybka piłka hamuje mocniej niż wolna.
        air_factor = 1.0 - AIR_RESISTANCE * TIME_STEP
        ball.velocity.x = ball.velocity.x * air_factor
        ball.velocity.y = ball.velocity.y * air_factor

        # 3. Prędkość zmienia położenie.
        ball.position.x = ball.position.x + ball.velocity.x * TIME_STEP
        if not ball.is_resting:
            ball.position.y = ball.position.y + ball.velocity.y * TIME_STEP

        # 4. Odbicia od ścian i podłogi.
        self.bounce_off_walls(ball)
        if not ball.is_resting:
            self.bounce_off_floor(ball)

        # 5. Piłka leżąca na podłodze powoli się zatrzymuje (tarcie toczne).
        if ball.is_resting:
            self.apply_rolling_friction(ball)

    def bounce_off_floor(self, ball):
        """Odbicie od podłogi: sprężystość + tarcie + zatrzymanie."""

        # Piłka dotyka podłogi, gdy jej DOLNA krawędź (środek - promień) zejdzie poniżej zera.
        if ball.position.y - ball.radius >= 0.0:
            return   # piłka jest nad podłogą, nic nie robimy

        # Ustawiamy piłkę dokładnie na podłodze.
        ball.position.y = ball.radius

        # Odbijamy tylko, jeśli piłka porusza się w dół.
        if ball.velocity.y >= 0.0:
            return

        # Prędkość uderzenia (liczba dodatnia).
        impact_speed = -ball.velocity.y

        # Składowa pionowa: odbicie ze stratą energii.
        bounce_speed = impact_speed * FLOOR_BOUNCINESS

        # Składowa pozioma: lekkie tarcie o podłogę.
        ball.velocity.x = ball.velocity.x * FLOOR_FRICTION_FACTOR

        if bounce_speed < STOP_THRESHOLD:
            # Odbicie jest za słabe - piłka przestaje podskakiwać i zostaje na podłodze.
            ball.velocity.y = 0.0
            ball.is_resting = True
        else:
            ball.velocity.y = bounce_speed

    def bounce_off_walls(self, ball):
        """Odbicie od lewej i prawej ściany: sprężystość + lekkie tarcie."""

        # Lewa ściana
        if ball.position.x - ball.radius < 0.0:
            ball.position.x = ball.radius

            if ball.velocity.x < 0.0:
                # Odbicie: zmieniamy kierunek i tracimy trochę energii.
                ball.velocity.x = -ball.velocity.x * WALL_BOUNCINESS
                # Lekkie tarcie o ścianę hamuje ruch pionowy.
                ball.velocity.y = ball.velocity.y * WALL_FRICTION_FACTOR

        # Prawa ściana
        right_limit = self.sim_width - ball.radius
        if ball.position.x > right_limit:
            ball.position.x = right_limit

            if ball.velocity.x > 0.0:
                ball.velocity.x = -ball.velocity.x * WALL_BOUNCINESS
                ball.velocity.y = ball.velocity.y * WALL_FRICTION_FACTOR

    def apply_rolling_friction(self, ball):
        """Hamuje poziomy ruch piłki leżącej na podłodze.

        Hamowanie ma stałą wartość, więc piłka zatrzymuje się po skończonym
        czasie (a nie zwalnia w nieskończoność).
        """
        slowdown = ROLLING_DECELERATION * TIME_STEP
        ball.velocity.x = reduce_towards_zero(ball.velocity.x, slowdown)

    # Rysowanie
    # -----------------------------------------------------------------

    def draw(self):
        """Przesuwa narysowane piłki w nowe miejsca."""
        for ball in self.balls:
            center_x = self.to_pixel_x(ball.position.x)
            center_y = self.to_pixel_y(ball.position.y)
            radius_in_pixels = self.pixels_per_unit * ball.radius

            # Koło rysujemy w kwadracie: lewy-górny i prawy-dolny róg.
            left = center_x - radius_in_pixels
            top = center_y - radius_in_pixels
            right = center_x + radius_in_pixels
            bottom = center_y + radius_in_pixels

            self.canvas.coords(ball.canvas_item, left, top, right, bottom)

    def update(self):
        """Jedna klatka animacji: policz, narysuj, zaplanuj następną."""
        for ball in self.balls:
            self.simulate_ball(ball)

        self.draw()

        # Za chwilę (ok. 60 razy na sekundę) wywołaj update jeszcze raz.
        self.root.after(FRAME_DELAY_MS, self.update)


def main():
    root = tk.Tk()
    CannonballSimulation(root)
    root.mainloop()


if __name__ == "__main__":
    main()