"""
Shared functions for the application
"""
from LM_cluster import run as cluster_run                                             # DEMO: neomatrix cluster

CURRENT_ANIMATION_INDEX = 0                                                           # DEMO: neomatrix cluster animation

def indicator_color(r, g, b):
    """
    TODO: Set RGB color on the indicator led
    """
    pass

def neomatrix_update():
    """
    TODO: Update remote neopixel matrix cluster
    """
    pass

def neomatrix_animation():
    """
    DEMO - Set random animation on neomatrix espnow cluster
    """
    global CURRENT_ANIMATION_INDEX
    animations = ('spiral', 'snake', 'noise')

    next_animation = CURRENT_ANIMATION_INDEX + 1
    CURRENT_ANIMATION_INDEX = 0 if next_animation >= len(animations) else next_animation
    command = f"neomatrix {animations[CURRENT_ANIMATION_INDEX]}"
    cluster_run(command)
    return {"cmd": command, "cluster": "task show con.espnow.*"}