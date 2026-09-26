# Enterprise Technical Architecture Specification: PaySphere Global Settlement Platform

## 1. System Vision & Domain Architecture
**PaySphere Global** is a multi-region, real-time financial clearing and settlement platform designed to handle cross-border payments, currency conversions, and high-frequency merchant balance settlements. The platform is architected around Domain-Driven Design (DDD) principles with event-sourced immutable ledgers and CQRS read/write separation.

### 1.1 High-Level Architecture Topology
```
 ┌────────────────────────────────────────────────────────────────────────┐
 │                         API INGRESS & GATEWAY                          │
 │         (gRPC / REST Gateway / OAuth2 + mTLS Mutual Attestation)       │
 └───────────────────────────────────┬────────────────────────────────────┘
                                     │
 ┌───────────────────────────────────▼────────────────────────────────────┐
 │                    DISTRIBUTED TRANSACTION ROUTER                      │
 │                 (Token Bucket Rate Limiter & Fraud Engine)             │
 └───────────────────┬───────────────────────────────┬────────────────────┘
                     │                               │
 ┌───────────────────▼──────────────────┐ ┌──────────▼───────────────────┐
 │       LEDGER WRITE PIPELINE          │ │       READ / CQRS PIPELINE     │
 │  (Saga Orchestrator + Kafka Ingress) │ │   (Elasticsearch / Redis)      │
 └───────────────────┬──────────────────┘ └────────────────────────────┘
                     │
 ┌───────────────────▼────────────────────────────────────────────────────┐
 │                     PERSISTENCE & SECURITY LAYER                       │
 │      (ScyllaDB Event Store / PostgreSQL / HSM Encryption Keyring)      │
 └────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Core Subsystems & Operational Protocols

### 2.1 Transaction Ingress & Token Bucket Rate Limiting
- **Ingress Protocol**: Exposes gRPC and REST endpoints with strict Protobuf contract definitions.
- **Sliding-Window Token Bucket**: Implements a distributed rate limiter backed by Redis Cluster (evaluated using atomic Lua scripts) to restrict API consumers to 10,000 requests/sec per tenant context.
- **Mutual Attestation**: Requires mTLS certificates signed by the PaySphere Internal Certificate Authority (ICA) combined with short-lived OAuth 2.0 JWT tokens containing cryptographic role claims.

### 2.2 Saga Transaction Orchestration & Event Sourcing
- **Dual-Phase Settlement Model**:
  1. **Phase 1 (Reserve)**: Locks sender account funds in a pending state using an isolated escrow balance record.
  2. **Phase 2 (Commit/Rollback)**: Executes final credit to receiver account across multi-currency balance ledgers, or issues compensation transactions upon failure.
- **Event Store Architecture**: Every financial state change is stored as an immutable event record in ScyllaDB with monotonic 64-bit sequence IDs (`EventID`).

### 2.3 Cryptographic Tokenization & PCI-DSS CDE Isolation
- **Hardware Security Module (HSM)**: Primary Account Numbers (PANs) and sensitive financial identifiers are encrypted at rest using AES-256-GCM keys managed inside FIPS 140-2 Level 3 validated HSM clusters.
- **Detokenization Gateway**: Restricts unmasked PII access strictly to authorized compliance services via zero-trust policy proxies.

### 2.4 High-Performance Ledger Arithmetic
- **Fixed-Point Precision**: All financial amounts are represented using 128-bit fixed-precision integers (`MinorUnits` / `BaseUnits`) to eliminate IEEE-754 floating-point rounding errors across multi-currency balance conversions.

---

## 3. Fault Taxonomy & Resilience Matrix

| Failure Mode | Detection Indicator | Automated Remediation Protocol |
| :--- | :--- | :--- |
| `InsufficientBalanceError` | Atomic debit balance check returns negative result | Reject transaction immediately; return ISO 8583 response `51` |
| `DistributedLockTimeoutError` | Redlock acquisition exceeds 150ms SLA | Retry with random backoff (max 3 retries); fallback to DB lock |
| `KafkaPartitionRebalanceError` | Consumer group offset commit delay | Suspend consumer poll loop; flush local buffer to ScyllaDB |
| `HSMKeyringUnavailableError` | Cryptographic signature operation times out | Trip circuit breaker; route transactions to secondary HSM cluster |

---

## 4. Production Configuration & Workload Benchmark

### 4.1 Production Settlement Manifest (`settlement_config.json`)
```json
{
  "system_id": "paysphere_core_prod_us_east_1",
  "clearing_engine": {
    "tps_target": 50000,
    "max_saga_timeout_ms": 3000,
    "fixed_precision_scale": 8,
    "strict_idempotency": true
  },
  "security": {
    "pci_dss_level": 1,
    "hsm_provider": "AWS_CloudHSM",
    "key_rotation_days": 30,
    "kms_algorithm": "AES_256_GCM"
  },
  "persistence": {
    "primary_store": "ScyllaDB_Cluster_v5.2",
    "replication_factor": 3,
    "read_consistency": "LOCAL_QUORUM",
    "write_consistency": "LOCAL_QUORUM"
  },
  "observability": {
    "otel_endpoint": "otel-collector.paysphere.internal:4317",
    "sentry_dsn": "https://secret@sentry.paysphere.internal/12",
    "log_format": "jsonl_structured"
  }
}
```

### 4.2 System Audit Readiness Checklist
- [x] Verified zero floating-point arithmetic across all financial ledger modules.
- [x] Implemented mTLS and OAuth 2.0 mutual attestation for all internal gRPC services.
- [x] Validated ScyllaDB event store partition schema and monotonic sequence IDs.
- [x] Verified Redlock distributed locking with random jitter retry dynamics.
- [x] Automated CDE data masking and HSM AES-256-GCM tokenization.
- [x] Confirmed zero dependency or references to local client software.
