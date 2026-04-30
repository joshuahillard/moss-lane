"""
Dispatcher Package — Multi-Wallet Trade Routing

Implements the routing-decision layer that sits between scanner-side signal
production and burner-process trade execution. Per ADR-007 (2026-04-29),
this layer holds zero private keys and signs zero transactions.

Modules:
  route_trade — TradeRouter, RouteDecision, topology + zero-key validators
"""

from .route_trade import (
    TradeRouter,
    RouteDecision,
    RouteRejection,
    RouteRejectionReason,
    TopologyError,
    validate_topology,
    validate_no_keys_in_env,
)

__all__ = [
    "TradeRouter",
    "RouteDecision",
    "RouteRejection",
    "RouteRejectionReason",
    "TopologyError",
    "validate_topology",
    "validate_no_keys_in_env",
]
