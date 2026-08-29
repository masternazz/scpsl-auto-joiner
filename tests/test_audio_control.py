from audio_control import GameAudioMute


class FakeVolume:
    def __init__(self, muted=False):
        self.muted = muted

    def GetMute(self):
        return self.muted

    def SetMute(self, value, _event):
        self.muted = bool(value)


class FakeSession:
    def __init__(self, volume):
        self.SimpleAudioVolume = volume


def test_game_audio_mute_restores_previous_state(monkeypatch):
    volume = FakeVolume(muted=False)
    controller = GameAudioMute()
    controller.available = True
    monkeypatch.setattr(controller, "_game_sessions", lambda: [FakeSession(volume)])

    controller._mute_current()
    assert volume.muted is True
    controller.stop()
    assert volume.muted is False


def test_game_audio_mute_preserves_already_muted_session(monkeypatch):
    volume = FakeVolume(muted=True)
    controller = GameAudioMute()
    controller.available = True
    monkeypatch.setattr(controller, "_game_sessions", lambda: [FakeSession(volume)])

    controller._mute_current()
    controller.stop()
    assert volume.muted is True
