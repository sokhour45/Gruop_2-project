# Small Warehouse Management System

A desktop inventory application built with Python 3.10+, Tkinter/ttk, and SQLite.
It uses only Python standard-library modules; no external package installation
is required.

## File tree

```text
python_project/
├── main.py
├── requirements.txt
└── warehouse/
    ├── __init__.py
    ├── main.py
    ├── db.py
    ├── models.py
    ├── validation.py
    ├── README.md
    └── ui/
        ├── __init__.py
        ├── common.py
        ├── dashboard.py
        ├── products.py
        ├── stock_in.py
        ├── stock_out.py
        ├── stock_movement.py
        ├── history.py
        └── reports.py
```

## Setup and run

1. Install Python 3.10 or later. On Windows, select the option to install
   Python and Tkinter (Tkinter is included with the standard Windows installer).
2. Open a terminal in the project folder.
3. Run `python main.py`.

The SQLite database `warehouse.db` is created automatically in the project
folder the first time the application starts. `requirements.txt` is included
for clarity; it lists no third-party dependencies.

## Features

- Add, edit, search, filter, and delete products.
- Product SKU uniqueness, supported category/unit selection, and numeric
  inventory validation.
- Stock receiving and issuing with confirmation, balance checks, and
  transaction history.
- Quantity adjustments made while editing a product are confirmed and logged
  as stock transactions as well.
- Dashboard with stock value, product counts, low-stock alerts, and recent
  movements.
- Visually highlighted low-stock rows in dashboard and product listing.
- Sortable tables and CSV export for inventory and transaction history.
- Password-protected login with salted PBKDF2 password hashes and logout.
- Employee registration and administrator-controlled admin, manager, and employee roles.
- Employee accounts cannot access Stock In or Stock Out.
- Employee accounts can view products and add new products, but cannot edit or delete them.
- Friendly status/error messages, keyboard submission with Enter, cancellation
  with Escape, and modal product/movement forms.
- Transactions use parameterized SQL and commit/rollback boundaries so a failed
  stock change cannot leave a partially updated balance or history record.

For a complete description of screens, workflows, validation rules, roles, and
data safety, see the project-level [Functionality Guide](../FUNCTIONALITY.md).

## Validation gate and retry behavior

`warehouse/validation.py` defines the reusable `validation_gate` and field-level
validators. Product and movement modal forms call the gate on every Save or
Submit press. It validates all fields together; when any field is invalid it
shows specific messages, highlights/refocuses the first invalid field, and
returns without closing the form. The next submission repeats the complete
gate. Stock movement then has a separate confirmation step before the atomic
database operation. Cancellation or a database error keeps the form available
for correction/retry.

## Login

On the first launch, create the administrator account with a password of at
least eight characters. Later launches require that account's username and
password before the warehouse screens are available. Use **Log out** in the
sidebar to return to the login screen. New accounts can be registered from the
login screen as employees. Administrators can use **User Accounts** to change
registered users to manager, employee, or administrator.

## Screenshots description

No screenshots are bundled. On launch, the Dashboard shows three summary
cards, a low-stock alert table with red-tinted rows, and recent stock movements.
The left navigation opens Products, Stock In, Stock Out, History, and Reports.
Product and stock movement editors appear as centered modal dialogs.
