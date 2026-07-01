# Society for Ancient Greek Philosophy Member Database Management System

# Society for Ancient Greek Philosophy Member Database Management System

```text
sagp/
│
├── README.md
├── .gitignore
│
├── sagp_member_db/                 (Git submodule)
│   │
│   ├── App 1
│   │     Raw membership files
│   │            │
│   │            ▼
│   │     SAGP_Reconciliation.xlsx
│   │
│   └── App 2
│         SAGP_Reconciliation.xlsx
│                    │
│                    ▼
│         sagp_members.db
│
└── sagp_member_manager/            (Git submodule)
    │
    └── App 3
          GUI for searching, editing,
          and managing the membership database
```

# App 1
python build_sagp_database.py

# App 2
python build_database_from_master.py \
    --input output/SAGP_Reconciliation.xlsx \
    --output output/sagp_members.db \
    --overwrite

# App 3
python main.py --db ../sagp_member_db/output/sagp_members.db
