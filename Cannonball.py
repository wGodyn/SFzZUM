"""Symulacja piłki, która leci i odbija się od ścian (wersja prosta).

Program jest przepisany z pliku Lab01.html.
"""

import tkinter as tk
from dataclasses import dataclass


@dataclass
class Vector2:
    """Para liczb: x to ruch poziomo, y to ruch pionowo."""
    x: float
    y: float


@dataclass
class Ball:
    """Piłka: ma wielkość, miejsce, w którym jest, i prędkość."""
    radius: float
    position: Vector2
    velocity: Vector2


class CannonballSimulation:
    def __init__(self, root):
        self.root = root
        self.root.title("Cannonball")

        # Okna nie da się rozciągać, bo skala jest liczona tylko raz.
        self.root.resizable(False, False)

        # --- Rozmiar płótna (obszaru rysowania) w pikselach ---
        self.canvas_width = max(200, root.winfo_screenwidth() - 20)
        self.canvas_height = max(200, root.winfo_screenheight() - 100)

        # Czarna ramka wokół płótna. Robimy ją osobno (Frame),
        # żeby nie zasłaniała brzegów obszaru rysowania.
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

        # --- Świat symulacji ---
        # Krótszy bok okna to 20 jednostek świata.
        # pixels_per_unit mówi, ile pikseli ma jedna jednostka świata.
        self.sim_min_width = 20.0
        shorter_side = min(self.canvas_width, self.canvas_height)
        self.pixels_per_unit = shorter_side / self.sim_min_width

        # Rozmiar świata w jednostkach (a nie w pikselach).
        self.sim_width = self.canvas_width / self.pixels_per_unit
        self.sim_height = self.canvas_height / self.pixels_per_unit

        # --- Ustawienia sceny ---
        self.gravity = Vector2(0.0, -10.0)   # grawitacja ciągnie w dół (minus)
        self.time_step = 1.0 / 60.0          # jeden krok = 1/60 sekundy

        self.ball = Ball(
            radius=0.2,
            position=Vector2(0.2, 0.2),
            velocity=Vector2(10.0, 15.0),
        )

        # Rysujemy piłkę raz. Potem tylko ją przesuwamy.
        self.ball_shape = self.canvas.create_oval(
            0, 0, 0, 0, fill="#FF0000", outline="#FF0000"
        )

        # Start pętli animacji.
        self.update()

    def to_pixel_x(self, world_x):
        """Zamienia pozycję poziomą ze świata symulacji na piksele."""
        return world_x * self.pixels_per_unit

    def to_pixel_y(self, world_y):
        """Zamienia pozycję pionową ze świata symulacji na piksele.

        W świecie symulacji y rośnie w górę, ale na ekranie rośnie w dół.
        Dlatego odejmujemy od wysokości płótna.
        """
        return self.canvas_height - world_y * self.pixels_per_unit

    def simulate(self):
        """Jeden krok symulacji: przesuwa piłkę i obsługuje odbicia."""

        # 1. Grawitacja zmienia prędkość.
        self.ball.velocity.x = self.ball.velocity.x + self.gravity.x * self.time_step
        self.ball.velocity.y = self.ball.velocity.y + self.gravity.y * self.time_step

        # 2. Prędkość zmienia położenie.
        self.ball.position.x = self.ball.position.x + self.ball.velocity.x * self.time_step
        self.ball.position.y = self.ball.position.y + self.ball.velocity.y * self.time_step

        # 3. Odbicie od lewej ściany.
        if self.ball.position.x < 0.0:
            self.ball.position.x = 0.0
            self.ball.velocity.x = -self.ball.velocity.x

        # 4. Odbicie od prawej ściany.
        if self.ball.position.x > self.sim_width:
            self.ball.position.x = self.sim_width
            self.ball.velocity.x = -self.ball.velocity.x

        # 5. Odbicie od podłogi.
        if self.ball.position.y < 0.0:
            self.ball.position.y = 0.0
            self.ball.velocity.y = -self.ball.velocity.y

        # Sufitu nie ma - tak samo jak w oryginale HTML.

    def draw(self):
        """Przesuwa narysowaną piłkę w nowe miejsce."""
        center_x = self.to_pixel_x(self.ball.position.x)
        center_y = self.to_pixel_y(self.ball.position.y)
        radius_in_pixels = self.pixels_per_unit * self.ball.radius

        # Koło rysujemy w kwadracie: lewy-górny i prawy-dolny róg.
        left = center_x - radius_in_pixels
        top = center_y - radius_in_pixels
        right = center_x + radius_in_pixels
        bottom = center_y + radius_in_pixels

        self.canvas.coords(self.ball_shape, left, top, right, bottom)

    def update(self):
        """Jedna klatka animacji: policz, narysuj, zaplanuj następną."""
        self.simulate()
        self.draw()

        # Za 16 milisekund (ok. 60 razy na sekundę) wywołaj update jeszcze raz.
        self.root.after(16, self.update)


def main():
    root = tk.Tk()
    CannonballSimulation(root)
    root.mainloop()


if __name__ == "__main__":
    main()
