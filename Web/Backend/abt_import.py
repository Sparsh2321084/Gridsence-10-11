"""Compatibility exports for the weekly ABT importer."""

from Web.Backend.integrations.abt_import import (
    ingest_abt_week,
    main,
    read_abt_week,
    scan_abt_folder,
)

__all__ = ["ingest_abt_week", "read_abt_week", "scan_abt_folder"]

if __name__ == "__main__":
    raise SystemExit(main())
