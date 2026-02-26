from openatoms.adapters import (
    ArduinoCloudAdapter,
    BambuAdapter,
    HomeAssistantAdapter,
    OpentronsAdapter,
    ViamAdapter,
)
from openatoms.driver_conformance import run_conformance


def test_driver_conformance_suite():
    adapters = [
        OpentronsAdapter,
        ViamAdapter,
        BambuAdapter,
        HomeAssistantAdapter,
        ArduinoCloudAdapter,
    ]
    for adapter_cls in adapters:
        results = run_conformance(adapter_cls)
        failed = [result for result in results if not result.passed]
        assert not failed, f"{adapter_cls.__name__} failed conformance: {failed}"
