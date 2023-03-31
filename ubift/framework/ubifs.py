from ubift.framework.ubi import UBIVolume
from ubift.logging import ubiftlog


class UBIFS:
    """
    Represents an UBIFS instance which resides within an UBI volume.
    """

    def __init__(self, ubi_volume: UBIVolume):
        self._ubi_volume = ubi_volume

        if self._validate() == False:
            ubiftlog.error(f"[-] Invalid UBIFS instance for UBI volume {self._ubi_volume}")

        ubiftlog.info(f"[!] Initialized UBIFS instance for UBI volume {self._ubi_volume}")

    def _validate(self) -> bool:
        return True

    @property
    def ubi_volume(self) -> UBIVolume:
        return self._ubi_volume
