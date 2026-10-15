# Data Retention & Access Control Spec (attachment — slow)

1.1 All user records must be retained for 7 years after account deactivation.
1.2 Access to PII requires role-based authorization; roles: owner, admin, viewer.
1.3 Every PII read must be logged with actor, timestamp, and record id.
1.4 Encryption at rest: AES-256; encryption in transit: TLS 1.2 or higher.
1.5 Backup frequency: daily incremental, weekly full; retention 30 days.
1.6 Deletion requests must be honored within 30 days and purged from all replicas.
1.7 Cross-region data transfer is prohibited unless a Standard Contractual
    Clause is in place.
1.8 Audit logs are immutable and retained for 10 years.
1.9 Periodic access review every 90 days; stale access is revoked automatically.
1.10 Incident response: PII breach notification within 72 hours to the data
      protection officer and affected individuals where risk is high.
