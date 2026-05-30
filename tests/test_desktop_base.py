from src.code_ai.desktop.platforms import base


class FakeProc:
    def __init__(self, exe, children=None):
        self.info = {"exe": exe}
        self._children = children or []
        self.terminated = False
        self.killed = False

    def children(self, recursive=False):
        return list(self._children)

    def terminate(self):
        self.terminated = True

    def kill(self):
        self.killed = True


class FakePsutil:
    """Minimal psutil stand-in. `dead_on_wait` controls wait_procs result."""
    def __init__(self, procs, dead_on_wait=True):
        self._procs = procs
        self._dead_on_wait = dead_on_wait

    def process_iter(self, attrs=None):
        return list(self._procs)

    def wait_procs(self, procs, timeout=None):
        if self._dead_on_wait:
            return (list(procs), [])
        return ([], list(procs))


def test_appstatus_display_state():
    assert base.AppStatus("x", found=False).display_state == "not_found"
    assert base.AppStatus("x", found=True, direct=False).display_state == "brokered"
    assert base.AppStatus("x", found=True, direct=True).display_state == "direct"


def test_any_process_under_matches_directory_prefix(monkeypatch):
    procs = [FakeProc(r"C:\Apps\Claude\app\Claude.exe"), FakeProc(r"C:\Other\thing.exe")]
    monkeypatch.setattr(base, "psutil", FakePsutil(procs))
    assert base.any_process_under([r"C:\Apps\Claude"]) is True
    assert base.any_process_under([r"C:\Nope"]) is False
    assert base.any_process_under([""]) is False


def test_stop_terminates_matches_and_children_not_others(monkeypatch):
    child = FakeProc(r"C:\Apps\Claude\helper.exe")
    match = FakeProc(r"C:\Apps\Claude\app\Claude.exe", children=[child])
    other = FakeProc(r"C:\Other\thing.exe")
    monkeypatch.setattr(base, "psutil", FakePsutil([match, other], dead_on_wait=True))

    base.stop_processes_under([r"C:\Apps\Claude"])

    assert match.terminated is True
    assert child.terminated is True
    assert other.terminated is False
    assert match.killed is False  # died on terminate, no kill needed


def test_stop_kills_stragglers(monkeypatch):
    match = FakeProc(r"C:\Apps\Claude\app\Claude.exe")
    monkeypatch.setattr(base, "psutil", FakePsutil([match], dead_on_wait=False))

    base.stop_processes_under([r"C:\Apps\Claude"])

    assert match.terminated is True
    assert match.killed is True
