from langflow.services.base import Service
from langflow.services.factory import ServiceFactory
from langflow.services.wasm.service import WasmService


class WasmServiceFactory(ServiceFactory):
    def __init__(self) -> None:
        super().__init__(WasmService)

    def create(self) -> Service:
        return WasmService()