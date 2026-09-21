"""Glue between the audio and widget layers, kept out of both so neither depends on the other."""

from __future__ import annotations

from audiowave.audio.player import AudioPlayer, PlayerState
from audiowave.widgets.overview import OverviewView
from audiowave.widgets.timeline import TimelineView


def bind_player(player: AudioPlayer, *views: TimelineView | OverviewView, sync_loop: bool = True, follow: bool = True) -> None:
    """Connect a player to any number of timeline widgets.

    The player drives each view's playhead; clicks on a view seek the player; loops drawn on a view
    become the player's loop (unless ``sync_loop`` is False); and, unless ``follow`` is False, views scroll to keep the playhead
    visible while playing.
    Views stay unaware of the player and vice versa, so this is the only place they meet.
    """
    for view in views:
        player.positionChanged.connect(view.set_position)
        view.seekRequested.connect(player.seek)
        if sync_loop and hasattr(view, "loopChanged"):
            view.loopChanged.connect(player.set_loop)

    def follow_playhead(state: PlayerState) -> None:
        for view in views:
            if isinstance(view, TimelineView):
                view.set_follow(state is PlayerState.PLAYING)

    if follow:
        player.stateChanged.connect(follow_playhead)
