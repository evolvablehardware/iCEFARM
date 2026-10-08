from __future__ import annotations

from icefarm.client.lib.bitstream import BitstreamEvaluation, BitstreamBaseClient

class VarMaxEvaluation(BitstreamEvaluation): ...

class VarMaxBaseClient(BitstreamBaseClient):
    """Provides access to variance maximization specific control API methods."""
    def reserve(self, devices: int | list[str], available_timeout: int=60, send_waveform: bool=False, flush_interval_seconds: int=10, flush_at_bitstreams_remaining: int=25):
        args = {
            "send_waveform": send_waveform,
        }

        return super().reserve(devices, "variance", extra_args=args, available_timeout=available_timeout, flush_interval_seconds=flush_interval_seconds, flush_at_bitstreams_remaining=flush_at_bitstreams_remaining)

