from langflow.services.base import Service
from langflow.services.factory import ServiceFactory
from langflow.services.wasmcloud.service import WasmCloudService


class WasmCloudServiceFactory(ServiceFactory):
    def __init__(self) -> None:
        super().__init__(WasmCloudService)

    def create(self) -> Service:
        return WasmCloudService()