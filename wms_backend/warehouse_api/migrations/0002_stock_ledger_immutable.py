from django.db import migrations


def install_ledger_guards(apps, schema_editor):
    vendor = schema_editor.connection.vendor
    with schema_editor.connection.cursor() as cursor:
        if vendor == "postgresql":
            cursor.execute(
                """
                CREATE OR REPLACE FUNCTION warehouse_ledger_immutable()
                RETURNS trigger AS $$
                BEGIN
                    RAISE EXCEPTION 'stock ledger rows are immutable';
                END;
                $$ LANGUAGE plpgsql;
                """
            )
            cursor.execute(
                """
                CREATE TRIGGER warehouse_ledger_no_mutation
                BEFORE UPDATE OR DELETE ON warehouse_api_stockledger
                FOR EACH ROW EXECUTE FUNCTION warehouse_ledger_immutable();
                """
            )
        elif vendor == "sqlite":
            cursor.execute(
                """
                CREATE TRIGGER warehouse_ledger_no_update
                BEFORE UPDATE ON warehouse_api_stockledger
                BEGIN
                    SELECT RAISE(ABORT, 'stock ledger rows are immutable');
                END;
                """
            )
            cursor.execute(
                """
                CREATE TRIGGER warehouse_ledger_no_delete
                BEFORE DELETE ON warehouse_api_stockledger
                BEGIN
                    SELECT RAISE(ABORT, 'stock ledger rows are immutable');
                END;
                """
            )


def remove_ledger_guards(apps, schema_editor):
    vendor = schema_editor.connection.vendor
    with schema_editor.connection.cursor() as cursor:
        if vendor == "postgresql":
            cursor.execute("DROP TRIGGER IF EXISTS warehouse_ledger_no_mutation ON warehouse_api_stockledger")
            cursor.execute("DROP FUNCTION IF EXISTS warehouse_ledger_immutable()")
        elif vendor == "sqlite":
            cursor.execute("DROP TRIGGER IF EXISTS warehouse_ledger_no_update")
            cursor.execute("DROP TRIGGER IF EXISTS warehouse_ledger_no_delete")


class Migration(migrations.Migration):
    dependencies = [("warehouse_api", "0001_initial")]
    operations = [migrations.RunPython(install_ledger_guards, remove_ledger_guards)]
