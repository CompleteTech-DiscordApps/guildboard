"""Expose the T12 experiment suite to unittest discovery."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


def load_tests(loader, standard_tests, pattern):
    # Preserve the direct runner used by historical commands. The evidence
    # hashes refer to the script bytes at the commits recorded in the receipts.
    path = Path(__file__).with_name("t12-test-experiments.py")
    spec = spec_from_file_location("t12_experiments", path)
    experiments = module_from_spec(spec)
    spec.loader.exec_module(experiments)
    return loader.loadTestsFromModule(experiments)
