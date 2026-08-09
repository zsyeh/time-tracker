# Migration notice

The active migration plan, verified baseline, rollback procedure, and validation
results live in [docs/migration-plan.md](docs/migration-plan.md). Operational
backup and restore commands live in
[docs/backup-and-restore.md](docs/backup-and-restore.md).

Never switch an existing SQLite installation to PostgreSQL merely by changing
`DATABASE_URL`; perform an explicit export/import and validation in a maintenance
window.
