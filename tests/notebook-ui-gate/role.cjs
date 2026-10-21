// Fixture classification only; not the product's cell identification contract.
function readRole(metadata) {
  // ipynb serializer at VS Code 1.142.0: cell.metadata.metadata.
  // Direct/legacy wrappers are read-only probe compatibility, not an API promise.
  return (metadata.metadata?.task00101Probe ?? metadata.task00101Probe ?? metadata.custom?.metadata?.task00101Probe)?.role;
}
module.exports = { readRole };
