from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from django.core.files.base import ContentFile


def generate_transaction_receipt_pdf(transaction) -> ContentFile:
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    y = height - 72
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(72, y, "BankX Transaction Receipt")
    y -= 36
    pdf.setFont("Helvetica", 12)
    lines = [
        f"Type: {transaction.get_transaction_type_display()}",
        f"Amount: ${transaction.amount}",
        f"Account: {transaction.account.account_number}",
        f"Category: {transaction.get_category_display()}",
        f"Date: {transaction.created_at:%Y-%m-%d %H:%M}",
        f"Description: {transaction.description}",
    ]
    for line in lines:
        pdf.drawString(72, y, line)
        y -= 20
    pdf.showPage()
    pdf.save()
    buffer.seek(0)
    return ContentFile(buffer.read(), name=f"receipt_{transaction.id}.pdf")

