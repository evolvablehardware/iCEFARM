from __future__ import annotations

from icefarm.client.lib.bitstream import BitstreamEvaluation, BitstreamBaseClient

class PulseCountEvaluation(BitstreamEvaluation): ...

class PulseCountBaseClient(BitstreamBaseClient):
    """Provides access to pulse count specific control API methods."""
    def reserve(self, devices: int | list[str], available_timeout: int=60, flush_interval_seconds: int=10, flush_at_bitstreams_remaining: int=25):
        return super().reserve(devices, "pulsecount", available_timeout=available_timeout, flush_interval_seconds=flush_interval_seconds, flush_at_bitstreams_remaining=flush_at_bitstreams_remaining)
