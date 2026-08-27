"""Shared test fixtures for MittelWerk."""

from __future__ import annotations

from decimal import Decimal

import pytest

from mittelwerk.core.models import (
    Equipment,
    EquipmentCategory,
)


@pytest.fixture
def equipment() -> dict[str, Equipment]:
    return {
        "CNC-01": Equipment(
            asset_id="CNC-01",
            name="CNC Mill Line 1",
            equipment_type=EquipmentCategory.CNC_MACHINE,
            service_interval_days=30,
            hourly_service_rate=Decimal("85.00"),
            rate_increment=Decimal("0.50"),
            hour_lot_size=Decimal("0.25"),
        ),
        "PRESS-04": Equipment(
            asset_id="PRESS-04",
            name="Hydraulic Press 400t",
            equipment_type=EquipmentCategory.HYDRAULIC_PRESS,
            service_interval_days=45,
            hourly_service_rate=Decimal("120.00"),
            rate_increment=Decimal("1.00"),
            hour_lot_size=Decimal("0.5"),
        ),
        "ROBOT-07": Equipment(
            asset_id="ROBOT-07",
            name="Robotic Welding Arm 7",
            equipment_type=EquipmentCategory.ROBOTIC_ARM,
            service_interval_days=21,
            hourly_service_rate=Decimal("110.00"),
            rate_increment=Decimal("1.00"),
            hour_lot_size=Decimal("0.25"),
        ),
    }
