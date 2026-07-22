from sqlalchemy import text

from balance360.database import SessionLocal

with SessionLocal() as db:
    db.execute(text("DELETE FROM serial_numbers"))
    db.execute(text("DELETE FROM invoice_lines"))
    db.execute(text("DELETE FROM invoices"))

    db.commit()
    print("Listo")
