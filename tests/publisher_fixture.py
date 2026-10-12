"""Independent cached native fixture; no Observer collection or adapters."""

from sdk_fixture import Publisher

from mesh_plus.api import CachedPublication, CachedPublisher


class Source:
    def __init__(self, domain, host, source="default"):
        self.fixture = Publisher(domain, host, source)
        self.reads = 0

    async def snapshot(self):
        self.reads += 1
        return self.fixture.frame

    async def watch(self):
        self.fixture.watchers += 1
        try:
            while True:
                frame = self.fixture.frame
                epoch = self.fixture.codec.inspect_native(frame).publisher
                yield CachedPublication(frame, epoch, {"revision": frame["viewRevision"]})
                await self.fixture.changes.get()
        finally:
            self.fixture.watchers -= 1


def factory(domain):
    def build(host, source, socket):
        native = Source(domain, host, source)
        return CachedPublisher(domain, host, source, native, profile=native.fixture.state_profile)
    return build


class KitPublisher(CachedPublisher):
    """Adapt fixture controls to the portable kit; delivery remains the public helper."""

    def __init__(self, domain, host, source, profile):
        native = Source(domain, host, source)
        super().__init__(domain, host, source, native, profile=profile)

    @property
    def frame(self):
        return self.native.fixture.frame

    @frame.setter
    def frame(self, value):
        self.native.fixture.frame = value

    @property
    def watchers(self):
        return self.native.fixture.watchers

    @property
    def changes(self):
        return self.native.fixture.changes

    def wrap(self, frame=None, nonce=None):
        if not isinstance(frame, dict):
            nonce, frame = frame, self.frame
        return super().wrap(frame, nonce)
