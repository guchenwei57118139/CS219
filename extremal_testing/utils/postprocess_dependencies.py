"""
Post-process AllOpsMetaData.json to expand DependsOn relationships to include all direct and indirect parents.
"""
from typing import List, Dict, Set
from collections import defaultdict


class DependencyProcessor:
    """Process and expand operation dependencies to include all direct and indirect parents."""
    
    def __init__(self, operations: List[Dict]):
        """Initialize with a list of operations."""
        self.operations = operations
        self.operation_names = {op["Operation"] for op in operations}
        self.dependency_graph: Dict[str, Set[str]] = {}
        self._build_graph()
    
    def _build_graph(self) -> None:
        """Build a dependency graph mapping operation names to their direct dependencies."""
        graph: Dict[str, Set[str]] = defaultdict(set)
        
        for operation in self.operations:
            operation_name = operation["Operation"]
            if "DependsOn" in operation and operation["DependsOn"]:
                depends_on_value = operation["DependsOn"]
                
                # Handle both string (comma-separated) and list formats
                if isinstance(depends_on_value, str):
                    dependencies = [dep.strip() for dep in depends_on_value.split(",") if dep.strip()]
                elif isinstance(depends_on_value, list):
                    dependencies = [str(dep).strip() for dep in depends_on_value if dep]
                else:
                    dependencies = [str(depends_on_value).strip()]
                
                # Only add dependencies that exist in the operations list
                for dep in dependencies:
                    if dep in self.operation_names:
                        graph[operation_name].add(dep)
        
        self.dependency_graph = dict(graph)
    
    def _compute_transitive_dependencies_with_depth(
        self,
        operation_name: str,
        visited: Set[str] = None,
        current_depth: int = 0
    ) -> Dict[str, int]:
        """Compute all direct and indirect dependencies with their depth in the dependency tree."""
        if visited is None:
            visited = set()
        
        if operation_name in visited:
            return {}  # Cycle detected, return empty to avoid infinite recursion
        
        visited.add(operation_name)
        dependency_depths: Dict[str, int] = {}
        
        if operation_name in self.dependency_graph:
            direct_deps = self.dependency_graph[operation_name]
            
            # Direct dependencies are at current_depth (youngest from this node's perspective)
            for dep in direct_deps:
                if dep not in dependency_depths:
                    dependency_depths[dep] = current_depth
            
            # Recursively get indirect dependencies (deeper = older ancestors)
            for dep in direct_deps:
                # Recursive call starts at depth 0 for the child node
                indirect_deps = self._compute_transitive_dependencies_with_depth(
                    dep, visited.copy(), 0
                )
                for indirect_dep, indirect_depth in indirect_deps.items():
                    # Add 1 to convert depth relative to 'dep' to depth relative to 'operation_name'
                    # Keep the maximum depth (deepest = eldest ancestor)
                    adjusted_depth = indirect_depth + 1
                    if indirect_dep not in dependency_depths or dependency_depths[indirect_dep] < adjusted_depth:
                        dependency_depths[indirect_dep] = adjusted_depth
        
        return dependency_depths
    
    def expand_dependencies(self) -> List[Dict]:
        """Expand DependsOn to include all direct and indirect parent operations, ordered from eldest to youngest ancestor."""
        expanded_operations = []
        
        for operation in self.operations:
            operation_name = operation["Operation"]
            expanded_operation = operation.copy()
            
            # Get all transitive dependencies with their depths
            dependency_depths = self._compute_transitive_dependencies_with_depth(operation_name)
            
            if dependency_depths:
                # Sort by depth descending (eldest first), then by name for consistency
                sorted_deps = sorted(
                    dependency_depths.keys(),
                    key=lambda dep: (-dependency_depths[dep], dep)
                )
                expanded_operation["DependsOn"] = sorted_deps
            else:
                # Remove DependsOn if empty or not present
                expanded_operation.pop("DependsOn", None)
            
            expanded_operations.append(expanded_operation)
        
        return expanded_operations


def expand_dependencies(operations: List[Dict]) -> List[Dict]:
    """Convenience function to expand dependencies for a list of operations."""
    processor = DependencyProcessor(operations)
    return processor.expand_dependencies()
