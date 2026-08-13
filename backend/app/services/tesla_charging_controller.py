from dataclasses import dataclass
from typing import Optional


@dataclass
class TeslaChargingControllerConfig:
    voltage_v: float = 230.0

    min_charging_current_a: int = 6
    max_charging_current_a: int = 32

    max_snapshot_age_seconds: int = 420

    # Keep a little charging-power headroom so small
    # house-load changes do not immediately cause grid import.
    safety_reserve_kw: float = 0.30

    # Ignore small current changes.
    current_change_threshold_a: int = 2

    # Increases are deliberately slower.
    increase_hold_seconds: int = 45

    # Decreases happen faster to protect against grid import.
    decrease_hold_seconds: int = 10


@dataclass
class TeslaChargingControllerState:
    charging: bool = False
    current_a: int = 0

    pending_current_a: Optional[int] = None
    pending_since: Optional[float] = None


@dataclass
class TeslaChargingCommand:
    action: str
    target_current_a: int
    reason: str


class TeslaChargingController:
    """
    Stabilizes Tesla charging decisions.

    This controller DOES NOT communicate with Tesla.

    It only decides what Helios should do.

    Possible actions:
        start
        stop
        set_current
        hold
    """

    def __init__(
        self,
        config: Optional[
            TeslaChargingControllerConfig
        ] = None,
    ):
        self.config = (
            config
            or TeslaChargingControllerConfig()
        )

        self.state = TeslaChargingControllerState()

    def calculate_raw_current(
        self,
        available_power_kw: float,
    ) -> int:
        """
        Convert available charging power into charging amps.

        A safety reserve is removed first.
        """

        usable_power_kw = max(
            available_power_kw
            - self.config.safety_reserve_kw,
            0.0,
        )

        amps = int(
            usable_power_kw
            * 1000
            / self.config.voltage_v
        )

        return min(
            amps,
            self.config.max_charging_current_a,
        )

    def update(
        self,
        *,
        available_power_kw: float,
        charging_allowed: bool,
        now: float,
        snapshot_age_seconds: float = 0.0,
    ) -> TeslaChargingCommand:
        """
        Evaluate Helios charging conditions and return
        the Tesla command that should be performed.
        """

        #
        # Stale telemetry always blocks charging.
        #
        if (
            snapshot_age_seconds
            > self.config.max_snapshot_age_seconds
        ):
            return self._stop(
                reason=(
                    f"Solis data is stale "
                    f"({snapshot_age_seconds:.0f}s old); "
                    f"Tesla charging blocked"
                )
            )

        #
        # The upstream charging policy always has authority.
        #
        if not charging_allowed:
            return self._stop(
                reason=(
                    "Energy decision engine does not "
                    "allow Tesla charging"
                )
            )

        raw_current = self.calculate_raw_current(
            available_power_kw
        )

        #
        # Tesla cannot AC charge below our configured minimum.
        #
        if (
            raw_current
            < self.config.min_charging_current_a
        ):
            return self._stop(
                reason=(
                    "Available charging power is below minimum "
                    "Tesla charging current"
                )
            )

        target_current = max(
            raw_current,
            self.config.min_charging_current_a,
        )

        #
        # Tesla is currently stopped.
        #
        if not self.state.charging:
            return self._handle_start_candidate(
                target_current=target_current,
                now=now,
            )

        current_difference = (
            target_current
            - self.state.current_a
        )

        #
        # Ignore small changes.
        #
        if (
            abs(current_difference)
            < self.config.current_change_threshold_a
        ):
            self._clear_pending()

            return TeslaChargingCommand(
                action="hold",
                target_current_a=self.state.current_a,
                reason=(
                    "Current change is below hysteresis "
                    "threshold"
                ),
            )

        #
        # Charging power dropped.
        #
        if current_difference < 0:
            return self._handle_current_candidate(
                target_current=target_current,
                now=now,
                hold_seconds=(
                    self.config.decrease_hold_seconds
                ),
                direction="decrease",
            )

        #
        # Charging power increased.
        #
        return self._handle_current_candidate(
            target_current=target_current,
            now=now,
            hold_seconds=(
                self.config.increase_hold_seconds
            ),
            direction="increase",
        )

    def _handle_start_candidate(
        self,
        *,
        target_current: int,
        now: float,
    ) -> TeslaChargingCommand:
        pending = self.state.pending_current_a

        #
        # First valid start candidate.
        #
        if pending is None:
            self.state.pending_current_a = (
                target_current
            )

            self.state.pending_since = now

            return TeslaChargingCommand(
                action="hold",
                target_current_a=0,
                reason=(
                    "Waiting for charging power to remain "
                    "stable before starting Tesla"
                ),
            )

        #
        # Tiny target changes do not restart the timer.
        #
        if (
            abs(target_current - pending)
            < self.config.current_change_threshold_a
        ):
            #
            # Be conservative and retain the lower
            # current observed during the stable window.
            #
            self.state.pending_current_a = min(
                pending,
                target_current,
            )

        else:
            #
            # Meaningful target change.
            # Restart the stability window.
            #
            self.state.pending_current_a = (
                target_current
            )

            self.state.pending_since = now

            return TeslaChargingCommand(
                action="hold",
                target_current_a=0,
                reason=(
                    "Charging target changed significantly; "
                    "restarting stability timer"
                ),
            )

        elapsed = (
            now
            - (
                self.state.pending_since
                if self.state.pending_since is not None
                else now
            )
        )

        if (
            elapsed
            < self.config.increase_hold_seconds
        ):
            return TeslaChargingCommand(
                action="hold",
                target_current_a=0,
                reason=(
                    "Charging power is stabilizing before "
                    "Tesla charging starts"
                ),
            )

        start_current = (
            self.state.pending_current_a
            if self.state.pending_current_a is not None
            else target_current
        )

        self.state.charging = True
        self.state.current_a = start_current

        self._clear_pending()

        return TeslaChargingCommand(
            action="start",
            target_current_a=start_current,
            reason=(
                "Charging power remained stable; "
                "Tesla charging can start"
            ),
        )

    def _handle_current_candidate(
        self,
        *,
        target_current: int,
        now: float,
        hold_seconds: int,
        direction: str,
    ) -> TeslaChargingCommand:
        pending = self.state.pending_current_a

        #
        # First candidate for an increase/decrease.
        #
        if pending is None:
            self.state.pending_current_a = (
                target_current
            )

            self.state.pending_since = now

            return TeslaChargingCommand(
                action="hold",
                target_current_a=self.state.current_a,
                reason=(
                    f"Waiting before Tesla current "
                    f"{direction}"
                ),
            )

        #
        # Small movement around the same target should
        # not restart the timer.
        #
        if (
            abs(target_current - pending)
            < self.config.current_change_threshold_a
        ):
            #
            # Always retain the lower current during
            # a stability window.
            #
            # For increases, this prevents chasing a
            # temporary sunny spike.
            #
            # For decreases, this ensures we reduce
            # enough to avoid unnecessary grid import.
            #
            self.state.pending_current_a = min(
                pending,
                target_current,
            )

        else:
            #
            # Significant change.
            #
            # Restart the hold window around the new target.
            #
            self.state.pending_current_a = (
                target_current
            )

            self.state.pending_since = now

            return TeslaChargingCommand(
                action="hold",
                target_current_a=self.state.current_a,
                reason=(
                    f"Tesla current {direction} target "
                    f"changed significantly"
                ),
            )

        elapsed = (
            now
            - (
                self.state.pending_since
                if self.state.pending_since is not None
                else now
            )
        )

        if elapsed < hold_seconds:
            return TeslaChargingCommand(
                action="hold",
                target_current_a=self.state.current_a,
                reason=(
                    f"Tesla current {direction} "
                    f"is stabilizing"
                ),
            )

        new_current = (
            self.state.pending_current_a
            if self.state.pending_current_a is not None
            else target_current
        )

        self.state.current_a = new_current

        self._clear_pending()

        return TeslaChargingCommand(
            action="set_current",
            target_current_a=new_current,
            reason=(
                f"Stable charging conditions allow "
                f"Tesla current {direction}"
            ),
        )

    def _stop(
        self,
        *,
        reason: str,
    ) -> TeslaChargingCommand:
        self._clear_pending()

        if self.state.charging:
            self.state.charging = False
            self.state.current_a = 0

            return TeslaChargingCommand(
                action="stop",
                target_current_a=0,
                reason=reason,
            )

        return TeslaChargingCommand(
            action="hold",
            target_current_a=0,
            reason=reason,
        )

    def _clear_pending(self) -> None:
        self.state.pending_current_a = None
        self.state.pending_since = None