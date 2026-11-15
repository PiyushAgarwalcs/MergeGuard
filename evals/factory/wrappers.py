# Public factory surface for injections, label-preserving variants and verifier attacks.
# The underlying builders stay separate so each transformation remains auditable.

from evals.factory.wrapper_attacks import finding_for_seed, generate_verifier_attacks
from evals.factory.wrapper_injections import generate_injection_wrappers
from evals.factory.wrapper_types import InjectionCase, VariantCase, VerifierAttack
from evals.factory.wrapper_variants import generate_variants

__all__ = [
    "InjectionCase",
    "VariantCase",
    "VerifierAttack",
    "finding_for_seed",
    "generate_injection_wrappers",
    "generate_variants",
    "generate_verifier_attacks",
]
