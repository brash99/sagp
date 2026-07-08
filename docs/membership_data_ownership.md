# Membership Data Ownership

## Purpose

This document defines ownership of SAGP membership data after the Phase II architecture refactor.

## Import Pipeline

Directory:

    sagp_member_import/

Formerly:

    sagp_member_db/

Role:

    Convert historical and messy CSV files into a normalized bootstrap SQLite database.

Output:

    sagp_member_import/output/sagp_members.db

Ownership:

    This database is an import artifact. It is authoritative only with respect to the historical CSV import process.

It is not the live operational database once the Membership Manager is in use.

## Operational Membership Database

Directory:

    sagp_member_manager/output/

Authoritative database:

    sagp_member_manager/output/sagp_members.db

Role:

    Store the live operational membership records used and edited by the Membership Manager.

Ownership:

    Once human edits occur in the Membership Manager, this database becomes the authoritative membership database.

The import pipeline must not overwrite it.

## Ownership Transfer

The intended lifecycle is:

    Historical CSV files
            ↓
    sagp_member_import
            ↓
    Bootstrap database
            ↓
    Membership Manager initialization / enrichment
            ↓
    Operational membership database
            ↓
    Audience knowledge objects

After ownership transfers to the Membership Manager, the import database becomes a reference/import artifact only.

## Architectural Rule

Every persistent object must have an explicit owner.

For membership data:

    Import pipeline owns bootstrap data.
    Membership Manager owns operational data.
    Communications Workspace consumes Audience knowledge objects.

