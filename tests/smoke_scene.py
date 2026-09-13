from manim import FadeIn, Scene, Text


class SmokeScene(Scene):
    def construct(self):
        label = Text("Manim is ready", font_size=40)
        self.play(FadeIn(label), run_time=0.2)
        self.wait(0.2)
