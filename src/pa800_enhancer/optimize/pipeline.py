from ..domain.changes import ChangeSet
from .base import OptimizationContext, OptimizationModule


class OptimizationPipeline:
    def __init__(self, modules: list[OptimizationModule] | None = None) -> None:
        self.modules = modules or []

    def suggest(self, context: OptimizationContext) -> ChangeSet:
        result = ChangeSet()
        for module in self.modules:
            result.changes.extend(module.suggest(context).changes)
        return result