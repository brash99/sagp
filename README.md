# Society for Ancient Greek Philosophy Member Database Management System

sagp/
│
├── README.md
├── .gitignore
│
├── sagp_member_db/        (submodule)
│      App 1: Raw data → Master XLSX
│      App 2: Master XLSX → SQLite
│
└── sagp_member_manager/   (submodule)
       App 3: GUI and editing

# App 1
python build_sagp_database.py

# App 2
python build_database_from_master.py \
    --input output/SAGP_Reconciliation.xlsx \
    --output output/sagp_members.db \
    --overwrite

# App 3
python main.py --db ../sagp_member_db/output/sagp_members.db
